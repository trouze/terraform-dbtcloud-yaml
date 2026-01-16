"""Credential form component for entering dbt Platform account credentials."""

from typing import Callable, Optional, Union

from nicegui import ui
from nicegui.events import UploadEventArguments

from importer.web.env_manager import detect_token_type
from importer.web.state import AppState, SourceCredentials, TargetCredentials


# dbt brand colors
DBT_ORANGE = "#FF694A"


def _render_token_type_indicator(token_type: str) -> None:
    """Render a token type indicator chip.
    
    Args:
        token_type: "service_token" or "user_token"
    """
    if token_type == "user_token":
        ui.chip(
            "PAT (User Token)",
            icon="person",
            color="blue-5",
        ).props("dense outline")
    else:
        ui.chip(
            "Service Token",
            icon="settings",
            color="green-5",
        ).props("dense outline")


def create_source_credential_form(
    state: AppState,
    on_credentials_change: Optional[Callable[[SourceCredentials], None]] = None,
    on_load_env: Optional[Callable[[], None]] = None,
    on_load_env_content: Optional[Callable[[str, str], None]] = None,
    on_save_env: Optional[Callable[[], None]] = None,
) -> None:
    """Create a form for entering source dbt Platform credentials.

    Args:
        state: Application state containing current credentials
        on_credentials_change: Callback when credentials change
        on_load_env: Callback when "Load default .env" is clicked
        on_load_env_content: Callback when file is uploaded (content, filename)
        on_save_env: Callback when "Save to .env" is clicked
    """
    creds = state.source_credentials
    
    # Track upload component reference
    upload_ref = {"upload": None}
    
    async def handle_upload(e: UploadEventArguments):
        """Handle file upload."""
        if e.file and on_load_env_content:
            content = await e.file.text()
            on_load_env_content(content, e.file.name)
            # Reset the upload component
            if upload_ref["upload"]:
                upload_ref["upload"].reset()

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between mb-4"):
            ui.label("Source Account Credentials").classes("text-lg font-semibold")
            
            # .env buttons with dropdown menu for load options
            with ui.row().classes("gap-2"):
                with ui.button_group().props("outline"):
                    ui.button(
                        "Load .env",
                        icon="upload_file",
                        on_click=on_load_env,
                    ).props("size=sm").tooltip("Load from default .env location")
                    
                    with ui.button(icon="arrow_drop_down").props("size=sm dropdown-icon=none"):
                        with ui.menu().classes("min-w-[200px]"):
                            ui.menu_item(
                                "Load default .env",
                                on_click=on_load_env,
                            )
                            ui.separator()
                            # Tip for hidden files
                            ui.label("Tip: Press ⌘+Shift+. to show hidden files").classes(
                                "text-xs text-slate-500 px-4 py-1"
                            )
                            # Upload component for browsing files
                            upload = ui.upload(
                                label="Browse for .env file...",
                                on_upload=handle_upload,
                                auto_upload=True,
                                max_files=1,
                            ).props("accept=* flat").classes("w-full")
                            upload_ref["upload"] = upload
                
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

        # Track token type indicator reference for updates
        token_type_indicator = {"container": None}
        
        def update_token_type_display():
            """Update the token type indicator based on current token."""
            detected = detect_token_type(creds.api_token)
            creds.token_type = detected
            if token_type_indicator["container"]:
                token_type_indicator["container"].clear()
                with token_type_indicator["container"]:
                    _render_token_type_indicator(detected)
        
        # API Token field with show/hide toggle
        with ui.row().classes("w-full items-end gap-2 mt-4"):
            token_input = ui.input(
                label="API Token",
                value=creds.api_token,
                placeholder="dbtc_••••••••••••••••",
                password=True,
                password_toggle_button=True,
            ).classes("flex-grow").props('outlined')
            
            def on_token_change(e):
                _update_token(creds, e.args, on_credentials_change)
                update_token_type_display()
            
            token_input.on('update:model-value', on_token_change)

        # Token type indicator (read-only, auto-detected from prefix)
        with ui.row().classes("w-full mt-4 items-center gap-2"):
            ui.label("Token Type:").classes("text-sm text-slate-600")
            token_type_indicator["container"] = ui.row().classes("items-center gap-1")
            with token_type_indicator["container"]:
                _render_token_type_indicator(creds.token_type)

        # Help text
        with ui.row().classes("w-full mt-4 items-center gap-2"):
            ui.icon("info", size="xs").classes("text-slate-500")
            ui.label(
                "Token type auto-detected: dbtc_* = Service Token, dbtu_* = PAT"
            ).classes("text-xs text-slate-500")


def create_target_credential_form(
    state: AppState,
    on_credentials_change: Optional[Callable[[TargetCredentials], None]] = None,
    on_load_env: Optional[Callable[[], None]] = None,
    on_load_env_content: Optional[Callable[[str, str], None]] = None,
    on_save_env: Optional[Callable[[], None]] = None,
) -> None:
    """Create a form for entering target dbt Platform credentials.

    Args:
        state: Application state containing current credentials
        on_credentials_change: Callback when credentials change
        on_load_env: Callback when "Load default .env" is clicked
        on_load_env_content: Callback when file is uploaded (content, filename)
        on_save_env: Callback when "Save to .env" is clicked
    """
    creds = state.target_credentials
    
    # Track upload component reference
    upload_ref = {"upload": None}
    
    async def handle_upload(e: UploadEventArguments):
        """Handle file upload."""
        if e.file and on_load_env_content:
            content = await e.file.text()  # async read
            on_load_env_content(content, e.file.name)
            # Reset the upload component
            if upload_ref["upload"]:
                upload_ref["upload"].reset()

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between mb-4"):
            ui.label("Target Account Credentials").classes("text-lg font-semibold")
            
            # .env buttons with dropdown menu for load options
            with ui.row().classes("gap-2"):
                with ui.button_group().props("outline"):
                    ui.button(
                        "Load .env",
                        icon="upload_file",
                        on_click=on_load_env,
                    ).props("size=sm").tooltip("Load from default .env location")
                    
                    with ui.button(icon="arrow_drop_down").props("size=sm dropdown-icon=none"):
                        with ui.menu().classes("min-w-[200px]"):
                            ui.menu_item(
                                "Load default .env",
                                on_click=on_load_env,
                            )
                            ui.separator()
                            # Tip for hidden files
                            ui.label("Tip: Press ⌘+Shift+. to show hidden files").classes(
                                "text-xs text-slate-500 px-4 py-1"
                            )
                            # Upload component for browsing files
                            upload = ui.upload(
                                label="Browse for .env file...",
                                on_upload=handle_upload,
                                auto_upload=True,
                                max_files=1,
                            ).props("accept=* flat").classes("w-full")
                            upload_ref["upload"] = upload
                
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

        # Track token type indicator reference for updates
        token_type_indicator = {"container": None}
        
        def update_token_type_display():
            """Update the token type indicator based on current token."""
            detected = detect_token_type(creds.api_token)
            creds.token_type = detected
            if token_type_indicator["container"]:
                token_type_indicator["container"].clear()
                with token_type_indicator["container"]:
                    _render_token_type_indicator(detected)
        
        # API Token field with show/hide toggle
        with ui.row().classes("w-full items-end gap-2 mt-4"):
            token_input = ui.input(
                label="API Token",
                value=creds.api_token,
                placeholder="dbtc_••••••••••••••••",
                password=True,
                password_toggle_button=True,
            ).classes("flex-grow").props('outlined')
            
            def on_token_change(e):
                _update_target_token(creds, e.args, on_credentials_change)
                update_token_type_display()
            
            token_input.on('update:model-value', on_token_change)

        # Token type indicator (read-only, auto-detected from prefix)
        with ui.row().classes("w-full mt-4 items-center gap-2"):
            ui.label("Token Type:").classes("text-sm text-slate-600")
            token_type_indicator["container"] = ui.row().classes("items-center gap-1")
            with token_type_indicator["container"]:
                _render_token_type_indicator(creds.token_type)

        # Help text
        with ui.row().classes("w-full mt-4 items-center gap-2"):
            ui.icon("info", size="xs").classes("text-slate-500")
            ui.label(
                "Token type auto-detected: dbtc_* = Service Token, dbtu_* = PAT"
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
