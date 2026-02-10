"""Integration tests for deploy generate YAML merge behavior.

These tests verify the complete deploy generate workflow as it relates to
YAML merging: when an existing deployment YAML exists, source-selected projects
should be merged into it (not overwrite it), preserving already-managed resources.

This addresses the root cause bug where deploy generate would overwrite a
deployment YAML containing 11 managed projects with a source-selected YAML
containing only 1 project, causing Terraform to plan 303 destroys.

Reference: Fix Protection Flow Plan - Fix 2
"""

import json
import pytest
import shutil
import yaml
from pathlib import Path
from typing import Dict, Any, List

from importer.web.utils.adoption_yaml_updater import (
    merge_yaml_configs,
    apply_protection_from_set,
    apply_unprotection_from_set,
    apply_adoption_overrides,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def existing_deployment_yaml() -> Dict[str, Any]:
    """Represents an existing deployment YAML with 11 managed projects.
    
    This simulates the real-world scenario where the target account
    already has multiple projects managed under Terraform.
    """
    return {
        "version": 2,
        "account": {"id": 11, "name": "Target Account"},
        "projects": [
            {"key": f"project_{i}", "name": f"Project {i}", "protected": i % 3 == 0}
            for i in range(1, 12)  # 11 projects
        ],
        "globals": {
            "repositories": [
                {"key": f"repo_{i}", "remote_url": f"https://github.com/org/repo-{i}"}
                for i in range(1, 12)
            ],
            "connections": [
                {"key": "snowflake_prod", "type": "snowflake"},
                {"key": "snowflake_dev", "type": "snowflake"},
            ],
        },
    }


@pytest.fixture
def source_selected_yaml() -> Dict[str, Any]:
    """Represents a source-selected YAML with 1 cherry-picked project.
    
    This is what state.map.last_yaml_file points to after user selects
    a single project from source for migration.
    """
    return {
        "version": 2,
        "projects": [
            {
                "key": "new_project",
                "name": "New Migration Project",
                "protected": False,
                "repository": "new_repo",
            },
        ],
        "globals": {
            "repositories": [
                {
                    "key": "new_repo",
                    "remote_url": "https://github.com/org/new-repo",
                    "git_clone_strategy": "deploy_key",
                },
            ],
        },
    }


@pytest.fixture
def deployment_dir(tmp_path: Path) -> Path:
    """Create a temporary deployment directory."""
    deploy_dir = tmp_path / "deployments" / "migration"
    deploy_dir.mkdir(parents=True)
    return deploy_dir


# =============================================================================
# Tests: Deploy Generate Merge Behavior
# =============================================================================

class TestDeployGenerateMerge:
    """Integration tests simulating deploy generate with YAML merge."""
    
    def test_merge_preserves_existing_projects(
        self, deployment_dir, existing_deployment_yaml, source_selected_yaml
    ):
        """Existing YAML with 11 projects + source with 1 new = 12 projects in output."""
        # Arrange: Write existing deployment YAML
        existing_yaml_path = deployment_dir / "dbt-cloud-config.yml"
        with open(existing_yaml_path, "w") as f:
            yaml.dump(existing_deployment_yaml, f, default_flow_style=False, sort_keys=False)
        
        # Act: Simulate merge (what deploy generate should do)
        with open(existing_yaml_path, "r") as f:
            existing = yaml.safe_load(f)
        merged = merge_yaml_configs(existing, source_selected_yaml)
        with open(existing_yaml_path, "w") as f:
            yaml.dump(merged, f, default_flow_style=False, sort_keys=False)
        
        # Assert: All 11 existing + 1 new = 12 projects
        with open(existing_yaml_path, "r") as f:
            result = yaml.safe_load(f)
        
        assert len(result["projects"]) == 12
        project_keys = {p["key"] for p in result["projects"]}
        assert "new_project" in project_keys
        for i in range(1, 12):
            assert f"project_{i}" in project_keys, f"project_{i} should be preserved"
    
    def test_fresh_migration_copies_source(
        self, deployment_dir, source_selected_yaml
    ):
        """No existing YAML - source used as-is (fresh migration behavior)."""
        # Arrange: No existing YAML file
        yaml_path = deployment_dir / "dbt-cloud-config.yml"
        assert not yaml_path.exists()
        
        # Act: Simulate fresh deploy generate (no merge needed)
        # When there's no existing file, merge_yaml_configs with None base returns source
        result = merge_yaml_configs(None, source_selected_yaml)
        with open(yaml_path, "w") as f:
            yaml.dump(result, f, default_flow_style=False, sort_keys=False)
        
        # Assert
        with open(yaml_path, "r") as f:
            output = yaml.safe_load(f)
        
        assert len(output["projects"]) == 1
        assert output["projects"][0]["key"] == "new_project"
    
    def test_merge_then_protection_applied(
        self, deployment_dir, existing_deployment_yaml, source_selected_yaml
    ):
        """Merge runs first, then protection intents applied to merged YAML."""
        # Arrange
        yaml_path = deployment_dir / "dbt-cloud-config.yml"
        with open(yaml_path, "w") as f:
            yaml.dump(existing_deployment_yaml, f, default_flow_style=False, sort_keys=False)
        
        # Act Step 1: Merge
        with open(yaml_path, "r") as f:
            existing = yaml.safe_load(f)
        merged = merge_yaml_configs(existing, source_selected_yaml)
        with open(yaml_path, "w") as f:
            yaml.dump(merged, f, default_flow_style=False, sort_keys=False)
        
        # Act Step 2: Apply protection intent to new project
        apply_protection_from_set(str(yaml_path), {"PRJ:new_project"})
        
        # Assert: New project is protected, existing projects unchanged
        with open(yaml_path, "r") as f:
            result = yaml.safe_load(f)
        
        new_proj = next(p for p in result["projects"] if p["key"] == "new_project")
        assert new_proj.get("protected") is True
        
        # Existing protected project still protected
        project_3 = next(p for p in result["projects"] if p["key"] == "project_3")
        assert project_3.get("protected") is True
        
        # Total projects still 12
        assert len(result["projects"]) == 12
    
    def test_merge_idempotent(
        self, deployment_dir, existing_deployment_yaml, source_selected_yaml
    ):
        """Running merge twice produces same result."""
        # Arrange
        yaml_path = deployment_dir / "dbt-cloud-config.yml"
        with open(yaml_path, "w") as f:
            yaml.dump(existing_deployment_yaml, f, default_flow_style=False, sort_keys=False)
        
        # Act: Merge once
        with open(yaml_path, "r") as f:
            existing = yaml.safe_load(f)
        merged1 = merge_yaml_configs(existing, source_selected_yaml)
        
        # Act: Merge again with same source
        merged2 = merge_yaml_configs(merged1, source_selected_yaml)
        
        # Assert: Same result
        assert len(merged1["projects"]) == len(merged2["projects"])
        keys1 = {p["key"] for p in merged1["projects"]}
        keys2 = {p["key"] for p in merged2["projects"]}
        assert keys1 == keys2
    
    def test_merge_with_adoption_overrides(
        self, deployment_dir, existing_deployment_yaml, source_selected_yaml
    ):
        """Merge + adoption overrides work together correctly."""
        # Arrange
        yaml_path = deployment_dir / "dbt-cloud-config.yml"
        with open(yaml_path, "w") as f:
            yaml.dump(existing_deployment_yaml, f, default_flow_style=False, sort_keys=False)
        
        # Act Step 1: Merge
        with open(yaml_path, "r") as f:
            existing = yaml.safe_load(f)
        merged = merge_yaml_configs(existing, source_selected_yaml)
        with open(yaml_path, "w") as f:
            yaml.dump(merged, f, default_flow_style=False, sort_keys=False)
        
        # Act Step 2: Apply adoption overrides for the new repo
        adopt_data = [
            {
                "source_key": "new_repo",
                "source_type": "REP",
                "target_id": "999",
            }
        ]
        target_report_items = [
            {
                "element_type_code": "REP",
                "dbt_id": 999,
                "remote_url": "https://github.com/target-org/adopted-repo",
                "git_clone_strategy": "github_app",
            }
        ]
        apply_adoption_overrides(str(yaml_path), adopt_data, target_report_items)
        
        # Assert: Existing repos still present, new repo updated
        with open(yaml_path, "r") as f:
            result = yaml.safe_load(f)
        
        repo_keys = {r["key"] for r in result["globals"]["repositories"]}
        assert "repo_1" in repo_keys, "Existing repos should be preserved"
        assert "new_repo" in repo_keys, "New repo should be present"
        
        # Verify adoption override was applied to new repo
        new_repo = next(r for r in result["globals"]["repositories"] if r["key"] == "new_repo")
        assert new_repo["remote_url"] == "https://github.com/target-org/adopted-repo"
        assert new_repo["git_clone_strategy"] == "github_app"
    
    def test_merge_preserves_protection_on_existing_resources(
        self, deployment_dir, existing_deployment_yaml, source_selected_yaml
    ):
        """Protected resources in existing YAML retain protection after merge."""
        # Arrange
        yaml_path = deployment_dir / "dbt-cloud-config.yml"
        with open(yaml_path, "w") as f:
            yaml.dump(existing_deployment_yaml, f, default_flow_style=False, sort_keys=False)
        
        # Act: Merge
        with open(yaml_path, "r") as f:
            existing = yaml.safe_load(f)
        merged = merge_yaml_configs(existing, source_selected_yaml)
        
        # Assert: Protected projects from existing YAML still protected
        for project in merged["projects"]:
            original = next(
                (p for p in existing_deployment_yaml["projects"] if p["key"] == project["key"]),
                None,
            )
            if original and original.get("protected"):
                assert project.get("protected") is True, (
                    f"Project {project['key']} should remain protected after merge"
                )
