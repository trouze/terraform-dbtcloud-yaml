"""Credential form component for entering dbt Platform account credentials."""

from typing import Callable, Optional, Union

from nicegui import ui

from importer.web.state import AppState, SourceCredentials, TargetCredentials


# dbt brand colors
DBT_ORANGE = "#FF694A"


def create_source_credential_form(
    state: AppState,
    on_credentials_change: Optional[Callable[[SourceCredentials], None]] = None,
    on_load_env: Optional[Callable[[], None]] = None,
    on_save_env: Optional[Callable[[], None]] = None,
) -> None:
    """Create a form for entering source dbt Platform credentials.

    Args:
        state: Application state containing current credentials
        on_credentials_change: Callback when credentials change
        on_load_env: Callback when "Load from .env" is clicked
        on_save_env: Callback when "Save to .env" is clicked
    """
    creds = state.source_credentials

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between mb-4"):
            ui.label("Source Account Credentials").classes("text-lg font-semibold")
            
            # .env buttons
            with ui.row().classes("gap-2"):
                ui.button(
                    "Load from .env",
                    icon="upload_file",
                    on_click=on_load_env,
                ).props("outline size=sm")
                ui.button(
                    "Save to .env",
                    icon="save",
                    on_click=on_save_env,
                ).props("outline size=sm")

        # Host URL field
        host_input = ui.input(
            label="Host URL",
            value=creds.host_url,
            placeholder="https://cloud.getdbt.com",
        ).classes("w-full").props('outlined')
        host_input.on('update:model-value', lambda e: _update_host(creds, e.args, on_credentials_change))

        # Account ID field
        account_input = ui.input(
            label="Account ID",
            value=creds.account_id,
            placeholder="12345",
        ).classes("w-full mt-4").props('outlined type=number')
        account_input.on('update:model-value', lambda e: _update_account_id(creds, e.args, on_credentials_change))

        # API Token field with show/hide toggle
        with ui.row().classes("w-full items-end gap-2 mt-4"):
            token_input = ui.input(
                label="API Token",
                value=creds.api_token,
                placeholder="dbtc_••••••••••••••••",
                password=True,
                password_toggle_button=True,
            ).classes("flex-grow").props('outlined')
            token_input.on('update:model-value', lambda e: _update_token(creds, e.args, on_credentials_change))

        # Help text
        with ui.row().classes("w-full mt-4 items-center gap-2"):
            ui.icon("info", size="xs").classes("text-slate-500")
            ui.label(
                "Use a Personal Access Token (PAT) or Service Token with read permissions."
            ).classes("text-xs text-slate-500")


def create_target_credential_form(
    state: AppState,
    on_credentials_change: Optional[Callable[[TargetCredentials], None]] = None,
    on_load_env: Optional[Callable[[], None]] = None,
    on_save_env: Optional[Callable[[], None]] = None,
) -> None:
    """Create a form for entering target dbt Platform credentials.

    Args:
        state: Application state containing current credentials
        on_credentials_change: Callback when credentials change
        on_load_env: Callback when "Load from .env" is clicked
        on_save_env: Callback when "Save to .env" is clicked
    """
    creds = state.target_credentials

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between mb-4"):
            ui.label("Target Account Credentials").classes("text-lg font-semibold")
            
            # .env buttons
            with ui.row().classes("gap-2"):
                ui.button(
                    "Load from .env",
                    icon="upload_file",
                    on_click=on_load_env,
                ).props("outline size=sm")
                ui.button(
                    "Save to .env",
                    icon="save",
                    on_click=on_save_env,
                ).props("outline size=sm")

        # Host URL field
        host_input = ui.input(
            label="Host URL",
            value=creds.host_url,
            placeholder="https://cloud.getdbt.com",
        ).classes("w-full").props('outlined')
        host_input.on('update:model-value', lambda e: _update_target_host(creds, e.args, on_credentials_change))

        # Account ID field
        account_input = ui.input(
            label="Account ID",
            value=creds.account_id,
            placeholder="12345",
        ).classes("w-full mt-4").props('outlined type=number')
        account_input.on('update:model-value', lambda e: _update_target_account_id(creds, e.args, on_credentials_change))

        # API Token field with show/hide toggle
        with ui.row().classes("w-full items-end gap-2 mt-4"):
            token_input = ui.input(
                label="API Token",
                value=creds.api_token,
                placeholder="dbtc_••••••••••••••••",
                password=True,
                password_toggle_button=True,
            ).classes("flex-grow").props('outlined')
            token_input.on('update:model-value', lambda e: _update_target_token(creds, e.args, on_credentials_change))

        # Token type selector
        ui.select(
            label="Token Type",
            options=[
                {"label": "Service Token", "value": "service_token"},
                {"label": "User Token (PAT)", "value": "user_token"},
            ],
            value=creds.token_type,
        ).classes("w-full mt-4").props('outlined').on(
            'update:model-value',
            lambda e: _update_target_token_type(creds, e.args, on_credentials_change)
        )

        # Help text
        with ui.row().classes("w-full mt-4 items-center gap-2"):
            ui.icon("info", size="xs").classes("text-slate-500")
            ui.label(
                "Target account needs write permissions for deployment."
            ).classes("text-xs text-slate-500")


def _update_host(creds: SourceCredentials, value: str, callback: Optional[Callable] = None) -> None:
    """Update host URL in credentials."""
    creds.host_url = value if value else "https://cloud.getdbt.com"
    if callback:
        callback(creds)


def _update_account_id(creds: SourceCredentials, value: str, callback: Optional[Callable] = None) -> None:
    """Update account ID in credentials."""
    creds.account_id = value if value else ""
    if callback:
        callback(creds)


def _update_token(creds: SourceCredentials, value: str, callback: Optional[Callable] = None) -> None:
    """Update API token in credentials."""
    creds.api_token = value if value else ""
    if callback:
        callback(creds)


def _update_target_host(creds: TargetCredentials, value: str, callback: Optional[Callable] = None) -> None:
    """Update host URL in target credentials."""
    creds.host_url = value if value else "https://cloud.getdbt.com"
    if callback:
        callback(creds)


def _update_target_account_id(creds: TargetCredentials, value: str, callback: Optional[Callable] = None) -> None:
    """Update account ID in target credentials."""
    creds.account_id = value if value else ""
    if callback:
        callback(creds)


def _update_target_token(creds: TargetCredentials, value: str, callback: Optional[Callable] = None) -> None:
    """Update API token in target credentials."""
    creds.api_token = value if value else ""
    if callback:
        callback(creds)


def _update_target_token_type(creds: TargetCredentials, value: str, callback: Optional[Callable] = None) -> None:
    """Update token type in target credentials."""
    creds.token_type = value if value else "service_token"
    if callback:
        callback(creds)


def validate_credentials(creds: Union[SourceCredentials, TargetCredentials]) -> tuple[bool, list[str]]:
    """Validate credentials and return (is_valid, error_messages).

    Args:
        creds: Credentials to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Check host URL
    if not creds.host_url:
        errors.append("Host URL is required")
    elif not creds.host_url.startswith(("http://", "https://")):
        errors.append("Host URL must start with http:// or https://")

    # Check account ID
    if not creds.account_id:
        errors.append("Account ID is required")
    else:
        try:
            int(creds.account_id)
        except ValueError:
            errors.append("Account ID must be a number")

    # Check API token
    if not creds.api_token:
        errors.append("API Token is required")

    return len(errors) == 0, errors
