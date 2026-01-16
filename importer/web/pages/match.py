"""Match step page - match source resources to existing target resources."""

import json
import logging
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, STEP_NAMES
from importer.web.components.target_matcher import (
    MatchSuggestion,
    generate_match_suggestions,
)
from importer.web.components.selection_manager import SelectionManager
from importer.web.utils.mapping_file import (
    TargetResourceMapping,
    save_mapping_file,
    create_mapping_from_confirmations,
)
from importer.web.utils.yaml_viewer import create_yaml_viewer_dialog


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
        selected_source_count = len(source_items)
        
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
    )
    from importer.web.components.clone_dialog import show_clone_dialog
    from importer.web.state import CloneConfig
    
    # Build grid data from source/target items and existing mappings
    rejected_keys = state.map.rejected_suggestions if isinstance(state.map.rejected_suggestions, set) else set(state.map.rejected_suggestions)
    clone_configs = getattr(state.map, "cloned_resources", [])
    
    grid_row_data = build_grid_data(
        source_items,
        target_items,
        state.map.confirmed_mappings,
        rejected_keys,
        clone_configs,
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
        for row in grid_data_ref["data"]:
            if row.get("status") == "pending" and row.get("action") == "match" and row.get("target_id"):
                state.map.confirmed_mappings.append({
                    "resource_type": row.get("source_type"),
                    "source_name": row.get("source_name"),
                    "source_key": row.get("source_key"),
                    "target_id": row.get("target_id"),
                    "target_name": row.get("target_name"),
                    "match_type": "auto" if row.get("confidence") == "exact_match" else "manual",
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
    
    def on_row_change(row_data: dict):
        """Handle row data changes from the grid."""
        source_key = row_data.get("source_key")
        action = row_data.get("action")
        status = row_data.get("status")
        
        # Update grid data ref
        for i, row in enumerate(grid_data_ref["data"]):
            if row.get("source_key") == source_key:
                grid_data_ref["data"][i] = row_data
                break
        
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
        # Items with key=null use element_mapping_id as their key
        for s in source_items:
            item_key = s.get("key") or s.get("element_mapping_id", "")
            if item_key == source_key:
                return s
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
        
        # Regular resource - use standard detail dialog
        source_item = find_source_item(source_key)
        if source_item:
            from importer.web.components.entity_table import show_entity_detail_dialog
            show_entity_detail_dialog(source_item, state)
    
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
    
    # Info banner with Reset button
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
            
            # Reset All Mappings button - use flat with explicit color for dark mode
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
        )
    
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
                        # Build confirmed mappings from grid data
                        mappings_to_save = []
                        for row in grid_data_ref["data"]:
                            if row.get("status") == "confirmed" and row.get("target_id"):
                                mappings_to_save.append({
                                    "resource_type": row.get("source_type"),
                                    "source_name": row.get("source_name"),
                                    "source_key": row.get("source_key"),
                                    "target_id": row.get("target_id"),
                                    "target_name": row.get("target_name"),
                                    "match_type": "auto" if row.get("confidence") == "exact_match" else "manual",
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
