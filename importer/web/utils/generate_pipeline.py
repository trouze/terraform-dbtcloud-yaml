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

            tf_type, unprotected_name, protected_name = RESOURCE_TYPE_MAP[rtype]
            if intent.protected:
                old_addr = f'{MODULE_PREFIX}.{tf_type}.{unprotected_name}["{rkey}"]'
                new_addr = f'{MODULE_PREFIX}.{tf_type}.{protected_name}["{rkey}"]'
            else:
                old_addr = f'{MODULE_PREFIX}.{tf_type}.{protected_name}["{rkey}"]'
                new_addr = f'{MODULE_PREFIX}.{tf_type}.{unprotected_name}["{rkey}"]'

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
