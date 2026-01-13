"""Map step page - select entities for migration and run normalization."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, STEP_NAMES
from importer.web.components.stepper import DBT_ORANGE
from importer.web.components.selection_manager import SelectionManager

# Resource type display info (reuse from entity_table)
RESOURCE_TYPES = {
    "ACC": {"name": "Account", "icon": "cloud", "color": "#3B82F6"},
    "CON": {"name": "Connection", "icon": "storage", "color": "#10B981"},
    "REP": {"name": "Repository", "icon": "source", "color": "#8B5CF6"},
    "TOK": {"name": "Service Token", "icon": "key", "color": "#EC4899"},
    "GRP": {"name": "Group", "icon": "group", "color": "#6366F1"},
    "NOT": {"name": "Notification", "icon": "notifications", "color": "#F97316"},
    "WEB": {"name": "Webhook", "icon": "webhook", "color": "#84CC16"},
    "PLE": {"name": "PrivateLink", "icon": "lock", "color": "#14B8A6"},
    "PRJ": {"name": "Project", "icon": "folder", "color": "#F59E0B"},
    "ENV": {"name": "Environment", "icon": "layers", "color": "#06B6D4"},
    "VAR": {"name": "Env Variable", "icon": "code", "color": "#A855F7"},
    "JOB": {"name": "Job", "icon": "schedule", "color": "#EF4444"},
}


def create_mapping_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Map step page."""
    
    # Main container
    with ui.element("div").classes("w-full max-w-7xl mx-auto p-4").style(
        "display: grid; "
        "grid-template-rows: auto 1fr auto; "
        "height: calc(100vh - 100px); "
        "gap: 8px; "
        "overflow: hidden;"
    ):
        # Row 1: Header
        _create_header(state)
        
        # Check if data is available
        if not state.fetch.fetch_complete:
            _create_no_data_message(on_step_change)
            return
        
        # Load report items
        report_items = _load_report_items(state)
        if not report_items:
            _create_no_data_message(on_step_change)
            return
        
        # Initialize selection manager
        selection_manager = SelectionManager(
            account_id=state.source_account.account_id or "unknown",
            base_url=state.source_account.host_url,
        )
        selection_manager.load()
        
        # Reconcile selections with current entities
        reconcile_result = selection_manager.reconcile_with_entities(report_items)
        
        # Update state counts
        counts = selection_manager.get_selection_counts()
        state.map.selection_counts = counts
        
        # Row 2: Main content (split into selection panel and results panel)
        # Ref for summary refresh callback
        summary_refresh_ref = {"refresh": None}
        
        with ui.element("div").style(
            "display: grid; "
            "grid-template-columns: 1fr 350px; "
            "gap: 16px; "
            "overflow: hidden; "
            "min-height: 0;"
        ):
            # Left: Entity selection
            _create_selection_panel(report_items, selection_manager, state, save_state, summary_refresh_ref)
            
            # Right: Results/action panel
            _create_action_panel(state, selection_manager, report_items, on_step_change, save_state, summary_refresh_ref)
        
        # Row 3: Navigation
        _create_navigation(state, on_step_change)


def _create_header(state: AppState) -> None:
    """Create the page header."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-1"):
                ui.label("Map Entities for Migration").classes("text-2xl font-bold")
                ui.label(
                    "Select which entities to include in the Terraform configuration"
                ).classes("text-slate-600 dark:text-slate-400")
            
            if state.fetch.account_name:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("cloud", size="sm").classes("text-slate-500")
                    ui.label(state.fetch.account_name).classes("font-medium")


def _create_no_data_message(on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Show message when no fetch data is available."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("warning", size="3rem").classes("text-amber-500 mx-auto")
        ui.label("No Data Available").classes("text-xl font-bold mt-4")
        ui.label("Complete the Fetch step first to map entities.").classes(
            "text-slate-600 dark:text-slate-400 mt-2"
        )
        ui.button(
            f"Go to {STEP_NAMES[WorkflowStep.FETCH]}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.FETCH),
        ).classes("mt-4")


def _load_report_items(state: AppState) -> list:
    """Load report items from the last fetch."""
    if not state.fetch.last_report_items_file:
        return []
    
    try:
        path = Path(state.fetch.last_report_items_file)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        pass
    
    return []


def _create_selection_panel(
    report_items: list,
    selection_manager: SelectionManager,
    state: AppState,
    save_state: Callable[[], None],
    summary_refresh_ref: dict,
) -> None:
    """Create the entity selection panel with table and controls."""
    
    with ui.card().classes("w-full h-full p-4").style("overflow: hidden; display: flex; flex-direction: column;"):
        # Track UI refs
        grid_ref = {"grid": None}
        count_ref = {"label": None}
        # Initialize from persisted state
        filter_ref = {
            "type": state.map.type_filter,
            "selected_only": state.map.selected_only_filter
        }
        show_selected_btn_ref = {"button": None}
        type_select_ref = {"select": None}
        # Flag to prevent circular updates
        programmatic_update = {"active": False}
        
        def update_count_display():
            """Update the selection count display."""
            counts = selection_manager.get_selection_counts()
            state.map.selection_counts = counts
            if count_ref["label"]:
                count_ref["label"].set_text(f"{counts['selected']} of {counts['total']} selected")
            # Also refresh the summary panel
            if summary_refresh_ref.get("refresh"):
                summary_refresh_ref["refresh"]()
        
        def get_visible_ids() -> set:
            """Get IDs of currently visible (filtered) entities."""
            filter_type = filter_ref["type"]
            if filter_type == "all":
                return {e.get("element_mapping_id") for e in report_items if e.get("element_mapping_id")}
            return {
                e.get("element_mapping_id") 
                for e in report_items 
                if e.get("element_type_code") == filter_type and e.get("element_mapping_id")
            }
        
        async def on_select_all():
            visible_ids = get_visible_ids()
            selection_manager.select_all(visible_ids)
            update_count_display()
            if grid_ref["grid"]:
                programmatic_update["active"] = True
                # If "selected only" filter is active, refresh the filtered view
                if filter_ref.get("selected_only") and filter_ref.get("refresh_grid"):
                    filter_ref["refresh_grid"]()
                else:
                    await _refresh_grid_selections(grid_ref["grid"], selection_manager, True)
                programmatic_update["active"] = False
        
        async def on_deselect_all():
            visible_ids = get_visible_ids()
            selection_manager.deselect_all(visible_ids)
            update_count_display()
            if grid_ref["grid"]:
                programmatic_update["active"] = True
                # If "selected only" filter is active, refresh the filtered view
                if filter_ref.get("selected_only") and filter_ref.get("refresh_grid"):
                    filter_ref["refresh_grid"]()
                else:
                    await _refresh_grid_selections(grid_ref["grid"], selection_manager, False)
                programmatic_update["active"] = False
        
        async def on_invert():
            visible_ids = get_visible_ids()
            selection_manager.invert_selection(visible_ids)
            update_count_display()
            if grid_ref["grid"]:
                programmatic_update["active"] = True
                # If "selected only" filter is active, refresh the filtered view
                if filter_ref.get("selected_only") and filter_ref.get("refresh_grid"):
                    filter_ref["refresh_grid"]()
                else:
                    await _refresh_grid_selections(grid_ref["grid"], selection_manager, None)
                programmatic_update["active"] = False
        
        # Header row with controls
        with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap mb-2"):
            # Type filter
            types_in_data = sorted(
                set(item.get("element_type_code", "UNK") for item in report_items)
            )
            type_options = {"all": "All Types"} | {
                t: f"{RESOURCE_TYPES.get(t, {}).get('name', t)}" 
                for t in types_in_data
            }
            
            async def on_type_change(e):
                filter_ref["type"] = e.value
                # Persist to state
                state.map.type_filter = e.value
                save_state()
                if grid_ref["grid"]:
                    filtered = _get_filtered_items(report_items, e.value)
                    # Apply selected_only filter if active
                    if filter_ref["selected_only"]:
                        filtered = [r for r in filtered if selection_manager.is_selected(r.get("element_mapping_id"))]
                    grid_ref["grid"].options["rowData"] = _add_selection_column(filtered, selection_manager)
                    grid_ref["grid"].update()
            
            type_select_ref["select"] = ui.select(
                options=type_options,
                value=filter_ref["type"],  # Use persisted value
                on_change=on_type_change,
            ).props("outlined dense").classes("min-w-[150px]")
            
            # Selection controls
            with ui.row().classes("gap-2"):
                ui.button("Select All", icon="check_box", on_click=on_select_all).props("outline dense")
                ui.button("Deselect All", icon="check_box_outline_blank", on_click=on_deselect_all).props("outline dense")
                ui.button("Invert", icon="flip", on_click=on_invert).props("outline dense")
                
                # Toggle to show only selected
                def refresh_grid_with_filters():
                    """Refresh grid respecting current filter settings."""
                    if grid_ref["grid"]:
                        # Get items based on type filter first
                        filtered = _get_filtered_items(report_items, filter_ref["type"])
                        # Then filter by selected if toggle is on
                        if filter_ref["selected_only"]:
                            filtered = [r for r in filtered if selection_manager.is_selected(r.get("element_mapping_id"))]
                        grid_ref["grid"].options["rowData"] = _add_selection_column(filtered, selection_manager)
                        grid_ref["grid"].update()
                
                def toggle_selected_only():
                    filter_ref["selected_only"] = not filter_ref["selected_only"]
                    # Persist to state
                    state.map.selected_only_filter = filter_ref["selected_only"]
                    save_state()
                    refresh_grid_with_filters()
                    # Update button appearance
                    _update_selected_only_button_style()
                
                def _update_selected_only_button_style():
                    if show_selected_btn_ref["button"]:
                        if filter_ref["selected_only"]:
                            show_selected_btn_ref["button"].props(remove="outline")
                            show_selected_btn_ref["button"].style(f"background-color: {DBT_ORANGE};")
                        else:
                            show_selected_btn_ref["button"].props("outline")
                            show_selected_btn_ref["button"].style("background-color: transparent;")
                
                # Store refresh function for use by select all/deselect all
                filter_ref["refresh_grid"] = refresh_grid_with_filters
                
                # Create button with initial state from persistence
                if filter_ref["selected_only"]:
                    show_selected_btn_ref["button"] = ui.button(
                        "Selected Only", 
                        icon="filter_list", 
                        on_click=toggle_selected_only
                    ).props("dense").style(f"background-color: {DBT_ORANGE};")
                else:
                    show_selected_btn_ref["button"] = ui.button(
                        "Selected Only", 
                        icon="filter_list", 
                        on_click=toggle_selected_only
                    ).props("outline dense")
            
            # Count display
            counts = selection_manager.get_selection_counts()
            count_ref["label"] = ui.label(f"{counts['selected']} of {counts['total']} selected").classes(
                "text-sm font-medium"
            )
        
        # Entity table with checkboxes
        with ui.element("div").classes("w-full flex-1").style("overflow: hidden; min-height: 200px;"):
            _create_selection_grid(report_items, selection_manager, grid_ref, count_ref, state, programmatic_update, summary_refresh_ref, filter_ref)


def _get_filtered_items(report_items: list, type_filter: str) -> list:
    """Filter report items by type."""
    if type_filter == "all":
        return report_items
    return [r for r in report_items if r.get("element_type_code") == type_filter]


def _add_selection_column(items: list, selection_manager: SelectionManager) -> list:
    """Add selection state to items for grid display."""
    result = []
    for item in items:
        item_copy = dict(item)
        mapping_id = item.get("element_mapping_id")
        item_copy["_selected"] = selection_manager.is_selected(mapping_id) if mapping_id else True
        result.append(item_copy)
    return result


async def _refresh_grid_selections(grid, selection_manager: SelectionManager, select_all: Optional[bool]) -> None:
    """Refresh the visual state of checkboxes in the grid by updating row data.
    
    Args:
        grid: The AG Grid component
        selection_manager: The selection manager instance
        select_all: Not used - we update based on SelectionManager state
    """
    try:
        # Update _selected field in row data based on SelectionManager
        row_data = grid.options.get("rowData", [])
        for row in row_data:
            mapping_id = row.get("element_mapping_id")
            if mapping_id:
                row["_selected"] = selection_manager.is_selected(mapping_id)
        
        # Trigger grid update to reflect changes
        grid.update()
    except Exception as e:
        print(f"Error refreshing grid selections: {e}")


def _create_selection_grid(
    report_items: list,
    selection_manager: SelectionManager,
    grid_ref: dict,
    count_ref: dict,
    state: AppState,
    programmatic_update: dict,
    summary_refresh_ref: dict,
    filter_ref: dict,
) -> None:
    """Create the AG Grid with selection checkboxes."""
    
    # Apply initial filters from persisted state
    filtered_items = _get_filtered_items(report_items, filter_ref.get("type", "all"))
    if filter_ref.get("selected_only", False):
        filtered_items = [r for r in filtered_items if selection_manager.is_selected(r.get("element_mapping_id"))]
    
    # Prepare data with selection column
    row_data = _add_selection_column(filtered_items, selection_manager)
    
    # Column definitions - use _selected as a visible checkbox indicator
    column_defs = [
        {
            "field": "_selected",
            "colId": "_selected",
            "headerName": "✓",
            "width": 50,
            "pinned": "left",
            "cellRenderer": "agCheckboxCellRenderer",  # Use AG Grid's checkbox renderer
            "editable": True,  # Make it editable to allow clicking
            "cellStyle": {"textAlign": "center"},
        },
        {
            "field": "element_type_code",
            "colId": "element_type_code", 
            "headerName": "Type",
            "width": 80,
            "pinned": "left",
        },
        {
            "field": "name",
            "colId": "name",
            "headerName": "Name",
            "width": 250,
            "filter": "agTextColumnFilter",
        },
        {
            "field": "project_name",
            "colId": "project_name",
            "headerName": "Project",
            "width": 180,
            "filter": "agTextColumnFilter",
        },
        {
            "field": "key",
            "colId": "key",
            "headerName": "Key",
            "width": 200,
        },
        {
            "field": "element_mapping_id",
            "colId": "element_mapping_id",
            "headerName": "Mapping ID",
            "width": 140,
        },
    ]
    
    grid = ui.aggrid({
        "columnDefs": column_defs,
        "rowData": row_data,
        "pagination": True,
        "paginationPageSize": 50,
        "paginationPageSizeSelector": [25, 50, 100, 200],
        "headerHeight": 36,
        "defaultColDef": {
            "resizable": True,
            "sortable": True,
            "filter": True,
        },
        "stopEditingWhenCellsLoseFocus": True,
    }, theme="balham").classes("w-full h-full")
    
    grid_ref["grid"] = grid
    
    # Handle cell value changes (when checkbox is toggled)
    def on_cell_value_changed(e):
        """Handle when a cell value changes (checkbox toggled)."""
        if programmatic_update.get("active", False):
            return
            
        try:
            if e.args and e.args.get("colId") == "_selected":
                row_data_item = e.args.get("data", {})
                mapping_id = row_data_item.get("element_mapping_id")
                new_value = e.args.get("newValue", False)
                
                if mapping_id:
                    selection_manager.set_selected(mapping_id, new_value)
                    
                    # Update count display
                    counts = selection_manager.get_selection_counts()
                    state.map.selection_counts = counts
                    if count_ref["label"]:
                        count_ref["label"].set_text(f"{counts['selected']} of {counts['total']} selected")
                    
                    # Refresh summary panel
                    if summary_refresh_ref.get("refresh"):
                        summary_refresh_ref["refresh"]()
        except Exception as ex:
            print(f"Cell value change error: {ex}")
    
    grid.on("cellValueChanged", on_cell_value_changed)


def _create_action_panel(
    state: AppState,
    selection_manager: SelectionManager,
    report_items: list,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
    summary_refresh_ref: dict,
) -> None:
    """Create the right-side action panel with normalize button and results."""
    
    with ui.card().classes("w-full h-full p-4").style("overflow-y: auto;"):
        # Selection summary
        ui.label("Selection Summary").classes("text-lg font-bold mb-2")
        
        summary_container = ui.column().classes("w-full gap-2 mb-4")
        
        # Create a refreshable summary
        @ui.refreshable
        def refreshable_summary():
            counts = selection_manager.get_selection_counts()
            _create_summary_stats(counts, report_items, selection_manager)
        
        with summary_container:
            refreshable_summary()
        
        # Store the refresh function so it can be called from elsewhere
        summary_refresh_ref["refresh"] = refreshable_summary.refresh
        
        ui.separator()
        
        # Normalize section
        ui.label("Generate Configuration").classes("text-lg font-bold mt-4 mb-2")
        ui.label(
            "Run normalization to generate Terraform-ready YAML from selected entities."
        ).classes("text-sm text-slate-600 dark:text-slate-400 mb-4")
        
        # Progress/status area
        status_container = ui.column().classes("w-full gap-2 mb-4")
        
        # Normalize button
        async def on_normalize():
            await _run_normalize(state, selection_manager, status_container, save_state)
        
        normalize_btn = ui.button(
            "Normalize Selected Entities",
            icon="transform",
            on_click=on_normalize,
        ).style(f"background-color: {DBT_ORANGE};").classes("w-full")
        
        # Results section (shown after normalize)
        results_container = ui.column().classes("w-full gap-2 mt-4")
        
        with results_container:
            if state.map.normalize_complete and state.map.last_yaml_file:
                _create_results_display(state, on_step_change)


def _create_summary_stats(counts: dict, report_items: list, selection_manager: SelectionManager) -> None:
    """Create summary statistics display."""
    
    # Overall count
    with ui.row().classes("w-full justify-between items-center"):
        ui.label("Total Selected").classes("text-sm")
        ui.label(f"{counts['selected']} / {counts['total']}").classes("font-bold")
    
    # Progress bar
    if counts['total'] > 0:
        pct = (counts['selected'] / counts['total']) * 100
        ui.linear_progress(value=pct/100).classes("w-full")
    
    # By type breakdown - use report_items to get type info
    ui.label("By Type:").classes("text-sm font-medium mt-2")
    
    # Count by type using report items
    type_counts = {}
    for item in report_items:
        type_code = item.get("element_type_code", "UNK")
        mapping_id = item.get("element_mapping_id")
        
        if type_code not in type_counts:
            type_counts[type_code] = {"selected": 0, "total": 0}
        type_counts[type_code]["total"] += 1
        
        if mapping_id and selection_manager.is_selected(mapping_id):
            type_counts[type_code]["selected"] += 1
    
    for type_code in sorted(type_counts.keys()):
        tc = type_counts[type_code]
        type_info = RESOURCE_TYPES.get(type_code, {"name": type_code, "icon": "help", "color": "#6B7280"})
        with ui.row().classes("w-full justify-between items-center"):
            with ui.row().classes("items-center gap-1"):
                ui.icon(type_info["icon"], size="xs").style(f"color: {type_info['color']};")
                ui.label(type_info["name"]).classes("text-xs")
            ui.label(f"{tc['selected']}/{tc['total']}").classes("text-xs font-medium")


async def _run_normalize(
    state: AppState,
    selection_manager: SelectionManager,
    status_container,
    save_state: Callable[[], None],
) -> None:
    """Run the normalization process."""
    
    # Clear status container
    status_container.clear()
    
    with status_container:
        ui.label("Normalizing...").classes("text-sm font-medium")
        spinner = ui.spinner(size="sm")
    
    state.map.normalize_running = True
    state.map.normalize_error = None
    
    try:
        # Run normalize in background thread
        result = await asyncio.to_thread(
            _do_normalize,
            state.fetch.last_fetch_file,
            selection_manager.get_deselected_ids(),
            state.fetch.output_dir,
        )
        
        # Update state with results
        state.map.normalize_complete = True
        state.map.last_yaml_file = result.get("yaml_file")
        state.map.last_lookups_file = result.get("lookups_file")
        state.map.last_exclusions_file = result.get("exclusions_file")
        state.map.lookups_count = result.get("lookups_count", 0)
        state.map.exclusions_count = result.get("exclusions_count", 0)
        
        save_state()
        
        # Update status
        status_container.clear()
        with status_container:
            ui.icon("check_circle", size="sm").classes("text-green-500")
            ui.label("Normalization complete!").classes("text-sm text-green-600")
        
        # Show results
        ui.notify("Normalization complete!", type="positive")
        
        # Trigger page refresh to show results
        ui.navigate.reload()
        
    except Exception as e:
        state.map.normalize_error = str(e)
        status_container.clear()
        with status_container:
            ui.icon("error", size="sm").classes("text-red-500")
            ui.label(f"Error: {e}").classes("text-sm text-red-600")
        ui.notify(f"Normalization failed: {e}", type="negative")
    
    finally:
        state.map.normalize_running = False


def _do_normalize(
    input_file: str,
    exclude_ids: set,
    output_dir: str,
) -> dict:
    """Perform the actual normalization (runs in background thread)."""
    import yaml
    from pathlib import Path
    
    from importer.models import AccountSnapshot
    from importer.normalizer import MappingConfig, NormalizationContext
    from importer.normalizer.core import normalize_snapshot
    from importer.normalizer.writer import YAMLWriter
    from importer.norm_tracker import NormalizationRunTracker
    
    # Load snapshot
    input_path = Path(input_file)
    snapshot_data = json.loads(input_path.read_text(encoding="utf-8"))
    
    # Get metadata
    metadata = snapshot_data.get("_metadata", {})
    account_id = metadata.get("account_id") or snapshot_data.get("account_id", 0)
    fetch_run_id = metadata.get("run_id", 0)
    
    # Reconstruct snapshot
    snapshot = AccountSnapshot(**snapshot_data)
    
    # Create mapping config with exclusions
    config_data = {
        "version": 1,
        "scope": {"mode": "all_projects"},
        "resource_filters": {},
        "normalization_options": {
            "strip_source_ids": True,
            "secret_handling": "redact",
        },
    }
    
    # Add exclude_ids to resource filters
    if exclude_ids:
        # Group exclude IDs by resource type
        exclude_by_type = {}
        for eid in exclude_ids:
            if "-" in eid:
                type_code = eid.split("-")[0]
                # Map type code to resource filter name
                type_to_filter = {
                    "CON": "connections",
                    "REP": "repositories", 
                    "TOK": "service_tokens",
                    "GRP": "groups",
                    "NOT": "notifications",
                    "WEB": "webhooks",
                    "PLE": "privatelink_endpoints",
                    "PRJ": "projects",
                    "ENV": "environments",
                    "JOB": "jobs",
                    "VAR": "environment_variables",
                }
                filter_name = type_to_filter.get(type_code)
                if filter_name:
                    if filter_name not in exclude_by_type:
                        exclude_by_type[filter_name] = []
                    exclude_by_type[filter_name].append(eid)
        
        for filter_name, ids in exclude_by_type.items():
            config_data["resource_filters"][filter_name] = {"exclude_ids": ids}
    
    config = MappingConfig(**config_data)
    
    # Initialize tracking
    norm_output_dir = Path(output_dir)
    norm_tracker = NormalizationRunTracker(norm_output_dir / "normalization_runs.json")
    norm_run_id, timestamp = norm_tracker.start_run(account_id, fetch_run_id)
    
    # Initialize context
    context = NormalizationContext(config)
    
    # Normalize
    normalized_data = normalize_snapshot(snapshot, config, context)
    
    # Write artifacts
    writer = YAMLWriter(config, context)
    artifacts = writer.write_all_artifacts(
        normalized_data,
        norm_output_dir,
        norm_run_id,
        timestamp,
        account_id,
    )
    
    return {
        "yaml_file": str(artifacts.get("yaml")),
        "lookups_file": str(artifacts.get("lookups")) if artifacts.get("lookups") else None,
        "exclusions_file": str(artifacts.get("exclusions")) if artifacts.get("exclusions") else None,
        "lookups_count": len(context.placeholders),
        "exclusions_count": len(context.exclusions),
    }


def _create_results_display(state: AppState, on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Create the results display after normalization."""
    
    ui.separator()
    ui.label("Results").classes("text-lg font-bold mt-4 mb-2")
    
    # YAML file
    if state.map.last_yaml_file:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("description", size="sm").classes("text-green-500")
            ui.label("YAML Config:").classes("text-sm font-medium")
        
        yaml_path = Path(state.map.last_yaml_file)
        ui.label(yaml_path.name).classes("text-xs text-slate-500 ml-6")
        
        if yaml_path.exists():
            size_kb = yaml_path.stat().st_size / 1024
            ui.label(f"({size_kb:.1f} KB)").classes("text-xs text-slate-400 ml-6")
    
    # Lookups count
    if state.map.lookups_count > 0:
        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.icon("warning", size="sm").classes("text-amber-500")
            ui.label(f"{state.map.lookups_count} LOOKUP placeholders").classes("text-sm")
        ui.label("Need manual resolution before deploy").classes("text-xs text-slate-500 ml-6")
    
    # Exclusions count
    if state.map.exclusions_count > 0:
        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.icon("info", size="sm").classes("text-blue-500")
            ui.label(f"{state.map.exclusions_count} resources excluded").classes("text-sm")
    
    # Continue button
    ui.button(
        f"Continue to {STEP_NAMES[WorkflowStep.TARGET]}",
        icon="arrow_forward",
        on_click=lambda: on_step_change(WorkflowStep.TARGET),
    ).style(f"background-color: {DBT_ORANGE};").classes("w-full mt-4")


def _create_navigation(state: AppState, on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Create navigation buttons."""
    with ui.row().classes("w-full justify-between mt-4"):
        ui.button(
            f"Back to {STEP_NAMES[WorkflowStep.EXPLORE]}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.EXPLORE),
        ).props("outline")
        
        if state.map.normalize_complete:
            ui.button(
                f"Continue to {STEP_NAMES[WorkflowStep.TARGET]}",
                icon="arrow_forward",
                on_click=lambda: on_step_change(WorkflowStep.TARGET),
            ).style(f"background-color: {DBT_ORANGE};")
