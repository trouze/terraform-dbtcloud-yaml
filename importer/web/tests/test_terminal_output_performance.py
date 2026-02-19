"""Performance-focused unit tests for terminal output buffering."""

from typing import Any, cast

from importer.web.components.terminal_output import LogLevel, TerminalOutput
from importer.web.utils.terraform_helpers import (
    OutputBudget,
    budget_output_lines,
    emit_process_output,
)


def test_terminal_output_message_buffer_is_bounded() -> None:
    terminal = TerminalOutput(max_lines=50, auto_scroll=False)
    for i in range(250):
        terminal.log(f"line {i}", LogLevel.INFO)
    assert len(terminal.messages) == 50
    assert terminal.messages[0].text == "line 200"
    assert terminal.messages[-1].text == "line 249"


def test_budget_output_lines_omits_middle_segment() -> None:
    lines = [f"line-{i}" for i in range(1000)]
    bounded, omitted = budget_output_lines(
        lines,
        OutputBudget(max_lines=100, head_lines=40, tail_lines=30),
    )
    assert omitted == 930
    assert bounded[0] == "line-0"
    assert bounded[39] == "line-39"
    assert bounded[-1] == "line-999"


def test_emit_process_output_applies_budget_and_omitted_notice() -> None:
    stdout_seen: list[str] = []
    stderr_seen: list[str] = []
    omitted_seen: list[int] = []
    stdout = "\n".join(f"out-{i}" for i in range(10))
    stderr = "\n".join(f"err-{i}" for i in range(6))

    stdout_omitted, stderr_omitted = emit_process_output(
        stdout,
        stderr,
        on_stdout_line=stdout_seen.append,
        on_stderr_line=stderr_seen.append,
        stdout_budget=OutputBudget(max_lines=6, head_lines=3, tail_lines=2),
        stderr_budget=OutputBudget(max_lines=3, head_lines=2, tail_lines=1),
        on_omitted=omitted_seen.append,
    )

    assert stdout_omitted == 5
    assert stderr_omitted == 3
    assert omitted_seen == [8]
    assert stdout_seen == ["out-0", "out-1", "out-2", "out-8", "out-9"]
    assert stderr_seen == ["err-0", "err-1", "err-5"]


def test_terminal_output_flushes_messages_in_batches() -> None:
    rendered: list[str] = []
    terminal = TerminalOutput(max_lines=200, auto_scroll=False, max_flush_batch=3)
    terminal._container = cast(Any, object())  # Simulate mounted UI.
    terminal._add_message_to_ui = lambda msg: rendered.append(msg.text)  # type: ignore[method-assign]

    for i in range(8):
        terminal.log(f"line-{i}", LogLevel.INFO)

    assert len(rendered) == 0
    terminal._flush_pending_messages()
    assert rendered == ["line-0", "line-1", "line-2"]
    terminal._flush_pending_messages()
    assert rendered == ["line-0", "line-1", "line-2", "line-3", "line-4", "line-5"]
    terminal._flush_pending_messages()
    assert rendered[-2:] == ["line-6", "line-7"]


def test_terminal_output_detach_is_marked_once() -> None:
    terminal = TerminalOutput(max_lines=20, auto_scroll=False)
    terminal._container = cast(Any, object())  # Simulate mounted UI.

    def _raise_detached(_msg: Any) -> None:
        raise RuntimeError("Client this element belongs to has been deleted")

    terminal._add_message_to_ui = _raise_detached  # type: ignore[method-assign]
    terminal.log("first", LogLevel.INFO)
    terminal._flush_pending_messages()

    assert terminal._ui_detached is True
    assert terminal._detach_notice_added is True
    assert any("logging continues in memory" in msg.text.lower() for msg in terminal.messages)

    notices_before = sum(
        1 for msg in terminal.messages if "logging continues in memory" in msg.text.lower()
    )
    terminal.log("second", LogLevel.INFO)
    terminal._flush_pending_messages()
    notices_after = sum(
        1 for msg in terminal.messages if "logging continues in memory" in msg.text.lower()
    )
    assert notices_after == notices_before
