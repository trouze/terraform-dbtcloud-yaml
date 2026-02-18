"""Target account configuration page for Jobs as Code Generator clone workflow."""

from typing import Callable

from nicegui import ui

from importer.web.state import AppState, WorkflowStep
from importer.web.components.credential_form import create_target_credential_form
from importer.web.env_manager import load_target_credentials, save_target_credentials, resolve_project_env_path, auto_seed_project_env
from importer.web.workflows.jobs_as_code.utils.job_fetcher import (
    fetch_jobs_from_api,
    extract_projects_from_jobs,
    extract_environments_from_jobs,
    JobFetchError,
)


# dbt brand colors
DBT_ORANGE = "#FF694A"


def create_jac_target_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the target account configuration page.
    
    For clone workflow: Users configure target account credentials
    and fetch available projects/environments.
    
    Args:
        state: Application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to save state
    """
    jac = state.jobs_as_code
    
    # Containers for dynamic content
    fetch_status_container = {"element": None}
    
    with ui.column().classes("w-full max-w-4xl mx-auto p-8 gap-6"):
        # Header
        with ui.card().classes("w-full p-6"):
            with ui.row().classes("items-center gap-3 mb-2"):
                ui.icon("flight_land", size="lg").style(f"color: {DBT_ORANGE};")
                ui.label("Configure Target Account").classes("text-2xl font-bold")
            
            ui.badge("Clone / Migrate Jobs", color="orange").props("outline")
            
            ui.markdown("""
                Configure the target account where cloned jobs will be created.
                You can use the same account (different project/environment) or a different account entirely.
            """).classes("text-slate-600 dark:text-slate-400 mt-3")
        
        # Same/Different account toggle
        with ui.card().classes("w-full"):
            ui.label("Target Account").classes("text-lg font-semibold mb-4")
            
            with ui.row().classes("gap-4"):
                def set_same_account(same: bool):
                    jac.target_same_account = same
                    save_state()
                    ui.navigate.reload()
                
                with ui.card().classes(
                    "p-4 cursor-pointer " + 
                    ("ring-2 ring-orange-400" if jac.target_same_account else "")
                ).on("click", lambda: set_same_account(True)):
                    with ui.row().classes("items-center gap-2"):
                        ui.radio(
                            options={"same": ""},
                            value="same" if jac.target_same_account else None,
                        ).props("dense")
                        ui.label("Same Account").classes("font-semibold")
                    
                    ui.label(
                        "Clone jobs to a different project or environment within the same account."
                    ).classes("text-sm text-slate-500 mt-2")
                
                with ui.card().classes(
                    "p-4 cursor-pointer " + 
                    ("ring-2 ring-orange-400" if not jac.target_same_account else "")
                ).on("click", lambda: set_same_account(False)):
                    with ui.row().classes("items-center gap-2"):
                        ui.radio(
                            options={"diff": ""},
                            value="diff" if not jac.target_same_account else None,
                        ).props("dense")
                        ui.label("Different Account").classes("font-semibold")
                    
                    ui.label(
                        "Migrate jobs to an entirely different dbt Cloud account."
                    ).classes("text-sm text-slate-500 mt-2")
        
        # Target credentials form (only for different account)
        if not jac.target_same_account:
            def on_load_env():
                """Load credentials from .env file."""
                try:
                    env_path = resolve_project_env_path(state.project_path, "target")
                    if env_path and not __import__('pathlib').Path(env_path).exists():
                        auto_seed_project_env(state.project_path, "target")
                    creds = load_target_credentials(env_path=env_path)
                    if creds:
                        state.target_credentials.host_url = creds.get("host_url", "https://cloud.getdbt.com")
                        state.target_credentials.account_id = creds.get("account_id", "")
                        state.target_credentials.api_token = creds.get("api_token", "")
                        state.target_credentials.token_type = creds.get("token_type", "service_token")
                        save_state()
                        ui.notify("Loaded credentials from .env", type="positive")
                        ui.navigate.reload()
                    else:
                        ui.notify("No target credentials found in .env", type="warning")
                except Exception as e:
                    ui.notify(f"Error loading .env: {str(e)}", type="negative")
            
            def on_load_env_content(content: str, filename: str):
                """Load credentials from uploaded file content."""
                try:
                    creds = {}
                    for line in content.split("\n"):
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            
                            if key == "DBT_CLOUD_TARGET_HOST_URL":
                                creds["host_url"] = value
                            elif key == "DBT_CLOUD_TARGET_ACCOUNT_ID":
                                creds["account_id"] = value
                            elif key == "DBT_CLOUD_TARGET_API_KEY":
                                creds["api_token"] = value
                    
                    if creds:
                        from importer.web.env_manager import detect_token_type
                        state.target_credentials.host_url = creds.get("host_url", "https://cloud.getdbt.com")
                        state.target_credentials.account_id = creds.get("account_id", "")
                        state.target_credentials.api_token = creds.get("api_token", "")
                        state.target_credentials.token_type = detect_token_type(creds.get("api_token", ""))
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
                    env_path = resolve_project_env_path(state.project_path, "target")
                    save_target_credentials(
                        host_url=state.target_credentials.host_url,
                        account_id=state.target_credentials.account_id,
                        api_token=state.target_credentials.api_token,
                        env_path=env_path,
                    )
                    ui.notify("Saved credentials to .env", type="positive")
                except Exception as e:
                    ui.notify(f"Error saving .env: {str(e)}", type="negative")
            
            create_target_credential_form(
                state,
                on_load_env=on_load_env,
                on_load_env_content=on_load_env_content,
                on_save_env=on_save_env,
            )
        
        # Fetch status area
        with ui.card().classes("w-full") as status_card:
            fetch_status_container["element"] = status_card
            
            if jac.target_fetch_complete:
                _show_fetch_complete(jac)
            else:
                _show_fetch_ready(jac.target_same_account)
        
        # Fetch button and navigation
        with ui.row().classes("w-full justify-between items-center"):
            ui.button(
                "Back",
                icon="arrow_back",
                on_click=lambda: on_step_change(WorkflowStep.JAC_JOBS),
            ).props("outline")
            
            with ui.row().classes("gap-4"):
                async def do_fetch():
                    """Perform the fetch operation."""
                    if jac.target_same_account:
                        # Use source credentials
                        creds = state.source_credentials
                    else:
                        # Use target credentials
                        creds = state.target_credentials
                    
                    # Validate credentials
                    if not creds.host_url or not creds.account_id or not creds.api_token:
                        ui.notify("Please fill in all credential fields", type="warning")
                        return
                    
                    # Update UI
                    with fetch_status_container["element"]:
                        fetch_status_container["element"].clear()
                        with ui.row().classes("items-center gap-3"):
                            ui.spinner(size="lg").style(f"color: {DBT_ORANGE};")
                            ui.label("Fetching target account data...").classes("text-lg")
                    
                    try:
                        # Fetch jobs to extract projects and environments
                        jobs = fetch_jobs_from_api(
                            host_url=creds.host_url,
                            account_id=creds.account_id,
                            api_token=creds.api_token,
                        )
                        
                        # Extract projects and environments
                        projects = extract_projects_from_jobs(jobs)
                        environments = extract_environments_from_jobs(jobs)
                        
                        # Update state
                        jac.target_jobs = jobs
                        jac.target_projects = projects
                        jac.target_environments = environments
                        jac.target_fetch_complete = True
                        save_state()
                        
                        # Update UI
                        with fetch_status_container["element"]:
                            fetch_status_container["element"].clear()
                            _show_fetch_complete(jac)
                        
                        ui.notify("Target account data fetched successfully!", type="positive")
                        
                    except JobFetchError as e:
                        with fetch_status_container["element"]:
                            fetch_status_container["element"].clear()
                            _show_fetch_error(str(e))
                        
                        ui.notify(f"Fetch failed: {str(e)}", type="negative")
                        
                    except Exception as e:
                        with fetch_status_container["element"]:
                            fetch_status_container["element"].clear()
                            _show_fetch_error(f"Unexpected error: {str(e)}")
                        
                        ui.notify(f"Error: {str(e)}", type="negative")
                
                ui.button(
                    "Fetch Target Data",
                    icon="cloud_download",
                    on_click=do_fetch,
                ).props("size=lg")
                
                continue_btn = ui.button(
                    "Continue to Mapping",
                    icon="arrow_forward",
                    on_click=lambda: on_step_change(WorkflowStep.JAC_MAPPING),
                ).props("size=lg").style(f"background-color: {DBT_ORANGE};")
                
                if not jac.target_fetch_complete:
                    continue_btn.disable()


def _show_fetch_ready(same_account: bool) -> None:
    """Show the ready-to-fetch state."""
    with ui.row().classes("items-center gap-3"):
        ui.icon("info", size="md").classes("text-blue-500")
        if same_account:
            ui.label(
                "Click 'Fetch Target Data' to load projects and environments from your account."
            ).classes("text-slate-600")
        else:
            ui.label(
                "Enter target credentials and click 'Fetch Target Data' to proceed."
            ).classes("text-slate-600")


def _show_fetch_complete(jac) -> None:
    """Show fetch completion statistics."""
    with ui.column().classes("gap-4"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("check_circle", size="md").classes("text-green-500")
            ui.label("Target data fetched successfully!").classes(
                "text-lg font-semibold text-green-600"
            )
        
        with ui.row().classes("gap-8"):
            _stat_card("Projects", str(len(jac.target_projects)), "folder")
            _stat_card("Environments", str(len(jac.target_environments)), "dns")
            _stat_card("Existing Jobs", str(len(jac.target_jobs)), "work")


def _show_fetch_error(error: str) -> None:
    """Show fetch error."""
    with ui.column().classes("gap-2"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("error", size="md").classes("text-red-500")
            ui.label("Fetch failed").classes("text-lg font-semibold text-red-600")
        
        ui.label(error).classes("text-sm text-red-500")


def _stat_card(label: str, value: str, icon: str) -> None:
    """Create a small stat card."""
    with ui.card().classes("p-4"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon, size="sm").style(f"color: {DBT_ORANGE};")
            ui.label(label).classes("text-sm text-slate-500")
        ui.label(value).classes("text-2xl font-bold mt-1")
