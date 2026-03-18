"""Destroy step page for selective resource taint/destroy.

Implements US-048 from PRD Part 5:
- Destroy button only available after successful apply
- Strong confirmation dialog (type resource count to confirm)
- Real-time output during destroy
- Summary of destroyed resources
- Warning that this is irreversible
"""

import asyncio
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.components.terminal_output import TerminalOutput
from importer.web.pages.deploy import _get_state_file_path
from importer.web.utils.terraform_helpers import (
    OutputBudget,
    emit_process_output,
    get_terraform_env as _get_terraform_env,
    resolve_deployment_paths,
    run_terraform_command,
)
from importer.web.state import AppState, WorkflowStep
from importer.web.utils.protection_manager import (
    extract_protected_resources,
    load_yaml_config,
    detect_and_repair_protection_mismatches,
    format_mismatches_for_display,
    ProtectionRepairResult,
)
from importer.web.utils.yaml_viewer import create_state_viewer_dialog
from importer.web.utils.ui_logger import log_action, log_state_change


# dbt brand colors
DBT_ORANGE = "#FF694A"
STATUS_ERROR = "#EF4444"  # red-500
_DEBUG_LOG_PATH = Path("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-673991.log")
_DEBUG_SESSION_ID = "673991"

def _agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict,
    *,
    run_id: str = "run1",
) -> None:
    _ = (hypothesis_id, location, message, data, run_id)


def _debug_673991(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict,
    *,
    run_id: str = "run1",
) -> None:
    """Write NDJSON debug logs for runtime AG Grid investigation."""
    try:
        payload = {
            "sessionId": _DEBUG_SESSION_ID,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def _extract_destroy_count_from_plan_output(plan_output: str) -> int:
    """Extract planned destroy count from Terraform plan output."""
    match = re.search(
        r"Plan:\s*\d+\s*to add,\s*\d+\s*to change,\s*(\d+)\s*to destroy\.",
        plan_output,
    )
    if match:
        return int(match.group(1))
    # Fallback for variant output when plan summary is missing/truncated.
    return sum(1 for line in plan_output.split("\n") if " will be destroyed" in line)


def _extract_destroy_count_from_apply_output(output: str) -> int:
    """Extract actual destroyed count from Terraform apply/destroy output."""
    summary_match = re.search(
        r"Destroy complete!\s*Resources:\s*(\d+)\s*destroyed\.",
        output,
    )
    if summary_match:
        return int(summary_match.group(1))
    return len(re.findall(r": Destruction complete after ", output))


def _emit_bounded_output(
    terminal: TerminalOutput,
    *,
    phase_name: str,
    stdout: str,
    stderr: str,
    on_stdout_line: Callable[[str], None],
    on_stderr_line: Callable[[str], None],
    stdout_budget: Optional[OutputBudget] = None,
    stderr_budget: Optional[OutputBudget] = None,
) -> None:
    """Emit command output with a bounded terminal budget."""
    emit_process_output(
        stdout,
        stderr,
        on_stdout_line=on_stdout_line,
        on_stderr_line=on_stderr_line,
        stdout_budget=stdout_budget,
        stderr_budget=stderr_budget,
        on_omitted=lambda omitted: terminal.warning(
            f"Large {phase_name} output detected; omitted {omitted} line(s) from terminal view."
        ),
    )


def _is_destroy_confirmation_text_valid(raw_value: str) -> bool:
    """Require exact DESTROY keyword (case-insensitive, surrounding whitespace ignored)."""
    return (raw_value or "").strip().upper() == "DESTROY"


def create_destroy_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the destroy step page content."""
    terminal = TerminalOutput(show_timestamps=True)

    destroy_state = {
        "terraform_dir": None,
        "selected": set(),
        "table": None,
    }

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
        with ui.row().classes("w-full items-center gap-4"):
            ui.icon("delete_forever", size="2rem").style(f"color: {DBT_ORANGE};")
            ui.label("Destroy Resources").classes("text-2xl font-bold")

        ui.label(
            "Inspect Terraform state and selectively taint or destroy resources."
        ).classes("text-slate-600 dark:text-slate-400")

        if not _check_prerequisites(state, on_step_change, destroy_state):
            return

        # Compact info bar: State path + Target info in one row
        _create_compact_info_bar(state, destroy_state, on_step_change)

        # Protected resources panel (full width, self-contained with actions)
        _create_destroy_protection_panel(state, save_state, destroy_state)

        # Protection mismatch detection and repair panel
        _create_protection_repair_panel(state, save_state, destroy_state, terminal)

        # Destroy resources table (full width, self-contained with actions)
        _create_resource_table(state, destroy_state, terminal, save_state)

        # Output terminal (full width)
        with ui.card().classes("w-full"):
            ui.label("Output").classes("font-semibold mb-2")
            terminal.create(height="520px")

        _create_navigation_section(on_step_change)


def _check_prerequisites(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    destroy_state: dict,
) -> bool:
    """Check if prerequisites are met for destroy - requires credentials only.
    
    State file is not required to access the page - the user can view the page
    and see that no state exists yet. Individual destroy operations will check
    for state file existence when needed.
    """
    errors = []
    
    # Check for target credentials
    if not state.target_credentials.is_complete():
        errors.append(("Target credentials not configured", WorkflowStep.FETCH_TARGET))
    
    # Note: State file is NOT required to access this page - user can always view
    # the destroy page and see status. Actions will check for state file when needed.
    
    if errors:
        with ui.card().classes("w-full p-6 border-l-4 border-yellow-500"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("warning", size="lg").classes("text-yellow-500")
                ui.label("Prerequisites Required").classes("text-xl font-semibold")

            ui.label(
                "Complete the following steps before destroying resources:"
            ).classes("mt-4 text-slate-600 dark:text-slate-400")

            with ui.column().classes("mt-4 gap-3"):
                for error_msg, step in errors:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("error", size="sm").classes("text-red-500")
                        ui.label(error_msg).classes("text-sm")
                        ui.button(
                            f"Go to {state.get_step_label(step)}",
                            on_click=lambda s=step: on_step_change(s),
                        ).props("size=sm outline")

        return False

    return True


def _create_compact_info_bar(
    state: AppState,
    destroy_state: dict,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create a compact info bar with state path and target account info."""
    state_path = _get_state_file_path(state, destroy_state)
    creds = state.target_credentials
    
    # Extract display-friendly host
    host_display = creds.host_url or "https://cloud.getdbt.com"
    host_display = host_display.replace("https://", "").replace("http://", "").rstrip("/")
    if host_display.endswith("/api"):
        host_display = host_display[:-4]
    
    with ui.row().classes("w-full items-center gap-4 p-3 rounded").style(
        "background-color: rgba(100, 116, 139, 0.1);"
    ):
        # State file info
        ui.icon("description", size="sm").classes("text-slate-500")
        if state_path:
            ui.label(state_path).classes("text-xs text-slate-600 dark:text-slate-400 font-mono truncate")
        else:
            ui.label("No state file").classes("text-xs text-slate-500 italic")
        
        def open_state_viewer():
            current_state_path = _get_state_file_path(state, destroy_state)
            if current_state_path:
                dialog = create_state_viewer_dialog(current_state_path)
                dialog.open()
            else:
                _show_no_state_dialog(state, destroy_state)
        
        ui.button(
            icon="visibility",
            on_click=open_state_viewer,
        ).props("flat dense round size=sm").tooltip("View State")
        
        ui.separator().props("vertical").classes("mx-2")
        
        # Target account info
        ui.icon("cloud", size="sm").classes("text-slate-500")
        account_name = getattr(state.target_credentials, 'account_name', None) or "Target"
        ui.label(f"{account_name} (ID: {creds.account_id})").classes("text-xs text-slate-600 dark:text-slate-400")
        ui.label(host_display).classes("text-xs text-slate-500 font-mono")
        
        ui.button(
            icon="settings",
            on_click=lambda: on_step_change(WorkflowStep.FETCH_TARGET),
        ).props("flat dense round size=sm").tooltip("Configure Target")


def _show_no_state_dialog(state: AppState, destroy_state: dict) -> None:
    """Show a dialog indicating no state file exists yet."""
    tf_path, _yaml_file, _baseline_yaml = resolve_deployment_paths(state)
    expected_path = tf_path / "terraform.tfstate"
    
    with ui.dialog() as dialog:
        with ui.card().classes("w-full max-w-md"):
            with ui.row().classes("items-center gap-3 mb-4"):
                ui.icon("info", size="lg").classes("text-blue-500")
                ui.label("No Terraform State").classes("text-lg font-semibold")
            
            ui.label(
                "No Terraform state file exists yet. The state file is created "
                "after a successful 'terraform apply' operation."
            ).classes("text-sm text-slate-600 dark:text-slate-400 mb-4")
            
            with ui.column().classes("gap-2 mb-4"):
                ui.label("Expected location:").classes("text-xs text-slate-500 font-medium")
                ui.label(str(expected_path)).classes(
                    "text-xs text-slate-500 font-mono p-2 rounded bg-slate-100 dark:bg-slate-800"
                )
            
            ui.label(
                "Complete the Deploy workflow (Generate → Init → Plan → Apply) to create the state file."
            ).classes("text-xs text-slate-500")
            
            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Close", on_click=dialog.close).props("outline")
    
    dialog.open()


def _create_state_inspection_panel(state: AppState, destroy_state: dict) -> None:
    """Create state inspection panel."""
    state_path = _get_state_file_path(state, destroy_state)

    def open_state_viewer() -> None:
        # Re-check state path in case it was created after page load
        current_state_path = _get_state_file_path(state, destroy_state)
        if current_state_path:
            dialog = create_state_viewer_dialog(current_state_path)
            dialog.open()
        else:
            # Show dialog indicating no state file exists yet
            _show_no_state_dialog(state, destroy_state)

    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("description", size="sm").classes("text-slate-500")
            ui.label("State File").classes("font-semibold")
        
        if state_path:
            ui.label(state_path).classes("text-xs text-slate-500 font-mono truncate mb-3")
        else:
            ui.label("No state file available yet.").classes("text-xs text-slate-500 mb-3")

        # Always enable the View State button - it will show helpful info if no state exists
        view_btn = ui.button(
            "View State",
            icon="visibility",
            on_click=open_state_viewer,
        ).props("outline").classes("w-full")
        
        if state_path:
            view_btn.style("color: white; background-color: rgba(255,255,255,0.1);")


def _create_target_info_panel(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create target account information panel."""
    creds = state.target_credentials
    
    # Extract display-friendly host (remove https:// and /api suffix)
    host_display = creds.host_url or "https://cloud.getdbt.com"
    host_display = host_display.replace("https://", "").replace("http://", "").rstrip("/")
    if host_display.endswith("/api"):
        host_display = host_display[:-4]
    
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between mb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("cloud", size="sm").classes("text-slate-500")
                ui.label("Target").classes("font-semibold")
            ui.button(
                icon="settings",
                on_click=lambda: on_step_change(WorkflowStep.CONFIGURE),
            ).props("flat dense round size=sm").tooltip("Target Configuration")
        
        with ui.column().classes("gap-1"):
            # Account name (if available from state, otherwise show generic)
            account_name = getattr(state.target_credentials, 'account_name', None) or "dbt Cloud Account"
            ui.label(account_name).classes("text-sm font-medium")
            
            # Account ID
            ui.label(f"ID: {creds.account_id}").classes("text-xs text-slate-500 font-mono")
            
            # Host URL
            ui.label(host_display).classes("text-xs text-slate-500 font-mono")


def _create_resource_table(
    state: AppState,
    destroy_state: dict,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
) -> None:
    """Create the self-contained Destroy Resources AG Grid with filters and action buttons."""
    # Note: AG Grid dark mode CSS is now applied globally in app.py setup_page()
    
    resources = _load_state_resources(state, destroy_state)
    
    # Filter out data sources (mode="data") - they can't be tainted/destroyed
    managed_resources = [r for r in resources if r.get("mode") != "data"]
    
    # Pre-sort data by display_name (per AG Grid standards - no default sort via AG Grid)
    managed_resources = sorted(managed_resources, key=lambda x: x.get("display_name", ""))
    
    # Store all resources for filtering
    destroy_state["all_resources"] = managed_resources
    resource_count = len(managed_resources)
    # region agent log
    _debug_673991(
        "H1",
        "destroy.py:_create_resource_table",
        "loaded resource table input",
        {
            "resources_total": len(resources),
            "managed_resources": resource_count,
            "first_managed_keys": list(managed_resources[0].keys()) if managed_resources else [],
            "first_managed_preview": (
                {
                    "address": managed_resources[0].get("address"),
                    "type": managed_resources[0].get("type"),
                    "display_name": managed_resources[0].get("display_name"),
                }
                if managed_resources
                else {}
            ),
        },
    )
    # endregion

    # Filter state
    filter_state = {"type": "all", "search": ""}
    
    # Count resources by type
    type_counts = {}
    for r in managed_resources:
        t = r.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    
    # Build type filter options
    type_options = {"all": f"All Types ({len(managed_resources)})"}
    for t in sorted(type_counts.keys()):
        # Create friendly display name from terraform type
        display_name = t.replace("dbtcloud_", "").replace("_", " ").title()
        type_options[t] = f"{display_name} ({type_counts[t]})"

    # Add _selected column to row data for checkbox state
    for row in managed_resources:
        row["_selected"] = False
    
    # AG Grid column definitions with explicit colId (per standards)
    column_defs = [
        {
            "field": "_selected",
            "colId": "_selected",
            "headerName": "✓",
            "width": 50,
            "pinned": "left",
            "cellRenderer": "agCheckboxCellRenderer",
            "editable": True,
            "cellStyle": {"textAlign": "center"},
        },
        {
            "field": "protected",
            "colId": "protected",
            "headerName": "",
            "width": 50,
            "cellDataType": False,  # Prevent auto-checkbox for boolean
            ":valueFormatter": "params => params.value ? '🛡️' : ''",
            "sortable": False,
            "filter": False,
        },
        {
            "field": "type",
            "colId": "type",
            "headerName": "Type",
            "width": 180,
            "sortable": True,
            "filter": "agTextColumnFilter",
        },
        {
            "field": "display_name",
            "colId": "display_name",
            "headerName": "Name",
            "flex": 1,
            "sortable": True,
            "filter": "agTextColumnFilter",
        },
    ]
    # region agent log
    _debug_673991(
        "H2",
        "destroy.py:_create_resource_table",
        "column definitions prepared",
        {
            "column_count": len(column_defs),
            "column_fields": [c.get("field") for c in column_defs],
            "protected_col_keys": list(column_defs[1].keys()) if len(column_defs) > 1 else [],
            "protected_has_typo_value_formatter": (
                ":valueFormatter" in column_defs[1] if len(column_defs) > 1 else False
            ),
        },
    )
    # endregion

    with ui.card().classes("w-full"):
        # Header row with title and refresh
        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label("Destroy Resources").classes("font-semibold")
                resource_badge = ui.badge(f"{resource_count} managed").props("color=primary outline")
                destroy_state["resource_badge"] = resource_badge
            ui.button(
                "Refresh",
                icon="refresh",
                on_click=lambda: _refresh_resources_aggrid(state, destroy_state),
            ).props("outline size=sm")
        
        # Helper to update selection label
        def _update_selection_label():
            label = destroy_state.get("selection_label")
            if label:
                count = len(destroy_state.get("selected", set()))
                label.set_text(f"Selected: {count}")
        
        # Helper to update the grid with quick filter (type filter requires row data update)
        def update_destroy_grid_filter():
            grid = destroy_state.get("grid")
            if not grid:
                return
            
            # Use AG Grid's quick filter for search
            search_term = filter_state.get("search", "")
            grid.run_grid_method('setGridOption', 'quickFilterText', search_term)
            
            # For type filter, update rowData
            if filter_state["type"] != "all":
                filtered = [r for r in managed_resources if r.get("type") == filter_state["type"]]
                grid.options["rowData"] = filtered
                grid.update()
                # region agent log
                _debug_673991(
                    "H1",
                    "destroy.py:update_destroy_grid_filter",
                    "applied typed filter",
                    {
                        "filter_type": filter_state["type"],
                        "search_term": search_term,
                        "rowdata_len": len(filtered),
                    },
                )
                # endregion
            else:
                grid.options["rowData"] = managed_resources
                grid.update()
                # region agent log
                _debug_673991(
                    "H1",
                    "destroy.py:update_destroy_grid_filter",
                    "applied all-type filter",
                    {
                        "filter_type": "all",
                        "search_term": search_term,
                        "rowdata_len": len(managed_resources),
                    },
                )
                # endregion
            
            # Update badge
            badge = destroy_state.get("resource_badge")
            if badge:
                if filter_state["type"] == "all" and not filter_state["search"]:
                    badge.set_text(f"{len(managed_resources)} managed")
                else:
                    visible_count = len([r for r in managed_resources if r.get("type") == filter_state["type"]]) if filter_state["type"] != "all" else len(managed_resources)
                    badge.set_text(f"{visible_count} shown / {len(managed_resources)} total")
        
        # Select all visible rows (checkbox pattern)
        def select_all_destroy():
            grid = destroy_state.get("grid")
            if not grid:
                return
            # Update all rows to selected
            for row in managed_resources:
                row["_selected"] = True
                addr = row.get("address")
                if addr:
                    destroy_state["selected"].add(addr)
            grid.options["rowData"] = managed_resources
            grid.update()
            _update_selection_label()
        
        # Clear all selections (checkbox pattern)
        def clear_destroy_selection():
            grid = destroy_state.get("grid")
            if not grid:
                return
            # Update all rows to unselected
            for row in managed_resources:
                row["_selected"] = False
            destroy_state["selected"] = set()
            grid.options["rowData"] = managed_resources
            grid.update()
            _update_selection_label()
        
        # Export CSV handler
        def export_destroy_csv():
            grid = destroy_state.get("grid")
            if grid:
                grid.run_grid_method('exportDataAsCsv', {
                    'fileName': 'destroy_resources.csv',
                    'columnSeparator': ',',
                })
        
        # Action button handlers
        async def on_destroy_selected():
            await _confirm_destroy_selected(state, terminal, save_state, destroy_state)
        
        async def on_destroy_all():
            await _confirm_destroy_all(state, terminal, save_state, destroy_state, resource_count)
        
        # Action buttons row (above filters)
        with ui.row().classes("w-full items-center gap-2 mb-3 flex-wrap"):
            # Selection buttons
            ui.button(
                "Select All",
                icon="select_all",
                on_click=select_all_destroy,
            ).props("outline size=sm padding='4px 12px'")
            
            ui.button(
                "Clear",
                icon="close",
                on_click=clear_destroy_selection,
            ).props("outline size=sm padding='4px 12px'")
            
            ui.separator().props("vertical").classes("mx-1")
            
            # Taint button
            ui.button(
                "Taint Selected",
                icon="warning",
                on_click=lambda: _run_terraform_taint(
                    state, terminal, save_state, destroy_state
                ),
            ).props("outline color=warning size=sm padding='4px 12px'")
            
            # Destroy Selected button
            ui.button(
                "Plan Destroy (Selected)",
                icon="delete",
                on_click=on_destroy_selected,
            ).props("outline color=negative size=sm padding='4px 12px'")
            
            ui.separator().props("vertical").classes("mx-1")
            
            # Export CSV button
            ui.button(
                "Export CSV",
                icon="download",
                on_click=export_destroy_csv,
            ).props("outline size=sm padding='4px 12px'")
            
            ui.space()
            
            # Destroy All (danger)
            ui.button(
                f"Destroy All ({resource_count})",
                icon="delete_forever",
                on_click=on_destroy_all,
            ).props("color=negative size=sm padding='4px 16px'").style(f"background-color: {STATUS_ERROR}; color: white;")
        
        # Type filter change handler
        def on_type_change(e):
            new_value = e.value if e.value else "all"
            filter_state["type"] = new_value
            update_destroy_grid_filter()
        
        # Search change handler (uses AG Grid quick filter)
        def on_search_change(e):
            new_value = e.value if e.value else ""
            filter_state["search"] = new_value
            update_destroy_grid_filter()
        
        # Filter row: Type dropdown | Search input | Selection counter
        with ui.row().classes("w-full items-center gap-3 mb-3"):
            ui.select(
                options=type_options,
                value="all",
                label="Filter by Type",
                on_change=on_type_change,
            ).props("outlined dense").classes("min-w-[180px]")
            
            ui.input(
                placeholder="Search by name or ID...",
                on_change=on_search_change,
            ).props("outlined dense clearable").classes("flex-grow min-w-[200px]")
            
            selection_label = ui.label("Selected: 0").classes(
                "text-sm text-slate-600 dark:text-slate-400 whitespace-nowrap"
            )
            destroy_state["selection_label"] = selection_label

        # AG Grid with checkbox column for selection
        grid = ui.aggrid({
            "columnDefs": column_defs,
            "rowData": managed_resources,
            "defaultColDef": {
                "sortable": True,
                "filter": True,
                "resizable": True,
            },
            "stopEditingWhenCellsLoseFocus": True,
            "animateRows": False,
            "pagination": True,
            "paginationPageSize": 50,
            "paginationPageSizeSelector": [25, 50, 100, 200],
        }, theme="quartz").classes("w-full ag-theme-quartz-auto-dark").style("height: 400px;")
        # region agent log
        _debug_673991(
            "H3",
            "destroy.py:_create_resource_table",
            "grid instantiated",
            {
                "theme": "quartz",
                "classes": "w-full ag-theme-quartz-auto-dark",
                "initial_rowdata_len": len(grid.options.get("rowData", [])),
                "default_col_def": grid.options.get("defaultColDef", {}),
            },
        )
        # endregion
        
        destroy_state["grid"] = grid
        
        # region agent log
        def on_grid_ready(e):
            _debug_673991(
                "H4",
                "destroy.py:on_grid_ready",
                "grid ready event fired",
                {"event_keys": list(e.args.keys()) if e and e.args else []},
            )

        def on_first_data_rendered(e):
            _debug_673991(
                "H4",
                "destroy.py:on_first_data_rendered",
                "first data rendered event fired",
                {"event_keys": list(e.args.keys()) if e and e.args else []},
            )

        grid.on("gridReady", on_grid_ready)
        grid.on("firstDataRendered", on_first_data_rendered)
        # endregion
        
        # Handle checkbox toggle (cellValueChanged event)
        def on_cell_value_changed(e):
            """Handle when a checkbox is toggled."""
            try:
                if e.args and e.args.get("colId") == "_selected":
                    row_data = e.args.get("data", {})
                    address = row_data.get("address")
                    new_value = e.args.get("newValue", False)
                    
                    if address:
                        # Update the row data in managed_resources
                        for row in managed_resources:
                            if row.get("address") == address:
                                row["_selected"] = new_value
                                break
                        
                        # Update selection set
                        if new_value:
                            destroy_state["selected"].add(address)
                        else:
                            destroy_state["selected"].discard(address)
                        
                        _update_selection_label()
            except Exception as ex:
                print(f"Cell value change error: {ex}")
        
        grid.on("cellValueChanged", on_cell_value_changed)
        
        # Handle cell click for showing details (but not for checkbox column)
        def on_cell_clicked(e):
            """Show resource details when a cell is clicked."""
            if e.args and e.args.get("colId") == "_selected":
                return  # Don't show popup when clicking checkbox
            if e.args and "data" in e.args:
                row = e.args["data"]
                address = row.get("address", "")
                display_name = row.get("display_name", "")
                resource_type = row.get("type", "")
                _show_resource_detail_dialog(state, destroy_state, address, display_name, resource_type)
        
        grid.on("cellClicked", on_cell_clicked)

        ui.label(
            "Select resources to taint or destroy. Click a row for details."
        ).classes("text-xs text-slate-500 mt-2")


def _show_resource_detail_dialog(
    state: AppState,
    destroy_state: dict,
    address: str,
    display_name: str,
    resource_type: str,
) -> None:
    """Show a dialog with full resource state details."""
    state_path = _get_state_file_path(state, destroy_state)
    if not state_path:
        ui.notify("No state file found", type="warning")
        return
    
    # Load and find the specific resource
    try:
        content = Path(state_path).read_text(encoding="utf-8")
        state_data = json.loads(content)
    except Exception as e:
        ui.notify(f"Error loading state: {e}", type="negative")
        return
    
    # Find the resource and instance matching the address
    resource_detail = None
    for resource in state_data.get("resources", []):
        module = resource.get("module", "")
        rtype = resource.get("type", "")
        name = resource.get("name", "")
        
        # Build base address
        if module:
            base_address = f"{module}.{rtype}.{name}"
        else:
            base_address = f"{rtype}.{name}"
        
        # Check if this resource matches
        for inst in resource.get("instances", []):
            index_key = inst.get("index_key")
            if index_key is not None:
                if isinstance(index_key, str):
                    full_address = f'{base_address}["{index_key}"]'
                else:
                    full_address = f"{base_address}[{index_key}]"
            else:
                full_address = base_address
            
            if full_address == address:
                resource_detail = {
                    "address": full_address,
                    "type": rtype,
                    "name": name,
                    "module": module,
                    "mode": resource.get("mode", ""),
                    "provider": resource.get("provider", ""),
                    "index_key": index_key,
                    "attributes": inst.get("attributes", {}),
                    "sensitive_attributes": inst.get("sensitive_attributes", []),
                    "dependencies": inst.get("dependencies", []),
                }
                break
        if resource_detail:
            break
    
    if not resource_detail:
        ui.notify(f"Resource not found: {address}", type="warning")
        return
    
    # Track sensitive visibility state
    viewer_state = {"show_sensitive": False}
    
    # Get attributes and sensitive info
    attributes = resource_detail.get("attributes", {})
    sensitive_attrs = resource_detail.get("sensitive_attributes", [])
    
    # Common sensitive key name patterns
    common_sensitive_patterns = {"token", "password", "secret", "api_key", "private_key", "credentials", "key"}
    
    def is_sensitive_key(key: str) -> bool:
        """Check if a key name suggests sensitive data."""
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in common_sensitive_patterns)
    
    def mask_sensitive_values(obj, show_sensitive: bool):
        """Recursively mask sensitive values in nested structures."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if is_sensitive_key(key) and not show_sensitive:
                    # Mask sensitive keys
                    result[key] = "********"
                elif isinstance(value, (dict, list)):
                    # Recurse into nested structures
                    result[key] = mask_sensitive_values(value, show_sensitive)
                else:
                    result[key] = value
            return result
        elif isinstance(obj, list):
            return [mask_sensitive_values(item, show_sensitive) for item in obj]
        else:
            return obj
    
    def get_display_attrs(show_sensitive: bool) -> dict:
        """Get attributes with sensitive values masked or shown."""
        return mask_sensitive_values(attributes, show_sensitive)
    
    # Create the dialog
    with ui.dialog() as dialog:
        with ui.card().classes("w-full max-h-[90vh] p-6").style("width: 90vw; max-width: 90vw;"):
            # Header
            with ui.row().classes("w-full items-center justify-between mb-4"):
                with ui.column().classes("gap-1"):
                    ui.label(display_name or resource_detail["name"]).classes("text-lg font-semibold")
                    with ui.row().classes("items-center gap-2"):
                        ui.badge(resource_type).props("color=primary outline")
                        if resource_detail.get("module"):
                            ui.label(resource_detail["module"]).classes("text-xs text-slate-500 font-mono")
                ui.button(icon="close", on_click=dialog.close).props("flat round size=sm")
            
            # Full address
            with ui.row().classes("items-center gap-2 mb-4"):
                ui.icon("link", size="xs").classes("text-slate-400")
                ui.label(address).classes("text-xs text-slate-500 font-mono break-all")
            
            # Key Target Resource Details (extracted from attributes)
            key_fields = []
            # Extract important fields from attributes
            if attributes.get("id"):
                key_fields.append(("dbt Cloud ID", str(attributes["id"])))
            if attributes.get("project_id"):
                key_fields.append(("Project ID", str(attributes["project_id"])))
            if attributes.get("environment_id"):
                key_fields.append(("Environment ID", str(attributes["environment_id"])))
            if attributes.get("account_id"):
                key_fields.append(("Account ID", str(attributes["account_id"])))
            if attributes.get("name"):
                key_fields.append(("Name", str(attributes["name"])))
            if attributes.get("dbt_version"):
                key_fields.append(("dbt Version", str(attributes["dbt_version"])))
            if attributes.get("type"):
                key_fields.append(("Type", str(attributes["type"])))
            if attributes.get("state"):
                key_fields.append(("State", str(attributes["state"])))
            if attributes.get("is_active") is not None:
                key_fields.append(("Active", "Yes" if attributes["is_active"] else "No"))
            
            if key_fields:
                with ui.card().classes("w-full mb-4 p-4").style(
                    "background-color: rgba(59, 130, 246, 0.05); border: 1px solid rgba(59, 130, 246, 0.2);"
                ):
                    ui.label("Target Resource Details").classes("text-sm font-semibold mb-3 text-blue-600")
                    with ui.row().classes("w-full gap-6 flex-wrap"):
                        for label, value in key_fields:
                            with ui.column().classes("items-start min-w-[120px]"):
                                ui.label(label).classes("text-xs text-slate-400")
                                ui.label(value).classes("text-sm font-mono")
            
            # Metadata section (provider, mode, dependencies)
            with ui.row().classes("w-full gap-4 mb-4 flex-wrap"):
                if resource_detail.get("provider"):
                    with ui.column().classes("items-start"):
                        ui.label("Provider").classes("text-xs text-slate-400")
                        ui.label(resource_detail["provider"]).classes("text-sm font-mono")
                if resource_detail.get("mode"):
                    with ui.column().classes("items-start"):
                        ui.label("Mode").classes("text-xs text-slate-400")
                        ui.label(resource_detail["mode"]).classes("text-sm")
                if resource_detail.get("dependencies"):
                    with ui.column().classes("items-start"):
                        ui.label("Dependencies").classes("text-xs text-slate-400")
                        ui.label(str(len(resource_detail["dependencies"]))).classes("text-sm")
            
            # Sensitive values toggle - always show since we check recursively
            def has_sensitive_content(obj) -> bool:
                """Check if object contains any sensitive keys."""
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if is_sensitive_key(key):
                            return True
                        if has_sensitive_content(value):
                            return True
                elif isinstance(obj, list):
                    for item in obj:
                        if has_sensitive_content(item):
                            return True
                return False
            
            if has_sensitive_content(attributes) or sensitive_attrs:
                with ui.row().classes("w-full items-center gap-3 p-3 rounded mb-2").style(
                    "background-color: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3);"
                ) as sensitive_banner:
                    ui.icon("visibility_off", size="sm").classes("text-green-600")
                    ui.label("Sensitive values are hidden").classes("text-sm text-green-700 flex-grow")
                    sensitive_toggle = ui.button(
                        "Show Values",
                        icon="visibility",
                    ).props("outline size=sm color=warning")
                
                # Warning banner (hidden by default)
                warning_banner = ui.row().classes("w-full items-center gap-2 p-3 rounded mb-2").style(
                    "background-color: rgba(239, 68, 68, 0.9); display: none;"
                )
                with warning_banner:
                    ui.icon("warning", size="sm").classes("text-white")
                    ui.label("Sensitive values are currently visible. Do not share this screen.").classes(
                        "text-sm text-white flex-grow"
                    )
                    hide_toggle = ui.button(
                        "Hide Values",
                        icon="visibility_off",
                    ).props("size=sm").style("background-color: white; color: #ef4444;")
            
            ui.separator()
            
            # Attributes section (scrollable)
            ui.label("Attributes").classes("text-sm font-semibold mt-2 mb-2")
            
            # Show as formatted JSON (initially masked)
            initial_json = json.dumps(get_display_attrs(False), indent=2, default=str)
            code_element = ui.code(initial_json, language="json").classes("w-full max-h-[400px] overflow-auto")
            
            # Toggle handler (only if we showed the toggle)
            if has_sensitive_content(attributes) or sensitive_attrs:
                def toggle_sensitive(show: bool):
                    viewer_state["show_sensitive"] = show
                    new_json = json.dumps(get_display_attrs(show), indent=2, default=str)
                    code_element.content = new_json
                    code_element.update()
                    if show:
                        sensitive_banner.style("display: none;")
                        warning_banner.style("display: flex; background-color: rgba(239, 68, 68, 0.9);")
                    else:
                        sensitive_banner.style("display: flex;")
                        warning_banner.style("display: none;")
                
                sensitive_toggle.on("click", lambda: toggle_sensitive(True))
                hide_toggle.on("click", lambda: toggle_sensitive(False))
            
            # Dependencies section (if any)
            if resource_detail.get("dependencies"):
                ui.label("Dependencies").classes("text-sm font-semibold mt-4 mb-2")
                with ui.column().classes("gap-1"):
                    for dep in resource_detail["dependencies"][:10]:  # Limit to 10
                        ui.label(dep).classes("text-xs text-slate-500 font-mono")
                    if len(resource_detail["dependencies"]) > 10:
                        ui.label(f"... and {len(resource_detail['dependencies']) - 10} more").classes(
                            "text-xs text-slate-400"
                        )
            
            # Close button
            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Close", on_click=dialog.close).props("outline")
    
    dialog.open()


def _create_destroy_protection_panel(
    state: AppState,
    save_state: Callable[[], None],
    destroy_state: dict,
) -> None:
    """Create a self-contained panel for protected resources with filters, selection, and actions.
    
    This panel displays resources that have lifecycle.prevent_destroy = true
    and provides inline controls for filtering, selecting, and unprotecting them.
    
    Uses AG Grid with checkbox column for reliable selection (same pattern as Select Source page).
    """
    # Look for the generated config YAML in the terraform directory
    tf_path, _yaml_file, _baseline_yaml = resolve_deployment_paths(state)
    
    # Try multiple possible config file names
    possible_paths = [
        tf_path / "dbt-cloud-config.yml",
        tf_path / "dbt_cloud_config.yml",
        tf_path / "config.yml",
    ]
    
    # Also try the map's last_yaml_file as fallback
    if state.map.last_yaml_file:
        possible_paths.append(Path(state.map.last_yaml_file))
    
    yaml_path = None
    for path in possible_paths:
        if path.exists():
            yaml_path = str(path)
            break
    
    if not yaml_path:
        return
    
    try:
        yaml_config = load_yaml_config(yaml_path)
        all_protected_resources = extract_protected_resources(yaml_config)
        # region agent log
        _agent_debug_log(
            "D1",
            "destroy.py:_create_destroy_protection_panel",
            "loaded protected resources from yaml for destroy panel",
            {
                "yaml_path": yaml_path,
                "all_protected_count": len(all_protected_resources),
                "contains_member": any(r.resource_key == "member" for r in all_protected_resources),
                "types": sorted({r.resource_type for r in all_protected_resources}),
                "sample_keys": [r.resource_key for r in all_protected_resources[:10]],
            },
        )
        # endregion
    except Exception:
        return
    
    # Filter out resources that the user has explicitly unprotected via intent
    # Use ProtectionIntentManager for effective protection status
    protection_intent_manager = state.get_protection_intent_manager()
    
    protected_resources = [
        r for r in all_protected_resources
        if protection_intent_manager.get_effective_protection(r.resource_key, yaml_protected=True)
    ]
    # region agent log
    _agent_debug_log(
        "D2",
        "destroy.py:_create_destroy_protection_panel",
        "filtered protected resources via intent manager",
        {
            "filtered_count": len(protected_resources),
            "contains_member": any(r.resource_key == "member" for r in protected_resources),
            "sample_keys": [r.resource_key for r in protected_resources[:10]],
        },
    )
    # endregion
    
    if not protected_resources:
        return
    
    # Type mappings
    type_labels = {
        "PRJ": "Project",
        "ENV": "Environment",
        "PRF": "Profile",
        "JOB": "Job",
        "JCTG": "Job Completion Trigger",
        "JEVO": "Env Var Job Override",
        "REP": "Repository",
        "CON": "Connection",
        "EXTATTR": "Extended Attributes",
        "ACFT": "Account Features",
        "IPRST": "IP Restrictions Rule",
        "LNGI": "Lineage Integration",
        "OAUTH": "OAuth Configuration",
        "PARFT": "Project Artefacts",
        "USRGRP": "User Groups",
        "SLCFG": "Semantic Layer Config",
        "SLSTM": "SL Credential Mapping",
    }
    
    # Terraform address mapping for protected resources
    tf_type_map = {
        "PRJ": "dbtcloud_project",
        "ENV": "dbtcloud_environment",
        "PRF": "dbtcloud_profile",
        "JOB": "dbtcloud_job",
        "JCTG": "dbtcloud_job_completion_trigger",
        "JEVO": "dbtcloud_environment_variable_job_override",
        "REP": "dbtcloud_repository",
        "CON": "dbtcloud_connection",
        "EXTATTR": "dbtcloud_extended_attributes",
        "ACFT": "dbtcloud_account_features",
        "IPRST": "dbtcloud_ip_restrictions_rule",
        "LNGI": "dbtcloud_lineage_integration",
        "OAUTH": "dbtcloud_oauth_configuration",
        "PARFT": "dbtcloud_project_artefacts",
        "USRGRP": "dbtcloud_user_groups",
        "SLCFG": "dbtcloud_semantic_layer_configuration",
        "SLSTM": "dbtcloud_semantic_layer_credential_service_token_mapping",
    }
    
    # Build rows for the grid with _selected column for checkbox state
    protected_rows = []
    for res in protected_resources:
        type_label = type_labels.get(res.resource_type, res.resource_type)
        tf_type = tf_type_map.get(res.resource_type, f"dbtcloud_{res.resource_type.lower()}")
        protected_rows.append({
            "key": f"{res.resource_type}_{res.name}",
            "type": type_label,
            "type_code": res.resource_type,
            "name": res.name,
            "id": getattr(res, "resource_id", ""),
            "tf_address": f"{tf_type}.protected_{res.name}",
            "_selected": False,  # Checkbox state
        })
    
    # Pre-sort data by name (per AG Grid standards - no default sort via AG Grid)
    protected_rows = sorted(protected_rows, key=lambda x: x.get("name", ""))
    
    # Store all rows for filtering
    all_protected_rows = protected_rows.copy()
    
    # Panel state for filters, grid reference, and selection tracking
    panel_state = {
        "type": "all",
        "search": "",
        "grid": None,
        "selected_keys": set(),  # Track selected row keys
    }
    
    # Count resources by type for filter dropdown
    type_counts = {}
    for r in protected_rows:
        t = r.get("type_code", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    
    # Build type filter options
    type_options = {"all": f"All Types ({len(protected_rows)})"}
    for t in sorted(type_counts.keys()):
        display_name = type_labels.get(t, t)
        type_options[t] = f"{display_name}s ({type_counts[t]})"
    
    # Capture references for button handlers
    _protected_res = protected_resources
    _state = state
    _save_fn = save_state
    
    # Full-width card for protected resources panel
    with ui.card().classes("w-full").style("border-left: 4px solid #3B82F6;"):
        # Header row with icon, title, count, and badge
        with ui.row().classes("w-full items-center gap-3 mb-2"):
            ui.icon("shield", size="md").classes("text-blue-500")
            ui.label(f"Protected Resources ({len(protected_resources)})").classes("font-semibold")
            resource_badge = ui.badge("Will be SKIPPED").props("color=blue outline")
            panel_state["badge"] = resource_badge
        
        # Info text
        ui.label(
            "These resources have lifecycle.prevent_destroy = true and will be preserved during destroy operations."
        ).classes("text-xs text-slate-500 mb-3")
        
        # Helper to get selected keys from row data
        def get_selected_keys():
            return {r["key"] for r in all_protected_rows if r.get("_selected", False)}
        
        # Helper to get selected count
        def get_selected_count():
            return sum(1 for r in all_protected_rows if r.get("_selected", False))
        
        # Helper to update the grid with AG Grid quick filter (not local filtering)
        def update_grid_filter():
            grid = panel_state.get("grid")
            if not grid:
                return
            
            # Use AG Grid's quick filter for search
            search_term = panel_state.get("search", "")
            grid.run_grid_method('setGridOption', 'quickFilterText', search_term)
            
            # For type filter, we need to update rowData since AG Grid quick filter
            # doesn't support complex type filtering - filter the data and update
            if panel_state["type"] != "all":
                filtered = [r for r in all_protected_rows if r.get("type_code") == panel_state["type"]]
                grid.options["rowData"] = filtered
                grid.update()
            else:
                grid.options["rowData"] = all_protected_rows
                grid.update()
            
            # Update badge
            badge = panel_state.get("badge")
            if badge:
                if panel_state["type"] == "all" and not panel_state["search"]:
                    badge.set_text("Will be SKIPPED")
                else:
                    visible_count = len([r for r in all_protected_rows if r.get("type_code") == panel_state["type"]]) if panel_state["type"] != "all" else len(all_protected_rows)
                    badge.set_text(f"{visible_count} shown / {len(all_protected_rows)} total")
        
        # Helper to select all visible rows (checkbox pattern)
        def select_all_protected():
            grid = panel_state.get("grid")
            if not grid:
                return
            filtered_keys = {r["key"] for r in (
                [r for r in all_protected_rows if r.get("type_code") == panel_state["type"]]
                if panel_state["type"] != "all" else all_protected_rows
            )}
            for row in all_protected_rows:
                if row["key"] in filtered_keys:
                    row["_selected"] = True
            grid.options["rowData"] = all_protected_rows if panel_state["type"] == "all" else [r for r in all_protected_rows if r.get("type_code") == panel_state["type"]]
            grid.update()
            _update_selection_label()
        
        # Helper to clear selection (checkbox pattern)
        def clear_protected_selection():
            grid = panel_state.get("grid")
            if not grid:
                return
            for row in all_protected_rows:
                row["_selected"] = False
            grid.options["rowData"] = all_protected_rows if panel_state["type"] == "all" else [r for r in all_protected_rows if r.get("type_code") == panel_state["type"]]
            grid.update()
            _update_selection_label()
        
        # Helper to update selection label
        def _update_selection_label():
            label = panel_state.get("selection_label")
            count = get_selected_count()
            if label:
                label.set_text(f"Selected: {count}")
            # Update unprotect selected button
            btn = panel_state.get("unprotect_selected_btn")
            if btn:
                btn.set_text(f"Unprotect Selected ({count})")
                if count > 0:
                    btn.enable()
                else:
                    btn.disable()
        
        # Export CSV handler
        def export_protected_csv():
            grid = panel_state.get("grid")
            if grid:
                grid.run_grid_method('exportDataAsCsv', {
                    'fileName': 'protected_resources.csv',
                    'columnSeparator': ',',
                })
        
        # Unprotect selected handler
        def on_unprotect_selected():
            # Get selected keys from row data (authoritative source)
            selected_keys = get_selected_keys()
            
            if not selected_keys:
                ui.notify("No resources selected", type="warning")
                return
            
            # Find matching resources by their display key and get the resource_key
            keys_to_unprotect = set()
            for res in protected_resources:
                display_key = f"{res.resource_type}_{res.name}"
                if display_key in selected_keys:
                    keys_to_unprotect.add(res.resource_key)
            
            if not keys_to_unprotect:
                ui.notify("No matching protected resources found", type="warning")
                return
            
            # Use ProtectionIntentManager to record unprotect intent
            protection_intent = state.get_protection_intent_manager()
            for key in keys_to_unprotect:
                protection_intent.set_intent(
                    key=key,
                    protected=False,
                    source="destroy_unprotect_selected",
                    reason="Unprotected from Destroy page selection",
                )
            protection_intent.save()
            
            # Log the action
            log_action("on_unprotect_selected", "executed", {
                "keys_to_unprotect": list(keys_to_unprotect),
                "source": "destroy_page",
            })
            
            save_state()
            
            # Notify user to apply changes on Match page
            ui.notify(
                f"Intent recorded for {len(keys_to_unprotect)} resources - click 'Generate Protection Changes' on Match page to apply",
                type="positive",
            )
            
            # Helper to generate moved blocks and navigate to deploy
            def generate_and_go_to_deploy():
                """Generate moved blocks for the unprotected resources and navigate to Deploy.
                
                This follows the same workflow as Match page:
                1. Apply intents to YAML (remove protected: true)
                2. Generate protection_moves.tf from state comparison
                """
                from importer.web.utils.protection_manager import (
                    detect_protection_mismatches,
                    write_moved_blocks_file,
                    ProtectionChange,
                    generate_moved_blocks_from_state,
                )
                
                # Get terraform directory
                tf_path, _yaml_file, _baseline_yaml = resolve_deployment_paths(state)
                
                if not tf_path.exists():
                    ui.notify(f"Terraform directory not found: {tf_path}", type="negative")
                    return
                
                # Step 1: Apply intents to YAML (remove protected: true for unprotected resources)
                yaml_file = tf_path / "dbt-cloud-config.yml"
                if yaml_file.exists():
                    from importer.web.utils.adoption_yaml_updater import apply_unprotection_from_set
                    apply_unprotection_from_set(str(yaml_file), set(keys_to_unprotect))
                    
                    # Mark intents as applied to YAML
                    protection_intent = state.get_protection_intent_manager()
                    protection_intent.mark_applied_to_yaml(set(keys_to_unprotect))
                    protection_intent.save()
                    
                    ui.notify(f"Updated YAML: removed protection from {len(keys_to_unprotect)} resource(s)", type="info")
                else:
                    ui.notify(f"Warning: YAML file not found: {yaml_file}", type="warning")
                
                # Step 2: Generate moved blocks by comparing YAML to TF state
                state_file = tf_path / "terraform.tfstate"
                if state_file.exists() and yaml_file.exists():
                    from importer.web.utils.protection_manager import load_yaml_config
                    
                    yaml_config = load_yaml_config(str(yaml_file))
                    changes = generate_moved_blocks_from_state(yaml_config, str(state_file))
                    
                    if changes:
                        output_file = write_moved_blocks_file(
                            changes,
                            tf_path,
                            filename="protection_moves.tf",
                            preserve_existing=False,
                        )
                        
                        if output_file:
                            ui.notify(f"Generated {len(changes)} moved block(s) → {output_file.name}", type="positive")
                            next_steps_dialog.close()
                            ui.navigate.to("/deploy")
                        else:
                            ui.notify("Failed to write moved blocks file", type="negative")
                    else:
                        ui.notify("No moved blocks needed - state already matches YAML", type="info")
                        next_steps_dialog.close()
                        ui.navigate.to("/deploy")
                else:
                    # Fallback to old direct approach if no state file
                    module_prefix = "module.dbt_cloud.module.projects_v2[0]"
                    changes = []
                    
                    RESOURCE_TYPE_MAP = {
                        "PRJ": ("dbtcloud_project", "projects", "protected_projects"),
                        "REP": ("dbtcloud_repository", "repositories", "protected_repositories"),
                        "PREP": ("dbtcloud_project_repository", "project_repositories", "protected_project_repositories"),
                        "ENV": ("dbtcloud_environment", "environments", "protected_environments"),
                        "PRF": ("dbtcloud_profile", "profiles", "protected_profiles"),
                        "JOB": ("dbtcloud_job", "jobs", "protected_jobs"),
                        "JCTG": ("dbtcloud_job_completion_trigger", "job_completion_triggers", "protected_job_completion_triggers"),
                        "JEVO": ("dbtcloud_environment_variable_job_override", "environment_variable_job_overrides", "protected_environment_variable_job_overrides"),
                        "EXTATTR": ("dbtcloud_extended_attributes", "extended_attrs", "protected_extended_attrs"),
                        "GC": ("dbtcloud_global_connection", "global_connections", "protected_global_connections"),
                    }
                    
                    for key in keys_to_unprotect:
                        for res in protected_resources:
                            if res.resource_key == key:
                                resource_type = res.resource_type
                                resource_name = res.name
                                if resource_type in RESOURCE_TYPE_MAP:
                                    tf_type, unprotected, protected = RESOURCE_TYPE_MAP[resource_type]
                                    from_addr = f'{module_prefix}.{tf_type}.{protected}["{key}"]'
                                    to_addr = f'{module_prefix}.{tf_type}.{unprotected}["{key}"]'
                                    changes.append(ProtectionChange(
                                        resource_key=key,
                                        resource_type=resource_type,
                                        name=resource_name,
                                        direction="unprotect",
                                        from_address=from_addr,
                                        to_address=to_addr,
                                    ))
                                break
                    
                    if changes:
                        output_file = write_moved_blocks_file(
                            changes,
                            tf_path,
                            filename="protection_moves.tf",
                            preserve_existing=False,
                        )
                        if output_file:
                            ui.notify(f"Generated {len(changes)} moved block(s) → {output_file.name}", type="positive")
                            next_steps_dialog.close()
                            ui.navigate.to("/deploy")
                    else:
                        ui.notify("No protection changes to generate", type="warning")
            
            # Show dialog with clear next steps
            with ui.dialog() as next_steps_dialog, ui.card().style("width: 600px; max-width: 90vw;"):
                with ui.row().classes("items-center gap-3 mb-4"):
                    ui.icon("shield_outlined", size="lg").classes("text-amber-600")
                    ui.label(f"Unprotected {len(keys_to_unprotect)} Resource(s)").classes("text-xl font-bold text-amber-700")
                
                ui.separator()
                
                ui.markdown("""
**What happened:** The resource(s) have been marked as unprotected in your YAML configuration.

**What's next:** To complete the unprotection in Terraform state:
""").classes("text-sm")
                
                # Quick action option
                with ui.card().classes("w-full p-3 my-3").style("background: #ECFDF5; border: 1px solid #10B981;"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("bolt", size="sm").classes("text-green-600")
                        ui.label("Quick Option").classes("font-bold text-green-700")
                    ui.label(
                        "Generate moved blocks now and go directly to Deploy to run terraform apply."
                    ).classes("text-sm text-green-700 mt-1")
                    ui.button(
                        "Generate & Go to Deploy",
                        icon="play_arrow",
                        on_click=generate_and_go_to_deploy,
                    ).props("color=positive").classes("mt-2")
                
                ui.label("— OR —").classes("text-center text-slate-400 text-xs my-2")
                
                # Manual steps option
                with ui.expansion("Manual Steps", icon="list").classes("w-full"):
                    with ui.column().classes("gap-3 py-2"):
                        with ui.row().classes("items-start gap-3"):
                            ui.badge("1", color="amber").classes("mt-0.5")
                            with ui.column().classes("gap-1"):
                                ui.label("Generate Moved Blocks").classes("font-semibold")
                                ui.label("Go to Match Resources → Protection Mismatch panel → 'Unprotect All'").classes("text-xs text-slate-500")
                        
                        with ui.row().classes("items-start gap-3"):
                            ui.badge("2", color="amber").classes("mt-0.5")
                            with ui.column().classes("gap-1"):
                                ui.label("Apply Changes").classes("font-semibold")
                                ui.label("Go to Deploy → Run 'terraform plan' then 'terraform apply'").classes("text-xs text-slate-500")
                
                ui.markdown("""
⚠️ **Until terraform apply completes**, the resource remains protected and **cannot be destroyed**.
""").classes("text-sm text-amber-700 bg-amber-50 p-3 rounded mt-3")
                
                ui.separator().classes("my-3")
                
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Stay Here", on_click=lambda: (next_steps_dialog.close(), ui.navigate.reload())).props("flat")
                    ui.button(
                        "Go to Match Resources",
                        icon="arrow_forward",
                        on_click=lambda: (next_steps_dialog.close(), ui.navigate.to("/match")),
                    ).props("outline")
            
            next_steps_dialog.open()
        
        # Action buttons row (above filters)
        with ui.row().classes("w-full items-center gap-2 mb-3 flex-wrap"):
            ui.button(
                "Select All",
                icon="select_all",
                on_click=select_all_protected,
            ).props("outline size=sm padding='4px 12px'")
            
            ui.button(
                "Clear",
                icon="close",
                on_click=clear_protected_selection,
            ).props("outline size=sm padding='4px 12px'")
            
            ui.separator().props("vertical").classes("mx-1")
            
            # Unprotect Selected button (amber, black text)
            unprotect_selected_btn = ui.button(
                "Unprotect Selected (0)",
                icon="lock_open",
                on_click=on_unprotect_selected,
            ).props("color=amber size=sm padding='4px 12px'").style("color: black !important;")
            unprotect_selected_btn.disable()
            panel_state["unprotect_selected_btn"] = unprotect_selected_btn
            
            # Unprotect All button
            ui.button(
                "Unprotect All",
                icon="lock_open",
                on_click=lambda pr=_protected_res, st=_state, sf=_save_fn: _show_destroy_unprotection_dialog(pr, st, sf),
            ).props("color=amber size=sm padding='4px 12px'").style("color: black !important;")
            
            ui.space()
            
            # Export CSV button
            ui.button(
                "Export CSV",
                icon="download",
                on_click=export_protected_csv,
            ).props("outline size=sm padding='4px 12px'")
        
        # Filter handlers
        def on_type_change(e):
            new_value = e.value if e.value else "all"
            panel_state["type"] = new_value
            update_grid_filter()
        
        def on_search_change(e):
            new_value = e.value if e.value else ""
            panel_state["search"] = new_value
            update_grid_filter()
        
        # Filter row: Type dropdown | Search input | Selection counter
        with ui.row().classes("w-full items-center gap-3 mb-3"):
            ui.select(
                options=type_options,
                value="all",
                label="Filter by Type",
                on_change=on_type_change,
            ).props("outlined dense").classes("min-w-[180px]")
            
            ui.input(
                placeholder="Search by name or ID...",
                on_change=on_search_change,
            ).props("outlined dense clearable").classes("flex-grow min-w-[200px]")
            
            selection_label = ui.label("Selected: 0").classes(
                "text-sm text-slate-600 dark:text-slate-400 whitespace-nowrap"
            )
            panel_state["selection_label"] = selection_label
        
        # AG Grid column definitions with explicit colId (per standards)
        column_defs = [
            {
                "field": "_selected",
                "colId": "_selected",
                "headerName": "✓",
                "width": 50,
                "pinned": "left",
                "cellRenderer": "agCheckboxCellRenderer",
                "editable": True,
                "cellStyle": {"textAlign": "center"},
            },
            {
                "field": "type",
                "colId": "type",
                "headerName": "Type",
                "width": 100,
                "sortable": True,
                "filter": "agTextColumnFilter",
            },
            {
                "field": "name",
                "colId": "name",
                "headerName": "Name",
                "width": 200,
                "sortable": True,
                "filter": "agTextColumnFilter",
            },
            {
                "field": "id",
                "colId": "id",
                "headerName": "ID",
                "width": 100,
                "filter": "agTextColumnFilter",
            },
        ]
        
        # AG Grid with checkbox column for selection
        protected_grid = ui.aggrid({
            "columnDefs": column_defs,
            "rowData": protected_rows,
            "pagination": False,
            "headerHeight": 36,
            "defaultColDef": {
                "resizable": True,
                "sortable": True,
                "filter": True,
            },
            "stopEditingWhenCellsLoseFocus": True,
            "animateRows": False,
        }, theme="quartz").classes("w-full ag-theme-quartz-auto-dark").style("height: 200px;")
        
        panel_state["grid"] = protected_grid
        
        # Handle checkbox toggle (cellValueChanged event)
        def on_cell_value_changed(e):
            """Handle when a checkbox is toggled."""
            try:
                if e.args and e.args.get("colId") == "_selected":
                    row_data = e.args.get("data", {})
                    row_key = row_data.get("key")
                    new_value = e.args.get("newValue", False)
                    
                    if row_key:
                        # Update the authoritative row data in all_protected_rows
                        for row in all_protected_rows:
                            if row["key"] == row_key:
                                row["_selected"] = new_value
                                break
                        
                        _update_selection_label()
            except Exception as ex:
                print(f"Cell value change error: {ex}")
        
        protected_grid.on("cellValueChanged", on_cell_value_changed)
        
        # Row click shows protected resource detail popup (but not for checkbox column)
        def on_cell_clicked(e):
            """Handle cell click - show details unless clicking checkbox."""
            if e.args and e.args.get("colId") == "_selected":
                return  # Don't show popup when clicking checkbox
            if e.args and "data" in e.args:
                row = e.args["data"]
                _show_protected_resource_dialog(row)
        
        protected_grid.on("cellClicked", on_cell_clicked)
        
        ui.label(
            "Click a row to view details. Check resources and click 'Unprotect Selected' to remove protection."
        ).classes("text-xs text-slate-500 mt-2")


def _create_protection_repair_panel(
    state: AppState,
    save_state: Callable[[], None],
    destroy_state: dict,
    terminal: TerminalOutput,
) -> None:
    """Create a panel to detect and repair protection mismatches.
    
    This panel detects when the protection status in the YAML config doesn't match
    the Terraform state (e.g., resource is protected in state but not in YAML),
    and offers to generate/repair the moved blocks file.
    """
    terraform_dir, _yaml_file, _baseline_yaml = resolve_deployment_paths(state)
    
    # Find YAML config file
    possible_paths = [
        terraform_dir / "dbt-cloud-config.yml",
        terraform_dir / "dbt_cloud_config.yml",
        terraform_dir / "config.yml",
    ]
    if state.map.last_yaml_file:
        possible_paths.append(Path(state.map.last_yaml_file))
    
    yaml_path = None
    for path in possible_paths:
        if path.exists():
            yaml_path = path
            break
    
    # Check if state file exists
    state_file = terraform_dir / "terraform.tfstate"
    if not yaml_path or not state_file.exists():
        return  # Can't detect mismatches without both files
    
    # Detect mismatches
    try:
        repair_result = detect_and_repair_protection_mismatches(
            yaml_path=yaml_path,
            terraform_dir=terraform_dir,
            auto_repair=False,  # Don't auto-repair, let user confirm
        )
    except Exception as e:
        # Silent failure - don't show panel if detection fails
        return
    
    if not repair_result.mismatches:
        return  # No mismatches to show
    
    # Panel state for UI updates
    panel_state = {"expanded": False}
    
    with ui.card().classes("w-full").style("border-left: 4px solid #F59E0B;"):
        # Header with warning
        with ui.row().classes("w-full items-center gap-3 mb-2"):
            ui.icon("warning", size="md").classes("text-amber-500")
            ui.label(f"Protection Mismatch Detected ({len(repair_result.mismatches)})").classes(
                "font-semibold text-amber-600"
            )
            ui.badge("Needs Repair").props("color=amber outline")
        
        # Explanation
        ui.label(
            "The Terraform state has resources in different protection blocks than the YAML config expects. "
            "This typically happens when protection status was changed but the moved blocks weren't updated correctly."
        ).classes("text-xs text-slate-500 mb-3")
        
        # Show mismatch summary
        with ui.expansion("View Mismatches", icon="list").classes("w-full mb-3"):
            type_names = {
                "PRJ": "Project",
                "REP": "Repository",
                "PREP": "Project-Repo Link",
            }
            
            # Group by project key
            by_project = {}
            for m in repair_result.mismatches:
                if m.resource_key not in by_project:
                    by_project[m.resource_key] = []
                by_project[m.resource_key].append(m)
            
            for project_key, project_mismatches in sorted(by_project.items()):
                yaml_status = "protected" if project_mismatches[0].yaml_protected else "unprotected"
                
                with ui.card().classes("w-full p-3 mb-2").style(
                    "background-color: rgba(245, 158, 11, 0.1);"
                ):
                    with ui.row().classes("items-center gap-2 mb-1"):
                        ui.icon("folder", size="xs").classes("text-amber-600")
                        ui.label(project_key).classes("font-semibold text-sm")
                    
                    # Separate PRJ from REP+PREP (they have different linkage)
                    prj_mismatches = [m for m in project_mismatches if m.resource_type == "PRJ"]
                    repo_mismatches = [m for m in project_mismatches if m.resource_type in ("REP", "PREP")]
                    
                    # Show project mismatch (independent)
                    if prj_mismatches:
                        prj = prj_mismatches[0]
                        state_status = "protected" if prj.state_protected else "unprotected"
                        with ui.row().classes("items-center gap-2 mb-1"):
                            ui.badge("Project").props("color=primary outline")
                            ui.label(f"State: {state_status}").classes("text-xs text-slate-500")
                            ui.icon("arrow_forward", size="xs").classes("text-amber-500")
                            ui.label(f"Move to {yaml_status}").classes("text-xs text-amber-600")
                            ui.label("(independent)").classes("text-xs text-slate-400 italic")
                    
                    # Show repository mismatches (linked together)
                    if repo_mismatches:
                        rep_m = next((m for m in repo_mismatches if m.resource_type == "REP"), None)
                        state_status = "protected" if rep_m and rep_m.state_protected else "unprotected"
                        with ui.row().classes("items-center gap-2"):
                            ui.badge("Repository").props("color=grey outline")
                            ui.label("+").classes("text-xs text-slate-400")
                            ui.badge("Project-Repo Link").props("color=grey outline")
                            ui.label(f"State: {state_status}").classes("text-xs text-slate-500")
                            ui.icon("arrow_forward", size="xs").classes("text-amber-500")
                            ui.label(f"Move to {yaml_status}").classes("text-xs text-amber-600")
                            ui.label("(linked)").classes("text-xs text-slate-400 italic")
        
        # Show generated moved blocks preview
        if repair_result.moved_blocks_content:
            with ui.expansion("Preview Repair (protection_moves.tf)", icon="code").classes("w-full mb-3"):
                ui.code(repair_result.moved_blocks_content, language="hcl").classes(
                    "w-full max-h-[200px] overflow-auto"
                )
        
        # Action buttons
        with ui.row().classes("w-full items-center gap-3"):
            async def apply_repair():
                """Apply the repair by writing the moved blocks file."""
                repair_path = terraform_dir / "protection_moves.tf"
                try:
                    repair_path.write_text(repair_result.moved_blocks_content, encoding="utf-8")
                    terminal.success(f"✅ Wrote protection repair to {repair_path}")
                    terminal.info("")
                    terminal.info("Next steps:")
                    terminal.info("  1. Run 'terraform plan' to verify the moves")
                    terminal.info("  2. Run 'terraform apply' to apply the state moves")
                    terminal.info("  3. After successful apply, you can delete protection_moves.tf")
                    ui.notify(
                        f"Repair written to protection_moves.tf. Run terraform plan to verify.",
                        type="positive",
                        timeout=6000,
                    )
                    # Reload to refresh the panel
                    ui.navigate.reload()
                except Exception as e:
                    terminal.error(f"Failed to write repair file: {e}")
                    ui.notify(f"Failed to write repair: {e}", type="negative")
            
            ui.button(
                "Apply Repair",
                icon="build",
                on_click=apply_repair,
            ).props("color=amber").style("color: black !important;")
            
            async def run_init():
                """Run terraform init to initialize the workspace."""
                terminal.clear()
                terminal.set_title("Output — TERRAFORM INIT")
                terminal.info("Running terraform init...")
                terminal.info("")
                
                env = _get_terraform_env(state)
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["terraform", "init", "-no-color"],
                    cwd=str(terraform_dir),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                
                _emit_bounded_output(
                    terminal,
                    phase_name="init",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    stdout_budget=OutputBudget(max_lines=600, head_lines=360, tail_lines=180),
                    stderr_budget=OutputBudget(max_lines=220, head_lines=140, tail_lines=60),
                    on_stdout_line=lambda line: (
                        terminal.success(line)
                        if "Terraform has been successfully initialized" in line
                        else terminal.info(line)
                    ),
                    on_stderr_line=lambda line: (
                        terminal.error(line)
                        if "Error:" in line or "error:" in line.lower()
                        else terminal.warning(line)
                        if "Warning:" in line
                        else terminal.info(line)
                    ),
                )
                
                if result.returncode == 0:
                    ui.notify("Terraform initialized successfully!", type="positive")
                else:
                    ui.notify("Init failed - see output for details", type="negative")
            
            ui.button(
                "Init",
                icon="downloading",
                on_click=run_init,
            ).props("outline")
            
            async def run_validate():
                """Run terraform validate to check for other errors."""
                terminal.clear()
                terminal.set_title("Output — TERRAFORM VALIDATE")
                terminal.info("Running terraform validate...")
                terminal.info("")
                
                env = _get_terraform_env(state)
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["terraform", "validate", "-no-color"],
                    cwd=str(terraform_dir),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                
                _emit_bounded_output(
                    terminal,
                    phase_name="validate",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    stdout_budget=OutputBudget(max_lines=420, head_lines=260, tail_lines=120),
                    stderr_budget=OutputBudget(max_lines=220, head_lines=140, tail_lines=60),
                    on_stdout_line=lambda line: (
                        terminal.success(line) if "Success" in line else terminal.info(line)
                    ),
                    on_stderr_line=lambda line: (
                        terminal.error(line)
                        if "Error:" in line or "error:" in line.lower()
                        else terminal.warning(line)
                        if "Warning:" in line
                        else terminal.info(line)
                    ),
                )
                
                if result.returncode == 0:
                    ui.notify("Validation passed!", type="positive")
                else:
                    ui.notify("Validation failed - see output for details", type="warning")
            
            ui.button(
                "Validate",
                icon="check_circle",
                on_click=run_validate,
            ).props("outline")
            
            async def run_plan():
                """Run terraform plan to preview the changes."""
                from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                
                terminal.clear()
                terminal.set_title("Output — TERRAFORM PLAN")
                terminal.info("Running terraform plan...")
                terminal.info("")
                
                env = _get_terraform_env(state)
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["terraform", "plan", "-no-color"],
                    cwd=str(terraform_dir),
                    capture_output=True,
                    text=True,
                    env=env,
                )
                
                # Store the raw plan output
                plan_output = result.stdout + result.stderr
                
                # Also show in terminal for quick reference
                _emit_bounded_output(
                    terminal,
                    phase_name="plan",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    stdout_budget=OutputBudget(max_lines=900, head_lines=520, tail_lines=320),
                    stderr_budget=OutputBudget(max_lines=300, head_lines=180, tail_lines=80),
                    on_stdout_line=lambda line: (
                        terminal.success(line)
                        if "Plan:" in line or "Changes to Outputs:" in line or "No changes" in line
                        else terminal.warning(line)
                        if "will be" in line.lower()
                        and (
                            "created" in line.lower()
                            or "destroyed" in line.lower()
                            or "changed" in line.lower()
                        )
                        else terminal.info(line)
                    ),
                    on_stderr_line=lambda line: (
                        terminal.error(line)
                        if "Error:" in line or "error:" in line.lower()
                        else terminal.warning(line)
                        if "Warning:" in line
                        else terminal.info(line)
                    ),
                )
                
                if result.returncode == 0:
                    ui.notify("Plan completed - opening full-screen view", type="positive")
                    # Open the full-screen plan viewer dialog
                    dialog = create_plan_viewer_dialog(plan_output, "Protection Repair Plan")
                    dialog.open()
                else:
                    ui.notify("Plan failed - see output for details", type="negative")
            
            ui.button(
                "Plan",
                icon="preview",
                on_click=run_plan,
            ).props("outline color=primary")
            
            async def run_apply():
                """Run terraform apply with auto-approve."""
                # Confirm before applying
                with ui.dialog() as confirm_dialog, ui.card().style("width: 450px;"):
                    ui.label("Confirm Apply").classes("text-xl font-bold mb-3")
                    ui.label(
                        "This will apply the protection moves to Terraform state. "
                        "Make sure you've reviewed the plan first."
                    ).classes("text-sm text-slate-600 mb-4")
                    
                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                        
                        async def do_apply():
                            confirm_dialog.close()
                            terminal.clear()
                            terminal.set_title("Output — TERRAFORM APPLY")
                            terminal.info("Running terraform apply -auto-approve...")
                            terminal.info("")
                            
                            env = _get_terraform_env(state)
                            result = await asyncio.to_thread(
                                subprocess.run,
                                ["terraform", "apply", "-auto-approve", "-no-color"],
                                cwd=str(terraform_dir),
                                capture_output=True,
                                text=True,
                                env=env,
                            )
                            
                            _emit_bounded_output(
                                terminal,
                                phase_name="apply",
                                stdout=result.stdout,
                                stderr=result.stderr,
                                stdout_budget=OutputBudget(max_lines=900, head_lines=520, tail_lines=320),
                                stderr_budget=OutputBudget(max_lines=300, head_lines=180, tail_lines=80),
                                on_stdout_line=lambda line: (
                                    terminal.success(line)
                                    if "Apply complete" in line or "Resources:" in line
                                    else terminal.info(line)
                                ),
                                on_stderr_line=lambda line: (
                                    terminal.error(line)
                                    if "Error:" in line or "error:" in line.lower()
                                    else terminal.warning(line)
                                    if "Warning:" in line
                                    else terminal.info(line)
                                ),
                            )
                            
                            if result.returncode == 0:
                                ui.notify("Apply completed successfully! Protection moves applied.", type="positive", timeout=6000)
                                terminal.success("")
                                terminal.success("✅ Protection moves applied successfully!")
                                terminal.info("The protection_moves.tf file can now be deleted if desired.")
                                # Reload to refresh the panel (mismatch should be resolved)
                                await asyncio.sleep(1)
                                ui.navigate.reload()
                            else:
                                ui.notify("Apply failed - see output for details", type="negative")
                        
                        ui.button("Apply", icon="rocket_launch", on_click=do_apply).props("color=primary")
                
                confirm_dialog.open()
            
            ui.button(
                "Apply",
                icon="rocket_launch",
                on_click=run_apply,
            ).props("color=positive")
            
            # Spacer to push AI Debug button to far right
            ui.space()
            
            def show_ai_debug():
                """Show AI debugging summary dialog."""
                # Build diagnostic report
                lines = [
                    "# Protection Mismatch Debug Report",
                    "",
                    f"**Generated**: {__import__('datetime').datetime.now().isoformat()}",
                    f"**Terraform Dir**: `{terraform_dir}`",
                    f"**YAML Config**: `{yaml_path}`",
                    "",
                    "## Summary",
                    f"- **Total Mismatches**: {len(repair_result.mismatches)}",
                    "",
                    "## Mismatches by Project",
                    "",
                ]
                
                # Group by project key
                by_project = {}
                for m in repair_result.mismatches:
                    if m.resource_key not in by_project:
                        by_project[m.resource_key] = []
                    by_project[m.resource_key].append(m)
                
                type_names = {
                    "PRJ": "Project",
                    "REP": "Repository", 
                    "PREP": "Project-Repo Link",
                }
                
                for project_key, mismatches in sorted(by_project.items()):
                    yaml_status = "protected" if mismatches[0].yaml_protected else "unprotected"
                    state_status = "protected" if mismatches[0].state_protected else "unprotected"
                    direction = mismatches[0].move_direction
                    
                    lines.append(f"### `{project_key}`")
                    lines.append("")
                    lines.append(f"**YAML says**: {yaml_status}")
                    lines.append(f"**State has**: {state_status}")
                    lines.append(f"**Action needed**: Move to {direction}ed collection")
                    lines.append("")
                    lines.append("**Resources affected:**")
                    
                    for m in mismatches:
                        type_name = type_names.get(m.resource_type, m.resource_type)
                        lines.append(f"- **{type_name}** (`{m.resource_type}`)")
                        lines.append(f"  - Current: `{m.state_address}`")
                        lines.append(f"  - Expected: `{m.expected_address}`")
                    lines.append("")
                
                lines.append("## Root Cause Analysis")
                lines.append("")
                lines.append("Protection mismatches occur when:")
                lines.append("1. The `protected: true/false` flag in YAML config was changed")
                lines.append("2. But the Terraform state still has resources in the old collection")
                lines.append("3. Without `moved` blocks, Terraform sees these as different resources")
                lines.append("")
                lines.append("## Resolution")
                lines.append("")
                lines.append("1. Click **Apply Repair** to generate `protection_moves.tf`")
                lines.append("2. Run **Init** to reinitialize Terraform")
                lines.append("3. Run **Plan** to verify the moves (should show 0 add, 0 destroy)")
                lines.append("4. Run **Apply** to execute the state moves")
                lines.append("5. After successful apply, the `protection_moves.tf` file can be deleted")
                lines.append("")
                lines.append("## Raw Mismatch Data")
                lines.append("")
                lines.append("```python")
                for m in repair_result.mismatches:
                    lines.append(f"ProtectionMismatch(")
                    lines.append(f"    resource_key='{m.resource_key}',")
                    lines.append(f"    resource_type='{m.resource_type}',")
                    lines.append(f"    yaml_protected={m.yaml_protected},")
                    lines.append(f"    state_protected={m.state_protected},")
                    lines.append(f"    state_address='{m.state_address}',")
                    lines.append(f"    expected_address='{m.expected_address}',")
                    lines.append(f")")
                lines.append("```")
                
                if repair_result.moved_blocks_content:
                    lines.append("")
                    lines.append("## Generated Moved Blocks")
                    lines.append("")
                    lines.append("```hcl")
                    lines.append(repair_result.moved_blocks_content)
                    lines.append("```")
                
                report = "\n".join(lines)
                
                # Create dialog (same width as destroy resource detail dialog)
                with ui.dialog() as debug_dialog, ui.card().classes("w-full max-h-[90vh] p-6").style("width: 90vw; max-width: 90vw;"):
                    with ui.row().classes("w-full items-center justify-between mb-3"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("bug_report", size="md").classes("text-purple-500")
                            ui.label("AI Debug Report").classes("text-xl font-bold")
                        ui.button(icon="close", on_click=debug_dialog.close).props("flat round size=sm")
                    
                    ui.separator()
                    
                    # Scrollable content area
                    with ui.scroll_area().classes("w-full").style("max-height: 60vh;"):
                        ui.markdown(report).classes("text-sm")
                    
                    ui.separator()
                    
                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                        def copy_report():
                            ui.run_javascript(f'navigator.clipboard.writeText({repr(report)})')
                            ui.notify("Copied to clipboard!", type="positive")
                        
                        ui.button("Copy to Clipboard", icon="content_copy", on_click=copy_report).props("outline")
                        ui.button("Close", on_click=debug_dialog.close).props("flat")
                
                debug_dialog.open()
            
            ui.button(
                "AI Debug",
                icon="bug_report", 
                on_click=show_ai_debug,
            ).props("flat color=purple")


def _show_protected_resource_dialog(row: dict) -> None:
    """Show a dialog with protected resource details.
    
    Protected resources may not exist in the Terraform state file
    (they're in the YAML config), so we show info from the row data.
    """
    display_name = row.get("name", "Unknown")
    resource_type = row.get("type", "Unknown")
    resource_id = row.get("id", "")
    tf_address = row.get("tf_address", "")
    
    with ui.dialog() as dialog:
        with ui.card().classes("w-full max-w-lg p-6"):
            # Header
            with ui.row().classes("w-full items-center justify-between mb-4"):
                with ui.column().classes("gap-1"):
                    ui.label(display_name).classes("text-lg font-semibold")
                    with ui.row().classes("items-center gap-2"):
                        ui.badge(resource_type).props("color=primary outline")
                        ui.badge("Protected").props("color=blue")
                ui.button(icon="close", on_click=dialog.close).props("flat round size=sm")
            
            # Resource info
            with ui.column().classes("gap-3"):
                if resource_id:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("badge", size="xs").classes("text-slate-400")
                        ui.label(f"ID: {resource_id}").classes("text-sm font-mono")
                
                if tf_address:
                    with ui.row().classes("items-start gap-2"):
                        ui.icon("link", size="xs").classes("text-slate-400 mt-1")
                        ui.label(tf_address).classes("text-sm font-mono text-slate-600 break-all")
                
                # Protection status
                with ui.card().classes("w-full p-3 mt-2").style(
                    "background-color: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3);"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("shield", size="sm").classes("text-blue-500")
                        ui.label("This resource has lifecycle.prevent_destroy = true").classes(
                            "text-sm text-blue-700"
                        )
                    ui.label(
                        "It will be skipped during destroy operations. Use 'Unprotect Selected' to remove protection."
                    ).classes("text-xs text-blue-600 mt-2")
            
            # Close button
            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Close", on_click=dialog.close).props("outline")
    
    dialog.open()


def _show_destroy_unprotection_dialog(
    protected_resources: list,
    state: AppState,
    save_state: Callable[[], None],
) -> None:
    """Show confirmation dialog for unprotecting resources before destroy (US-DP-06).
    
    Only shown when user explicitly clicks 'Unprotect All'.
    """
    with ui.dialog() as dialog:
        with ui.card().classes("p-6 w-full max-w-xl"):
            # Header with warning icon
            with ui.row().classes("items-center gap-2 mb-4"):
                ui.icon("warning", size="md").classes("text-amber-500")
                ui.label("Unprotect All Resources").classes("text-lg font-semibold")
        
        # Warning message
        with ui.column().classes("gap-2 mb-4"):
            ui.label(
                f"This will remove protection from {len(protected_resources)} resource(s)."
            ).classes("text-sm")
            
            with ui.card().classes("w-full p-3").style("background-color: rgba(245, 158, 11, 0.1);"):
                ui.label(
                    "After unprotecting, you must regenerate Terraform files before destroying."
                ).classes("text-xs text-amber-700")
        
        # Resource list (max 10)
        with ui.column().classes("gap-1 mb-4 max-h-48 overflow-auto"):
            ui.label("Resources to unprotect:").classes("text-xs text-slate-500 mb-1")
            for res in protected_resources[:10]:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("shield_outlined", size="xs").classes("text-slate-400")
                    ui.label(res.name).classes("text-sm")
            if len(protected_resources) > 10:
                ui.label(f"... and {len(protected_resources) - 10} more").classes("text-xs text-slate-400 pl-6")
        
        # Buttons
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            
            def on_confirm():
                # Clear all protected resources from state
                state.map.protected_resources.clear()
                save_state()
                dialog.close()
                # Notification with next steps (US-DP-07)
                ui.notify(
                    "Resources unprotected. Go to Deploy tab and click 'Generate Terraform' to apply changes.",
                    type="warning",
                    timeout=8000,
                )
                # Reload to update the UI
                ui.navigate.reload()
            
            ui.button(
                "Unprotect All",
                icon="lock_open",
                on_click=on_confirm,
            ).props("color=amber").style("color: black !important;")
    
    dialog.open()


def _create_bulk_actions_panel(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    destroy_state: dict,
) -> None:
    """Create bulk action buttons for taint/destroy."""
    # Filter out data sources - same as the table
    all_resources = _load_state_resources(state, destroy_state)
    managed_resources = [r for r in all_resources if r.get("mode") != "data"]
    resource_count = len(managed_resources)

    with ui.card().classes("flex-1"):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("build", size="sm").classes("text-slate-500")
            ui.label("Actions").classes("font-semibold")

        # Selection buttons row
        with ui.row().classes("w-full gap-2 mb-2"):
            ui.button(
                "Select All",
                icon="select_all",
                on_click=lambda: _select_all(destroy_state),
            ).props("outline")
            ui.button(
                "Clear",
                icon="clear",
                on_click=lambda: _clear_selection(destroy_state),
            ).props("outline")

        # Action buttons row
        with ui.row().classes("w-full gap-2 mb-3"):
            ui.button(
                "Taint Selected",
                icon="warning",
                on_click=lambda: _run_terraform_taint(
                    state, terminal, save_state, destroy_state
                ),
            ).props("outline color=warning")
            
            async def on_destroy_selected():
                await _confirm_destroy_selected(state, terminal, save_state, destroy_state)
            
            ui.button(
                "Plan Destroy (Selected)",
                icon="delete_forever",
                on_click=on_destroy_selected,
            ).style(f"background-color: {STATUS_ERROR}; color: white;")

        # Danger zone
        ui.separator().classes("my-2")
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("warning", size="sm").classes("text-red-500")
            ui.label("Danger Zone").classes("text-sm font-semibold text-red-500")
        
        async def on_destroy_all():
            await _confirm_destroy_all(state, terminal, save_state, destroy_state, resource_count)
        
        ui.button(
            f"Destroy All ({resource_count} resources)",
            icon="delete_forever",
            on_click=on_destroy_all,
        ).classes("w-full mt-2").style(f"background-color: {STATUS_ERROR}; color: white;")


async def _select_all(destroy_state: dict) -> None:
    """Select all rows in the grid."""
    grid = destroy_state.get("grid")
    if grid:
        await grid.run_grid_method("selectAll")


async def _clear_selection(destroy_state: dict) -> None:
    """Clear all selections."""
    grid = destroy_state.get("grid")
    if grid:
        await grid.run_grid_method("deselectAll")
        destroy_state["selected"] = set()


def _refresh_resources_aggrid(state: AppState, destroy_state: dict) -> None:
    """Reload resources from state file and update the AG Grid."""
    grid = destroy_state.get("grid")
    if not grid:
        return
    
    # Filter out data sources (mode="data") - same as initial grid population
    all_resources = _load_state_resources(state, destroy_state)
    managed_resources = [r for r in all_resources if r.get("mode") != "data"]
    
    # Pre-sort data by display_name
    managed_resources = sorted(managed_resources, key=lambda x: x.get("display_name", ""))
    
    # Update AG Grid rowData
    grid.options["rowData"] = managed_resources
    grid.update()
    
    # Update stored resources for filtering
    destroy_state["all_resources"] = managed_resources
    # region agent log
    _debug_673991(
        "H5",
        "destroy.py:_refresh_resources_aggrid",
        "refreshed managed resources",
        {
            "managed_resources": len(managed_resources),
            "first_address": managed_resources[0].get("address") if managed_resources else None,
            "grid_exists": bool(grid),
        },
    )
    # endregion
    
    # Update the resource count badge
    resource_badge = destroy_state.get("resource_badge")
    if resource_badge:
        resource_badge.set_text(f"{len(managed_resources)} managed")
    
    destroy_state["selected"] = set()
    
    # Update selection label
    label = destroy_state.get("selection_label")
    if label:
        label.set_text("Selected: 0")
    
    ui.notify(f"Refreshed: {len(managed_resources)} managed resources", type="info")


def _refresh_resources(state: AppState, destroy_state: dict) -> None:
    """Legacy refresh function - redirects to AG Grid version."""
    _refresh_resources_aggrid(state, destroy_state)


async def _confirm_destroy_selected(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    destroy_state: dict,
) -> None:
    """Run init+validate+plan, then confirm before applying selected destroy plan."""
    selected = destroy_state.get("selected", set())
    if not selected:
        ui.notify("Select resources first", type="warning")
        return

    count = len(selected)
    selected_targets = sorted(selected)
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog

    # Step 1: terraform init + validate + plan -destroy
    terminal.clear()
    terminal.set_title("Output — PLAN DESTROY (SELECTED)")
    terminal.warning("━━━ TERRAFORM PLAN DESTROY (SELECTED) ━━━")
    terminal.info("")
    terminal.info(f"Selected targets: {count} resource{'s' if count != 1 else ''}")
    terminal.info("")

    tf_dir = state.deploy.terraform_dir or "deployments/migration"
    env = _get_terraform_env(state)
    target_args = [f"-target={address}" for address in selected_targets]
    plan_file = "destroy_selected.tfplan"

    terminal.info("Running terraform init...")
    init_result = await asyncio.to_thread(
        subprocess.run,
        ["terraform", "init", "-no-color"],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    _emit_bounded_output(
        terminal,
        phase_name="destroy init",
        stdout=init_result.stdout,
        stderr=init_result.stderr,
        stdout_budget=OutputBudget(max_lines=600, head_lines=360, tail_lines=180),
        stderr_budget=OutputBudget(max_lines=220, head_lines=140, tail_lines=60),
        on_stdout_line=lambda line: terminal.info_auto(line),
        on_stderr_line=lambda line: (
            terminal.error(line)
            if "Error:" in line or "error:" in line.lower()
            else terminal.warning(line)
            if "Warning:" in line
            else terminal.info_auto(line)
        ),
    )
    if init_result.returncode != 0:
        terminal.error("")
        terminal.error(f"terraform init failed with exit code {init_result.returncode}")
        ui.notify("Destroy init failed", type="negative")
        return

    terminal.info("")
    terminal.info("Running terraform validate...")
    validate_result = await asyncio.to_thread(
        subprocess.run,
        ["terraform", "validate", "-no-color"],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    _emit_bounded_output(
        terminal,
        phase_name="destroy validate",
        stdout=validate_result.stdout,
        stderr=validate_result.stderr,
        stdout_budget=OutputBudget(max_lines=420, head_lines=260, tail_lines=120),
        stderr_budget=OutputBudget(max_lines=220, head_lines=140, tail_lines=60),
        on_stdout_line=lambda line: terminal.info_auto(line),
        on_stderr_line=lambda line: (
            terminal.error(line)
            if "Error:" in line or "error:" in line.lower()
            else terminal.warning(line)
            if "Warning:" in line
            else terminal.info_auto(line)
        ),
    )
    if validate_result.returncode != 0:
        terminal.error("")
        terminal.error(f"terraform validate failed with exit code {validate_result.returncode}")
        ui.notify("Destroy validate failed", type="negative")
        return

    terminal.info("")
    terminal.info("Running terraform plan -destroy...")
    result = await asyncio.to_thread(
        subprocess.run,
        ["terraform", "plan", "-destroy", f"-out={plan_file}", "-no-color", *target_args],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )

    plan_output = result.stdout + result.stderr
    destroy_count = _extract_destroy_count_from_plan_output(plan_output)
    
    _emit_bounded_output(
        terminal,
        phase_name="destroy plan",
        stdout=result.stdout,
        stderr=result.stderr,
        stdout_budget=OutputBudget(max_lines=900, head_lines=520, tail_lines=320),
        stderr_budget=OutputBudget(max_lines=300, head_lines=180, tail_lines=80),
        on_stdout_line=lambda line: (
            terminal.warning(line)
            if "will be destroyed" in line
            else terminal.success(line)
            if "Plan:" in line
            else terminal.info_auto(line)
        ),
        on_stderr_line=lambda line: (
            terminal.error(line)
            if "Error:" in line or "error:" in line.lower()
            else terminal.warning(line)
            if "Warning:" in line
            else terminal.info_auto(line)
        ),
    )
    
    if result.returncode != 0:
        terminal.error("")
        terminal.error(f"Plan failed with exit code {result.returncode}")
        ui.notify("Destroy plan failed", type="negative")
        return

    terminal.info("")
    terminal.warning(f"⚠️  {destroy_count} resource(s) will be destroyed (including dependencies)")
    
    # Step 2: confirmation + apply destroy plan
    with ui.dialog() as dialog:
        with ui.card().classes("w-full max-w-lg"):
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.icon("warning", size="md").classes("text-red-500")
                ui.label("Destroy Plan Ready").classes("text-lg font-semibold")

            # Show count difference warning
            if destroy_count > count:
                with ui.row().classes("w-full items-center gap-2 p-3 rounded mb-3").style(
                    "background-color: rgba(251, 146, 60, 0.2); border: 1px solid rgba(251, 146, 60, 0.5);"
                ):
                    ui.icon("warning", size="sm").classes("text-orange-500")
                    with ui.column().classes("gap-1"):
                        ui.label(f"Cascade Warning: {destroy_count} resources will be destroyed").classes(
                            "text-sm font-semibold text-orange-600"
                        )
                        ui.label(
                            f"You selected {count}, but {destroy_count - count} dependent resource(s) "
                            "will also be destroyed due to Terraform dependencies."
                        ).classes("text-xs text-orange-600")
            
            ui.label(
                f"Plan created successfully. Applying this plan will destroy {destroy_count} resource(s). "
                "This action cannot be undone."
            ).classes("text-sm text-slate-600 dark:text-slate-400")

            # Warning banner
            with ui.row().classes("w-full items-center gap-2 p-3 rounded mt-3").style(
                "background-color: rgba(239, 68, 68, 0.1);"
            ):
                ui.icon("error", size="sm").classes("text-red-500")
                ui.label("This is irreversible!").classes("text-sm font-medium text-red-500")

            with ui.row().classes("w-full justify-between mt-4"):
                def open_plan_viewer():
                    plan_dialog = create_plan_viewer_dialog(plan_output, "Destroy Plan")
                    plan_dialog.open()
                
                ui.button(
                    "View Plan",
                    icon="visibility",
                    on_click=open_plan_viewer,
                ).props("outline")
                
                with ui.row().classes("gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("outline")

                    async def do_destroy() -> None:
                        dialog.close()
                        with ui.dialog() as confirm_dialog:
                            with ui.card().classes("w-full max-w-md"):
                                ui.label("Apply Destroy Plan").classes("text-lg font-semibold")
                                ui.label(
                                    f"Type DESTROY to confirm deletion of {destroy_count} resource(s)."
                                ).classes("text-sm text-slate-600 dark:text-slate-400")
                                confirm_input = ui.input(
                                    placeholder="Type DESTROY",
                                ).classes("w-full mt-2").props("outlined")

                                apply_btn = ui.button(
                                    f"Apply Destroy ({destroy_count})",
                                    icon="delete_forever",
                                    on_click=lambda: None,
                                ).props("color=negative")
                                apply_btn.disable()

                                def on_change(e):
                                    raw_value = (
                                        e.args
                                        if isinstance(e.args, str)
                                        else str(e.args) if e.args is not None else ""
                                    )
                                    if _is_destroy_confirmation_text_valid(raw_value):
                                        apply_btn.enable()
                                    else:
                                        apply_btn.disable()

                                confirm_input.on("update:model-value", on_change)

                                async def do_apply() -> None:
                                    confirm_dialog.close()
                                    await _run_terraform_destroy_selected(
                                        state,
                                        terminal,
                                        save_state,
                                        destroy_state,
                                        selected_override=selected_targets,
                                        plan_file=plan_file,
                                        expected_destroy_count=destroy_count,
                                    )

                                apply_btn.on("click", do_apply)
                                with ui.row().classes("w-full justify-between mt-3"):
                                    ui.button(
                                        "View Plan",
                                        icon="visibility",
                                        on_click=open_plan_viewer,
                                    ).props("outline")
                                    ui.button("Cancel", on_click=confirm_dialog.close).props("outline")
                        confirm_dialog.open()

                    ui.button(
                        f"Apply Destroy ({destroy_count})",
                        icon="delete_forever",
                        on_click=do_destroy,
                    ).props("color=negative")
    dialog.open()


async def _confirm_destroy_all(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    destroy_state: dict,
    resource_count: int,
) -> None:
    """Run destroy plan first, then confirm before destroying ALL resources."""
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
    
    if resource_count == 0:
        ui.notify("No resources to destroy", type="warning")
        return

    # Run terraform plan -destroy first to show what will be destroyed
    terminal.clear()
    terminal.set_title("Output — DESTROY ALL PLAN")
    terminal.warning("━━━ TERRAFORM DESTROY ALL PLAN ━━━")
    terminal.info("")
    
    # Calculate protected vs unprotected from terraform state
    tf_dir = state.deploy.terraform_dir or "deployments/migration"
    env = _get_terraform_env(state)
    
    # Get actual resources from terraform state to determine protected count
    terminal.info("Analyzing terraform state...")
    state_result = await asyncio.to_thread(
        subprocess.run,
        ["terraform", "state", "list"],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    
    if state_result.returncode == 0:
        all_state_resources = [r.strip() for r in state_result.stdout.strip().split("\n") if r.strip()]
        
        # Categorize resources based on protected_ prefix (lifecycle.prevent_destroy)
        protected_resources = [r for r in all_state_resources if "protected_" in r]
        unprotected_resources = [r for r in all_state_resources if "protected_" not in r]
        
        protected_count = len(protected_resources)
        unprotected_count = len(unprotected_resources)
        
        terminal.info("")
        terminal.info(f"📊 Resource Breakdown:")
        terminal.info(f"    Total in state: {len(all_state_resources)}")
        if protected_count > 0:
            terminal.success(f"    🛡️  Protected (will be PRESERVED): {protected_count}")
            terminal.warning(f"    🗑️  Unprotected (will be DESTROYED): {unprotected_count}")
        else:
            terminal.warning(f"    🗑️  To be destroyed: {unprotected_count}")
        terminal.info("")
        
        if unprotected_count == 0:
            terminal.warning("⚠️  All resources are protected - nothing to destroy")
            terminal.info("To destroy protected resources, use 'Unprotect All' first.")
            ui.notify("All resources are protected", type="warning")
            return
        
        # Store for later use in dialog
        actual_protected_count = protected_count
        # Build list of unprotected resources for targeted plan
        unprotected_targets = unprotected_resources
        
        # When there are protected resources, skip the full terraform plan
        # because Terraform's -target with -destroy still evaluates prevent_destroy rules
        # on dependencies, causing errors. The actual destroy with -target will work correctly.
        terminal.info(f"✅ {unprotected_count} resource{'s' if unprotected_count != 1 else ''} will be destroyed")
        terminal.info(f"🛡️  {protected_count} protected resource{'s' if protected_count != 1 else ''} will be preserved")
        terminal.info("")
        terminal.info("Skipping full terraform plan (protected resources require targeted destroy)...")
        
        # Use the calculated count as destroy_count
        destroy_count = unprotected_count
        
        # Create a summary for the "View Plan" button since we skipped the actual plan
        plan_output = f"""Protected resources detected - full plan skipped.

Resource Breakdown:
  Protected resources (prevent_destroy=true): {protected_count}
  Unprotected resources: {unprotected_count}

Protected resources that will be PRESERVED:
""" + "\n".join(f"  - {r}" for r in protected_resources) + f"""

The following {unprotected_count} unprotected resources will be destroyed:
""" + "\n".join(f"  - {r}" for r in unprotected_resources[:50])
        if len(unprotected_resources) > 50:
            plan_output += f"\n  ... and {len(unprotected_resources) - 50} more"
        
    else:
        # Fall back to original behavior if state list fails
        terminal.info(f"Planning destruction of {resource_count} managed resource{'s' if resource_count != 1 else ''}...")
        actual_protected_count = 0
        unprotected_targets = []  # Empty means plan all
        terminal.info("")
    
        # Run plan -destroy (full plan, no protected resources)
        plan_cmd = ["terraform", "plan", "-destroy", "-no-color"]
    
        result = await asyncio.to_thread(
            subprocess.run,
            plan_cmd,
            cwd=tf_dir,
            capture_output=True,
            text=True,
            env=env,
        )
    
        # Parse plan output to count resources
        plan_output = result.stdout + result.stderr
        destroy_count = 0
    
        _emit_bounded_output(
            terminal,
            phase_name="destroy all plan",
            stdout=result.stdout,
            stderr=result.stderr,
            stdout_budget=OutputBudget(max_lines=900, head_lines=520, tail_lines=320),
            stderr_budget=OutputBudget(max_lines=300, head_lines=180, tail_lines=80),
            on_stdout_line=lambda line: (
                terminal.warning(line)
                if "will be destroyed" in line
                else terminal.success(line)
                if "Plan:" in line
                else terminal.info_auto(line)
            ),
            on_stderr_line=lambda line: (
                terminal.error(line)
                if "Error:" in line or "error:" in line.lower()
                else terminal.warning(line)
                if "Warning:" in line
                else terminal.info_auto(line)
            ),
        )
        destroy_count = _extract_destroy_count_from_plan_output(plan_output)
    
        if result.returncode != 0:
            terminal.error("")
            terminal.error(f"Plan failed with exit code {result.returncode}")
            ui.notify("Destroy plan failed", type="negative")
            return
    
    terminal.info("")
    terminal.warning(f"⚠️  {destroy_count} resource(s) will be destroyed")

    with ui.dialog() as dialog:
        # Track confirmation input
        confirm_state = {"valid": False}

        with ui.card().classes("w-full max-w-lg"):
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.icon("warning", size="lg").classes("text-red-500")
                ui.label("Destroy All Resources").classes("text-xl font-bold text-red-500")

            # Show protected info if any
            if actual_protected_count > 0:
                ui.label(
                    f"You are about to destroy {destroy_count} unprotected resources. "
                    f"{actual_protected_count} protected resource(s) will be preserved. "
                    "This action is permanent and cannot be undone."
                ).classes("text-sm text-slate-600 dark:text-slate-400 mt-2")
            else:
                ui.label(
                    f"You are about to destroy ALL {destroy_count} resources in the target account. "
                    "This action is permanent and cannot be undone."
                ).classes("text-sm text-slate-600 dark:text-slate-400 mt-2")

            # Strong warning banner
            with ui.column().classes("w-full p-4 rounded mt-4 gap-2").style(
                "background-color: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3);"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("error", size="md").classes("text-red-500")
                    ui.label("DANGER: This is irreversible!").classes(
                        "text-base font-bold text-red-500"
                    )
                ui.label(
                    "All deployed dbt Cloud resources (projects, environments, jobs, "
                    "connections, etc.) will be permanently deleted from the target account."
                ).classes("text-sm text-red-400")

            # Type to confirm
            ui.label(
                f"Type the resource count ({destroy_count}) to confirm:"
            ).classes("text-sm font-medium mt-4")

            confirm_input = ui.input(
                placeholder=f"Type {destroy_count} to confirm",
            ).classes("w-full").props("outlined")

            destroy_btn = ui.button(
                f"Destroy All {destroy_count} Resources",
                icon="delete_forever",
                on_click=lambda: None,  # Replaced below
            ).classes("w-full mt-4").style(
                f"background-color: {STATUS_ERROR}; color: white;"
            )
            destroy_btn.disable()

            def on_input_change(e):
                try:
                    value = e.args if isinstance(e.args, str) else str(e.args) if e.args else ""
                    typed_value = int(value) if value else 0
                    if typed_value == destroy_count:
                        confirm_state["valid"] = True
                        destroy_btn.enable()
                    else:
                        confirm_state["valid"] = False
                        destroy_btn.disable()
                except (ValueError, TypeError):
                    confirm_state["valid"] = False
                    destroy_btn.disable()

            confirm_input.on("update:model-value", on_input_change)

            async def do_destroy_all():
                if confirm_state["valid"]:
                    dialog.close()
                    await _run_terraform_destroy_all(state, terminal, save_state, destroy_state)

            destroy_btn.on("click", do_destroy_all)

            with ui.row().classes("w-full justify-between mt-2"):
                ui.button(
                    "View Plan",
                    icon="visibility",
                    on_click=lambda: create_plan_viewer_dialog(plan_output, "Destroy All Plan").open(),
                ).props("outline")
                ui.button("Cancel", on_click=dialog.close).props("outline")

    dialog.open()


def _load_state_resources(state: AppState, destroy_state: dict) -> list[dict]:
    """Load resources from terraform state file, expanding instances."""
    state_path = _get_state_file_path(state, destroy_state)
    if not state_path:
        return []

    try:
        content = Path(state_path).read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception:
        return []

    rows = []
    for resource in data.get("resources", []):
        module = resource.get("module", "")
        rtype = resource.get("type", "")
        name = resource.get("name", "")
        mode = resource.get("mode", "")
        instances = resource.get("instances", [])
        
        # Build base address
        if module:
            base_address = f"{module}.{rtype}.{name}"
        else:
            base_address = f"{rtype}.{name}"
        
        # Expand each instance as a separate row
        if len(instances) <= 1:
            # Single instance or no index_key - use base address
            # Try to get index_key from single instance if available
            single_index = instances[0].get("index_key") if instances else None
            display = single_index if single_index else name
            # Extract dbt_id from instance attributes if available
            dbt_id = None
            if instances:
                attrs = instances[0].get("attributes", {})
                dbt_id = attrs.get("id") or attrs.get("project_id")
            # Check if resource is protected (address contains "protected_")
            is_protected = "protected_" in base_address
            rows.append({
                "address": base_address,
                "type": rtype,
                "name": name,
                "display_name": str(display),
                "mode": mode,
                "protected": is_protected,
                "dbt_id": dbt_id,
            })
        else:
            # Multiple instances - expand with index_key
            for inst in instances:
                index_key = inst.get("index_key")
                if index_key is not None:
                    if isinstance(index_key, str):
                        full_address = f'{base_address}["{index_key}"]'
                        display = index_key
                    else:
                        full_address = f"{base_address}[{index_key}]"
                        display = str(index_key)
                else:
                    full_address = base_address
                    display = name
                
                # Extract dbt_id from instance attributes if available
                attrs = inst.get("attributes", {})
                dbt_id = attrs.get("id") or attrs.get("project_id")
                # Check if resource is protected (address contains "protected_")
                is_protected = "protected_" in full_address
                
                rows.append({
                    "address": full_address,
                    "type": rtype,
                    "name": name,
                    "display_name": display,
                    "mode": mode,
                    "protected": is_protected,
                    "dbt_id": dbt_id,
                })

    return rows


async def _run_terraform_taint(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    destroy_state: dict,
) -> None:
    """Run terraform taint for selected resources."""
    selected = sorted(destroy_state.get("selected", []))
    if not selected:
        ui.notify("Select resources first", type="warning")
        return

    tf_dir = state.deploy.terraform_dir or "deployments/migration"

    terminal.clear()
    terminal.warning("━━━ TERRAFORM TAINT ━━━")
    terminal.info("")

    env = _get_terraform_env(state)

    for address in selected:
        terminal.info(f"Tainting {address}...")
        result = await asyncio.to_thread(
            subprocess.run,
            ["terraform", "taint", "-no-color", address],
            cwd=tf_dir,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode == 0:
            terminal.success(f"Tainted {address}")
        else:
            terminal.error(f"Failed to taint {address}")
            if result.stderr:
                terminal.warning(result.stderr.strip())

    ui.notify("Taint operations complete", type="positive")
    save_state()


async def _run_terraform_destroy_selected(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    destroy_state: dict,
    selected_override: Optional[list[str]] = None,
    plan_file: Optional[str] = None,
    expected_destroy_count: Optional[int] = None,
) -> None:
    """Apply selected destroy plan (or fallback to direct targeted destroy)."""
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog

    selected = sorted(selected_override or destroy_state.get("selected", []))
    if not selected:
        ui.notify("Select resources first", type="warning")
        return

    tf_dir = state.deploy.terraform_dir or "deployments/migration"

    terminal.clear()
    terminal.set_title("Output — APPLY DESTROY (SELECTED)")
    terminal.warning("━━━ TERRAFORM APPLY DESTROY (SELECTED) ━━━")
    terminal.warning("")
    terminal.warning(f"Targets: {len(selected)} resources")
    for addr in selected:
        terminal.info(f"  • {addr}")
    terminal.info("")

    env = _get_terraform_env(state)
    if plan_file:
        cmd = ["terraform", "apply", "-no-color", "-auto-approve", plan_file]
    else:
        target_args = [f"-target={address}" for address in selected]
        cmd = ["terraform", "destroy", "-no-color", "-auto-approve", *target_args]

    result = await asyncio.to_thread(
        subprocess.run,
        cmd,
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )

    combined_output = result.stdout + result.stderr
    destroyed_count = _extract_destroy_count_from_apply_output(combined_output)

    _emit_bounded_output(
        terminal,
        phase_name="destroy apply",
        stdout=result.stdout,
        stderr=result.stderr,
        stdout_budget=OutputBudget(max_lines=900, head_lines=520, tail_lines=320),
        stderr_budget=OutputBudget(max_lines=300, head_lines=180, tail_lines=80),
        on_stdout_line=lambda line: (
            terminal.success(line)
            if "Destroy complete!" in line or "Destruction complete after" in line
            else terminal.info_auto(line)
        ),
        on_stderr_line=lambda line: (
            terminal.error(line)
            if "Error:" in line or "error:" in line.lower()
            else terminal.warning(line)
            if "Warning:" in line
            else terminal.info_auto(line)
        ),
    )

    if result.returncode == 0:
        final_count = expected_destroy_count if expected_destroy_count is not None else destroyed_count
        terminal.success("")
        terminal.success("━━━ DESTROY SUMMARY ━━━")
        terminal.success(f"Successfully destroyed {final_count} resource(s)")
        state.deploy.destroy_complete = True
        save_state()
        ui.notify(f"Destroyed {final_count} resources", type="positive")
        
        # Refresh the resource table to reflect destroyed resources
        _refresh_resources(state, destroy_state)
        terminal.info("")
        terminal.info("Resource table refreshed.")
        create_plan_viewer_dialog(combined_output, "Destroy Apply Output").open()
    else:
        terminal.error("")
        terminal.error(f"Destroy failed with exit code {result.returncode}")
        ui.notify("Destroy failed", type="negative")


async def _run_terraform_destroy_all(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    destroy_state: dict,
) -> None:
    """Run terraform destroy for ALL resources, auto-skipping protected resources (US-048, US-DP-01)."""
    tf_dir = state.deploy.terraform_dir or "deployments/migration"

    terminal.clear()
    terminal.set_title("Output — DESTROY ALL")
    terminal.error("━━━ TERRAFORM DESTROY ALL ━━━")
    terminal.error("")

    env = _get_terraform_env(state)

    # Step 1: Get list of all resources in terraform state
    terminal.info("Checking terraform state...")
    state_result = await asyncio.to_thread(
        subprocess.run,
        ["terraform", "state", "list"],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    
    if state_result.returncode != 0:
        terminal.error("Failed to list terraform state")
        _emit_bounded_output(
            terminal,
            phase_name="state list",
            stdout="",
            stderr=state_result.stderr,
            stdout_budget=None,
            stderr_budget=OutputBudget(max_lines=160, head_lines=110, tail_lines=40),
            on_stdout_line=lambda _line: None,
            on_stderr_line=lambda line: terminal.error(f"  {line}"),
        )
        ui.notify("Failed to list terraform state", type="negative")
        return
    
    # Parse resources from state
    all_state_resources = [r.strip() for r in state_result.stdout.strip().split("\n") if r.strip()]
    
    if not all_state_resources:
        terminal.warning("No resources found in terraform state")
        ui.notify("No resources to destroy", type="warning")
        return
    
    # Step 2: Filter out protected resources (addresses containing "protected_")
    unprotected_resources = [r for r in all_state_resources if "protected_" not in r]
    protected_resources = [r for r in all_state_resources if "protected_" in r]
    # region agent log
    member_addresses = [r for r in protected_resources if '["member"]' in r]
    _agent_debug_log(
        "D5",
        "destroy.py:_run_terraform_destroy_all",
        "classified terraform state resources for destroy",
        {
            "all_state_count": len(all_state_resources),
            "protected_count": len(protected_resources),
            "unprotected_count": len(unprotected_resources),
            "member_protected_addresses": member_addresses,
            "protected_group_addresses_sample": [
                r for r in protected_resources if ".dbtcloud_group.protected_groups[" in r
            ][:10],
        },
    )
    # endregion
    
    # Step 3: Show skip notification if any protected (US-DP-02)
    if protected_resources:
        terminal.info("")
        terminal.info(f"Skipping {len(protected_resources)} protected resource(s):")
        # Show up to 10 protected resources
        for addr in protected_resources[:10]:
            # Extract a shorter display name from the address
            short_name = addr.split("[")[-1].rstrip("]").strip('"') if "[" in addr else addr.split(".")[-1]
            terminal.info(f"  🛡️ {short_name}")
        if len(protected_resources) > 10:
            terminal.info(f"  ... and {len(protected_resources) - 10} more")
        terminal.info("")
    
    # Step 4: If nothing unprotected to destroy, exit early (US-DP-03)
    if not unprotected_resources:
        terminal.warning("")
        terminal.warning("All resources are protected - nothing to destroy")
        terminal.info("")
        terminal.info("To destroy protected resources:")
        terminal.info("  1. Click 'Unprotect All' in the protection panel above")
        terminal.info("  2. Go to Deploy tab and click 'Generate Terraform'")
        terminal.info("  3. Return here and run destroy again")
        ui.notify("All resources are protected", type="warning")
        return
    
    # Step 5: Show what will be destroyed
    terminal.warning("⚠️  DESTROYING UNPROTECTED RESOURCES")
    terminal.warning(f"    Resources to destroy: {len(unprotected_resources)}")
    if protected_resources:
        terminal.info(f"    Protected (skipped): {len(protected_resources)}")
    terminal.info("")
    
    # Step 6: Build command with -target for each unprotected resource
    cmd = ["terraform", "destroy", "-no-color", "-auto-approve"]
    for target in unprotected_resources:
        cmd.extend(["-target", target])
    
    # Step 7: Run destroy
    result = await asyncio.to_thread(
        subprocess.run,
        cmd,
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )

    # Track destroyed resources for summary
    destroyed_resources = []
    destroy_count = 0

    def _on_destroy_all_stdout(line: str) -> None:
        nonlocal destroy_count
        if "Destroy complete!" in line:
            terminal.success(line)
            match = re.search(r"Resources:\s*(\d+)\s*destroyed", line)
            if match:
                destroy_count = int(match.group(1))
            return
        if "Destruction complete" in line:
            terminal.warning(line)
            if ":" in line:
                destroyed_resources.append(line.split(":", 1)[0].strip())
            return
        if "Destroying..." in line:
            terminal.warning(line)
            return
        terminal.info_auto(line)

    _emit_bounded_output(
        terminal,
        phase_name="destroy all apply",
        stdout=result.stdout,
        stderr=result.stderr,
        stdout_budget=OutputBudget(max_lines=900, head_lines=520, tail_lines=320),
        stderr_budget=OutputBudget(max_lines=300, head_lines=180, tail_lines=80),
        on_stdout_line=_on_destroy_all_stdout,
        on_stderr_line=lambda line: terminal.warning(line),
    )

    # Use destroy_count from summary if we didn't capture individual resources
    final_count = destroy_count if destroy_count > 0 else len(destroyed_resources)

    if result.returncode == 0:
        terminal.success("")
        terminal.success("━━━ DESTROY ALL SUMMARY ━━━")
        terminal.success(f"Successfully destroyed {final_count} resource(s)")
        
        # Show preserved count if any protected (US-DP-08)
        if protected_resources:
            terminal.info(f"({len(protected_resources)} protected resource(s) preserved)")
        
        if destroyed_resources:
            terminal.info("")
            terminal.info("Destroyed resources:")
            for addr in destroyed_resources[:20]:  # Show first 20
                terminal.info(f"  ✓ {addr}")
            if len(destroyed_resources) > 20:
                terminal.info(f"  ... and {len(destroyed_resources) - 20} more")

        # Reset deploy state flags
        state.deploy.apply_complete = False
        state.deploy.last_plan_success = False
        state.deploy.destroy_complete = True
        save_state()
        ui.notify(f"Destroyed {final_count} resources", type="positive")
        
        # Refresh the resource table to reflect destroyed resources
        _refresh_resources(state, destroy_state)
        terminal.info("")
        terminal.info("Resource table refreshed.")
    else:
        terminal.error("")
        terminal.error(f"Destroy failed with exit code {result.returncode}")
        ui.notify("Destroy all failed", type="negative")


def _create_navigation_section(on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Create the navigation buttons section."""
    with ui.row().classes("w-full justify-between mt-6"):
        ui.button(
            "Back to Deploy",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.DEPLOY),
        ).props("outline")
