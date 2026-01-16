"""Fetch jobs page for Jobs as Code Generator."""

from typing import Callable

from nicegui import ui

from importer.web.state import AppState, WorkflowStep, JACSubWorkflow
from importer.web.components.credential_form import create_source_credential_form
from importer.web.env_manager import load_source_credentials, save_source_credentials
from importer.web.workflows.jobs_as_code.utils.job_fetcher import (
    fetch_jobs_from_api,
    extract_projects_from_jobs,
    extract_environments_from_jobs,
    JobFetchError,
)


# dbt brand colors
DBT_ORANGE = "#FF694A"


def create_jac_fetch_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the fetch jobs page.
    
    Users enter credentials and fetch jobs from their dbt Cloud account.
    
    Args:
        state: Application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to save state
    """
    jac = state.jobs_as_code
    
    # Containers for dynamic content
    fetch_status_container = {"element": None}
    stats_container = {"element": None}
    
    with ui.column().classes("w-full max-w-4xl mx-auto p-8 gap-6"):
        # Header
        with ui.card().classes("w-full p-6"):
            with ui.row().classes("items-center gap-3 mb-2"):
                ui.icon("cloud_download", size="lg").style(f"color: {DBT_ORANGE};")
                ui.label("Fetch Jobs from dbt Cloud").classes("text-2xl font-bold")
            
            workflow_label = (
                "Adopt Existing Jobs" if jac.sub_workflow == JACSubWorkflow.ADOPT 
                else "Clone / Migrate Jobs"
            )
            ui.badge(workflow_label, color="orange").props("outline")
            
            ui.markdown("""
                Enter your dbt Cloud credentials to fetch all jobs from your account.
                You'll be able to select which jobs to include in the next step.
            """).classes("text-slate-600 dark:text-slate-400 mt-3")
        
        # Credentials form
        def on_load_env():
            """Load credentials from .env file."""
            try:
                creds = load_source_credentials()
                if creds:
                    state.source_credentials.host_url = creds.get("host_url", "https://cloud.getdbt.com")
                    state.source_credentials.account_id = creds.get("account_id", "")
                    state.source_credentials.api_token = creds.get("api_token", "")
                    state.source_credentials.token_type = creds.get("token_type", "service_token")
                    save_state()
                    ui.notify("Loaded credentials from .env", type="positive")
                    ui.navigate.reload()
                else:
                    ui.notify("No credentials found in .env", type="warning")
            except Exception as e:
                ui.notify(f"Error loading .env: {str(e)}", type="negative")
        
        def on_load_env_content(content: str, filename: str):
            """Load credentials from uploaded file content."""
            try:
                # Parse .env content
                creds = {}
                for line in content.split("\n"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        if key == "DBT_CLOUD_HOST_URL":
                            creds["host_url"] = value
                        elif key == "DBT_CLOUD_ACCOUNT_ID":
                            creds["account_id"] = value
                        elif key == "DBT_CLOUD_API_KEY":
                            creds["api_token"] = value
                
                if creds:
                    from importer.web.env_manager import detect_token_type
                    state.source_credentials.host_url = creds.get("host_url", "https://cloud.getdbt.com")
                    state.source_credentials.account_id = creds.get("account_id", "")
                    state.source_credentials.api_token = creds.get("api_token", "")
                    state.source_credentials.token_type = detect_token_type(creds.get("api_token", ""))
                    save_state()
                    ui.notify(f"Loaded credentials from {filename}", type="positive")
                    ui.navigate.reload()
                else:
                    ui.notify("No valid credentials found in file", type="warning")
            except Exception as e:
                ui.notify(f"Error parsing file: {str(e)}", type="negative")
        
        def on_save_env():
            """Save credentials to .env file."""
            try:
                save_source_credentials(
                    host_url=state.source_credentials.host_url,
                    account_id=state.source_credentials.account_id,
                    api_token=state.source_credentials.api_token,
                )
                ui.notify("Saved credentials to .env", type="positive")
            except Exception as e:
                ui.notify(f"Error saving .env: {str(e)}", type="negative")
        
        create_source_credential_form(
            state,
            on_load_env=on_load_env,
            on_load_env_content=on_load_env_content,
            on_save_env=on_save_env,
        )
        
        # Fetch status area
        with ui.card().classes("w-full") as status_card:
            fetch_status_container["element"] = status_card
            
            if jac.fetch_complete and jac.source_jobs:
                _show_fetch_complete(jac)
            elif jac.fetch_error:
                _show_fetch_error(jac.fetch_error)
            else:
                _show_fetch_ready()
        
        # Fetch button and navigation
        with ui.row().classes("w-full justify-between items-center"):
            ui.button(
                "Back",
                icon="arrow_back",
                on_click=lambda: on_step_change(WorkflowStep.JAC_SELECT),
            ).props("outline")
            
            with ui.row().classes("gap-4"):
                # Create buttons first so we can reference them in async function
                fetch_btn = ui.button(
                    "Fetch Jobs",
                    icon="cloud_download",
                ).props("size=lg")
                
                continue_btn = ui.button(
                    "Continue",
                    icon="arrow_forward",
                    on_click=lambda: on_step_change(WorkflowStep.JAC_JOBS),
                ).props("size=lg").style(f"background-color: {DBT_ORANGE};")
                
                if jac.is_fetching:
                    fetch_btn.disable()
                
                if not jac.fetch_complete:
                    continue_btn.disable()
                
                async def do_fetch():
                    """Perform the fetch operation."""
                    creds = state.source_credentials
                    
                    # Validate credentials
                    if not creds.host_url or not creds.account_id or not creds.api_token:
                        ui.notify("Please fill in all credential fields", type="warning")
                        return
                    
                    jac.is_fetching = True
                    jac.fetch_error = None
                    fetch_btn.disable()
                    save_state()
                    
                    # Update UI
                    with fetch_status_container["element"]:
                        fetch_status_container["element"].clear()
                        with ui.row().classes("items-center gap-3"):
                            ui.spinner(size="lg").style(f"color: {DBT_ORANGE};")
                            ui.label("Fetching jobs from dbt Cloud...").classes("text-lg")
                    
                    try:
                        # Fetch jobs
                        jobs = fetch_jobs_from_api(
                            host_url=creds.host_url,
                            account_id=creds.account_id,
                            api_token=creds.api_token,
                        )
                        
                        # Extract projects and environments
                        projects = extract_projects_from_jobs(jobs)
                        environments = extract_environments_from_jobs(jobs)
                        
                        # Update state
                        jac.source_jobs = jobs
                        jac.source_projects = projects
                        jac.source_environments = environments
                        jac.fetch_complete = True
                        jac.is_fetching = False
                        save_state()
                        
                        # Update UI
                        with fetch_status_container["element"]:
                            fetch_status_container["element"].clear()
                            _show_fetch_complete(jac)
                        
                        # Enable continue button
                        fetch_btn.enable()
                        continue_btn.enable()
                        
                        ui.notify(f"Fetched {len(jobs)} jobs successfully!", type="positive")
                        
                    except JobFetchError as e:
                        jac.fetch_error = str(e)
                        jac.is_fetching = False
                        fetch_btn.enable()
                        save_state()
                        
                        with fetch_status_container["element"]:
                            fetch_status_container["element"].clear()
                            _show_fetch_error(str(e))
                        
                        ui.notify(f"Fetch failed: {str(e)}", type="negative")
                        
                    except Exception as e:
                        jac.fetch_error = f"Unexpected error: {str(e)}"
                        jac.is_fetching = False
                        fetch_btn.enable()
                        save_state()
                        
                        with fetch_status_container["element"]:
                            fetch_status_container["element"].clear()
                            _show_fetch_error(f"Unexpected error: {str(e)}")
                        
                        ui.notify(f"Error: {str(e)}", type="negative")
                
                fetch_btn.on("click", do_fetch)


def _show_fetch_ready() -> None:
    """Show the ready-to-fetch state."""
    with ui.row().classes("items-center gap-3"):
        ui.icon("info", size="md").classes("text-blue-500")
        ui.label("Enter your credentials and click 'Fetch Jobs' to get started.").classes(
            "text-slate-600"
        )


def _show_fetch_complete(jac) -> None:
    """Show fetch completion statistics."""
    jobs = jac.source_jobs
    projects = jac.source_projects
    environments = jac.source_environments
    
    # Count managed jobs
    from importer.web.workflows.jobs_as_code.utils.job_fetcher import is_job_managed
    managed_count = sum(1 for job in jobs if is_job_managed(job))
    
    with ui.column().classes("gap-4"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("check_circle", size="md").classes("text-green-500")
            ui.label("Jobs fetched successfully!").classes("text-lg font-semibold text-green-600")
        
        with ui.row().classes("gap-8"):
            _stat_card("Jobs", str(len(jobs)), "work")
            _stat_card("Projects", str(len(projects)), "folder")
            _stat_card("Environments", str(len(environments)), "dns")
            _stat_card("Already Managed", str(managed_count), "link")


def _show_fetch_error(error: str) -> None:
    """Show fetch error."""
    with ui.column().classes("gap-2"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("error", size="md").classes("text-red-500")
            ui.label("Fetch failed").classes("text-lg font-semibold text-red-600")
        
        ui.label(error).classes("text-sm text-red-500")
        
        ui.markdown("""
            **Common issues:**
            - Check your API token has read permissions
            - Verify the account ID is correct
            - Ensure the host URL matches your dbt Cloud instance
        """).classes("text-sm text-slate-500 mt-2")


def _stat_card(label: str, value: str, icon: str) -> None:
    """Create a small stat card."""
    with ui.card().classes("p-4"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon, size="sm").style(f"color: {DBT_ORANGE};")
            ui.label(label).classes("text-sm text-slate-500")
        ui.label(value).classes("text-2xl font-bold mt-1")
