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
import subprocess
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.components.terminal_output import TerminalOutput
from importer.web.pages.deploy import _get_state_file_path, _get_terraform_env
from importer.web.state import AppState, WorkflowStep
from importer.web.utils.yaml_viewer import create_state_viewer_dialog


# dbt brand colors
DBT_ORANGE = "#FF694A"
STATUS_ERROR = "#EF4444"  # red-500


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

        # Top row: State/Target info on left, Actions on right
        with ui.row().classes("w-full gap-4"):
            # Left column: State file and Target info stacked
            with ui.column().classes("flex-1 gap-4"):
                _create_state_inspection_panel(state, destroy_state)
                _create_target_info_panel(state, on_step_change)
            # Right column: Actions
            _create_bulk_actions_panel(state, terminal, save_state, destroy_state)

        # Resource table (full width)
        _create_resource_table(state, destroy_state)

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
    """Check if prerequisites are met for destroy - requires credentials and state file."""
    errors = []
    
    # Check for target credentials
    if not state.target_credentials.is_complete():
        errors.append(("Target credentials not configured", WorkflowStep.TARGET))
    
    # Check if state file exists (allows destroy even if apply wasn't done in this session)
    state_path = _get_state_file_path(state, destroy_state)
    if not state_path:
        errors.append(("No Terraform state file found", WorkflowStep.DEPLOY))
    
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

            # Show state file path hint
            tf_dir = state.deploy.terraform_dir or "deployments/migration"
            with ui.row().classes("items-center gap-2 mt-4"):
                ui.icon("info", size="sm").classes("text-slate-400")
                ui.label(f"Expected state file: {tf_dir}/terraform.tfstate").classes("text-xs text-slate-500 font-mono")

        return False

    return True


def _create_state_inspection_panel(state: AppState, destroy_state: dict) -> None:
    """Create state inspection panel."""
    state_path = _get_state_file_path(state, destroy_state)

    def open_state_viewer() -> None:
        if not state_path:
            ui.notify("No terraform state file found", type="warning")
            return
        dialog = create_state_viewer_dialog(state_path)
        dialog.open()

    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("description", size="sm").classes("text-slate-500")
            ui.label("State File").classes("font-semibold")
        
        if state_path:
            ui.label(state_path).classes("text-xs text-slate-500 font-mono truncate mb-3")
        else:
            ui.label("No state file available yet.").classes("text-xs text-slate-500 mb-3")

        view_btn = ui.button(
            "View State",
            icon="visibility",
            on_click=open_state_viewer,
        ).props("outline").classes("w-full")

        if not state_path:
            view_btn.disable()
            view_btn.tooltip("Generate, init, and apply to create state")


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
                on_click=lambda: on_step_change(WorkflowStep.TARGET),
            ).props("flat dense round size=sm").tooltip("Target Configuration")
        
        with ui.column().classes("gap-1"):
            # Account name (if available from state, otherwise show generic)
            account_name = getattr(state.target_credentials, 'account_name', None) or "dbt Cloud Account"
            ui.label(account_name).classes("text-sm font-medium")
            
            # Account ID
            ui.label(f"ID: {creds.account_id}").classes("text-xs text-slate-500 font-mono")
            
            # Host URL
            ui.label(host_display).classes("text-xs text-slate-500 font-mono")


def _create_resource_table(state: AppState, destroy_state: dict) -> None:
    """Create the resource selection table."""
    resources = _load_state_resources(state, destroy_state)
    
    # Filter out data sources (mode="data") - they can't be tainted/destroyed
    managed_resources = [r for r in resources if r.get("mode") != "data"]

    columns = [
        {"name": "type", "label": "Type", "field": "type", "align": "left", "sortable": True},
        {"name": "display_name", "label": "Name", "field": "display_name", "align": "left", "sortable": True},
    ]

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label("Select Resources").classes("font-semibold")
                ui.badge(f"{len(managed_resources)} managed").props("color=primary outline")
            ui.button(
                "Refresh",
                icon="refresh",
                on_click=lambda: _refresh_resources(state, destroy_state),
            ).props("outline size=sm")

        table = ui.table(
            columns=columns,
            rows=managed_resources,
            row_key="address",
            pagination={"rowsPerPage": 0},  # 0 means show all rows
        ).classes("w-full").style("max-height: 400px;")
        table.props("selection=multiple dense")

        def on_selection(e) -> None:
            # Selection event is incremental - "added" indicates if rows were added or removed
            changed_rows = e.args.get("rows", [])
            is_added = e.args.get("added", True)
            
            # Initialize selected set if not present
            if "selected" not in destroy_state:
                destroy_state["selected"] = set()
            
            # Add or remove based on the "added" flag
            for row in changed_rows:
                addr = row.get("address")
                if addr:
                    if is_added:
                        destroy_state["selected"].add(addr)
                    else:
                        destroy_state["selected"].discard(addr)

        table.on("selection", on_selection)
        
        def on_row_click(e) -> None:
            """Show resource details when a row is clicked."""
            # Try different formats - NiceGUI table events vary
            row = None
            if isinstance(e.args, dict):
                row = e.args.get("row", {})
            elif isinstance(e.args, list) and len(e.args) > 1:
                # Format might be [event, row, col]
                row = e.args[1] if isinstance(e.args[1], dict) else None
            
            if not row:
                ui.notify("Could not get row data", type="warning")
                return
            address = row.get("address", "")
            display_name = row.get("display_name", "")
            resource_type = row.get("type", "")
            _show_resource_detail_dialog(state, destroy_state, address, display_name, resource_type)
        
        table.on("row-click", on_row_click)
        destroy_state["table"] = table

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
        with ui.card().classes("w-full max-w-4xl max-h-[90vh]"):
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
            
            # Metadata section
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
                "Destroy Selected",
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


def _select_all(destroy_state: dict) -> None:
    """Select all rows in the table."""
    table = destroy_state.get("table")
    if not table:
        return
    table.selected = list(table.rows)
    table.update()
    destroy_state["selected"] = {row["address"] for row in table.rows}


def _clear_selection(destroy_state: dict) -> None:
    """Clear all selections."""
    table = destroy_state.get("table")
    if not table:
        return
    table.selected = []
    table.update()
    destroy_state["selected"] = set()


def _refresh_resources(state: AppState, destroy_state: dict) -> None:
    """Reload resources from state file."""
    table = destroy_state.get("table")
    if not table:
        return
    # Filter out data sources (mode="data") - same as initial table population
    all_resources = _load_state_resources(state, destroy_state)
    managed_resources = [r for r in all_resources if r.get("mode") != "data"]
    
    # Modify in place for reactivity (don't replace the list reference)
    table.rows.clear()
    table.rows.extend(managed_resources)
    table.selected.clear()
    table.update()
    
    destroy_state["selected"] = set()
    ui.notify(f"Refreshed: {len(managed_resources)} managed resources", type="info")


async def _confirm_destroy_selected(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    destroy_state: dict,
) -> None:
    """Run destroy plan first, then confirm before destroying selected resources."""
    selected = destroy_state.get("selected", set())
    if not selected:
        ui.notify("Select resources first", type="warning")
        return

    count = len(selected)
    
    # Run terraform plan -destroy first to show what will be destroyed
    terminal.clear()
    terminal.set_title("Output — DESTROY PLAN")
    terminal.warning("━━━ TERRAFORM DESTROY PLAN ━━━")
    terminal.info("")
    terminal.info(f"Planning destruction of {count} selected resource{'s' if count != 1 else ''}...")
    terminal.info("")
    
    tf_dir = state.deploy.terraform_dir or "deployments/migration"
    env = _get_terraform_env(state)
    target_args = [f"-target={address}" for address in sorted(selected)]
    
    # Run plan -destroy to see what will actually be destroyed (including dependencies)
    result = await asyncio.to_thread(
        subprocess.run,
        ["terraform", "plan", "-destroy", "-no-color", *target_args],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    
    # Parse plan output to count resources
    plan_output = result.stdout + result.stderr
    destroy_count = 0
    resources_to_destroy = []
    
    for line in plan_output.split("\n"):
        if line.strip():
            # Show all plan output
            if "will be destroyed" in line:
                terminal.warning(line)
                destroy_count += 1
                # Extract resource address
                if "#" in line:
                    addr = line.split("#")[1].split(" will be")[0].strip()
                    resources_to_destroy.append(addr)
            elif "Error:" in line or "error:" in line.lower():
                terminal.error(line)
            elif "Warning:" in line:
                terminal.warning(line)
            elif "Plan:" in line:
                terminal.success(line)
            else:
                terminal.info_auto(line)
    
    if result.returncode != 0:
        terminal.error("")
        terminal.error(f"Plan failed with exit code {result.returncode}")
        ui.notify("Destroy plan failed", type="negative")
        return
    
    terminal.info("")
    terminal.warning(f"⚠️  {destroy_count} resource(s) will be destroyed (including dependencies)")
    
    # Show confirmation dialog with plan results
    with ui.dialog() as dialog:
        with ui.card().classes("w-full max-w-lg"):
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.icon("warning", size="md").classes("text-red-500")
                ui.label("Confirm Destroy").classes("text-lg font-semibold")

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
                f"This will permanently destroy {destroy_count} resource(s). "
                "This action cannot be undone."
            ).classes("text-sm text-slate-600 dark:text-slate-400")

            # Warning banner
            with ui.row().classes("w-full items-center gap-2 p-3 rounded mt-3").style(
                "background-color: rgba(239, 68, 68, 0.1);"
            ):
                ui.icon("error", size="sm").classes("text-red-500")
                ui.label("This is irreversible!").classes("text-sm font-medium text-red-500")

            with ui.row().classes("w-full justify-between mt-4"):
                # View Plan button on the left
                def open_plan_viewer():
                    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                    plan_dialog = create_plan_viewer_dialog(plan_output, "Destroy Plan")
                    plan_dialog.open()
                
                ui.button(
                    "View Plan",
                    icon="visibility",
                    on_click=open_plan_viewer,
                ).props("outline")
                
                # Cancel and Destroy buttons on the right
                with ui.row().classes("gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("outline")

                    async def do_destroy() -> None:
                        dialog.close()
                        await _run_terraform_destroy_selected(
                            state, terminal, save_state, destroy_state
                        )

                    ui.button(
                        f"Destroy {destroy_count} Resource{'s' if destroy_count != 1 else ''}",
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
    terminal.info(f"Planning destruction of ALL {resource_count} managed resource{'s' if resource_count != 1 else ''}...")
    terminal.info("")
    
    tf_dir = state.deploy.terraform_dir or "deployments/migration"
    env = _get_terraform_env(state)
    
    # Run plan -destroy for everything (no -target flags)
    result = await asyncio.to_thread(
        subprocess.run,
        ["terraform", "plan", "-destroy", "-no-color"],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    
    # Parse plan output to count resources
    plan_output = result.stdout + result.stderr
    destroy_count = 0
    
    for line in plan_output.split("\n"):
        if line.strip():
            if "will be destroyed" in line:
                terminal.warning(line)
                destroy_count += 1
            elif "Error:" in line or "error:" in line.lower():
                terminal.error(line)
            elif "Warning:" in line:
                terminal.warning(line)
            elif "Plan:" in line:
                terminal.success(line)
            else:
                terminal.info_auto(line)
    
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
            rows.append({
                "address": base_address,
                "type": rtype,
                "name": name,
                "display_name": str(display),
                "mode": mode,
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
                
                rows.append({
                    "address": full_address,
                    "type": rtype,
                    "name": name,
                    "display_name": display,
                    "mode": mode,
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
) -> None:
    """Run terraform destroy for selected resources."""
    selected = sorted(destroy_state.get("selected", []))
    if not selected:
        ui.notify("Select resources first", type="warning")
        return

    tf_dir = state.deploy.terraform_dir or "deployments/migration"

    terminal.clear()
    terminal.set_title("Output — DESTROY (SELECTED)")
    terminal.warning("━━━ TERRAFORM DESTROY (SELECTED) ━━━")
    terminal.warning("")
    terminal.warning(f"Targets: {len(selected)} resources")
    for addr in selected:
        terminal.info(f"  • {addr}")
    terminal.info("")

    env = _get_terraform_env(state)
    target_args = [f"-target={address}" for address in selected]

    result = await asyncio.to_thread(
        subprocess.run,
        ["terraform", "destroy", "-no-color", "-auto-approve", *target_args],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )

    # Track destroyed resources for summary
    destroyed_count = 0

    for line in result.stdout.split("\n"):
        if line.strip():
            if "Destroy complete!" in line or "destroyed" in line.lower():
                terminal.success(line)
                if "destroyed" in line.lower():
                    destroyed_count += 1
            else:
                terminal.info_auto(line)
    for line in result.stderr.split("\n"):
        if line.strip():
            terminal.warning(line)

    if result.returncode == 0:
        terminal.success("")
        terminal.success("━━━ DESTROY SUMMARY ━━━")
        terminal.success(f"Successfully destroyed {destroyed_count} resource(s)")
        state.deploy.destroy_complete = True
        save_state()
        ui.notify(f"Destroyed {destroyed_count} resources", type="positive")
        
        # Refresh the resource table to reflect destroyed resources
        _refresh_resources(state, destroy_state)
        terminal.info("")
        terminal.info("Resource table refreshed.")
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
    """Run terraform destroy for ALL resources (US-048)."""
    tf_dir = state.deploy.terraform_dir or "deployments/migration"
    resources = _load_state_resources(state, destroy_state)

    terminal.clear()
    terminal.set_title("Output — DESTROY ALL")
    terminal.error("━━━ TERRAFORM DESTROY ALL ━━━")
    terminal.error("")
    terminal.warning("⚠️  DESTROYING ALL RESOURCES IN TARGET ACCOUNT")
    terminal.warning(f"    Total resources: {len(resources)}")
    terminal.info("")

    env = _get_terraform_env(state)

    result = await asyncio.to_thread(
        subprocess.run,
        ["terraform", "destroy", "-no-color", "-auto-approve"],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        env=env,
    )

    # Track destroyed resources for summary
    destroyed_resources = []

    for line in result.stdout.split("\n"):
        if line.strip():
            if "Destroy complete!" in line:
                terminal.success(line)
            elif "destroyed" in line.lower():
                terminal.warning(line)
                # Extract resource address if present
                if ":" in line:
                    destroyed_resources.append(line.split(":")[0].strip())
            else:
                terminal.info_auto(line)
    for line in result.stderr.split("\n"):
        if line.strip():
            terminal.warning(line)

    if result.returncode == 0:
        terminal.success("")
        terminal.success("━━━ DESTROY ALL SUMMARY ━━━")
        terminal.success(f"Successfully destroyed {len(destroyed_resources)} resource(s)")
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
        ui.notify(f"Destroyed all {len(destroyed_resources)} resources", type="positive")
        
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
