"""Fetch Source step page - configure source credentials and fetch account data."""

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep
from importer.web.components.credential_form import (
    create_source_credential_form,
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
    load_account_info_from_env,
    fetch_account_name,
    resolve_project_env_path,
    auto_seed_project_env,
)
from importer.element_ids import apply_element_ids
from importer.web.project_manager import resolve_fetch_output_dirs_for_project


# dbt brand colors
DBT_ORANGE = "#FF694A"

# Default source folder when no active project is loaded.
_DEFAULT_SOURCE_OUTPUT_DIR = "dev_support/samples/source"


def _dbg_db419a(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "db419a",
        "runId": "post-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(
            "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-db419a.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


def _enforced_source_output_dir(state: AppState) -> str:
    project_source_dir, _ = resolve_fetch_output_dirs_for_project(state.project_path)
    if project_source_dir:
        return project_source_dir
    return _DEFAULT_SOURCE_OUTPUT_DIR


def _enforce_source_output_dir(state: AppState, save_state: Callable[[], None]) -> None:
    enforced_dir = _enforced_source_output_dir(state)
    if state.fetch.output_dir != enforced_dir:
        previous = state.fetch.output_dir
        state.fetch.output_dir = enforced_dir
        save_state()
        # region agent log
        _dbg_db419a(
            "H27",
            "fetch_source.py:_enforce_source_output_dir",
            "enforced read-only source output directory",
            {
                "project_path": state.project_path,
                "previous_output_dir": previous,
                "enforced_output_dir": enforced_dir,
            },
        )
        # endregion


def create_fetch_source_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Fetch Source step page content.

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
    fetch_complete = {"value": state.fetch.fetch_complete}

    _enforce_source_output_dir(state, save_state)
    
    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-4"):
        # Page header
        with ui.row().classes("w-full items-center gap-4"):
            ui.icon("cloud_download", size="2rem").style(f"color: {DBT_ORANGE};")
            ui.label("Fetch Source Account").classes("text-2xl font-bold")

        ui.label(
            "Configure your source dbt Platform account credentials and fetch the account data."
        ).classes("text-slate-600 dark:text-slate-400")

        # Vertical layout: Credentials, Options, Actions, then Logs
        
        # 1. Source credential form (full width card)
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
                cancel_btn = ui.button(
                    "Cancel",
                    icon="cancel",
                    on_click=lambda: _cancel_fetch(cancel_event, terminal),
                ).props("outline color=negative").classes("hidden")

                fetch_btn = ui.button(
                    "Fetch Account Data",
                    icon="cloud_download",
                ).classes("flex-grow").style(f"background-color: {DBT_ORANGE};")
                fetch_btn.on(
                    "click",
                    lambda: _run_fetch(
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
                )

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
                value=state.fetch.output_dir,
                placeholder=_DEFAULT_SOURCE_OUTPUT_DIR,
            ).classes("flex-grow").props("outlined dense readonly")

            # Auto-timestamp toggle (inline)
            ui.switch(
                "Auto-timestamp",
                value=state.fetch.auto_timestamp,
                on_change=lambda e: _update_auto_timestamp(state, e.value, save_state),
            )

            # Advanced options button
            with ui.expansion("Advanced", icon="settings", value=False).classes("w-auto"):
                with ui.column().classes("gap-2 p-2"):
                    def _update_threads(e):
                        val = e.args if e.args is not None else 50
                        state.fetch.threads = int(val) if val else 50
                        save_state()
                    
                    ui.number(
                        label="Threads",
                        value=getattr(state.fetch, 'threads', 25) or 25,
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
                        value=5,
                        min=1,
                        max=10,
                    ).props('outlined dense')

            ui.switch(
                "Verify SSL",
                value=True,
            ).classes("mt-2")


def _create_results_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    container: ui.column,
) -> None:
    """Create the results section showing file paths and continue button when fetch is complete."""
    with container:
        if state.fetch.fetch_complete:
            ui.separator().classes("my-3")
            with ui.row().classes("w-full items-center justify-between"):
                # File paths on the left
                with ui.column().classes("gap-0 text-xs text-slate-500 font-mono"):
                    if state.fetch.last_fetch_file:
                        ui.label(f"Data: {state.fetch.last_fetch_file}")
                    if state.fetch.last_summary_file:
                        ui.label(f"Summary: {state.fetch.last_summary_file}")
                
                # Continue button (full width, same style as fetch button)
                ui.button(
                    "Explore Source",
                    icon="arrow_forward",
                    on_click=lambda: on_step_change(WorkflowStep.EXPLORE_SOURCE),
                ).classes("w-full").style(f"background-color: {DBT_ORANGE};")


def _on_credentials_change(state: AppState, save_state: Callable[[], None]) -> None:
    """Handle credentials change."""
    save_state()


def _update_auto_timestamp(
    state: AppState,
    value: bool,
    save_state: Callable[[], None],
) -> None:
    """Update auto-timestamp setting."""
    state.fetch.auto_timestamp = value
    save_state()


def _load_env_credentials(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
) -> None:
    """Load credentials from default .env file."""
    
    # Check if there's existing fetch data
    has_existing_fetch = (
        state.fetch.fetch_complete and 
        state.fetch.last_fetch_file
    )
    
    if has_existing_fetch:
        # Show confirmation dialog
        _show_load_credentials_dialog(
            state=state,
            terminal=terminal,
            save_state=save_state,
            fetch_type="source",
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
    """Actually load credentials from default .env file."""
    terminal.info("Loading credentials from default .env file...")
    
    try:
        env_path = resolve_project_env_path(state.project_path, "source")
        if env_path and not Path(env_path).exists() and state.project_path:
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
        state.source_account = load_account_info_from_env("source")
        
        # Optionally clear previous fetch results
        if reset_fetch:
            state.fetch.fetch_complete = False
            terminal.info("Previous fetch data cleared - ready for fresh fetch")
        else:
            terminal.info("Keeping existing fetch data")
        
        save_state()
        
        terminal.success("Credentials loaded from .env")
        ui.notify("Credentials loaded", type="positive")
        
        # Reload page to show new values
        ui.navigate.reload()

    except Exception as e:
        terminal.error(f"Failed to load credentials: {e}")
        ui.notify(f"Failed to load: {e}", type="negative")


def _show_load_credentials_dialog(
    state: AppState,
    terminal: TerminalOutput,
    save_state: Callable[[], None],
    fetch_type: str,
    load_func: Callable[[bool], None],
) -> None:
    """Show a dialog asking whether to keep or reset existing fetch data."""
    fetch_state = state.fetch if fetch_type == "source" else state.target_fetch
    
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
    """Load credentials from uploaded .env file content."""
    
    # Check if there's existing fetch data
    has_existing_fetch = (
        state.fetch.fetch_complete and 
        state.fetch.last_fetch_file
    )
    
    if has_existing_fetch:
        # Show confirmation dialog
        _show_load_credentials_dialog(
            state=state,
            terminal=terminal,
            save_state=save_state,
            fetch_type="source",
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
    """Actually load credentials from uploaded .env file content."""
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
        
        # Optionally clear previous fetch results
        if reset_fetch:
            state.fetch.fetch_complete = False
            terminal.info("Previous fetch data cleared - ready for fresh fetch")
        else:
            terminal.info("Keeping existing fetch data")
        
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


async def _test_connection(
    state: AppState,
    terminal: TerminalOutput,
) -> None:
    """Test connection to source dbt Platform API."""
    creds = state.source_credentials
    
    # Validate first
    is_valid, errors = validate_credentials(creds)
    if not is_valid:
        for err in errors:
            terminal.error(err)
        ui.notify("Invalid credentials", type="negative")
        return

    terminal.info(f"Testing source connection to {creds.host_url}...")
    
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
    """Run the source fetch operation."""
    creds = state.source_credentials
    fetch_state = state.fetch
    
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
    state.fetch.fetch_complete = False
    
    # Reset the results panel to placeholder state (preserves layout)
    if results_container is not None:
        results_container.clear()
        # Recreate the placeholder to maintain consistent height
        _create_results_section(state, on_step_change, results_container)
    
    # Start progress tracking
    terminal.clear()
    progress_tree.start()
    
    terminal.info("Starting source fetch operation...")
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
        
        run_tracker = RunTracker(output_dir / "importer_runs.json")
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
        event.clear()  # Ensure no stale set() from a previous run or shared reference
        import time
        fetch_start_time = time.time()
        
        def do_fetch():
            # Clear cancel event at thread start so we ignore any set() that happened
            # before the thread was scheduled (e.g. phantom/race with Cancel button).
            event.clear()
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
        fetch_state.last_fetch_file = str(json_path)
        fetch_state.last_summary_file = str(summary_path)
        fetch_state.last_report_file = str(report_path)
        fetch_state.last_report_items_file = str(report_items_path)
        fetch_state.account_name = snapshot.account_name
        
        # Calculate resource counts (including credentials and extended attributes)
        fetch_state.resource_counts = {
            "projects": len(snapshot.projects),
            "environments": sum(len(p.environments) for p in snapshot.projects),
            "credentials": sum(
                1 for p in snapshot.projects 
                for e in p.environments 
                if e.credential is not None
            ),
            "jobs": sum(len(p.jobs) for p in snapshot.projects),
            "extended_attributes": sum(len(p.extended_attributes) for p in snapshot.projects),
            "connections": len(snapshot.globals.connections),
            "repositories": len(snapshot.globals.repositories),
        }

        # Also update account info
        state.source_account.account_name = snapshot.account_name or ""
        state.source_account.account_id = creds.account_id
        state.source_account.host_url = creds.host_url
        state.source_account.is_configured = True
        state.source_account.is_verified = True
        
        # Store raw account data
        state.account_data = payload

        # Reset downstream state since source data has changed
        # This ensures Match, Configure, and Deploy steps reflect fresh data
        #
        # PRESERVED per FR-14/FR-16/FR-19 (PRD 21.02):
        #   - confirmed_mappings: kept for stale detection (may need review)
        #   - rejected_suggestions: kept (user work)
        #   - disable_job_triggers: kept (user setting, FR-14)
        #   - import_mode: kept (user setting, FR-15)
        #   - protected_resources: kept (FR-17)
        #   - scope_mode, resource_filters, normalization_options: kept (FR-18)
        #
        # RESET (re-derivable or invalid after source change):
        state.map.suggested_matches = []  # Tier 3: re-generated from new data
        state.map.mapping_file_valid = False  # May be stale
        state.map.mapping_file_path = None
        state.map.normalize_complete = False  # Re-scope needed with new source data

        save_state()
        fetch_complete["value"] = True

        terminal.info("")
        terminal.success("━━━ FETCH COMPLETE ━━━")
        terminal.info(f"  Projects: {fetch_state.resource_counts.get('projects', 0)}")
        terminal.info(f"  Environments: {fetch_state.resource_counts.get('environments', 0)}")
        terminal.info(f"  Credentials: {fetch_state.resource_counts.get('credentials', 0)}")
        terminal.info(f"  Jobs: {fetch_state.resource_counts.get('jobs', 0)}")
        terminal.info(f"  Extended Attributes: {fetch_state.resource_counts.get('extended_attributes', 0)}")
        terminal.info(f"  Connections: {fetch_state.resource_counts.get('connections', 0)}")
        terminal.info(f"  Repositories: {fetch_state.resource_counts.get('repositories', 0)}")
        terminal.info(f"  Total time: {fetch_duration:.1f}s")

        # Mark progress tree as complete
        progress_tree.complete()
        
        ui.notify("Fetch completed successfully!", type="positive")

        # Dynamically show the results section instead of reloading
        # This preserves the terminal logs and progress tree state
        if results_container is not None:
            results_container.clear()
            _create_results_section(state, on_step_change, results_container)

    except asyncio.CancelledError:
        # Task was cancelled (e.g. navigation away); don't treat as user cancel
        raise
    except FetchCancelledException as _fce:
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