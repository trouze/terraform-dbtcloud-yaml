"""Entity table component with AGGrid."""

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState
from importer.web.components.stepper import DBT_ORANGE


# Resource type display names and icons
RESOURCE_TYPES = {
    "ACC": {"name": "Account", "icon": "cloud", "color": "#3B82F6"},
    "CON": {"name": "Connection", "icon": "storage", "color": "#10B981"},
    "REP": {"name": "Repository", "icon": "source", "color": "#8B5CF6"},
    "PRJ": {"name": "Project", "icon": "folder", "color": "#F59E0B"},
    "ENV": {"name": "Environment", "icon": "layers", "color": "#06B6D4"},
    "JOB": {"name": "Job", "icon": "schedule", "color": "#EF4444"},
    "TOK": {"name": "Service Token", "icon": "key", "color": "#EC4899"},
    "GRP": {"name": "Group", "icon": "group", "color": "#6366F1"},
    "NOT": {"name": "Notification", "icon": "notifications", "color": "#F97316"},
    "WEB": {"name": "Webhook", "icon": "webhook", "color": "#84CC16"},
    "PLE": {"name": "PrivateLink", "icon": "lock", "color": "#14B8A6"},
    "EVR": {"name": "Env Variable", "icon": "code", "color": "#A855F7"},
}


def create_entity_table(
    report_items: list,
    state: AppState,
    save_state: Callable[[], None],
) -> None:
    """Create the entity table with filtering, sorting, and export."""
    
    # State for filtering
    current_filter = {"type": "all", "search": ""}
    grid_ref = {"grid": None}
    
    # Get unique types for the filter dropdown
    types_in_data = sorted(set(item.get("element_type_code", "UNK") for item in report_items))
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
        """Export filtered data to CSV."""
        filtered = get_filtered_data()
        if not filtered:
            ui.notify("No data to export", type="warning")
            return
        
        # Create CSV in memory
        output = io.StringIO()
        if filtered:
            fieldnames = ["element_type_code", "name", "key", "dbt_id", "element_mapping_id", 
                         "include_in_conversion", "line_item_number", "state"]
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(filtered)
        
        csv_content = output.getvalue()
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        account_id = state.source_account.account_id or "unknown"
        filename = f"entities_{account_id}_{timestamp}.csv"
        
        # Trigger download using JavaScript
        ui.download(csv_content.encode("utf-8"), filename)
        ui.notify(f"Exported {len(filtered)} items to {filename}", type="positive")
    
    def show_entity_detail(e):
        """Show detail dialog for clicked entity."""
        if e.args and "data" in e.args:
            row_data = e.args["data"]
            _show_detail_dialog(row_data)
    
    # Toolbar row
    with ui.row().classes("w-full items-center gap-4 flex-wrap"):
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
        
        # Item count
        count_label = ui.label(f"Showing {len(report_items)} of {len(report_items)} items").classes(
            "text-sm text-slate-500"
        )
    
    # AGGrid table
    grid = ui.aggrid({
        "columnDefs": [
            {
                "field": "element_type_code",
                "headerName": "Type",
                "width": 100,
                "filter": True,
                "sortable": True,
                "cellRenderer": """
                    function(params) {
                        const types = {
                            'ACC': 'Account', 'CON': 'Connection', 'REP': 'Repository',
                            'PRJ': 'Project', 'ENV': 'Environment', 'JOB': 'Job',
                            'TOK': 'Token', 'GRP': 'Group', 'NOT': 'Notification',
                            'WEB': 'Webhook', 'PLE': 'PrivateLink', 'EVR': 'EnvVar'
                        };
                        return types[params.value] || params.value;
                    }
                """,
            },
            {
                "field": "name",
                "headerName": "Name",
                "flex": 2,
                "filter": "agTextColumnFilter",
                "sortable": True,
            },
            {
                "field": "key",
                "headerName": "Key",
                "flex": 1,
                "filter": True,
                "sortable": True,
                "cellStyle": {"fontFamily": "monospace", "fontSize": "0.85em"},
            },
            {
                "field": "dbt_id",
                "headerName": "dbt ID",
                "width": 100,
                "filter": "agNumberColumnFilter",
                "sortable": True,
            },
            {
                "field": "include_in_conversion",
                "headerName": "Include",
                "width": 90,
                "cellRenderer": """
                    function(params) {
                        return params.value ? '✓' : '✗';
                    }
                """,
                "cellStyle": """
                    function(params) {
                        return {
                            color: params.value ? '#10B981' : '#EF4444',
                            fontWeight: 'bold',
                            textAlign: 'center'
                        };
                    }
                """,
            },
            {
                "field": "line_item_number",
                "headerName": "Line #",
                "width": 80,
                "sortable": True,
            },
            {
                "field": "element_mapping_id",
                "headerName": "Mapping ID",
                "width": 120,
                "cellStyle": {"fontFamily": "monospace", "fontSize": "0.8em"},
            },
        ],
        "rowData": report_items,
        "pagination": True,
        "paginationPageSize": 50,
        "paginationPageSizeSelector": [25, 50, 100, 200],
        "rowSelection": "single",
        "animateRows": True,
        "defaultColDef": {
            "resizable": True,
        },
    }).classes("w-full").style("height: 500px;")
    
    grid_ref["grid"] = grid
    
    # Handle row click for detail view
    grid.on("cellClicked", show_entity_detail)


def _show_detail_dialog(row_data: dict) -> None:
    """Show a dialog with entity details."""
    import json
    
    type_code = row_data.get("element_type_code", "UNK")
    type_info = RESOURCE_TYPES.get(type_code, {"name": type_code, "icon": "info", "color": "#6B7280"})
    
    with ui.dialog() as dialog, ui.card().classes("w-[600px] max-h-[80vh]"):
        with ui.row().classes("w-full items-center justify-between p-4 border-b"):
            with ui.row().classes("items-center gap-2"):
                ui.icon(type_info["icon"]).style(f"color: {type_info['color']};")
                ui.label(row_data.get("name", "Unknown")).classes("text-xl font-bold")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")
        
        with ui.scroll_area().classes("w-full p-4").style("max-height: 400px;"):
            # Key info cards
            with ui.row().classes("w-full gap-4 mb-4"):
                _info_chip("Type", type_info["name"], type_info["color"])
                if row_data.get("dbt_id"):
                    _info_chip("dbt ID", str(row_data["dbt_id"]), "#3B82F6")
                if row_data.get("key"):
                    _info_chip("Key", row_data["key"], "#8B5CF6")
            
            # Additional info
            if row_data.get("project_name"):
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.icon("folder", size="xs").classes("text-slate-500")
                    ui.label(f"Project: {row_data['project_name']}")
            
            if row_data.get("environment_key"):
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.icon("layers", size="xs").classes("text-slate-500")
                    ui.label(f"Environment: {row_data['environment_key']}")
            
            # Divider
            ui.separator().classes("my-4")
            
            # JSON view toggle
            with ui.expansion("View Raw JSON", icon="code").classes("w-full"):
                formatted_json = json.dumps(row_data, indent=2, sort_keys=True)
                with ui.row().classes("w-full justify-end mb-2"):
                    ui.button(
                        "Copy",
                        icon="content_copy",
                        on_click=lambda: (
                            ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(formatted_json)})"),
                            ui.notify("Copied to clipboard", type="positive"),
                        ),
                    ).props("flat dense")
                ui.code(formatted_json, language="json").classes("w-full")
    
    dialog.open()


def _info_chip(label: str, value: str, color: str) -> None:
    """Create an info chip with label and value."""
    with ui.card().classes("p-2").style(f"border-left: 3px solid {color};"):
        ui.label(label).classes("text-xs text-slate-500")
        ui.label(value).classes("font-medium text-sm")
