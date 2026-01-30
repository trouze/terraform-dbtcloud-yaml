"""Match step page - match source resources to existing target resources."""

import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from nicegui import ui

from importer.web.state import AppState, WorkflowStep
from importer.web.components.selection_manager import SelectionManager
from importer.web.utils.mapping_file import (
    save_mapping_file,
    create_mapping_from_confirmations,
)
from importer.web.utils.yaml_viewer import create_yaml_viewer_dialog
from importer.web.utils.terraform_state_reader import read_terraform_state, StateReadResult
from importer.web.utils.terraform_import import (
    generate_adopt_imports_from_grid,
    generate_state_rm_commands,
    generate_adoption_script,
    write_adopt_imports_file,
)
from importer.web.utils.protection_manager import (
    get_resources_to_protect,
    get_resources_to_unprotect,
    CascadeResource,
    check_single_resource_protection,
    EXTENDED_RESOURCE_TYPE_MAP,
    generate_repair_moved_blocks,
)
from importer.web.components.hierarchy_index import HierarchyIndex

if TYPE_CHECKING:
    from importer.web.utils.terraform_state_reader import StateReadResult


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"


def create_match_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Match step page for source-to-target resource matching."""
    
    with ui.element("div").classes("w-full max-w-7xl mx-auto p-4").style(
        "display: grid; "
        "grid-template-rows: auto 1fr auto; "
        "height: calc(100vh - 100px); "
        "gap: 8px; "
        "overflow: hidden;"
    ):
        # Row 1: Header
        _create_header(state)
        
        # Check prerequisites
        if not state.map.normalize_complete:
            _create_prerequisite_message(
                "Source Scope Required",
                "Complete the Scope step to normalize source resources first.",
                "Go to Scope",
                WorkflowStep.SCOPE,
                on_step_change,
            )
            return
        
        if not state.target_fetch.fetch_complete:
            _create_prerequisite_message(
                "Target Fetch Required", 
                "Fetch the target account data to match existing resources.",
                "Go to Fetch Target",
                WorkflowStep.FETCH_TARGET,
                on_step_change,
            )
            return
        
        # Load source and target report items
        all_source_items = _load_report_items(state, target=False)
        target_items = _load_report_items(state, target=True)
        
        if not all_source_items:
            _create_no_data_message("No source data available", on_step_change)
            return
        
        if not target_items:
            _create_no_data_message("No target data available", on_step_change)
            return
        
        # Filter source items by selection from Select Source step
        selection_manager = SelectionManager(
            account_id=state.source_account.account_id or "unknown",
            base_url=state.source_account.host_url,
        )
        selection_manager.load()
        selected_ids = selection_manager.get_selected_ids()
        
        # Filter to only selected items
        source_items = [
            item for item in all_source_items 
            if item.get("element_mapping_id") in selected_ids
        ]
        
        total_source_count = len(all_source_items)
        len(source_items)
        
        if not source_items:
            _create_no_selected_message(
                total_source_count,
                on_step_change,
            )
            return
        
        # Row 2: Main content - flex container that allows grid to grow
        # Note: Navigation is created inside _create_matching_content so it has access
        # to the grid data for accurate status display
        with ui.element("div").classes("flex flex-col").style(
            "width: 100%; height: 100%; overflow: auto; display: flex; flex-direction: column;"
        ):
            _create_matching_content(
                state, 
                source_items, 
                target_items, 
                save_state, 
                total_source_count,
                on_step_change,
            )


def _create_header(state: AppState) -> None:
    """Create the page header."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("link", size="md").style(f"color: {DBT_TEAL};")
                    ui.label("Match Source to Target Resources").classes("text-2xl font-bold")
                
                ui.label(
                    "Match source resources to existing target resources for Terraform import"
                ).classes("text-slate-600 dark:text-slate-400")
            
            # Show both account details with ID and URL
            with ui.row().classes("gap-4"):
                if state.fetch.account_name or state.source_account.account_id:
                    with ui.card().classes("p-2"):
                        ui.label("Source").classes("text-xs text-slate-500 font-semibold")
                        ui.label(state.fetch.account_name or "Unknown").classes("font-medium text-sm")
                        with ui.column().classes("gap-0 mt-1"):
                            if state.source_account.account_id:
                                ui.label(f"ID: {state.source_account.account_id}").classes("text-xs text-slate-400 font-mono")
                            if state.source_account.host_url:
                                ui.label(state.source_account.host_url).classes("text-xs text-slate-400 font-mono")
                
                ui.icon("arrow_forward").classes("text-slate-400 self-center")
                
                if state.target_fetch.account_name or state.target_account.account_id:
                    with ui.card().classes("p-2").style(f"border: 1px solid {DBT_TEAL};"):
                        ui.label("Target").classes("text-xs text-slate-500 font-semibold")
                        ui.label(state.target_fetch.account_name or "Unknown").classes("font-medium text-sm")
                        with ui.column().classes("gap-0 mt-1"):
                            if state.target_account.account_id:
                                ui.label(f"ID: {state.target_account.account_id}").classes("text-xs text-slate-400 font-mono")
                            if state.target_account.host_url:
                                ui.label(state.target_account.host_url).classes("text-xs text-slate-400 font-mono")


def _create_prerequisite_message(
    title: str,
    message: str,
    button_text: str,
    target_step: WorkflowStep,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Show message when prerequisites are not met."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("warning", size="3rem").classes("text-amber-500 mx-auto")
        ui.label(title).classes("text-xl font-bold mt-4")
        ui.label(message).classes("text-slate-600 dark:text-slate-400 mt-2")
        ui.button(
            button_text,
            icon="arrow_back",
            on_click=lambda: on_step_change(target_step),
        ).classes("mt-4").style(f"background-color: {DBT_TEAL};")


def _create_no_data_message(message: str, on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Show message when data is missing."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("error_outline", size="3rem").classes("text-red-500 mx-auto")
        ui.label(message).classes("text-xl font-bold mt-4")


def _create_no_selected_message(
    total_count: int,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Show message when no items are selected."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("filter_list_off", size="3rem").classes("text-amber-500 mx-auto")
        ui.label("No Resources Selected").classes("text-xl font-bold mt-4")
        ui.label(
            f"{total_count} resources are available, but none are selected for matching."
        ).classes("text-slate-600 dark:text-slate-400 mt-2")
        ui.label(
            "Go to Select Source to choose which resources to include."
        ).classes("text-slate-500 dark:text-slate-400")
        ui.button(
            "Adjust Selection",
            icon="tune",
            on_click=lambda: on_step_change(WorkflowStep.SCOPE),
        ).classes("mt-4")


def _load_report_items(state: AppState, target: bool = False) -> list:
    """Load report items from source or target fetch."""
    if target:
        report_file = state.target_fetch.last_report_items_file
    else:
        report_file = state.fetch.last_report_items_file
    
    if not report_file:
        return []
    
    try:
        report_path = Path(report_file)
        if report_path.exists():
            return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        logging.warning(f"Error loading report items: {e}")
    
    return []


def _create_matching_content(
    state: AppState,
    source_items: list,
    target_items: list,
    save_state: Callable[[], None],
    total_source_count: int = 0,
    on_step_change: Optional[Callable[[WorkflowStep], None]] = None,
) -> None:
    """Create the main matching interface with editable grid."""
    from importer.web.components.match_grid import (
        build_grid_data,
        create_match_grid,
        create_grid_toolbar,
        export_mappings_to_csv,
        DRIFT_ID_MISMATCH,
        DRIFT_NOT_IN_STATE,
    )
    from importer.web.components.clone_dialog import show_clone_dialog
    from importer.web.state import CloneConfig
    
    # Mutable container for state result (shared across callbacks)
    state_ref = {
        "state_result": None,
        "state_loaded": state.deploy.reconcile_state_loaded,
    }
    
    # Store target_items for callbacks (since it's a local variable)
    target_items_ref = {"items": target_items}
    
    # Build hierarchy index for parent/child lookups (used for protection cascade)
    hierarchy_index = HierarchyIndex(source_items)
    
    # Try to restore state result if previously loaded
    # (We store serialized state in reconcile_state_resources)
    if state.deploy.reconcile_state_loaded and state.deploy.reconcile_state_resources:
        # Reconstruct a minimal StateReadResult from saved data
        import re
        from importer.web.utils.terraform_state_reader import StateReadResult, StateResource
        state_result = StateReadResult(success=True)
        for res_data in state.deploy.reconcile_state_resources:
            # Get resource_index from cached data, or extract from address as fallback
            resource_index = res_data.get("resource_index")
            address = res_data.get("address", "")
            if resource_index is None and address and "[" in address:
                # Extract index from address like: resource.name["key"] or resource.name[0]
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
            state_result.resources.append(resource)
            if resource.dbt_id is not None:
                state_result.resources_by_id[(resource.element_code, resource.dbt_id)] = resource
        state_ref["state_result"] = state_result
    
    # Build grid data from source/target items and existing mappings
    rejected_keys = state.map.rejected_suggestions if isinstance(state.map.rejected_suggestions, set) else set(state.map.rejected_suggestions)
    clone_configs = getattr(state.map, "cloned_resources", [])
    
    grid_row_data = build_grid_data(
        source_items,
        target_items,
        state.map.confirmed_mappings,
        rejected_keys,
        clone_configs,
        state_result=state_ref["state_result"],
        protected_resources=state.map.protected_resources,
    )
    
    # Stats from grid data - separate primary resources from derived resources
    # Derived resource types: JEVO (env var overrides), JCTG (job triggers), PREP (project repo links)
    derived_types = {"JEVO", "JCTG", "PREP"}
    primary_rows = [r for r in grid_row_data if r.get("source_type") not in derived_types]
    derived_rows = [r for r in grid_row_data if r.get("source_type") in derived_types]
    
    pending = sum(1 for r in primary_rows if r.get("status") == "pending" and r.get("action") == "match")
    confirmed = sum(1 for r in primary_rows if r.get("status") == "confirmed")
    create_new_primary = sum(1 for r in primary_rows if r.get("action") == "create_new")
    create_new_derived = len(derived_rows)  # All derived resources are create_new
    create_new_total = create_new_primary + create_new_derived
    skipped = sum(1 for r in primary_rows if r.get("action") == "skip")
    
    # Total rows in grid including overrides
    total_grid_rows = len(grid_row_data)
    
    # Stat cards with selection info
    with ui.row().classes("w-full gap-4 mb-4 items-center"):
        _create_stat_card("Pending", pending, "text-amber-600", "hourglass_empty")
        _create_stat_card("Confirmed", confirmed, "text-green-600", "check_circle")
        
        # Create New card - show total with breakdown if overrides exist
        with ui.card().classes("p-3 min-w-[100px]"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("add_circle", size="sm").classes("text-orange-500")
                ui.label(str(create_new_total)).classes("text-2xl font-bold text-orange-500")
            ui.label("Create New").classes("text-xs text-slate-500")
            if create_new_derived > 0:
                ui.label(f"({create_new_primary} + {create_new_derived} derived)").classes(
                    "text-xs text-orange-400"
                )
        
        _create_stat_card("Skip", skipped, "text-slate-500", "block")
        
        # Selected source items with total count - shows primary resources + overrides
        with ui.card().classes("p-3 min-w-[120px]"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("upload", size="sm").classes("text-blue-600")
                ui.label(f"{total_grid_rows} of {total_source_count + create_new_derived}").classes(
                    "text-2xl font-bold text-blue-600"
                )
            with ui.row().classes("items-center gap-2"):
                ui.label("Total Resources").classes("text-xs text-slate-500")
                if on_step_change and total_source_count > len(source_items):
                    ui.button(
                        "Adjust",
                        icon="tune",
                        on_click=lambda: on_step_change(WorkflowStep.SCOPE),
                    ).props("flat dense size=xs")
            if create_new_derived > 0:
                ui.label(f"({len(source_items)} selected + {create_new_derived} derived)").classes(
                    "text-xs text-blue-400"
                )
        
        _create_stat_card("Existing Target Items", len(target_items), f"color: {DBT_TEAL}", "download")
        
        # Drift stats (only show if state is loaded)
        drift_count = sum(
            1 for r in grid_row_data 
            if r.get("drift_status") in [DRIFT_ID_MISMATCH, DRIFT_NOT_IN_STATE]
        )
        if state_ref["state_loaded"]:
            with ui.card().classes("p-3 min-w-[100px]"):
                with ui.row().classes("items-center gap-2"):
                    if drift_count > 0:
                        ui.icon("warning", size="sm").classes("text-amber-500")
                        ui.label(str(drift_count)).classes("text-2xl font-bold text-amber-500")
                    else:
                        ui.icon("check_circle", size="sm").classes("text-green-500")
                        ui.label("0").classes("text-2xl font-bold text-green-500")
                ui.label("Drift").classes("text-xs text-slate-500")
    
    # Store grid row data in a mutable container for callbacks
    grid_data_ref = {"data": grid_row_data}
    
    # Reset all mappings function
    def reset_all_mappings():
        """Reset all mappings and re-generate suggestions."""
        # Clear confirmed mappings
        state.map.confirmed_mappings = []
        # Clear suggested matches
        state.map.suggested_matches = []
        # Clear rejected suggestions
        state.map.rejected_suggestions = set()
        # Invalidate mapping file
        state.map.mapping_file_valid = False
        
        # Delete mapping file if exists
        if state.map.mapping_file_path:
            mapping_path = Path(state.map.mapping_file_path)
            if mapping_path.exists():
                try:
                    mapping_path.unlink()
                except Exception as e:
                    logging.warning(f"Could not delete mapping file: {e}")
            state.map.mapping_file_path = None
        
        save_state()
        ui.notify("All mappings reset. Suggestions will be regenerated.", type="info")
        ui.navigate.reload()
    
    def accept_all_pending():
        """Accept all pending matches."""
        # Confidence types that represent automatic matching (not manual selection)
        auto_match_types = {
            "exact_match", "state_id_match", "url_match", "github_match", "env_match"
        }
        for row in grid_data_ref["data"]:
            # Include both "match" and "adopt" actions - both represent mapping to existing target resources
            if row.get("status") == "pending" and row.get("action") in ("match", "adopt") and row.get("target_id"):
                confidence = row.get("confidence", "manual")
                state.map.confirmed_mappings.append({
                    "resource_type": row.get("source_type"),
                    "source_name": row.get("source_name"),
                    "source_key": row.get("source_key"),
                    "target_id": row.get("target_id"),
                    "target_name": row.get("target_name"),
                    # Store the action for deploy.py to filter on
                    "action": row.get("action"),
                    # Preserve the actual confidence type for better diagnostics
                    "match_type": confidence if confidence in auto_match_types else "manual",
                })
        save_state()
        ui.navigate.reload()
                    
    def reject_all_pending():
        """Reject all pending matches - set them to create new."""
        for row in grid_data_ref["data"]:
            if row.get("status") == "pending" and row.get("action") == "match":
                if isinstance(state.map.rejected_suggestions, set):
                    state.map.rejected_suggestions.add(row.get("source_key"))
                else:
                    state.map.rejected_suggestions = set(state.map.rejected_suggestions)
                    state.map.rejected_suggestions.add(row.get("source_key"))
        save_state()
        ui.navigate.reload()
                    
    async def export_csv():
        """Export current mappings to CSV."""
        csv_content = export_mappings_to_csv(grid_data_ref["data"])
        escaped = csv_content.replace('`', '\\`')
        await ui.run_javascript(f'''
            const blob = new Blob([`{escaped}`], {{type: 'text/csv'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'resource_mappings.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        ''')
        ui.notify("CSV exported", type="positive")
    
    def show_protection_cascade_dialog(
        resource_name: str,
        parents_to_protect: list[CascadeResource],
        on_confirm: Callable[[], None],
    ) -> None:
        """Show dialog confirming protection of resource and its parents."""
        with ui.dialog() as dialog, ui.card().classes("p-4").style("min-width: 450px;"):
            with ui.row().classes("items-center gap-2 mb-4"):
                ui.icon("shield", size="md").classes("text-blue-500")
                ui.label("Protect Resource").classes("text-lg font-bold")
            
            ui.label(
                f"To protect '{resource_name}', the following parent resources must also be protected:"
            ).classes("mb-3")
            
            with ui.column().classes("pl-4 gap-1 mb-4"):
                for res in parents_to_protect:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("subdirectory_arrow_right", size="xs").classes("text-slate-400")
                        ui.badge(res.type_label).props("dense color=blue-grey")
                        ui.label(res.name).classes("text-sm")
            
            ui.label(
                "This ensures Terraform won't destroy parent resources that protected children depend on."
            ).classes("text-xs text-slate-500 mb-4")
            
            with ui.row().classes("gap-2 justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                
                def confirm_and_close():
                    on_confirm()
                    dialog.close()
                
                ui.button(
                    f"Protect All ({len(parents_to_protect) + 1})",
                    on_click=confirm_and_close,
                ).props("color=primary")
        
        dialog.open()
    
    def show_unprotection_cascade_dialog(
        resource_name: str,
        protected_children: list[CascadeResource],
        on_unprotect_all: Callable[[], None],
        on_unprotect_self_only: Callable[[], None],
    ) -> None:
        """Show dialog asking about unprotecting children."""
        with ui.dialog() as dialog, ui.card().classes("p-4").style("min-width: 450px;"):
            with ui.row().classes("items-center gap-2 mb-4"):
                ui.icon("shield_outlined", size="md").classes("text-amber-500")
                ui.label("Unprotect Resource").classes("text-lg font-bold")
            
            ui.label(
                f"'{resource_name}' has {len(protected_children)} protected child resource(s):"
            ).classes("mb-3")
            
            with ui.column().classes("pl-4 gap-1 mb-4"):
                for res in protected_children[:10]:  # Show max 10
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("subdirectory_arrow_right", size="xs").classes("text-slate-400")
                        ui.badge(res.type_label).props("dense color=blue-grey")
                        ui.label(res.name).classes("text-sm")
                if len(protected_children) > 10:
                    ui.label(f"... and {len(protected_children) - 10} more").classes("text-xs text-slate-400 pl-6")
            
            ui.label(
                "Would you like to unprotect the children as well?"
            ).classes("text-sm mb-4")
            
            with ui.row().classes("gap-2 justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                
                def unprotect_self_and_close():
                    on_unprotect_self_only()
                    dialog.close()
                
                def unprotect_all_and_close():
                    on_unprotect_all()
                    dialog.close()
                
                ui.button(
                    "Unprotect This Only",
                    on_click=unprotect_self_and_close,
                ).props("flat color=grey")
                
                ui.button(
                    f"Unprotect All ({len(protected_children) + 1})",
                    on_click=unprotect_all_and_close,
                ).props("color=amber")
        
        dialog.open()
    
    def apply_protection(keys_to_protect: list[str]) -> None:
        """Apply protection to multiple resources."""
        for key in keys_to_protect:
            state.map.protected_resources.add(key)
        save_state()
        ui.notify(f"Protected {len(keys_to_protect)} resource(s)", type="positive")
        ui.navigate.reload()
    
    def remove_protection(keys_to_unprotect: list[str]) -> None:
        """Remove protection from multiple resources."""
        for key in keys_to_unprotect:
            state.map.protected_resources.discard(key)
        save_state()
        ui.notify(f"Unprotected {len(keys_to_unprotect)} resource(s)", type="info")
        ui.navigate.reload()
    
    def on_row_change(row_data: dict):
        """Handle row data changes from the grid."""
        source_key = row_data.get("source_key")
        action = row_data.get("action")
        new_protected = row_data.get("protected", False)
        row_data.get("status")
        
        # region agent log
        try:
            with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                import json as _json
                f.write(_json.dumps({"location": "match.py:on_row_change:entry", "message": "Row change received", "data": {"source_key": source_key, "action": action, "new_protected": new_protected, "in_protected_resources": source_key in state.map.protected_resources}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H1"}) + "\n")
        except: pass
        # endregion
        
        # IMPORTANT: Always update grid_data_ref immediately so dialogs see current state
        # This must happen BEFORE any early returns for cascade dialogs
        # Also update yaml_protected to stay consistent with the user's intent
        row_data["yaml_protected"] = new_protected
        for i, row in enumerate(grid_data_ref["data"]):
            if row.get("source_key") == source_key:
                grid_data_ref["data"][i] = row_data
                # region agent log
                try:
                    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                        import json as _json
                        f.write(_json.dumps({"location": "match.py:on_row_change:grid_update", "message": "Updated grid_data_ref", "data": {"source_key": source_key, "new_protected": new_protected, "yaml_protected": row_data.get("yaml_protected"), "row_protected_after": grid_data_ref["data"][i].get("protected")}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H1"}) + "\n")
                except: pass
                # endregion
                break
        
        # Check if protection status changed
        old_protected = source_key in state.map.protected_resources
        
        if new_protected and not old_protected:
            # User is protecting this resource - check for cascade
            target_resource, parents_to_protect = get_resources_to_protect(
                source_key, hierarchy_index, source_items, state.map.protected_resources
            )
            
            if parents_to_protect:
                # Has unprotected parents - show confirmation dialog
                all_keys = [source_key] + [p.key for p in parents_to_protect]
                show_protection_cascade_dialog(
                    target_resource.name,
                    parents_to_protect,
                    on_confirm=lambda keys=all_keys: apply_protection(keys),
                )
                return  # Don't save yet - wait for dialog
            else:
                # No parents to protect, just protect this one
                state.map.protected_resources.add(source_key)
                save_state()
                ui.notify(f"Protected: {target_resource.name}", type="positive")
                # Reload to refresh protection mismatch panel
                ui.navigate.reload()
                return
        
        elif not new_protected and old_protected:
            # User is removing protection - check for protected children
            target_resource, protected_children = get_resources_to_unprotect(
                source_key, hierarchy_index, source_items, state.map.protected_resources
            )
            
            if protected_children:
                # Has protected children - show dialog
                child_keys = [c.key for c in protected_children]
                show_unprotection_cascade_dialog(
                    target_resource.name,
                    protected_children,
                    on_unprotect_all=lambda keys=[source_key] + child_keys: remove_protection(keys),
                    on_unprotect_self_only=lambda: remove_protection([source_key]),
                )
                return  # Don't save yet - wait for dialog
            else:
                # No protected children, just unprotect
                state.map.protected_resources.discard(source_key)
                save_state()
                ui.notify(f"Unprotected: {target_resource.name}", type="info")
                # Reload to refresh protection mismatch panel
                ui.navigate.reload()
                return
        
        # Note: grid_data_ref update now happens at the start of this function
        # to ensure dialogs always see the current state
        
        # If action is match and has valid target, it can be confirmed
        # If action is skip or create_new, remove from confirmed if present
        if action in ("skip", "create_new"):
            state.map.confirmed_mappings = [
                m for m in state.map.confirmed_mappings 
                if m.get("source_key") != source_key
            ]
        
        save_state()
    
    def on_accept(source_key: str):
        """Accept a single suggestion."""
        for row in grid_data_ref["data"]:
            if row.get("source_key") == source_key:
                if row.get("target_id"):
                    state.map.confirmed_mappings.append({
                        "resource_type": row.get("source_type"),
                        "source_name": row.get("source_name"),
                        "source_key": source_key,
                        "target_id": row.get("target_id"),
                        "target_name": row.get("target_name"),
                        "action": row.get("action", "adopt"),  # Include action for deploy.py
                        "match_type": "manual",
                    })
                    row["status"] = "confirmed"
                    break
        save_state()
        ui.navigate.reload()
    
    def on_reject(source_key: str):
        """Reject a single suggestion."""
        if isinstance(state.map.rejected_suggestions, set):
            state.map.rejected_suggestions.add(source_key)
        else:
            state.map.rejected_suggestions = set(state.map.rejected_suggestions)
            state.map.rejected_suggestions.add(source_key)
        save_state()
        ui.navigate.reload()
    
    def find_source_item(source_key: str) -> Optional[dict]:
        """Find source item by key, checking both 'key' and 'element_mapping_id'."""
        # region agent log
        try:
            with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                import json as _json
                f.write(_json.dumps({"location": "match.py:find_source_item", "message": "Looking for source_key", "data": {"source_key": source_key, "source_items_count": len(source_items)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H1"}) + "\n")
        except: pass
        # endregion
        # Items with key=null use element_mapping_id as their key
        for s in source_items:
            item_key = s.get("key") or s.get("element_mapping_id", "")
            if item_key == source_key:
                # region agent log
                try:
                    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                        import json as _json
                        f.write(_json.dumps({"location": "match.py:find_source_item", "message": "FOUND source_item", "data": {"source_key": source_key, "item_type": s.get("element_type_code"), "item_name": s.get("name")}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H1"}) + "\n")
                except: pass
                # endregion
                return s
        # region agent log
        try:
            sample_keys = [s.get("key") or s.get("element_mapping_id", "") for s in source_items[:10]]
            with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                import json as _json
                f.write(_json.dumps({"location": "match.py:find_source_item", "message": "NOT FOUND - source_key not in source_items", "data": {"source_key": source_key, "sample_keys": sample_keys}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H1"}) + "\n")
        except: pass
        # endregion
        return None
    
    def on_view_details(source_key: str):
        """View details for a resource."""
        # Check if this is a JEVO (job env var override) - synthetic key format
        if "__override__" in source_key:
            # Extract parent job key and variable name
            parts = source_key.split("__override__", 1)
            parent_job_key = parts[0]
            var_name = parts[1] if len(parts) > 1 else "Unknown"
            
            # Find parent job to get override value
            parent_job = find_source_item(parent_job_key)
            if parent_job:
                overrides = parent_job.get("environment_variable_overrides", {})
                var_value = overrides.get(var_name, "N/A")
                job_name = parent_job.get("name", parent_job_key)
                
                # Show simple dialog for override details
                with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[400px]"):
                    ui.label("Environment Variable Override").classes("text-lg font-bold mb-4")
                    
                    with ui.column().classes("gap-2"):
                        with ui.row().classes("gap-2"):
                            ui.label("Variable:").classes("font-semibold w-24")
                            ui.label(var_name).classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("Value:").classes("font-semibold w-24")
                            # Mask secret values
                            display_value = "********" if "SECRET" in var_name.upper() else str(var_value)
                            ui.label(display_value).classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("Parent Job:").classes("font-semibold w-24")
                            ui.label(job_name).classes("font-mono")
                    
                    ui.button("Close", on_click=dialog.close).classes("mt-4")
                dialog.open()
            else:
                ui.notify(f"Parent job not found for override: {source_key}", type="warning")
            return
        
        # Check if this is a JCTG (job completion trigger) - synthetic key format
        if "__trigger__completion" in source_key:
            parent_job_key = source_key.split("__trigger__completion")[0]
            
            parent_job = find_source_item(parent_job_key)
            if parent_job:
                job_name = parent_job.get("name", parent_job_key)
                jctc = parent_job.get("job_completion_trigger_condition", {})
                
                # Extract trigger details
                trigger_job_id = jctc.get("job_id") or jctc.get("condition", {}).get("job_id")
                statuses = jctc.get("statuses") or jctc.get("condition", {}).get("statuses", [])
                
                # Map status codes to names
                status_map = {10: "Success", 20: "Error", 30: "Cancelled"}
                status_names = [status_map.get(s, str(s)) for s in statuses] if statuses else ["Unknown"]
                
                with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[400px]"):
                    ui.label("Job Completion Trigger").classes("text-lg font-bold mb-4")
                    
                    with ui.column().classes("gap-2"):
                        with ui.row().classes("gap-2"):
                            ui.label("Parent Job:").classes("font-semibold w-28")
                            ui.label(job_name).classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("Trigger Job ID:").classes("font-semibold w-28")
                            ui.label(str(trigger_job_id) if trigger_job_id else "N/A").classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("On Statuses:").classes("font-semibold w-28")
                            ui.label(", ".join(status_names)).classes("font-mono")
                    
                    ui.button("Close", on_click=dialog.close).classes("mt-4")
                dialog.open()
            else:
                ui.notify(f"Parent job not found for trigger: {source_key}", type="warning")
            return
        
        # Check if this is a PREP (project repository link) - synthetic key format
        if "__repo_link__" in source_key:
            parts = source_key.split("__repo_link__", 1)
            parent_project_key = parts[0]
            repo_key = parts[1] if len(parts) > 1 else "Unknown"
            
            parent_project = find_source_item(parent_project_key)
            if parent_project:
                project_name = parent_project.get("name", parent_project_key)
                
                with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[400px]"):
                    ui.label("Project Repository Link").classes("text-lg font-bold mb-4")
                    
                    with ui.column().classes("gap-2"):
                        with ui.row().classes("gap-2"):
                            ui.label("Project:").classes("font-semibold w-28")
                            ui.label(project_name).classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("Repository:").classes("font-semibold w-28")
                            ui.label(repo_key).classes("font-mono")
                        ui.label(
                            "This resource links the project to its repository in Terraform."
                        ).classes("text-xs text-slate-500 mt-2")
                    
                    ui.button("Close", on_click=dialog.close).classes("mt-4")
                dialog.open()
            else:
                ui.notify(f"Parent project not found for repository link: {source_key}", type="warning")
            return
        
        # Regular resource - use enhanced match detail dialog with drift info
        source_item = find_source_item(source_key)
        # region agent log
        try:
            with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                import json as _json
                f.write(_json.dumps({"location": "match.py:on_view_details", "message": "After find_source_item", "data": {"source_key": source_key, "source_item_found": source_item is not None, "source_item_type": source_item.get("element_type_code") if source_item else None}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H2"}) + "\n")
        except: pass
        # endregion
        if source_item:
            from importer.web.components.entity_table import show_match_detail_dialog
            
            # Find grid row data for this source
            grid_row = None
            for row in grid_data_ref["data"]:
                if row.get("source_key") == source_key:
                    grid_row = row
                    break
            
            # region agent log
            try:
                with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                    import json as _json
                    f.write(_json.dumps({"location": "match.py:on_view_details:grid_row_lookup", "message": "Found grid row for dialog", "data": {"source_key": source_key, "grid_row_found": grid_row is not None, "grid_row_protected": grid_row.get("protected") if grid_row else None, "in_protected_resources": source_key in state.map.protected_resources}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H3"}) + "\n")
            except: pass
            # endregion
            
            if not grid_row:
                grid_row = {"source_key": source_key, "drift_status": "no_state"}
            
            # Find target data if matched
            target_data = None
            target_id = grid_row.get("target_id")
            if target_id:
                # Use target_items_ref which stores the target items passed to this function
                for t in target_items_ref.get("items", []):
                    if str(t.get("dbt_id")) == str(target_id):
                        target_data = t
                        break
            
            # Find state resource data if available
            state_resource = None
            state_id = grid_row.get("state_id")
            if state_ref.get("state_result") and state_ref["state_result"].resources:
                source_type = source_item.get("element_type_code", "")
                # Try to find by ID first
                if state_id:
                    for res in state_ref["state_result"].resources:
                        if res.dbt_id == state_id and res.element_code == source_type:
                            state_resource = {
                                "address": res.address,
                                "dbt_id": res.dbt_id,
                                "name": res.name,
                                "tf_name": res.tf_name,
                                "element_code": res.element_code,
                                "project_id": res.project_id,
                                "resource_index": res.resource_index,
                                **res.attributes,
                            }
                            break
            
            # Callback to handle manual target selection from dropdown
            def handle_target_selected(selected_target: dict):
                """Handle when user selects a target from the dropdown."""
                source_key = source_item.get("key") or source_item.get("element_mapping_id", "")
                source_type = source_item.get("element_type_code", "")
                target_id = selected_target.get("dbt_id")
                target_name = selected_target.get("name", "")
                # region agent log
                try:
                    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as log_file:
                        log_file.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H4",
                            "location": "match.py:646",
                            "message": "handle_target_selected input",
                            "data": {
                                "source_key": source_key,
                                "source_type": source_type,
                                "target_id": target_id,
                                "target_id_type": str(type(target_id)),
                                "target_name": target_name,
                            },
                            "timestamp": int(time.time() * 1000),
                        }) + "\n")
                except Exception:
                    pass
                # endregion
                
                # Check if target is in TF state to determine action
                action = "match"
                if state_ref.get("state_result") and state_ref["state_result"].resources:
                    # Check if this target_id is in state
                    found_in_state = False
                    for res in state_ref["state_result"].resources:
                        if res.dbt_id == target_id and res.element_code == source_type:
                            found_in_state = True
                            break
                    if not found_in_state:
                        action = "adopt"  # Target exists but not in TF state - needs adoption
                elif state_ref.get("state_loaded"):
                    # State is loaded but target not found
                    action = "adopt"
                
                # Add to confirmed mappings
                if not hasattr(state.map, "confirmed_mappings"):
                    state.map.confirmed_mappings = []
                
                # Remove any existing mapping for this source
                state.map.confirmed_mappings = [
                    m for m in state.map.confirmed_mappings
                    if m.get("source_key") != source_key
                ]
                
                # Add new mapping with action
                state.map.confirmed_mappings.append({
                    "source_key": source_key,
                    "target_id": target_id,
                    "target_name": target_name,
                    "match_type": "manual",
                    "action": action,  # Store the action with the mapping
                })
                
                # Also remove from rejected keys if it was there
                if hasattr(state.map, "rejected_suggestions"):
                    if isinstance(state.map.rejected_suggestions, set):
                        state.map.rejected_suggestions.discard(source_key)
                    elif isinstance(state.map.rejected_suggestions, list):
                        state.map.rejected_suggestions = [k for k in state.map.rejected_suggestions if k != source_key]
                
                save_state()
                ui.notify(f"Matched to {target_name} (ID: {target_id}) with action '{action}'", type="positive")
                ui.navigate.reload()  # Reload to update the grid
            
            # Callback to handle "Set to Adopt" button click
            def handle_adopt(protected: bool = True):
                """Handle when user clicks Set to Adopt button.
                
                Args:
                    protected: Whether to protect this resource from destroy (default: True)
                """
                source_key = source_item.get("key") or source_item.get("element_mapping_id", "")
                source_type = source_item.get("element_type_code", "")
                target_id = grid_row.get("target_id")
                target_name = grid_row.get("target_name", "")
                # region agent log
                try:
                    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as log_file:
                        log_file.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H5",
                            "location": "match.py:709",
                            "message": "handle_adopt input",
                            "data": {
                                "source_key": source_key,
                                "source_type": source_type,
                                "target_id": target_id,
                                "target_id_type": str(type(target_id)),
                                "target_name": target_name,
                                "protected": protected,
                            },
                            "timestamp": int(time.time() * 1000),
                        }) + "\n")
                except Exception:
                    pass
                # endregion
                
                # Add/update confirmed mapping with adopt action
                if not hasattr(state.map, "confirmed_mappings"):
                    state.map.confirmed_mappings = []
                
                # Remove any existing mapping for this source
                state.map.confirmed_mappings = [
                    m for m in state.map.confirmed_mappings
                    if m.get("source_key") != source_key
                ]
                
                # Add new mapping with adopt action and protection flag
                state.map.confirmed_mappings.append({
                    "source_key": source_key,
                    "target_id": target_id,
                    "target_name": target_name,
                    "match_type": "manual",
                    "action": "adopt",
                    "protected": protected,  # Store protection preference
                })
                
                save_state()
                protection_msg = " (protected)" if protected else ""
                ui.notify(f"Set {source_item.get('name', source_key)} to adopt{protection_msg}", type="positive")
                ui.navigate.reload()
            
            # region agent log
            try:
                with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                    import json as _json
                    f.write(_json.dumps({"location": "match.py:on_view_details", "message": "Calling show_match_detail_dialog", "data": {"source_key": source_key, "has_target": target_data is not None, "has_state_resource": state_resource is not None}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H5"}) + "\n")
            except: pass
            # endregion
            show_match_detail_dialog(
                source_data=source_item,
                grid_row=grid_row,
                target_data=target_data,
                state_resource=state_resource,
                app_state=state,
                available_targets=target_items_ref.get("items", []),
                has_state_loaded=state_ref.get("state_loaded", False),
                on_target_selected=handle_target_selected,
                on_adopt=handle_adopt,
            )
        else:
            # region agent log
            try:
                with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                    import json as _json
                    f.write(_json.dumps({"location": "match.py:on_view_details", "message": "source_item is None - dialog NOT opened", "data": {"source_key": source_key}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H1"}) + "\n")
            except: pass
            # endregion
            ui.notify(f"Source resource not found: {source_key}", type="warning")
    
    def on_configure_clone(source_key: str):
        """Configure clone for a resource set to Create New."""
        source_item = find_source_item(source_key)
        if not source_item:
            ui.notify(f"Source resource not found: {source_key}", type="negative")
            return
        
        # Check for existing config
        existing_config = None
        cloned_resources = getattr(state.map, "cloned_resources", [])
        for config in cloned_resources:
            if config.source_key == source_key:
                existing_config = config
                break
        
        def save_clone_config(config: CloneConfig):
            """Save clone configuration to state."""
            # Initialize cloned_resources if needed
            if not hasattr(state.map, "cloned_resources"):
                state.map.cloned_resources = []
            
            # Remove existing config if present
            state.map.cloned_resources = [
                c for c in state.map.cloned_resources 
                if c.source_key != config.source_key
            ]
            
            # Add new config
            state.map.cloned_resources.append(config)
            save_state()
            ui.navigate.reload()
        
        show_clone_dialog(
            source_item=source_item,
            all_source_items=source_items,
            state=state,
            on_save=save_clone_config,
            existing_config=existing_config,
        )
    
    # Load Terraform State function
    async def load_terraform_state():
        """Load Terraform state to enable drift detection."""
        # Get terraform directory
        tf_dir = state.deploy.terraform_dir or "deployments/migration"
        tf_path = Path(tf_dir)
        if not tf_path.is_absolute():
            # Make relative to project root
            project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
            tf_path = project_root / tf_dir
        
        ui.notify("Loading Terraform state...", type="info")
        
        result = await read_terraform_state(tf_path)
        
        if not result.success:
            ui.notify(f"Failed to load state: {result.error_message}", type="negative")
            return
        
        if not result.resources:
            ui.notify("Terraform state is empty or no dbt Cloud resources found", type="warning")
            # Still mark as loaded so we can show "not in state" drift
        
        # Save to app state for persistence
        state.deploy.reconcile_state_loaded = True
        state.deploy.reconcile_state_resources = [
            {
                "address": r.address,
                "tf_type": r.tf_type,
                "element_code": r.element_code,
                "tf_name": r.tf_name,
                "dbt_id": r.dbt_id,
                "name": r.name,
                "project_id": r.project_id,
                "attributes": r.attributes,
                "resource_index": r.resource_index,
            }
            for r in result.resources
        ]
        save_state()
        
        ui.notify(f"Loaded {len(result.resources)} resources from Terraform state", type="positive")
        ui.navigate.reload()
    
    # Info banner with Reset button and Load State button
    with ui.card().classes("w-full p-3 mb-4").style(f"border-left: 4px solid {DBT_TEAL};"):
        with ui.row().classes("w-full items-start justify-between"):
            with ui.row().classes("items-start gap-2"):
                ui.icon("info", size="sm").style(f"color: {DBT_TEAL};")
                with ui.column().classes("gap-1"):
                    ui.label("How Matching Works").classes("font-semibold text-sm")
                    ui.label(
                        "Resources are auto-matched by exact name. Edit Action to change behavior: "
                        "Match = import existing, Create New = create fresh, Skip = exclude from migration. "
                        "Double-click a row to view details."
                    ).classes("text-xs text-slate-500")
                    if state_ref["state_loaded"]:
                        ui.label(
                            "Terraform state loaded - State ID and Drift columns show reconciliation status."
                        ).classes("text-xs text-green-600")
            
            with ui.row().classes("items-center gap-2"):
                # Load Terraform State button
                if state_ref["state_loaded"]:
                    ui.button(
                        "State Loaded",
                        icon="check_circle",
                        on_click=load_terraform_state,
                    ).props("flat text-color=green-6 size=sm").tooltip(
                        "Click to reload Terraform state"
                    )
                else:
                    ui.button(
                        "Load TF State",
                        icon="cloud_download",
                        on_click=load_terraform_state,
                    ).props("outline size=sm").tooltip(
                        "Load Terraform state to detect drift between state and target"
                    )
                
                # Reset All Mappings button
                ui.button(
                    "Reset All Mappings",
                    icon="refresh",
                    on_click=reset_all_mappings,
                ).props("flat text-color=orange-6 size=sm").tooltip(
                    "Clear all mappings and regenerate suggestions"
                )
    
    # Grid toolbar
    create_grid_toolbar(
        grid_row_data,
        on_accept_all=accept_all_pending,
        on_reject_all=reject_all_pending,
        on_reset_all=reset_all_mappings,
        on_export_csv=export_csv,
    )
    
    # Main grid in a card - flex container that grows to fill available space
    with ui.card().classes("w-full p-4 flex flex-col flex-grow").style("min-height: 350px;"):
        grid, _ = create_match_grid(
            source_items,
            target_items,
            state.map.confirmed_mappings,
            rejected_keys,
            on_row_change=on_row_change,
            on_accept=on_accept,
            on_reject=on_reject,
            on_view_details=on_view_details,
            clone_configs=clone_configs,
            on_configure_clone=on_configure_clone,
            state_result=state_ref["state_result"],
            protected_resources=state.map.protected_resources,
        )
    
    # Adopt imports section - show when TF state is loaded so user can adopt resources
    # This section lets users generate import blocks for resources marked with action="adopt"
    adopt_count = sum(1 for r in grid_row_data if r.get("action") == "adopt" and r.get("target_id"))
    # Only count resources that NEED adoption (target exists but not in state, or ID mismatch)
    # Exclude "state_only" - those are orphan resources in state, not adoption candidates
    # Also require that the resource has a target_id (something to adopt)
    drift_needing_adoption = [
        r for r in grid_row_data 
        if r.get("drift_status") in ("not_in_state", "id_mismatch") 
        and r.get("target_id")
        and r.get("action") != "adopt"  # Don't double-count already marked for adopt
    ]
    drift_resources_exist = len(drift_needing_adoption)
    mismatch_count = sum(1 for r in grid_row_data if r.get("action") == "adopt" and r.get("drift_status") == "id_mismatch")
    has_state = state_ref.get("state_result") is not None
    
    # Shared log storage for execution results - persisted in state
    # Format: {"logs": [(timestamp, cmd, success, output, cwd), ...]}
    # Initialize from persisted state so logs survive page reloads
    execution_logs_ref: dict[str, list] = {"logs": state.deploy.reconcile_execution_logs}
    
    def strip_ansi(text: str) -> str:
        """Remove ANSI escape codes from text."""
        import re
        ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
        return ansi_pattern.sub('', text)
    
    # Show adopt section if state is loaded and there are resources that could be adopted
    if has_state and (adopt_count > 0 or drift_resources_exist > 0):
        with ui.card().classes("w-full p-4 mt-4").style("border: 2px solid #8B5CF6;"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("download", size="sm").classes("text-purple-600")
                        ui.label("Adopt Resources into Terraform State").classes("font-semibold")
                    
                    if adopt_count > 0:
                        ui.label(
                            f"{adopt_count} resources marked for adoption"
                        ).classes("text-sm text-purple-600")
                    elif drift_resources_exist > 0:
                        # Show which resources have drift
                        drift_names = [f"{r.get('source_type', '?')}:{r.get('source_name', '?')}" for r in drift_needing_adoption[:3]]
                        drift_preview = ", ".join(drift_names)
                        if len(drift_needing_adoption) > 3:
                            drift_preview += f" (+{len(drift_needing_adoption) - 3} more)"
                        ui.label(
                            f"{drift_resources_exist} resources have drift: {drift_preview}"
                        ).classes("text-sm text-amber-600")
                        ui.label(
                            "Change Action to 'adopt' to import them"
                        ).classes("text-xs text-slate-500")
                    
                    ui.label(
                        "Set Action='adopt' in the grid for resources you want to import, then click Generate"
                    ).classes("text-xs text-slate-500")
                    
                    if state.deploy.reconcile_imports_generated:
                        ui.label("Import blocks generated - run terraform plan/apply").classes(
                            "text-xs text-green-600 mt-1"
                        )
                
                def generate_adopt_imports():
                    # region agent log
                    try:
                        with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as log_file:
                            log_file.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H8",
                                "location": "match.py:925",
                                "message": "generate_adopt_imports clicked",
                                "data": {
                                    "state_loaded": bool(state_ref.get("state_result")),
                                    "grid_ref_count": len(grid_data_ref.get("data", [])),
                                },
                                "timestamp": int(time.time() * 1000),
                            }) + "\n")
                    except Exception:
                        pass
                    # endregion
                    # Get terraform directory
                    tf_dir = state.deploy.terraform_dir or "deployments/migration"
                    tf_path = Path(tf_dir)
                    if not tf_path.is_absolute():
                        project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                        tf_path = project_root / tf_dir
                    # region agent log
                    try:
                        with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as log_file:
                            log_file.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H12",
                                "location": "match.py:930",
                                "message": "terraform path resolved",
                                "data": {
                                    "tf_dir": tf_dir,
                                    "tf_path": str(tf_path),
                                },
                                "timestamp": int(time.time() * 1000),
                            }) + "\n")
                    except Exception:
                        pass
                    # endregion
                    
                    # Get ALL grid rows - function will filter internally but needs PRJ rows for lookup
                    all_rows = grid_data_ref["data"]
                    adopt_rows = [r for r in all_rows if r.get("action") == "adopt" and r.get("target_id")]
                    # region agent log
                    try:
                        sample = []
                        for r in adopt_rows[:5]:
                            sample.append({
                                "source_key": r.get("source_key"),
                                "source_type": r.get("source_type"),
                                "source_name": r.get("source_name"),
                                "project_name": r.get("project_name"),
                                "target_id": r.get("target_id"),
                            })
                        with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as log_file:
                            log_file.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H9",
                                "location": "match.py:933",
                                "message": "adopt_rows selected",
                                "data": {
                                    "adopt_count": len(adopt_rows),
                                    "sample": sample,
                                },
                                "timestamp": int(time.time() * 1000),
                            }) + "\n")
                    except Exception:
                        pass
                    # endregion
                    
                    if not adopt_rows:
                        # Log the attempt
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        execution_logs_ref["logs"].append((
                            timestamp,
                            "Generate Import Blocks",
                            False,
                            "No resources marked for adoption. Set Action='adopt' in the grid first.",
                            str(tf_path),
                        ))
                        save_state()  # Persist the log entry
                        ui.notify("No resources marked for adoption. Set Action='adopt' in the grid first.", type="warning")
                        return
                    
                    # Generate and write imports file - pass ALL rows so PRJ lookup works
                    output_path, error = write_adopt_imports_file(
                        all_rows,
                        tf_path,
                        filename="adopt_imports.tf",
                    )
                    # region agent log
                    try:
                        with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as log_file:
                            log_file.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H10",
                                "location": "match.py:941",
                                "message": "write_adopt_imports_file returned",
                                "data": {
                                    "output_path": str(output_path) if output_path else None,
                                    "error": error,
                                },
                                "timestamp": int(time.time() * 1000),
                            }) + "\n")
                    except Exception:
                        pass
                    # endregion
                    
                    if error:
                        # Log the failure
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        execution_logs_ref["logs"].append((
                            timestamp,
                            f"Generate Import Blocks ({len(adopt_rows)} resources)",
                            False,
                            f"Error: {error}",
                            str(tf_path),
                        ))
                        save_state()  # Persist the log entry
                        ui.notify(f"Error generating imports: {error}", type="negative")
                        return
                    
                    # Log the success
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Build detailed output message
                    import_summary_lines = ["Generated import blocks for:"]
                    for row in adopt_rows:
                        import_summary_lines.append(f"  - {row.get('source_type', '?')}: {row.get('source_name', row.get('source_key', '?'))} → target ID {row.get('target_id', '?')}")
                    import_summary_lines.append(f"\nOutput file: {output_path}")
                    
                    execution_logs_ref["logs"].append((
                        timestamp,
                        f"Generate Import Blocks ({len(adopt_rows)} resources)",
                        True,
                        "\n".join(import_summary_lines),
                        str(tf_path),
                    ))
                    
                    state.deploy.reconcile_imports_generated = True
                    
                    # Save adopt rows for use in Generate Files (adoption YAML overrides)
                    # Debug: log all REP rows and their actions
                    rep_rows = [r for r in all_rows if r.get("source_type") == "REP"]
                    # region agent log
                    try:
                        with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as log_file:
                            log_file.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H20",
                                "location": "match.py:adopt_rows",
                                "message": "REP rows before filtering",
                                "data": {
                                    "rep_count": len(rep_rows),
                                    "samples": [{"source_key": r.get("source_key"), "action": r.get("action"), "target_id": r.get("target_id"), "drift_status": r.get("drift_status")} for r in rep_rows[:5]],
                                },
                                "timestamp": int(time.time() * 1000),
                            }) + "\n")
                    except Exception:
                        pass
                    # endregion
                    
                    adopt_rows = [
                        {
                            "source_key": r.get("source_key"),
                            "source_type": r.get("source_type"),
                            "source_name": r.get("source_name"),
                            "target_id": r.get("target_id"),
                            "target_name": r.get("target_name"),
                            "project_name": r.get("project_name"),
                            "project_id": r.get("project_id"),
                            "drift_status": r.get("drift_status"),
                        }
                        for r in all_rows
                        if r.get("action") == "adopt" and r.get("target_id")
                    ]
                    
                    # region agent log
                    try:
                        with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as log_file:
                            log_file.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H21",
                                "location": "match.py:adopt_rows",
                                "message": "adopt_rows after filtering",
                                "data": {
                                    "adopt_count": len(adopt_rows),
                                    "samples": adopt_rows[:5] if adopt_rows else [],
                                },
                                "timestamp": int(time.time() * 1000),
                            }) + "\n")
                    except Exception:
                        pass
                    # endregion
                    
                    state.deploy.reconcile_adopt_rows = adopt_rows
                    
                    # Log the saved adoption data
                    saved_data_lines = [f"Saved {len(adopt_rows)} resources for adoption override in Deploy:"]
                    for row in adopt_rows:
                        saved_data_lines.append(f"  - {row.get('source_type', '?')}: {row.get('source_key', '?')} (drift: {row.get('drift_status', 'unknown')})")
                    
                    execution_logs_ref["logs"].append((
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        f"Save Adoption Data ({len(adopt_rows)} resources)",
                        True,
                        "\n".join(saved_data_lines),
                        str(tf_path),
                    ))
                    
                    save_state()
                    
                    ui.notify(f"Import blocks written to {output_path}. Re-run 'terraform plan' to see imports.", type="positive", timeout=5000)
                    ui.navigate.reload()
                
                with ui.row().classes("gap-2"):
                    ui.button(
                        "Generate Import Blocks",
                        icon="file_download",
                        on_click=generate_adopt_imports,
                    ).style("background-color: #8B5CF6;")
                    def preview_adopt_imports():
                        # Build preview content - pass ALL rows so PRJ lookup works for project_id
                        all_rows = grid_data_ref["data"]
                        
                        # Get state rm commands for ID mismatches
                        state_rm_cmds = generate_state_rm_commands(all_rows)
                        
                        # Get import blocks
                        import_content = generate_adopt_imports_from_grid(all_rows, module_name="dbt_cloud")
                        adopt_count = sum(1 for r in all_rows if r.get("action") == "adopt" and r.get("target_id"))
                        mismatch_count = sum(1 for r in all_rows if r.get("action") == "adopt" and r.get("drift_status") == "id_mismatch")
                        
                        with ui.dialog().classes("w-3/4") as dialog, ui.card().classes("w-full max-h-screen overflow-auto"):
                            ui.label("Adoption Plan Preview").classes("text-lg font-semibold mb-2")
                            
                            # Show state rm commands if any
                            if state_rm_cmds:
                                with ui.expansion(f"Step 1: Remove Stale State ({len(state_rm_cmds)} commands)", icon="delete_sweep").classes("w-full mb-2").props("default-opened"):
                                    ui.label("These resources have different IDs in Terraform state vs target. The stale state entries must be removed before importing the correct resources.").classes("text-sm text-amber-600 mb-2")
                                    ui.label("This does NOT destroy any actual dbt Cloud resources.").classes("text-xs text-slate-500 mb-2")
                                    state_rm_content = "\n".join(state_rm_cmds)
                                    ui.code(state_rm_content, language="bash").classes("w-full text-xs")
                            else:
                                ui.label("Step 1: No stale state entries to remove").classes("text-sm text-green-600 mb-2")
                            
                            # Show import blocks
                            with ui.expansion(f"Step 2: Import Blocks ({adopt_count} resources)", icon="file_download").classes("w-full").props("default-opened"):
                                ui.code(import_content, language="hcl").classes("w-full text-xs")
                            
                            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                                if state_rm_cmds:
                                    async def run_state_rm():
                                        """Execute state rm commands"""
                                        from datetime import datetime
                                        import subprocess
                                        
                                        # Resolve terraform directory
                                        tf_dir = state.deploy.terraform_dir or "deployments/migration"
                                        tf_path = Path(tf_dir)
                                        if not tf_path.is_absolute():
                                            project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                                            tf_path = project_root / tf_dir
                                        
                                        if not tf_path.exists():
                                            ui.notify(f"Terraform directory not found: {tf_path}", type="negative")
                                            return
                                        
                                        results = []
                                        for cmd in state_rm_cmds:
                                            timestamp = datetime.now().isoformat(timespec='seconds')
                                            try:
                                                result = subprocess.run(
                                                    cmd,
                                                    shell=True,
                                                    cwd=str(tf_path),
                                                    capture_output=True,
                                                    text=True,
                                                )
                                                output = strip_ansi(result.stdout + result.stderr)
                                                results.append((timestamp, cmd, result.returncode == 0, output, str(tf_path)))
                                            except Exception as e:
                                                results.append((timestamp, cmd, False, str(e), str(tf_path)))
                                        
                                        # Store logs for later viewing
                                        execution_logs_ref["logs"].extend(results)
                                        save_state()  # Persist logs
                                        
                                        # Close the preview dialog
                                        dialog.close()
                                        
                                        # Show results in a new dialog
                                        success_count = sum(1 for _, _, ok, _, _ in results if ok)
                                        with ui.dialog().classes("w-3/4") as results_dialog, ui.card().classes("w-full max-h-screen overflow-auto"):
                                            if success_count == len(results):
                                                ui.label("State Removal Complete").classes("text-lg font-semibold text-green-600 mb-2")
                                                ui.label(f"Successfully removed {success_count} stale state entries.").classes("text-sm mb-4")
                                            else:
                                                ui.label("State Removal Results").classes("text-lg font-semibold text-amber-600 mb-2")
                                                ui.label(f"Removed {success_count}/{len(results)} entries.").classes("text-sm mb-4")
                                            
                                            ui.label(f"Working directory: {tf_path}").classes("text-xs text-slate-500 mb-4 font-mono")
                                            
                                            # Show command output
                                            for ts, cmd, ok, output, cwd in results:
                                                status_icon = "check_circle" if ok else "error"
                                                status_color = "text-green-600" if ok else "text-red-600"
                                                with ui.expansion(f"{cmd}", icon=status_icon).classes(f"w-full mb-2 {status_color}").props("default-opened" if not ok else ""):
                                                    ui.label(f"[{ts}]").classes("text-xs text-slate-400 font-mono")
                                                    if output.strip():
                                                        ui.code(output, language="text").classes("w-full text-xs")
                                                    else:
                                                        ui.label("(no output)").classes("text-xs text-slate-500")
                                            
                                            with ui.row().classes("w-full justify-end mt-4"):
                                                ui.button("Close", on_click=results_dialog.close).props("flat")
                                        results_dialog.open()
                                    
                                    ui.button(
                                        "Run State Remove Commands",
                                        icon="delete_sweep",
                                        on_click=run_state_rm,
                                    ).props("color=warning")
                                ui.button("Close", on_click=dialog.close).props("flat")
                        dialog.open()

                    ui.button(
                        "Preview Adoption Plan",
                        icon="visibility",
                        on_click=preview_adopt_imports,
                    ).props("outline").classes("text-purple-600")
                    
                    # Direct Run State Removal button (if there are mismatches)
                    if mismatch_count > 0:
                        async def run_state_removal_direct():
                            """Execute state rm commands directly"""
                            from datetime import datetime
                            import subprocess
                            
                            all_rows = grid_data_ref["data"]
                            state_rm_cmds = generate_state_rm_commands(all_rows)
                            
                            if not state_rm_cmds:
                                ui.notify("No stale state entries to remove", type="info")
                                return
                            
                            # Resolve terraform directory - use deployment dir from state
                            tf_dir = state.deploy.terraform_dir or "deployments/migration"
                            tf_path = Path(tf_dir)
                            if not tf_path.is_absolute():
                                # Make relative to project root
                                project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                                tf_path = project_root / tf_dir
                            
                            if not tf_path.exists():
                                ui.notify(f"Terraform directory not found: {tf_path}", type="negative")
                                return
                            
                            results = []
                            for cmd in state_rm_cmds:
                                timestamp = datetime.now().isoformat(timespec='seconds')
                                try:
                                    result = subprocess.run(
                                        cmd,
                                        shell=True,
                                        cwd=str(tf_path),
                                        capture_output=True,
                                        text=True,
                                    )
                                    output = strip_ansi(result.stdout + result.stderr)
                                    results.append((timestamp, cmd, result.returncode == 0, output, str(tf_path)))
                                except Exception as e:
                                    results.append((timestamp, cmd, False, str(e), str(tf_path)))
                            
                            # Store logs for later viewing
                            execution_logs_ref["logs"].extend(results)
                            save_state()  # Persist logs
                            
                            # Show results dialog
                            success_count = sum(1 for _, _, ok, _, _ in results if ok)
                            with ui.dialog().classes("w-3/4") as results_dialog, ui.card().classes("w-full max-h-screen overflow-auto"):
                                if success_count == len(results):
                                    ui.label("State Removal Complete").classes("text-lg font-semibold text-green-600 mb-2")
                                    ui.label(f"Successfully removed {success_count} stale state entries.").classes("text-sm mb-4")
                                else:
                                    ui.label("State Removal Results").classes("text-lg font-semibold text-amber-600 mb-2")
                                    ui.label(f"Removed {success_count}/{len(results)} entries.").classes("text-sm mb-4")
                                
                                ui.label(f"Working directory: {tf_path}").classes("text-xs text-slate-500 mb-4 font-mono")
                                
                                # Show command output
                                for ts, cmd, ok, output, cwd in results:
                                    status_icon = "check_circle" if ok else "error"
                                    status_color = "text-green-600" if ok else "text-red-600"
                                    with ui.expansion(f"{cmd}", icon=status_icon).classes(f"w-full mb-2 {status_color}").props("default-opened" if not ok else ""):
                                        ui.label(f"[{ts}]").classes("text-xs text-slate-400 font-mono")
                                        if output.strip():
                                            ui.code(output, language="text").classes("w-full text-xs")
                                        else:
                                            ui.label("(no output)").classes("text-xs text-slate-500")
                                
                                with ui.row().classes("w-full justify-end mt-4"):
                                    ui.button("Close", on_click=results_dialog.close).props("flat")
                            results_dialog.open()
                        
                        ui.button(
                            f"Run State Removal ({mismatch_count})",
                            icon="delete_sweep",
                            on_click=run_state_removal_direct,
                        ).props("color=warning")
                    
                    # View Logs button
                    def show_execution_logs():
                        """Show last execution logs in traditional format"""
                        logs = execution_logs_ref.get("logs", [])
                        filter_text = {"value": ""}
                        
                        with ui.dialog().props("maximized") as logs_dialog, ui.card().classes("w-full h-full"):
                            # Header bar
                            with ui.row().classes("w-full items-center justify-between p-4 border-b dark:border-slate-700"):
                                with ui.row().classes("items-center gap-4"):
                                    ui.icon("article", size="md").classes("text-slate-600")
                                    ui.label("Execution Logs").classes("text-xl font-semibold")
                                    if logs:
                                        # Summary badges
                                        total = len(logs)
                                        success = sum(1 for e in logs if (e[2] if len(e) == 5 else e[1]))
                                        failed = total - success
                                        ui.badge(f"{total} total").props("outline")
                                        ui.badge(f"{success} success", color="green")
                                        if failed > 0:
                                            ui.badge(f"{failed} failed", color="red")
                                
                                with ui.row().classes("items-center gap-2"):
                                    if logs:
                                        # Search input
                                        search_input = ui.input(placeholder="Filter logs...").props("dense outlined").classes("w-64")
                                        
                                        def clear_logs():
                                            execution_logs_ref["logs"].clear()  # Clear in-place to preserve reference
                                            state.deploy.reconcile_execution_logs.clear()  # Also clear persisted state
                                            save_state()
                                            logs_dialog.close()
                                            ui.notify("Logs cleared", type="info")
                                        ui.button("Clear All", icon="delete", on_click=clear_logs).props("flat color=negative")
                                    ui.button("Close", icon="close", on_click=logs_dialog.close).props("flat")
                            
                            if not logs:
                                with ui.column().classes("w-full h-full items-center justify-center"):
                                    ui.icon("inbox", size="4rem").classes("text-slate-300 mb-4")
                                    ui.label("No execution logs yet").classes("text-lg text-slate-500")
                                    ui.label("Run a command to see logs here.").classes("text-sm text-slate-400")
                            else:
                                # Main log content area - full height terminal style
                                with ui.scroll_area().classes("w-full flex-grow bg-slate-900 dark:bg-slate-950"):
                                    with ui.element("div").classes("p-6 font-mono text-sm"):
                                        for idx, entry in enumerate(logs):
                                            # Handle both old format (3-tuple) and new format (5-tuple)
                                            if len(entry) == 5:
                                                ts, cmd, ok, output, cwd = entry
                                            else:
                                                cmd, ok, output = entry
                                                ts = "unknown"
                                                cwd = "unknown"
                                            
                                            status_text = "SUCCESS" if ok else "FAILED"
                                            status_color = "text-green-400" if ok else "text-red-400"
                                            bg_color = "bg-green-900/20" if ok else "bg-red-900/20"
                                            
                                            # Log entry container
                                            with ui.element("div").classes(f"mb-4 p-4 rounded-lg {bg_color} border border-slate-700"):
                                                # Header row with timestamp and status
                                                with ui.row().classes("w-full items-center gap-4 mb-2"):
                                                    ui.label(f"#{idx + 1}").classes("text-slate-500 font-bold")
                                                    ui.label(f"[{ts}]").classes("text-slate-400")
                                                    ui.label(status_text).classes(f"{status_color} font-bold px-2 py-0.5 rounded text-xs")
                                                
                                                # Command line
                                                with ui.row().classes("w-full items-start gap-2 mb-2"):
                                                    ui.label("$").classes("text-cyan-400 font-bold")
                                                    ui.label(cmd).classes("text-white break-all whitespace-pre-wrap")
                                                
                                                # Working directory
                                                if cwd and cwd != "unknown":
                                                    ui.label(f"cwd: {cwd}").classes("text-slate-500 text-xs mb-2")
                                                
                                                # Output
                                                if output and output.strip():
                                                    ui.label("Output:").classes("text-slate-400 text-xs mt-2 mb-1")
                                                    with ui.element("pre").classes("text-xs bg-black/30 p-3 rounded overflow-x-auto whitespace-pre-wrap"):
                                                        line_color = "text-red-300" if not ok else "text-slate-300"
                                                        ui.label(output.strip()).classes(f"{line_color}")
                                                elif not ok:
                                                    ui.label("(no output captured)").classes("text-slate-500 text-xs italic")
                        
                        logs_dialog.open()
                    
                    ui.button(
                        "View Logs",
                        icon="article",
                        on_click=show_execution_logs,
                    ).props("flat").classes("text-slate-600")
    
    # Protection mismatch section - detect and fix state/YAML protection mismatches
    # Scan grid data for protection mismatches (state says protected but YAML says not, or vice versa)
    protection_mismatches = []
    
    def _extract_resource_key_from_address(address: str) -> str:
        """Extract the resource key from a Terraform state address.
        
        Address format: module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["key"]
        Returns: "key"
        """
        import re
        match = re.search(r'\["([^"]+)"\]$', address)
        if match:
            return match.group(1)
        return ""
    
    for row in grid_row_data:
        source_type = row.get("source_type", "")
        state_address = row.get("state_address")
        
        if source_type in EXTENDED_RESOURCE_TYPE_MAP and state_address:
            # Use the separate protection fields from grid row
            # yaml_protected = what user wants (from protected_resources set / YAML config)
            # state_protected = what TF state actually has (from address containing "protected_")
            yaml_protected = row.get("yaml_protected", False)
            state_protected = row.get("state_protected", False)
            
            # Check for mismatch
            if state_protected != yaml_protected:
                # Extract resource key from the state address (most reliable source)
                # Address format: module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["key"]
                resource_key = _extract_resource_key_from_address(state_address)
                
                # Fallback to source_key or project_name if extraction failed
                if not resource_key:
                    if source_type == "PRJ":
                        # For projects, source_key is the project key
                        resource_key = row.get("source_key", "")
                    else:
                        # For REP/PREP, project_name is the key (repos are keyed by project)
                        resource_key = row.get("project_name", row.get("source_key", ""))
                
                # Skip if we still don't have a key
                if not resource_key:
                    continue
                
                project_name = row.get("project_name") or resource_key
                protection_mismatches.append({
                    "type": source_type,
                    "key": resource_key,
                    "name": row.get("source_name", resource_key),
                    "state_protected": state_protected,
                    "yaml_protected": yaml_protected,
                    "project_name": project_name,
                })
    
    # Group mismatches by project to identify all related resources
    # And deduplicate since PRJ, REP, PREP may all show for same project
    unique_projects_with_mismatches = set()
    for m in protection_mismatches:
        unique_projects_with_mismatches.add(m.get("project_name") or m.get("key"))
    
    if has_state and protection_mismatches:
        with ui.card().classes("w-full p-4 mt-4").style("border: 2px solid #F59E0B;"):
            # Container for pending status - placed at card level, not inside button row
            fix_status_container = ui.element("div").classes("w-full")
            
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-1 flex-grow"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("warning", size="sm").classes("text-amber-600")
                        ui.label("Protection Mismatches Detected").classes("font-semibold text-amber-600")
                    
                    ui.label(
                        f"{len(protection_mismatches)} resources in {len(unique_projects_with_mismatches)} project(s) have protection status mismatch"
                    ).classes("text-sm text-amber-600")
                    
                    # Show preview of mismatches
                    preview_items = []
                    for m in protection_mismatches[:3]:
                        direction = "protect" if m["yaml_protected"] else "unprotect"
                        preview_items.append(f"{m['type']}:{m['key']} ({direction})")
                    preview_text = ", ".join(preview_items)
                    if len(protection_mismatches) > 3:
                        preview_text += f" (+{len(protection_mismatches) - 3} more)"
                    ui.label(preview_text).classes("text-xs text-slate-500")
                    
                    ui.label(
                        "State protection status differs from YAML config. Generate moved blocks to reconcile."
                    ).classes("text-xs text-slate-500")
                
                with ui.row().classes("gap-2 flex-shrink-0"):
                    def show_protection_details():
                        """Show details of all protection mismatches"""
                        # Use standard dialog with explicit centering via Quasar classes
                        with ui.dialog() as detail_dialog:
                            detail_dialog.props("position=standard")
                            with ui.card().classes("q-pa-md max-h-screen overflow-auto").style("width: 950px; max-width: 90vw; margin: 0 auto;"):
                                ui.label("Protection Mismatches").classes("text-lg font-semibold mb-4")
                                
                                # Group by project
                                by_project: dict[str, list] = {}
                                for m in protection_mismatches:
                                    pkey = m.get("project_name") or m.get("key")
                                    if pkey not in by_project:
                                        by_project[pkey] = []
                                    by_project[pkey].append(m)
                                
                                for project_key, items in sorted(by_project.items()):
                                    direction = "unprotect" if items[0]["state_protected"] else "protect"
                                    with ui.card().classes("w-full p-3 mb-2"):
                                        with ui.row().classes("items-center gap-2 mb-2"):
                                            ui.icon("folder", size="sm").classes("text-blue-500")
                                            ui.label(project_key).classes("font-semibold")
                                            ui.badge(direction, color="amber")
                                        
                                        for m in items:
                                            state_status = "protected" if m["state_protected"] else "unprotected"
                                            yaml_status = "protected" if m["yaml_protected"] else "unprotected"
                                            with ui.row().classes("items-center gap-2 ml-4"):
                                                ui.badge(m["type"], color="grey").props("dense")
                                                ui.label(f"State: {state_status} → YAML: {yaml_status}").classes("text-sm")
                                
                                # AI Debug Summary section
                                ui.separator().classes("my-4")
                                with ui.expansion("AI Debug Summary", icon="smart_toy").classes("w-full"):
                                    # Build AI-friendly summary
                                    ai_summary_lines = [
                                        "# Protection Mismatch Summary",
                                        "",
                                        f"**Total mismatches**: {len(protection_mismatches)} resources in {len(by_project)} project(s)",
                                        "",
                                        "## Mismatches by Project",
                                    ]
                                    
                                    for project_key, items in sorted(by_project.items()):
                                        direction = "unprotect" if items[0]["state_protected"] else "protect"
                                        ai_summary_lines.append(f"\n### Project: `{project_key}` ({direction})")
                                        
                                        for m in items:
                                            state_status = "protected" if m["state_protected"] else "unprotected"
                                            yaml_status = "protected" if m["yaml_protected"] else "unprotected"
                                            # EXTENDED_RESOURCE_TYPE_MAP returns (terraform_resource, unprotected_block, protected_block)
                                            resource_tuple = EXTENDED_RESOURCE_TYPE_MAP.get(m["type"], ("unknown", "unknown", "unknown"))
                                            tf_resource, unprotected_block, protected_block = resource_tuple
                                            
                                            ai_summary_lines.append(f"- **{m['type']}** (`{m['key']}`): {state_status} → {yaml_status}")
                                            ai_summary_lines.append(f"  - Terraform resource: `{tf_resource}`")
                                            if direction == "unprotect":
                                                ai_summary_lines.append(f"  - Move from: `{protected_block}` → `{unprotected_block}`")
                                            else:
                                                ai_summary_lines.append(f"  - Move from: `{unprotected_block}` → `{protected_block}`")
                                    
                                    ai_summary_lines.extend([
                                        "",
                                        "## Required Actions",
                                        "Generate `moved` blocks to reconcile Terraform state with YAML configuration.",
                                        "",
                                        "## Protection Relationships",
                                        "- **PRJ** (Project): Independent - can be protected/unprotected on its own",
                                        "- **REP** (Repository) ↔ **PREP** (Project-Repository): Linked - must move together",
                                    ])
                                    
                                    ai_summary_text = "\n".join(ai_summary_lines)
                                    
                                    with ui.row().classes("w-full justify-end mb-2"):
                                        ui.button(
                                            "Copy to Clipboard",
                                            icon="content_copy",
                                            on_click=lambda: (
                                                ui.run_javascript(f'navigator.clipboard.writeText({repr(ai_summary_text)})'),
                                                ui.notify("Copied to clipboard!", type="positive"),
                                            ),
                                        ).props("flat dense")
                                    
                                    ui.markdown(ai_summary_text).classes("text-sm")
                                
                                ui.button("Close", on_click=detail_dialog.close).props("flat").classes("mt-4")
                        detail_dialog.open()
                    
                    ui.button(
                        "View Details",
                        icon="visibility",
                        on_click=show_protection_details,
                    ).props("outline").classes("text-amber-600")
                    
                    # Use persistent state for fix tracking (survives page re-renders)
                    # state.map.protection_fix_pending, protection_fix_file_path, protection_fix_previous_content
                    
                    def undo_all_protection_fixes(protect_btn, unprotect_btn, undo_btn, status_container):
                        """Restore the previous protection_moves.tf content."""
                        if not state.map.protection_fix_pending:
                            ui.notify("No pending fix to undo", type="warning")
                            return
                        
                        try:
                            file_path = Path(state.map.protection_fix_file_path)
                            previous = state.map.protection_fix_previous_content
                            
                            if previous:
                                file_path.write_text(previous)
                                ui.notify("Restored previous protection_moves.tf", type="positive")
                            else:
                                # No previous content - clear the file
                                file_path.write_text("# Protection moves cleared\n")
                                ui.notify("Cleared protection_moves.tf", type="positive")
                            
                            # Reset persistent state
                            state.map.protection_fix_pending = False
                            state.map.protection_fix_file_path = ""
                            state.map.protection_fix_previous_content = ""
                            state.map.protection_fix_action = ""
                            
                            # Restore protection sets from backup
                            if state.map.protection_fix_backup_protected:
                                state.map.protected_resources = set(state.map.protection_fix_backup_protected)
                            if state.map.protection_fix_backup_unprotected:
                                state.map.unprotected_keys = set(state.map.protection_fix_backup_unprotected)
                            state.map.protection_fix_backup_protected = set()
                            state.map.protection_fix_backup_unprotected = set()
                            
                            save_state()
                            
                            # Reset button states - enable both, reset colors and text
                            protect_btn.props(remove="disabled")
                            protect_btn.props("color=positive")
                            protect_btn.set_text(f"Protect All ({len(protection_mismatches)})")
                            protect_btn.set_icon("shield")
                            
                            unprotect_btn.props(remove="disabled")
                            unprotect_btn.props("color=warning")
                            unprotect_btn.set_text(f"Unprotect All ({len(protection_mismatches)})")
                            unprotect_btn.set_icon("shield_outlined")
                            
                            undo_btn.set_visibility(False)
                            
                            # Clear status container
                            status_container.clear()
                            
                        except Exception as e:
                            ui.notify(f"Error undoing fix: {e}", type="negative")
                    
                    def apply_protection_fix(action: str, protect_btn, unprotect_btn, undo_btn, status_container):
                        """Generate moved blocks for protection changes.
                        
                        Args:
                            action: Either 'protect' or 'unprotect'
                        """
                        from datetime import datetime
                        
                        # Resolve terraform directory
                        tf_dir = state.deploy.terraform_dir or "deployments/migration"
                        tf_path = Path(tf_dir)
                        if not tf_path.is_absolute():
                            project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                            tf_path = project_root / tf_dir
                        
                        if not tf_path.exists():
                            ui.notify(f"Terraform directory not found: {tf_path}", type="negative")
                            return
                        
                        moves_file = tf_path / "protection_moves.tf"
                        module_prefix = "module.dbt_cloud.module.projects_v2[0]"
                        
                        # Save previous content for undo in persistent state
                        previous_content = ""
                        if moves_file.exists():
                            previous_content = moves_file.read_text()
                        state.map.protection_fix_previous_content = previous_content
                        
                        # Filter mismatches based on action
                        # protect: resources that need moved blocks TO protected (state=unprotected)
                        # unprotect: resources that need moved blocks FROM protected (state=protected)
                        if action == "protect":
                            # For "protect": move unprotected → protected, or keep already-protected
                            # Only need moved blocks for resources currently NOT protected in state
                            target_mismatches = [m for m in protection_mismatches if not m["state_protected"]]
                            # Also handle resources that ARE protected in state but YAML says not protected
                            # These just need YAML updated, no moved blocks
                            yaml_only_updates = [m for m in protection_mismatches if m["state_protected"] and not m["yaml_protected"]]
                        else:  # unprotect
                            # For "unprotect": move protected → unprotected, or keep already-unprotected
                            # Only need moved blocks for resources currently protected in state
                            target_mismatches = [m for m in protection_mismatches if m["state_protected"]]
                            # Also handle resources that are NOT protected in state but YAML says protected
                            # These just need YAML updated, no moved blocks
                            yaml_only_updates = [m for m in protection_mismatches if not m["state_protected"] and m["yaml_protected"]]
                        
                        # Group mismatches by project
                        by_project: dict[str, list] = {}
                        for m in target_mismatches:
                            pkey = m.get("project_name") or m.get("key")
                            if pkey not in by_project:
                                by_project[pkey] = []
                            by_project[pkey].append(m)
                        
                        # Generate moved blocks
                        generated_moves: set[tuple[str, str]] = set()
                        blocks = []
                        block_count = 0
                        
                        for project_key, items in sorted(by_project.items()):
                            blocks.append(f"# {action.upper()} moves for {project_key}")
                            for m in items:
                                rtype = m["type"]
                                rkey = m["key"]
                                
                                if rtype in EXTENDED_RESOURCE_TYPE_MAP and (rtype, rkey) not in generated_moves:
                                    tf_type, unprotected, protected = EXTENDED_RESOURCE_TYPE_MAP[rtype]
                                    
                                    if action == "protect":
                                        from_block = unprotected
                                        to_block = protected
                                    else:
                                        from_block = protected
                                        to_block = unprotected
                                    
                                    blocks.append(f'''moved {{
  from = {module_prefix}.{tf_type}.{from_block}["{rkey}"]
  to   = {module_prefix}.{tf_type}.{to_block}["{rkey}"]
}}''')
                                    block_count += 1
                                    generated_moves.add((rtype, rkey))
                                    
                                    # REP and PREP are linked
                                    if rtype == "REP" and ("PREP", rkey) not in generated_moves:
                                        prep_tf_type, prep_unprotected, prep_protected = EXTENDED_RESOURCE_TYPE_MAP["PREP"]
                                        if action == "protect":
                                            prep_from, prep_to = prep_unprotected, prep_protected
                                        else:
                                            prep_from, prep_to = prep_protected, prep_unprotected
                                        blocks.append(f'''moved {{
  from = {module_prefix}.{prep_tf_type}.{prep_from}["{rkey}"]
  to   = {module_prefix}.{prep_tf_type}.{prep_to}["{rkey}"]
}}''')
                                        block_count += 1
                                        generated_moves.add(("PREP", rkey))
                            blocks.append("")
                        
                        action_label = "PROTECT" if action == "protect" else "UNPROTECT"
                        content = f'''# Generated moved blocks to {action_label} resources
# Action: {action_label}
# Generated: {datetime.now().isoformat()}
# Projects: {', '.join(sorted(by_project.keys())) if by_project else 'None (YAML-only updates)'}

''' + "\n".join(blocks)
                        
                        try:
                            moves_file.write_text(content)
                            
                            # Update persistent state
                            state.map.protection_fix_pending = True
                            state.map.protection_fix_file_path = str(moves_file)
                            state.map.protection_fix_action = action  # Track which action was taken
                            
                            # Backup current protection state for undo
                            state.map.protection_fix_backup_protected = set(state.map.protected_resources)
                            state.map.protection_fix_backup_unprotected = set(state.map.unprotected_keys)
                            
                            # Update YAML protection sets based on action
                            for m in protection_mismatches:
                                rkey = m["key"]
                                if action == "protect":
                                    # Add ALL mismatched resources to protected set
                                    state.map.protected_resources.add(rkey)
                                    state.map.unprotected_keys.discard(rkey)
                                else:  # unprotect
                                    # Remove ALL mismatched resources from protected set
                                    state.map.protected_resources.discard(rkey)
                                    state.map.unprotected_keys.add(rkey)
                            
                            save_state()
                            
                            # Update buttons to show success
                            protect_btn.props("disabled")
                            unprotect_btn.props("disabled")
                            if action == "protect":
                                protect_btn.props("color=positive")
                                protect_btn.set_text("Protection Queued")
                                protect_btn.set_icon("shield")
                            else:
                                unprotect_btn.props("color=positive")
                                unprotect_btn.set_text("Unprotection Queued")
                                unprotect_btn.set_icon("shield_outlined")
                            
                            # Show undo button
                            undo_btn.set_visibility(True)
                            
                            # Show pending status
                            with status_container:
                                status_container.clear()
                                color = "#ECFDF5" if action == "protect" else "#FEF3C7"
                                border_color = "#10B981" if action == "protect" else "#F59E0B"
                                text_color = "green" if action == "protect" else "amber"
                                icon_name = "shield" if action == "protect" else "shield_outlined"
                                
                                with ui.card().classes("w-full p-3 mt-3").style(f"background: {color}; border: 1px solid {border_color};"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon(icon_name, size="sm").classes(f"text-{text_color}-600")
                                        ui.label(f"PENDING {action_label}").classes(f"font-bold text-{text_color}-700")
                                    if block_count > 0:
                                        ui.label(f"Wrote {block_count} moved blocks to: {moves_file.name}").classes(f"text-sm text-{text_color}-700 mt-1")
                                    if yaml_only_updates:
                                        ui.label(f"Plus {len(yaml_only_updates)} YAML-only updates (no state change needed)").classes(f"text-sm text-{text_color}-700")
                                    ui.label("Run 'Generate Files' then 'terraform plan/apply' to complete").classes(f"text-xs text-{text_color}-600")
                            
                            ui.notify(f"SUCCESS: {action_label} queued for {len(protection_mismatches)} resource(s)", type="positive")
                        except Exception as e:
                            ui.notify(f"Error writing file: {e}", type="negative")
                    
                    def show_protect_confirmation():
                        """Show confirmation dialog before protecting resources."""
                        # Categorize what will happen
                        need_moved = [m for m in protection_mismatches if not m["state_protected"]]
                        need_yaml_only = [m for m in protection_mismatches if m["state_protected"] and not m["yaml_protected"]]
                        
                        with ui.dialog() as confirm_dialog, ui.card().style("width: 600px; max-width: 90vw;"):
                            ui.label("Confirm: PROTECT Resources").classes("text-xl font-bold text-green-700")
                            ui.separator()
                            
                            ui.markdown(f"""
This will **PROTECT** all {len(protection_mismatches)} mismatched resource(s):

- Resources will be in the **protected_*** Terraform collections
- YAML will have **`protected: true`** for these resources
- Protected resources cannot be destroyed without explicit unprotection
""").classes("text-sm")
                            
                            if need_moved:
                                ui.label(f"State Changes ({len(need_moved)} resources):").classes("font-semibold mt-3")
                                with ui.scroll_area().classes("max-h-32 w-full border rounded p-2"):
                                    for m in need_moved:
                                        tf_type, unprotected, protected = EXTENDED_RESOURCE_TYPE_MAP.get(m["type"], ("?", "?", "?"))
                                        ui.label(f"• {m['type']}:{m['key']} → {unprotected} → {protected}").classes("text-xs font-mono")
                            
                            if need_yaml_only:
                                ui.label(f"YAML-Only Updates ({len(need_yaml_only)} resources):").classes("font-semibold mt-3")
                                with ui.scroll_area().classes("max-h-32 w-full border rounded p-2"):
                                    for m in need_yaml_only:
                                        ui.label(f"• {m['type']}:{m['key']} (already protected in state, add to YAML)").classes("text-xs font-mono")
                            
                            ui.separator().classes("my-3")
                            
                            with ui.row().classes("w-full justify-end gap-2"):
                                ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                                ui.button(
                                    "Yes, Protect All",
                                    icon="shield",
                                    on_click=lambda: (
                                        confirm_dialog.close(),
                                        apply_protection_fix("protect", protect_btn, unprotect_btn, undo_btn, fix_status_container),
                                    ),
                                ).props("color=positive")
                        
                        confirm_dialog.open()
                    
                    def show_unprotect_confirmation():
                        """Show confirmation dialog before unprotecting resources."""
                        need_moved = [m for m in protection_mismatches if m["state_protected"]]
                        need_yaml_only = [m for m in protection_mismatches if not m["state_protected"] and m["yaml_protected"]]
                        
                        with ui.dialog() as confirm_dialog, ui.card().style("width: 600px; max-width: 90vw;"):
                            ui.label("Confirm: UNPROTECT Resources").classes("text-xl font-bold text-amber-700")
                            ui.separator()
                            
                            ui.markdown(f"""
This will **UNPROTECT** all {len(protection_mismatches)} mismatched resource(s):

- Resources will be in the **regular** Terraform collections (not protected_*)
- YAML will **NOT** have `protected: true` for these resources  
- ⚠️ **Warning**: Unprotected resources CAN be destroyed by Terraform
""").classes("text-sm")
                            
                            if need_moved:
                                ui.label(f"State Changes ({len(need_moved)} resources):").classes("font-semibold mt-3")
                                with ui.scroll_area().classes("max-h-32 w-full border rounded p-2"):
                                    for m in need_moved:
                                        tf_type, unprotected, protected = EXTENDED_RESOURCE_TYPE_MAP.get(m["type"], ("?", "?", "?"))
                                        ui.label(f"• {m['type']}:{m['key']} → {protected} → {unprotected}").classes("text-xs font-mono")
                            
                            if need_yaml_only:
                                ui.label(f"YAML-Only Updates ({len(need_yaml_only)} resources):").classes("font-semibold mt-3")
                                with ui.scroll_area().classes("max-h-32 w-full border rounded p-2"):
                                    for m in need_yaml_only:
                                        ui.label(f"• {m['type']}:{m['key']} (already unprotected in state, remove from YAML)").classes("text-xs font-mono")
                            
                            ui.separator().classes("my-3")
                            
                            with ui.row().classes("w-full justify-end gap-2"):
                                ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                                ui.button(
                                    "Yes, Unprotect All",
                                    icon="shield_outlined",
                                    on_click=lambda: (
                                        confirm_dialog.close(),
                                        apply_protection_fix("unprotect", protect_btn, unprotect_btn, undo_btn, fix_status_container),
                                    ),
                                ).props("color=warning")
                        
                        confirm_dialog.open()
                    
                    # Check if there's already a pending fix from persistent state
                    has_pending_fix = state.map.protection_fix_pending
                    pending_action = getattr(state.map, 'protection_fix_action', None)
                    
                    # Count resources by current state for button labels
                    can_protect = sum(1 for m in protection_mismatches if not m["state_protected"] or not m["yaml_protected"])
                    can_unprotect = sum(1 for m in protection_mismatches if m["state_protected"] or m["yaml_protected"])
                    
                    if has_pending_fix:
                        # Show which action was taken
                        if pending_action == "protect":
                            protect_btn = ui.button("Protection Queued", icon="shield").props("color=positive disabled")
                            unprotect_btn = ui.button(f"Unprotect All", icon="shield_outlined").props("color=grey disabled")
                        else:
                            protect_btn = ui.button(f"Protect All", icon="shield").props("color=grey disabled")
                            unprotect_btn = ui.button("Unprotection Queued", icon="shield_outlined").props("color=positive disabled")
                    else:
                        # Show both options
                        protect_btn = ui.button(
                            f"Protect All ({len(protection_mismatches)})",
                            icon="shield",
                            on_click=show_protect_confirmation,
                        ).props("color=positive")
                        
                        unprotect_btn = ui.button(
                            f"Unprotect All ({len(protection_mismatches)})",
                            icon="shield_outlined",
                            on_click=show_unprotect_confirmation,
                        ).props("color=warning")
                    
                    # Undo button - shown if there's a pending fix
                    undo_btn = ui.button(
                        "Undo",
                        icon="undo",
                        on_click=lambda: undo_all_protection_fixes(protect_btn, unprotect_btn, undo_btn, fix_status_container),
                    ).props("color=grey outline")
                    undo_btn.set_visibility(has_pending_fix)
                    
                    # Show pending status if there's already a fix queued
                    if has_pending_fix and state.map.protection_fix_file_path:
                        with fix_status_container:
                            action_label = "PROTECT" if pending_action == "protect" else "UNPROTECT"
                            color = "#ECFDF5" if pending_action == "protect" else "#FEF3C7"
                            border_color = "#10B981" if pending_action == "protect" else "#F59E0B"
                            text_color = "green" if pending_action == "protect" else "amber"
                            icon_name = "shield" if pending_action == "protect" else "shield_outlined"
                            
                            with ui.card().classes("w-full p-3 mt-3").style(f"background: {color}; border: 1px solid {border_color};"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon(icon_name, size="sm").classes(f"text-{text_color}-600")
                                    ui.label(f"PENDING {action_label}").classes(f"font-bold text-{text_color}-700")
                                moves_file_name = Path(state.map.protection_fix_file_path).name
                                ui.label(f"Moved blocks written to: {moves_file_name}").classes(f"text-sm text-{text_color}-700 mt-1")
                                ui.label("Run 'Generate Files' then 'terraform plan/apply' to complete").classes(f"text-xs text-{text_color}-600")
    
    # Save mapping file section (show if there are any confirmed or pending matches)
    has_matches = any(r.get("action") == "match" and r.get("target_id") for r in grid_row_data)
    confirmed_count = sum(1 for r in grid_row_data if r.get("status") == "confirmed")
    pending_match_count = sum(1 for r in grid_row_data if r.get("status") == "pending" and r.get("action") == "match" and r.get("target_id"))
    
    if has_matches:
        with ui.card().classes("w-full p-4 mt-4").style(f"border: 2px solid {DBT_TEAL};"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-1"):
                    ui.label("Save Mapping File").classes("font-semibold")
                    if confirmed_count > 0:
                        ui.label(
                            f"{confirmed_count} confirmed mappings"
                        ).classes("text-sm text-green-600")
                    if pending_match_count > 0:
                        ui.label(
                            f"{pending_match_count} pending matches (accept to include)"
                        ).classes("text-sm text-amber-600")
                    
                    if state.map.mapping_file_path:
                        ui.label(f"Last saved: {state.map.mapping_file_path}").classes("text-xs text-green-600 mt-1")
                
                def save_mappings():
                    try:
                        # Confidence types that represent automatic matching (not manual selection)
                        auto_match_types = {
                            "exact_match", "state_id_match", "url_match", "github_match", "env_match"
                        }
                        # Build confirmed mappings from grid data
                        mappings_to_save = []
                        for row in grid_data_ref["data"]:
                            if row.get("status") == "confirmed" and row.get("target_id"):
                                confidence = row.get("confidence", "manual")
                                mappings_to_save.append({
                                    "resource_type": row.get("source_type"),
                                    "source_name": row.get("source_name"),
                                    "source_key": row.get("source_key"),
                                    "target_id": row.get("target_id"),
                                    "target_name": row.get("target_name"),
                                    # Preserve the actual confidence type for better diagnostics
                                    "match_type": confidence if confidence in auto_match_types else "manual",
                                })
                        
                        if not mappings_to_save:
                            ui.notify("No confirmed mappings to save. Accept pending matches first.", type="warning")
                            return
                        
                        mapping = create_mapping_from_confirmations(
                            mappings_to_save,
                            state.source_account.account_id or "unknown",
                            state.target_account.account_id or "unknown",
                        )
                        
                        output_dir = Path(state.fetch.output_dir)
                        output_path = output_dir / "target_resource_mapping.yml"
                        
                        error = save_mapping_file(mapping, output_path)
                        if error:
                            ui.notify(f"Error saving: {error}", type="negative")
                        else:
                            state.map.mapping_file_path = str(output_path)
                            state.map.mapping_file_valid = True
                            state.map.confirmed_mappings = mappings_to_save
                            save_state()
                            ui.notify(f"Mapping saved to {output_path}", type="positive")
                            # Reload to update navigation button state
                            ui.navigate.reload()
                            
                    except Exception as e:
                        ui.notify(f"Error: {e}", type="negative")
                
                def view_mapping_file():
                    if state.map.mapping_file_path and Path(state.map.mapping_file_path).exists():
                        dialog = create_yaml_viewer_dialog(
                            state.map.mapping_file_path,
                            title="Target Resource Mapping"
                        )
                        dialog.open()
                    else:
                        ui.notify("Mapping file not found. Save the mapping first.", type="warning")
                
                with ui.row().classes("gap-2"):
                    save_btn = ui.button(
                        "Save Mapping File",
                        icon="save",
                        on_click=save_mappings,
                    ).style(f"background-color: {DBT_TEAL};")
                    
                    if confirmed_count == 0:
                        save_btn.disable()
                        save_btn.tooltip("Accept pending matches first")
                    
                    if state.map.mapping_file_path:
                        ui.button(
                            "View Mapping",
                            icon="visibility",
                            on_click=view_mapping_file,
                        ).props("outline")
    
    # Navigation section - placed inside _create_matching_content to access grid data
    _create_navigation_with_grid_data(
        state, 
        on_step_change, 
        save_state,
        confirmed_count=confirmed_count,
        has_unsaved_confirmed=confirmed_count > 0 and not state.map.mapping_file_valid,
    )


def _create_stat_card(label: str, value: int, color_class: str, icon_name: str) -> None:
    """Create a stat card."""
    with ui.card().classes("p-3 min-w-[120px]"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon_name, size="sm").classes(color_class)
            ui.label(str(value)).classes(f"text-2xl font-bold {color_class}")
        ui.label(label).classes("text-xs text-slate-500")


def _create_navigation_with_grid_data(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
    confirmed_count: int = 0,
    has_unsaved_confirmed: bool = False,
) -> None:
    """Create navigation buttons with grid-aware logic.
    
    Args:
        state: Application state
        on_step_change: Step change callback
        save_state: State save callback  
        confirmed_count: Number of confirmed mappings in current grid
        has_unsaved_confirmed: True if there are confirmed mappings that need saving
    """
    with ui.row().classes("w-full justify-between mt-4"):
        ui.button(
            f"Back to {state.get_step_label(WorkflowStep.EXPLORE_TARGET)}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.EXPLORE_TARGET),
        ).props("outline")
        
        # Show mapping status and continue button
        with ui.row().classes("items-center gap-4"):
            if state.map.mapping_file_valid and confirmed_count > 0:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("check_circle", size="sm").classes("text-green-500")
                    ui.label("Mapping saved").classes("text-green-600 text-sm")
            elif has_unsaved_confirmed:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning", size="sm").classes("text-amber-500")
                    ui.label("Save mapping file to continue").classes("text-amber-600 text-sm")
            
            # Allow continue if:
            # - Mapping file is saved and valid, OR
            # - There are no confirmed mappings that need saving (all create-new)
            continue_enabled = state.map.mapping_file_valid or not has_unsaved_confirmed
            
            def on_continue(unsaved=has_unsaved_confirmed):
                # Mark mapping as valid if we're allowing continue without saving
                # (this happens when all items are "Create New" - no matches to save)
                if not unsaved and not state.map.mapping_file_valid:
                    state.map.mapping_file_valid = True
                    save_state()
                on_step_change(WorkflowStep.CONFIGURE)
            
            btn = ui.button(
                f"Continue to {state.get_step_label(WorkflowStep.CONFIGURE)}",
                icon="arrow_forward",
                on_click=on_continue,
            ).style(f"background-color: {DBT_ORANGE};")
            
            if not continue_enabled:
                btn.disable()
