"""Main NiceGUI application setup and routing."""

from pathlib import Path
from typing import Optional

from nicegui import app, ui

from importer.web.state import AppState, WorkflowStep, STEP_NAMES
from importer.web.components.stepper import create_nav_drawer, create_progress_header, DBT_NAVY
from importer.web.pages.home import create_home_page
from importer.web.pages.requirements import create_requirements_page
from importer.web.pages.fetch import create_fetch_page
from importer.web.pages.explore import create_explore_page
from importer.web.env_manager import load_account_info_from_env

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
    return _app_state


def _refresh_account_info(state: AppState) -> None:
    """Refresh account info from .env file."""
    try:
        state.source_account = load_account_info_from_env("source")
        state.target_account = load_account_info_from_env("target")
    except Exception:
        # If loading fails, keep defaults
        pass


def save_state() -> None:
    """Save the current state to storage."""
    global _app_state
    if _app_state:
        app.storage.user["app_state"] = _app_state.to_dict()


def navigate_to_step(step: WorkflowStep) -> None:
    """Navigate to a workflow step."""
    state = get_state()
    state.current_step = step
    save_state()
    ui.navigate.to(f"/{step.name.lower()}" if step != WorkflowStep.HOME else "/")


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


def setup_page(state: AppState) -> None:
    """Common page setup - theme and navigation."""
    # Apply theme
    if state.theme == "dark":
        ui.dark_mode().enable()
    else:
        ui.dark_mode().disable()

    # Create navigation drawer with callbacks
    create_nav_drawer(
        state,
        navigate_to_step,
        toggle_theme,
        clear_session,
        navigate_to_requirements,
    )


def create_page_content(state: AppState) -> None:
    """Create the main content area based on current step."""
    step = state.current_step

    if step == WorkflowStep.HOME:
        create_home_page(state, navigate_to_step)
    elif step == WorkflowStep.FETCH:
        create_fetch_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.EXPLORE:
        create_explore_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.MAP:
        _create_placeholder_page("Map", "Select entities and configure normalization", state)
    elif step == WorkflowStep.TARGET:
        _create_placeholder_page("Target", "Configure target account credentials", state)
    elif step == WorkflowStep.DEPLOY:
        _create_placeholder_page("Deploy", "Generate Terraform and deploy", state)


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


@ui.page("/fetch")
def fetch_page() -> None:
    """Fetch step page route."""
    state = get_state()
    state.current_step = WorkflowStep.FETCH
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/explore")
def explore_page() -> None:
    """Explore step page route."""
    state = get_state()
    state.current_step = WorkflowStep.EXPLORE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/map")
def map_page() -> None:
    """Map step page route."""
    state = get_state()
    state.current_step = WorkflowStep.MAP
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/target")
def target_page() -> None:
    """Target step page route."""
    state = get_state()
    state.current_step = WorkflowStep.TARGET
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/deploy")
def deploy_page() -> None:
    """Deploy step page route."""
    state = get_state()
    state.current_step = WorkflowStep.DEPLOY
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
        title="dbt Platform Account Exploration and Migration Tool",
        favicon=str(favicon_path),
        storage_secret="dbt-cloud-importer-secret",  # For user storage
    )
