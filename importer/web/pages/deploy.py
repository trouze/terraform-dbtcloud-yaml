"""Deploy step page for generating Terraform files and running deployment."""

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, ImportResult
from importer.web.components.terminal_output import TerminalOutput
from importer.web.utils.yaml_viewer import (
    create_state_viewer_dialog,
    create_yaml_viewer_dialog,
    get_yaml_stats,
)
from importer.web.components.backend_config import (
    create_backend_config_section,
    write_backend_tf,
)
from importer.web.components.folder_picker import create_folder_picker_dialog
from importer.web.utils.terraform_import import (
    detect_terraform_version,
    supports_import_blocks,
    generate_import_commands,
    write_import_blocks_file,
)
from importer.web.utils.protection_manager import (
    extract_protected_resources,
    format_protection_warnings,
    load_yaml_config,
    detect_protection_changes,
    write_moved_blocks_file,
)


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_NAVY = "#192847"
DBT_TEAL = "#047377"

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

        # Protected resources panel (only shown if there are protected resources)
        _create_protected_resources_panel(state, deploy_state)

        # Import existing resources section (only shown if mappings exist)
        if state.map.target_matching_enabled and state.map.confirmed_mappings:
            _create_import_section(state, terminal, save_state, deploy_state)

        # Tiles: 2x3 grid (6 sections)
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

        # Note: State reconciliation is now handled in the Set Target Intent tab

        # Navigation buttons
        _create_navigation_section(state, on_step_change)


def _check_prerequisites(state: AppState, on_step_change: Callable[[WorkflowStep], None]) -> bool:
    """Check if prerequisites are met for deployment."""
    errors = []

    if not state.map.normalize_complete:
        errors.append(("Map step not completed", WorkflowStep.SCOPE))
    
    if not state.target_credentials.is_complete():
        errors.append(("Target credentials not configured", WorkflowStep.CONFIGURE))

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
    
    # Helper to update state path display when directory changes
    def update_state_path(new_dir: str):
        if new_dir and "state_path_display" in deploy_state:
            deploy_state["terraform_dir"] = new_dir
            deploy_state["state_path_display"].value = f"{new_dir}/terraform.tfstate"
    
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
                            update_state_path(path)
                        
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
            
            # Update state path when tf_dir changes via typing
            def on_tf_dir_change(e):
                update_state_path(e.value)
            
            tf_dir_input.on("change", on_tf_dir_change)


def _create_protected_resources_panel(
    state: AppState,
    deploy_state: dict,
) -> None:
    """Create a panel showing protected resources.
    
    This panel displays resources that have lifecycle.prevent_destroy = true
    and will refuse to be deleted by Terraform.
    """
    yaml_path = state.map.last_yaml_file
    if not yaml_path:
        return
    
    try:
        yaml_config = load_yaml_config(yaml_path)
        protected_resources = extract_protected_resources(yaml_config)
    except Exception:
        return
    
    if not protected_resources:
        return
    
    # Group by type
    by_type: dict[str, list] = {}
    for res in protected_resources:
        if res.resource_type not in by_type:
            by_type[res.resource_type] = []
        by_type[res.resource_type].append(res)
    
    type_labels = {
        "PRJ": "Projects",
        "ENV": "Environments",
        "JOB": "Jobs",
        "REP": "Repositories",
        "CON": "Connections",
        "EXTATTR": "Extended Attributes",
    }
    
    with ui.expansion(
        f"Protected Resources ({len(protected_resources)})",
        icon="shield",
    ).classes("w-full").props("dense").style("border-left: 3px solid #3B82F6;"):
        
        # Info banner
        with ui.card().classes("w-full p-3 mb-3"):
            with ui.row().classes("items-start gap-2"):
                ui.icon("info", size="sm").classes("text-blue-500")
                with ui.column().classes("gap-1"):
                    ui.label(
                        "These resources have lifecycle.prevent_destroy = true"
                    ).classes("text-sm")
                    ui.label(
                        "Terraform will refuse to destroy them. To remove, first set protected: false in YAML."
                    ).classes("text-xs text-slate-500")
        
        # Resource list by type
        for rtype, resources in sorted(by_type.items()):
            type_label = type_labels.get(rtype, rtype)
            
            with ui.row().classes("w-full items-center gap-2 mb-2"):
                ui.badge(f"{len(resources)} {type_label}").props("dense color=blue")
            
            with ui.column().classes("w-full pl-4 mb-3 gap-1"):
                for res in resources:
                    with ui.row().classes("w-full items-center gap-2"):
                        ui.icon("shield", size="xs").classes("text-blue-400")
                        ui.label(res.name).classes("text-sm")
                        ui.label(f"({res.resource_key})").classes("text-xs text-slate-400")


def _create_import_section(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Create the import existing resources section.
    
    This section appears when there are confirmed target mappings and allows
    importing existing target resources into Terraform state before plan/apply.
    """
    num_mappings = len(state.map.confirmed_mappings)
    is_initialized = state.deploy.terraform_initialized
    is_imported = state.deploy.import_completed
    
    with ui.expansion(
        f"Import Existing Resources ({num_mappings} mappings)",
        icon="import_export",
        value=not is_imported,  # Expand if not yet imported
    ).classes("w-full").style(f"border-left: 3px solid {DBT_TEAL};"):
        
        # Info banner
        with ui.card().classes("w-full p-3 mb-3"):
            with ui.row().classes("items-start gap-2"):
                ui.icon("info", size="sm").style(f"color: {DBT_TEAL};")
                with ui.column().classes("gap-1"):
                    ui.label(
                        "These resources will be imported into Terraform state before planning."
                    ).classes("text-sm")
                    ui.label(
                        "This prevents Terraform from creating duplicates of existing resources."
                    ).classes("text-xs text-slate-500")
        
        # Status indicator
        if is_imported:
            with ui.row().classes("w-full items-center gap-2 mb-3"):
                ui.icon("check_circle", size="sm").classes("text-green-500")
                ui.label("Imports completed successfully").classes("text-sm text-green-600")
        elif not is_initialized:
            with ui.row().classes("w-full items-center gap-2 mb-3"):
                ui.icon("warning", size="sm").classes("text-amber-500")
                ui.label("Run 'terraform init' first to enable imports").classes("text-sm text-amber-600")
        
        # Mapping summary
        ui.label("Resources to Import:").classes("font-semibold text-sm mb-2")
        
        # Group by resource type
        by_type: dict[str, list] = {}
        for mapping in state.map.confirmed_mappings:
            rtype = mapping.get("resource_type", "unknown")
            if rtype not in by_type:
                by_type[rtype] = []
            by_type[rtype].append(mapping)
        
        with ui.row().classes("w-full gap-2 flex-wrap mb-3"):
            for rtype, items in by_type.items():
                type_labels = {
                    "PRJ": "Projects",
                    "ENV": "Environments",
                    "JOB": "Jobs",
                    "CON": "Connections",
                    "REP": "Repositories",
                    "TOK": "Service Tokens",
                    "GRP": "Groups",
                    "NOT": "Notifications",
                    "EXTATTR": "Extended Attributes",
                }
                label = type_labels.get(rtype, rtype)
                ui.badge(f"{len(items)} {label}").props("dense")
        
        # Import mode selector
        with ui.row().classes("w-full items-center gap-4 mb-3"):
            ui.label("Import Method:").classes("text-sm")
            
            def on_mode_change(e):
                state.deploy.import_mode = e.value
                save_state()
            
            ui.radio(
                options=["modern", "legacy"],
                value=state.deploy.import_mode,
                on_change=on_mode_change,
            ).props("inline").classes("text-sm")
            
            with ui.column().classes("gap-0"):
                ui.label(
                    "Modern: Use TF 1.5+ import blocks (recommended)"
                    if state.deploy.import_mode == "modern"
                    else "Legacy: Run terraform import commands sequentially"
                ).classes("text-xs text-slate-500")
        
        # Action buttons
        with ui.row().classes("w-full gap-2"):
            if is_imported:
                # Already imported - show re-import option
                ui.button(
                    "Re-run Imports",
                    icon="refresh",
                    on_click=lambda: _run_imports(state, terminal, save_state, deploy_state),
                ).props("outline")
            else:
                import_btn = ui.button(
                    "Run Imports",
                    icon="import_export",
                    on_click=lambda: _run_imports(state, terminal, save_state, deploy_state),
                ).style(f"background-color: {DBT_TEAL};")
                
                if not is_initialized:
                    import_btn.disable()
            
            # Generate import file button
            ui.button(
                "Generate Import File",
                icon="description",
                on_click=lambda: _generate_import_file(state, terminal, deploy_state),
            ).props("outline")


async def _run_imports(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    deploy_state: dict,
) -> None:
    """Run the import operation for confirmed mappings."""
    tf_dir = deploy_state.get("terraform_dir") or state.deploy.terraform_dir or "deployments/migration"
    
    terminal.set_title("Output — IMPORT")
    terminal.clear()
    terminal.info("Starting resource imports...")
    terminal.info(f"Import mode: {state.deploy.import_mode}")
    terminal.info(f"Terraform directory: {tf_dir}")
    terminal.info("")
    
    try:
        # Check Terraform version
        version, err = await detect_terraform_version(tf_dir)
        if err:
            terminal.error(f"Terraform version check failed: {err}")
            ui.notify(f"Error: {err}", type="negative")
            return
        
        terminal.info(f"Terraform version: {'.'.join(map(str, version))}")
        state.deploy.terraform_version = ".".join(map(str, version))
        
        # Decide import mode
        use_modern = state.deploy.import_mode == "modern" and supports_import_blocks(version)
        
        if state.deploy.import_mode == "modern" and not supports_import_blocks(version):
            terminal.warning(f"TF version {'.'.join(map(str, version))} doesn't support import blocks. Using legacy mode.")
            use_modern = False
        
        mappings = state.map.confirmed_mappings
        
        if use_modern:
            # Generate and write import blocks file
            terminal.info("Using modern import blocks (TF 1.5+)")
            file_path, err = write_import_blocks_file(mappings, tf_dir)
            if err:
                terminal.error(f"Failed to write import file: {err}")
                ui.notify(f"Error: {err}", type="negative")
                return
            
            terminal.info(f"Generated import blocks: {file_path}")
            terminal.info("")
            terminal.info("Import blocks will be processed during 'terraform plan'")
            terminal.info("The imports.tf file has been created in your terraform directory.")
            
            state.deploy.imports_file_generated = True
            state.deploy.import_completed = True
            save_state()
            
            ui.notify("Import blocks generated. Run 'terraform plan' to process.", type="positive")
            
        else:
            # Legacy mode: run terraform import commands
            terminal.info("Using legacy terraform import commands")
            terminal.info(f"Processing {len(mappings)} imports...")
            terminal.info("")
            
            import_commands = generate_import_commands(mappings)
            
            # Initialize results
            state.deploy.import_results = []
            for addr, tid, skey, rtype in import_commands:
                result = ImportResult(
                    resource_address=addr,
                    target_id=tid,
                    source_key=skey,
                    resource_type=rtype,
                    status="pending",
                )
                state.deploy.import_results.append(result)
            
            def on_output(line: str):
                terminal.info(line.rstrip())
            
            def on_progress(result):
                terminal.info(f"  {result.status.upper()}: {result.resource_address}")
            
            # Run imports
            from importer.web.utils.terraform_import import run_import_batch
            summary = await run_import_batch(
                import_commands,
                tf_dir,
                on_progress=on_progress,
                on_output=on_output,
            )
            
            # Update state
            state.deploy.import_completed = summary.failed == 0
            state.deploy.last_import_output = f"Success: {summary.success}, Failed: {summary.failed}"
            save_state()
            
            terminal.info("")
            if summary.failed == 0:
                terminal.success("━━━ IMPORT COMPLETE ━━━")
                terminal.info(f"  Imported: {summary.success} resources")
                terminal.info(f"  Duration: {summary.duration_ms}ms")
                ui.notify("All imports successful!", type="positive")
            else:
                terminal.warning("━━━ IMPORT COMPLETED WITH ERRORS ━━━")
                terminal.info(f"  Success: {summary.success}")
                terminal.error(f"  Failed: {summary.failed}")
                ui.notify(f"{summary.failed} imports failed", type="warning")
        
        # Reload to update UI
        ui.navigate.reload()
        
    except Exception as e:
        terminal.error(f"Import failed: {e}")
        ui.notify(f"Import error: {e}", type="negative")


def _generate_import_file(
    state: AppState,
    terminal: TerminalOutput,
    deploy_state: dict,
) -> None:
    """Generate import blocks file without running imports."""
    tf_dir = deploy_state.get("terraform_dir") or state.deploy.terraform_dir or "deployments/migration"
    
    terminal.info("Generating import blocks file...")
    
    try:
        mappings = state.map.confirmed_mappings
        file_path, err = write_import_blocks_file(mappings, tf_dir)
        
        if err:
            terminal.error(f"Failed: {err}")
            ui.notify(f"Error: {err}", type="negative")
        else:
            terminal.success(f"Generated: {file_path}")
            ui.notify(f"Import file created: {file_path}", type="positive")
            state.deploy.imports_file_generated = True
            
    except Exception as e:
        terminal.error(f"Error: {e}")
        ui.notify(f"Error: {e}", type="negative")


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


def _show_no_state_dialog(state: AppState, deploy_state: dict) -> None:
    """Show a dialog indicating no state file exists yet."""
    tf_dir = (
        deploy_state.get("terraform_dir")
        or state.deploy.terraform_dir
        or "deployments/migration"
    )
    expected_path = Path(tf_dir) / "terraform.tfstate"
    
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
                "Complete the Generate → Init → Plan → Apply workflow to create the state file."
            ).classes("text-xs text-slate-500")
            
            with ui.row().classes("w-full justify-end mt-4"):
                ui.button("Close", on_click=dialog.close).props("outline")
    
    dialog.open()


def _create_state_inspection_section(
    state: AppState,
    deploy_state: dict,
) -> None:
    """Create the Terraform state inspection section."""
    state_path = _get_state_file_path(state, deploy_state)

    def open_state_viewer() -> None:
        # Re-check state path in case it was created after page load
        current_state_path = _get_state_file_path(state, deploy_state)
        if current_state_path:
            dialog = create_state_viewer_dialog(
                current_state_path,
                title="Terraform State",
            )
            dialog.open()
        else:
            # Show dialog indicating no state file exists yet
            _show_no_state_dialog(state, deploy_state)

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

        # Button at bottom - always enabled
        with ui.column().classes("w-full gap-2 mt-auto"):
            view_btn = ui.button(
                "View State",
                icon="visibility",
                on_click=open_state_viewer,
            ).props("outline").classes("w-full")
            
            if state_path:
                view_btn.style("color: white; background-color: rgba(255,255,255,0.1);")


def _create_navigation_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create the navigation buttons section."""
    with ui.row().classes("w-full justify-between mt-6"):
        # Back button - goes to Target Credentials
        ui.button(
            f"Back to {state.get_step_label(WorkflowStep.TARGET_CREDENTIALS)}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.TARGET_CREDENTIALS),
        ).props("outline")

        # Status
        if state.deploy.apply_complete:
            with ui.row().classes("items-center gap-2"):
                ui.icon("check_circle", size="md").classes("text-green-500")
                ui.label("Deployment Complete!").classes("text-green-500 font-semibold")


def _apply_tf_state_repo_values(yaml_file: str, tfstate_path: Path, terminal: Any) -> int:
    """Overlay TF state repository identity attributes onto the merged YAML.

    For every repository resource in TF state, find the matching repo entry
    in ``globals.repositories`` (by project key) and overwrite the identity-
    critical attributes: ``remote_url``, ``git_clone_strategy``, and
    ``github_installation_id``.  This prevents Terraform from planning a
    destroy+recreate when the source YAML has different values than the
    target/TF state.

    Returns the number of repos updated.
    """
    import json as _json_tf
    import yaml as _yaml_tf

    if not tfstate_path.exists():
        terminal.info("  TF state not found — skipping repo identity fixup")
        return 0

    # 1. Read TF state repos keyed by project (index_key)
    try:
        with open(tfstate_path, "r") as f:
            state_data = _json_tf.load(f)
    except Exception as e:
        terminal.warning(f"  Failed to read TF state for repo fixup: {e}")
        return 0

    # Collect repo resources from TF state: {project_key -> attrs}
    state_repos: dict[str, dict] = {}
    for res in state_data.get("resources", []):
        if res.get("type") != "dbtcloud_repository":
            continue
        if res.get("name") not in ("repositories", "protected_repositories"):
            continue
        for inst in res.get("instances", []):
            idx = inst.get("index_key")
            attrs = inst.get("attributes", {})
            if idx and attrs:
                state_repos[str(idx)] = {
                    "remote_url": attrs.get("remote_url"),
                    "git_clone_strategy": attrs.get("git_clone_strategy"),
                    "github_installation_id": attrs.get("github_installation_id"),
                    "protected": res.get("name") == "protected_repositories",
                }

    if not state_repos:
        terminal.info("  No repo resources in TF state — skipping repo identity fixup")
        return 0

    # 2. Load the YAML
    yaml_path = Path(yaml_file)
    if not yaml_path.exists():
        return 0
    with open(yaml_path, "r") as f:
        config = _yaml_tf.safe_load(f)
    if not config:
        return 0

    # 3. Build project_key -> repo_key map from YAML projects section
    project_to_repo_key: dict[str, str] = {}
    for project in config.get("projects", []):
        pkey = project.get("key")
        repo_ref = project.get("repository")
        if pkey and repo_ref:
            project_to_repo_key[pkey] = repo_ref

    # 4. Match TF state repos to YAML repos and overlay identity attributes
    globals_repos = config.get("globals", {}).get("repositories", [])
    repos_by_key = {r.get("key"): r for r in globals_repos}

    updated = 0

    for project_key, state_attrs in state_repos.items():
        repo_key = project_to_repo_key.get(project_key, project_key)
        repo = repos_by_key.get(repo_key)
        if not repo:
            # Try project key directly as repo key
            repo = repos_by_key.get(project_key)
        if not repo:
            continue

        changed = False
        for attr in ("remote_url", "git_clone_strategy", "github_installation_id"):
            state_val = state_attrs.get(attr)
            if state_val is not None and repo.get(attr) != state_val:
                old_val = repo.get(attr)
                repo[attr] = state_val
                terminal.info(f"    {repo_key}: {attr}: {old_val} -> {state_val}")
                changed = True
            elif state_val is not None and attr not in repo:
                repo[attr] = state_val
                terminal.info(f"    {repo_key}: {attr}: (missing) -> {state_val}")
                changed = True

        if changed:
            updated += 1

    if updated > 0:
        with open(yaml_path, "w") as f:
            _yaml_tf.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return updated


def _disable_job_triggers_in_yaml(yaml_file: str, output_dir: str) -> str:
    """Disable all job triggers in a YAML file.
    
    Sets schedule, on_merge, and git_provider_webhook to false for all jobs
    while keeping them active (is_active=true).
    
    Args:
        yaml_file: Path to the YAML file
        output_dir: Output directory for the modified file
        
    Returns:
        Path to the modified YAML file
    """
    import yaml as yaml_lib
    
    yaml_path = Path(yaml_file)
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml_lib.safe_load(f)
    
    # Process projects to find jobs
    for project in data.get("projects", []):
        for job in project.get("jobs", []):
            # Disable triggers but keep job active
            if "triggers" in job:
                job["triggers"]["schedule"] = False
                job["triggers"]["on_merge"] = False
                job["triggers"]["git_provider_webhook"] = False
            else:
                job["triggers"] = {
                    "schedule": False,
                    "on_merge": False,
                    "git_provider_webhook": False,
                }
    
    # Write to output directory
    output_path = Path(output_dir) / "dbt-cloud-config.yml"
    with open(output_path, "w", encoding="utf-8") as f:
        yaml_lib.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    return str(output_path)


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

        # Target intent: load persisted target-intent.json (computed on Match page).
        # Re-validate against current TF state; use persisted output_config if available.
        from importer.web.utils.target_intent import (
            TargetIntentManager,
            compute_target_intent,
            build_included_globals,
            validate_intent_coverage,
            get_tf_state_project_keys,
            normalize_target_fetch,
        )

        existing_yaml_path = output_path / "dbt-cloud-config.yml"
        tfstate_path = output_path / "terraform.tfstate"
        removal_keys = set(getattr(state.map, "removal_keys", None) or [])

        try:
            intent_manager = TargetIntentManager(output_path)
            persisted_intent = intent_manager.load()

            if persisted_intent and persisted_intent.output_config:
                # Use persisted target intent (computed on Match page)
                terminal.info("  Using persisted target intent from Match page")
                target_intent = persisted_intent

                # Re-validate: check TF state hasn't changed since intent was computed
                tf_state_keys = get_tf_state_project_keys(tfstate_path)
                intent_keys = set(target_intent.dispositions.keys())
                new_keys = tf_state_keys - intent_keys
                missing_keys = {k for k in intent_keys if target_intent.dispositions.get(k) and target_intent.dispositions[k].tf_state_address} - tf_state_keys
                if new_keys:
                    terminal.warning(f"  STALE: {len(new_keys)} new TF state key(s) not in persisted intent: {', '.join(sorted(new_keys)[:5])}")
                if missing_keys:
                    terminal.warning(f"  STALE: {len(missing_keys)} intent key(s) no longer in TF state: {', '.join(sorted(missing_keys)[:5])}")

                coverage_warnings = validate_intent_coverage(target_intent, tf_state_keys, removal_keys)
                for w in coverage_warnings:
                    terminal.warning(f"  COVERAGE: {w}")
                for w in target_intent.coverage_warnings:
                    terminal.warning(f"  COVERAGE: {w}")

                # Build protection sets from dispositions for downstream YAML application
                state.map.protected_resources = set()
                state.map.unprotected_keys = set()
                for key, disp in target_intent.dispositions.items():
                    prefixed = f"{disp.resource_type}:{key}"
                    if disp.protected:
                        state.map.protected_resources.add(prefixed)
                        state.map.protected_resources.add(key)
                    else:
                        state.map.unprotected_keys.add(prefixed)
                        state.map.unprotected_keys.add(key)

            else:
                # Fallback: recompute from scratch (backward compatibility or first-time)
                terminal.info("  No persisted output_config; recomputing target intent...")
                target_report_items = None
                if getattr(state, "target_fetch", None) and getattr(state.target_fetch, "last_report_items_file", None):
                    _tr_path = Path(state.target_fetch.last_report_items_file)
                    if _tr_path.exists():
                        try:
                            import json as _json_tr
                            with open(_tr_path, "r") as f:
                                target_report_items = _json_tr.load(f)
                        except Exception:
                            pass
                adopt_rows_early = getattr(state.deploy, "reconcile_adopt_rows", []) or []

                # Try to use target baseline YAML as fallback baseline
                baseline_yaml = str(existing_yaml_path) if existing_yaml_path.exists() else None
                if not baseline_yaml:
                    baseline_yaml = normalize_target_fetch(state)

                protection_intent_mgr = None
                try:
                    protection_intent_mgr = state.get_protection_intent_manager()
                except Exception:
                    pass

                included_globals = build_included_globals(state)

                target_intent = compute_target_intent(
                    tfstate_path=tfstate_path,
                    source_focus_yaml=yaml_file,
                    baseline_yaml=baseline_yaml,
                    target_report_items=target_report_items,
                    adopt_rows=adopt_rows_early,
                    removal_keys=removal_keys,
                    previous_intent=persisted_intent,
                    protection_intent_manager=protection_intent_mgr,
                    included_globals=included_globals,
                )

                tf_state_keys = get_tf_state_project_keys(tfstate_path)
                coverage_warnings = validate_intent_coverage(target_intent, tf_state_keys, removal_keys)
                for w in coverage_warnings:
                    terminal.warning(f"  COVERAGE: {w}")
                for w in target_intent.coverage_warnings:
                    terminal.warning(f"  COVERAGE: {w}")

                # Build protection sets from dispositions
                state.map.protected_resources = set()
                state.map.unprotected_keys = set()
                for key, disp in target_intent.dispositions.items():
                    prefixed = f"{disp.resource_type}:{key}"
                    if disp.protected:
                        state.map.protected_resources.add(prefixed)
                        state.map.protected_resources.add(key)
                    else:
                        state.map.unprotected_keys.add(prefixed)
                        state.map.unprotected_keys.add(key)

            # Report orphans and drift
            if target_intent.orphan_flagged_keys:
                for key in target_intent.orphan_flagged_keys:
                    terminal.warning(f"  ORPHAN: '{key}' is in TF state but NOT in target account -- flagged for removal")
                terminal.warning("  Review flagged orphans in Utilities > Removal Management. Confirm before state rm.")
            if target_intent.orphan_retained_keys:
                for key in target_intent.orphan_retained_keys:
                    terminal.info(f"  ORPHAN (retained): '{key}' -- user chose to keep stale state entry")
            for warn in target_intent.drift_warnings:
                terminal.warning(f"  DRIFT: {warn}")

            yaml_file = intent_manager.write_merged_yaml(target_intent)
            intent_manager.save(target_intent)
            terminal.success(
                f"  Target intent: {len(target_intent.retained_keys)} retained, "
                f"{len(target_intent.upserted_keys)} upserted, "
                f"{len(target_intent.adopted_keys)} adopted, "
                f"{len(target_intent.removed_keys)} removed, "
                f"{len(target_intent.orphan_flagged_keys)} orphans flagged"
            )
            # Report protection summary
            prot_count = sum(1 for d in target_intent.dispositions.values() if d.protected)
            unprot_count = sum(1 for d in target_intent.dispositions.values() if not d.protected)
            terminal.info(f"  Protection: {prot_count} protected, {unprot_count} unprotected")

            # Config preference summary
            target_pref = sum(1 for d in target_intent.dispositions.values() if d.config_preference == "target")
            source_pref = sum(1 for d in target_intent.dispositions.values() if d.config_preference == "source")
            terminal.info(f"  Config preference: {target_pref} target, {source_pref} source")

            # Apply TF state repo identity values to prevent destroy+recreate of repos
            # Repositories are identity-critical: changing remote_url or git_clone_strategy
            # forces destroy+recreate. Always prefer TF state values for repos that exist
            # in state, regardless of project-level config_preference.
            terminal.info("  Applying TF state repo identity fixup...")
            repo_fixup_count = _apply_tf_state_repo_values(yaml_file, tfstate_path, terminal)
            if repo_fixup_count > 0:
                terminal.info(f"  Fixed {repo_fixup_count} repo(s) with TF state identity values")
            else:
                terminal.info("  No repo identity fixups needed")

            terminal.info(f"  Using merged YAML: {yaml_file}")
        except Exception as e:
            terminal.warning(f"  Target intent processing failed: {e}")
            import traceback
            terminal.warning(traceback.format_exc()[:400])
            terminal.info("  Falling back to source YAML (may cause destroys!)")

        # Handle clone configurations if any
        cloned_resources = getattr(state.map, "cloned_resources", [])
        if cloned_resources:
            terminal.info(f"Processing {len(cloned_resources)} clone configuration(s)...")
            try:
                from importer.web.utils.clone_generator import augment_yaml_with_clones
                
                # Get report items for clone generation
                report_items = []
                if state.fetch.last_report_items_file:
                    report_items_path = Path(state.fetch.last_report_items_file)
                    if report_items_path.exists():
                        import json
                        with open(report_items_path, "r") as f:
                            report_items = json.load(f)
                
                # Create augmented YAML with clones in output directory
                augmented_yaml = output_path / "dbt-cloud-config-with-clones.yml"
                shutil.copy2(yaml_file, augmented_yaml)
                yaml_file = await asyncio.to_thread(
                    augment_yaml_with_clones,
                    str(augmented_yaml),
                    cloned_resources,
                    report_items,
                    str(augmented_yaml),
                )
                terminal.info("  Added clones to YAML configuration")
            except Exception as e:
                terminal.warning(f"  Clone processing failed: {e}")
                terminal.info("  Proceeding with original YAML file")
        
        # Handle job trigger disable setting
        if state.deploy.disable_job_triggers:
            terminal.info("Job triggers will be disabled in generated configuration")
            try:
                yaml_file = await asyncio.to_thread(
                    _disable_job_triggers_in_yaml,
                    yaml_file,
                    str(output_path),
                )
                terminal.info("  Job triggers disabled in YAML")
            except Exception as e:
                terminal.warning(f"  Failed to disable job triggers: {e}")

        terminal.info("")

        # Apply adoption overrides - update YAML with target values for adopted resources
        # This ensures imported resources match their target configuration
        # reconcile_adopt_rows is populated when user clicks "Generate Import Blocks" on Set Target Intent tab
        adopt_rows = getattr(state.deploy, "reconcile_adopt_rows", []) or []
        terminal.info(f"Checking adoption overrides: {len(adopt_rows)} row(s) in reconcile_adopt_rows")

        # Auto-populate adopt_rows from confirmed_mappings if empty
        # This ensures adoption overrides work even after server restart (when reconcile_adopt_rows was lost)
        if not adopt_rows and state.map.confirmed_mappings:
            terminal.info("  Auto-populating adopt_rows from confirmed_mappings...")
            # Accept "match", "adopt", or missing action (for older mappings) - all represent mapping to existing target
            confirmed_with_action = [m for m in state.map.confirmed_mappings if m.get("target_id") and m.get("action") in ("adopt", "match", None)]
            if confirmed_with_action:
                # Get protection status from state.map.protected_resources
                protected_keys = getattr(state.map, "protected_resources", set()) or set()
                adopt_rows = [
                    {
                        "source_key": m.get("source_key"),
                        "source_type": m.get("resource_type") or m.get("source_type"),
                        "source_name": m.get("source_name", m.get("source_key", "")),
                        "target_id": m.get("target_id"),
                        "target_name": m.get("target_name", ""),
                        "project_name": m.get("project_name", ""),
                        "drift_status": m.get("drift_status", "unknown"),
                        "protected": m.get("source_key") in protected_keys,
                    }
                    for m in confirmed_with_action
                ]
                terminal.info(f"  Derived {len(adopt_rows)} adopt rows from confirmed_mappings (protected_keys: {len(protected_keys)})")
        
        # Fallback: Load from saved mapping file if still empty and mapping_file_path exists
        if not adopt_rows and state.map.mapping_file_path:
            mapping_file = Path(state.map.mapping_file_path)
            if mapping_file.exists():
                terminal.info(f"  Loading mappings from saved file: {mapping_file}")
                try:
                    import yaml as _yaml_loader
                    with open(mapping_file, "r") as f:
                        mapping_data = _yaml_loader.safe_load(f)
                    if mapping_data and "mappings" in mapping_data:
                        # All mappings from file have target_id and represent existing target resources to adopt
                        # Get protection status from state.map.protected_resources
                        protected_keys = getattr(state.map, "protected_resources", set()) or set()
                        file_mappings = [
                            {
                                "source_key": m.get("source_key"),
                                "source_type": m.get("resource_type"),
                                "source_name": m.get("source_name", m.get("source_key", "")),
                                "target_id": m.get("target_id"),
                                "target_name": m.get("target_name", ""),
                                "protected": m.get("source_key") in protected_keys,
                            }
                            for m in mapping_data["mappings"]
                            if m.get("target_id") and m.get("target_id") != "None"
                        ]
                        if file_mappings:
                            adopt_rows = file_mappings
                            terminal.info(f"  Loaded {len(adopt_rows)} adopt rows from mapping file (protected_keys: {len(protected_keys)})")
                except Exception as e:
                    terminal.warning(f"  Failed to load mapping file: {e}")
        
        if adopt_rows:
            terminal.info(f"Applying {len(adopt_rows)} adoption override(s) to YAML...")
            # Debug: show what we're trying to adopt
            for i, row in enumerate(adopt_rows[:5]):  # Show first 5
                terminal.info(f"  [{i}] source_key={row.get('source_key')}, source_type={row.get('source_type')}, target_id={row.get('target_id')}")
            if len(adopt_rows) > 5:
                terminal.info(f"  ... and {len(adopt_rows) - 5} more")
            
            try:
                from importer.web.utils.adoption_yaml_updater import apply_adoption_overrides
                import json as json_mod
                
                # Get target report items from file (TargetFetchState only has last_report_items_file)
                target_items = []
                if state.target_fetch and state.target_fetch.last_report_items_file:
                    target_items_path = Path(state.target_fetch.last_report_items_file)
                    if target_items_path.exists():
                        with open(target_items_path, "r") as f:
                            target_items = json_mod.load(f)
                        terminal.info(f"  Loaded {len(target_items)} target report items from {target_items_path.name}")
                    else:
                        terminal.warning(f"  Target report items file not found: {target_items_path}")
                else:
                    terminal.warning(f"  No target_fetch.last_report_items_file configured")
                
                if target_items:
                    # Copy the (already-merged) YAML into the output dir for adoption updates
                    adoption_yaml = output_path / "dbt-cloud-config.yml"
                    if Path(yaml_file) != adoption_yaml:
                        shutil.copy2(yaml_file, adoption_yaml)
                    
                    # Debug: show target lookup for our adopt rows
                    target_by_id = {}
                    for item in target_items:
                        elem_type = item.get("element_type_code") or item.get("element_type")
                        dbt_id = item.get("dbt_id") or item.get("id")
                        if elem_type and dbt_id:
                            target_by_id[(elem_type, int(dbt_id))] = item
                    
                    for row in adopt_rows[:3]:
                        src_type = row.get("source_type")
                        tgt_id = row.get("target_id")
                        if src_type and tgt_id:
                            try:
                                key = (src_type, int(tgt_id))
                                found = target_by_id.get(key)
                                if found:
                                    terminal.info(f"  Target lookup ({src_type}, {tgt_id}): FOUND - remote_url={found.get('remote_url')}, git_clone_strategy={found.get('git_clone_strategy')}, github_installation_id={found.get('github_installation_id')}")
                                else:
                                    terminal.warning(f"  Target lookup ({src_type}, {tgt_id}): NOT FOUND")
                            except ValueError:
                                terminal.warning(f"  Target lookup ({src_type}, {tgt_id}): Invalid target_id")
                    
                    yaml_file = await asyncio.to_thread(
                        apply_adoption_overrides,
                        str(adoption_yaml),
                        adopt_rows,
                        target_items,
                    )
                    terminal.info("  Adoption overrides applied to YAML")
                    
                    # Verify the YAML was updated
                    with open(adoption_yaml, "r") as f:
                        updated_content = f.read()
                    if "mds-emu" in updated_content:
                        terminal.info("  Verification: Found target remote_url in updated YAML")
                    else:
                        terminal.warning("  Verification: Target remote_url NOT found in updated YAML")
                else:
                    terminal.warning("  No target data available for adoption overrides")
                    terminal.warning("  Make sure you've fetched target account data first")
            except Exception as e:
                terminal.warning(f"  Failed to apply adoption overrides: {e}")
                import traceback
                terminal.warning(f"  {traceback.format_exc()}")
                terminal.info("  Proceeding with original YAML values")
        else:
            terminal.info("  No adopt rows found - click 'Generate Import Blocks' on Set Target Intent tab first")

        # Strip source account's github_installation_id from repositories that are
        # NOT in TF state (new repos being created via deploy_key).
        # Repos already in TF state were fixed by _apply_tf_state_repo_values above
        # and should keep their TF-state-sourced github_installation_id.
        terminal.info("")
        terminal.info("Stripping source account github_installation_id from non-state repos...")
        try:
            import yaml as yaml_strip
            import json as _json_state
            
            yaml_output_path = output_path / "dbt-cloud-config.yml"
            terminal.info(f"  Output YAML path: {yaml_output_path}")
            terminal.info(f"  Output path exists: {yaml_output_path.exists()}")
            
            # Ensure YAML is in output directory (already merged upstream)
            if Path(yaml_file) != yaml_output_path:
                terminal.info(f"  Copying (merged) YAML to {yaml_output_path}")
                shutil.copy2(yaml_file, yaml_output_path)
            
            with open(yaml_output_path, "r") as f:
                yaml_config = yaml_strip.safe_load(f)
            
            # Build set of repo keys that are in TF state (these have correct values
            # from _apply_tf_state_repo_values and should not be stripped)
            tf_state_repo_keys: set[str] = set()
            if tfstate_path.exists():
                try:
                    with open(tfstate_path, "r") as f:
                        _state_data = _json_state.load(f)
                    for res in _state_data.get("resources", []):
                        if res.get("type") != "dbtcloud_repository":
                            continue
                        if res.get("name") not in ("repositories", "protected_repositories"):
                            continue
                        for inst in res.get("instances", []):
                            idx = inst.get("index_key")
                            if idx:
                                tf_state_repo_keys.add(str(idx))
                except Exception:
                    pass

            # Also build adopted repo keys from adopt_rows (both source_key and project_name)
            adopted_repo_keys: set[str] = set()
            for row in adopt_rows:
                if row.get("source_type") == "REP":
                    adopted_repo_keys.add(row.get("source_key", ""))
                    if row.get("project_name"):
                        adopted_repo_keys.add(row["project_name"])

            # Combine: repos to keep are those in TF state OR adopted
            keep_keys = tf_state_repo_keys | adopted_repo_keys
            terminal.info(f"  TF state repo keys: {tf_state_repo_keys}")
            terminal.info(f"  Adopted repo keys: {adopted_repo_keys}")

            # Strip github_installation_id from repos not in the keep set
            repos_stripped = 0
            globals_repos = yaml_config.get("globals", {}).get("repositories", [])
            terminal.info(f"  Found {len(globals_repos)} repos in globals.repositories")
            
            for repo in globals_repos:
                repo_key = repo.get("key")
                has_install_id = "github_installation_id" in repo
                if repo_key not in keep_keys and has_install_id:
                    terminal.info(f"    Stripping from: {repo_key}")
                    del repo["github_installation_id"]
                    repos_stripped += 1
                elif repo_key in keep_keys and has_install_id:
                    terminal.info(f"    Keeping for: {repo_key} (github_installation_id={repo.get('github_installation_id')})")
            
            # Also check top-level repositories (old schema)
            top_level_repos = yaml_config.get("repositories", [])
            terminal.info(f"  Found {len(top_level_repos)} repos in top-level repositories")
            
            for repo in top_level_repos:
                repo_key = repo.get("key")
                has_install_id = "github_installation_id" in repo
                if repo_key not in keep_keys and has_install_id:
                    terminal.info(f"    Stripping from: {repo_key}")
                    del repo["github_installation_id"]
                    repos_stripped += 1
            
            terminal.info(f"  Total repos stripped: {repos_stripped}")
            
            if repos_stripped > 0:
                with open(yaml_output_path, "w") as f:
                    yaml_strip.dump(yaml_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                terminal.info(f"  Wrote updated YAML to {yaml_output_path}")
            
            # Update yaml_file to point to the output path for converter
            yaml_file = str(yaml_output_path)
            terminal.info(f"  Set yaml_file to: {yaml_file}")
        except Exception as e:
            terminal.warning(f"  Failed to strip github_installation_id: {e}")
            import traceback
            terminal.warning(f"  {traceback.format_exc()[:500]}")

        # Protection is now sourced from target intent dispositions (built above).
        # The protected_resources and unprotected_keys sets were populated from
        # disposition.protected when loading or computing target intent.
        # Apply protection changes from both protected_resources and unprotected_keys sets
        # protected_resources: resources that should have protected=True
        # unprotected_keys: resources that should have protected removed/False
        has_protection_changes = bool(state.map.protected_resources) or bool(state.map.unprotected_keys)
        if has_protection_changes:
            terminal.info("")
            terminal.info(f"Applying protection changes: {len(state.map.protected_resources)} to protect, {len(state.map.unprotected_keys)} to unprotect...")
            try:
                from importer.web.utils.adoption_yaml_updater import apply_protection_from_set, apply_unprotection_from_set
                from importer.web.utils.ui_logger import log_generate_step
                
                yaml_output_path = output_path / "dbt-cloud-config.yml"
                
                # CRITICAL FIX: Ensure the YAML exists in output directory before modifying
                # If adoption overrides didn't run, the file might not be there yet
                # Note: By this point, the strip section above should have already
                # created/merged the file. This is a safety fallback only.
                if not yaml_output_path.exists():
                    shutil.copy2(yaml_file, yaml_output_path)
                    terminal.info(f"  Copied YAML to output directory for protection updates")
                
                # Log protection state for debugging
                log_generate_step("protection_changes", {
                    "protected_resources": list(state.map.protected_resources),
                    "unprotected_keys": list(state.map.unprotected_keys) if hasattr(state.map, 'unprotected_keys') else [],
                    "yaml_output_path": str(yaml_output_path),
                    "yaml_file_before": yaml_file,
                })
                
                # First apply protection (set protected=True)
                if state.map.protected_resources:
                    await asyncio.to_thread(
                        apply_protection_from_set,
                        str(yaml_output_path),
                        state.map.protected_resources,
                    )
                    terminal.success(f"  Protection applied to {len(state.map.protected_resources)} resource(s)")
                
                # Then apply unprotection (set protected=False or remove flag)
                if state.map.unprotected_keys:
                    await asyncio.to_thread(
                        apply_unprotection_from_set,
                        str(yaml_output_path),
                        state.map.unprotected_keys,
                    )
                    terminal.success(f"  Unprotection applied to {len(state.map.unprotected_keys)} resource(s)")
                
                # CRITICAL FIX: Update yaml_file to point to the modified copy
                # This ensures the converter uses the protection-updated YAML
                yaml_file = str(yaml_output_path)
                terminal.info(f"  Using protection-updated YAML for Terraform generation")
                
            except Exception as e:
                terminal.warning(f"  Failed to apply protection changes: {e}")
                import traceback
                terminal.warning(f"  {traceback.format_exc()[:500]}")

        # Generate the Terraform files using the converter
        from importer.yaml_converter import YamlToTerraformConverter
        from importer.web.utils.ui_logger import log_generate_step
        
        # Show target info (credentials are passed via TF_VAR_* env vars at runtime)
        target_host = state.target_credentials.host_url
        target_id = state.target_credentials.account_id
        terminal.info(f"Target account: {target_id} @ {target_host}")
        terminal.info("Credentials will be passed via TF_VAR_* environment variables")
        terminal.info("")
        
        log_generate_step("converter_start", {"yaml_file": yaml_file, "output_path": str(output_path)})
        
        converter = YamlToTerraformConverter()
        await asyncio.to_thread(
            converter.convert,
            yaml_file,
            str(output_path),
        )
        
        log_generate_step("converter_complete", {"yaml_file": yaml_file})

        # Generate backend.tf if configured
        backend_config = deploy_state.get("backend_config", {})
        if not backend_config.get("use_existing", False):
            backend_file = write_backend_tf(backend_config, str(output_path))
            if backend_file:
                terminal.info(f"Generated backend configuration: {Path(backend_file).name}")

        # Check for protection status changes and generate moved blocks
        try:
            previous_yaml_path = state.deploy.previous_yaml_file
            current_yaml_path = str(output_path / "dbt-cloud-config.yml")
            
            # FIX: Apply pending protection intents to YAML BEFORE comparing to state
            # This ensures the Deploy page respects intents just like the Match page does
            protection_intent_manager = state.get_protection_intent_manager()
            pending_yaml_updates = protection_intent_manager.get_pending_yaml_updates()
            pending_tf_apply = {k: i for k, i in protection_intent_manager._intent.items()
                               if i.applied_to_yaml and not i.applied_to_tf_state}
            
            all_pending = {**pending_yaml_updates, **pending_tf_apply}
            
            if all_pending:
                terminal.info("")
                terminal.info(f"Applying {len(all_pending)} pending protection intent(s) to YAML...")
                
                from importer.web.utils.adoption_yaml_updater import apply_protection_from_set, apply_unprotection_from_set
                
                # Find the YAML file to update
                yaml_file_to_update = Path(current_yaml_path)
                if not yaml_file_to_update.exists():
                    # Try terraform directory
                    if state.deploy.terraform_dir:
                        yaml_file_to_update = Path(state.deploy.terraform_dir) / "dbt-cloud-config.yml"
                
                if yaml_file_to_update.exists():
                    keys_to_protect = {k for k, i in all_pending.items() if i.protected}
                    keys_to_unprotect = {k for k, i in all_pending.items() if not i.protected}
                    
                    if keys_to_protect:
                        apply_protection_from_set(str(yaml_file_to_update), keys_to_protect)
                        terminal.info(f"  Applied protection to {len(keys_to_protect)} resource(s)")
                        for k in list(keys_to_protect)[:5]:
                            terminal.info(f"    + {k}")
                        if len(keys_to_protect) > 5:
                            terminal.info(f"    ... and {len(keys_to_protect) - 5} more")
                    
                    if keys_to_unprotect:
                        apply_unprotection_from_set(str(yaml_file_to_update), keys_to_unprotect)
                        terminal.info(f"  Removed protection from {len(keys_to_unprotect)} resource(s)")
                        for k in list(keys_to_unprotect)[:5]:
                            terminal.info(f"    - {k}")
                        if len(keys_to_unprotect) > 5:
                            terminal.info(f"    ... and {len(keys_to_unprotect) - 5} more")
                    
                    # Mark intents as applied to YAML
                    for key in all_pending:
                        protection_intent_manager.mark_applied_to_yaml(key)
                    protection_intent_manager.save()
                    
                    terminal.success("  Protection intents applied to YAML")
                else:
                    terminal.warning(f"  Could not find YAML file to update: {yaml_file_to_update}")
            
            # ADDITIONAL FIX: Validate that intent matches YAML reality
            # Detect case where intent says applied_to_yaml=true but YAML doesn't actually have the protection status
            yaml_to_check = Path(current_yaml_path) if Path(current_yaml_path).exists() else None
            if not yaml_to_check and state.deploy.terraform_dir:
                yaml_to_check = Path(state.deploy.terraform_dir) / "dbt-cloud-config.yml"
            
            if yaml_to_check and yaml_to_check.exists():
                terminal.info("")
                terminal.info("Validating protection intent vs YAML reality...")
                
                yaml_config = load_yaml_config(str(yaml_to_check))
                
                # Build set of actually protected projects in YAML
                yaml_protected = set()
                for proj in yaml_config.get("projects", []):
                    if proj.get("protected"):
                        key = proj.get("key", "")
                        yaml_protected.add(f"PRJ:{key}")
                        # Also check repositories — add both REPO: (current)
                        # and REP: (legacy) prefixes so validation matches
                        # intent entries regardless of which prefix was used.
                        if proj.get("repository"):
                            yaml_protected.add(f"REPO:{key}")
                            yaml_protected.add(f"REP:{key}")
                
                # Check each intent that claims applied_to_yaml=true
                intent_yaml_mismatches = []
                for key, intent in protection_intent_manager._intent.items():
                    if intent.applied_to_yaml:
                        # Intent claims YAML should have this protection status
                        should_be_protected = intent.protected
                        is_protected_in_yaml = key in yaml_protected
                        
                        if should_be_protected != is_protected_in_yaml:
                            intent_yaml_mismatches.append({
                                "key": key,
                                "intent_says": "protected" if should_be_protected else "unprotected",
                                "yaml_says": "protected" if is_protected_in_yaml else "unprotected",
                            })
                
                if intent_yaml_mismatches:
                    terminal.warning(f"  Found {len(intent_yaml_mismatches)} intent/YAML mismatch(es) - fixing...")
                    for mismatch in intent_yaml_mismatches:
                        terminal.warning(f"    {mismatch['key']}: intent={mismatch['intent_says']}, yaml={mismatch['yaml_says']}")
                        # Fix by re-applying the intent to YAML
                        key = mismatch["key"]
                        intent = protection_intent_manager._intent[key]
                        if intent.protected:
                            from importer.web.utils.adoption_yaml_updater import apply_protection_from_set
                            apply_protection_from_set(str(yaml_to_check), {key})
                        else:
                            from importer.web.utils.adoption_yaml_updater import apply_unprotection_from_set
                            apply_unprotection_from_set(str(yaml_to_check), {key})
                    terminal.success("  Intent/YAML mismatches repaired")
                else:
                    terminal.info("  Intent matches YAML - no repairs needed")
            
            # Collect all protection changes from both YAML-vs-YAML and YAML-vs-State
            all_protection_changes = []
            
            if previous_yaml_path and Path(previous_yaml_path).exists():
                terminal.info("")
                terminal.info("Checking for protection status changes (YAML-vs-YAML)...")
                
                previous_yaml = load_yaml_config(previous_yaml_path)
                current_yaml = load_yaml_config(current_yaml_path)
                
                yaml_changes = detect_protection_changes(current_yaml, previous_yaml)
                
                if yaml_changes:
                    terminal.info(f"  Detected {len(yaml_changes)} YAML-vs-YAML protection change(s)")
                    all_protection_changes.extend(yaml_changes)
                else:
                    terminal.info("  No YAML-vs-YAML protection changes detected")
            
            # ALWAYS run state-based detection as a safety net
            # This catches mismatches from match page TF applies, manual state edits, etc.
            # (Previously this only ran when no previous YAML existed)
            terminal.info("")
            terminal.info("Checking protection status (YAML-vs-State)...")
            
            from importer.web.utils.protection_manager import generate_moved_blocks_from_state
            
            current_yaml = load_yaml_config(current_yaml_path)
            terraform_dir = state.deploy.terraform_dir
            
            if terraform_dir and Path(terraform_dir).exists():
                state_file = Path(terraform_dir) / "terraform.tfstate"
                if state_file.exists():
                    state_changes = generate_moved_blocks_from_state(
                        current_yaml,
                        str(state_file),
                    )
                    
                    if state_changes:
                        # De-duplicate: only add state changes not already found by YAML comparison
                        existing_keys = {(c.resource_type, c.resource_key) for c in all_protection_changes}
                        new_state_changes = [
                            sc for sc in state_changes
                            if (sc.resource_type, sc.resource_key) not in existing_keys
                        ]
                        if new_state_changes:
                            terminal.info(f"  Detected {len(new_state_changes)} additional state-vs-YAML mismatch(es)")
                            for sc in new_state_changes:
                                terminal.info(f"    {sc.resource_type}:{sc.resource_key} → {sc.direction}")
                            all_protection_changes.extend(new_state_changes)
                        else:
                            terminal.info("  State mismatches already covered by YAML changes")
                    else:
                        terminal.info("  No protection mismatches between state and YAML")
                else:
                    terminal.info("  No Terraform state file found - skipping state-based detection")
            else:
                terminal.info("  No Terraform directory configured - skipping state-based detection")
            
            # Write combined moved blocks
            if all_protection_changes:
                terminal.info(f"  Total: {len(all_protection_changes)} protection change(s) to generate moved blocks for")
                moved_file = write_moved_blocks_file(all_protection_changes, str(output_path), preserve_existing=False)
                if moved_file:
                    terminal.success(f"  Generated moved blocks: {moved_file.name}")
                    terminal.info("  These will move resources between protected/unprotected blocks")
            else:
                terminal.info("  No protection changes - clearing any stale moved blocks")
                # Clear any stale protection_moves.tf from previous runs
                stale_moves = Path(output_path) / "protection_moves.tf"
                if stale_moves.exists():
                    stale_moves.unlink()
                    terminal.info("  Removed stale protection_moves.tf")
            
            # Store current YAML path as previous for next generation
            state.deploy.previous_yaml_file = current_yaml_path
        except Exception as e:
            terminal.warning(f"Protection change detection skipped: {e}")
            import traceback
            terminal.warning(f"  {traceback.format_exc()[:300]}")

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
    token_type = state.target_credentials.token_type
    
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
    
    # If using a PAT (user_token), also set TF_VAR_dbt_pat for GitHub App integration
    # PATs can access the /integrations/github/installations/ endpoint
    # Service tokens cannot, so they fall back to deploy_key strategy
    # Also check token prefix as PATs start with 'dbtu_'
    is_pat = token_type == "user_token" or (api_token and api_token.startswith("dbtu_"))
    if is_pat:
        env["TF_VAR_dbt_pat"] = api_token
    
    # Log PAT status for debugging
    import logging
    log = logging.getLogger(__name__)
    log.info(f"Token type: {token_type}, Is PAT: {is_pat}, TF_VAR_dbt_pat set: {is_pat}")
    
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
        
        # Log PAT status
        has_pat = "TF_VAR_dbt_pat" in env
        terminal.info(f"Token type: {state.target_credentials.token_type}")
        terminal.info(f"PAT configured: {'Yes' if has_pat else 'No'}")
        if has_pat:
            terminal.success("GitHub App integration will be attempted")
        else:
            terminal.warning("No PAT provided - repositories will use deploy key")
        terminal.info("")

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
            
            # Check for protected resources that would be destroyed
            protected_destroy_warning = _check_protected_destroys(
                result.stdout, 
                state.map.last_yaml_file
            )
            if protected_destroy_warning:
                terminal.warning("")
                terminal.warning("⚠️  PROTECTED RESOURCES WARNING")
                terminal.warning(protected_destroy_warning)
                terminal.warning("")
            
            # Detect warnings in output
            has_warnings = (
                "warning" in result.stdout.lower() 
                or "warning" in result.stderr.lower()
                or protected_destroy_warning is not None
            )
            
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


def _check_protected_destroys(
    plan_output: str,
    yaml_file: Optional[str],
) -> Optional[str]:
    """Check if any protected resources would be destroyed by the plan.
    
    Args:
        plan_output: Output from terraform plan
        yaml_file: Path to YAML configuration file
        
    Returns:
        Warning message if protected resources would be destroyed, None otherwise
    """
    if not yaml_file:
        return None
    
    try:
        # Load protected resources from YAML
        yaml_config = load_yaml_config(yaml_file)
        protected_resources = extract_protected_resources(yaml_config)
        
        if not protected_resources:
            return None
        
        # Build a set of protected resource identifiers to check
        # Protected resources use the "protected_*" resource names
        protected_identifiers = set()
        for res in protected_resources:
            # The protected address will contain "protected_jobs", "protected_environments", etc.
            protected_identifiers.add(res.protected_address)
            # Also add the resource name/key for simpler matching
            protected_identifiers.add(res.name.lower())
            protected_identifiers.add(res.resource_key.lower())
        
        # Parse plan output for destroy actions
        destroyed_protected = []
        for line in plan_output.split("\n"):
            line_lower = line.lower()
            if "will be destroyed" in line_lower or "must be replaced" in line_lower:
                # Check if this line mentions any protected resource
                for res in protected_resources:
                    if (
                        res.resource_key.lower() in line_lower
                        or res.name.lower() in line_lower
                        or "protected_" in line_lower
                    ):
                        destroyed_protected.append(res)
                        break
        
        if destroyed_protected:
            # Format warning message
            lines = [
                "Protected resources would be affected:",
            ]
            for res in destroyed_protected:
                type_name = {
                    "PRJ": "Project",
                    "ENV": "Environment",
                    "JOB": "Job",
                    "REP": "Repository",
                    "EXTATTR": "Extended Attributes",
                }.get(res.resource_type, res.resource_type)
                lines.append(f"  - {type_name}: {res.name}")
            
            lines.extend([
                "",
                "Terraform will fail with 'prevent_destroy' error.",
                "To destroy: set protected=false in YAML and regenerate.",
            ])
            return "\n".join(lines)
        
        return None
        
    except Exception as e:
        # Don't fail the plan if protection check fails
        import logging
        logging.getLogger(__name__).warning(f"Protection check failed: {e}")
        return None


def _parse_plan_summary(plan_output: str) -> dict:
    """Parse terraform plan output to extract import/add/change/destroy counts."""
    import re
    
    summary = {"import": 0, "add": 0, "change": 0, "destroy": 0}
    
    # Look for the "Plan: X to import, Y to add, Z to change, W to destroy" line
    # Format can be: "Plan: 2 to import, 2 to add, 1 to change, 0 to destroy."
    # Or without imports: "Plan: 2 to add, 1 to change, 0 to destroy."
    
    # First try to match with imports
    match = re.search(
        r"Plan:\s*(\d+)\s*to import,\s*(\d+)\s*to add,\s*(\d+)\s*to change,\s*(\d+)\s*to destroy",
        plan_output
    )
    if match:
        summary["import"] = int(match.group(1))
        summary["add"] = int(match.group(2))
        summary["change"] = int(match.group(3))
        summary["destroy"] = int(match.group(4))
    else:
        # Try without imports
        match = re.search(
            r"Plan:\s*(\d+)\s*to add,\s*(\d+)\s*to change,\s*(\d+)\s*to destroy",
            plan_output
        )
        if match:
            summary["add"] = int(match.group(1))
            summary["change"] = int(match.group(2))
            summary["destroy"] = int(match.group(3))
        else:
            # Fallback: count individual resource lines
            for line in plan_output.split("\n"):
                if "will be imported" in line:
                    summary["import"] += 1
                elif "will be created" in line:
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
    
    total_changes = summary["import"] + summary["add"] + summary["change"] + summary["destroy"]
    
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
                if summary["import"] > 0:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("download", size="sm").classes("text-purple-500")
                        ui.label(f"{summary['import']} to import").classes("text-sm font-medium text-purple-600")
                
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
