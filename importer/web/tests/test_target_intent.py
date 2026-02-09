"""Unit tests for target_intent module: compute logic, orphan detection, serialization, match_mappings."""

import json
import pytest
from pathlib import Path

from importer.web.utils.target_intent import (
    DISP_RETAINED,
    DISP_UPSERTED,
    DISP_ADOPTED,
    DISP_REMOVED,
    DISP_ORPHAN_FLAGGED,
    get_tf_state_project_keys,
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

    def test_ignores_protected_projects_resource(self, tmp_path: Path):
        """Only 'projects' name counts, not 'protected_projects'."""
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
        assert keys == {"p1"}


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
