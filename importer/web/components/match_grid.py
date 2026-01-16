"""Editable AG Grid component for resource matching."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import json
import logging

from nicegui import ui


# Colors
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"


@dataclass
class GridRow:
    """A row in the mapping grid."""
    
    source_key: str
    source_name: str
    source_type: str
    source_id: Optional[int]
    action: str  # "match", "create_new", "skip"
    target_id: str  # String to allow empty/partial input
    target_name: str
    status: str  # "pending", "confirmed", "error", "skipped"
    confidence: str  # "exact_match", "fuzzy", "manual", "none"
    project_name: str = ""


# Resource type display info
RESOURCE_TYPE_INFO = {
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


def build_grid_data(
    source_items: list[dict],
    target_items: list[dict],
    confirmed_mappings: list[dict],
    rejected_keys: set[str],
) -> list[dict]:
    """Build grid row data from source/target items and existing mappings.
    
    Args:
        source_items: Report items from source account
        target_items: Report items from target account
        confirmed_mappings: Already confirmed source->target mappings
        rejected_keys: Set of source keys that were rejected
        
    Returns:
        List of row dictionaries for AG Grid
    """
    # Build target lookup by (type, name) for auto-matching
    target_by_type_name: dict[tuple[str, str], dict] = {}
    target_by_id: dict[int, dict] = {}
    
    for item in target_items:
        key = (item.get("element_type_code", ""), item.get("name", ""))
        if key not in target_by_type_name:
            target_by_type_name[key] = item
        
        dbt_id = item.get("dbt_id")
        if dbt_id:
            target_by_id[dbt_id] = item
    
    # Build confirmed mapping lookup
    confirmed_by_source_key = {
        m.get("source_key"): m for m in confirmed_mappings
    }
    
    rows = []
    for source in source_items:
        source_key = source.get("key", "")
        source_name = source.get("name", "")
        source_type = source.get("element_type_code", "")
        source_id = source.get("dbt_id")
        project_name = source.get("project_name", "")
        
        # Skip if no key
        if not source_key:
            continue
        
        # Check if this source is already confirmed
        confirmed = confirmed_by_source_key.get(source_key)
        if confirmed:
            target_id = confirmed.get("target_id", "")
            target_name = confirmed.get("target_name", "")
            row = {
                "source_key": source_key,
                "source_name": source_name,
                "source_type": source_type,
                "source_id": source_id,
                "project_name": project_name,
                "action": "match",
                "target_id": str(target_id) if target_id else "",
                "target_name": target_name,
                "status": "confirmed",
                "confidence": confirmed.get("match_type", "manual"),
            }
            rows.append(row)
            continue
        
        # Check if rejected
        if source_key in rejected_keys:
            row = {
                "source_key": source_key,
                "source_name": source_name,
                "source_type": source_type,
                "source_id": source_id,
                "project_name": project_name,
                "action": "create_new",
                "target_id": "",
                "target_name": "",
                "status": "skipped",
                "confidence": "none",
            }
            rows.append(row)
            continue
        
        # Try auto-match by exact name
        lookup_key = (source_type, source_name)
        if lookup_key in target_by_type_name:
            target = target_by_type_name[lookup_key]
            row = {
                "source_key": source_key,
                "source_name": source_name,
                "source_type": source_type,
                "source_id": source_id,
                "project_name": project_name,
                "action": "match",
                "target_id": str(target.get("dbt_id", "")),
                "target_name": target.get("name", ""),
                "status": "pending",
                "confidence": "exact_match",
            }
        else:
            # No match found
            row = {
                "source_key": source_key,
                "source_name": source_name,
                "source_type": source_type,
                "source_id": source_id,
                "project_name": project_name,
                "action": "create_new",
                "target_id": "",
                "target_name": "",
                "status": "pending",
                "confidence": "none",
            }
        
        rows.append(row)
    
    return rows


def create_match_grid(
    source_items: list[dict],
    target_items: list[dict],
    confirmed_mappings: list[dict],
    rejected_keys: set[str],
    on_row_change: Callable[[dict], None],
    on_accept: Callable[[str], None],
    on_reject: Callable[[str], None],
    on_view_details: Callable[[str], None],
) -> tuple:
    """Create the editable matching grid.
    
    Args:
        source_items: Report items from source account
        target_items: Report items from target account
        confirmed_mappings: Already confirmed mappings
        rejected_keys: Set of rejected source keys
        on_row_change: Callback when a row value changes
        on_accept: Callback when accept button clicked (source_key)
        on_reject: Callback when reject button clicked (source_key)
        on_view_details: Callback when details button clicked (source_key)
        
    Returns:
        Tuple of (grid component, row data list)
    """
    # Build row data
    row_data = build_grid_data(source_items, target_items, confirmed_mappings, rejected_keys)
    
    # Build target options for autocomplete
    target_options = [
        {
            "id": str(t.get("dbt_id", "")),
            "name": t.get("name", ""),
            "type": t.get("element_type_code", ""),
        }
        for t in target_items if t.get("dbt_id")
    ]
    
    # Column definitions
    column_defs = [
        {
            "field": "source_type",
            "headerName": "Type",
            "width": 110,
            "cellRenderer": """function(params) {
                const types = {
                    'ACC': {name: 'Account', color: '#3B82F6'},
                    'CON': {name: 'Connection', color: '#10B981'},
                    'REP': {name: 'Repository', color: '#8B5CF6'},
                    'TOK': {name: 'Token', color: '#EC4899'},
                    'GRP': {name: 'Group', color: '#6366F1'},
                    'NOT': {name: 'Notify', color: '#F97316'},
                    'WEB': {name: 'Webhook', color: '#84CC16'},
                    'PLE': {name: 'PrivateLink', color: '#14B8A6'},
                    'PRJ': {name: 'Project', color: '#F59E0B'},
                    'ENV': {name: 'Environment', color: '#06B6D4'},
                    'VAR': {name: 'EnvVar', color: '#A855F7'},
                    'JOB': {name: 'Job', color: '#EF4444'},
                };
                const info = types[params.value] || {name: params.value, color: '#6B7280'};
                return '<span style="display: inline-flex; align-items: center; gap: 4px;">' +
                    '<span style="width: 8px; height: 8px; border-radius: 50%; background: ' + info.color + ';"></span>' +
                    '<span style="font-size: 11px;">' + info.name + '</span></span>';
            }""",
        },
        {
            "field": "source_name",
            "headerName": "Source Name",
            "width": 200,
            "filter": "agTextColumnFilter",
            "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
        },
        {
            "field": "source_id",
            "headerName": "Source ID",
            "width": 90,
            "cellStyle": {"fontFamily": "monospace", "fontSize": "11px", "color": "#6B7280"},
        },
        {
            "field": "action",
            "headerName": "Action",
            "width": 130,
            "editable": True,
            "cellEditor": "agSelectCellEditor",
            "cellEditorParams": {
                "values": ["match", "create_new", "skip"],
            },
            "cellRenderer": """function(params) {
                const icons = {
                    'match': '<span style="color: #047377;">⛓️ Match</span>',
                    'create_new': '<span style="color: #F59E0B;">➕ Create New</span>',
                    'skip': '<span style="color: #6B7280;">⏭️ Skip</span>',
                };
                return icons[params.value] || params.value;
            }""",
        },
        {
            "field": "target_id",
            "headerName": "Target ID",
            "width": 100,
            "editable": True,
            "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
        },
        {
            "field": "target_name",
            "headerName": "Target Name",
            "width": 180,
            "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
            "cellRenderer": """function(params) {
                if (!params.value) return '<span style="color: #9CA3AF;">—</span>';
                return '<span style="color: #10B981;">' + params.value + '</span>';
            }""",
        },
        {
            "field": "status",
            "headerName": "Status",
            "width": 110,
            "cellRenderer": """function(params) {
                const styles = {
                    'pending': {bg: '#FEF3C7', color: '#D97706', text: 'Pending'},
                    'confirmed': {bg: '#D1FAE5', color: '#059669', text: 'Confirmed'},
                    'error': {bg: '#FEE2E2', color: '#DC2626', text: 'Error'},
                    'skipped': {bg: '#F3F4F6', color: '#6B7280', text: 'Skipped'},
                };
                const s = styles[params.value] || styles.pending;
                return '<span style="display: inline-block; padding: 2px 8px; border-radius: 9999px; ' +
                    'background: ' + s.bg + '; color: ' + s.color + '; font-size: 11px; font-weight: 500;">' +
                    s.text + '</span>';
            }""",
        },
        {
            "field": "project_name",
            "headerName": "Project",
            "width": 140,
            "filter": "agTextColumnFilter",
            "cellStyle": {"fontSize": "11px", "color": "#6B7280"},
        },
    ]
    
    # Grid options
    grid_options = {
        "columnDefs": column_defs,
        "rowData": row_data,
        "pagination": True,
        "paginationPageSize": 50,
        "paginationPageSizeSelector": [25, 50, 100, 200],
        "rowHeight": 40,
        "headerHeight": 36,
        "defaultColDef": {
            "resizable": True,
            "sortable": True,
            "filter": True,
        },
        "rowClassRules": {
            "row-confirmed": "data.status === 'confirmed'",
            "row-error": "data.status === 'error'",
            "row-skipped": "data.status === 'skipped' || data.action === 'skip'",
        },
        "stopEditingWhenCellsLoseFocus": True,
        "singleClickEdit": True,
        "getRowId": "function(params) { return params.data.source_key; }",
    }
    
    # Create the grid
    grid = ui.aggrid(grid_options, theme="quartz").classes("w-full").style("height: 100%;")
    
    # Handle cell value changes
    def on_cell_changed(e):
        if e.args:
            data = e.args.get("data", {})
            col = e.args.get("colId", "")
            new_val = e.args.get("newValue")
            
            if col == "action":
                # When action changes, update the row
                data["action"] = new_val
                if new_val == "skip":
                    data["status"] = "skipped"
                    data["target_id"] = ""
                    data["target_name"] = ""
                elif new_val == "create_new":
                    data["target_id"] = ""
                    data["target_name"] = ""
                    data["status"] = "pending"
                
                on_row_change(data)
            
            elif col == "target_id":
                # Validate target ID
                data["target_id"] = new_val
                if new_val:
                    # Look up target name
                    target = next(
                        (t for t in target_options if t["id"] == str(new_val)),
                        None
                    )
                    if target:
                        # Validate type matches
                        if target["type"] == data.get("source_type"):
                            data["target_name"] = target["name"]
                            data["status"] = "pending"
                        else:
                            data["target_name"] = f"Type mismatch: {target['type']}"
                            data["status"] = "error"
                    else:
                        data["target_name"] = ""
                        data["status"] = "error"
                else:
                    data["target_name"] = ""
                    data["status"] = "pending" if data.get("action") == "create_new" else "error"
                
                on_row_change(data)
    
    grid.on("cellValueChanged", on_cell_changed)
    
    # Custom CSS for row classes
    ui.add_css("""
        .row-confirmed {
            background-color: rgba(16, 185, 129, 0.1) !important;
        }
        .row-error {
            background-color: rgba(239, 68, 68, 0.1) !important;
        }
        .row-skipped {
            background-color: rgba(156, 163, 175, 0.1) !important;
            color: #9CA3AF !important;
        }
    """)
    
    return grid, row_data


def create_grid_toolbar(
    row_data: list[dict],
    on_accept_all: Callable[[], None],
    on_reject_all: Callable[[], None],
    on_reset_all: Callable[[], None],
    on_export_csv: Callable[[], None],
) -> None:
    """Create the toolbar above the grid with bulk actions.
    
    Args:
        row_data: Current row data for counting
        on_accept_all: Callback for Accept All button
        on_reject_all: Callback for Reject All button
        on_reset_all: Callback for Reset All button
        on_export_csv: Callback for Export CSV button
    """
    # Count stats
    pending = sum(1 for r in row_data if r.get("status") == "pending" and r.get("action") == "match")
    confirmed = sum(1 for r in row_data if r.get("status") == "confirmed")
    create_new = sum(1 for r in row_data if r.get("action") == "create_new")
    skipped = sum(1 for r in row_data if r.get("action") == "skip")
    
    with ui.row().classes("w-full items-center justify-between mb-3 flex-wrap gap-2"):
        # Stats
        with ui.row().classes("items-center gap-4"):
            with ui.row().classes("items-center gap-1"):
                ui.badge(str(pending), color="amber").props("dense")
                ui.label("Pending").classes("text-sm")
            
            with ui.row().classes("items-center gap-1"):
                ui.badge(str(confirmed), color="green").props("dense")
                ui.label("Confirmed").classes("text-sm")
            
            with ui.row().classes("items-center gap-1"):
                ui.badge(str(create_new), color="orange").props("dense")
                ui.label("Create New").classes("text-sm")
            
            with ui.row().classes("items-center gap-1"):
                ui.badge(str(skipped), color="grey").props("dense")
                ui.label("Skip").classes("text-sm")
        
        # Actions
        with ui.row().classes("items-center gap-2"):
            ui.button(
                f"Accept All ({pending})",
                icon="check",
                on_click=on_accept_all,
            ).props("size=sm color=positive outline").set_enabled(pending > 0)
            
            ui.button(
                "Reject All",
                icon="close",
                on_click=on_reject_all,
            ).props("size=sm color=negative outline").set_enabled(pending > 0)
            
            ui.button(
                "Reset",
                icon="refresh",
                on_click=on_reset_all,
            ).props("size=sm outline")
            
            ui.button(
                "Export CSV",
                icon="download",
                on_click=on_export_csv,
            ).props("size=sm flat")


def export_mappings_to_csv(row_data: list[dict]) -> str:
    """Export mapping data to CSV format.
    
    Args:
        row_data: Grid row data
        
    Returns:
        CSV string
    """
    lines = ["source_key,source_name,source_type,action,target_id,target_name,status"]
    
    for row in row_data:
        line = ",".join([
            f'"{row.get("source_key", "")}"',
            f'"{row.get("source_name", "")}"',
            f'"{row.get("source_type", "")}"',
            f'"{row.get("action", "")}"',
            f'"{row.get("target_id", "")}"',
            f'"{row.get("target_name", "")}"',
            f'"{row.get("status", "")}"',
        ])
        lines.append(line)
    
    return "\n".join(lines)
