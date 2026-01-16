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
        source_items = _load_report_items(state, target=False)
        target_items = _load_report_items(state, target=True)
        
        if not source_items:
            _create_no_data_message("No source data available", on_step_change)
            return
        
        if not target_items:
            _create_no_data_message("No target data available", on_step_change)
            return
        
        # Row 2: Main content
        with ui.element("div").style(
            "width: 100%; height: 100%; overflow: auto;"
        ):
            _create_matching_content(state, source_items, target_items, save_state)
        
        # Row 3: Navigation
        _create_navigation(state, on_step_change, save_state)


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
) -> None:
    """Create the main matching interface with editable grid."""
    from importer.web.components.match_grid import (
        build_grid_data,
        create_match_grid,
        create_grid_toolbar,
        export_mappings_to_csv,
    )
    
    # Build grid data from source/target items and existing mappings
    rejected_keys = state.map.rejected_suggestions if isinstance(state.map.rejected_suggestions, set) else set(state.map.rejected_suggestions)
    grid_row_data = build_grid_data(
        source_items,
        target_items,
        state.map.confirmed_mappings,
        rejected_keys,
    )
    
    # Stats from grid data
    pending = sum(1 for r in grid_row_data if r.get("status") == "pending" and r.get("action") == "match")
    confirmed = sum(1 for r in grid_row_data if r.get("status") == "confirmed")
    create_new = sum(1 for r in grid_row_data if r.get("action") == "create_new")
    skipped = sum(1 for r in grid_row_data if r.get("action") == "skip")
    
    with ui.row().classes("w-full gap-4 mb-4"):
        _create_stat_card("Pending", pending, "text-amber-600", "hourglass_empty")
        _create_stat_card("Confirmed", confirmed, "text-green-600", "check_circle")
        _create_stat_card("Create New", create_new, "text-orange-500", "add_circle")
        _create_stat_card("Skip", skipped, "text-slate-500", "block")
        _create_stat_card("Source Items", len(source_items), "text-blue-600", "upload")
        _create_stat_card("Target Items", len(target_items), f"color: {DBT_TEAL}", "download")
    
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
    
    def on_view_details(source_key: str):
        """View details for a resource."""
        # Find the source item
        source_item = next((s for s in source_items if s.get("key") == source_key), None)
        if source_item:
            from importer.web.components.entity_table import show_entity_detail_dialog
            show_entity_detail_dialog(source_item, state)
    
    # Info banner with Reset button
    with ui.card().classes("w-full p-3 mb-4").style(f"border-left: 4px solid {DBT_TEAL};"):
        with ui.row().classes("w-full items-start justify-between"):
            with ui.row().classes("items-start gap-2"):
                ui.icon("info", size="sm").style(f"color: {DBT_TEAL};")
                with ui.column().classes("gap-1"):
                    ui.label("How Matching Works").classes("font-semibold text-sm")
                    ui.label(
                        "Resources are auto-matched by exact name. Edit Action to change behavior: "
                        "Match = import existing, Create New = create fresh, Skip = exclude from migration."
                    ).classes("text-xs text-slate-500")
            
            # Reset All Mappings button
            ui.button(
                "Reset All Mappings",
                icon="refresh",
                on_click=reset_all_mappings,
            ).props("outline color=negative size=sm").tooltip(
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
    
    # Main grid in a card
    with ui.card().classes("w-full p-4").style("height: 400px;"):
        grid, _ = create_match_grid(
            source_items,
            target_items,
            state.map.confirmed_mappings,
            rejected_keys,
            on_row_change=on_row_change,
            on_accept=on_accept,
            on_reject=on_reject,
            on_view_details=on_view_details,
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


def _create_stat_card(label: str, value: int, color_class: str, icon_name: str) -> None:
    """Create a stat card."""
    with ui.card().classes("p-3 min-w-[120px]"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon_name, size="sm").classes(color_class)
            ui.label(str(value)).classes(f"text-2xl font-bold {color_class}")
        ui.label(label).classes("text-xs text-slate-500")


def _create_navigation(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create navigation buttons."""
    with ui.row().classes("w-full justify-between mt-4"):
        ui.button(
            f"Back to {state.get_step_label(WorkflowStep.EXPLORE_TARGET)}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.EXPLORE_TARGET),
        ).props("outline")
        
        # Show mapping status and continue button
        with ui.row().classes("items-center gap-4"):
            if state.map.mapping_file_valid:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("check_circle", size="sm").classes("text-green-500")
                    ui.label("Mapping saved").classes("text-green-600 text-sm")
            elif state.map.confirmed_mappings:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning", size="sm").classes("text-amber-500")
                    ui.label("Save mapping file to continue").classes("text-amber-600 text-sm")
            
            continue_enabled = state.map.mapping_file_valid or not state.map.confirmed_mappings
            
            btn = ui.button(
                f"Continue to {state.get_step_label(WorkflowStep.CONFIGURE)}",
                icon="arrow_forward",
                on_click=lambda: on_step_change(WorkflowStep.CONFIGURE),
            ).style(f"background-color: {DBT_ORANGE};")
            
            if not continue_enabled:
                btn.disable()
