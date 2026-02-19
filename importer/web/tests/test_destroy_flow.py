"""Focused unit tests for destroy planning/apply flow."""

import asyncio
import subprocess
from types import SimpleNamespace
from typing import Any, Literal, Optional, cast

from importer.web.pages import destroy
from importer.web.utils import yaml_viewer


class _FakeNode:
    def __init__(self) -> None:
        self.disabled = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        return False

    def classes(self, *_args, **_kwargs):
        return self

    def props(self, *_args, **_kwargs):
        return self

    def style(self, *_args, **_kwargs):
        return self

    def on(self, *_args, **_kwargs):
        return self

    def tooltip(self, *_args, **_kwargs):
        return self

    def set_text(self, *_args, **_kwargs) -> None:
        return None

    def update(self) -> None:
        return None

    def disable(self) -> None:
        self.disabled = True

    def enable(self) -> None:
        self.disabled = False

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None


class _FakeUI:
    def __init__(self) -> None:
        self.notifications: list[tuple[str, str | None]] = []

    def notify(self, message: str, *, type: Optional[str] = None, timeout: Optional[int] = None) -> None:
        _ = timeout
        self.notifications.append((message, type))

    def dialog(self):
        return _FakeNode()

    def card(self):
        return _FakeNode()

    def row(self):
        return _FakeNode()

    def column(self):
        return _FakeNode()

    def icon(self, *_args, **_kwargs):
        return _FakeNode()

    def label(self, *_args, **_kwargs):
        return _FakeNode()

    def button(self, *_args, **_kwargs):
        return _FakeNode()

    def input(self, *_args, **_kwargs):
        return _FakeNode()


class _FakeTerminal:
    def __init__(self) -> None:
        self.success_lines: list[str] = []

    def clear(self) -> None:
        return None

    def set_title(self, *_args, **_kwargs) -> None:
        return None

    def warning(self, *_args, **_kwargs) -> None:
        return None

    def info(self, *_args, **_kwargs) -> None:
        return None

    def info_auto(self, *_args, **_kwargs) -> None:
        return None

    def error(self, *_args, **_kwargs) -> None:
        return None

    def success(self, line: str) -> None:
        self.success_lines.append(line)


def _fake_state() -> SimpleNamespace:
    deploy = SimpleNamespace(terraform_dir="deployments/migration", destroy_complete=False)
    target_credentials = SimpleNamespace(api_token="", account_id="", host_url="")
    return SimpleNamespace(deploy=deploy, target_credentials=target_credentials)


def test_extract_destroy_count_from_apply_output_prefers_summary_count() -> None:
    output = "\n".join(
        [
            "# module.foo.bar will be destroyed",
            "module.foo.bar: Destruction complete after 1s",
            "Destroy complete! Resources: 1 destroyed.",
        ]
    )
    assert destroy._extract_destroy_count_from_apply_output(output) == 1


def test_confirm_destroy_selected_runs_init_validate_plan_in_order(monkeypatch) -> None:
    fake_ui = _FakeUI()
    terminal = _FakeTerminal()
    commands: list[list[str]] = []
    state = _fake_state()
    destroy_state = {"selected": {"module.dbt_cloud.module.projects_v2[0].dbtcloud_job.jobs[\"x\"]"}}

    monkeypatch.setattr(destroy, "ui", fake_ui)
    monkeypatch.setattr(destroy, "_get_terraform_env", lambda _state: {})

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        if cmd[:2] == ["terraform", "init"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="Terraform has been successfully initialized!\n", stderr="")
        if cmd[:2] == ["terraform", "validate"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="Success! The configuration is valid.\n", stderr="")
        if cmd[:2] == ["terraform", "plan"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="Plan: 0 to add, 0 to change, 1 to destroy.\n", stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(destroy.asyncio, "to_thread", fake_to_thread)

    asyncio.run(
        destroy._confirm_destroy_selected(
            state=cast(Any, state),
            terminal=cast(Any, terminal),
            save_state=lambda: None,
            destroy_state=destroy_state,
        )
    )

    assert commands[0] == ["terraform", "init", "-no-color"]
    assert commands[1] == ["terraform", "validate", "-no-color"]
    assert commands[2][0:4] == ["terraform", "plan", "-destroy", "-out=destroy_selected.tfplan"]


def test_destroy_confirmation_validator_accepts_only_destroy_keyword() -> None:
    assert destroy._is_destroy_confirmation_text_valid("DESTROY") is True
    assert destroy._is_destroy_confirmation_text_valid(" destroy ") is True
    assert destroy._is_destroy_confirmation_text_valid("DELETE") is False
    assert destroy._is_destroy_confirmation_text_valid("") is False


def test_confirm_destroy_selected_with_empty_selection_returns_early(monkeypatch) -> None:
    fake_ui = _FakeUI()
    state = _fake_state()
    terminal = _FakeTerminal()

    monkeypatch.setattr(destroy, "ui", fake_ui)

    asyncio.run(
        destroy._confirm_destroy_selected(
            state=cast(Any, state),
            terminal=cast(Any, terminal),
            save_state=lambda: None,
            destroy_state={"selected": set()},
        )
    )

    assert ("Select resources first", "warning") in fake_ui.notifications


def test_confirm_destroy_selected_large_plan_output_is_bounded(monkeypatch) -> None:
    fake_ui = _FakeUI()
    state = _fake_state()
    destroy_state = {"selected": {'module.dbt_cloud.module.projects_v2[0].dbtcloud_job.jobs["x"]'}}

    class _RecordingTerminal:
        def __init__(self) -> None:
            self.info_auto_lines: list[str] = []
            self.warning_lines: list[str] = []
            self.error_lines: list[str] = []
            self.success_lines: list[str] = []

        def clear(self) -> None:
            return None

        def set_title(self, *_args, **_kwargs) -> None:
            return None

        def info(self, *_args, **_kwargs) -> None:
            return None

        def info_auto(self, line: str) -> None:
            self.info_auto_lines.append(line)

        def warning(self, line: str) -> None:
            self.warning_lines.append(line)

        def error(self, line: str) -> None:
            self.error_lines.append(line)

        def success(self, line: str) -> None:
            self.success_lines.append(line)

    terminal = _RecordingTerminal()
    commands: list[list[str]] = []

    monkeypatch.setattr(destroy, "ui", fake_ui)
    monkeypatch.setattr(destroy, "_get_terraform_env", lambda _state: {})

    huge_plan_stdout = "\n".join(f"line-{i}" for i in range(5000))

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        if cmd[:2] == ["terraform", "init"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="init ok\n", stderr="")
        if cmd[:2] == ["terraform", "validate"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="validate ok\n", stderr="")
        if cmd[:2] == ["terraform", "plan"]:
            return subprocess.CompletedProcess(cmd, 1, stdout=huge_plan_stdout, stderr="plan failed\n")
        raise AssertionError(f"Unexpected command: {cmd}")

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(destroy.asyncio, "to_thread", fake_to_thread)

    asyncio.run(
        destroy._confirm_destroy_selected(
            state=cast(Any, state),
            terminal=cast(Any, terminal),
            save_state=lambda: None,
            destroy_state=destroy_state,
        )
    )

    assert commands[2][:3] == ["terraform", "plan", "-destroy"]
    assert len(terminal.info_auto_lines) < 2000
    assert any(
        "Large destroy plan output detected; omitted" in line for line in terminal.warning_lines
    )
    assert any("Plan failed with exit code 1" in line for line in terminal.error_lines)


def test_run_destroy_selected_large_apply_output_is_bounded_and_keeps_full_viewer_output(
    monkeypatch,
) -> None:
    fake_ui = _FakeUI()
    state = _fake_state()
    destroy_state = {"selected": {'module.dbt_cloud.module.projects_v2[0].dbtcloud_job.jobs["x"]'}}

    class _RecordingTerminal:
        def __init__(self) -> None:
            self.info_auto_lines: list[str] = []
            self.warning_lines: list[str] = []
            self.error_lines: list[str] = []
            self.success_lines: list[str] = []
            self.info_lines: list[str] = []

        def clear(self) -> None:
            return None

        def set_title(self, *_args, **_kwargs) -> None:
            return None

        def info(self, line: str) -> None:
            self.info_lines.append(line)

        def info_auto(self, line: str) -> None:
            self.info_auto_lines.append(line)

        def warning(self, line: str) -> None:
            self.warning_lines.append(line)

        def error(self, line: str) -> None:
            self.error_lines.append(line)

        def success(self, line: str) -> None:
            self.success_lines.append(line)

    terminal = _RecordingTerminal()
    commands: list[list[str]] = []
    opened_dialogs: list[tuple[str, str]] = []
    refreshed: list[bool] = []
    saved: list[bool] = []

    monkeypatch.setattr(destroy, "ui", fake_ui)
    monkeypatch.setattr(destroy, "_get_terraform_env", lambda _state: {})
    monkeypatch.setattr(destroy, "_refresh_resources", lambda *_args, **_kwargs: refreshed.append(True))

    def fake_create_plan_viewer_dialog(output: str, title: str):
        opened_dialogs.append((output, title))
        return _FakeNode()

    monkeypatch.setattr(yaml_viewer, "create_plan_viewer_dialog", fake_create_plan_viewer_dialog)

    huge_stdout = "\n".join(f"apply-line-{i}" for i in range(5000))
    huge_stdout += "\nDestroy complete! Resources: 48 destroyed.\n"
    huge_stderr = "\n".join(f"warn-line-{i}" for i in range(600))

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=huge_stdout, stderr=huge_stderr)

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(destroy.asyncio, "to_thread", fake_to_thread)

    asyncio.run(
        destroy._run_terraform_destroy_selected(
            state=cast(Any, state),
            terminal=cast(Any, terminal),
            save_state=lambda: saved.append(True),
            destroy_state=destroy_state,
        )
    )

    assert commands[0][:3] == ["terraform", "destroy", "-no-color"]
    assert state.deploy.destroy_complete is True
    assert saved, "Expected save_state to be called on success"
    assert refreshed, "Expected resource refresh after successful destroy"
    assert any("Large destroy apply output detected; omitted" in line for line in terminal.warning_lines)
    assert len(terminal.info_auto_lines) < 2000
    assert any("Successfully destroyed 48 resource(s)" in line for line in terminal.success_lines)

    assert opened_dialogs, "Expected plan viewer dialog to open with full output"
    viewer_output, viewer_title = opened_dialogs[0]
    assert viewer_title == "Destroy Apply Output"
    assert "apply-line-4999" in viewer_output
    assert "warn-line-599" in viewer_output


def test_run_destroy_all_large_output_is_bounded_and_preserves_protected_skip(monkeypatch) -> None:
    fake_ui = _FakeUI()
    state = _fake_state()
    destroy_state = {"selected": set()}

    class _RecordingTerminal:
        def __init__(self) -> None:
            self.info_auto_lines: list[str] = []
            self.warning_lines: list[str] = []
            self.error_lines: list[str] = []
            self.success_lines: list[str] = []
            self.info_lines: list[str] = []

        def clear(self) -> None:
            return None

        def set_title(self, *_args, **_kwargs) -> None:
            return None

        def info(self, line: str) -> None:
            self.info_lines.append(line)

        def info_auto(self, line: str) -> None:
            self.info_auto_lines.append(line)

        def warning(self, line: str) -> None:
            self.warning_lines.append(line)

        def error(self, line: str) -> None:
            self.error_lines.append(line)

        def success(self, line: str) -> None:
            self.success_lines.append(line)

    terminal = _RecordingTerminal()
    commands: list[list[str]] = []
    refreshed: list[bool] = []
    saved: list[bool] = []

    monkeypatch.setattr(destroy, "ui", fake_ui)
    monkeypatch.setattr(destroy, "_get_terraform_env", lambda _state: {})
    monkeypatch.setattr(destroy, "_refresh_resources", lambda *_args, **_kwargs: refreshed.append(True))

    protected = [f'module.x.dbtcloud_group.protected_groups["p{i}"]' for i in range(5)]
    unprotected = [f'module.x.dbtcloud_job.jobs["j{i}"]' for i in range(55)]
    state_list_stdout = "\n".join(unprotected + protected)
    huge_destroy_stdout = "\n".join(f"destroy-out-{i}" for i in range(5000))
    huge_destroy_stdout += "\nDestroy complete! Resources: 55 destroyed.\n"
    huge_destroy_stderr = "\n".join(f"destroy-warn-{i}" for i in range(600))

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        if cmd[:3] == ["terraform", "state", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=state_list_stdout, stderr="")
        if cmd[:2] == ["terraform", "destroy"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=huge_destroy_stdout, stderr=huge_destroy_stderr)
        raise AssertionError(f"Unexpected command: {cmd}")

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(destroy.asyncio, "to_thread", fake_to_thread)

    asyncio.run(
        destroy._run_terraform_destroy_all(
            state=cast(Any, state),
            terminal=cast(Any, terminal),
            save_state=lambda: saved.append(True),
            destroy_state=destroy_state,
        )
    )

    assert commands[0] == ["terraform", "state", "list"]
    assert commands[1][:3] == ["terraform", "destroy", "-no-color"]
    # Ensure protected addresses are not targeted.
    destroy_cmd = commands[1]
    for p in protected:
        assert p not in destroy_cmd
    for u in unprotected[:3]:
        assert u in destroy_cmd

    assert state.deploy.destroy_complete is True
    assert saved, "Expected save_state to be called on successful destroy all"
    assert refreshed, "Expected resource refresh after successful destroy all"
    assert any(
        "Large destroy all apply output detected; omitted" in line for line in terminal.warning_lines
    )
    assert len(terminal.info_auto_lines) < 2000
    assert any("Successfully destroyed 55 resource(s)" in line for line in terminal.success_lines)
    assert any("protected resource(s) preserved" in line for line in terminal.info_lines)


def test_run_destroy_all_failure_with_large_output_surfaces_error_and_bounds_stream(
    monkeypatch,
) -> None:
    fake_ui = _FakeUI()
    state = _fake_state()
    destroy_state = {"selected": set()}

    class _RecordingTerminal:
        def __init__(self) -> None:
            self.info_auto_lines: list[str] = []
            self.warning_lines: list[str] = []
            self.error_lines: list[str] = []
            self.success_lines: list[str] = []
            self.info_lines: list[str] = []

        def clear(self) -> None:
            return None

        def set_title(self, *_args, **_kwargs) -> None:
            return None

        def info(self, line: str) -> None:
            self.info_lines.append(line)

        def info_auto(self, line: str) -> None:
            self.info_auto_lines.append(line)

        def warning(self, line: str) -> None:
            self.warning_lines.append(line)

        def error(self, line: str) -> None:
            self.error_lines.append(line)

        def success(self, line: str) -> None:
            self.success_lines.append(line)

    terminal = _RecordingTerminal()
    commands: list[list[str]] = []
    refreshed: list[bool] = []
    saved: list[bool] = []

    monkeypatch.setattr(destroy, "ui", fake_ui)
    monkeypatch.setattr(destroy, "_get_terraform_env", lambda _state: {})
    monkeypatch.setattr(destroy, "_refresh_resources", lambda *_args, **_kwargs: refreshed.append(True))

    state_list_stdout = "\n".join(f'module.x.dbtcloud_job.jobs["j{i}"]' for i in range(40))
    huge_destroy_stdout = "\n".join(f"destroy-out-{i}" for i in range(5000))
    huge_destroy_stderr = "\n".join(
        [f"destroy-warn-{i}" for i in range(600)] + ["Error: upstream API timeout"]
    )

    def fake_run(cmd, **_kwargs):
        commands.append(cmd)
        if cmd[:3] == ["terraform", "state", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=state_list_stdout, stderr="")
        if cmd[:2] == ["terraform", "destroy"]:
            return subprocess.CompletedProcess(cmd, 1, stdout=huge_destroy_stdout, stderr=huge_destroy_stderr)
        raise AssertionError(f"Unexpected command: {cmd}")

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(destroy.asyncio, "to_thread", fake_to_thread)

    asyncio.run(
        destroy._run_terraform_destroy_all(
            state=cast(Any, state),
            terminal=cast(Any, terminal),
            save_state=lambda: saved.append(True),
            destroy_state=destroy_state,
        )
    )

    assert commands[0] == ["terraform", "state", "list"]
    assert commands[1][:3] == ["terraform", "destroy", "-no-color"]
    assert state.deploy.destroy_complete is False
    assert not saved, "save_state should not be called on failed destroy all"
    assert not refreshed, "resource refresh should not run on failed destroy all"
    assert any(
        "Large destroy all apply output detected; omitted" in line for line in terminal.warning_lines
    )
    assert len(terminal.info_auto_lines) < 2000
    assert any("Destroy failed with exit code 1" in line for line in terminal.error_lines)
    assert ("Destroy all failed", "negative") in fake_ui.notifications
