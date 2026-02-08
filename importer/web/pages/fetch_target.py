"""Fetch Target step page - configure target credentials and fetch target account data."""

import asyncio
import json
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from nicegui import ui

from importer.web.state import AppState, WorkflowStep
from importer.web.components.credential_form import (
    create_target_credential_form,
    validate_credentials,
)
from importer.web.components.terminal_output import (
    CombinedProgressHandler,
    TerminalOutput,
)
from importer.web.components.progress_tree import ProgressTree
from importer.web.env_manager import (
    load_target_credentials,
    load_target_credentials_from_content,
    save_target_credentials,
    load_account_info_from_env,
    fetch_account_name,
)
from importer.element_ids import apply_element_ids


# Native integration strategies that require PAT for target operations
NATIVE_INTEGRATION_STRATEGIES = {"github_app", "deploy_token", "azure_active_directory_app"}


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"  # Primary color for target pages


def _get_source_native_integration_repos(state: AppState) -> List[Tuple[str, str]]:
    """Check if source has repositories using native integrations (github_app, deploy_token, etc.).
    
    Returns:
        List of (repo_name, strategy) tuples for repos using native integrations.
    """
    if not state.fetch.last_report_items_file:
        return []
    
    try:
        report_path = Path(state.fetch.last_report_items_file)
        if not report_path.exists():
            return []
        
        report_items = json.loads(report_path.read_text(encoding="utf-8"))
        native_repos = []
        
        for item in report_items:
            if item.get("type") == "REP":
                strategy = item.get("git_clone_strategy", "")
                if strategy in NATIVE_INTEGRATION_STRATEGIES:
                    name = item.get("name") or item.get("remote_url", "Unknown")
                    native_repos.append((name, strategy))
        
        return native_repos
    except Exception:
        return []


def _has_native_integration_repos(state: AppState) -> bool:
    """Check if source has any repositories using native integrations."""
    return len(_get_source_native_integration_repos(state)) > 0


def create_fetch_target_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Fetch Target step page content.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to persist state
    """
    # Terminal output for progress logs
    terminal = TerminalOutput(show_timestamps=True)
    
    # Progress tree for structured hierarchy
    progress_tree = ProgressTree()
    
    # State for tracking fetch progress
    fetch_in_progress = {"value": False}
    cancel_event = {"event": None}  # Will hold threading.Event during fetch
    fetch_complete = {"value": state.target_fetch.fetch_complete}
    
    # Check for native integration repositories in source
    native_repos = _get_source_native_integration_repos(state)
    has_native_integrations = len(native_repos) > 0
    
    # Auto-set token type to user_token (PAT) if native integrations detected
    # and user hasn't explicitly set credentials yet
    if has_native_integrations and state.target_credentials.token_type == "service_token":
        if not state.target_credentials.api_token:  # Only auto-switch if no token set yet
            state.target_credentials.token_type = "user_token"
            save_state()
    
    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-4"):
        # Page header
        with ui.row().classes("w-full items-center gap-4"):
            ui.icon("cloud_download", size="2rem").style(f"color: {DBT_TEAL};")
            ui.label("Fetch Target Account").classes("text-2xl font-bold")

        ui.label(
            "Configure your target dbt Platform account credentials and fetch the existing infrastructure data."
        ).classes("text-slate-600 dark:text-slate-400")
        
        # Warning banner if source has native integration repositories
        if has_native_integrations:
            strategy_names = {
                "github_app": "GitHub App",
                "deploy_token": "GitLab Deploy Token",
                "azure_active_directory_app": "Azure AD App",
            }
            repo_details = ", ".join([
                f"{name} ({strategy_names.get(strategy, strategy)})"
                for name, strategy in native_repos[:3]  # Show first 3
            ])
            if len(native_repos) > 3:
                repo_details += f" and {len(native_repos) - 3} more"
            
            with ui.card().classes("w-full p-3 border-l-4 border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20"):
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("warning", size="sm").classes("text-yellow-600")
                        ui.label("PAT Required for Native Git Integration").classes("font-semibold text-yellow-800 dark:text-yellow-200")
                    ui.label(
                        f"Source contains repositories using native integrations: {repo_details}. "
                        "A Personal Access Token (PAT) is required to discover GitHub/GitLab/Azure integration IDs "
                        "in the target account. Service tokens cannot access the integrations API."
                    ).classes("text-sm text-yellow-700 dark:text-yellow-300")
                    ui.label(
                        "Use a User Token (PAT) below, or repositories will fall back to deploy key authentication."
                    ).classes("text-xs text-yellow-600 dark:text-yellow-400 italic")
        
        # Info banner explaining target fetch purpose
        with ui.card().classes("w-full p-3 border-l-4").style(f"border-color: {DBT_TEAL};"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("info", size="sm").style(f"color: {DBT_TEAL};")
                ui.label(
                    "Target fetch retrieves existing resources from your target account. "
                    "This enables matching source resources to existing targets for import into Terraform state."
                ).classes("text-sm")

        # Vertical layout: Credentials, Options, Actions, then Logs
        
        # 1. Target credential form (full width card)
        create_target_credential_form(
            state=state,
            on_credentials_change=lambda creds: _on_credentials_change(state, save_state),
            on_load_env=lambda: _load_env_credentials(state, terminal, save_state),
            on_load_env_content=lambda content, filename: _load_env_from_upload(
                content, filename, state, terminal, save_state
            ),
            on_save_env=lambda: _save_env_credentials(state, terminal),
        )

        # 2. Fetch Options (compact card)
        _create_fetch_options(state, save_state)

        # 3. Actions + Progress card
        with ui.card().classes("w-full p-4"):
            # Actions row at top
            with ui.row().classes("w-full items-center justify-between mb-3"):
                ui.label("Actions").classes("font-semibold")
                
                # Test connection button
                ui.button(
                    "Test Connection",
                    icon="network_check",
                    on_click=lambda: _test_connection(state, terminal),
                ).props("outline size=sm")

            # Fetch button row - create container first, add button after results_container exists
            fetch_btn_container = ui.row().classes("w-full mb-4")
            
            # Progress section (compact two-column layout)
            ui.separator().classes("my-2")
            ui.label("Progress").classes("font-semibold mb-2")
            progress_tree.create(compact=True)

            # Results section (file paths + continue button)
            results_container = ui.column().classes("w-full")
            _create_results_section(state, on_step_change, results_container)

        # Add the fetch button now that results_container exists
        with fetch_btn_container:
            with ui.row().classes("w-full gap-2"):
                fetch_btn = ui.button(
                    "Fetch Target Account Data",
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
                    ),
                ).classes("flex-grow").style(f"background-color: {DBT_TEAL};")

                cancel_btn = ui.button(
                    "Cancel",
                    icon="cancel",
                    on_click=lambda: _cancel_fetch(cancel_event, terminal),
                ).props("outline color=negative").classes("hidden")

        # 4. Terminal output (full width)
        terminal.create(height="500px")


def _create_fetch_options(
    state: AppState,
    save_state: Callable[[], None],
) -> None:
    """Create compact fetch options card."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center gap-4"):
            ui.label("Fetch Options").classes("font-semibold")
            
            # Output directory (inline)
            ui.input(
                label="Output Directory",
                value=state.target_fetch.output_dir,
                placeholder="dev_support/samples/target",
            ).classes("flex-grow").props('outlined dense').on(
                'update:model-value',
                lambda e: _update_output_dir(state, e.args, save_state)
            )

            # Auto-timestamp toggle (inline)
            ui.switch(
                "Auto-timestamp",
                value=state.target_fetch.auto_timestamp,
                on_change=lambda e: _update_auto_timestamp(state, e.value, save_state),
            )

            # Advanced options button
            with ui.expansion("Advanced", icon="settings", value=False).classes("w-auto"):
                with ui.column().classes("gap-2 p-2"):
                    def _update_threads(e):
                        val = e.args if e.args is not None else 50
                        state.target_fetch.threads = int(val) if val else 50
                        save_state()
                    
                    ui.number(
                        label="Threads",
                        value=getattr(state.target_fetch, 'threads', 25) or 25,
                        min=1,
                        max=50,
                    ).props('outlined dense').tooltip(
                        "Number of parallel threads for fetching data (1-50)"
                    ).on("update:model-value", _update_threads)
                    
                    ui.number(
                        label="API Timeout (seconds)",
                        value=90,
                        min=10,
                        max=300,
                    ).props('outlined dense')

                    ui.number(
                        label="Max Retries",
                        value=3,
                        min=0,
                        max=10,
                    ).props('outlined dense')


def _create_results_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    container: ui.column,
) -> None:
    """Create the results section showing file paths and continue button when fetch is complete."""
    with container:
        if state.target_fetch.fetch_complete:
            ui.separator().classes("my-3")
            with ui.row().classes("w-full items-center justify-between"):
                # File paths on the left
                with ui.column().classes("gap-0 text-xs text-slate-500 font-mono"):
                    if state.target_fetch.last_fetch_file:
                        ui.label(f"Data: {state.target_fetch.last_fetch_file}")
                    if state.target_fetch.last_summary_file:
                        ui.label(f"Summary: {state.target_fetch.last_summary_file}")
                
                # Continue button (full width, same style as fetch button)
                ui.button(
                    "Explore Target",
                    icon="arrow_forward",
                    on_click=lambda: on_step_change(WorkflowStep.EXPLORE_TARGET),
                ).classes("w-full").style(f"background-color: {DBT_TEAL};")


def _on_credentials_change(state: AppState, save_state: Callable[[], None]) -> None:
    """Handle credentials change."""
    save_state()


def _update_output_dir(
    state: AppState,
    value: str,
    save_state: Callable[[], None],
) -> None:
    """Update output directory in state."""
    state.target_fetch.output_dir = value if value else "dev_support/samples/target"
    save_state()


def _update_auto_timestamp(
    state: AppState,
    value: bool,
    save_state: Callable[[], None],
) -> None:
    """Update auto-timestamp setting."""
    state.target_fetch.auto_timestamp = value
    save_state()


def _load_env_credentials(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
) -> None:
    """Load target credentials from default .env file."""
    
    # Check if there's existing fetch data
    has_existing_fetch = (
        state.target_fetch.fetch_complete and 
        state.target_fetch.last_fetch_file
    )
    
    if has_existing_fetch:
        # Show confirmation dialog
        _show_load_credentials_dialog(
            state=state,
            terminal=terminal,
            save_state=save_state,
            fetch_type="target",
            load_func=lambda reset: _do_load_env_credentials(state, terminal, save_state, reset),
        )
    else:
        # No existing fetch, just load directly
        _do_load_env_credentials(state, terminal, save_state, reset_fetch=True)


def _do_load_env_credentials(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    reset_fetch: bool = True,
) -> None:
    """Actually load target credentials from default .env file."""
    terminal.info("Loading target credentials from default .env file...")
    
    try:
        creds = load_target_credentials()
        
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
        state.target_account = load_account_info_from_env("target")
        
        # Optionally clear previous fetch results
        if reset_fetch:
            state.target_fetch.fetch_complete = False
            terminal.info("Previous fetch data cleared - ready for fresh fetch")
        else:
            terminal.info("Keeping existing fetch data")
        
        save_state()
        
        terminal.success("Target credentials loaded from .env")
        ui.notify("Target credentials loaded", type="positive")
        
        # Reload page to show new values
        ui.navigate.reload()

    except Exception as e:
        terminal.error(f"Failed to load target credentials: {e}")
        ui.notify(f"Failed to load: {e}", type="negative")


def _show_load_credentials_dialog(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    fetch_type: str,
    load_func: Callable[[bool], None],
) -> None:
    """Show a dialog asking whether to keep or reset existing fetch data."""
    fetch_state = state.target_fetch if fetch_type == "target" else state.fetch
    
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-md"):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("warning", size="md").classes("text-amber-500")
            ui.label("Existing Fetch Data Detected").classes("text-lg font-semibold")
        
        ui.label(
            f"You have existing {fetch_type} fetch data. What would you like to do?"
        ).classes("text-sm mb-4")
        
        # Show existing data info
        with ui.card().classes("w-full p-3 bg-slate-100 dark:bg-slate-800 mb-4"):
            if fetch_state.last_fetch_file:
                ui.label(f"Data file: {fetch_state.last_fetch_file}").classes("text-xs text-slate-600 dark:text-slate-400")
            if fetch_state.account_name:
                ui.label(f"Account: {fetch_state.account_name}").classes("text-xs text-slate-600 dark:text-slate-400")
        
        with ui.row().classes("w-full justify-end gap-2"):
            def on_keep():
                dialog.close()
                load_func(False)  # Don't reset fetch
            
            def on_reset():
                dialog.close()
                load_func(True)  # Reset fetch
            
            ui.button(
                "Keep Existing Data",
                on_click=on_keep,
                color="primary",
            ).props("outline")
            
            ui.button(
                "Reset for Fresh Fetch",
                on_click=on_reset,
                color="warning",
            )
        
        ui.button(icon="close", on_click=dialog.close).props(
            "flat round dense"
        ).classes("absolute top-2 right-2")
    
    dialog.open()


def _load_env_from_upload(
    content: str,
    filename: str,
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
) -> None:
    """Load target credentials from uploaded .env file content."""
    
    # Check if there's existing fetch data
    has_existing_fetch = (
        state.target_fetch.fetch_complete and 
        state.target_fetch.last_fetch_file
    )
    
    if has_existing_fetch:
        # Show confirmation dialog
        _show_load_credentials_dialog(
            state=state,
            terminal=terminal,
            save_state=save_state,
            fetch_type="target",
            load_func=lambda reset: _do_load_env_from_upload(
                content, filename, state, terminal, save_state, reset
            ),
        )
    else:
        # No existing fetch, just load directly
        _do_load_env_from_upload(content, filename, state, terminal, save_state, reset_fetch=True)


def _do_load_env_from_upload(
    content: str,
    filename: str,
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    reset_fetch: bool = True,
) -> None:
    """Actually load target credentials from uploaded .env file content."""
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
        
        # Optionally clear previous fetch results
        if reset_fetch:
            state.target_fetch.fetch_complete = False
            terminal.info("Previous fetch data cleared - ready for fresh fetch")
        else:
            terminal.info("Keeping existing fetch data")
        
        save_state()
        
        terminal.success(f"Target credentials loaded from {filename}")
        ui.notify(f"Target credentials loaded from {filename}", type="positive")
        
        # Reload page to show new values
        ui.navigate.reload()

    except Exception as e:
        terminal.error(f"Failed to load target credentials from {filename}: {e}")
        ui.notify(f"Failed to load: {e}", type="negative")


def _save_env_credentials(state: AppState, terminal: TerminalOutput) -> None:
    """Save target credentials to .env file."""
    creds = state.target_credentials
    
    if not creds.account_id or not creds.api_token:
        terminal.warning("Cannot save: Account ID and API Token are required")
        ui.notify("Fill in credentials first", type="warning")
        return

    terminal.info("Saving target credentials to .env file...")
    
    try:
        path = save_target_credentials(
            host_url=creds.host_url,
            account_id=creds.account_id,
            api_token=creds.api_token,
            token_type=creds.token_type,
        )
        terminal.success(f"Target credentials saved to {path}")
        ui.notify("Target credentials saved", type="positive")

    except Exception as e:
        terminal.error(f"Failed to save target credentials: {e}")
        ui.notify(f"Failed to save: {e}", type="negative")


async def _test_connection(
    state: AppState,
    terminal: TerminalOutput,
) -> None:
    """Test connection to target dbt Platform API."""
    creds = state.target_credentials
    
    # Validate first
    is_valid, errors = validate_credentials(creds)
    if not is_valid:
        for err in errors:
            terminal.error(err)
        ui.notify("Invalid credentials", type="negative")
        return

    terminal.info(f"Testing target connection to {creds.host_url}...")
    
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
) -> None:
    """Run the target fetch operation."""
    creds = state.target_credentials
    fetch_state = state.target_fetch
    
    # Validate credentials
    is_valid, errors = validate_credentials(creds)
    if not is_valid:
        for err in errors:
            terminal.error(err)
        ui.notify("Please fix credential errors", type="negative")
        return
    
    # Check for native integration repos and warn if using service token
    native_repos = _get_source_native_integration_repos(state)
    if native_repos and creds.token_type == "service_token":
        strategy_names = {
            "github_app": "GitHub App",
            "deploy_token": "GitLab Deploy Token",
            "azure_active_directory_app": "Azure AD App",
        }
        repo_list = ", ".join([f"{name} ({strategy_names.get(s, s)})" for name, s in native_repos[:3]])
        if len(native_repos) > 3:
            repo_list += f" and {len(native_repos) - 3} more"
        
        terminal.warning("⚠️ PAT REQUIRED FOR NATIVE GIT INTEGRATIONS")
        terminal.warning(f"Source has repositories using native integrations: {repo_list}")
        terminal.warning("Service tokens cannot access the integrations API.")
        terminal.warning("Repositories will fall back to deploy key authentication in the target.")
        terminal.warning("")
        terminal.warning("To preserve native integrations, please:")
        terminal.warning("  1. Change Token Type to 'User Token (PAT)' above")
        terminal.warning("  2. Enter a Personal Access Token (starts with 'dbtu_')")
        terminal.warning("")
        
        ui.notify(
            "Service token detected with native integrations - repositories will use deploy key. "
            "Switch to User Token (PAT) for native integration support.",
            type="warning",
            timeout=10000,
        )

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
    state.target_fetch.fetch_complete = False
    
    # Reset the results panel to placeholder state (preserves layout)
    if results_container is not None:
        results_container.clear()
        # Recreate the placeholder to maintain consistent height
        _create_results_section(state, on_step_change, results_container)
    
    # Start progress tracking
    terminal.clear()
    progress_tree.start()
    
    terminal.info("Starting target fetch operation...")
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
        
        run_tracker = RunTracker(output_dir / "target_importer_runs.json")
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
        terminal.success("Target fetch complete!")

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

        # Also update target account info
        state.target_account.account_name = snapshot.account_name or ""
        state.target_account.account_id = creds.account_id
        state.target_account.host_url = creds.host_url
        state.target_account.is_configured = True
        state.target_account.is_verified = True
        
        # Store raw account data
        state.target_account_data = payload
        
        # Reset match-related state since target data has changed
        # This ensures the Match page shows fresh data, not stale mappings
        #
        # PRESERVED per FR-14/FR-16/FR-19 (PRD 21.02):
        #   - confirmed_mappings: kept for stale detection (may need review)
        #   - rejected_suggestions: kept (user work)
        #   - disable_job_triggers: kept (user setting, FR-14)
        #   - import_mode: kept (user setting, FR-15)
        #   - protected_resources: kept (FR-17)
        #
        # RESET (re-derivable or invalid after target change):
        state.map.suggested_matches = []  # Tier 3: re-generated from new data
        state.map.mapping_file_valid = False  # May be stale
        state.map.mapping_file_path = None

        save_state()
        fetch_complete["value"] = True

        terminal.info("")
        terminal.success("━━━ TARGET FETCH COMPLETE ━━━")
        terminal.info(f"  Projects: {fetch_state.resource_counts.get('projects', 0)}")
        terminal.info(f"  Environments: {fetch_state.resource_counts.get('environments', 0)}")
        terminal.info(f"  Credentials: {fetch_state.resource_counts.get('credentials', 0)}")
        terminal.info(f"  Jobs: {fetch_state.resource_counts.get('jobs', 0)}")
        terminal.info(f"  Connections: {fetch_state.resource_counts.get('connections', 0)}")
        terminal.info(f"  Repositories: {fetch_state.resource_counts.get('repositories', 0)}")
        terminal.info(f"  Total time: {fetch_duration:.1f}s")

        # Mark progress tree as complete
        progress_tree.complete()
        
        ui.notify("Target fetch completed successfully!", type="positive")

        # Dynamically show the results section instead of reloading
        # This preserves the terminal logs and progress tree state
        if results_container is not None:
            results_container.clear()
            _create_results_section(state, on_step_change, results_container)

    except FetchCancelledException:
        terminal.warning("")
        terminal.warning("━━━ TARGET FETCH CANCELLED ━━━")
        terminal.warning("The fetch operation was cancelled by the user.")
        
        # Mark progress tree as cancelled
        progress_tree.error("Cancelled")
        
        ui.notify("Fetch cancelled", type="warning")

    except Exception as e:
        terminal.error("")
        terminal.error(f"Target fetch failed: {e}")
        
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
