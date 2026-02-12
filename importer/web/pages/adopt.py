"""Adopt step page — automated terraform state rm + import for adopted resources.

PRD 43.02: Dedicated Adoption Terraform Step.

This page sits between Match and Configure in the Migration workflow. It automates
the terraform state rm + terraform apply (import) cycle that was previously manual.
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

from nicegui import ui

from importer.web.state import AppState, WorkflowStep
from importer.web.components.terminal_output import TerminalOutput
from importer.web.utils.terraform_import import (
    generate_state_rm_commands,
    write_adopt_imports_file,
)
from importer.web.utils.adoption_yaml_updater import (
    cleanup_unadopted_yaml_configs,
    inject_adopted_resource_configs,
)

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


def _get_terraform_dir(state: AppState) -> Path:
    """Resolve the terraform directory from state."""
    tf_dir = state.deploy.terraform_dir or "deployments/migration"
    tf_path = Path(tf_dir)
    if not tf_path.is_absolute():
        project_root = (
            Path(state.fetch.output_dir).parent.parent
            if state.fetch.output_dir
            else Path.cwd()
        )
        tf_path = project_root / tf_dir
    return tf_path


def _get_terraform_env(state: AppState) -> dict:
    """Get environment variables for terraform commands (mirrors deploy.py)."""
    env = dict(os.environ)

    api_token = state.target_credentials.api_token
    account_id = state.target_credentials.account_id
    host_url = state.target_credentials.host_url

    base_host = (host_url or "https://cloud.getdbt.com").rstrip("/")
    if not base_host.endswith("/api"):
        host_url = f"{base_host}/api"
    else:
        host_url = base_host

    env["TF_VAR_dbt_account_id"] = str(account_id)
    env["TF_VAR_dbt_token"] = api_token
    env["TF_VAR_dbt_host_url"] = host_url

    token_type = state.target_credentials.token_type
    env["DBT_CLOUD_TOKEN"] = api_token
    env["DBT_CLOUD_ACCOUNT_ID"] = str(account_id)
    env["DBT_CLOUD_HOST_URL"] = host_url
    if token_type == "service_token":
        env["DBT_CLOUD_TOKEN_TYPE"] = "service"
    return env


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

    if not source_items or not target_items:
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

    grid_data = build_grid_data(
        source_items,
        target_items,
        state.map.confirmed_mappings,
        rejected_keys,
        clone_configs,
        state_result=state_result,
        protected_resources=state.map.protected_resources,
    )

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


# Drift statuses that indicate the resource needs to be imported into TF state
_ADOPTABLE_DRIFT = {"not_in_state", "id_mismatch", "attr_mismatch"}


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
    # Build a lookup from confirmed_mappings keyed by source_key
    cm_by_key: dict[str, str] = {}
    if confirmed_mappings:
        for m in confirmed_mappings:
            sk = m.get("source_key", "")
            cm_by_key[sk] = m.get("action", "match")

    # Filter by drift status — these resources need to be imported into TF.
    # Only adopt if confirmed_mappings explicitly says "adopt".
    adopt_rows = []
    for r in grid_rows:
        if r.get("drift_status") in _ADOPTABLE_DRIFT and r.get("target_id"):
            source_key = r.get("source_key", "")

            # Look up in confirmed_mappings: try exact key, then target__ variant
            cm_action = cm_by_key.get(source_key)
            if cm_action is None and not source_key.startswith("target__"):
                cm_action = cm_by_key.get(f"target__{source_key}")

            # Only adopt if explicitly "adopt" in confirmed_mappings
            if cm_action == "adopt":
                r["action"] = "adopt"
            else:
                r["action"] = "ignore"
            adopt_rows.append(r)

    adopt_count = sum(1 for r in adopt_rows if r.get("action") == "adopt")
    protected_count = sum(1 for r in adopt_rows if r.get("protected") and r.get("action") == "adopt")
    state_rm_cmds = generate_state_rm_commands(grid_rows) if adopt_rows else []

    # #region agent log
    import json as _json_dbg2; open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a").write(_json_dbg2.dumps({"id":"compute_summary","timestamp":__import__('time').time(),"location":"adopt.py:_compute_adopt_summary","message":"Summary computed","data":{"adopt_count":adopt_count,"total_rows":len(adopt_rows),"cm_by_key":cm_by_key,"row_details":[{"sk":r.get("source_key",""),"action":r.get("action",""),"drift":r.get("drift_status",""),"tid":r.get("target_id","")} for r in adopt_rows]},"hypothesisId":"B"}) + "\n")
    # #endregion

    return {
        "adopt_count": adopt_count,
        "rm_count": len(state_rm_cmds),
        "protected_count": protected_count,
        "adopt_rows": adopt_rows,
        "state_rm_commands": state_rm_cmds,
    }


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

                for line in result.stdout.split("\n"):
                    if line.strip():
                        terminal.info_auto(f"  {line}")
                for line in result.stderr.split("\n"):
                    if line.strip():
                        terminal.warning(f"  {line}")

                if result.returncode != 0:
                    error_msg = f"terraform state rm failed for {address} (exit code {result.returncode})"
                    terminal.error(error_msg)
                    raise RuntimeError(error_msg)

                terminal.success(f"  ✓ Removed: {address}")

            terminal.info("")
        else:
            terminal.info("━━━ PHASE 2: STATE RM — SKIPPED (no mismatches) ━━━")
            terminal.info("")

        # ── Phase 3: Inject Adopted Resource Configs ─────────────────────
        # For target-only resources being adopted, the deployment YAML
        # (dbt-cloud-config.yml) may not contain a matching config block.
        # Without it Terraform has nothing to import into and plan fails
        # with "Configuration for import target does not exist".
        # This phase reads the target baseline YAML (normalised from the
        # target fetch) and copies the entries for adopted resources into
        # the deployment YAML.
        terminal.set_title("Output — INJECT CONFIG")
        terminal.info("━━━ PHASE 3: INJECT ADOPTED CONFIG ━━━")

        # Filter to only action="adopt" rows for import block generation.
        # adopt_rows contains ALL adoptable rows (including ignored) for display.
        rows_to_import = [r for r in adopt_rows if r.get("action") == "adopt"]

        deployment_yaml_path = tf_path / "dbt-cloud-config.yml"
        target_baseline = state.target_fetch.target_baseline_yaml

        # Step 3a: Clean up stale YAML entries from previous plan runs.
        # If the user switched a resource from "adopt" to "ignore" since the
        # last plan, the old injected config entry must be removed or
        # Terraform will try to CREATE the resource instead of importing it.
        if deployment_yaml_path.exists():
            try:
                _, cleanup_count = cleanup_unadopted_yaml_configs(
                    deployment_yaml=str(deployment_yaml_path),
                    all_grid_rows=adopt_rows,
                )
                if cleanup_count > 0:
                    terminal.info(
                        f"  Cleaned up {cleanup_count} stale config(s) from prior plan run"
                    )
            except Exception as exc:
                terminal.warning(f"  Config cleanup warning: {exc}")

        # Step 3b: Inject config entries for currently adopted resources.
        if target_baseline and deployment_yaml_path.exists():
            try:
                updated_yaml, inject_count = inject_adopted_resource_configs(
                    deployment_yaml=str(deployment_yaml_path),
                    adopt_rows=rows_to_import,
                    target_baseline_yaml=target_baseline,
                )
                if inject_count > 0:
                    terminal.success(
                        f"✓ Injected {inject_count} adopted resource config(s) into {deployment_yaml_path.name}"
                    )
                    for row in rows_to_import:
                        terminal.info(
                            f"  • {row.get('source_type', '?')}: "
                            f"{row.get('source_name', row.get('source_key', '?'))}"
                        )
                else:
                    terminal.info("  All adopted resources already have config entries — no injection needed")
            except Exception as exc:
                terminal.warning(f"  Config injection warning: {exc}")
                terminal.info("  Proceeding — terraform plan will report any missing config")
        else:
            if not target_baseline:
                terminal.info("  No target baseline YAML available — skipping config injection")
            elif not deployment_yaml_path.exists():
                terminal.info(f"  {deployment_yaml_path.name} not found — skipping config injection")

        terminal.info("")

        # ── Phase 4: Write Import Blocks ─────────────────────────────────
        state.deploy.adopt_step_status = "write_imports"
        save_state()
        terminal.set_title("Output — WRITE IMPORTS")

        terminal.info(f"━━━ PHASE 4: WRITE IMPORT BLOCKS ({len(rows_to_import)} resources) ━━━")

        output_path, error = write_adopt_imports_file(
            rows_to_import,
            tf_path,
            filename="adopt_imports.tf",
        )

        if error:
            terminal.error(f"Error writing import blocks: {error}")
            raise RuntimeError(f"Failed to write import blocks: {error}")

        terminal.success(f"✓ Written {len(rows_to_import)} import blocks to {output_path}")
        for row in rows_to_import:
            terminal.info(f"  • {row.get('source_type', '?')}: {row.get('source_name', row.get('source_key', '?'))} → ID {row.get('target_id', '?')}")
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

        for line in result.stdout.split("\n"):
            if line.strip():
                terminal.info_auto(f"  {line}")
        for line in result.stderr.split("\n"):
            if line.strip():
                terminal.warning(f"  {line}")

        if result.returncode != 0:
            raise RuntimeError(f"terraform init failed (exit code {result.returncode})")

        terminal.success("✓ Terraform initialized")
        terminal.info("")

        # ── Phase 6: Terraform Plan ──────────────────────────────────────
        state.deploy.adopt_step_status = "plan"
        save_state()
        terminal.set_title("Output — PLAN")
        terminal.info("━━━ PHASE 6: TERRAFORM PLAN ━━━")

        # Build -target flags from the adopt_imports.tf that was written in Phase 4.
        # This scopes the plan to ONLY the resources being imported, preventing
        # unrelated drift from cluttering the plan output.
        target_flags: list[str] = []
        adopt_imports_content = (tf_path / "adopt_imports.tf").read_text(encoding="utf-8")
        for match in re.finditer(r'to\s*=\s*(.+)', adopt_imports_content):
            addr = match.group(1).strip()
            if addr:
                target_flags.extend(["-target", addr])

        plan_cmd = ["terraform", "plan", "-out=adopt.tfplan", "-no-color"] + target_flags

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

        # Color-code plan output lines like the deploy page
        for line in result.stdout.split("\n"):
            if line.strip():
                if "+" in line and "create" in line.lower():
                    terminal.success(line)
                elif "-" in line and "destroy" in line.lower():
                    terminal.error(line)
                elif "~" in line and "change" in line.lower():
                    terminal.warning(line)
                else:
                    terminal.info_auto(f"  {line}")
        for line in result.stderr.split("\n"):
            if line.strip():
                terminal.warning(f"  {line}")

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
        terminal.error(f"━━━ PLAN FAILED ━━━")
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


async def _run_adopt_apply(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    summary: dict,
    tf_path: Path,
    on_complete: Callable[[], None],
    on_failure: Callable[[str], None],
) -> None:
    """Apply the saved adoption plan (``adopt.tfplan``).

    Phases: apply → verify → cleanup.
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

        for line in result.stdout.split("\n"):
            if line.strip():
                terminal.info_auto(f"  {line}")
        for line in result.stderr.split("\n"):
            if line.strip():
                terminal.warning(f"  {line}")

        if result.returncode != 0:
            raise RuntimeError(f"terraform apply failed (exit code {result.returncode})")

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

        state_addresses = set()
        for line in result.stdout.split("\n"):
            addr = line.strip()
            if addr:
                state_addresses.add(addr)
                terminal.debug(f"  {addr}")

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
        terminal.success(f"Successfully imported {len(adopt_rows)} resources into Terraform state.")

        # Update state
        state.deploy.adopt_step_complete = True
        state.deploy.adopt_step_running = False
        state.deploy.adopt_step_status = "complete"
        state.deploy.adopt_step_last_output = terminal.get_text()
        state.deploy.reconcile_imports_generated = True
        save_state()

        on_complete()

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Adopt apply failed: {error_msg}")
        terminal.error("")
        terminal.error(f"━━━ ADOPTION FAILED ━━━")
        terminal.error(f"Error: {error_msg}")

        if backup_file.exists():
            terminal.warning(f"State backup available at: {backup_file.name}")
            terminal.warning("Use 'Restore Backup' button to revert to pre-adoption state.")

        state.deploy.adopt_step_running = False
        state.deploy.adopt_step_status = "failed"
        state.deploy.adopt_step_error = error_msg
        state.deploy.adopt_step_last_output = terminal.get_text()
        save_state()

        on_failure(error_msg)


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
    has_adopt_rows = summary["adopt_count"] > 0

    # ── Page header ──────────────────────────────────────────────────────
    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-4"):
        with ui.row().classes("w-full items-center gap-3"):
            ui.icon("download_for_offline", size="2rem").style(f"color: {DBT_ORANGE};")
            ui.label("Adopt Resources into Terraform State").classes("text-2xl font-bold")

        ui.label(
            "This step automates the terraform state rm + import cycle for resources "
            "you marked as 'adopt' on the Match page."
        ).classes("text-slate-600 dark:text-slate-400 text-sm")

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
            with ui.card().classes("w-full p-6"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("check_circle", size="1.5rem").style(f"color: {STATUS_SUCCESS};")
                    ui.label("Adoption Complete").classes("text-lg font-semibold text-green-600")

                ui.label(
                    f"Successfully imported {summary['adopt_count']} resources into Terraform state."
                ).classes("text-slate-600 dark:text-slate-400 mt-2")

                with ui.row().classes("gap-4 mt-4"):
                    ui.button(
                        "Back to Match",
                        icon="arrow_back",
                        on_click=lambda: navigate_to_step(WorkflowStep.MATCH),
                    ).props("outline")

                    async def rerun_adoption():
                        state.deploy.adopt_step_complete = False
                        state.deploy.adopt_step_status = ""
                        state.deploy.adopt_step_error = ""
                        save_state()
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

            return

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
        adopt_grid_data = []
        for row in summary["adopt_rows"]:
            # Display name: prefer source_name, fall back to source_key,
            # and always strip the internal "target__" prefix so the UI
            # shows the clean resource name (e.g. "everyone" not "target__everyone").
            _display_name = row.get("source_name") or row.get("source_key", "?")
            if _display_name.startswith("target__"):
                _display_name = _display_name[len("target__"):]
            adopt_grid_data.append({
                "source_key": row.get("source_key", ""),
                "source_type": row.get("source_type", row.get("resource_type", "?")),
                "source_name": _display_name,
                "target_id": row.get("target_id", ""),
                "target_name": row.get("target_name", ""),
                "drift_status": row.get("drift_status", ""),
                "state_address": row.get("state_address", ""),
                "protected": row.get("protected", False),
                "project_name": row.get("project_name", ""),
                "project_id": row.get("project_id", ""),
                "action": row.get("action", "adopt"),  # Respect user choice from Match page
            })

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
                "headerTooltip": "Protected from destroy",
                "width": 55,
                "maxWidth": 55,
                "cellStyle": {"textAlign": "center"},
                ":cellRenderer": """params => params.value ? '<span style="color: #3B82F6; font-size: 16px;">🛡️</span>' : ''""",
            },
            {
                "field": "action",
                "headerName": "Action",
                "width": 120,
                "editable": True,
                "cellEditor": "agSelectCellEditor",
                "cellEditorParams": {"values": ["adopt", "ignore"]},
                ":valueFormatter": """params => {
                    const labels = {'adopt': '📥 Adopt', 'ignore': '🚫 Ignore'};
                    return labels[params.value] || params.value;
                }""",
                "cellClassRules": {
                    "action-adopt": "x === 'adopt'",
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
                "row-ignored": "data.action === 'ignore'",
            },
            "stopEditingWhenCellsLoseFocus": True,
            "singleClickEdit": True,
            "animateRows": False,
        }

        grid_title_label = ui.label(f"Resources to Adopt ({summary['adopt_count']})").classes("text-lg font-semibold")

        # Add AG Grid styling
        ui.add_head_html("""
        <style>
        .adopt-grid .ag-row.row-ignored { opacity: 0.5; }
        .adopt-grid .action-adopt { color: #8B5CF6; font-weight: 600; }
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
        ).classes("w-full adopt-grid ag-theme-quartz-auto-dark").style(
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

        # ── Grid event handlers ──────────────────────────────────────────
        def _on_adopt_cell_clicked(e):
            """Handle cell clicks in the adopt grid."""
            col_id = e.args.get("colId", "")
            row = e.args.get("data", {})

            if col_id == "details_btn" and row:
                _show_detail(row)

        def _on_adopt_cell_changed(e):
            """Handle action changes in the adopt grid (adopt ↔ ignore)."""
            row = e.args.get("data", {})
            if not row:
                return

            source_key = row.get("source_key", "")
            new_action = row.get("action", "adopt")

            # #region agent log
            import json as _json_dbg; open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a").write(_json_dbg.dumps({"id":"cell_changed","timestamp":__import__('time').time(),"location":"adopt.py:_on_adopt_cell_changed","message":"Cell changed","data":{"source_key":source_key,"new_action":new_action,"cm_keys":[m.get("source_key","") for m in state.map.confirmed_mappings],"cm_actions":[m.get("action","?") for m in state.map.confirmed_mappings]},"hypothesisId":"A"}) + "\n")
            # #endregion

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
                    mapping["action"] = new_action
                    _found = True
                    break
            if not _found and not source_key.startswith("target__"):
                # Try the reverse: grid key has prefix, mapping doesn't
                bare = source_key.removeprefix("target__")
                for mapping in state.map.confirmed_mappings:
                    if mapping.get("source_key") == bare:
                        mapping["action"] = new_action
                        _found = True
                        break
            if not _found:
                # Target-only resource not in confirmed_mappings — add it
                state.map.confirmed_mappings.append({
                    "source_key": source_key,
                    "action": new_action,
                })

            # #region agent log
            open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a").write(_json_dbg.dumps({"id":"cell_changed_after","timestamp":__import__('time').time(),"location":"adopt.py:_on_adopt_cell_changed:after","message":"After update","data":{"found":_found,"cm_actions_after":[m.get("action","?") for m in state.map.confirmed_mappings],"cm_keys":[m.get("source_key","") for m in state.map.confirmed_mappings]},"hypothesisId":"A"}) + "\n")
            # #endregion

            save_state()

            # Update adopt_grid_data in-place to track user choices
            for r in adopt_grid_data:
                if r.get("source_key") == source_key:
                    r["action"] = new_action
                    break

            # Compute counts from adopt_grid_data (reflects user choices)
            adopt_count = sum(1 for r in adopt_grid_data if r.get("action") == "adopt")
            ignored_count = len(adopt_grid_data) - adopt_count
            protected_adopt = sum(1 for r in adopt_grid_data if r.get("action") == "adopt" and r.get("protected"))

            # Update ALL summary displays
            summary_label.set_text(f"📥 {adopt_count} to adopt, 🚫 {ignored_count} ignored")
            adopt_count_label.set_text(str(adopt_count))
            protected_count_label.set_text(str(protected_adopt))
            grid_title_label.set_text(f"Resources to Adopt ({adopt_count})")

            # Invalidate any stale plan — the user changed their selections,
            # so the previous plan (if any) no longer matches.
            # Show the Plan button, hide Apply and View Plan.
            if btn_refs.get("plan"):
                btn_refs["plan"].set_visibility(True)
                btn_refs["plan"].enable()
            if btn_refs.get("apply"):
                btn_refs["apply"].set_visibility(False)
            if btn_refs.get("view_plan"):
                btn_refs["view_plan"].set_visibility(False)
            if btn_refs.get("skip"):
                btn_refs["skip"].set_visibility(True)

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

            async def _on_plan_click():
                # Build summary directly from adopt_grid_data — it reflects all
                # user changes (including target-only resources toggled on the grid).
                fresh_summary = _build_summary_from_grid()
                await _start_plan(
                    state, terminal, save_state, fresh_summary, tf_path,
                    btn_refs["plan"], btn_refs["apply"], btn_refs["skip"],
                    btn_refs["restore"], btn_refs["proceed"],
                    btn_refs=btn_refs,
                )

            def _on_apply_click():
                fresh_summary = _build_summary_from_grid()
                _start_apply(
                    state, terminal, save_state, fresh_summary, tf_path,
                    btn_refs["plan"], btn_refs["apply"], btn_refs["skip"],
                    btn_refs["restore"], btn_refs["proceed"],
                )

            plan_btn = ui.button(
                "Plan Adoption",
                icon="preview",
                on_click=_on_plan_click,
            ).style(f"background-color: {DBT_ORANGE};")

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

            view_output_btn = ui.button(
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


def _start_apply(
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
    """Start the apply phase of adoption (UI callback)."""
    if state.deploy.adopt_step_running:
        ui.notify("Adoption is already running", type="warning")
        return

    # Disable buttons during execution
    apply_btn.disable()
    restore_btn.set_visibility(False)

    def on_complete():
        apply_btn.set_visibility(False)
        restore_btn.set_visibility(False)
        proceed_btn.set_visibility(True)
        # Note: ui.notify() cannot be called from background tasks (no slot context)
        # The terminal output already shows the adoption success message

    def on_failure(error_msg: str):
        apply_btn.enable()
        apply_btn.set_visibility(True)
        if state.deploy.adopt_step_backup_path:
            restore_btn.set_visibility(True)
        # Note: ui.notify() cannot be called from background tasks (no slot context)
        # The terminal output already shows the error details

    asyncio.ensure_future(
        _run_adopt_apply(
            state, terminal, save_state, summary, tf_path,
            on_complete, on_failure,
        )
    )


def _skip_and_proceed(
    state: AppState,
    save_state: Callable[[], None],
    navigate_to_step: Callable[[WorkflowStep], None],
) -> None:
    """Skip the adopt step and proceed to Configure."""
    state.deploy.adopt_step_complete = True
    state.deploy.adopt_step_skipped = True
    save_state()
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
