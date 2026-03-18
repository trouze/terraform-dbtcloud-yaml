"""Contract tests enforcing resource_metadata wiring in module templates."""

import json
from pathlib import Path

from importer.web.components.match_grid import MATCH_GRID_TYPE_LABELS
from importer.web.components.progress_tree import PROJECT_RESOURCES
from importer.web.components.target_matcher import RESOURCE_TYPE_LABELS
from importer.web.utils.yaml_viewer import get_yaml_stats
from importer.web.utils.protection_manager import (
    EXTENDED_RESOURCE_TYPE_MAP,
    RESOURCE_TYPE_MAP,
    TYPE_LABELS,
)
from importer.web.utils.terraform_import import RESOURCE_TYPE_TO_TF
from importer.web.utils.terraform_state_reader import TF_TYPE_TO_CODE


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULES_DIR = REPO_ROOT / "modules" / "projects_v2"


def _resource_block(module_file: Path, resource_decl: str) -> str:
    lines = module_file.read_text(encoding="utf-8").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if resource_decl in line),
        None,
    )
    assert start is not None, f"Missing resource declaration: {resource_decl}"

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith('resource "'):
            end = i
            break
    return "\n".join(lines[start:end])


def test_projects_and_extended_attributes_include_resource_metadata() -> None:
    projects_tf = MODULES_DIR / "projects.tf"
    extended_attrs_tf = MODULES_DIR / "extended_attributes.tf"

    assert "resource_metadata" in _resource_block(
        projects_tf, 'resource "dbtcloud_project" "projects"'
    )
    assert "resource_metadata" in _resource_block(
        projects_tf, 'resource "dbtcloud_project" "protected_projects"'
    )
    assert "resource_metadata" in _resource_block(
        extended_attrs_tf, 'resource "dbtcloud_extended_attributes" "extended_attrs"'
    )
    assert "resource_metadata" in _resource_block(
        extended_attrs_tf,
        'resource "dbtcloud_extended_attributes" "protected_extended_attrs"',
    )


def test_other_migrated_resources_include_resource_metadata() -> None:
    environments_tf = MODULES_DIR / "environments.tf"
    jobs_tf = MODULES_DIR / "jobs.tf"
    env_vars_tf = MODULES_DIR / "environment_vars.tf"
    globals_tf = MODULES_DIR / "globals.tf"
    projects_tf = MODULES_DIR / "projects.tf"

    required_blocks = [
        (environments_tf, 'resource "dbtcloud_environment" "environments"'),
        (environments_tf, 'resource "dbtcloud_environment" "protected_environments"'),
        (jobs_tf, 'resource "dbtcloud_job" "jobs"'),
        (jobs_tf, 'resource "dbtcloud_job" "protected_jobs"'),
        (env_vars_tf, 'resource "dbtcloud_environment_variable" "environment_variables"'),
        (
            env_vars_tf,
            'resource "dbtcloud_environment_variable" "protected_environment_variables"',
        ),
        (globals_tf, 'resource "dbtcloud_global_connection" "connections"'),
        (globals_tf, 'resource "dbtcloud_global_connection" "protected_connections"'),
        (globals_tf, 'resource "dbtcloud_service_token" "service_tokens"'),
        (globals_tf, 'resource "dbtcloud_service_token" "protected_service_tokens"'),
        (globals_tf, 'resource "dbtcloud_group" "groups"'),
        (globals_tf, 'resource "dbtcloud_group" "protected_groups"'),
        (projects_tf, 'resource "dbtcloud_repository" "repositories"'),
        (projects_tf, 'resource "dbtcloud_repository" "protected_repositories"'),
        (projects_tf, 'resource "dbtcloud_project_repository" "project_repositories"'),
        (
            projects_tf,
            'resource "dbtcloud_project_repository" "protected_project_repositories"',
        ),
    ]

    missing = [
        decl for module_file, decl in required_blocks
        if "resource_metadata" not in _resource_block(module_file, decl)
    ]
    assert not missing, f"resource_metadata missing from blocks: {missing}"


def test_resource_metadata_includes_required_identity_fields() -> None:
    modules = [
        MODULES_DIR / "projects.tf",
        MODULES_DIR / "environments.tf",
        MODULES_DIR / "jobs.tf",
        MODULES_DIR / "environment_vars.tf",
        MODULES_DIR / "extended_attributes.tf",
        MODULES_DIR / "globals.tf",
    ]
    required_fields = [
        "source_identity",
        "source_key",
        "source_name",
        "source_id",
    ]

    missing_by_file: dict[str, list[str]] = {}
    for module_file in modules:
        content = module_file.read_text(encoding="utf-8")
        missing_fields = [field for field in required_fields if field not in content]
        if missing_fields:
            missing_by_file[module_file.name] = missing_fields

    assert not missing_by_file, (
        f"Missing required resource_metadata fields: {missing_by_file}"
    )


def test_prf_in_all_maps() -> None:
    """Profiles stay registered across Terraform, state, protection, and UI maps."""
    profiles_tf = MODULES_DIR / "profiles.tf"
    assert profiles_tf.exists(), "Missing modules/projects_v2/profiles.tf"
    assert "resource_metadata" in _resource_block(
        profiles_tf, 'resource "dbtcloud_profile" "profiles"'
    )
    assert "resource_metadata" in _resource_block(
        profiles_tf, 'resource "dbtcloud_profile" "protected_profiles"'
    )

    assert RESOURCE_TYPE_TO_TF["PRF"] == "dbtcloud_profile"
    assert TF_TYPE_TO_CODE["dbtcloud_profile"] == "PRF"
    assert RESOURCE_TYPE_MAP["PRF"] == ("dbtcloud_profile", "profiles", "protected_profiles")
    assert EXTENDED_RESOURCE_TYPE_MAP["PRF"] == ("dbtcloud_profile", "profiles", "protected_profiles")
    assert TYPE_LABELS["PRF"] == "Profile"
    assert MATCH_GRID_TYPE_LABELS["PRF"] == "Profiles"


def test_prf_in_page_contracts() -> None:
    """Profiles are wired into page-level filters, summaries, and destroy labels."""
    mapping_page = (REPO_ROOT / "importer" / "web" / "pages" / "mapping.py").read_text(encoding="utf-8")
    scope_page = (REPO_ROOT / "importer" / "web" / "pages" / "scope.py").read_text(encoding="utf-8")
    deploy_page = (REPO_ROOT / "importer" / "web" / "pages" / "deploy.py").read_text(encoding="utf-8")
    destroy_page = (REPO_ROOT / "importer" / "web" / "pages" / "destroy.py").read_text(encoding="utf-8")
    entity_table = (REPO_ROOT / "importer" / "web" / "components" / "entity_table.py").read_text(encoding="utf-8")

    assert '"PRF": ("profiles", "Profiles")' in mapping_page
    assert '"PRF": ("profiles", "Profiles")' in scope_page
    assert '"PRF": "Profiles"' in deploy_page
    assert '["projects", "environments", "profiles", "jobs", "environment_variables"]' in deploy_page
    assert '"PRF": "dbtcloud_profile"' in destroy_page
    assert 'elif type_code == "PRF":' in entity_table


def test_prf_in_browser_facing_summaries(tmp_path: Path) -> None:
    """Profiles appear in progress, matcher labels, and YAML summary stats."""
    assert ("profiles", "Profiles") in PROJECT_RESOURCES
    assert RESOURCE_TYPE_LABELS["PRF"] == "Profile"

    yaml_path = tmp_path / "profile-summary.yml"
    yaml_path.write_text(
        json.dumps(
            {
                "globals": {},
                "projects": [
                    {
                        "key": "analytics",
                        "environments": [{"key": "prod"}],
                        "profiles": [{"key": "prod_profile"}],
                        "jobs": [],
                        "environment_variables": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    stats = get_yaml_stats(str(yaml_path))
    assert stats["profiles"] == 1
    assert stats["environments"] == 1
