"""Target step page for configuring target account credentials."""

import asyncio
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, TargetCredentials
from importer.web.components.credential_form import (
    create_target_credential_form,
    validate_credentials,
)
from importer.web.env_manager import (
    load_target_credentials,
    load_target_credentials_from_content,
    save_target_credentials,
    fetch_account_name,
)
from importer.web.utils.yaml_viewer import (
    create_migration_summary_card,
    create_yaml_viewer_dialog,
)


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_NAVY = "#192847"


def create_target_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the target step page content.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to persist state
    """
    # Track connection verification state
    connection_status = {
        "tested": False,
        "success": False,
        "message": "",
        "account_name": "",
    }

    # UI element references for dynamic updates
    status_container_ref = {"container": None}

    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-6"):
        # Page header
        with ui.row().classes("w-full items-center gap-4"):
            ui.icon("settings", size="2rem").style(f"color: {DBT_ORANGE};")
            ui.label("Configure Target Account").classes("text-2xl font-bold")

        ui.label(
            "Configure the target dbt Platform account where resources will be deployed."
        ).classes("text-slate-600 dark:text-slate-400")

        # Prerequisite check
        if not state.map.normalize_complete:
            _create_prerequisite_warning(state, on_step_change)
            return

        # Two-column layout
        with ui.row().classes("w-full gap-6"):
            # Left column: Credentials form
            with ui.column().classes("w-1/2 min-w-[400px] gap-4"):
                # Source account info card (read-only reference)
                _create_source_reference_card(state)

                # Target credentials form
                create_target_credential_form(
                    state=state,
                    on_credentials_change=lambda creds: _on_credentials_change(
                        state, save_state, connection_status, status_container_ref
                    ),
                    on_load_env=lambda: _load_env_credentials(state, save_state),
                    on_load_env_content=lambda content, filename: _load_env_from_upload(
                        content, filename, state, save_state
                    ),
                    on_save_env=lambda: _save_env_credentials(state),
                )

            # Right column: Connection status and actions
            with ui.column().classes("flex-grow gap-4"):
                # Connection test section
                _create_connection_test_section(
                    state, save_state, connection_status, status_container_ref
                )

                # Migration summary (what will be deployed)
                _create_migration_summary(state)

        # Navigation buttons
        _create_navigation_section(state, on_step_change, save_state)


def _create_prerequisite_warning(
    state: AppState, on_step_change: Callable[[WorkflowStep], None]
) -> None:
    """Show warning when prerequisites aren't met."""
    with ui.card().classes("w-full p-6 border-l-4 border-yellow-500"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("warning", size="lg").classes("text-yellow-500")
            ui.label("Prerequisites Required").classes("text-xl font-semibold")

        ui.label(
            "You need to complete the Map step and normalize your configuration before configuring the target account."
        ).classes("mt-4 text-slate-600 dark:text-slate-400")

        with ui.row().classes("mt-6 gap-4"):
            if not state.fetch.fetch_complete:
                ui.button(
                    "Go to Fetch",
                    icon="cloud_download",
                    on_click=lambda: on_step_change(WorkflowStep.FETCH),
                ).props("outline")
            elif not state.map.normalize_complete:
                ui.button(
                    "Go to Map",
                    icon="tune",
                    on_click=lambda: on_step_change(WorkflowStep.MAP),
                ).style(f"background-color: {DBT_ORANGE};")


def _create_source_reference_card(state: AppState) -> None:
    """Create a read-only card showing source account info for reference."""
    with ui.card().classes("w-full bg-slate-50 dark:bg-slate-800/50"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("info", size="sm").classes("text-slate-500")
            ui.label("Source Account (Reference)").classes(
                "text-sm font-medium text-slate-600 dark:text-slate-400"
            )

        with ui.column().classes("gap-1"):
            if state.source_account.account_name:
                ui.label(f"Account: {state.source_account.account_name}").classes(
                    "text-sm"
                )
            if state.source_account.account_id:
                ui.label(f"ID: {state.source_account.account_id}").classes(
                    "text-xs text-slate-500 font-mono"
                )
            if state.source_account.host_url:
                ui.label(f"Host: {state.source_account.host_url}").classes(
                    "text-xs text-slate-500 font-mono"
                )


def _create_connection_test_section(
    state: AppState,
    save_state: Callable[[], None],
    connection_status: dict,
    status_container_ref: dict,
) -> None:
    """Create the connection test section."""
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center justify-between mb-4"):
            ui.label("Connection Status").classes("text-lg font-semibold")

            # Test connection button
            test_btn = ui.button(
                "Test Connection",
                icon="network_check",
                on_click=lambda: _test_connection(
                    state, save_state, connection_status, status_container_ref
                ),
            ).props("outline")

        # Status display area
        status_container = ui.column().classes("w-full")
        status_container_ref["container"] = status_container

        with status_container:
            _render_connection_status(state, connection_status)


def _render_connection_status(state: AppState, connection_status: dict) -> None:
    """Render the current connection status."""
    creds = state.target_credentials

    if not creds.is_complete():
        # Show placeholder when credentials aren't entered
        with ui.row().classes("items-center gap-3 p-4 bg-slate-100 dark:bg-slate-800 rounded"):
            ui.icon("pending", size="md").classes("text-slate-400")
            with ui.column().classes("gap-1"):
                ui.label("Awaiting credentials").classes("font-medium text-slate-600 dark:text-slate-400")
                ui.label("Enter target account credentials to test the connection").classes(
                    "text-sm text-slate-500"
                )
    elif connection_status["tested"]:
        if connection_status["success"]:
            # Show success state
            with ui.row().classes("items-center gap-3 p-4 bg-green-50 dark:bg-green-900/20 rounded border border-green-200 dark:border-green-800"):
                ui.icon("check_circle", size="md").classes("text-green-500")
                with ui.column().classes("gap-1"):
                    ui.label("Connection Verified").classes("font-medium text-green-700 dark:text-green-400")
                    if connection_status["account_name"]:
                        ui.label(f"Account: {connection_status['account_name']}").classes(
                            "text-sm text-green-600 dark:text-green-500"
                        )
                    ui.label(connection_status["message"]).classes(
                        "text-sm text-green-600 dark:text-green-500"
                    )
        else:
            # Show error state
            with ui.row().classes("items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded border border-red-200 dark:border-red-800"):
                ui.icon("error", size="md").classes("text-red-500")
                with ui.column().classes("gap-1"):
                    ui.label("Connection Failed").classes("font-medium text-red-700 dark:text-red-400")
                    ui.label(connection_status["message"]).classes(
                        "text-sm text-red-600 dark:text-red-500"
                    )
    else:
        # Credentials entered but not tested
        with ui.row().classes("items-center gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 rounded border border-blue-200 dark:border-blue-800"):
            ui.icon("info", size="md").classes("text-blue-500")
            with ui.column().classes("gap-1"):
                ui.label("Ready to Test").classes("font-medium text-blue-700 dark:text-blue-400")
                ui.label("Click 'Test Connection' to verify your credentials").classes(
                    "text-sm text-blue-600 dark:text-blue-500"
                )


def _create_migration_summary(state: AppState) -> None:
    """Create a summary card showing what will be deployed from the YAML file."""
    yaml_path = state.map.last_yaml_file

    def open_yaml_viewer():
        if yaml_path:
            dialog = create_yaml_viewer_dialog(
                yaml_path,
                title="Migration Configuration"
            )
            dialog.open()

    create_migration_summary_card(
        yaml_path=yaml_path,
        on_view_yaml=open_yaml_viewer,
        show_yaml_button=True,
    )


def _create_navigation_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the navigation buttons section."""
    with ui.row().classes("w-full justify-between mt-6"):
        # Back button
        ui.button(
            "Back to Map",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.MAP),
        ).props("outline")

        # Continue button
        continue_btn = ui.button(
            "Continue to Deploy",
            icon="arrow_forward",
            on_click=lambda: _continue_to_deploy(state, on_step_change),
        ).style(f"background-color: {DBT_ORANGE};")

        # Disable if credentials aren't complete
        if not state.target_credentials.is_complete():
            continue_btn.disable()
            continue_btn.tooltip("Enter and verify target credentials first")


def _on_credentials_change(
    state: AppState,
    save_state: Callable[[], None],
    connection_status: dict,
    status_container_ref: dict,
) -> None:
    """Handle credentials change."""
    # Reset connection status when credentials change
    connection_status["tested"] = False
    connection_status["success"] = False
    connection_status["message"] = ""
    connection_status["account_name"] = ""

    save_state()

    # Update status display
    if status_container_ref["container"]:
        status_container_ref["container"].clear()
        with status_container_ref["container"]:
            _render_connection_status(state, connection_status)


def _load_env_credentials(state: AppState, save_state: Callable[[], None]) -> None:
    """Load target credentials from default .env file."""
    try:
        creds = load_target_credentials()

        if not creds.get("account_id") and not creds.get("api_token"):
            ui.notify("No target credentials found in .env", type="warning")
            return

        # Update state
        state.target_credentials.host_url = creds.get(
            "host_url", "https://cloud.getdbt.com"
        )
        state.target_credentials.account_id = creds.get("account_id", "")
        state.target_credentials.api_token = creds.get("api_token", "")
        state.target_credentials.token_type = creds.get("token_type", "service_token")

        save_state()

        ui.notify("Target credentials loaded", type="positive")

        # Reload page to show new values
        ui.navigate.reload()

    except Exception as e:
        ui.notify(f"Failed to load credentials: {e}", type="negative")


def _load_env_from_upload(
    content: str,
    filename: str,
    state: AppState,
    save_state: Callable[[], None],
) -> None:
    """Load target credentials from uploaded .env file content."""
    try:
        creds = load_target_credentials_from_content(content)

        if not creds.get("account_id") and not creds.get("api_token"):
            ui.notify(f"No target credentials found in {filename}", type="warning")
            return

        # Update state
        state.target_credentials.host_url = creds.get(
            "host_url", "https://cloud.getdbt.com"
        )
        state.target_credentials.account_id = creds.get("account_id", "")
        state.target_credentials.api_token = creds.get("api_token", "")
        state.target_credentials.token_type = creds.get("token_type", "service_token")

        save_state()

        ui.notify(f"Target credentials loaded from {filename}", type="positive")

        # Reload page to show new values
        ui.navigate.reload()

    except Exception as e:
        ui.notify(f"Failed to load credentials: {e}", type="negative")


def _save_env_credentials(state: AppState) -> None:
    """Save target credentials to .env file."""
    creds = state.target_credentials

    if not creds.account_id or not creds.api_token:
        ui.notify("Fill in credentials first", type="warning")
        return

    try:
        path = save_target_credentials(
            host_url=creds.host_url,
            account_id=creds.account_id,
            api_token=creds.api_token,
            token_type=creds.token_type,
        )
        ui.notify(f"Target credentials saved to {path}", type="positive")

    except Exception as e:
        ui.notify(f"Failed to save credentials: {e}", type="negative")


async def _test_connection(
    state: AppState,
    save_state: Callable[[], None],
    connection_status: dict,
    status_container_ref: dict,
) -> None:
    """Test connection to target dbt Platform API."""
    creds = state.target_credentials

    # Validate first
    is_valid, errors = validate_credentials(creds)
    if not is_valid:
        for err in errors:
            ui.notify(err, type="negative")
        return

    # Show testing status
    connection_status["tested"] = False
    if status_container_ref["container"]:
        status_container_ref["container"].clear()
        with status_container_ref["container"]:
            with ui.row().classes("items-center gap-3 p-4 bg-slate-100 dark:bg-slate-800 rounded"):
                ui.spinner(size="md")
                ui.label("Testing connection...").classes("text-slate-600 dark:text-slate-400")

    try:
        success, result = await asyncio.to_thread(
            fetch_account_name,
            creds.host_url,
            creds.account_id,
            creds.api_token,
        )

        connection_status["tested"] = True
        connection_status["success"] = success

        if success:
            connection_status["message"] = "Successfully connected to target account"
            connection_status["account_name"] = result

            # Update target account info
            state.target_account.account_name = result
            state.target_account.account_id = creds.account_id
            state.target_account.host_url = creds.host_url
            state.target_account.is_configured = True
            state.target_account.is_verified = True
            save_state()

            ui.notify(f"Connected to: {result}", type="positive")
        else:
            connection_status["message"] = result
            ui.notify(f"Connection failed: {result}", type="negative")

    except Exception as e:
        connection_status["tested"] = True
        connection_status["success"] = False
        connection_status["message"] = str(e)
        ui.notify(f"Error: {e}", type="negative")

    # Update status display
    if status_container_ref["container"]:
        status_container_ref["container"].clear()
        with status_container_ref["container"]:
            _render_connection_status(state, connection_status)


def _continue_to_deploy(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Validate and continue to deploy step."""
    creds = state.target_credentials

    if not creds.is_complete():
        ui.notify("Please complete target credentials first", type="warning")
        return

    # Check for same account warning
    if (
        state.source_account.account_id
        and state.target_account.account_id
        and state.source_account.account_id == state.target_account.account_id
        and state.source_credentials.host_url == state.target_credentials.host_url
    ):
        ui.notify(
            "Warning: Source and target accounts appear to be the same!",
            type="warning",
            timeout=5,
        )

    on_step_change(WorkflowStep.DEPLOY)
