"""Job selection page for Jobs as Code Generator."""

import json
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, JACSubWorkflow, JACJobConfig
from importer.web.workflows.jobs_as_code.utils.job_fetcher import (
    parse_job_identifier,
    is_job_managed,
)
from importer.web.workflows.jobs_as_code.utils.yaml_generator import sanitize_identifier
from importer.web.workflows.jobs_as_code.utils.validator import deduplicate_identifiers


# dbt brand colors
DBT_ORANGE = "#FF694A"


def _show_job_detail_dialog(job: dict, config: Optional[JACJobConfig]) -> None:
    """Show a dialog with job details.
    
    Per AGGRID_NICEGUI_PATTERNS.md section 10.5, use tabbed dialog for complex details.
    
    Args:
        job: The full job dictionary from the API
        config: The job configuration (if any)
    """
    job_name = job.get("name", "Unknown Job")
    job_id = job.get("id", "N/A")
    
    # Extract nested data safely
    project = job.get("project") or {}
    environment = job.get("environment") or {}
    schedule = job.get("schedule") or {}
    settings = job.get("settings") or {}
    execution = job.get("execution") or {}
    triggers = job.get("triggers") or {}
    
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl").style("height: 80vh;"):
        # Header with close button (per pattern 10.1)
        with ui.row().classes("w-full items-center justify-between p-4 border-b"):
            with ui.column().classes("gap-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("work", size="md").style(f"color: {DBT_ORANGE};")
                    ui.label(job_name).classes("text-xl font-bold")
                with ui.row().classes("items-center gap-2"):
                    ui.badge(f"ID: {job_id}", color="grey").props("outline")
                    ui.badge(job.get("job_type", "scheduled"), color="blue").props("outline")
                    if config and config.is_managed:
                        ui.badge("Managed", color="green").props("outline")
            
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")
        
        # Tabs (per pattern 10.5)
        with ui.tabs().classes("w-full") as tabs:
            summary_tab = ui.tab("Summary", icon="summarize")
            execution_tab = ui.tab("Execution", icon="play_arrow")
            schedule_tab = ui.tab("Schedule", icon="schedule")
            json_tab = ui.tab("JSON", icon="code")
        
        # Tab panels
        with ui.tab_panels(tabs, value=summary_tab).classes("w-full flex-1"):
            # Summary tab
            with ui.tab_panel(summary_tab):
                with ui.scroll_area().style("height: 55vh;"):
                    with ui.column().classes("w-full gap-4 p-2"):
                        # Basic Info
                        with ui.card().classes("w-full p-4"):
                            ui.label("Basic Information").classes("font-semibold mb-2")
                            with ui.grid(columns=2).classes("w-full gap-2"):
                                ui.label("Job ID:").classes("text-slate-500")
                                ui.label(str(job_id)).classes("font-mono")
                                
                                ui.label("Job Type:").classes("text-slate-500")
                                ui.label(job.get("job_type", "scheduled"))
                                
                                ui.label("State:").classes("text-slate-500")
                                state_val = job.get("state", 1)
                                state_text = "Active" if state_val == 1 else "Paused"
                                ui.label(state_text).classes(
                                    "text-green-600" if state_val == 1 else "text-amber-600"
                                )
                                
                                ui.label("Identifier:").classes("text-slate-500")
                                ui.label(config.identifier if config else "N/A").classes("font-mono")
                        
                        # Project & Environment
                        with ui.card().classes("w-full p-4"):
                            ui.label("Project & Environment").classes("font-semibold mb-2")
                            with ui.grid(columns=2).classes("w-full gap-2"):
                                ui.label("Project:").classes("text-slate-500")
                                project_name = project.get("name") or f"Project {job.get('project_id', 'N/A')}"
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(project_name)
                                    ui.badge(f"ID: {job.get('project_id', 'N/A')}", color="grey").props(
                                        "outline dense"
                                    )
                                
                                ui.label("Environment:").classes("text-slate-500")
                                env_name = environment.get("name") or f"Env {job.get('environment_id', 'N/A')}"
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(env_name)
                                    ui.badge(f"ID: {job.get('environment_id', 'N/A')}", color="grey").props(
                                        "outline dense"
                                    )
                                
                                ui.label("Account ID:").classes("text-slate-500")
                                ui.label(str(job.get("account_id", "N/A"))).classes("font-mono")
                        
                        # Triggers
                        with ui.card().classes("w-full p-4"):
                            ui.label("Triggers").classes("font-semibold mb-2")
                            with ui.grid(columns=2).classes("w-full gap-2"):
                                ui.label("Scheduled:").classes("text-slate-500")
                                scheduled = triggers.get("schedule", False)
                                ui.icon(
                                    "check_circle" if scheduled else "cancel",
                                    size="sm"
                                ).classes("text-green-500" if scheduled else "text-slate-400")
                                
                                ui.label("GitHub Webhook:").classes("text-slate-500")
                                github = triggers.get("github_webhook", False)
                                ui.icon(
                                    "check_circle" if github else "cancel",
                                    size="sm"
                                ).classes("text-green-500" if github else "text-slate-400")
                                
                                ui.label("Git Provider Webhook:").classes("text-slate-500")
                                git_provider = triggers.get("git_provider_webhook", False)
                                ui.icon(
                                    "check_circle" if git_provider else "cancel",
                                    size="sm"
                                ).classes("text-green-500" if git_provider else "text-slate-400")
                                
                                ui.label("On Merge:").classes("text-slate-500")
                                on_merge = triggers.get("on_merge", False)
                                ui.icon(
                                    "check_circle" if on_merge else "cancel",
                                    size="sm"
                                ).classes("text-green-500" if on_merge else "text-slate-400")
            
            # Execution tab
            with ui.tab_panel(execution_tab):
                with ui.scroll_area().style("height: 55vh;"):
                    with ui.column().classes("w-full gap-4 p-2"):
                        # Execute Steps
                        with ui.card().classes("w-full p-4"):
                            ui.label("Execute Steps").classes("font-semibold mb-2")
                            steps = job.get("execute_steps") or ["dbt build"]
                            for i, step in enumerate(steps, 1):
                                with ui.row().classes("items-center gap-2"):
                                    ui.badge(str(i), color="orange")
                                    ui.code(step).classes("text-sm")
                        
                        # Execution Settings
                        with ui.card().classes("w-full p-4"):
                            ui.label("Execution Settings").classes("font-semibold mb-2")
                            with ui.grid(columns=2).classes("w-full gap-2"):
                                ui.label("Generate Docs:").classes("text-slate-500")
                                ui.label("Yes" if job.get("generate_docs", False) else "No")
                                
                                ui.label("Run Generate Sources:").classes("text-slate-500")
                                ui.label("Yes" if job.get("run_generate_sources", False) else "No")
                                
                                ui.label("Timeout (seconds):").classes("text-slate-500")
                                ui.label(str(execution.get("timeout_seconds", 0)))
                                
                                ui.label("Threads Override:").classes("text-slate-500")
                                ui.label(str(settings.get("threads", "Default")))
                                
                                ui.label("Target Name:").classes("text-slate-500")
                                ui.label(settings.get("target_name") or "Default")
                        
                        # Deferring
                        with ui.card().classes("w-full p-4"):
                            ui.label("Deferring").classes("font-semibold mb-2")
                            with ui.grid(columns=2).classes("w-full gap-2"):
                                ui.label("Deferring Job ID:").classes("text-slate-500")
                                ui.label(str(job.get("deferring_job_definition_id") or "None"))
                                
                                ui.label("Deferring Env ID:").classes("text-slate-500")
                                ui.label(str(job.get("deferring_environment_id") or "None"))
            
            # Schedule tab
            with ui.tab_panel(schedule_tab):
                with ui.scroll_area().style("height: 55vh;"):
                    with ui.column().classes("w-full gap-4 p-2"):
                        with ui.card().classes("w-full p-4"):
                            ui.label("Schedule Configuration").classes("font-semibold mb-2")
                            
                            if not schedule:
                                ui.label("No schedule configured").classes("text-slate-500 italic")
                            else:
                                with ui.grid(columns=2).classes("w-full gap-2"):
                                    ui.label("Cron:").classes("text-slate-500")
                                    cron = schedule.get("cron", "N/A")
                                    ui.code(cron).classes("text-sm")
                                    
                                    date_info = schedule.get("date") or {}
                                    ui.label("Type:").classes("text-slate-500")
                                    ui.label(date_info.get("type", "N/A"))
                                    
                                    time_info = schedule.get("time") or {}
                                    ui.label("Interval:").classes("text-slate-500")
                                    ui.label(str(time_info.get("interval", "N/A")))
            
            # JSON tab
            with ui.tab_panel(json_tab):
                formatted_json = json.dumps(job, indent=2, default=str)
                with ui.column().classes("w-full gap-2"):
                    # Copy button (per pattern 10.5)
                    with ui.row().classes("w-full justify-end p-2"):
                        ui.button(
                            "Copy",
                            icon="content_copy",
                            on_click=lambda: (
                                ui.run_javascript(
                                    f"navigator.clipboard.writeText({json.dumps(formatted_json)})"
                                ),
                                ui.notify("Copied to clipboard", type="positive"),
                            ),
                        ).props("flat dense")
                    
                    with ui.scroll_area().style("height: 50vh;"):
                        ui.code(formatted_json, language="json").classes("w-full text-xs")
    
    # Open dialog after definition (per pattern 10.1)
    dialog.open()


def create_jac_jobs_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the job selection page.
    
    Users select which jobs to include and configure identifiers.
    
    Args:
        state: Application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to save state
    """
    jac = state.jobs_as_code
    
    # Convert Observable types to plain Python for AG Grid compatibility
    jobs = [dict(j) for j in jac.source_jobs]
    
    # Initialize job configs if needed
    if not jac.job_configs:
        _initialize_job_configs(jac)
    
    # Build lookup
    config_by_id = {c.job_id: c for c in jac.job_configs}
    
    # Build rows once at page load
    rows = []
    for job in jobs:
        job_id = job.get("id")
        job_name = job.get("name", "")
        
        existing_id, clean_name = parse_job_identifier(job_name)
        managed = existing_id is not None
        
        config = config_by_id.get(job_id)
        identifier = config.identifier if config else sanitize_identifier(clean_name or job_name)
        
        # Handle case where project/environment might be None
        project = job.get("project") or {}
        environment = job.get("environment") or {}
        
        project_name = (
            project.get("name") if isinstance(project, dict) else None
        ) or f"Project {job.get('project_id', 'N/A')}"
        
        env_name = (
            environment.get("name") if isinstance(environment, dict) else None
        ) or f"Env {job.get('environment_id', 'N/A')}"
        
        rows.append({
            "id": job_id,
            "name": clean_name or job_name,
            "project_name": project_name,
            "project_id": job.get("project_id"),
            "environment_name": env_name,
            "environment_id": job.get("environment_id"),
            "job_type": job.get("job_type", "scheduled"),
            "identifier": identifier,
            "is_managed": managed,
            "selected": job_id in jac.selected_job_ids,
        })
    
    with ui.column().classes("w-full max-w-6xl mx-auto p-8 gap-6"):
        # Header
        with ui.card().classes("w-full p-6"):
            with ui.row().classes("items-center gap-3 mb-2"):
                ui.icon("checklist", size="lg").style(f"color: {DBT_ORANGE};")
                ui.label("Select Jobs").classes("text-2xl font-bold")
            
            workflow_label = (
                "Adopt Existing Jobs" if jac.sub_workflow == JACSubWorkflow.ADOPT 
                else "Clone / Migrate Jobs"
            )
            ui.badge(workflow_label, color="orange").props("outline")
            
            ui.markdown("""
                Select the jobs you want to include and configure their identifiers.
                The identifier becomes the YAML key for each job.
                
                **Tip:** Click on any row to view full job details.
            """).classes("text-slate-600 dark:text-slate-400 mt-3")
        
        # Selection summary
        selected_count = len(jac.selected_job_ids)
        managed_count = sum(
            1 for job in jobs 
            if job.get("id") in jac.selected_job_ids and is_job_managed(job)
        )
        
        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-4"):
                    ui.label(f"{selected_count} of {len(jobs)} jobs selected").classes(
                        "text-lg font-semibold"
                    )
                    
                    if managed_count > 0:
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("info", size="sm").classes("text-amber-500")
                            ui.label(f"{managed_count} already managed").classes(
                                "text-sm text-amber-600"
                            )
                
                with ui.row().classes("gap-2"):
                    def select_all():
                        jac.selected_job_ids = set(job.get("id") for job in jobs)
                        for config in jac.job_configs:
                            config.selected = True
                        save_state()
                        ui.navigate.reload()
                    
                    def deselect_all():
                        jac.selected_job_ids = set()
                        for config in jac.job_configs:
                            config.selected = False
                        save_state()
                        ui.navigate.reload()
                    
                    ui.button("Select All", on_click=select_all).props("outline size=sm")
                    ui.button("Deselect All", on_click=deselect_all).props("outline size=sm")
        
        # AG Grid columns - per AGGRID_NICEGUI_PATTERNS.md, always use explicit colId
        # Note: Using rowSelection.checkboxes instead of checkboxSelection column
        columns = [
            {
                "field": "name",
                "colId": "name",  # Explicit colId prevents phantom columns
                "headerName": "Job Name",
                "minWidth": 200,
                "filter": "agTextColumnFilter",
                "sortable": True,
            },
            {
                "field": "project_name",
                "colId": "project_name",
                "headerName": "Project",
                "minWidth": 180,
                "filter": "agTextColumnFilter",
                "sortable": True,
            },
            {
                "field": "project_id",
                "colId": "project_id",
                "headerName": "Proj ID",
                "width": 80,
                "filter": "agNumberColumnFilter",
                "sortable": True,
                "cellStyle": {"fontFamily": "monospace", "fontSize": "11px"},
            },
            {
                "field": "environment_name",
                "colId": "environment_name",
                "headerName": "Environment",
                "minWidth": 150,
                "filter": "agTextColumnFilter",
                "sortable": True,
            },
            {
                "field": "job_type",
                "colId": "job_type",
                "headerName": "Type",
                "width": 100,
                "filter": "agTextColumnFilter",
                "sortable": True,
            },
            {
                "field": "identifier",
                "colId": "identifier",
                "headerName": "Identifier",
                "minWidth": 150,
                "editable": True,
                "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
            },
            {
                "field": "is_managed",
                "colId": "is_managed",
                "headerName": "Managed",
                "width": 90,
                # Use cellDataType to prevent boolean from rendering as checkbox
                "cellDataType": False,
                ":valueFormatter": "params => params.value ? '✓ Yes' : ''",
                "cellClassRules": {
                    "text-green-600": "x === true",
                },
            },
        ]
        
        # Build job lookup for detail dialog
        jobs_by_id = {job.get("id"): job for job in jobs}
        
        # Pre-selected job IDs based on state
        pre_selected_ids = set(jac.selected_job_ids)
        all_selected = pre_selected_ids and len(pre_selected_ids) == len(rows)
        
        # Create AG Grid with all recommended options per AGGRID_NICEGUI_PATTERNS.md
        grid = ui.aggrid({
            "columnDefs": columns,
            "rowData": rows,
            "rowSelection": {
                "mode": "multiRow",
                "headerCheckbox": True,
                "checkboxes": True,
            },
            "suppressRowClickSelection": True,  # Only checkbox selects, not row click
            "animateRows": False,  # Stability (pattern 8.3)
            "pagination": True,
            "paginationPageSize": 25,
            "paginationPageSizeSelector": [25, 50, 100],
            "headerHeight": 36,
            "defaultColDef": {
                "sortable": True,
                "resizable": True,
                "filter": True,
                "minWidth": 80,
            },
            "stopEditingWhenCellsLoseFocus": True,  # Important for editable cells (pattern 4.2)
        }, theme="quartz").classes("w-full ag-theme-quartz-auto-dark").style("height: 400px;")
        
        # Pre-select rows based on saved state
        if all_selected:
            # If all rows are selected, use selectAll() for simplicity
            async def select_all_rows():
                await grid.run_grid_method("selectAll")
            ui.timer(0.1, select_all_rows, once=True)
        elif pre_selected_ids:
            # For partial selection, we need to select specific rows
            # Use JavaScript to select by IDs
            ids_list = list(pre_selected_ids)
            js_code = f"""
                const selectedIds = {ids_list};
                getElement({grid.id}).gridOptions.api.forEachNode(node => {{
                    if (selectedIds.includes(node.data.id)) {{
                        node.setSelected(true);
                    }}
                }});
            """
            ui.timer(0.2, lambda: ui.run_javascript(js_code), once=True)
        
        # Add CSS for cell class rules
        ui.add_css("""
            .text-green-600 { color: #059669 !important; font-weight: 600; }
            .dark .text-green-600, .body--dark .text-green-600 { color: #6EE7B7 !important; }
        """)
        
        # Handle selection changes
        async def handle_selection():
            selected = await grid.get_selected_rows()
            selected_ids = set(row["id"] for row in selected)
            
            # Update state
            jac.selected_job_ids = selected_ids
            for config in jac.job_configs:
                config.selected = config.job_id in selected_ids
            save_state()
        
        grid.on("selectionChanged", lambda: handle_selection())
        
        # Handle cell click - show detail dialog (pattern 10.2)
        def handle_cell_click(e):
            # Skip checkbox column clicks (pattern 4.3)
            if e.args and e.args.get("colId") == "_checkbox":
                return
            
            if e.args and "data" in e.args:
                row_data = e.args["data"]
                job_id = row_data.get("id")
                
                # Get full job data for the dialog
                full_job = jobs_by_id.get(job_id)
                if full_job:
                    config = config_by_id.get(job_id)
                    _show_job_detail_dialog(full_job, config)
        
        grid.on("cellClicked", handle_cell_click)
        
        # Handle identifier edits
        async def handle_cell_edit(e):
            data = e.args.get("data", {})
            job_id = data.get("id")
            new_identifier = data.get("identifier", "")
            
            config = config_by_id.get(job_id)
            if config:
                config.identifier = new_identifier
                save_state()
        
        grid.on("cellValueChanged", handle_cell_edit)
        
        # Navigation
        with ui.row().classes("w-full justify-between items-center mt-4"):
            ui.button(
                "Back",
                icon="arrow_back",
                on_click=lambda: on_step_change(WorkflowStep.JAC_FETCH),
            ).props("outline")
            
            # Determine next step based on workflow
            if jac.sub_workflow == JACSubWorkflow.CLONE:
                next_step = WorkflowStep.JAC_TARGET
                next_label = "Configure Target"
            else:
                next_step = WorkflowStep.JAC_CONFIG
                next_label = "Configure Jobs"
            
            continue_btn = ui.button(
                next_label,
                icon="arrow_forward",
                on_click=lambda: on_step_change(next_step),
            ).props("size=lg").style(f"background-color: {DBT_ORANGE};")
            
            if len(jac.selected_job_ids) == 0:
                continue_btn.disable()


def _initialize_job_configs(jac) -> None:
    """Initialize job configs from fetched jobs.
    
    Automatically deduplicates identifiers by appending numeric suffixes.
    Stores warnings for any auto-renamed identifiers.
    """
    jobs = jac.source_jobs
    configs = []
    
    for job in jobs:
        job_id = job.get("id")
        job_name = job.get("name", "")
        
        existing_id, clean_name = parse_job_identifier(job_name)
        
        config = JACJobConfig(
            job_id=job_id,
            original_name=clean_name or job_name,
            new_name=clean_name or job_name,
            identifier=existing_id or sanitize_identifier(clean_name or job_name),
            selected=False,
            is_managed=existing_id is not None,
        )
        configs.append(config)
    
    # Deduplicate identifiers (auto-append suffixes for duplicates)
    configs, warnings = deduplicate_identifiers(configs)
    
    # Store warnings as strings for display
    jac.identifier_warnings = [str(w) for w in warnings]
    jac.job_configs = configs
