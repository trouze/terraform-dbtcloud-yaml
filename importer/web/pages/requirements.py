"""Requirements page for checking and installing dependencies."""


import os

from dotenv import set_key
from nicegui import app, ui

from importer.web.state import AppState
from importer.web.env_manager import find_env_file, load_env_values
from importer.web.licensing import check_migration_license, get_license_manager
from importer.web.utils.dependency_checker import (
    DependencyCategory,
    DependencyResult,
    DependencyStatus,
    check_python_packages,
    get_overall_status,
    install_python_packages,
    run_all_checks,
)


# dbt brand colors
DBT_ORANGE = "#FF694A"
LICENSE_BYPASS_ENV = "MAGELLAN_LICENSE_BYPASS"


def create_requirements_page(state: AppState) -> None:
    """Create the requirements checker page.
    
    Args:
        state: Current application state
    """
    with ui.column().classes("w-full max-w-4xl mx-auto p-8 gap-6"):
        # Header
        with ui.card().classes("w-full p-6"):
            with ui.row().classes("items-center gap-4"):
                ui.icon("checklist", size="2rem").style(f"color: {DBT_ORANGE};")
                ui.label("Requirements Checker").classes("text-2xl font-bold")
            
            ui.label(
                "Verify that all required dependencies are installed and properly configured."
            ).classes("text-slate-600 dark:text-slate-400 mt-2")

        # Licensing bypass
        with ui.card().classes("w-full p-6"):
            ui.label("Licensing").classes("text-lg font-semibold mb-2")
            ui.label(
                "Temporarily bypass Migration Workflow licensing checks."
            ).classes("text-slate-600 dark:text-slate-400 text-sm")
            bypass_enabled = _is_bypass_enabled()
            ui.switch(
                "Bypass migration licensing",
                value=bypass_enabled,
                on_change=lambda e: _toggle_license_bypass(state, bool(e.value)),
            ).classes("mt-2")
        
        # Status cards container
        status_container = ui.column().classes("w-full gap-4")
        
        # Initial check results
        with status_container:
            _create_status_cards(state)
        
        # Action buttons
        with ui.card().classes("w-full p-4"):
            with ui.row().classes("gap-4 justify-end"):
                ui.button(
                    "Run Checks",
                    icon="refresh",
                    on_click=lambda: _refresh_checks(status_container, state)
                ).props("outline")
                
                ui.button(
                    "Install Missing Python Packages",
                    icon="download",
                    on_click=lambda: _install_missing(status_container, state)
                ).style(f"background-color: {DBT_ORANGE};")


def _create_status_cards(state: AppState) -> None:
    """Create status cards for all dependencies."""
    # Run all checks
    results = run_all_checks()
    overall = get_overall_status(results)
    
    # Overall status banner
    if overall == DependencyStatus.OK:
        with ui.row().classes("w-full p-4 rounded-lg bg-green-100 dark:bg-green-900 items-center gap-3"):
            ui.icon("check_circle", size="md").classes("text-green-600 dark:text-green-400")
            ui.label("All requirements satisfied").classes("text-green-800 dark:text-green-200 font-medium")
    else:
        with ui.row().classes("w-full p-4 rounded-lg bg-amber-100 dark:bg-amber-900 items-center gap-3"):
            ui.icon("warning", size="md").classes("text-amber-600 dark:text-amber-400")
            ui.label("Some requirements need attention").classes("text-amber-800 dark:text-amber-200 font-medium")
    
    # Individual dependency cards
    for result in results:
        _create_dependency_card(result)
    
    # Detailed Python packages section
    _create_python_packages_detail()


def _create_dependency_card(result: DependencyResult) -> None:
    """Create a card for a single dependency check result."""
    # Determine status styling
    if result.status == DependencyStatus.OK:
        icon = "check_circle"
        icon_color = "text-green-500"
        border_color = "border-green-500"
    elif result.status == DependencyStatus.OPTIONAL:
        icon = "info"
        icon_color = "text-slate-400"
        border_color = "border-slate-300"
    elif result.status == DependencyStatus.MISSING:
        icon = "cancel"
        icon_color = "text-red-500"
        border_color = "border-red-500"
    elif result.status == DependencyStatus.OUTDATED:
        icon = "update"
        icon_color = "text-amber-500"
        border_color = "border-amber-500"
    else:  # ERROR
        icon = "error"
        icon_color = "text-red-500"
        border_color = "border-red-500"
    
    with ui.card().classes(f"w-full p-4 border-l-4 {border_color}"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.icon(icon, size="md").classes(icon_color)
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(result.name).classes("font-semibold")
                        # Show category badge for optional/workflow-specific
                        if result.category == DependencyCategory.WORKFLOW_SPECIFIC:
                            ui.badge("Optional", color="grey").props("rounded outline")
                    if result.version:
                        ui.label(f"Version: {result.version}").classes("text-sm text-slate-500")
                    # Show which workflows need this dependency
                    if result.workflows:
                        ui.label(f"Used by: {', '.join(result.workflows)}").classes("text-xs text-slate-400")
            
            # Status message
            ui.label(result.message or "").classes("text-sm text-slate-600 dark:text-slate-400")
        
        # Install instructions if missing or optional
        if result.status in (DependencyStatus.MISSING, DependencyStatus.ERROR, DependencyStatus.OPTIONAL):
            with ui.column().classes("mt-3 pt-3 border-t border-slate-200 dark:border-slate-700 gap-2"):
                if result.install_command:
                    with ui.row().classes("items-center gap-2"):
                        ui.label("Install command:").classes("text-sm text-slate-500")
                        ui.code(result.install_command).classes("text-sm")
                
                if result.install_url:
                    with ui.row().classes("items-center gap-2"):
                        ui.label("More info:").classes("text-sm text-slate-500")
                        ui.link(result.install_url, result.install_url, new_tab=True).classes("text-sm")


def _create_python_packages_detail() -> None:
    """Create detailed view of Python package status."""
    _, package_status = check_python_packages()
    
    with ui.expansion("Python Package Details", icon="inventory_2").classes("w-full"):
        with ui.element("div").classes("grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 p-2"):
            for import_name, pip_name, is_installed in package_status:
                if is_installed:
                    icon_class = "text-green-500"
                    icon_name = "check"
                    bg_class = "bg-green-50 dark:bg-green-900/20"
                else:
                    icon_class = "text-red-500"
                    icon_name = "close"
                    bg_class = "bg-red-50 dark:bg-red-900/20"
                
                with ui.row().classes(f"items-center gap-2 p-2 rounded {bg_class}"):
                    ui.icon(icon_name, size="xs").classes(icon_class)
                    ui.label(pip_name).classes("text-sm")


def _is_bypass_enabled() -> bool:
    """Check if licensing bypass is enabled in .env or process env."""
    env_values = load_env_values()
    raw = env_values.get(LICENSE_BYPASS_ENV) or os.getenv(LICENSE_BYPASS_ENV, "")
    return str(raw).lower() in {"1", "true", "yes", "on"}


def _toggle_license_bypass(state: AppState, enabled: bool) -> None:
    """Enable or disable license bypass in .env and refresh state."""
    env_path = find_env_file()
    if not env_path.exists():
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.touch()

    set_key(str(env_path), LICENSE_BYPASS_ENV, "true" if enabled else "false")
    os.environ[LICENSE_BYPASS_ENV] = "true" if enabled else "false"

    get_license_manager().clear_cache()
    status = check_migration_license()
    state.is_migration_licensed = status.is_valid
    state.license_message = status.message
    app.storage.user["app_state"] = state.to_dict()

    if enabled:
        ui.notify("Migration licensing bypass enabled", type="warning")
    else:
        ui.notify("Migration licensing bypass disabled", type="positive")


async def _refresh_checks(container: ui.column, state: AppState) -> None:
    """Refresh all dependency checks."""
    container.clear()
    with container:
        ui.spinner("dots", size="lg").classes("mx-auto my-8")
    
    # Small delay to show spinner
    await ui.run_javascript("await new Promise(r => setTimeout(r, 500))")
    
    container.clear()
    with container:
        _create_status_cards(state)
    
    ui.notify("Dependency checks refreshed", type="positive")


async def _install_missing(container: ui.column, state: AppState) -> None:
    """Install missing Python packages."""
    # Get missing packages
    _, package_status = check_python_packages()
    missing = [pip_name for _, pip_name, installed in package_status if not installed]
    
    if not missing:
        ui.notify("All Python packages are already installed", type="info")
        return
    
    # Show installing notification
    notification = ui.notification(
        f"Installing {len(missing)} package(s)...",
        type="ongoing",
        spinner=True,
        timeout=None
    )
    
    # Run install
    success, message = install_python_packages(missing)
    
    notification.dismiss()
    
    if success:
        ui.notify("Packages installed successfully! Refreshing...", type="positive")
        await _refresh_checks(container, state)
    else:
        ui.notify(f"Installation failed: {message}", type="negative", timeout=10)
