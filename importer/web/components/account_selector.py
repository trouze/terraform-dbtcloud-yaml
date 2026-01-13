"""Account selector component for the sidebar."""

from typing import Callable

from nicegui import ui

from importer.web.state import AccountInfo, AppState, WorkflowStep


# dbt brand colors
DBT_ORANGE = "#FF694A"


def create_account_cards(
    state: AppState,
    on_configure_source: Callable[[], None],
    on_configure_target: Callable[[], None],
) -> None:
    """Create account info cards for the sidebar.

    Args:
        state: Current application state
        on_configure_source: Callback when "Configure" is clicked for source
        on_configure_target: Callback when "Configure" is clicked for target
    """
    ui.label("ACCOUNTS").classes(
        "px-4 pt-4 pb-2 text-xs text-slate-500 font-semibold tracking-wider"
    )

    # Source Account Card
    _create_account_card(
        account=state.source_account,
        label="Source",
        icon_color="#3B82F6",  # blue
        on_configure=on_configure_source,
    )

    # Target Account Card
    _create_account_card(
        account=state.target_account,
        label="Target",
        icon_color="#10B981",  # green
        on_configure=on_configure_target,
    )


def _create_account_card(
    account: AccountInfo,
    label: str,
    icon_color: str,
    on_configure: Callable[[], None],
) -> None:
    """Create a single account info card.

    Args:
        account: Account information
        label: Label for the card (e.g., "Source", "Target")
        icon_color: Color for the status indicator
        on_configure: Callback when "Configure" is clicked
    """
    with ui.column().classes("w-full px-3 py-2"):
        with ui.card().classes("w-full p-3").style(
            "background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);"
        ):
            # Header row with label, ID, and configure button
            with ui.row().classes("w-full items-center justify-between mb-1"):
                with ui.row().classes("items-center gap-2"):
                    # Status indicator
                    if account.is_verified:
                        ui.icon("check_circle", size="xs").style(f"color: {icon_color};")
                    elif account.is_configured:
                        ui.icon("pending", size="xs").classes("text-amber-500")
                    else:
                        ui.icon("radio_button_unchecked", size="xs").classes("text-slate-500")
                    
                    # Label with ID on same line
                    if account.account_id:
                        ui.label(f"{label} - {account.account_id}").classes("text-xs text-slate-400 uppercase tracking-wide")
                    else:
                        ui.label(label).classes("text-xs text-slate-400 uppercase tracking-wide")
                
                # Configure button
                ui.button(
                    icon="edit",
                    on_click=on_configure,
                ).props("flat dense size=xs").classes("text-slate-400 hover:text-white")

            # Account info
            if account.is_configured:
                # Account name
                if account.account_name:
                    ui.label(account.account_name).classes("text-white font-medium text-sm truncate")
                else:
                    ui.label("Verifying...").classes("text-slate-400 text-sm italic")

                # Host URL (truncated)
                host_display = account.host_url.replace("https://", "").replace("http://", "")
                if len(host_display) > 25:
                    host_display = host_display[:22] + "..."
                ui.label(host_display).classes("text-xs text-white opacity-70")
            else:
                ui.label("Not configured").classes("text-slate-500 text-sm italic")


def create_compact_account_status(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create a compact account status display for the sidebar.

    Shows just icons and minimal info with tooltips.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
    """
    ui.label("ACCOUNTS").classes(
        "px-4 pt-4 pb-2 text-xs text-slate-500 font-semibold tracking-wider"
    )

    with ui.row().classes("w-full px-4 gap-2"):
        # Source account
        with ui.column().classes("flex-1"):
            _create_mini_account_card(
                account=state.source_account,
                label="Source",
                color="#3B82F6",
                on_click=lambda: on_step_change(WorkflowStep.FETCH),
            )

        # Target account
        with ui.column().classes("flex-1"):
            _create_mini_account_card(
                account=state.target_account,
                label="Target",
                color="#10B981",
                on_click=lambda: on_step_change(WorkflowStep.TARGET),
            )


def _create_mini_account_card(
    account: AccountInfo,
    label: str,
    color: str,
    on_click: Callable[[], None],
) -> None:
    """Create a mini account card."""
    with ui.card().classes("w-full p-2 cursor-pointer").style(
        "background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);"
    ).on("click", on_click):
        with ui.column().classes("items-center gap-1"):
            # Status icon
            if account.is_verified:
                ui.icon("check_circle", size="sm").style(f"color: {color};")
            elif account.is_configured:
                ui.icon("pending", size="sm").classes("text-amber-500")
            else:
                ui.icon("add_circle_outline", size="sm").classes("text-slate-500")

            # Label
            ui.label(label).classes("text-xs text-slate-400")

            # Account name or ID (truncated)
            if account.account_name:
                display = account.account_name[:10] + "..." if len(account.account_name) > 10 else account.account_name
                ui.label(display).classes("text-xs text-white font-medium truncate")
            elif account.account_id:
                ui.label(f"#{account.account_id}").classes("text-xs text-slate-500")
            else:
                ui.label("—").classes("text-xs text-slate-600")
