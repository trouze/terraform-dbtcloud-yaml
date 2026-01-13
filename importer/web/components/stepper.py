"""Navigation stepper component for the workflow steps."""

from typing import Callable

from nicegui import ui

from importer.web.state import STEP_ICONS, STEP_NAMES, AppState, WorkflowStep
from importer.web.components.account_selector import create_account_cards


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_ORANGE_DARK = "#E55A3D"
DBT_NAVY = "#1E1E2E"
DBT_NAVY_LIGHT = "#2D2D3D"


def create_nav_drawer(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    on_theme_change: Callable[[], None],
    on_clear_session: Callable[[], None],
    on_navigate_requirements: Callable[[], None],
) -> None:
    """Create the left navigation drawer with workflow steps.

    Args:
        state: Current application state
        on_step_change: Callback when user clicks a step
        on_theme_change: Callback when theme toggle is clicked
        on_clear_session: Callback when clear session is clicked
        on_navigate_requirements: Callback when requirements link is clicked
    """
    # Sidebar is always dark navy with white text
    with ui.left_drawer(value=True).classes("text-white").style(
        f"background-color: {DBT_NAVY};"
    ) as drawer:
        # Logo/title area
        with ui.column().classes("w-full items-center py-6 border-b border-slate-700"):
            ui.image("/static/favicon.svg").classes("w-14 h-14")
            ui.label("dbt Platform").classes("text-xl font-bold mt-3 text-white")
            ui.label("Account Migration Tool").classes("text-sm text-slate-400")

        # Workflow steps
        ui.label("WORKFLOW").classes("px-4 pt-6 pb-2 text-xs text-slate-500 font-semibold tracking-wider")

        workflow_steps = [
            WorkflowStep.FETCH,
            WorkflowStep.EXPLORE,
            WorkflowStep.MAP,
            WorkflowStep.TARGET,
            WorkflowStep.DEPLOY,
        ]

        for step in workflow_steps:
            _create_step_item(state, step, on_step_change)

        # Account cards section (below workflow)
        create_account_cards(
            state=state,
            on_configure_source=lambda: on_step_change(WorkflowStep.FETCH),
            on_configure_target=lambda: on_step_change(WorkflowStep.TARGET),
        )

        # Spacer
        ui.element("div").classes("flex-grow")

        # Bottom section with actions
        with ui.column().classes("w-full border-t border-slate-700 p-4 gap-2"):
            # Home button
            with ui.row().classes("w-full items-center gap-2 px-2 py-2 rounded hover:bg-slate-700 cursor-pointer").on(
                "click", lambda: on_step_change(WorkflowStep.HOME)
            ):
                ui.icon("home", size="sm").classes("text-slate-400")
                ui.label("Home").classes("text-white text-sm")

            # Requirements button
            with ui.row().classes("w-full items-center gap-2 px-2 py-2 rounded hover:bg-slate-700 cursor-pointer").on(
                "click", on_navigate_requirements
            ):
                ui.icon("checklist", size="sm").classes("text-slate-400")
                ui.label("Requirements").classes("text-white text-sm")

            # Theme toggle
            theme_icon = "light_mode" if state.theme == "dark" else "dark_mode"
            theme_label = "Light Mode" if state.theme == "dark" else "Dark Mode"
            with ui.row().classes("w-full items-center gap-2 px-2 py-2 rounded hover:bg-slate-700 cursor-pointer").on(
                "click", on_theme_change
            ):
                ui.icon(theme_icon, size="sm").classes("text-slate-400")
                ui.label(theme_label).classes("text-white text-sm")

            # Clear session
            with ui.row().classes("w-full items-center gap-2 px-2 py-2 rounded hover:bg-slate-700 cursor-pointer").on(
                "click", on_clear_session
            ):
                ui.icon("refresh", size="sm").classes("text-slate-400")
                ui.label("Clear Session").classes("text-white text-sm")

    return drawer


def _create_step_item(
    state: AppState,
    step: WorkflowStep,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create a single step item in the navigation."""
    is_current = state.current_step == step
    is_complete = state.step_is_complete(step)
    is_accessible = state.step_is_accessible(step)

    # Determine styling using dbt orange (always dark sidebar)
    if is_current:
        bg_style = f"background-color: {DBT_ORANGE};"
        text_class = "text-white"
        icon_class = "text-white"
        number_style = f"background-color: {DBT_ORANGE_DARK}; color: white;"
    elif is_complete:
        bg_style = ""
        text_class = "text-green-400"
        icon_class = "text-green-400"
        number_style = "background-color: #22c55e; color: white;"
    elif is_accessible:
        bg_style = ""
        text_class = "text-white"
        icon_class = "text-slate-400"
        number_style = f"background-color: {DBT_NAVY_LIGHT}; color: #94a3b8;"
    else:
        bg_style = ""
        text_class = "text-slate-600"
        icon_class = "text-slate-600"
        number_style = f"background-color: {DBT_NAVY_LIGHT}; color: #475569;"

    cursor_class = "cursor-pointer" if is_accessible else "cursor-not-allowed"
    hover_class = "hover:bg-slate-700" if is_accessible and not is_current else ""

    def handle_click():
        if is_accessible:
            on_step_change(step)
        else:
            ui.notify("Complete previous steps first", type="warning")

    with ui.row().classes(
        f"w-full px-4 py-3 items-center gap-3 {hover_class} {cursor_class}"
    ).style(bg_style).on("click", handle_click):
        # Step number or checkmark
        if is_complete and not is_current:
            ui.icon("check_circle", size="sm").classes(icon_class)
        else:
            with ui.element("div").classes(
                "w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold"
            ).style(number_style):
                ui.label(str(step.value))

        # Step icon and name
        ui.icon(STEP_ICONS[step], size="sm").classes(icon_class)
        ui.label(STEP_NAMES[step]).classes(f"flex-grow font-medium {text_class}")

        # Lock indicator for inaccessible steps
        if not is_accessible:
            ui.icon("lock", size="xs").classes("text-slate-600")


def create_progress_header(state: AppState) -> None:
    """Create the progress header showing current step and overall progress."""
    is_light = state.theme == "light"
    
    workflow_steps = [
        WorkflowStep.FETCH,
        WorkflowStep.EXPLORE,
        WorkflowStep.MAP,
        WorkflowStep.TARGET,
        WorkflowStep.DEPLOY,
    ]

    completed_count = sum(1 for s in workflow_steps if state.step_is_complete(s))
    total_steps = len(workflow_steps)

    # Theme-aware colors for progress header
    if is_light:
        header_bg = "#F3F4F6"  # light gray
        text_color = "#1F2937"  # dark text
        text_muted = "#6B7280"
        dot_inactive = "#D1D5DB"
    else:
        header_bg = DBT_NAVY_LIGHT
        text_color = "#FFFFFF"
        text_muted = "#94A3B8"
        dot_inactive = "#475569"

    with ui.row().classes("w-full items-center gap-4 px-6 py-3").style(
        f"background-color: {header_bg};"
    ):
        # Current step info
        if state.current_step == WorkflowStep.HOME:
            step_text = "Home"
        else:
            step_text = f"Step {state.current_step.value} of {total_steps}: {STEP_NAMES[state.current_step]}"

        ui.label(step_text).classes("text-lg font-semibold").style(f"color: {text_color};")

        # Spacer
        ui.element("div").classes("flex-grow")

        # Progress indicator
        ui.label(f"{completed_count}/{total_steps} complete").classes("text-sm").style(f"color: {text_muted};")

        # Progress dots using dbt orange
        with ui.row().classes("gap-1.5"):
            for step in workflow_steps:
                if state.step_is_complete(step):
                    color = "background-color: #22c55e;"  # green
                elif state.current_step == step:
                    color = f"background-color: {DBT_ORANGE};"
                else:
                    color = f"background-color: {dot_inactive};"
                ui.element("div").classes("w-2.5 h-2.5 rounded-full").style(color)
