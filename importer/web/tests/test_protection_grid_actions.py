"""Unit tests for Protection Management grid row/actions helpers.

These tests cover the shared helper layer in utilities.py that powers:
- unified row model (intents + TF state)
- filter behavior (including selected-only and hide-unprotected defaults)
- detail dialog adapter payload mapping
"""

from pathlib import Path

from importer.web.pages.utilities import (
    _build_dialog_payload_from_protection_row,
    _build_protection_grid_rows,
    _filter_protection_rows,
)
from importer.web.utils.protection_intent import ProtectionIntentManager


def _make_manager(tmp_path: Path) -> ProtectionIntentManager:
    manager = ProtectionIntentManager(tmp_path / "protection-intent.json")
    return manager


def test_build_rows_includes_explicit_and_state_only(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    manager.set_intent(
        key="PRJ:analytics",
        protected=True,
        source="user_click",
        reason="protect project",
        resource_type="PRJ",
    )

    rows = _build_protection_grid_rows(
        protection_intent=manager,
        state_protection_by_key={"PRJ:analytics": True, "GRP:member": True},
        yaml_protected_resources=set(),
    )

    keys = {row["resource_key"] for row in rows}
    assert "PRJ:analytics" in keys
    assert "GRP:member" in keys

    explicit = next(row for row in rows if row["resource_key"] == "PRJ:analytics")
    assert explicit["intent_origin"] == "explicit"
    assert explicit["status"] == "Pending Generate"

    state_only = next(row for row in rows if row["resource_key"] == "GRP:member")
    assert state_only["status"] == "State Only"
    assert state_only["state"] == "Protected"


def test_dense_baseline_intent_origin_detected(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    manager.set_intent(
        key="GRP:member",
        protected=True,
        source="dense_baseline",
        reason="auto-fill from TF state",
        resource_type="GRP",
    )

    rows = _build_protection_grid_rows(
        protection_intent=manager,
        state_protection_by_key={"GRP:member": True},
        yaml_protected_resources=set(),
    )
    row = next(row for row in rows if row["resource_key"] == "GRP:member")
    assert row["intent_origin"] == "baseline"


def test_filter_hides_unprotected_by_default(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    manager.set_intent(
        key="PRJ:analytics",
        protected=True,
        source="user_click",
        reason="protect",
        resource_type="PRJ",
    )
    manager.set_intent(
        key="REP:repo_a",
        protected=False,
        source="user_click",
        reason="unprotect",
        resource_type="REP",
    )

    rows = _build_protection_grid_rows(
        protection_intent=manager,
        state_protection_by_key={},
        yaml_protected_resources=set(),
    )
    filtered = _filter_protection_rows(
        rows=rows,
        filter_state={
            "status": "all",
            "type": "all",
            "search": "",
            "selected_only": False,
            "hide_unprotected": True,
        },
        selected_keys=set(),
    )
    assert {row["resource_key"] for row in filtered} == {"PRJ:analytics"}


def test_filter_selected_only(tmp_path: Path) -> None:
    manager = _make_manager(tmp_path)
    manager.set_intent(
        key="PRJ:analytics",
        protected=True,
        source="user_click",
        reason="protect",
        resource_type="PRJ",
    )
    manager.set_intent(
        key="REP:repo_a",
        protected=True,
        source="user_click",
        reason="protect",
        resource_type="REP",
    )
    rows = _build_protection_grid_rows(
        protection_intent=manager,
        state_protection_by_key={},
        yaml_protected_resources=set(),
    )

    filtered = _filter_protection_rows(
        rows=rows,
        filter_state={
            "status": "all",
            "type": "all",
            "search": "",
            "selected_only": True,
            "hide_unprotected": False,
        },
        selected_keys={"REP:repo_a"},
    )
    assert len(filtered) == 1
    assert filtered[0]["resource_key"] == "REP:repo_a"


def test_dialog_payload_marks_mismatch() -> None:
    row = {
        "resource_key": "GRP:member",
        "type": "GRP",
        "intent_protected": False,
        "state_protected": True,
        "yaml_protected": True,
    }
    source_data, grid_row, state_resource = _build_dialog_payload_from_protection_row(
        row=row,
        state_resource_by_key={"GRP:member": {"resource_index": "member", "dbt_id": 123}},
    )
    assert source_data["element_type_code"] == "GRP"
    assert source_data["name"] == "member"
    assert grid_row["drift_status"] == "protection_mismatch"
    assert state_resource is not None


def test_dialog_payload_handles_missing_state() -> None:
    row = {
        "resource_key": "PRJ:analytics",
        "type": "PRJ",
        "intent_protected": True,
        "state_protected": None,
        "yaml_protected": True,
    }
    _source_data, grid_row, state_resource = _build_dialog_payload_from_protection_row(
        row=row,
        state_resource_by_key={},
    )
    assert grid_row["drift_status"] == "no_state"
    assert state_resource is None
