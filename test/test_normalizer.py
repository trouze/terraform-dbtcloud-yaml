"""Unit tests for Phase 2 normalizer."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from importer.models import AccountSnapshot
from importer.normalizer import MappingConfig, NormalizationContext
from importer.normalizer.core import normalize_snapshot
from importer.normalizer.writer import YAMLWriter


# Test fixtures
@pytest.fixture
def minimal_snapshot_dict():
    """Minimal account snapshot for testing."""
    return {
        "account_id": 12345,
        "account_name": "Test Account",
        "globals": {
            "connections": {},
            "repositories": {},
            "service_tokens": {},
            "groups": {},
            "notifications": {},
            "webhooks": {},
            "privatelink_endpoints": {},
        },
        "projects": [],
    }


@pytest.fixture
def full_snapshot_dict():
    """Full account snapshot with all resource types."""
    return {
        "account_id": 12345,
        "account_name": "Test Account",
        "globals": {
            "connections": {
                "snowflake_prod": {
                    "key": "snowflake_prod",
                    "id": 100,
                    "name": "Snowflake Production",
                    "type": "snowflake",
                    "details": {"account": "test_account"},
                    "element_mapping_id": "CON_001",
                    "include_in_conversion": True,
                }
            },
            "repositories": {
                "jaffle_shop": {
                    "key": "jaffle_shop",
                    "id": 200,
                    "remote_url": "https://github.com/dbt-labs/jaffle_shop",
                    "git_clone_strategy": "deploy_key",
                    "metadata": {},
                    "element_mapping_id": "REP_001",
                    "include_in_conversion": True,
                }
            },
            "service_tokens": {},
            "groups": {},
            "notifications": {},
            "webhooks": {},
            "privatelink_endpoints": {},
        },
        "projects": [
            {
                "key": "analytics",
                "id": 300,
                "name": "Analytics",
                "repository_key": "jaffle_shop",
                "environments": [
                    {
                        "key": "production",
                        "id": 400,
                        "name": "Production",
                        "type": "deployment",
                        "connection_key": "snowflake_prod",
                        "credential": {
                            "token_name": "prod_token",
                            "schema": "analytics_prod",
                            "element_mapping_id": "CRE_001",
                        },
                        "dbt_version": "1.6.0",
                        "element_mapping_id": "ENV_001",
                        "include_in_conversion": True,
                    }
                ],
                "jobs": [
                    {
                        "key": "daily_build",
                        "id": 500,
                        "name": "Daily Build",
                        "environment_key": "production",
                        "execute_steps": ["dbt build"],
                        "triggers": {
                            "schedule": True,
                            "github_webhook": False,
                            "git_provider_webhook": False,
                            "on_merge": False,
                        },
                        "settings": {"schedule_type": "every_day"},
                        "element_mapping_id": "JOB_001",
                        "include_in_conversion": True,
                    }
                ],
                "environment_variables": [
                    {
                        "name": "DBT_ENV_VAR_TEST",
                        "project_default": "default_value",
                        "environment_values": {"production": "prod_value"},
                        "element_mapping_id": "VAR_001",
                        "include_in_conversion": True,
                    }
                ],
                "metadata": {},
                "element_mapping_id": "PRJ_001",
                "include_in_conversion": True,
            }
        ],
    }


@pytest.fixture
def default_mapping_config():
    """Default mapping configuration."""
    return MappingConfig(
        version=1,
        scope={"mode": "all_projects"},
        resource_filters={},
        normalization_options={
            "strip_source_ids": True,
            "placeholder_strategy": "lookup",
            "name_collision_strategy": "suffix",
            "secret_handling": "redact",
            "multi_project_mode": "single_file",
            "include_inactive": False,
        },
        output={
            "yaml_file": "dbt-config.yml",
            "output_directory": "normalized/",
            "generate_manifests": {
                "lookups": True,
                "exclusions": True,
                "diff_json": True,
            },
        },
    )


# Test cases
def test_minimal_normalization(minimal_snapshot_dict, default_mapping_config):
    """Test normalizing a minimal snapshot."""
    snapshot = AccountSnapshot(**minimal_snapshot_dict)
    context = NormalizationContext(default_mapping_config)
    
    result = normalize_snapshot(snapshot, default_mapping_config, context)
    
    assert result["version"] == 2
    assert result["account"]["name"] == "Test Account"
    assert "id" not in result["account"]  # Stripped by default
    assert result["projects"] == []


def test_full_normalization_with_all_resources(full_snapshot_dict, default_mapping_config):
    """Test normalizing a full snapshot with all resource types."""
    snapshot = AccountSnapshot(**full_snapshot_dict)
    context = NormalizationContext(default_mapping_config)
    
    result = normalize_snapshot(snapshot, default_mapping_config, context)
    
    # Check structure
    assert result["version"] == 2
    assert "account" in result
    assert "globals" in result
    assert "projects" in result
    
    # Check globals
    assert len(result["globals"]["connections"]) == 1
    assert result["globals"]["connections"][0]["key"] == "snowflake_prod"
    assert "id" not in result["globals"]["connections"][0]  # Stripped
    
    assert len(result["globals"]["repositories"]) == 1
    assert result["globals"]["repositories"][0]["key"] == "jaffle_shop"
    
    # Check projects
    assert len(result["projects"]) == 1
    project = result["projects"][0]
    assert project["name"] == "Analytics"
    assert project["repository"] == "jaffle_shop"  # Resolved reference
    
    # Check environments
    assert len(project["environments"]) == 1
    env = project["environments"][0]
    assert env["name"] == "Production"
    assert env["connection"] == "snowflake_prod"  # Resolved reference
    assert env["credential"]["token_name"] == "prod_token"
    
    # Check jobs
    assert len(project["jobs"]) == 1
    job = project["jobs"][0]
    assert job["name"] == "Daily Build"
    assert job["environment_key"] == "production"
    assert job["execute_steps"] == ["dbt build"]
    
    # Check environment variables
    assert len(project["environment_variables"]) == 1
    var = project["environment_variables"][0]
    assert var["name"] == "DBT_ENV_VAR_TEST"
    assert var["environment_values"]["production"] == "prod_value"


def test_scope_filtering_specific_projects(full_snapshot_dict):
    """Test scope filtering to include only specific projects."""
    config = MappingConfig(
        version=1,
        scope={"mode": "specific_projects", "project_keys": ["other_project"]},
        resource_filters={},
        normalization_options={"strip_source_ids": True},
        output={},
    )
    
    snapshot = AccountSnapshot(**full_snapshot_dict)
    context = NormalizationContext(config)
    
    result = normalize_snapshot(snapshot, config, context)
    
    # Analytics project should be excluded
    assert len(result["projects"]) == 0
    assert len(context.exclusions) > 0
    assert any(e["resource_type"] == "project" for e in context.exclusions)


def test_scope_filtering_account_level_only(full_snapshot_dict):
    """Test scope filtering to include only account-level globals."""
    config = MappingConfig(
        version=1,
        scope={"mode": "account_level_only"},
        resource_filters={},
        normalization_options={"strip_source_ids": True},
        output={},
    )
    
    snapshot = AccountSnapshot(**full_snapshot_dict)
    context = NormalizationContext(config)
    
    result = normalize_snapshot(snapshot, config, context)
    
    # No projects should be included
    assert len(result["projects"]) == 0
    # But globals should still be present
    assert len(result["globals"]["connections"]) == 1
    assert len(result["globals"]["repositories"]) == 1


def test_resource_exclusion_by_key(full_snapshot_dict):
    """Test excluding specific resources by key."""
    config = MappingConfig(
        version=1,
        scope={"mode": "all_projects"},
        resource_filters={
            "connections": {"include": True, "exclude_keys": ["snowflake_prod"]},
            "jobs": {"include": True, "exclude_keys": ["daily_build"]},
        },
        normalization_options={"strip_source_ids": True},
        output={},
    )
    
    snapshot = AccountSnapshot(**full_snapshot_dict)
    context = NormalizationContext(config)
    
    result = normalize_snapshot(snapshot, config, context)
    
    # Connection should be excluded
    assert len(result["globals"]["connections"]) == 0
    
    # Job should be excluded
    project = result["projects"][0]
    assert len(project["jobs"]) == 0
    
    # Check exclusions were logged
    assert any(e["key"] == "snowflake_prod" for e in context.exclusions)
    assert any(e["key"] == "daily_build" for e in context.exclusions)


def test_resource_exclusion_by_type(full_snapshot_dict):
    """Test excluding entire resource types."""
    config = MappingConfig(
        version=1,
        scope={"mode": "all_projects"},
        resource_filters={
            "jobs": {"include": False},
            "environment_variables": {"include": False},
        },
        normalization_options={"strip_source_ids": True},
        output={},
    )
    
    snapshot = AccountSnapshot(**full_snapshot_dict)
    context = NormalizationContext(config)
    
    result = normalize_snapshot(snapshot, config, context)
    
    project = result["projects"][0]
    
    # Jobs should be excluded entirely
    assert len(project.get("jobs", [])) == 0
    
    # Environment variables should be excluded
    assert len(project.get("environment_variables", [])) == 0


def test_name_collision_handling(default_mapping_config):
    """Test handling of duplicate keys (name collisions)."""
    snapshot_dict = {
        "account_id": 12345,
        "account_name": "Test Account",
        "globals": {
            "connections": {
                "prod_connection": {
                    "key": "prod_connection",
                    "id": 100,
                    "name": "Prod Connection",
                    "type": "snowflake",
                    "details": {},
                    "element_mapping_id": "CON_001",
                    "include_in_conversion": True,
                },
                "prod_connection_2": {  # Collision!
                    "key": "prod_connection",  # Same key
                    "id": 101,
                    "name": "Prod-Connection",
                    "type": "snowflake",
                    "details": {},
                    "element_mapping_id": "CON_002",
                    "include_in_conversion": True,
                },
            },
            "repositories": {},
            "service_tokens": {},
            "groups": {},
            "notifications": {},
            "webhooks": {},
            "privatelink_endpoints": {},
        },
        "projects": [],
    }
    
    snapshot = AccountSnapshot(**snapshot_dict)
    context = NormalizationContext(default_mapping_config)
    
    result = normalize_snapshot(snapshot, default_mapping_config, context)
    
    # First connection should keep original key
    assert result["globals"]["connections"][0]["key"] == "prod_connection"
    # Second should get suffix
    assert result["globals"]["connections"][1]["key"] == "prod_connection_2"
    
    # Check collision was logged
    assert "prod_connection" in context.collisions


def test_secret_handling_redacted(full_snapshot_dict):
    """Test that secrets are redacted by default."""
    # Add a secret variable
    full_snapshot_dict["projects"][0]["environment_variables"].append({
        "name": "DBT_ENV_SECRET_API_KEY",
        "project_default": "secret_value",
        "environment_values": {"production": "prod_secret"},
        "element_mapping_id": "VAR_002",
        "include_in_conversion": True,
    })
    
    config = MappingConfig(
        version=1,
        scope={"mode": "all_projects"},
        resource_filters={},
        normalization_options={"secret_handling": "redact"},
        output={},
    )
    
    snapshot = AccountSnapshot(**full_snapshot_dict)
    context = NormalizationContext(config)
    
    result = normalize_snapshot(snapshot, config, context)
    
    project = result["projects"][0]
    secret_var = next(v for v in project["environment_variables"] if v["name"] == "DBT_ENV_SECRET_API_KEY")
    
    # Secret should be redacted
    assert secret_var["environment_values"]["production"] == "REDACTED"


def test_yaml_writer_creates_all_artifacts(full_snapshot_dict, default_mapping_config):
    """Test that YAML writer creates all expected artifact files."""
    snapshot = AccountSnapshot(**full_snapshot_dict)
    context = NormalizationContext(default_mapping_config)
    
    normalized_data = normalize_snapshot(snapshot, default_mapping_config, context)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        writer = YAMLWriter(default_mapping_config, context)
        
        artifacts = writer.write_all_artifacts(
            normalized_data,
            output_dir,
            run_id=1,
            timestamp="20251121_120000",
            account_id=12345,
        )
        
        # Check all artifacts were created
        assert "yaml" in artifacts
        assert artifacts["yaml"].exists()
        
        assert "lookups" in artifacts
        assert artifacts["lookups"].exists()
        
        assert "exclusions" in artifacts
        assert artifacts["exclusions"].exists()
        
        assert "diff_json" in artifacts
        assert artifacts["diff_json"].exists()
        
        # Verify YAML is valid
        with open(artifacts["yaml"], "r") as f:
            yaml_content = yaml.safe_load(f)
            assert yaml_content["version"] == 2
        
        # Verify lookups manifest is valid JSON
        with open(artifacts["lookups"], "r") as f:
            lookups_content = json.load(f)
            assert "_metadata" in lookups_content
            assert "placeholders" in lookups_content


def test_preserve_source_ids_option(full_snapshot_dict):
    """Test that source IDs are preserved when option is enabled."""
    config = MappingConfig(
        version=1,
        scope={"mode": "all_projects"},
        resource_filters={},
        normalization_options={"strip_source_ids": False},
        output={},
    )
    
    snapshot = AccountSnapshot(**full_snapshot_dict)
    context = NormalizationContext(config)
    
    result = normalize_snapshot(snapshot, config, context)
    
    # IDs should be preserved
    assert result["account"]["id"] == 12345
    assert result["globals"]["connections"][0]["id"] == 100
    assert result["globals"]["repositories"][0]["id"] == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

