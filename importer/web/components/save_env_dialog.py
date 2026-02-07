"""Save .env file dialog component (US-094 through US-096).

Provides a dialog for choosing where to save credentials, with a preview
panel showing masked credential values.

See PRD 21.02-Project-Management.md for full specification.
"""

from pathlib import Path
from typing import Callable, Optional

from nicegui import ui


# Masking helper
def _mask_token(token: str) -> str:
    """Mask a token, showing only the last 4 characters."""
    if not token or len(token) <= 4:
        return "****"
    return "*" * (len(token) - 4) + token[-4:]


def show_save_env_dialog(
    env_vars: dict[str, str],
    default_path: str = ".env",
    context_label: str = "",
    on_save: Optional[Callable[[str], None]] = None,
) -> None:
    """Show the save .env dialog.

    Args:
        env_vars: Dictionary of environment variable name → value to save.
        default_path: Default file path for saving.
        context_label: Context label (e.g., "Project: my-project / Source").
        on_save: Callback invoked with the saved file path on success.
    """
    save_data = {"path": default_path}

    def _do_save() -> None:
        file_path = save_data["path"].strip()
        if not file_path:
            ui.notify("Please enter a file path", type="warning")
            return

        try:
            target = Path(file_path)
            # Create parent directories if needed
            target.parent.mkdir(parents=True, exist_ok=True)

            # Preserve existing keys not being updated (FR-10)
            existing: dict[str, str] = {}
            if target.exists():
                for line in target.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        existing[key.strip()] = value.strip()

            existing.update(env_vars)

            lines = [f"{k}={v}" for k, v in sorted(existing.items())]
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")

            ui.notify(f"Saved to {file_path}", type="positive")
            dialog.close()

            if on_save:
                on_save(file_path)

        except Exception as exc:
            ui.notify(f"Save failed: {exc}", type="negative")

    # Build dialog (Config/Picker style per ag-grid-standards.mdc)
    with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[400px] max-h-[80vh]"):
        # Header
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Save Credentials").classes("text-lg font-bold")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")

        if context_label:
            ui.label(context_label).classes("text-xs text-gray-500")

        ui.separator()

        # File path input
        ui.input(
            label="Save to file",
            value=default_path,
        ).classes("w-full").bind_value(save_data, "path")

        # Overwrite warning
        if Path(default_path).exists():
            with ui.row().classes("items-center gap-1"):
                ui.icon("warning", color="amber").classes("text-sm")
                ui.label("File exists — existing keys will be preserved, matching keys will be updated.").classes(
                    "text-xs text-amber-400"
                )

        ui.separator()

        # Preview panel (US-095)
        ui.label("Preview").classes("text-sm font-medium")
        with ui.scroll_area().classes("w-full").style("max-height: 200px;"):
            with ui.column().classes("gap-1 w-full"):
                for key, value in sorted(env_vars.items()):
                    # Mask tokens/secrets
                    display_value = value
                    key_lower = key.lower()
                    if any(t in key_lower for t in ("token", "secret", "password", "key", "api")):
                        display_value = _mask_token(value)
                    with ui.row().classes("items-center gap-2 w-full"):
                        ui.label(key).classes("text-xs font-mono text-blue-300")
                        ui.label("=").classes("text-xs text-gray-500")
                        ui.label(display_value).classes("text-xs font-mono text-gray-400 truncate")

        ui.separator()

        # Action buttons
        with ui.row().classes("w-full justify-end mt-2 gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", icon="save", on_click=_do_save).props("color=primary")

    dialog.open()
