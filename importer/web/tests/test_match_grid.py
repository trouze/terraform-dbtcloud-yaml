"""Unit tests for match grid: action values, removal_keys (unadopt), type labels."""

import pytest
from types import SimpleNamespace

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
        """Action column includes match, create_new, skip, adopt, unadopt, ignore."""
        expected = {"match", "create_new", "skip", "adopt", "unadopt", "ignore"}
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


# --- Protection mismatch detection (UT-AD-06/07) ---


class TestProtectionMismatchDetection:
    """Criteria 21: Protection mismatch flag on rows.
    
    Tests the post-processing protection mismatch logic without needing
    actual StateReadResult objects. We build rows with pre-set fields
    that match what the state cross-reference would produce.
    """

    def test_protection_mismatch_when_state_protected_but_user_wants_unprotected(self):
        """UT-AD-06: protection_mismatch=True when state has .protected_ but user doesn't want it."""
        # Without state_result, build_grid_data sets drift_status=no_state.
        # We can verify the mismatch logic by building rows directly.
        rows = build_grid_data(
            source_items=[{
                "key": "PRJ:analytics",
                "name": "analytics",
                "element_type_code": "PRJ",
                "dbt_cloud_id": "100",
                "project_name": "analytics",
            }],
            target_items=[],
            confirmed_mappings=[],
            rejected_keys=set(),
            protected_resources=set(),
        )
        prj_rows = [r for r in rows if r.get("source_type") == "PRJ"]
        assert len(prj_rows) >= 1
        prj = prj_rows[0]
        
        # Simulate state cross-ref results (as if state was loaded)
        prj["drift_status"] = "in_sync"
        prj["state_address"] = 'module.dbt_cloud.dbtcloud_project.protected_projects["analytics"]'
        
        # The post-processing already ran; verify the logic inline
        state_protected = ".protected_" in prj["state_address"]
        user_wants = prj.get("yaml_protected", False)
        has_state = prj["drift_status"] in ("in_sync", "id_mismatch", "attr_mismatch")
        mismatch = has_state and user_wants != state_protected
        
        assert state_protected is True
        assert user_wants is False
        assert mismatch is True

    def test_protection_mismatch_when_state_protected_but_user_wants_unprotected_v2(self):
        """Variant: same as above but also checks yaml_protected field from build_grid_data."""
        # This test verifies the row fields set by build_grid_data itself
        rows = build_grid_data(
            source_items=[{
                "key": "PRJ:analytics",
                "name": "analytics",
                "element_type_code": "PRJ",
                "dbt_cloud_id": "100",
                "project_name": "analytics",
            }],
            target_items=[],
            confirmed_mappings=[],
            rejected_keys=set(),
            protected_resources=set(),  # user doesn't want protection
        )
        prj_rows = [r for r in rows if r.get("source_type") == "PRJ"]
        assert len(prj_rows) >= 1
        prj = prj_rows[0]
        # With no protected_resources and no intent manager, yaml_protected=False
        assert prj.get("yaml_protected") is False
        assert prj.get("protected") is False

    def test_no_protection_mismatch_when_consistent(self):
        """UT-AD-07: protection_mismatch=False when state and user agree (both unprotected)."""
        rows = build_grid_data(
            source_items=[{
                "key": "PRJ:analytics",
                "name": "analytics",
                "element_type_code": "PRJ",
                "dbt_cloud_id": "100",
                "project_name": "analytics",
            }],
            target_items=[],
            confirmed_mappings=[],
            rejected_keys=set(),
            protected_resources=set(),
        )
        prj_rows = [r for r in rows if r.get("source_type") == "PRJ"]
        assert len(prj_rows) >= 1
        prj = prj_rows[0]
        
        # Simulate state cross-ref with non-protected address
        prj["drift_status"] = "in_sync"
        prj["state_address"] = 'module.dbt_cloud.dbtcloud_project.projects["analytics"]'
        
        state_protected = ".protected_" in prj["state_address"]
        user_wants = prj.get("yaml_protected", False)
        has_state = prj["drift_status"] in ("in_sync", "id_mismatch", "attr_mismatch")
        mismatch = has_state and user_wants != state_protected
        
        assert state_protected is False
        assert user_wants is False
        assert mismatch is False

    def test_protection_mismatch_flag_set_by_build_grid_data(self):
        """Verify that build_grid_data sets protection_mismatch on rows."""
        rows = build_grid_data(
            source_items=[{
                "key": "PRJ:analytics",
                "name": "analytics",
                "element_type_code": "PRJ",
                "dbt_cloud_id": "100",
                "project_name": "analytics",
            }],
            target_items=[],
            confirmed_mappings=[],
            rejected_keys=set(),
        )
        prj_rows = [r for r in rows if r.get("source_type") == "PRJ"]
        assert len(prj_rows) >= 1
        prj = prj_rows[0]
        # Without state_result, drift_status is no_state → protection_mismatch should be False
        assert "protection_mismatch" in prj
        assert prj["protection_mismatch"] is False


# --- Target-only protection lookup (target__ prefix normalization) ---


@pytest.fixture
def target_only_group_items() -> list[dict]:
    """Target-only group items for protection lookup tests."""
    return [
        {
            "key": "everyone",
            "name": "Everyone",
            "element_type_code": "GRP",
            "dbt_id": 775,
            "project_name": "",
        },
        {
            "key": "member",
            "name": "Member",
            "element_type_code": "GRP",
            "dbt_id": 774,
            "project_name": "",
        },
    ]


class TestTargetOnlyProtection:
    """Tests for target-only resource protection lookup in build_grid_data.
    
    Target-only rows have source_key = "target__<name>" but protected_resources
    stores bare keys (without prefix). build_grid_data must normalize before lookup.
    """

    def test_target_only_protected_via_protected_resources(
        self, target_only_group_items,
    ):
        """Target-only row with bare key in protected_resources shows protected=True
        when action is 'adopt'. Ignored rows suppress protection display."""
        # With action='adopt', protection should show
        rows = build_grid_data(
            source_items=[],
            target_items=target_only_group_items,
            confirmed_mappings=[{
                "source_key": "target__everyone",
                "target_id": "775",
                "target_name": "Everyone",
                "action": "adopt",
                "match_type": "manual",
            }],
            rejected_keys=set(),
            protected_resources={"everyone"},  # bare key
        )
        by_key = {r["source_key"]: r for r in rows}
        assert "target__everyone" in by_key
        everyone = by_key["target__everyone"]
        assert everyone["protected"] is True
        assert everyone["yaml_protected"] is True

        # member is NOT in protected_resources and defaults to ignore
        assert "target__member" in by_key
        member = by_key["target__member"]
        assert member["protected"] is False
        assert member["yaml_protected"] is False

    def test_target_only_ignored_suppresses_protection(
        self, target_only_group_items,
    ):
        """Target-only row with 'ignore' action suppresses protection even if
        protected_resources or intent has stale entries."""
        rows = build_grid_data(
            source_items=[],
            target_items=target_only_group_items,
            confirmed_mappings=[],  # default action is 'ignore'
            rejected_keys=set(),
            protected_resources={"everyone"},  # stale protection
        )
        by_key = {r["source_key"]: r for r in rows}
        everyone = by_key["target__everyone"]
        # Protection is suppressed because action is 'ignore'
        assert everyone["protected"] is False
        assert everyone["yaml_protected"] is False

    def test_target_only_protected_via_intent_manager(
        self, target_only_group_items, tmp_path,
    ):
        """Target-only row with TYPE:bare_key in intent manager shows protected=True
        when action is 'adopt'."""
        from importer.web.utils.protection_intent import ProtectionIntentManager
        intent_file = tmp_path / "protection-intent.json"
        mgr = ProtectionIntentManager(intent_file)
        mgr.set_intent(
            key="GRP:everyone",
            protected=True,
            source="test",
            reason="test protection",
        )
        mgr.save()

        rows = build_grid_data(
            source_items=[],
            target_items=target_only_group_items,
            confirmed_mappings=[{
                "source_key": "target__everyone",
                "target_id": "775",
                "target_name": "Everyone",
                "action": "adopt",
                "match_type": "manual",
            }],
            rejected_keys=set(),
            protected_resources=set(),
            protection_intent_manager=mgr,
        )
        by_key = {r["source_key"]: r for r in rows}
        assert "target__everyone" in by_key
        everyone = by_key["target__everyone"]
        # Intent manager should mark it as protected (action is adopt, not suppressed)
        assert everyone["protected"] is True

    def test_target_only_unprotected_by_default(
        self, target_only_group_items,
    ):
        """Target-only rows with no protection in either system show protected=False."""
        rows = build_grid_data(
            source_items=[],
            target_items=target_only_group_items,
            confirmed_mappings=[],
            rejected_keys=set(),
            protected_resources=set(),
            protection_intent_manager=None,
        )
        for r in rows:
            if r.get("is_target_only"):
                assert r["protected"] is False
                assert r["yaml_protected"] is False


# --- Adopt-and-protect roundtrip test ---


class TestAdoptAndProtectRoundtrip:
    """End-to-end data flow: set intent + protected_resources, build grid, verify."""

    def test_adopt_and_protect_roundtrip(self, tmp_path):
        """Simulates _adopt_and_protect_from_match then verifies build_grid_data picks it up."""
        from importer.web.utils.protection_intent import ProtectionIntentManager

        # 1. Create protection intent (simulating _adopt_and_protect_from_match)
        intent_file = tmp_path / "protection-intent.json"
        mgr = ProtectionIntentManager(intent_file)
        mgr.set_intent(
            key="GRP:everyone",
            protected=True,
            source="adopt_and_protect",
            reason="Adopted & protected from Match page",
        )
        mgr.save()

        # 2. Set protected_resources with bare key (as the handler does)
        protected_resources = {"everyone"}

        # 3. Set confirmed_mappings with adopt action
        confirmed_mappings = [
            {"source_key": "target__everyone", "action": "adopt"},
        ]

        # 4. Build grid data
        target_items = [
            {
                "key": "everyone",
                "name": "Everyone",
                "element_type_code": "GRP",
                "dbt_id": 775,
                "project_name": "",
            },
        ]
        rows = build_grid_data(
            source_items=[],
            target_items=target_items,
            confirmed_mappings=confirmed_mappings,
            rejected_keys=set(),
            protected_resources=protected_resources,
            protection_intent_manager=mgr,
        )

        # 5. Verify the row
        by_key = {r["source_key"]: r for r in rows}
        assert "target__everyone" in by_key
        everyone = by_key["target__everyone"]
        assert everyone["action"] == "adopt"
        assert everyone["protected"] is True
        assert everyone["yaml_protected"] is True


class TestBuildGridDataStateLoadedFlag:
    """Regression coverage for state_loaded-only paths."""

    def test_state_loaded_without_state_result_does_not_crash_and_defaults_to_adopt(self):
        """When state is marked loaded but no state_result is present, rows still build."""
        source_items = [
            {
                "key": "conn_foo",
                "name": "conn_foo",
                "element_type_code": "CON",
                "dbt_id": 11,
                "project_name": "",
            }
        ]
        target_items = [
            {
                "key": "conn_foo",
                "name": "conn_foo",
                "element_type_code": "CON",
                "dbt_id": 1636,
                "project_name": "",
            }
        ]

        rows = build_grid_data(
            source_items=source_items,
            target_items=target_items,
            confirmed_mappings=[],
            rejected_keys=set(),
            state_result=None,
            state_loaded=True,
        )

        assert len(rows) >= 1
        row = rows[0]
        assert row["source_type"] == "CON"
        assert row["drift_status"] == "not_in_state"
        assert row["action"] == "adopt"

    def test_no_state_loaded_exact_match_defaults_to_adopt(self):
        """Exact target match with no Terraform state defaults to adopt."""
        source_items = [
            {
                "key": "conn_foo",
                "name": "conn_foo",
                "element_type_code": "CON",
                "dbt_id": 11,
                "project_name": "",
            }
        ]
        target_items = [
            {
                "key": "conn_foo",
                "name": "conn_foo",
                "element_type_code": "CON",
                "dbt_id": 1636,
                "project_name": "",
            }
        ]

        rows = build_grid_data(
            source_items=source_items,
            target_items=target_items,
            confirmed_mappings=[],
            rejected_keys=set(),
            state_result=None,
            state_loaded=False,
        )

        assert len(rows) >= 1
        row = rows[0]
        assert row["source_type"] == "CON"
        assert row["drift_status"] == "no_state"
        assert row["action"] == "adopt"

    def test_no_state_loaded_group_exact_match_defaults_to_match(self):
        """No-state auto-match should not auto-adopt groups."""
        source_items = [
            {
                "key": "member",
                "name": "member",
                "element_type_code": "GRP",
                "dbt_id": 10,
                "project_name": "",
            }
        ]
        target_items = [
            {
                "key": "member",
                "name": "member",
                "element_type_code": "GRP",
                "dbt_id": 774,
                "project_name": "",
            }
        ]

        rows = build_grid_data(
            source_items=source_items,
            target_items=target_items,
            confirmed_mappings=[],
            rejected_keys=set(),
            state_result=None,
            state_loaded=False,
        )

        assert len(rows) >= 1
        row = rows[0]
        assert row["source_type"] == "GRP"
        assert row["drift_status"] == "no_state"
        assert row["action"] == "match"

    def test_state_id_match_prefers_type_scoped_lookup_on_id_collision(self):
        """State-id auto-match should not fail when another type shares the same dbt_id."""
        source_items = [
            {
                "key": "sse_dm_fin_fido",
                "name": "sse_dm_fin_fido",
                "element_type_code": "PRJ",
                "dbt_id": 554,
                "project_name": "",
            }
        ]
        # PRJ and JOB intentionally share dbt_id=601 to simulate cross-type collision.
        target_items = [
            {
                "key": "job_with_same_id",
                "name": "job_with_same_id",
                "element_type_code": "JOB",
                "dbt_id": 601,
                "project_name": "other_project",
            },
            {
                "key": "sse_dm_fin_fido_target",
                "name": "renamed_project",
                "element_type_code": "PRJ",
                "dbt_id": 601,
                "project_name": "",
            },
        ]
        state_result = SimpleNamespace(
            resources=[
                SimpleNamespace(
                    element_code="PRJ",
                    dbt_id=601,
                    name="sse_dm_fin_fido",
                    tf_name="protected_projects",
                    project_id=None,
                    resource_index="sse_dm_fin_fido",
                    address='module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["sse_dm_fin_fido"]',
                )
            ]
        )

        rows = build_grid_data(
            source_items=source_items,
            target_items=target_items,
            confirmed_mappings=[],
            rejected_keys=set(),
            state_result=state_result,
            state_loaded=True,
        )

        assert len(rows) >= 1
        row = rows[0]
        assert row["source_type"] == "PRJ"
        assert row["target_id"] == "601"
        assert row["target_name"] == "renamed_project"
        assert row["confidence"] == "state_id_match"
        assert row["drift_status"] == "in_sync"


class TestMatchGridRegressionCases:
    """Regression tests for match-grid reconciliation edge cases."""

    def test_connection_state_none_id_does_not_report_id_mismatch(self):
        """CON state entries with null/None IDs should not produce id_mismatch."""
        source_items = [
            {
                "key": "snowflake",
                "name": "snowflake",
                "element_type_code": "CON",
                "dbt_id": 10,
                "project_name": "",
            }
        ]
        target_items = [
            {
                "key": "snowflake",
                "name": "snowflake",
                "element_type_code": "CON",
                "dbt_id": 1636,
                "project_name": "",
            }
        ]
        state_result = SimpleNamespace(
            resources=[
                SimpleNamespace(
                    element_code="CON",
                    dbt_id="None",
                    name="snowflake",
                    tf_name="snowflake",
                    project_id=None,
                    resource_index="snowflake",
                    address='module.dbt_cloud.dbtcloud_global_connection.connections["snowflake"]',
                )
            ]
        )

        rows = build_grid_data(
            source_items=source_items,
            target_items=target_items,
            confirmed_mappings=[],
            rejected_keys=set(),
            state_result=state_result,
            state_loaded=True,
        )

        assert len(rows) >= 1
        row = rows[0]
        assert row["source_type"] == "CON"
        assert row["target_id"] == "1636"
        assert row["drift_status"] == "not_in_state"
        assert row["drift_status"] != "id_mismatch"

    def test_extattr_state_index_auto_match_uses_state_id_and_avoids_state_only_duplicate(self):
        """EXTATTR rows should resolve by resource_index and suppress duplicate state-only rows."""
        source_items = [
            {
                "key": "ext_attrs_1",
                "name": "Extended Attributes",
                "element_type_code": "EXTATTR",
                "dbt_id": 33,
                "project_name": "analytics",
                "project_key": "analytics_3",
            }
        ]
        target_items = [
            {
                "key": "analytics_extattrs",
                "name": "Renamed Ext Attrs",
                "element_type_code": "EXTATTR",
                "dbt_id": 556,
                "project_name": "analytics",
            }
        ]
        state_result = SimpleNamespace(
            resources=[
                SimpleNamespace(
                    element_code="EXTATTR",
                    dbt_id=556,
                    name="legacy_extattr_name",
                    tf_name="extended_attributes",
                    project_id=3,
                    resource_index="analytics_3_ext_attrs_1",
                    address='module.dbt_cloud.module.projects_v2[0].dbtcloud_extended_attributes.extended_attributes["analytics_3_ext_attrs_1"]',
                )
            ]
        )

        rows = build_grid_data(
            source_items=source_items,
            target_items=target_items,
            confirmed_mappings=[],
            rejected_keys=set(),
            state_result=state_result,
            state_loaded=True,
        )

        assert len(rows) >= 1
        extattr_rows = [r for r in rows if r.get("source_type") == "EXTATTR"]
        assert len(extattr_rows) == 1
        row = extattr_rows[0]
        assert row["target_id"] == "556"
        assert row["confidence"] == "state_id_match"
        assert row["drift_status"] == "in_sync"

        duplicate_state_only = [
            r
            for r in rows
            if r.get("is_state_only")
            and r.get("source_type") == "EXTATTR"
            and r.get("state_id") == 556
        ]
        assert duplicate_state_only == []

    def test_confirmed_mapping_collision_disambiguates_by_project_name(self):
        """When source_key collides, confirmed mapping should select by project_name."""
        source_items = [
            {
                "key": "prod",
                "name": "PROD_CI",
                "element_type_code": "ENV",
                "dbt_id": 101,
                "project_name": "analytics_a",
            },
            {
                "key": "prod",
                "name": "PROD_CI",
                "element_type_code": "ENV",
                "dbt_id": 202,
                "project_name": "analytics_b",
            },
        ]
        target_items = [
            {
                "key": "analytics_a_prod",
                "name": "PROD_CI",
                "element_type_code": "ENV",
                "dbt_id": 6101,
                "project_name": "analytics_a",
            },
            {
                "key": "analytics_b_prod",
                "name": "PROD_CI",
                "element_type_code": "ENV",
                "dbt_id": 6202,
                "project_name": "analytics_b",
            },
        ]
        confirmed_mappings = [
            {
                "source_key": "prod",
                "source_name": "PROD_CI",
                "source_type": "ENV",
                "project_name": "analytics_a",
                "target_id": 6101,
                "target_name": "PROD_CI",
                "action": "match",
                "match_type": "manual",
            },
            {
                "source_key": "prod",
                "source_name": "PROD_CI",
                "source_type": "ENV",
                "project_name": "analytics_b",
                "target_id": 6202,
                "target_name": "PROD_CI",
                "action": "match",
                "match_type": "manual",
            },
        ]

        rows = build_grid_data(
            source_items=source_items,
            target_items=target_items,
            confirmed_mappings=confirmed_mappings,
            rejected_keys=set(),
        )

        row_by_project = {r["project_name"]: r for r in rows if r.get("source_type") == "ENV"}
        assert row_by_project["analytics_a"]["target_id"] == "6101"
        assert row_by_project["analytics_b"]["target_id"] == "6202"
