"""Fetch step page for configuring source credentials and fetching account data."""

import asyncio
import json
import logging
import threading
from datetime import datetime
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
    FetchProgressHandler,
    LogLevel,
    TerminalOutput,
)
from importer.web.components.progress_tree import ProgressTree
from importer.web.env_manager import (
    load_source_credentials,
    load_source_credentials_from_content,
    save_source_credentials,
    load_account_info_from_env,
    fetch_account_name,
)
from importer.element_ids import apply_element_ids


# dbt brand colors
DBT_ORANGE = "#FF694A"


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
    
    # State for tracking fetch progress
    fetch_in_progress = {"value": False}
    fetch_complete = {"value": state.fetch.fetch_complete}
    cancel_event = {"event": None}  # Will hold threading.Event during fetch
    
    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-4"):
        # Page header
        with ui.row().classes("w-full items-center gap-4"):
            ui.icon("cloud_download", size="2rem").style(f"color: {DBT_ORANGE};")
            ui.label("Fetch Source Account").classes("text-2xl font-bold")

        ui.label(
            "Configure your source dbt Platform account credentials and fetch the account data."
        ).classes("text-slate-600 dark:text-slate-400")

        # Two-column layout: 1/3 credentials, 2/3 output
        with ui.row().classes("w-full gap-6"):
            # Left column: Credentials and Options (1/3 width)
            with ui.column().classes("w-1/3 min-w-[300px] gap-4"):
                create_source_credential_form(
                    state=state,
                    on_credentials_change=lambda creds: _on_credentials_change(state, save_state),
                    on_load_env=lambda: _load_env_credentials(state, terminal, save_state),
                    on_load_env_content=lambda content, filename: _load_env_from_upload(
                        content, filename, state, terminal, save_state
                    ),
                    on_save_env=lambda: _save_env_credentials(state, terminal),
                )

                # Fetch Options
                _create_fetch_options(state, save_state)

            # Right column: Actions, Progress, and Output (2/3 width)
            with ui.column().classes("flex-grow gap-4"):
                # Action buttons row
                with ui.card().classes("w-full p-4"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label("Actions").classes("font-semibold")
                        
                        # Test connection button
                        test_btn = ui.button(
                            "Test Connection",
                            icon="network_check",
                            on_click=lambda: _test_connection(state, terminal),
                        ).props("outline")

                    # Fetch button - defined after results_container
                    fetch_btn_container = ui.row().classes("w-full mt-4")

                # Progress Tree (structured hierarchy) and Terminal Output
                with ui.row().classes("w-full gap-4"):
                    # Progress tree panel
                    with ui.card().classes("w-1/3 min-w-[220px] p-4"):
                        ui.label("Progress").classes("font-semibold mb-2")
                        progress_tree.create()
                    
                    # Terminal output (scrolling logs)
                    with ui.column().classes("flex-grow"):
                        terminal.create(height="400px")

        # Results section (shown after fetch completes)
        results_container = ui.column().classes("w-full gap-4")
        
        if state.fetch.fetch_complete:
            with results_container:
                _create_results_section(state, on_step_change)

        # Now add the fetch button with access to results_container
        with fetch_btn_container:
            with ui.row().classes("w-full gap-2"):
                fetch_btn = ui.button(
                    "Fetch Account Data",
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
                ).classes("flex-grow").style(f"background-color: {DBT_ORANGE};")

                cancel_btn = ui.button(
                    "Cancel",
                    icon="cancel",
                    on_click=lambda: _cancel_fetch(cancel_event, terminal),
                ).props("outline color=negative").classes("hidden")


def _create_fetch_options(state: AppState, save_state: Callable[[], None]) -> None:
    """Create fetch options card."""
    with ui.card().classes("w-full"):
        ui.label("Fetch Options").classes("font-semibold mb-4")

        # Output directory
        ui.input(
            label="Output Directory",
            value=state.fetch.output_dir,
            placeholder="dev_support/samples",
        ).classes("w-full").props('outlined').on(
            'update:model-value',
            lambda e: _update_output_dir(state, e.args, save_state)
        )

        # Auto-timestamp toggle
        ui.switch(
            "Auto-timestamp filenames",
            value=state.fetch.auto_timestamp,
            on_change=lambda e: _update_auto_timestamp(state, e.value, save_state),
        ).classes("mt-4")

        # Advanced options (collapsed by default)
        with ui.expansion("Advanced Options", icon="settings").classes("w-full mt-4"):
            ui.number(
                label="API Timeout (seconds)",
                value=90,
                min=10,
                max=300,
            ).classes("w-full").props('outlined')

            ui.number(
                label="Max Retries",
                value=5,
                min=1,
                max=10,
            ).classes("w-full mt-2").props('outlined')

            ui.switch(
                "Verify SSL",
                value=True,
            ).classes("mt-2")


def _create_results_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create the results section shown after successful fetch."""
    with ui.card().classes("w-full p-6 border-l-4 border-green-500"):
        with ui.row().classes("w-full items-center gap-3"):
            ui.icon("check_circle", size="lg").classes("text-green-500")
            ui.label("Fetch Complete").classes("text-xl font-semibold")

        # Stats grid
        counts = state.fetch.resource_counts
        if counts:
            with ui.row().classes("w-full mt-4 gap-4 flex-wrap"):
                for resource, count in counts.items():
                    with ui.card().classes("p-3 min-w-[100px]"):
                        ui.label(str(count)).classes("text-2xl font-bold")
                        ui.label(resource.replace("_", " ").title()).classes("text-sm text-slate-500")

        # Account info
        if state.fetch.account_name:
            ui.label(f"Account: {state.fetch.account_name}").classes("mt-4 text-slate-600 dark:text-slate-400")

        # File paths
        with ui.column().classes("mt-4 gap-1"):
            if state.fetch.last_fetch_file:
                ui.label(f"Data: {state.fetch.last_fetch_file}").classes("text-xs text-slate-500 font-mono")
            if state.fetch.last_summary_file:
                ui.label(f"Summary: {state.fetch.last_summary_file}").classes("text-xs text-slate-500 font-mono")

        # Continue button
        ui.button(
            "Continue to Explore",
            icon="arrow_forward",
            on_click=lambda: on_step_change(WorkflowStep.EXPLORE),
        ).classes("mt-6").style(f"background-color: {DBT_ORANGE};")


def _on_credentials_change(state: AppState, save_state: Callable[[], None]) -> None:
    """Handle credentials change."""
    save_state()


def _update_output_dir(state: AppState, value: str, save_state: Callable[[], None]) -> None:
    """Update output directory in state."""
    state.fetch.output_dir = value if value else "dev_support/samples"
    save_state()


def _update_auto_timestamp(state: AppState, value: bool, save_state: Callable[[], None]) -> None:
    """Update auto-timestamp setting."""
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
        creds = load_source_credentials()
        
        if not creds.get("account_id") and not creds.get("api_token"):
            terminal.warning("No source credentials found in .env file")
            ui.notify("No credentials found in .env", type="warning")
            return

        # Update state
        state.source_credentials.host_url = creds.get("host_url", "https://cloud.getdbt.com")
        state.source_credentials.account_id = creds.get("account_id", "")
        state.source_credentials.api_token = creds.get("api_token", "")
        
        # Also update account info
        state.source_account = load_account_info_from_env("source")
        
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
        path = save_source_credentials(
            host_url=creds.host_url,
            account_id=creds.account_id,
            api_token=creds.api_token,
        )
        terminal.success(f"Credentials saved to {path}")
        ui.notify("Credentials saved", type="positive")

    except Exception as e:
        terminal.error(f"Failed to save credentials: {e}")
        ui.notify(f"Failed to save: {e}", type="negative")


async def _test_connection(state: AppState, terminal: TerminalOutput) -> None:
    """Test connection to dbt Platform API."""
    creds = state.source_credentials
    
    # Validate first
    is_valid, errors = validate_credentials(creds)
    if not is_valid:
        for err in errors:
            terminal.error(err)
        ui.notify("Invalid credentials", type="negative")
        return

    terminal.info(f"Testing connection to {creds.host_url}...")
    
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
    """Run the fetch operation."""
    creds = state.source_credentials
    
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
    
    # Clear previous results panel if it exists
    if results_container is not None:
        results_container.clear()
    
    # Start progress tracking
    terminal.clear()
    progress_tree.start()
    
    terminal.info("Starting fetch operation...")
    terminal.info(f"Host: {creds.host_url}")
    terminal.info(f"Account ID: {creds.account_id}")
    terminal.info(f"Output: {state.fetch.output_dir}")
    terminal.info("")

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
        output_dir = Path(state.fetch.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        run_tracker = RunTracker(output_dir / "importer_runs.json")
        run_id, timestamp = run_tracker.start_run(settings.account_id)

        terminal.info(f"Run ID: {run_id}, Timestamp: {timestamp}")
        terminal.info("")

        # Create combined progress handler that updates both terminal and tree
        progress = CombinedProgressHandler(terminal, progress_tree)

        # Run fetch in thread pool
        terminal.info("Connecting to dbt Platform API...")
        threads = getattr(state.fetch, 'threads', 5) or 5
        event = cancel_event["event"]
        
        def do_fetch():
            client = DbtCloudClient(settings)
            try:
                return fetch_account_snapshot(
                    client, progress=progress, threads=threads, cancel_event=event
                )
            finally:
                client.close()

        snapshot = await asyncio.to_thread(do_fetch)

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
        state.fetch.fetch_complete = True
        state.fetch.last_fetch_file = str(json_path)
        state.fetch.last_summary_file = str(summary_path)
        state.fetch.last_report_file = str(report_path)
        state.fetch.last_report_items_file = str(report_items_path)
        state.fetch.account_name = snapshot.account_name
        
        # Calculate resource counts
        state.fetch.resource_counts = {
            "projects": len(snapshot.projects),
            "environments": sum(len(p.environments) for p in snapshot.projects),
            "jobs": sum(len(p.jobs) for p in snapshot.projects),
            "connections": len(snapshot.globals.connections),
            "repositories": len(snapshot.globals.repositories),
        }

        # Also update account info
        state.source_account.account_name = snapshot.account_name or ""
        state.source_account.account_id = creds.account_id
        state.source_account.host_url = creds.host_url
        state.source_account.is_configured = True
        state.source_account.is_verified = True

        save_state()
        fetch_complete["value"] = True

        terminal.info("")
        terminal.success("━━━ FETCH COMPLETE ━━━")
        terminal.info(f"  Projects: {state.fetch.resource_counts.get('projects', 0)}")
        terminal.info(f"  Environments: {state.fetch.resource_counts.get('environments', 0)}")
        terminal.info(f"  Jobs: {state.fetch.resource_counts.get('jobs', 0)}")
        terminal.info(f"  Connections: {state.fetch.resource_counts.get('connections', 0)}")
        terminal.info(f"  Repositories: {state.fetch.resource_counts.get('repositories', 0)}")

        # Mark progress tree as complete
        progress_tree.complete()
        
        ui.notify("Fetch completed successfully!", type="positive")

        # Dynamically add results section (instead of reloading)
        if results_container is not None:
            results_container.clear()
            with results_container:
                _create_results_section(state, on_step_change)

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