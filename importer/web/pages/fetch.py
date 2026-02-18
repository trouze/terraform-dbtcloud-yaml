"""Fetch step page for configuring source/target credentials and fetching account data."""

import asyncio
import json
import threading
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, FetchMode
from importer.web.components.credential_form import (
    create_source_credential_form,
    create_target_credential_form,
    validate_credentials,
)
from importer.web.components.terminal_output import (
    CombinedProgressHandler,
    TerminalOutput,
)
from importer.web.components.progress_tree import ProgressTree
from importer.web.env_manager import (
    load_source_credentials,
    load_source_credentials_from_content,
    save_source_credentials,
    load_target_credentials,
    load_target_credentials_from_content,
    save_target_credentials,
    load_account_info_from_env,
    fetch_account_name,
    resolve_project_env_path,
    auto_seed_project_env,
)
from importer.element_ids import apply_element_ids


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"  # Color for target mode


def create_fetch_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the fetch step page content.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to persist state
    """
    # Terminal output for progress logs
    terminal = TerminalOutput(show_timestamps=True)
    
    # Progress tree for structured hierarchy
    progress_tree = ProgressTree()
    
    # State for tracking fetch progress (used by current mode)
    fetch_in_progress = {"value": False}
    cancel_event = {"event": None}  # Will hold threading.Event during fetch
    
    # Determine current mode
    is_target_mode = state.active_fetch_mode == FetchMode.TARGET
    current_fetch_state = state.target_fetch if is_target_mode else state.fetch
    fetch_complete = {"value": current_fetch_state.fetch_complete}
    
    # Mode colors
    mode_color = DBT_TEAL if is_target_mode else DBT_ORANGE
    
    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-4"):
        # Page header with mode toggle
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-4"):
                ui.icon("cloud_download", size="2rem").style(f"color: {mode_color};")
                header_text = "Fetch Target Account" if is_target_mode else "Fetch Source Account"
                ui.label(header_text).classes("text-2xl font-bold")
            
            # Mode toggle tabs
            with ui.row().classes("gap-2"):
                source_btn = ui.button(
                    "Source",
                    icon="upload",
                    on_click=lambda: _switch_fetch_mode(state, FetchMode.SOURCE, save_state),
                ).props("flat" if is_target_mode else "").style(
                    f"background-color: {DBT_ORANGE};" if not is_target_mode else ""
                )
                if state.fetch.fetch_complete:
                    source_btn.props("icon-right=check_circle")
                
                target_btn = ui.button(
                    "Target",
                    icon="download",
                    on_click=lambda: _switch_fetch_mode(state, FetchMode.TARGET, save_state),
                ).props("flat" if not is_target_mode else "").style(
                    f"background-color: {DBT_TEAL};" if is_target_mode else ""
                )
                if state.target_fetch.fetch_complete:
                    target_btn.props("icon-right=check_circle")

        # Mode description
        if is_target_mode:
            ui.label(
                "Fetch existing resources from your TARGET dbt Platform account for matching with source resources."
            ).classes("text-slate-600 dark:text-slate-400")
            
            # Target mode info banner
            with ui.card().classes("w-full p-3 border-l-4").style(f"border-color: {DBT_TEAL};"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("info", size="sm").style(f"color: {DBT_TEAL};")
                    ui.label(
                        "Target fetch is used to identify existing resources that can be imported into Terraform state "
                        "instead of being created as duplicates."
                    ).classes("text-sm")
        else:
            ui.label(
                "Configure your source dbt Platform account credentials and fetch the account data."
            ).classes("text-slate-600 dark:text-slate-400")

        # Vertical layout: Credentials, Options, Actions, then Logs
        
        # 1. Credential form (full width card)
        if is_target_mode:
            create_target_credential_form(
                state=state,
                on_credentials_change=lambda creds: _on_credentials_change(state, save_state),
                on_load_env=lambda: _load_target_env_credentials(state, terminal, save_state),
                on_load_env_content=lambda content, filename: _load_target_env_from_upload(
                    content, filename, state, terminal, save_state
                ),
                on_save_env=lambda: _save_target_env_credentials(state, terminal),
            )
        else:
            create_source_credential_form(
                state=state,
                on_credentials_change=lambda creds: _on_credentials_change(state, save_state),
                on_load_env=lambda: _load_env_credentials(state, terminal, save_state),
                on_load_env_content=lambda content, filename: _load_env_from_upload(
                    content, filename, state, terminal, save_state
                ),
                on_save_env=lambda: _save_env_credentials(state, terminal),
            )

        # 2. Fetch Options (compact card)
        _create_fetch_options(state, save_state, is_target_mode)

        # 3. Actions + Progress card
        with ui.card().classes("w-full p-4"):
            # Actions row at top
            with ui.row().classes("w-full items-center justify-between mb-3"):
                ui.label("Actions").classes("font-semibold")
                
                # Test connection button
                ui.button(
                    "Test Connection",
                    icon="network_check",
                    on_click=lambda: _test_connection(state, terminal, is_target_mode),
                ).props("outline size=sm")

            # Fetch button row - create container first, add button after results_container exists
            fetch_btn_container = ui.row().classes("w-full mb-4")
            
            # Progress section (compact two-column layout)
            ui.separator().classes("my-2")
            ui.label("Progress").classes("font-semibold mb-2")
            progress_tree.create(compact=True)

            # Results section (file paths + continue button)
            results_container = ui.column().classes("w-full")
            _create_results_section(state, on_step_change, is_target_mode, results_container)

        # Add the fetch button now that results_container exists
        with fetch_btn_container:
            with ui.row().classes("w-full gap-2"):
                fetch_label = "Fetch Target Account Data" if is_target_mode else "Fetch Account Data"
                fetch_btn = ui.button(
                    fetch_label,
                    icon="cloud_download",
                    on_click=lambda: _run_fetch(
                        state,
                        terminal,
                        progress_tree,
                        fetch_btn,
                        cancel_btn,
                        fetch_in_progress,
                        fetch_complete,
                        cancel_event,
                        on_step_change,
                        save_state,
                        results_container,
                        is_target_mode,
                    ),
                ).classes("flex-grow").style(f"background-color: {mode_color};")

                cancel_btn = ui.button(
                    "Cancel",
                    icon="cancel",
                    on_click=lambda: _cancel_fetch(cancel_event, terminal),
                ).props("outline color=negative").classes("hidden")

        # 4. Terminal output (full width)
        terminal.create(height="500px")


def _switch_fetch_mode(
    state: AppState,
    mode: FetchMode,
    save_state: Callable[[], None],
) -> None:
    """Switch between source and target fetch modes."""
    if state.active_fetch_mode != mode:
        state.active_fetch_mode = mode
        save_state()
        ui.navigate.reload()


def _create_fetch_options(
    state: AppState,
    save_state: Callable[[], None],
    is_target_mode: bool = False,
) -> None:
    """Create compact fetch options card."""
    # Get the appropriate fetch state
    fetch_state = state.target_fetch if is_target_mode else state.fetch
    default_dir = "dev_support/samples/target" if is_target_mode else "dev_support/samples"
    
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center gap-4"):
            ui.label("Fetch Options").classes("font-semibold")
            
            # Output directory (inline)
            ui.input(
                label="Output Directory",
                value=fetch_state.output_dir,
                placeholder=default_dir,
            ).classes("flex-grow").props('outlined dense').on(
                'update:model-value',
                lambda e: _update_output_dir(state, e.args, save_state, is_target_mode)
            )

            # Auto-timestamp toggle (inline)
            ui.switch(
                "Auto-timestamp",
                value=fetch_state.auto_timestamp,
                on_change=lambda e: _update_auto_timestamp(state, e.value, save_state, is_target_mode),
            )

            # Advanced options button
            with ui.expansion("Advanced", icon="settings", value=False).classes("w-auto"):
                with ui.column().classes("gap-2 p-2"):
                    def _update_threads(e):
                        val = e.args if e.args is not None else 50
                        if is_target_mode:
                            state.target_fetch.threads = int(val) if val else 50
                        else:
                            state.fetch.threads = int(val) if val else 50
                        save_state()
                    
                    ui.number(
                        label="Threads",
                        value=getattr(fetch_state, 'threads', 50) or 50,
                        min=1,
                        max=100,
                    ).props('outlined dense').tooltip(
                        "Number of parallel threads for fetching data (1-100)"
                    ).on("update:model-value", _update_threads)
                    
                    ui.number(
                        label="API Timeout (seconds)",
                        value=90,
                        min=10,
                        max=300,
                    ).props('outlined dense')

                    ui.number(
                        label="Max Retries",
                        value=5,
                        min=1,
                        max=10,
                    ).props('outlined dense')

                    ui.switch(
                        "Verify SSL",
                        value=True,
                    )


def _create_results_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    is_target_mode: bool,
    container: ui.column,
) -> None:
    """Create the results section showing file paths and continue button when fetch is complete."""
    # Get the appropriate fetch state
    fetch_state = state.target_fetch if is_target_mode else state.fetch
    mode_color = DBT_TEAL if is_target_mode else DBT_ORANGE
    
    with container:
        if fetch_state.fetch_complete:
            ui.separator().classes("my-3")
            with ui.row().classes("w-full items-center justify-between"):
                # File paths on the left
                with ui.column().classes("gap-0 text-xs text-slate-500 font-mono"):
                    if fetch_state.last_fetch_file:
                        ui.label(f"Data: {fetch_state.last_fetch_file}")
                    if fetch_state.last_summary_file:
                        ui.label(f"Summary: {fetch_state.last_summary_file}")
                
                # Continue button (full width, same style as fetch button)
                if is_target_mode:
                    ui.button(
                        "Map Resources",
                        icon="arrow_forward",
                        on_click=lambda: on_step_change(WorkflowStep.MAP),
                    ).classes("w-full").style(f"background-color: {mode_color};")
                else:
                    ui.button(
                        "Explore",
                        icon="arrow_forward",
                        on_click=lambda: on_step_change(WorkflowStep.EXPLORE),
                    ).classes("w-full").style(f"background-color: {mode_color};")


def _on_credentials_change(state: AppState, save_state: Callable[[], None]) -> None:
    """Handle credentials change."""
    save_state()


def _update_output_dir(
    state: AppState,
    value: str,
    save_state: Callable[[], None],
    is_target_mode: bool = False,
) -> None:
    """Update output directory in state."""
    default = "dev_support/samples/target" if is_target_mode else "dev_support/samples"
    if is_target_mode:
        state.target_fetch.output_dir = value if value else default
    else:
        state.fetch.output_dir = value if value else default
    save_state()


def _update_auto_timestamp(
    state: AppState,
    value: bool,
    save_state: Callable[[], None],
    is_target_mode: bool = False,
) -> None:
    """Update auto-timestamp setting."""
    if is_target_mode:
        state.target_fetch.auto_timestamp = value
    else:
        state.fetch.auto_timestamp = value
    save_state()


def _load_env_credentials(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
) -> None:
    """Load credentials from default .env file."""
    terminal.info("Loading credentials from default .env file...")
    
    try:
        env_path = resolve_project_env_path(state.project_path, "source")
        if env_path and not Path(env_path).exists():
            auto_seed_project_env(state.project_path, "source")
        creds = load_source_credentials(env_path=env_path)
        
        if not creds.get("account_id") and not creds.get("api_token"):
            terminal.warning("No source credentials found in .env file")
            ui.notify("No credentials found in .env", type="warning")
            return

        # Update state
        state.source_credentials.host_url = creds.get("host_url", "https://cloud.getdbt.com")
        state.source_credentials.account_id = creds.get("account_id", "")
        state.source_credentials.api_token = creds.get("api_token", "")
        state.source_credentials.token_type = creds.get("token_type", "service_token")
        
        # Also update account info
        state.source_account = load_account_info_from_env("source", env_path=env_path)
        
        # Clear previous fetch results since credentials changed
        state.fetch.fetch_complete = False
        
        save_state()
        
        terminal.success("Credentials loaded from .env")
        ui.notify("Credentials loaded", type="positive")
        
        # Reload page to show new values
        ui.navigate.reload()

    except Exception as e:
        terminal.error(f"Failed to load credentials: {e}")
        ui.notify(f"Failed to load: {e}", type="negative")


def _load_env_from_upload(
    content: str,
    filename: str,
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
) -> None:
    """Load credentials from uploaded .env file content."""
    terminal.info(f"Loading credentials from uploaded file: {filename}")
    
    try:
        creds = load_source_credentials_from_content(content)
        
        if not creds.get("account_id") and not creds.get("api_token"):
            terminal.warning(f"No source credentials found in {filename}")
            ui.notify("No credentials found in uploaded file", type="warning")
            return

        # Update state
        state.source_credentials.host_url = creds.get("host_url", "https://cloud.getdbt.com")
        state.source_credentials.account_id = creds.get("account_id", "")
        state.source_credentials.api_token = creds.get("api_token", "")
        state.source_credentials.token_type = creds.get("token_type", "service_token")
        
        # Try to fetch account name to update account info
        if creds.get("account_id") and creds.get("api_token"):
            success, result = fetch_account_name(
                creds["host_url"],
                creds["account_id"],
                creds["api_token"],
            )
            if success:
                state.source_account.account_name = result
                state.source_account.is_verified = True
            state.source_account.account_id = creds["account_id"]
            state.source_account.host_url = creds["host_url"]
            state.source_account.is_configured = True
        
        # Clear previous fetch results since credentials changed
        state.fetch.fetch_complete = False
        
        save_state()
        
        terminal.success(f"Credentials loaded from {filename}")
        ui.notify(f"Credentials loaded from {filename}", type="positive")
        
        # Reload page to show new values
        ui.navigate.reload()

    except Exception as e:
        terminal.error(f"Failed to load credentials from {filename}: {e}")
        ui.notify(f"Failed to load: {e}", type="negative")


def _save_env_credentials(state: AppState, terminal: TerminalOutput) -> None:
    """Save credentials to .env file."""
    creds = state.source_credentials
    
    if not creds.account_id or not creds.api_token:
        terminal.warning("Cannot save: Account ID and API Token are required")
        ui.notify("Fill in credentials first", type="warning")
        return

    terminal.info("Saving credentials to .env file...")
    
    try:
        env_path = resolve_project_env_path(state.project_path, "source")
        path = save_source_credentials(
            host_url=creds.host_url,
            account_id=creds.account_id,
            api_token=creds.api_token,
            env_path=env_path,
        )
        terminal.success(f"Credentials saved to {path}")
        ui.notify("Credentials saved", type="positive")

    except Exception as e:
        terminal.error(f"Failed to save credentials: {e}")
        ui.notify(f"Failed to save: {e}", type="negative")


# Target credential helpers

def _load_target_env_credentials(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
) -> None:
    """Load target credentials from default .env file."""
    terminal.info("Loading target credentials from default .env file...")
    
    try:
        env_path = resolve_project_env_path(state.project_path, "target")
        if env_path and not Path(env_path).exists():
            auto_seed_project_env(state.project_path, "target")
        creds = load_target_credentials(env_path=env_path)
        
        if not creds.get("account_id") and not creds.get("api_token"):
            terminal.warning("No target credentials found in .env file")
            ui.notify("No target credentials found in .env", type="warning")
            return

        # Update state
        state.target_credentials.host_url = creds.get("host_url", "https://cloud.getdbt.com")
        state.target_credentials.account_id = creds.get("account_id", "")
        state.target_credentials.api_token = creds.get("api_token", "")
        state.target_credentials.token_type = creds.get("token_type", "service_token")
        
        # Also update target account info
        state.target_account = load_account_info_from_env("target", env_path=env_path)
        
        # Clear previous fetch results since credentials changed
        state.target_fetch.fetch_complete = False
        
        save_state()
        
        terminal.success("Target credentials loaded from .env")
        ui.notify("Target credentials loaded", type="positive")
        
        # Reload page to show new values
        ui.navigate.reload()

    except Exception as e:
        terminal.error(f"Failed to load target credentials: {e}")
        ui.notify(f"Failed to load: {e}", type="negative")


def _load_target_env_from_upload(
    content: str,
    filename: str,
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
) -> None:
    """Load target credentials from uploaded .env file content."""
    terminal.info(f"Loading target credentials from uploaded file: {filename}")
    
    try:
        creds = load_target_credentials_from_content(content)
        
        if not creds.get("account_id") and not creds.get("api_token"):
            terminal.warning(f"No target credentials found in {filename}")
            ui.notify("No target credentials found in uploaded file", type="warning")
            return

        # Update state
        state.target_credentials.host_url = creds.get("host_url", "https://cloud.getdbt.com")
        state.target_credentials.account_id = creds.get("account_id", "")
        state.target_credentials.api_token = creds.get("api_token", "")
        state.target_credentials.token_type = creds.get("token_type", "service_token")
        
        # Try to fetch account name to update account info
        if creds.get("account_id") and creds.get("api_token"):
            success, result = fetch_account_name(
                creds["host_url"],
                creds["account_id"],
                creds["api_token"],
            )
            if success:
                state.target_account.account_name = result
                state.target_account.is_verified = True
            state.target_account.account_id = creds["account_id"]
            state.target_account.host_url = creds["host_url"]
            state.target_account.is_configured = True
        
        # Clear previous fetch results since credentials changed
        state.target_fetch.fetch_complete = False
        
        save_state()
        
        terminal.success(f"Target credentials loaded from {filename}")
        ui.notify(f"Target credentials loaded from {filename}", type="positive")
        
        # Reload page to show new values
        ui.navigate.reload()

    except Exception as e:
        terminal.error(f"Failed to load target credentials from {filename}: {e}")
        ui.notify(f"Failed to load: {e}", type="negative")


def _save_target_env_credentials(state: AppState, terminal: TerminalOutput) -> None:
    """Save target credentials to .env file."""
    creds = state.target_credentials
    
    if not creds.account_id or not creds.api_token:
        terminal.warning("Cannot save: Account ID and API Token are required")
        ui.notify("Fill in credentials first", type="warning")
        return

    terminal.info("Saving target credentials to .env file...")
    
    try:
        env_path = resolve_project_env_path(state.project_path, "target")
        path = save_target_credentials(
            host_url=creds.host_url,
            account_id=creds.account_id,
            api_token=creds.api_token,
            token_type=creds.token_type,
            env_path=env_path,
        )
        terminal.success(f"Target credentials saved to {path}")
        ui.notify("Target credentials saved", type="positive")

    except Exception as e:
        terminal.error(f"Failed to save target credentials: {e}")
        ui.notify(f"Failed to save: {e}", type="negative")


async def _test_connection(
    state: AppState,
    terminal: TerminalOutput,
    is_target_mode: bool = False,
) -> None:
    """Test connection to dbt Platform API."""
    creds = state.target_credentials if is_target_mode else state.source_credentials
    mode_label = "target" if is_target_mode else "source"
    
    # Validate first
    is_valid, errors = validate_credentials(creds)
    if not is_valid:
        for err in errors:
            terminal.error(err)
        ui.notify("Invalid credentials", type="negative")
        return

    terminal.info(f"Testing {mode_label} connection to {creds.host_url}...")
    
    try:
        from importer.web.env_manager import fetch_account_name
        
        success, result = await asyncio.to_thread(
            fetch_account_name,
            creds.host_url,
            creds.account_id,
            creds.api_token,
        )
        
        if success:
            terminal.success(f"✓ Connection successful! Account: {result}")
            ui.notify(f"Connected to: {result}", type="positive")
        else:
            terminal.error(f"Connection failed: {result}")
            ui.notify(f"Connection failed: {result}", type="negative")

    except Exception as e:
        terminal.error(f"Connection error: {e}")
        ui.notify(f"Error: {e}", type="negative")


def _cancel_fetch(cancel_event: dict, terminal: TerminalOutput) -> None:
    """Cancel an in-progress fetch operation."""
    if cancel_event["event"] is not None:
        cancel_event["event"].set()
        terminal.warning("Cancellation requested... Please wait.")
        ui.notify("Cancellation requested", type="warning")


async def _run_fetch(
    state: AppState,
    terminal: TerminalOutput,
    progress_tree: ProgressTree,
    fetch_btn: ui.button,
    cancel_btn: ui.button,
    fetch_in_progress: dict,
    fetch_complete: dict,
    cancel_event: dict,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
    results_container: Optional[ui.column] = None,
    is_target_mode: bool = False,
) -> None:
    """Run the fetch operation."""
    # Get appropriate credentials and fetch state based on mode
    creds = state.target_credentials if is_target_mode else state.source_credentials
    fetch_state = state.target_fetch if is_target_mode else state.fetch
    mode_label = "target" if is_target_mode else "source"
    
    # Validate credentials
    is_valid, errors = validate_credentials(creds)
    if not is_valid:
        for err in errors:
            terminal.error(err)
        ui.notify("Please fix credential errors", type="negative")
        return

    # Prevent double-fetch
    if fetch_in_progress["value"]:
        ui.notify("Fetch already in progress", type="warning")
        return

    fetch_in_progress["value"] = True
    fetch_btn.disable()
    
    # Initialize cancel event and show cancel button
    cancel_event["event"] = threading.Event()
    cancel_btn.classes(remove="hidden")
    
    # Reset fetch_complete state before starting new fetch
    fetch_state.fetch_complete = False
    
    # Reset the results panel to placeholder state (preserves layout)
    if results_container is not None:
        results_container.clear()
        # Recreate the placeholder to maintain consistent height
        _create_results_section(state, on_step_change, is_target_mode, results_container)
    
    # Start progress tracking
    terminal.clear()
    progress_tree.start()
    
    terminal.info(f"Starting {mode_label} fetch operation...")
    terminal.info(f"Host: {creds.host_url}")
    terminal.info(f"Account ID: {creds.account_id}")
    terminal.info(f"Output: {fetch_state.output_dir}")
    terminal.info("")

    # Pre-declare FetchCancelledException to avoid UnboundLocalError if import fails
    FetchCancelledException = Exception
    
    try:
        # Import fetch dependencies
        from importer.config import Settings
        from importer.client import DbtCloudClient
        from importer.fetcher import fetch_account_snapshot, FetchCancelledException
        from importer.run_tracker import RunTracker
        from importer.reporter import generate_summary_report, generate_detailed_report

        # Create settings
        settings = Settings(
            host=creds.host_url.rstrip("/"),
            account_id=int(creds.account_id),
            api_token=creds.api_token,
        )

        # Setup output directory and run tracker
        output_dir = Path(fetch_state.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        tracker_filename = "target_importer_runs.json" if is_target_mode else "importer_runs.json"
        run_tracker = RunTracker(output_dir / tracker_filename)
        run_id, timestamp = run_tracker.start_run(settings.account_id)

        terminal.info(f"Run ID: {run_id}, Timestamp: {timestamp}")
        terminal.info("")

        # Create combined progress handler that updates both terminal and tree
        progress = CombinedProgressHandler(terminal, progress_tree)

        # Run fetch in thread pool
        terminal.info("Connecting to dbt Platform API...")
        threads = getattr(fetch_state, 'threads', 50) or 50
        terminal.info(f"Using {threads} threads for parallel fetching")
        event = cancel_event["event"]
        
        import time
        fetch_start_time = time.time()
        
        def do_fetch():
            client = DbtCloudClient(settings)
            try:
                return fetch_account_snapshot(
                    client, progress=progress, threads=threads, cancel_event=event
                )
            finally:
                client.close()

        snapshot = await asyncio.to_thread(do_fetch)
        
        fetch_duration = time.time() - fetch_start_time

        terminal.info("")
        terminal.success("Fetch complete!")

        # Generate filenames
        json_filename = run_tracker.get_filename(
            settings.account_id, run_id, timestamp, "json", "json"
        )
        summary_filename = run_tracker.get_filename(
            settings.account_id, run_id, timestamp, "summary", "md"
        )
        report_filename = run_tracker.get_filename(
            settings.account_id, run_id, timestamp, "report", "md"
        )
        report_items_filename = run_tracker.get_filename(
            settings.account_id, run_id, timestamp, "report_items", "json"
        )

        # Write files
        json_path = output_dir / json_filename
        summary_path = output_dir / summary_filename
        report_path = output_dir / report_filename
        report_items_path = output_dir / report_items_filename

        terminal.info(f"Writing {json_filename}...")
        payload = snapshot.model_dump(mode="json")
        
        # Apply element IDs and generate report_items
        report_items = apply_element_ids(payload)
        
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        terminal.info(f"Writing {summary_filename}...")
        summary_path.write_text(generate_summary_report(snapshot), encoding="utf-8")

        terminal.info(f"Writing {report_filename}...")
        report_path.write_text(generate_detailed_report(snapshot), encoding="utf-8")
        
        terminal.info(f"Writing {report_items_filename}...")
        report_items_path.write_text(json.dumps(report_items, indent=2), encoding="utf-8")

        # Update state
        fetch_state.fetch_complete = True
        if is_target_mode:
            fetch_state.clear_stale()
        fetch_state.last_fetch_file = str(json_path)
        fetch_state.last_summary_file = str(summary_path)
        fetch_state.last_report_file = str(report_path)
        fetch_state.last_report_items_file = str(report_items_path)
        fetch_state.account_name = snapshot.account_name
        
        # Calculate resource counts (including credentials)
        fetch_state.resource_counts = {
            "projects": len(snapshot.projects),
            "environments": sum(len(p.environments) for p in snapshot.projects),
            "credentials": sum(
                1 for p in snapshot.projects 
                for e in p.environments 
                if e.credential is not None
            ),
            "jobs": sum(len(p.jobs) for p in snapshot.projects),
            "connections": len(snapshot.globals.connections),
            "repositories": len(snapshot.globals.repositories),
        }

        # Also update account info
        account_info = state.target_account if is_target_mode else state.source_account
        account_info.account_name = snapshot.account_name or ""
        account_info.account_id = creds.account_id
        account_info.host_url = creds.host_url
        account_info.is_configured = True
        account_info.is_verified = True
        
        # Store raw account data
        if is_target_mode:
            state.target_account_data = payload
            # Reset match-related state since target data has changed
            state.map.confirmed_mappings = []
            state.map.suggested_matches = []
            state.map.rejected_suggestions = set()
            state.map.mapping_file_valid = False
            state.map.mapping_file_path = None
            state.deploy.configure_complete = False
            state.deploy.disable_job_triggers = False
        else:
            state.account_data = payload
            # Reset downstream state since source data has changed
            state.map.confirmed_mappings = []
            state.map.suggested_matches = []
            state.map.rejected_suggestions = set()
            state.map.mapping_file_valid = False
            state.map.mapping_file_path = None
            state.map.normalize_complete = False  # Re-scope needed
            state.deploy.configure_complete = False
            state.deploy.disable_job_triggers = False

        save_state()
        fetch_complete["value"] = True

        terminal.info("")
        complete_msg = "TARGET FETCH COMPLETE" if is_target_mode else "FETCH COMPLETE"
        terminal.success(f"━━━ {complete_msg} ━━━")
        terminal.info(f"  Projects: {fetch_state.resource_counts.get('projects', 0)}")
        terminal.info(f"  Environments: {fetch_state.resource_counts.get('environments', 0)}")
        terminal.info(f"  Credentials: {fetch_state.resource_counts.get('credentials', 0)}")
        terminal.info(f"  Jobs: {fetch_state.resource_counts.get('jobs', 0)}")
        terminal.info(f"  Connections: {fetch_state.resource_counts.get('connections', 0)}")
        terminal.info(f"  Repositories: {fetch_state.resource_counts.get('repositories', 0)}")
        terminal.info(f"  Total time: {fetch_duration:.1f}s")

        # Mark progress tree as complete
        progress_tree.complete()
        
        ui.notify(f"{mode_label.title()} fetch completed successfully!", type="positive")

        # Dynamically show the results section instead of reloading
        # This preserves the terminal logs and progress tree state
        if results_container is not None:
            results_container.clear()
            _create_results_section(state, on_step_change, is_target_mode, results_container)

    except FetchCancelledException:
        terminal.warning("")
        terminal.warning("━━━ FETCH CANCELLED ━━━")
        terminal.warning("The fetch operation was cancelled by the user.")
        
        # Mark progress tree as cancelled
        progress_tree.error("Cancelled")
        
        ui.notify("Fetch cancelled", type="warning")

    except Exception as e:
        terminal.error("")
        terminal.error(f"Fetch failed: {e}")
        
        # Mark progress tree as error
        progress_tree.error(f"Failed: {type(e).__name__}")
        
        # Provide specific guidance for common errors
        error_str = str(e).lower()
        if "401" in error_str or "unauthorized" in error_str:
            terminal.warning("Hint: Check your API token - it may be invalid or expired")
        elif "404" in error_str or "not found" in error_str:
            terminal.warning("Hint: Check your Account ID - the account may not exist")
        elif "connect" in error_str or "network" in error_str:
            terminal.warning("Hint: Check your Host URL and network connection")

        ui.notify(f"Fetch failed: {e}", type="negative", timeout=10)

    finally:
        fetch_in_progress["value"] = False
        fetch_btn.enable()
        cancel_btn.classes(add="hidden")
        cancel_event["event"] = None