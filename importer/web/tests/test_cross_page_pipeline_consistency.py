"""Cross-page pipeline consistency tests (Harness 6).

Verifies that different pages produce the same artifacts for the same
intents when calling run_generate_pipeline.

See PRD 43.03: CP-1 through CP-4.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from importer.web.utils.generate_pipeline import PipelineResult, run_generate_pipeline
from importer.web.utils.protection_intent import ProtectionIntentManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_yaml(tmp_path: Path, config: dict) -> Path:
    yaml_file = tmp_path / "dbt-cloud-config.yml"
    yaml_file.write_text(yaml.dump(config, default_flow_style=False))
    return yaml_file


def _make_tf_state(tmp_path: Path, resources: list[dict]) -> Path:
    state_file = tmp_path / "terraform.tfstate"
    state_data = {"version": 4, "resources": resources}
    state_file.write_text(json.dumps(state_data))
    return state_file


def _tf_resource(
    module: str,
    rtype: str,
    name: str,
    instances: list[dict],
) -> dict:
    return {
        "module": module,
        "type": rtype,
        "name": name,
        "instances": instances,
    }


def _tf_instance(key: str) -> dict:
    return {"index_key": key, "attributes": {"id": f"id_{key}"}}


MODULE = "module.dbt_cloud.module.projects_v2[0]"


@pytest.fixture
def mock_state(tmp_path: Path) -> MagicMock:
    state = MagicMock()
    state.deploy.terraform_dir = str(tmp_path)
    state.fetch.output_dir = None
    state.target_credentials.api_token = "test_token"
    state.target_credentials.account_id = "1"
    state.target_credentials.host_url = "https://cloud.getdbt.com"
    state.target_credentials.token_type = "service_token"
    state.target_fetch = MagicMock()
    state.target_fetch.target_baseline_yaml = None
    state.map.protected_resources = set()
    return state


@pytest.fixture
def intent_manager(tmp_path: Path) -> ProtectionIntentManager:
    return ProtectionIntentManager(tmp_path / "protection-intent.json")


# ---------------------------------------------------------------------------
# CP-1: Utilities and Adopt produce same protection_moves.tf
# ---------------------------------------------------------------------------


class TestCP1SameMovesFile:
    """Utilities (include_adopt=False) and Adopt (include_adopt=True) must
    produce identical protection_moves.tf for the same protection intents.
    """

    def test_same_protection_moves_for_protect_intent(
        self, tmp_path: Path, mock_state: MagicMock, intent_manager: ProtectionIntentManager
    ) -> None:
        yaml_config = {
            "projects": [
                {
                    "key": "proj_a",
                    "name": "Project A",
                    "repositories": [{"key": "proj_a"}],
                }
            ]
        }
        _make_yaml(tmp_path, yaml_config)

        _make_tf_state(
            tmp_path,
            [
                _tf_resource(MODULE, "dbtcloud_project", "projects", [_tf_instance("proj_a")]),
                _tf_resource(MODULE, "dbtcloud_repository", "repositories", [_tf_instance("proj_a")]),
                _tf_resource(MODULE, "dbtcloud_project_repository", "project_repositories", [_tf_instance("proj_a")]),
            ],
        )

        intent_manager.set_intent(
            "PRJ:proj_a", protected=True, source="test", reason="test protect",
            resource_type="PRJ",
        )
        intent_manager.save()
        mock_state.get_protection_intent_manager.return_value = intent_manager

        with patch(
            "importer.web.utils.generate_pipeline.resolve_deployment_paths",
            return_value=(tmp_path, tmp_path / "dbt-cloud-config.yml", None),
        ):
            # Utilities path: include_adopt=False
            result_util = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    include_adopt=False,
                    include_protection_moves=True,
                    merge_baseline=False,
                    regenerate_hcl=False,
                )
            )

            # Reset intent for second run
            intent_manager2 = ProtectionIntentManager(tmp_path / "protection-intent2.json")
            intent_manager2.set_intent(
                "PRJ:proj_a", protected=True, source="test", reason="test protect",
                resource_type="PRJ",
            )
            intent_manager2.save()
            mock_state.get_protection_intent_manager.return_value = intent_manager2

            # Adopt path: include_adopt=True but no adopt rows
            result_adopt = asyncio.run(
                run_generate_pipeline(
                    mock_state,
                    include_adopt=True,
                    adopt_rows=[],
                    include_protection_moves=True,
                    merge_baseline=False,
                    regenerate_hcl=False,
                )
            )

        assert result_util.moves_count == result_adopt.moves_count, (
            f"Utilities produced {result_util.moves_count} moves, "
            f"Adopt produced {result_adopt.moves_count}"
        )


# ---------------------------------------------------------------------------
# CP-2 / CP-3: Intent survives across pages (via file persistence)
# ---------------------------------------------------------------------------


class TestCP2IntentSurvivesNavigation:
    """Intents set on Match page persist via protection-intent.json and
    are available when Adopt or Utilities loads.
    """

    def test_intent_persists_to_file_and_reloads(self, tmp_path: Path) -> None:
        intent_file = tmp_path / "protection-intent.json"

        # Match page records intent
        manager1 = ProtectionIntentManager(intent_file)
        manager1.set_intent(
            "GRP:everyone", protected=True, source="test", reason="test protect",
            resource_type="GRP",
        )
        manager1.save()

        # Adopt page loads intent from file
        manager2 = ProtectionIntentManager(intent_file)
        manager2.load()
        assert manager2.has_intent("GRP:everyone")
        intent = manager2.get_intent("GRP:everyone")
        assert intent is not None
        assert intent.protected is True

    def test_multiple_intents_survive_reload(self, tmp_path: Path) -> None:
        intent_file = tmp_path / "protection-intent.json"

        manager1 = ProtectionIntentManager(intent_file)
        manager1.set_intent(
            "GRP:everyone", protected=True, source="test", reason="test protect",
            resource_type="GRP",
        )
        manager1.set_intent(
            "PRJ:proj_a", protected=False, source="test", reason="test unprotect",
            resource_type="PRJ",
        )
        manager1.set_intent(
            "REP:repo_b", protected=True, source="test", reason="test protect",
            resource_type="REP",
        )
        manager1.save()

        manager2 = ProtectionIntentManager(intent_file)
        manager2.load()
        assert manager2.has_intent("GRP:everyone")
        assert manager2.has_intent("PRJ:proj_a")
        assert manager2.has_intent("REP:repo_b")

        everyone = manager2.get_intent("GRP:everyone")
        assert everyone is not None and everyone.protected is True

        proj_a = manager2.get_intent("PRJ:proj_a")
        assert proj_a is not None and proj_a.protected is False
