"""Unified headless pipeline for protection + adoption artifact generation.

This module is the **single source of truth** for generating all Terraform
artifacts related to protection and adoption workflows.  UI pages call
``run_generate_pipeline()`` and then hand the ``PipelineResult`` to the
terraform plan/apply buttons.

See PRD 43.03 — Unified Protect & Adopt Pipeline.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

import yaml

if TYPE_CHECKING:
    from importer.web.state import AppState

from importer.web.utils.protection_manager import (
    RESOURCE_TYPE_MAP,
    ProtectionMismatch,
    detect_protection_mismatches,
    generate_repair_moved_blocks,
)
from importer.web.utils.terraform_helpers import (
    MODULE_PREFIX,
    build_target_flags,
    read_tf_state_addresses,
    resolve_deployment_paths,
)

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Outcome of ``run_generate_pipeline``."""

    yaml_updated: bool = False
    hcl_regenerated: bool = False
    moves_file: Optional[Path] = None       # protection_moves.tf
    imports_file: Optional[Path] = None      # adopt_imports.tf
    target_addresses: list[str] = field(default_factory=list)
    target_flags: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    intents_applied: list[str] = field(default_factory=list)
    moves_count: int = 0
    imports_count: int = 0

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _progress(on_progress: Optional[Callable[[str], None]], msg: str) -> None:
    if on_progress:
        on_progress(msg)
    logger.info(msg)


def _is_cancelled(is_cancelled: Optional[Callable[[], bool]]) -> bool:
    if is_cancelled and is_cancelled():
        return True
    return False


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def run_generate_pipeline(
    state: "AppState",
    *,
    # What to generate
    include_adopt: bool = False,
    adopt_rows: Optional[list[dict]] = None,
    include_protection_moves: bool = True,
    # Options
    merge_baseline: bool = True,
    regenerate_hcl: bool = True,
    # Progress / cancellation
    on_progress: Optional[Callable[[str], None]] = None,
    is_cancelled_fn: Optional[Callable[[], bool]] = None,
) -> PipelineResult:
    """Run the unified generation pipeline.

    Steps:
        1. Resolve paths
        2. Read pending + all protection intents
        3. Merge baseline YAML (if ``merge_baseline``)
        4. Apply all protection flags to YAML
        5. Regenerate HCL (if ``regenerate_hcl``)
        6. Generate ``protection_moves.tf`` (if ``include_protection_moves``)
        7. Generate / update ``adopt_imports.tf`` (if ``include_adopt``)
        8. Mark intents as applied to YAML
        9. Build target addresses from both ``.tf`` files
       10. Return ``PipelineResult``

    This function is **headless**: no NiceGUI imports, no UI side-effects.
    All progress is reported via the ``on_progress`` callback.
    """
    result = PipelineResult()

    # ------------------------------------------------------------------
    # Step 1: Resolve paths
    # ------------------------------------------------------------------
    _progress(on_progress, "Resolving deployment paths...")
    tf_path, yaml_file, baseline_yaml_path = resolve_deployment_paths(state)
    # region agent log
    _dbg_db419a(
        "H66",
        "generate_pipeline.py:run_generate_pipeline:path_snapshot",
        "pipeline path snapshot after resolve_deployment_paths",
        {
            "active_project": getattr(state, "active_project", "") or "",
            "project_path": str(getattr(state, "project_path", "") or ""),
            "terraform_dir_state": str(getattr(state.deploy, "terraform_dir", "") or ""),
            "map_last_yaml_file": str(getattr(state.map, "last_yaml_file", "") or ""),
            "resolved_tf_path": str(tf_path),
            "resolved_yaml_file": str(yaml_file),
            "baseline_yaml_path": str(baseline_yaml_path) if baseline_yaml_path else "",
            "tf_path_exists": bool(tf_path.exists()),
            "yaml_exists_initial": bool(yaml_file.exists()),
        },
    )
    # endregion

    if not tf_path.exists():
        result.errors.append(f"Terraform directory does not exist: {tf_path}")
        return result

    protection_intent_manager = state.get_protection_intent_manager()

    # ------------------------------------------------------------------
    # Step 2: Read pending intents
    # ------------------------------------------------------------------
    _progress(on_progress, "Reading pending intents...")

    pending_yaml = protection_intent_manager.get_pending_yaml_updates()
    pending_tf = {
        k: i
        for k, i in protection_intent_manager._intent.items()
        if i.applied_to_yaml and not i.applied_to_tf_state
    }
    pending = {**pending_yaml, **pending_tf}

    _progress(
        on_progress,
        f"  Found {len(pending_yaml)} YAML-pending, {len(pending_tf)} TF-pending intents",
    )
    # region agent log
    _dbg_db419a(
        "H62",
        "generate_pipeline.py:run_generate_pipeline:pending_intents",
        "pending intent breakdown before generation",
        {
            "include_adopt": bool(include_adopt),
            "include_protection_moves": bool(include_protection_moves),
            "pending_keys": sorted(list(pending.keys()))[:50],
            "pending_rep_keys": sorted([k for k in pending.keys() if str(k).startswith("REP:")])[:30],
            "pending_prep_keys": sorted([k for k in pending.keys() if str(k).startswith("PREP:")])[:30],
            "pending_protected_true": sorted([k for k, v in pending.items() if bool(getattr(v, "protected", False))])[:30],
            "pending_protected_false": sorted([k for k, v in pending.items() if not bool(getattr(v, "protected", False))])[:30],
        },
    )
    # endregion
    # region agent log
    try:
        yaml_snapshot = {}
        if yaml_file.exists():
            yaml_snapshot = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        globals_block = yaml_snapshot.get("globals", {}) if isinstance(yaml_snapshot, dict) else {}
        projects_block = yaml_snapshot.get("projects", []) if isinstance(yaml_snapshot, dict) else []
        global_repo_keys = []
        for repo in globals_block.get("repositories", []) if isinstance(globals_block, dict) else []:
            if isinstance(repo, dict) and repo.get("key"):
                global_repo_keys.append(str(repo.get("key")))
        project_repo_refs = []
        project_nested_repo_keys = []
        for project in projects_block if isinstance(projects_block, list) else []:
            if not isinstance(project, dict):
                continue
            if project.get("repository"):
                project_repo_refs.append(str(project.get("repository")))
            for repo in project.get("repositories", []) if isinstance(project.get("repositories"), list) else []:
                if isinstance(repo, dict) and repo.get("key"):
                    project_nested_repo_keys.append(str(repo.get("key")))
        _dbg_db419a(
            "H61",
            "generate_pipeline.py:run_generate_pipeline:yaml_repo_shape",
            "deployment YAML repository structure snapshot",
            {
                "global_repo_count": len(global_repo_keys),
                "global_repo_keys": sorted(global_repo_keys)[:30],
                "project_repo_ref_count": len(project_repo_refs),
                "project_repo_refs": sorted(project_repo_refs)[:30],
                "project_nested_repo_count": len(project_nested_repo_keys),
                "project_nested_repo_keys": sorted(project_nested_repo_keys)[:30],
            },
        )
    except Exception as e:
        _dbg_db419a(
            "H61",
            "generate_pipeline.py:run_generate_pipeline:yaml_repo_shape",
            "failed to inspect YAML repository structure",
            {"error": str(e)},
        )
    # endregion

    if _is_cancelled(is_cancelled_fn):
        return result

    # ------------------------------------------------------------------
    # Step 3: Merge baseline YAML
    # ------------------------------------------------------------------
    adopted_project_keys: set[str] = set()
    if include_adopt and adopt_rows:
        adopted_project_keys = {
            str(r.get("source_key", "")).removeprefix("target__")
            for r in adopt_rows
            if r.get("action") == "adopt" and r.get("source_type") == "PRJ"
        }
    adopt_only_non_project = include_adopt and (not include_protection_moves) and (not adopted_project_keys)

    if merge_baseline and yaml_file.exists():
        _progress(on_progress, "Merging target baseline into deployment YAML...")
        try:
            if adopt_only_non_project:
                _progress(
                    on_progress,
                    "  Skipping baseline merge (no adopted projects selected)",
                )
            elif baseline_yaml_path and baseline_yaml_path.exists():
                from importer.web.utils.adoption_yaml_updater import merge_yaml_configs

                with open(str(baseline_yaml_path), "r") as bf:
                    baseline_config = yaml.safe_load(bf) or {}
                with open(str(yaml_file), "r") as df:
                    deploy_config = yaml.safe_load(df) or {}

                # Filter baseline to projects already in deploy config
                deploy_project_keys = {
                    p.get("key")
                    for p in deploy_config.get("projects", [])
                    if p.get("key")
                }
                # Preserve target-only adopted projects even when they are not
                # present in deploy YAML yet (e.g. source_key="target__not_terraform").
                deploy_project_keys.update({k for k in adopted_project_keys if k})
                if baseline_config.get("projects"):
                    baseline_config["projects"] = [
                        p
                        for p in baseline_config["projects"]
                        if p.get("key") in deploy_project_keys
                    ]
                # In adopt-only runs, only project records should be merged from
                # target baseline. Merging baseline globals pollutes deployment YAML
                # and causes unrelated resources in later full deploy plans.
                if include_adopt and not include_protection_moves:
                    baseline_config = {
                        "projects": baseline_config.get("projects", []),
                    }

                merged = merge_yaml_configs(baseline_config, deploy_config)
                with open(str(yaml_file), "w") as wf:
                    yaml.dump(
                        merged,
                        wf,
                        default_flow_style=False,
                        sort_keys=False,
                        allow_unicode=True,
                    )
                _progress(on_progress, "  Merged target baseline (fills missing resources)")
            else:
                _progress(on_progress, "  No target baseline available — skipping merge")
        except Exception as e:
            logger.warning(f"Baseline merge failed (non-fatal): {e}")
            _progress(on_progress, f"  Baseline merge skipped: {e}")

    if _is_cancelled(is_cancelled_fn):
        return result

    # ------------------------------------------------------------------
    # Step 4: Apply protection flags to YAML
    # ------------------------------------------------------------------
    if adopt_only_non_project:
        _progress(
            on_progress,
            "Skipping protection+HCL updates (adopt-only non-project import)",
        )
        # In adopt-only repo/link flows, still persist repository-level protection
        # intent so projects_v2 can materialize the correct repositories collection.
        try:
            repo_intents = {
                k: v
                for k, v in pending.items()
                if isinstance(k, str) and ":" in k and k.split(":", 1)[0] in {"REP", "PREP", "REPO"}
            }
            repo_overrides: list[dict] = []
            if repo_intents and yaml_file.exists():
                config = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                projects = config.get("projects", []) if isinstance(config, dict) else []
                changed = False
                for intent_key, intent in repo_intents.items():
                    rtype, rkey = intent_key.split(":", 1)
                    normalized_key = rkey
                    if rtype in {"REP", "PREP"} and normalized_key.startswith("dbt_ep_"):
                        candidate = normalized_key[len("dbt_ep_"):]
                        if candidate:
                            normalized_key = candidate
                    matched = False
                    for project in projects if isinstance(projects, list) else []:
                        if not isinstance(project, dict):
                            continue
                        if str(project.get("key", "")) != normalized_key:
                            continue
                        project["repository_protected"] = bool(intent.protected)
                        matched = True
                        changed = True
                        repo_overrides.append(
                            {
                                "intent_key": intent_key,
                                "project_key": normalized_key,
                                "repository_protected": bool(intent.protected),
                            }
                        )
                        break
                    if not matched:
                        repo_overrides.append(
                            {
                                "intent_key": intent_key,
                                "project_key": normalized_key,
                                "repository_protected": bool(intent.protected),
                                "matched_project": False,
                            }
                        )
                if changed:
                    yaml_file.write_text(
                        yaml.dump(
                            config,
                            default_flow_style=False,
                            sort_keys=False,
                            allow_unicode=True,
                        ),
                        encoding="utf-8",
                    )
                    result.yaml_updated = True
                    _progress(
                        on_progress,
                        f"  Applied repository_protected overrides for {len(repo_intents)} repo intent(s)",
                    )
            # region agent log
            _dbg_db419a(
                "H63",
                "generate_pipeline.py:run_generate_pipeline:repo_only_protection_overrides",
                "applied repo-level repository_protected overrides in adopt-only flow",
                {
                    "repo_intent_count": len(repo_intents),
                    "repo_overrides": repo_overrides[:30],
                    "yaml_exists": yaml_file.exists(),
                },
            )
            # endregion
        except Exception as e:
            _progress(on_progress, f"  Repo protection override skipped: {e}")
            # region agent log
            _dbg_db419a(
                "H63",
                "generate_pipeline.py:run_generate_pipeline:repo_only_protection_overrides",
                "failed to apply repo-level repository_protected overrides in adopt-only flow",
                {"error": str(e)},
            )
            # endregion
    elif yaml_file.exists():
        _progress(on_progress, "Applying protection flags to YAML...")

        from importer.web.utils.adoption_yaml_updater import (
            apply_protection_from_set,
            apply_unprotection_from_set,
        )

        # Gather keys from pending intents
        keys_to_protect: set[str] = {k for k, i in pending.items() if i.protected}
        keys_to_unprotect: set[str] = {k for k, i in pending.items() if not i.protected}

        # IMPORTANT: Re-apply all previously applied intents after baseline merge.
        # The merge may overwrite protection flags with baseline defaults.
        all_intents = protection_intent_manager.get_all_intents()
        for key, intent in all_intents.items():
            if key not in pending and intent.applied_to_yaml:
                if intent.protected:
                    keys_to_protect.add(key)
                else:
                    keys_to_unprotect.add(key)

        if keys_to_protect:
            apply_protection_from_set(str(yaml_file), keys_to_protect)
            _progress(on_progress, f"  Applied protection to {len(keys_to_protect)} resources")

        if keys_to_unprotect:
            apply_unprotection_from_set(str(yaml_file), keys_to_unprotect)
            _progress(on_progress, f"  Removed protection from {len(keys_to_unprotect)} resources")

        result.yaml_updated = bool(keys_to_protect or keys_to_unprotect)
    else:
        _progress(on_progress, f"  YAML file not found: {yaml_file}")
        # region agent log
        _dbg_db419a(
            "H67",
            "generate_pipeline.py:run_generate_pipeline:yaml_missing",
            "YAML missing at protection-application step",
            {
                "active_project": getattr(state, "active_project", "") or "",
                "project_path": str(getattr(state, "project_path", "") or ""),
                "terraform_dir_state": str(getattr(state.deploy, "terraform_dir", "") or ""),
                "map_last_yaml_file": str(getattr(state.map, "last_yaml_file", "") or ""),
                "resolved_tf_path": str(tf_path),
                "resolved_yaml_file": str(yaml_file),
                "baseline_yaml_path": str(baseline_yaml_path) if baseline_yaml_path else "",
                "tf_path_exists": bool(tf_path.exists()),
                "yaml_exists_now": bool(yaml_file.exists()),
            },
        )
        # endregion
        result.errors.append(f"YAML file not found: {yaml_file}")

    if _is_cancelled(is_cancelled_fn):
        return result

    # ------------------------------------------------------------------
    # Step 5: Regenerate HCL
    # ------------------------------------------------------------------
    if regenerate_hcl and yaml_file.exists():
        _progress(on_progress, "Regenerating Terraform HCL files...")
        try:
            import asyncio

            from importer.yaml_converter import YamlToTerraformConverter

            converter = YamlToTerraformConverter()
            await asyncio.to_thread(converter.convert, str(yaml_file), str(tf_path))
            _progress(on_progress, f"  HCL regenerated from {yaml_file.name}")
            result.hcl_regenerated = True
        except Exception as e:
            _progress(on_progress, f"  HCL regeneration warning: {e}")
            result.errors.append(f"HCL regeneration failed: {e}")

    if _is_cancelled(is_cancelled_fn):
        return result

    # ------------------------------------------------------------------
    # Step 6: Generate protection_moves.tf
    # ------------------------------------------------------------------
    if include_protection_moves:
        _progress(on_progress, "Generating protection_moves.tf...")

        tf_state_addresses = read_tf_state_addresses(tf_path)
        moves_data: list[ProtectionMismatch] = []
        added_keys: set[str] = set()

        def _add_mismatch(res_type: str, res_key: str, is_protected: bool) -> None:
            combo_key = f"{res_type}:{res_key}"
            if combo_key in added_keys:
                return
            if res_type not in RESOURCE_TYPE_MAP:
                return
            added_keys.add(combo_key)

            tf_type, unprotected_name, protected_name = RESOURCE_TYPE_MAP[res_type]
            if is_protected:
                state_addr = f'{MODULE_PREFIX}.{tf_type}.{unprotected_name}["{res_key}"]'
                expected_addr = f'{MODULE_PREFIX}.{tf_type}.{protected_name}["{res_key}"]'
            else:
                state_addr = f'{MODULE_PREFIX}.{tf_type}.{protected_name}["{res_key}"]'
                expected_addr = f'{MODULE_PREFIX}.{tf_type}.{unprotected_name}["{res_key}"]'

            moves_data.append(
                ProtectionMismatch(
                    resource_key=res_key,
                    resource_type=res_type,
                    yaml_protected=is_protected,
                    state_protected=not is_protected,
                    state_address=state_addr,
                    expected_address=expected_addr,
                )
            )

        for key, intent in pending.items():
            if ":" in key:
                resource_type, resource_key = key.split(":", 1)
            else:
                resource_type = intent.resource_type if intent.resource_type else "PRJ"
                resource_key = key

            # Skip resources not in TF state — they get imported directly
            if tf_state_addresses and resource_type in RESOURCE_TYPE_MAP:
                tf_type, unprotected_name, protected_name = RESOURCE_TYPE_MAP[resource_type]
                un_addr = f'{MODULE_PREFIX}.{tf_type}.{unprotected_name}["{resource_key}"]'
                pr_addr = f'{MODULE_PREFIX}.{tf_type}.{protected_name}["{resource_key}"]'
                if un_addr not in tf_state_addresses and pr_addr not in tf_state_addresses:
                    _progress(
                        on_progress,
                        f"  Skipping {key}: not in TF state (will be imported directly)",
                    )
                    continue

            _add_mismatch(resource_type, resource_key, intent.protected)

            # PRJ cascade to REP + PREP
            if resource_type == "PRJ":
                _add_mismatch("REP", resource_key, intent.protected)
                _add_mismatch("PREP", resource_key, intent.protected)

        # Detect orphaned YAML-vs-state mismatches
        try:
            tf_state_file = tf_path / "terraform.tfstate"
            if tf_state_file.exists() and yaml_file.exists():
                with open(str(tf_state_file), "r") as sf:
                    tf_state_raw = json.load(sf)
                with open(str(yaml_file), "r") as yf:
                    yaml_config = yaml.safe_load(yf) or {}

                all_mismatches = detect_protection_mismatches(
                    yaml_config, tf_state_raw, MODULE_PREFIX
                )
                new_count = 0
                for mm in all_mismatches:
                    combo = f"{mm.resource_type}:{mm.resource_key}"
                    if combo not in added_keys:
                        added_keys.add(combo)
                        moves_data.append(mm)
                        new_count += 1

                if new_count > 0:
                    _progress(
                        on_progress,
                        f"  Found {new_count} additional YAML-vs-state mismatches",
                    )
        except Exception as e:
            logger.warning(f"detect_protection_mismatches failed: {e}")
            _progress(on_progress, f"  YAML-vs-state detection skipped: {e}")

        # Write moved blocks
        moves_file = tf_path / "protection_moves.tf"
        moved_blocks = generate_repair_moved_blocks(moves_data, MODULE_PREFIX)

        if moved_blocks:
            moves_file.parent.mkdir(parents=True, exist_ok=True)
            moves_file.write_text(moved_blocks)
            result.moves_file = moves_file
            result.moves_count = len(moves_data)
            _progress(on_progress, f"  Generated {len(moves_data)} moved blocks")
        else:
            # Write an empty file so Terraform doesn't error on stale blocks
            if moves_file.exists():
                moves_file.write_text(
                    "# protection_moves.tf — no pending moves\n"
                )
            _progress(on_progress, "  No moved blocks needed")

    if _is_cancelled(is_cancelled_fn):
        return result

    # ------------------------------------------------------------------
    # Step 7: Generate / update adopt_imports.tf
    # ------------------------------------------------------------------
    if include_adopt and adopt_rows is not None:
        _progress(on_progress, "Generating adopt_imports.tf...")
        try:
            from importer.web.utils.terraform_import import write_adopt_imports_file

            rows_to_import = [r for r in adopt_rows if r.get("action") == "adopt"]
            # region agent log
            _dbg_db419a(
                "H1",
                "generate_pipeline.py:run_generate_pipeline:rows_to_import",
                "rows selected for adopt imports",
                {
                    "row_count": len(rows_to_import),
                    "rows": [
                        {
                            "source_key": str(r.get("source_key") or ""),
                            "source_type": str(r.get("source_type") or ""),
                            "target_id": str(r.get("target_id") or ""),
                            "protected": bool(r.get("protected", False)),
                        }
                        for r in rows_to_import[:10]
                    ],
                },
            )
            # endregion

            if rows_to_import:
                output_path, error = write_adopt_imports_file(
                    rows_to_import,
                    tf_path,
                    filename="adopt_imports.tf",
                )
                if error:
                    result.errors.append(f"adopt_imports.tf error: {error}")
                else:
                    result.imports_file = output_path
                    result.imports_count = len(rows_to_import)
                    _progress(
                        on_progress,
                        f"  Written {len(rows_to_import)} import blocks",
                    )
            else:
                # Remove stale file
                imports_file = tf_path / "adopt_imports.tf"
                if imports_file.exists():
                    imports_file.unlink()
                _progress(on_progress, "  No resources to import — cleaned up adopt_imports.tf")
        except Exception as e:
            result.errors.append(f"adopt_imports.tf generation failed: {e}")
            _progress(on_progress, f"  Error generating imports: {e}")

    # Also update existing adopt_imports.tf addresses if protection changed
    _update_adopt_imports_addresses(tf_path, pending, on_progress)
    if include_adopt:
        imports_file_dbg = tf_path / "adopt_imports.tf"
        imports_targets_dbg: list[str] = []
        if imports_file_dbg.exists():
            imports_content_dbg = imports_file_dbg.read_text(encoding="utf-8")
            imports_targets_dbg = [
                m.group(1) for m in re.finditer(r"to\s*=\s*(module\.\S+)", imports_content_dbg)
            ]
        # region agent log
        _dbg_db419a(
            "H2",
            "generate_pipeline.py:run_generate_pipeline:post_address_update",
            "import targets after address update",
            {
                "pending_intent_keys": sorted(list(pending.keys()))[:30],
                "imports_exists": imports_file_dbg.exists(),
                "imports_target_count": len(imports_targets_dbg),
                "imports_targets": imports_targets_dbg[:20],
            },
        )
        # endregion

    if _is_cancelled(is_cancelled_fn):
        return result

    # ------------------------------------------------------------------
    # Step 8: Mark intents as applied to YAML
    # ------------------------------------------------------------------
    if pending:
        _progress(on_progress, "Marking intents as applied to YAML...")
        protection_intent_manager.mark_applied_to_yaml(set(pending.keys()))
        protection_intent_manager.save()
        result.intents_applied = list(pending.keys())
        _progress(on_progress, f"  Updated {len(pending)} intent records")

    # ------------------------------------------------------------------
    # Step 9: Build target flags
    # ------------------------------------------------------------------
    _progress(on_progress, "Building target flags...")
    # For adopt-only runs without protection moves, scope targets strictly to
    # the generated adopt import blocks and ignore stale protection_moves.tf.
    if include_adopt and not include_protection_moves:
        import_targets: list[str] = []
        imports_tf = tf_path / "adopt_imports.tf"
        if imports_tf.exists():
            content = imports_tf.read_text(encoding="utf-8")
            import_targets = [m.group(1) for m in re.finditer(r"to\s*=\s*(module\.\S+)", content)]
        result.target_flags = [flag for addr in import_targets for flag in ("-target", addr)]
    else:
        # Non-adopt flows can include protection intent/moves-derived targets.
        target_intent_mgr = None if include_adopt else protection_intent_manager
        result.target_flags = build_target_flags(tf_path, target_intent_mgr)

    # Extract addresses from the flags list
    result.target_addresses = [
        result.target_flags[i + 1]
        for i in range(0, len(result.target_flags) - 1, 2)
        if result.target_flags[i] == "-target"
    ]
    if include_adopt:
        tf_non_import_files = [p for p in tf_path.glob("*.tf") if p.name != "adopt_imports.tf"]
        tf_non_import_text = "\n".join(
            p.read_text(encoding="utf-8", errors="ignore") for p in tf_non_import_files
        )
        yaml_repo_keys: list[str] = []
        try:
            if yaml_file.exists():
                _cfg = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                _globals = _cfg.get("globals", {}) if isinstance(_cfg, dict) else {}
                for _repo in _globals.get("repositories", []) if isinstance(_globals, dict) else []:
                    if isinstance(_repo, dict) and _repo.get("key"):
                        yaml_repo_keys.append(str(_repo.get("key")))
        except Exception:
            pass
        address_diagnostics: list[dict] = []
        for addr in result.target_addresses[:20]:
            m = re.search(
                r'module\.\S+\.(?P<tf_type>[^.]+)\.(?P<collection>[^\[]+)\["(?P<key>[^"]+)"\]',
                addr,
            )
            if not m:
                address_diagnostics.append({"address": addr, "parsed": False})
                continue
            tf_type = m.group("tf_type")
            collection = m.group("collection")
            key = m.group("key")
            address_diagnostics.append(
                {
                    "address": addr,
                    "parsed": True,
                    "tf_type": tf_type,
                    "collection": collection,
                    "key": key,
                    "has_resource_block": f'"{tf_type}" "{collection}"' in tf_non_import_text,
                    "has_key_literal": key in tf_non_import_text,
                    "key_in_yaml_globals_repositories": key in set(yaml_repo_keys),
                }
            )
        # region agent log
        _dbg_db419a(
            "H3",
            "generate_pipeline.py:run_generate_pipeline:target_diagnostics",
            "target addresses vs generated tf config",
            {
                "target_count": len(result.target_addresses),
                "non_import_tf_files": [p.name for p in tf_non_import_files],
                "yaml_globals_repository_keys": sorted(yaml_repo_keys)[:30],
                "address_diagnostics": address_diagnostics,
            },
        )
        # endregion
    _progress(
        on_progress,
        f"  {len(result.target_addresses)} target address(es) for plan/apply",
    )

    _progress(on_progress, "Pipeline complete.")
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _update_adopt_imports_addresses(
    tf_path: Path,
    pending: dict,
    on_progress: Optional[Callable[[str], None]],
) -> None:
    """Update import target addresses in adopt_imports.tf when protection changes.

    When a resource's protection status changes, the import block must target
    the correct ``protected_*`` / unprotected resource address.
    """
    imports_file = tf_path / "adopt_imports.tf"
    if not imports_file.exists() or not pending:
        return

    try:
        content = imports_file.read_text(encoding="utf-8")
        updated = False
        for key, intent in pending.items():
            if ":" not in key:
                continue
            rtype, rkey = key.split(":", 1)
            if rtype not in RESOURCE_TYPE_MAP:
                continue

            normalized_key = rkey
            if rtype in {"REP", "PREP"} and rkey.startswith("dbt_ep_"):
                candidate = rkey[len("dbt_ep_"):]
                if candidate:
                    normalized_key = candidate

            # Use explicit pending intent as source-of-truth for protection.
            # Do not infer repository protection from project-level YAML fallback.
            effective_protected = bool(intent.protected)

            tf_type, unprotected_name, protected_name = RESOURCE_TYPE_MAP[rtype]
            if effective_protected:
                old_addr = f'{MODULE_PREFIX}.{tf_type}.{unprotected_name}["{normalized_key}"]'
                new_addr = f'{MODULE_PREFIX}.{tf_type}.{protected_name}["{normalized_key}"]'
            else:
                old_addr = f'{MODULE_PREFIX}.{tf_type}.{protected_name}["{normalized_key}"]'
                new_addr = f'{MODULE_PREFIX}.{tf_type}.{unprotected_name}["{normalized_key}"]'

            # region agent log
            _dbg_db419a(
                "H57",
                "generate_pipeline.py:_update_adopt_imports_addresses",
                "computed adopt import protection address rewrite",
                {
                    "intent_key": key,
                    "resource_type": rtype,
                    "original_key": rkey,
                    "normalized_key": normalized_key,
                    "intent_protected": bool(intent.protected),
                    "effective_protected": effective_protected,
                    "old_addr": old_addr,
                    "new_addr": new_addr,
                    "old_addr_found": old_addr in content,
                },
            )
            # endregion

            if old_addr in content:
                content = content.replace(old_addr, new_addr)
                updated = True

        if updated:
            imports_file.write_text(content, encoding="utf-8")
            _progress(
                on_progress,
                "  Updated adopt_imports.tf with corrected protection targets",
            )
    except Exception as e:
        _progress(on_progress, f"  adopt_imports.tf update skipped: {e}")
