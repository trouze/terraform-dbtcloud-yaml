"""Job selection grid component for Jobs as Code Generator."""

from typing import Callable, Optional

from nicegui import ui

from importer.web.state import JACJobConfig
from importer.web.workflows.jobs_as_code.utils.job_fetcher import parse_job_identifier
from importer.web.workflows.jobs_as_code.utils.yaml_generator import sanitize_identifier


# dbt brand colors
DBT_ORANGE = "#FF694A"


def create_job_grid(
    jobs: list[dict],
    job_configs: list[JACJobConfig],
    on_selection_change: Callable[[list[int]], None],
    on_identifier_change: Optional[Callable[[int, str], None]] = None,
    on_name_change: Optional[Callable[[int, str], None]] = None,
    show_new_name: bool = False,
    editable_identifiers: bool = True,
) -> ui.aggrid:
    """Create an AG Grid for job selection and configuration.
    
    Args:
        jobs: List of job dictionaries from API
        job_configs: List of job configurations
        on_selection_change: Callback when selection changes (receives list of job IDs)
        on_identifier_change: Callback when identifier is edited
        on_name_change: Callback when new name is edited (clone workflow)
        show_new_name: Whether to show the "New Name" column (clone workflow)
        editable_identifiers: Whether identifiers can be edited
        
    Returns:
        AG Grid element
    """
    # Build row data
    rows = []
    config_by_id = {c.job_id: c for c in job_configs}
    
    for job in jobs:
        job_id = job.get("id")
        job_name = job.get("name", "")
        
        # Check if already managed
        existing_identifier, clean_name = parse_job_identifier(job_name)
        is_managed = existing_identifier is not None
        
        # Get config if exists
        config = config_by_id.get(job_id)
        
        # Determine identifier
        if config and config.identifier:
            identifier = config.identifier
        elif existing_identifier:
            identifier = existing_identifier
        else:
            identifier = sanitize_identifier(clean_name or job_name)
        
        # Get project and environment info
        project = job.get("project", {})
        environment = job.get("environment", {})
        
        row = {
            "id": job_id,
            "name": clean_name or job_name,
            "project_name": project.get("name", f"Project {job.get('project_id', 'N/A')}"),
            "project_id": job.get("project_id"),
            "environment_name": environment.get("name", f"Env {job.get('environment_id', 'N/A')}"),
            "environment_id": job.get("environment_id"),
            "job_type": job.get("job_type", "scheduled"),
            "identifier": identifier,
            "new_name": config.new_name if config else job_name,
            "is_managed": is_managed,
            "has_schedule": job.get("triggers", {}).get("schedule", False),
            "has_webhook": (
                job.get("triggers", {}).get("github_webhook", False) or
                job.get("triggers", {}).get("git_provider_webhook", False)
            ),
        }
        rows.append(row)
    
    # Build column definitions - all columns must have explicit colId per ag-grid-standards.mdc
    columns = [
        {
            "field": "name",
            "colId": "name",
            "headerName": "Job Name",
            "flex": 2,
            "filter": "agTextColumnFilter",
            "cellRenderer": """function(params) {
                const managed = params.data.is_managed;
                const badge = managed ? '<span style="background: #10B981; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 8px;">Managed</span>' : '';
                return params.value + badge;
            }""",
        },
        {
            "field": "project_name",
            "colId": "project_name",
            "headerName": "Project",
            "flex": 1,
            "filter": "agTextColumnFilter",
        },
        {
            "field": "environment_name",
            "colId": "environment_name",
            "headerName": "Environment",
            "flex": 1,
            "filter": "agTextColumnFilter",
        },
        {
            "field": "job_type",
            "colId": "job_type",
            "headerName": "Type",
            "width": 100,
            "filter": "agSetColumnFilter",
            "cellRenderer": """function(params) {
                const icons = {
                    'scheduled': '📅',
                    'ci': '🔄',
                    'merge': '🔀',
                    'other': '📋'
                };
                return (icons[params.value] || '📋') + ' ' + params.value;
            }""",
        },
        {
            "field": "identifier",
            "colId": "identifier",
            "headerName": "Identifier",
            "flex": 1,
            "editable": editable_identifiers,
            "cellStyle": {"fontFamily": "monospace"},
        },
    ]
    
    # Add new name column for clone workflow
    if show_new_name:
        columns.insert(1, {
            "field": "new_name",
            "colId": "new_name",
            "headerName": "New Name",
            "flex": 2,
            "editable": True,
        })
    
    # Create grid options - using AG Grid v32+ row selection API per ag-grid-standards.mdc
    grid_options = {
        "columnDefs": columns,
        "rowData": rows,
        "rowSelection": {
            "mode": "multiRow",
            "headerCheckbox": True,
            "checkboxes": True,
        },
        "suppressRowClickSelection": True,
        "animateRows": False,  # Stability - per ag-grid-standards.mdc
        "defaultColDef": {
            "sortable": True,
            "resizable": True,
            "filter": True,
        },
        "stopEditingWhenCellsLoseFocus": True,
        # Note: getRowId removed - can cause issues with NiceGUI's AG Grid wrapper
        "domLayout": "autoHeight",
    }
    
    grid = ui.aggrid(grid_options, theme="quartz").classes("w-full ag-theme-quartz-auto-dark")
    
    # Handle selection changes
    async def handle_selection():
        selected = await grid.get_selected_rows()
        selected_ids = [row["id"] for row in selected]
        on_selection_change(selected_ids)
    
    grid.on("selectionChanged", lambda: handle_selection())
    
    # Handle cell edits
    if on_identifier_change or on_name_change:
        async def handle_cell_edit(e):
            data = e.args.get("data", {})
            col = e.args.get("colId")
            job_id = data.get("id")
            
            if col == "identifier" and on_identifier_change:
                on_identifier_change(job_id, data.get("identifier", ""))
            elif col == "new_name" and on_name_change:
                on_name_change(job_id, data.get("new_name", ""))
        
        grid.on("cellValueChanged", handle_cell_edit)
    
    return grid


def create_job_filter_controls(
    projects: dict[int, str],
    environments: dict[int, dict],
    on_filter_change: Callable[[Optional[int], Optional[int], Optional[str]], None],
) -> None:
    """Create filter controls for the job grid.
    
    Args:
        projects: Dictionary of project_id -> project_name
        environments: Dictionary of environment_id -> environment info
        on_filter_change: Callback when filters change (project_id, env_id, job_type)
    """
    with ui.row().classes("w-full gap-4 items-end"):
        # Project filter
        project_options = {"": "All Projects"}
        project_options.update({str(k): v for k, v in projects.items()})
        
        project_select = ui.select(
            label="Filter by Project",
            options=project_options,
            value="",
        ).classes("min-w-[200px]").props("outlined dense")
        
        # Environment filter
        env_options = {"": "All Environments"}
        env_options.update({str(k): v["name"] for k, v in environments.items()})
        
        env_select = ui.select(
            label="Filter by Environment",
            options=env_options,
            value="",
        ).classes("min-w-[200px]").props("outlined dense")
        
        # Job type filter
        type_options = {
            "": "All Types",
            "scheduled": "Scheduled",
            "ci": "CI",
            "merge": "Merge",
            "other": "Other",
        }
        
        type_select = ui.select(
            label="Filter by Type",
            options=type_options,
            value="",
        ).classes("min-w-[150px]").props("outlined dense")
        
        # Search box
        ui.input(
            label="Search",
            placeholder="Search job names...",
        ).classes("min-w-[200px]").props("outlined dense clearable")
        
        def update_filters():
            project_id = int(project_select.value) if project_select.value else None
            env_id = int(env_select.value) if env_select.value else None
            job_type = type_select.value if type_select.value else None
            on_filter_change(project_id, env_id, job_type)
        
        project_select.on("update:model-value", lambda: update_filters())
        env_select.on("update:model-value", lambda: update_filters())
        type_select.on("update:model-value", lambda: update_filters())


def create_selection_summary(
    total_jobs: int,
    selected_count: int,
    managed_count: int,
) -> None:
    """Create a summary bar showing selection statistics.
    
    Args:
        total_jobs: Total number of jobs
        selected_count: Number of selected jobs
        managed_count: Number of already-managed jobs in selection
    """
    with ui.row().classes("w-full items-center gap-4 py-2"):
        ui.label(f"{selected_count} of {total_jobs} jobs selected").classes(
            "text-lg font-semibold"
        )
        
        if managed_count > 0:
            with ui.row().classes("items-center gap-1"):
                ui.icon("info", size="sm").classes("text-amber-500")
                ui.label(f"{managed_count} already managed").classes(
                    "text-sm text-amber-600"
                )


def create_export_button(grid: ui.aggrid, filename: str = "jobs_export.csv") -> ui.button:
    """Create an export CSV button for a grid.
    
    Args:
        grid: The AG Grid instance to export from
        filename: The filename for the CSV export
        
    Returns:
        The export button element
    """
    def export_csv():
        grid.run_grid_method('exportDataAsCsv', {
            'fileName': filename,
            'columnSeparator': ',',
        })
    
    return ui.button(
        "Export CSV",
        icon="download",
        on_click=export_csv
    ).props("outline dense")
