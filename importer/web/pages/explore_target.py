"""Explore Target step page - browse target account entities, view reports, export data."""

import json
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, STEP_NAMES
from importer.web.components.stepper import DBT_ORANGE

# Target accent color
DBT_TEAL = "#047377"


def create_explore_target_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Explore Target step page with tabs."""
    
    # Main container - use CSS Grid for reliable height constraints
    with ui.element("div").classes("w-full max-w-7xl mx-auto p-4").style(
        "display: grid; "
        "grid-template-rows: auto auto 1fr auto; "
        "height: calc(100vh - 100px); "
        "gap: 8px; "
        "overflow: hidden;"
    ):
        # Row 1: Header (auto height)
        _create_header(state)
        
        # Check if data is available
        if not state.target_fetch.fetch_complete:
            _create_no_data_message(on_step_change)
            return
        
        # Load data files
        summary_content = _load_file(state.target_fetch.last_summary_file)
        report_content = _load_file(state.target_fetch.last_report_file)
        report_items = _load_report_items(state)
        
        # Row 2: Tabs (auto height)
        with ui.tabs().classes("w-full") as tabs:
            summary_tab = ui.tab("Summary", icon="summarize")
            report_tab = ui.tab("Report", icon="article")
            entities_tab = ui.tab("Entities", icon="table_chart")
            charts_tab = ui.tab("Charts", icon="bar_chart")
            erd_tab = ui.tab("ERD", icon="account_tree")
        
        # Row 3: Tab panels (1fr - takes remaining space)
        with ui.tab_panels(tabs, value=summary_tab).classes("w-full").style(
            "overflow: hidden; min-height: 0;"
        ):
            with ui.tab_panel(summary_tab).style("width: 100%; height: 100%; overflow: hidden;"):
                _create_summary_tab(summary_content, state)
            
            with ui.tab_panel(report_tab).style("width: 100%; height: 100%; overflow: hidden;"):
                _create_report_tab(report_content, state)
            
            with ui.tab_panel(entities_tab).style("width: 100%; height: 100%; overflow: hidden;"):
                _create_entities_tab(report_items, state, save_state)
            
            with ui.tab_panel(charts_tab).style("width: 100%; height: 100%; overflow: auto;"):
                _create_charts_tab(report_items, state)
            
            with ui.tab_panel(erd_tab).style("width: 100%; height: 100%; overflow: hidden;"):
                _create_erd_tab(report_items, state)
        
        # Row 4: Navigation buttons (auto height)
        _create_navigation(state, on_step_change)


def _create_header(state: AppState) -> None:
    """Create the page header with account info."""
    with ui.card().classes("w-full p-4").style(f"border-left: 4px solid {DBT_TEAL};"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-1"):
                ui.label("Explore Target Account Data").classes("text-2xl font-bold")
                if state.target_fetch.account_name:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("cloud", size="sm").style(f"color: {DBT_TEAL};")
                        ui.label(state.target_fetch.account_name).classes("text-slate-600 dark:text-slate-400")
            
            # Resource counts summary
            if state.target_fetch.resource_counts:
                with ui.row().classes("gap-4"):
                    counts = state.target_fetch.resource_counts
                    for key, icon in [
                        ("projects", "folder"),
                        ("environments", "layers"),
                        ("jobs", "schedule"),
                        ("connections", "storage"),
                    ]:
                        if key in counts:
                            with ui.row().classes("items-center gap-1"):
                                ui.icon(icon, size="xs").style(f"color: {DBT_TEAL};")
                                ui.label(f"{counts[key]}").classes("font-medium")


def _create_no_data_message(on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Show message when no fetch data is available."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("warning", size="3rem").classes("text-amber-500 mx-auto")
        ui.label("No Target Data Available").classes("text-xl font-bold mt-4")
        ui.label("Complete the Fetch Target step first to explore target account data.").classes(
            "text-slate-600 dark:text-slate-400 mt-2"
        )
        ui.button(
            "Go to Fetch Target",
            icon="cloud_download",
            on_click=lambda: on_step_change(WorkflowStep.FETCH_TARGET),
        ).classes("mt-4").style(f"background-color: {DBT_TEAL};")


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
    if state.target_fetch.last_report_items_file:
        report_items_path = Path(state.target_fetch.last_report_items_file)
        if report_items_path.exists():
            try:
                return json.loads(report_items_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    
    # Fallback: try to find report_items file based on the summary file path
    if state.target_fetch.last_summary_file:
        summary_path = Path(state.target_fetch.last_summary_file)
        # Convert summary filename to report_items filename
        parts = summary_path.stem.split("__")
        if len(parts) >= 3:
            prefix = parts[0]  # account_XXX_run_YYY
            timestamp = parts[-1]  # 20260112_...
            report_items_name = f"{prefix}__report_items__{timestamp}.json"
            report_items_path = summary_path.parent / report_items_name
            if report_items_path.exists():
                try:
                    return json.loads(report_items_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
    
    # Fallback: search in output directory
    if state.target_fetch.output_dir:
        output_dir = Path(state.target_fetch.output_dir)
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
    from importer.web.utils.markdown_exporter import (
        format_summary_as_markdown,
        generate_download_filename,
    )
    
    async def copy_markdown():
        if content:
            await ui.run_javascript(f'''
                navigator.clipboard.writeText({repr(content)}).catch(err => {{
                    console.error('Failed to copy:', err);
                }});
            ''')
            ui.notify("Summary markdown copied to clipboard", type="positive")
        else:
            ui.notify("No content to copy", type="warning")
    
    async def download_markdown():
        if not content:
            ui.notify("No content to download", type="warning")
            return
        
        # Format with header
        formatted = format_summary_as_markdown(
            content,
            state.target_fetch.account_name or "Unknown",
            state.target_account.account_id,
            state.target_account.host_url,
        )
        
        # Generate filename
        filename = generate_download_filename(
            "summary_target",
            state.target_fetch.account_name or "account",
        )
        
        # Trigger download
        escaped = formatted.replace('`', '\\`').replace('\\', '\\\\')
        await ui.run_javascript(f'''
            const blob = new Blob([`{escaped}`], {{type: 'text/markdown'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = '{filename}';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        ''')
        ui.notify(f"Downloaded {filename}", type="positive")
    
    with ui.element("div").style(
        "display: grid; "
        "grid-template-rows: auto 1fr; "
        "width: 100%; "
        "height: 100%; "
        "gap: 8px; "
        "overflow: hidden;"
    ):
        # Header with icon, copy button, download button, and refresh button (auto height)
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("summarize", size="sm").style(f"color: {DBT_TEAL};")
                ui.label("Target Account Summary").classes("text-lg font-semibold")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Copy Markdown",
                    icon="content_copy",
                    on_click=copy_markdown,
                ).props("flat dense")
                ui.button(
                    "Download",
                    icon="download",
                    on_click=download_markdown,
                ).props("flat dense")
                ui.button(
                    "Refresh",
                    icon="refresh",
                    on_click=lambda: ui.notify("Refresh from file not yet implemented", type="info"),
                ).props("flat dense")
        
        if content:
            # Render markdown in a scrollable card (1fr - fills remaining space)
            with ui.card().classes("w-full").style(
                f"border-left: 4px solid {DBT_TEAL}; overflow: hidden; min-height: 0;"
            ):
                with ui.scroll_area().classes("w-full h-full"):
                    ui.markdown(content).classes("prose dark:prose-invert max-w-none p-4")
        else:
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("description", size="2rem").classes("text-slate-400")
                ui.label("No summary file found").classes("text-slate-500 mt-2")


def _create_report_tab(content: str, state: AppState) -> None:
    """Create the Report tab content."""
    from importer.web.utils.markdown_exporter import (
        format_report_as_markdown,
        generate_download_filename,
    )
    
    async def copy_markdown():
        if content:
            await ui.run_javascript(f'''
                navigator.clipboard.writeText({repr(content)}).catch(err => {{
                    console.error('Failed to copy:', err);
                }});
            ''')
            ui.notify("Report markdown copied to clipboard", type="positive")
        else:
            ui.notify("No content to copy", type="warning")
    
    async def download_markdown():
        if not content:
            ui.notify("No content to download", type="warning")
            return
        
        # Format with header
        formatted = format_report_as_markdown(
            content,
            state.target_fetch.account_name or "Unknown",
            state.target_account.account_id,
            state.target_account.host_url,
        )
        
        # Generate filename
        filename = generate_download_filename(
            "report_target",
            state.target_fetch.account_name or "account",
        )
        
        # Trigger download
        escaped = formatted.replace('`', '\\`').replace('\\', '\\\\')
        await ui.run_javascript(f'''
            const blob = new Blob([`{escaped}`], {{type: 'text/markdown'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = '{filename}';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        ''')
        ui.notify(f"Downloaded {filename}", type="positive")
    
    with ui.element("div").style(
        "display: grid; "
        "grid-template-rows: auto 1fr; "
        "width: 100%; "
        "height: 100%; "
        "gap: 8px; "
        "overflow: hidden;"
    ):
        # Header with icon, search box, copy button, download button, and refresh button (auto height)
        with ui.row().classes("w-full items-center gap-4"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("article", size="sm").style(f"color: {DBT_TEAL};")
                ui.label("Detailed Report").classes("text-lg font-semibold")
            
            search = ui.input(
                placeholder="Search in report...",
            ).props("outlined dense").classes("flex-grow")
            
            with ui.row().classes("gap-2"):
                ui.button(
                    "Copy Markdown",
                    icon="content_copy",
                    on_click=copy_markdown,
                ).props("flat dense")
                ui.button(
                    "Download",
                    icon="download",
                    on_click=download_markdown,
                ).props("flat dense")
                ui.button("Refresh", icon="refresh").props("flat dense")
        
        if content:
            # Scrollable card (1fr - fills remaining space)
            with ui.card().classes("w-full").style(
                f"border-left: 4px solid {DBT_TEAL}; overflow: hidden; min-height: 0;"
            ):
                with ui.scroll_area().classes("w-full h-full"):
                    ui.markdown(content).classes("prose dark:prose-invert max-w-none text-sm p-4")
        else:
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("description", size="2rem").classes("text-slate-400")
                ui.label("No report file found").classes("text-slate-500 mt-2")


def _create_entities_tab(report_items: list, state: AppState, save_state: Callable[[], None]) -> None:
    """Create the Entities tab with AGGrid table."""
    from importer.web.components.entity_table import create_entity_table
    
    with ui.element("div").style(
        "display: grid; "
        "grid-template-rows: 1fr; "
        "width: 100%; "
        "height: 100%; "
        "overflow: hidden;"
    ):
        if not report_items:
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("table_chart", size="2rem").classes("text-slate-400")
                ui.label("No entity data available").classes("text-slate-500 mt-2")
                ui.label("Run the Fetch Target step to load target account entities.").classes("text-sm text-slate-400")
            return
        
        # Create the entity table component (fills available space) - pass is_target=True
        create_entity_table(report_items, state, save_state, is_target=True)


def _create_charts_tab(report_items: list, state: AppState) -> None:
    """Create the Charts tab with visualizations."""
    from importer.web.components.charts import create_charts
    
    with ui.scroll_area().classes("w-full h-full"):
        with ui.column().classes("w-full gap-4 p-2"):
            if not report_items:
                with ui.card().classes("w-full p-6 text-center"):
                    ui.icon("bar_chart", size="2rem").classes("text-slate-400")
                    ui.label("No data available for charts").classes("text-slate-500 mt-2")
                return
            
            # Pass is_target=True to use teal color palette
            create_charts(report_items, state, is_target=True)


def _create_erd_tab(report_items: list, state: AppState) -> None:
    """Create the ERD tab with interactive graph visualization."""
    from importer.web.components.erd_viewer import create_erd_viewer
    from importer.web.components.entity_table import show_entity_detail_dialog

    # #region agent log
    import json as _json
    import time as _time

    def _log_debug(message: str, data: dict) -> None:
        with open(
            "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log",
            "a",
            encoding="utf-8",
        ) as _f:
            _f.write(
                _json.dumps(
                    {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H7",
                        "location": "explore_target.py:_create_erd_tab",
                        "message": message,
                        "data": data,
                        "timestamp": int(_time.time() * 1000),
                    }
                )
                + "\n"
            )

    _log_debug(
        "ERD tab render",
        {"report_items_count": len(report_items), "has_items": bool(report_items)},
    )
    # #endregion
    
    def on_node_click(node_data: dict):
        """Handle node click to show entity details."""
        # Find the corresponding report item
        node_key = node_data.get("id")
        for item in report_items:
            if item.get("key") == node_key:
                show_entity_detail_dialog(item, state)
                break
    
    with ui.element("div").style(
        "display: grid; "
        "grid-template-rows: 1fr; "
        "width: 100%; "
        "height: 100%; "
        "overflow: hidden;"
    ):
        if not report_items:
            # #region agent log
            _log_debug("ERD tab empty state", {})
            # #endregion
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("account_tree", size="2rem").classes("text-slate-400")
                ui.label("No entity data available for ERD").classes("text-slate-500 mt-2")
                ui.label("Run the Fetch Target step to load account entities.").classes("text-sm text-slate-400")
            return
        
        # #region agent log
        _log_debug("ERD viewer create start", {})
        # #endregion
        create_erd_viewer(report_items, on_node_click=on_node_click, is_target=True)
        # #region agent log
        _log_debug("ERD viewer create end", {})
        # #endregion


def _create_navigation(state: AppState, on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Create navigation buttons."""
    with ui.row().classes("w-full justify-between mt-4"):
        ui.button(
            f"Back to {state.get_step_label(WorkflowStep.FETCH_TARGET)}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.FETCH_TARGET),
        ).props("outline")
        
        ui.button(
            f"Continue to {state.get_step_label(WorkflowStep.MATCH)}",
            icon="arrow_forward",
            on_click=lambda: on_step_change(WorkflowStep.MATCH),
        ).style(f"background-color: {DBT_TEAL};")
