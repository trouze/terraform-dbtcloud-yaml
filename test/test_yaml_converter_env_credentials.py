from pathlib import Path
from unittest.mock import patch

from importer.yaml_converter import YamlToTerraformConverter


def test_environment_credentials_fall_back_to_root_env_and_match_indexed_keys(
    tmp_path: Path,
) -> None:
    root_env = tmp_path / ".env"
    root_env.write_text(
        "\n".join(
            [
                "DBT_ENV_CRED_1_PROD_USE_DUMMY='false'",
                "DBT_ENV_CRED_1_PROD_DATABASE='analytics'",
                "DBT_ENV_CRED_1_PROD_SCHEMA='public'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    project_dir = tmp_path / "projects" / "ps-sandbox"
    project_dir.mkdir(parents=True)
    target_env = project_dir / "target.env"
    target_env.write_text(
        "DBT_TARGET_HOST_URL='https://target.example.com'\n",
        encoding="utf-8",
    )

    yaml_path = project_dir / "dbt-cloud-config.yml"
    yaml_path.write_text(
        "\n".join(
            [
                "projects:",
                "  - key: sample_project",
                "    environments:",
                "      - key: prod",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    converter = YamlToTerraformConverter()
    with patch("importer.web.env_manager.find_env_file", return_value=root_env):
        creds = converter._load_environment_credentials_from_env(
            yaml_path=yaml_path,
            env_path=str(target_env),
        )

    assert creds == {
        "sample_project_prod": {
            "database": "analytics",
            "schema": "public",
        }
    }
