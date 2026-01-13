"""Entity table component with AGGrid."""

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, List, Dict, Any

from nicegui import ui

from importer.web.state import AppState
from importer.web.components.stepper import DBT_ORANGE


def _load_full_data_for_type(state: AppState, type_code: str) -> List[Dict[str, Any]]:
    """Load full data from the JSON snapshot for a specific entity type.
    
    This provides ALL fields from the API, not just the simplified report_items.
    """
    if not state.fetch.last_fetch_file:
        return []
    
    json_path = Path(state.fetch.last_fetch_file)
    if not json_path.exists():
        return []
    
    try:
        snapshot = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []
    
    results = []
    globals_block = snapshot.get("globals", {})
    
    # Map type codes to data extraction logic
    if type_code == "ACC":
        # Account is the root level
        account_data = {k: v for k, v in snapshot.items() if k not in ("globals", "projects")}
        results.append(account_data)
    
    elif type_code == "CON":
        for key, conn in globals_block.get("connections", {}).items():
            conn["_key"] = key
            results.append(conn)
    
    elif type_code == "REP":
        for key, repo in globals_block.get("repositories", {}).items():
            repo["_key"] = key
            results.append(repo)
    
    elif type_code == "TOK":
        for key, token in globals_block.get("service_tokens", {}).items():
            token["_key"] = key
            results.append(token)
    
    elif type_code == "GRP":
        for key, group in globals_block.get("groups", {}).items():
            group["_key"] = key
            results.append(group)
    
    elif type_code == "NOT":
        for key, notif in globals_block.get("notifications", {}).items():
            notif["_key"] = key
            results.append(notif)
    
    elif type_code == "WEB":
        for key, webhook in globals_block.get("webhooks", {}).items():
            webhook["_key"] = key
            results.append(webhook)
    
    elif type_code == "PLE":
        for key, endpoint in globals_block.get("privatelink_endpoints", {}).items():
            endpoint["_key"] = key
            results.append(endpoint)
    
    elif type_code == "PRJ":
        for project in snapshot.get("projects", []):
            # Exclude nested arrays for cleaner export
            proj_data = {k: v for k, v in project.items() 
                        if k not in ("environments", "jobs", "environment_variables")}
            proj_data["environment_count"] = len(project.get("environments", []))
            proj_data["job_count"] = len(project.get("jobs", []))
            proj_data["env_var_count"] = len(project.get("environment_variables", []))
            results.append(proj_data)
    
    elif type_code == "ENV":
        for project in snapshot.get("projects", []):
            project_name = project.get("name")
            project_key = project.get("key")
            for env in project.get("environments", []):
                env["project_name"] = project_name
                env["project_key"] = project_key
                results.append(env)
    
    elif type_code == "JOB":
        for project in snapshot.get("projects", []):
            project_name = project.get("name")
            project_key = project.get("key")
            for job in project.get("jobs", []):
                job["project_name"] = project_name
                job["project_key"] = project_key
                # Flatten steps list to comma-separated string for CSV
                if "steps" in job and isinstance(job["steps"], list):
                    job["steps_csv"] = "; ".join(str(s) for s in job["steps"])
                results.append(job)
    
    elif type_code == "VAR":
        for project in snapshot.get("projects", []):
            project_name = project.get("name")
            project_key = project.get("key")
            for var in project.get("environment_variables", []):
                var["project_name"] = project_name
                var["project_key"] = project_key
                results.append(var)
    
    return results


def _flatten_for_csv(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dicts for CSV export, handling special cases."""
    flat = {}
    for key, value in data.items():
        full_key = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten_for_csv(value, f"{full_key}_"))
        elif isinstance(value, list):
            # Convert lists to string representation
            if all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
                flat[full_key] = "; ".join(str(v) for v in value if v is not None)
            else:
                flat[full_key] = json.dumps(value)
        else:
            flat[full_key] = value
    return flat


# Resource type display names, icons, and sort order
# Sort order ranges (with room for future items):
#   00-09: Account level
#   10-19: Global resources
#   30-39: Projects
#   40-49: Project resources
#   50-59: Execution/Jobs
RESOURCE_TYPES = {
    "ACC": {"name": "Account", "icon": "cloud", "color": "#3B82F6", "sort_order": "00"},
    "CON": {"name": "Connection", "icon": "storage", "color": "#10B981", "sort_order": "10"},
    "REP": {"name": "Repository", "icon": "source", "color": "#8B5CF6", "sort_order": "11"},
    "TOK": {"name": "Service Token", "icon": "key", "color": "#EC4899", "sort_order": "12"},
    "GRP": {"name": "Group", "icon": "group", "color": "#6366F1", "sort_order": "13"},
    "NOT": {"name": "Notification", "icon": "notifications", "color": "#F97316", "sort_order": "14"},
    "WEB": {"name": "Webhook", "icon": "webhook", "color": "#84CC16", "sort_order": "15"},
    "PLE": {"name": "PrivateLink", "icon": "lock", "color": "#14B8A6", "sort_order": "16"},
    "PRJ": {"name": "Project", "icon": "folder", "color": "#F59E0B", "sort_order": "30"},
    "ENV": {"name": "Environment", "icon": "layers", "color": "#06B6D4", "sort_order": "40"},
    "VAR": {"name": "Env Variable", "icon": "code", "color": "#A855F7", "sort_order": "41"},
    "JOB": {"name": "Job", "icon": "schedule", "color": "#EF4444", "sort_order": "50"},
}


def _add_sort_key(items: list) -> list:
    """Add a sort_key field to each item based on type sort order."""
    for item in items:
        type_code = item.get("element_type_code", "ZZ")
        sort_order = RESOURCE_TYPES.get(type_code, {}).get("sort_order", "99")
        item["_type_sort_key"] = f"{sort_order}-{type_code}"
    return items


def create_entity_table(
    report_items: list,
    state: AppState,
    save_state: Callable[[], None],
) -> None:
    """Create the entity table with filtering, sorting, and export."""
    # Add sort keys to all items
    _add_sort_key(report_items)
    
    # State for filtering
    current_filter = {"type": "all", "search": ""}
    grid_ref = {"grid": None}
    
    # Get unique types for the filter dropdown, sorted by sort_order
    types_in_data = sorted(
        set(item.get("element_type_code", "UNK") for item in report_items),
        key=lambda t: RESOURCE_TYPES.get(t, {}).get("sort_order", "99")
    )
    filter_options = ["all"] + types_in_data
    
    # Count by type
    type_counts = {}
    for item in report_items:
        t = item.get("element_type_code", "UNK")
        type_counts[t] = type_counts.get(t, 0) + 1
    
    def get_filtered_data():
        """Get data filtered by current settings."""
        filtered = report_items
        
        # Apply type filter
        if current_filter["type"] != "all":
            filtered = [r for r in filtered if r.get("element_type_code") == current_filter["type"]]
        
        # Apply search filter
        if current_filter["search"]:
            search_lower = current_filter["search"].lower()
            filtered = [
                r for r in filtered
                if search_lower in str(r.get("name", "")).lower()
                or search_lower in str(r.get("key", "")).lower()
                or search_lower in str(r.get("dbt_id", "")).lower()
                or search_lower in str(r.get("element_mapping_id", "")).lower()
            ]
        
        return filtered
    
    def update_grid():
        """Update grid with filtered data."""
        if grid_ref["grid"]:
            filtered = get_filtered_data()
            grid_ref["grid"].options["rowData"] = filtered
            grid_ref["grid"].update()
            count_label.set_text(f"Showing {len(filtered)} of {len(report_items)} items")
    
    def on_type_change(e):
        current_filter["type"] = e.value
        update_grid()
    
    def on_search_change(e):
        current_filter["search"] = e.value
        update_grid()
    
    def export_csv():
        """Export filtered data to CSV.
        
        When a specific type is selected, loads full data from the JSON snapshot
        to include ALL fields from the API (not just the simplified report_items).
        """
        type_code = current_filter["type"]
        
        if type_code == "all":
            # For "all" types, use the simplified report_items
            filtered = get_filtered_data()
            if not filtered:
                ui.notify("No data to export", type="warning")
                return
            
            fieldnames = ["element_type_code", "name", "project_name", "key", "dbt_id", 
                         "element_mapping_id", "include_in_conversion", "line_item_number", 
                         "state", "project_id"]
            export_data = filtered
        else:
            # For specific types, load FULL data from the JSON snapshot
            full_data = _load_full_data_for_type(state, type_code)
            if not full_data:
                # Fall back to report_items if full data not available
                filtered = get_filtered_data()
                if not filtered:
                    ui.notify("No data to export", type="warning")
                    return
                full_data = filtered
            
            # Flatten nested structures for CSV
            export_data = [_flatten_for_csv(item) for item in full_data]
            
            # Collect all unique keys from the flattened items
            all_keys = set()
            for item in export_data:
                all_keys.update(item.keys())
            
            # Sort keys for consistent output, with common fields first
            priority_fields = ["id", "name", "key", "project_name", "project_key", 
                              "environment_key", "state", "steps_csv", "steps",
                              "dbt_version", "description", "schedule_type", "schedule_cron"]
            fieldnames = [f for f in priority_fields if f in all_keys]
            fieldnames.extend(sorted(f for f in all_keys if f not in priority_fields))
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(export_data)
        
        csv_content = output.getvalue()
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        account_id = state.source_account.account_id or "unknown"
        type_suffix = f"_{type_code}" if type_code != "all" else ""
        type_name = RESOURCE_TYPES.get(type_code, {}).get("name", type_code) if type_code != "all" else "all"
        filename = f"{type_name.lower().replace(' ', '_')}_{account_id}{type_suffix}_{timestamp}.csv"
        
        # Trigger download using JavaScript
        ui.download(csv_content.encode("utf-8"), filename)
        ui.notify(f"Exported {len(export_data)} items ({len(fieldnames)} columns) to {filename}", type="positive")
    
    def show_entity_detail(e):
        """Show detail dialog for clicked entity."""
        if e.args and "data" in e.args:
            row_data = e.args["data"]
            _show_detail_dialog(row_data, state)
    
    # Main container with grid layout to fill available space
    with ui.element("div").style(
        "display: grid; "
        "grid-template-rows: auto 1fr; "
        "width: 100%; "
        "height: 100%; "
        "gap: 8px; "
        "overflow: hidden;"
    ):
        # Toolbar row (auto height)
        with ui.row().classes("w-full items-center gap-2 flex-wrap"):
            # Type filter dropdown
            type_select = ui.select(
                options={
                    opt: f"{RESOURCE_TYPES.get(opt, {}).get('name', opt)} ({type_counts.get(opt, 0)})" 
                    if opt != "all" else f"All Types ({len(report_items)})"
                    for opt in filter_options
                },
                value="all",
                on_change=on_type_change,
            ).props("outlined dense").classes("min-w-[200px]")
            
            # Search box
            search_input = ui.input(
                placeholder="Search by name, key, or ID...",
                on_change=on_search_change,
            ).props("outlined dense clearable").classes("flex-grow min-w-[200px]")
            
            # Export button
            ui.button(
                "Export CSV",
                icon="download",
                on_click=export_csv,
            ).props("outline")
            
            # Column visibility button
            def show_column_dialog():
                """Show dialog to configure visible columns."""
                all_columns = [
                    ("element_type_code", "Type"),
                    ("name", "Name"),
                    ("project_name", "Project"),
                    ("key", "Key"),
                    ("dbt_id", "dbt ID"),
                    ("include_in_conversion", "Include"),
                    ("line_item_number", "Line #"),
                    ("element_mapping_id", "Mapping ID"),
                    ("project_id", "Project ID"),
                ]
                
                with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[300px]"):
                    ui.label("Visible Columns").classes("text-lg font-semibold mb-4")
                    
                    checkboxes = {}
                    for field, label in all_columns:
                        is_visible = field in state.explore.visible_columns
                        cb = ui.checkbox(label, value=is_visible)
                        checkboxes[field] = cb
                    
                    with ui.row().classes("w-full justify-end mt-4 gap-2"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")
                        
                        def apply_columns():
                            new_visible = [f for f, cb in checkboxes.items() if cb.value]
                            state.explore.visible_columns = new_visible
                            save_state()
                            dialog.close()
                            # Update grid column visibility
                            if grid_ref["grid"]:
                                for field, _ in all_columns:
                                    hide = field not in new_visible
                                    grid_ref["grid"].run_column_method("setColumnVisible", field, not hide)
                        
                        ui.button("Apply", on_click=apply_columns).props("color=primary")
                
                dialog.open()
            
            ui.button(icon="view_column", on_click=show_column_dialog).props(
                "outline dense"
            ).tooltip("Configure visible columns")
            
            # Export button
            ui.button(
                "Export CSV",
                icon="download",
                on_click=export_csv,
            ).props("outline")
            
            # Item count
            count_label = ui.label(f"Showing {len(report_items)} of {len(report_items)} items").classes(
                "text-sm text-slate-500"
            )
        
        # Define column definitions with visibility based on state
        visible_cols = state.explore.visible_columns
        column_defs = [
            {
                "field": "_type_sort_key",
                "headerName": "Sort Key",
                "hide": True,  # Always hidden - used for sorting
                "sortable": True,
            },
            {
                "field": "element_type_code",
                "headerName": "Type",
                "width": 100,
                "filter": True,
                "sortable": True,
                "hide": "element_type_code" not in visible_cols,
            },
            {
                "field": "name",
                "headerName": "Name",
                "width": 250,
                "filter": "agTextColumnFilter",
                "sortable": True,
                "hide": "name" not in visible_cols,
            },
            {
                "field": "project_name",
                "headerName": "Project",
                "width": 180,
                "filter": "agTextColumnFilter",
                "sortable": True,
                "hide": "project_name" not in visible_cols,
            },
            {
                "field": "key",
                "headerName": "Key",
                "width": 200,
                "filter": True,
                "sortable": True,
                "hide": "key" not in visible_cols,
            },
            {
                "field": "dbt_id",
                "headerName": "dbt ID",
                "width": 100,
                "filter": "agNumberColumnFilter",
                "sortable": True,
                "hide": "dbt_id" not in visible_cols,
            },
            {
                "field": "include_in_conversion",
                "headerName": "Include",
                "width": 90,
                "sortable": True,
                "hide": "include_in_conversion" not in visible_cols,
            },
            {
                "field": "line_item_number",
                "headerName": "Line #",
                "width": 80,
                "sortable": True,
                "hide": "line_item_number" not in visible_cols,
            },
            {
                "field": "element_mapping_id",
                "headerName": "Mapping ID",
                "width": 150,
                "hide": "element_mapping_id" not in visible_cols,
            },
            {
                "field": "project_id",
                "headerName": "Project ID",
                "width": 100,
                "filter": "agNumberColumnFilter",
                "sortable": True,
                "hide": "project_id" not in visible_cols,
            },
        ]
        
        # AGGrid table (fills remaining space)
        grid = ui.aggrid({
            "columnDefs": column_defs,
            "rowData": report_items,
            "pagination": True,
            "paginationPageSize": 50,
            "paginationPageSizeSelector": [25, 50, 100, 200],
            "rowSelection": {"mode": "singleRow"},
            "animateRows": False,
            "rowHeight": 35,
            "headerHeight": 40,
            # Default sort: Project A-Z, Type (by sort order) A-Z, Name A-Z
            "initialState": {
                "sort": {
                    "sortModel": [
                        {"colId": "project_name", "sort": "asc"},
                        {"colId": "_type_sort_key", "sort": "asc"},
                        {"colId": "name", "sort": "asc"},
                    ]
                }
            },
            "suppressAutoSize": True,
            "defaultColDef": {
                "resizable": True,
            },
        }, theme="balham").classes("w-full h-full").style("min-height: 200px;")
        
        grid_ref["grid"] = grid
        
        # Handle row click for detail view
        grid.on("cellClicked", show_entity_detail)


def _get_full_entity_data(state: "AppState", row_data: dict) -> Optional[Dict[str, Any]]:
    """Load full entity data from the JSON snapshot."""
    type_code = row_data.get("element_type_code", "")
    entity_id = row_data.get("dbt_id")
    entity_key = row_data.get("key")
    
    full_data_list = _load_full_data_for_type(state, type_code)
    
    # Find matching entity
    for item in full_data_list:
        if entity_id and item.get("id") == entity_id:
            return item
        if entity_key and item.get("key") == entity_key:
            return item
        if entity_key and item.get("_key") == entity_key:
            return item
    
    return None


def _show_detail_dialog(row_data: dict, state: Optional["AppState"] = None) -> None:
    """Show a dialog with entity details."""
    
    type_code = row_data.get("element_type_code", "UNK")
    type_info = RESOURCE_TYPES.get(type_code, {"name": type_code, "icon": "info", "color": "#6B7280"})
    
    # Load full data if state is available
    full_data = _get_full_entity_data(state, row_data) if state else None
    
    with ui.dialog() as dialog, ui.card().classes("w-[800px] max-h-[85vh]"):
        # Header
        with ui.row().classes("w-full items-center justify-between p-4 border-b"):
            with ui.row().classes("items-center gap-2"):
                ui.icon(type_info["icon"]).style(f"color: {type_info['color']};")
                ui.label(row_data.get("name", "Unknown")).classes("text-xl font-bold")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")
        
        # Tabs
        with ui.tabs().classes("w-full") as tabs:
            overview_tab = ui.tab("Overview", icon="info")
            details_tab = ui.tab("Details", icon="list")
            json_summary_tab = ui.tab("JSON (Summary)", icon="code")
            if full_data:
                json_full_tab = ui.tab("JSON (Full)", icon="data_object")
        
        with ui.tab_panels(tabs, value=overview_tab).classes("w-full"):
            # Overview tab
            with ui.tab_panel(overview_tab):
                with ui.scroll_area().style("max-height: 450px;"):
                    with ui.column().classes("w-full gap-4 p-2"):
                        # Key info chips
                        with ui.row().classes("w-full gap-4 flex-wrap"):
                            _info_chip("Type", type_info["name"], type_info["color"])
                            if row_data.get("dbt_id"):
                                _info_chip("dbt ID", str(row_data["dbt_id"]), "#3B82F6")
                            if row_data.get("key"):
                                _info_chip("Key", row_data["key"], "#8B5CF6")
                            if row_data.get("state") is not None:
                                state_val = row_data["state"]
                                color = "#22C55E" if state_val == 1 else "#EF4444"
                                _info_chip("State", "Active" if state_val == 1 else "Inactive", color)
                        
                        # Context info
                        ui.separator()
                        if row_data.get("project_name"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("folder", size="sm").classes("text-slate-500")
                                ui.label(f"Project: {row_data['project_name']}").classes("text-sm")
                        
                        if row_data.get("environment_key"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("layers", size="sm").classes("text-slate-500")
                                ui.label(f"Environment: {row_data['environment_key']}").classes("text-sm")
                        
                        if row_data.get("include_in_conversion") is not None:
                            with ui.row().classes("items-center gap-2"):
                                icon = "check_circle" if row_data["include_in_conversion"] else "cancel"
                                color = "text-green-500" if row_data["include_in_conversion"] else "text-red-500"
                                ui.icon(icon, size="sm").classes(color)
                                ui.label(
                                    "Included in conversion" if row_data["include_in_conversion"] 
                                    else "Excluded from conversion"
                                ).classes("text-sm")
            
            # Details tab - tree/outline view
            with ui.tab_panel(details_tab):
                with ui.scroll_area().style("max-height: 450px;"):
                    _render_property_tree(full_data if full_data else row_data)
            
            # JSON Summary tab
            with ui.tab_panel(json_summary_tab):
                formatted_json = json.dumps(row_data, indent=2, sort_keys=True)
                with ui.column().classes("w-full gap-2"):
                    with ui.row().classes("w-full justify-end"):
                        ui.button(
                            "Copy",
                            icon="content_copy",
                            on_click=lambda fj=formatted_json: (
                                ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(fj)})"),
                                ui.notify("Copied to clipboard", type="positive"),
                            ),
                        ).props("flat dense")
                    with ui.scroll_area().style("max-height: 420px;"):
                        ui.code(formatted_json, language="json").classes("w-full text-xs")
            
            # JSON Full tab (if full data available)
            if full_data:
                with ui.tab_panel(json_full_tab):
                    full_json = json.dumps(full_data, indent=2, sort_keys=True)
                    with ui.column().classes("w-full gap-2"):
                        with ui.row().classes("w-full justify-end"):
                            ui.button(
                                "Copy",
                                icon="content_copy",
                                on_click=lambda fj=full_json: (
                                    ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(fj)})"),
                                    ui.notify("Copied to clipboard", type="positive"),
                                ),
                            ).props("flat dense")
                        with ui.scroll_area().style("max-height: 420px;"):
                            ui.code(full_json, language="json").classes("w-full text-xs")
    
    dialog.open()


def _render_property_tree(data: dict, level: int = 0) -> None:
    """Render a property tree/outline view of the data."""
    if not data:
        ui.label("No data available").classes("text-slate-500 italic")
        return
    
    for key, value in sorted(data.items()):
        # Skip internal keys
        if key.startswith("_"):
            continue
        
        if isinstance(value, dict) and value:
            # Nested object - use expansion
            with ui.expansion(key, icon="folder_open").classes("w-full"):
                _render_property_tree(value, level + 1)
        elif isinstance(value, list):
            # List - show count and items
            with ui.expansion(f"{key} ({len(value)} items)", icon="list").classes("w-full"):
                if not value:
                    ui.label("Empty list").classes("text-slate-500 italic text-sm")
                else:
                    for i, item in enumerate(value[:20]):  # Limit to 20 items
                        if isinstance(item, dict):
                            item_label = item.get("name") or item.get("key") or f"Item {i+1}"
                            with ui.expansion(f"{i+1}. {item_label}", icon="article").classes("w-full"):
                                _render_property_tree(item, level + 2)
                        else:
                            with ui.row().classes("items-center gap-2 pl-4"):
                                ui.label(f"{i+1}.").classes("text-slate-500 text-xs w-6")
                                ui.label(str(item)).classes("text-sm font-mono")
                    if len(value) > 20:
                        ui.label(f"... and {len(value) - 20} more items").classes(
                            "text-slate-500 italic text-sm pl-4"
                        )
        else:
            # Simple value
            with ui.row().classes("items-start gap-2 py-1"):
                ui.label(f"{key}:").classes("text-slate-600 dark:text-slate-400 text-sm min-w-[120px]")
                if value is None:
                    ui.label("null").classes("text-slate-400 italic text-sm font-mono")
                elif isinstance(value, bool):
                    icon = "check" if value else "close"
                    color = "text-green-500" if value else "text-red-500"
                    ui.icon(icon, size="xs").classes(color)
                else:
                    display_val = str(value)
                    if len(display_val) > 100:
                        display_val = display_val[:100] + "..."
                    ui.label(display_val).classes("text-sm font-mono break-all")


def _info_chip(label: str, value: str, color: str) -> None:
    """Create an info chip with label and value."""
    with ui.card().classes("p-2").style(f"border-left: 3px solid {color};"):
        ui.label(label).classes("text-xs text-slate-500")
        ui.label(value).classes("font-medium text-sm")
