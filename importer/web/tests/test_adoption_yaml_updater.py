"""Unit tests for adoption_yaml_updater.py module.

These tests cover critical YAML modification functions:
- apply_unprotection_from_set: Remove protection flags from YAML
- apply_adoption_overrides: Apply target mappings to YAML
- Update helper functions: _update_project, _update_repository, etc.

Reference: Protection Test Coverage Analysis Plan
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any

from importer.web.utils.adoption_yaml_updater import (
    apply_protection_from_set,
    apply_unprotection_from_set,
    apply_adoption_overrides,
    merge_yaml_configs,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_yaml_config() -> Dict[str, Any]:
    """Sample YAML configuration for testing."""
    return {
        "projects": [
            {
                "key": "my_project",
                "name": "My Project",
                "protected": True,
                "repository": "my_repo",
                "environments": [
                    {"key": "dev", "name": "Development", "protected": False},
                    {"key": "prod", "name": "Production", "protected": True},
                ],
            },
            {
                "key": "other_project",
                "name": "Other Project",
                "protected": False,
                "environments": [
                    {"key": "staging", "name": "Staging"},
                ],
            },
        ],
        "globals": {
            "repositories": [
                {
                    "key": "global_repo",
                    "remote_url": "https://github.com/example/repo",
                    "protected": True,
                },
                {
                    "key": "dbt_ep_test_project",
                    "remote_url": "https://github.com/example/test",
                    "protected": True,
                },
            ],
        },
    }


@pytest.fixture
def yaml_file(tmp_path: Path, sample_yaml_config: Dict[str, Any]) -> Path:
    """Create a temporary YAML file with sample config."""
    file_path = tmp_path / "config.yml"
    with open(file_path, "w") as f:
        yaml.dump(sample_yaml_config, f)
    return file_path


# =============================================================================
# Tests: apply_unprotection_from_set
# =============================================================================

class TestApplyUnprotectionFromSet:
    """Tests for apply_unprotection_from_set function."""
    
    def test_removes_protected_flag_from_project(self, yaml_file: Path):
        """Test that protection flag is removed from a project."""
        # Act
        apply_unprotection_from_set(str(yaml_file), {"PRJ:my_project"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        my_project = next(p for p in result["projects"] if p["key"] == "my_project")
        assert "protected" not in my_project, "Protection should be removed"
    
    def test_removes_protected_flag_from_global_repository(self, yaml_file: Path):
        """Test that protection flag is removed from a global repository."""
        # Act
        apply_unprotection_from_set(str(yaml_file), {"REP:global_repo"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        repo = next(r for r in result["globals"]["repositories"] if r["key"] == "global_repo")
        assert "protected" not in repo, "Protection should be removed from repository"
    
    def test_handles_missing_resource_gracefully(self, yaml_file: Path):
        """Test that missing resources don't cause errors."""
        # Act - should not raise
        result_path = apply_unprotection_from_set(str(yaml_file), {"PRJ:nonexistent_project"})
        
        # Assert - file should still be valid
        assert result_path == str(yaml_file)
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        assert len(result["projects"]) == 2
    
    def test_preserves_other_fields_when_unprotecting(self, yaml_file: Path):
        """Test that other fields are preserved when removing protection."""
        # Act
        apply_unprotection_from_set(str(yaml_file), {"PRJ:my_project"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        my_project = next(p for p in result["projects"] if p["key"] == "my_project")
        assert my_project["name"] == "My Project"
        assert my_project["repository"] == "my_repo"
        assert "environments" in my_project
    
    def test_handles_unprefixed_keys(self, yaml_file: Path):
        """Test that unprefixed keys are handled."""
        # Act - unprefixed key should match project
        apply_unprotection_from_set(str(yaml_file), {"my_project"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        my_project = next(p for p in result["projects"] if p["key"] == "my_project")
        assert "protected" not in my_project
    
    def test_idempotent_unprotection(self, yaml_file: Path):
        """Test that running unprotection twice has same result as once."""
        # First unprotection
        apply_unprotection_from_set(str(yaml_file), {"PRJ:my_project"})
        
        with open(yaml_file, "r") as f:
            result1 = yaml.safe_load(f)
        
        # Second unprotection - should not error
        apply_unprotection_from_set(str(yaml_file), {"PRJ:my_project"})
        
        with open(yaml_file, "r") as f:
            result2 = yaml.safe_load(f)
        
        # Results should be identical
        assert result1 == result2
    
    def test_multiple_resources_unprotected(self, yaml_file: Path):
        """Test unprotecting multiple resources at once."""
        # Act
        apply_unprotection_from_set(str(yaml_file), {"PRJ:my_project", "REP:global_repo"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        my_project = next(p for p in result["projects"] if p["key"] == "my_project")
        repo = next(r for r in result["globals"]["repositories"] if r["key"] == "global_repo")
        
        assert "protected" not in my_project
        assert "protected" not in repo
    
    def test_empty_keys_set_returns_unchanged(self, yaml_file: Path):
        """Test that empty keys set returns file unchanged."""
        # Read original
        with open(yaml_file, "r") as f:
            original = yaml.safe_load(f)
        
        # Act
        result_path = apply_unprotection_from_set(str(yaml_file), set())
        
        # Assert - should return original path and content unchanged
        assert result_path == str(yaml_file)
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        assert result == original
    
    def test_handles_repository_with_prefix_pattern(self, yaml_file: Path):
        """Test matching repositories with dbt_ep_ prefix pattern."""
        # Act - use base name that should match dbt_ep_test_project
        apply_unprotection_from_set(str(yaml_file), {"REP:test_project"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        repo = next(r for r in result["globals"]["repositories"] if r["key"] == "dbt_ep_test_project")
        assert "protected" not in repo, "Should match by suffix pattern"


class TestApplyProtectionFromSet:
    """Additional tests for apply_protection_from_set function."""
    
    def test_sets_protected_flag_on_project(self, yaml_file: Path):
        """Test that protection flag is set on a project."""
        # First remove protection
        apply_unprotection_from_set(str(yaml_file), {"PRJ:my_project"})
        
        # Then re-apply
        apply_protection_from_set(str(yaml_file), {"PRJ:my_project"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        my_project = next(p for p in result["projects"] if p["key"] == "my_project")
        assert my_project.get("protected") is True
    
    def test_sets_protected_flag_on_repository(self, yaml_file: Path):
        """Test that protection flag is set on a global repository."""
        # First remove protection
        apply_unprotection_from_set(str(yaml_file), {"REP:global_repo"})
        
        # Then re-apply
        apply_protection_from_set(str(yaml_file), {"REP:global_repo"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        repo = next(r for r in result["globals"]["repositories"] if r["key"] == "global_repo")
        assert repo.get("protected") is True


# =============================================================================
# Tests: apply_adoption_overrides
# =============================================================================

class TestApplyAdoptionOverrides:
    """Tests for apply_adoption_overrides function."""
    
    @pytest.fixture
    def simple_yaml(self, tmp_path: Path) -> Path:
        """Create a simple YAML file for adoption testing."""
        config = {
            "projects": [
                {
                    "key": "test_project",
                    "name": "Test Project",
                },
            ],
            "globals": {
                "repositories": [
                    {
                        "key": "test_repo",
                        "remote_url": "https://source.com/repo",
                        "git_clone_strategy": "deploy_key",
                    },
                ],
            },
        }
        file_path = tmp_path / "simple_config.yml"
        with open(file_path, "w") as f:
            yaml.dump(config, f)
        return file_path
    
    def test_applies_repository_remote_url(self, simple_yaml: Path):
        """Test that repository remote_url is updated from target."""
        # Arrange
        adopt_data = [
            {
                "source_key": "test_repo",
                "source_type": "REP",
                "target_id": "123",
                "protected": False,
            }
        ]
        target_report_items = [
            {
                "element_type_code": "REP",
                "dbt_id": 123,
                "remote_url": "https://target.com/new-repo",
                "git_clone_strategy": "github_app",
            }
        ]
        
        # Act
        apply_adoption_overrides(str(simple_yaml), adopt_data, target_report_items)
        
        # Assert
        with open(simple_yaml, "r") as f:
            result = yaml.safe_load(f)
        
        repo = result["globals"]["repositories"][0]
        assert repo["remote_url"] == "https://target.com/new-repo"
        assert repo["git_clone_strategy"] == "github_app"
    
    def test_handles_missing_target_lookup(self, simple_yaml: Path):
        """Test graceful handling when target data is not found."""
        # Arrange - target_id 999 doesn't exist in target_report_items
        adopt_data = [
            {
                "source_key": "test_repo",
                "source_type": "REP",
                "target_id": "999",
            }
        ]
        target_report_items = [
            {
                "element_type_code": "REP",
                "dbt_id": 123,
                "remote_url": "https://other.com/repo",
            }
        ]
        
        # Read original
        with open(simple_yaml, "r") as f:
            original = yaml.safe_load(f)
        
        # Act - should not raise
        apply_adoption_overrides(str(simple_yaml), adopt_data, target_report_items)
        
        # Assert - should remain unchanged
        with open(simple_yaml, "r") as f:
            result = yaml.safe_load(f)
        
        assert result["globals"]["repositories"][0]["remote_url"] == original["globals"]["repositories"][0]["remote_url"]
    
    def test_preserves_non_adopted_resources(self, simple_yaml: Path):
        """Test that resources not in adopt_data are preserved."""
        # Arrange - adopt empty list
        adopt_data = []
        target_report_items = []
        
        # Read original
        with open(simple_yaml, "r") as f:
            original = yaml.safe_load(f)
        
        # Act
        apply_adoption_overrides(str(simple_yaml), adopt_data, target_report_items)
        
        # Assert - should be unchanged
        with open(simple_yaml, "r") as f:
            result = yaml.safe_load(f)
        
        assert result == original
    
    def test_handles_none_target_id(self, simple_yaml: Path):
        """Test that None target_id is skipped."""
        # Arrange
        adopt_data = [
            {
                "source_key": "test_repo",
                "source_type": "REP",
                "target_id": None,
            }
        ]
        target_report_items = []
        
        # Read original
        with open(simple_yaml, "r") as f:
            original = yaml.safe_load(f)
        
        # Act - should not raise
        apply_adoption_overrides(str(simple_yaml), adopt_data, target_report_items)
        
        # Assert - should be unchanged
        with open(simple_yaml, "r") as f:
            result = yaml.safe_load(f)
        
        assert result == original
    
    def test_handles_string_none_target_id(self, simple_yaml: Path):
        """Test that string "None" target_id is skipped."""
        # Arrange
        adopt_data = [
            {
                "source_key": "test_repo",
                "source_type": "REP",
                "target_id": "None",
            }
        ]
        target_report_items = []
        
        # Read original
        with open(simple_yaml, "r") as f:
            original = yaml.safe_load(f)
        
        # Act
        apply_adoption_overrides(str(simple_yaml), adopt_data, target_report_items)
        
        # Assert - should be unchanged
        with open(simple_yaml, "r") as f:
            result = yaml.safe_load(f)
        
        assert result == original
    
    def test_handles_legacy_dict_format(self, simple_yaml: Path):
        """Test handling of legacy dict adopt_data format."""
        # Arrange - legacy format with dict
        adopt_data = {
            "test_repo": {
                "action": "adopt",
                "target_id": "123",
                "source_type": "REP",
            }
        }
        target_report_items = [
            {
                "element_type_code": "REP",
                "dbt_id": 123,
                "remote_url": "https://target.com/repo",
            }
        ]
        
        # Act
        apply_adoption_overrides(str(simple_yaml), adopt_data, target_report_items)
        
        # Assert
        with open(simple_yaml, "r") as f:
            result = yaml.safe_load(f)
        
        # Note: Legacy format may or may not update depending on source_key matching
        # The important thing is it doesn't crash
        assert result is not None


# =============================================================================
# Tests: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_empty_yaml_file(self, tmp_path: Path):
        """Test handling of empty YAML file."""
        empty_file = tmp_path / "empty.yml"
        empty_file.write_text("")
        
        # Act - should not raise
        result = apply_unprotection_from_set(str(empty_file), {"PRJ:test"})
        
        # Assert
        assert result == str(empty_file)
    
    def test_yaml_with_only_projects(self, tmp_path: Path):
        """Test YAML with projects but no globals section."""
        config = {
            "projects": [
                {"key": "proj1", "name": "Project 1", "protected": True},
            ]
        }
        file_path = tmp_path / "projects_only.yml"
        with open(file_path, "w") as f:
            yaml.dump(config, f)
        
        # Act
        apply_unprotection_from_set(str(file_path), {"PRJ:proj1"})
        
        # Assert
        with open(file_path, "r") as f:
            result = yaml.safe_load(f)
        
        assert "protected" not in result["projects"][0]
    
    def test_yaml_with_only_globals(self, tmp_path: Path):
        """Test YAML with globals but no projects section."""
        config = {
            "globals": {
                "repositories": [
                    {"key": "repo1", "remote_url": "https://test.com", "protected": True},
                ]
            }
        }
        file_path = tmp_path / "globals_only.yml"
        with open(file_path, "w") as f:
            yaml.dump(config, f)
        
        # Act
        apply_unprotection_from_set(str(file_path), {"REP:repo1"})
        
        # Assert
        with open(file_path, "r") as f:
            result = yaml.safe_load(f)
        
        assert "protected" not in result["globals"]["repositories"][0]
    
    def test_output_to_different_path(self, yaml_file: Path, tmp_path: Path):
        """Test writing output to a different file."""
        output_path = tmp_path / "output.yml"
        
        # Act
        result_path = apply_unprotection_from_set(
            str(yaml_file), 
            {"PRJ:my_project"}, 
            output_path=str(output_path)
        )
        
        # Assert
        assert result_path == str(output_path)
        assert output_path.exists()
        
        with open(output_path, "r") as f:
            result = yaml.safe_load(f)
        
        my_project = next(p for p in result["projects"] if p["key"] == "my_project")
        assert "protected" not in my_project
    
    def test_special_characters_in_key(self, tmp_path: Path):
        """Test handling of special characters in resource keys."""
        config = {
            "projects": [
                {"key": "project-with-dashes", "name": "Dashed Project", "protected": True},
                {"key": "project_with_underscores", "name": "Underscored Project", "protected": True},
            ]
        }
        file_path = tmp_path / "special_chars.yml"
        with open(file_path, "w") as f:
            yaml.dump(config, f)
        
        # Act
        apply_unprotection_from_set(str(file_path), {"PRJ:project-with-dashes"})
        
        # Assert
        with open(file_path, "r") as f:
            result = yaml.safe_load(f)
        
        dashed = next(p for p in result["projects"] if p["key"] == "project-with-dashes")
        assert "protected" not in dashed


# =============================================================================
# Tests: merge_yaml_configs
# =============================================================================

class TestMergeYamlConfigs:
    """Tests for merge_yaml_configs function.
    
    This function is critical for deploy generate: it merges source-selected
    projects into an existing deployment YAML without destroying already-managed
    resources.
    """
    
    @pytest.fixture
    def base_yaml(self) -> Dict[str, Any]:
        """Base YAML representing existing deployment with 3 managed projects."""
        return {
            "version": 2,
            "account": {"id": 11, "name": "Target Account"},
            "projects": [
                {"key": "project_alpha", "name": "Project Alpha", "protected": True},
                {"key": "project_beta", "name": "Project Beta", "protected": False},
                {"key": "project_gamma", "name": "Project Gamma"},
            ],
            "globals": {
                "repositories": [
                    {"key": "repo_alpha", "remote_url": "https://github.com/alpha"},
                    {"key": "repo_beta", "remote_url": "https://github.com/beta"},
                ],
                "connections": [
                    {"key": "conn_snowflake", "type": "snowflake"},
                ],
            },
        }
    
    @pytest.fixture
    def source_yaml(self) -> Dict[str, Any]:
        """Source YAML representing newly selected project to add."""
        return {
            "version": 2,
            "projects": [
                {"key": "project_delta", "name": "Project Delta", "protected": False},
            ],
            "globals": {
                "repositories": [
                    {"key": "repo_delta", "remote_url": "https://github.com/delta"},
                ],
            },
        }
    
    def test_preserves_existing_projects(self, base_yaml, source_yaml):
        """Base has 3 projects, source has 1 new, result has 4."""
        result = merge_yaml_configs(base_yaml, source_yaml)
        
        assert len(result["projects"]) == 4
        keys = {p["key"] for p in result["projects"]}
        assert keys == {"project_alpha", "project_beta", "project_gamma", "project_delta"}
    
    def test_adds_new_projects_from_source(self, base_yaml, source_yaml):
        """New project key not in base gets added."""
        result = merge_yaml_configs(base_yaml, source_yaml)
        
        delta = next(p for p in result["projects"] if p["key"] == "project_delta")
        assert delta["name"] == "Project Delta"
    
    def test_updates_matched_projects(self, base_yaml):
        """Source project with same key updates base values."""
        source = {
            "projects": [
                {"key": "project_alpha", "name": "Alpha UPDATED", "protected": False},
            ],
        }
        result = merge_yaml_configs(base_yaml, source)
        
        alpha = next(p for p in result["projects"] if p["key"] == "project_alpha")
        assert alpha["name"] == "Alpha UPDATED"
        assert alpha["protected"] is False
        # Other projects preserved
        assert len(result["projects"]) == 3
    
    def test_preserves_globals_repositories(self, base_yaml, source_yaml):
        """globals.repositories from base preserved after merge."""
        result = merge_yaml_configs(base_yaml, source_yaml)
        
        repo_keys = {r["key"] for r in result["globals"]["repositories"]}
        assert "repo_alpha" in repo_keys
        assert "repo_beta" in repo_keys
        assert "repo_delta" in repo_keys
        assert len(result["globals"]["repositories"]) == 3
    
    def test_merges_globals_repositories(self, base_yaml, source_yaml):
        """New source repo added, existing preserved."""
        result = merge_yaml_configs(base_yaml, source_yaml)
        
        delta_repo = next(
            r for r in result["globals"]["repositories"] if r["key"] == "repo_delta"
        )
        assert delta_repo["remote_url"] == "https://github.com/delta"
    
    def test_preserves_globals_connections(self, base_yaml, source_yaml):
        """globals.connections from base preserved (source has no connections)."""
        result = merge_yaml_configs(base_yaml, source_yaml)
        
        assert "connections" in result["globals"]
        assert len(result["globals"]["connections"]) == 1
        assert result["globals"]["connections"][0]["key"] == "conn_snowflake"
    
    def test_fresh_migration_uses_source_as_is(self, source_yaml):
        """Empty/None base returns source unchanged."""
        result = merge_yaml_configs(None, source_yaml)
        assert result == source_yaml
        
        result2 = merge_yaml_configs({}, source_yaml)
        assert result2 == source_yaml
    
    def test_empty_source_returns_base(self, base_yaml):
        """Empty/None source returns base unchanged."""
        result = merge_yaml_configs(base_yaml, None)
        assert result == base_yaml
        
        result2 = merge_yaml_configs(base_yaml, {})
        assert result2 == base_yaml
    
    def test_preserves_top_level_fields(self, base_yaml, source_yaml):
        """version, account, etc. from base preserved."""
        result = merge_yaml_configs(base_yaml, source_yaml)
        
        assert result["version"] == 2
        assert result["account"] == {"id": 11, "name": "Target Account"}
    
    def test_both_empty_returns_empty(self):
        """Both empty inputs returns empty dict."""
        assert merge_yaml_configs(None, None) == {}
        assert merge_yaml_configs({}, {}) == {}
        assert merge_yaml_configs(None, {}) == {}
        assert merge_yaml_configs({}, None) == {}
    
    def test_merge_with_protection_flags(self, base_yaml):
        """Protected: true/false flags preserved correctly during merge."""
        source = {
            "projects": [
                {"key": "project_new", "name": "New Project", "protected": True},
            ],
        }
        result = merge_yaml_configs(base_yaml, source)
        
        # Existing protected project preserved
        alpha = next(p for p in result["projects"] if p["key"] == "project_alpha")
        assert alpha["protected"] is True
        
        # Existing unprotected project preserved
        beta = next(p for p in result["projects"] if p["key"] == "project_beta")
        assert beta["protected"] is False
        
        # New protected project added
        new_proj = next(p for p in result["projects"] if p["key"] == "project_new")
        assert new_proj["protected"] is True
    
    def test_does_not_mutate_inputs(self, base_yaml, source_yaml):
        """Merge should not modify the input dicts."""
        import copy
        base_copy = copy.deepcopy(base_yaml)
        source_copy = copy.deepcopy(source_yaml)
        
        merge_yaml_configs(base_yaml, source_yaml)
        
        assert base_yaml == base_copy
        assert source_yaml == source_copy
