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
                        "id": 600,
                        "project_default": "default_value",
                        "environment_values": {"production": "prod_value"},
                        "element_mapping_id": "VAR_001",
                        "include_in_conversion": True,
                    }
                ],
                "extended_attributes": [
                    {
                        "key": "ext_attrs_1",
                        "id": 700,
                        "extended_attributes": {
                            "connection_parameters": {"_retry_stop_after_attempts_count": 30}
                        },
                        "state": 1,
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


def test_normalization_preserves_account_host_url(minimal_snapshot_dict, default_mapping_config):
    """Target/account host should flow into normalized YAML when provided."""
    minimal_snapshot_dict["host_url"] = "https://do446.eu1.dbt.com"

    snapshot = AccountSnapshot(**minimal_snapshot_dict)
    context = NormalizationContext(default_mapping_config)

    result = normalize_snapshot(snapshot, default_mapping_config, context)

    assert result["account"]["host_url"] == "https://do446.eu1.dbt.com"


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
    assert result["globals"]["repositories"][0]["key"] == "analytics"
    
    # Check projects
    assert len(result["projects"]) == 1
    project = result["projects"][0]
    assert project["name"] == "Analytics"
    assert project["repository"] == "analytics"  # Resolved reference key
    
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


def test_profile_normalization_uses_primary_profile_key(full_snapshot_dict, default_mapping_config):
    """Deployment environments that reference profiles emit profiles + primary_profile_key."""
    snapshot_dict = json.loads(json.dumps(full_snapshot_dict))
    project = snapshot_dict["projects"][0]
    project["profiles"] = [
        {
            "key": "prod_profile",
            "id": 900,
            "connection_key": "snowflake_prod",
            "connection_id": 100,
            "credentials_key": "production",
            "credentials_id": 901,
            "credential": {
                "id": 901,
                "credential_type": "snowflake",
                "schema": "analytics",
                "user": "dbt_user",
                "auth_type": "password",
                "num_threads": 4,
            },
            "extended_attributes_key": "ext_attrs_1",
            "extended_attributes_id": 700,
            "element_mapping_id": "PRF_001",
            "include_in_conversion": True,
        }
    ]
    project["environments"][0]["primary_profile_id"] = 900

    snapshot = AccountSnapshot(**snapshot_dict)
    context = NormalizationContext(default_mapping_config)

    result = normalize_snapshot(snapshot, default_mapping_config, context)

    normalized_project = result["projects"][0]
    assert normalized_project["profiles"] == [
        {
            "key": "prod_profile",
            "connection_key": "snowflake_prod",
            "credentials_key": "production",
            "credential": {
                "schema": "analytics",
                "credential_type": "snowflake",
                "user": "dbt_user",
                "auth_type": "password",
                "num_threads": 4,
            },
            "extended_attributes_key": "ext_attrs_1",
        }
    ]
    assert normalized_project["environments"][0]["primary_profile_key"] == "prod_profile"


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
    
    # Check collision tracking - both keys should be tracked in the connections namespace
    assert "connections" in context.collisions
    assert "prod_connection" in context.collisions["connections"]


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
    assert result["projects"][0]["id"] == 300
    assert result["projects"][0]["environments"][0]["id"] == 400
    assert result["projects"][0]["jobs"][0]["id"] == 500
    assert result["projects"][0]["environment_variables"][0]["id"] == 600
    assert result["projects"][0]["extended_attributes"][0]["id"] == 700


def test_bigquery_connection_maps_private_key_id_from_details_config(default_mapping_config):
    """BigQuery private_key_id should map from details.config into provider_config."""
    snapshot_dict = {
        "account_id": 12345,
        "account_name": "Test Account",
        "globals": {
            "connections": {
                "bigquery_sthibeault": {
                    "key": "bigquery_sthibeault",
                    "id": 238776,
                    "name": "BigQuery - sthibeault",
                    "type": "bigquery",
                    "details": {
                        "adapter_version": "bigquery_v1",
                        "config": {
                            "project_id": "ps-sthibeault-fusion-dev",
                            "deployment_env_auth_type": "service-account-json",
                            "private_key_id": "8efdff6229f48bfc1047e7259e8d0d968ef55a78",
                            "private_key": "**********",
                            "client_email": "dbt-service@ps-sthibeault-fusion-dev.iam.gserviceaccount.com",
                            "client_id": "110206344724199657711",
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/dbt-service%40ps-sthibeault-fusion-dev.iam.gserviceaccount.com",
                        },
                    },
                    "include_in_conversion": True,
                }
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

    connection = result["globals"]["connections"][0]
    provider_config = connection.get("provider_config", {})
    assert provider_config["gcp_project_id"] == "ps-sthibeault-fusion-dev"
    assert provider_config["deployment_env_auth_type"] == "service-account-json"
    assert provider_config["private_key_id"] == "8efdff6229f48bfc1047e7259e8d0d968ef55a78"
    # private_key is sensitive/masked and should not be propagated into provider_config
    assert "private_key" not in provider_config


def test_adapter_connection_maps_field_values_and_normalizes_type(default_mapping_config):
    """Adapter connections should infer provider type from connection_details.fields."""
    snapshot_dict = {
        "account_id": 12345,
        "account_name": "Test Account",
        "globals": {
            "connections": {
                "connection_203604": {
                    "key": "connection_203604",
                    "id": 203604,
                    "name": "Databricks",
                    "type": "adapter",
                    "details": {
                        "connection_details": {
                            "fields": {
                                "type": {"value": "databricks"},
                                "host": {"value": "dbc-88636ef1-59c4.cloud.databricks.com"},
                                "http_path": {"value": "/sql/1.0/warehouses/b633a121c93855a0"},
                                "catalog": {"value": ""},
                            }
                        }
                    },
                    "include_in_conversion": True,
                }
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

    connection = result["globals"]["connections"][0]
    assert connection["type"] == "databricks"
    provider_config = connection.get("provider_config", {})
    assert provider_config["host"] == "dbc-88636ef1-59c4.cloud.databricks.com"
    assert provider_config["http_path"] == "/sql/1.0/warehouses/b633a121c93855a0"
    assert "catalog" not in provider_config


def test_bigquery_mapped_private_key_id_wins_over_module_dummy(default_mapping_config):
    """When source provides private_key_id, normalized output should preserve it.

    Terraform module fallback should only apply when this field is absent.
    """
    source_private_key_id = "8efdff6229f48bfc1047e7259e8d0d968ef55a78"
    module_dummy_private_key_id = "0000000000000000000000000000000000000000"

    snapshot_dict = {
        "account_id": 12345,
        "account_name": "Test Account",
        "globals": {
            "connections": {
                "bigquery_with_id": {
                    "key": "bigquery_with_id",
                    "id": 238776,
                    "name": "BigQuery - with id",
                    "type": "bigquery",
                    "details": {
                        "config": {
                            "project_id": "ps-sthibeault-fusion-dev",
                            "deployment_env_auth_type": "service-account-json",
                            "private_key_id": source_private_key_id,
                        },
                    },
                    "include_in_conversion": True,
                }
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

    provider_config = result["globals"]["connections"][0].get("provider_config", {})
    assert provider_config["private_key_id"] == source_private_key_id
    assert provider_config["private_key_id"] != module_dummy_private_key_id


def test_bigquery_private_key_id_backfilled_from_details_config_when_include_related_omits_it(
    default_mapping_config,
):
    """Merge connection_details.config and details.config for provider_config mapping.

    Some API responses include BigQuery private_key_id only in details.config.
    """
    snapshot_dict = {
        "account_id": 12345,
        "account_name": "Test Account",
        "globals": {
            "connections": {
                "bigquery_sthibeault": {
                    "key": "bigquery_sthibeault",
                    "id": 238776,
                    "name": "BigQuery - sthibeault",
                    "type": "bigquery",
                    "details": {
                        # include_related payload: missing private_key_id
                        "connection_details": {
                            "config": {
                                "project_id": "ps-sthibeault-fusion-dev",
                                "deployment_env_auth_type": "service-account-json",
                                "client_email": "dbt-service@ps-sthibeault-fusion-dev.iam.gserviceaccount.com",
                                "client_id": "110206344724199657711",
                            }
                        },
                        # top-level details payload: contains private_key_id
                        "config": {
                            "project_id": "ps-sthibeault-fusion-dev",
                            "deployment_env_auth_type": "service-account-json",
                            "private_key_id": "8efdff6229f48bfc1047e7259e8d0d968ef55a78",
                            "client_email": "dbt-service@ps-sthibeault-fusion-dev.iam.gserviceaccount.com",
                            "client_id": "110206344724199657711",
                        },
                    },
                    "include_in_conversion": True,
                }
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

    provider_config = result["globals"]["connections"][0].get("provider_config", {})
    assert provider_config["gcp_project_id"] == "ps-sthibeault-fusion-dev"
    assert provider_config["private_key_id"] == "8efdff6229f48bfc1047e7259e8d0d968ef55a78"


def test_group_permissions_are_deduplicated(default_mapping_config):
    """Duplicate group permissions should be collapsed to avoid TF set collisions."""
    snapshot_dict = {
        "account_id": 12345,
        "account_name": "Test Account",
        "globals": {
            "connections": {},
            "repositories": {},
            "service_tokens": {},
            "groups": {
                "owner": {
                    "key": "owner",
                    "id": 11851,
                    "name": "Owner",
                    "assign_by_default": False,
                    "sso_mapping_groups": [],
                    "metadata": {
                        "group_permissions": [
                            {
                                "permission_set": "owner",
                                "project_id": None,
                                "writable_environment_categories": [],
                            },
                            {
                                "permission_set": "owner",
                                "project_id": None,
                                "writable_environment_categories": [],
                            },
                        ]
                    },
                    "include_in_conversion": True,
                }
            },
            "notifications": {},
            "webhooks": {},
            "privatelink_endpoints": {},
        },
        "projects": [],
    }

    snapshot = AccountSnapshot(**snapshot_dict)
    context = NormalizationContext(default_mapping_config)
    result = normalize_snapshot(snapshot, default_mapping_config, context)

    owner_group = result["globals"]["groups"][0]
    permissions = owner_group.get("group_permissions", [])
    assert len(permissions) == 1
    assert permissions[0]["permission_set"] == "owner"
    assert permissions[0]["all_projects"] is True
    assert permissions[0]["project_id"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

