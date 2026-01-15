"""Deploy step page for generating Terraform files and running deployment."""

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, DeployState
from importer.web.components.terminal_output import TerminalOutput
from importer.web.utils.yaml_viewer import (
    create_state_viewer_dialog,
    create_text_viewer_dialog,
    create_yaml_viewer_dialog,
    get_yaml_stats,
)
from importer.web.components.backend_config import (
    create_backend_config_section,
    write_backend_tf,
)
from importer.web.components.folder_picker import create_folder_picker_dialog


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_NAVY = "#192847"

# Status colors for buttons
STATUS_SUCCESS = "#22C55E"  # green-500
STATUS_WARNING = "#EAB308"  # yellow-500
STATUS_ERROR = "#EF4444"    # red-500


def create_deploy_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the deploy step page content.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to persist state
    """
    # Terminal output for Terraform operations
    terminal = TerminalOutput(show_timestamps=True)
    
    # Track deployment state
    deploy_state = {
        "terraform_dir": None,
        "init_running": False,
        "plan_running": False,
        "apply_running": False,
        "destroy_running": False,
        "backend_config": {
            "type": "local",
            "use_existing": False,
        },
    }

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
        # Page header
        with ui.row().classes("w-full items-center gap-4"):
            ui.icon("rocket_launch", size="2rem").style(f"color: {DBT_ORANGE};")
            ui.label("Deploy to Target Account").classes("text-2xl font-bold")

        ui.label(
            "Generate Terraform configuration and deploy resources to the target dbt Platform account."
        ).classes("text-slate-600 dark:text-slate-400")

        # Prerequisite check
        if not _check_prerequisites(state, on_step_change):
            return

        # Deployment summary
        _create_deployment_summary(state)

        # Output directories section (narrow row above tiles)
        _create_output_directories_section(state, deploy_state)

        # Backend configuration (collapsible)
        with ui.expansion("Backend Configuration", icon="storage").classes("w-full").props("dense"):
            create_backend_config_section(
                backend_config=deploy_state["backend_config"],
            )

        # Tiles: 2x3 grid
        with ui.element("div").classes("w-full").style(
            "display: grid; "
            "grid-template-columns: repeat(3, minmax(0, 1fr)); "
            "gap: 16px; "
            "align-items: stretch;"
        ):
            with ui.column().classes("min-w-0 h-full"):
                _create_generate_section(state, terminal, save_state, deploy_state)
            with ui.column().classes("min-w-0 h-full"):
                _create_init_section(state, terminal, save_state, deploy_state)
            with ui.column().classes("min-w-0 h-full"):
                _create_validate_section(state, terminal, save_state, deploy_state)
            with ui.column().classes("min-w-0 h-full"):
                _create_plan_section(state, terminal, save_state, deploy_state)
            with ui.column().classes("min-w-0 h-full"):
                _create_apply_section(state, terminal, save_state, deploy_state)
            with ui.column().classes("min-w-0 h-full"):
                _create_state_inspection_section(state, deploy_state)

        # Output terminal (full width below tiles)
        with ui.column().classes("w-full"):
            terminal.create(height="450px")

        # Navigation buttons
        _create_navigation_section(state, on_step_change)


def _check_prerequisites(state: AppState, on_step_change: Callable[[WorkflowStep], None]) -> bool:
    """Check if prerequisites are met for deployment."""
    errors = []

    if not state.map.normalize_complete:
        errors.append(("Map step not completed", WorkflowStep.MAP))
    
    if not state.target_credentials.is_complete():
        errors.append(("Target credentials not configured", WorkflowStep.TARGET))

    if errors:
        with ui.card().classes("w-full p-6 border-l-4 border-yellow-500"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("warning", size="lg").classes("text-yellow-500")
                ui.label("Prerequisites Required").classes("text-xl font-semibold")

            ui.label(
                "Complete the following steps before deployment:"
            ).classes("mt-4 text-slate-600 dark:text-slate-400")

            with ui.column().classes("mt-4 gap-2"):
                for error_msg, step in errors:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("error_outline", size="sm").classes("text-yellow-500")
                        ui.label(error_msg)
                        ui.button(
                            f"Go to {state.get_step_label(step)}",
                            on_click=lambda s=step: on_step_change(s),
                        ).props("size=sm outline")

        return False

    return True


def _create_deployment_summary(state: AppState) -> None:
    """Create a summary card showing deployment details with YAML stats."""
    yaml_path = state.map.last_yaml_file
    stats = get_yaml_stats(yaml_path) if yaml_path else {}

    def open_yaml_viewer():
        if yaml_path:
            dialog = create_yaml_viewer_dialog(
                yaml_path,
                title="Deployment Configuration"
            )
            dialog.open()

    with ui.card().classes("w-full"):
        # Header row with title, buttons, and status
        with ui.row().classes("items-center justify-between mb-3"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("summarize", size="md").style(f"color: {DBT_ORANGE};")
                ui.label("Deployment Summary").classes("text-lg font-semibold")

            with ui.row().classes("items-center gap-2"):
                # YAML file reference (compact)
                if yaml_path:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("description", size="xs").classes("text-slate-400")
                        ui.label(yaml_path).classes("text-xs text-slate-500 font-mono truncate max-w-[200px]")
                
                # View YAML button
                if yaml_path:
                    ui.button(
                        "View YAML",
                        icon="visibility",
                        on_click=open_yaml_viewer,
                    ).props("outline size=sm")

                # Status badge
                if state.deploy.apply_complete:
                    ui.badge("Deployed", color="positive").props("rounded")
                elif state.deploy.last_plan_success:
                    ui.badge("Plan Ready", color="info").props("rounded")
                elif state.deploy.terraform_initialized:
                    ui.badge("Initialized", color="warning").props("rounded")

        # Main content: Source/Target on left, Resource stats on right
        with ui.row().classes("w-full gap-6 items-start"):
            # Left side: Source -> Target flow
            with ui.row().classes("gap-4 items-center"):
                # Source
                with ui.column().classes("gap-0"):
                    ui.label("Source").classes("text-xs text-slate-500 uppercase")
                    if state.source_account.account_name:
                        ui.label(state.source_account.account_name).classes("font-medium text-sm")
                    ui.label(f"ID: {state.source_account.account_id}").classes("text-xs text-slate-500")
                    if state.source_account.host_url:
                        source_url = state.source_account.host_url.replace("https://", "").replace("http://", "").rstrip("/")
                        ui.label(source_url).classes("text-xs text-slate-400 font-mono")

                # Arrow
                ui.icon("arrow_forward", size="md").classes("text-slate-400")

                # Target
                with ui.column().classes("gap-0"):
                    ui.label("Target").classes("text-xs text-slate-500 uppercase")
                    if state.target_account.account_name:
                        ui.label(state.target_account.account_name).classes("font-medium text-sm")
                    ui.label(f"ID: {state.target_account.account_id}").classes("text-xs text-slate-500")
                    if state.target_account.host_url:
                        target_url = state.target_account.host_url.replace("https://", "").replace("http://", "").rstrip("/")
                        ui.label(target_url).classes("text-xs text-slate-400 font-mono")

            # Vertical divider
            if stats:
                ui.element("div").classes("w-px bg-slate-200 dark:bg-slate-700 self-stretch")

            # Right side: Resource counts (compact tiles)
            if stats:
                with ui.column().classes("gap-2 flex-grow"):
                    # Project resources row
                    project_stats = {k: v for k, v in stats.items() 
                                  if k in ["projects", "environments", "jobs", "environment_variables"] and v > 0}
                    
                    if project_stats:
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Project:").classes("text-xs text-slate-500 w-14")
                            with ui.row().classes("gap-2 flex-wrap"):
                                for resource, count in project_stats.items():
                                    with ui.row().classes("items-center gap-1 px-2 py-1 bg-slate-50 dark:bg-slate-800 rounded"):
                                        ui.label(str(count)).classes("text-sm font-bold")
                                        ui.label(resource.replace("_", " ").title()).classes("text-xs text-slate-500")

                    # Global resources row
                    global_stats = {k: v for k, v in stats.items() 
                                  if k in ["connections", "repositories", "service_tokens", "groups", 
                                          "notifications", "privatelink_endpoints"] and v > 0}
                    
                    if global_stats:
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Global:").classes("text-xs text-slate-500 w-14")
                            with ui.row().classes("gap-2 flex-wrap"):
                                for resource, count in global_stats.items():
                                    with ui.row().classes("items-center gap-1 px-2 py-1 bg-slate-50 dark:bg-slate-800 rounded"):
                                        ui.label(str(count)).classes("text-sm font-bold")
                                        ui.label(resource.replace("_", " ").title()).classes("text-xs text-slate-500")

                    # Total
                    total = sum(stats.values())
                    ui.label(f"Total: {total} resources").classes("text-xs text-slate-500")


def _create_output_directories_section(state: AppState, deploy_state: dict) -> None:
    """Create the output directories configuration section above tiles."""
    # Initialize default paths
    default_tf_dir = state.deploy.terraform_dir or "deployments/migration"
    
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-end gap-4"):
            # Terraform output directory
            with ui.column().classes("flex-grow"):
                ui.label("Terraform Output Directory").classes("text-sm font-medium mb-1")
                with ui.row().classes("w-full items-center gap-2"):
                    tf_dir_input = ui.input(
                        value=default_tf_dir,
                        placeholder="deployments/migration",
                    ).classes("flex-grow").props("outlined dense")
                    deploy_state["tf_dir_input"] = tf_dir_input
                    
                    def open_tf_folder_picker():
                        def on_select(path: str):
                            tf_dir_input.value = path
                            deploy_state["terraform_dir"] = path
                        
                        dialog = create_folder_picker_dialog(
                            initial_path=tf_dir_input.value or ".",
                            title="Select Terraform Output Directory",
                            on_select=on_select,
                        )
                        dialog.open()
                    
                    ui.button(
                        icon="folder_open",
                        on_click=open_tf_folder_picker,
                    ).props("flat dense")
            
            # State file location (read-only info)
            with ui.column().classes("flex-grow"):
                ui.label("State File Location").classes("text-sm font-medium mb-1")
                with ui.row().classes("w-full items-center gap-2"):
                    state_path_display = ui.input(
                        value=f"{default_tf_dir}/terraform.tfstate",
                        placeholder="(determined by backend config)",
                    ).classes("flex-grow").props("outlined dense readonly")
                    deploy_state["state_path_display"] = state_path_display
                    
                    ui.icon("info", size="sm").classes("text-slate-400").tooltip(
                        "State file location is determined by the backend configuration. "
                        "For local backend, it's stored in the Terraform output directory."
                    )
            
            # Update state path when tf_dir changes
            def on_tf_dir_change(e):
                if e.value:
                    deploy_state["terraform_dir"] = e.value
                    state_path_display.value = f"{e.value}/terraform.tfstate"
            
            tf_dir_input.on("change", on_tf_dir_change)


def _create_generate_section(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Create the generate Terraform files section."""
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
    
    # Get output directory from shared state
    def get_output_dir():
        if "tf_dir_input" in deploy_state:
            return deploy_state["tf_dir_input"].value
        return deploy_state.get("terraform_dir") or state.deploy.terraform_dir or "deployments/migration"
    
    with ui.card().classes("w-full h-full").style("display: flex; flex-direction: column;"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.badge("1", color="primary").props("rounded")
            ui.label("Generate Terraform Files").classes("font-semibold")
            
            # Dynamic checkmark - stored in deploy_state for updating
            checkmark = ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")
            checkmark.visible = state.deploy.files_generated
            deploy_state["generate_checkmark"] = checkmark

        ui.label(
            "Generate Terraform configuration from your normalized YAML."
        ).classes("text-sm text-slate-500 flex-grow")

        # Buttons at bottom - action button above view button
        with ui.column().classes("w-full gap-2 mt-auto"):
            # Determine button state
            is_complete = state.deploy.files_generated
            
            generate_btn = ui.button(
                "Generate Files",
                icon="code",
                on_click=lambda: _run_generate(
                    state, terminal, save_state, deploy_state, get_output_dir()
                ),
            ).classes("w-full")
            
            # Style based on state: blue when enabled, green when complete
            if is_complete:
                generate_btn.style(f"background-color: {STATUS_SUCCESS};")
            else:
                generate_btn.style(f"background-color: {DBT_ORANGE};")
            
            deploy_state["generate_btn"] = generate_btn
            
            # View Generate Output button
            def open_generate_viewer():
                output = deploy_state.get("last_generate_output") or state.deploy.last_generate_output
                if not output:
                    ui.notify("No generate output available. Run generate first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(output, "Generate Output")
                dialog.open()
            
            has_output = deploy_state.get("last_generate_output") or state.deploy.last_generate_output
            view_btn = ui.button(
                "View Output",
                icon="visibility",
                on_click=open_generate_viewer,
            ).props("outline").classes("w-full")
            
            # White text when output available
            if has_output:
                view_btn.style("color: white; background-color: rgba(255,255,255,0.1);")
            
            deploy_state["generate_view_btn"] = view_btn
            
            if not has_output:
                view_btn.disable()
                view_btn.tooltip("Run generate first")


def _create_init_section(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Create the Terraform init section."""
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
    
    with ui.card().classes("w-full h-full").style("display: flex; flex-direction: column;"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.badge("2", color="primary").props("rounded")
            ui.label("Initialize Terraform").classes("font-semibold")
            
            # Dynamic checkmark - stored in deploy_state for updating
            checkmark = ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")
            checkmark.visible = state.deploy.terraform_initialized
            deploy_state["init_checkmark"] = checkmark

        ui.label(
            "Initialize the Terraform working directory and download providers."
        ).classes("text-sm text-slate-500 flex-grow")

        # Buttons at bottom
        with ui.column().classes("w-full gap-2 mt-auto"):
            # Determine button states
            is_enabled = state.deploy.files_generated
            is_complete = state.deploy.terraform_initialized
            
            init_btn = ui.button(
                "Run terraform init",
                icon="download",
                on_click=lambda: _run_terraform_init(
                    state, terminal, save_state, deploy_state
                ),
            ).classes("w-full")
            
            # Style based on state
            if is_complete:
                init_btn.style(f"background-color: {STATUS_SUCCESS};")
            elif is_enabled:
                init_btn.style(f"background-color: {DBT_ORANGE};")
            else:
                init_btn.props("outline").style("opacity: 0.5;")
                init_btn.disable()
                init_btn.tooltip("Generate files first")
            
            deploy_state["init_btn"] = init_btn
            
            # View Init Output button
            def open_init_viewer():
                output = deploy_state.get("last_init_output") or state.deploy.last_init_output
                if not output:
                    ui.notify("No init output available. Run init first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(output, "Terraform Init Output")
                dialog.open()
            
            has_output = deploy_state.get("last_init_output") or state.deploy.last_init_output
            view_btn = ui.button(
                "View Output",
                icon="visibility",
                on_click=open_init_viewer,
            ).props("outline").classes("w-full")
            
            if has_output:
                view_btn.style("color: white; background-color: rgba(255,255,255,0.1);")
            
            deploy_state["init_view_btn"] = view_btn
            
            if not has_output:
                view_btn.disable()
                view_btn.tooltip("Run init first")


def _create_validate_section(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Create the Terraform validate section."""
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
    
    with ui.card().classes("w-full h-full").style("display: flex; flex-direction: column;"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.badge("3", color="primary").props("rounded")
            ui.label("Validate Configuration").classes("font-semibold")
            
            # Dynamic checkmark - stored in deploy_state for updating
            checkmark = ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")
            checkmark.visible = state.deploy.last_validate_success
            deploy_state["validate_checkmark"] = checkmark

        ui.label(
            "Validate the Terraform configuration for syntax and consistency errors."
        ).classes("text-sm text-slate-500 flex-grow")

        # Buttons at bottom
        with ui.column().classes("w-full gap-2 mt-auto"):
            # Determine button states
            is_enabled = state.deploy.terraform_initialized
            is_complete = state.deploy.last_validate_success
            
            validate_btn = ui.button(
                "Run terraform validate",
                icon="check",
                on_click=lambda: _run_terraform_validate(
                    state, terminal, save_state, deploy_state
                ),
            ).classes("w-full")
            
            # Style based on state
            if is_complete:
                validate_btn.style(f"background-color: {STATUS_SUCCESS};")
            elif is_enabled:
                validate_btn.style(f"background-color: {DBT_ORANGE};")
            else:
                validate_btn.props("outline").style("opacity: 0.5;")
                validate_btn.disable()
                validate_btn.tooltip("Run init first")
            
            deploy_state["validate_btn"] = validate_btn
            
            # View Validate Output button
            def open_validate_viewer():
                output = deploy_state.get("last_validate_output") or state.deploy.last_validate_output
                if not output:
                    ui.notify("No validate output available. Run validate first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(output, "Terraform Validate Output")
                dialog.open()
            
            has_output = deploy_state.get("last_validate_output") or state.deploy.last_validate_output
            view_btn = ui.button(
                "View Output",
                icon="visibility",
                on_click=open_validate_viewer,
            ).props("outline").classes("w-full")
            
            if has_output:
                view_btn.style("color: white; background-color: rgba(255,255,255,0.1);")
            
            deploy_state["validate_view_btn"] = view_btn
            
            if not has_output:
                view_btn.disable()
                view_btn.tooltip("Run validate first")


def _create_plan_section(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Create the Terraform plan section."""
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
    
    with ui.card().classes("w-full h-full").style("display: flex; flex-direction: column;"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.badge("4", color="primary").props("rounded")
            ui.label("Plan Deployment").classes("font-semibold")
            
            # Dynamic checkmark - stored in deploy_state for updating
            checkmark = ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")
            checkmark.visible = state.deploy.last_plan_success
            deploy_state["plan_checkmark"] = checkmark

        ui.label(
            "Preview the changes that will be made to the target account."
        ).classes("text-sm text-slate-500 flex-grow")

        # Buttons at bottom
        with ui.column().classes("w-full gap-2 mt-auto"):
            # Determine button states
            is_enabled = state.deploy.terraform_initialized
            is_complete = state.deploy.last_plan_success
            
            plan_btn = ui.button(
                "Run terraform plan",
                icon="preview",
                on_click=lambda: _run_terraform_plan(
                    state, terminal, save_state, deploy_state
                ),
            ).classes("w-full")
            
            # Style based on state
            if is_complete:
                plan_btn.style(f"background-color: {STATUS_SUCCESS};")
            elif is_enabled:
                plan_btn.style(f"background-color: {DBT_ORANGE};")
            else:
                plan_btn.props("outline").style("opacity: 0.5;")
                plan_btn.disable()
                plan_btn.tooltip("Run init first")
            
            deploy_state["plan_btn"] = plan_btn
            
            # View Plan button - opens dialog to view full plan output
            def open_plan_viewer():
                plan_output = deploy_state.get("last_plan_output") or state.deploy.last_plan_output
                if not plan_output:
                    ui.notify("No plan output available. Run plan first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(plan_output, "Terraform Plan")
                dialog.open()
            
            has_output = deploy_state.get("last_plan_output") or state.deploy.last_plan_output
            view_plan_btn = ui.button(
                "View Plan",
                icon="visibility",
                on_click=open_plan_viewer,
            ).props("outline").classes("w-full")
            
            if has_output:
                view_plan_btn.style("color: white; background-color: rgba(255,255,255,0.1);")
            
            deploy_state["plan_view_btn"] = view_plan_btn
            
            # Disable if no plan output exists yet
            if not has_output:
                view_plan_btn.disable()
                view_plan_btn.tooltip("Run plan first")


def _create_apply_section(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Create the Terraform apply section."""
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
    
    with ui.card().classes("w-full h-full").style("display: flex; flex-direction: column;"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.badge("5", color="primary").props("rounded")
            ui.label("Apply Changes").classes("font-semibold")
            
            # Dynamic checkmark - stored in deploy_state for updating
            apply_checkmark = ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")
            apply_checkmark.visible = state.deploy.apply_complete
            deploy_state["apply_checkmark"] = apply_checkmark

        ui.label(
            "Deploy resources to the target dbt Platform account."
        ).classes("text-sm text-slate-500 flex-grow")

        # Buttons at bottom
        with ui.column().classes("w-full gap-2 mt-auto"):
            # Determine button states
            is_enabled = state.deploy.last_plan_success
            is_complete = state.deploy.apply_complete
            
            async def on_apply_click():
                await _confirm_apply(state, terminal, save_state, deploy_state)
            
            apply_btn = ui.button(
                "Run terraform apply",
                icon="rocket_launch",
                on_click=on_apply_click,
            ).classes("w-full")
            
            # Style based on state
            if is_complete:
                apply_btn.style(f"background-color: {STATUS_SUCCESS};")
            elif is_enabled:
                apply_btn.style(f"background-color: {DBT_ORANGE};")
            else:
                apply_btn.props("outline").style("opacity: 0.5;")
                apply_btn.disable()
                apply_btn.tooltip("Run plan first")
            
            deploy_state["apply_btn"] = apply_btn
            
            # View Apply Output button
            def open_apply_viewer():
                output = deploy_state.get("last_apply_output") or state.deploy.last_apply_output
                if not output:
                    ui.notify("No apply output available. Run apply first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(output, "Terraform Apply Output")
                dialog.open()
            
            has_output = deploy_state.get("last_apply_output") or state.deploy.last_apply_output
            view_btn = ui.button(
                "View Output",
                icon="visibility",
                on_click=open_apply_viewer,
            ).props("outline").classes("w-full")
            
            if has_output:
                view_btn.style("color: white; background-color: rgba(255,255,255,0.1);")
            
            deploy_state["apply_view_btn"] = view_btn
            
            if not has_output:
                view_btn.disable()
                view_btn.tooltip("Run apply first")


def _get_state_file_path(state: AppState, deploy_state: dict) -> Optional[str]:
    """Get the current terraform state file path if it exists."""
    tf_dir = (
        deploy_state.get("terraform_dir")
        or state.deploy.terraform_dir
        or "deployments/migration"
    )
    state_path = Path(tf_dir) / "terraform.tfstate"
    if state_path.exists():
        return str(state_path)
    return None


def _create_state_inspection_section(
    state: AppState,
    deploy_state: dict,
) -> None:
    """Create the Terraform state inspection section."""
    state_path = _get_state_file_path(state, deploy_state)

    def open_state_viewer() -> None:
        # Re-check state path in case it was created after page load
        current_state_path = _get_state_file_path(state, deploy_state)
        if not current_state_path:
            ui.notify("No terraform state file found", type="warning")
            return
        dialog = create_state_viewer_dialog(
            current_state_path,
            title="Terraform State",
        )
        dialog.open()

    with ui.card().classes("w-full h-full").style("display: flex; flex-direction: column;"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.badge("Optional", color="grey").props("rounded")
            ui.label("Inspect Terraform State").classes("font-semibold")

        ui.label(
            "Review the current Terraform state file with sensitive value masking."
        ).classes("text-sm text-slate-500")

        if state_path:
            ui.label(state_path).classes("text-xs text-slate-500 font-mono truncate flex-grow")
        else:
            ui.label("No state file available yet.").classes("text-xs text-slate-500 flex-grow")

        # Button at bottom
        with ui.column().classes("w-full gap-2 mt-auto"):
            view_btn = ui.button(
                "View State",
                icon="visibility",
                on_click=open_state_viewer,
            ).props("outline").classes("w-full")
            
            if state_path:
                view_btn.style("color: white; background-color: rgba(255,255,255,0.1);")
            else:
                view_btn.disable()
                view_btn.tooltip("Generate, init, and apply to create state")


def _create_navigation_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create the navigation buttons section."""
    with ui.row().classes("w-full justify-between mt-6"):
        # Back button
        ui.button(
            f"Back to {state.get_step_label(WorkflowStep.TARGET)}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.TARGET),
        ).props("outline")

        # Status
        if state.deploy.apply_complete:
            with ui.row().classes("items-center gap-2"):
                ui.icon("check_circle", size="md").classes("text-green-500")
                ui.label("Deployment Complete!").classes("text-green-500 font-semibold")


# Terraform operation handlers

async def _run_generate(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
    output_dir: str,
) -> None:
    """Generate Terraform files from YAML configuration."""
    terminal.set_title("Output — GENERATE")
    terminal.clear()
    terminal.info("Generating Terraform configuration files...")
    terminal.info("")
    
    # Reset all downstream checkmarks and state when regenerating
    # This ensures a clean state for the new deployment
    state.deploy.terraform_initialized = False
    state.deploy.last_validate_success = False
    state.deploy.last_plan_success = False
    state.deploy.apply_complete = False
    
    # Reset checkmark visibility in UI
    for checkmark_key in ["init_checkmark", "validate_checkmark", "plan_checkmark", "apply_checkmark"]:
        if checkmark_key in deploy_state:
            deploy_state[checkmark_key].visible = False
    
    # Disable downstream buttons since we're regenerating
    # Init will be re-enabled after successful generation
    # Note: style("") clears inline styles, then we add outline + opacity to match initial state
    if "init_btn" in deploy_state:
        deploy_state["init_btn"].disable()
        deploy_state["init_btn"].props("outline")
        deploy_state["init_btn"].style("")  # Clear all inline styles
        deploy_state["init_btn"].style("opacity: 0.5;")
        deploy_state["init_btn"].tooltip("Generate files first")
    if "init_view_btn" in deploy_state:
        deploy_state["init_view_btn"].disable()
        deploy_state["init_view_btn"].tooltip("Run init first")
    if "validate_btn" in deploy_state:
        deploy_state["validate_btn"].disable()
        deploy_state["validate_btn"].props("outline")
        deploy_state["validate_btn"].style("")  # Clear all inline styles
        deploy_state["validate_btn"].style("opacity: 0.5;")
        deploy_state["validate_btn"].tooltip("Run init first")
    if "validate_view_btn" in deploy_state:
        deploy_state["validate_view_btn"].disable()
        deploy_state["validate_view_btn"].tooltip("Run validate first")
    if "plan_btn" in deploy_state:
        deploy_state["plan_btn"].disable()
        deploy_state["plan_btn"].props("outline")
        deploy_state["plan_btn"].style("")  # Clear all inline styles
        deploy_state["plan_btn"].style("opacity: 0.5;")
        deploy_state["plan_btn"].tooltip("Run init first")
    if "plan_view_btn" in deploy_state:
        deploy_state["plan_view_btn"].disable()
        deploy_state["plan_view_btn"].tooltip("Run plan first")
    if "apply_btn" in deploy_state:
        deploy_state["apply_btn"].disable()
        deploy_state["apply_btn"].props("outline")
        deploy_state["apply_btn"].style("")  # Clear all inline styles
        deploy_state["apply_btn"].style("opacity: 0.5;")
        deploy_state["apply_btn"].tooltip("Run plan first")
    if "apply_view_btn" in deploy_state:
        deploy_state["apply_view_btn"].disable()
        deploy_state["apply_view_btn"].tooltip("Run apply first")

    try:
        # Check if YAML file exists
        yaml_file = state.map.last_yaml_file
        if not yaml_file or not Path(yaml_file).exists():
            terminal.error(f"YAML configuration file not found: {yaml_file}")
            ui.notify("YAML file not found", type="negative")
            return

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        terminal.info(f"Source YAML: {yaml_file}")
        terminal.info(f"Output directory: {output_path}")
        terminal.info("")

        # Generate the Terraform files using the converter
        from importer.yaml_converter import YamlToTerraformConverter
        
        # Show target info (credentials are passed via TF_VAR_* env vars at runtime)
        target_host = state.target_credentials.host_url
        target_id = state.target_credentials.account_id
        terminal.info(f"Target account: {target_id} @ {target_host}")
        terminal.info("Credentials will be passed via TF_VAR_* environment variables")
        terminal.info("")
        
        converter = YamlToTerraformConverter()
        await asyncio.to_thread(
            converter.convert,
            yaml_file,
            str(output_path),
        )

        # Generate backend.tf if configured
        backend_config = deploy_state.get("backend_config", {})
        if not backend_config.get("use_existing", False):
            backend_file = write_backend_tf(backend_config, str(output_path))
            if backend_file:
                terminal.info(f"Generated backend configuration: {Path(backend_file).name}")

        terminal.success("Terraform files generated!")
        terminal.info("")
        
        # List generated files
        tf_files = list(output_path.glob("*.tf"))
        tfvars_files = list(output_path.glob("*.tfvars"))
        yaml_files = list(output_path.glob("*.yml")) + list(output_path.glob("*.yaml"))
        
        all_files = tf_files + tfvars_files + yaml_files
        terminal.info(f"Generated {len(all_files)} file(s):")
        for f in sorted(all_files, key=lambda x: x.name):
            terminal.info(f"  • {f.name}")

        deploy_state["terraform_dir"] = str(output_path)
        
        # Persist to state for cross-page-load access
        state.deploy.files_generated = True
        state.deploy.terraform_dir = str(output_path)
        
        # Store output for View button
        output_text = terminal.get_text()
        deploy_state["last_generate_output"] = output_text
        state.deploy.last_generate_output = output_text
        
        save_state()
        
        # Update UI elements
        if "generate_checkmark" in deploy_state:
            deploy_state["generate_checkmark"].visible = True
        if "generate_view_btn" in deploy_state:
            deploy_state["generate_view_btn"].enable()
            deploy_state["generate_view_btn"].tooltip("")
        
        # Enable downstream buttons now that files are generated
        if "init_btn" in deploy_state:
            deploy_state["init_btn"].enable()
            deploy_state["init_btn"].props(remove="outline")
            deploy_state["init_btn"].style("")  # Clear all inline styles first
            deploy_state["init_btn"].style(f"background-color: {DBT_ORANGE};")
            deploy_state["init_btn"].tooltip("")
        
        # Update generate button to show success state (green)
        if "generate_btn" in deploy_state:
            deploy_state["generate_btn"].style(f"background-color: {STATUS_SUCCESS};")

        ui.notify("Terraform files generated successfully", type="positive")

    except Exception as e:
        terminal.error(f"Generation failed: {e}")
        ui.notify(f"Generation failed: {e}", type="negative")


def _get_terraform_env(state: AppState) -> dict:
    """Get environment variables for Terraform commands.
    
    Sets TF_VAR_* variables for terraform input variables and
    DBT_CLOUD_* for provider fallback (same pattern as e2e test).
    
    Requires credentials to be loaded via the Target step.
    """
    import os
    
    env = dict(os.environ)
    
    # Get credentials from state (must be loaded via Target step)
    api_token = state.target_credentials.api_token
    account_id = state.target_credentials.account_id
    host_url = state.target_credentials.host_url
    
    # Normalize host URL: strip trailing slash and ensure /api suffix
    # This matches the e2e test pattern
    base_host = (host_url or "https://cloud.getdbt.com").rstrip("/")
    if not base_host.endswith("/api"):
        host_url = f"{base_host}/api"
    else:
        host_url = base_host
    
    # TF_VAR_* for terraform input variables
    env["TF_VAR_dbt_account_id"] = str(account_id)
    env["TF_VAR_dbt_token"] = api_token
    env["TF_VAR_dbt_host_url"] = host_url
    
    # DBT_CLOUD_* for provider fallback
    env["DBT_CLOUD_ACCOUNT_ID"] = str(account_id)
    env["DBT_CLOUD_TOKEN"] = api_token
    env["DBT_CLOUD_HOST_URL"] = host_url
    
    return env


async def _run_terraform_init(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Run terraform init."""
    # Check if terraform is available
    if not shutil.which("terraform"):
        terminal.error("Terraform not found in PATH")
        terminal.warning("Please install Terraform: https://developer.hashicorp.com/terraform/downloads")
        ui.notify("Terraform not installed", type="negative")
        return

    tf_dir = deploy_state.get("terraform_dir") or state.deploy.terraform_dir or "deployments/migration"
    if not Path(tf_dir).exists():
        terminal.error(f"Terraform directory not found: {tf_dir}")
        terminal.warning("Generate Terraform files first")
        ui.notify("Generate files first", type="warning")
        return

    terminal.set_title("Output — INIT")
    terminal.clear()
    terminal.info(f"Running terraform init in {tf_dir}...")
    terminal.info("")

    deploy_state["init_running"] = True

    try:
        # Set TF_VAR_* environment variables for terraform
        env = _get_terraform_env(state)
        
        result = await asyncio.to_thread(
            subprocess.run,
            ["terraform", "init", "-no-color"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        # Output stdout (auto-detect warnings/errors)
        for line in result.stdout.split("\n"):
            if line.strip():
                terminal.info_auto(line)

        # Output stderr
        for line in result.stderr.split("\n"):
            if line.strip():
                terminal.warning(line)

        if result.returncode == 0:
            terminal.success("")
            terminal.success("Terraform initialized successfully!")
            state.deploy.terraform_initialized = True
            
            # Store output for View button
            output_text = terminal.get_text()
            deploy_state["last_init_output"] = output_text
            state.deploy.last_init_output = output_text
            
            save_state()
            
            # Detect warnings in output
            has_warnings = "warning" in result.stdout.lower() or "warning" in result.stderr.lower()
            
            # Update UI elements
            if "init_checkmark" in deploy_state:
                deploy_state["init_checkmark"].visible = True
            if "init_view_btn" in deploy_state:
                deploy_state["init_view_btn"].enable()
                deploy_state["init_view_btn"].tooltip("")
            
            # Update init button color based on result
            if "init_btn" in deploy_state:
                deploy_state["init_btn"].props(remove="outline")
                deploy_state["init_btn"].style("")  # Clear all inline styles
                if has_warnings:
                    deploy_state["init_btn"].style(f"background-color: {STATUS_WARNING}; color: black;")
                else:
                    deploy_state["init_btn"].style(f"background-color: {STATUS_SUCCESS};")
            
            # Enable downstream buttons now that init is complete
            if "validate_btn" in deploy_state:
                deploy_state["validate_btn"].enable()
                deploy_state["validate_btn"].props(remove="outline")
                deploy_state["validate_btn"].style("")  # Clear all inline styles first
                deploy_state["validate_btn"].style(f"background-color: {DBT_ORANGE};")
                deploy_state["validate_btn"].tooltip("")
            if "plan_btn" in deploy_state:
                deploy_state["plan_btn"].enable()
                deploy_state["plan_btn"].props(remove="outline")
                deploy_state["plan_btn"].style("")  # Clear all inline styles first
                deploy_state["plan_btn"].style(f"background-color: {DBT_ORANGE};")
                deploy_state["plan_btn"].tooltip("")
            
            if has_warnings:
                ui.notify("Terraform initialized with warnings", type="warning")
            else:
                ui.notify("Terraform initialized", type="positive")
        else:
            terminal.error("")
            terminal.error(f"Terraform init failed with exit code {result.returncode}")
            
            # Still store output for troubleshooting
            output_text = terminal.get_text()
            deploy_state["last_init_output"] = output_text
            state.deploy.last_init_output = output_text
            if "init_view_btn" in deploy_state:
                deploy_state["init_view_btn"].enable()
                deploy_state["init_view_btn"].tooltip("")
            
            # Update init button to show error state (red)
            if "init_btn" in deploy_state:
                deploy_state["init_btn"].props(remove="outline")
                deploy_state["init_btn"].style("")  # Clear all inline styles
                deploy_state["init_btn"].style(f"background-color: {STATUS_ERROR}; color: white;")
            
            ui.notify("Init failed", type="negative")

    except Exception as e:
        terminal.error(f"Error running terraform: {e}")
        ui.notify(f"Error: {e}", type="negative")

    finally:
        deploy_state["init_running"] = False


async def _run_terraform_validate(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Run terraform validate."""
    # Check if terraform is available
    if not shutil.which("terraform"):
        terminal.error("Terraform not found in PATH")
        terminal.warning("Please install Terraform: https://developer.hashicorp.com/terraform/downloads")
        ui.notify("Terraform not installed", type="negative")
        return

    tf_dir = deploy_state.get("terraform_dir") or state.deploy.terraform_dir or "deployments/migration"
    if not Path(tf_dir).exists():
        terminal.error(f"Terraform directory not found: {tf_dir}")
        terminal.warning("Generate Terraform files first")
        ui.notify("Generate files first", type="warning")
        return

    if not state.deploy.terraform_initialized:
        terminal.warning("Run terraform init first")
        ui.notify("Run init first", type="warning")
        return

    terminal.set_title("Output — VALIDATE")
    terminal.clear()
    terminal.info(f"Running terraform validate in {tf_dir}...")
    terminal.info("")

    deploy_state["validate_running"] = True

    try:
        # Set TF_VAR_* environment variables for terraform
        env = _get_terraform_env(state)
        
        result = await asyncio.to_thread(
            subprocess.run,
            ["terraform", "validate", "-no-color"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        # Output stdout (auto-detect warnings/errors)
        for line in result.stdout.split("\n"):
            if line.strip():
                terminal.info_auto(line)

        # Output stderr
        for line in result.stderr.split("\n"):
            if line.strip():
                terminal.warning(line)

        if result.returncode == 0:
            terminal.success("")
            terminal.success("Configuration is valid!")
            state.deploy.last_validate_success = True
            
            # Store output for View button
            output_text = terminal.get_text()
            deploy_state["last_validate_output"] = output_text
            state.deploy.last_validate_output = output_text
            
            save_state()
            
            # Detect warnings in output
            has_warnings = "warning" in result.stdout.lower() or "warning" in result.stderr.lower()
            
            # Update UI elements
            if "validate_checkmark" in deploy_state:
                deploy_state["validate_checkmark"].visible = True
            if "validate_view_btn" in deploy_state:
                deploy_state["validate_view_btn"].enable()
                deploy_state["validate_view_btn"].tooltip("")
            
            # Update validate button color based on result
            if "validate_btn" in deploy_state:
                deploy_state["validate_btn"].props(remove="outline")
                deploy_state["validate_btn"].style("")  # Clear all inline styles
                if has_warnings:
                    deploy_state["validate_btn"].style(f"background-color: {STATUS_WARNING}; color: black;")
                else:
                    deploy_state["validate_btn"].style(f"background-color: {STATUS_SUCCESS};")
            
            if has_warnings:
                ui.notify("Configuration valid with warnings", type="warning")
            else:
                ui.notify("Configuration validated successfully", type="positive")
        else:
            terminal.error("")
            terminal.error(f"Validation failed with exit code {result.returncode}")
            state.deploy.last_validate_success = False
            
            # Still store output for troubleshooting
            output_text = terminal.get_text()
            deploy_state["last_validate_output"] = output_text
            state.deploy.last_validate_output = output_text
            if "validate_view_btn" in deploy_state:
                deploy_state["validate_view_btn"].enable()
                deploy_state["validate_view_btn"].tooltip("")
            
            # Update validate button to show error state (red)
            if "validate_btn" in deploy_state:
                deploy_state["validate_btn"].props(remove="outline")
                deploy_state["validate_btn"].style("")  # Clear all inline styles
                deploy_state["validate_btn"].style(f"background-color: {STATUS_ERROR}; color: white;")
            
            save_state()
            ui.notify("Validation failed", type="negative")

    except Exception as e:
        terminal.error(f"Error running terraform: {e}")
        ui.notify(f"Error: {e}", type="negative")

    finally:
        deploy_state["validate_running"] = False


async def _run_terraform_plan(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Run terraform plan."""
    if not state.deploy.terraform_initialized:
        terminal.warning("Run terraform init first")
        ui.notify("Run init first", type="warning")
        return

    tf_dir = deploy_state.get("terraform_dir") or state.deploy.terraform_dir or "deployments/migration"
    
    terminal.set_title("Output — PLAN")
    terminal.clear()
    terminal.info(f"Running terraform plan in {tf_dir}...")
    terminal.info("")

    deploy_state["plan_running"] = True

    try:
        # Set TF_VAR_* environment variables for terraform
        env = _get_terraform_env(state)

        result = await asyncio.to_thread(
            subprocess.run,
            ["terraform", "plan", "-no-color", "-out=tfplan"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        # Output stdout
        for line in result.stdout.split("\n"):
            if line.strip():
                # Color-code plan output
                if "+" in line and "create" in line.lower():
                    terminal.success(line)
                elif "-" in line and "destroy" in line.lower():
                    terminal.error(line)
                elif "~" in line and "change" in line.lower():
                    terminal.warning(line)
                else:
                    terminal.info_auto(line)

        # Output stderr
        for line in result.stderr.split("\n"):
            if line.strip():
                terminal.warning(line)

        if result.returncode == 0:
            terminal.success("")
            terminal.success("Plan complete!")
            state.deploy.last_plan_success = True
            state.deploy.last_plan_output = result.stdout
            deploy_state["last_plan_output"] = result.stdout  # Store for View Plan button
            save_state()
            
            # Detect warnings in output
            has_warnings = "warning" in result.stdout.lower() or "warning" in result.stderr.lower()
            
            # Update UI elements
            if "plan_checkmark" in deploy_state:
                deploy_state["plan_checkmark"].visible = True
            if "plan_view_btn" in deploy_state:
                deploy_state["plan_view_btn"].enable()
                deploy_state["plan_view_btn"].tooltip("")
            
            # Update plan button color based on result
            if "plan_btn" in deploy_state:
                deploy_state["plan_btn"].props(remove="outline")
                deploy_state["plan_btn"].style("")  # Clear all inline styles
                if has_warnings:
                    deploy_state["plan_btn"].style(f"background-color: {STATUS_WARNING}; color: black;")
                else:
                    deploy_state["plan_btn"].style(f"background-color: {STATUS_SUCCESS};")
            
            if "apply_btn" in deploy_state:
                deploy_state["apply_btn"].enable()
                deploy_state["apply_btn"].props(remove="outline")
                deploy_state["apply_btn"].style("")  # Clear all inline styles first
                deploy_state["apply_btn"].style(f"background-color: {DBT_ORANGE};")
                deploy_state["apply_btn"].tooltip("")
            
            if has_warnings:
                ui.notify("Plan succeeded with warnings", type="warning")
            else:
                ui.notify("Plan succeeded", type="positive")
            
            # Auto-open the plan viewer dialog
            from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
            dialog = create_plan_viewer_dialog(result.stdout, "Terraform Plan")
            dialog.open()
        else:
            terminal.error("")
            terminal.error(f"Plan failed with exit code {result.returncode}")
            state.deploy.last_plan_success = False
            deploy_state["last_plan_output"] = result.stdout + "\n" + result.stderr  # Store output for troubleshooting
            if "plan_view_btn" in deploy_state:
                deploy_state["plan_view_btn"].enable()
                deploy_state["plan_view_btn"].tooltip("")
            
            # Update plan button to show error state (red)
            if "plan_btn" in deploy_state:
                deploy_state["plan_btn"].props(remove="outline")
                deploy_state["plan_btn"].style("")  # Clear all inline styles
                deploy_state["plan_btn"].style(f"background-color: {STATUS_ERROR}; color: white;")
            
            if "apply_btn" in deploy_state:
                deploy_state["apply_btn"].disable()
                deploy_state["apply_btn"].tooltip("Run plan first")
            save_state()
            ui.notify("Plan failed", type="negative")

    except Exception as e:
        terminal.error(f"Error running terraform: {e}")
        ui.notify(f"Error: {e}", type="negative")

    finally:
        deploy_state["plan_running"] = False


def _parse_plan_summary(plan_output: str) -> dict:
    """Parse terraform plan output to extract add/change/destroy counts."""
    import re
    
    summary = {"add": 0, "change": 0, "destroy": 0}
    
    # Look for the "Plan: X to add, Y to change, Z to destroy" line
    match = re.search(r"Plan:\s*(\d+)\s*to add,\s*(\d+)\s*to change,\s*(\d+)\s*to destroy", plan_output)
    if match:
        summary["add"] = int(match.group(1))
        summary["change"] = int(match.group(2))
        summary["destroy"] = int(match.group(3))
    else:
        # Fallback: count individual resource lines
        for line in plan_output.split("\n"):
            if "will be created" in line:
                summary["add"] += 1
            elif "will be updated" in line or "will be changed" in line:
                summary["change"] += 1
            elif "will be destroyed" in line:
                summary["destroy"] += 1
    
    return summary


async def _confirm_apply(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Show confirmation dialog before applying changes."""
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
    
    if not state.deploy.last_plan_success:
        terminal.warning("Run terraform plan first")
        ui.notify("Run plan first", type="warning")
        return
    
    # Get plan output and parse summary
    plan_output = deploy_state.get("last_plan_output") or state.deploy.last_plan_output or ""
    summary = _parse_plan_summary(plan_output)
    
    total_changes = summary["add"] + summary["change"] + summary["destroy"]
    
    with ui.dialog() as dialog:
        with ui.card().classes("w-full max-w-lg"):
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.icon("rocket_launch", size="md").classes("text-orange-500")
                ui.label("Confirm Apply").classes("text-lg font-semibold")
            
            ui.label(
                "You are about to apply the planned changes to your dbt Cloud account. "
                "Please review the summary below."
            ).classes("text-sm text-slate-600 dark:text-slate-400 mt-2")
            
            # Change summary badges
            with ui.row().classes("w-full gap-3 mt-4 justify-center"):
                if summary["add"] > 0:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("add_circle", size="sm").classes("text-green-500")
                        ui.label(f"{summary['add']} to add").classes("text-sm font-medium text-green-600")
                
                if summary["change"] > 0:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("change_circle", size="sm").classes("text-yellow-500")
                        ui.label(f"{summary['change']} to change").classes("text-sm font-medium text-yellow-600")
                
                if summary["destroy"] > 0:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("remove_circle", size="sm").classes("text-red-500")
                        ui.label(f"{summary['destroy']} to destroy").classes("text-sm font-medium text-red-600")
            
            if total_changes == 0:
                ui.label("No changes detected in plan.").classes("text-sm text-slate-500 mt-2 text-center")
            
            # Info banner
            with ui.row().classes("w-full items-center gap-2 p-3 rounded mt-4").style(
                "background-color: rgba(251, 146, 60, 0.15); border: 1px solid rgba(251, 146, 60, 0.3);"
            ):
                ui.icon("info", size="sm").classes("text-orange-500")
                ui.label(
                    "This will make changes to your dbt Cloud account. "
                    "Ensure you have reviewed the plan before proceeding."
                ).classes("text-xs text-orange-600")
            
            with ui.row().classes("w-full justify-between mt-4"):
                # View Plan button on the left
                ui.button(
                    "View Plan",
                    icon="visibility",
                    on_click=lambda: create_plan_viewer_dialog(plan_output, "Terraform Plan").open(),
                ).props("outline")
                
                # Cancel and Apply buttons on the right
                with ui.row().classes("gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("outline")
                    
                    async def do_apply():
                        dialog.close()
                        await _run_terraform_apply(state, terminal, save_state, deploy_state)
                    
                    ui.button(
                        "Apply Changes",
                        icon="rocket_launch",
                        on_click=do_apply,
                    ).style(f"background-color: {DBT_ORANGE}; color: white;")
    
    dialog.open()


async def _run_terraform_apply(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Run terraform apply."""
    if not state.deploy.last_plan_success:
        terminal.warning("Run terraform plan first")
        ui.notify("Run plan first", type="warning")
        return

    # Use deploy_state value, or persisted state, or fall back to default directory
    tf_dir = deploy_state.get("terraform_dir") or state.deploy.terraform_dir or "deployments/migration"
    
    terminal.set_title("Output — APPLY")
    terminal.clear()
    terminal.info(f"Running terraform apply in {tf_dir}...")
    terminal.info("")
    terminal.info("⚠️ This will create/modify resources in the target account!")
    terminal.info("")

    deploy_state["apply_running"] = True

    try:
        # Set TF_VAR_* environment variables for terraform
        env = _get_terraform_env(state)

        result = await asyncio.to_thread(
            subprocess.run,
            ["terraform", "apply", "-no-color", "-auto-approve", "tfplan"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        # Output stdout
        for line in result.stdout.split("\n"):
            if line.strip():
                if "Apply complete" in line:
                    terminal.success(line)
                elif "created" in line.lower():
                    terminal.success(line)
                elif "destroyed" in line.lower():
                    terminal.warning(line)
                else:
                    terminal.info_auto(line)

        # Output stderr
        for line in result.stderr.split("\n"):
            if line.strip():
                terminal.warning(line)

        # Store output for View button
        output_text = result.stdout + "\n" + result.stderr
        deploy_state["last_apply_output"] = output_text
        state.deploy.last_apply_output = output_text
        
        if "apply_view_btn" in deploy_state:
            deploy_state["apply_view_btn"].enable()
            deploy_state["apply_view_btn"].tooltip("")
        
        if result.returncode == 0:
            terminal.success("")
            terminal.success("━━━ DEPLOYMENT COMPLETE ━━━")
            state.deploy.apply_complete = True
            save_state()
            
            # Detect warnings in output
            has_warnings = "warning" in result.stdout.lower() or "warning" in result.stderr.lower()
            
            # Update checkmark visibility
            if "apply_checkmark" in deploy_state:
                deploy_state["apply_checkmark"].visible = True
            
            # Update apply button color based on result
            if "apply_btn" in deploy_state:
                deploy_state["apply_btn"].props(remove="outline")
                deploy_state["apply_btn"].style("")  # Clear all inline styles
                if has_warnings:
                    deploy_state["apply_btn"].style(f"background-color: {STATUS_WARNING}; color: black;")
                else:
                    deploy_state["apply_btn"].style(f"background-color: {STATUS_SUCCESS};")
            
            if has_warnings:
                ui.notify("Deployment complete with warnings!", type="warning")
            else:
                ui.notify("Deployment complete!", type="positive")
        else:
            terminal.error("")
            terminal.error(f"Apply failed with exit code {result.returncode}")
            save_state()
            
            # Update apply button to show error state (red)
            if "apply_btn" in deploy_state:
                deploy_state["apply_btn"].props(remove="outline")
                deploy_state["apply_btn"].style("")  # Clear all inline styles
                deploy_state["apply_btn"].style(f"background-color: {STATUS_ERROR}; color: white;")
            
            ui.notify("Apply failed", type="negative")

    except Exception as e:
        terminal.error(f"Error running terraform: {e}")
        ui.notify(f"Error: {e}", type="negative")

    finally:
        deploy_state["apply_running"] = False


async def _run_terraform_destroy(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Run terraform destroy."""
    if not state.deploy.terraform_initialized:
        terminal.warning("Terraform not initialized")
        ui.notify("Initialize terraform first", type="warning")
        return

    tf_dir = deploy_state.get("terraform_dir") or state.deploy.terraform_dir or "deployments/migration"
    
    terminal.set_title("Output — DESTROY")
    terminal.clear()
    terminal.warning("━━━ TERRAFORM DESTROY ━━━")
    terminal.warning("")
    terminal.warning("⚠️ This will DESTROY all resources in the target account!")
    terminal.info("")
    terminal.info(f"Running terraform destroy in {tf_dir}...")
    terminal.info("")

    deploy_state["destroy_running"] = True

    try:
        # Set TF_VAR_* environment variables for terraform
        env = _get_terraform_env(state)

        result = await asyncio.to_thread(
            subprocess.run,
            ["terraform", "destroy", "-no-color", "-auto-approve"],
            cwd=tf_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        # Output stdout
        for line in result.stdout.split("\n"):
            if line.strip():
                if "destroyed" in line.lower():
                    terminal.warning(line)
                elif "Destroy complete" in line:
                    terminal.success(line)
                else:
                    terminal.info_auto(line)

        # Output stderr
        for line in result.stderr.split("\n"):
            if line.strip():
                terminal.warning(line)

        if result.returncode == 0:
            terminal.success("")
            terminal.success("Destroy complete!")
            state.deploy.apply_complete = False
            state.deploy.last_plan_success = False
            save_state()
            ui.notify("Destroy complete", type="positive")
        else:
            terminal.error("")
            terminal.error(f"Destroy failed with exit code {result.returncode}")
            ui.notify("Destroy failed", type="negative")

    except Exception as e:
        terminal.error(f"Error running terraform: {e}")
        ui.notify(f"Error: {e}", type="negative")

    finally:
        deploy_state["destroy_running"] = False
