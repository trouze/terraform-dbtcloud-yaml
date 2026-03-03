"""Removal management utility page for explicit Terraform state removals."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable, Optional

from nicegui import ui

from importer.web.components.terminal_output import TerminalOutput
from importer.web.state import AppState, WorkflowStep
from importer.web.utils.terraform_helpers import (
    get_terraform_env,
    resolve_deployment_paths,
    run_terraform_command,
)
from importer.web.utils.terraform_state_reader import read_terraform_state
from importer.web.utils.yaml_viewer import create_plan_viewer_dialog


def _normalize_str(value: object) -> str:
    return str(value or "").strip()


def _key_variants(key: str) -> set[str]:
    key = _normalize_str(key)
    if not key:
        return set()
    bare = key.removeprefix("target__").removeprefix("state__")
    return {key, bare, f"target__{bare}", f"state__{bare}"}


def _coerce_type_key(type_code: str, key: str) -> str:
    type_code = _normalize_str(type_code)
    key = _normalize_str(key)
    if type_code and key:
        return f"{type_code}:{key}"
    return key


def _build_candidate_rows_from_inputs(
    *,
    reconcile_rows: list[dict],
    confirmed_mappings: list[dict],
    removal_keys: set[str],
    orphan_flagged_keys: set[str],
) -> list[dict]:
    """Build deterministic candidate rows for state-rm management."""
    drift_by_typed_key: dict[str, str] = {}
    for mapping in confirmed_mappings:
        source_key = _normalize_str(mapping.get("source_key"))
        source_type = _normalize_str(mapping.get("source_type") or mapping.get("resource_type"))
        drift = _normalize_str(mapping.get("drift_status"))
        if not source_key or not source_type or not drift:
            continue
        for variant in _key_variants(source_key):
            drift_by_typed_key[_coerce_type_key(source_type, variant)] = drift

    rows: list[dict] = []
    seen_row_ids: set[str] = set()
    normalized_removal_keys: set[str] = set()
    for key in removal_keys:
        normalized_removal_keys.update(_key_variants(key))
    normalized_orphans: set[str] = set(orphan_flagged_keys)

    def _append_row(candidate: dict) -> None:
        row_id = _normalize_str(candidate.get("row_id"))
        if not row_id or row_id in seen_row_ids:
            return
        seen_row_ids.add(row_id)
        rows.append(candidate)

    for resource in reconcile_rows:
        resource_type = _normalize_str(resource.get("element_code"))
        resource_key = _normalize_str(resource.get("resource_index"))
        state_address = _normalize_str(resource.get("address"))
        if not resource_key and not state_address:
            continue

        typed_key = _coerce_type_key(resource_type, resource_key)
        orphan_flagged = bool(
            resource_key in normalized_orphans
            or typed_key in normalized_orphans
            or f"target__{resource_key}" in normalized_orphans
        )
        pending_unadopt = bool(resource_key and resource_key in normalized_removal_keys)
        drift_status = drift_by_typed_key.get(typed_key, "")
        id_mismatch = drift_status == "id_mismatch"

        if orphan_flagged:
            suggested_reason = "orphan_flagged"
        elif id_mismatch:
            suggested_reason = "id_mismatch"
        elif pending_unadopt:
            suggested_reason = "pending_unadopt"
        else:
            suggested_reason = "state_entry"

        row_id = state_address or typed_key
        _append_row(
            {
                "row_id": row_id,
                "resource_key": resource_key or typed_key,
                "resource_type": resource_type or "UNKNOWN",
                "resource_name": _normalize_str(resource.get("name") or resource.get("tf_name") or resource_key),
                "drift_status": drift_status or "in_state",
                "state_address": state_address,
                "suggested_reason": suggested_reason,
                "orphan_flagged": orphan_flagged,
                "id_mismatch": id_mismatch,
                "has_state_address": bool(state_address),
                "_selected": False,
            }
        )

    for mapping in confirmed_mappings:
        state_address = _normalize_str(mapping.get("state_address"))
        if not state_address:
            continue
        source_type = _normalize_str(mapping.get("source_type") or mapping.get("resource_type"))
        source_key = _normalize_str(mapping.get("source_key"))
        bare_key = source_key.removeprefix("target__").removeprefix("state__")
        typed_key = _coerce_type_key(source_type, bare_key)
        drift_status = _normalize_str(mapping.get("drift_status") or drift_by_typed_key.get(typed_key))
        orphan_flagged = bool(typed_key in normalized_orphans or bare_key in normalized_orphans)
        id_mismatch = drift_status == "id_mismatch"
        if orphan_flagged:
            suggested_reason = "orphan_flagged"
        elif id_mismatch:
            suggested_reason = "id_mismatch"
        else:
            suggested_reason = "mapping_state_address"
        _append_row(
            {
                "row_id": state_address,
                "resource_key": bare_key or typed_key,
                "resource_type": source_type or "UNKNOWN",
                "resource_name": _normalize_str(mapping.get("source_name") or mapping.get("target_name") or bare_key),
                "drift_status": drift_status or "in_state",
                "state_address": state_address,
                "suggested_reason": suggested_reason,
                "orphan_flagged": orphan_flagged,
                "id_mismatch": id_mismatch,
                "has_state_address": True,
                "_selected": False,
            }
        )

    rows.sort(key=lambda row: (row.get("resource_type", ""), row.get("resource_key", "")))
    return rows


def _build_removal_candidates(state: AppState) -> list[dict]:
    """Build candidate rows using live app state."""
    target_intent = state.get_target_intent_manager().load()
    orphan_keys = set(target_intent.orphan_flagged_keys) if target_intent else set()
    return _build_candidate_rows_from_inputs(
        reconcile_rows=list(state.deploy.reconcile_state_resources or []),
        confirmed_mappings=list(state.map.confirmed_mappings or []),
        removal_keys=set(state.map.removal_keys or set()),
        orphan_flagged_keys=orphan_keys,
    )


def _filter_removal_rows(
    *,
    rows: list[dict],
    filter_state: dict,
    selected_keys: set[str],
) -> list[dict]:
    """Filter rows by type/search/toggle filters and keep checkbox state in sync."""
    selected_types = set(filter_state.get("selected_types") or set())
    search_term = _normalize_str(filter_state.get("search")).lower()
    only_id_mismatch = bool(filter_state.get("only_id_mismatch"))
    only_orphan_flagged = bool(filter_state.get("only_orphan_flagged"))
    only_with_state_address = bool(filter_state.get("only_with_state_address"))
    selected_only = bool(filter_state.get("selected_only"))

    filtered: list[dict] = []
    for row in rows:
        resource_type = _normalize_str(row.get("resource_type"))
        row_id = _normalize_str(row.get("row_id"))
        is_selected = row_id in selected_keys

        if selected_types and resource_type not in selected_types:
            continue
        if only_id_mismatch and not bool(row.get("id_mismatch")):
            continue
        if only_orphan_flagged and not bool(row.get("orphan_flagged")):
            continue
        if only_with_state_address and not bool(row.get("has_state_address")):
            continue
        if selected_only and not is_selected:
            continue

        if search_term:
            haystack = " ".join(
                [
                    _normalize_str(row.get("resource_key")),
                    _normalize_str(row.get("resource_name")),
                    _normalize_str(row.get("resource_type")),
                    _normalize_str(row.get("state_address")),
                    _normalize_str(row.get("suggested_reason")),
                ]
            ).lower()
            if search_term not in haystack:
                continue

        new_row = dict(row)
        new_row["_selected"] = is_selected
        filtered.append(new_row)
    return filtered


def _build_state_rm_commands_from_rows(rows: list[dict]) -> list[str]:
    """Build deterministic terraform state rm commands from selected rows."""
    commands: list[str] = []
    seen_addresses: set[str] = set()
    for row in rows:
        address = _normalize_str(row.get("state_address"))
        if not address or address in seen_addresses:
            continue
        seen_addresses.add(address)
        commands.append(f"terraform state rm '{address}'")
    return commands


def _build_refresh_target_addresses_from_rows(rows: list[dict]) -> list[str]:
    """Build deterministic target addresses for refresh-only commands."""
    addresses: list[str] = []
    seen_addresses: set[str] = set()
    for row in rows:
        address = _normalize_str(row.get("state_address"))
        if not address or address in seen_addresses:
            continue
        seen_addresses.add(address)
        addresses.append(address)
    return addresses


def _build_refresh_only_command_preview(target_addresses: list[str]) -> dict[str, str]:
    """Build preview strings for refresh-only plan/apply."""
    target_flags = " ".join([f"-target '{address}'" for address in target_addresses])
    plan_flags = "-refresh-only -no-color -input=false"
    apply_flags = "-refresh-only -auto-approve -no-color -input=false"
    if target_flags:
        return {
            "plan": f"terraform plan {plan_flags} {target_flags}",
            "apply": f"terraform apply {apply_flags} {target_flags}",
        }
    return {
        "plan": f"terraform plan {plan_flags}",
        "apply": f"terraform apply {apply_flags}",
    }


def _build_refresh_plan_cmd(target_addresses: list[str]) -> list[str]:
    """Build argv for terraform plan -refresh-only."""
    cmd = ["terraform", "plan", "-refresh-only", "-no-color", "-input=false"]
    for address in target_addresses:
        cmd.extend(["-target", address])
    return cmd


def _build_refresh_apply_cmd(target_addresses: list[str]) -> list[str]:
    """Build argv for terraform apply -refresh-only."""
    cmd = ["terraform", "apply", "-refresh-only", "-auto-approve", "-no-color", "-input=false"]
    for address in target_addresses:
        cmd.extend(["-target", address])
    return cmd


def _build_type_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        resource_type = _normalize_str(row.get("resource_type"))
        if not resource_type:
            continue
        counts[resource_type] = counts.get(resource_type, 0) + 1
    return counts


def _collect_missing_terraform_env(env: dict[str, str]) -> list[str]:
    missing: list[str] = []
    if not _normalize_str(env.get("TF_VAR_dbt_token")):
        missing.append("TF_VAR_dbt_token")
    if not _normalize_str(env.get("TF_VAR_dbt_account_id")):
        missing.append("TF_VAR_dbt_account_id")
    if not _normalize_str(env.get("TF_VAR_dbt_host_url")):
        missing.append("TF_VAR_dbt_host_url")
    return missing


def _extract_first_error_reason(output: str) -> Optional[str]:
    for line in output.splitlines():
        if line.startswith("Error:"):
            reason = line.replace("Error:", "", 1).strip()
            return reason or "terraform command failed"
    return None


async def _refresh_reconcile_state(state: AppState, tf_path: Path, save_state: Optional[Callable[[], None]]) -> None:
    """Reload reconcile resources from `terraform show -json`."""
    result = await read_terraform_state(tf_path)
    if not result.success:
        return
    state.deploy.reconcile_state_resources = [resource.__dict__ for resource in result.resources]
    state.deploy.reconcile_state_loaded = True
    if save_state:
        save_state()


def create_removal_management_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Optional[Callable[[], None]] = None,
) -> None:
    """Create the state removal management utility page."""
    _ = on_step_change
    all_rows = _build_removal_candidates(state)
    total_rows = len(all_rows)
    resource_types = sorted({_normalize_str(row.get("resource_type")) for row in all_rows if row.get("resource_type")})
    initial_type_counts = _build_type_counts(all_rows)
    selected_keys: set[str] = set()
    filter_state: dict = {
        "selected_types": set(),
        "search": "",
        "only_id_mismatch": False,
        "only_orphan_flagged": False,
        "only_with_state_address": True,
        "selected_only": False,
    }
    ui_refs: dict[str, Any] = {}
    refresh_state: dict[str, Any] = {
        "plan_output": "",
        "plan_failure": None,
    }

    def _selected_rows() -> list[dict]:
        return [row for row in all_rows if _normalize_str(row.get("row_id")) in selected_keys]

    def _update_selection_controls(filtered_rows: list[dict]) -> None:
        selection_label = ui_refs.get("selection_label")
        count = len(selected_keys)
        current_total = len(all_rows)
        if selection_label is not None:
            selection_label.set_text(f"Selected: {count}")
        showing_label = ui_refs.get("showing_label")
        if showing_label is not None:
            showing_label.set_text(f"{len(filtered_rows)} shown / {current_total} total")

        preview_btn = ui_refs.get("preview_button")
        execute_btn = ui_refs.get("execute_button")
        refresh_selected_btn = ui_refs.get("refresh_selected_button")
        refresh_preview_selected_btn = ui_refs.get("refresh_preview_selected_button")
        clear_btn = ui_refs.get("clear_button")
        select_filtered_btn = ui_refs.get("select_filtered_button")
        view_plan_btn = ui_refs.get("view_plan_button")
        if preview_btn is not None:
            preview_btn.set_text(f"Preview Removal Commands ({count})")
            preview_btn.set_enabled(count > 0)
        if execute_btn is not None:
            execute_btn.set_text(f"Execute State Removals ({count})")
            execute_btn.set_enabled(count > 0)
        if refresh_selected_btn is not None:
            refresh_selected_btn.set_text(f"Refresh Selected ({count})")
            refresh_selected_btn.set_enabled(count > 0)
        if refresh_preview_selected_btn is not None:
            refresh_preview_selected_btn.set_text(f"Preview Selected Refresh ({count})")
            refresh_preview_selected_btn.set_enabled(count > 0)
        if clear_btn is not None:
            clear_btn.set_enabled(count > 0)
        if select_filtered_btn is not None:
            select_filtered_btn.set_enabled(len(filtered_rows) > 0)
        if view_plan_btn is not None:
            view_plan_btn.set_enabled(bool(refresh_state.get("plan_output")))

    def _refresh_grid() -> list[dict]:
        type_select = ui_refs.get("type_select")
        if type_select is not None:
            counts = _build_type_counts(all_rows)
            valid_selected = {
                t for t in set(filter_state.get("selected_types") or set()) if _normalize_str(t) in counts
            }
            filter_state["selected_types"] = valid_selected
            type_select.options = {t: f"{t} ({counts[t]})" for t in sorted(counts)}
            type_select.value = sorted(valid_selected)
            type_select.update()
        filtered_rows = _filter_removal_rows(
            rows=all_rows,
            filter_state=filter_state,
            selected_keys=selected_keys,
        )
        grid = ui_refs.get("grid")
        if grid is not None:
            grid.options["rowData"] = filtered_rows
            grid.update()
        _update_selection_controls(filtered_rows)
        return filtered_rows

    async def _execute_commands(commands: list[str]) -> None:
        tf_path, _yaml_file, _baseline = resolve_deployment_paths(state)
        if not tf_path.exists() or not tf_path.is_dir():
            ui.notify("State removal blocked: Terraform directory not found", type="negative")
            return
        if shutil.which("terraform") is None:
            ui.notify("State removal blocked: terraform CLI not found in PATH", type="negative")
            return

        env = get_terraform_env(state)
        missing_env = _collect_missing_terraform_env(env)
        if missing_env:
            ui.notify(
                f"State removal blocked: missing terraform credentials ({', '.join(missing_env)})",
                type="negative",
            )
            return

        terminal: TerminalOutput = ui_refs["terminal"]  # type: ignore[assignment]
        terminal.clear()
        terminal.set_title("Output - State Management")
        terminal.info(f"Executing {len(commands)} terraform state rm command(s)")
        terminal.info("")

        success_count = 0
        failure_count = 0
        for command in commands:
            address = command.split("terraform state rm ", 1)[1].strip().strip("'")
            terminal.info(f"> terraform state rm -no-color '{address}'")
            return_code, stdout, stderr = await run_terraform_command(
                ["terraform", "state", "rm", "-no-color", address],
                tf_path=tf_path,
                env=env,
            )
            if stdout.strip():
                for line in stdout.splitlines():
                    terminal.info(f"  {line}")
            if stderr.strip():
                for line in stderr.splitlines():
                    terminal.warning(f"  {line}")
            if return_code == 0:
                success_count += 1
                terminal.success(f"  Removed: {address}")
            else:
                failure_count += 1
                terminal.error(f"  Failed: {address} (exit code {return_code})")
            terminal.info("")

        if success_count > 0:
            await _refresh_reconcile_state(state, tf_path, save_state)

        if failure_count == 0:
            ui.notify(f"Removed {success_count} state entr{'y' if success_count == 1 else 'ies'}", type="positive")
        else:
            ui.notify(
                f"State removal finished with failures: {success_count} succeeded, {failure_count} failed",
                type="warning",
            )

        selected_keys.clear()
        updated_rows = _build_removal_candidates(state)
        all_rows.clear()
        all_rows.extend(updated_rows)
        _refresh_grid()

    def _selected_target_addresses() -> list[str]:
        rows = _selected_rows()
        return _build_refresh_target_addresses_from_rows(rows)

    def _open_refresh_preview_dialog(selected_only: bool) -> None:
        target_addresses = _selected_target_addresses() if selected_only else []
        if selected_only and not target_addresses:
            ui.notify("Select at least one row with a valid state address", type="warning")
            return
        preview = _build_refresh_only_command_preview(target_addresses)
        title = "Preview Refresh Commands (Selected)" if selected_only else "Preview Refresh Commands (All In State)"
        with ui.dialog() as dialog, ui.card().classes("p-4").style("min-width: 680px;"):
            ui.label(title).classes("text-lg font-semibold mb-2")
            with ui.column().classes("w-full gap-2 mb-2"):
                ui.label(preview["plan"]).classes("font-mono text-xs")
                ui.label(preview["apply"]).classes("font-mono text-xs")
            with ui.row().classes("w-full justify-end"):
                ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    def _open_refresh_plan_output() -> None:
        plan_output = str(refresh_state.get("plan_output") or "")
        if not plan_output:
            ui.notify("No refresh plan output available yet", type="warning")
            return
        create_plan_viewer_dialog(
            plan_output,
            "State Refresh Plan Output",
            failure_reason=refresh_state.get("plan_failure"),
        ).open()

    async def _run_refresh_apply(target_addresses: list[str]) -> None:
        tf_path, _yaml_file, _baseline = resolve_deployment_paths(state)
        if not tf_path.exists() or not tf_path.is_dir():
            ui.notify("State refresh blocked: Terraform directory not found", type="negative")
            return
        if shutil.which("terraform") is None:
            ui.notify("State refresh blocked: terraform CLI not found in PATH", type="negative")
            return
        env = get_terraform_env(state)
        missing_env = _collect_missing_terraform_env(env)
        if missing_env:
            ui.notify(
                f"State refresh blocked: missing terraform credentials ({', '.join(missing_env)})",
                type="negative",
            )
            return

        terminal: TerminalOutput = ui_refs["terminal"]  # type: ignore[assignment]
        terminal.info("")
        terminal.info("Running refresh-only apply...")
        preview = _build_refresh_only_command_preview(target_addresses)
        terminal.info(f"> {preview['apply']}")
        return_code, stdout, stderr = await run_terraform_command(
            _build_refresh_apply_cmd(target_addresses),
            tf_path=tf_path,
            env=env,
        )
        if stdout.strip():
            for line in stdout.splitlines():
                terminal.info(f"  {line}")
        if stderr.strip():
            for line in stderr.splitlines():
                terminal.warning(f"  {line}")
        if return_code != 0:
            terminal.error(f"Refresh apply failed (exit code {return_code})")
            ui.notify(
                f"State refresh apply failed: {_extract_first_error_reason(stdout + stderr) or 'see output'}",
                type="negative",
            )
            return

        terminal.success("Refresh apply completed successfully")
        await _refresh_reconcile_state(state, tf_path, save_state)
        selected_keys.clear()
        updated_rows = _build_removal_candidates(state)
        all_rows.clear()
        all_rows.extend(updated_rows)
        _refresh_grid()
        ui.notify("State refresh apply completed", type="positive")

    def _open_refresh_apply_dialog(target_addresses: list[str]) -> None:
        preview = _build_refresh_only_command_preview(target_addresses)
        with ui.dialog() as dialog, ui.card().classes("p-4").style("min-width: 640px;"):
            ui.label("Confirm Refresh-Only Apply").classes("text-lg font-semibold mb-2")
            ui.label(
                "This will run `terraform apply -refresh-only` and update Terraform state for existing managed objects."
            ).classes("text-sm opacity-80 mb-2")
            with ui.column().classes("w-full gap-1 mb-3"):
                ui.label(preview["apply"]).classes("font-mono text-xs")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                async def _confirm_and_run() -> None:
                    dialog.close()
                    await _run_refresh_apply(target_addresses)

                ui.button("Run Refresh Apply", on_click=_confirm_and_run).props("color=primary")
        dialog.open()

    async def _run_refresh_plan(selected_only: bool) -> None:
        target_addresses = _selected_target_addresses() if selected_only else []
        if selected_only and not target_addresses:
            ui.notify("Select at least one row with a valid state address", type="warning")
            return
        tf_path, _yaml_file, _baseline = resolve_deployment_paths(state)
        if not tf_path.exists() or not tf_path.is_dir():
            ui.notify("State refresh blocked: Terraform directory not found", type="negative")
            return
        if shutil.which("terraform") is None:
            ui.notify("State refresh blocked: terraform CLI not found in PATH", type="negative")
            return
        env = get_terraform_env(state)
        missing_env = _collect_missing_terraform_env(env)
        if missing_env:
            ui.notify(
                f"State refresh blocked: missing terraform credentials ({', '.join(missing_env)})",
                type="negative",
            )
            return

        terminal: TerminalOutput = ui_refs["terminal"]  # type: ignore[assignment]
        terminal.clear()
        terminal.set_title("Output - State Management")
        preview = _build_refresh_only_command_preview(target_addresses)
        terminal.info("Running refresh-only plan...")
        terminal.info(f"> {preview['plan']}")
        return_code, stdout, stderr = await run_terraform_command(
            _build_refresh_plan_cmd(target_addresses),
            tf_path=tf_path,
            env=env,
        )
        if stdout.strip():
            for line in stdout.splitlines():
                terminal.info(f"  {line}")
        if stderr.strip():
            for line in stderr.splitlines():
                terminal.warning(f"  {line}")

        full_output = (stdout or "") + (stderr or "")
        refresh_state["plan_output"] = full_output
        refresh_state["plan_failure"] = _extract_first_error_reason(full_output) if return_code != 0 else None
        if return_code != 0:
            terminal.error(f"Refresh plan failed (exit code {return_code})")
            _refresh_grid()
            ui.notify(
                f"State refresh plan failed: {refresh_state['plan_failure'] or 'see output'}",
                type="negative",
            )
            return

        terminal.success("Refresh plan completed")
        _refresh_grid()
        _open_refresh_plan_output()
        _open_refresh_apply_dialog(target_addresses)
        ui.notify("Refresh plan complete. Review and confirm apply.", type="positive")

    def _open_execute_dialog() -> None:
        rows = _selected_rows()
        if not rows:
            ui.notify("No rows selected", type="warning")
            return
        commands = _build_state_rm_commands_from_rows(rows)
        if not commands:
            ui.notify("Selected rows do not have valid state addresses", type="warning")
            return

        with ui.dialog() as dialog, ui.card().classes("p-4").style("min-width: 560px;"):
            ui.label("Confirm Terraform State Removal").classes("text-lg font-semibold mb-2")
            ui.label(
                f"This will run `terraform state rm` for {len(commands)} selected resource(s). "
                "This removes entries from Terraform state only; it does not delete remote resources."
            ).classes("text-sm opacity-80 mb-2")
            with ui.column().classes("w-full gap-1 mb-3").style("max-height: 180px; overflow-y: auto;"):
                for cmd in commands[:20]:
                    ui.label(cmd).classes("font-mono text-xs")
                if len(commands) > 20:
                    ui.label(f"... and {len(commands) - 20} more").classes("text-xs text-slate-500")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                async def _confirm_and_run() -> None:
                    dialog.close()
                    await _execute_commands(commands)

                ui.button("Run State Removals", on_click=_confirm_and_run).props("color=negative")
        dialog.open()

    def _show_preview_dialog() -> None:
        rows = _selected_rows()
        commands = _build_state_rm_commands_from_rows(rows)
        with ui.dialog() as dialog, ui.card().classes("p-4").style("min-width: 640px;"):
            ui.label("Preview State Removal Commands").classes("text-lg font-semibold mb-2")
            if not commands:
                ui.label("No commands available for current selection.").classes("text-sm opacity-70")
            else:
                with ui.column().classes("w-full gap-1").style("max-height: 320px; overflow-y: auto;"):
                    for cmd in commands:
                        ui.label(cmd).classes("font-mono text-xs")
            with ui.row().classes("w-full justify-end mt-2"):
                ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    with ui.column().classes("w-full max-w-7xl mx-auto p-8 gap-4"):
        with ui.row().classes("w-full items-center gap-3"):
            ui.icon("sync_alt", size="lg").classes("text-slate-600")
            ui.label("State Management").classes("text-2xl font-bold")

        ui.label(
            "Manage Terraform state with refresh-only sync and explicit state-removal controls."
        ).classes("text-sm text-slate-500")

        with ui.card().classes("w-full p-4 border border-blue-300 bg-blue-50"):
            ui.label("Refresh-Only Notice").classes("font-semibold text-blue-800")
            ui.label(
                "Refresh-only updates Terraform state from remote objects for resources already in state. "
                "It does not import unmanaged resources and does not create or destroy infrastructure."
            ).classes("text-sm text-blue-900")

        with ui.card().classes("w-full p-4 border border-amber-300 bg-amber-50"):
            ui.label("State Removal Notice").classes("font-semibold text-amber-800")
            ui.label(
                "This action runs `terraform state rm` and only detaches resources from Terraform state. "
                "It does not delete remote dbt Cloud objects."
            ).classes("text-sm text-amber-900")

        with ui.card().classes("w-full p-3 border border-slate-200 rounded-lg"):
            ui.label("Filters").classes("text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2")
            with ui.row().classes("w-full items-end gap-3 flex-wrap"):
                def _on_types_changed(event) -> None:
                    raw_value = event.value
                    if isinstance(raw_value, str):
                        normalized_types = {raw_value} if raw_value else set()
                    elif isinstance(raw_value, (list, tuple, set)):
                        normalized_types = {_normalize_str(v) for v in raw_value if _normalize_str(v)}
                    else:
                        normalized_types = set()
                    filter_state["selected_types"] = normalized_types
                    _refresh_grid()

                def _on_search_changed(event) -> None:
                    filter_state["search"] = _normalize_str(event.value)
                    _refresh_grid()

                def _on_id_mismatch_toggle(event) -> None:
                    filter_state["only_id_mismatch"] = bool(event.value)
                    _refresh_grid()

                def _on_orphan_toggle(event) -> None:
                    filter_state["only_orphan_flagged"] = bool(event.value)
                    _refresh_grid()

                def _on_has_address_toggle(event) -> None:
                    filter_state["only_with_state_address"] = bool(event.value)
                    _refresh_grid()

                def _on_selected_only_toggle(event) -> None:
                    filter_state["selected_only"] = bool(event.value)
                    _refresh_grid()

                def _reset_filters() -> None:
                    filter_state.update(
                        {
                            "selected_types": set(),
                            "search": "",
                            "only_id_mismatch": False,
                            "only_orphan_flagged": False,
                            "only_with_state_address": True,
                            "selected_only": False,
                        }
                    )
                    type_select.value = []
                    _refresh_grid()

                type_select = ui.select(
                    label="Object Types",
                    options={code: f"{code} ({initial_type_counts.get(code, 0)})" for code in resource_types},
                    value=[],
                    on_change=_on_types_changed,
                    multiple=True,
                ).props("use-chips dense outlined").classes("min-w-[280px]")
                ui_refs["type_select"] = type_select
                ui.input(
                    label="Search",
                    placeholder="Filter by key, name, or state address",
                    on_change=_on_search_changed,
                ).props("dense outlined clearable").classes("flex-grow min-w-[240px]")

            with ui.row().classes("w-full items-center gap-3 flex-wrap pt-2"):
                ui.switch(
                    "ID mismatch only",
                    value=False,
                    on_change=_on_id_mismatch_toggle,
                ).props("dense")
                ui.switch(
                    "Orphan flagged only",
                    value=False,
                    on_change=_on_orphan_toggle,
                ).props("dense")
                ui.switch(
                    "Has state address",
                    value=True,
                    on_change=_on_has_address_toggle,
                ).props("dense")
                ui.switch(
                    "Selected only",
                    value=False,
                    on_change=_on_selected_only_toggle,
                ).props("dense")
                ui.button(
                    "Reset Filters",
                    icon="restart_alt",
                    on_click=_reset_filters,
                ).props("outline dense")

            with ui.row().classes("w-full justify-end pt-1"):
                showing_label = ui.label(f"{total_rows} shown / {total_rows} total").classes("text-sm text-slate-500")
                ui_refs["showing_label"] = showing_label

        with ui.card().classes("w-full p-3 border border-slate-200 rounded-lg"):
            with ui.row().classes("w-full items-center justify-between gap-3 flex-wrap"):
                selection_label = ui.label("Selected: 0").classes("text-sm text-slate-600")
                ui_refs["selection_label"] = selection_label
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    select_filtered_button = ui.button("Select Filtered", icon="done_all").props("outline dense")
                    clear_button = ui.button("Clear Selection", icon="clear_all").props("outline dense")
                    ui_refs["select_filtered_button"] = select_filtered_button
                    ui_refs["clear_button"] = clear_button

        with ui.card().classes("w-full p-3 border border-blue-200 rounded-lg"):
            ui.label("State Refresh").classes("text-xs font-semibold uppercase tracking-wide text-blue-700 mb-2")
            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                refresh_preview_all_button = ui.button("Preview All Refresh Commands", icon="visibility").props(
                    "outline dense"
                )
                refresh_preview_selected_button = ui.button("Preview Selected Refresh (0)", icon="visibility").props(
                    "outline dense"
                )
                refresh_all_button = ui.button("Refresh All In State", icon="sync").props("color=primary dense")
                refresh_selected_button = ui.button("Refresh Selected (0)", icon="sync_alt").props(
                    "outline color=primary dense"
                )
                view_plan_button = ui.button("View Plan Output", icon="description").props("outline dense")
                ui_refs["refresh_preview_selected_button"] = refresh_preview_selected_button
                ui_refs["refresh_selected_button"] = refresh_selected_button
                ui_refs["view_plan_button"] = view_plan_button

        with ui.card().classes("w-full p-3 border border-amber-200 rounded-lg"):
            ui.label("State Removal").classes("text-xs font-semibold uppercase tracking-wide text-amber-700 mb-2")
            with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                preview_button = ui.button("Preview Removal Commands (0)", icon="visibility").props("outline dense")
                execute_button = ui.button("Execute State Removals (0)", icon="play_arrow").props("color=negative dense")
                ui_refs["preview_button"] = preview_button
                ui_refs["execute_button"] = execute_button

        column_defs = [
            {
                "field": "_selected",
                "colId": "_selected",
                "headerName": "",
                "width": 60,
                "editable": True,
                "cellRenderer": "agCheckboxCellRenderer",
            },
            {"field": "resource_type", "colId": "resource_type", "headerName": "Type", "width": 90},
            {"field": "resource_key", "colId": "resource_key", "headerName": "Resource Key", "width": 220},
            {"field": "resource_name", "colId": "resource_name", "headerName": "Name", "flex": 1},
            {"field": "drift_status", "colId": "drift_status", "headerName": "Drift", "width": 120},
            {"field": "suggested_reason", "colId": "suggested_reason", "headerName": "Suggested Reason", "width": 170},
            {"field": "state_address", "colId": "state_address", "headerName": "State Address", "flex": 2},
        ]
        initial_rows = _filter_removal_rows(rows=all_rows, filter_state=filter_state, selected_keys=selected_keys)
        grid = ui.aggrid(
            {
                "columnDefs": column_defs,
                "rowData": initial_rows,
                "defaultColDef": {"sortable": True, "resizable": True},
                "pagination": True,
                "paginationPageSize": 200,
                "paginationPageSizeSelector": [50, 100, 200],
            },
            theme="quartz",
        ).classes("w-full ag-theme-quartz").style("height: 460px;")
        ui_refs["grid"] = grid

        def _on_cell_value_changed(e) -> None:
            if not e.args or e.args.get("colId") != "_selected":
                return
            row = e.args.get("data", {})
            row_id = _normalize_str(row.get("row_id"))
            selected = bool(e.args.get("newValue", False))
            if not row_id:
                return
            if selected:
                selected_keys.add(row_id)
            else:
                selected_keys.discard(row_id)
            for existing in all_rows:
                if _normalize_str(existing.get("row_id")) == row_id:
                    existing["_selected"] = selected
                    break
            _refresh_grid()

        grid.on("cellValueChanged", _on_cell_value_changed)

        def _select_filtered() -> None:
            for row in _filter_removal_rows(rows=all_rows, filter_state=filter_state, selected_keys=selected_keys):
                row_id = _normalize_str(row.get("row_id"))
                if not row_id:
                    continue
                selected_keys.add(row_id)
                for existing in all_rows:
                    if _normalize_str(existing.get("row_id")) == row_id:
                        existing["_selected"] = True
                        break
            _refresh_grid()

        def _clear_selection() -> None:
            selected_keys.clear()
            for row in all_rows:
                row["_selected"] = False
            _refresh_grid()

        select_filtered_button.on("click", _select_filtered)
        clear_button.on("click", _clear_selection)
        preview_button.on("click", _show_preview_dialog)
        execute_button.on("click", _open_execute_dialog)
        refresh_preview_all_button.on("click", lambda: _open_refresh_preview_dialog(False))
        refresh_preview_selected_button.on("click", lambda: _open_refresh_preview_dialog(True))
        async def _run_refresh_all_click() -> None:
            await _run_refresh_plan(False)

        async def _run_refresh_selected_click() -> None:
            await _run_refresh_plan(True)

        refresh_all_button.on("click", _run_refresh_all_click)
        refresh_selected_button.on("click", _run_refresh_selected_click)
        view_plan_button.on("click", _open_refresh_plan_output)

        terminal = TerminalOutput(max_lines=1200, auto_scroll=True, show_timestamps=True)
        terminal.create(height="300px", title="Output - State Management")
        ui_refs["terminal"] = terminal

        _refresh_grid()

