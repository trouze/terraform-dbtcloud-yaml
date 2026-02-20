"""Adopt step page — automated terraform state rm + import for adopted resources.

PRD 43.02: Dedicated Adoption Terraform Step.

This page sits between Match and Configure in the Migration workflow. It automates
the terraform state rm + terraform apply (import) cycle that was previously manual.
"""

import asyncio
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep
from importer.web.components.terminal_output import TerminalOutput
from importer.web.utils.terraform_import import (
    generate_state_rm_commands,
)
from importer.web.utils.terraform_helpers import (
    OutputBudget,
    emit_process_output,
    get_terraform_env as _get_terraform_env_shared,
    resolve_deployment_paths,
)
from importer.web.utils.generate_pipeline import run_generate_pipeline

logger = logging.getLogger(__name__)

# Style constants (matching deploy.py)
DBT_ORANGE = "#FF694A"
STATUS_SUCCESS = "#22c55e"
STATUS_ERROR = "#ef4444"
STATUS_WARNING = "#f59e0b"
PHASE_COLORS = {
    "backup": "#6366f1",     # indigo
    "state_rm": "#f59e0b",   # amber
    "write_imports": "#8b5cf6",  # violet
    "init": "#3b82f6",       # blue
    "apply": "#22c55e",      # green
    "verify": "#06b6d4",     # cyan
}


def _dbg_673991(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    """Temporary debug hook (disabled)."""
    _ = (hypothesis_id, location, message, data)


def _dbg_db419a(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "db419a",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(
            "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-db419a.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


def _get_terraform_dir(state: AppState) -> Path:
    """Resolve the terraform directory from state.

    Delegates to the canonical ``resolve_deployment_paths`` helper and
    returns only the ``tf_path`` component for backward compatibility.
    """
    tf_path, _yaml_file, _baseline = resolve_deployment_paths(state)
    return tf_path


def _get_terraform_env(state: AppState) -> dict:
    """Get environment variables for terraform commands.

    Delegates to ``terraform_helpers.get_terraform_env`` — the single
    source of truth for TF env construction.
    """
    return _get_terraform_env_shared(state)


# ---------------------------------------------------------------------------
# Workflow state persistence helpers
# ---------------------------------------------------------------------------

def _persist_adopt_workflow_state(
    state: AppState,
    *,
    complete: bool,
    skipped: bool = False,
    imported_count: int = 0,
) -> None:
    """Persist adopt step outcome to target-intent.json so it survives restarts."""
    try:
        mgr = state.get_target_intent_manager()
        intent = mgr.load()
        if intent is None:
            return  # No target intent yet — nothing to persist into
        intent.set_adopt_state(
            complete=complete,
            skipped=skipped,
            imported_count=imported_count,
        )
        mgr.save(intent)
        logger.info(f"Persisted adopt workflow state: complete={complete}, skipped={skipped}, imported={imported_count}")
    except Exception as e:
        logger.warning(f"Failed to persist adopt workflow state: {e}")


def _restore_adopt_workflow_state(state: AppState) -> None:
    """Restore adopt step state from target-intent.json into in-memory DeployState."""
    try:
        mgr = state.get_target_intent_manager()
        intent = mgr.load()
        if intent is None:
            return
        adopt = intent.get_adopt_state()
        if not adopt:
            return
        state.deploy.adopt_step_complete = adopt.get("complete", False)
        state.deploy.adopt_step_skipped = adopt.get("skipped", False)
        state.deploy.adopt_step_imported_count = adopt.get("imported_count", 0)
        if state.deploy.adopt_step_complete:
            state.deploy.adopt_step_status = "complete"
            logger.info(
                f"Restored adopt state from disk: complete={state.deploy.adopt_step_complete}, "
                f"skipped={state.deploy.adopt_step_skipped}, imported={state.deploy.adopt_step_imported_count}"
            )
    except Exception as e:
        logger.warning(f"Failed to restore adopt workflow state: {e}")


def _clear_adopt_workflow_state(state: AppState) -> None:
    """Clear adopt state from target-intent.json (for re-run)."""
    try:
        mgr = state.get_target_intent_manager()
        intent = mgr.load()
        if intent is None:
            return
        intent.clear_adopt_state()
        mgr.save(intent)
        logger.info("Cleared adopt workflow state from disk")
    except Exception as e:
        logger.warning(f"Failed to clear adopt workflow state: {e}")


def _load_report_items(state: AppState, target: bool = False) -> list:
    """Load report items from source or target fetch (mirrors match.py)."""
    import json as _json
    report_file = (state.target_fetch.last_report_items_file if target
                   else state.fetch.last_report_items_file)
    if not report_file:
        return []
    try:
        p = Path(report_file)
        if p.exists():
            return _json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Error loading report items: %s", exc)
    return []


def _reconstruct_state_result(state: AppState):
    """Reconstruct StateReadResult from persisted reconcile_state_resources (mirrors match.py)."""
    if not state.deploy.reconcile_state_loaded or not state.deploy.reconcile_state_resources:
        return None
    import re
    from importer.web.utils.terraform_state_reader import StateReadResult, StateResource
    result = StateReadResult(success=True)
    for res_data in state.deploy.reconcile_state_resources:
        resource_index = res_data.get("resource_index")
        address = res_data.get("address", "")
        if resource_index is None and address and "[" in address:
            match = re.search(r'\["([^"]+)"\]$', address)
            if match:
                resource_index = match.group(1)
            else:
                match = re.search(r'\[(\d+)\]$', address)
                if match:
                    resource_index = match.group(1)
        resource = StateResource(
            address=address,
            tf_type=res_data.get("tf_type", ""),
            element_code=res_data.get("element_code", ""),
            tf_name=res_data.get("tf_name", ""),
            dbt_id=res_data.get("dbt_id"),
            name=res_data.get("name"),
            project_id=res_data.get("project_id"),
            attributes=res_data.get("attributes", {}),
            resource_index=resource_index,
        )
        result.resources.append(resource)
        if resource.dbt_id is not None:
            result.resources_by_id[(resource.element_code, resource.dbt_id)] = resource
    return result


def _get_grid_rows_from_state(state: AppState) -> list[dict]:
    """Build grid rows using build_grid_data (same logic as the match page).

    This ensures drift-based action computation is consistent between the
    Match page and the Adopt page — no stale ``action='adopt'`` leaks through.
    Falls back to raw confirmed_mappings if report data is unavailable.
    """
    from importer.web.components.match_grid import build_grid_data

    source_items = _load_report_items(state, target=False)
    target_items = _load_report_items(state, target=True)

    # region agent log
    _dbg_db419a(
        "H36",
        "adopt.py:_get_grid_rows_from_state",
        "loaded report items for adopt grid",
        {
            "source_items_count": len(source_items),
            "target_items_count": len(target_items),
            "has_source_report": bool(state.fetch.last_report_items_file),
            "has_target_report": bool(state.target_fetch.last_report_items_file),
            "source_report_path": state.fetch.last_report_items_file or "",
            "target_report_path": state.target_fetch.last_report_items_file or "",
        },
    )
    # endregion
    if not source_items or not target_items:
        # region agent log
        _dbg_db419a(
            "H37",
            "adopt.py:_get_grid_rows_from_state",
            "falling back to confirmed mappings due missing report items",
            {
                "source_items_count": len(source_items),
                "target_items_count": len(target_items),
                "confirmed_mappings_count": len(state.map.confirmed_mappings or []),
            },
        )
        # endregion
        # Fall back: return raw confirmed_mappings when report files are gone
        return _get_grid_rows_from_confirmed_mappings_fallback(state)

    # Apply source selection filter (mirrors match.py)
    try:
        from importer.web.utils.selection_manager import SelectionManager
        sm = SelectionManager(
            account_id=state.source_account.account_id or "unknown",
            base_url=state.source_account.host_url,
        )
        sm.load()
        selected_ids = sm.get_selected_ids()
        if selected_ids:
            source_items = [i for i in source_items if i.get("element_mapping_id") in selected_ids]
    except Exception:
        pass  # If selection manager not available, use all source items

    state_result = _reconstruct_state_result(state)

    rejected_keys = (state.map.rejected_suggestions
                     if isinstance(state.map.rejected_suggestions, set)
                     else set(state.map.rejected_suggestions))
    clone_configs = getattr(state.map, "cloned_resources", [])

    # Get protection intent manager for effective protection lookup (matches match.py)
    protection_intent_manager = state.get_protection_intent_manager()

    # region agent log
    _dbg_673991(
        "H2",
        "adopt.py:_get_grid_rows_from_state",
        "build_grid_data inputs",
        {
            "has_intent_mgr": protection_intent_manager is not None,
            "protected_resources_count": len(state.map.protected_resources or set()),
            "source_items_count": len(source_items),
            "target_items_count": len(target_items),
            "confirmed_mappings_count": len(state.map.confirmed_mappings or []),
        },
    )
    # endregion

    grid_data = build_grid_data(
        source_items,
        target_items,
        state.map.confirmed_mappings,
        rejected_keys,
        clone_configs,
        state_result=state_result,
        protected_resources=state.map.protected_resources,
        protection_intent_manager=protection_intent_manager,
    )
    # region agent log
    _dbg_db419a(
        "H38",
        "adopt.py:_get_grid_rows_from_state",
        "build_grid_data completed for adopt page",
        {
            "grid_rows_count": len(grid_data),
            "state_result_loaded": state_result is not None,
            "confirmed_mappings_count": len(state.map.confirmed_mappings or []),
            "adopt_action_rows": sum(1 for r in grid_data if r.get("action") == "adopt"),
        },
    )
    # endregion

    return grid_data


def _get_grid_rows_from_confirmed_mappings_fallback(state: AppState) -> list[dict]:
    """Fallback: return rows from raw confirmed_mappings when report files are unavailable."""
    rows = []
    for mapping in state.map.confirmed_mappings:
        resource_type = mapping.get("resource_type", "")
        rows.append({
            "source_key": mapping.get("source_key", ""),
            "source_type": mapping.get("source_type", resource_type or ""),
            "source_name": mapping.get("source_name", ""),
            "target_id": mapping.get("target_id", ""),
            "target_name": mapping.get("target_name", ""),
            "action": mapping.get("action", "match"),
            "protected": mapping.get("protected", False),
            "drift_status": mapping.get("drift_status", ""),
            "project_name": mapping.get("project_name", ""),
            "project_id": mapping.get("project_id", ""),
            "state_address": mapping.get("state_address", ""),
            "is_target_only": mapping.get("is_target_only", False),
        })
    return rows


# Drift statuses that indicate the resource can be imported into TF state.
# Include "no_state" so mapped global groups (e.g. owner/everyone) remain
# visible/editable on Adopt when they are not yet tracked in Terraform state.
_ADOPTABLE_DRIFT = {"not_in_state", "id_mismatch", "attr_mismatch", "no_state"}


def _compute_adopt_summary(
    grid_rows: list[dict],
    confirmed_mappings=None,
) -> dict:
    """Compute summary counts for the adopt step.

    Identifies resources that need adoption based on drift status (not in TF
    state, ID mismatch, or attribute mismatch) AND that have a matched
    target_id.  Only resources explicitly marked 'adopt' in confirmed_mappings
    are set to adopt; everything else defaults to 'ignore'.

    The lookup handles a key mismatch: build_grid_data may return
    source-matched rows with source_key="member" while confirmed_mappings
    stores the action under source_key="target__member".  Both key formats
    are checked.

    Returns dict with:
        adopt_count: Total resources to import (action=adopt)
        rm_count: Resources needing state rm first (ID mismatch)
        protected_count: Protected resources in the adopt set
        adopt_rows: ALL adoptable rows (including ignored ones for display)
        state_rm_commands: List of terraform state rm command strings
    """
    def _normalize_project_key(value: str) -> str:
        key = (value or "").strip().lstrip("↳").strip()
        if not key:
            return ""
        if key.startswith("target__"):
            key = key[len("target__"):]
        if key.startswith("PRJ:"):
            key = key.split(":", 1)[1]
        if key.startswith("dbt_ep_"):
            key = key[len("dbt_ep_"):]
        return key

    # Build a lookup from confirmed_mappings keyed by source_key
    cm_by_key: dict[str, str] = {}
    project_id_by_project_key: dict[str, str] = {}
    if confirmed_mappings:
        for m in confirmed_mappings:
            sk = m.get("source_key", "")
            cm_by_key[sk] = m.get("action", "match")
            m_type = str(m.get("resource_type") or m.get("source_type") or "")
            if m_type != "PRJ":
                continue
            m_pid = m.get("target_id") or m.get("project_id")
            if not m_pid:
                continue
            for raw in (
                m.get("project_name"),
                m.get("source_name"),
                m.get("source_key"),
                m.get("target_name"),
            ):
                normalized = _normalize_project_key(str(raw or ""))
                if normalized:
                    project_id_by_project_key[normalized] = str(m_pid)

    # Filter by drift status — these resources need to be imported into TF.
    # Action source is confirmed_mappings only (explicit user intent).
    # This avoids stale/default grid actions accidentally adopting resources
    # (e.g. target-only groups) that were not explicitly selected.
    adopt_rows = []
    rows_without_confirmed_action = 0
    rows_using_row_action = 0
    for r in grid_rows:
        # Target-only rows are informational and can be very large in count;
        # keep Adopt focused on source-selected resources.
        if r.get("is_target_only"):
            continue
        if r.get("drift_status") in _ADOPTABLE_DRIFT and r.get("target_id"):
            source_key = r.get("source_key", "")

            # Look up in confirmed_mappings: try exact key, then target__ variant
            cm_action = cm_by_key.get(source_key)
            if cm_action is None and not source_key.startswith("target__"):
                cm_action = cm_by_key.get(f"target__{source_key}")

            # Only adopt if explicitly "adopt" in confirmed_mappings.
            if cm_action == "adopt":
                r["action"] = "adopt"
                if (
                    r.get("source_type") == "REP"
                    and not r.get("project_id")
                ):
                    for raw in (
                        r.get("project_name"),
                        r.get("source_name"),
                        r.get("source_key"),
                        r.get("target_name"),
                    ):
                        normalized = _normalize_project_key(str(raw or ""))
                        if not normalized:
                            continue
                        candidate_project_id = project_id_by_project_key.get(normalized)
                        if candidate_project_id:
                            r["project_id"] = candidate_project_id
                            break
            else:
                if cm_action is None:
                    rows_without_confirmed_action += 1
                r["action"] = "ignore"
            adopt_rows.append(r)

    # region agent log
    _dbg_db419a(
        "H55",
        "adopt.py:_compute_adopt_summary",
        "resolved adopt actions from confirmed mappings only",
        {
            "grid_rows_count": len(grid_rows),
            "adopt_rows_count": len(adopt_rows),
            "confirmed_mappings_count": len(cm_by_key),
            "rows_without_confirmed_action": rows_without_confirmed_action,
            "rows_using_row_action": rows_using_row_action,
            "adopt_source_type_counts": {
                str(k): int(v)
                for k, v in __import__("collections").Counter(
                    str(r.get("source_type", "")) for r in adopt_rows if r.get("action") == "adopt"
                ).items()
            },
            "project_id_lookup_keys": sorted(project_id_by_project_key.keys())[:30],
            "rep_adopt_missing_project_id_count": sum(
                1
                for r in adopt_rows
                if r.get("action") == "adopt"
                and r.get("source_type") == "REP"
                and not r.get("project_id")
            ),
        },
    )
    # endregion

    # region agent log
    grp_rows = [r for r in grid_rows if r.get("source_type") == "GRP"]
    grp_not_adoptable = [
        {
            "source_key": r.get("source_key"),
            "source_name": r.get("source_name"),
            "drift_status": r.get("drift_status"),
            "has_target_id": bool(r.get("target_id")),
        }
        for r in grp_rows
        if not (r.get("drift_status") in _ADOPTABLE_DRIFT and r.get("target_id"))
    ]
    _dbg_673991(
        "H2",
        "adopt.py:_compute_adopt_summary",
        "adoptability filter results",
        {
            "grid_rows_count": len(grid_rows),
            "grp_rows_count": len(grp_rows),
            "grp_not_adoptable": grp_not_adoptable[:20],
            "adoptable_drift_values": sorted(list(_ADOPTABLE_DRIFT)),
        },
    )
    # endregion

    adopt_count = sum(1 for r in adopt_rows if r.get("action") == "adopt")
    protected_count = sum(1 for r in adopt_rows if r.get("protected") and r.get("action") == "adopt")
    state_rm_cmds = generate_state_rm_commands(grid_rows) if adopt_rows else []

    return {
        "adopt_count": adopt_count,
        "rm_count": len(state_rm_cmds),
        "protected_count": protected_count,
        "adopt_rows": adopt_rows,
        "state_rm_commands": state_rm_cmds,
    }


def _terraform_declares_variable(tf_path: Path, variable_name: str) -> bool:
    """Return True when the root module declares the given Terraform variable."""
    pattern = re.compile(rf'variable\s+"{re.escape(variable_name)}"')
    for tf_file in tf_path.glob("*.tf"):
        try:
            if pattern.search(tf_file.read_text(encoding="utf-8")):
                return True
        except Exception:
            continue
    return False


def _invalidate_adopt_artifacts_for_action_change(
    tf_path: Path,
    adopt_grid_data: list[dict],
    new_action: str,
    adopt_count: int,
    source_yaml_file: Optional[str],
) -> dict:
    """Invalidate adopt artifacts after action changes.

    Removes stale adopt artifacts and, when unselecting target-only resources,
    cleans stale YAML entries. If adopt scope becomes empty, reset deployment
    YAML to source-normalized YAML and regenerate HCL.
    """
    removed_imports = False
    removed_plan = False
    cleaned_yaml_entries = 0
    regenerated_hcl_after_cleanup = False
    reset_deployment_yaml_from_source = False
    reset_source_yaml_path = None
    cleanup_error = None
    try:
        imports_file = tf_path / "adopt_imports.tf"
        if imports_file.exists():
            imports_file.unlink()
            removed_imports = True

        adopt_plan_file = tf_path / "adopt.tfplan"
        if adopt_plan_file.exists():
            adopt_plan_file.unlink()
            removed_plan = True

        if new_action in ("ignore", "unadopt"):
            from importer.web.utils.adoption_yaml_updater import cleanup_unadopted_yaml_configs
            from importer.yaml_converter import YamlToTerraformConverter

            deployment_yaml = tf_path / "dbt-cloud-config.yml"
            cleaned_yaml_path, cleaned_yaml_entries = cleanup_unadopted_yaml_configs(
                str(deployment_yaml),
                adopt_grid_data,
            )
            if cleaned_yaml_entries > 0:
                converter = YamlToTerraformConverter()
                converter.convert(str(cleaned_yaml_path), str(tf_path))
                regenerated_hcl_after_cleanup = True

            # Reset deployment YAML to source-normalized scope when no adopts remain.
            if adopt_count == 0 and source_yaml_file:
                source_yaml = Path(source_yaml_file)
                if source_yaml.exists():
                    shutil.copy2(str(source_yaml), str(deployment_yaml))
                    converter = YamlToTerraformConverter()
                    converter.convert(str(deployment_yaml), str(tf_path))
                    regenerated_hcl_after_cleanup = True
                    reset_deployment_yaml_from_source = True
                    reset_source_yaml_path = str(source_yaml)
    except Exception as _cleanup_err:
        cleanup_error = str(_cleanup_err)

    return {
        "removed_imports": removed_imports,
        "removed_plan": removed_plan,
        "cleaned_yaml_entries": cleaned_yaml_entries,
        "regenerated_hcl_after_cleanup": regenerated_hcl_after_cleanup,
        "reset_deployment_yaml_from_source": reset_deployment_yaml_from_source,
        "reset_source_yaml_path": reset_source_yaml_path,
        "cleanup_error": cleanup_error,
    }


def _emit_bounded_terminal_output(
    terminal: TerminalOutput,
    *,
    phase_name: str,
    stdout: str,
    stderr: str,
    stdout_budget: Optional[OutputBudget] = None,
    stderr_budget: Optional[OutputBudget] = None,
    on_stdout_line: Optional[Callable[[str], None]] = None,
    on_stderr_line: Optional[Callable[[str], None]] = None,
) -> None:
    """Emit process output to terminal with bounded line budgets."""
    emit_process_output(
        stdout,
        stderr,
        on_stdout_line=on_stdout_line or (lambda line: terminal.info_auto(f"  {line}")),
        on_stderr_line=on_stderr_line or (lambda line: terminal.warning(f"  {line}")),
        stdout_budget=stdout_budget,
        stderr_budget=stderr_budget,
        on_omitted=lambda omitted: terminal.warning(
            f"Large {phase_name} output detected; omitted {omitted} line(s) from terminal view."
        ),
    )


# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------

async def _run_adopt_plan(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    summary: dict,
    tf_path: Path,
    on_plan_ready: Callable[[str], None] = None,
    on_failure: Callable[[str], None] = None,
):
    """Run phases 1-6 of adoption: backup, state_rm, inject_config, write_imports, init, plan.

    After a successful plan the saved plan file (``adopt.tfplan``) is ready
    for ``_run_adopt_apply`` to execute.

    Returns the raw plan stdout on success, or None on failure.
    """
    adopt_rows = summary["adopt_rows"]
    state_rm_cmds = summary["state_rm_commands"]
    _adopt_project_rows = [
        r for r in adopt_rows
        if r.get("action") == "adopt" and r.get("source_type") == "PRJ"
    ]
    _adopt_non_project_only = bool(summary.get("adopt_count", 0) > 0 and not _adopt_project_rows)
    # region agent log
    _dbg_673991(
        "H1",
        "adopt.py:_run_adopt_plan:entry",
        "adopt plan starting",
        {
            "adopt_count": summary.get("adopt_count", 0),
            "row_count": len(adopt_rows),
            "adopt_non_project_only": _adopt_non_project_only,
            "adopt_project_keys": sorted([
                str(r.get("source_key") or r.get("source_name"))
                for r in _adopt_project_rows
            ])[:50],
        },
    )
    # endregion

    state.deploy.adopt_step_running = True
    state.deploy.adopt_step_status = "backup"
    save_state()

    env = _get_terraform_env(state)
    tfstate_file = tf_path / "terraform.tfstate"
    backup_file = tf_path / "terraform.tfstate.adopt-backup"

    try:
        # ── Phase 1: Backup ──────────────────────────────────────────────
        terminal.set_title("Output — BACKUP")
        terminal.info("━━━ PHASE 1: STATE BACKUP ━━━")

        if tfstate_file.exists():
            shutil.copy2(str(tfstate_file), str(backup_file))
            state.deploy.adopt_step_backup_path = str(backup_file)
            terminal.success(f"✓ State backed up to {backup_file.name}")
        else:
            terminal.info("No terraform.tfstate found — skipping backup (clean start)")
        terminal.info("")

        # ── Phase 2: State Removal ───────────────────────────────────────
        if state_rm_cmds:
            state.deploy.adopt_step_status = "state_rm"
            save_state()
            terminal.set_title("Output — STATE RM")
            terminal.info(f"━━━ PHASE 2: REMOVE STALE STATE ({len(state_rm_cmds)} commands) ━━━")

            for cmd_str in state_rm_cmds:
                terminal.info(f"> {cmd_str}")
                parts = cmd_str.split("terraform state rm ", 1)
                if len(parts) < 2:
                    terminal.warning(f"Could not parse command: {cmd_str}")
                    continue
                address = parts[1].strip().strip('"').strip("'")

                result = await asyncio.to_thread(
                    subprocess.run,
                    ["terraform", "state", "rm", "-no-color", address],
                    cwd=str(tf_path),
                    capture_output=True,
                    text=True,
                    env=env,
                )

                _emit_bounded_terminal_output(
                    terminal,
                    phase_name="state rm",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    stdout_budget=OutputBudget(max_lines=220, head_lines=140, tail_lines=60),
                    stderr_budget=OutputBudget(max_lines=120, head_lines=80, tail_lines=30),
                )

                if result.returncode != 0:
                    error_msg = f"terraform state rm failed for {address} (exit code {result.returncode})"
                    terminal.error(error_msg)
                    raise RuntimeError(error_msg)

                terminal.success(f"  ✓ Removed: {address}")

            terminal.info("")
        else:
            terminal.info("━━━ PHASE 2: STATE RM — SKIPPED (no mismatches) ━━━")
            terminal.info("")

        # ── Phase 3/4: Unified Generate Pipeline ─────────────────────────
        state.deploy.adopt_step_status = "write_imports"
        save_state()
        terminal.set_title("Output — GENERATE PIPELINE")
        terminal.info("━━━ PHASE 3/4: GENERATE ADOPT + PROTECTION ARTIFACTS ━━━")
        terminal.info("")

        pipeline_messages: list[str] = []

        def _on_pipeline_progress(msg: str) -> None:
            pipeline_messages.append(msg)
            terminal.info_auto(f"  {msg}")

        pipeline_result = await run_generate_pipeline(
            state,
            include_adopt=True,
            adopt_rows=adopt_rows,
            include_protection_moves=False,
            merge_baseline=True,
            regenerate_hcl=True,
            on_progress=_on_pipeline_progress,
        )
        terminal.info("")
        # region agent log
        _dbg_673991(
            "H3",
            "adopt.py:_run_adopt_plan:post_pipeline",
            "pipeline result",
            {
                "imports_count": pipeline_result.imports_count,
                "moves_count": pipeline_result.moves_count,
                "imports_file": str(pipeline_result.imports_file) if pipeline_result.imports_file else None,
                "target_count": len(pipeline_result.target_addresses),
                "target_contains_not_terraform": any("not_terraform" in a for a in pipeline_result.target_addresses),
            },
        )
        # endregion

        if pipeline_result.errors:
            raise RuntimeError(
                "Generate pipeline failed: " + "; ".join(pipeline_result.errors)
            )
        terminal.success(
            "✓ Pipeline complete "
            f"(imports={pipeline_result.imports_count}, moves={pipeline_result.moves_count}, "
            f"targets={len(pipeline_result.target_addresses)})"
        )
        terminal.info("")

        # ── Phase 5: Terraform Init ──────────────────────────────────────
        state.deploy.adopt_step_status = "init"
        save_state()
        terminal.set_title("Output — INIT")
        terminal.info("━━━ PHASE 5: TERRAFORM INIT ━━━")

        if not shutil.which("terraform"):
            raise RuntimeError("Terraform not found in PATH. Install from https://developer.hashicorp.com/terraform/downloads")

        result = await asyncio.to_thread(
            subprocess.run,
            ["terraform", "init", "-no-color"],
            cwd=str(tf_path),
            capture_output=True,
            text=True,
            env=env,
        )

        _emit_bounded_terminal_output(
            terminal,
            phase_name="init",
            stdout=result.stdout,
            stderr=result.stderr,
            stdout_budget=OutputBudget(max_lines=700, head_lines=420, tail_lines=220),
            stderr_budget=OutputBudget(max_lines=300, head_lines=180, tail_lines=100),
        )

        if result.returncode != 0:
            raise RuntimeError(f"terraform init failed (exit code {result.returncode})")

        terminal.success("✓ Terraform initialized")
        terminal.info("")

        # ── Phase 6: Terraform Plan ──────────────────────────────────────
        state.deploy.adopt_step_status = "plan"
        save_state()
        terminal.set_title("Output — PLAN")
        terminal.info("━━━ PHASE 6: TERRAFORM PLAN ━━━")

        # Build -target flags from pipeline artifacts.
        target_flags: list[str] = pipeline_result.target_flags
        target_addresses_dbg = [
            target_flags[i + 1]
            for i in range(0, len(target_flags) - 1, 2)
            if target_flags[i] == "-target"
        ]
        tf_non_import_files_dbg = [p for p in tf_path.glob("*.tf") if p.name != "adopt_imports.tf"]
        tf_non_import_text_dbg = "\n".join(
            p.read_text(encoding="utf-8", errors="ignore") for p in tf_non_import_files_dbg
        )
        target_presence_dbg: list[dict] = []
        for addr in target_addresses_dbg[:20]:
            m = re.search(
                r'module\.\S+\.(?P<tf_type>[^.]+)\.(?P<collection>[^\[]+)\["(?P<key>[^"]+)"\]',
                addr,
            )
            if not m:
                target_presence_dbg.append({"address": addr, "parsed": False})
                continue
            tf_type = m.group("tf_type")
            collection = m.group("collection")
            key = m.group("key")
            target_presence_dbg.append(
                {
                    "address": addr,
                    "parsed": True,
                    "tf_type": tf_type,
                    "collection": collection,
                    "key": key,
                    "has_resource_block": f'"{tf_type}" "{collection}"' in tf_non_import_text_dbg,
                    "has_key_literal": key in tf_non_import_text_dbg,
                }
            )
        # region agent log
        _dbg_db419a(
            "H4",
            "adopt.py:_run_adopt_plan:pre_plan_target_presence",
            "pre-plan target/config presence check",
            {
                "target_addresses": target_addresses_dbg,
                "tf_non_import_files": [p.name for p in tf_non_import_files_dbg],
                "target_presence": target_presence_dbg,
            },
        )
        # endregion
        tf_non_import_files = [p for p in tf_path.glob("*.tf") if p.name != "adopt_imports.tf"]
        regen_fallback_generated_config = False
        if not tf_non_import_files:
            terminal.warning(
                "No Terraform config files found besides adopt_imports.tf; "
                "attempting HCL regeneration before plan."
            )
            candidate_yaml_paths: list[Path] = []
            _tf_dir2, deployment_yaml_file, _baseline = resolve_deployment_paths(state)
            if deployment_yaml_file:
                candidate_yaml_paths.append(deployment_yaml_file)
            try:
                _intent = state.get_target_intent_manager().load()
                if _intent and _intent.source_focus_path:
                    candidate_yaml_paths.append(Path(_intent.source_focus_path))
            except Exception:
                pass
            if state.map.last_yaml_file:
                candidate_yaml_paths.append(Path(state.map.last_yaml_file))

            selected_yaml: Optional[Path] = None
            for candidate in candidate_yaml_paths:
                if candidate and candidate.exists():
                    selected_yaml = candidate
                    break

            if selected_yaml:
                try:
                    from importer.yaml_converter import YamlToTerraformConverter

                    converter = YamlToTerraformConverter()
                    await asyncio.to_thread(converter.convert, str(selected_yaml), str(tf_path))
                    tf_files_after_regen = sorted([p.name for p in tf_path.glob("*.tf")])
                    regen_fallback_generated_config = any(
                        name != "adopt_imports.tf" for name in tf_files_after_regen
                    )
                except Exception as regen_err:
                    terminal.warning(f"HCL regeneration fallback failed: {regen_err}")
        if regen_fallback_generated_config:
            terminal.info("Re-running terraform init after fallback HCL regeneration...")
            reinit_result = await asyncio.to_thread(
                subprocess.run,
                ["terraform", "init", "-no-color"],
                cwd=str(tf_path),
                capture_output=True,
                text=True,
                env=env,
            )
            _emit_bounded_terminal_output(
                terminal,
                phase_name="re-init",
                stdout=reinit_result.stdout,
                stderr=reinit_result.stderr,
                stdout_budget=OutputBudget(max_lines=700, head_lines=420, tail_lines=220),
                stderr_budget=OutputBudget(max_lines=300, head_lines=180, tail_lines=100),
            )
            if reinit_result.returncode != 0:
                raise RuntimeError(
                    f"terraform init after fallback regeneration failed (exit code {reinit_result.returncode})"
                )
            terminal.success("✓ Terraform re-initialized after fallback regeneration")
        # In adopt flow, never fall back to broad target derivation when no
        # import targets were generated; this would produce a regular/full plan.
        if not target_flags:
            raise RuntimeError(
                "No resources are selected for adoption. Choose at least one row "
                "with action 'adopt' before running Plan Adoption."
            )

        plan_cmd = ["terraform", "plan", "-out=adopt.tfplan", "-no-color"] + target_flags
        if _adopt_non_project_only:
            # For global-only adoption plans, suppress project-linked
            # group/service-token permission expansion so -target does not
            # pull unmanaged projects into the plan graph.
            _skip_var = "projects_v2_skip_global_project_permissions"
            if _terraform_declares_variable(tf_path, _skip_var):
                plan_cmd += ["-var", f"{_skip_var}=true"]
            else:
                terminal.warning(
                    f"Skipping -var {_skip_var}=true because this module does not declare that variable."
                )

        terminal.info(f"> {' '.join(plan_cmd)}")
        terminal.info("")

        result = await asyncio.to_thread(
            subprocess.run,
            plan_cmd,
            cwd=str(tf_path),
            capture_output=True,
            text=True,
            env=env,
        )

        # Defensive recovery for occasional module-install race/miss:
        # if plan reports modules are not installed, re-init once and retry plan.
        if result.returncode != 0 and "Module not installed" in (result.stderr or ""):
            terminal.warning(
                "Plan reported 'Module not installed'; re-running terraform init and retrying plan once."
            )
            retry_init_result = await asyncio.to_thread(
                subprocess.run,
                ["terraform", "init", "-no-color"],
                cwd=str(tf_path),
                capture_output=True,
                text=True,
                env=env,
            )
            _emit_bounded_terminal_output(
                terminal,
                phase_name="retry-init",
                stdout=retry_init_result.stdout,
                stderr=retry_init_result.stderr,
                stdout_budget=OutputBudget(max_lines=700, head_lines=420, tail_lines=220),
                stderr_budget=OutputBudget(max_lines=300, head_lines=180, tail_lines=100),
            )
            if retry_init_result.returncode == 0:
                result = await asyncio.to_thread(
                    subprocess.run,
                    plan_cmd,
                    cwd=str(tf_path),
                    capture_output=True,
                    text=True,
                    env=env,
                )

        # Color-code plan output lines like the deploy page, with bounded rendering.
        _emit_bounded_terminal_output(
            terminal,
            phase_name="plan",
            stdout=result.stdout,
            stderr=result.stderr,
            stdout_budget=OutputBudget(max_lines=900, head_lines=520, tail_lines=320),
            stderr_budget=OutputBudget(max_lines=360, head_lines=220, tail_lines=120),
            on_stdout_line=lambda line: (
                terminal.success(line)
                if "+" in line and "create" in line.lower()
                else terminal.error(line)
                if "-" in line and "destroy" in line.lower()
                else terminal.warning(line)
                if "~" in line and "change" in line.lower()
                else terminal.info_auto(f"  {line}")
            ),
            on_stderr_line=lambda line: terminal.warning(f"  {line}"),
        )

        if result.returncode != 0:
            raise RuntimeError(f"terraform plan failed (exit code {result.returncode})")

        # Prepend an explanatory note about output changes and "update in-place"
        # so novice Terraform users see it first without scrolling.
        _NOTE_LINES = [
            "─── NOTE ───────────────────────────────────────────────────────────────────",
            "This is an IMPORT plan. Resources shown as \"will be imported\" are being",
            "adopted into Terraform state — no infrastructure is created or destroyed.",
            "",
            "  * \"update in-place (imported from ...)\" means Terraform is reconciling",
            "    the declared config with the imported resource. This is normal and",
            "    harmless on first import.",
            "",
            "  * \"Changes to Outputs\" reflects Terraform registering newly imported",
            "    resources in its output maps. No real changes are made to your",
            "    dbt Cloud account.",
            "─────────────────────────────────────────────────────────────────────────────",
            "",
        ]
        plan_stdout = "\n".join(_NOTE_LINES) + result.stdout

        terminal.success("✓ Plan saved to adopt.tfplan")
        terminal.info("")
        for note_line in _NOTE_LINES:
            terminal.info(note_line)
        terminal.info("Click 'View Plan' to inspect, then 'Apply Adoption' when ready.")

        # Update state — plan is ready but not yet applied
        state.deploy.adopt_step_running = False
        state.deploy.adopt_step_status = "plan_ready"
        state.deploy.adopt_step_last_output = terminal.get_text()
        save_state()

        if on_plan_ready:
            on_plan_ready(plan_stdout)

        return plan_stdout

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Adopt plan failed: {error_msg}")
        terminal.error("")
        terminal.error("━━━ PLAN FAILED ━━━")
        terminal.error(f"Error: {error_msg}")

        if backup_file.exists():
            terminal.warning(f"State backup available at: {backup_file.name}")
            terminal.warning("Use 'Restore Backup' button to revert to pre-adoption state.")

        state.deploy.adopt_step_running = False
        state.deploy.adopt_step_status = "failed"
        state.deploy.adopt_step_error = error_msg
        state.deploy.adopt_step_last_output = terminal.get_text()
        save_state()

        if on_failure:
            on_failure(error_msg)

        return None
    finally:
        pass


async def _run_adopt_apply(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    summary: dict,
    tf_path: Path,
) -> None:
    """Apply the saved adoption plan (``adopt.tfplan``).

    Phases: apply → verify → cleanup.
    Raises on failure — caller handles UI updates.
    """
    adopt_rows = summary["adopt_rows"]

    state.deploy.adopt_step_running = True
    state.deploy.adopt_step_status = "apply"
    save_state()

    env = _get_terraform_env(state)
    backup_file = tf_path / "terraform.tfstate.adopt-backup"
    plan_file = tf_path / "adopt.tfplan"

    try:
        if not plan_file.exists():
            raise RuntimeError("No plan file found (adopt.tfplan). Run 'Plan Adoption' first.")

        # ── Apply the saved plan ─────────────────────────────────────────
        terminal.info("")
        terminal.info("━━━ APPLYING SAVED PLAN ━━━")
        terminal.info("> terraform apply -no-color adopt.tfplan")
        terminal.info("")
        terminal.set_title("Output — APPLY")

        result = await asyncio.to_thread(
            subprocess.run,
            ["terraform", "apply", "-no-color", "adopt.tfplan"],
            cwd=str(tf_path),
            capture_output=True,
            text=True,
            env=env,
        )

        _emit_bounded_terminal_output(
            terminal,
            phase_name="apply",
            stdout=result.stdout,
            stderr=result.stderr,
            stdout_budget=OutputBudget(max_lines=900, head_lines=520, tail_lines=320),
            stderr_budget=OutputBudget(max_lines=360, head_lines=220, tail_lines=120),
        )

        if result.returncode != 0:
            raise RuntimeError(f"terraform apply failed (exit code {result.returncode})")

        # Parse terraform's Apply summary for the actual import count.
        # Terraform outputs: "Apply complete! Resources: N imported, ..."
        _actual_imported = 0
        for _apply_line in result.stdout.split("\n"):
            _m = re.search(r"(\d+)\s+imported", _apply_line)
            if _m:
                _actual_imported = int(_m.group(1))
                break

        terminal.success("✓ Terraform apply completed")
        terminal.info("")

        # ── Verify ───────────────────────────────────────────────────────
        state.deploy.adopt_step_status = "verify"
        save_state()
        terminal.set_title("Output — VERIFY")
        terminal.info("━━━ VERIFY IMPORTS ━━━")
        terminal.info("> terraform state list")

        result = await asyncio.to_thread(
            subprocess.run,
            ["terraform", "state", "list", "-no-color"],
            cwd=str(tf_path),
            capture_output=True,
            text=True,
            env=env,
        )

        state_addresses = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        _emit_bounded_terminal_output(
            terminal,
            phase_name="verify",
            stdout=result.stdout,
            stderr=result.stderr,
            stdout_budget=OutputBudget(max_lines=520, head_lines=340, tail_lines=140),
            stderr_budget=OutputBudget(max_lines=160, head_lines=110, tail_lines=40),
            on_stdout_line=lambda line: terminal.debug(f"  {line}"),
            on_stderr_line=lambda line: terminal.warning(f"  {line}"),
        )

        found_in_state = len(state_addresses) if state_addresses else 0
        terminal.info(f"  State contains {found_in_state} resources")
        terminal.success(f"✓ Verification complete — {found_in_state} resources in state")
        terminal.info("")

        # ── Cleanup ──────────────────────────────────────────────────────
        terminal.info("━━━ CLEANUP ━━━")
        adopt_imports_file = tf_path / "adopt_imports.tf"
        if adopt_imports_file.exists():
            adopt_imports_file.unlink()
            terminal.success("✓ Removed adopt_imports.tf (one-time artifact)")
        if plan_file.exists():
            plan_file.unlink()
            terminal.success("✓ Removed adopt.tfplan")

        if backup_file.exists():
            terminal.info(f"State backup retained at {backup_file.name} (safe to delete)")

        terminal.info("")
        terminal.success("━━━ ADOPTION COMPLETE ━━━")
        # Use the actual count from terraform's Apply summary (parsed above).
        # Falls back to the adopt_count from the summary dict if parsing yielded 0.
        _import_display = _actual_imported if _actual_imported > 0 else summary.get("adopt_count", len(adopt_rows))
        terminal.success(f"Successfully imported {_import_display} resources into Terraform state.")

        # Update in-memory state
        state.deploy.adopt_step_complete = True
        state.deploy.adopt_step_running = False
        state.deploy.adopt_step_status = "complete"
        state.deploy.adopt_step_last_output = terminal.get_text()
        state.deploy.reconcile_imports_generated = True
        # Store the actual import count so the UI card shows the correct number
        state.deploy.adopt_step_imported_count = _import_display
        save_state()

        # Persist adopt completion to target-intent.json (survives server restart)
        _persist_adopt_workflow_state(state, complete=True, imported_count=_import_display)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Adopt apply failed: {error_msg}")
        terminal.error("")
        terminal.error("━━━ ADOPTION FAILED ━━━")
        terminal.error(f"Error: {error_msg}")

        if backup_file.exists():
            terminal.warning(f"State backup available at: {backup_file.name}")
            terminal.warning("Use 'Restore Backup' button to revert to pre-adoption state.")

        state.deploy.adopt_step_running = False
        state.deploy.adopt_step_status = "failed"
        state.deploy.adopt_step_error = error_msg
        state.deploy.adopt_step_last_output = terminal.get_text()
        save_state()

        raise  # Re-raise so the caller can handle UI updates


# ---------------------------------------------------------------------------
# Page creation
# ---------------------------------------------------------------------------

def create_adopt_page(
    state: AppState,
    navigate_to_step: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Adopt Resources page content."""

    # Resolve terraform directory
    tf_path = _get_terraform_dir(state)
    # region agent log
    _dbg_db419a(
        "H39",
        "adopt.py:create_adopt_page",
        "adopt page entered with resolved terraform path",
        {
            "active_project": state.active_project or "",
            "project_path": state.project_path or "",
            "terraform_dir_state": state.deploy.terraform_dir or "",
            "resolved_tf_path": str(tf_path),
        },
    )
    # endregion

    # Restore adopt step state from disk (survives server restart).
    # Do this before any UI rendering so the "Already complete" card shows correctly.
    if not state.deploy.adopt_step_complete:
        _restore_adopt_workflow_state(state)
    # region agent log
    _dbg_db419a(
        "H5",
        "adopt.py:create_adopt_page:post_restore",
        "adopt workflow state after restore",
        {
            "adopt_step_complete": bool(state.deploy.adopt_step_complete),
            "adopt_step_skipped": bool(state.deploy.adopt_step_skipped),
            "adopt_step_status": str(state.deploy.adopt_step_status or ""),
            "adopt_step_imported_count": int(state.deploy.adopt_step_imported_count or 0),
            "tfplan_exists": (tf_path / "adopt.tfplan").exists(),
            "imports_exists": (tf_path / "adopt_imports.tf").exists(),
        },
    )
    # endregion

    # Only load confirmed_mappings from target intent if they haven't been
    # populated by the Match page yet.  The in-memory state.map.confirmed_mappings
    # is the source of truth — it reflects the user's latest action choices.
    if not state.map.confirmed_mappings:
        try:
            intent = state.get_target_intent_manager().load()
            if intent and intent.match_mappings.source_to_target:
                state.map.confirmed_mappings = intent.match_mappings.to_confirmed_mappings()
        except Exception:
            pass

    # Load source/target items and state_result for detail popups
    _source_items = _load_report_items(state, target=False)
    _target_items = _load_report_items(state, target=True)
    _state_result = _reconstruct_state_result(state)

    # Build source/target lookup indexes for detail popup
    _source_by_key: dict[str, dict] = {s.get("source_key", s.get("element_mapping_id", "")): s for s in _source_items}
    _target_by_id: dict[str, dict] = {str(t.get("dbt_id", "")): t for t in _target_items if t.get("dbt_id")}

    # Get grid rows and compute summary
    grid_rows = _get_grid_rows_from_state(state)
    summary = _compute_adopt_summary(grid_rows, state.map.confirmed_mappings)
    has_adopt_rows = len(summary["adopt_rows"]) > 0
    has_target_credentials = bool(
        state.target_credentials.api_token and state.target_credentials.account_id
    )
    # region agent log
    _dbg_db419a(
        "H40",
        "adopt.py:create_adopt_page",
        "computed adopt summary and gate flags",
        {
            "adopt_count": int(summary.get("adopt_count", 0)),
            "adopt_rows_count": len(summary.get("adopt_rows", [])),
            "has_adopt_rows": has_adopt_rows,
            "confirmed_mappings_count": len(state.map.confirmed_mappings or []),
            "reconcile_state_loaded": bool(state.deploy.reconcile_state_loaded),
            "reconcile_state_resources_count": len(state.deploy.reconcile_state_resources or []),
            "has_target_credentials": has_target_credentials,
        },
    )
    # endregion

    # region agent log
    _dbg_673991(
        "H2",
        "adopt.py:create_adopt_page",
        "protected resources at page load",
        {"count": len(state.map.protected_resources), "sample": sorted(state.map.protected_resources)[:20]},
    )
    _grp_rows = [r for r in grid_rows if r.get("source_type") == "GRP"]
    _dbg_673991(
        "H2",
        "adopt.py:create_adopt_page",
        "GRP rows from build_grid_data",
        {
            "rows": [
                {
                    k: r.get(k)
                    for k in (
                        "source_key",
                        "source_type",
                        "source_name",
                        "action",
                        "protected",
                        "yaml_protected",
                        "drift_status",
                        "target_id",
                    )
                }
                for r in _grp_rows
            ]
        },
    )
    _adopt_grp = [r for r in summary["adopt_rows"] if r.get("source_type") == "GRP"]
    _dbg_673991(
        "H2",
        "adopt.py:create_adopt_page",
        "GRP adopt_rows after _compute_adopt_summary",
        {
            "rows": [
                {
                    k: r.get(k)
                    for k in (
                        "source_key",
                        "source_type",
                        "source_name",
                        "action",
                        "protected",
                        "yaml_protected",
                        "drift_status",
                    )
                }
                for r in _adopt_grp
            ]
        },
    )
    _cm_grp = [m for m in state.map.confirmed_mappings if "everyone" in m.get("source_key", "").lower() or m.get("resource_type") == "GRP"]
    _dbg_673991("H2", "adopt.py:create_adopt_page", "GRP confirmed_mappings", {"mappings": _cm_grp})
    _dbg_673991(
        "H2",
        "adopt.py:create_adopt_page",
        "summary counts",
        {
            "adopt_count": summary["adopt_count"],
            "protected_count": summary["protected_count"],
            "total_rows": len(summary["adopt_rows"]),
        },
    )
    # endregion

    # ── Page header ──────────────────────────────────────────────────────
    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-4"):
        with ui.row().classes("w-full items-center gap-3"):
            ui.icon("download_for_offline", size="2rem").style(f"color: {DBT_ORANGE};")
            ui.label("Adopt Resources into Terraform State").classes("text-2xl font-bold")

        ui.label(
            "This step automates the terraform state rm + import cycle for resources "
            "you marked as 'adopt' on the Match page."
        ).classes("text-slate-600 dark:text-slate-400 text-sm")

        # Target credential readiness indicator for Adopt plan/apply.
        with ui.row().classes("items-center gap-2"):
            if has_target_credentials:
                ui.icon("check_circle").classes("text-green-600")
                ui.label("Target credentials loaded for Plan/Apply").classes(
                    "text-sm text-green-700 dark:text-green-400"
                )
            else:
                ui.icon("warning").classes("text-amber-600")
                ui.label(
                    "Target credentials not loaded. Load .env on Fetch Target before Plan Adoption."
                ).classes("text-sm text-amber-700 dark:text-amber-400")

        # ── Skip-when-empty ──────────────────────────────────────────────
        if not has_adopt_rows:
            with ui.card().classes("w-full p-6"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("check_circle", size="1.5rem").style(f"color: {STATUS_SUCCESS};")
                    ui.label("Nothing to adopt").classes("text-lg font-semibold")
                ui.label(
                    "No resources are marked for adoption. All resources will be created new or ignored. "
                    "You can proceed directly to Configure."
                ).classes("text-slate-600 dark:text-slate-400 mt-2")

                with ui.row().classes("gap-4 mt-4"):
                    ui.button(
                        "Back to Match",
                        icon="arrow_back",
                        on_click=lambda: navigate_to_step(WorkflowStep.MATCH),
                    ).props("outline")
                    ui.button(
                        "Continue to Configure",
                        icon="arrow_forward",
                        on_click=lambda: _skip_and_proceed(state, save_state, navigate_to_step),
                    ).style(f"background-color: {DBT_ORANGE};")

            return  # Nothing else to render

        # ── Already complete ─────────────────────────────────────────────
        if state.deploy.adopt_step_complete:
            # region agent log
            _dbg_db419a(
                "H5",
                "adopt.py:create_adopt_page:complete_card",
                "rendering adoption complete mode",
                {
                    "adopt_count_summary": int(summary.get("adopt_count", 0)),
                    "adopt_rows_count": len(summary.get("adopt_rows", [])),
                    "adopt_step_status": str(state.deploy.adopt_step_status or ""),
                    "tfplan_exists": (tf_path / "adopt.tfplan").exists(),
                    "imports_exists": (tf_path / "adopt_imports.tf").exists(),
                },
            )
            # endregion
            _imported = state.deploy.adopt_step_imported_count or summary['adopt_count']
            with ui.card().classes("w-full p-6"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("check_circle", size="1.5rem").style(f"color: {STATUS_SUCCESS};")
                    ui.label("Adoption Complete").classes("text-lg font-semibold text-green-600")

                ui.label(
                    f"Successfully imported {_imported} resources into Terraform state."
                ).classes("text-slate-600 dark:text-slate-400 mt-2")

                with ui.row().classes("gap-4 mt-4"):
                    ui.button(
                        "Back to Match",
                        icon="arrow_back",
                        on_click=lambda: navigate_to_step(WorkflowStep.MATCH),
                    ).props("outline")

                    async def rerun_adoption():
                        # Reset stale adopt artifacts and deployment YAML scope so
                        # a rerun always starts from source-selected intent.
                        _invalidate_adopt_artifacts_for_action_change(
                            tf_path=tf_path,
                            adopt_grid_data=[],
                            new_action="ignore",
                            adopt_count=0,
                            source_yaml_file=state.map.last_yaml_file,
                        )
                        state.deploy.adopt_step_complete = False
                        state.deploy.adopt_step_skipped = False
                        state.deploy.adopt_step_status = ""
                        state.deploy.adopt_step_error = ""
                        state.deploy.adopt_step_imported_count = 0
                        save_state()
                        _clear_adopt_workflow_state(state)
                        ui.navigate.reload()

                    ui.button(
                        "Re-run Adoption",
                        icon="replay",
                        on_click=rerun_adoption,
                    ).props("outline")

                    ui.button(
                        "Continue to Configure",
                        icon="arrow_forward",
                        on_click=lambda: navigate_to_step(WorkflowStep.CONFIGURE),
                    ).style(f"background-color: {DBT_ORANGE};")

            # Show previous output if available
            if state.deploy.adopt_step_last_output:
                with ui.expansion("Previous Execution Log", icon="terminal").classes("w-full mt-4"):
                    ui.code(state.deploy.adopt_step_last_output, language="text").classes("w-full text-xs")

            # Show grid with adopted/unadopt status below the complete card
            # (falls through to grid rendering below instead of returning)

        # ── Summary card ─────────────────────────────────────────────────
        with ui.card().classes("w-full p-6"):
            ui.label("Adoption Summary").classes("text-lg font-semibold mb-3")

            with ui.row().classes("gap-8"):
                # Resources to import
                with ui.column().classes("items-center"):
                    adopt_count_label = ui.label(str(summary["adopt_count"])).classes(
                        "text-3xl font-bold text-purple-600"
                    )
                    ui.label("Resources to Import").classes("text-xs text-slate-500")

                # State rm needed
                with ui.column().classes("items-center"):
                    rm_color = "text-amber-600" if summary["rm_count"] > 0 else "text-slate-400"
                    ui.label(str(summary["rm_count"])).classes(f"text-3xl font-bold {rm_color}")
                    ui.label("Need State RM").classes("text-xs text-slate-500")

                # Protected
                with ui.column().classes("items-center"):
                    prot_color = "text-blue-600" if summary["protected_count"] > 0 else "text-slate-400"
                    protected_count_label = ui.label(str(summary["protected_count"])).classes(
                        f"text-3xl font-bold {prot_color}"
                    )
                    ui.label("Protected").classes("text-xs text-slate-500")

            if summary["rm_count"] > 0:
                with ui.row().classes("items-center gap-2 mt-3 p-2 bg-amber-50 dark:bg-amber-900/20 rounded"):
                    ui.icon("warning", size="1.2rem").style(f"color: {STATUS_WARNING};")
                    ui.label(
                        f"{summary['rm_count']} resource(s) have mismatched IDs in Terraform state. "
                        "Stale entries will be removed before importing the correct resources."
                    ).classes("text-sm text-amber-700 dark:text-amber-300")

        # ── Resources AG Grid ─────────────────────────────────────────────
        # Build row data for the grid — only adopt rows with actionable dropdown
        _is_complete = state.deploy.adopt_step_complete
        adopt_grid_data = []
        for row in summary["adopt_rows"]:
            # Display name: prefer source_name, fall back to source_key,
            # and always strip the internal "target__" prefix so the UI
            # shows the clean resource name (e.g. "everyone" not "target__everyone").
            _display_name = row.get("source_name") or row.get("source_key", "?")
            if _display_name.startswith("target__"):
                _display_name = _display_name[len("target__"):]
            _action = row.get("action", "adopt")
            # After adoption completes, show "adopted" instead of "adopt"
            if _is_complete and _action == "adopt":
                _action = "adopted"
            # Ignored resources should never show a shield — clear stale
            # protection that may persist from a previous session.
            _protected = row.get("protected", False) if _action not in ("ignore",) else False
            adopt_grid_data.append({
                "source_key": row.get("source_key", ""),
                "source_type": row.get("source_type", row.get("resource_type", "?")),
                "source_name": _display_name,
                "target_id": row.get("target_id", ""),
                "target_name": row.get("target_name", ""),
                "drift_status": row.get("drift_status", ""),
                "state_address": row.get("state_address", ""),
                "protected": _protected,
                "project_name": row.get("project_name", ""),
                "project_id": row.get("project_id", ""),
                "action": _action,
            })

        # region agent log
        _dbg_673991(
            "H18",
            "adopt.py:create_adopt_page:grid_data",
            "adopt grid data prepared",
            {
                "row_count": len(adopt_grid_data),
                "adopt_count_summary": summary.get("adopt_count", 0),
                "action_counts": {
                    "adopt": sum(1 for r in adopt_grid_data if r.get("action") == "adopt"),
                    "ignore": sum(1 for r in adopt_grid_data if r.get("action") == "ignore"),
                    "other": sum(1 for r in adopt_grid_data if r.get("action") not in {"adopt", "ignore"}),
                },
                "source_type_counts": {
                    str(k): int(v) for k, v in __import__("collections").Counter(
                        str(r.get("source_type", "")) for r in adopt_grid_data
                    ).items()
                },
                "sample_rows": [
                    {
                        "source_key": str(r.get("source_key", "")),
                        "source_type": str(r.get("source_type", "")),
                        "source_name": str(r.get("source_name", "")),
                        "action": str(r.get("action", "")),
                        "drift_status": str(r.get("drift_status", "")),
                    }
                    for r in adopt_grid_data[:10]
                ],
            },
        )
        # endregion
        # region agent log
        _dbg_db419a(
            "H56",
            "adopt.py:create_adopt_page",
            "adopt grid row data prepared for AG Grid render",
            {
                "row_count": len(adopt_grid_data),
                "adopt_count_summary": int(summary.get("adopt_count", 0)),
                "ignore_count_summary": int(len(adopt_grid_data) - int(summary.get("adopt_count", 0))),
                "sample_rows": [
                    {
                        "source_key": str(r.get("source_key", "")),
                        "source_type": str(r.get("source_type", "")),
                        "source_name": str(r.get("source_name", "")),
                        "action": str(r.get("action", "")),
                    }
                    for r in adopt_grid_data[:8]
                ],
            },
        )
        # endregion

        TYPE_LABELS_JS = """{
            'ACC': 'Account', 'CON': 'Connection', 'REP': 'Repository',
            'TOK': 'Token', 'GRP': 'Group', 'NOT': 'Notify',
            'WEB': 'Webhook', 'PLE': 'PrivateLink', 'PRJ': 'Project',
            'ENV': 'Environment', 'VAR': 'EnvVar', 'JOB': 'Job',
            'JEVO': 'EnvVar Ovr', 'JCTG': 'Job Trigger', 'PREP': 'Repo Link',
        }"""

        adopt_col_defs = [
            {
                "field": "details_btn",
                "headerName": "",
                "width": 50,
                "maxWidth": 50,
                "sortable": False,
                "filter": False,
                "resizable": False,
                "cellStyle": {"textAlign": "center", "cursor": "pointer"},
                ":cellRenderer": """params => '<span style="font-size: 16px; cursor: pointer;" title="View Details">🔍</span>'""",
            },
            {
                "field": "source_type",
                "headerName": "Type",
                "width": 120,
                ":valueFormatter": f"""params => {{
                    const types = {TYPE_LABELS_JS};
                    return types[params.value] || params.value;
                }}""",
                "cellClassRules": {
                    "type-project": "x === 'PRJ'",
                    "type-environment": "x === 'ENV'",
                    "type-job": "x === 'JOB'",
                    "type-connection": "x === 'CON'",
                    "type-repository": "x === 'REP'",
                    "type-envvar": "x === 'VAR'",
                    "type-other": "!['PRJ','ENV','JOB','CON','REP','VAR'].includes(x)",
                },
            },
            {
                "field": "source_name",
                "headerName": "Name",
                "flex": 2,
                "minWidth": 180,
                "filter": "agTextColumnFilter",
                "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
            },
            {
                "field": "target_id",
                "headerName": "Target ID",
                "width": 100,
                "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
            },
            {
                "field": "target_name",
                "headerName": "Target Name",
                "flex": 1,
                "minWidth": 140,
                "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
            },
            {
                "field": "drift_status",
                "headerName": "Drift",
                "width": 120,
                ":valueFormatter": """params => {
                    const labels = {
                        'no_state': '—',
                        'in_sync': '✓ In Sync',
                        'id_mismatch': '⚠️ Mismatch',
                        'not_in_state': '➕ Not in TF',
                        'state_only': '📌 In State',
                        'attr_mismatch': '⚠️ Attr Diff',
                    };
                    return labels[params.value] || params.value || '—';
                }""",
                "cellClassRules": {
                    "drift-sync": "x === 'in_sync'",
                    "drift-mismatch": "x === 'id_mismatch' || x === 'attr_mismatch'",
                    "drift-missing": "x === 'not_in_state'",
                },
            },
            {
                "field": "protected",
                "headerName": "🛡️",
                "headerTooltip": "Protected from destroy — click to toggle",
                "width": 55,
                "maxWidth": 55,
                "cellStyle": {"textAlign": "center", "cursor": "pointer"},
                ":cellRenderer": """params => params.value ? '<span style="color: #3B82F6; font-size: 16px;" title="Protected — click to unprotect">🛡️</span>' : '<span style="color: #CBD5E1; font-size: 14px;" title="Click to protect">○</span>'""",
            },
            {
                "field": "action",
                "headerName": "Action",
                "width": 130,
                "editable": True,
                "cellEditor": "agSelectCellEditor",
                "cellEditorParams": {"values": ["adopted", "unadopt", "ignore"] if _is_complete else ["adopt", "ignore"]},
                ":valueFormatter": """params => {
                    const labels = {
                        'adopt': '📥 Adopt',
                        'adopted': '✅ Adopted',
                        'unadopt': '↩️ Unadopt',
                        'ignore': '🚫 Ignore',
                    };
                    return labels[params.value] || params.value;
                }""",
                "cellClassRules": {
                    "action-adopt": "x === 'adopt'",
                    "action-adopted": "x === 'adopted'",
                    "action-unadopt": "x === 'unadopt'",
                    "action-ignore": "x === 'ignore'",
                },
            },
            {
                "field": "project_name",
                "headerName": "Project",
                "width": 140,
                "filter": "agTextColumnFilter",
                "cellStyle": {"fontSize": "11px"},
            },
        ]

        adopt_grid_options = {
            "columnDefs": adopt_col_defs,
            "rowData": adopt_grid_data,
            "pagination": False,
            "rowHeight": 40,
            "headerHeight": 36,
            "defaultColDef": {
                "resizable": True,
                "sortable": True,
                "filter": True,
            },
            "rowClassRules": {
                "row-ignored": "data.action === 'ignore' || data.action === 'unadopt'",
            },
            "stopEditingWhenCellsLoseFocus": True,
            "singleClickEdit": True,
            "animateRows": False,
        }

        # region agent log
        _dbg_673991(
            "H19",
            "adopt.py:create_adopt_page:grid_options",
            "aggrid options prepared",
            {
                "column_count": len(adopt_col_defs),
                "column_fields": [str(c.get("field", "")) for c in adopt_col_defs],
                "row_data_count": len(adopt_grid_options.get("rowData", [])),
                "theme": "quartz + ag-theme-quartz",
            },
        )
        # endregion

        _grid_title = f"Adopted Resources ({summary['adopt_count']})" if _is_complete else f"Resources to Adopt ({summary['adopt_count']})"
        grid_title_label = ui.label(_grid_title).classes("text-lg font-semibold")

        # Add AG Grid styling
        ui.add_head_html("""
        <style>
        .adopt-grid .ag-row.row-ignored { opacity: 0.5; }
        .adopt-grid .action-adopt { color: #8B5CF6; font-weight: 600; }
        .adopt-grid .action-adopted { color: #22C55E; font-weight: 600; }
        .adopt-grid .action-unadopt { color: #F59E0B; font-weight: 600; }
        .adopt-grid .action-ignore { color: #94A3B8; font-style: italic; }
        .adopt-grid .drift-sync { color: #22C55E; }
        .adopt-grid .drift-mismatch { color: #F59E0B; font-weight: 600; }
        .adopt-grid .drift-missing { color: #8B5CF6; }
        .adopt-grid .type-project { color: #3B82F6; font-weight: 600; }
        .adopt-grid .type-environment { color: #10B981; }
        .adopt-grid .type-job { color: #F59E0B; }
        .adopt-grid .type-connection { color: #6366F1; }
        .adopt-grid .type-repository { color: #EC4899; }
        .adopt-grid .type-envvar { color: #14B8A6; }
        .adopt-grid .type-other { color: #64748B; }
        </style>
        """)

        adopt_grid = ui.aggrid(
            adopt_grid_options, theme="quartz"
        ).classes("w-full adopt-grid ag-theme-quartz").style(
            "height: 400px; min-height: 200px; width: 100%;"
        )

        # Summary badge below the grid
        _initial_ignored = len(summary["adopt_rows"]) - summary["adopt_count"]
        summary_label = ui.label(
            f"📥 {summary['adopt_count']} to adopt, 🚫 {_initial_ignored} ignored"
        ).classes("text-sm text-slate-500 mt-1")

        def _show_detail(row_data: dict):
            """Show detail popup using the same dialog as the match page."""
            from importer.web.components.entity_table import show_match_detail_dialog

            source_key = row_data.get("source_key", "")
            target_id = str(row_data.get("target_id", ""))

            # Look up full source data by key
            source_data = _source_by_key.get(source_key, row_data)

            # Look up full target data by target_id
            target_data = _target_by_id.get(target_id)

            # Look up state resource if state_result available
            state_resource = None
            if _state_result:
                ecode = row_data.get("source_type", "")
                state_id = row_data.get("state_id")
                if state_id is not None:
                    state_resource = _state_result.resources_by_id.get((ecode, state_id))

            show_match_detail_dialog(
                source_data=source_data,
                grid_row=row_data,
                target_data=target_data,
                state_resource=state_resource,
                app_state=state,
                has_state_loaded=state.deploy.reconcile_state_loaded,
            )

        # ── Protection Intent Manager ─────────────────────────────────────
        # Load ProtectionIntentManager so protection decisions persist to
        # protection-intent.json and sync with the Match page.
        protection_intent = state.get_protection_intent_manager()
        protection_intent.load()

        # Protectable type codes — derived from RESOURCE_TYPE_MAP so adding new
        # types in protection_manager.py automatically makes them protectable here.
        from importer.web.utils.protection_manager import RESOURCE_TYPE_MAP
        _PROTECTABLE_TYPES = set(RESOURCE_TYPE_MAP.keys())

        def _make_adopt_intent_key(source_type: str, source_key: str) -> str:
            """Build a prefixed intent key like 'PRJ:my_project' for the adopt grid."""
            bare_key = source_key
            if bare_key.startswith("target__"):
                bare_key = bare_key[len("target__"):]
            if source_type:
                return f"{source_type}:{bare_key}"
            return bare_key

        def _update_protection_in_grid(source_key: str, new_protected: bool):
            """Update protection flag in adopt_grid_data and refresh the grid + counters."""
            for r in adopt_grid_data:
                if r.get("source_key") == source_key:
                    r["protected"] = new_protected
                    break

            # Recompute counters
            adopt_count = sum(1 for r in adopt_grid_data if r.get("action") == "adopt")
            ignored_count = len(adopt_grid_data) - adopt_count
            protected_adopt = sum(
                1 for r in adopt_grid_data
                if r.get("action") == "adopt" and r.get("protected")
            )

            summary_label.set_text(f"📥 {adopt_count} to adopt, 🚫 {ignored_count} ignored")
            adopt_count_label.set_text(str(adopt_count))
            protected_count_label.set_text(str(protected_adopt))
            grid_title_label.set_text(f"Resources to Adopt ({adopt_count})")

            # Refresh the grid so the shield column re-renders
            adopt_grid.update()

            # Invalidate stale plan — protection change means different TF addresses
            if btn_refs.get("plan"):
                btn_refs["plan"].set_visibility(True)
                if adopt_count > 0:
                    btn_refs["plan"].enable()
                else:
                    btn_refs["plan"].disable()
            if btn_refs.get("apply"):
                btn_refs["apply"].set_visibility(False)
            if btn_refs.get("view_plan"):
                btn_refs["view_plan"].set_visibility(False)
            if btn_refs.get("skip"):
                btn_refs["skip"].set_visibility(True)

        def _persist_protection(source_key: str, source_type: str, new_protected: bool):
            """Persist protection decision to intent manager and state."""
            intent_key = _make_adopt_intent_key(source_type, source_key)
            protection_intent.set_intent(
                key=intent_key,
                protected=new_protected,
                source="adopt_page_click",
                reason="Protection toggled on Adopt page",
                resource_type=source_type or None,
            )
            protection_intent.save()

            bare_key = source_key
            if bare_key.startswith("target__"):
                bare_key = bare_key[len("target__"):]
            if new_protected:
                state.map.protected_resources.add(bare_key)
            else:
                state.map.protected_resources.discard(bare_key)
            save_state()

        def _apply_adopt_and_protect(source_key: str, source_type: str):
            """Apply both adopt and protect to a row (after dialog Yes)."""
            # 1) Set action=adopt in grid data
            for r in adopt_grid_data:
                if r.get("source_key") == source_key:
                    r["action"] = "adopt"
                    r["protected"] = True
                    break

            # 2) Update confirmed_mappings
            _found = False
            for mapping in state.map.confirmed_mappings:
                mk = mapping.get("source_key", "")
                if mk == source_key or mk == f"target__{source_key}":
                    mapping["action"] = "adopt"
                    _found = True
                    break
            if not _found:
                state.map.confirmed_mappings.append({
                    "source_key": source_key,
                    "action": "adopt",
                })

            # 3) Persist protection
            _persist_protection(source_key, source_type, True)

            # 4) Update grid + counters
            _update_protection_in_grid(source_key, True)

        def _show_adopt_to_protect_dialog(source_key: str, source_type: str, display_name: str):
            """Show the 'Protection requires Adoption' confirmation dialog."""
            with ui.dialog() as dlg, ui.card().classes("p-6").style("min-width: 400px;"):
                ui.label("Protection Requires Adoption").classes("text-lg font-semibold mb-2")
                ui.label(
                    f'The resource "{display_name}" is currently ignored (not adopted). '
                    "Protection only applies to resources that are imported into Terraform state."
                ).classes("text-sm text-slate-600 dark:text-slate-400 mb-4")
                ui.label(
                    "Would you like to adopt and protect this resource?"
                ).classes("text-sm font-medium mb-4")

                with ui.row().classes("gap-4 justify-end"):
                    def _on_no():
                        dlg.close()

                    def _on_yes(sk=source_key, st=source_type):
                        dlg.close()
                        _apply_adopt_and_protect(sk, st)

                    ui.button("No", on_click=_on_no).props("outline")
                    ui.button(
                        "Yes — Adopt & Protect",
                        on_click=_on_yes,
                    ).style(f"background-color: {DBT_ORANGE};")

            dlg.open()

        # ── Grid event handlers ──────────────────────────────────────────
        def _on_adopt_cell_clicked(e):
            """Handle cell clicks in the adopt grid."""
            col_id = e.args.get("colId", "")
            row = e.args.get("data", {})

            if col_id == "details_btn" and row:
                _show_detail(row)
                return

            if col_id == "protected" and row:
                source_key = row.get("source_key", "")
                source_type = row.get("source_type", "")
                action = row.get("action", "ignore")
                currently_protected = row.get("protected", False)
                display_name = row.get("source_name") or source_key

                # Check if this resource type is protectable
                if source_type not in _PROTECTABLE_TYPES:
                    ui.notify(
                        f"Resource type '{source_type}' does not support protection.",
                        type="warning",
                    )
                    return

                if currently_protected:
                    # Unprotecting: always allowed directly (no dialog needed)
                    for r in adopt_grid_data:
                        if r.get("source_key") == source_key:
                            r["protected"] = False
                            break
                    _persist_protection(source_key, source_type, False)
                    _update_protection_in_grid(source_key, False)
                    return

                # Protecting: check if adopted
                if action == "adopt":
                    # Already adopted — toggle protection directly
                    for r in adopt_grid_data:
                        if r.get("source_key") == source_key:
                            r["protected"] = True
                            break
                    _persist_protection(source_key, source_type, True)
                    _update_protection_in_grid(source_key, True)
                else:
                    # Not adopted — show the adopt-and-protect dialog
                    _show_adopt_to_protect_dialog(source_key, source_type, display_name)

        def _on_adopt_cell_changed(e):
            """Handle action changes in the adopt grid (adopt/adopted/unadopt/ignore)."""
            row = e.args.get("data", {})
            if not row:
                return

            source_key = row.get("source_key", "")
            new_action = row.get("action", "adopt")

            # Normalize: "adopted" in the dropdown means the user wants to keep it as adopt
            _persist_action = new_action
            if _persist_action == "adopted":
                _persist_action = "adopt"

            # Update confirmed_mappings in state.
            # Grid rows may use bare keys ("everyone") while confirmed_mappings
            # stores target-only resources with a "target__" prefix ("target__everyone").
            # Check both forms to ensure the update reaches the right entry.
            # Target-only resources may NOT exist in confirmed_mappings at all
            # (they were never on the Match page), so we add a new entry if needed.
            _found = False
            for mapping in state.map.confirmed_mappings:
                mk = mapping.get("source_key", "")
                if mk == source_key or mk == f"target__{source_key}":
                    mapping["action"] = _persist_action
                    _found = True
                    break
            if not _found and not source_key.startswith("target__"):
                # Try the reverse: grid key has prefix, mapping doesn't
                bare = source_key.removeprefix("target__")
                for mapping in state.map.confirmed_mappings:
                    if mapping.get("source_key") == bare:
                        mapping["action"] = _persist_action
                        _found = True
                        break
            if not _found:
                # Target-only resource not in confirmed_mappings — add it
                state.map.confirmed_mappings.append({
                    "source_key": source_key,
                    "action": _persist_action,
                })

            save_state()

            # ── Persist action change to target-intent.json ──
            # The Match page re-seeds confirmed_mappings from target-intent.json
            # on load (source of truth). Without this, changes made here would be
            # lost when navigating back to the Match page.
            try:
                from importer.web.utils.target_intent import MatchMappings
                _ti_mgr = state.get_target_intent_manager()
                _prev_intent = _ti_mgr.load()
                if _prev_intent:
                    _prev_intent.match_mappings = MatchMappings.from_confirmed_mappings(
                        state.map.confirmed_mappings
                    )
                    state.save_target_intent(_prev_intent)
            except Exception as _ti_err:
                import logging as _logging
                _logging.warning(f"Failed to persist adopt action to target-intent: {_ti_err}")


            # Update adopt_grid_data in-place to track user choices.
            # If switching to ignore or unadopt, also clear protection — non-managed
            # resources should not show a shield.
            cleared_protection = False
            for r in adopt_grid_data:
                if r.get("source_key") == source_key:
                    r["action"] = new_action
                    if new_action in ("ignore", "unadopt") and r.get("protected"):
                        r["protected"] = False
                        _persist_protection(source_key, r.get("source_type", ""), False)
                        cleared_protection = True
                    break

            if cleared_protection:
                adopt_grid.update()

            # Compute counts from adopt_grid_data (reflects user choices)
            _active_actions = ("adopt", "adopted")
            adopt_count = sum(1 for r in adopt_grid_data if r.get("action") in _active_actions)
            other_count = len(adopt_grid_data) - adopt_count
            protected_adopt = sum(1 for r in adopt_grid_data if r.get("action") in _active_actions and r.get("protected"))

            # Update ALL summary displays
            if _is_complete:
                summary_label.set_text(f"✅ {adopt_count} adopted, 🚫 {other_count} other")
                grid_title_label.set_text(f"Adopted Resources ({adopt_count})")
            else:
                summary_label.set_text(f"📥 {adopt_count} to adopt, 🚫 {other_count} ignored")
                grid_title_label.set_text(f"Resources to Adopt ({adopt_count})")
            adopt_count_label.set_text(str(adopt_count))
            protected_count_label.set_text(str(protected_adopt))

            # Invalidate any stale plan — the user changed their selections,
            # so the previous plan (if any) no longer matches.
            # Show the Plan button, hide Apply and View Plan.
            if btn_refs.get("plan"):
                btn_refs["plan"].set_visibility(True)
                if adopt_count > 0:
                    btn_refs["plan"].enable()
                else:
                    btn_refs["plan"].disable()
            if btn_refs.get("apply"):
                btn_refs["apply"].set_visibility(False)
            if btn_refs.get("view_plan"):
                btn_refs["view_plan"].set_visibility(False)
            if btn_refs.get("skip"):
                btn_refs["skip"].set_visibility(True)

            # Remove stale adoption artifacts immediately when selections change.
            # This prevents Deploy from consuming old import blocks if the user
            # navigates away before re-running Plan Adoption.
            cleanup_result = _invalidate_adopt_artifacts_for_action_change(
                tf_path=tf_path,
                adopt_grid_data=adopt_grid_data,
                new_action=new_action,
                adopt_count=adopt_count,
                source_yaml_file=state.map.last_yaml_file,
            )
            removed_imports = bool(cleanup_result["removed_imports"])
            removed_plan = bool(cleanup_result["removed_plan"])
            cleaned_yaml_entries = int(cleanup_result["cleaned_yaml_entries"])
            regenerated_hcl_after_cleanup = bool(
                cleanup_result["regenerated_hcl_after_cleanup"]
            )
            reset_deployment_yaml_from_source = bool(
                cleanup_result["reset_deployment_yaml_from_source"]
            )
            reset_source_yaml_path = cleanup_result["reset_source_yaml_path"]
            cleanup_error = cleanup_result["cleanup_error"]

            # region agent log
            imports_file = tf_path / "adopt_imports.tf"
            imports_has_not_terraform = False
            imports_count = 0
            if imports_file.exists():
                try:
                    imports_content = imports_file.read_text(encoding="utf-8")
                    imports_count = len(re.findall(r"^\s*import\s*\{", imports_content, flags=re.MULTILINE))
                    imports_has_not_terraform = 'dbtcloud_project.projects["not_terraform"]' in imports_content
                except Exception:
                    pass
            _dbg_673991(
                "H31",
                "adopt.py:_on_adopt_cell_changed",
                "adopt action changed and plan invalidated",
                {
                    "source_key": source_key,
                    "new_action": new_action,
                    "adopt_count": adopt_count,
                    "plan_btn_visible": bool(btn_refs.get("plan") and btn_refs["plan"].visible),
                    "plan_btn_enabled": bool(btn_refs.get("plan") and btn_refs["plan"].enabled),
                    "apply_btn_visible": bool(btn_refs.get("apply") and btn_refs["apply"].visible),
                    "adopt_imports_exists": imports_file.exists(),
                    "adopt_imports_count": imports_count,
                    "adopt_imports_has_not_terraform": imports_has_not_terraform,
                    "removed_imports_file": removed_imports,
                    "removed_adopt_tfplan": removed_plan,
                    "cleaned_yaml_entries": cleaned_yaml_entries,
                    "regenerated_hcl_after_cleanup": regenerated_hcl_after_cleanup,
                    "reset_deployment_yaml_from_source": reset_deployment_yaml_from_source,
                    "reset_source_yaml_path": reset_source_yaml_path,
                    "cleanup_error": cleanup_error,
                },
            )
            # Additional YAML/HCL invalidation evidence
            deployment_yaml = tf_path / "dbt-cloud-config.yml"
            yaml_has_not_terraform = False
            if deployment_yaml.exists():
                try:
                    yaml_has_not_terraform = 'key: not_terraform' in deployment_yaml.read_text(encoding="utf-8")
                except Exception:
                    pass
            _dbg_673991(
                "H38",
                "adopt.py:_on_adopt_cell_changed",
                "post-cleanup deployment yaml snapshot",
                {
                    "source_key": source_key,
                    "new_action": new_action,
                    "deployment_yaml_exists": deployment_yaml.exists(),
                    "deployment_yaml_has_not_terraform": yaml_has_not_terraform,
                    "cleaned_yaml_entries": cleaned_yaml_entries,
                    "regenerated_hcl_after_cleanup": regenerated_hcl_after_cleanup,
                    "reset_deployment_yaml_from_source": reset_deployment_yaml_from_source,
                },
            )
            # endregion

        adopt_grid.on("cellClicked", _on_adopt_cell_clicked)
        adopt_grid.on("cellValueChanged", _on_adopt_cell_changed)

        if summary["state_rm_commands"]:
            with ui.expansion(
                f"State RM Commands ({summary['rm_count']})",
                icon="delete_sweep",
            ).classes("w-full"):
                ui.label(
                    "These commands remove stale state entries before importing. "
                    "This does NOT destroy any actual dbt Cloud resources."
                ).classes("text-sm text-amber-600 mb-2 px-2")
                content = "\n".join(summary["state_rm_commands"])
                ui.code(content, language="bash").classes("w-full text-xs")

        # ── Action buttons (above the log panel) ─────────────────────────
        action_row = ui.row().classes("gap-4 mt-4 items-center")
        with action_row:
            ui.button(
                "Back to Match",
                icon="arrow_back",
                on_click=lambda: navigate_to_step(WorkflowStep.MATCH),
            ).props("outline")

            # Use a mutable container so the lambda can capture the buttons after creation
            btn_refs: dict = {}

            def _build_summary_from_grid():
                """Build summary dict directly from adopt_grid_data (reflects UI toggles)."""
                adopt_rows = list(adopt_grid_data)  # shallow copy
                adopt_count = sum(1 for r in adopt_rows if r.get("action") == "adopt")
                protected_count = sum(
                    1 for r in adopt_rows
                    if r.get("protected") and r.get("action") == "adopt"
                )
                state_rm_cmds = generate_state_rm_commands(adopt_rows) if adopt_rows else []
                return {
                    "adopt_count": adopt_count,
                    "rm_count": len(state_rm_cmds),
                    "protected_count": protected_count,
                    "adopt_rows": adopt_rows,
                    "state_rm_commands": state_rm_cmds,
                }

            async def _force_refresh_adopt_grid(reason: str) -> None:
                """Best-effort AG Grid redraw to recover from transient blank-grid state."""
                try:
                    await adopt_grid.run_grid_method("setGridOption", "rowData", adopt_grid_data)
                    await adopt_grid.run_grid_method("refreshCells", {"force": True})
                    await adopt_grid.run_grid_method("redrawRows")
                    # region agent log
                    _dbg_673991(
                        "H24",
                        "adopt.py:_force_refresh_adopt_grid",
                        "forced aggrid refresh",
                        {
                            "reason": reason,
                            "row_count": len(adopt_grid_data),
                        },
                    )
                    # endregion
                except Exception as _grid_err:
                    adopt_grid.update()
                    # region agent log
                    _dbg_673991(
                        "H24",
                        "adopt.py:_force_refresh_adopt_grid",
                        "aggrid refresh fallback via update()",
                        {
                            "reason": reason,
                            "row_count": len(adopt_grid_data),
                            "error": str(_grid_err),
                        },
                    )
                    # endregion

            async def _on_plan_click():
                # Gate plan execution when target credentials are not loaded.
                has_creds_now = bool(
                    state.target_credentials.api_token and state.target_credentials.account_id
                )
                if not has_creds_now:
                    await _force_refresh_adopt_grid("blocked_missing_creds")
                    ui.notify(
                        "Target credentials are required for Plan Adoption. "
                        "Go to Fetch Target and click 'Load .env', then retry.",
                        type="warning",
                    )
                    return

                # Build summary directly from adopt_grid_data — it reflects all
                # user changes (including target-only resources toggled on the grid).
                fresh_summary = _build_summary_from_grid()
                # region agent log
                _dbg_673991(
                    "H20",
                    "adopt.py:_on_plan_click",
                    "plan click fresh summary from grid",
                    {
                        "adopt_count": fresh_summary.get("adopt_count", 0),
                        "row_count": len(fresh_summary.get("adopt_rows", [])),
                        "row_action_counts": {
                            "adopt": sum(
                                1
                                for r in fresh_summary.get("adopt_rows", [])
                                if r.get("action") == "adopt"
                            ),
                            "ignore": sum(
                                1
                                for r in fresh_summary.get("adopt_rows", [])
                                if r.get("action") == "ignore"
                            ),
                            "other": sum(
                                1
                                for r in fresh_summary.get("adopt_rows", [])
                                if r.get("action") not in {"adopt", "ignore"}
                            ),
                        },
                    },
                )
                # endregion
                if fresh_summary.get("adopt_count", 0) == 0:
                    # region agent log
                    _dbg_673991(
                        "H12",
                        "adopt.py:_on_plan_click",
                        "plan click blocked because nothing selected",
                        {
                            "adopt_count": fresh_summary.get("adopt_count", 0),
                            "total_rows": len(fresh_summary.get("adopt_rows", [])),
                        },
                    )
                    # endregion
                    await _force_refresh_adopt_grid("blocked_zero_adopt")
                    ui.notify(
                        "No resources selected for adoption. Set at least one row to "
                        "'Adopt' before planning.",
                        type="warning",
                    )
                    return

                # region agent log
                _dbg_673991(
                    "H27",
                    "adopt.py:_on_plan_click",
                    "force refresh grid before plan start",
                    {
                        "grid_rows": len(adopt_grid_data),
                        "adopt_count": fresh_summary.get("adopt_count", 0),
                    },
                )
                # endregion
                await _force_refresh_adopt_grid("before_plan_start")

                await _start_plan(
                    state, terminal, save_state, fresh_summary, tf_path,
                    btn_refs["plan"], btn_refs["apply"], btn_refs["skip"],
                    btn_refs["restore"], btn_refs["proceed"],
                    btn_refs=btn_refs,
                )

            async def _on_apply_click():
                fresh_summary = _build_summary_from_grid()
                await _start_apply(
                    state, terminal, save_state, fresh_summary, tf_path,
                    btn_refs["plan"], btn_refs["apply"], btn_refs["skip"],
                    btn_refs["restore"], btn_refs["proceed"],
                )

            plan_btn = ui.button(
                "Plan Adoption",
                icon="preview",
                on_click=_on_plan_click,
            ).style(f"background-color: {DBT_ORANGE};")
            if summary.get("adopt_count", 0) == 0:
                plan_btn.disable()

            apply_btn = ui.button(
                "Apply Adoption",
                icon="play_arrow",
                on_click=_on_apply_click,
            ).props("color=negative")
            apply_btn.set_visibility(False)

            # "View Plan" button — opens the plan viewer dialog with parsed stats
            def _open_plan_viewer():
                plan_output = btn_refs.get("_plan_output", "")
                if not plan_output:
                    ui.notify("No plan output available. Run Plan first.", type="warning")
                    return
                from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                dlg = create_plan_viewer_dialog(plan_output, "Adoption Plan")
                dlg.open()

            view_plan_btn = ui.button(
                "View Plan",
                icon="visibility",
                on_click=_open_plan_viewer,
            ).props("outline")
            view_plan_btn.set_visibility(False)

            # "View Output" button — always available, shows full terminal log
            def _open_output_viewer():
                raw = terminal.get_text() if hasattr(terminal, "get_text") else ""
                if not raw:
                    ui.notify("No output yet.", type="warning")
                    return
                from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                dlg = create_plan_viewer_dialog(raw, "Adoption Output")
                dlg.open()

            ui.button(
                "View Output",
                icon="open_in_full",
                on_click=_open_output_viewer,
            ).props("outline")

            skip_link = ui.button(
                "Skip — I'll handle imports manually",
                icon="skip_next",
                on_click=lambda: _skip_and_proceed(state, save_state, navigate_to_step),
            ).props("flat").classes("text-slate-500")

            restore_btn = ui.button(
                "Restore Backup",
                icon="restore",
                on_click=lambda: _restore_backup(state, terminal, save_state, tf_path),
            ).props("outline color=negative")
            restore_btn.set_visibility(False)

            proceed_btn = ui.button(
                "Continue to Configure",
                icon="arrow_forward",
                on_click=lambda: navigate_to_step(WorkflowStep.CONFIGURE),
            ).style(f"background-color: {DBT_ORANGE};")
            proceed_btn.set_visibility(False)

            btn_refs["plan"] = plan_btn
            btn_refs["apply"] = apply_btn
            btn_refs["view_plan"] = view_plan_btn
            btn_refs["skip"] = skip_link
            btn_refs["restore"] = restore_btn
            btn_refs["proceed"] = proceed_btn

        # ── Terminal output (below buttons) ───────────────────────────────
        terminal = TerminalOutput(show_timestamps=True)
        terminal.create(height="400px", title="Execution Log")


async def _start_plan(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    summary: dict,
    tf_path: Path,
    plan_btn,
    apply_btn,
    skip_link,
    restore_btn,
    proceed_btn,
    btn_refs: dict = None,
) -> None:
    """Start the plan phase of adoption (UI callback).

    This is an async function so that NiceGUI preserves the UI slot context
    throughout the entire plan execution.  After the plan finishes we can
    safely create UI elements (e.g. the plan viewer dialog).
    """
    if state.deploy.adopt_step_running:
        ui.notify("Adoption is already running", type="warning")
        return

    terminal.clear()
    terminal.info(f"Planning adoption of {summary['adopt_count']} resources...")
    terminal.info(f"Terraform directory: {tf_path}")
    terminal.info("")

    # Disable buttons during execution
    plan_btn.disable()
    apply_btn.set_visibility(False)
    skip_link.set_visibility(False)
    if btn_refs and "view_plan" in btn_refs:
        btn_refs["view_plan"].set_visibility(False)

    plan_stdout = await _run_adopt_plan(
        state, terminal, save_state, summary, tf_path,
    )

    if plan_stdout is not None:
        # ── Plan succeeded — update buttons and auto-open the plan viewer ──
        if btn_refs is not None:
            btn_refs["_plan_output"] = plan_stdout
            btn_refs["view_plan"].set_visibility(True)
        plan_btn.set_visibility(False)
        apply_btn.set_visibility(True)
        restore_btn.set_visibility(True)

        # Auto-open the plan viewer dialog (safe here because we are in UI context)
        from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
        dlg = create_plan_viewer_dialog(plan_stdout, "Adoption Plan")
        dlg.open()
    else:
        # ── Plan failed — re-enable the plan button ────────────────────────
        plan_btn.enable()
        plan_btn.set_visibility(True)
        apply_btn.set_visibility(False)
        skip_link.set_visibility(True)
        if state.deploy.adopt_step_backup_path:
            restore_btn.set_visibility(True)


async def _start_apply(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    summary: dict,
    tf_path: Path,
    plan_btn,
    apply_btn,
    skip_link,
    restore_btn,
    proceed_btn,
) -> None:
    """Start the apply phase of adoption (UI callback).

    Awaiting (not ensure_future) preserves NiceGUI's slot context so UI
    updates in on_complete/on_failure work without 'slot stack empty' errors.
    """
    if state.deploy.adopt_step_running:
        ui.notify("Adoption is already running", type="warning")
        return

    # Disable buttons during execution
    apply_btn.disable()
    restore_btn.set_visibility(False)

    try:
        await _run_adopt_apply(state, terminal, save_state, summary, tf_path)

        # ── Success — UI updates run in correct slot context ──
        apply_btn.set_visibility(False)
        restore_btn.set_visibility(False)
        proceed_btn.set_visibility(True)
        # Reload the page so the grid refreshes with "adopted" status
        ui.navigate.reload()

    except Exception:
        # ── Failure — re-enable buttons for retry ──
        apply_btn.enable()
        apply_btn.set_visibility(True)
        if state.deploy.adopt_step_backup_path:
            restore_btn.set_visibility(True)
        # The terminal output already shows the error details


def _skip_and_proceed(
    state: AppState,
    save_state: Callable[[], None],
    navigate_to_step: Callable[[WorkflowStep], None],
) -> None:
    """Skip the adopt step and proceed to Configure."""
    state.deploy.adopt_step_complete = True
    state.deploy.adopt_step_skipped = True
    save_state()
    _persist_adopt_workflow_state(state, complete=True, skipped=True)
    navigate_to_step(WorkflowStep.CONFIGURE)


async def _restore_backup(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    tf_path: Path,
) -> None:
    """Restore terraform.tfstate from the adopt backup."""
    backup_file = tf_path / "terraform.tfstate.adopt-backup"
    tfstate_file = tf_path / "terraform.tfstate"

    if not backup_file.exists():
        terminal.error("Backup file not found — cannot restore")
        ui.notify("No backup file available", type="negative")
        return

    terminal.info("")
    terminal.info("━━━ RESTORING STATE FROM BACKUP ━━━")

    try:
        shutil.copy2(str(backup_file), str(tfstate_file))
        terminal.success(f"✓ State restored from {backup_file.name}")
        state.deploy.adopt_step_error = ""
        state.deploy.adopt_step_status = "idle"
        save_state()
        ui.notify("State restored from backup", type="positive")
    except Exception as e:
        terminal.error(f"Failed to restore backup: {e}")
        ui.notify(f"Restore failed: {e}", type="negative")
