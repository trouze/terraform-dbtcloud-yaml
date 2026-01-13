"""Home/dashboard page for the web UI."""

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep


def create_home_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create the home/dashboard page content.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
    """
    with ui.column().classes("w-full max-w-4xl mx-auto p-8 gap-8"):
        # Welcome section
        _create_welcome_section(on_step_change)

        # Quick stats (if there's previous data)
        if state.fetch.fetch_complete:
            _create_quick_stats(state)

        # Recent runs
        _create_recent_runs_section(state, on_step_change)


def _create_welcome_section(on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Create the welcome/hero section."""
    with ui.card().classes("w-full p-8"):
        with ui.column().classes("gap-4"):
            with ui.row().classes("items-center gap-4"):
                ui.image("/static/favicon.svg").classes("w-12 h-12")
                with ui.column().classes("gap-0"):
                    ui.label("dbt Magellan").classes("text-3xl font-bold")
                    ui.label("Exploration & Migration Tool").classes("text-sm text-slate-500")

            ui.markdown("""
                Explore, audit, and migrate dbt Platform account configurations with a guided workflow:
                
                1. **Fetch** - Download your account configuration via API
                2. **Explore** - Review entities, view reports, export CSVs, analyze charts
                3. **Map** - Select entities to migrate, configure transformations
                4. **Target** - Set up destination account credentials
                5. **Deploy** - Generate Terraform and apply changes
                
                *Use steps 1-2 for account exploration and auditing, or complete all steps for full migration.*
            """).classes("text-slate-600 dark:text-slate-400")

            with ui.row().classes("gap-4 mt-4"):
                ui.button(
                    "Get Started",
                    icon="rocket_launch",
                    on_click=lambda: on_step_change(WorkflowStep.FETCH),
                ).style("background-color: #FF694A;")

                ui.button(
                    "Documentation",
                    icon="menu_book",
                    on_click=lambda: ui.notify("Documentation coming soon"),
                ).props("outline")


def _create_quick_stats(state: AppState) -> None:
    """Create quick stats cards from the last fetch."""
    with ui.card().classes("w-full"):
        ui.label("Current Session").classes("text-lg font-semibold mb-4")

        with ui.row().classes("gap-4 flex-wrap"):
            # Account info
            if state.fetch.account_name:
                _stat_card("Account", state.fetch.account_name, "business")

            # Resource counts
            counts = state.fetch.resource_counts
            if counts:
                if "projects" in counts:
                    _stat_card("Projects", str(counts["projects"]), "folder")
                if "environments" in counts:
                    _stat_card("Environments", str(counts["environments"]), "dns")
                if "jobs" in counts:
                    _stat_card("Jobs", str(counts["jobs"]), "schedule")
                if "connections" in counts:
                    _stat_card("Connections", str(counts["connections"]), "cable")


def _stat_card(label: str, value: str, icon: str) -> None:
    """Create a small stat card."""
    with ui.card().classes("p-4 min-w-[120px]"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon, size="sm").style("color: #FF694A;")
            ui.label(label).classes("text-sm text-slate-500")
        ui.label(value).classes("text-xl font-semibold mt-1")


def _create_recent_runs_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Create the recent runs table."""
    with ui.card().classes("w-full"):
        ui.label("Recent Runs").classes("text-lg font-semibold mb-4")

        # Try to load recent runs
        runs = _load_recent_runs(state.fetch.output_dir)

        if not runs:
            with ui.row().classes("items-center gap-2 text-slate-500"):
                ui.icon("info", size="sm")
                ui.label("No previous runs found. Click 'Get Started' to fetch your first account.")
            return

        # Create table
        columns = [
            {"name": "type", "label": "Type", "field": "type", "align": "left"},
            {"name": "account", "label": "Account", "field": "account", "align": "left"},
            {"name": "timestamp", "label": "Timestamp", "field": "timestamp", "align": "left"},
            {"name": "status", "label": "Status", "field": "status", "align": "left"},
        ]

        rows = []
        for run in runs[:10]:  # Show last 10
            rows.append({
                "type": run.get("type", "fetch"),
                "account": f"Account {run.get('account_id', 'N/A')}",
                "timestamp": run.get("timestamp", "Unknown"),
                "status": "Complete" if run.get("success", True) else "Failed",
            })

        table = ui.table(columns=columns, rows=rows, row_key="timestamp").classes("w-full")

        # TODO: Add click handler to load run data


def _load_recent_runs(output_dir: str) -> list:
    """Load recent runs from importer_runs.json and normalization_runs.json."""
    runs = []

    # Try to find runs files
    output_path = Path(output_dir)
    if not output_path.exists():
        return runs

    # Load fetch runs
    importer_runs_file = output_path / "importer_runs.json"
    if importer_runs_file.exists():
        try:
            data = json.loads(importer_runs_file.read_text())
            for account_id, account_runs in data.items():
                for run in account_runs:
                    runs.append({
                        "type": "fetch",
                        "account_id": account_id,
                        "timestamp": run.get("timestamp", ""),
                        "run_id": run.get("run_id"),
                        "success": True,
                    })
        except (json.JSONDecodeError, KeyError):
            pass

    # Load normalize runs
    norm_dir = output_path / "normalized"
    norm_runs_file = norm_dir / "normalization_runs.json"
    if norm_runs_file.exists():
        try:
            data = json.loads(norm_runs_file.read_text())
            for account_id, account_runs in data.items():
                for run in account_runs:
                    runs.append({
                        "type": "normalize",
                        "account_id": account_id,
                        "timestamp": run.get("timestamp", ""),
                        "run_id": run.get("norm_run_id"),
                        "success": True,
                    })
        except (json.JSONDecodeError, KeyError):
            pass

    # Sort by timestamp descending
    runs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)

    return runs
