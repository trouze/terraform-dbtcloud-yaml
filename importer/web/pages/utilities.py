"""Utilities page for protection intent management and advanced tools."""

import asyncio
import json
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.components.entity_table import show_match_detail_dialog
from importer.web.state import AppState, WorkflowStep
from importer.web.utils.terraform_helpers import (
    build_target_flags,
    get_terraform_env,
    resolve_deployment_paths,
    run_terraform_command,
)

# region agent log
_DEBUG_LOG_PATH = Path("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-65e6e9.log")


def _agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict,
    *,
    run_id: str = "run1",
) -> None:
    try:
        payload = {
            "sessionId": "65e6e9",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass
# endregion


def create_utilities_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Optional[Callable[[], None]] = None,
) -> None:
    """Create the utilities page content.
    
    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to persist state changes
    """
    with ui.column().classes("w-full max-w-6xl mx-auto p-8 gap-6"):
        # Page header
        with ui.row().classes("w-full items-center gap-3 mb-4"):
            ui.icon("security", size="lg").classes("text-slate-600")
            ui.label("Protection Management").classes("text-2xl font-bold")
        
        # Current Protection Status Section
        _create_protection_status_section(state, save_state)
        
        # Protection Management Section
        _create_protection_management_section(state, save_state)


def _create_protection_status_section(
    state: AppState,
    save_state: Optional[Callable[[], None]] = None,
) -> None:
    """Create the current protection status section showing YAML vs TF State."""
    
    # Get data from state
    yaml_protected = state.map.protected_resources or set()
    has_state = state.deploy.has_state_file()
    
    # Get TF state protected resources
    state_protected_resources = set()
    state_unprotected_resources = set()
    state_protected_resources_display = set()
    state_unprotected_resources_display = set()
    
    if has_state and state.deploy.reconcile_state_loaded and state.deploy.reconcile_state_resources:
        # region agent log
        code_counts: dict[str, int] = {}
        for resource in state.deploy.reconcile_state_resources:
            code = resource.get("element_code", "UNKNOWN")
            code_counts[code] = code_counts.get(code, 0) + 1
        member_rows = [
            {
                "element_code": r.get("element_code"),
                "tf_name": r.get("tf_name"),
                "resource_index": r.get("resource_index"),
            }
            for r in state.deploy.reconcile_state_resources
            if r.get("resource_index") == "member"
        ]
        _agent_debug_log(
            "D3",
            "utilities.py:_create_protection_status_section",
            "reconcile rows entering protection status summary",
            {
                "reconcile_count": len(state.deploy.reconcile_state_resources),
                "element_code_counts": code_counts,
                "member_rows": member_rows[:5],
            },
        )
        # endregion
        for resource in state.deploy.reconcile_state_resources:
            tf_name = resource.get("tf_name", "")
            resource_index = resource.get("resource_index", "")
            element_code = resource.get("element_code", "")
            
            if element_code in ("PRJ", "REP", "PREP", "GRP") and resource_index:
                if "protected_" in tf_name:
                    state_protected_resources_display.add(resource_index)
                else:
                    state_unprotected_resources_display.add(resource_index)

            if element_code in ("PRJ", "REP", "PREP") and resource_index:
                if "protected_" in tf_name:
                    state_protected_resources.add(resource_index)
                else:
                    state_unprotected_resources.add(resource_index)
    # region agent log
    _agent_debug_log(
        "D6",
        "utilities.py:_create_protection_status_section",
        "derived protection status counts for summary cards",
        {
            "tf_state_protected_display_count": len(state_protected_resources_display),
            "tf_state_unprotected_display_count": len(state_unprotected_resources_display),
            "tf_state_protected_mismatch_count": len(state_protected_resources),
            "tf_state_unprotected_mismatch_count": len(state_unprotected_resources),
            "member_in_display_protected": "member" in state_protected_resources_display,
            "member_in_mismatch_protected": "member" in state_protected_resources,
        },
    )
    # endregion
    
    # Calculate mismatches
    # Resources in YAML as protected but in state as unprotected (or vice versa)
    mismatches = []
    all_keys = yaml_protected | state_protected_resources | state_unprotected_resources
    
    for key in all_keys:
        yaml_is_protected = key in yaml_protected
        state_is_protected = key in state_protected_resources
        state_is_unprotected = key in state_unprotected_resources
        
        # Only count as mismatch if we have state data for this resource
        if state_is_protected or state_is_unprotected:
            if yaml_is_protected != state_is_protected:
                direction = "protect" if yaml_is_protected else "unprotect"
                mismatches.append({
                    "key": key,
                    "yaml_protected": yaml_is_protected,
                    "state_protected": state_is_protected,
                    "direction": direction,
                })
    
    with ui.card().classes("w-full p-4 mb-4"):
        with ui.row().classes("w-full items-center justify-between mb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("assessment", size="md").classes("text-slate-600")
                ui.label("Current Protection Status").classes("text-xl font-semibold")
            
            # State file indicator
            if has_state:
                ui.badge("TF State Loaded").props("color=positive")
            else:
                ui.badge("No TF State").props("color=grey")
        
        # Summary cards row
        with ui.row().classes("w-full gap-3 mb-4"):
            # YAML Protected
            with ui.card().classes("flex-1 p-3 border border-blue-300"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("description", size="sm").classes("text-blue-600")
                    ui.label("YAML Protected").classes("font-semibold text-blue-600")
                ui.label(str(len(yaml_protected))).classes("text-2xl font-bold text-blue-700 mt-1")
                ui.label("From config file").classes("text-xs opacity-70")
            
            # TF State Protected
            with ui.card().classes("flex-1 p-3 border border-green-300"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("cloud", size="sm").classes("text-green-600")
                    ui.label("TF State Protected").classes("font-semibold text-green-600")
                count = len(state_protected_resources_display) if has_state else "—"
                ui.label(str(count)).classes("text-2xl font-bold text-green-700 mt-1")
                ui.label("From terraform state" if has_state else "Load state to see").classes("text-xs opacity-70")
            
            # Mismatches
            mismatch_color = "red" if len(mismatches) > 0 else "grey"
            with ui.card().classes(f"flex-1 p-3 border border-{mismatch_color}-300"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning" if len(mismatches) > 0 else "check", size="sm").classes(f"text-{mismatch_color}-600")
                    ui.label("Mismatches").classes(f"font-semibold text-{mismatch_color}-600")
                ui.label(str(len(mismatches))).classes(f"text-2xl font-bold text-{mismatch_color}-700 mt-1")
                ui.label("Need resolution" if len(mismatches) > 0 else "All in sync").classes("text-xs opacity-70")
        
        # Mismatches expansion (if any)
        if len(mismatches) > 0:
            protection_intent = state.get_protection_intent_manager()
            mismatch_resource_types = ("PRJ", "REP", "PREP")

            def mismatch_intent_keys(base_key: str) -> list[str]:
                return [f"{rtype}:{base_key}" for rtype in mismatch_resource_types] + [base_key]

            def has_mismatch_intent(base_key: str) -> bool:
                return any(protection_intent.has_intent(k) for k in mismatch_intent_keys(base_key))

            def get_mismatch_intent(base_key: str):
                for key in mismatch_intent_keys(base_key):
                    intent = protection_intent.get_intent(key)
                    if intent is not None:
                        return intent
                return None

            def set_mismatch_intent(base_key: str, protected: bool, source: str, reason: str) -> None:
                # Mismatch rows are project-scoped. Persist explicit typed intents for
                # PRJ/REP/PREP so downstream TF targeting stays deterministic.
                for rtype in mismatch_resource_types:
                    protection_intent.set_intent(
                        key=f"{rtype}:{base_key}",
                        protected=protected,
                        source=source,
                        reason=reason,
                        resource_type=rtype,
                    )

                # Remove any legacy unprefixed key to avoid UNKNOWN rows and stale lookups.
                if protection_intent.has_intent(base_key):
                    protection_intent.remove_intent(base_key, source=source)
            
            with ui.expansion(
                f"⚠️ {len(mismatches)} Protection Mismatches - Click to Resolve",
                icon="warning"
            ).classes("w-full border border-red-400 rounded"):
                ui.label(
                    "These resources have different protection status in YAML vs TF State. "
                    "Set your intent to resolve each mismatch."
                ).classes("text-xs opacity-70 mb-3")
                
                for m in mismatches[:20]:
                    key = m["key"]
                    yaml_prot = m["yaml_protected"]
                    state_prot = m["state_protected"]
                    
                    # Check if intent already recorded
                    has_intent = has_mismatch_intent(key)
                    
                    with ui.card().classes("w-full p-2 mb-2 bg-red-500 bg-opacity-10"):
                        with ui.row().classes("items-center justify-between"):
                            with ui.column().classes("gap-1"):
                                ui.label(key).classes("font-medium text-sm")
                                with ui.row().classes("items-center gap-2"):
                                    ui.badge(f"YAML: {'Protected' if yaml_prot else 'Unprotected'}").props(
                                        f"color={'blue' if yaml_prot else 'grey'} dense"
                                    )
                                    ui.icon("sync_problem", size="xs").classes("text-red-500")
                                    ui.badge(f"State: {'Protected' if state_prot else 'Unprotected'}").props(
                                        f"color={'blue' if state_prot else 'grey'} dense"
                                    )
                                    if has_intent:
                                        intent = get_mismatch_intent(key)
                                        intent_label = "→ Protect" if intent.protected else "→ Unprotect"
                                        ui.badge(f"Intent: {intent_label}").props("color=amber dense")
                            
                            if not has_intent:
                                with ui.row().classes("items-center gap-1"):
                                    def make_protect_handler(rkey=key):
                                        def handler():
                                            set_mismatch_intent(
                                                base_key=rkey,
                                                protected=True,
                                                source="protection_status",
                                                reason="Resolve mismatch: protect",
                                            )
                                            protection_intent.save()
                                            ui.notify(f"Intent: PROTECT {rkey}", type="positive")
                                            ui.navigate.reload()
                                        return handler
                                    
                                    def make_unprotect_handler(rkey=key):
                                        def handler():
                                            set_mismatch_intent(
                                                base_key=rkey,
                                                protected=False,
                                                source="protection_status",
                                                reason="Resolve mismatch: unprotect",
                                            )
                                            protection_intent.save()
                                            ui.notify(f"Intent: UNPROTECT {rkey}", type="info")
                                            ui.navigate.reload()
                                        return handler
                                    
                                    ui.button("Protect", icon="shield", on_click=make_protect_handler()).props("dense size=sm color=positive")
                                    ui.button("Unprotect", icon="lock_open", on_click=make_unprotect_handler()).props("dense size=sm color=warning")
                            else:
                                def make_undo_handler(rkey=key):
                                    def handler():
                                        removed = False
                                        for intent_key in mismatch_intent_keys(rkey):
                                            if protection_intent.has_intent(intent_key):
                                                protection_intent.remove_intent(intent_key, source="protection_status")
                                                removed = True
                                        if removed:
                                            protection_intent.save()
                                            ui.notify(f"Cleared intent for {rkey}", type="info")
                                            ui.navigate.reload()
                                    return handler
                                
                                ui.button("Undo", icon="undo", on_click=make_undo_handler()).props("dense size=sm flat")
                
                if len(mismatches) > 20:
                    ui.label(f"... and {len(mismatches) - 20} more").classes("text-xs opacity-60")
                
                # Bulk resolution buttons
                ui.separator().classes("my-2")
                
                unresolved = [m for m in mismatches if not has_mismatch_intent(m["key"])]
                
                with ui.row().classes("items-center gap-2"):
                    def protect_all_unresolved():
                        for m in unresolved:
                            set_mismatch_intent(
                                base_key=m["key"],
                                protected=True,
                                source="protection_status_bulk",
                                reason="Bulk resolve: protect all",
                            )
                        protection_intent.save()
                        ui.notify(f"Set intent to PROTECT for {len(unresolved)} resources", type="positive")
                        ui.navigate.reload()
                    
                    def unprotect_all_unresolved():
                        for m in unresolved:
                            set_mismatch_intent(
                                base_key=m["key"],
                                protected=False,
                                source="protection_status_bulk",
                                reason="Bulk resolve: unprotect all",
                            )
                        protection_intent.save()
                        ui.notify(f"Set intent to UNPROTECT for {len(unresolved)} resources", type="info")
                        ui.navigate.reload()
                    
                    def follow_yaml():
                        """Set intents to match what YAML says."""
                        for m in unresolved:
                            set_mismatch_intent(
                                base_key=m["key"],
                                protected=m["yaml_protected"],
                                source="protection_status_bulk",
                                reason="Follow YAML configuration",
                            )
                        protection_intent.save()
                        ui.notify(f"Set intents to follow YAML for {len(unresolved)} resources", type="positive")
                        ui.navigate.reload()
                    
                    def follow_state():
                        """Set intents to match what TF state says."""
                        for m in unresolved:
                            set_mismatch_intent(
                                base_key=m["key"],
                                protected=m["state_protected"],
                                source="protection_status_bulk",
                                reason="Follow TF state",
                            )
                        protection_intent.save()
                        ui.notify(f"Set intents to follow TF State for {len(unresolved)} resources", type="positive")
                        ui.navigate.reload()
                    
                    if len(unresolved) > 0:
                        ui.button(f"Follow YAML ({len(unresolved)})", icon="description", on_click=follow_yaml).props("dense size=sm outline")
                        ui.button(f"Follow TF State ({len(unresolved)})", icon="cloud", on_click=follow_state).props("dense size=sm outline")
                        ui.button(f"Protect All ({len(unresolved)})", icon="shield", on_click=protect_all_unresolved).props("dense size=sm color=positive outline")
                        ui.button(f"Unprotect All ({len(unresolved)})", icon="lock_open", on_click=unprotect_all_unresolved).props("dense size=sm color=warning outline")
                    else:
                        ui.label("All mismatches have intents recorded").classes("text-sm text-green-600")
        
        # Load State button if not loaded
        if not has_state:
            ui.separator().classes("my-4")
            with ui.row().classes("w-full items-center gap-4"):
                ui.icon("info", size="sm").classes("text-blue-500")
                ui.label("Load Terraform state to see current protection status and detect mismatches").classes("text-sm opacity-70")
                
                async def load_state_action():
                    tf_path, _yaml, _baseline = resolve_deployment_paths(state)
                    state_file = tf_path / "state.json"
                    if not state_file.exists():
                        ui.notify(f"State file not found: {state_file}. Run 'terraform show -json > state.json' in your TF directory.", type="negative")
                        return
                    
                    try:
                        state_json = json.loads(state_file.read_text())
                        from importer.web.utils.terraform_state_reader import parse_state_json
                        result = parse_state_json(state_json)
                        
                        if result.success:
                            # Store parsed resources in the proper DeployState field
                            state.deploy.reconcile_state_resources = [r.__dict__ for r in result.resources]
                            state.deploy.reconcile_state_loaded = True
                            if save_state:
                                save_state()
                            ui.notify(f"Loaded {len(result.resources)} resources from state", type="positive")
                            ui.navigate.reload()
                        else:
                            ui.notify(f"Failed to parse state: {result.error_message}", type="negative")
                    except Exception as e:
                        ui.notify(f"Error loading state: {e}", type="negative")
                
                ui.button("Load State", icon="cloud_download", on_click=load_state_action).props("color=primary")


def _create_protection_management_section(
    state: AppState,
    save_state: Optional[Callable[[], None]] = None,
) -> None:
    """Create the protection management section."""
    
    # Get protection intent manager
    protection_intent = state.get_protection_intent_manager()
    
    # Calculate counts
    pending_generate = len(protection_intent.get_pending_yaml_updates())
    pending_tf = sum(
        1 for intent in protection_intent._intent.values()
        if intent.needs_tf_move
    )
    synced = sum(
        1 for intent in protection_intent._intent.values()
        if intent.applied_to_yaml and intent.applied_to_tf_state
    )
    total_intents = protection_intent.intent_count
    
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center gap-2 mb-3"):
            ui.icon("shield", size="md").classes("text-slate-600")
            ui.label("Protection Management").classes("text-xl font-semibold")
        
        # Status Summary Cards
        with ui.row().classes("w-full gap-3 mb-4"):
            # Pending Generate card
            with ui.card().classes("flex-1 p-3").style("border: 2px solid #F59E0B;"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("pending_actions", size="sm").classes("text-amber-600")
                    ui.label("Pending Generate").classes("font-semibold text-amber-600")
                ui.label(str(pending_generate)).classes("text-2xl font-bold text-amber-700 mt-1")
                ui.label("Need YAML updates").classes("text-xs text-slate-500")
            
            # Pending TF Intents card
            with ui.card().classes("flex-1 p-3").style("border: 2px solid #3B82F6;"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("cloud_sync", size="sm").classes("text-blue-600")
                    ui.label("Pending TF Intents").classes("font-semibold text-blue-600")
                ui.label(str(pending_tf)).classes("text-2xl font-bold text-blue-700 mt-1")
                ui.label("Need terraform apply (intent count)").classes("text-xs text-slate-500")
            
            # Synced card
            with ui.card().classes("flex-1 p-3").style("border: 2px solid #10B981;"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("check_circle", size="sm").classes("text-green-600")
                    ui.label("Synced").classes("font-semibold text-green-600")
                ui.label(str(synced)).classes("text-2xl font-bold text-green-700 mt-1")
                ui.label("Fully applied").classes("text-xs text-slate-500")
        
        # Build TF-state protection map used by filters and table state column.
        # Key format mirrors intent keys: "<TYPE>:<resource_key>".
        state_protection_by_key: dict[str, bool] = {}
        state_resource_by_key: dict[str, dict] = {}
        if state.deploy.reconcile_state_loaded and state.deploy.reconcile_state_resources:
            for resource in state.deploy.reconcile_state_resources:
                element_code = resource.get("element_code", "")
                resource_index = resource.get("resource_index", "")
                tf_name = resource.get("tf_name", "")
                if element_code in ("PRJ", "REP", "PREP", "GRP", "ENV", "JOB", "CON", "CONN") and resource_index:
                    typed_key = f"{element_code}:{resource_index}"
                    state_protection_by_key[typed_key] = "protected_" in tf_name
                    state_resource_by_key[typed_key] = resource

        # Build unified row model up-front so filters and actions are consistent.
        all_rows = _build_protection_grid_rows(
            protection_intent=protection_intent,
            state_protection_by_key=state_protection_by_key,
            yaml_protected_resources=state.map.protected_resources or set(),
        )
        total_rows = len(all_rows)

        # Grid state for filter/action handlers.
        grid_ref = {
            "grid": None,
            "all_rows": all_rows,
            "selected_keys": set(),
            "showing_label": None,
            "selection_label": None,
            "bulk_btn_refs": {},
        }

        # Filters and Search
        filter_state = {
            "status": "all",
            "type": "all",
            "search": "",
            "selected_only": False,
            "hide_unprotected": True,
        }
        
        def _render_filter_controls() -> None:
            with ui.card().classes("w-full p-3 mb-4 border border-slate-200 rounded-lg"):
                ui.label("Grid Filters").classes("text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2")
                with ui.row().classes("w-full gap-4 items-end flex-wrap"):
                    # Status filter with counts.
                    status_counts = _count_values(all_rows, "status")
                    status_options = {
                        "all": f"All Status ({total_rows})",
                        "pending_generate": f"Pending Generate ({status_counts.get('Pending Generate', 0)})",
                        "pending_tf": f"Pending TF Intents ({status_counts.get('Pending TF Intents', 0)})",
                        "state_mismatch": f"State Mismatch ({status_counts.get('State Mismatch', 0)})",
                        "state_only": f"State Only ({status_counts.get('State Only', 0)})",
                        "synced": f"Synced ({status_counts.get('Synced', 0)})",
                    }
                    status_select = ui.select(
                        label="Status",
                        options=status_options,
                        value="all",
                        on_change=lambda e: _update_filter(filter_state, "status", e.value, grid_ref),
                    ).props("dense outlined").classes("w-44 self-end")

                    # Type filter with counts.
                    type_counts = _count_values(all_rows, "type")
                    type_options = {"all": f"All Types ({total_rows})"}
                    for resource_type in sorted(type_counts.keys()):
                        type_options[resource_type] = f"{resource_type} ({type_counts[resource_type]})"

                    type_select = ui.select(
                        label="Type",
                        options=type_options,
                        value="all",
                        on_change=lambda e: _update_filter(filter_state, "type", e.value, grid_ref),
                    ).props("dense outlined").classes("w-44 self-end")

                    search_input = ui.input(
                        label="Search Resource Key",
                        placeholder="Type to filter...",
                        on_change=lambda e: _update_filter(filter_state, "search", e.value, grid_ref),
                    ).props("dense outlined clearable").classes("flex-grow min-w-[220px]")

                    def _reset_filters() -> None:
                        status_select.value = "all"
                        type_select.value = "all"
                        search_input.value = ""
                        filter_state["status"] = "all"
                        filter_state["type"] = "all"
                        filter_state["search"] = ""
                        filter_state["selected_only"] = False
                        filter_state["hide_unprotected"] = True
                        selected_only_switch.value = False
                        hide_unprotected_switch.value = True
                        _refresh_protection_grid(grid_ref, filter_state)

                with ui.row().classes("w-full items-center gap-2 flex-wrap pt-1"):
                    selected_only_switch = ui.switch(
                        "Selected only",
                        value=False,
                        on_change=lambda e: _update_filter(filter_state, "selected_only", bool(e.value), grid_ref),
                    ).props("dense")
                    hide_unprotected_switch = ui.switch(
                        "Hide unprotected",
                        value=True,
                        on_change=lambda e: _update_filter(filter_state, "hide_unprotected", bool(e.value), grid_ref),
                    ).props("dense")
                    ui.button("Reset", icon="restart_alt", on_click=_reset_filters).props("outline dense")

                with ui.row().classes("w-full justify-end"):
                    showing_label = ui.label(f"0 shown / {total_rows} total").classes("text-sm text-slate-500")
                    grid_ref["showing_label"] = showing_label
        
        # Bulk Action Buttons
        with ui.column().classes("w-full gap-3 mb-4 p-3 border border-slate-200 rounded-lg"):
            async def reset_all_to_yaml():
                """Reset all intents, falling back to YAML flags."""
                dialog = ui.dialog()
                confirmed = {"value": False}
                
                with dialog:
                    with ui.card().classes("p-4"):
                        ui.label("Reset All to YAML").classes("text-lg font-semibold mb-2")
                        ui.label("This will clear all intent history. Protection status will fall back to YAML configuration.").classes("text-sm text-slate-500 mb-4")
                        
                        with ui.row().classes("gap-2 justify-end"):
                            ui.button("Cancel", on_click=dialog.close).props("flat")
                            
                            def confirm_reset():
                                confirmed["value"] = True
                                dialog.close()
                            
                            ui.button("Reset All", on_click=confirm_reset).props("color=red")
                
                dialog.open()
                await dialog
                
                if confirmed["value"]:
                    protection_intent._intent.clear()
                    protection_intent._history.clear()
                    protection_intent.save()
                    ui.notify("All intents reset to YAML defaults", type="positive")
                    ui.navigate.reload()
            
            async def sync_from_tf_state():
                """Sync intents from current TF state - set intents to match what's in TF state."""
                if not state.deploy.has_state_file() or not state.deploy.reconcile_state_resources:
                    ui.notify("No TF state loaded. Load state first.", type="warning")
                    return
                
                # Confirmation dialog
                dialog = ui.dialog()
                confirmed = {"value": False}
                
                with dialog:
                    with ui.card().classes("p-4"):
                        ui.label("Sync from TF State").classes("text-lg font-semibold mb-2")
                        ui.label(
                            "This will create protection intents for all resources to match their current TF state. "
                            "Resources currently in protected_* blocks will get intent=protect, others will get intent=unprotect."
                        ).classes("text-sm opacity-70 mb-4")
                        
                        with ui.row().classes("gap-2 justify-end"):
                            ui.button("Cancel", on_click=dialog.close).props("flat")
                            
                            def confirm_sync():
                                confirmed["value"] = True
                                dialog.close()
                            
                            ui.button("Sync", on_click=confirm_sync).props("color=primary")
                
                dialog.open()
                await dialog
                
                if not confirmed["value"]:
                    return
                
                # Get resources from state
                count = 0
                for resource in state.deploy.reconcile_state_resources:
                    tf_name = resource.get("tf_name", "")
                    resource_index = resource.get("resource_index", "")
                    element_code = resource.get("element_code", "")
                    
                    if element_code in ("PRJ", "REP", "PREP", "GRP", "ENV", "JOB", "CON", "CONN") and resource_index:
                        typed_key = f"{element_code}:{resource_index}"
                        is_protected = "protected_" in tf_name
                        intent = protection_intent.set_intent(
                            key=typed_key,
                            protected=is_protected,
                            source="sync_from_tf_state",
                            reason=f"Synced from TF state - was in {tf_name}",
                            resource_type=element_code,
                        )
                        # Intent was derived FROM TF state, so TF state already matches.
                        # Mark as applied_to_tf_state=True to avoid requiring a TF plan/apply.
                        intent.applied_to_tf_state = True
                        count += 1
                
                protection_intent.save()
                ui.notify(f"Synced {count} resources from TF state", type="positive")
                ui.navigate.reload()
            
            async def generate_all_pending():
                """Process all pending-generate intents at once.
                
                This follows the same workflow as Match page:
                1. Read pending intents
                2. Apply intents to YAML
                3. Generate protection_moves.tf from state comparison
                4. Regenerate Terraform files from YAML (shared converter path)
                """
                # Get both pending YAML updates AND pending TF apply items
                pending_yaml = protection_intent.get_pending_yaml_updates()
                pending_tf = {k: i for k, i in protection_intent._intent.items()
                             if i.applied_to_yaml and not i.applied_to_tf_state}
                
                pending = {**pending_yaml, **pending_tf}
                # region agent log
                _agent_debug_log(
                    "H1",
                    "utilities.py:generate_all_pending",
                    "pending intent snapshot before generation",
                    {
                        "pending_yaml_count": len(pending_yaml),
                        "pending_tf_count": len(pending_tf),
                        "pending_yaml_has_fido": any("sse_dm_fin_fido" in k for k in pending_yaml),
                        "pending_tf_has_fido": any("sse_dm_fin_fido" in k for k in pending_tf),
                    },
                )
                # endregion
                
                if not pending:
                    ui.notify("No pending intents to generate", type="warning")
                    return
                
                tf_path, yaml_file, _baseline = resolve_deployment_paths(state)
                if not yaml_file.exists():
                    ui.notify(f"YAML file not found: {yaml_file}", type="negative")
                    return
                # region agent log
                _agent_debug_log(
                    "H1",
                    "utilities.py:generate_all_pending",
                    "selected yaml file for generation",
                    {
                        "tf_path": str(tf_path),
                        "yaml_file": str(yaml_file),
                        "merged_exists": (tf_path / "dbt-cloud-config-merged.yml").exists(),
                        "base_exists": (tf_path / "dbt-cloud-config.yml").exists(),
                    },
                )
                # endregion
                
                # Step 1: Apply intents to YAML
                try:
                    from importer.web.utils.adoption_yaml_updater import apply_protection_from_set, apply_unprotection_from_set
                    
                    keys_to_protect = {k for k, i in pending.items() if i.protected}
                    keys_to_unprotect = {k for k, i in pending.items() if not i.protected}
                    
                    if keys_to_protect:
                        apply_protection_from_set(str(yaml_file), keys_to_protect)
                    if keys_to_unprotect:
                        apply_unprotection_from_set(str(yaml_file), keys_to_unprotect)
                    
                    # Mark as applied to YAML
                    protection_intent.mark_applied_to_yaml(set(pending_yaml.keys()))
                    protection_intent.save()
                    if save_state:
                        save_state()
                except Exception as e:
                    import traceback
                    ui.notify(f"Error applying YAML changes: {e}", type="negative")
                    traceback.print_exc()
                    return
                
                # Step 2: Generate protection_moves.tf by comparing YAML to state
                try:
                    from importer.web.utils.protection_manager import (
                        ProtectionChange,
                        generate_moved_blocks_from_state,
                        get_resource_address,
                        load_yaml_config,
                        write_moved_blocks_file,
                    )

                    yaml_config = load_yaml_config(str(yaml_file))
                    protection_changes: list[ProtectionChange] = []

                    # Prefer loaded reconcile state (from terraform show -json) so
                    # move direction matches what the UI mismatch cards display.
                    if state.deploy.reconcile_state_loaded and state.deploy.reconcile_state_resources:
                        # Build YAML protection map for PRJ/REP/PREP.
                        yaml_protection: dict[tuple[str, str], bool] = {}
                        project_keys = set()
                        for project in yaml_config.get("projects", []):
                            project_key = project.get("key", "")
                            project_keys.add(project_key)
                            yaml_protection[("PRJ", project_key)] = bool(project.get("protected", False))
                        for repo in yaml_config.get("globals", {}).get("repositories", []):
                            repo_key = repo.get("key", "")
                            repo_protected = bool(repo.get("protected", False))
                            yaml_protection[("REP", repo_key)] = repo_protected
                            for project_key in project_keys:
                                if project_key in repo_key or repo_key.endswith(project_key):
                                    yaml_protection[("REP", project_key)] = repo_protected
                                    yaml_protection[("PREP", project_key)] = repo_protected
                                    break

                        # region agent log
                        _agent_debug_log(
                            "H6",
                            "utilities.py:generate_all_pending",
                            "using reconcile_state_resources as move generation source",
                            {
                                "resource_count": len(state.deploy.reconcile_state_resources),
                                "has_fido_reconcile": any(r.get("resource_index") == "sse_dm_fin_fido" for r in state.deploy.reconcile_state_resources),
                            },
                        )
                        # endregion

                        for resource in state.deploy.reconcile_state_resources:
                            element_code = resource.get("element_code", "")
                            resource_index = resource.get("resource_index", "")
                            tf_name = resource.get("tf_name", "")
                            if element_code not in ("PRJ", "REP", "PREP") or not resource_index:
                                continue
                            state_protected = "protected_" in tf_name
                            yaml_protected = yaml_protection.get((element_code, resource_index), False)
                            if yaml_protected == state_protected:
                                continue
                            direction = "protect" if yaml_protected else "unprotect"
                            protection_changes.append(
                                ProtectionChange(
                                    resource_key=resource_index,
                                    resource_type=element_code,
                                    name=resource_index,
                                    direction=direction,
                                    from_address=get_resource_address(element_code, resource_index, protected=state_protected),
                                    to_address=get_resource_address(element_code, resource_index, protected=yaml_protected),
                                )
                            )
                    else:
                        state_file = tf_path / "terraform.tfstate"
                        # region agent log
                        _agent_debug_log(
                            "H2",
                            "utilities.py:generate_all_pending",
                            "starting terraform.tfstate comparison for moved block generation",
                            {
                                "yaml_file": str(yaml_file),
                                "state_file": str(state_file),
                                "state_file_exists": state_file.exists(),
                            },
                        )
                        # endregion
                        if state_file.exists():
                            protection_changes = generate_moved_blocks_from_state(yaml_config, str(state_file))
                        else:
                            ui.notify("YAML updated - no state file found to compare", type="info")

                    if protection_changes:
                        moved_file = write_moved_blocks_file(
                            protection_changes,
                            str(tf_path),
                            filename="protection_moves.tf",
                            preserve_existing=False,
                        )
                        if moved_file:
                            ui.notify(f"Generated {len(protection_changes)} moved block(s) → {moved_file.name}", type="positive")
                    else:
                        # Clear stale generated moves to prevent old directions from
                        # blocking plan/apply with "Moved object still exists".
                        moves_file = tf_path / "protection_moves.tf"
                        if moves_file.exists():
                            moves_file.write_text(
                                "# Protection moves cleared - no pending protection moves\n",
                                encoding="utf-8",
                            )
                        ui.notify("YAML updated - no moved blocks needed (state already matches)", type="info")
                except Exception as e:
                    import traceback
                    ui.notify(f"Error generating moved blocks: {e}", type="negative")
                    traceback.print_exc()

                # Step 3: Regenerate Terraform files so moved blocks can apply
                # (moves fail if HCL still declares resources in protected_* blocks).
                try:
                    from importer.yaml_converter import YamlToTerraformConverter

                    converter = YamlToTerraformConverter()
                    await asyncio.to_thread(
                        converter.convert,
                        str(yaml_file),
                        str(tf_path),
                    )
                    ui.notify("Regenerated Terraform files from updated YAML", type="positive")
                except Exception as e:
                    ui.notify(f"Error regenerating Terraform files: {e}", type="negative")
                    return
                
                ui.notify(f"Processed {len(pending)} protection intent(s)", type="positive")
                ui.navigate.reload()
            
            def export_json():
                """Download protection-intent.json."""
                intent_data = {
                    "intent": {k: v.__dict__ for k, v in protection_intent._intent.items()},
                    "history": [h.__dict__ for h in protection_intent._history],
                }
                json_str = json.dumps(intent_data, indent=2, default=str)
                ui.download(json_str.encode(), "protection-intent.json")
                ui.notify("Exported protection-intent.json", type="positive")

            def _set_row_intent(row: dict, protected: bool, source: str, reason: str) -> None:
                resource_key = row.get("resource_key", "")
                resource_type = row.get("type", "UNKNOWN")
                state_protected = row.get("state_protected")
                intent = protection_intent.set_intent(
                    key=resource_key,
                    protected=protected,
                    source=source,
                    reason=reason,
                    resource_type=resource_type,
                    tf_state_at_decision="protected" if state_protected is True else "unprotected" if state_protected is False else None,
                    yaml_state_before=bool(row.get("yaml_protected", False)),
                )
                if state_protected is not None and bool(state_protected) == bool(protected):
                    intent.applied_to_tf_state = True

            def _baseline_value(row: dict) -> bool:
                # Dense baseline rule: default false unless state/yaml are protected.
                return bool(row.get("state_protected") is True or row.get("yaml_protected") is True)

            def fill_dense_baseline() -> None:
                created = 0
                for row in all_rows:
                    key = row.get("resource_key", "")
                    if not key or protection_intent.has_intent(key):
                        continue
                    _set_row_intent(
                        row=row,
                        protected=_baseline_value(row),
                        source="dense_baseline",
                        reason="auto-fill from TF state",
                    )
                    created += 1
                protection_intent.save()
                ui.notify(f"Dense baseline synced for {created} resources", type="positive")
                ui.navigate.reload()

            def _selected_rows() -> list[dict]:
                selected_keys: set[str] = grid_ref.get("selected_keys", set())
                return [row for row in all_rows if row.get("resource_key") in selected_keys]

            def _apply_to_selected(mode: str) -> None:
                rows = _selected_rows()
                if not rows:
                    ui.notify("No rows selected", type="warning")
                    return
                updated = 0
                for row in rows:
                    resource_key = row.get("resource_key", "")
                    if not resource_key:
                        continue
                    if mode == "reset":
                        if protection_intent.has_intent(resource_key):
                            protection_intent.remove_intent(resource_key, source="utilities_bulk_reset")
                        _set_row_intent(
                            row=row,
                            protected=_baseline_value(row),
                            source="dense_baseline",
                            reason="reset to baseline rule",
                        )
                    elif mode == "protect":
                        _set_row_intent(
                            row=row,
                            protected=True,
                            source="utilities_bulk",
                            reason="bulk protect from protection grid",
                        )
                    elif mode == "unprotect":
                        _set_row_intent(
                            row=row,
                            protected=False,
                            source="utilities_bulk",
                            reason="bulk unprotect from protection grid",
                        )
                    updated += 1
                protection_intent.save()
                ui.notify(f"Updated {updated} selected row(s)", type="positive")
                ui.navigate.reload()
            
            with ui.card().classes("w-full p-3 mb-4 border border-slate-200 rounded-lg"):
                ui.label("Intent Actions").classes("text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2")
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    generate_btn = ui.button(
                        f"Generate All Pending ({pending_generate + pending_tf})" if (pending_generate + pending_tf) > 0 else "Generate All Pending",
                        icon="auto_fix_high",
                        on_click=generate_all_pending,
                    ).props("color=green dense").classes("min-w-[190px]")
                    generate_btn.set_enabled((pending_generate + pending_tf) > 0)
                    ui.button(
                        "Fill Dense Baseline",
                        icon="dataset",
                        on_click=fill_dense_baseline,
                    ).props("outline dense").classes("min-w-[170px]").tooltip("Create baseline intents for rows that have no explicit intent")
                    ui.button(
                        "Sync from TF State",
                        icon="cloud_download",
                        on_click=sync_from_tf_state,
                    ).props("outline dense").classes("min-w-[170px]").tooltip("Create intents to match current TF state")
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    ui.button(
                        "Reset All to YAML",
                        icon="restart_alt",
                        on_click=reset_all_to_yaml,
                    ).props("outline color=red dense").classes("min-w-[170px]").tooltip("Clear all intents, fall back to YAML flags")
                    ui.button(
                        "Export JSON",
                        icon="download",
                        on_click=export_json,
                    ).props("outline dense").classes("min-w-[140px]").tooltip("Download protection-intent.json")

                ui.separator().classes("my-3")
                with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                    ui.label("Selection Actions").classes("text-xs font-semibold uppercase tracking-wide text-slate-500")
                    selection_label = ui.label("Selected: 0").classes("text-sm text-slate-500")
                    grid_ref["selection_label"] = selection_label
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    protect_selected_btn = ui.button(
                        "Protect Selected (0)",
                        icon="shield",
                        on_click=lambda: _apply_to_selected("protect"),
                    ).props("outline color=positive dense").classes("min-w-[170px]")
                    protect_selected_btn.set_enabled(False)
                    unprotect_selected_btn = ui.button(
                        "Unprotect Selected (0)",
                        icon="lock_open",
                        on_click=lambda: _apply_to_selected("unprotect"),
                    ).props("outline color=warning dense").classes("min-w-[170px]")
                    unprotect_selected_btn.set_enabled(False)
                    reset_selected_btn = ui.button(
                        "Reset Selected (0)",
                        icon="restart_alt",
                        on_click=lambda: _apply_to_selected("reset"),
                    ).props("outline dense").classes("min-w-[170px]")
                    reset_selected_btn.set_enabled(False)
                    grid_ref["bulk_btn_refs"] = {
                        "protect": protect_selected_btn,
                        "unprotect": unprotect_selected_btn,
                        "reset": reset_selected_btn,
                    }

            # Terraform actions for pending TF intents from this page.
            tf_outputs: dict[str, str] = {"init": "", "plan": "", "apply": ""}
            tf_failures: dict[str, Optional[str]] = {"init": None, "plan": None, "apply": None}

            def _resolve_tf_path() -> Path:
                tf_path, _yaml, _baseline = resolve_deployment_paths(state)
                return tf_path

            def _pending_tf_keys() -> set[str]:
                return {
                    key
                    for key in protection_intent._intent
                    if protection_intent._intent[key].applied_to_yaml
                    and not protection_intent._intent[key].applied_to_tf_state
                }

            def _extract_first_error_reason(output: str) -> Optional[str]:
                for line in output.splitlines():
                    if line.startswith("Error:"):
                        return line.replace("Error:", "", 1).strip() or "terraform command failed"
                return None

            def _run_tf_preflight(
                action_label: str,
                *,
                require_pending_intents: bool,
            ) -> Optional[tuple[Path, dict[str, str], list[str]]]:
                tf_path = _resolve_tf_path()
                if not tf_path.exists() or not tf_path.is_dir():
                    ui.notify(f"{action_label} blocked: terraform directory not found", type="negative")
                    return None

                if shutil.which("terraform") is None:
                    ui.notify(f"{action_label} blocked: terraform CLI not found in PATH", type="negative")
                    return None

                env = get_terraform_env(state)
                missing: list[str] = []
                if not env.get("TF_VAR_dbt_token", "").strip():
                    missing.append("TF_VAR_dbt_token")
                if not env.get("TF_VAR_dbt_account_id", "").strip():
                    missing.append("TF_VAR_dbt_account_id")
                if not env.get("TF_VAR_dbt_host_url", "").strip():
                    missing.append("TF_VAR_dbt_host_url")

                if missing:
                    ui.notify(
                        f"{action_label} blocked: missing terraform credentials ({', '.join(missing)})",
                        type="negative",
                    )
                    return None

                pending_keys = _pending_tf_keys()
                if require_pending_intents and not pending_keys:
                    ui.notify(f"{action_label} blocked: no pending TF intents", type="warning")
                    return None

                target_flags = build_target_flags(tf_path, protection_intent)
                if not target_flags:
                    ui.notify(
                        f"{action_label} blocked: no terraform targets found (refresh state or regenerate pending)",
                        type="warning",
                    )
                    return None

                return tf_path, env, target_flags

            async def _refresh_reconcile_state_from_terraform(tf_path: Path) -> None:
                """Refresh in-memory reconcile state from live terraform show -json."""
                try:
                    from importer.web.utils.terraform_state_reader import read_terraform_state

                    result = await read_terraform_state(tf_path)
                    if result.success:
                        state.deploy.reconcile_state_resources = [r.__dict__ for r in result.resources]
                        state.deploy.reconcile_state_loaded = True
                        if save_state:
                            save_state()
                        # region agent log
                        _agent_debug_log(
                            "H7",
                            "utilities.py:_refresh_reconcile_state_from_terraform",
                            "reconcile state refreshed from terraform show",
                            {
                                "tf_path": str(tf_path),
                                "resource_count": len(result.resources),
                                "has_fido": any(r.resource_index == "sse_dm_fin_fido" for r in result.resources),
                            },
                        )
                        # endregion
                except Exception:
                    # Non-blocking; stale reconcile state should not block plan/apply completion.
                    pass

            async def run_tf_init():
                tf_path = _resolve_tf_path()
                env = get_terraform_env(state)
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["terraform", "init", "-no-color", "-input=false"],
                    cwd=str(tf_path),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                tf_outputs["init"] = result.stdout + result.stderr
                tf_failures["init"] = _extract_first_error_reason(tf_outputs["init"]) if result.returncode != 0 else None
                if result.returncode == 0:
                    ui.notify("Terraform init completed", type="positive")
                else:
                    ui.notify("Terraform init failed", type="negative")

            async def run_tf_plan_pending():
                preflight = _run_tf_preflight("TF Plan Pending", require_pending_intents=False)
                if preflight is None:
                    return
                tf_path, env, target_flags = preflight
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["terraform", "plan", "-no-color", "-input=false", *target_flags],
                    cwd=str(tf_path),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                plan_output = result.stdout + result.stderr
                tf_outputs["plan"] = plan_output

                if result.returncode != 0:
                    reason = _extract_first_error_reason(plan_output)
                    tf_failures["plan"] = reason
                    if "Moved object still exists" in plan_output:
                        ui.notify("Plan failed: run Generate All Pending, then plan again", type="warning")
                    ui.notify(f"Terraform plan failed: {reason or 'see output'}", type="negative")
                    return

                tf_failures["plan"] = None
                # Move-only plans still require apply; do not auto-sync intents.
                has_moved_objects = (
                    " has moved to " in plan_output
                    or re.search(r"\b\d+\s+to move\b", plan_output) is not None
                )
                no_changes = (
                    (
                        "No changes." in plan_output
                        or "Your infrastructure matches the configuration" in plan_output
                    )
                    and not has_moved_objects
                )
                if no_changes:
                    keys = _pending_tf_keys()
                    # region agent log
                    _agent_debug_log(
                        "H8",
                        "utilities.py:run_tf_plan_pending",
                        "plan detected no changes; syncing pending tf intents",
                        {"pending_tf_keys_count": len(keys), "contains_fido": any("sse_dm_fin_fido" in k for k in keys)},
                    )
                    # endregion
                    if keys:
                        protection_intent.mark_applied_to_tf_state(keys)
                        protection_intent.save()
                        if save_state:
                            save_state()
                    await _refresh_reconcile_state_from_terraform(tf_path)
                    ui.notify("No TF changes needed; pending intents marked synced", type="positive")
                    ui.navigate.reload()
                elif has_moved_objects:
                    ui.notify("Terraform plan includes moved resources; run TF Apply Pending Intents", type="warning")
                else:
                    ui.notify("Terraform plan completed", type="positive")

            async def run_tf_apply_pending():
                preflight = _run_tf_preflight("TF Apply Pending Intents", require_pending_intents=True)
                if preflight is None:
                    return
                tf_path, env, target_flags = preflight
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["terraform", "apply", "-auto-approve", "-no-color", "-input=false", *target_flags],
                    cwd=str(tf_path),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                tf_outputs["apply"] = result.stdout + result.stderr
                tf_failures["apply"] = _extract_first_error_reason(tf_outputs["apply"]) if result.returncode != 0 else None
                if result.returncode == 0:
                    keys = _pending_tf_keys()
                    if keys:
                        protection_intent.mark_applied_to_tf_state(keys)
                        protection_intent.save()
                        if save_state:
                            save_state()
                    await _refresh_reconcile_state_from_terraform(tf_path)
                    ui.notify("Terraform apply completed; pending intents synced", type="positive")
                    ui.navigate.reload()
                else:
                    ui.notify(f"Terraform apply failed: {tf_failures['apply'] or 'see output'}", type="negative")

            async def refresh_tf_state():
                tf_path = _resolve_tf_path()
                await _refresh_reconcile_state_from_terraform(tf_path)
                ui.notify("Refreshed TF state from terraform show -json", type="positive")
                ui.navigate.reload()

            def show_tf_output(kind: str, title: str):
                output = tf_outputs.get(kind, "")
                if not output:
                    ui.notify(f"No {kind} output yet", type="warning")
                    return
                from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                create_plan_viewer_dialog(
                    output,
                    title,
                    failure_reason=tf_failures.get(kind),
                ).open()

            ui.label("Terraform Actions").classes("text-xs font-semibold uppercase tracking-wide text-slate-500")
            with ui.column().classes("w-full gap-2"):
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    ui.button(
                        "TF Init",
                        icon="download",
                        on_click=run_tf_init,
                    ).props("outline").tooltip("Run terraform init in deployment directory")
                    ui.button(
                        "TF Plan Pending",
                        icon="preview",
                        on_click=run_tf_plan_pending,
                    ).props("outline color=primary").tooltip("Run targeted terraform plan for pending protection moves")
                    ui.button(
                        "Refresh TF State",
                        icon="refresh",
                        on_click=refresh_tf_state,
                    ).props("outline").tooltip("Reload protection state from terraform show -json")
                    apply_btn = ui.button(
                        f"TF Apply Pending Intents ({pending_tf})",
                        icon="cloud_sync",
                        on_click=run_tf_apply_pending,
                    ).props("color=blue")
                    apply_btn.set_enabled(pending_tf > 0)

                ui.label("Outputs").classes("text-xs font-semibold uppercase tracking-wide text-slate-500")
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    ui.button(
                        "View Init Output",
                        icon="visibility",
                        on_click=lambda: show_tf_output("init", "Protection TF Init Output"),
                    ).props("flat")
                    ui.button(
                        "View Plan Output",
                        icon="visibility",
                        on_click=lambda: show_tf_output("plan", "Protection TF Plan Output"),
                    ).props("flat")
                    ui.button(
                        "View Apply Output",
                        icon="visibility",
                        on_click=lambda: show_tf_output("apply", "Protection TF Apply Output"),
                    ).props("flat")

            # Requested order: terraform actions above grid filters.
            _render_filter_controls()
        
        # AG Grid for Current Intents + state-only rows.
        if total_rows > 0:
            row_data = _filter_protection_rows(
                rows=all_rows,
                filter_state=filter_state,
                selected_keys=grid_ref["selected_keys"],
            )

            # region agent log
            _agent_debug_log(
                "D7",
                "utilities.py:_create_protection_management_section",
                "protection grid row composition",
                {
                    "total_rows": total_rows,
                    "intent_row_count": len(protection_intent._intent),
                    "state_rows_total": len(state_protection_by_key),
                    "state_only_count": sum(1 for row in all_rows if row.get("status") == "State Only"),
                    "member_state_row_present": "GRP:member" in state_protection_by_key,
                    "member_in_row_data": any(r.get("resource_key") == "GRP:member" for r in all_rows),
                },
            )
            # endregion

            column_defs = [
                {"field": "_selected", "colId": "_selected", "headerName": "", "width": 60, "editable": True, "cellRenderer": "agCheckboxCellRenderer", "headerCheckboxSelection": False},
                {"field": "resource_key", "colId": "resource_key", "headerName": "Resource Key", "flex": 2},
                {"field": "type", "colId": "type", "headerName": "Type", "width": 90},
                {"field": "intent", "colId": "intent", "headerName": "Intent", "width": 140},
                {"field": "intent_origin", "colId": "intent_origin", "headerName": "Intent Origin", "width": 130},
                {"field": "state", "colId": "state", "headerName": "State", "width": 120},
                {"field": "status", "colId": "status", "headerName": "Status", "width": 150},
                {"field": "set_at", "colId": "set_at", "headerName": "Set At", "width": 170},
                {"field": "actions", "colId": "actions", "headerName": "Actions", "width": 120, "cellRenderer": "agGroupCellRenderer"},
            ]

            grid = ui.aggrid({
                "columnDefs": column_defs,
                "rowData": row_data,
                "defaultColDef": {
                    "sortable": True,
                    "resizable": True,
                },
                "pagination": True,
                "paginationPageSize": 200,
                "paginationPageSizeSelector": [50, 100, 200],
            }, theme="quartz").classes("w-full ag-theme-quartz-auto-dark").style("height: 430px;")

            grid_ref["grid"] = grid
            _refresh_protection_grid(grid_ref, filter_state)

            grid.add_slot("body-cell-actions", '''
                <q-td :props="props">
                    <q-btn flat dense icon="edit" size="sm" @click="$parent.$emit('edit-intent', props.row)" />
                    <q-btn flat dense icon="visibility" size="sm" @click="$parent.$emit('view-details', props.row)" />
                </q-td>
            ''')

            def _set_selected_count(count: int) -> None:
                label = grid_ref.get("selection_label")
                if label:
                    label.set_text(f"Selected: {count}")
                bulk_btn_refs = grid_ref.get("bulk_btn_refs", {})
                for key, label_prefix in (("protect", "Protect Selected"), ("unprotect", "Unprotect Selected"), ("reset", "Reset Selected")):
                    btn = bulk_btn_refs.get(key)
                    if btn:
                        btn.set_text(f"{label_prefix} ({count})")
                        btn.set_enabled(count > 0)

            def on_cell_value_changed(e) -> None:
                if not e.args or e.args.get("colId") != "_selected":
                    return
                row = e.args.get("data", {})
                resource_key = row.get("resource_key")
                selected = bool(e.args.get("newValue", False))
                if not resource_key:
                    return
                selected_keys: set[str] = grid_ref["selected_keys"]
                if selected:
                    selected_keys.add(resource_key)
                else:
                    selected_keys.discard(resource_key)
                for existing in all_rows:
                    if existing.get("resource_key") == resource_key:
                        existing["_selected"] = selected
                        break
                _set_selected_count(len(selected_keys))
                _refresh_protection_grid(grid_ref, filter_state)

            grid.on("cellValueChanged", on_cell_value_changed)

            def handle_edit(row: dict) -> None:
                key = row.get("resource_key", "")
                current_intent = protection_intent.get_intent(key)
                initial_value = (
                    current_intent.protected
                    if current_intent is not None
                    else bool(row.get("intent_protected", False))
                )
                new_protected = {"value": initial_value}
                reason_text = {"value": ""}
                dialog = ui.dialog()
                with dialog:
                    with ui.card().classes("p-4").style("width: 520px;"):
                        ui.label("Edit Protection Intent").classes("text-lg font-semibold mb-4")
                        ui.input(label="Resource Key", value=key).props("dense outlined readonly").classes("w-full mb-3")
                        with ui.row().classes("w-full items-center gap-4 mb-3"):
                            ui.label("Protection Intent:").classes("font-medium")
                            ui.toggle(
                                {True: "Protect", False: "Unprotect"},
                                value=initial_value,
                                on_change=lambda e: new_protected.update({"value": bool(e.value)}),
                            )
                        ui.input(
                            label="Reason",
                            placeholder="Optional reason",
                            on_change=lambda e: reason_text.update({"value": e.value}),
                        ).props("dense outlined").classes("w-full mb-4")
                        with ui.row().classes("w-full items-center justify-between"):
                            def reset_to_baseline() -> None:
                                if protection_intent.has_intent(key):
                                    protection_intent.remove_intent(key, source="utilities_edit")
                                baseline_value = bool(row.get("state_protected") is True or row.get("yaml_protected") is True)
                                protection_intent.set_intent(
                                    key=key,
                                    protected=baseline_value,
                                    source="dense_baseline",
                                    reason="reset to baseline rule",
                                    resource_type=row.get("type", "UNKNOWN"),
                                )
                                protection_intent.save()
                                dialog.close()
                                ui.notify(f"Reset {key} to baseline", type="positive")
                                ui.navigate.reload()
                            ui.button("Reset to Baseline", on_click=reset_to_baseline).props("flat")
                            with ui.row().classes("items-center gap-2"):
                                ui.button("Cancel", on_click=dialog.close).props("flat")
                                def save_changes() -> None:
                                    protection_intent.set_intent(
                                        key=key,
                                        protected=bool(new_protected["value"]),
                                        source="utilities_edit",
                                        reason=reason_text["value"] or "Edited via Protection Management",
                                        resource_type=row.get("type", "UNKNOWN"),
                                    )
                                    protection_intent.save()
                                    dialog.close()
                                    ui.notify(f"Updated intent for {key}", type="positive")
                                    ui.navigate.reload()
                                ui.button("Save", on_click=save_changes).props("color=primary")
                dialog.open()

            def handle_view_details(row: dict) -> None:
                source_data, grid_row_payload, state_resource = _build_dialog_payload_from_protection_row(
                    row=row,
                    state_resource_by_key=state_resource_by_key,
                )
                show_match_detail_dialog(
                    source_data=source_data,
                    grid_row=grid_row_payload,
                    target_data=None,
                    state_resource=state_resource,
                    app_state=state,
                    available_targets=[],
                    has_state_loaded=bool(state.deploy.reconcile_state_loaded),
                    on_target_selected=None,
                    on_adopt=None,
                )

            grid.on("edit-intent", lambda e: handle_edit(e.args))
            grid.on("view-details", lambda e: handle_view_details(e.args))

            def on_cell_clicked(e) -> None:
                if not e.args:
                    return
                if e.args.get("colId") == "_selected":
                    return
                row = e.args.get("data")
                if isinstance(row, dict):
                    handle_view_details(row)

            grid.on("cellClicked", on_cell_clicked)
        else:
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("inbox", size="xl").classes("text-slate-300 mb-2")
                ui.label("No protection intents recorded").classes("text-lg text-slate-500")
                ui.label("Click Protect/Unprotect on the Match page to record intents").classes("text-sm text-slate-400")
        
        ui.separator().classes("my-6")
        
        # Audit History Section
        _create_audit_history_section(protection_intent)


def _create_audit_history_section(protection_intent) -> None:
    """Create the audit history section."""
    history = protection_intent._history
    
    with ui.row().classes("w-full items-center justify-between mb-4"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("history", size="md").classes("text-slate-600")
            ui.label(f"Audit History (last 20 of {len(history)})").classes("text-lg font-semibold")
        
        def copy_history():
            """Copy history to clipboard."""
            lines = []
            for entry in reversed(history):
                ts = entry.timestamp[:19].replace("T", " ") if entry.timestamp else ""
                lines.append(f"{ts} | {entry.resource_key} | {entry.action} | {entry.source}")
            text = "\n".join(lines)
            ui.run_javascript(f'navigator.clipboard.writeText({repr(text)})')
            ui.notify("Copied history to clipboard!", type="positive")
        
        ui.button(
            "Copy History",
            icon="content_copy",
            on_click=copy_history,
        ).props("flat dense")
    
    if history:
        # Show last 20 entries (newest first)
        recent_history = list(reversed(history[-20:]))
        
        # Build table data
        table_data = []
        for entry in recent_history:
            ts = entry.timestamp[:19].replace("T", " ") if entry.timestamp else ""
            table_data.append({
                "timestamp": ts,
                "resource": entry.resource_key,
                "action": entry.action,
                "source": entry.source,
            })
        
        columns = [
            {"name": "timestamp", "label": "Timestamp", "field": "timestamp", "align": "left"},
            {"name": "resource", "label": "Resource", "field": "resource", "align": "left"},
            {"name": "action", "label": "Action", "field": "action", "align": "left"},
            {"name": "source", "label": "Source", "field": "source", "align": "left"},
        ]
        
        table = ui.table(columns=columns, rows=table_data, row_key="timestamp").classes("w-full")
        
        # View All link
        if len(history) > 20:
            def view_all_history():
                """Show full history in a dialog."""
                dialog = ui.dialog()
                with dialog:
                    with ui.card().classes("p-4").style("width: 900px; max-width: 95vw; max-height: 90vh; overflow-y: auto;"):
                        ui.label(f"Full Audit History ({len(history)} entries)").classes("text-lg font-semibold mb-4")
                        
                        all_data = []
                        for entry in reversed(history):
                            ts = entry.timestamp[:19].replace("T", " ") if entry.timestamp else ""
                            all_data.append({
                                "timestamp": ts,
                                "resource": entry.resource_key,
                                "action": entry.action,
                                "source": entry.source,
                            })
                        
                        ui.table(columns=columns, rows=all_data, row_key="timestamp").classes("w-full")
                        
                        ui.button("Close", on_click=dialog.close).props("flat").classes("mt-4")
                
                dialog.open()
            
            ui.label(f"View all {len(history)} entries →").classes(
                "text-sm text-blue-600 cursor-pointer hover:underline mt-2"
            ).on("click", view_all_history)
    else:
        with ui.card().classes("w-full p-4 text-center"):
            ui.icon("history", size="lg").classes("text-slate-300 mb-2")
            ui.label("No history recorded yet").classes("text-slate-500")


def _count_values(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _filter_protection_rows(
    rows: list[dict],
    filter_state: dict,
    selected_keys: set[str],
) -> list[dict]:
    status_filter = filter_state.get("status", "all")
    type_filter = filter_state.get("type", "all")
    search_filter = str(filter_state.get("search", "") or "").strip().lower()
    selected_only = bool(filter_state.get("selected_only", False))
    hide_unprotected = bool(filter_state.get("hide_unprotected", True))

    status_map = {
        "pending_generate": "Pending Generate",
        "pending_tf": "Pending TF Intents",
        "state_mismatch": "State Mismatch",
        "state_only": "State Only",
        "synced": "Synced",
    }
    target_status = status_map.get(status_filter)

    filtered: list[dict] = []
    for row in rows:
        if selected_only and row.get("resource_key") not in selected_keys:
            continue
        if type_filter != "all" and row.get("type") != type_filter:
            continue
        if target_status is not None and row.get("status") != target_status:
            continue
        if hide_unprotected and bool(row.get("intent_protected", False)) is False:
            continue
        if search_filter:
            search_blob = " ".join(
                [
                    str(row.get("resource_key", "")),
                    str(row.get("type", "")),
                    str(row.get("intent", "")),
                    str(row.get("status", "")),
                ]
            ).lower()
            if search_filter not in search_blob:
                continue
        filtered.append(row)
    return filtered


def _refresh_protection_grid(grid_ref: dict, filter_state: dict) -> None:
    grid = grid_ref.get("grid")
    if grid is None:
        return
    all_rows: list[dict] = grid_ref.get("all_rows", [])
    selected_keys: set[str] = grid_ref.get("selected_keys", set())
    filtered_rows = _filter_protection_rows(all_rows, filter_state, selected_keys)
    grid.options["rowData"] = filtered_rows
    grid.update()
    showing_label = grid_ref.get("showing_label")
    if showing_label is not None:
        showing_label.set_text(f"{len(filtered_rows)} shown / {len(all_rows)} total")


def _parse_resource_key(resource_key: str) -> tuple[str, str]:
    if ":" in resource_key:
        rtype, base_key = resource_key.split(":", 1)
        return rtype, base_key
    return "UNKNOWN", resource_key


def _build_protection_grid_rows(
    protection_intent,
    state_protection_by_key: dict[str, bool],
    yaml_protected_resources: set[str],
) -> list[dict]:
    all_rows: list[dict] = []
    used_state_keys: set[str] = set()
    yaml_keys = set(yaml_protected_resources)

    for key, intent in protection_intent._intent.items():
        rtype, base_key = _parse_resource_key(key)
        typed_key = key if ":" in key else f"{rtype}:{base_key}"
        state_protected = state_protection_by_key.get(typed_key)
        if state_protected is not None:
            used_state_keys.add(typed_key)
        yaml_protected = key in yaml_keys or typed_key in yaml_keys or base_key in yaml_keys
        intent_protected = bool(intent.protected)
        intent_origin = "baseline" if intent.set_by == "dense_baseline" else "explicit"
        if not intent.applied_to_yaml:
            status = "Pending Generate"
        elif state_protected is not None and state_protected != intent_protected:
            status = "State Mismatch"
        elif not intent.applied_to_tf_state:
            status = "Pending TF Intents"
        else:
            status = "Synced"
        all_rows.append(
            {
                "_selected": False,
                "resource_key": typed_key,
                "type": rtype,
                "intent": "Protect" if intent_protected else "Unprotect",
                "intent_protected": intent_protected,
                "intent_origin": intent_origin,
                "state_protected": state_protected,
                "state": "Protected" if state_protected is True else "Unprotected" if state_protected is False else "Unknown",
                "yaml_protected": yaml_protected,
                "status": status,
                "set_at": intent.set_at[:19].replace("T", " ") if intent.set_at else "",
            }
        )

    for typed_key, state_protected in state_protection_by_key.items():
        if typed_key in used_state_keys:
            continue
        rtype, base_key = _parse_resource_key(typed_key)
        yaml_protected = typed_key in yaml_keys or base_key in yaml_keys
        intent_protected = bool(yaml_protected or state_protected)
        all_rows.append(
            {
                "_selected": False,
                "resource_key": typed_key,
                "type": rtype,
                "intent": "Protect" if intent_protected else "Unprotect",
                "intent_protected": intent_protected,
                "intent_origin": "baseline",
                "state_protected": bool(state_protected),
                "state": "Protected" if state_protected else "Unprotected",
                "yaml_protected": yaml_protected,
                "status": "State Only",
                "set_at": "",
            }
        )

    all_rows.sort(key=lambda row: (row.get("set_at", ""), row.get("resource_key", "")), reverse=True)
    return all_rows


def _build_dialog_payload_from_protection_row(
    row: dict,
    state_resource_by_key: dict[str, dict],
) -> tuple[dict, dict, Optional[dict]]:
    resource_key = str(row.get("resource_key", ""))
    rtype, base_key = _parse_resource_key(resource_key)
    state_resource = state_resource_by_key.get(resource_key)
    state_protected = row.get("state_protected")
    intent_protected = bool(row.get("intent_protected", False))
    if state_protected is None:
        drift_status = "no_state"
    elif bool(state_protected) == intent_protected:
        drift_status = "in_sync"
    else:
        drift_status = "protection_mismatch"

    source_data = {
        "name": base_key,
        "key": resource_key,
        "element_mapping_id": resource_key,
        "element_type_code": rtype,
        "display_name": base_key,
    }
    grid_row = {
        "source_key": resource_key,
        "source_type": rtype,
        "state_id": state_resource.get("dbt_id") if state_resource else None,
        "target_id": None,
        "action": "protect" if intent_protected else "unprotect",
        "drift_status": drift_status,
    }
    return source_data, grid_row, state_resource


def _update_filter(filter_state: dict, key: str, value, grid_ref: dict) -> None:
    """Update filter state and refresh grid."""
    filter_state[key] = value
    _refresh_protection_grid(grid_ref, filter_state)
