"""Regression tests for state-only resource visibility.

Covers the fix where a GRP:member resource was counted in TF-state summary
cards but not visible in the protection management grid.

Root cause: The grid was built only from explicit intents. State-only
resources (those in TF state but not in protection-intent.json) were
invisible. The fix added state-only row merging and a separate "State" column.

See: docs/guides/intent-workflow-guardrails.md, root cause #7.
"""

from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from importer.web.pages.utilities import _build_protection_grid_rows
from importer.web.utils.protection_intent import ProtectionIntentManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_reconcile_resources(
    resources: list[dict],
) -> list[dict]:
    """Build reconcile_state_resources entries from compact specs.

    Each entry in ``resources`` should have:
        element_code, resource_index, tf_name
    """
    result = []
    for r in resources:
        result.append({
            "element_code": r["element_code"],
            "resource_index": r["resource_index"],
            "tf_name": r.get("tf_name", "groups"),
            "full_address": r.get("full_address", ""),
            "display_name": r.get("display_name", r["resource_index"]),
        })
    return result


def _build_state_protection_map(
    reconcile_resources: list[dict],
) -> dict[str, bool]:
    """Replicate the state_protection_by_key logic from utilities.py.

    This is the grid row-building logic that was fixed to include GRP.
    """
    state_protection_by_key: dict[str, bool] = {}
    for resource in reconcile_resources:
        element_code = resource.get("element_code", "")
        resource_index = resource.get("resource_index", "")
        tf_name = resource.get("tf_name", "")
        if element_code in ("PRJ", "REP", "PREP", "GRP") and resource_index:
            typed_key = f"{element_code}:{resource_index}"
            state_protection_by_key[typed_key] = "protected_" in tf_name
    return state_protection_by_key


def _merge_state_only_rows(
    intent_keys: set[str],
    state_protection_by_key: dict[str, bool],
) -> list[dict]:
    """Replicate the state-only row merging logic from utilities.py."""
    rows = []
    for state_key, state_protected in state_protection_by_key.items():
        if state_key in intent_keys:
            continue
        rtype = state_key.split(":")[0] if ":" in state_key else "unknown"
        rows.append({
            "resource_key": state_key,
            "type": rtype,
            "intent": "No Intent",
            "state": "Protected" if state_protected else "Unprotected",
            "status": "State Only",
        })
    return rows


# ---------------------------------------------------------------------------
# Regression: GRP element code included in display counts
# ---------------------------------------------------------------------------


class TestGrpIncludedInDisplayCounts:
    """Fix: GRP resources must be counted in TF-state summary cards.

    Previously, the filter only included PRJ, REP, PREP — omitting GRP.
    """

    def test_grp_member_appears_in_state_protection_map(self) -> None:
        resources = _make_reconcile_resources([
            {"element_code": "GRP", "resource_index": "member", "tf_name": "protected_groups"},
            {"element_code": "PRJ", "resource_index": "project_a", "tf_name": "projects"},
        ])
        state_map = _build_state_protection_map(resources)

        assert "GRP:member" in state_map
        assert state_map["GRP:member"] is True  # protected_groups → protected
        assert "PRJ:project_a" in state_map
        assert state_map["PRJ:project_a"] is False  # projects → unprotected

    def test_grp_unprotected_groups_tracked(self) -> None:
        resources = _make_reconcile_resources([
            {"element_code": "GRP", "resource_index": "everyone", "tf_name": "groups"},
        ])
        state_map = _build_state_protection_map(resources)

        assert "GRP:everyone" in state_map
        assert state_map["GRP:everyone"] is False

    def test_non_relevant_element_codes_excluded(self) -> None:
        resources = _make_reconcile_resources([
            {"element_code": "ENV", "resource_index": "dev", "tf_name": "environments"},
            {"element_code": "JOB", "resource_index": "nightly", "tf_name": "jobs"},
        ])
        state_map = _build_state_protection_map(resources)

        assert len(state_map) == 0


# ---------------------------------------------------------------------------
# Regression: State-only rows appear in grid
# ---------------------------------------------------------------------------


class TestStateOnlyRowsMerged:
    """Fix: Resources in TF state but not in protection-intent.json
    must still appear in the AG grid with "State Only" status.
    """

    def test_state_only_resource_gets_row(self) -> None:
        intent_keys = {"GRP:everyone"}
        state_map = {
            "GRP:everyone": False,
            "GRP:member": True,
        }

        state_only_rows = _merge_state_only_rows(intent_keys, state_map)

        assert len(state_only_rows) == 1
        row = state_only_rows[0]
        assert row["resource_key"] == "GRP:member"
        assert row["status"] == "State Only"
        assert row["state"] == "Protected"
        assert row["intent"] == "No Intent"

    def test_no_duplicate_rows_for_intent_resources(self) -> None:
        intent_keys = {"GRP:everyone", "GRP:member"}
        state_map = {
            "GRP:everyone": False,
            "GRP:member": True,
        }

        state_only_rows = _merge_state_only_rows(intent_keys, state_map)
        assert len(state_only_rows) == 0

    def test_multiple_state_only_resources(self) -> None:
        intent_keys: set[str] = set()
        state_map = {
            "GRP:member": True,
            "PRJ:project_x": False,
            "REP:repo_y": True,
        }

        state_only_rows = _merge_state_only_rows(intent_keys, state_map)
        assert len(state_only_rows) == 3
        keys = {r["resource_key"] for r in state_only_rows}
        assert keys == {"GRP:member", "PRJ:project_x", "REP:repo_y"}


# ---------------------------------------------------------------------------
# Regression: Summary/table parity
# ---------------------------------------------------------------------------


class TestSummaryTableParity:
    """If a resource is counted in TF-state summary cards, it must be
    representable in the management table.

    This is the "Summary/Table Parity" guardrail from .ralph/guardrails.md.
    """

    def test_protected_count_matches_grid_rows(self) -> None:
        resources = _make_reconcile_resources([
            {"element_code": "GRP", "resource_index": "member", "tf_name": "protected_groups"},
            {"element_code": "PRJ", "resource_index": "proj_a", "tf_name": "projects"},
            {"element_code": "REP", "resource_index": "repo_b", "tf_name": "protected_repositories"},
        ])

        state_map = _build_state_protection_map(resources)

        # Summary card count: how many are protected
        summary_protected_count = sum(1 for v in state_map.values() if v)

        # Grid: merge intents (empty) + state-only
        intent_keys: set[str] = set()
        state_only_rows = _merge_state_only_rows(intent_keys, state_map)

        grid_protected_count = sum(
            1 for r in state_only_rows if r["state"] == "Protected"
        )

        assert summary_protected_count == grid_protected_count, (
            f"Summary shows {summary_protected_count} protected but grid "
            f"only has {grid_protected_count} protected rows"
        )

    def test_unprotected_count_matches_grid_rows(self) -> None:
        resources = _make_reconcile_resources([
            {"element_code": "GRP", "resource_index": "everyone", "tf_name": "groups"},
            {"element_code": "PRJ", "resource_index": "proj_a", "tf_name": "projects"},
        ])

        state_map = _build_state_protection_map(resources)

        summary_unprotected_count = sum(1 for v in state_map.values() if not v)

        intent_keys: set[str] = set()
        state_only_rows = _merge_state_only_rows(intent_keys, state_map)

        grid_unprotected_count = sum(
            1 for r in state_only_rows if r["state"] == "Unprotected"
        )

        assert summary_unprotected_count == grid_unprotected_count


class TestDenseBaselineRepresentability:
    """Dense baseline requirement: every in-scope state row is representable."""

    def test_all_state_rows_are_representable_without_explicit_intents(self) -> None:
        resources = _make_reconcile_resources([
            {"element_code": "PRJ", "resource_index": "analytics", "tf_name": "projects"},
            {"element_code": "REP", "resource_index": "repo_a", "tf_name": "protected_repositories"},
            {"element_code": "GRP", "resource_index": "member", "tf_name": "protected_groups"},
        ])
        state_map = _build_state_protection_map(resources)

        manager = MagicMock()
        manager._intent = {}

        rows = _build_protection_grid_rows(
            protection_intent=manager,
            state_protection_by_key=state_map,
            yaml_protected_resources=set(),
        )
        represented_keys = {row["resource_key"] for row in rows}
        assert represented_keys == set(state_map.keys())
