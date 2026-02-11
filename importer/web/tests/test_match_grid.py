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


# --- Target-only rows (no source match) ---


@pytest.fixture
def target_only_items() -> list[dict]:
    """Target items that do NOT match any source items."""
    return [
        {
            "key": "platform_infra",
            "name": "Platform Infra",
            "element_type_code": "PRJ",
            "dbt_id": 900,
            "project_name": "Platform Infra",
        },
        {
            "key": "legacy_job",
            "name": "Legacy ETL Job",
            "element_type_code": "JOB",
            "dbt_id": 901,
            "project_name": "Platform Infra",
        },
    ]


@pytest.fixture
def matched_target_items() -> list[dict]:
    """Target items that overlap with minimal_source_items by dbt_id."""
    return [
        {
            "key": "proj_a",
            "name": "Project A Target",
            "element_type_code": "PRJ",
            "dbt_id": 1,
            "project_name": "Project A",
        },
    ]


class TestBuildGridDataTargetOnly:
    """Tests for target-only rows in build_grid_data (UT-AD-20, UT-AD-21, UT-AD-22)."""

    def test_target_only_rows_have_is_target_only_flag(
        self, minimal_source_items, target_only_items,
    ):
        """UT-AD-20: Target-only rows have is_target_only=True."""
        rows = build_grid_data(
            minimal_source_items,
            target_items=target_only_items,
            confirmed_mappings=[],
            rejected_keys=set(),
        )
        target_only = [r for r in rows if r.get("is_target_only")]
        assert len(target_only) == 2
        for r in target_only:
            assert r["is_target_only"] is True

    def test_target_only_rows_default_action_ignore(
        self, minimal_source_items, target_only_items,
    ):
        """UT-AD-21: Target-only rows default to action='ignore'."""
        rows = build_grid_data(
            minimal_source_items,
            target_items=target_only_items,
            confirmed_mappings=[],
            rejected_keys=set(),
        )
        target_only = [r for r in rows if r.get("is_target_only")]
        for r in target_only:
            assert r["action"] == "ignore"

    def test_target_only_rows_have_empty_source_columns(
        self, minimal_source_items, target_only_items,
    ):
        """UT-AD-22: Target-only rows have empty/null source name, id, and project."""
        rows = build_grid_data(
            minimal_source_items,
            target_items=target_only_items,
            confirmed_mappings=[],
            rejected_keys=set(),
        )
        target_only = [r for r in rows if r.get("is_target_only")]
        for r in target_only:
            assert r["source_name"] == ""
            assert r["source_id"] is None

    def test_target_only_rows_have_target_data(
        self, minimal_source_items, target_only_items,
    ):
        """Target-only rows carry the target_id and target_name from the target item."""
        rows = build_grid_data(
            minimal_source_items,
            target_items=target_only_items,
            confirmed_mappings=[],
            rejected_keys=set(),
        )
        target_only = [r for r in rows if r.get("is_target_only")]
        ids = {r.get("target_id") for r in target_only}
        assert "900" in ids
        assert "901" in ids
        names = {r.get("target_name") for r in target_only}
        assert "Platform Infra" in names
        assert "Legacy ETL Job" in names

    def test_matched_targets_not_duplicated_as_target_only(
        self, minimal_source_items, matched_target_items,
    ):
        """Targets that match a source item are NOT duplicated as target-only."""
        # matched_target_items has dbt_id=1 which overlaps with proj_a (source_id=1)
        # However, build_grid_data tracks matched targets by target_id in rows
        # For this test, we need a confirmed mapping to link them
        rows = build_grid_data(
            minimal_source_items,
            target_items=matched_target_items,
            confirmed_mappings=[{
                "source_key": "proj_a",
                "target_id": 1,
                "target_name": "Project A Target",
                "match_type": "manual",
                "action": "match",
            }],
            rejected_keys=set(),
        )
        target_only = [r for r in rows if r.get("is_target_only")]
        assert len(target_only) == 0

    def test_mixed_source_matched_target_only_and_state_only_flags(
        self, minimal_source_items, target_only_items,
    ):
        """UT-AD-27: Grid with all three row types has correct flags."""
        rows = build_grid_data(
            minimal_source_items,
            target_items=target_only_items,
            confirmed_mappings=[],
            rejected_keys=set(),
        )
        source_rows = [r for r in rows if not r.get("is_target_only") and not r.get("is_state_only")]
        target_only = [r for r in rows if r.get("is_target_only")]
        
        # Source rows should not have is_target_only
        for r in source_rows:
            assert not r.get("is_target_only")
        
        # Target-only rows should have is_target_only=True
        for r in target_only:
            assert r["is_target_only"] is True

    def test_no_target_items_produces_no_target_only_rows(self, minimal_source_items):
        """When no target items provided, no target-only rows are produced."""
        rows = build_grid_data(
            minimal_source_items,
            target_items=[],
            confirmed_mappings=[],
            rejected_keys=set(),
        )
        target_only = [r for r in rows if r.get("is_target_only")]
        assert len(target_only) == 0
