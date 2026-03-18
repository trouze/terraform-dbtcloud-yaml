"""Tests for terraform_helpers shared contract equivalence.

Verifies that:
- get_terraform_env produces correct TF_VAR_* and DBT_CLOUD_* env vars
- resolve_deployment_paths handles absolute/relative dirs and YAML fallbacks
- build_target_flags collects from protection intents, moves, and imports
- run_terraform_command wraps subprocess correctly
- read_tf_state_addresses parses tfstate JSON

These tests form the regression suite for Contract 3 (Terraform Helpers)
from docs/architecture/canonical-contracts.md.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_state(tmp_path: Path) -> MagicMock:
    """Minimal mock AppState for terraform helpers tests."""
    state = MagicMock()
    state.deploy.terraform_dir = str(tmp_path)
    state.fetch.output_dir = str(tmp_path / "output" / "fetch")
    state.target_credentials.api_token = "dbtc_test_token_123"
    state.target_credentials.account_id = "12345"
    state.target_credentials.host_url = "https://cloud.getdbt.com"
    state.target_credentials.token_type = "service_token"
    state.target_fetch = MagicMock()
    state.target_fetch.target_baseline_yaml = None
    return state


@pytest.fixture
def pat_state(tmp_path: Path) -> MagicMock:
    """Mock AppState with a PAT (user_token)."""
    state = MagicMock()
    state.deploy.terraform_dir = str(tmp_path)
    state.fetch.output_dir = str(tmp_path / "output" / "fetch")
    state.target_credentials.api_token = "dbtu_pat_token_456"
    state.target_credentials.account_id = "67890"
    state.target_credentials.host_url = "https://custom.getdbt.com/api"
    state.target_credentials.token_type = "user_token"
    state.target_fetch = MagicMock()
    state.target_fetch.target_baseline_yaml = None
    return state


# ---------------------------------------------------------------------------
# Contract 3a: get_terraform_env
# ---------------------------------------------------------------------------


class TestGetTerraformEnv:
    """Verify env construction for service tokens and PATs."""

    def test_service_token_sets_tf_vars(self, mock_state: MagicMock) -> None:
        from importer.web.utils.terraform_helpers import get_terraform_env

        env = get_terraform_env(mock_state)

        assert env["TF_VAR_dbt_account_id"] == "12345"
        assert env["TF_VAR_dbt_token"] == "dbtc_test_token_123"
        assert env["TF_VAR_dbt_host_url"] == "https://cloud.getdbt.com/api"
        assert env["DBT_CLOUD_TOKEN"] == "dbtc_test_token_123"
        assert env["DBT_CLOUD_ACCOUNT_ID"] == "12345"
        assert "TF_VAR_dbt_pat" not in env

    def test_pat_token_sets_dbt_pat(self, pat_state: MagicMock) -> None:
        from importer.web.utils.terraform_helpers import get_terraform_env

        env = get_terraform_env(pat_state)

        assert env["TF_VAR_dbt_pat"] == "dbtu_pat_token_456"
        assert env["TF_VAR_dbt_token"] == "dbtu_pat_token_456"

    def test_host_url_normalization_adds_api(self, mock_state: MagicMock) -> None:
        from importer.web.utils.terraform_helpers import get_terraform_env

        mock_state.target_credentials.host_url = "https://cloud.getdbt.com"
        env = get_terraform_env(mock_state)
        assert env["TF_VAR_dbt_host_url"] == "https://cloud.getdbt.com/api"

    def test_host_url_already_has_api(self, mock_state: MagicMock) -> None:
        from importer.web.utils.terraform_helpers import get_terraform_env

        mock_state.target_credentials.host_url = "https://cloud.getdbt.com/api"
        env = get_terraform_env(mock_state)
        assert env["TF_VAR_dbt_host_url"] == "https://cloud.getdbt.com/api"

    def test_dbtu_prefix_triggers_pat_even_without_user_token_type(
        self, mock_state: MagicMock
    ) -> None:
        from importer.web.utils.terraform_helpers import get_terraform_env

        mock_state.target_credentials.api_token = "dbtu_auto_detected"
        mock_state.target_credentials.token_type = "service_token"
        env = get_terraform_env(mock_state)
        assert env["TF_VAR_dbt_pat"] == "dbtu_auto_detected"

    def test_falls_back_to_target_env_when_state_token_missing(
        self, tmp_path: Path, mock_state: MagicMock
    ) -> None:
        from importer.web.utils.terraform_helpers import get_terraform_env

        mock_state.project_path = str(tmp_path)
        mock_state.target_credentials.api_token = ""
        mock_state.target_credentials.account_id = ""
        mock_state.target_credentials.host_url = ""
        mock_state.target_credentials.token_type = ""
        (tmp_path / "target.env").write_text(
            "\n".join(
                [
                    "DBT_TARGET_HOST_URL=https://fallback.getdbt.com/",
                    "DBT_TARGET_ACCOUNT_ID=4242",
                    "DBT_TARGET_API_TOKEN=dbtu_fallback_token",
                    ""
                ]
            ),
            encoding="utf-8",
        )

        env = get_terraform_env(mock_state)

        assert env["TF_VAR_dbt_account_id"] == "4242"
        assert env["TF_VAR_dbt_token"] == "dbtu_fallback_token"
        assert env["TF_VAR_dbt_pat"] == "dbtu_fallback_token"
        assert env["TF_VAR_dbt_host_url"] == "https://fallback.getdbt.com/api"


# ---------------------------------------------------------------------------
# Contract 3a: adopt.py and deploy.py delegate to shared helper
# ---------------------------------------------------------------------------


class TestAdoptDelegation:
    """Verify adopt.py's thin wrappers delegate to terraform_helpers."""

    def test_adopt_get_terraform_env_delegates(self, mock_state: MagicMock) -> None:
        from importer.web.pages.adopt import _get_terraform_env
        from importer.web.utils.terraform_helpers import get_terraform_env

        adopt_env = _get_terraform_env(mock_state)
        shared_env = get_terraform_env(mock_state)

        for key in ("TF_VAR_dbt_token", "TF_VAR_dbt_account_id", "TF_VAR_dbt_host_url"):
            assert adopt_env[key] == shared_env[key], f"Mismatch on {key}"

    def test_adopt_get_terraform_dir_delegates(self, mock_state: MagicMock) -> None:
        from importer.web.pages.adopt import _get_terraform_dir
        from importer.web.utils.terraform_helpers import resolve_deployment_paths

        adopt_path = _get_terraform_dir(mock_state)
        shared_path, _, _ = resolve_deployment_paths(mock_state)

        assert adopt_path == shared_path

    def test_deploy_get_terraform_env_delegates(self, mock_state: MagicMock) -> None:
        from importer.web.pages.deploy import _get_terraform_env
        from importer.web.utils.terraform_helpers import get_terraform_env

        deploy_env = _get_terraform_env(mock_state)
        shared_env = get_terraform_env(mock_state)

        for key in ("TF_VAR_dbt_token", "TF_VAR_dbt_account_id", "TF_VAR_dbt_host_url"):
            assert deploy_env[key] == shared_env[key], f"Mismatch on {key}"


# ---------------------------------------------------------------------------
# Contract 3b: resolve_deployment_paths
# ---------------------------------------------------------------------------


class TestResolveDeploymentPaths:
    """Verify path resolution for various configurations."""

    def test_absolute_terraform_dir(self, tmp_path: Path) -> None:
        from importer.web.utils.terraform_helpers import resolve_deployment_paths

        state = MagicMock()
        state.deploy.terraform_dir = str(tmp_path / "absolute_tf")
        state.fetch.output_dir = str(tmp_path / "fetch")
        state.target_fetch = MagicMock()
        state.target_fetch.target_baseline_yaml = None

        (tmp_path / "absolute_tf").mkdir()
        (tmp_path / "absolute_tf" / "dbt-cloud-config.yml").write_text("projects: []")

        tf_path, yaml_file, _ = resolve_deployment_paths(state)
        assert tf_path.is_absolute()
        assert tf_path == (tmp_path / "absolute_tf").resolve()

    def test_yaml_fallback_to_merged(self, tmp_path: Path) -> None:
        from importer.web.utils.terraform_helpers import resolve_deployment_paths

        state = MagicMock()
        state.deploy.terraform_dir = str(tmp_path)
        state.fetch.output_dir = None
        state.target_fetch = MagicMock()
        state.target_fetch.target_baseline_yaml = None

        (tmp_path / "dbt-cloud-config-merged.yml").write_text("projects: []")

        tf_path, yaml_file, _ = resolve_deployment_paths(state)
        assert yaml_file.name == "dbt-cloud-config-merged.yml"


# ---------------------------------------------------------------------------
# Contract 3e: read_tf_state_addresses
# ---------------------------------------------------------------------------


class TestReadTfStateAddresses:
    """Verify TF state parsing."""

    def test_parses_module_resources(self, tmp_path: Path) -> None:
        from importer.web.utils.terraform_helpers import read_tf_state_addresses

        state_data = {
            "version": 4,
            "resources": [
                {
                    "module": "module.dbt_cloud.module.projects_v2[0]",
                    "type": "dbtcloud_group",
                    "name": "groups",
                    "instances": [
                        {"index_key": "everyone", "attributes": {}},
                        {"index_key": "admins", "attributes": {}},
                    ],
                }
            ],
        }
        (tmp_path / "terraform.tfstate").write_text(json.dumps(state_data))

        addresses = read_tf_state_addresses(tmp_path)
        assert (
            'module.dbt_cloud.module.projects_v2[0].dbtcloud_group.groups["everyone"]'
            in addresses
        )
        assert (
            'module.dbt_cloud.module.projects_v2[0].dbtcloud_group.groups["admins"]'
            in addresses
        )

    def test_empty_on_missing_file(self, tmp_path: Path) -> None:
        from importer.web.utils.terraform_helpers import read_tf_state_addresses

        addresses = read_tf_state_addresses(tmp_path)
        assert addresses == set()

    def test_empty_on_invalid_json(self, tmp_path: Path) -> None:
        from importer.web.utils.terraform_helpers import read_tf_state_addresses

        (tmp_path / "terraform.tfstate").write_text("not json")
        addresses = read_tf_state_addresses(tmp_path)
        assert addresses == set()


# ---------------------------------------------------------------------------
# Contract 3f: output budgeting + emission
# ---------------------------------------------------------------------------


class TestOutputBudgeting:
    """Verify helper-level output budgeting behavior."""

    def test_budget_output_lines_none_budget_is_passthrough(self) -> None:
        from importer.web.utils.terraform_helpers import budget_output_lines

        lines = ["a", "b", "c"]
        bounded, omitted = budget_output_lines(lines, None)
        assert bounded == lines
        assert omitted == 0

    def test_emit_process_output_skips_blank_lines(self) -> None:
        from importer.web.utils.terraform_helpers import OutputBudget, emit_process_output

        stdout_seen: list[str] = []
        stderr_seen: list[str] = []
        omitted_seen: list[int] = []

        emit_process_output(
            "ok\n\nvalue\n",
            "\nwarn\n",
            on_stdout_line=stdout_seen.append,
            on_stderr_line=stderr_seen.append,
            stdout_budget=OutputBudget(max_lines=10, head_lines=5, tail_lines=5),
            stderr_budget=OutputBudget(max_lines=10, head_lines=5, tail_lines=5),
            on_omitted=omitted_seen.append,
        )

        assert stdout_seen == ["ok", "value"]
        assert stderr_seen == ["warn"]
        assert omitted_seen == []
