"""Entity table component with AGGrid."""

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, List, Dict, Any

from nicegui import ui

from importer.web.state import AppState


# Sensitive field patterns for masking
SENSITIVE_FIELD_PATTERNS = [
    "password", "secret", "token", "key", "credential", "auth",
    "private", "api_key", "apikey", "access_key", "accesskey",
]


def _is_sensitive_field(field_name: str) -> bool:
    """Check if a field name appears to be sensitive and should be masked."""
    field_lower = field_name.lower()
    return any(pattern in field_lower for pattern in SENSITIVE_FIELD_PATTERNS)


def _load_full_data_for_type(state: AppState, type_code: str, is_target: bool = False) -> List[Dict[str, Any]]:
    """Load full data from the JSON snapshot for a specific entity type.
    
    This provides ALL fields from the API, not just the simplified report_items.
    
    Args:
        state: Application state
        type_code: Entity type code (e.g., "JOB", "ENV")
        is_target: If True, load from target_fetch state; otherwise from fetch state
    """
    fetch_state = state.target_fetch if is_target else state.fetch
    if not fetch_state.last_fetch_file:
        return []
    
    json_path = Path(fetch_state.last_fetch_file)
    if not json_path.exists():
        return []
    
    try:
        snapshot = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []
    
    results = []
    globals_block = snapshot.get("globals", {})
    
    # Build project_id -> project_name lookup for linking repos to projects
    project_id_to_name = {}
    for project in snapshot.get("projects", []):
        if project.get("id"):
            project_id_to_name[project.get("id")] = project.get("name")
    
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
            # Look up project and name from metadata
            metadata = repo.get("metadata") or {}
            # Populate name from metadata if not at top level
            if not repo.get("name") and metadata.get("name"):
                repo["name"] = metadata.get("name")
            repo_project_id = metadata.get("project_id")
            if repo_project_id and repo_project_id in project_id_to_name:
                repo["project_name"] = project_id_to_name[repo_project_id]
                repo["project_id"] = repo_project_id
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
    "ACC": {"name": "Account", "code": "ACCNT", "icon": "cloud", "color": "#3B82F6", "sort_order": "00"},
    "CON": {"name": "Connection", "code": "CONN", "icon": "storage", "color": "#10B981", "sort_order": "10"},
    "REP": {"name": "Repository", "code": "REPO", "icon": "source", "color": "#8B5CF6", "sort_order": "11"},
    "TOK": {"name": "Service Token", "code": "SRVTKN", "icon": "key", "color": "#EC4899", "sort_order": "12"},
    "GRP": {"name": "Group", "code": "GRP", "icon": "group", "color": "#6366F1", "sort_order": "13"},
    "NOT": {"name": "Notification", "code": "NOTIFY", "icon": "notifications", "color": "#F97316", "sort_order": "14"},
    "WEB": {"name": "Webhook", "code": "WBHK", "icon": "webhook", "color": "#84CC16", "sort_order": "15"},
    "PLE": {"name": "PrivateLink", "code": "PRVLNK", "icon": "lock", "color": "#14B8A6", "sort_order": "16"},
    "PRJ": {"name": "Project", "code": "PRJCT", "icon": "folder", "color": "#F59E0B", "sort_order": "30"},
    "ENV": {"name": "Environment", "code": "ENV", "icon": "layers", "color": "#06B6D4", "sort_order": "40"},
    "VAR": {"name": "Env Variable", "code": "ENVVAR", "icon": "code", "color": "#A855F7", "sort_order": "41"},
    "JOB": {"name": "Job", "code": "JOB", "icon": "schedule", "color": "#EF4444", "sort_order": "50"},
}

# Optimized default columns per entity type (most useful fields for each type)
DEFAULT_COLUMNS_BY_TYPE = {
    "all": ["line_item_number", "element_type_code", "name", "project_name", "key", "dbt_id"],
    "ACC": ["line_item_number", "name", "id", "plan", "state"],
    "CON": ["line_item_number", "name", "id", "type", "adapter_type", "state", "project_name"],
    "REP": ["line_item_number", "name", "id", "remote_url", "git_clone_strategy", "project_name"],
    "TOK": ["line_item_number", "name", "id", "state", "created_at"],
    "GRP": ["line_item_number", "name", "id", "state", "assign_by_default"],
    "NOT": ["line_item_number", "id", "type", "state", "on_success", "on_failure"],
    "WEB": ["line_item_number", "name", "id", "active", "event_types", "client_url"],
    "PLE": ["line_item_number", "name", "id", "type", "state", "cidr_range"],
    "PRJ": ["line_item_number", "name", "id", "state", "created_at", "description"],
    "ENV": ["line_item_number", "name", "id", "type", "dbt_version", "project_name", "deployment_type"],
    "VAR": ["line_item_number", "name", "project_name", "type", "display_value"],
    "JOB": ["line_item_number", "name", "id", "state", "project_name", "environment_id", "schedule_type", "triggers"],
}


def _add_sort_key(items: list) -> list:
    """Add a sort_key field and display type to each item based on type sort order."""
    for item in items:
        type_code = item.get("element_type_code", "ZZ")
        type_info = RESOURCE_TYPES.get(type_code, {})
        sort_order = type_info.get("sort_order", "99")
        item["_type_sort_key"] = f"{sort_order}-{type_code}"
        # Add display type code (ACCNT, REPO, etc.) for the Type column
        item["_display_type"] = type_info.get("code", type_code)
    return items


def _build_column_defs(visible_cols: list, type_filter: str, state: "AppState", is_target: bool = False) -> list:
    """Build AG Grid column definitions based on visible columns and type filter.
    
    Args:
        visible_cols: List of column field names that should be visible
        type_filter: Current type filter ("all" or a specific type code)
        state: App state for loading full data
        is_target: If True, load from target_fetch state
        
    Returns:
        List of AG Grid column definitions
    """
    # Column width optimization based on typical content
    # Wider widths for name/label fields that need full visibility
    COLUMN_WIDTHS = {
        "element_type_code": 85,
        "name": 280,  # Wider for full names
        "project_name": 200,  # Wider for project names
        "project_key": 180,
        "key": 220,  # Keys can be long
        "dbt_id": 80,
        "id": 80,
        "include_in_conversion": 85,
        "line_item_number": 80,
        "element_mapping_id": 160,
        "project_id": 90,
        "environment_id": 100,
        "environment_key": 180,
        "state": 75,
        "type": 110,
        "description": 300,  # Descriptions need space
        "dbt_version": 110,
        "created_at": 160,
        "updated_at": 160,
        "schedule_type": 120,
        "triggers": 150,
        "execute_steps": 110,
        "remote_url": 300,  # URLs can be long
        "git_clone_strategy": 140,
        "adapter_type": 120,
        "steps_csv": 300,  # Job steps need space
    }
    DEFAULT_WIDTH = 140
    
    # Base column definitions with explicit colId to prevent AG Grid auto-numbering
    column_defs = [
        {
            "field": "_type_sort_key",
            "colId": "_type_sort_key",
            "headerName": "Sort Key",
            "hide": True,
            "sortable": True,
        },
        {
            "field": "line_item_number",
            "colId": "line_item_number",
            "headerName": "Line #",
            "width": COLUMN_WIDTHS["line_item_number"],
            "sortable": True,
            "hide": "line_item_number" not in visible_cols,
            "pinned": "left",
        },
        {
            "field": "_display_type",  # Use display code (ACCNT, REPO, etc.) instead of internal code
            "colId": "element_type_code",
            "headerName": "Type",
            "width": COLUMN_WIDTHS["element_type_code"],
            "filter": True,
            "sortable": True,
            "hide": "element_type_code" not in visible_cols,
            "pinned": "left",
            "wrapText": False,
        },
        {
            "field": "name",
            "colId": "name",
            "headerName": "Name",
            "width": COLUMN_WIDTHS["name"],
            "filter": "agTextColumnFilter",
            "sortable": True,
            "hide": "name" not in visible_cols,
            "pinned": "left",
            "wrapText": True,
            "autoHeight": True,
        },
        {
            "field": "project_name",
            "colId": "project_name",
            "headerName": "Project",
            "width": COLUMN_WIDTHS["project_name"],
            "filter": "agTextColumnFilter",
            "sortable": True,
            "hide": "project_name" not in visible_cols,
            "wrapText": True,
            "autoHeight": True,
        },
        {
            "field": "key",
            "colId": "key",
            "headerName": "Key",
            "width": COLUMN_WIDTHS["key"],
            "filter": True,
            "sortable": True,
            "hide": "key" not in visible_cols,
            "wrapText": True,
            "autoHeight": True,
        },
        {
            "field": "dbt_id",
            "colId": "dbt_id",
            "headerName": "ID",
            "width": COLUMN_WIDTHS["dbt_id"],
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "hide": "dbt_id" not in visible_cols,
        },
        {
            "field": "include_in_conversion",
            "colId": "include_in_conversion",
            "headerName": "Include",
            "width": COLUMN_WIDTHS["include_in_conversion"],
            "sortable": True,
            "hide": "include_in_conversion" not in visible_cols,
        },
        {
            "field": "element_mapping_id",
            "colId": "element_mapping_id",
            "headerName": "Mapping ID",
            "width": COLUMN_WIDTHS["element_mapping_id"],
            "hide": "element_mapping_id" not in visible_cols,
        },
        {
            "field": "project_id",
            "colId": "project_id",
            "headerName": "Proj ID",
            "width": COLUMN_WIDTHS["project_id"],
            "filter": "agNumberColumnFilter",
            "sortable": True,
            "hide": "project_id" not in visible_cols,
        },
    ]
    
    # Track fields we've already added to avoid duplicates
    existing_fields = {col["field"] for col in column_defs}
    
    # Add type-specific columns if a type is filtered
    if type_filter != "all":
        full_data = _load_full_data_for_type(state, type_filter, is_target)
        if full_data:
            # Discover additional keys from the data
            all_keys = set()
            for item in full_data[:10]:
                all_keys.update(item.keys())
            
            # Filter out already-defined fields and internal fields
            extra_keys = sorted(k for k in all_keys 
                              if k not in existing_fields and not k.startswith("_"))
            
            # Fields that should have text wrapping
            text_fields = {"description", "remote_url", "steps_csv", "steps", "git_clone_strategy",
                          "environment_key", "project_key", "custom_branch", "custom_environment_variables"}
            
            for field in extra_keys:
                col_def = {
                    "field": field,
                    "colId": field,  # Explicit colId to prevent AG Grid auto-numbering
                    "headerName": field.replace("_", " ").title(),
                    "width": COLUMN_WIDTHS.get(field, DEFAULT_WIDTH),
                    "filter": True,
                    "sortable": True,
                    "hide": field not in visible_cols,
                }
                # Enable wrapping for text fields
                if field in text_fields or "url" in field.lower() or "description" in field.lower():
                    col_def["wrapText"] = True
                    col_def["autoHeight"] = True
                column_defs.append(col_def)
                existing_fields.add(field)
    
    return column_defs


def create_entity_table(
    report_items: list,
    state: AppState,
    save_state: Callable[[], None],
    is_target: bool = False,
) -> None:
    """Create the entity table with filtering, sorting, and export.
    
    Args:
        report_items: List of entity items to display
        state: Application state
        save_state: Callback to save state changes
        is_target: If True, use target_fetch/target_account state; otherwise use source state
    """
    # Add sort keys to all items
    _add_sort_key(report_items)
    
    # State for filtering and grid refresh
    current_filter = {"type": "all", "search": ""}
    grid_ref = {"grid": None, "container": None}
    
    # Track refresh function
    refresh_ref = {"fn": None}
    
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
    
    # Cache for full data by type
    full_data_cache = {"type": None, "data": None}
    
    def get_filtered_data():
        """Get data filtered by current settings.
        
        When a specific type is filtered, loads full data from JSON snapshot
        to include all available fields for that type.
        """
        type_filter = current_filter["type"]
        
        if type_filter == "all":
            # Use simplified report_items for "all" view
            filtered = report_items
        else:
            # Load full data for specific type (with all fields)
            if full_data_cache["type"] != type_filter:
                full_data = _load_full_data_for_type(state, type_filter, is_target)
                if full_data:
                    # Add sort keys and merge with report_items metadata
                    for item in full_data:
                        # Find matching report_item to get element_type_code and other metadata
                        item_id = item.get("id")
                        item_key = item.get("key") or item.get("_key")
                        for ri in report_items:
                            if ri.get("dbt_id") == item_id or ri.get("key") == item_key:
                                item["element_type_code"] = ri.get("element_type_code", type_filter)
                                item["element_mapping_id"] = ri.get("element_mapping_id")
                                item["include_in_conversion"] = ri.get("include_in_conversion")
                                item["line_item_number"] = ri.get("line_item_number")
                                item["dbt_id"] = ri.get("dbt_id") or item.get("id")
                                break
                        else:
                            # No match found, use type_filter
                            item["element_type_code"] = type_filter
                            item["dbt_id"] = item.get("id")
                    _add_sort_key(full_data)
                    full_data_cache["type"] = type_filter
                    full_data_cache["data"] = full_data
                else:
                    # Fall back to report_items
                    full_data_cache["type"] = type_filter
                    full_data_cache["data"] = [r for r in report_items if r.get("element_type_code") == type_filter]
            
            filtered = full_data_cache["data"] or []
        
        # Apply type filter for "all" view
        if type_filter != "all" and full_data_cache["data"] is None:
            filtered = [r for r in filtered if r.get("element_type_code") == type_filter]
        
        # Apply search filter
        if current_filter["search"]:
            search_lower = current_filter["search"].lower()
            filtered = [
                r for r in filtered
                if search_lower in str(r.get("name", "")).lower()
                or search_lower in str(r.get("key", "")).lower()
                or search_lower in str(r.get("dbt_id", "")).lower()
                or search_lower in str(r.get("element_mapping_id", "")).lower()
                or search_lower in str(r.get("id", "")).lower()
            ]
        
        return filtered
    
    async def update_grid():
        """Update grid with filtered data and column definitions."""
        if grid_ref["grid"]:
            # Build new column definitions for current filter/visibility
            new_col_defs = _build_column_defs(state.explore.visible_columns, current_filter["type"], state, is_target)
            # Use AG Grid's setGridOption API to properly replace columns
            try:
                await grid_ref["grid"].run_grid_method("setGridOption", "columnDefs", new_col_defs)
            except Exception:
                # Fallback
                grid_ref["grid"].options["columnDefs"] = new_col_defs
                grid_ref["grid"].update()
            # Update row data
            filtered = get_filtered_data()
            grid_ref["grid"].options["rowData"] = filtered
            grid_ref["grid"].update()
            count_label.set_text(f"Showing {len(filtered)} of {len(report_items)} items")
    
    async def on_type_change(e):
        current_filter["type"] = e.value
        # Update the grid with new type-specific columns and filtered data
        await update_grid()
    
    def on_search_change(e):
        current_filter["search"] = e.value
        # For search, just update the row data without full rebuild
        if grid_ref["grid"]:
            filtered = get_filtered_data()
            grid_ref["grid"].options["rowData"] = filtered
            grid_ref["grid"].update()
            count_label.set_text(f"Showing {len(filtered)} of {len(report_items)} items")
    
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
            full_data = _load_full_data_for_type(state, type_code, is_target)
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
        account_state = state.target_account if is_target else state.source_account
        account_id = account_state.account_id or "unknown"
        account_prefix = "target_" if is_target else ""
        type_suffix = f"_{type_code}" if type_code != "all" else ""
        type_name = RESOURCE_TYPES.get(type_code, {}).get("name", type_code) if type_code != "all" else "all"
        filename = f"{account_prefix}{type_name.lower().replace(' ', '_')}_{account_id}{type_suffix}_{timestamp}.csv"
        
        # Trigger download using JavaScript
        ui.download(csv_content.encode("utf-8"), filename)
        ui.notify(f"Exported {len(export_data)} items ({len(fieldnames)} columns) to {filename}", type="positive")
    
    def show_entity_detail(e):
        """Show detail dialog for clicked entity."""
        if e.args and "data" in e.args:
            row_data = e.args["data"]
            show_entity_detail_dialog(row_data, state, is_target)
    
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
            ui.select(
                options={
                    opt: f"{RESOURCE_TYPES.get(opt, {}).get('name', opt)} ({RESOURCE_TYPES.get(opt, {}).get('code', opt)}) [{type_counts.get(opt, 0)}]" 
                    if opt != "all" else f"All Types ({len(report_items)})"
                    for opt in filter_options
                },
                value="all",
                on_change=on_type_change,
            ).props("outlined dense").classes("min-w-[200px]")
            
            # Search box
            ui.input(
                placeholder="Search by name, key, or ID...",
                on_change=on_search_change,
            ).props("outlined dense clearable").classes("flex-grow min-w-[200px]")
            
            # Column visibility button
            def show_column_dialog():
                """Show dialog to configure visible columns.
                
                When a specific type is filtered, discovers additional columns 
                from the full JSON data for that type.
                """
                # Base columns always available
                base_columns = [
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
                base_keys = {col[0] for col in base_columns}
                
                # Discover additional columns if a specific type is filtered
                type_specific_columns = []
                if current_filter["type"] != "all":
                    full_data = _load_full_data_for_type(state, current_filter["type"], is_target)
                    if full_data:
                        # Collect all unique keys from the data
                        all_keys = set()
                        for item in full_data[:10]:  # Sample first 10 items
                            all_keys.update(item.keys())
                        
                        # Filter out base keys and internal keys
                        extra_keys = sorted(k for k in all_keys 
                                          if k not in base_keys and not k.startswith("_"))
                        type_specific_columns = [(k, k.replace("_", " ").title()) for k in extra_keys]
                
                with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[400px] max-h-[80vh]"):
                    ui.label("Visible Columns").classes("text-lg font-semibold mb-2")
                    
                    checkboxes = {}
                    
                    with ui.scroll_area().style("max-height: 400px;"):
                        # Base columns section
                        ui.label("Standard Columns").classes("text-sm font-medium text-slate-500 mt-2 mb-1")
                        for field, label in base_columns:
                            is_visible = field in state.explore.visible_columns
                            cb = ui.checkbox(label, value=is_visible)
                            checkboxes[field] = cb
                        
                        # Type-specific columns section (if available)
                        if type_specific_columns:
                            ui.separator().classes("my-2")
                            type_name = RESOURCE_TYPES.get(current_filter["type"], {}).get("name", current_filter["type"])
                            ui.label(f"{type_name} Fields").classes("text-sm font-medium text-slate-500 mb-1")
                            for field, label in type_specific_columns:
                                is_visible = field in state.explore.visible_columns
                                cb = ui.checkbox(label, value=is_visible)
                                checkboxes[field] = cb
                    
                    with ui.row().classes("w-full justify-between mt-4"):
                        # Select all / none / default buttons
                        with ui.row().classes("gap-2"):
                            def select_all():
                                for cb in checkboxes.values():
                                    cb.set_value(True)
                            def select_none():
                                for cb in checkboxes.values():
                                    cb.set_value(False)
                            def select_default():
                                # Get optimized defaults for current type filter
                                type_key = current_filter["type"] if current_filter["type"] != "all" else "all"
                                default_cols = DEFAULT_COLUMNS_BY_TYPE.get(type_key, DEFAULT_COLUMNS_BY_TYPE["all"])
                                for field, cb in checkboxes.items():
                                    cb.set_value(field in default_cols)
                            ui.button("All", on_click=select_all).props("flat dense size=sm")
                            ui.button("None", on_click=select_none).props("flat dense size=sm")
                            ui.button("Default", on_click=select_default).props("flat dense size=sm").tooltip(
                                "Reset to optimized defaults for this entity type"
                            )
                        
                        with ui.row().classes("gap-2"):
                            ui.button("Cancel", on_click=dialog.close).props("flat")
                            
                            async def apply_columns():
                                new_visible = [f for f, cb in checkboxes.items() if cb.value]
                                state.explore.visible_columns = new_visible
                                save_state()
                                dialog.close()
                                
                                # Update grid column visibility using AG Grid API
                                if grid_ref["grid"]:
                                    new_col_defs = _build_column_defs(new_visible, current_filter["type"], state, is_target)
                                    try:
                                        await grid_ref["grid"].run_grid_method("setGridOption", "columnDefs", new_col_defs)
                                        ui.notify("Column visibility updated", type="positive")
                                    except Exception:
                                        # Fallback: try options update
                                        grid_ref["grid"].options["columnDefs"] = new_col_defs
                                        grid_ref["grid"].update()
                                        ui.notify("Column visibility updated", type="info")
                                else:
                                    ui.notify("Could not update grid", type="warning")
                            
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
        
        # Create a container for the grid that can be cleared and rebuilt
        grid_container = ui.element("div").classes("w-full h-full").style("min-height: 200px;")
        
        def build_grid_in_container():
            """Build the AG Grid inside the container."""
            # Build column definitions based on current state
            column_defs = _build_column_defs(state.explore.visible_columns, current_filter["type"], state, is_target)
            
            # Get the current data
            row_data = get_filtered_data()
            
            # AGGrid table - Note: removed initialState.sortModel as it may create phantom columns
            # Use quartz theme for automatic dark mode support
            grid = ui.aggrid({
                "columnDefs": column_defs,
                "rowData": row_data,
                "pagination": True,
                "paginationPageSize": 50,
                "paginationPageSizeSelector": [25, 50, 100, 200],
                "rowSelection": {"mode": "singleRow"},
                "animateRows": False,
                "headerHeight": 36,
                "suppressHorizontalScroll": False,
                "alwaysShowHorizontalScroll": True,
                "defaultColDef": {
                    "resizable": True,
                    "sortable": True,
                    "filter": True,
                    "minWidth": 80,
                    "wrapText": True,
                    "autoHeight": True,
                },
            }, theme="quartz").classes("w-full h-full").style("overflow-x: auto;")
            
            grid_ref["grid"] = grid
            grid.on("cellClicked", show_entity_detail)
        
        def rebuild_grid():
            """Clear and rebuild the grid with current settings."""
            grid_container.clear()
            with grid_container:
                build_grid_in_container()
        
        # Store the rebuild function for column updates
        refresh_ref["fn"] = rebuild_grid
        
        # Initial grid creation
        with grid_container:
            build_grid_in_container()


def _get_full_entity_data(state: "AppState", row_data: dict, is_target: bool = False) -> Optional[Dict[str, Any]]:
    """Load full entity data from the JSON snapshot.
    
    Args:
        state: Application state
        row_data: Row data containing entity type and identifiers
        is_target: If True, load from target_fetch state; otherwise from fetch state
    """
    type_code = row_data.get("element_type_code", "")
    entity_id = row_data.get("dbt_id")
    entity_key = row_data.get("key")
    
    full_data_list = _load_full_data_for_type(state, type_code, is_target)
    
    # Find matching entity
    for item in full_data_list:
        if entity_id and item.get("id") == entity_id:
            return item
        if entity_key and item.get("key") == entity_key:
            return item
        if entity_key and item.get("_key") == entity_key:
            return item
    
    return None


# Curated summary fields by entity type
SUMMARY_FIELDS = {
    "JOB": ["id", "name", "environment_id", "project_id", "triggers", "state", "dbt_version", 
            "execute_steps", "generate_docs", "run_generate_sources", "schedule_type"],
    "ENV": ["id", "name", "type", "dbt_version", "project_id", "use_custom_branch", 
            "custom_branch", "deployment_type", "credentials_id", "connection_id"],
    "PRJ": ["id", "name", "description", "created_at", "updated_at", "state", 
            "dbt_project_subdirectory", "semantic_layer_config_id"],
    "CON": ["id", "name", "type", "adapter_type", "state", "created_at", "account_id"],
    "REP": ["id", "name", "remote_url", "git_clone_strategy", "deploy_key_id", 
            "github_installation_id", "gitlab_project_id"],
    "TOK": ["id", "name", "state", "created_at", "uid", "access_url"],
    "GRP": ["id", "name", "state", "assign_by_default", "sso_mapping_groups"],
    "VAR": ["name", "project_id", "type", "display_value"],
    "ACC": ["id", "name", "plan", "state", "developer_seat_count", "read_only_seat_count"],
    "NOT": ["id", "type", "state", "on_success", "on_failure", "on_cancel"],
    "WEB": ["id", "name", "active", "http_status_code", "event_types"],
    "PLE": ["id", "name", "type", "state", "cidr_range"],
}


def show_entity_detail_dialog(row_data: dict, state: Optional["AppState"] = None, is_target: bool = False) -> None:
    """Show a dialog with entity details.
    
    Args:
        row_data: Row data containing entity information
        state: Application state for loading full data
        is_target: If True, load from target_fetch state; otherwise from fetch state
    """
    type_code = row_data.get("element_type_code", "UNK")
    type_info = RESOURCE_TYPES.get(type_code, {"name": type_code, "code": type_code, "icon": "info", "color": "#6B7280"})
    
    # Load full data if state is available
    full_data = _get_full_entity_data(state, row_data, is_target) if state else None
    display_data = full_data if full_data else row_data
    
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-6xl").style("height: 80vh;"):
        # Header
        with ui.row().classes("w-full items-center justify-between p-4 border-b"):
            with ui.row().classes("items-center gap-2"):
                ui.icon(type_info["icon"]).style(f"color: {type_info['color']};")
                ui.label(row_data.get("name", "Unknown")).classes("text-xl font-bold")
                ui.badge(f"{type_info['name']} ({type_info['code']})").style(f"background-color: {type_info['color']};")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")
        
        # Tabs - Summary is now the default
        with ui.tabs().classes("w-full") as tabs:
            summary_tab = ui.tab("Summary", icon="summarize")
            details_tab = ui.tab("Details", icon="table_rows")
            json_summary_tab = ui.tab("JSON (Summary)", icon="code")
            if full_data:
                json_full_tab = ui.tab("JSON (Full)", icon="data_object")
        
        with ui.tab_panels(tabs, value=summary_tab).classes("w-full flex-1"):
            # Summary tab - curated key fields
            with ui.tab_panel(summary_tab):
                with ui.scroll_area().style("height: 55vh;"):
                    _render_summary_tab(row_data, display_data, type_code, type_info)
            
            # Details tab - compact table layout
            with ui.tab_panel(details_tab):
                with ui.scroll_area().style("height: 55vh;"):
                    _render_details_table(display_data)
            
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
                    with ui.scroll_area().style("height: 55vh;"):
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
                        with ui.scroll_area().style("height: 55vh;"):
                            ui.code(full_json, language="json").classes("w-full text-xs")
    
    dialog.open()


def _render_summary_tab(row_data: dict, full_data: dict, type_code: str, type_info: dict) -> None:
    """Render the Summary tab with curated fields."""
    with ui.column().classes("w-full gap-4 p-2"):
        # Key info chips at top
        with ui.row().classes("w-full gap-3 flex-wrap"):
            _info_chip("Type", f"{type_info['name']} ({type_info['code']})", type_info["color"])
            if row_data.get("dbt_id") or full_data.get("id"):
                _info_chip("ID", str(row_data.get("dbt_id") or full_data.get("id")), "#3B82F6")
            if row_data.get("key") or full_data.get("key"):
                _info_chip("Key", row_data.get("key") or full_data.get("key"), "#8B5CF6")
            
            # State chip
            state_val = row_data.get("state") or full_data.get("state")
            if state_val is not None:
                if isinstance(state_val, int):
                    color = "#22C55E" if state_val == 1 else "#EF4444"
                    label = "Active" if state_val == 1 else "Inactive"
                else:
                    color = "#22C55E" if state_val else "#EF4444"
                    label = str(state_val)
                _info_chip("State", label, color)
        
        # Context info
        if row_data.get("project_name") or full_data.get("project_name"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("folder", size="sm").classes("text-slate-500")
                ui.label(f"Project: {row_data.get('project_name') or full_data.get('project_name')}").classes("text-sm")
        
        ui.separator()
        
        # Curated fields table
        ui.label("Key Properties").classes("text-lg font-semibold")
        
        summary_fields = SUMMARY_FIELDS.get(type_code, [])
        if not summary_fields:
            # Fallback to common fields
            summary_fields = ["id", "name", "state", "created_at", "updated_at"]
        
        # Render as compact table
        with ui.element("div").classes("w-full"):
            columns = [
                {"name": "field", "label": "Field", "field": "field", "align": "left"},
                {"name": "value", "label": "Value", "field": "value", "align": "left"},
            ]
            rows = []
            for field in summary_fields:
                value = full_data.get(field)
                if value is not None:
                    display_value = _format_value_for_display(value)
                    rows.append({"field": field, "value": display_value})
            
            if rows:
                ui.table(columns=columns, rows=rows, row_key="field").classes("w-full").props("dense flat")
            else:
                ui.label("No summary data available").classes("text-slate-500 italic")


def _render_details_table(data: dict) -> None:
    """Render all entity data as a compact table with inline expansion for nested objects."""
    if not data:
        ui.label("No data available").classes("text-slate-500 italic")
        return
    
    with ui.column().classes("w-full gap-1"):
        # Separate simple values, objects, and arrays
        simple_items = []
        complex_items = []
        
        for key, value in sorted(data.items()):
            if key.startswith("_"):
                continue
            if isinstance(value, (dict, list)) and value:
                complex_items.append((key, value))
            else:
                simple_items.append((key, value))
        
        # Render simple values as a dense table
        if simple_items:
            ui.label("Properties").classes("text-sm font-semibold text-slate-600 dark:text-slate-400 mb-1")
            with ui.element("div").classes("w-full border rounded").style("max-height: 300px; overflow-y: auto;"):
                for key, value in simple_items:
                    with ui.row().classes("w-full items-start border-b last:border-b-0 py-1 px-2 hover:bg-slate-50 dark:hover:bg-slate-800"):
                        ui.label(key).classes("text-sm font-medium w-1/3 text-slate-700 dark:text-slate-300")
                        _render_value_cell(value)
        
        # Render complex values (objects and arrays) with inline expansion
        if complex_items:
            ui.label("Nested Data").classes("text-sm font-semibold text-slate-600 dark:text-slate-400 mt-3 mb-1")
            for key, value in complex_items:
                if isinstance(value, dict):
                    with ui.expansion(f"{key}", icon="data_object", value=True).classes("w-full"):
                        _render_nested_object_table(value)
                elif isinstance(value, list):
                    with ui.expansion(f"{key} ({len(value)} items)", icon="list", value=True).classes("w-full"):
                        _render_nested_array(value)


def _render_value_cell(value: Any) -> None:
    """Render a value cell with appropriate formatting."""
    if value is None:
        ui.label("null").classes("text-slate-400 italic text-sm font-mono")
    elif isinstance(value, bool):
        icon_name = "check_circle" if value else "cancel"
        color = "text-green-500" if value else "text-red-500"
        with ui.row().classes("items-center gap-1"):
            ui.icon(icon_name, size="xs").classes(color)
            ui.label("true" if value else "false").classes(f"text-sm {color}")
    elif isinstance(value, (int, float)):
        ui.label(str(value)).classes("text-sm font-mono")
    else:
        display_val = str(value)
        if len(display_val) > 80:
            with ui.row().classes("items-center gap-1"):
                ui.label(display_val[:80] + "...").classes("text-sm font-mono break-all")
                ui.button(icon="unfold_more", on_click=lambda v=display_val: ui.notify(v, multi_line=True)).props("flat dense size=xs")
        else:
            ui.label(display_val).classes("text-sm font-mono break-all")


def _render_nested_object_table(obj: dict) -> None:
    """Render a nested object as a compact table."""
    if not obj:
        ui.label("Empty object").classes("text-slate-500 italic text-sm")
        return
    
    with ui.element("div").classes("w-full pl-2"):
        for key, value in sorted(obj.items()):
            if key.startswith("_"):
                continue
            with ui.row().classes("w-full items-start border-b last:border-b-0 py-1"):
                ui.label(key).classes("text-xs font-medium w-1/3 text-slate-600 dark:text-slate-400")
                if isinstance(value, dict) and value:
                    with ui.column().classes("w-2/3"):
                        _render_nested_object_table(value)
                elif isinstance(value, list) and value:
                    with ui.column().classes("w-2/3"):
                        _render_nested_array(value, compact=True)
                else:
                    _render_value_cell(value)


def _render_nested_array(arr: list, compact: bool = False) -> None:
    """Render a nested array with items."""
    if not arr:
        ui.label("Empty array").classes("text-slate-500 italic text-sm")
        return
    
    max_items = 10 if compact else 20
    for i, item in enumerate(arr[:max_items]):
        if isinstance(item, dict):
            item_label = item.get("name") or item.get("key") or item.get("id") or f"Item {i+1}"
            with ui.expansion(f"{i+1}. {item_label}", icon="article", value=not compact).classes("w-full"):
                _render_nested_object_table(item)
        else:
            with ui.row().classes("items-center gap-2 py-1"):
                ui.label(f"{i+1}.").classes("text-slate-500 text-xs w-6")
                ui.label(str(item)).classes("text-sm font-mono")
    
    if len(arr) > max_items:
        ui.label(f"... and {len(arr) - max_items} more items").classes("text-slate-500 italic text-sm pl-4")


def _format_value_for_display(value: Any) -> str:
    """Format a value for display in summary table."""
    if value is None:
        return "—"
    elif isinstance(value, bool):
        return "Yes" if value else "No"
    elif isinstance(value, dict):
        return f"{{...}} ({len(value)} keys)"
    elif isinstance(value, list):
        return f"[...] ({len(value)} items)"
    else:
        s = str(value)
        return s[:60] + "..." if len(s) > 60 else s


def _info_chip(label: str, value: str, color: str) -> None:
    """Create an info chip with label and value."""
    with ui.card().classes("p-2").style(f"border-left: 3px solid {color};"):
        ui.label(label).classes("text-xs text-slate-500")
        ui.label(value).classes("font-medium text-sm")


def show_match_detail_dialog(
    source_data: dict,
    grid_row: dict,
    target_data: Optional[dict] = None,
    state_resource: Optional[dict] = None,
    app_state: Optional["AppState"] = None,
    available_targets: Optional[list] = None,
    has_state_loaded: bool = False,
    on_target_selected: Optional[callable] = None,
    on_adopt: Optional[callable] = None,
) -> None:
    """Show an enhanced detail dialog for the Match context with drift comparison.
    
    Args:
        source_data: Source resource data
        grid_row: Row data from the match grid (has state_id, drift_status, target_id, etc.)
        target_data: Target resource data (if matched)
        state_resource: Terraform state resource data (if in state)
        app_state: Application state for loading full data
        available_targets: List of available target items to choose from (for manual matching)
        has_state_loaded: Whether TF state has been loaded (affects messaging)
        on_target_selected: Callback when user selects a target from dropdown
        on_adopt: Callback when user clicks "Set to Adopt" button
    """
    type_code = source_data.get("element_type_code", "UNK")
    type_info = RESOURCE_TYPES.get(type_code, {"name": type_code, "code": type_code, "icon": "info", "color": "#6B7280"})
    
    # Load full source data
    full_source = _get_full_entity_data(app_state, source_data, is_target=False) if app_state else None
    display_source = full_source if full_source else source_data
    
    # Load full target data
    full_target = _get_full_entity_data(app_state, target_data, is_target=True) if app_state and target_data else target_data
    
    # Get drift info from grid row
    drift_status = grid_row.get("drift_status", "no_state")
    state_id = grid_row.get("state_id")
    target_id = grid_row.get("target_id")
    action = grid_row.get("action", "")
    
    # Wider dialog for comparison view
    with ui.dialog() as dialog, ui.card().classes("w-full").style("max-width: 95vw; width: 1400px; height: 85vh;"):
        # Header with drift status
        with ui.row().classes("w-full items-center justify-between p-4 border-b"):
            with ui.row().classes("items-center gap-2"):
                ui.icon(type_info["icon"]).style(f"color: {type_info['color']};")
                ui.label(source_data.get("name", "Unknown")).classes("text-xl font-bold")
                ui.badge(f"{type_info['name']} ({type_info['code']})").style(f"background-color: {type_info['color']};")
                
                # Drift status badge
                drift_colors = {
                    "in_sync": ("#059669", "✓ In Sync"),
                    "id_mismatch": ("#D97706", "⚠️ ID Mismatch"),
                    "not_in_state": ("#F59E0B", "🚫 Not in TF State"),
                    "state_only": ("#3B82F6", "📌 In State Only"),
                    "no_state": ("#9CA3AF", "— No State Loaded"),
                }
                drift_color, drift_label = drift_colors.get(drift_status, ("#6B7280", drift_status))
                ui.badge(drift_label).style(f"background-color: {drift_color};")
                
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")
        
        # Filter available targets to same type
        type_code = source_data.get("element_type_code", "UNK")
        same_type_targets = []
        if available_targets:
            same_type_targets = [
                t for t in available_targets 
                if t.get("element_type_code") == type_code
            ]
        
        # Tabs with Drift/Compare tab
        with ui.tabs().classes("w-full") as tabs:
            drift_tab = ui.tab("Drift / Compare", icon="compare_arrows")
            summary_tab = ui.tab("Source Details", icon="summarize")
            target_tab = ui.tab("Target Details", icon="cloud_download")
            state_tab = ui.tab("TF State", icon="storage")
            json_tab = ui.tab("JSON", icon="code")
        
        with ui.tab_panels(tabs, value=drift_tab).classes("w-full flex-1 overflow-auto"):
            # Drift comparison tab
            with ui.tab_panel(drift_tab):
                with ui.scroll_area().style("height: 65vh;"):
                    _render_drift_comparison(
                        source_data=display_source,
                        target_data=full_target,
                        state_resource=state_resource,
                        grid_row=grid_row,
                        type_info=type_info,
                        has_state_loaded=has_state_loaded,
                        available_targets=same_type_targets,
                        on_target_selected=on_target_selected,
                        on_adopt=on_adopt,
                    )
            
            # Source details tab
            with ui.tab_panel(summary_tab):
                with ui.scroll_area().style("height: 65vh;"):
                    _render_summary_tab(source_data, display_source, type_code, type_info)
            
            # Target details tab
            with ui.tab_panel(target_tab):
                with ui.scroll_area().style("height: 65vh;"):
                    if full_target:
                        with ui.column().classes("w-full gap-4 p-4"):
                            ui.label("Matched Target Resource").classes("font-bold text-lg text-green-600")
                            
                            # Basic info card
                            with ui.card().classes("w-full p-4"):
                                ui.label(full_target.get("name", "Unknown")).classes("text-xl font-semibold")
                                ui.label(f"ID: {full_target.get('dbt_id', '—')}").classes("text-sm text-slate-500")
                                if full_target.get("project_name"):
                                    ui.label(f"Project: {full_target.get('project_name')}").classes("text-sm text-slate-500")
                            
                            # Target JSON
                            ui.separator()
                            ui.label("Full Target Data (JSON)").classes("font-semibold")
                            target_json_str = json.dumps(full_target, indent=2, sort_keys=True)
                            with ui.row().classes("w-full justify-end"):
                                ui.button(
                                    "Copy",
                                    icon="content_copy",
                                    on_click=lambda tj=target_json_str: (
                                        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(tj)})"),
                                        ui.notify("Copied to clipboard", type="positive"),
                                    ),
                                ).props("flat dense")
                            ui.code(target_json_str, language="json").classes("w-full text-xs")
                    else:
                        with ui.column().classes("w-full items-center justify-center p-8"):
                            ui.icon("cloud_off", size="xl").classes("text-slate-300 mb-4")
                            ui.label("No Target Matched").classes("text-lg text-slate-500")
                            ui.label("This resource has no matched target from dbt Cloud").classes("text-sm text-slate-400")
                            if same_type_targets:
                                ui.label(f"{len(same_type_targets)} available {type_info.get('name', type_code)} resources in target").classes("text-sm text-slate-400 mt-2")
            
            # TF State tab - formatted view with show/hide sensitive
            with ui.tab_panel(state_tab):
                with ui.scroll_area().style("height: 65vh;"):
                    if state_resource:
                        with ui.column().classes("w-full gap-4 p-4"):
                            # Header with address
                            ui.label("Terraform State Resource").classes("font-bold text-lg text-purple-600")
                            if state_resource.get("address"):
                                ui.code(state_resource.get("address")).classes("text-sm font-mono")
                            
                            # Show/hide sensitive toggle
                            show_sensitive = {"value": False}
                            
                            with ui.row().classes("items-center gap-2 mb-4"):
                                ui.label("Show Sensitive Values:").classes("text-sm")
                                sensitive_switch = ui.switch(value=False).props("dense")
                            
                            # State data container that updates based on toggle
                            state_container = ui.column().classes("w-full gap-2")
                            
                            def render_state_content():
                                state_container.clear()
                                with state_container:
                                    # Build display data
                                    display_data = {}
                                    for key, value in state_resource.items():
                                        if key.startswith("_"):
                                            continue
                                        # Mask sensitive fields if not showing
                                        if not sensitive_switch.value and _is_sensitive_field(key):
                                            if isinstance(value, str) and value:
                                                display_data[key] = "********"
                                            else:
                                                display_data[key] = value
                                        else:
                                            display_data[key] = value
                                    
                                    # Render as formatted table
                                    important_fields = ["address", "dbt_id", "name", "project_id", "tf_name", "element_code"]
                                    other_fields = sorted([k for k in display_data.keys() if k not in important_fields])
                                    ordered_fields = [f for f in important_fields if f in display_data] + other_fields
                                    
                                    with ui.element("div").classes("w-full border rounded").style("max-height: 400px; overflow-y: auto;"):
                                        for field in ordered_fields:
                                            value = display_data.get(field)
                                            if value is None:
                                                continue
                                            with ui.row().classes("w-full items-start border-b last:border-b-0 py-1 px-2 hover:bg-slate-50 dark:hover:bg-slate-800"):
                                                ui.label(field).classes("text-sm font-medium w-1/3 text-slate-700 dark:text-slate-300 font-mono")
                                                if isinstance(value, (dict, list)):
                                                    ui.code(json.dumps(value, indent=2), language="json").classes("text-xs w-2/3")
                                                elif value == "":
                                                    ui.label("(empty)").classes("text-sm w-2/3 text-slate-400 dark:text-slate-500 italic")
                                                else:
                                                    ui.label(str(value)).classes("text-sm w-2/3 break-all text-slate-900 dark:text-slate-100")
                            
                            # Initial render
                            render_state_content()
                            
                            # Update on toggle change
                            sensitive_switch.on_value_change(lambda e: render_state_content())
                            
                            # Raw JSON section
                            ui.separator()
                            ui.label("Raw State JSON").classes("font-semibold mt-4")
                            state_json_str = json.dumps(state_resource, indent=2, sort_keys=True)
                            with ui.row().classes("w-full justify-end"):
                                ui.button(
                                    "Copy",
                                    icon="content_copy",
                                    on_click=lambda sj=state_json_str: (
                                        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(sj)})"),
                                        ui.notify("Copied to clipboard", type="positive"),
                                    ),
                                ).props("flat dense")
                            ui.code(state_json_str, language="json").classes("w-full text-xs")
                    else:
                        with ui.column().classes("w-full items-center justify-center p-8"):
                            ui.icon("storage", size="xl").classes("text-slate-300 mb-4")
                            if has_state_loaded:
                                ui.label("No Matching State Resource").classes("text-lg text-slate-500")
                                ui.label("This resource was not found in Terraform state").classes("text-sm text-slate-400")
                            else:
                                ui.label("Terraform State Not Loaded").classes("text-lg text-slate-500")
                                ui.label("Load Terraform state to see state resource details").classes("text-sm text-slate-400")
            
            # JSON tab
            with ui.tab_panel(json_tab):
                with ui.scroll_area().style("height: 65vh;"):
                    with ui.column().classes("w-full gap-4"):
                        # Source JSON
                        ui.label("Source Data").classes("font-semibold text-lg")
                        source_json = json.dumps(display_source, indent=2, sort_keys=True)
                        with ui.row().classes("w-full justify-end"):
                            ui.button(
                                "Copy",
                                icon="content_copy",
                                on_click=lambda sj=source_json: (
                                    ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(sj)})"),
                                    ui.notify("Copied to clipboard", type="positive"),
                                ),
                            ).props("flat dense")
                        ui.code(source_json, language="json").classes("w-full text-xs")
                        
                        if full_target:
                            ui.separator()
                            ui.label("Target Data").classes("font-semibold text-lg")
                            target_json = json.dumps(full_target, indent=2, sort_keys=True)
                            with ui.row().classes("w-full justify-end"):
                                ui.button(
                                    "Copy",
                                    icon="content_copy",
                                    on_click=lambda tj=target_json: (
                                        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(tj)})"),
                                        ui.notify("Copied to clipboard", type="positive"),
                                    ),
                                ).props("flat dense")
                            ui.code(target_json, language="json").classes("w-full text-xs")
                        
                        if state_resource:
                            ui.separator()
                            ui.label("Terraform State Data").classes("font-semibold text-lg")
                            state_json = json.dumps(state_resource, indent=2, sort_keys=True)
                            with ui.row().classes("w-full justify-end"):
                                ui.button(
                                    "Copy",
                                    icon="content_copy",
                                    on_click=lambda stj=state_json: (
                                        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(stj)})"),
                                        ui.notify("Copied to clipboard", type="positive"),
                                    ),
                                ).props("flat dense")
                            ui.code(state_json, language="json").classes("w-full text-xs")
    
    dialog.open()


def _render_drift_comparison(
    source_data: dict,
    target_data: Optional[dict],
    state_resource: Optional[dict],
    grid_row: dict,
    type_info: dict,
    has_state_loaded: bool = False,
    available_targets: Optional[list] = None,
    on_target_selected: Optional[callable] = None,
    on_adopt: Optional[callable] = None,
) -> None:
    """Render the drift comparison view."""
    drift_status = grid_row.get("drift_status", "no_state")
    state_id = grid_row.get("state_id")
    target_id = grid_row.get("target_id")
    action = grid_row.get("action", "")
    
    with ui.column().classes("w-full gap-4 p-4"):
        # Status summary cards
        with ui.row().classes("w-full gap-4"):
            # Source card
            with ui.card().classes("flex-1 p-4").style("border: 2px solid #3B82F6;"):
                ui.label("Source (YAML)").classes("font-bold text-blue-600")
                ui.label(source_data.get("name", "Unknown")).classes("text-lg")
                ui.label(f"ID: {source_data.get('dbt_id', '—')}").classes("text-sm text-slate-500")
                if source_data.get("project_name"):
                    ui.label(f"Project: {source_data.get('project_name')}").classes("text-sm text-slate-500")
            
            # Arrow
            with ui.column().classes("justify-center"):
                ui.icon("arrow_forward", size="lg").classes("text-slate-400")
            
            # Target card (matched)
            with ui.card().classes("flex-1 p-4").style(f"border: 2px solid {'#10B981' if target_id else '#9CA3AF'};"):
                ui.label("Target (dbt Cloud)").classes(f"font-bold {'text-green-600' if target_id else 'text-slate-400'}")
                if target_data:
                    ui.label(target_data.get("name", "Unknown")).classes("text-lg")
                    ui.label(f"ID: {target_id or '—'}").classes("text-sm text-slate-500")
                else:
                    ui.label("No match" if not target_id else f"ID: {target_id}").classes("text-lg text-slate-400")
            
            # Arrow
            with ui.column().classes("justify-center"):
                ui.icon("sync_alt", size="lg").classes("text-slate-400")
            
            # State card
            with ui.card().classes("flex-1 p-4").style(f"border: 2px solid {'#8B5CF6' if state_id else '#9CA3AF'};"):
                ui.label("Terraform State").classes(f"font-bold {'text-purple-600' if state_id else 'text-slate-400'}")
                if state_resource:
                    ui.label(state_resource.get("name") or state_resource.get("tf_name", "Unknown")).classes("text-lg")
                    ui.label(f"ID: {state_id or '—'}").classes("text-sm text-slate-500")
                    if state_resource.get("address"):
                        ui.label(f"Address: {state_resource.get('address')}").classes("text-xs text-slate-400 font-mono")
                elif state_id:
                    ui.label(f"ID: {state_id}").classes("text-lg")
                else:
                    ui.label("Not in state").classes("text-lg text-slate-400")
        
        ui.separator()
        
        # Drift explanation
        with ui.card().classes("w-full p-4").style("border: 1px solid var(--q-primary);"):
            ui.label("Drift Analysis").classes("font-bold text-lg mb-2")
            
            # Determine the right "no_state" message based on whether state is loaded
            if has_state_loaded and drift_status == "no_state":
                no_state_explanation = (
                    "— No Matching Object in State",
                    "Terraform state is loaded but no matching resource was found. "
                    "This resource will be created as new by Terraform.",
                    "text-slate-500"
                )
            else:
                no_state_explanation = (
                    "— Terraform State Not Loaded",
                    "Load Terraform state to see drift analysis.",
                    "text-slate-500"
                )
            
            drift_explanations = {
                "in_sync": (
                    "✓ No drift detected",
                    "The Terraform state ID matches the target resource ID. No action needed.",
                    "text-green-600"
                ),
                "id_mismatch": (
                    "⚠️ ID Mismatch Detected",
                    f"The Terraform state tracks ID {state_id}, but the matched target has ID {target_id}. "
                    "This means Terraform would try to update/replace this resource. "
                    "To adopt the current target, set action to 'adopt' and generate import blocks.",
                    "text-amber-600"
                ),
                "not_in_state": (
                    "🚫 Resource Not in Terraform State",
                    f"This resource matched target ID {target_id}, but it's not tracked in Terraform state. "
                    "Terraform will try to create a new resource. "
                    "To adopt the existing resource, set action to 'adopt' and generate import blocks.",
                    "text-amber-600"
                ),
                "state_only": (
                    "📌 Resource Only in State",
                    f"This resource exists in Terraform state (ID {state_id}) but has no target match. "
                    "If you proceed with 'create_new', Terraform may destroy the existing resource. "
                    "Consider matching to an existing target or reviewing the state.",
                    "text-blue-600"
                ),
                "no_state": no_state_explanation,
            }
            
            title, explanation, color = drift_explanations.get(
                drift_status, 
                ("Unknown Status", f"Drift status: {drift_status}", "text-slate-500")
            )
            
            ui.label(title).classes(f"font-semibold {color}")
            ui.label(explanation).classes("text-sm mt-1")
            
            # Recommended action
            if drift_status in ("id_mismatch", "not_in_state"):
                # State to track protection checkbox
                protection_state = {"protected": True}  # Default to protected
                
                with ui.column().classes("mt-3 gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("lightbulb", color="amber")
                        ui.label("Recommended: Set Action to 'adopt' and generate import blocks").classes("text-sm font-medium")
                    
                    # Protection option when adopting
                    if on_adopt and action != "adopt":
                        with ui.row().classes("items-center gap-4 mt-2"):
                            # Protection checkbox
                            protect_checkbox = ui.checkbox(
                                "Protect from destroy",
                                value=True,
                            ).props("dense").on(
                                "update:model-value",
                                lambda e: protection_state.update({"protected": e.args})
                            )
                            with ui.row().classes("items-center gap-1"):
                                ui.icon("shield", size="sm").classes("text-blue-500")
                                ui.label("Terraform will refuse to destroy this resource").classes("text-xs text-slate-500")
                        
                        # Adopt button
                        with ui.row().classes("mt-2"):
                            ui.button(
                                "Set to Adopt",
                                icon="download",
                                on_click=lambda: on_adopt(protected=protection_state["protected"]),
                            ).props("color=warning dense")
        
        # Target selector dropdown (for manual matching)
        if available_targets and not target_id:
            ui.separator()
            with ui.card().classes("w-full p-4").style("border: 2px solid #3B82F6;"):
                ui.label("Select a Target to Match").classes("font-bold text-lg mb-2")
                ui.label(f"{len(available_targets)} available {type_info.get('name', 'resources')} in target account").classes("text-sm opacity-70 mb-3")
                
                # Build options for dropdown
                target_options = {
                    "": "— Select a target —",
                }
                for t in available_targets:
                    t_id = t.get("dbt_id", "")
                    t_name = t.get("name", "Unknown")
                    t_project = t.get("project_name", "")
                    label = f"{t_name} (ID: {t_id})"
                    if t_project:
                        label += f" [{t_project}]"
                    target_options[str(t_id)] = label
                
                selected_target = ui.select(
                    options=target_options,
                    value="",
                    label="Available Targets",
                ).classes("w-full").props("outlined dark")
                
                def handle_target_selection():
                    sel_id = selected_target.value
                    if sel_id and on_target_selected:
                        # Find the full target data
                        for t in available_targets:
                            if str(t.get("dbt_id")) == sel_id:
                                on_target_selected(t)
                                break
                
                ui.button("Match to Selected Target", icon="link", on_click=handle_target_selection).props("color=primary").classes("mt-2")
        
        # Detailed comparison table
        if target_data or state_resource:
            ui.separator()
            ui.label("Detailed Comparison").classes("font-bold text-lg mb-2")
            
            # Build comparison data
            all_keys = set()
            if source_data:
                all_keys.update(k for k in source_data.keys() if not k.startswith("_"))
            if target_data:
                all_keys.update(k for k in target_data.keys() if not k.startswith("_"))
            
            # Important fields to show first
            important_fields = ["id", "dbt_id", "name", "project_id", "environment_id", "state"]
            other_fields = sorted(all_keys - set(important_fields))
            ordered_fields = [f for f in important_fields if f in all_keys] + other_fields
            
            columns = [
                {"name": "field", "label": "Field", "field": "field", "align": "left", "style": "width: 200px;"},
                {"name": "source", "label": "Source (YAML)", "field": "source", "align": "left"},
                {"name": "target", "label": "Target (dbt Cloud)", "field": "target", "align": "left"},
            ]
            if state_resource:
                columns.append({"name": "state", "label": "TF State", "field": "state", "align": "left"})
            
            rows = []
            for field in ordered_fields[:30]:  # Limit to 30 fields
                source_val = source_data.get(field) if source_data else None
                target_val = target_data.get(field) if target_data else None
                state_val = state_resource.get(field) if state_resource else None
                
                # Skip if all are None or empty
                if source_val is None and target_val is None and state_val is None:
                    continue
                
                row = {
                    "field": field,
                    "source": _format_value_for_display(source_val),
                    "target": _format_value_for_display(target_val),
                }
                if state_resource:
                    row["state"] = _format_value_for_display(state_val)
                
                rows.append(row)
            
            if rows:
                ui.table(columns=columns, rows=rows, row_key="field").classes("w-full").props("dense flat")
