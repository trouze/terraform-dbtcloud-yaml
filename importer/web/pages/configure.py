"""Configure Migration step page - provider config and migration summary."""

from typing import Callable

from nicegui import ui

from importer.web.state import AppState, WorkflowStep
from importer.web.utils.yaml_viewer import (
    create_migration_summary_card,
    create_yaml_viewer_dialog,
)


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"


def create_configure_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Configure Migration step page content.

    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to persist state
    """
    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        # Page header
        with ui.row().classes("w-full items-center gap-3"):
            ui.icon("settings", size="1.5rem").style(f"color: {DBT_ORANGE};")
            ui.label("Configure Migration").classes("text-xl font-bold")
            ui.label(
                "Review migration summary and configure provider settings before deployment."
            ).classes("text-slate-600 dark:text-slate-400 text-sm")

        # Prerequisite check
        if not state.map.normalize_complete:
            _create_prerequisite_warning(state, on_step_change, "Scope")
            return
        
        if not state.target_credentials.is_complete():
            _create_prerequisite_warning(state, on_step_change, "Target Credentials")
            return

        # Account info summary row
        _create_account_summary(state)

        # Main content - two column layout
        with ui.row().classes("w-full gap-4 items-start"):
            # Left column: Migration Summary
            with ui.column().classes("flex-1 min-w-[400px] gap-4"):
                _create_migration_summary(state)
                
                # Mapping file status (if matches exist)
                if state.map.confirmed_mappings:
                    _create_mapping_summary(state)
            
            # Right column: Provider Configuration
            with ui.column().classes("flex-1 min-w-[400px] gap-4"):
                _create_provider_config_section(state, save_state)

        # Navigation buttons
        _create_navigation_section(state, on_step_change, save_state)


def _create_prerequisite_warning(
    state: AppState, 
    on_step_change: Callable[[WorkflowStep], None],
    missing: str,
) -> None:
    """Show warning when prerequisites aren't met."""
    with ui.card().classes("w-full p-4 border-l-4 border-yellow-500"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("warning", size="md").classes("text-yellow-500")
            ui.label(f"Prerequisites Required: {missing}").classes("text-lg font-semibold")

        ui.label(
            "Complete previous steps before configuring the migration."
        ).classes("mt-2 text-sm text-slate-600 dark:text-slate-400")

        with ui.row().classes("mt-4 gap-3"):
            if not state.map.normalize_complete:
                ui.button(
                    f"Go to {state.get_step_label(WorkflowStep.SCOPE)}",
                    icon="tune",
                    on_click=lambda: on_step_change(WorkflowStep.SCOPE),
                ).style(f"background-color: {DBT_ORANGE};")
            elif not state.target_credentials.is_complete():
                ui.button(
                    f"Go to {state.get_step_label(WorkflowStep.FETCH_TARGET)}",
                    icon="cloud_download",
                    on_click=lambda: on_step_change(WorkflowStep.FETCH_TARGET),
                ).style(f"background-color: {DBT_TEAL};")


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
                        ui.label(state.source_account.account_name or state.source_credentials.account_id or "Not set").classes("font-medium")
                        if state.source_account.host_url:
                            ui.label(state.source_account.host_url).classes("text-xs text-slate-500 font-mono")
            
            # Arrow
            ui.icon("arrow_forward", size="lg").classes("text-slate-300")
            
            # Target account
            with ui.card().classes("p-3").style(f"border: 2px solid {DBT_TEAL}; background: rgba(4, 115, 119, 0.05);"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("download", size="sm").style(f"color: {DBT_TEAL};")
                    with ui.column().classes("gap-0"):
                        ui.label("Target Account").classes("text-xs text-slate-500")
                        ui.label(state.target_account.account_name or state.target_credentials.account_id or "Not set").classes("font-medium")
                        if state.target_account.host_url:
                            ui.label(state.target_account.host_url).classes("text-xs text-slate-500 font-mono")


def _create_migration_summary(state: AppState) -> None:
    """Create a summary card showing what will be deployed from the YAML file."""
    yaml_path = state.map.last_yaml_file

    def open_yaml_viewer():
        if yaml_path:
            dialog = create_yaml_viewer_dialog(
                yaml_path,
                title="Migration Configuration"
            )
            dialog.open()

    create_migration_summary_card(
        yaml_path=yaml_path,
        on_view_yaml=open_yaml_viewer,
        show_yaml_button=True,
    )


def _create_mapping_summary(state: AppState) -> None:
    """Create a summary of confirmed resource mappings for import."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("link", size="sm").style(f"color: {DBT_TEAL};")
            ui.label("Resource Mappings").classes("font-semibold")
        
        mapping_count = len(state.map.confirmed_mappings)
        
        with ui.row().classes("items-center gap-4"):
            with ui.column().classes("gap-0"):
                ui.label(str(mapping_count)).classes("text-2xl font-bold").style(f"color: {DBT_TEAL};")
                ui.label("resources to import").classes("text-xs text-slate-500")
            
            if state.map.mapping_file_valid:
                with ui.row().classes("items-center gap-1"):
                    ui.icon("check_circle", size="sm").classes("text-green-500")
                    ui.label("Mapping file saved").classes("text-sm text-green-600")
            else:
                with ui.row().classes("items-center gap-1"):
                    ui.icon("warning", size="sm").classes("text-amber-500")
                    ui.label("Mapping file not saved").classes("text-sm text-amber-600")
        
        if state.map.mapping_file_path:
            ui.label(state.map.mapping_file_path).classes("text-xs text-slate-500 font-mono mt-2")
        
        # Show summary of mapped resource types
        if state.map.confirmed_mappings:
            type_counts = {}
            for mapping in state.map.confirmed_mappings:
                res_type = mapping.get("resource_type", "Unknown")
                type_counts[res_type] = type_counts.get(res_type, 0) + 1
            
            ui.separator().classes("my-2")
            with ui.row().classes("flex-wrap gap-2"):
                for res_type, count in sorted(type_counts.items()):
                    ui.label(f"{res_type}: {count}").classes(
                        "text-xs px-2 py-1 rounded bg-slate-100 dark:bg-slate-800"
                    )


def _create_provider_config_section(state: AppState, save_state: Callable[[], None]) -> None:
    """Create the provider configuration section."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("code", size="sm").style(f"color: {DBT_ORANGE};")
            ui.label("Provider Configuration").classes("font-semibold")
        
        ui.label(
            "Configure the dbt Cloud Terraform provider settings."
        ).classes("text-sm text-slate-500 mb-3")
        
        # Host URL
        ui.input(
            label="Host URL",
            value=state.target_credentials.host_url,
            placeholder="https://cloud.getdbt.com",
        ).classes("w-full").props("outlined dense")
        
        # Token type select
        with ui.row().classes("w-full items-center gap-4 mt-3"):
            ui.label("Token Type:").classes("text-sm")
            ui.radio(
                options={"service_token": "Service Token", "user_token": "User Token"},
                value=state.target_credentials.token_type,
            ).props("inline").on(
                "update:model-value", 
                lambda e: _update_token_type(state, e.args, save_state)
            )
        
        # Info about token types
        with ui.card().classes("w-full mt-3 p-2 bg-slate-50 dark:bg-slate-800/50"):
            ui.label("Token Types:").classes("text-xs font-semibold text-slate-600")
            ui.label(
                "• Service Token: Recommended for automation and CI/CD pipelines"
            ).classes("text-xs text-slate-500")
            ui.label(
                "• User Token: Your personal API token from Account Settings"
            ).classes("text-xs text-slate-500")
        
        ui.separator().classes("my-4")
        
        # Migration Options
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("tune", size="sm").style(f"color: {DBT_TEAL};")
            ui.label("Migration Options").classes("font-semibold")
        
        # Disable scheduled triggers toggle
        def on_toggle_triggers(e):
            state.deploy.disable_job_triggers = e.value
            save_state()
        
        with ui.row().classes("w-full items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded"):
            with ui.column().classes("gap-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("schedule_send", size="sm").classes("text-amber-500")
                    ui.label("Disable Scheduled Triggers").classes("font-medium")
                ui.label(
                    "Jobs will remain active (is_active=true) but all schedule triggers "
                    "will be set to false, preventing automatic runs during migration."
                ).classes("text-xs text-slate-500 max-w-lg")
            
            ui.switch(
                value=state.deploy.disable_job_triggers,
                on_change=on_toggle_triggers,
            )
        
        if state.deploy.disable_job_triggers:
            with ui.card().classes("w-full mt-2 p-2 border-l-2 border-amber-500 bg-amber-50 dark:bg-amber-900/20"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("info", size="xs").classes("text-amber-600")
                    ui.label(
                        "Job triggers will be disabled. Remember to re-enable them after migration."
                    ).classes("text-xs text-amber-700 dark:text-amber-300")


def _update_token_type(state: AppState, value: str, save_state: Callable[[], None]) -> None:
    """Update the token type setting."""
    state.target_credentials.token_type = value
    save_state()


def _create_navigation_section(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the navigation buttons section."""
    with ui.row().classes("w-full justify-between mt-4"):
        # Back button
        ui.button(
            f"Back to {state.get_step_label(WorkflowStep.MATCH)}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.MATCH),
        ).props("outline")

        # Continue button - goes to Target Credentials
        def on_continue():
            # Mark configure step as complete
            state.deploy.configure_complete = True
            save_state()
            on_step_change(WorkflowStep.TARGET_CREDENTIALS)
        
        ui.button(
            f"Continue to {state.get_step_label(WorkflowStep.TARGET_CREDENTIALS)}",
            icon="arrow_forward",
            on_click=on_continue,
        ).style(f"background-color: {DBT_ORANGE};")
