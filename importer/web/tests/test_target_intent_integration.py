"""Integration tests: deploy generate with target intent (TF state as floor)."""

import json
import pytest
import yaml
from pathlib import Path

from importer.web.utils.target_intent import (
    TargetIntentManager,
    compute_target_intent,
    get_tf_state_project_keys,
)


@pytest.fixture
def scenario_partial_source_full_state(tmp_path: Path):
    """Setup: TF state has 11 projects, source focus YAML has 1 project, baseline has 11."""
    # TF state
    state = {
        "version": 4,
        "resources": [
            {
                "type": "dbtcloud_project",
                "name": "projects",
                "instances": [{"index_key": f"project_{i}"} for i in range(1, 12)],
            }
        ],
    }
    tfstate = tmp_path / "terraform.tfstate"
    with open(tfstate, "w") as f:
        json.dump(state, f)

    # Source focus: 1 project
    source_config = {
        "version": 1,
        "projects": [{"key": "project_5", "name": "Project 5", "environments": []}],
    }
    source_path = tmp_path / "source.yml"
    with open(source_path, "w") as f:
        yaml.dump(source_config, f, default_flow_style=False, sort_keys=False)

    # Baseline: 11 projects
    baseline_config = {
        "version": 1,
        "projects": [
            {"key": f"project_{i}", "name": f"Project {i}", "environments": []}
            for i in range(1, 12)
        ],
    }
    baseline_path = tmp_path / "baseline.yml"
    with open(baseline_path, "w") as f:
        yaml.dump(baseline_config, f, default_flow_style=False, sort_keys=False)

    return {
        "tfstate": tfstate,
        "source_yaml": str(source_path),
        "baseline_yaml": str(baseline_path),
        "tmp_path": tmp_path,
    }


class TestTargetIntentIntegration:
    def test_partial_source_full_state_produces_complete_yaml(self, scenario_partial_source_full_state):
        """Source has 1 project, TF state has 11 -> output YAML has 11 projects."""
        s = scenario_partial_source_full_state
        result = compute_target_intent(
            tfstate_path=s["tfstate"],
            source_focus_yaml=s["source_yaml"],
            baseline_yaml=s["baseline_yaml"],
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        out_projects = result.output_config.get("projects", [])
        out_keys = [p["key"] for p in out_projects]
        assert len(out_keys) == 11
        assert "project_5" in out_keys
        assert "project_1" in out_keys

    def test_merged_yaml_preserves_all_tf_state_keys(self, scenario_partial_source_full_state):
        """Every project key in tfstate appears in output YAML."""
        s = scenario_partial_source_full_state
        result = compute_target_intent(
            tfstate_path=s["tfstate"],
            source_focus_yaml=s["source_yaml"],
            baseline_yaml=s["baseline_yaml"],
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        tf_keys = get_tf_state_project_keys(s["tfstate"])
        out_keys = {p["key"] for p in result.output_config.get("projects", [])}
        assert tf_keys <= out_keys

    def test_target_intent_json_written(self, scenario_partial_source_full_state):
        """target-intent.json exists in output dir after compute + save."""
        s = scenario_partial_source_full_state
        result = compute_target_intent(
            tfstate_path=s["tfstate"],
            source_focus_yaml=s["source_yaml"],
            baseline_yaml=s["baseline_yaml"],
            target_report_items=None,
            adopt_rows=[],
            removal_keys=set(),
        )
        manager = TargetIntentManager(s["tmp_path"])
        manager.write_merged_yaml(result)
        manager.save(result)
        assert (s["tmp_path"] / "target-intent.json").exists()
        assert (s["tmp_path"] / "dbt-cloud-config-merged.yml").exists()

    def test_scenario_orphan_in_state_not_in_target(self, scenario_partial_source_full_state):
        """E2E scenario: TF state has 11 projects, target fetch has 10 -> 1 orphan_flagged."""
        s = scenario_partial_source_full_state
        target_report_items = [
            {"element_type_code": "PRJ", "element_mapping_id": f"project_{i}", "dbt_id": 600 + i}
            for i in range(1, 11)
        ]
        result = compute_target_intent(
            tfstate_path=s["tfstate"],
            source_focus_yaml=s["source_yaml"],
            baseline_yaml=s["baseline_yaml"],
            target_report_items=target_report_items,
            adopt_rows=[],
            removal_keys=set(),
        )
        assert "project_11" in result.orphan_flagged_keys
        out_keys = [p["key"] for p in result.output_config.get("projects", [])]
        assert "project_11" not in out_keys
        assert len(out_keys) == 10
