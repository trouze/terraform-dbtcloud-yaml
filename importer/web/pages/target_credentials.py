"""Target Credentials step page - configure connections and environment credentials."""

from typing import Any, Callable, Dict, List, Optional

import yaml
from nicegui import ui

from importer.web.state import (
    AppState,
    WorkflowStep,
    EnvironmentCredentialConfig,
)
from importer.web.components.credential_schemas import (
    get_credential_schema,
    get_credential_type_for_connection,
    get_dummy_credentials,
    get_sensitive_fields,
    should_show_field,
)
from importer.web.env_manager import (
    load_env_credential_config,
    save_env_credential_config,
    save_all_env_credential_configs,
    get_env_file_path,
)
from importer.web.components.connection_config import create_connection_config_section


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"

# Status colors
STATUS_GREEN = "#22C55E"  # green-500
STATUS_ORANGE = "#F97316"  # orange-500
STATUS_GRAY = "#9CA3AF"  # gray-400


def create_target_credentials_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Target Credentials step page content.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to persist state
    """
    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        # Page header
        with ui.row().classes("w-full items-center gap-3"):
            ui.icon("key", size="1.5rem").style(f"color: {DBT_TEAL};")
            ui.label("Target Credentials").classes("text-xl font-bold")
            ui.label(
                "Configure global connections and environment credentials for the target account."
            ).classes("text-slate-600 dark:text-slate-400 text-sm")

        # Prerequisite check
        if not state.deploy.configure_complete:
            _create_prerequisite_warning(state, on_step_change)
            return

        # Account info summary
        _create_account_summary(state)

        # Global connections section (moved from Configure Migration)
        _create_global_connections_section(state)

        # Load environments from YAML
        environments = _load_environments_from_yaml(state)

        if not environments:
            _create_no_environments_info(state, on_step_change, save_state)
            return

        # Initialize env_credentials state if needed
        _initialize_env_configs(state, environments, save_state)

        # Environment credentials section
        _create_environment_credentials_section(state, environments, save_state)

        # Navigation buttons
        _create_navigation_section(state, on_step_change, save_state)


def _create_prerequisite_warning(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Show warning when prerequisites aren't met."""
    with ui.card().classes("w-full p-4 border-l-4 border-yellow-500"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("warning", size="md").classes("text-yellow-500")
            ui.label("Prerequisites Required").classes("text-lg font-semibold")

        ui.label(
            "Complete the Configure Migration step before configuring target credentials."
        ).classes("mt-2 text-sm text-slate-600 dark:text-slate-400")

        with ui.row().classes("mt-4 gap-3"):
            ui.button(
                f"Go to {state.get_step_label(WorkflowStep.CONFIGURE)}",
                icon="settings",
                on_click=lambda: on_step_change(WorkflowStep.CONFIGURE),
            ).style(f"background-color: {DBT_ORANGE};")


def _create_account_summary(state: AppState) -> None:
    """Create a summary showing source and target account info."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center justify-between"):
            # Source account
            with ui.card().classes("p-3 bg-slate-50 dark:bg-slate-800/50"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("upload", size="sm").classes("text-slate-400")
                    with ui.column().classes("gap-0"):
                        ui.label("Source Account").classes("text-xs text-slate-500")
                        ui.label(
                            state.source_account.account_name
                            or state.source_credentials.account_id
                            or "Not set"
                        ).classes("font-medium")

            # Arrow
            ui.icon("arrow_forward", size="lg").classes("text-slate-300")

            # Target account
            with ui.card().classes("p-3").style(
                f"border: 2px solid {DBT_TEAL}; background: rgba(4, 115, 119, 0.05);"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("download", size="sm").style(f"color: {DBT_TEAL};")
                    with ui.column().classes("gap-0"):
                        ui.label("Target Account").classes("text-xs text-slate-500")
                        ui.label(
                            state.target_account.account_name
                            or state.target_credentials.account_id
                            or "Not set"
                        ).classes("font-medium")


def _create_global_connections_section(state: AppState) -> None:
    """Create the global connections configuration section (moved from Configure)."""
    yaml_path = state.map.last_yaml_file

    with ui.card().classes("w-full p-4"):
        with ui.row().classes("items-center gap-2 mb-4"):
            ui.icon("cable", size="sm").style(f"color: {DBT_TEAL};")
            ui.label("Global Connections").classes("font-semibold text-lg")
            ui.label(
                "Configure connection-level credentials (e.g., Snowflake account, Databricks host)"
            ).classes("text-sm text-slate-500 ml-2")

        # Use the existing connection config component
        create_connection_config_section(yaml_path=yaml_path)


def _create_no_environments_info(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Show info when no environments are selected."""
    with ui.card().classes("w-full p-6"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("info", size="lg").classes("text-blue-500")
            with ui.column().classes("gap-1"):
                ui.label("No Environments to Configure").classes("text-lg font-semibold")
                ui.label(
                    "No environments were found in the migration configuration. "
                    "This is fine if you're not migrating environments, or if credentials "
                    "are managed separately."
                ).classes("text-sm text-slate-600 dark:text-slate-400")

        ui.separator().classes("my-4")

        with ui.row().classes("justify-between"):
            ui.button(
                f"Back to {state.get_step_label(WorkflowStep.CONFIGURE)}",
                icon="arrow_back",
                on_click=lambda: on_step_change(WorkflowStep.CONFIGURE),
            ).props("outline")

            def on_continue():
                state.env_credentials.step_complete = True
                save_state()
                on_step_change(WorkflowStep.DEPLOY)

            ui.button(
                "Continue to Deploy",
                icon="arrow_forward",
                on_click=on_continue,
            ).style(f"background-color: {DBT_TEAL};")


def _load_environments_from_yaml(state: AppState) -> List[Dict[str, Any]]:
    """Load environments from the normalized YAML file.

    Returns list of environment dicts with keys:
    - id, name, project_id, project_name, connection_type
    - env_type ('development' or 'deployment')
    - deployment_type ('production', 'staging', or '')
    - dbt_version, custom_branch
    - source_values (dict with pre-fill values like schema, database)
    """
    yaml_path = state.map.last_yaml_file
    if not yaml_path:
        return []

    try:
        from pathlib import Path

        if not Path(yaml_path).exists():
            return []

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        environments = []

        # Build connection lookup for source values
        connections = {}
        for conn in data.get("globals", {}).get("connections", []):
            conn_key = conn.get("key", conn.get("name", ""))
            connections[conn_key] = conn

        # Extract environments from projects
        projects = data.get("projects", [])
        for project in projects:
            project_name = project.get("name", "Unknown Project")
            project_id = project.get("key", "")

            for env in project.get("environments", []):
                env_id = env.get("key", "")
                env_name = env.get("name", "Unknown Environment")

                # Determine environment type
                env_type = env.get("type", "deployment")
                deployment_type = env.get("deployment_type", "")
                dbt_version = env.get("dbt_version", "")
                custom_branch = env.get("custom_branch", "")

                # Determine connection type from environment or project connection
                connection_type = env.get("connection_type", "")
                connection_ref = env.get("connection")
                source_values = {}

                if connection_ref and connection_ref in connections:
                    conn_data = connections[connection_ref]
                    if not connection_type:
                        connection_type = conn_data.get("type", "")

                    # Extract source values from connection provider_config
                    provider_config = conn_data.get("provider_config", {})
                    for key in ["schema", "database", "warehouse", "role", "catalog"]:
                        if key in provider_config:
                            source_values[key] = provider_config[key]

                # Extract source values from environment credential block
                credential_block = env.get("credential", {})
                for key in [
                    "schema", "database", "default_schema", "dataset", "catalog",
                    "user", "token_name", "warehouse", "role", "num_threads",
                    "auth_type", "authentication", "auth_method",  # Authentication type
                ]:
                    if key in credential_block:
                        source_values[key] = credential_block[key]

                # Infer auth_type for Snowflake if not explicitly set but we have auth-related fields
                if "auth_type" not in source_values and connection_type == "snowflake":
                    if "private_key" in credential_block:
                        source_values["auth_type"] = "keypair"
                    elif "password" in credential_block:
                        source_values["auth_type"] = "password"

                environments.append({
                    "id": env_id,
                    "name": env_name,
                    "project_id": project_id,
                    "project_name": project_name,
                    "connection_type": connection_type,
                    "env_type": env_type,
                    "deployment_type": deployment_type,
                    "dbt_version": dbt_version,
                    "custom_branch": custom_branch,
                    "source_values": source_values,
                })

        return environments

    except Exception:
        return []


def _initialize_env_configs(
    state: AppState,
    environments: List[Dict[str, Any]],
    save_state: Callable[[], None],
) -> None:
    """Initialize environment credential configs from environments and .env."""
    # Track selected env IDs
    env_ids = set()

    for env in environments:
        env_id = env["id"]
        env_ids.add(env_id)

        # Skip if already initialized
        if env_id in state.env_credentials.env_configs:
            # Update metadata fields even if already initialized
            config = state.env_credentials.env_configs[env_id]
            config.env_type = env.get("env_type", "")
            config.deployment_type = env.get("deployment_type", "")
            config.dbt_version = env.get("dbt_version", "")
            config.custom_branch = env.get("custom_branch", "")
            config.source_values = env.get("source_values", {})
            continue

        # Determine credential type
        connection_type = env.get("connection_type", "")
        credential_type = get_credential_type_for_connection(connection_type) or ""

        # Load existing config from .env
        existing_config = load_env_credential_config(env_id)
        use_dummy = (
            existing_config.pop("use_dummy", "false").lower() == "true"
            if "use_dummy" in existing_config
            else False
        )

        # Create config
        config = EnvironmentCredentialConfig(
            env_id=env_id,
            env_name=env["name"],
            project_id=env["project_id"],
            project_name=env["project_name"],
            connection_type=connection_type,
            credential_type=credential_type,
            env_type=env.get("env_type", ""),
            deployment_type=env.get("deployment_type", ""),
            dbt_version=env.get("dbt_version", ""),
            custom_branch=env.get("custom_branch", ""),
            credential_values=existing_config,
            source_values=env.get("source_values", {}),
            use_dummy_credentials=use_dummy,
            is_saved=bool(existing_config),
        )

        state.env_credentials.set_config(config)

    # Update selected env IDs
    state.env_credentials.selected_env_ids = env_ids
    save_state()


def _create_environment_credentials_section(
    state: AppState,
    environments: List[Dict[str, Any]],
    save_state: Callable[[], None],
) -> None:
    """Create the environment credentials section with project-grouped table."""
    with ui.card().classes("w-full p-4"):
        # Header
        with ui.row().classes("items-center justify-between mb-4"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("dns", size="sm").style(f"color: {DBT_ORANGE};")
                ui.label("Environment Credentials").classes("font-semibold text-lg")
                ui.label(f"({len(environments)} environments)").classes(
                    "text-sm text-slate-500"
                )

            # Bulk actions
            ui.button(
                "Save All to .env",
                icon="save",
                on_click=lambda: _save_all_configs(state, save_state),
            ).props("outline size=sm")

        # Info banner
        with ui.card().classes(
            "w-full p-3 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 mb-4"
        ):
            with ui.row().classes("items-start gap-2"):
                ui.icon("info", size="sm").classes("text-blue-600 mt-0.5")
                ui.label(
                    "Development environments don't require credentials (users set their own). "
                    "Deployment environments need credentials to be configured."
                ).classes("text-sm text-blue-700 dark:text-blue-300")

        # Group environments by project
        projects_envs: Dict[str, List[Dict[str, Any]]] = {}
        for env in environments:
            proj_key = f"{env['project_id']}|{env['project_name']}"
            if proj_key not in projects_envs:
                projects_envs[proj_key] = []
            projects_envs[proj_key].append(env)

        # Create table for each project
        for proj_key, proj_envs in projects_envs.items():
            project_id, project_name = proj_key.split("|", 1)
            _create_project_environment_table(
                project_name=project_name,
                environments=proj_envs,
                state=state,
                save_state=save_state,
            )


def _create_project_environment_table(
    project_name: str,
    environments: List[Dict[str, Any]],
    state: AppState,
    save_state: Callable[[], None],
) -> None:
    """Create a table showing environments for a project."""
    with ui.expansion(f"Project: {project_name}", icon="folder").classes(
        "w-full mb-2"
    ).props("default-opened"):
        # Table
        columns = [
            {"name": "name", "label": "Environment", "field": "name", "align": "left"},
            {"name": "type", "label": "Type", "field": "type", "align": "left"},
            {"name": "connection", "label": "Connection", "field": "connection", "align": "left"},
            {"name": "status", "label": "Status", "field": "status", "align": "center"},
            {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
        ]

        rows = []
        for env in environments:
            config = state.env_credentials.get_config(env["id"])
            env_type = env.get("env_type", "deployment")
            is_dev = env_type == "development"

            # Determine status
            if is_dev:
                status_html = f'<span style="color: {STATUS_GRAY};">— N/A</span>'
            elif config and config.is_saved:
                if config.use_dummy_credentials:
                    status_html = f'<span style="color: {STATUS_ORANGE};">● Dummy</span>'
                else:
                    status_html = f'<span style="color: {STATUS_GREEN};">● Saved</span>'
            else:
                status_html = f'<span style="color: {STATUS_GRAY};">○ Not set</span>'

            rows.append({
                "id": env["id"],
                "name": env["name"],
                "type": "dev" if is_dev else "deploy",
                "connection": env.get("connection_type", "unknown"),
                "status": status_html,
                "is_dev": is_dev,
            })

        with ui.table(columns=columns, rows=rows, row_key="id").classes(
            "w-full"
        ) as table:
            table.add_slot(
                "body-cell-status",
                """
                <q-td :props="props">
                    <span v-html="props.row.status"></span>
                </q-td>
                """,
            )

            table.add_slot(
                "body-cell-actions",
                """
                <q-td :props="props">
                    <q-btn v-if="!props.row.is_dev" flat dense icon="edit" 
                           @click="$parent.$emit('edit', props.row)" color="primary">
                        <q-tooltip>Edit credentials</q-tooltip>
                    </q-btn>
                    <q-btn flat dense icon="visibility" 
                           @click="$parent.$emit('view', props.row)" color="grey">
                        <q-tooltip>View details</q-tooltip>
                    </q-btn>
                    <q-btn v-if="!props.row.is_dev" flat dense icon="restart_alt" 
                           @click="$parent.$emit('reset', props.row)" color="orange">
                        <q-tooltip>Reset to dummy credentials</q-tooltip>
                    </q-btn>
                </q-td>
                """,
            )

            def on_edit(e):
                env_id = e.args["id"]
                _show_edit_dialog(env_id, state, save_state)

            def on_view(e):
                env_id = e.args["id"]
                _show_view_dialog(env_id, state)

            def on_reset(e):
                env_id = e.args["id"]
                _reset_to_dummy(env_id, state, save_state)

            table.on("edit", on_edit)
            table.on("view", on_view)
            table.on("reset", on_reset)


def _reset_to_dummy(
    env_id: str,
    state: AppState,
    save_state: Callable[[], None],
) -> None:
    """Reset environment credentials to dummy values."""
    config = state.env_credentials.get_config(env_id)
    if not config:
        ui.notify(f"Configuration not found for {env_id}", type="negative")
        return

    # Get dummy credentials for this credential type
    dummy_values = get_dummy_credentials(config.credential_type)
    
    # Update config
    config.use_dummy_credentials = True
    config.credential_values = dummy_values
    config.is_saved = True
    state.env_credentials.set_config(config)
    save_state()

    # Save to .env
    try:
        save_env_credential_config(
            env_id=env_id,
            config=dummy_values,
            use_dummy=True,
        )
        ui.notify(f"Reset {config.env_name} to dummy credentials", type="positive")
        ui.navigate.reload()
    except Exception as e:
        ui.notify(f"Failed to save: {e}", type="negative")


def _show_edit_dialog(
    env_id: str,
    state: AppState,
    save_state: Callable[[], None],
) -> None:
    """Show the edit credentials dialog."""
    config = state.env_credentials.get_config(env_id)
    if not config:
        ui.notify(f"Configuration not found for {env_id}", type="negative")
        return

    credential_type = config.credential_type
    schema = get_credential_schema(credential_type) if credential_type else None

    # Form data - merge source values with existing credential values (creds take precedence)
    form_data: Dict[str, Any] = {}
    # First add source values as defaults
    for key, value in config.source_values.items():
        form_data[key] = value
    # Then overlay credential values
    for key, value in config.credential_values.items():
        form_data[key] = value

    # Initialize auth field with default if present
    if schema and schema.get("auth_modes"):
        auth_field = schema["auth_modes"].get("field", "auth_type")
        auth_default = schema["auth_modes"].get("default", "")
        if auth_field not in form_data:
            form_data[auth_field] = auth_default

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-6xl"):
        # Header
        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("edit", size="sm").style(f"color: {DBT_ORANGE};")
                ui.label(f"Edit Credentials: {config.env_name}").classes(
                    "text-lg font-semibold"
                )
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # Context info
        with ui.row().classes("w-full gap-4 mb-4"):
            ui.label(f"Project: {config.project_name}").classes("text-sm text-slate-500")
            if credential_type:
                ui.badge(credential_type.upper(), color="primary").props("outline")

        # Dummy toggle with override indicator
        # Check if source values exist that would be overridden
        has_source_values = bool(config.source_values)
        dummy_indicators = {"override": None}

        with ui.row().classes(
            "w-full items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded mb-4"
        ):
            with ui.row().classes("items-center gap-3"):
                with ui.column().classes("gap-1"):
                    ui.label("Use Dummy Credentials").classes("font-medium")
                    ui.label(
                        "Use placeholder values for testing (real values preserved)"
                    ).classes("text-xs text-slate-500")

                # Show override indicator when dummy is enabled and source values exist
                if has_source_values:
                    dummy_indicators["override"] = ui.element("div")
                    dummy_indicators["override"].set_visibility(config.use_dummy_credentials)
                    with dummy_indicators["override"]:
                        ui.badge("Overrides Source", color="yellow-8").props("dense outline").classes("text-xs")

            use_dummy = {"value": config.use_dummy_credentials}

            def on_dummy_change(e):
                use_dummy["value"] = e.value
                # Update override indicator visibility
                if dummy_indicators["override"]:
                    dummy_indicators["override"].set_visibility(e.value)

            ui.switch(value=config.use_dummy_credentials, on_change=on_dummy_change)

        # Credentials form (only show if not using dummy)
        form_container = ui.column().classes("w-full")

        def build_form():
            form_container.clear()
            with form_container:
                if not schema:
                    with ui.row().classes(
                        "items-center gap-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded"
                    ):
                        ui.icon("help", size="sm").classes("text-yellow-500")
                        ui.label(
                            f"Unknown credential type for '{config.connection_type}'"
                        ).classes("text-sm text-yellow-600")
                elif use_dummy["value"]:
                    with ui.card().classes(
                        "w-full p-4 bg-orange-50 dark:bg-orange-900/20"
                    ):
                        with ui.row().classes("items-center gap-2 mb-3"):
                            ui.icon("swap_horiz", size="sm").classes("text-orange-600")
                            ui.label("Dummy credentials will override source values").classes(
                                "text-sm font-medium text-orange-700"
                            )

                        # Show comparison: source vs dummy values
                        dummy_vals = get_dummy_credentials(credential_type)
                        source_vals = config.source_values
                        sensitive_fields = get_sensitive_fields(credential_type)

                        if dummy_vals:
                            # Table header using CSS grid
                            with ui.element("div").classes("w-full").style(
                                "display: grid; grid-template-columns: 120px 1fr 1fr; gap: 8px; margin-bottom: 8px;"
                            ):
                                ui.label("Field").classes("text-xs font-semibold text-slate-500")
                                ui.label("Source Value").classes("text-xs font-semibold text-green-600")
                                ui.label("Dummy Override").classes("text-xs font-semibold text-orange-600")

                            ui.separator().classes("mb-2")

                            # Show each field comparison
                            for field, dummy_val in dummy_vals.items():
                                is_sensitive = field in sensitive_fields
                                source_val = source_vals.get(field)

                                # Format display values
                                if is_sensitive:
                                    source_display = "••••••••" if source_val else "—"
                                    dummy_display = "••••••••"
                                else:
                                    source_display = str(source_val) if source_val else "—"
                                    dummy_display = str(dummy_val)

                                with ui.element("div").classes("w-full").style(
                                    "display: grid; grid-template-columns: 120px 1fr 1fr; gap: 8px; align-items: center;"
                                ):
                                    ui.label(field).classes("text-xs font-mono text-slate-600")
                                    # Source value
                                    with ui.element("div").classes("flex items-center gap-1"):
                                        if source_val:
                                            ui.label(source_display).classes(
                                                "text-xs font-mono text-green-700 bg-green-100 px-2 py-0.5 rounded"
                                            )
                                        else:
                                            ui.label("—").classes("text-xs text-slate-400")
                                    # Dummy value (with arrow if overriding)
                                    with ui.element("div").classes("flex items-center gap-1"):
                                        if source_val:
                                            ui.icon("arrow_forward", size="xs").classes("text-orange-400")
                                        ui.label(dummy_display).classes(
                                            "text-xs font-mono text-orange-700 bg-orange-100 px-2 py-0.5 rounded"
                                        )
                else:
                    _create_credential_form_fields(
                        schema=schema,
                        credential_type=credential_type,
                        form_data=form_data,
                        source_values=config.source_values,
                    )

        build_form()

        # Footer buttons
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("outline")

            def on_save():
                # Update config
                config.use_dummy_credentials = use_dummy["value"]

                if use_dummy["value"]:
                    config.credential_values = get_dummy_credentials(credential_type)
                else:
                    config.credential_values = {
                        k: v for k, v in form_data.items() if v is not None and v != ""
                    }

                config.is_saved = True
                state.env_credentials.set_config(config)
                save_state()

                # Save to .env
                try:
                    save_env_credential_config(
                        env_id=env_id,
                        config=config.credential_values,
                        use_dummy=config.use_dummy_credentials,
                    )
                    ui.notify(f"Saved credentials for {config.env_name}", type="positive")
                    dialog.close()
                    ui.navigate.reload()
                except Exception as e:
                    ui.notify(f"Failed to save: {e}", type="negative")

            ui.button("Save to .env", icon="save", on_click=on_save).style(
                f"background-color: {DBT_TEAL};"
            )

    dialog.open()


def _create_credential_form_fields(
    schema: Dict[str, Any],
    credential_type: str,
    form_data: Dict[str, Any],
    source_values: Dict[str, Any],
) -> None:
    """Create form fields for a credential schema with proper conditional visibility."""
    required_fields = schema.get("required", [])
    optional_fields = schema.get("optional", [])
    sensitive_fields = schema.get("sensitive", [])
    descriptions = schema.get("descriptions", {})
    defaults = schema.get("defaults", {})
    conditionals = schema.get("conditional", {})
    auth_modes = schema.get("auth_modes", {})

    # Track conditional containers for visibility updates
    conditional_containers: Dict[str, ui.element] = {}

    def update_conditional_visibility():
        """Update visibility of all conditional fields based on current form data."""
        for field, condition in conditionals.items():
            container = conditional_containers.get(field)
            if container:
                visible = should_show_field(credential_type, field, form_data)
                container.set_visibility(visible)

    # Auth mode selector (if applicable)
    if auth_modes:
        auth_field = auth_modes.get("field", "auth_type")
        auth_options = auth_modes.get("options", [])
        auth_default = auth_modes.get("default", auth_options[0] if auth_options else "")
        current_auth = form_data.get(auth_field, auth_default)
        source_auth = source_values.get(auth_field)

        # Ensure form_data has auth field set for conditional logic
        form_data[auth_field] = current_auth

        # Track if auth matches source
        has_auth_source = source_auth is not None
        is_auth_from_source = has_auth_source and str(current_auth) == str(source_auth)
        auth_indicators = {"from_source": None, "override": None}

        def update_auth_indicators(new_value):
            if has_auth_source:
                matches = str(new_value) == str(source_auth)
                if auth_indicators["from_source"]:
                    auth_indicators["from_source"].set_visibility(matches)
                if auth_indicators["override"]:
                    auth_indicators["override"].set_visibility(not matches)

        # UI references for dynamic updates
        auth_select_ref = {"select": None}

        def reset_auth_to_source():
            """Reset authentication to source value."""
            if source_auth is not None and auth_select_ref["select"]:
                auth_select_ref["select"].value = source_auth
                form_data[auth_field] = source_auth
                update_auth_indicators(source_auth)
                update_conditional_visibility()

        # Use CSS grid for consistent alignment with fields
        # Grid: [Label 140px] [Select flex] [Indicator 100px] [Reset 40px]
        with ui.element("div").classes("w-full mb-4").style(
            "display: grid; grid-template-columns: 140px 1fr 100px 40px; gap: 12px; align-items: center;"
        ):
            # Column 1: Label
            ui.label("Authentication:").classes("text-sm font-medium text-right")

            # Column 2: Select dropdown
            def on_auth_change(e, field=auth_field):
                form_data[field] = e.value
                update_auth_indicators(e.value)
                update_conditional_visibility()

            auth_select_ref["select"] = ui.select(
                options=auth_options,
                value=current_auth,
                label=descriptions.get(auth_field, "Authentication Type"),
                on_change=on_auth_change,
            ).props("dense outlined").classes("w-full")

            # Column 3: Source indicator
            with ui.element("div").classes("flex justify-center"):
                if has_auth_source:
                    auth_indicators["from_source"] = ui.element("div")
                    auth_indicators["from_source"].set_visibility(is_auth_from_source)
                    with auth_indicators["from_source"]:
                        ui.badge("From source", color="green").props("dense outline").classes("text-xs")

                    auth_indicators["override"] = ui.element("div")
                    auth_indicators["override"].set_visibility(not is_auth_from_source)
                    with auth_indicators["override"]:
                        ui.badge("Override", color="yellow-8").props("dense outline").classes("text-xs")

            # Column 4: Reset button
            with ui.element("div").classes("flex justify-center"):
                if has_auth_source:
                    ui.button(
                        icon="restore",
                        on_click=reset_auth_to_source,
                    ).props("flat dense size=sm").tooltip(f"Reset to source: {source_auth}").classes(
                        "text-slate-400 hover:text-green-500"
                    )

    # Required fields
    if required_fields:
        ui.label("Required Fields").classes(
            "text-sm font-medium text-slate-600 dark:text-slate-400 mb-2"
        )
        with ui.column().classes("gap-3 mb-4"):
            for field in required_fields:
                # Skip auth field if rendered above
                if auth_modes and field == auth_modes.get("field"):
                    continue

                is_conditional = field in conditionals
                if is_conditional:
                    initial_visible = should_show_field(credential_type, field, form_data)
                    container = ui.column().classes("w-full")
                    container.set_visibility(initial_visible)
                    conditional_containers[field] = container
                    with container:
                        _create_single_field(
                            field=field,
                            description=descriptions.get(field, ""),
                            is_required=True,
                            is_sensitive=field in sensitive_fields,
                            current_value=form_data.get(field, defaults.get(field, "")),
                            source_value=source_values.get(field),
                            form_data=form_data,
                        )
                else:
                    _create_single_field(
                        field=field,
                        description=descriptions.get(field, ""),
                        is_required=True,
                        is_sensitive=field in sensitive_fields,
                        current_value=form_data.get(field, defaults.get(field, "")),
                        source_value=source_values.get(field),
                        form_data=form_data,
                    )

    # Optional fields
    if optional_fields:
        ui.label("Optional Fields").classes(
            "text-sm font-medium text-slate-600 dark:text-slate-400 mb-2 mt-4"
        )
        with ui.column().classes("gap-3"):
            for field in optional_fields:
                # Skip auth field if rendered above
                if auth_modes and field == auth_modes.get("field"):
                    continue

                is_conditional = field in conditionals
                if is_conditional:
                    initial_visible = should_show_field(credential_type, field, form_data)
                    container = ui.column().classes("w-full")
                    container.set_visibility(initial_visible)
                    conditional_containers[field] = container
                    with container:
                        _create_single_field(
                            field=field,
                            description=descriptions.get(field, ""),
                            is_required=False,
                            is_sensitive=field in sensitive_fields,
                            current_value=form_data.get(field, defaults.get(field, "")),
                            source_value=source_values.get(field),
                            form_data=form_data,
                        )
                else:
                    _create_single_field(
                        field=field,
                        description=descriptions.get(field, ""),
                        is_required=False,
                        is_sensitive=field in sensitive_fields,
                        current_value=form_data.get(field, defaults.get(field, "")),
                        source_value=source_values.get(field),
                        form_data=form_data,
                    )


def _create_single_field(
    field: str,
    description: str,
    is_required: bool,
    is_sensitive: bool,
    current_value: Any,
    source_value: Optional[Any],
    form_data: Dict[str, Any],
) -> None:
    """Create a single form field with clean columnar layout using CSS grid."""
    label_text = field.replace("_", " ").title()
    if is_required:
        label_text += " *"

    # Initialize form data
    form_data[field] = current_value

    # Track if value matches source (for showing/hiding badges)
    has_source = source_value is not None and not is_sensitive
    is_from_source = has_source and str(current_value) == str(source_value)

    # UI element references for dynamic updates
    indicators = {"from_source": None, "override": None, "input": None}

    def update_indicators(new_value):
        """Update the source indicators based on whether value matches source."""
        if has_source:
            matches_source = str(new_value) == str(source_value)
            if indicators["from_source"]:
                indicators["from_source"].set_visibility(matches_source)
            if indicators["override"]:
                indicators["override"].set_visibility(not matches_source)

    def on_change(e, f=field):
        form_data[f] = e.value
        update_indicators(e.value)

    def reset_to_source():
        """Reset the field to its source value."""
        if source_value is not None and indicators["input"]:
            indicators["input"].value = str(source_value)
            form_data[field] = source_value
            update_indicators(source_value)

    # Determine field type
    is_number = field in ["num_threads", "threads", "port"]
    is_boolean = field in ["use_latest_adapter"]

    # Use CSS grid for precise column alignment
    # Grid: [Label 140px] [Input flex] [Indicator 100px] [Reset 40px]
    with ui.element("div").classes("w-full").style(
        "display: grid; grid-template-columns: 140px 1fr 100px 40px; gap: 12px; align-items: center;"
    ):
        # Column 1: Label
        ui.label(label_text).classes("text-sm text-right").tooltip(description)

        # Column 2: Input field
        if is_boolean:
            ui.switch(value=bool(current_value), on_change=on_change)
        elif is_number:
            inp = ui.input(
                value=str(current_value) if current_value else "",
                placeholder=description or f"Enter {field}",
                on_change=on_change,
            ).props("dense outlined type=number").classes("w-full")
            indicators["input"] = inp
        elif is_sensitive:
            inp = ui.input(
                value=str(current_value) if current_value else "",
                password=True,
                password_toggle_button=True,
                placeholder="••••••••" if current_value else description,
                on_change=on_change,
            ).props("dense outlined").classes("w-full")
            indicators["input"] = inp
        else:
            inp = ui.input(
                value=str(current_value) if current_value else "",
                placeholder=description or f"Enter {field}",
                on_change=on_change,
            ).props("dense outlined").classes("w-full")
            indicators["input"] = inp

        # Column 3: Source indicator
        with ui.element("div").classes("flex justify-center"):
            if has_source:
                # "From source" badge
                indicators["from_source"] = ui.element("div")
                indicators["from_source"].set_visibility(is_from_source)
                with indicators["from_source"]:
                    ui.badge("From source", color="green").props("dense outline").classes("text-xs")

                # "Override" badge
                indicators["override"] = ui.element("div")
                indicators["override"].set_visibility(not is_from_source)
                with indicators["override"]:
                    ui.badge("Override", color="yellow-8").props("dense outline").classes("text-xs")

        # Column 4: Reset button
        with ui.element("div").classes("flex justify-center"):
            if has_source:
                ui.button(
                    icon="restore",
                    on_click=reset_to_source,
                ).props("flat dense size=sm").tooltip(f"Reset to source: {source_value}").classes(
                    "text-slate-400 hover:text-green-500"
                )


def _show_view_dialog(env_id: str, state: AppState) -> None:
    """Show the view environment details dialog."""
    config = state.env_credentials.get_config(env_id)
    if not config:
        ui.notify(f"Configuration not found for {env_id}", type="negative")
        return

    is_dev = config.env_type == "development"

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
        # Header
        with ui.row().classes("w-full items-center justify-between mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("visibility", size="sm").classes("text-slate-500")
                ui.label(f"Environment: {config.env_name}").classes(
                    "text-lg font-semibold"
                )
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # Tabs
        with ui.tabs().classes("w-full") as tabs:
            overview_tab = ui.tab("Overview", icon="info")
            credentials_tab = ui.tab("Credentials", icon="key")

        with ui.tab_panels(tabs, value=overview_tab).classes("w-full"):
            # Overview panel
            with ui.tab_panel(overview_tab):
                with ui.column().classes("gap-3"):
                    _detail_row("Project", config.project_name)
                    _detail_row("Connection Type", config.connection_type or "Not set")
                    _detail_row("Environment Type", config.env_type or "deployment")
                    if config.deployment_type:
                        _detail_row("Deployment Type", config.deployment_type)
                    _detail_row("dbt Version", config.dbt_version or "Default")
                    _detail_row(
                        "Custom Branch",
                        config.custom_branch or "Default branch",
                    )

            # Credentials panel
            with ui.tab_panel(credentials_tab):
                if is_dev:
                    with ui.row().classes(
                        "items-center gap-2 p-3 bg-slate-50 dark:bg-slate-800/50 rounded"
                    ):
                        ui.icon("info", size="sm").classes("text-slate-400")
                        ui.label(
                            "Development environments don't require credentials. "
                            "Users configure their own development credentials in dbt Cloud."
                        ).classes("text-sm text-slate-600")
                else:
                    with ui.column().classes("gap-3"):
                        _detail_row(
                            "Credential Type",
                            config.credential_type.upper()
                            if config.credential_type
                            else "Unknown",
                        )

                        # Status
                        if config.is_saved:
                            if config.use_dummy_credentials:
                                status_text = "● Dummy credentials"
                                status_color = STATUS_ORANGE
                            else:
                                status_text = "● Saved (real credentials)"
                                status_color = STATUS_GREEN
                        else:
                            status_text = "○ Not configured"
                            status_color = STATUS_GRAY

                        with ui.row().classes("items-center gap-2"):
                            ui.label("Status:").classes("text-sm text-slate-500 w-32")
                            ui.label(status_text).style(f"color: {status_color};")

                        # Auth type if present
                        if config.credential_values:
                            auth_keys = ["auth_type", "authentication", "_auth_mode"]
                            for key in auth_keys:
                                if key in config.credential_values:
                                    _detail_row(
                                        "Auth Type",
                                        config.credential_values[key],
                                    )
                                    break

                            # List configured fields (not sensitive)
                            sensitive = get_sensitive_fields(config.credential_type)
                            configured = [
                                k
                                for k in config.credential_values.keys()
                                if k not in sensitive and config.credential_values[k]
                            ]
                            if configured:
                                _detail_row(
                                    "Fields Configured",
                                    ", ".join(configured),
                                )

        # Footer
        with ui.row().classes("w-full justify-end mt-4"):
            ui.button("Close", on_click=dialog.close).props("outline")

    dialog.open()


def _detail_row(label: str, value: str) -> None:
    """Create a detail row for the view dialog."""
    with ui.row().classes("items-center gap-2"):
        ui.label(f"{label}:").classes("text-sm text-slate-500 w-32 min-w-32")
        ui.label(value).classes("text-sm font-medium")


def _save_all_configs(
    state: AppState,
    save_state: Callable[[], None],
) -> None:
    """Save all environment credential configs to .env."""
    saved_count = 0

    for env_id in state.env_credentials.selected_env_ids:
        config = state.env_credentials.get_config(env_id)
        if not config:
            continue

        # Skip development environments
        if config.env_type == "development":
            continue

        # Get values to save
        if config.use_dummy_credentials:
            values_to_save = get_dummy_credentials(config.credential_type)
        else:
            values_to_save = config.credential_values.copy() if config.credential_values else {}

        # Filter mutually exclusive fields based on auth_type (for Snowflake)
        # When auth_type is 'keypair', password should not be set
        # When auth_type is 'password', private_key/private_key_passphrase should not be set
        auth_type = values_to_save.get("auth_type", "")
        if auth_type == "keypair":
            values_to_save.pop("password", None)
        elif auth_type == "password":
            values_to_save.pop("private_key", None)
            values_to_save.pop("private_key_passphrase", None)

        # Always include credential_type - required by Terraform
        if config.credential_type:
            values_to_save["credential_type"] = config.credential_type

        if values_to_save or config.use_dummy_credentials:
            try:
                save_env_credential_config(
                    env_id=env_id,
                    config=values_to_save,
                    use_dummy=config.use_dummy_credentials,
                )
                config.is_saved = True
                state.env_credentials.set_config(config)
                saved_count += 1
            except Exception:
                pass

    save_state()

    if saved_count > 0:
        env_path = get_env_file_path()
        ui.notify(
            f"Saved {saved_count} environment credential(s) to {env_path}",
            type="positive",
        )
        ui.navigate.reload()
    else:
        ui.notify("No credentials to save", type="warning")


def _create_navigation_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the navigation buttons section."""
    with ui.row().classes("w-full justify-between mt-4"):
        # Back button
        ui.button(
            f"Back to {state.get_step_label(WorkflowStep.CONFIGURE)}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.CONFIGURE),
        ).props("outline")

        # Continue button
        def on_continue():
            state.env_credentials.step_complete = True
            save_state()
            on_step_change(WorkflowStep.DEPLOY)

        ui.button(
            "Continue to Deploy",
            icon="arrow_forward",
            on_click=on_continue,
        ).style(f"background-color: {DBT_TEAL};")
