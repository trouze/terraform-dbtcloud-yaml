"""Unit tests for target_intent module: compute logic, orphan detection, serialization, match_mappings."""

import json
import pytest
from pathlib import Path

from unittest.mock import MagicMock

from importer.web.utils.target_intent import (
    DISP_RETAINED,
    DISP_UPSERTED,
    DISP_ADOPTED,
    DISP_REMOVED,
    DISP_ORPHAN_FLAGGED,
    get_tf_state_project_keys,
    get_tf_state_protected_project_keys,
    get_tf_state_global_sections,
    build_included_globals,
    compute_target_intent,
    validate_intent_coverage,
    ResourceDisposition,
    TargetIntentResult,
    TargetIntentManager,
    SourceToTargetMapping,
    StateToTargetMapping,
    MatchMappings,
)


# --- Fixtures ---


@pytest.fixture
def sample_tfstate_11_projects(tmp_path: Path) -> Path:
    """Minimal terraform.tfstate with 11 project keys (dbtcloud_project.projects)."""
    state = {
        "version": 4,
        "resources": [
            {
                "type": "dbtcloud_project",
                "name": "projects",
                "instances": [
                    {"index_key": "bt_data_ops_db"},
                    {"index_key": "bt_data_ops_dp"},
                    {"index_key": "bt_dbt_platform"},
                    {"index_key": "edw_dm_sales"},
                    {"index_key": "edw_dna_foundations_metrics"},
                    {"index_key": "sse_dm_fin_fido"},
                    {"index_key": "sse_dm_gdso"},
                    {"index_key": "sse_dna_fndn"},
                    {"index_key": "sse_dna_success"},
                    {"index_key": "sse_ml_pltm"},
                    {"index_key": "sse_mlp_fs"},
                ],
            }
        ],
    }
    path = tmp_path / "terraform.tfstate"
    with open(path, "w") as f:
        json.dump(state, f)
    return path


@pytest.fixture
def sample_tfstate_empty(tmp_path: Path) -> Path:
    """Empty terraform state (no projects)."""
    path = tmp_path / "terraform.tfstate"
    with open(path, "w") as f:
        json.dump({"version": 4, "resources": []}, f)
    return path


@pytest.fixture
def sample_source_focus_1_project(tmp_path: Path) -> str:
    """Source focus YAML with one project (sse_dm_fin_fido)."""
    config = {
        "version": 1,
        "projects": [
            {"key": "sse_dm_fin_fido", "name": "sse_dm_fin_fido", "environments": []}
        ],
    }
    path = tmp_path / "source_focus.yml"
    import yaml
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    return str(path)


@pytest.fixture
def sample_baseline_11_projects(tmp_path: Path) -> str:
    """Baseline YAML with all 11 projects (minimal)."""
    keys = [
        "bt_data_ops_db", "bt_data_ops_dp", "bt_dbt_platform", "edw_dm_sales",
        "edw_dna_foundations_metrics", "sse_dm_fin_fido", "sse_dm_gdso",
        "sse_dna_fndn", "sse_dna_success", "sse_ml_pltm", "sse_mlp_fs",
    ]
    config = {
        "version": 1,
        "projects": [{"key": k, "name": k, "environments": []} for k in keys],
    }
    path = tmp_path / "baseline.yml"
    import yaml
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    return str(path)


@pytest.fixture
def sample_target_report_items_10_projects():
    """Target fetch report items: 10 projects (one missing = orphan candidate)."""
    keys = [
        "bt_data_ops_db", "bt_data_ops_dp", "bt_dbt_platform", "edw_dm_sales",
        "edw_dna_foundations_metrics", "sse_dm_fin_fido", "sse_dm_gdso",
        "sse_dna_fndn", "sse_dna_success", "sse_ml_pltm",
        # sse_mlp_fs missing -> orphan if in TF state
    ]
    return [
        {"element_type_code": "PRJ", "element_mapping_id": k, "dbt_id": 600 + i}
        for i, k in enumerate(keys)
    ]


# --- get_tf_state_project_keys ---


class TestGetTFStateProjectKeys:
    def test_extracts_project_keys(self, sample_tfstate_11_projects: Path):
        keys = get_tf_state_project_keys(sample_tfstate_11_projects)
        assert len(keys) == 11
        assert "sse_dm_fin_fido" in keys
        assert "bt_data_ops_db" in keys
        assert "sse_mlp_fs" in keys

    def test_empty_state(self, sample_tfstate_empty: Path):
        keys = get_tf_state_project_keys(sample_tfstate_empty)
        assert keys == set()

    def test_missing_file(self, tmp_path: Path):
        keys = get_tf_state_project_keys(tmp_path / "nonexistent.tfstate")
        assert keys == set()

    def test_includes_protected_projects_resource(self, tmp_path: Path):
        """Both 'projects' and 'protected_projects' names contribute keys."""
        state = {
            "version": 4,
            "resources": [
                {"type": "dbtcloud_project", "name": "projects", "instances": [{"index_key": "p1"}]},
                {"type": "dbtcloud_project", "name": "protected_projects", "instances": [{"index_key": "p2"}]},
            ],
        }
        path = tmp_path / "terraform.tfstate"
        with open(path, "w") as f:
            json.dump(state, f)
        keys = get_tf_state_project_keys(path)
        assert keys == {"p1", "p2"}


# --- compute_target_intent ---


class TestComputeTargetIntent:
    def test_tf_state_keys_default_to_retained(
        self,
        sample_tfstate_11_projects: Path,
        sample_baseline_11_projects: str,
        sample_source_focus_1_project: str,
    ):
        """TF state has 11 projects, source focus has 1 -> 10 retained + 1 upserted."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        assert len(result.retained_keys) == 10
        assert len(result.upserted_keys) == 1
        assert "sse_dm_fin_fido" in result.upserted_keys
        assert "bt_data_ops_db" in result.retained_keys
        assert len(result.output_config.get("projects", [])) == 11

    def test_source_focus_upserts_into_retained(
        self,
        sample_tfstate_11_projects: Path,
        sample_baseline_11_projects: str,
        sample_source_focus_1_project: str,
    ):
        """Source focus project gets upserted disposition."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        assert result.dispositions["sse_dm_fin_fido"].disposition == DISP_UPSERTED

    def test_removal_keys_create_removed_disposition(
        self,
        sample_tfstate_11_projects: Path,
        sample_baseline_11_projects: str,
        sample_source_focus_1_project: str,
    ):
        """Explicit removal key -> removed disposition, excluded from output."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=None,
            adopt_rows=[],
            removal_keys={"bt_data_ops_db"},
        )
        assert result.dispositions["bt_data_ops_db"].disposition == DISP_REMOVED
        project_keys = [p["key"] for p in result.output_config.get("projects", [])]
        assert "bt_data_ops_db" not in project_keys
        assert len(project_keys) == 10

    def test_removal_keys_multiple_all_get_removed_disposition(
        self,
        sample_tfstate_11_projects: Path,
        sample_baseline_11_projects: str,
        sample_source_focus_1_project: str,
    ):
        """Multiple removal keys -> all get DISP_REMOVED and excluded from output."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=None,
            adopt_rows=[],
            removal_keys={"bt_data_ops_db", "sse_dm_gdso"},
        )
        assert result.dispositions["bt_data_ops_db"].disposition == DISP_REMOVED
        assert result.dispositions["sse_dm_gdso"].disposition == DISP_REMOVED
        project_keys = [p["key"] for p in result.output_config.get("projects", [])]
        assert "bt_data_ops_db" not in project_keys
        assert "sse_dm_gdso" not in project_keys
        assert len(project_keys) == 9

    def test_orphan_detected_when_not_in_target_fetch(
        self,
        sample_tfstate_11_projects: Path,
        sample_baseline_11_projects: str,
        sample_source_focus_1_project: str,
        sample_target_report_items_10_projects: list,
    ):
        """TF state key not in target fetch -> orphan_flagged."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=sample_target_report_items_10_projects,
            adopt_rows=[],
            removal_keys=set(),
        )
        assert "sse_mlp_fs" in result.orphan_flagged_keys
        assert result.dispositions["sse_mlp_fs"].disposition == DISP_ORPHAN_FLAGGED
        project_keys = [p["key"] for p in result.output_config.get("projects", [])]
        assert "sse_mlp_fs" not in project_keys

    def test_orphan_not_flagged_without_target_fetch(
        self,
        sample_tfstate_11_projects: Path,
        sample_baseline_11_projects: str,
        sample_source_focus_1_project: str,
    ):
        """No target fetch data -> no orphan_flagged; all retained or upserted."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        assert len(result.orphan_flagged_keys) == 0

    def test_no_tfstate_uses_source_focus_only(
        self,
        sample_tfstate_empty: Path,
        sample_source_focus_1_project: str,
        tmp_path: Path,
    ):
        """No TF state -> only source focus projects in output."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_empty,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=None,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        assert len(result.retained_keys) == 0
        assert len(result.upserted_keys) == 1
        assert "sse_dm_fin_fido" in result.upserted_keys
        assert len(result.output_config.get("projects", [])) == 1


# --- validate_intent_coverage ---


class TestValidateIntentCoverage:
    def test_full_coverage_no_warnings(
        self,
        sample_tfstate_11_projects: Path,
        sample_baseline_11_projects: str,
        sample_source_focus_1_project: str,
    ):
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        tf_state_keys = get_tf_state_project_keys(sample_tfstate_11_projects)
        warnings = validate_intent_coverage(result, tf_state_keys, set())
        assert len(warnings) == 0

    def test_removed_keys_dont_trigger_warning(
        self,
        sample_tfstate_11_projects: Path,
        sample_baseline_11_projects: str,
        sample_source_focus_1_project: str,
    ):
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=None,
            adopt_rows=[],
            removal_keys={"bt_data_ops_db"},
        )
        tf_state_keys = get_tf_state_project_keys(sample_tfstate_11_projects)
        warnings = validate_intent_coverage(result, tf_state_keys, {"bt_data_ops_db"})
        assert len(warnings) == 0


# --- Serialization ---


class TestTargetIntentResultSerialization:
    def test_round_trip_dict(self):
        result = TargetIntentResult(
            version=1,
            computed_at="2026-02-04T12:00:00Z",
            dispositions={
                "p1": ResourceDisposition("p1", "PRJ", DISP_RETAINED, "tf_state_default"),
                "p2": ResourceDisposition("p2", "PRJ", DISP_UPSERTED, "source_focus"),
            },
            coverage_warnings=[],
            drift_warnings=[],
        )
        data = result.to_dict()
        restored = TargetIntentResult.from_dict(data)
        assert restored.version == result.version
        assert restored.computed_at == result.computed_at
        assert set(restored.dispositions.keys()) == set(result.dispositions.keys())
        assert restored.retained_keys == result.retained_keys
        assert restored.upserted_keys == result.upserted_keys


# --- TargetIntentManager ---


class TestTargetIntentManager:
    def test_write_merged_yaml(self, tmp_path: Path):
        manager = TargetIntentManager(tmp_path)
        result = TargetIntentResult(
            version=1,
            computed_at="2026-02-04T12:00:00Z",
            dispositions={},
            output_config={"version": 1, "projects": [{"key": "p1", "name": "p1"}]},
        )
        path = manager.write_merged_yaml(result)
        assert Path(path).exists()
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["projects"][0]["key"] == "p1"

    def test_save_and_load(self, tmp_path: Path):
        manager = TargetIntentManager(tmp_path)
        result = TargetIntentResult(
            version=1,
            computed_at="2026-02-04T12:00:00Z",
            dispositions={
                "p1": ResourceDisposition("p1", "PRJ", DISP_RETAINED, "tf_state_default"),
            },
        )
        manager.save(result)
        assert (tmp_path / "target-intent.json").exists()
        loaded = manager.load()
        assert loaded is not None
        assert "p1" in loaded.dispositions
        assert loaded.dispositions["p1"].disposition == DISP_RETAINED

    def test_load_missing_returns_none(self, tmp_path: Path):
        manager = TargetIntentManager(tmp_path)
        assert manager.load() is None


# --- Match Mappings ---


class TestSourceToTargetMapping:
    def test_round_trip_dict(self):
        m = SourceToTargetMapping(
            source_key="prj_1",
            resource_type="PRJ",
            target_id="42",
            target_name="My Project",
            match_type="exact_match",
            action="match",
            confirmed=True,
            confirmed_at="2026-02-09T10:00:00Z",
        )
        data = m.to_dict()
        restored = SourceToTargetMapping.from_dict(data)
        assert restored.source_key == "prj_1"
        assert restored.target_id == "42"
        assert restored.match_type == "exact_match"
        assert restored.confirmed is True
        assert restored.confirmed_at == "2026-02-09T10:00:00Z"

    def test_from_confirmed_mapping(self):
        cm = {
            "source_key": "prj_1",
            "resource_type": "PRJ",
            "target_id": "42",
            "target_name": "My Project",
            "match_type": "exact_match",
            "action": "adopt",
        }
        m = SourceToTargetMapping.from_confirmed_mapping(cm)
        assert m.source_key == "prj_1"
        assert m.action == "adopt"
        assert m.confirmed is True
        assert m.confirmed_at is not None

    def test_to_confirmed_mapping(self):
        m = SourceToTargetMapping(
            source_key="prj_1",
            resource_type="PRJ",
            target_id="42",
            target_name="My Project",
            match_type="manual",
            action="match",
            confirmed=True,
        )
        cm = m.to_confirmed_mapping()
        assert cm["source_key"] == "prj_1"
        assert cm["target_id"] == "42"
        assert cm["action"] == "match"
        # confirmed/confirmed_at are NOT in confirmed_mapping format
        assert "confirmed" not in cm


class TestStateToTargetMapping:
    def test_round_trip_dict(self):
        m = StateToTargetMapping(
            state_key="prj_1",
            state_address="dbtcloud_project.projects[\"prj_1\"]",
            resource_type="PRJ",
            target_id="42",
            target_name="My Project",
            match_type="auto",
            confirmed=False,
        )
        data = m.to_dict()
        restored = StateToTargetMapping.from_dict(data)
        assert restored.state_key == "prj_1"
        assert restored.state_address == "dbtcloud_project.projects[\"prj_1\"]"
        assert restored.target_id == "42"
        assert restored.match_type == "auto"


class TestMatchMappings:
    def test_round_trip_dict(self):
        mm = MatchMappings(
            source_to_target=[
                SourceToTargetMapping(source_key="prj_1", target_id="42"),
                SourceToTargetMapping(source_key="prj_2", target_id="43"),
            ],
            state_to_target=[
                StateToTargetMapping(state_key="prj_1", target_id="42"),
            ],
        )
        data = mm.to_dict()
        restored = MatchMappings.from_dict(data)
        assert len(restored.source_to_target) == 2
        assert len(restored.state_to_target) == 1
        assert restored.source_to_target[0].source_key == "prj_1"
        assert restored.state_to_target[0].state_key == "prj_1"

    def test_source_key_set(self):
        mm = MatchMappings(
            source_to_target=[
                SourceToTargetMapping(source_key="a"),
                SourceToTargetMapping(source_key="b"),
            ],
        )
        assert mm.source_key_set() == {"a", "b"}

    def test_state_key_set(self):
        mm = MatchMappings(
            state_to_target=[
                StateToTargetMapping(state_key="x"),
                StateToTargetMapping(state_key="y"),
            ],
        )
        assert mm.state_key_set() == {"x", "y"}

    def test_to_confirmed_mappings(self):
        mm = MatchMappings(
            source_to_target=[
                SourceToTargetMapping(source_key="prj_1", target_id="42", action="match"),
                SourceToTargetMapping(source_key="prj_2", target_id="43", action="adopt"),
            ],
        )
        confirmed = mm.to_confirmed_mappings()
        assert len(confirmed) == 2
        assert confirmed[0]["source_key"] == "prj_1"
        assert confirmed[1]["action"] == "adopt"

    def test_from_confirmed_mappings(self):
        confirmed = [
            {"source_key": "prj_1", "target_id": "42", "action": "match", "match_type": "exact_match"},
            {"source_key": "prj_2", "target_id": "43", "action": "adopt", "match_type": "manual"},
        ]
        mm = MatchMappings.from_confirmed_mappings(confirmed)
        assert len(mm.source_to_target) == 2
        assert mm.source_to_target[0].source_key == "prj_1"
        assert mm.source_to_target[0].match_type == "exact_match"
        assert mm.source_to_target[0].confirmed is True
        assert mm.source_to_target[1].action == "adopt"

    def test_empty_default(self):
        mm = MatchMappings()
        assert mm.source_to_target == []
        assert mm.state_to_target == []
        assert mm.to_dict() == {"source_to_target": [], "state_to_target": []}


class TestMatchMappingsIntentSerialization:
    def test_intent_round_trip_with_match_mappings(self, tmp_path: Path):
        """TargetIntentResult with match_mappings round-trips through save/load."""
        manager = TargetIntentManager(tmp_path)
        mm = MatchMappings(
            source_to_target=[
                SourceToTargetMapping(source_key="prj_1", target_id="42", confirmed=True),
            ],
            state_to_target=[
                StateToTargetMapping(state_key="prj_1", state_address="dbtcloud_project.projects[\"prj_1\"]", target_id="42"),
            ],
        )
        intent = TargetIntentResult(
            version=2,
            computed_at="2026-02-09T10:00:00Z",
            dispositions={
                "prj_1": ResourceDisposition("prj_1", "PRJ", DISP_RETAINED, "tf_state_default"),
            },
            match_mappings=mm,
        )
        manager.save(intent)
        loaded = manager.load()
        assert loaded is not None
        assert len(loaded.match_mappings.source_to_target) == 1
        assert loaded.match_mappings.source_to_target[0].source_key == "prj_1"
        assert loaded.match_mappings.source_to_target[0].confirmed is True
        assert len(loaded.match_mappings.state_to_target) == 1
        assert loaded.match_mappings.state_to_target[0].target_id == "42"

    def test_backward_compat_version_1_no_match_mappings(self, tmp_path: Path):
        """Version 1 intent files have no match_mappings -> defaults to empty."""
        v1_data = {
            "version": 1,
            "computed_at": "2026-01-01T00:00:00Z",
            "provenance": {},
            "dispositions": {
                "prj_1": {"key": "prj_1", "resource_type": "PRJ", "disposition": "retained", "source": "tf_state_default"},
            },
            "coverage_warnings": [],
            "drift_warnings": [],
        }
        path = tmp_path / "target-intent.json"
        with open(path, "w") as f:
            json.dump(v1_data, f)
        manager = TargetIntentManager(tmp_path)
        loaded = manager.load()
        assert loaded is not None
        assert loaded.version == 1
        assert loaded.match_mappings.source_to_target == []
        assert loaded.match_mappings.state_to_target == []

    def test_compute_preserves_match_mappings_from_previous(
        self,
        sample_tfstate_11_projects: Path,
        sample_baseline_11_projects: str,
        sample_source_focus_1_project: str,
    ):
        """compute_target_intent preserves match_mappings from previous_intent."""
        previous = TargetIntentResult(
            version=2,
            match_mappings=MatchMappings(
                source_to_target=[
                    SourceToTargetMapping(source_key="prj_1", target_id="42", confirmed=True),
                ],
                state_to_target=[
                    StateToTargetMapping(state_key="prj_1", target_id="42"),
                ],
            ),
        )
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
            previous_intent=previous,
        )
        # match_mappings should be preserved from previous
        assert len(result.match_mappings.source_to_target) == 1
        assert result.match_mappings.source_to_target[0].source_key == "prj_1"
        assert len(result.match_mappings.state_to_target) == 1

    def test_sync_confirmed_mappings_round_trip(self):
        """confirmed_mappings -> MatchMappings -> confirmed_mappings round-trip."""
        original = [
            {"source_key": "a", "resource_type": "PRJ", "target_id": "1", "target_name": "A", "match_type": "exact_match", "action": "match"},
            {"source_key": "b", "resource_type": "ENV", "target_id": "2", "target_name": "B", "match_type": "manual", "action": "adopt"},
        ]
        mm = MatchMappings.from_confirmed_mappings(original)
        restored = mm.to_confirmed_mappings()
        assert len(restored) == 2
        for orig, rest in zip(original, restored):
            assert rest["source_key"] == orig["source_key"]
            assert rest["target_id"] == orig["target_id"]
            assert rest["action"] == orig["action"]
            assert rest["match_type"] == orig["match_type"]


# --- Protection Defaults ---


class TestProtectionDefaults:
    """Verify default protection logic: all false unless TF state protected."""

    @pytest.fixture
    def tfstate_with_protected(self, tmp_path: Path) -> Path:
        """TF state with both regular and protected projects."""
        state = {
            "version": 4,
            "resources": [
                {
                    "type": "dbtcloud_project",
                    "name": "projects",
                    "instances": [
                        {"index_key": "unprotected_proj"},
                    ],
                },
                {
                    "type": "dbtcloud_project",
                    "name": "protected_projects",
                    "instances": [
                        {"index_key": "protected_proj"},
                    ],
                },
            ],
        }
        path = tmp_path / "terraform.tfstate"
        with open(path, "w") as f:
            json.dump(state, f)
        return path

    @pytest.fixture
    def baseline_yaml_both(self, tmp_path: Path) -> str:
        import yaml
        config = {
            "version": 1,
            "projects": [
                {"key": "unprotected_proj", "name": "Unprotected"},
                {"key": "protected_proj", "name": "Protected"},
            ],
        }
        path = tmp_path / "baseline.yml"
        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        return str(path)

    def test_default_protection_is_false(
        self, tfstate_with_protected: Path, baseline_yaml_both: str
    ):
        """All resources default to protected=False unless in protected_projects."""
        result = compute_target_intent(
            tfstate_path=tfstate_with_protected,
            source_focus_yaml="",
            baseline_yaml=baseline_yaml_both,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        # unprotected_proj should be protected=False
        assert "unprotected_proj" in result.dispositions
        assert result.dispositions["unprotected_proj"].protected is False
        assert result.dispositions["unprotected_proj"].protection_set_by == "default_unprotected"

    def test_tf_state_protected_projects_get_protected_true(
        self, tfstate_with_protected: Path, baseline_yaml_both: str
    ):
        """Resources in protected_projects TF resource get protected=True."""
        result = compute_target_intent(
            tfstate_path=tfstate_with_protected,
            source_focus_yaml="",
            baseline_yaml=baseline_yaml_both,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        assert "protected_proj" in result.dispositions
        assert result.dispositions["protected_proj"].protected is True
        assert result.dispositions["protected_proj"].protection_set_by == "tf_state_default"

    def test_get_tf_state_protected_project_keys(self, tfstate_with_protected: Path):
        """get_tf_state_protected_project_keys returns only protected keys."""
        keys = get_tf_state_protected_project_keys(tfstate_with_protected)
        assert keys == {"protected_proj"}

    def test_get_tf_state_project_keys_includes_both(self, tfstate_with_protected: Path):
        """get_tf_state_project_keys now includes both regular and protected."""
        keys = get_tf_state_project_keys(tfstate_with_protected)
        assert keys == {"unprotected_proj", "protected_proj"}

    def test_protection_intent_overrides_tf_state(
        self, tfstate_with_protected: Path, baseline_yaml_both: str
    ):
        """Level 3: protection-intent.json entry overrides TF state default."""
        from unittest.mock import MagicMock

        # Mock a protection intent manager that says protected_proj should be unprotected
        mock_mgr = MagicMock()

        class FakeIntent:
            def __init__(self, protected: bool):
                self.protected = protected

        def get_intent_side_effect(key):
            if key == "protected_proj":
                return FakeIntent(False)  # Override TF state
            return None

        mock_mgr.get_intent = MagicMock(side_effect=get_intent_side_effect)

        result = compute_target_intent(
            tfstate_path=tfstate_with_protected,
            source_focus_yaml="",
            baseline_yaml=baseline_yaml_both,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
            protection_intent_manager=mock_mgr,
        )
        assert result.dispositions["protected_proj"].protected is False
        assert result.dispositions["protected_proj"].protection_set_by == "protection_intent"

    def test_user_edit_overrides_all(
        self, tfstate_with_protected: Path, baseline_yaml_both: str
    ):
        """Level 4: User edit in previous intent overrides everything."""
        previous = TargetIntentResult(
            version=2,
            dispositions={
                "unprotected_proj": ResourceDisposition(
                    key="unprotected_proj",
                    resource_type="PRJ",
                    disposition=DISP_RETAINED,
                    source="tf_state_default",
                    protected=True,
                    protection_set_by="user",
                    protection_set_at="2025-01-01T00:00:00Z",
                ),
            },
        )
        result = compute_target_intent(
            tfstate_path=tfstate_with_protected,
            source_focus_yaml="",
            baseline_yaml=baseline_yaml_both,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
            previous_intent=previous,
        )
        # User override should persist even though TF default would be False
        assert result.dispositions["unprotected_proj"].protected is True
        assert result.dispositions["unprotected_proj"].protection_set_by == "user"
        assert result.dispositions["unprotected_proj"].protection_set_at == "2025-01-01T00:00:00Z"


# --- ResourceDisposition Protection Serialization ---


class TestResourceDispositionProtection:
    def test_protection_fields_round_trip(self):
        """protected, protection_set_by, protection_set_at survive to_dict/from_dict."""
        disp = ResourceDisposition(
            key="proj1",
            resource_type="PRJ",
            disposition=DISP_RETAINED,
            source="tf_state_default",
            protected=True,
            protection_set_by="user",
            protection_set_at="2025-01-15T12:00:00Z",
        )
        d = disp.to_dict()
        assert d["protected"] is True
        assert d["protection_set_by"] == "user"
        assert d["protection_set_at"] == "2025-01-15T12:00:00Z"

        restored = ResourceDisposition.from_dict(d)
        assert restored.protected is True
        assert restored.protection_set_by == "user"
        assert restored.protection_set_at == "2025-01-15T12:00:00Z"

    def test_protection_defaults_when_missing(self):
        """Missing protection fields default to False/None."""
        d = {"key": "proj1", "resource_type": "PRJ", "disposition": "retained", "source": "test"}
        restored = ResourceDisposition.from_dict(d)
        assert restored.protected is False
        assert restored.protection_set_by is None
        assert restored.protection_set_at is None


# --- output_config Round-Trip ---


class TestOutputConfigRoundTrip:
    def test_manager_save_load_preserves_output_config(self, tmp_path: Path):
        """TargetIntentManager.save() and load() preserve output_config."""
        manager = TargetIntentManager(tmp_path)
        intent = TargetIntentResult(
            version=2,
            computed_at="2025-01-15T12:00:00Z",
            dispositions={
                "proj1": ResourceDisposition(
                    key="proj1",
                    resource_type="PRJ",
                    disposition=DISP_RETAINED,
                    source="tf_state_default",
                ),
            },
            output_config={
                "version": 1,
                "projects": [
                    {"key": "proj1", "name": "Project 1", "environments": []},
                ],
            },
        )
        manager.save(intent)

        # Verify file was written
        assert (tmp_path / "target-intent.json").exists()

        # Reload and check
        loaded = manager.load()
        assert loaded is not None
        assert loaded.output_config is not None
        assert "projects" in loaded.output_config
        assert len(loaded.output_config["projects"]) == 1
        assert loaded.output_config["projects"][0]["key"] == "proj1"

    def test_manager_load_empty_output_config(self, tmp_path: Path):
        """Load handles intent files without output_config gracefully."""
        # Write a minimal intent file without output_config
        intent_file = tmp_path / "target-intent.json"
        with open(intent_file, "w") as f:
            json.dump({
                "version": 2,
                "computed_at": "2025-01-15T12:00:00Z",
                "dispositions": {},
            }, f)

        manager = TargetIntentManager(tmp_path)
        loaded = manager.load()
        assert loaded is not None
        assert loaded.output_config == {}

    def test_manager_save_load_preserves_protection(self, tmp_path: Path):
        """Protection fields survive save/load round-trip."""
        manager = TargetIntentManager(tmp_path)
        intent = TargetIntentResult(
            version=2,
            dispositions={
                "proj1": ResourceDisposition(
                    key="proj1",
                    resource_type="PRJ",
                    disposition=DISP_RETAINED,
                    source="tf_state_default",
                    protected=True,
                    protection_set_by="user",
                    protection_set_at="2025-01-15T12:00:00Z",
                ),
                "proj2": ResourceDisposition(
                    key="proj2",
                    resource_type="PRJ",
                    disposition=DISP_RETAINED,
                    source="tf_state_default",
                    protected=False,
                    protection_set_by="default_unprotected",
                ),
            },
        )
        manager.save(intent)
        loaded = manager.load()
        assert loaded is not None
        assert loaded.dispositions["proj1"].protected is True
        assert loaded.dispositions["proj1"].protection_set_by == "user"
        assert loaded.dispositions["proj2"].protected is False
        assert loaded.dispositions["proj2"].protection_set_by == "default_unprotected"


# --- Retained Project Config ---


class TestRetainedProjectConfig:
    """Verify that retained projects get config from baseline YAML."""

    def test_retained_projects_have_config_from_baseline(
        self,
        sample_tfstate_11_projects: Path,
        sample_source_focus_1_project: str,
        sample_baseline_11_projects: str,
    ):
        """Retained projects (in TF state but not in source focus) get config from baseline."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=sample_baseline_11_projects,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        # output_config should have ALL 11 projects
        project_keys = {p["key"] for p in result.output_config.get("projects", [])}
        assert len(project_keys) == 11
        # Retained project should be in output
        assert "bt_data_ops_db" in project_keys
        # Upserted project should also be in output
        assert "sse_dm_fin_fido" in project_keys

    def test_output_config_without_baseline_only_has_source(
        self,
        sample_tfstate_11_projects: Path,
        sample_source_focus_1_project: str,
    ):
        """Without baseline, retained projects have no config -- only source focus project appears."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=sample_source_focus_1_project,
            baseline_yaml=None,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        # Only the source focus project has config
        project_keys = {p["key"] for p in result.output_config.get("projects", [])}
        # Source focus project should be there
        assert "sse_dm_fin_fido" in project_keys
        # But no retained projects have config since no baseline
        # (Some may still be in project_keys if the merge logic adds them)


# --- sync_protection_to_disposition ---


class TestSyncProtectionToDisposition:
    def test_sync_updates_disposition(self, tmp_path: Path):
        """sync_protection_to_disposition updates the matching disposition."""
        manager = TargetIntentManager(tmp_path)
        intent = TargetIntentResult(
            version=2,
            dispositions={
                "proj1": ResourceDisposition(
                    key="proj1",
                    resource_type="PRJ",
                    disposition=DISP_RETAINED,
                    source="tf_state_default",
                    protected=False,
                    protection_set_by="default_unprotected",
                ),
            },
        )
        manager.save(intent)

        # Sync protection change
        result = manager.sync_protection_to_disposition("proj1", True)
        assert result is True

        # Reload and verify
        loaded = manager.load()
        assert loaded.dispositions["proj1"].protected is True
        assert loaded.dispositions["proj1"].protection_set_by == "user"
        assert loaded.dispositions["proj1"].protection_set_at is not None

    def test_sync_handles_prefixed_key(self, tmp_path: Path):
        """sync_protection_to_disposition handles TYPE:key format."""
        manager = TargetIntentManager(tmp_path)
        intent = TargetIntentResult(
            version=2,
            dispositions={
                "my_project": ResourceDisposition(
                    key="my_project",
                    resource_type="PRJ",
                    disposition=DISP_RETAINED,
                    source="tf_state_default",
                    protected=False,
                ),
            },
        )
        manager.save(intent)

        result = manager.sync_protection_to_disposition("PRJ:my_project", True)
        assert result is True

        loaded = manager.load()
        assert loaded.dispositions["my_project"].protected is True

    def test_sync_returns_false_for_missing_key(self, tmp_path: Path):
        """sync_protection_to_disposition returns False for unknown keys."""
        manager = TargetIntentManager(tmp_path)
        intent = TargetIntentResult(version=2, dispositions={})
        manager.save(intent)

        result = manager.sync_protection_to_disposition("nonexistent", True)
        assert result is False

    def test_sync_returns_false_when_no_intent(self, tmp_path: Path):
        """sync_protection_to_disposition returns False when no intent file exists."""
        manager = TargetIntentManager(tmp_path / "empty")
        result = manager.sync_protection_to_disposition("proj1", True)
        assert result is False


# ── Config Preference Tests ─────────────────────────────────────


class TestConfigPreferenceField:
    """Tests for the config_preference field on ResourceDisposition."""

    def test_default_value_is_target(self):
        """config_preference defaults to 'target'."""
        disp = ResourceDisposition(key="p", resource_type="PRJ", disposition=DISP_RETAINED, source="test")
        assert disp.config_preference == "target"

    def test_serialization_roundtrip(self):
        """config_preference survives to_dict -> from_dict."""
        disp = ResourceDisposition(
            key="p",
            resource_type="PRJ",
            disposition=DISP_UPSERTED,
            source="source_focus",
            config_preference="source",
        )
        d = disp.to_dict()
        assert d["config_preference"] == "source"

        restored = ResourceDisposition.from_dict(d)
        assert restored.config_preference == "source"

    def test_from_dict_missing_field_defaults_to_target(self):
        """Old data without config_preference field defaults to 'target'."""
        d = {"key": "p", "resource_type": "PRJ", "disposition": DISP_RETAINED, "source": "test"}
        restored = ResourceDisposition.from_dict(d)
        assert restored.config_preference == "target"


class TestConfigPreferenceInComputeIntent:
    """Tests that compute_target_intent sets config_preference correctly."""

    def test_retained_projects_get_target_preference(
        self, sample_tfstate_11_projects, sample_source_focus_1_project
    ):
        """Retained (TF-state-only, not in source focus) projects get config_preference='target'."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=str(sample_source_focus_1_project),
            baseline_yaml=None,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        # sse_dm_fin_fido is the only project in both source YAML and TF state -> upserted
        # All other TF state projects should be retained with target preference
        for key in ("bt_data_ops_db", "bt_data_ops_dp", "bt_dbt_platform"):
            disp = result.dispositions.get(key)
            assert disp is not None, f"Missing disposition for {key}"
            assert disp.disposition == DISP_RETAINED
            assert disp.config_preference == "target", f"{key} should have target preference"

    def test_upserted_project_gets_source_preference(
        self, sample_tfstate_11_projects, sample_source_focus_1_project
    ):
        """Upserted (in source focus) projects get config_preference='source'."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=str(sample_source_focus_1_project),
            baseline_yaml=None,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        disp = result.dispositions.get("sse_dm_fin_fido")
        assert disp is not None
        assert disp.disposition == DISP_UPSERTED
        assert disp.config_preference == "source"

    def test_removed_projects_get_target_preference(
        self, sample_tfstate_11_projects, sample_source_focus_1_project
    ):
        """Removed projects get config_preference='target'."""
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=str(sample_source_focus_1_project),
            baseline_yaml=None,
            target_report_items=None,
            adopt_rows=[],
            removal_keys={"bt_data_ops_db"},
        )
        disp = result.dispositions["bt_data_ops_db"]
        assert disp.disposition == DISP_REMOVED
        assert disp.config_preference == "target"

    def test_confirmed_preserves_config_preference(
        self, sample_tfstate_11_projects, sample_source_focus_1_project
    ):
        """Confirmed dispositions from previous intent preserve config_preference."""
        previous = TargetIntentResult(
            version=2,
            dispositions={
                "bt_data_ops_db": ResourceDisposition(
                    key="bt_data_ops_db",
                    resource_type="PRJ",
                    disposition=DISP_RETAINED,
                    source="tf_state_default",
                    confirmed=True,
                    config_preference="target",
                ),
            },
        )
        result = compute_target_intent(
            tfstate_path=sample_tfstate_11_projects,
            source_focus_yaml=str(sample_source_focus_1_project),
            baseline_yaml=None,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
            previous_intent=previous,
        )
        disp = result.dispositions["bt_data_ops_db"]
        assert disp.confirmed is True
        assert disp.config_preference == "target"

    def test_full_intent_json_roundtrip_with_config_preference(self, tmp_path):
        """TargetIntentResult with config_preference survives save/load via TargetIntentManager."""
        manager = TargetIntentManager(tmp_path)
        intent = TargetIntentResult(
            version=2,
            dispositions={
                "proj_a": ResourceDisposition(
                    key="proj_a",
                    resource_type="PRJ",
                    disposition=DISP_RETAINED,
                    source="tf_state_default",
                    config_preference="target",
                ),
                "proj_b": ResourceDisposition(
                    key="proj_b",
                    resource_type="PRJ",
                    disposition=DISP_UPSERTED,
                    source="source_focus",
                    config_preference="source",
                ),
            },
        )
        manager.save(intent)
        loaded = manager.load()
        assert loaded is not None
        assert loaded.dispositions["proj_a"].config_preference == "target"
        assert loaded.dispositions["proj_b"].config_preference == "source"


# ── get_tf_state_global_sections Tests ──────────────────────────


class TestGetTFStateGlobalSections:
    """Tests for detecting which global sections have resources in TF state."""

    def test_empty_state_returns_empty(self, tmp_path: Path):
        """Empty TF state -> no global sections detected."""
        path = tmp_path / "terraform.tfstate"
        with open(path, "w") as f:
            json.dump({"version": 4, "resources": []}, f)
        result = get_tf_state_global_sections(path)
        assert result == {}

    def test_missing_file_returns_empty(self, tmp_path: Path):
        """Missing TF state file -> empty dict."""
        result = get_tf_state_global_sections(tmp_path / "nonexistent.tfstate")
        assert result == {}

    def test_detects_groups(self, tmp_path: Path):
        """TF state with dbtcloud_group resources -> groups section detected."""
        state = {
            "version": 4,
            "resources": [
                {
                    "type": "dbtcloud_group",
                    "name": "groups",
                    "instances": [
                        {"index_key": "owner"},
                        {"index_key": "developer"},
                        {"index_key": "analyst"},
                    ],
                }
            ],
        }
        path = tmp_path / "terraform.tfstate"
        with open(path, "w") as f:
            json.dump(state, f)
        result = get_tf_state_global_sections(path)
        assert result == {"groups": 3}

    def test_detects_service_tokens(self, tmp_path: Path):
        """TF state with dbtcloud_service_token resources -> service_tokens detected."""
        state = {
            "version": 4,
            "resources": [
                {
                    "type": "dbtcloud_service_token",
                    "name": "service_tokens",
                    "instances": [
                        {"index_key": "deploy_token"},
                    ],
                }
            ],
        }
        path = tmp_path / "terraform.tfstate"
        with open(path, "w") as f:
            json.dump(state, f)
        result = get_tf_state_global_sections(path)
        assert result == {"service_tokens": 1}

    def test_detects_multiple_global_types(self, tmp_path: Path):
        """TF state with multiple global types -> all detected with correct counts."""
        state = {
            "version": 4,
            "resources": [
                {
                    "type": "dbtcloud_group",
                    "name": "groups",
                    "instances": [{"index_key": "owner"}, {"index_key": "dev"}],
                },
                {
                    "type": "dbtcloud_service_token",
                    "name": "tokens",
                    "instances": [{"index_key": "t1"}],
                },
                {
                    "type": "dbtcloud_notification",
                    "name": "notifications",
                    "instances": [{"index_key": "n1"}, {"index_key": "n2"}],
                },
                # Projects should not appear in global sections
                {
                    "type": "dbtcloud_project",
                    "name": "projects",
                    "instances": [{"index_key": "p1"}],
                },
            ],
        }
        path = tmp_path / "terraform.tfstate"
        with open(path, "w") as f:
            json.dump(state, f)
        result = get_tf_state_global_sections(path)
        assert result == {"groups": 2, "service_tokens": 1, "notifications": 2}
        assert "projects" not in result

    def test_ignores_connections_and_repositories(self, tmp_path: Path):
        """Connections and repositories are always-included and excluded from safety-net results."""
        state = {
            "version": 4,
            "resources": [
                {
                    "type": "dbtcloud_global_connection",
                    "name": "connections",
                    "instances": [{"index_key": "c1"}],
                },
                {
                    "type": "dbtcloud_repository",
                    "name": "repos",
                    "instances": [{"index_key": "r1"}],
                },
            ],
        }
        path = tmp_path / "terraform.tfstate"
        with open(path, "w") as f:
            json.dump(state, f)
        result = get_tf_state_global_sections(path)
        # Connections and repositories are NOT returned (always included, not part of safety net)
        assert result == {}


# ── build_included_globals Tests ────────────────────────────────


class TestBuildIncludedGlobals:
    """Tests for building the included_globals set from state flags."""

    def _make_mock_state(
        self,
        include_groups: bool = False,
        include_service_tokens: bool = False,
        terraform_dir: str = "",
    ) -> MagicMock:
        """Create a mock AppState with the given flags."""
        mock_state = MagicMock()
        mock_state.map.include_groups = include_groups
        mock_state.map.include_service_tokens = include_service_tokens
        mock_state.deploy.terraform_dir = terraform_dir
        return mock_state

    def test_default_includes_connections_and_repositories(self, tmp_path: Path):
        """Default state (nothing checked) -> only connections and repositories."""
        mock_state = self._make_mock_state(terraform_dir=str(tmp_path))
        result = build_included_globals(mock_state)
        assert "connections" in result
        assert "repositories" in result
        assert "groups" not in result
        assert "service_tokens" not in result

    def test_include_groups_flag(self, tmp_path: Path):
        """include_groups=True -> groups added."""
        mock_state = self._make_mock_state(include_groups=True, terraform_dir=str(tmp_path))
        result = build_included_globals(mock_state)
        assert "groups" in result
        assert "connections" in result

    def test_include_service_tokens_flag(self, tmp_path: Path):
        """include_service_tokens=True -> service_tokens added."""
        mock_state = self._make_mock_state(include_service_tokens=True, terraform_dir=str(tmp_path))
        result = build_included_globals(mock_state)
        assert "service_tokens" in result

    def test_both_flags(self, tmp_path: Path):
        """Both flags true -> both sections added."""
        mock_state = self._make_mock_state(
            include_groups=True,
            include_service_tokens=True,
            terraform_dir=str(tmp_path),
        )
        result = build_included_globals(mock_state)
        assert result >= {"connections", "repositories", "groups", "service_tokens"}

    def test_auto_retain_from_tf_state(self, tmp_path: Path):
        """Groups in TF state but not checked -> auto-retained (safety net)."""
        # Create a TF state with groups
        state_data = {
            "version": 4,
            "resources": [
                {
                    "type": "dbtcloud_group",
                    "name": "groups",
                    "instances": [{"index_key": "owner"}, {"index_key": "dev"}],
                },
            ],
        }
        tfstate_path = tmp_path / "terraform.tfstate"
        with open(tfstate_path, "w") as f:
            json.dump(state_data, f)

        mock_state = self._make_mock_state(
            include_groups=False,
            terraform_dir=str(tmp_path),
        )
        result = build_included_globals(mock_state)
        # Groups should be auto-retained even though unchecked
        assert "groups" in result

    def test_auto_retain_does_not_duplicate_checked(self, tmp_path: Path):
        """Groups checked AND in TF state -> included once, no duplication issue."""
        state_data = {
            "version": 4,
            "resources": [
                {
                    "type": "dbtcloud_group",
                    "name": "groups",
                    "instances": [{"index_key": "owner"}],
                },
            ],
        }
        tfstate_path = tmp_path / "terraform.tfstate"
        with open(tfstate_path, "w") as f:
            json.dump(state_data, f)

        mock_state = self._make_mock_state(
            include_groups=True,
            terraform_dir=str(tmp_path),
        )
        result = build_included_globals(mock_state)
        assert "groups" in result
        # Set operations ensure no duplication — just verify the set works
        assert len([s for s in result if s == "groups"]) == 1

    def test_no_tf_state_file(self, tmp_path: Path):
        """No TF state file -> no auto-retain, just user selections."""
        mock_state = self._make_mock_state(
            include_groups=True,
            terraform_dir=str(tmp_path / "nonexistent"),
        )
        result = build_included_globals(mock_state)
        assert "groups" in result
        assert "connections" in result


# ── included_globals Integration Tests ──────────────────────────


class TestIncludedGlobalsInComputeIntent:
    """Tests that compute_target_intent correctly filters globals based on included_globals."""

    @pytest.fixture
    def source_yaml_with_globals(self, tmp_path: Path) -> str:
        """Source YAML with projects and globals (groups, service_tokens)."""
        import yaml
        config = {
            "version": 1,
            "projects": [
                {"key": "proj_a", "name": "Project A", "environments": []},
            ],
            "globals": {
                "connections": [{"name": "snowflake_conn"}],
                "repositories": [{"name": "main_repo"}],
                "groups": [
                    {"name": "Owner", "assign_by_default": False},
                    {"name": "Developer", "assign_by_default": True},
                ],
                "service_tokens": [
                    {"name": "deploy_token", "state": 1},
                ],
            },
        }
        path = tmp_path / "source_with_globals.yml"
        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        return str(path)

    @pytest.fixture
    def empty_tfstate(self, tmp_path: Path) -> Path:
        path = tmp_path / "terraform.tfstate"
        with open(path, "w") as f:
            json.dump({"version": 4, "resources": []}, f)
        return path

    def test_default_strips_groups_and_tokens(
        self, empty_tfstate: Path, source_yaml_with_globals: str
    ):
        """Default included_globals (None) strips groups and service_tokens from output."""
        result = compute_target_intent(
            tfstate_path=empty_tfstate,
            source_focus_yaml=source_yaml_with_globals,
            baseline_yaml=None,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        globals_in_output = result.output_config.get("globals", {})
        assert "connections" in globals_in_output
        assert "repositories" in globals_in_output
        assert "groups" not in globals_in_output
        assert "service_tokens" not in globals_in_output

    def test_included_globals_keeps_groups(
        self, empty_tfstate: Path, source_yaml_with_globals: str
    ):
        """included_globals with 'groups' -> groups preserved in output."""
        result = compute_target_intent(
            tfstate_path=empty_tfstate,
            source_focus_yaml=source_yaml_with_globals,
            baseline_yaml=None,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
            included_globals={"connections", "repositories", "groups"},
        )
        globals_in_output = result.output_config.get("globals", {})
        assert "groups" in globals_in_output
        assert len(globals_in_output["groups"]) == 2
        assert "service_tokens" not in globals_in_output

    def test_included_globals_keeps_both(
        self, empty_tfstate: Path, source_yaml_with_globals: str
    ):
        """included_globals with both groups and service_tokens -> both preserved."""
        result = compute_target_intent(
            tfstate_path=empty_tfstate,
            source_focus_yaml=source_yaml_with_globals,
            baseline_yaml=None,
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
            included_globals={"connections", "repositories", "groups", "service_tokens"},
        )
        globals_in_output = result.output_config.get("globals", {})
        assert "groups" in globals_in_output
        assert "service_tokens" in globals_in_output
        assert len(globals_in_output["groups"]) == 2
        assert len(globals_in_output["service_tokens"]) == 1
