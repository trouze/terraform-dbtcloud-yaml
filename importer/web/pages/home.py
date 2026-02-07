"""Home/dashboard page for the web UI."""

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

import os

from dotenv import set_key

from importer.web.env_manager import (
    find_env_file,
    load_license_credentials,
    save_license_credentials,
)
from importer.web.licensing import (
    ENV_LICENSE_BYPASS,
    LicenseTier,
    TIER_FEATURES,
    TIER_DISPLAY_NAMES,
    get_license_manager,
    has_feature_access,
)
from importer.web.state import AppState, WorkflowStep, WorkflowType, WORKFLOW_LABELS
from importer.web.project_manager import ProjectConfig, ProjectManager


# Workflow type badge colors
_WORKFLOW_COLORS: dict[str, str] = {
    "migration": "orange",
    "account_explorer": "blue",
    "jobs_as_code": "purple",
    "import_adopt": "teal",
}


def create_home_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    on_workflow_change: Callable[[WorkflowType], None],
    save_state: Optional[Callable[[], None]] = None,
    project_manager: Optional[ProjectManager] = None,
    on_project_load: Optional[Callable[[str], None]] = None,
) -> None:
    """Create the home/dashboard page content.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        on_workflow_change: Callback to switch workflows
        save_state: Callback to persist state changes
        project_manager: ProjectManager instance for project CRUD (optional)
        on_project_load: Callback to load a project by slug (optional)
    """
    with ui.column().classes("w-full max-w-4xl mx-auto p-8 gap-6"):
        # License panel at the top (full width)
        _create_license_panel(state, save_state)

        # Project management section (US-090)
        if project_manager is not None:
            _create_projects_section(
                state=state,
                project_manager=project_manager,
                on_workflow_change=on_workflow_change,
                on_project_load=on_project_load,
            )

        # Welcome section with workflow cards
        _create_welcome_section(state, on_step_change, on_workflow_change)

        # Quick stats (if there's previous data)
        if state.fetch.fetch_complete:
            _create_quick_stats(state)

        # Recent runs
        _create_recent_runs_section(state, on_step_change)


def _create_projects_section(
    state: AppState,
    project_manager: ProjectManager,
    on_workflow_change: Callable[[WorkflowType], None],
    on_project_load: Optional[Callable[[str], None]] = None,
) -> None:
    """Create the 'Your Projects' section with card grid and search (US-090)."""
    projects = project_manager.list_projects()

    # Mutable container ref for refreshing
    project_container_ref: dict = {"ref": None}
    search_term: dict = {"value": ""}
    filter_workflow: dict = {"value": "all"}

    def _filtered_projects() -> list[ProjectConfig]:
        """Apply search and filter to the project list."""
        result = projects
        # Workflow type filter
        wf = filter_workflow["value"]
        if wf and wf != "all":
            result = [p for p in result if p.workflow_type.value == wf]
        # Text search
        term = search_term["value"].strip().lower()
        if term:
            result = [
                p for p in result
                if term in p.name.lower() or term in p.description.lower() or term in p.slug.lower()
            ]
        return result

    def _refresh_projects() -> None:
        """Re-render the project cards."""
        nonlocal projects
        projects = project_manager.list_projects()
        container = project_container_ref.get("ref")
        if container is None:
            return
        container.clear()
        filtered = _filtered_projects()
        with container:
            if not filtered:
                with ui.row().classes("items-center gap-2 text-gray-500 py-4"):
                    ui.icon("folder_off", size="sm")
                    if projects:
                        ui.label("No projects match your filters.")
                    else:
                        ui.label("No projects yet. Create one to get started!")
                return

            # Card grid (always cards for now; AG Grid view at >=10 is a future enhancement)
            with ui.element("div").classes("w-full").style(
                "display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px;"
            ):
                for project in filtered:
                    _project_card(project, on_project_load, _confirm_delete)

    def _confirm_delete(slug: str, name: str) -> None:
        """Show delete confirmation dialog (US-092)."""
        if state.active_project == slug:
            ui.notify("Cannot delete the currently active project. Switch first.", type="warning")
            return

        with ui.dialog() as dlg, ui.card().classes("p-4 min-w-[350px]"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("warning", color="red", size="md")
                ui.label("Delete Project").classes("text-lg font-bold")
            ui.label(f"Are you sure you want to permanently delete '{name}'?").classes("text-sm mt-2")
            ui.label("This will remove all project files, credentials, and state.").classes("text-xs text-red-400")
            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat")

                def do_delete():
                    project_manager.delete_project(slug)
                    ui.notify(f"Deleted project '{name}'", type="positive")
                    dlg.close()
                    _refresh_projects()

                ui.button("Delete", icon="delete", on_click=do_delete).props("color=negative")
        dlg.open()

    def _open_wizard() -> None:
        """Open the new project wizard (US-085)."""
        from importer.web.components.new_project_wizard import show_new_project_wizard

        def _on_created(config: ProjectConfig) -> None:
            _refresh_projects()
            if on_project_load:
                on_project_load(config.slug)

        show_new_project_wizard(project_manager, _on_created)

    # ---- Render the section ----
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Your Projects").classes("text-lg font-semibold")
            ui.button("New Project", icon="add_circle", on_click=_open_wizard).props("color=primary")

        # Search and filter row
        if projects:
            with ui.row().classes("w-full gap-2 mt-2 items-center"):
                search_input = ui.input(
                    placeholder="Search projects...",
                    on_change=lambda e: (search_term.update({"value": e.value or ""}), _refresh_projects()),
                ).props("dense outlined clearable").classes("flex-grow").style("max-width: 300px;")
                search_input.props('prepend-inner-icon="search"')

                wf_options = {"all": "All Types", **{wt.value: WORKFLOW_LABELS[wt] for wt in WorkflowType}}
                ui.select(
                    options=wf_options,
                    value="all",
                    on_change=lambda e: (filter_workflow.update({"value": e.value or "all"}), _refresh_projects()),
                ).props("dense outlined").style("min-width: 160px;")

                if projects:
                    ui.label(f"{len(projects)} project{'s' if len(projects) != 1 else ''}").classes("text-xs text-gray-500")

        # Project cards container
        project_container_ref["ref"] = ui.column().classes("w-full mt-2")
        _refresh_projects()


def _project_card(
    project: ProjectConfig,
    on_project_load: Optional[Callable[[str], None]],
    on_delete: Callable[[str, str], None],
) -> None:
    """Render a single project card (US-090 card view)."""
    wf_color = _WORKFLOW_COLORS.get(project.workflow_type.value, "gray")

    def _relative_time(dt: datetime) -> str:
        """Format a datetime as relative time."""
        now = datetime.now()
        delta = now - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        return dt.strftime("%Y-%m-%d")

    with ui.card().classes("w-full p-3 cursor-pointer hover:shadow-lg transition-shadow"):
        # Click to load
        if on_project_load:
            ui.card().on("click", lambda slug=project.slug: on_project_load(slug))

        with ui.column().classes("gap-1 w-full"):
            # Title row with workflow badge
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(project.name).classes("font-semibold text-sm")
                    ui.badge(project.workflow_type.value.replace("_", " ").title(), color=wf_color).props("dense")
                # Delete button
                ui.button(
                    icon="delete_outline",
                    on_click=lambda e, s=project.slug, n=project.name: (e.sender.parent_slot.parent.stop_propagation if hasattr(e, 'stop_propagation') else None, on_delete(s, n)),
                ).props("flat round dense size=xs").classes("text-gray-400 hover:text-red-400")

            # Description
            if project.description:
                ui.label(project.description).classes(
                    "text-xs text-gray-500 line-clamp-2"
                ).style("display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;")

            # Account info
            with ui.row().classes("gap-3 mt-1"):
                if project.source_host:
                    acct_text = f"Source: {project.source_host}"
                    if project.source_account_id:
                        acct_text += f" / {project.source_account_id}"
                    ui.label(acct_text).classes("text-xs text-gray-500")
                if project.target_host:
                    acct_text = f"Target: {project.target_host}"
                    if project.target_account_id:
                        acct_text += f" / {project.target_account_id}"
                    ui.label(acct_text).classes("text-xs text-gray-500")

            # Footer: last modified
            ui.label(_relative_time(project.updated_at)).classes("text-xs text-gray-600 mt-1")

        # Make the whole card clickable
        if on_project_load:
            ui.card().on("click", lambda slug=project.slug: on_project_load(slug))


def _create_welcome_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    on_workflow_change: Callable[[WorkflowType], None],
) -> None:
    """Create the welcome/hero section with workflow cards."""
    # Get current tier for access checks
    try:
        tier = LicenseTier(state.license_tier)
    except ValueError:
        tier = LicenseTier.EXPLORER

    with ui.card().classes("w-full p-6"):
        with ui.column().classes("gap-3"):
            ui.markdown("""
                Choose a workflow to explore, audit, or migrate dbt Platform account configurations.
            """).classes("text-slate-600 dark:text-slate-400")

            # Workflow cards - 2x2 grid with consistent heights using CSS Grid
            # align-items: stretch ensures all items in row match height
            with ui.element("div").classes("w-full mt-4").style(
                "display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; align-items: stretch;"
            ):
                # Migration Workflow
                can_migrate = has_feature_access(tier, "migration")
                _create_workflow_card(
                    title=WORKFLOW_LABELS[WorkflowType.MIGRATION],
                    description="Full end-to-end migration with scoped selection and deploy.",
                    icon="rocket_launch",
                    on_click=(
                        lambda: on_workflow_change(WorkflowType.MIGRATION)
                        if can_migrate
                        else None
                    ),
                    highlight=can_migrate,
                    disabled=not can_migrate,
                    badge_text="Requires License" if not can_migrate else None,
                )

                # Account Explorer - always accessible
                _create_workflow_card(
                    title=WORKFLOW_LABELS[WorkflowType.ACCOUNT_EXPLORER],
                    description="Fetch and explore account configuration without deployment.",
                    icon="search",
                    on_click=lambda: on_workflow_change(WorkflowType.ACCOUNT_EXPLORER),
                )

                # Jobs as Code Generator
                can_jobs = has_feature_access(tier, "jobs_as_code")
                _create_workflow_card(
                    title=WORKFLOW_LABELS[WorkflowType.JOBS_AS_CODE],
                    description="Generate jobs-as-code YAML outputs from selected jobs and environments.",
                    icon="code",
                    on_click=(
                        lambda: on_workflow_change(WorkflowType.JOBS_AS_CODE)
                        if can_jobs
                        else None
                    ),
                    disabled=not can_jobs,
                    badge_text="Requires License" if not can_jobs else None,
                )

                # Import & Adopt
                can_import = has_feature_access(tier, "import_adopt")
                _create_workflow_card(
                    title=WORKFLOW_LABELS[WorkflowType.IMPORT_ADOPT],
                    description="Import existing infrastructure and adopt it into Terraform.",
                    icon="cloud_sync",
                    on_click=None,  # Not implemented yet
                    disabled=True,
                    badge_text="Coming Soon",
                )

            with ui.row().classes("gap-4 mt-4"):
                ui.button(
                    "Documentation",
                    icon="menu_book",
                    on_click=lambda: ui.notify("Documentation coming soon"),
                ).props("outline")


def _create_license_panel(
    state: AppState,
    save_state: Optional[Callable[[], None]] = None,
) -> None:
    """Create the license status and configuration panel.

    Shows current license status with tier information and allows
    editing license credentials.
    """
    # Get current tier
    try:
        tier = LicenseTier(state.license_tier)
    except ValueError:
        tier = LicenseTier.EXPLORER

    tier_name = TIER_DISPLAY_NAMES.get(tier, "Explorer")
    features = TIER_FEATURES.get(tier, TIER_FEATURES[LicenseTier.EXPLORER])

    # Determine status color and icon
    if state.is_migration_licensed and tier != LicenseTier.EXPLORER:
        status_color = "green"
        status_icon = "verified"
        status_text = f"Licensed to {state.license_email}" if state.license_email else "Licensed"
    elif tier == LicenseTier.EXPLORER:
        status_color = "slate"
        status_icon = "person"
        status_text = "Explorer Mode (No License)"
    else:
        status_color = "yellow"
        status_icon = "warning"
        status_text = state.license_message or "License verification pending"

    # UI state for expansion
    expanded = {"value": False}
    expand_container = {"ref": None}

    def toggle_expand():
        expanded["value"] = not expanded["value"]
        if expand_container["ref"]:
            expand_container["ref"].set_visibility(expanded["value"])

    with ui.card().classes("w-full p-4"):
        # Compact header row
        with ui.row().classes("w-full items-center justify-between"):
            # Left side: status
            with ui.row().classes("items-center gap-3"):
                ui.icon(status_icon, size="sm").classes(f"text-{status_color}-500")
                ui.label(status_text).classes("text-sm")
                ui.badge(tier_name, color=status_color).props("outline")

            # Right side: feature summary + expand button
            with ui.row().classes("items-center gap-4"):
                # Compact feature indicators
                with ui.row().classes("items-center gap-2"):
                    for feature_key, feature_name in [
                        ("account_explorer", "Explorer"),
                        ("jobs_as_code", "Jobs"),
                        ("migration", "Migration"),
                    ]:
                        enabled = features.get(feature_key, False)
                        icon_name = "check_circle" if enabled else "cancel"
                        color = "green" if enabled else "slate"
                        with ui.row().classes("items-center gap-1"):
                            ui.icon(icon_name, size="xs").classes(f"text-{color}-400")
                            ui.label(feature_name).classes(f"text-xs text-{color}-500")

                # Expand/collapse button
                ui.button(
                    icon="settings",
                    on_click=toggle_expand,
                ).props("flat dense").tooltip("Configure License")

        # Expandable section for credentials
        expand_container["ref"] = ui.column().classes("w-full mt-4 gap-4")
        expand_container["ref"].set_visibility(False)

        with expand_container["ref"]:
            ui.separator()

            # Load current credentials from .env
            creds = load_license_credentials()
            email_value = {"value": creds.get("email", "")}
            key_value = {"value": creds.get("key", "")}

            # Credential inputs
            with ui.row().classes("w-full gap-4 items-end"):
                email_input = ui.input(
                    "License Email",
                    value=email_value["value"],
                    placeholder="your.email@company.com",
                    on_change=lambda e: email_value.update({"value": e.value}),
                ).props("dense outlined").classes("flex-grow")

                key_input = ui.input(
                    "License Key",
                    value=key_value["value"],
                    password=True,
                    password_toggle_button=True,
                    placeholder="Base64-encoded key",
                    on_change=lambda e: key_value.update({"value": e.value}),
                ).props("dense outlined").classes("flex-grow")

            # Check current bypass status
            bypass_enabled = os.getenv(ENV_LICENSE_BYPASS, "").lower() in {"1", "true", "yes", "on"}

            # Action buttons
            with ui.row().classes("w-full gap-2 mt-2 items-center"):

                def do_load_env():
                    """Load credentials from .env file."""
                    creds = load_license_credentials()
                    email_input.value = creds.get("email", "")
                    key_input.value = creds.get("key", "")
                    email_value["value"] = creds.get("email", "")
                    key_value["value"] = creds.get("key", "")
                    ui.notify("Loaded credentials from .env", type="positive")

                def do_save_env():
                    """Save credentials to .env file."""
                    try:
                        save_license_credentials(
                            email_value["value"],
                            key_value["value"],
                        )
                        ui.notify(f"Saved to {find_env_file()}", type="positive")
                    except Exception as e:
                        ui.notify(f"Save failed: {e}", type="negative")

                def do_verify():
                    """Verify the license and update state."""
                    # Clear cache to force re-verification
                    manager = get_license_manager()
                    manager.clear_cache()

                    # Re-verify
                    status = manager.verify(force_refresh=True)

                    # Update state
                    state.is_migration_licensed = status.is_valid
                    state.license_tier = status.tier.value
                    state.license_email = status.email or ""
                    state.license_message = status.message

                    if save_state:
                        save_state()

                    if status.is_valid:
                        ui.notify(
                            f"License verified: {status.tier_display_name}",
                            type="positive",
                        )
                    else:
                        ui.notify(f"Verification failed: {status.message}", type="warning")

                    # Reload page to reflect changes
                    ui.navigate.reload()

                def do_toggle_bypass(enabled: bool):
                    """Toggle license bypass and refresh state."""
                    env_path = find_env_file()
                    set_key(str(env_path), ENV_LICENSE_BYPASS, "true" if enabled else "false")
                    os.environ[ENV_LICENSE_BYPASS] = "true" if enabled else "false"

                    # Clear cache and refresh
                    manager = get_license_manager()
                    manager.clear_cache()
                    status = manager.verify(force_refresh=True)

                    # Update state
                    state.is_migration_licensed = status.is_valid
                    state.license_tier = status.tier.value
                    state.license_email = status.email or ""
                    state.license_message = status.message

                    if save_state:
                        save_state()

                    tier_name = "Resident Architect" if enabled else "Explorer"
                    ui.notify(
                        f"Bypass {'enabled' if enabled else 'disabled'} ({tier_name} access)",
                        type="positive" if enabled else "info",
                    )
                    ui.navigate.reload()

                ui.button("Load from .env", icon="upload_file", on_click=do_load_env).props(
                    "flat dense"
                )
                ui.button("Save to .env", icon="save", on_click=do_save_env).props(
                    "flat dense"
                )
                ui.button("Verify License", icon="verified", on_click=do_verify).props(
                    "dense"
                ).style("background-color: #FF694A;")

                # Spacer
                ui.element("div").classes("flex-grow")

                # Bypass toggle
                with ui.row().classes("items-center gap-2"):
                    ui.switch(
                        "Bypass (Resident Architect)",
                        value=bypass_enabled,
                        on_change=lambda e: do_toggle_bypass(bool(e.value)),
                    ).props("dense").tooltip(
                        "Temporarily grant Resident Architect access without license verification"
                    )

            # Feature access table
            ui.separator().classes("mt-2")
            ui.label("Workflow Access by Tier").classes("text-sm font-semibold")

            with ui.element("div").classes("w-full overflow-x-auto"):
                with ui.element("table").classes(
                    "w-full text-xs border-collapse"
                ).style("min-width: 400px;"):
                    # Header row
                    with ui.element("tr").classes("border-b border-slate-200 dark:border-slate-700"):
                        with ui.element("th").classes("text-left p-2"):
                            ui.label("Workflow")
                        for t in LicenseTier:
                            is_current = t == tier
                            cell_class = "text-center p-2"
                            if is_current:
                                cell_class += " bg-orange-100 dark:bg-orange-900/30"
                            with ui.element("th").classes(cell_class):
                                ui.label(TIER_DISPLAY_NAMES[t]).classes(
                                    "font-semibold" if is_current else ""
                                )

                    # Data rows
                    workflow_names = [
                        ("account_explorer", "Account Explorer"),
                        ("jobs_as_code", "Jobs as Code"),
                        ("migration", "Migration"),
                        ("import_adopt", "Import & Adopt"),
                    ]
                    for feature_key, feature_name in workflow_names:
                        with ui.element("tr").classes(
                            "border-b border-slate-100 dark:border-slate-800"
                        ):
                            with ui.element("td").classes("p-2 text-left"):
                                ui.label(feature_name)
                            for t in LicenseTier:
                                is_current = t == tier
                                enabled = TIER_FEATURES[t].get(feature_key, False)
                                cell_class = "text-center p-2"
                                if is_current:
                                    cell_class += " bg-orange-50 dark:bg-orange-900/20"
                                with ui.element("td").classes(cell_class):
                                    if enabled:
                                        ui.icon("check", size="xs").classes("text-green-500")
                                    else:
                                        ui.icon("close", size="xs").classes("text-slate-300")


def _create_workflow_card(
    title: str,
    description: str,
    icon: str,
    on_click: Optional[Callable[[], None]],
    highlight: bool = False,
    disabled: bool = False,
    badge_text: Optional[str] = None,
) -> None:
    """Create a workflow selection card with consistent height."""
    card_classes = "w-full p-4"
    if highlight:
        card_classes += " border-2 border-orange-400"

    with ui.card().classes(card_classes):
        # Title row
        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.icon(icon, size="md").classes("text-slate-400")
            ui.label(title).classes("text-lg font-semibold")
            if disabled and badge_text:
                badge = ui.badge(badge_text, color="warning").props("rounded dense")
                if badge_text in {"Requires License", "Coming Soon"}:
                    badge.style("color: #000;")

        # Description with fixed height to ensure all cards match
        # 48px fits 2 lines of text comfortably
        ui.label(description).classes("text-sm text-slate-500 mt-1").style(
            "height: 48px; overflow: hidden;"
        )

        # Action button with top margin
        action = ui.button(
            "Select",
            icon="arrow_forward",
            on_click=on_click if on_click else None,
        ).props("outline").classes("mt-2")
        if disabled:
            action.disable()


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
            {"name": "actions", "label": "", "field": "actions", "align": "center"},
        ]

        rows = []
        for run in runs[:10]:  # Show last 10
            rows.append({
                "type": run.get("type", "fetch"),
                "account": f"Account {run.get('account_id', 'N/A')}",
                "timestamp": run.get("timestamp", "Unknown"),
                "status": "Complete" if run.get("success", True) else "Failed",
                "run_id": run.get("run_id", ""),
                "account_id": run.get("account_id", ""),
                "run_type": run.get("type", "fetch"),
            })

        table = ui.table(columns=columns, rows=rows, row_key="timestamp").classes("w-full")
        table.add_slot(
            "body-cell-actions",
            '''
            <q-td :props="props">
                <q-btn flat dense icon="open_in_new" size="sm" @click="$parent.$emit('load-run', props.row)" />
            </q-td>
            '''
        )
        table.on("load-run", lambda e: _load_run_and_navigate(
            e.args, state, on_step_change
        ))

        ui.label("Click a row to load that run's data into the Explore view.").classes(
            "text-xs text-slate-500 mt-2"
        )


def _load_run_and_navigate(
    row: dict,
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Load a run's data and navigate to Explore.
    
    Args:
        row: Table row data containing run information
        state: Application state to update
        on_step_change: Callback to navigate
    """
    account_id = row.get("account_id", "")
    run_id = row.get("run_id", "")
    run_type = row.get("run_type", "fetch")
    
    if not account_id or not run_id:
        ui.notify("Run data not available", type="warning")
        return
    
    output_path = Path(state.fetch.output_dir)
    
    # Find the YAML file for this run
    yaml_file = None
    
    if run_type == "fetch":
        # Look for the fetched account YAML
        account_yaml = output_path / str(account_id) / run_id / f"account_{account_id}.yaml"
        if account_yaml.exists():
            yaml_file = account_yaml
        else:
            # Try alternative path patterns
            account_dir = output_path / str(account_id) / run_id
            if account_dir.exists():
                yaml_files = list(account_dir.glob("*.yaml"))
                if yaml_files:
                    yaml_file = yaml_files[0]
    elif run_type == "normalize":
        # Look for normalized YAML
        norm_yaml = output_path / "normalized" / str(account_id) / run_id / "normalized.yaml"
        if norm_yaml.exists():
            yaml_file = norm_yaml
    
    if not yaml_file or not yaml_file.exists():
        ui.notify(f"Could not find data for run {run_id}", type="warning")
        return
    
    # Update state
    state.fetch.fetch_complete = True
    state.fetch.last_yaml_file = str(yaml_file)
    state.source_account.account_id = account_id
    
    ui.notify(f"Loaded run {run_id}", type="positive")
    
    # Navigate to Explore
    on_step_change(WorkflowStep.EXPLORE_SOURCE)


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
