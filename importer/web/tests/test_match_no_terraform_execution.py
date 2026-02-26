"""Regression tests for Match intent-only execution contract."""

from pathlib import Path


def _match_page_source() -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "importer" / "web" / "pages" / "match.py").read_text(
        encoding="utf-8"
    )


def test_match_shows_continue_to_adopt_cta() -> None:
    """Match keeps navigation CTA to execute changes in Adopt step."""
    source = _match_page_source()
    assert "Continue to Adopt & Apply" in source


def test_match_terraform_commands_panel_guarded_off() -> None:
    """Terraform command UI remains disabled on Match."""
    source = _match_page_source()
    assert 'if False:\n                    with ui.expansion("Terraform Commands"' in source


def test_match_recomputes_grid_after_key_row_actions() -> None:
    """Row action/protection edits trigger recompute refresh, not manual page reload."""
    source = _match_page_source()
    assert '_reload_with_debug(\n            "row_action_recompute"' in source
    assert '_reload_with_debug(\n                                "adopt_and_protect_guard_no"' in source
    assert '_reload_with_debug(\n                "adopt_cascade_skip"' in source
