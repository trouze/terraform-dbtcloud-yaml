"""Tests for environment credentials functionality.

Tests cover:
1. Credential schemas (from Terraform provider alignment)
2. Environment credential state management
3. Env var persistence (read/write to .env)
4. Dummy credentials behavior
5. UI workflow integration
"""

import pytest
import tempfile
from pathlib import Path

from importer.web.state import (
    AppState,
    WorkflowStep,
    WorkflowType,
    EnvironmentCredentialConfig,
    EnvironmentCredentialsState,
    STEP_NAMES,
    STEP_ICONS,
    WORKFLOW_STEPS,
)
from importer.web.components.credential_schemas import (
    CREDENTIAL_SCHEMAS,
    CONNECTION_TYPE_TO_CREDENTIAL,
    get_credential_schema,
    get_credential_type_for_connection,
    get_dummy_credentials,
    get_required_fields,
    get_all_fields,
    get_sensitive_fields,
    should_show_field,
    get_supported_credential_types,
)
from importer.web.env_manager import (
    load_env_credential_configs,
    load_env_credential_config,
    save_env_credential_config,
    save_all_env_credential_configs,
    clear_env_credential_config,
)


class TestCredentialSchemas:
    """Test credential schema definitions aligned with Terraform provider."""

    def test_all_major_warehouse_types_covered(self):
        """Verify all major warehouse types have credential schemas."""
        required_types = [
            "snowflake",
            "databricks",
            "bigquery",
            "redshift",
            "postgres",
            "athena",
            "fabric",
            "synapse",
            "starburst",
            "spark",
            "teradata",
        ]

        for wh_type in required_types:
            assert wh_type in CREDENTIAL_SCHEMAS, f"Missing schema for {wh_type}"

    def test_schema_has_required_fields(self):
        """Each schema must have required, optional, sensitive, descriptions."""
        for cred_type, schema in CREDENTIAL_SCHEMAS.items():
            assert "required" in schema, f"{cred_type} missing 'required'"
            assert "optional" in schema, f"{cred_type} missing 'optional'"
            assert "sensitive" in schema, f"{cred_type} missing 'sensitive'"
            assert "descriptions" in schema, f"{cred_type} missing 'descriptions'"
            assert "dummy_values" in schema, f"{cred_type} missing 'dummy_values'"

    def test_snowflake_schema_matches_provider(self):
        """Snowflake credential schema matches terraform provider."""
        schema = CREDENTIAL_SCHEMAS["snowflake"]

        # From provider: auth_type and num_threads are required
        assert "auth_type" in schema["required"]
        assert "num_threads" in schema["required"]

        # Optional includes user, password, private_key, etc.
        assert "user" in schema["optional"]
        assert "password" in schema["optional"]
        assert "private_key" in schema["optional"]

        # Sensitive fields
        assert "password" in schema["sensitive"]
        assert "private_key" in schema["sensitive"]
        assert "private_key_passphrase" in schema["sensitive"]

        # Auth modes
        assert "auth_modes" in schema
        assert schema["auth_modes"]["options"] == ["password", "keypair"]

    def test_databricks_schema_matches_provider(self):
        """Databricks credential schema matches terraform provider."""
        schema = CREDENTIAL_SCHEMAS["databricks"]

        # From provider: token is required
        assert "token" in schema["required"]
        assert "token" in schema["sensitive"]

    def test_bigquery_schema_matches_provider(self):
        """BigQuery credential schema matches terraform provider."""
        schema = CREDENTIAL_SCHEMAS["bigquery"]

        # From provider: dataset and num_threads are required
        assert "dataset" in schema["required"]
        assert "num_threads" in schema["required"]

    def test_athena_schema_matches_provider(self):
        """Athena credential schema matches terraform provider."""
        schema = CREDENTIAL_SCHEMAS["athena"]

        # From provider: aws credentials are required
        assert "aws_access_key_id" in schema["required"]
        assert "aws_secret_access_key" in schema["required"]
        assert "schema" in schema["required"]

        # AWS credentials are sensitive
        assert "aws_access_key_id" in schema["sensitive"]
        assert "aws_secret_access_key" in schema["sensitive"]

    def test_fabric_has_dual_auth_modes(self):
        """Fabric supports both user/pass and service principal auth."""
        schema = CREDENTIAL_SCHEMAS["fabric"]

        # Should have conditional fields
        assert "conditional" in schema

        # user/password vs tenant_id/client_id/client_secret
        assert "user" in schema["optional"]
        assert "password" in schema["optional"]
        assert "tenant_id" in schema["optional"]
        assert "client_id" in schema["optional"]
        assert "client_secret" in schema["optional"]

    def test_synapse_has_three_auth_modes(self):
        """Synapse supports SQL, AD Password, and Service Principal auth."""
        schema = CREDENTIAL_SCHEMAS["synapse"]

        assert "auth_modes" in schema
        assert "SQL" in schema["auth_modes"]["options"]
        assert "ActiveDirectoryPassword" in schema["auth_modes"]["options"]
        assert "ServicePrincipal" in schema["auth_modes"]["options"]


class TestCredentialSchemaHelpers:
    """Test credential schema helper functions."""

    def test_get_credential_schema_direct_match(self):
        """Direct lookup returns correct schema."""
        schema = get_credential_schema("snowflake")
        assert schema is not None
        assert "auth_type" in schema["required"]

    def test_get_credential_schema_fuzzy_match(self):
        """Fuzzy matching works for adapter variants."""
        # bigquery_v0, bigquery_v1 should all resolve to bigquery
        schema = get_credential_schema("bigquery_v0")
        assert schema is not None
        assert "dataset" in schema["required"]

    def test_get_credential_type_for_connection(self):
        """Connection type maps to credential type."""
        assert get_credential_type_for_connection("snowflake") == "snowflake"
        assert get_credential_type_for_connection("databricks") == "databricks"
        assert get_credential_type_for_connection("bigquery_v1") == "bigquery"
        assert get_credential_type_for_connection("trino") == "starburst"

    def test_get_dummy_credentials(self):
        """Dummy credentials contain required fields."""
        dummy = get_dummy_credentials("snowflake")
        assert "auth_type" in dummy
        assert "schema" in dummy
        assert "user" in dummy
        assert "num_threads" in dummy

    def test_get_required_fields(self):
        """Required fields extracted correctly."""
        required = get_required_fields("snowflake")
        assert "auth_type" in required
        assert "num_threads" in required

    def test_get_all_fields(self):
        """All fields includes required and optional."""
        all_fields = get_all_fields("snowflake")
        assert "auth_type" in all_fields  # Required
        assert "user" in all_fields  # Optional

    def test_get_sensitive_fields(self):
        """Sensitive fields extracted correctly."""
        sensitive = get_sensitive_fields("snowflake")
        assert "password" in sensitive
        assert "private_key" in sensitive

    def test_should_show_field_non_conditional(self):
        """Non-conditional fields always show."""
        # num_threads is not conditional
        assert should_show_field("snowflake", "num_threads", {}) is True

    def test_should_show_field_conditional_true(self):
        """Conditional field shows when condition met."""
        # password shows when auth_type is "password"
        assert should_show_field("snowflake", "password", {"auth_type": "password"}) is True

    def test_should_show_field_conditional_false(self):
        """Conditional field hides when condition not met."""
        # password hides when auth_type is "keypair"
        assert should_show_field("snowflake", "password", {"auth_type": "keypair"}) is False

    def test_get_supported_credential_types(self):
        """Returns all supported credential types."""
        types = get_supported_credential_types()
        assert "snowflake" in types
        assert "databricks" in types
        assert len(types) >= 10  # At least 10 major warehouse types


class TestEnvironmentCredentialConfig:
    """Test EnvironmentCredentialConfig dataclass."""

    def test_create_config(self):
        """Create a credential config with basic fields."""
        config = EnvironmentCredentialConfig(
            env_id="123",
            env_name="Production",
            project_id="456",
            project_name="MyProject",
            connection_type="snowflake",
            credential_type="snowflake",
        )

        assert config.env_id == "123"
        assert config.env_name == "Production"
        assert config.use_dummy_credentials is False
        assert config.is_saved is False

    def test_set_use_dummy_backs_up_values(self):
        """Toggling to dummy backs up real values."""
        config = EnvironmentCredentialConfig(
            env_id="123",
            env_name="Test",
            credential_type="snowflake",
            credential_values={"user": "real_user", "password": "real_pass"},
        )

        config.set_use_dummy(True)

        assert config.use_dummy_credentials is True
        assert config.credential_values == {}  # Cleared
        assert config._real_values_backup == {"user": "real_user", "password": "real_pass"}

    def test_set_use_dummy_restores_values(self):
        """Toggling back from dummy restores real values."""
        config = EnvironmentCredentialConfig(
            env_id="123",
            env_name="Test",
            credential_type="snowflake",
            credential_values={"user": "real_user", "password": "real_pass"},
        )

        config.set_use_dummy(True)
        config.set_use_dummy(False)

        assert config.use_dummy_credentials is False
        assert config.credential_values == {"user": "real_user", "password": "real_pass"}

    def test_to_dict_round_trip(self):
        """Config survives to_dict/from_dict cycle."""
        config = EnvironmentCredentialConfig(
            env_id="123",
            env_name="Production",
            project_id="456",
            project_name="MyProject",
            connection_type="snowflake",
            credential_type="snowflake",
            credential_values={"user": "test_user"},
            use_dummy_credentials=True,
            is_saved=True,
        )

        data = config.to_dict()
        restored = EnvironmentCredentialConfig.from_dict(data)

        assert restored.env_id == config.env_id
        assert restored.env_name == config.env_name
        assert restored.credential_type == config.credential_type
        assert restored.use_dummy_credentials == config.use_dummy_credentials
        assert restored.is_saved == config.is_saved


class TestEnvironmentCredentialsState:
    """Test EnvironmentCredentialsState dataclass."""

    def test_create_state(self):
        """Create empty credentials state."""
        state = EnvironmentCredentialsState()

        assert state.env_configs == {}
        assert state.step_complete is False
        assert state.selected_env_ids == set()

    def test_set_and_get_config(self):
        """Set and retrieve environment config."""
        state = EnvironmentCredentialsState()

        config = EnvironmentCredentialConfig(
            env_id="123",
            env_name="Production",
            credential_type="snowflake",
        )

        state.set_config(config)
        retrieved = state.get_config("123")

        assert retrieved is not None
        assert retrieved.env_name == "Production"

    def test_has_selected_environments(self):
        """Check if environments are selected."""
        state = EnvironmentCredentialsState()
        assert state.has_selected_environments() is False

        state.selected_env_ids.add("123")
        assert state.has_selected_environments() is True

    def test_all_saved_empty(self):
        """No environments = all saved."""
        state = EnvironmentCredentialsState()
        assert state.all_saved() is True

    def test_all_saved_with_configs(self):
        """Check all configs are saved."""
        state = EnvironmentCredentialsState()
        state.selected_env_ids = {"123", "456"}

        config1 = EnvironmentCredentialConfig(env_id="123", is_saved=True)
        config2 = EnvironmentCredentialConfig(env_id="456", is_saved=False)

        state.set_config(config1)
        state.set_config(config2)

        assert state.all_saved() is False

        config2.is_saved = True
        state.set_config(config2)
        assert state.all_saved() is True

    def test_to_dict_round_trip(self):
        """State survives to_dict/from_dict cycle."""
        state = EnvironmentCredentialsState()
        state.step_complete = True
        state.selected_env_ids = {"123", "456"}

        config = EnvironmentCredentialConfig(
            env_id="123",
            env_name="Production",
            credential_type="snowflake",
            is_saved=True,
        )
        state.set_config(config)

        data = state.to_dict()
        restored = EnvironmentCredentialsState.from_dict(data)

        assert restored.step_complete is True
        assert restored.selected_env_ids == {"123", "456"}
        assert "123" in restored.env_configs


class TestEnvVarPersistence:
    """Test .env file read/write for environment credentials."""

    def test_save_and_load_single_config(self):
        """Save and load a single environment's credentials."""
        with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
            temp_path = Path(f.name)

        try:
            config = {
                "user": "test_user",
                "password": "test_pass",
                "schema": "my_schema",
            }

            save_env_credential_config("env_123", config, use_dummy=False, env_path=str(temp_path))
            loaded = load_env_credential_config("env_123", env_path=str(temp_path))

            assert loaded["user"] == "test_user"
            assert loaded["password"] == "test_pass"
            assert loaded["schema"] == "my_schema"
            assert loaded.get("use_dummy") == "false"
        finally:
            temp_path.unlink(missing_ok=True)

    def test_save_with_dummy_flag(self):
        """Dummy flag is persisted correctly."""
        with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
            temp_path = Path(f.name)

        try:
            config = {"schema": "dummy_schema"}

            save_env_credential_config("env_123", config, use_dummy=True, env_path=str(temp_path))
            loaded = load_env_credential_config("env_123", env_path=str(temp_path))

            assert loaded.get("use_dummy") == "true"
        finally:
            temp_path.unlink(missing_ok=True)

    def test_load_all_configs(self):
        """Load multiple environment configs from .env."""
        with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Save two environments
            save_env_credential_config("env_1", {"user": "user1"}, env_path=str(temp_path))
            save_env_credential_config("env_2", {"user": "user2"}, env_path=str(temp_path))

            all_configs = load_env_credential_configs(env_path=str(temp_path))

            assert "env_1" in all_configs
            assert "env_2" in all_configs
            assert all_configs["env_1"]["user"] == "user1"
            assert all_configs["env_2"]["user"] == "user2"
        finally:
            temp_path.unlink(missing_ok=True)

    def test_env_var_naming_convention(self):
        """Verify env var naming: DBT_ENV_CRED_{ENV_ID}_{FIELD}."""
        with tempfile.NamedTemporaryFile(suffix=".env", delete=False) as f:
            temp_path = Path(f.name)

        try:
            save_env_credential_config("my_env_123", {"schema": "test_schema"}, env_path=str(temp_path))

            # Read raw file content
            content = temp_path.read_text()

            # Should contain properly formatted env var
            assert "DBT_ENV_CRED_MY_ENV_123_SCHEMA" in content
            assert "test_schema" in content
        finally:
            temp_path.unlink(missing_ok=True)


class TestWorkflowStepIntegration:
    """Test TARGET_CREDENTIALS step integration into workflow."""

    def test_target_credentials_step_exists(self):
        """TARGET_CREDENTIALS step is defined in WorkflowStep enum."""
        assert hasattr(WorkflowStep, "TARGET_CREDENTIALS")
        assert WorkflowStep.TARGET_CREDENTIALS is not None

    def test_target_credentials_in_migration_workflow(self):
        """TARGET_CREDENTIALS step is in MIGRATION workflow."""
        migration_steps = WORKFLOW_STEPS[WorkflowType.MIGRATION]
        assert WorkflowStep.TARGET_CREDENTIALS in migration_steps

    def test_target_credentials_between_configure_and_deploy(self):
        """TARGET_CREDENTIALS is after CONFIGURE and before DEPLOY."""
        migration_steps = WORKFLOW_STEPS[WorkflowType.MIGRATION]
        configure_idx = migration_steps.index(WorkflowStep.CONFIGURE)
        target_creds_idx = migration_steps.index(WorkflowStep.TARGET_CREDENTIALS)
        deploy_idx = migration_steps.index(WorkflowStep.DEPLOY)

        assert configure_idx < target_creds_idx < deploy_idx

    def test_target_credentials_has_step_name(self):
        """TARGET_CREDENTIALS has a display name."""
        assert WorkflowStep.TARGET_CREDENTIALS in STEP_NAMES
        assert STEP_NAMES[WorkflowStep.TARGET_CREDENTIALS] == "Target Credentials"

    def test_target_credentials_has_icon(self):
        """TARGET_CREDENTIALS has an icon."""
        assert WorkflowStep.TARGET_CREDENTIALS in STEP_ICONS
        assert STEP_ICONS[WorkflowStep.TARGET_CREDENTIALS] == "key"

    def test_target_credentials_step_accessible_after_configure(self):
        """TARGET_CREDENTIALS step accessible after configure complete."""
        state = AppState()
        state.deploy.configure_complete = True

        assert state.step_is_accessible(WorkflowStep.TARGET_CREDENTIALS) is True

    def test_target_credentials_step_not_accessible_before_configure(self):
        """TARGET_CREDENTIALS step locked before configure complete."""
        state = AppState()
        state.deploy.configure_complete = False

        assert state.step_is_accessible(WorkflowStep.TARGET_CREDENTIALS) is False

    def test_target_credentials_step_complete(self):
        """TARGET_CREDENTIALS step complete when state says so."""
        state = AppState()
        assert state.step_is_complete(WorkflowStep.TARGET_CREDENTIALS) is False

        state.env_credentials.step_complete = True
        assert state.step_is_complete(WorkflowStep.TARGET_CREDENTIALS) is True

    def test_deploy_accessible_after_target_credentials_complete(self):
        """DEPLOY accessible after TARGET_CREDENTIALS complete."""
        state = AppState()
        state.env_credentials.step_complete = True

        assert state.step_is_accessible(WorkflowStep.DEPLOY) is True

    def test_deploy_accessible_without_environments(self):
        """DEPLOY accessible when no environments are selected."""
        state = AppState()
        state.env_credentials.step_complete = False
        state.env_credentials.selected_env_ids = set()  # No environments

        # Should be accessible since there's nothing to configure
        assert state.step_is_accessible(WorkflowStep.DEPLOY) is True


class TestAppStatePersistence:
    """Test env_credentials state persistence in AppState."""

    def test_app_state_has_env_credentials(self):
        """AppState includes env_credentials field."""
        state = AppState()
        assert hasattr(state, "env_credentials")
        assert isinstance(state.env_credentials, EnvironmentCredentialsState)

    def test_env_credentials_survives_round_trip(self):
        """env_credentials state survives to_dict/from_dict cycle."""
        state = AppState()
        state.env_credentials.step_complete = True
        state.env_credentials.selected_env_ids = {"123"}

        config = EnvironmentCredentialConfig(
            env_id="123",
            env_name="Production",
            credential_type="snowflake",
            is_saved=True,
        )
        state.env_credentials.set_config(config)

        data = state.to_dict()
        restored = AppState.from_dict(data)

        assert restored.env_credentials.step_complete is True
        assert "123" in restored.env_credentials.selected_env_ids
        assert "123" in restored.env_credentials.env_configs


class TestExpandedCredentialModel:
    """Test the expanded Credential model in models.py."""

    def test_credential_model_has_all_fields(self):
        """Credential model has all adapter-specific fields."""
        from importer.models import Credential

        # Create a credential with various fields
        cred = Credential(
            credential_type="snowflake",
            schema_name="test_schema",
            auth_type="password",
            user="test_user",
            warehouse="test_wh",
        )

        assert cred.credential_type == "snowflake"
        assert cred.schema_name == "test_schema"
        assert cred.auth_type == "password"
        assert cred.user == "test_user"
        assert cred.warehouse == "test_wh"

    def test_credential_model_backwards_compatible(self):
        """Credential model supports old token_name/schema/catalog fields."""
        from importer.models import Credential

        # Old-style Databricks credential
        cred = Credential(
            token_name="my_token",
            schema_name="my_schema",
            catalog="my_catalog",
        )

        assert cred.token_name == "my_token"
        assert cred.schema_name == "my_schema"
        assert cred.catalog == "my_catalog"
        # schema property should still work
        assert cred.schema == "my_schema"

    def test_credential_model_serialization(self):
        """Credential model serializes correctly."""
        from importer.models import Credential

        cred = Credential(
            credential_type="bigquery",
            dataset="my_dataset",
            num_threads=4,
        )

        data = cred.model_dump(by_alias=True)
        assert data["credential_type"] == "bigquery"
        assert data["dataset"] == "my_dataset"
        assert data["num_threads"] == 4
        assert data["schema"] == ""  # Default value

    def test_environment_credential_optional(self):
        """Environment model allows optional credential."""
        from importer.models import Environment

        # Environment without credential (development type)
        env = Environment(
            key="dev",
            name="Development",
            type="development",
            connection_key="my_conn",
            credential=None,
        )

        assert env.credential is None

        # Environment with credential
        from importer.models import Credential
        
        cred = Credential(credential_type="snowflake", schema_name="prod")
        env_with_cred = Environment(
            key="prod",
            name="Production",
            type="deployment",
            connection_key="my_conn",
            credential=cred,
        )

        assert env_with_cred.credential is not None
        assert env_with_cred.credential.credential_type == "snowflake"


class TestYamlConverterEnvironmentCredentials:
    """Test environment credentials loading in YamlToTerraformConverter."""

    def test_load_environment_credentials_from_env(self):
        """Credentials are loaded from .env and mapped to project_key_env_key."""
        import tempfile
        import yaml as yaml_lib
        from pathlib import Path
        from unittest.mock import patch
        from importer.yaml_converter import YamlToTerraformConverter, ENVIRONMENT_CREDENTIAL_FIELDS

        yaml_content = {
            "projects": [
                {
                    "key": "my_project",
                    "environments": [
                        {"key": "prod", "name": "Production"},
                        {"key": "dev", "name": "Development"},
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "config.yml"
            with open(yaml_path, "w") as f:
                yaml_lib.dump(yaml_content, f)

            # Mock the env credential configs that would be loaded from .env
            mock_env_creds = {
                "prod": {
                    "credential_type": "snowflake",
                    "user": "prod_user",
                    "password": "prod_pass",
                    "schema": "prod_schema",
                },
            }

            converter = YamlToTerraformConverter()
            
            # Patch load_env_credential_configs to return our mock data
            with patch("importer.yaml_converter.yaml.safe_load") as mock_yaml_load:
                mock_yaml_load.return_value = yaml_content
                with patch("importer.web.env_manager.load_env_credential_configs") as mock_load:
                    mock_load.return_value = mock_env_creds
                    result = converter._load_environment_credentials_from_env(yaml_path)

            # Should have project_key_env_key format
            assert "my_project_prod" in result
            assert result["my_project_prod"]["user"] == "prod_user"
            assert result["my_project_prod"]["schema"] == "prod_schema"

    def test_load_environment_credentials_skips_dummy(self):
        """Dummy credentials are not loaded."""
        import tempfile
        import yaml as yaml_lib
        from pathlib import Path
        from importer.yaml_converter import YamlToTerraformConverter

        yaml_content = {
            "projects": [
                {
                    "key": "my_project",
                    "environments": [
                        {"key": "prod", "name": "Production"},
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "config.yml"
            with open(yaml_path, "w") as f:
                yaml_lib.dump(yaml_content, f)

            # Save dummy credentials to .env
            env_path = Path(tmpdir) / ".env"
            save_env_credential_config(
                "prod",
                {"credential_type": "snowflake", "user": "dummy_user"},
                use_dummy=True,  # Mark as dummy
                env_path=str(env_path),
            )

            converter = YamlToTerraformConverter()
            import importer.web.env_manager as env_manager
            original_find_env = getattr(env_manager, '_find_env_file', None)
            env_manager._find_env_file = lambda: str(env_path)

            try:
                result = converter._load_environment_credentials_from_env(yaml_path)
            finally:
                if original_find_env:
                    env_manager._find_env_file = original_find_env

            # Dummy credentials should be skipped
            assert "my_project_prod" not in result

    def test_secrets_tfvars_includes_environment_credentials(self):
        """Generated secrets.auto.tfvars includes environment_credentials."""
        import tempfile
        import yaml as yaml_lib
        from pathlib import Path
        from importer.yaml_converter import YamlToTerraformConverter

        yaml_content = {
            "globals": {"connections": []},
            "projects": [
                {
                    "key": "my_project",
                    "environments": [
                        {"key": "prod", "name": "Production", "connection": "my_conn"},
                    ],
                    "jobs": [],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "config.yml"
            with open(yaml_path, "w") as f:
                yaml_lib.dump(yaml_content, f)

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            env_creds = {
                "my_project_prod": {
                    "credential_type": "snowflake",
                    "user": "test_user",
                    "password": "secret123",
                    "schema": "my_schema",
                },
            }

            converter = YamlToTerraformConverter()
            converter._write_secrets_tfvars(output_dir, {}, env_creds)

            secrets_file = output_dir / "secrets.auto.tfvars"
            assert secrets_file.exists()

            content = secrets_file.read_text()
            assert "environment_credentials" in content
            assert "my_project_prod" in content
            assert "credential_type" in content
            assert '"snowflake"' in content
            assert "secret123" in content  # Password should be present

    def test_convert_sets_main_tf_host_default_from_yaml_account(self):
        """Generated main.tf should default dbt_host_url from normalized account host."""
        import tempfile
        import yaml as yaml_lib
        from pathlib import Path
        from importer.yaml_converter import YamlToTerraformConverter

        yaml_content = {
            "account": {"host_url": "https://do446.eu1.dbt.com"},
            "globals": {"connections": []},
            "projects": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "config.yml"
            with open(yaml_path, "w") as f:
                yaml_lib.dump(yaml_content, f)

            output_dir = Path(tmpdir) / "output"
            converter = YamlToTerraformConverter()
            converter.convert(str(yaml_path), str(output_dir), connection_credentials={}, environment_credentials={})

            main_tf = (output_dir / "main.tf").read_text()
            assert 'default     = "https://do446.eu1.dbt.com/api"' in main_tf


class TestModuleImports:
    """Verify all new modules import without errors."""

    def test_import_credential_schemas(self):
        """credential_schemas.py imports successfully."""
        from importer.web.components.credential_schemas import (
            CREDENTIAL_SCHEMAS,
            get_credential_schema,
            get_dummy_credentials,
        )

        assert CREDENTIAL_SCHEMAS is not None
        assert get_credential_schema is not None
        assert get_dummy_credentials is not None

    def test_import_target_credentials_page(self):
        """target_credentials.py imports successfully."""
        from importer.web.pages.target_credentials import (
            create_target_credentials_page,
        )

        assert create_target_credentials_page is not None

    def test_import_env_manager_credential_functions(self):
        """env_manager.py has credential functions."""
        from importer.web.env_manager import (
            load_env_credential_configs,
            load_env_credential_config,
            save_env_credential_config,
            save_all_env_credential_configs,
        )

        assert load_env_credential_configs is not None
        assert load_env_credential_config is not None
        assert save_env_credential_config is not None
        assert save_all_env_credential_configs is not None
