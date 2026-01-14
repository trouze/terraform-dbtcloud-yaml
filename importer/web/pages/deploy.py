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
    create_yaml_viewer_dialog,
    get_yaml_stats,
)


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_NAVY = "#192847"


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

        # Row 1: Generate, Init, Validate (3 equal tiles)
        with ui.row().classes("w-full gap-4"):
            with ui.column().classes("flex-1"):
                _create_generate_section(state, terminal, save_state, deploy_state)
            with ui.column().classes("flex-1"):
                _create_init_section(state, terminal, save_state, deploy_state)
            with ui.column().classes("flex-1"):
                _create_validate_section(state, terminal, save_state, deploy_state)

        # Row 2: Plan + Apply stacked on left, Output Terminal on right
        with ui.row().classes("w-full gap-4"):
            # Left column: Plan and Apply stacked
            with ui.column().classes("w-1/3 min-w-[300px] gap-4"):
                _create_plan_section(state, terminal, save_state, deploy_state)
                _create_apply_section(state, terminal, save_state, deploy_state)
            # Right column: Output terminal (spans full height)
            with ui.column().classes("flex-grow"):
                with ui.card().classes("w-full"):
                    ui.label("Output").classes("font-semibold mb-2")
                    terminal.create(height="450px")

        # Row 3: Danger zone (full width)
        _create_destroy_section(state, terminal, save_state, deploy_state)

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
                            f"Go to {step.name.title()}",
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


def _create_generate_section(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Create the generate Terraform files section."""
    from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
    
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-2 mb-4"):
            ui.badge("1", color="primary").props("rounded")
            ui.label("Generate Terraform Files").classes("font-semibold")
            
            # Dynamic checkmark - stored in deploy_state for updating
            checkmark = ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")
            checkmark.visible = state.deploy.files_generated
            deploy_state["generate_checkmark"] = checkmark

        ui.label(
            "Generate Terraform configuration from your normalized YAML."
        ).classes("text-sm text-slate-500 mb-4")

        # Output directory
        # Suggest a project-oriented deployment directory
        default_deploy_dir = "deployments/migration"
        output_dir = ui.input(
            label="Output Directory",
            value=default_deploy_dir,
            placeholder=default_deploy_dir,
        ).classes("w-full").props('outlined dense')

        with ui.row().classes("w-full gap-2 mt-4"):
            ui.button(
                "Generate Files",
                icon="code",
                on_click=lambda: _run_generate(
                    state, terminal, save_state, deploy_state, output_dir.value
                ),
            ).classes("flex-grow").style(f"background-color: {DBT_ORANGE};")
            
            # View Generate Output button
            def open_generate_viewer():
                output = deploy_state.get("last_generate_output") or state.deploy.last_generate_output
                if not output:
                    ui.notify("No generate output available. Run generate first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(output, "Generate Output")
                dialog.open()
            
            view_btn = ui.button(
                "View Output",
                icon="visibility",
                on_click=open_generate_viewer,
            ).props("outline")
            deploy_state["generate_view_btn"] = view_btn
            
            if not deploy_state.get("last_generate_output") and not state.deploy.last_generate_output:
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
    
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-2 mb-4"):
            ui.badge("2", color="primary").props("rounded")
            ui.label("Initialize Terraform").classes("font-semibold")
            
            # Dynamic checkmark - stored in deploy_state for updating
            checkmark = ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")
            checkmark.visible = state.deploy.terraform_initialized
            deploy_state["init_checkmark"] = checkmark

        ui.label(
            "Initialize the Terraform working directory and download providers."
        ).classes("text-sm text-slate-500 mb-4")

        with ui.row().classes("w-full gap-2"):
            ui.button(
                "Run terraform init",
                icon="download",
                on_click=lambda: _run_terraform_init(
                    state, terminal, save_state, deploy_state
                ),
            ).classes("flex-grow").props("outline")
            
            # View Init Output button
            def open_init_viewer():
                output = deploy_state.get("last_init_output") or state.deploy.last_init_output
                if not output:
                    ui.notify("No init output available. Run init first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(output, "Terraform Init Output")
                dialog.open()
            
            view_btn = ui.button(
                "View Output",
                icon="visibility",
                on_click=open_init_viewer,
            ).props("outline")
            deploy_state["init_view_btn"] = view_btn
            
            if not deploy_state.get("last_init_output") and not state.deploy.last_init_output:
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
    
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-2 mb-4"):
            ui.badge("3", color="primary").props("rounded")
            ui.label("Validate Configuration").classes("font-semibold")
            
            # Dynamic checkmark - stored in deploy_state for updating
            checkmark = ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")
            checkmark.visible = state.deploy.last_validate_success
            deploy_state["validate_checkmark"] = checkmark

        ui.label(
            "Validate the Terraform configuration for syntax and consistency errors."
        ).classes("text-sm text-slate-500 mb-4")

        with ui.row().classes("w-full gap-2"):
            ui.button(
                "Run terraform validate",
                icon="check",
                on_click=lambda: _run_terraform_validate(
                    state, terminal, save_state, deploy_state
                ),
            ).classes("flex-grow").props("outline")
            
            # View Validate Output button
            def open_validate_viewer():
                output = deploy_state.get("last_validate_output") or state.deploy.last_validate_output
                if not output:
                    ui.notify("No validate output available. Run validate first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(output, "Terraform Validate Output")
                dialog.open()
            
            view_btn = ui.button(
                "View Output",
                icon="visibility",
                on_click=open_validate_viewer,
            ).props("outline")
            deploy_state["validate_view_btn"] = view_btn
            
            if not deploy_state.get("last_validate_output") and not state.deploy.last_validate_output:
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
    
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-2 mb-4"):
            ui.badge("4", color="primary").props("rounded")
            ui.label("Plan Deployment").classes("font-semibold")
            
            # Dynamic checkmark - stored in deploy_state for updating
            checkmark = ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")
            checkmark.visible = state.deploy.last_plan_success
            deploy_state["plan_checkmark"] = checkmark

        ui.label(
            "Preview the changes that will be made to the target account."
        ).classes("text-sm text-slate-500 mb-4")

        with ui.row().classes("w-full gap-2"):
            ui.button(
                "Run terraform plan",
                icon="preview",
                on_click=lambda: _run_terraform_plan(
                    state, terminal, save_state, deploy_state
                ),
            ).classes("flex-grow").props("outline")
            
            # View Plan button - opens dialog to view full plan output
            def open_plan_viewer():
                plan_output = deploy_state.get("last_plan_output") or state.deploy.last_plan_output
                if not plan_output:
                    ui.notify("No plan output available. Run plan first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(plan_output, "Terraform Plan")
                dialog.open()
            
            view_plan_btn = ui.button(
                "View Plan",
                icon="visibility",
                on_click=open_plan_viewer,
            ).props("outline")
            deploy_state["plan_view_btn"] = view_plan_btn
            
            # Disable if no plan output exists yet
            if not deploy_state.get("last_plan_output") and not state.deploy.last_plan_output:
                view_plan_btn.disable()
                view_plan_btn.tooltip("Run plan first")


def _create_apply_section(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Create the Terraform apply section."""
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-2 mb-4"):
            ui.badge("5", color="primary").props("rounded")
            ui.label("Apply Changes").classes("font-semibold")
            
            if state.deploy.apply_complete:
                ui.icon("check_circle", size="sm").classes("text-green-500 ml-auto")

        ui.label(
            "Deploy resources to the target dbt Platform account."
        ).classes("text-sm text-slate-500 mb-4")

        with ui.row().classes("w-full gap-2"):
            apply_btn = ui.button(
                "Run terraform apply",
                icon="rocket_launch",
                on_click=lambda: _run_terraform_apply(
                    state, terminal, save_state, deploy_state
                ),
            ).classes("flex-grow").style(f"background-color: {DBT_ORANGE};")
            deploy_state["apply_btn"] = apply_btn

            # Disable if plan hasn't succeeded
            if not state.deploy.last_plan_success:
                apply_btn.disable()
                apply_btn.tooltip("Run plan first")
            
            # View Apply Output button
            from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
            
            def open_apply_viewer():
                output = deploy_state.get("last_apply_output") or state.deploy.last_apply_output
                if not output:
                    ui.notify("No apply output available. Run apply first.", type="warning")
                    return
                dialog = create_plan_viewer_dialog(output, "Terraform Apply Output")
                dialog.open()
            
            view_btn = ui.button(
                "View Output",
                icon="visibility",
                on_click=open_apply_viewer,
            ).props("outline")
            deploy_state["apply_view_btn"] = view_btn
            
            if not deploy_state.get("last_apply_output") and not state.deploy.last_apply_output:
                view_btn.disable()
                view_btn.tooltip("Run apply first")


def _create_destroy_section(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Create the Terraform destroy section."""
    with ui.expansion("Danger Zone", icon="warning").classes("w-full").props("dense"):
        ui.label(
            "⚠️ This will destroy all resources created in the target account."
        ).classes("text-sm text-red-500 mb-4")

        ui.button(
            "Run terraform destroy",
            icon="delete_forever",
            on_click=lambda: _run_terraform_destroy(
                state, terminal, save_state, deploy_state
            ),
        ).classes("w-full").props("outline color=negative")


def _create_navigation_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create the navigation buttons section."""
    with ui.row().classes("w-full justify-between mt-6"):
        # Back button
        ui.button(
            "Back to Target",
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
    terminal.clear()
    terminal.info("Generating Terraform configuration files...")
    terminal.info("")

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

        ui.notify("Terraform files generated successfully", type="positive")

    except Exception as e:
        terminal.error(f"Generation failed: {e}")
        ui.notify(f"Generation failed: {e}", type="negative")


def _get_terraform_env(state: AppState) -> dict:
    """Get environment variables for Terraform commands.
    
    Sets TF_VAR_* variables for terraform input variables and
    DBT_CLOUD_* for provider fallback (same pattern as e2e test).
    """
    import os
    env = dict(os.environ)
    
    # Normalize host URL: strip trailing slash and ensure /api suffix
    # This matches the e2e test pattern
    base_host = (state.target_credentials.host_url or "https://cloud.getdbt.com").rstrip("/")
    if not base_host.endswith("/api"):
        host_url = f"{base_host}/api"
    else:
        host_url = base_host
    
    # TF_VAR_* for terraform input variables
    env["TF_VAR_dbt_account_id"] = str(state.target_credentials.account_id)
    env["TF_VAR_dbt_token"] = state.target_credentials.api_token or ""
    env["TF_VAR_dbt_host_url"] = host_url
    
    # DBT_CLOUD_* for provider fallback
    env["DBT_CLOUD_ACCOUNT_ID"] = str(state.target_credentials.account_id)
    env["DBT_CLOUD_TOKEN"] = state.target_credentials.api_token or ""
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

        # Output stdout
        for line in result.stdout.split("\n"):
            if line.strip():
                terminal.info(line)

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
            
            # Update UI elements
            if "init_checkmark" in deploy_state:
                deploy_state["init_checkmark"].visible = True
            if "init_view_btn" in deploy_state:
                deploy_state["init_view_btn"].enable()
                deploy_state["init_view_btn"].tooltip("")
            
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

        # Output stdout
        for line in result.stdout.split("\n"):
            if line.strip():
                terminal.info(line)

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
            
            # Update UI elements
            if "validate_checkmark" in deploy_state:
                deploy_state["validate_checkmark"].visible = True
            if "validate_view_btn" in deploy_state:
                deploy_state["validate_view_btn"].enable()
                deploy_state["validate_view_btn"].tooltip("")
            
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
                    terminal.info(line)

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
            
            # Update UI elements
            if "plan_checkmark" in deploy_state:
                deploy_state["plan_checkmark"].visible = True
            if "plan_view_btn" in deploy_state:
                deploy_state["plan_view_btn"].enable()
                deploy_state["plan_view_btn"].tooltip("")
            if "apply_btn" in deploy_state:
                deploy_state["apply_btn"].enable()
                deploy_state["apply_btn"].tooltip("")
            
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
    
    terminal.clear()
    terminal.info(f"Running terraform apply in {tf_dir}...")
    terminal.info("")
    terminal.warning("⚠️ This will create/modify resources in the target account!")
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
                    terminal.info(line)

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
            ui.notify("Deployment complete!", type="positive")
        else:
            terminal.error("")
            terminal.error(f"Apply failed with exit code {result.returncode}")
            save_state()
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
                    terminal.info(line)

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
