"""Main NiceGUI application setup and routing."""

from pathlib import Path
from typing import Optional

from nicegui import app, ui

from importer.web.state import AppState, WorkflowStep, WorkflowType, STEP_NAMES
from importer.web.components.stepper import create_nav_drawer, create_progress_header
from importer.web.pages.home import create_home_page
from importer.web.pages.requirements import create_requirements_page
from importer.web.pages.fetch_source import create_fetch_source_page
from importer.web.pages.explore_source import create_explore_source_page
from importer.web.pages.scope import create_scope_page
from importer.web.pages.fetch_target import create_fetch_target_page
from importer.web.pages.explore_target import create_explore_target_page
from importer.web.pages.match import create_match_page
from importer.web.pages.configure import create_configure_page
from importer.web.pages.deploy import create_deploy_page
from importer.web.pages.destroy import create_destroy_page
from importer.web.pages.target_credentials import create_target_credentials_page
from importer.web.pages.utilities import create_utilities_page
from importer.web.env_manager import load_account_info_from_env
from importer.web.licensing import (
    LicenseTier,
    check_migration_license,
    has_feature_access,
)

# Jobs as Code Generator workflow pages
from importer.web.workflows.jobs_as_code.pages.select import create_jac_select_page
from importer.web.workflows.jobs_as_code.pages.fetch import create_jac_fetch_page
from importer.web.workflows.jobs_as_code.pages.jobs import create_jac_jobs_page
from importer.web.workflows.jobs_as_code.pages.target import create_jac_target_page
from importer.web.workflows.jobs_as_code.pages.mapping import create_jac_mapping_page
from importer.web.workflows.jobs_as_code.pages.config import create_jac_config_page
from importer.web.workflows.jobs_as_code.pages.generate import create_jac_generate_page

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


# Global state - will be replaced with proper session management
_app_state: Optional[AppState] = None


def get_state() -> AppState:
    """Get the current application state."""
    global _app_state
    if _app_state is None:
        # Try to restore from storage
        stored = app.storage.user.get("app_state")
        if stored:
            _app_state = AppState.from_dict(stored)
        else:
            _app_state = AppState()
        
        # Always refresh account info from .env on startup
        _refresh_account_info(_app_state)
        _refresh_license_status(_app_state)
    return _app_state


def _refresh_account_info(state: AppState) -> None:
    """Refresh account info from .env file."""
    try:
        state.source_account = load_account_info_from_env("source")
        state.target_account = load_account_info_from_env("target")
    except Exception:
        # If loading fails, keep defaults
        pass


def _refresh_license_status(state: AppState) -> None:
    """Refresh migration workflow license status and tier."""
    try:
        status = check_migration_license()
        state.is_migration_licensed = status.is_valid
        state.license_tier = status.tier.value
        state.license_email = status.email or ""
        state.license_message = status.message
    except Exception as exc:
        state.is_migration_licensed = False
        state.license_tier = LicenseTier.EXPLORER.value
        state.license_email = ""
        state.license_message = f"License verification failed: {exc}"


def save_state() -> None:
    """Save the current state to storage."""
    global _app_state
    if _app_state:
        try:
            app.storage.user["app_state"] = _app_state.to_dict()
            # Also save protection intent file if it was accessed
            _app_state.save_protection_intent()
        except (AssertionError, KeyError) as e:
            # User storage not yet initialized (e.g., direct URL access before session established)
            # This is recoverable - state will be saved on next interaction
            import logging
            logging.getLogger(__name__).debug(f"Could not save state (session not ready): {e}")


def navigate_to_step(step: WorkflowStep) -> None:
    """Navigate to a workflow step."""
    state = get_state()
    state.current_step = step
    save_state()
    ui.navigate.to(f"/{step.name.lower()}" if step != WorkflowStep.HOME else "/")


def set_workflow(workflow: WorkflowType) -> None:
    """Set the active workflow and navigate to a valid step."""
    state = get_state()

    # Get current tier for access checks
    try:
        tier = LicenseTier(state.license_tier)
    except ValueError:
        tier = LicenseTier.EXPLORER

    # Map workflow types to feature keys
    workflow_features = {
        WorkflowType.MIGRATION: "migration",
        WorkflowType.ACCOUNT_EXPLORER: "account_explorer",
        WorkflowType.JOBS_AS_CODE: "jobs_as_code",
        WorkflowType.IMPORT_ADOPT: "import_adopt",
    }

    feature_key = workflow_features.get(workflow)
    if feature_key and not has_feature_access(tier, feature_key):
        tier_name = {
            LicenseTier.EXPLORER: "Explorer",
            LicenseTier.SOLUTIONS_ARCHITECT: "Solutions Architect",
            LicenseTier.RESIDENT_ARCHITECT: "Resident Architect",
            LicenseTier.ENGINEERING: "Engineering",
        }.get(tier, "Explorer")
        ui.notify(
            f"Your license tier ({tier_name}) does not include access to this workflow. "
            "Upgrade your license or contact Professional Services at info@getdbt.com.",
            type="warning",
        )
        ui.navigate.to("/")
        return

    state.workflow = workflow
    steps = state.workflow_steps()
    next_step = state.current_step if state.current_step in steps else steps[0]
    state.current_step = next_step
    save_state()
    ui.navigate.to(f"/{next_step.name.lower()}" if next_step != WorkflowStep.HOME else "/")


def toggle_theme() -> None:
    """Toggle between dark and light theme."""
    state = get_state()
    state.theme = "light" if state.theme == "dark" else "dark"
    save_state()
    ui.navigate.reload()


def clear_session() -> None:
    """Clear the session and start fresh."""
    global _app_state
    _app_state = AppState()
    app.storage.user.clear()
    ui.notify("Session cleared", type="positive")
    ui.navigate.to("/")


def navigate_to_requirements() -> None:
    """Navigate to the requirements page."""
    ui.navigate.to("/requirements")


def _require_workflow_access(state: AppState) -> bool:
    """Ensure the current workflow is accessible with the current license tier."""
    # Get current tier
    try:
        tier = LicenseTier(state.license_tier)
    except ValueError:
        tier = LicenseTier.EXPLORER

    # Map workflow types to feature keys
    workflow_features = {
        WorkflowType.MIGRATION: "migration",
        WorkflowType.ACCOUNT_EXPLORER: "account_explorer",
        WorkflowType.JOBS_AS_CODE: "jobs_as_code",
        WorkflowType.IMPORT_ADOPT: "import_adopt",
    }

    feature_key = workflow_features.get(state.workflow)
    if feature_key and has_feature_access(tier, feature_key):
        return True

    ui.notify(
        "Your license tier does not include access to this workflow. "
        "Upgrade your license or contact Professional Services at info@getdbt.com.",
        type="warning",
    )
    ui.navigate.to("/")
    return False


def _require_migration_license(state: AppState) -> bool:
    """Ensure migration workflow access is licensed (legacy compatibility)."""
    return _require_workflow_access(state)


def setup_page(state: AppState) -> None:
    """Common page setup - theme and navigation."""
    # Apply theme
    if state.theme == "dark":
        ui.dark_mode().enable()
    else:
        ui.dark_mode().disable()

    # Add global CSS for AG Grid dark mode support
    # NiceGUI uses .dark class on body, but AG Grid's quartz-auto-dark only responds to
    # prefers-color-scheme media query. These CSS overrides bridge the gap.
    ui.add_css("""
        /* AG Grid dark mode overrides for NiceGUI */
        .dark .ag-theme-quartz, .body--dark .ag-theme-quartz,
        .dark .ag-theme-quartz-auto-dark, .body--dark .ag-theme-quartz-auto-dark {
            --ag-background-color: #1e1e1e !important;
            --ag-header-background-color: #2d2d2d !important;
            --ag-odd-row-background-color: #262626 !important;
            --ag-row-hover-color: #3d3d3d !important;
            --ag-selected-row-background-color: #3d5a80 !important;
            --ag-foreground-color: #e0e0e0 !important;
            --ag-header-foreground-color: #e0e0e0 !important;
            --ag-secondary-foreground-color: #a0a0a0 !important;
            --ag-border-color: #404040 !important;
            --ag-input-border-color: #505050 !important;
        }
        .dark .ag-theme-quartz .ag-root-wrapper, .body--dark .ag-theme-quartz .ag-root-wrapper,
        .dark .ag-theme-quartz-auto-dark .ag-root-wrapper, .body--dark .ag-theme-quartz-auto-dark .ag-root-wrapper {
            background-color: #1e1e1e !important;
        }
        .dark .ag-theme-quartz .ag-header, .body--dark .ag-theme-quartz .ag-header,
        .dark .ag-theme-quartz-auto-dark .ag-header, .body--dark .ag-theme-quartz-auto-dark .ag-header {
            background-color: #2d2d2d !important;
        }
        .dark .ag-theme-quartz .ag-row, .body--dark .ag-theme-quartz .ag-row,
        .dark .ag-theme-quartz-auto-dark .ag-row, .body--dark .ag-theme-quartz-auto-dark .ag-row {
            background-color: #1e1e1e !important;
        }
        .dark .ag-theme-quartz .ag-row-odd, .body--dark .ag-theme-quartz .ag-row-odd,
        .dark .ag-theme-quartz-auto-dark .ag-row-odd, .body--dark .ag-theme-quartz-auto-dark .ag-row-odd {
            background-color: #262626 !important;
        }
        .dark .ag-theme-quartz .ag-cell, .body--dark .ag-theme-quartz .ag-cell,
        .dark .ag-theme-quartz-auto-dark .ag-cell, .body--dark .ag-theme-quartz-auto-dark .ag-cell {
            color: #e0e0e0 !important;
        }
        
        /* Global AG Grid font size standardization - matches text-xs (12px) */
        .ag-theme-quartz .ag-cell,
        .ag-theme-quartz-auto-dark .ag-cell,
        .ag-theme-quartz .ag-header-cell-text,
        .ag-theme-quartz-auto-dark .ag-header-cell-text {
            font-size: 12px !important;
        }
        .ag-theme-quartz .ag-header-cell,
        .ag-theme-quartz-auto-dark .ag-header-cell {
            font-size: 12px !important;
        }
        
    """)

    # Create navigation drawer with callbacks
    create_nav_drawer(
        state,
        navigate_to_step,
        set_workflow,
        toggle_theme,
        clear_session,
        navigate_to_requirements,
    )


def create_page_content(state: AppState) -> None:
    """Create the main content area based on current step."""
    step = state.current_step

    if step == WorkflowStep.HOME:
        create_home_page(state, navigate_to_step, set_workflow, save_state)
    elif step == WorkflowStep.FETCH_SOURCE:
        create_fetch_source_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.EXPLORE_SOURCE:
        create_explore_source_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.SCOPE:
        create_scope_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.FETCH_TARGET:
        create_fetch_target_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.EXPLORE_TARGET:
        create_explore_target_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.MATCH:
        create_match_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.CONFIGURE:
        create_configure_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.TARGET_CREDENTIALS:
        create_target_credentials_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.DEPLOY:
        create_deploy_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.DESTROY:
        create_destroy_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.UTILITIES:
        create_utilities_page(state, navigate_to_step, save_state)
    # Jobs as Code Generator workflow steps
    elif step == WorkflowStep.JAC_SELECT:
        create_jac_select_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_FETCH:
        create_jac_fetch_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_JOBS:
        create_jac_jobs_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_TARGET:
        create_jac_target_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_MAPPING:
        create_jac_mapping_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_CONFIG:
        create_jac_config_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_GENERATE:
        create_jac_generate_page(state, navigate_to_step, save_state)


def _create_placeholder_page(title: str, description: str, state: AppState) -> None:
    """Create a placeholder page for unimplemented steps."""
    with ui.column().classes("w-full max-w-4xl mx-auto p-8 gap-4"):
        with ui.card().classes("w-full p-8"):
            with ui.row().classes("items-center gap-4"):
                ui.icon("construction", size="2rem").style("color: #FF694A;")
                ui.label(title).classes("text-2xl font-bold")

            ui.label(description).classes("text-slate-600 dark:text-slate-400 mt-2")

            ui.markdown("""
                This page is coming soon. The implementation will include:
                
                - Full functionality as described in the PRD
                - Integration with the existing importer modules
                - Persistent state management
            """).classes("mt-4")

            with ui.row().classes("gap-4 mt-6"):
                # Previous step button
                workflow_steps = list(WorkflowStep)
                current_idx = workflow_steps.index(state.current_step)
                if current_idx > 1:  # Skip HOME
                    prev_step = workflow_steps[current_idx - 1]
                    ui.button(
                        f"Back to {STEP_NAMES[prev_step]}",
                        icon="arrow_back",
                        on_click=lambda s=prev_step: navigate_to_step(s),
                    ).props("outline")

                # Next step button (placeholder)
                if current_idx < len(workflow_steps) - 1:
                    next_step = workflow_steps[current_idx + 1]
                    ui.button(
                        f"Continue to {STEP_NAMES[next_step]}",
                        icon="arrow_forward",
                        on_click=lambda s=next_step: navigate_to_step(s),
                    ).style("background-color: #FF694A;")


@ui.page("/")
def home_page() -> None:
    """Home page route."""
    state = get_state()
    state.current_step = WorkflowStep.HOME
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/fetch_source")
def fetch_source_page() -> None:
    """Fetch Source step page route."""
    state = get_state()
    state.current_step = WorkflowStep.FETCH_SOURCE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/explore_source")
def explore_source_page() -> None:
    """Explore Source step page route."""
    state = get_state()
    state.current_step = WorkflowStep.EXPLORE_SOURCE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/scope")
def scope_page() -> None:
    """Scope step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.SCOPE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/fetch_target")
def fetch_target_page() -> None:
    """Fetch Target step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.FETCH_TARGET
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/explore_target")
def explore_target_page() -> None:
    """Explore Target step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.EXPLORE_TARGET
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/match")
def match_page() -> None:
    """Match step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.MATCH
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/configure")
def configure_page() -> None:
    """Configure Migration step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.CONFIGURE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/target_credentials")
def target_credentials_page() -> None:
    """Target Credentials step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.TARGET_CREDENTIALS
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/deploy")
def deploy_page() -> None:
    """Deploy step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.DEPLOY
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/destroy")
def destroy_page() -> None:
    """Destroy step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.DESTROY
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/utilities")
def utilities_page() -> None:
    """Utilities page route."""
    state = get_state()
    state.current_step = WorkflowStep.UTILITIES
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/requirements")
def requirements_page() -> None:
    """Requirements checker page route."""
    state = get_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_requirements_page(state)


# Jobs as Code Generator workflow routes
@ui.page("/jac_select")
def jac_select_page() -> None:
    """Jobs as Code Generator - Select workflow page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_SELECT
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_fetch")
def jac_fetch_page() -> None:
    """Jobs as Code Generator - Fetch jobs page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_FETCH
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_jobs")
def jac_jobs_page() -> None:
    """Jobs as Code Generator - Select jobs page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_JOBS
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_target")
def jac_target_page() -> None:
    """Jobs as Code Generator - Target config page (clone only)."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_TARGET
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_mapping")
def jac_mapping_page() -> None:
    """Jobs as Code Generator - Resource mapping page (clone only)."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_MAPPING
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_config")
def jac_config_page() -> None:
    """Jobs as Code Generator - Job configuration page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_CONFIG
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_generate")
def jac_generate_page() -> None:
    """Jobs as Code Generator - Generate and export page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_GENERATE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


def run_app(
    host: str = "127.0.0.1",
    port: int = 8080,
    show: bool = True,
    reload: bool = False,
) -> None:
    """Run the NiceGUI application.

    Args:
        host: Host to bind to
        port: Port to run on
        show: Whether to auto-open browser
        reload: Whether to enable auto-reload
    """
    # Serve static files
    app.add_static_files("/static", str(STATIC_DIR))

    # Favicon needs absolute path
    favicon_path = STATIC_DIR / "favicon.svg"

    ui.run(
        host=host,
        port=port,
        show=show,
        reload=reload,
        title="dbt Magellan: Exploration & Migration Tool",
        favicon=str(favicon_path),
        storage_secret="dbt-cloud-importer-secret",  # For user storage
    )
