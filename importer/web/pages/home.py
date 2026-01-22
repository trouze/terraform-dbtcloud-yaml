"""Home/dashboard page for the web UI."""

import json
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


def create_home_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    on_workflow_change: Callable[[WorkflowType], None],
    save_state: Optional[Callable[[], None]] = None,
) -> None:
    """Create the home/dashboard page content.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        on_workflow_change: Callback to switch workflows
        save_state: Callback to persist state changes
    """
    with ui.column().classes("w-full max-w-4xl mx-auto p-8 gap-6"):
        # License panel at the top (full width)
        _create_license_panel(state, save_state)

        # Welcome section with workflow cards
        _create_welcome_section(state, on_step_change, on_workflow_change)

        # Quick stats (if there's previous data)
        if state.fetch.fetch_complete:
            _create_quick_stats(state)

        # Recent runs
        _create_recent_runs_section(state, on_step_change)


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
                ui.badge(badge_text, color="warning").props("rounded dense")

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
