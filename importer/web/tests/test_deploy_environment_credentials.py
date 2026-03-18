from pathlib import Path

from importer.web.pages.deploy import (
    _build_environment_credentials_from_state,
    _build_profile_credentials_from_yaml,
)
from importer.web.state import AppState, EnvironmentCredentialConfig


def test_build_environment_credentials_from_state_includes_unsaved_dummy_deploy_envs() -> None:
    state = AppState()
    state.env_credentials.selected_env_ids = {"prod", "development"}
    state.env_credentials.set_config(
        EnvironmentCredentialConfig(
            env_id="prod",
            env_name="Prod",
            project_id="pat_s_snowflake_sandbox",
            project_name="Pat's Snowflake Sandbox",
            connection_type="snowflake",
            credential_type="snowflake",
            env_type="deployment",
            credential_values={
                "credential_type": "snowflake",
                "database": "DEVELOPMENT",
                "warehouse": "TRANSFORMING",
                "role": "TRANSFORMER",
                "schema": "prod_pkearns",
                "user": "cse_test_user",
                "num_threads": 4,
                "auth_type": "keypair",
                "private_key": "dummy_private_key",
                "password": "should_be_removed",
            },
            use_dummy_credentials=True,
            is_saved=False,
        )
    )
    state.env_credentials.set_config(
        EnvironmentCredentialConfig(
            env_id="development",
            env_name="Development",
            project_id="pat_s_snowflake_sandbox",
            project_name="Pat's Snowflake Sandbox",
            connection_type="snowflake",
            credential_type="snowflake",
            env_type="development",
            credential_values={"credential_type": "snowflake", "schema": "ignored"},
        )
    )

    result = _build_environment_credentials_from_state(state)

    assert result == {
        "pat_s_snowflake_sandbox_prod": {
            "credential_type": "snowflake",
            "database": "DEVELOPMENT",
            "warehouse": "TRANSFORMING",
            "role": "TRANSFORMER",
            "schema": "prod_pkearns",
            "user": "cse_test_user",
            "num_threads": 4,
            "auth_type": "keypair",
            "private_key": "dummy_private_key",
        }
    }


def test_build_profile_credentials_from_yaml_includes_standalone_profile_credentials(
    tmp_path: Path,
) -> None:
    yaml_file = tmp_path / "config.yml"
    yaml_file.write_text(
        """
projects:
  - key: pat_s_snowflake_sandbox
    environments:
      - key: prod
        credential:
          id: 120533
          credential_type: snowflake
          schema: analytics
    profiles:
      - key: standalone_profile
        credentials_key: cred_446250
        credentials_id: 446250
        credential:
          id: 446250
          credential_type: databricks
          schema: sandbox_schema
""".strip(),
        encoding="utf-8",
    )

    result = _build_profile_credentials_from_yaml(str(yaml_file))

    assert result == {
        "pat_s_snowflake_sandbox_standalone_profile": {
            "credential_type": "databricks",
            "schema": "sandbox_schema",
            "token": "dummy_token",
        }
    }
