"""Multi-step wizard dialog for creating new projects (US-085 through US-089).

Opens from the "New Project" button on the home page and guides the user
through 4 steps:
  1. Project basics (name, workflow type, description)
  2. Import credentials (start fresh, import from .env, copy from project)
  3. Output configuration (source/target/normalized dirs, timestamp toggle)
  4. Summary & create

See PRD 21.02-Project-Management.md for the full specification.
"""

import json
import time
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.project_manager import (
    OutputConfig,
    ProjectConfig,
    ProjectManager,
)
from importer.web.state import WorkflowType


# Colors matching the app theme
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"

WORKFLOW_OPTIONS = [
    ("migration", "Migration", "Full account migration workflow"),
    ("account_explorer", "Account Explorer", "Explore & audit a dbt Cloud account"),
    ("jobs_as_code", "Jobs as Code", "Generate jobs-as-code YAML"),
    ("import_adopt", "Import & Adopt", "Import existing resources into Terraform"),
]

CREDENTIAL_MODES = [
    ("fresh", "Start fresh", "No credential import — configure credentials later"),
    ("env_file", "Import from .env file", "Copy credentials from an existing .env file"),
    ("project", "Copy from existing project", "Re-use credentials from another project"),
]


def show_new_project_wizard(
    project_manager: ProjectManager,
    on_created: Callable[[ProjectConfig], None],
) -> None:
    """Show the multi-step new project wizard dialog.

    Args:
        project_manager: The ProjectManager instance for CRUD operations.
        on_created: Callback invoked with the new ProjectConfig on success.
    """
    # ---- Wizard state (mutable refs) ------------------------------------
    wizard_data: dict = {
        "name": "",
        "description": "",
        "workflow_type": "migration",
        "slug": "",
        # Step 2: credentials
        "cred_mode": "fresh",
        "env_file_path": "",
        "copy_project_slug": "",
        "import_source": True,
        "import_target": True,
        # Step 3: output config
        "base_dir": "outputs",
        "use_timestamps": True,
    }
    current_step = {"value": 0}
    validation_error = {"value": ""}

    # ---- Helpers --------------------------------------------------------

    def _update_slug() -> None:
        wizard_data["slug"] = ProjectManager.slugify(wizard_data["name"])
        if slug_label:
            slug_label.set_text(f"Slug: {wizard_data['slug']}" if wizard_data["slug"] else "")

    def _validate_step_0() -> bool:
        name = wizard_data["name"].strip()
        if len(name) < 3:
            validation_error["value"] = "Project name must be at least 3 characters"
            return False
        if len(name) > 100:
            validation_error["value"] = "Project name must be 100 characters or fewer"
            return False
        slug = ProjectManager.slugify(name)
        if not slug:
            validation_error["value"] = "Project name produces an empty slug"
            return False
        if project_manager.project_exists(slug):
            validation_error["value"] = f"A project with slug '{slug}' already exists"
            return False
        if not wizard_data["workflow_type"]:
            validation_error["value"] = "Please select a workflow type"
            return False
        validation_error["value"] = ""
        return True

    def _go_next() -> None:
        step = current_step["value"]
        if step == 0 and not _validate_step_0():
            if error_label:
                error_label.set_text(validation_error["value"])
                error_label.set_visibility(True)
            return
        if error_label:
            error_label.set_visibility(False)
        current_step["value"] = min(step + 1, 3)
        _refresh_steps()

    def _go_back() -> None:
        current_step["value"] = max(current_step["value"] - 1, 0)
        if error_label:
            error_label.set_visibility(False)
        _refresh_steps()

    def _refresh_steps() -> None:
        step = current_step["value"]
        for i, container in enumerate(step_containers):
            container.set_visibility(i == step)
        # Update stepper indicators
        for i, (indicator, _label) in enumerate(step_indicators):
            if i < step:
                indicator.classes(replace="w-8 h-8 rounded-full flex items-center justify-center text-white bg-green-600")
                indicator.clear()
                with indicator:
                    ui.icon("check", size="sm")
            elif i == step:
                indicator.classes(replace="w-8 h-8 rounded-full flex items-center justify-center text-white bg-blue-600")
                indicator.clear()
                with indicator:
                    ui.label(str(i + 1)).classes("text-sm font-bold")
            else:
                indicator.classes(replace="w-8 h-8 rounded-full flex items-center justify-center text-gray-400 bg-gray-700")
                indicator.clear()
                with indicator:
                    ui.label(str(i + 1)).classes("text-sm")
        # Button states
        back_btn.set_visibility(step > 0)
        next_btn.set_visibility(step < 3)
        create_btn.set_visibility(step == 3)
        # Refresh summary if on step 3
        if step == 3:
            _refresh_summary()

    def _refresh_summary() -> None:
        if summary_container is None:
            return
        summary_container.clear()
        wf_name = dict((k, n) for k, n, _ in WORKFLOW_OPTIONS).get(wizard_data["workflow_type"], "")
        cred_name = dict((k, n) for k, n, _ in CREDENTIAL_MODES).get(wizard_data["cred_mode"], "")
        with summary_container:
            with ui.column().classes("gap-2 w-full"):
                ui.label("Project Name").classes("text-xs text-gray-400")
                ui.label(wizard_data["name"]).classes("text-lg font-semibold")
                ui.label(f"Slug: {wizard_data['slug']}").classes("text-xs text-gray-500")

                ui.separator()

                ui.label("Workflow Type").classes("text-xs text-gray-400")
                ui.label(wf_name).classes("font-medium")

                if wizard_data["description"]:
                    ui.separator()
                    ui.label("Description").classes("text-xs text-gray-400")
                    ui.label(wizard_data["description"]).classes("text-sm")

                ui.separator()

                ui.label("Credentials").classes("text-xs text-gray-400")
                ui.label(cred_name).classes("text-sm")
                if wizard_data["cred_mode"] == "env_file" and wizard_data["env_file_path"]:
                    ui.label(f"File: {wizard_data['env_file_path']}").classes("text-xs text-gray-500")
                elif wizard_data["cred_mode"] == "project" and wizard_data["copy_project_slug"]:
                    ui.label(f"From: {wizard_data['copy_project_slug']}").classes("text-xs text-gray-500")

                ui.separator()

                ui.label("Output Directories").classes("text-xs text-gray-400")
                ui.label(f"Base: {wizard_data['base_dir']}").classes("text-xs")
                ui.label(f"Source: {wizard_data['base_dir']}/source").classes("text-xs")
                ui.label(f"Target: {wizard_data['base_dir']}/target").classes("text-xs")
                ui.label(f"Normalized: {wizard_data['base_dir']}/normalized").classes("text-xs")
                ts_text = "Yes" if wizard_data["use_timestamps"] else "No"
                ui.label(f"Timestamped subdirs: {ts_text}").classes("text-xs")

    async def _create_project() -> None:
        if not _validate_step_0():
            ui.notify("Validation failed — go back to fix errors", type="negative")
            return
        create_btn.props("loading")
        try:
            output_config = OutputConfig(
                base_dir=wizard_data["base_dir"],
                use_timestamps=wizard_data["use_timestamps"],
            )
            # region agent log
            try:
                payload = {
                    "sessionId": "db419a",
                    "runId": "pre-fix",
                    "hypothesisId": "H24",
                    "location": "new_project_wizard.py:_create_project",
                    "message": "new project wizard submitted base_dir config",
                    "data": {
                        "base_dir": output_config.base_dir,
                        "source_dir": output_config.source_dir,
                        "target_dir": output_config.target_dir,
                        "normalized_dir": output_config.normalized_dir,
                    },
                    "timestamp": int(time.time() * 1000),
                }
                with open(
                    "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-db419a.log",
                    "a",
                    encoding="utf-8",
                ) as f:
                    f.write(json.dumps(payload, ensure_ascii=True) + "\n")
            except Exception:
                pass
            # endregion
            config = project_manager.create_project(
                name=wizard_data["name"].strip(),
                workflow_type=WorkflowType(wizard_data["workflow_type"]),
                description=wizard_data["description"].strip(),
                output_config=output_config,
            )
            # Handle credential import
            if wizard_data["cred_mode"] == "env_file" and wizard_data["env_file_path"]:
                try:
                    project_manager.import_credentials(
                        config.slug,
                        wizard_data["env_file_path"],
                        source=wizard_data["import_source"],
                        target=wizard_data["import_target"],
                    )
                except Exception as exc:
                    ui.notify(f"Credentials import failed: {exc}", type="warning")

            elif wizard_data["cred_mode"] == "project" and wizard_data["copy_project_slug"]:
                try:
                    src_path = project_manager.get_project_path(wizard_data["copy_project_slug"])
                    if wizard_data["import_source"] and (src_path / ".env.source").exists():
                        project_manager.import_credentials(
                            config.slug,
                            str(src_path / ".env.source"),
                            source=True,
                            target=False,
                        )
                    if wizard_data["import_target"] and (src_path / ".env.target").exists():
                        project_manager.import_credentials(
                            config.slug,
                            str(src_path / ".env.target"),
                            source=False,
                            target=True,
                        )
                except Exception as exc:
                    ui.notify(f"Credential copy failed: {exc}", type="warning")

            ui.notify(f"Project '{config.name}' created successfully!", type="positive")
            dialog.close()
            on_created(config)

        except Exception as exc:
            ui.notify(f"Failed to create project: {exc}", type="negative")
        finally:
            create_btn.props(remove="loading")

    # ---- Build the dialog -----------------------------------------------

    slug_label: Optional[ui.label] = None
    error_label: Optional[ui.label] = None
    summary_container: Optional[ui.column] = None
    step_containers: list[ui.column] = []
    step_indicators: list[tuple] = []  # (indicator_div, label)

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl min-w-[600px]"):
        # Header
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("New Project").classes("text-xl font-bold")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        # Stepper indicators
        step_labels = ["Basics", "Credentials", "Output", "Review"]
        with ui.row().classes("w-full justify-center gap-4 my-2"):
            for i, label_text in enumerate(step_labels):
                with ui.column().classes("items-center gap-1"):
                    indicator = ui.element("div").classes(
                        "w-8 h-8 rounded-full flex items-center justify-center text-gray-400 bg-gray-700"
                    )
                    with indicator:
                        ui.label(str(i + 1)).classes("text-sm")
                    lbl = ui.label(label_text).classes("text-xs")
                    step_indicators.append((indicator, lbl))

        ui.separator()

        # ---- Step 0: Project Basics (US-086) ----------------------------
        with ui.column().classes("w-full gap-3") as step0:
            ui.label("Project Basics").classes("text-lg font-semibold")

            name_input = ui.input(
                label="Project Name *",
                placeholder="e.g., Production Migration Q1",
                validation={"Min 3 chars": lambda v: len(v.strip()) >= 3},
            ).classes("w-full").bind_value(wizard_data, "name")
            name_input.on("update:model-value", lambda: _update_slug())

            slug_label = ui.label("").classes("text-xs text-gray-500 -mt-2")

            desc_input = ui.textarea(
                label="Description (optional)",
                placeholder="Brief description of this migration project...",
            ).classes("w-full").props("maxlength=500 counter").bind_value(wizard_data, "description")

            ui.label("Workflow Type *").classes("text-sm font-medium mt-2")
            # Single radio group with all options (avoids binding recursion
            # that occurs with multiple ui.radio() bound to the same key)
            wf_options = {value: label_text for value, label_text, _ in WORKFLOW_OPTIONS}
            ui.radio(
                options=wf_options,
                value="migration",
            ).bind_value(wizard_data, "workflow_type").props("dense")
            # Help text below the radio group
            with ui.column().classes("gap-0 ml-8 -mt-1"):
                for _, _, help_text in WORKFLOW_OPTIONS:
                    ui.label(help_text).classes("text-xs text-gray-500")

            error_label = ui.label("").classes("text-red-400 text-sm")
            error_label.set_visibility(False)

        step_containers.append(step0)

        # ---- Step 1: Import Credentials (US-087) ------------------------
        with ui.column().classes("w-full gap-3") as step1:
            step1.set_visibility(False)
            ui.label("Import Credentials").classes("text-lg font-semibold")
            ui.label("Optionally import existing credentials into your new project.").classes("text-sm text-gray-400")

            cred_radio = ui.radio(
                options={k: n for k, n, _ in CREDENTIAL_MODES},
                value="fresh",
            ).classes("w-full").bind_value(wizard_data, "cred_mode")

            # Shared import checkboxes (only one set, visible based on mode)
            # Using on_change callbacks instead of bind_value to avoid dual-
            # binding the same dict key from two checkbox instances.
            env_file_container = ui.column().classes("w-full gap-2 ml-4")
            env_file_container.bind_visibility_from(wizard_data, "cred_mode", value="env_file")
            with env_file_container:
                ui.input(
                    label=".env file path",
                    placeholder="/path/to/.env",
                ).classes("w-full").bind_value(wizard_data, "env_file_path")
                with ui.row().classes("gap-4"):
                    ui.checkbox(
                        "Import source credentials",
                        value=wizard_data["import_source"],
                        on_change=lambda e: wizard_data.update({"import_source": bool(e.value)}),
                    )
                    ui.checkbox(
                        "Import target credentials",
                        value=wizard_data["import_target"],
                        on_change=lambda e: wizard_data.update({"import_target": bool(e.value)}),
                    )

            project_copy_container = ui.column().classes("w-full gap-2 ml-4")
            project_copy_container.bind_visibility_from(wizard_data, "cred_mode", value="project")
            with project_copy_container:
                existing_projects = project_manager.list_projects()
                project_options = {p.slug: f"{p.name} ({p.workflow_type.value})" for p in existing_projects}
                if project_options:
                    ui.select(
                        label="Copy from project",
                        options=project_options,
                    ).classes("w-full").bind_value(wizard_data, "copy_project_slug")
                else:
                    ui.label("No existing projects to copy from").classes("text-sm text-gray-500 italic")
                with ui.row().classes("gap-4"):
                    ui.checkbox(
                        "Copy source credentials",
                        value=wizard_data["import_source"],
                        on_change=lambda e: wizard_data.update({"import_source": bool(e.value)}),
                    )
                    ui.checkbox(
                        "Copy target credentials",
                        value=wizard_data["import_target"],
                        on_change=lambda e: wizard_data.update({"import_target": bool(e.value)}),
                    )

        step_containers.append(step1)

        # ---- Step 2: Output Configuration (US-088) ----------------------
        with ui.column().classes("w-full gap-3") as step2:
            step2.set_visibility(False)
            ui.label("Output Configuration").classes("text-lg font-semibold")
            ui.label(
                "Set one base folder. Project output subfolders are fixed and cannot be changed."
            ).classes("text-sm text-gray-400")

            ui.input(
                label="Project base folder",
                value="outputs",
                placeholder="outputs",
            ).classes("w-full").bind_value(wizard_data, "base_dir")
            ui.label("Fixed subfolders (auto-created):").classes("text-sm font-medium mt-1")
            ui.label("source, target, normalized").classes("text-xs text-gray-500")
            ui.checkbox("Use timestamped subdirectories", value=True).bind_value(wizard_data, "use_timestamps")
            ui.label(
                "When enabled, each fetch creates a timestamped subfolder "
                "(e.g., outputs/source/2024-01-15_143022/)"
            ).classes("text-xs text-gray-500 ml-6")

        step_containers.append(step2)

        # ---- Step 3: Summary & Create (US-089) --------------------------
        with ui.column().classes("w-full gap-3") as step3:
            step3.set_visibility(False)
            ui.label("Review & Create").classes("text-lg font-semibold")
            ui.label("Please review your settings before creating the project.").classes("text-sm text-gray-400")

            with ui.scroll_area().classes("w-full").style("max-height: 400px;"):
                summary_container = ui.column().classes("w-full gap-2 p-2")

        step_containers.append(step3)

        ui.separator()

        # ---- Navigation buttons -----------------------------------------
        with ui.row().classes("w-full justify-between mt-2"):
            back_btn = ui.button("Back", icon="arrow_back", on_click=_go_back).props("flat")
            back_btn.set_visibility(False)

            ui.element("div").classes("flex-grow")  # Spacer

            with ui.row().classes("gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                next_btn = ui.button("Next", icon="arrow_forward", on_click=_go_next).props("color=primary")
                create_btn = ui.button(
                    "Create Project",
                    icon="add_circle",
                    on_click=_create_project,
                ).props("color=primary")
                create_btn.set_visibility(False)

    # Initialize the first step
    _refresh_steps()
    dialog.open()
