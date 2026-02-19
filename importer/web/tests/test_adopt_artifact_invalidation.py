"""Tests for adopt artifact invalidation on action changes."""

from pathlib import Path

import yaml

from importer.web.pages.adopt import _invalidate_adopt_artifacts_for_action_change


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.dump(payload, default_flow_style=False, sort_keys=False))


def test_invalidate_unadopt_removes_artifacts_and_resets_yaml(tmp_path, monkeypatch) -> None:
    """Changing to ignore removes stale artifacts and restores source YAML on zero-adopt."""
    tf_path = tmp_path
    deployment_yaml = tf_path / "dbt-cloud-config.yml"
    source_yaml = tf_path / "source-selected.yml"
    imports_file = tf_path / "adopt_imports.tf"
    plan_file = tf_path / "adopt.tfplan"

    _write_yaml(
        deployment_yaml,
        {
            "version": 2,
            "projects": [{"key": "not_terraform", "name": "Not Terraform"}],
            "globals": {"connections": [{"key": "legacy_conn"}]},
        },
    )
    _write_yaml(
        source_yaml,
        {
            "version": 2,
            "projects": [{"key": "source_project", "name": "Source Project"}],
        },
    )
    imports_file.write_text("import {}")
    plan_file.write_text("binary-plan-placeholder")

    convert_calls: list[tuple[str, str]] = []

    class _FakeConverter:
        def convert(self, yaml_path: str, out_dir: str) -> None:
            convert_calls.append((yaml_path, out_dir))

    monkeypatch.setattr(
        "importer.yaml_converter.YamlToTerraformConverter",
        _FakeConverter,
    )

    result = _invalidate_adopt_artifacts_for_action_change(
        tf_path=tf_path,
        adopt_grid_data=[
            {
                "source_key": "target__not_terraform",
                "source_type": "PRJ",
                "action": "ignore",
            }
        ],
        new_action="ignore",
        adopt_count=0,
        source_yaml_file=str(source_yaml),
    )

    assert not imports_file.exists()
    assert not plan_file.exists()
    assert result["removed_imports"] is True
    assert result["removed_plan"] is True
    assert result["reset_deployment_yaml_from_source"] is True
    assert result["cleanup_error"] is None
    assert len(convert_calls) >= 1

    final_yaml = yaml.safe_load(deployment_yaml.read_text())
    assert final_yaml["projects"][0]["key"] == "source_project"
    assert "globals" not in final_yaml


def test_invalidate_rerun_resets_scope_with_empty_grid(tmp_path, monkeypatch) -> None:
    """Rerun flow clears stale artifacts and resets deployment YAML to source scope."""
    tf_path = tmp_path
    deployment_yaml = tf_path / "dbt-cloud-config.yml"
    source_yaml = tf_path / "source-selected.yml"
    imports_file = tf_path / "adopt_imports.tf"
    plan_file = tf_path / "adopt.tfplan"

    _write_yaml(
        deployment_yaml,
        {
            "version": 2,
            "projects": [{"key": "not_terraform", "name": "Not Terraform"}],
            "globals": {"connections": [{"key": "legacy_conn"}]},
        },
    )
    _write_yaml(
        source_yaml,
        {
            "version": 2,
            "projects": [{"key": "source_project", "name": "Source Project"}],
        },
    )
    imports_file.write_text("import {}")
    plan_file.write_text("binary-plan-placeholder")

    convert_calls: list[tuple[str, str]] = []

    class _FakeConverter:
        def convert(self, yaml_path: str, out_dir: str) -> None:
            convert_calls.append((yaml_path, out_dir))

    monkeypatch.setattr(
        "importer.yaml_converter.YamlToTerraformConverter",
        _FakeConverter,
    )

    result = _invalidate_adopt_artifacts_for_action_change(
        tf_path=tf_path,
        adopt_grid_data=[],
        new_action="ignore",
        adopt_count=0,
        source_yaml_file=str(source_yaml),
    )

    assert result["removed_imports"] is True
    assert result["removed_plan"] is True
    assert result["reset_deployment_yaml_from_source"] is True
    assert result["cleanup_error"] is None
    assert len(convert_calls) >= 1
    assert not imports_file.exists()
    assert not plan_file.exists()

    final_yaml = yaml.safe_load(deployment_yaml.read_text())
    assert final_yaml["projects"][0]["key"] == "source_project"
    assert "globals" not in final_yaml
