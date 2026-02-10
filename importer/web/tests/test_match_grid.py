"""Unit tests for match grid: action values, removal_keys (unadopt), type labels."""

import pytest

from importer.web.components.match_grid import (
    ACTION_VALUES,
    MATCH_GRID_TYPE_LABELS,
    build_grid_data,
)


# --- ACTION_VALUES (unadopt in action column) ---


class TestActionValues:
    """Tests for the Action column allowed values."""

    def test_action_values_includes_unadopt(self):
        """Action column must include 'unadopt' for removal-from-TF-state flow."""
        assert "unadopt" in ACTION_VALUES

    def test_action_values_contains_all_expected_actions(self):
        """Action column includes match, create_new, skip, adopt, unadopt."""
        expected = {"match", "create_new", "skip", "adopt", "unadopt"}
        assert set(ACTION_VALUES) == expected


# --- MATCH_GRID_TYPE_LABELS (type filter dropdown) ---


class TestMatchGridTypeLabels:
    """Tests for type filter dropdown labels."""

    def test_type_labels_include_common_types(self):
        """Type filter dropdown has labels for PRJ, ENV, JOB, etc."""
        for code in ("PRJ", "ENV", "JOB", "CON", "REP", "VAR"):
            assert code in MATCH_GRID_TYPE_LABELS
            assert isinstance(MATCH_GRID_TYPE_LABELS[code], str)
            assert len(MATCH_GRID_TYPE_LABELS[code]) > 0

    def test_type_labels_include_derived_types(self):
        """Type filter includes JEVO, JCTG, PREP for overrides/triggers/links."""
        for code in ("JEVO", "JCTG", "PREP"):
            assert code in MATCH_GRID_TYPE_LABELS


# --- build_grid_data with removal_keys (unadopt on load) ---


@pytest.fixture
def minimal_source_items() -> list[dict]:
    """Two minimal source items (projects) for grid build tests."""
    return [
        {
            "key": "proj_a",
            "name": "Project A",
            "element_type_code": "PRJ",
            "dbt_id": 1,
            "project_name": "Project A",
        },
        {
            "key": "proj_b",
            "name": "Project B",
            "element_type_code": "PRJ",
            "dbt_id": 2,
            "project_name": "Project B",
        },
    ]


class TestBuildGridDataRemovalKeys:
    """Tests for build_grid_data with removal_keys (unadopt persistence)."""

    def test_removal_keys_sets_action_unadopt_and_status_unadopted(
        self, minimal_source_items: list[dict]
    ):
        """Rows whose source_key is in removal_keys get action=unadopt, status=unadopted."""
        rows = build_grid_data(
            minimal_source_items,
            target_items=[],
            confirmed_mappings=[],
            rejected_keys=set(),
            removal_keys={"proj_a"},
        )
        by_key = {r["source_key"]: r for r in rows}
        assert "proj_a" in by_key
        assert by_key["proj_a"]["action"] == "unadopt"
        assert by_key["proj_a"]["status"] == "unadopted"
        assert "proj_b" in by_key
        assert by_key["proj_b"]["action"] != "unadopt"
        assert by_key["proj_b"]["status"] != "unadopted"

    def test_removal_keys_empty_leaves_actions_unchanged(
        self, minimal_source_items: list[dict]
    ):
        """With no removal_keys, no row is forced to unadopt."""
        rows = build_grid_data(
            minimal_source_items,
            target_items=[],
            confirmed_mappings=[],
            rejected_keys=set(),
            removal_keys=set(),
        )
        for r in rows:
            # Default path gives create_new or match; neither should be unadopt
            assert r.get("action") in ("match", "create_new", "skip", "adopt", "unadopt")
        unadopted = [r for r in rows if r.get("action") == "unadopt"]
        assert len(unadopted) == 0

    def test_removal_keys_multiple_all_get_unadopt(self, minimal_source_items: list[dict]):
        """Multiple keys in removal_keys all get action=unadopt."""
        rows = build_grid_data(
            minimal_source_items,
            target_items=[],
            confirmed_mappings=[],
            rejected_keys=set(),
            removal_keys={"proj_a", "proj_b"},
        )
        for r in rows:
            assert r["action"] == "unadopt"
            assert r["status"] == "unadopted"
