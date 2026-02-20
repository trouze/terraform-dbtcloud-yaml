"""Main NiceGUI application setup and routing."""

import os
import time
from pathlib import Path
from typing import Optional

from nicegui import app, ui

from importer.web.state import AppState, WorkflowStep, WorkflowType, STEP_NAMES
from importer.web.components.stepper import create_nav_drawer, create_progress_header
from importer.web.project_manager import (
    ProjectManager,
    StateSaver,
    resolve_fetch_output_dirs_for_project,
)
from importer.web.pages.home import create_home_page
from importer.web.pages.requirements import create_requirements_page
from importer.web.pages.fetch_source import create_fetch_source_page
from importer.web.pages.explore_source import create_explore_source_page
from importer.web.pages.scope import create_scope_page
from importer.web.pages.fetch_target import create_fetch_target_page
from importer.web.pages.explore_target import create_explore_target_page
from importer.web.pages.match import create_match_page
from importer.web.pages.adopt import create_adopt_page
from importer.web.pages.configure import create_configure_page
from importer.web.pages.deploy import create_deploy_page
from importer.web.pages.destroy import create_destroy_page
from importer.web.pages.target_credentials import create_target_credentials_page
from importer.web.pages.utilities import create_utilities_page
from importer.web.env_manager import load_account_info_from_env, resolve_project_env_path
from importer.web.licensing import (
    LicenseTier,
    check_migration_license,
    has_feature_access,
)

# Jobs as Code Generator workflow pages
from importer.web.workflows.jobs_as_code.pages.select import create_jac_select_page
from importer.web.workflows.jobs_as_code.pages.fetch import create_jac_fetch_page
from importer.web.workflows.jobs_as_code.pages.jobs import create_jac_jobs_page
from importer.web.workflows.jobs_as_code.pages.target import create_jac_target_page
from importer.web.workflows.jobs_as_code.pages.mapping import create_jac_mapping_page
from importer.web.workflows.jobs_as_code.pages.config import create_jac_config_page
from importer.web.workflows.jobs_as_code.pages.generate import create_jac_generate_page

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


# Global state - will be replaced with proper session management
_app_state: Optional[AppState] = None

# Project management (PRD 21.02)
_project_manager: Optional[ProjectManager] = None
_state_saver: Optional[StateSaver] = None
_WS_DEBUG_ENABLED = os.getenv("IMPORTER_WS_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
_WS_DEBUG_LOG_PATH = Path(
    "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-db419a.log"
)
_WS_ROUTE_METRICS = {
    "route_transition_count": 0,
    "fetch_target_render_count": 0,
    "match_render_count": 0,
}


def _dbg_ws_metric(location: str, message: str, data: dict) -> None:
    if not _WS_DEBUG_ENABLED:
        return
    payload = {
        "sessionId": "db419a",
        "runId": "post-fix",
        "hypothesisId": "H71",
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        _WS_DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _WS_DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            import json
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


def get_project_manager() -> ProjectManager:
    """Get the singleton ProjectManager instance."""
    global _project_manager
    if _project_manager is None:
        project_root = Path(__file__).parent.parent.parent.resolve()
        _project_manager = ProjectManager(base_path=project_root)
    return _project_manager


def get_state_saver() -> StateSaver:
    """Get the singleton StateSaver instance."""
    global _state_saver
    if _state_saver is None:
        _state_saver = StateSaver(get_project_manager())
    return _state_saver


def load_project(slug: str) -> None:
    """Load a project by slug — restores AppState from project state.json.

    Updates global ``_app_state`` with the loaded project state and navigates
    to the first workflow step (or HOME).
    """
    global _app_state
    pm = get_project_manager()
    try:
        config, project_state = pm.load_project(slug)
        if project_state is not None:
            _app_state = project_state
        else:
            _app_state = AppState()
            _app_state.workflow = config.workflow_type
        _app_state.active_project = slug
        _app_state.project_path = str(pm.get_project_path(slug))
        source_dir, target_dir = resolve_fetch_output_dirs_for_project(_app_state.project_path)
        if source_dir:
            _app_state.fetch.output_dir = source_dir
        if target_dir:
            _app_state.target_fetch.output_dir = target_dir
        save_state()
        ui.notify(f"Loaded project: {config.name}", type="positive")
        ui.navigate.to("/")
    except Exception as exc:
        ui.notify(f"Failed to load project: {exc}", type="negative")


def get_state() -> AppState:
    """Get the current application state."""
    global _app_state
    if _app_state is None:
        # Try to restore from storage
        stored = app.storage.user.get("app_state")
        if stored:
            _app_state = AppState.from_dict(stored)
        else:
            _app_state = AppState()
        
        # Always refresh account info from .env on startup
        _refresh_account_info(_app_state)
        _refresh_license_status(_app_state)
    return _app_state


def _refresh_account_info(state: AppState) -> None:
    """Refresh account info from project-scoped .env file (or global fallback)."""
    try:
        source_env = resolve_project_env_path(state.project_path, "source")
        target_env = resolve_project_env_path(state.project_path, "target")
        state.source_account = load_account_info_from_env("source", env_path=source_env)
        state.target_account = load_account_info_from_env("target", env_path=target_env)
    except Exception:
        pass


def _refresh_license_status(state: AppState) -> None:
    """Refresh migration workflow license status and tier."""
    try:
        status = check_migration_license()
        state.is_migration_licensed = status.is_valid
        state.license_tier = status.tier.value
        state.license_email = status.email or ""
        state.license_message = status.message
    except Exception as exc:
        state.is_migration_licensed = False
        state.license_tier = LicenseTier.EXPLORER.value
        state.license_email = ""
        state.license_message = f"License verification failed: {exc}"


def save_state() -> None:
    """Save the current state to storage.
    
    Persists to NiceGUI user storage and, if a project is active, schedules
    a debounced save to the project's state.json (US-099).
    """
    global _app_state
    if _app_state:
        try:
            # region agent log
            import json as _json_dbg, time as _time_dbg, traceback as _tb_dbg, yaml as _yaml_dbg
            _DBG_LOG = Path("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-0c67c5.log")
            def _dbg(hid, loc, msg, data, rid="run1"):
                try:
                    with _DBG_LOG.open("a") as _f:
                        _f.write(_json_dbg.dumps({"sessionId":"0c67c5","runId":rid,"hypothesisId":hid,"location":loc,"message":msg,"data":data,"timestamp":int(_time_dbg.time()*1000)}, default=str)+"\n")
                except Exception:
                    pass
            def _max_depth(obj, seen=None, depth=0):
                if depth > 200:
                    return depth
                if seen is None:
                    seen = set()
                oid = id(obj)
                if oid in seen:
                    return -1  # circular
                seen.add(oid)
                if isinstance(obj, dict):
                    if not obj:
                        return depth
                    return max(_max_depth(v, seen, depth+1) for v in obj.values())
                elif isinstance(obj, (list, tuple)):
                    if not obj:
                        return depth
                    return max(_max_depth(v, seen, depth+1) for v in obj)
                return depth
            try:
                state_dict = _app_state.to_dict()
                _dbg("A","app.py:save_state","to_dict produced",{"keys":list(state_dict.keys()),"top_level_count":len(state_dict)})
                for k, v in state_dict.items():
                    d = _max_depth(v)
                    sz = len(_json_dbg.dumps(v, default=str)) if v is not None else 0
                    _dbg("A","app.py:save_state:field",f"field={k}",{"depth":d,"json_size":sz,"type":type(v).__name__})
                    if d == -1:
                        _dbg("A","app.py:save_state:CIRCULAR",f"CIRCULAR REF in {k}",{"field":k})
                    if d > 50:
                        _dbg("A","app.py:save_state:DEEP",f"DEEP nesting in {k}",{"field":k,"depth":d})
                    try:
                        _yaml_dbg.dump({k: v})
                    except Exception as _ye:
                        _dbg("B","app.py:save_state:yaml_fail",f"YAML fail on {k}",{"field":k,"error":str(_ye)[:500]})
                for extra_k in list(app.storage.user.keys()):
                    if extra_k == "app_state":
                        continue
                    ev = app.storage.user[extra_k]
                    ed = _max_depth(ev)
                    _dbg("E","app.py:save_state:extra_key",f"extra storage key={extra_k}",{"depth":ed,"type":type(ev).__name__})
                    try:
                        _yaml_dbg.dump({extra_k: ev})
                    except Exception as _ye2:
                        _dbg("E","app.py:save_state:extra_yaml_fail",f"YAML fail on extra key {extra_k}",{"key":extra_k,"error":str(_ye2)[:500]})
            except RecursionError as _re:
                _dbg("X","app.py:save_state:RECURSION","RecursionError during debug check",{"traceback":_tb_dbg.format_exc()[-1000:]})
            except Exception as _e:
                _dbg("X","app.py:save_state:ERROR","Error during debug check",{"error":str(_e)[:500]})
            # endregion
            app.storage.user["app_state"] = _app_state.to_dict()
            # Also save protection intent file if it was accessed
            _app_state.save_protection_intent()
        except (AssertionError, KeyError) as e:
            # User storage not yet initialized (e.g., direct URL access before session established)
            # This is recoverable - state will be saved on next interaction
            import logging
            logging.getLogger(__name__).debug(f"Could not save state (session not ready): {e}")
        except RecursionError as _re_outer:
            # region agent log
            try:
                import json as _json_re, time as _time_re, traceback as _tb_re
                _DBG_LOG_RE = Path("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-0c67c5.log")
                with _DBG_LOG_RE.open("a") as _fre:
                    _fre.write(_json_re.dumps({"sessionId":"0c67c5","runId":"run1","hypothesisId":"X","location":"app.py:save_state:outer_recursion","message":"OUTER RecursionError caught","data":{"traceback":_tb_re.format_exc()[-2000:]},"timestamp":int(_time_re.time()*1000)}, default=str)+"\n")
            except Exception:
                pass
            # endregion

        # Auto-save to project if one is active (US-099)
        if _app_state.active_project:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                saver = get_state_saver()
                loop.create_task(saver.schedule_save(_app_state))
            except RuntimeError:
                # No event loop — skip project auto-save (happens during tests)
                pass


def navigate_to_step(step: WorkflowStep) -> None:
    """Navigate to a workflow step."""
    state = get_state()
    prev_step = state.current_step
    state.current_step = step
    save_state()
    _WS_ROUTE_METRICS["route_transition_count"] += 1
    _dbg_ws_metric(
        "app.py:navigate_to_step",
        "workflow route transition requested",
        {
            "from_step": prev_step.name if isinstance(prev_step, WorkflowStep) else str(prev_step),
            "to_step": step.name,
            "route_transition_count": _WS_ROUTE_METRICS["route_transition_count"],
        },
    )
    # Map step to URL - handle special cases
    if step == WorkflowStep.HOME:
        url = "/"
    elif step == WorkflowStep.UTILITIES:
        url = "/protection-management"
    else:
        url = f"/{step.name.lower()}"
    ui.navigate.to(url)


def set_workflow(workflow: WorkflowType) -> None:
    """Set the active workflow and navigate to a valid step."""
    state = get_state()

    # Get current tier for access checks
    try:
        tier = LicenseTier(state.license_tier)
    except ValueError:
        tier = LicenseTier.EXPLORER

    # Map workflow types to feature keys
    workflow_features = {
        WorkflowType.MIGRATION: "migration",
        WorkflowType.ACCOUNT_EXPLORER: "account_explorer",
        WorkflowType.JOBS_AS_CODE: "jobs_as_code",
        WorkflowType.IMPORT_ADOPT: "import_adopt",
    }

    feature_key = workflow_features.get(workflow)
    if feature_key and not has_feature_access(tier, feature_key):
        tier_name = {
            LicenseTier.EXPLORER: "Explorer",
            LicenseTier.SOLUTIONS_ARCHITECT: "Solutions Architect",
            LicenseTier.RESIDENT_ARCHITECT: "Resident Architect",
            LicenseTier.ENGINEERING: "Engineering",
        }.get(tier, "Explorer")
        ui.notify(
            f"Your license tier ({tier_name}) does not include access to this workflow. "
            "Upgrade your license or contact Professional Services at info@getdbt.com.",
            type="warning",
        )
        ui.navigate.to("/")
        return

    state.workflow = workflow
    steps = state.workflow_steps()
    next_step = state.current_step if state.current_step in steps else steps[0]
    state.current_step = next_step
    save_state()
    # Map step to URL - handle special cases
    if next_step == WorkflowStep.HOME:
        url = "/"
    elif next_step == WorkflowStep.UTILITIES:
        url = "/protection-management"
    else:
        url = f"/{next_step.name.lower()}"
    ui.navigate.to(url)


def toggle_theme() -> None:
    """Toggle between dark and light theme."""
    state = get_state()
    state.theme = "light" if state.theme == "dark" else "dark"
    save_state()
    ui.navigate.reload()


def clear_session() -> None:
    """Clear the session and start fresh."""
    global _app_state
    _app_state = AppState()
    app.storage.user.clear()
    ui.notify("Session cleared", type="positive")
    ui.navigate.to("/")


def navigate_to_requirements() -> None:
    """Navigate to the requirements page."""
    ui.navigate.to("/requirements")


def _require_workflow_access(state: AppState) -> bool:
    """Ensure the current workflow is accessible with the current license tier."""
    # Get current tier
    try:
        tier = LicenseTier(state.license_tier)
    except ValueError:
        tier = LicenseTier.EXPLORER

    # Map workflow types to feature keys
    workflow_features = {
        WorkflowType.MIGRATION: "migration",
        WorkflowType.ACCOUNT_EXPLORER: "account_explorer",
        WorkflowType.JOBS_AS_CODE: "jobs_as_code",
        WorkflowType.IMPORT_ADOPT: "import_adopt",
    }

    feature_key = workflow_features.get(state.workflow)
    if feature_key and has_feature_access(tier, feature_key):
        return True

    ui.notify(
        "Your license tier does not include access to this workflow. "
        "Upgrade your license or contact Professional Services at info@getdbt.com.",
        type="warning",
    )
    ui.navigate.to("/")
    return False


def _require_migration_license(state: AppState) -> bool:
    """Ensure migration workflow access is licensed (legacy compatibility)."""
    return _require_workflow_access(state)


def setup_page(state: AppState) -> None:
    """Common page setup - theme and navigation."""
    # Apply theme
    if state.theme == "dark":
        ui.dark_mode().enable()
    else:
        ui.dark_mode().disable()

    # Add global CSS for AG Grid dark mode support
    # NiceGUI uses .dark class on body, but AG Grid's quartz-auto-dark only responds to
    # prefers-color-scheme media query. These CSS overrides bridge the gap.
    ui.add_css("""
        /* AG Grid dark mode overrides for NiceGUI */
        .dark .ag-theme-quartz, .body--dark .ag-theme-quartz,
        .dark .ag-theme-quartz-auto-dark, .body--dark .ag-theme-quartz-auto-dark {
            --ag-background-color: #1e1e1e !important;
            --ag-header-background-color: #2d2d2d !important;
            --ag-odd-row-background-color: #262626 !important;
            --ag-row-hover-color: #3d3d3d !important;
            --ag-selected-row-background-color: #3d5a80 !important;
            --ag-foreground-color: #e0e0e0 !important;
            --ag-header-foreground-color: #e0e0e0 !important;
            --ag-secondary-foreground-color: #a0a0a0 !important;
            --ag-border-color: #404040 !important;
            --ag-input-border-color: #505050 !important;
        }
        .dark .ag-theme-quartz .ag-root-wrapper, .body--dark .ag-theme-quartz .ag-root-wrapper,
        .dark .ag-theme-quartz-auto-dark .ag-root-wrapper, .body--dark .ag-theme-quartz-auto-dark .ag-root-wrapper {
            background-color: #1e1e1e !important;
        }
        .dark .ag-theme-quartz .ag-header, .body--dark .ag-theme-quartz .ag-header,
        .dark .ag-theme-quartz-auto-dark .ag-header, .body--dark .ag-theme-quartz-auto-dark .ag-header {
            background-color: #2d2d2d !important;
        }
        .dark .ag-theme-quartz .ag-row, .body--dark .ag-theme-quartz .ag-row,
        .dark .ag-theme-quartz-auto-dark .ag-row, .body--dark .ag-theme-quartz-auto-dark .ag-row {
            background-color: #1e1e1e !important;
        }
        .dark .ag-theme-quartz .ag-row-odd, .body--dark .ag-theme-quartz .ag-row-odd,
        .dark .ag-theme-quartz-auto-dark .ag-row-odd, .body--dark .ag-theme-quartz-auto-dark .ag-row-odd {
            background-color: #262626 !important;
        }
        .dark .ag-theme-quartz .ag-cell, .body--dark .ag-theme-quartz .ag-cell,
        .dark .ag-theme-quartz-auto-dark .ag-cell, .body--dark .ag-theme-quartz-auto-dark .ag-cell {
            color: #e0e0e0 !important;
        }
        
        /* Global AG Grid font size standardization - matches text-xs (12px) */
        .ag-theme-quartz .ag-cell,
        .ag-theme-quartz-auto-dark .ag-cell,
        .ag-theme-quartz .ag-header-cell-text,
        .ag-theme-quartz-auto-dark .ag-header-cell-text {
            font-size: 12px !important;
        }
        .ag-theme-quartz .ag-header-cell,
        .ag-theme-quartz-auto-dark .ag-header-cell {
            font-size: 12px !important;
        }
        
    """)

    # Create navigation drawer with callbacks
    create_nav_drawer(
        state,
        navigate_to_step,
        set_workflow,
        toggle_theme,
        clear_session,
        navigate_to_requirements,
    )


def create_page_content(state: AppState) -> None:
    """Create the main content area based on current step."""
    step = state.current_step

    if step == WorkflowStep.HOME:
        create_home_page(
            state,
            navigate_to_step,
            set_workflow,
            save_state,
            project_manager=get_project_manager(),
            on_project_load=load_project,
        )
    elif step == WorkflowStep.FETCH_SOURCE:
        create_fetch_source_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.EXPLORE_SOURCE:
        create_explore_source_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.SCOPE:
        create_scope_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.FETCH_TARGET:
        create_fetch_target_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.EXPLORE_TARGET:
        create_explore_target_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.MATCH:
        create_match_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.ADOPT:
        create_adopt_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.CONFIGURE:
        create_configure_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.TARGET_CREDENTIALS:
        create_target_credentials_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.DEPLOY:
        create_deploy_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.DESTROY:
        create_destroy_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.UTILITIES:
        create_utilities_page(state, navigate_to_step, save_state)
    # Jobs as Code Generator workflow steps
    elif step == WorkflowStep.JAC_SELECT:
        create_jac_select_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_FETCH:
        create_jac_fetch_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_JOBS:
        create_jac_jobs_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_TARGET:
        create_jac_target_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_MAPPING:
        create_jac_mapping_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_CONFIG:
        create_jac_config_page(state, navigate_to_step, save_state)
    elif step == WorkflowStep.JAC_GENERATE:
        create_jac_generate_page(state, navigate_to_step, save_state)


def _create_placeholder_page(title: str, description: str, state: AppState) -> None:
    """Create a placeholder page for unimplemented steps."""
    with ui.column().classes("w-full max-w-4xl mx-auto p-8 gap-4"):
        with ui.card().classes("w-full p-8"):
            with ui.row().classes("items-center gap-4"):
                ui.icon("construction", size="2rem").style("color: #FF694A;")
                ui.label(title).classes("text-2xl font-bold")

            ui.label(description).classes("text-slate-600 dark:text-slate-400 mt-2")

            ui.markdown("""
                This page is coming soon. The implementation will include:
                
                - Full functionality as described in the PRD
                - Integration with the existing importer modules
                - Persistent state management
            """).classes("mt-4")

            with ui.row().classes("gap-4 mt-6"):
                # Previous step button
                workflow_steps = list(WorkflowStep)
                current_idx = workflow_steps.index(state.current_step)
                if current_idx > 1:  # Skip HOME
                    prev_step = workflow_steps[current_idx - 1]
                    ui.button(
                        f"Back to {STEP_NAMES[prev_step]}",
                        icon="arrow_back",
                        on_click=lambda s=prev_step: navigate_to_step(s),
                    ).props("outline")

                # Next step button (placeholder)
                if current_idx < len(workflow_steps) - 1:
                    next_step = workflow_steps[current_idx + 1]
                    ui.button(
                        f"Continue to {STEP_NAMES[next_step]}",
                        icon="arrow_forward",
                        on_click=lambda s=next_step: navigate_to_step(s),
                    ).style("background-color: #FF694A;")


@ui.page("/")
def home_page() -> None:
    """Home page route."""
    state = get_state()
    state.current_step = WorkflowStep.HOME
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/fetch_source")
def fetch_source_page() -> None:
    """Fetch Source step page route."""
    state = get_state()
    state.current_step = WorkflowStep.FETCH_SOURCE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/explore_source")
def explore_source_page() -> None:
    """Explore Source step page route."""
    state = get_state()
    state.current_step = WorkflowStep.EXPLORE_SOURCE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/scope")
def scope_page() -> None:
    """Scope step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.SCOPE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/fetch_target")
def fetch_target_page() -> None:
    """Fetch Target step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.FETCH_TARGET
    save_state()
    setup_page(state)

    _render_started = time.time()
    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)
    _WS_ROUTE_METRICS["fetch_target_render_count"] += 1
    _dbg_ws_metric(
        "app.py:fetch_target_page",
        "fetch_target page rendered",
        {
            "render_ms": int((time.time() - _render_started) * 1000),
            "fetch_target_render_count": _WS_ROUTE_METRICS["fetch_target_render_count"],
            "route_transition_count": _WS_ROUTE_METRICS["route_transition_count"],
        },
    )


@ui.page("/explore_target")
def explore_target_page() -> None:
    """Explore Target step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.EXPLORE_TARGET
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/match")
def match_page() -> None:
    """Match step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.MATCH
    save_state()
    setup_page(state)

    _render_started = time.time()
    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)
    _WS_ROUTE_METRICS["match_render_count"] += 1
    _dbg_ws_metric(
        "app.py:match_page",
        "match page rendered",
        {
            "render_ms": int((time.time() - _render_started) * 1000),
            "match_render_count": _WS_ROUTE_METRICS["match_render_count"],
            "route_transition_count": _WS_ROUTE_METRICS["route_transition_count"],
        },
    )


@ui.page("/adopt")
def adopt_page() -> None:
    """Adopt step page route — automated terraform state rm + import."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.ADOPT
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/configure")
def configure_page() -> None:
    """Configure Migration step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.CONFIGURE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/target_credentials")
def target_credentials_page() -> None:
    """Target Credentials step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.TARGET_CREDENTIALS
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/deploy")
def deploy_page() -> None:
    """Deploy step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.DEPLOY
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/destroy")
def destroy_page() -> None:
    """Destroy step page route."""
    state = get_state()
    if not _require_migration_license(state):
        return
    state.current_step = WorkflowStep.DESTROY
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/protection-management")
def protection_management_page() -> None:
    """Protection Management page route."""
    state = get_state()
    state.current_step = WorkflowStep.UTILITIES
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/requirements")
def requirements_page() -> None:
    """Requirements checker page route."""
    state = get_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_requirements_page(state)


# Jobs as Code Generator workflow routes
@ui.page("/jac_select")
def jac_select_page() -> None:
    """Jobs as Code Generator - Select workflow page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_SELECT
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_fetch")
def jac_fetch_page() -> None:
    """Jobs as Code Generator - Fetch jobs page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_FETCH
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_jobs")
def jac_jobs_page() -> None:
    """Jobs as Code Generator - Select jobs page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_JOBS
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_target")
def jac_target_page() -> None:
    """Jobs as Code Generator - Target config page (clone only)."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_TARGET
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_mapping")
def jac_mapping_page() -> None:
    """Jobs as Code Generator - Resource mapping page (clone only)."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_MAPPING
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_config")
def jac_config_page() -> None:
    """Jobs as Code Generator - Job configuration page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_CONFIG
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


@ui.page("/jac_generate")
def jac_generate_page() -> None:
    """Jobs as Code Generator - Generate and export page."""
    state = get_state()
    state.current_step = WorkflowStep.JAC_GENERATE
    save_state()
    setup_page(state)

    with ui.column().classes("w-full"):
        create_progress_header(state)
        create_page_content(state)


def run_app(
    host: str = "127.0.0.1",
    port: int = 8080,
    show: bool = True,
    reload: bool = False,
) -> None:
    """Run the NiceGUI application.

    Args:
        host: Host to bind to
        port: Port to run on
        show: Whether to auto-open browser
        reload: Whether to enable auto-reload
    """
    # Serve static files
    app.add_static_files("/static", str(STATIC_DIR))

    # Favicon needs absolute path
    favicon_path = STATIC_DIR / "favicon.svg"
    # Keep client sockets alive longer during large page transitions (match <-> fetch_target)
    # so navigation does not trigger premature timeout-based reconnect loops on localhost.
    reconnect_timeout = float(os.getenv("IMPORTER_WS_RECONNECT_TIMEOUT", "20.0"))

    ui.run(
        host=host,
        port=port,
        show=show,
        reload=reload,
        title="dbt Magellan: Exploration & Migration Tool",
        favicon=str(favicon_path),
        storage_secret="dbt-cloud-importer-secret",  # For user storage
        reconnect_timeout=reconnect_timeout,
    )
