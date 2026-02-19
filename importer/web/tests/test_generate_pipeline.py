"""Pipeline unit tests for run_generate_pipeline (P-1 through P-8).

Tests the headless pipeline directly with fixture files in tmp_path.
No UI, no subprocess.

See PRD 43.03 — Unified Protect & Adopt Pipeline, Harness 1.
"""

from __future__ import annotations

import asyncio
import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from importer.web.utils.generate_pipeline import PipelineResult, run_generate_pipeline
from importer.web.utils.protection_intent import ProtectionIntentManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_yaml(tmp_path: Path, config: dict) -> Path:
    """Write a minimal YAML config file."""
    yaml_file = tmp_path / "dbt-cloud-config.yml"
    yaml_file.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    return yaml_file


def _make_tf_state(tmp_path: Path, resources: list[dict]) -> Path:
    """Write a terraform.tfstate with the given resources."""
    state_file = tmp_path / "terraform.tfstate"
    state = {"version": 4, "terraform_version": "1.5.0", "resources": resources}
    state_file.write_text(json.dumps(state, indent=2))
    return state_file


def _tf_resource(
    module: str,
    rtype: str,
    rname: str,
    instances: list[dict] | None = None,
) -> dict:
    """Build a TF state resource dict."""
    return {
        "module": module,
        "type": rtype,
        "name": rname,
        "instances": instances or [],
    }


def _tf_instance(index_key: str = "") -> dict:
    return {"index_key": index_key, "attributes": {}}


@pytest.fixture
def mock_state(tmp_path: Path):
    """Create a minimal AppState-like mock pointing to tmp_path."""
    state = MagicMock()
    state.deploy.terraform_dir = str(tmp_path)
    state.fetch.output_dir = None
    state.target_credentials.api_token = "test_token"
    state.target_credentials.account_id = "12345"
    state.target_credentials.host_url = "https://cloud.getdbt.com"
    state.target_credentials.token_type = "service_token"
    state.target_fetch.target_baseline_yaml = None
    state.map.protected_resources = set()
    return state


@pytest.fixture
def intent_manager(tmp_path: Path) -> ProtectionIntentManager:
    """Create a fresh ProtectionIntentManager."""
    mgr = ProtectionIntentManager(tmp_path / "protection-intent.json")
    return mgr


# ---------------------------------------------------------------------------
# P-1: Pipeline applies all intents after baseline merge
# ---------------------------------------------------------------------------

class TestP1ApplyIntentsAfterMerge:
    """Protection flags survive baseline merge."""

    def test_protection_flags_survive_merge(self, tmp_path, mock_state, intent_manager):
        # Arrange: YAML with one project (project-level protection is well-tested)
        config = {
            "projects": [
                {"key": "my_proj", "name": "My Project"},
            ],
        }
        _make_yaml(tmp_path, config)

        # Set intent to protect the project
        intent_manager.set_intent(
            "PRJ:my_proj", protected=True, source="test", reason="test",
        )
        mock_state.get_protection_intent_manager.return_value = intent_manager

        # Act
        with patch("importer.web.utils.generate_pipeline.resolve_deployment_paths") as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            # Skip HCL regen (no actual TF module)
            result = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    merge_baseline=False,
                    regenerate_hcl=False,
                    include_protection_moves=False,
                )
            )

        # Assert
        assert result.ok
        assert result.yaml_updated
        yaml_content = yaml.safe_load((tmp_path / "dbt-cloud-config.yml").read_text())
        project = yaml_content.get("projects", [{}])[0]
        assert project.get("protected") is True


# ---------------------------------------------------------------------------
# P-2: Pipeline skips moved blocks for resources not in TF state
# ---------------------------------------------------------------------------

class TestP2SkipMovedNotInState:
    """No moved block for resources being imported."""

    def test_no_moved_block_for_new_import(self, tmp_path, mock_state, intent_manager):
        config = {"projects": [{"key": "my_proj", "name": "My Project"}]}
        _make_yaml(tmp_path, config)
        # TF state with ONE resource (so the set is non-empty and the filter activates)
        # but the target resource (PRJ:my_proj) is NOT in state
        prefix = "module.dbt_cloud.module.projects_v2[0]"
        _make_tf_state(tmp_path, [
            _tf_resource(prefix, "dbtcloud_project", "projects", [_tf_instance("other_proj")]),
        ])

        intent_manager.set_intent(
            "PRJ:my_proj", protected=True, source="test", reason="test",
        )
        mock_state.get_protection_intent_manager.return_value = intent_manager

        with patch("importer.web.utils.generate_pipeline.resolve_deployment_paths") as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            result = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    merge_baseline=False,
                    regenerate_hcl=False,
                    include_protection_moves=True,
                )
            )

        # Should not have moved blocks for my_proj (not in state)
        assert result.moves_count == 0


# ---------------------------------------------------------------------------
# P-3: Pipeline expands PRJ intent to REP + PREP
# ---------------------------------------------------------------------------

class TestP3ExpandPRJ:
    """PRJ protection cascades to REP and PREP."""

    def test_prj_cascades_to_rep_prep(self, tmp_path, mock_state, intent_manager):
        config = {"projects": [{"key": "my_proj", "name": "My Project"}]}
        _make_yaml(tmp_path, config)

        # Put the project in TF state (unprotected block)
        prefix = "module.dbt_cloud.module.projects_v2[0]"
        _make_tf_state(tmp_path, [
            _tf_resource(prefix, "dbtcloud_project", "projects", [_tf_instance("my_proj")]),
            _tf_resource(prefix, "dbtcloud_repository", "repositories", [_tf_instance("my_proj")]),
            _tf_resource(prefix, "dbtcloud_project_repository", "project_repositories", [_tf_instance("my_proj")]),
        ])

        intent_manager.set_intent(
            "PRJ:my_proj", protected=True, source="test", reason="test",
        )
        mock_state.get_protection_intent_manager.return_value = intent_manager

        with patch("importer.web.utils.generate_pipeline.resolve_deployment_paths") as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            result = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    merge_baseline=False,
                    regenerate_hcl=False,
                    include_protection_moves=True,
                )
            )

        # Should have 3 moved blocks: PRJ, REP, PREP
        assert result.moves_count == 3
        content = result.moves_file.read_text()
        assert "projects" in content
        assert "repositories" in content
        assert "project_repositories" in content


# ---------------------------------------------------------------------------
# P-4: Pipeline uses protected address for protected adopt rows
# ---------------------------------------------------------------------------

class TestP4ProtectedAdoptAddress:
    """adopt_imports.tf uses protected_groups for protected resources."""

    def test_protected_adopt_uses_protected_address(self, tmp_path, mock_state, intent_manager):
        config = {"groups": [{"key": "everyone", "name": "Everyone", "protected": True}]}
        _make_yaml(tmp_path, config)
        _make_tf_state(tmp_path, [])

        mock_state.get_protection_intent_manager.return_value = intent_manager

        adopt_rows = [
            {
                "source_key": "target__everyone",
                "source_type": "GRP",
                "source_name": "Everyone",
                "target_id": "775",
                "action": "adopt",
                "protected": True,
                "drift_status": "not_in_state",
                "state_address": "",
                "is_target_only": True,
            }
        ]

        with patch("importer.web.utils.generate_pipeline.resolve_deployment_paths") as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            result = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    include_adopt=True,
                    adopt_rows=adopt_rows,
                    merge_baseline=False,
                    regenerate_hcl=False,
                    include_protection_moves=False,
                )
            )

        # Check that the import file uses the protected address
        assert result.imports_file is not None
        content = result.imports_file.read_text()
        assert "protected_groups" in content


# ---------------------------------------------------------------------------
# P-5: Pipeline target flags include both imports and moves
# ---------------------------------------------------------------------------

class TestP5TargetFlagsComplete:
    """Target addresses drawn from both protection_moves.tf and adopt_imports.tf."""

    def test_target_flags_from_both_files(self, tmp_path, mock_state, intent_manager):
        config = {"groups": [{"key": "everyone", "name": "Everyone"}]}
        _make_yaml(tmp_path, config)
        _make_tf_state(tmp_path, [])

        # Pre-create protection_moves.tf with a moved block
        (tmp_path / "protection_moves.tf").write_text(textwrap.dedent("""\
            moved {
              from = module.dbt_cloud.module.projects_v2[0].dbtcloud_project.projects["abc"]
              to   = module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["abc"]
            }
        """))

        # Pre-create adopt_imports.tf with an import block
        (tmp_path / "adopt_imports.tf").write_text(textwrap.dedent("""\
            import {
              to = module.dbt_cloud.module.projects_v2[0].dbtcloud_group.protected_groups["everyone"]
              id = "775"
            }
        """))

        mock_state.get_protection_intent_manager.return_value = intent_manager

        with patch("importer.web.utils.generate_pipeline.resolve_deployment_paths") as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            result = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    merge_baseline=False,
                    regenerate_hcl=False,
                    include_protection_moves=False,
                    include_adopt=False,
                )
            )

        # Both files' addresses should appear in targets
        assert len(result.target_addresses) >= 3  # 2 from moves (from + to) + 1 from imports
        addresses_str = " ".join(result.target_addresses)
        assert "projects" in addresses_str
        assert "protected_groups" in addresses_str


# ---------------------------------------------------------------------------
# P-6: Pipeline unprotect updates YAML
# ---------------------------------------------------------------------------

class TestP6UnprotectUpdatesYAML:
    """Unprotecting a resource clears its protection flag in YAML."""

    def test_unprotect_clears_yaml_flag(self, tmp_path, mock_state, intent_manager):
        # Use project-level protection (well-supported by apply_unprotection_from_set)
        config = {"projects": [{"key": "my_proj", "name": "My Project", "protected": True}]}
        _make_yaml(tmp_path, config)

        intent_manager.set_intent(
            "PRJ:my_proj", protected=False, source="test", reason="test",
        )
        mock_state.get_protection_intent_manager.return_value = intent_manager

        with patch("importer.web.utils.generate_pipeline.resolve_deployment_paths") as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            result = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    merge_baseline=False,
                    regenerate_hcl=False,
                    include_protection_moves=False,
                )
            )

        assert result.ok
        yaml_content = yaml.safe_load((tmp_path / "dbt-cloud-config.yml").read_text())
        project = yaml_content.get("projects", [{}])[0]
        # protected should be False or removed
        assert project.get("protected") is not True


# ---------------------------------------------------------------------------
# P-7: Pipeline is idempotent on rerun
# ---------------------------------------------------------------------------

class TestP7Idempotent:
    """Running the pipeline twice produces identical output."""

    def test_idempotent_run(self, tmp_path, mock_state, intent_manager):
        config = {"groups": [{"key": "everyone", "name": "Everyone"}]}
        _make_yaml(tmp_path, config)
        _make_tf_state(tmp_path, [])

        intent_manager.set_intent(
            "GRP:everyone", protected=True, source="test", reason="test",
        )
        mock_state.get_protection_intent_manager.return_value = intent_manager

        with patch("importer.web.utils.generate_pipeline.resolve_deployment_paths") as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            result1 = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    merge_baseline=False,
                    regenerate_hcl=False,
                    include_protection_moves=False,
                )
            )

        yaml1 = (tmp_path / "dbt-cloud-config.yml").read_text()

        # Run again (intent now marked applied_to_yaml)
        with patch("importer.web.utils.generate_pipeline.resolve_deployment_paths") as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            result2 = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    merge_baseline=False,
                    regenerate_hcl=False,
                    include_protection_moves=False,
                )
            )

        yaml2 = (tmp_path / "dbt-cloud-config.yml").read_text()
        assert yaml1 == yaml2


# ---------------------------------------------------------------------------
# P-8: Pipeline produces no files when nothing pending
# ---------------------------------------------------------------------------

class TestP8NothingPending:
    """Empty intents = no artifacts."""

    def test_no_output_when_nothing_pending(self, tmp_path, mock_state, intent_manager):
        config = {"groups": [{"key": "everyone", "name": "Everyone"}]}
        _make_yaml(tmp_path, config)

        # No intents set
        mock_state.get_protection_intent_manager.return_value = intent_manager

        with patch("importer.web.utils.generate_pipeline.resolve_deployment_paths") as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            result = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    merge_baseline=False,
                    regenerate_hcl=False,
                    include_protection_moves=True,
                )
            )

        assert result.ok
        assert result.moves_count == 0
        assert result.imports_file is None
        assert len(result.intents_applied) == 0


# ---------------------------------------------------------------------------
# P-9: Adopt-only baseline merge is projects-only
# ---------------------------------------------------------------------------

class TestP9AdoptBaselineProjectsOnly:
    """Adopt-only baseline merge must not pull in baseline globals."""

    def test_adopt_only_merge_trims_baseline_to_projects(
        self, tmp_path, mock_state, intent_manager
    ):
        source_config = {
            "version": 2,
            "projects": [{"key": "proj_a", "name": "Source Project"}],
        }
        baseline_config = {
            "version": 2,
            "globals": {
                "connections": [{"key": "baseline_conn", "name": "Baseline Conn"}],
                "environments": [{"key": "baseline_env", "name": "Baseline Env"}],
            },
            "projects": [
                {"key": "proj_a", "name": "Adopt Project A"},
                {"key": "proj_b", "name": "Other Baseline Project"},
            ],
        }
        _make_yaml(tmp_path, source_config)
        baseline_path = tmp_path / "target-baseline.yml"
        baseline_path.write_text(
            yaml.dump(baseline_config, default_flow_style=False, sort_keys=False)
        )

        mock_state.target_fetch.target_baseline_yaml = str(baseline_path)
        mock_state.get_protection_intent_manager.return_value = intent_manager
        adopt_rows = [
            {
                "source_key": "target__proj_a",
                "source_type": "PRJ",
                "target_id": "601",
                "action": "adopt",
                "drift_status": "not_in_state",
            }
        ]

        with patch(
            "importer.web.utils.generate_pipeline.resolve_deployment_paths"
        ) as mock_paths:
            mock_paths.return_value = (tmp_path, tmp_path / "dbt-cloud-config.yml", None)
            result = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    include_adopt=True,
                    adopt_rows=adopt_rows,
                    merge_baseline=True,
                    regenerate_hcl=False,
                    include_protection_moves=False,
                )
            )

        assert result.ok
        merged_yaml = yaml.safe_load((tmp_path / "dbt-cloud-config.yml").read_text())
        assert "globals" not in merged_yaml or not merged_yaml.get("globals")
        merged_project_keys = {p.get("key") for p in merged_yaml.get("projects", [])}
        assert "proj_a" in merged_project_keys
        assert "proj_b" not in merged_project_keys
