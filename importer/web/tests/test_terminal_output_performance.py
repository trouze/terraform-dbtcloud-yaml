"""Performance-focused unit tests for terminal output buffering."""

from importer.web.components.terminal_output import LogLevel, TerminalOutput
from importer.web.pages.adopt import _truncate_terminal_lines


def test_terminal_output_message_buffer_is_bounded() -> None:
    terminal = TerminalOutput(max_lines=50, auto_scroll=False)
    for i in range(250):
        terminal.log(f"line {i}", LogLevel.INFO)
    assert len(terminal.messages) == 50
    assert terminal.messages[0].text == "line 200"
    assert terminal.messages[-1].text == "line 249"


def test_truncate_terminal_lines_omits_middle_segment() -> None:
    lines = [f"line-{i}" for i in range(1000)]
    bounded, omitted = _truncate_terminal_lines(
        lines,
        max_lines=100,
        head_lines=40,
        tail_lines=30,
    )
    assert omitted == 930
    assert bounded[0] == "line-0"
    assert bounded[39] == "line-39"
    assert "... omitted 930 line(s) ..." in bounded
    assert bounded[-1] == "line-999"
