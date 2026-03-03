"""Tests for Removal Management utility helpers and step wiring."""

from importer.web.pages.removal_management import (
    _build_candidate_rows_from_inputs,
    _build_refresh_apply_cmd,
    _build_refresh_only_command_preview,
    _build_refresh_plan_cmd,
    _build_refresh_target_addresses_from_rows,
    _build_state_rm_commands_from_rows,
    _collect_missing_terraform_env,
    _filter_removal_rows,
)
from importer.web.state import AppState, WORKFLOW_UTILITIES, WorkflowStep, WorkflowType


def test_build_candidate_rows_dedupes_state_address_and_marks_reasons() -> None:
    reconcile_rows = [
        {
            "element_code": "PRJ",
            "resource_index": "my_project",
            "name": "My Project",
            "tf_name": "projects",
            "address": 'module.dbt_cloud.module.projects_v2[0].dbtcloud_project.projects["my_project"]',
        }
    ]
    confirmed_mappings = [
        {
            "source_key": "my_project",
            "source_type": "PRJ",
            "drift_status": "id_mismatch",
            "state_address": 'module.dbt_cloud.module.projects_v2[0].dbtcloud_project.projects["my_project"]',
        }
    ]
    rows = _build_candidate_rows_from_inputs(
        reconcile_rows=reconcile_rows,
        confirmed_mappings=confirmed_mappings,
        removal_keys={"my_project"},
        orphan_flagged_keys=set(),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["resource_type"] == "PRJ"
    assert row["resource_key"] == "my_project"
    assert row["drift_status"] == "id_mismatch"
    assert row["id_mismatch"] is True
    assert row["suggested_reason"] == "id_mismatch"


def test_build_candidate_rows_marks_orphan_flagged_priority() -> None:
    rows = _build_candidate_rows_from_inputs(
        reconcile_rows=[
            {
                "element_code": "GRP",
                "resource_index": "everyone",
                "name": "Everyone",
                "address": 'module.dbt_cloud.module.projects_v2[0].dbtcloud_group.groups["everyone"]',
            }
        ],
        confirmed_mappings=[],
        removal_keys=set(),
        orphan_flagged_keys={"GRP:everyone"},
    )
    assert len(rows) == 1
    assert rows[0]["orphan_flagged"] is True
    assert rows[0]["suggested_reason"] == "orphan_flagged"


def test_filter_rows_by_type_search_and_toggles() -> None:
    rows = [
        {
            "row_id": "a1",
            "resource_type": "PRJ",
            "resource_key": "alpha_project",
            "resource_name": "Alpha",
            "state_address": "addr.alpha",
            "suggested_reason": "id_mismatch",
            "id_mismatch": True,
            "orphan_flagged": False,
            "has_state_address": True,
        },
        {
            "row_id": "b1",
            "resource_type": "GRP",
            "resource_key": "everyone",
            "resource_name": "Everyone",
            "state_address": "addr.everyone",
            "suggested_reason": "orphan_flagged",
            "id_mismatch": False,
            "orphan_flagged": True,
            "has_state_address": True,
        },
    ]
    filtered = _filter_removal_rows(
        rows=rows,
        filter_state={
            "selected_types": {"GRP"},
            "search": "every",
            "only_id_mismatch": False,
            "only_orphan_flagged": True,
            "only_with_state_address": True,
            "selected_only": False,
        },
        selected_keys={"b1"},
    )
    assert len(filtered) == 1
    assert filtered[0]["resource_type"] == "GRP"
    assert filtered[0]["_selected"] is True


def test_filter_rows_selected_only_uses_selected_keys() -> None:
    rows = [
        {"row_id": "a", "resource_type": "PRJ", "resource_key": "a", "resource_name": "A", "state_address": "addr.a", "suggested_reason": "state_entry", "id_mismatch": False, "orphan_flagged": False, "has_state_address": True},
        {"row_id": "b", "resource_type": "PRJ", "resource_key": "b", "resource_name": "B", "state_address": "addr.b", "suggested_reason": "state_entry", "id_mismatch": False, "orphan_flagged": False, "has_state_address": True},
    ]
    filtered = _filter_removal_rows(
        rows=rows,
        filter_state={
            "selected_types": set(),
            "search": "",
            "only_id_mismatch": False,
            "only_orphan_flagged": False,
            "only_with_state_address": True,
            "selected_only": True,
        },
        selected_keys={"b"},
    )
    assert [row["row_id"] for row in filtered] == ["b"]


def test_build_state_rm_commands_from_rows_dedupes_addresses() -> None:
    commands = _build_state_rm_commands_from_rows(
        [
            {"state_address": "module.foo.bar[\"a\"]"},
            {"state_address": "module.foo.bar[\"a\"]"},
            {"state_address": "module.foo.bar[\"b\"]"},
        ]
    )
    assert commands == [
        "terraform state rm 'module.foo.bar[\"a\"]'",
        "terraform state rm 'module.foo.bar[\"b\"]'",
    ]


def test_build_refresh_target_addresses_from_rows_dedupes_and_skips_blank() -> None:
    addresses = _build_refresh_target_addresses_from_rows(
        [
            {"state_address": "module.foo.bar[\"a\"]"},
            {"state_address": "module.foo.bar[\"a\"]"},
            {"state_address": ""},
            {"state_address": "module.foo.bar[\"b\"]"},
        ]
    )
    assert addresses == [
        "module.foo.bar[\"a\"]",
        "module.foo.bar[\"b\"]",
    ]


def test_build_refresh_only_command_preview_for_all_scope() -> None:
    preview = _build_refresh_only_command_preview([])
    assert preview["plan"] == "terraform plan -refresh-only -no-color -input=false"
    assert preview["apply"] == "terraform apply -refresh-only -auto-approve -no-color -input=false"


def test_build_refresh_only_command_preview_for_selected_scope() -> None:
    preview = _build_refresh_only_command_preview(
        [
            "module.foo.bar[\"a\"]",
            "module.foo.bar[\"b\"]",
        ]
    )
    assert preview["plan"] == (
        "terraform plan -refresh-only -no-color -input=false "
        "-target 'module.foo.bar[\"a\"]' -target 'module.foo.bar[\"b\"]'"
    )
    assert preview["apply"] == (
        "terraform apply -refresh-only -auto-approve -no-color -input=false "
        "-target 'module.foo.bar[\"a\"]' -target 'module.foo.bar[\"b\"]'"
    )


def test_build_refresh_plan_cmd_all_scope() -> None:
    assert _build_refresh_plan_cmd([]) == [
        "terraform",
        "plan",
        "-refresh-only",
        "-no-color",
        "-input=false",
    ]


def test_build_refresh_apply_cmd_selected_scope() -> None:
    assert _build_refresh_apply_cmd(
        [
            "module.foo.bar[\"a\"]",
            "module.foo.bar[\"b\"]",
        ]
    ) == [
        "terraform",
        "apply",
        "-refresh-only",
        "-auto-approve",
        "-no-color",
        "-input=false",
        "-target",
        "module.foo.bar[\"a\"]",
        "-target",
        "module.foo.bar[\"b\"]",
    ]


def test_collect_missing_terraform_env_detects_required_vars() -> None:
    env = {"TF_VAR_dbt_token": "", "TF_VAR_dbt_account_id": "123", "TF_VAR_dbt_host_url": ""}
    missing = _collect_missing_terraform_env(env)
    assert missing == ["TF_VAR_dbt_token", "TF_VAR_dbt_host_url"]


def test_removal_management_step_is_registered_and_accessible() -> None:
    assert WorkflowStep.REMOVAL_MANAGEMENT in WORKFLOW_UTILITIES[WorkflowType.MIGRATION]
    assert WorkflowStep.REMOVAL_MANAGEMENT in WORKFLOW_UTILITIES[WorkflowType.IMPORT_ADOPT]

    state = AppState()
    state.workflow = WorkflowType.MIGRATION
    assert state.step_is_accessible(WorkflowStep.REMOVAL_MANAGEMENT) is True

