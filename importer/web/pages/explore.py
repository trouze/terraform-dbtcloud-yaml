"""Explore step page - browse entities, view reports, export data."""

import json
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, STEP_NAMES
from importer.web.components.stepper import DBT_ORANGE


def create_explore_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Explore step page with tabs."""
    
    with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-4"):
        # Header
        _create_header(state)
        
        # Check if data is available
        if not state.fetch.fetch_complete:
            _create_no_data_message(on_step_change)
            return
        
        # Load data files
        summary_content = _load_file(state.fetch.last_summary_file)
        report_content = _load_file(state.fetch.last_report_file)
        report_items = _load_report_items(state)
        
        # Main tabs
        with ui.tabs().classes("w-full") as tabs:
            summary_tab = ui.tab("Summary", icon="summarize")
            report_tab = ui.tab("Report", icon="article")
            entities_tab = ui.tab("Entities", icon="table_chart")
            charts_tab = ui.tab("Charts", icon="bar_chart")
        
        with ui.tab_panels(tabs, value=summary_tab).classes("w-full"):
            with ui.tab_panel(summary_tab):
                _create_summary_tab(summary_content, state)
            
            with ui.tab_panel(report_tab):
                _create_report_tab(report_content, state)
            
            with ui.tab_panel(entities_tab):
                _create_entities_tab(report_items, state, save_state)
            
            with ui.tab_panel(charts_tab):
                _create_charts_tab(report_items, state)
        
        # Navigation buttons
        _create_navigation(state, on_step_change)


def _create_header(state: AppState) -> None:
    """Create the page header with account info."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-1"):
                ui.label("Explore Account Data").classes("text-2xl font-bold")
                if state.fetch.account_name:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("cloud", size="sm").classes("text-slate-500")
                        ui.label(state.fetch.account_name).classes("text-slate-600 dark:text-slate-400")
            
            # Resource counts summary
            if state.fetch.resource_counts:
                with ui.row().classes("gap-4"):
                    counts = state.fetch.resource_counts
                    for key, icon in [
                        ("projects", "folder"),
                        ("environments", "layers"),
                        ("jobs", "schedule"),
                        ("connections", "storage"),
                    ]:
                        if key in counts:
                            with ui.row().classes("items-center gap-1"):
                                ui.icon(icon, size="xs").classes("text-slate-500")
                                ui.label(f"{counts[key]}").classes("font-medium")


def _create_no_data_message(on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Show message when no fetch data is available."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("warning", size="3rem").classes("text-amber-500 mx-auto")
        ui.label("No Data Available").classes("text-xl font-bold mt-4")
        ui.label("Complete the Fetch step first to explore account data.").classes(
            "text-slate-600 dark:text-slate-400 mt-2"
        )
        ui.button(
            "Go to Fetch",
            icon="cloud_download",
            on_click=lambda: on_step_change(WorkflowStep.FETCH),
        ).classes("mt-4").style(f"background-color: {DBT_ORANGE};")


def _load_file(filepath: Optional[str]) -> str:
    """Load a file's content or return empty string."""
    if not filepath:
        return ""
    path = Path(filepath)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _load_report_items(state: AppState) -> list:
    """Load report items from the JSON file."""
    # First, try to use the path from state
    if state.fetch.last_report_items_file:
        report_items_path = Path(state.fetch.last_report_items_file)
        if report_items_path.exists():
            try:
                return json.loads(report_items_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    
    # Fallback: try to find report_items file based on the summary file path
    if state.fetch.last_summary_file:
        summary_path = Path(state.fetch.last_summary_file)
        # Convert summary filename to report_items filename
        parts = summary_path.stem.split("__")
        if len(parts) >= 3:
            prefix = parts[0]  # account_86165_run_001
            timestamp = parts[-1]  # 20260112_...
            report_items_name = f"{prefix}__report_items__{timestamp}.json"
            report_items_path = summary_path.parent / report_items_name
            if report_items_path.exists():
                try:
                    return json.loads(report_items_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
    
    # Fallback: search in output directory
    if state.fetch.output_dir:
        output_dir = Path(state.fetch.output_dir)
        if output_dir.exists():
            # Find most recent report_items file
            pattern = "*__report_items__*.json"
            files = sorted(output_dir.glob(pattern), reverse=True)
            if files:
                try:
                    return json.loads(files[0].read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
    
    return []


def _create_summary_tab(content: str, state: AppState) -> None:
    """Create the Summary tab content."""
    with ui.column().classes("w-full gap-4"):
        # Refresh button
        with ui.row().classes("w-full justify-end"):
            ui.button(
                "Refresh",
                icon="refresh",
                on_click=lambda: ui.notify("Refresh from file not yet implemented", type="info"),
            ).props("flat")
        
        if content:
            # Render markdown in a card
            with ui.card().classes("w-full p-6"):
                ui.markdown(content).classes("prose dark:prose-invert max-w-none")
        else:
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("description", size="2rem").classes("text-slate-400")
                ui.label("No summary file found").classes("text-slate-500 mt-2")


def _create_report_tab(content: str, state: AppState) -> None:
    """Create the Report tab content."""
    with ui.column().classes("w-full gap-4"):
        # Search box for report
        with ui.row().classes("w-full items-center gap-4"):
            search = ui.input(
                placeholder="Search in report...",
            ).props("outlined dense").classes("flex-grow")
            
            ui.button("Refresh", icon="refresh").props("flat")
        
        if content:
            with ui.card().classes("w-full p-6 max-h-[600px] overflow-auto"):
                ui.markdown(content).classes("prose dark:prose-invert max-w-none text-sm")
        else:
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("description", size="2rem").classes("text-slate-400")
                ui.label("No report file found").classes("text-slate-500 mt-2")


def _create_entities_tab(report_items: list, state: AppState, save_state: Callable[[], None]) -> None:
    """Create the Entities tab with AGGrid table."""
    from importer.web.components.entity_table import create_entity_table
    
    with ui.column().classes("w-full gap-4"):
        if not report_items:
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("table_chart", size="2rem").classes("text-slate-400")
                ui.label("No entity data available").classes("text-slate-500 mt-2")
                ui.label("Run the Fetch step to load account entities.").classes("text-sm text-slate-400")
            return
        
        # Create the entity table component
        create_entity_table(report_items, state, save_state)


def _create_charts_tab(report_items: list, state: AppState) -> None:
    """Create the Charts tab with visualizations."""
    from importer.web.components.charts import create_charts
    
    with ui.column().classes("w-full gap-4"):
        if not report_items:
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("bar_chart", size="2rem").classes("text-slate-400")
                ui.label("No data available for charts").classes("text-slate-500 mt-2")
            return
        
        create_charts(report_items, state)


def _create_navigation(state: AppState, on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Create navigation buttons."""
    with ui.row().classes("w-full justify-between mt-4"):
        ui.button(
            f"Back to {STEP_NAMES[WorkflowStep.FETCH]}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.FETCH),
        ).props("outline")
        
        ui.button(
            f"Continue to {STEP_NAMES[WorkflowStep.MAP]}",
            icon="arrow_forward",
            on_click=lambda: on_step_change(WorkflowStep.MAP),
        ).style(f"background-color: {DBT_ORANGE};")
