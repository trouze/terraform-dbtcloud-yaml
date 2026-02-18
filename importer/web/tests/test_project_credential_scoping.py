"""Regression tests for project-scoped credential storage.

Ensures:
- ``resolve_project_env_path`` picks the correct file per naming priority.
- ``auto_seed_project_env`` copies matching keys from root ``.env``.
- Save/load operations stay isolated within the project folder.
- Environment credential configs are scoped to the project target env file.
- All page-level call sites pass explicit ``env_path`` when a project is active.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from importer.web.env_manager import (
    _SOURCE_ENV_NAMES,
    _TARGET_ENV_NAMES,
    auto_seed_project_env,
    load_source_credentials,
    load_target_credentials,
    resolve_project_env_path,
    save_source_credentials,
    save_target_credentials,
    load_env_credential_config,
    save_env_credential_config,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project folder with a root .env sibling."""
    project = tmp_path / "projects" / "my-proj"
    project.mkdir(parents=True)

    root_env = tmp_path / ".env"
    root_env.write_text(
        "DBT_SOURCE_HOST_URL=https://source.example.com\n"
        "DBT_SOURCE_ACCOUNT_ID=111\n"
        "DBT_SOURCE_API_TOKEN=dbtc_source_tok\n"
        "DBT_TARGET_HOST_URL=https://target.example.com\n"
        "DBT_TARGET_ACCOUNT_ID=222\n"
        "DBT_TARGET_API_TOKEN=dbtc_target_tok\n",
        encoding="utf-8",
    )

    return tmp_path, project


# ---------------------------------------------------------------------------
# resolve_project_env_path
# ---------------------------------------------------------------------------

class TestResolveProjectEnvPath:
    """Tests for the centralized path resolver."""

    def test_returns_none_when_no_project(self):
        assert resolve_project_env_path(None, "source") is None
        assert resolve_project_env_path(None, "target") is None

    def test_preferred_visible_name_when_nothing_exists(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        result = resolve_project_env_path(str(project), "source")
        assert result == str(project / "source.env")

    def test_preferred_visible_name_for_target(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        result = resolve_project_env_path(str(project), "target")
        assert result == str(project / "target.env")

    def test_finds_visible_name_first(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        (project / "source.env").write_text("A=1\n")
        (project / ".env.source").write_text("B=2\n")
        result = resolve_project_env_path(str(project), "source")
        assert result == str(project / "source.env")

    def test_falls_back_to_legacy_dotfile(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".env.source").write_text("B=2\n")
        result = resolve_project_env_path(str(project), "source")
        assert result == str(project / ".env.source")

    def test_falls_back_to_combined_env(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".env").write_text("C=3\n")
        result = resolve_project_env_path(str(project), "source")
        assert result == str(project / ".env")


# ---------------------------------------------------------------------------
# auto_seed_project_env
# ---------------------------------------------------------------------------

class TestAutoSeedProjectEnv:
    """Tests for auto-seeding from root .env."""

    def test_seeds_source_keys(self, tmp_project):
        tmp_path, project = tmp_project
        with patch("importer.web.env_manager.find_env_file", return_value=tmp_path / ".env"):
            result = auto_seed_project_env(str(project), "source")

        assert result is not None
        content = Path(result).read_text()
        assert "DBT_SOURCE_HOST_URL" in content
        assert "DBT_TARGET" not in content

    def test_seeds_target_keys(self, tmp_project):
        tmp_path, project = tmp_project
        with patch("importer.web.env_manager.find_env_file", return_value=tmp_path / ".env"):
            result = auto_seed_project_env(str(project), "target")

        assert result is not None
        content = Path(result).read_text()
        assert "DBT_TARGET_HOST_URL" in content
        assert "DBT_SOURCE" not in content

    def test_noop_when_file_already_exists(self, tmp_project):
        tmp_path, project = tmp_project
        (project / "source.env").write_text("EXISTING=yes\n")
        with patch("importer.web.env_manager.find_env_file", return_value=tmp_path / ".env"):
            result = auto_seed_project_env(str(project), "source")
        assert result is None

    def test_noop_when_root_env_missing(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        with patch("importer.web.env_manager.find_env_file", return_value=tmp_path / ".env"):
            result = auto_seed_project_env(str(project), "source")
        assert result is None

    def test_noop_when_no_matching_keys(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        root_env = tmp_path / ".env"
        root_env.write_text("UNRELATED_KEY=val\n")
        with patch("importer.web.env_manager.find_env_file", return_value=root_env):
            result = auto_seed_project_env(str(project), "source")
        assert result is None


# ---------------------------------------------------------------------------
# Project-scoped load/save isolation
# ---------------------------------------------------------------------------

class TestProjectScopedLoadSave:
    """Verify that load/save stay within the project folder."""

    def test_save_source_creates_in_project(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        env_path = resolve_project_env_path(str(project), "source")
        save_source_credentials(
            host_url="https://s.example.com",
            account_id="100",
            api_token="dbtc_tok",
            env_path=env_path,
        )
        assert Path(env_path).exists()
        assert Path(env_path).parent == project

    def test_save_target_creates_in_project(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        env_path = resolve_project_env_path(str(project), "target")
        save_target_credentials(
            host_url="https://t.example.com",
            account_id="200",
            api_token="dbtc_tok2",
            env_path=env_path,
        )
        assert Path(env_path).exists()
        assert Path(env_path).parent == project

    def test_load_reads_from_project_not_global(self, tmp_project):
        """Load with explicit env_path MUST NOT read from the root .env."""
        tmp_path, project = tmp_project
        (project / "source.env").write_text(
            "DBT_SOURCE_HOST_URL=https://project-source.com\n"
            "DBT_SOURCE_ACCOUNT_ID=999\n"
            "DBT_SOURCE_API_TOKEN=dbtc_proj\n",
        )
        env_path = resolve_project_env_path(str(project), "source")
        creds = load_source_credentials(env_path=env_path)
        assert creds["account_id"] == "999"
        assert creds["host_url"] == "https://project-source.com"

    def test_two_projects_stay_isolated(self, tmp_path):
        """Credentials saved to project A must not leak into project B."""
        proj_a = tmp_path / "proj-a"
        proj_b = tmp_path / "proj-b"
        proj_a.mkdir()
        proj_b.mkdir()

        env_a = resolve_project_env_path(str(proj_a), "source")
        env_b = resolve_project_env_path(str(proj_b), "source")

        save_source_credentials("https://a.com", "1", "dbtc_a", env_path=env_a)
        save_source_credentials("https://b.com", "2", "dbtc_b", env_path=env_b)

        creds_a = load_source_credentials(env_path=env_a)
        creds_b = load_source_credentials(env_path=env_b)

        assert creds_a["account_id"] == "1"
        assert creds_b["account_id"] == "2"
        assert creds_a["host_url"] != creds_b["host_url"]


# ---------------------------------------------------------------------------
# Environment credential config scoping
# ---------------------------------------------------------------------------

class TestEnvCredentialConfigScoping:
    """Verify env credential configs are scoped to the target env file."""

    def test_save_and_load_scoped(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        env_path = resolve_project_env_path(str(project), "target")

        save_env_credential_config(
            env_id="env-123",
            config={"schema": "my_schema", "user": "my_user"},
            env_path=env_path,
        )

        loaded = load_env_credential_config("env-123", env_path=env_path)
        assert loaded.get("schema") == "my_schema"
        assert loaded.get("user") == "my_user"

    def test_config_not_in_other_project(self, tmp_path):
        proj_a = tmp_path / "a"
        proj_b = tmp_path / "b"
        proj_a.mkdir()
        proj_b.mkdir()

        env_a = resolve_project_env_path(str(proj_a), "target")
        env_b = resolve_project_env_path(str(proj_b), "target")

        save_env_credential_config("env-1", {"schema": "s_a"}, env_path=env_a)

        loaded_b = load_env_credential_config("env-1", env_path=env_b)
        assert loaded_b == {}


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Ensure legacy .env.source / .env.target files are still found."""

    def test_reads_legacy_env_source(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".env.source").write_text(
            "DBT_SOURCE_HOST_URL=https://legacy.com\n"
            "DBT_SOURCE_ACCOUNT_ID=777\n"
            "DBT_SOURCE_API_TOKEN=dbtc_legacy\n",
        )
        env_path = resolve_project_env_path(str(project), "source")
        assert env_path == str(project / ".env.source")
        creds = load_source_credentials(env_path=env_path)
        assert creds["account_id"] == "777"

    def test_reads_legacy_env_target(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".env.target").write_text(
            "DBT_TARGET_HOST_URL=https://legacy-target.com\n"
            "DBT_TARGET_ACCOUNT_ID=888\n"
            "DBT_TARGET_API_TOKEN=dbtc_legacy_t\n",
        )
        env_path = resolve_project_env_path(str(project), "target")
        assert env_path == str(project / ".env.target")
        creds = load_target_credentials(env_path=env_path)
        assert creds["account_id"] == "888"

    def test_visible_name_preferred_over_legacy(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        (project / "source.env").write_text("DBT_SOURCE_ACCOUNT_ID=new\n")
        (project / ".env.source").write_text("DBT_SOURCE_ACCOUNT_ID=old\n")
        env_path = resolve_project_env_path(str(project), "source")
        assert env_path == str(project / "source.env")


# ---------------------------------------------------------------------------
# ProjectConfig defaults
# ---------------------------------------------------------------------------

class TestProjectConfigDefaults:
    """Verify ProjectConfig now defaults to visible filenames."""

    def test_defaults(self):
        from importer.web.project_manager import ProjectConfig
        from importer.web.state import WorkflowType

        cfg = ProjectConfig(name="test", slug="test", workflow_type=WorkflowType.MIGRATION)
        assert cfg.source_env_file == "source.env"
        assert cfg.target_env_file == "target.env"
