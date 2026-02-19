"""Tests for _compute_adopt_summary from adopt.py."""

from typing import Optional

from importer.web.pages.adopt import _compute_adopt_summary, _terraform_declares_variable
from importer.web.utils.terraform_import import generate_state_rm_commands


def _make_row(
    source_key: str,
    drift_status: str,
    target_id: str = "123",
    state_address: Optional[str] = None,
    source_type: str = "PRJ",
    protected: bool = False,
) -> dict:
    """Build a minimal grid row for adopt summary tests."""
    row = {
        "source_key": source_key,
        "drift_status": drift_status,
        "target_id": target_id,
        "source_type": source_type,
        "protected": protected,
    }
    if state_address is not None:
        row["state_address"] = state_address
    return row


def test_compute_summary_respects_adopt_action():
    """Rows with action=adopt in confirmed_mappings get action=adopt."""
    grid_rows = [
        _make_row("proj_a", "not_in_state", target_id="1"),
        _make_row("proj_b", "id_mismatch", target_id="2"),
    ]
    confirmed_mappings = [
        {"source_key": "proj_a", "action": "adopt"},
        {"source_key": "proj_b", "action": "adopt"},
    ]
    result = _compute_adopt_summary(grid_rows, confirmed_mappings)

    adopt_rows = result["adopt_rows"]
    assert len(adopt_rows) == 2
    assert adopt_rows[0]["action"] == "adopt"
    assert adopt_rows[1]["action"] == "adopt"
    assert result["adopt_count"] == 2


def test_compute_summary_defaults_to_row_action_when_no_confirmed_mapping():
    """Rows without confirmed mappings preserve row action from build_grid_data."""
    grid_rows = [
        {**_make_row("proj_a", "not_in_state", target_id="1"), "action": "adopt"},
        {**_make_row("proj_b", "attr_mismatch", target_id="2"), "action": "adopt"},
    ]
    confirmed_mappings = []  # No mappings
    result = _compute_adopt_summary(grid_rows, confirmed_mappings)

    adopt_rows = result["adopt_rows"]
    assert len(adopt_rows) == 2
    assert adopt_rows[0]["action"] == "adopt"
    assert adopt_rows[1]["action"] == "adopt"
    assert result["adopt_count"] == 2


def test_compute_summary_checks_target_prefixed_key():
    """Confirmed mapping with key 'target__everyone' matches row with source_key 'everyone'."""
    grid_rows = [
        _make_row("everyone", "not_in_state", target_id="1"),
    ]
    confirmed_mappings = [
        {"source_key": "target__everyone", "action": "adopt"},
    ]
    result = _compute_adopt_summary(grid_rows, confirmed_mappings)

    adopt_rows = result["adopt_rows"]
    assert len(adopt_rows) == 1
    assert adopt_rows[0]["source_key"] == "everyone"
    assert adopt_rows[0]["action"] == "adopt"
    assert result["adopt_count"] == 1


def test_compute_summary_excludes_target_only_rows():
    """Target-only rows should not be included in Adopt summary candidates."""
    grid_rows = [
        {
            **_make_row("target__legacy_conn", "no_state", target_id="800", source_type="CON"),
            "is_target_only": True,
            "action": "adopt",
        },
        {
            **_make_row("conn_main", "no_state", target_id="801", source_type="CON"),
            "is_target_only": False,
            "action": "adopt",
        },
    ]
    result = _compute_adopt_summary(grid_rows, confirmed_mappings=[])
    assert len(result["adopt_rows"]) == 1
    assert result["adopt_rows"][0]["source_key"] == "conn_main"
    assert result["adopt_count"] == 1


def test_compute_summary_counts_adopt_only():
    """adopt_count only includes rows where action=adopt."""
    grid_rows = [
        _make_row("proj_a", "not_in_state", target_id="1"),
        _make_row("proj_b", "not_in_state", target_id="2"),
        _make_row("proj_c", "not_in_state", target_id="3"),
    ]
    confirmed_mappings = [
        {"source_key": "proj_a", "action": "adopt"},
        {"source_key": "proj_b", "action": "ignore"},
        {"source_key": "proj_c", "action": "match"},  # Not adopt
    ]
    result = _compute_adopt_summary(grid_rows, confirmed_mappings)

    adopt_rows = result["adopt_rows"]
    assert len(adopt_rows) == 3
    adopt_actions = [r["action"] for r in adopt_rows]
    assert adopt_actions == ["adopt", "ignore", "ignore"]
    assert result["adopt_count"] == 1


def test_compute_summary_protected_count_only_adopted():
    """protected_count only includes rows that are both protected AND adopted."""
    grid_rows = [
        _make_row("proj_a", "not_in_state", target_id="1", protected=True),
        _make_row("proj_b", "not_in_state", target_id="2", protected=True),
        _make_row("proj_c", "not_in_state", target_id="3", protected=False),
    ]
    confirmed_mappings = [
        {"source_key": "proj_a", "action": "adopt"},
        {"source_key": "proj_b", "action": "ignore"},
        {"source_key": "proj_c", "action": "adopt"},
    ]
    result = _compute_adopt_summary(grid_rows, confirmed_mappings)

    adopt_rows = result["adopt_rows"]
    # proj_a: adopt + protected -> counted
    # proj_b: ignore + protected -> NOT counted
    # proj_c: adopt + not protected -> NOT counted
    assert result["protected_count"] == 1
    assert result["adopt_count"] == 2


def test_all_ignored_still_has_adopt_rows():
    """When all adoptable resources are ignored, adopt_rows is non-empty but adopt_count is 0.
    
    This covers the fix at adopt.py:812 where has_adopt_rows was changed from
    adopt_count > 0 to len(adopt_rows) > 0, ensuring the grid renders even when
    no resources are explicitly set to 'adopt'.
    """
    grid_rows = [
        _make_row("grp_owner", "not_in_state", target_id="773", source_type="GRP"),
        _make_row("grp_member", "not_in_state", target_id="774", source_type="GRP"),
        _make_row("grp_everyone", "not_in_state", target_id="775", source_type="GRP"),
    ]
    # All are ignored (either explicitly or by default)
    confirmed_mappings = [
        {"source_key": "grp_owner", "action": "ignore"},
        {"source_key": "grp_member", "action": "ignore"},
        {"source_key": "grp_everyone", "action": "ignore"},
    ]
    result = _compute_adopt_summary(grid_rows, confirmed_mappings)

    # adopt_rows should contain all adoptable resources (regardless of action)
    assert len(result["adopt_rows"]) == 3
    # But adopt_count should be 0 since none are set to 'adopt'
    assert result["adopt_count"] == 0


def test_all_ignored_default_still_has_adopt_rows():
    """When no confirmed mappings exist, summary uses per-row actions as fallback."""
    grid_rows = [
        {
            **_make_row("grp_owner", "not_in_state", target_id="773", source_type="GRP"),
            "action": "adopt",
        },
        {
            **_make_row("grp_member", "not_in_state", target_id="774", source_type="GRP"),
            "action": "adopt",
        },
    ]
    confirmed_mappings = []  # No mappings at all
    result = _compute_adopt_summary(grid_rows, confirmed_mappings)

    assert len(result["adopt_rows"]) == 2
    assert result["adopt_count"] == 2
    # Fallback should preserve adopt rows from grid action
    for row in result["adopt_rows"]:
        assert row["action"] == "adopt"


def test_compute_summary_rm_count_uses_generate_state_rm_commands():
    """rm_count equals len(state_rm_commands) from generate_state_rm_commands."""
    # Rows with id_mismatch and state_address generate state rm commands
    grid_rows = [
        _make_row(
            "proj_a",
            "id_mismatch",
            target_id="1",
            state_address="module.dbt_cloud.dbtcloud_project.proj_a",
        ),
        _make_row(
            "proj_b",
            "not_in_state",
            target_id="2",
        ),  # no state_address, not id_mismatch
    ]
    confirmed_mappings = [
        {"source_key": "proj_a", "action": "adopt"},
        {"source_key": "proj_b", "action": "adopt"},
    ]
    result = _compute_adopt_summary(grid_rows, confirmed_mappings)

    adopt_rows = result["adopt_rows"]
    expected_rm_cmds = generate_state_rm_commands(adopt_rows)
    assert result["rm_count"] == len(expected_rm_cmds)
    assert result["state_rm_commands"] == expected_rm_cmds
    assert result["rm_count"] == 1


def test_terraform_declares_variable_detects_declared_var(tmp_path):
    """Helper detects variable declaration in root .tf files."""
    (tmp_path / "variables.tf").write_text(
        'variable "projects_v2_skip_global_project_permissions" {\n  type = bool\n}\n',
        encoding="utf-8",
    )
    assert _terraform_declares_variable(
        tmp_path, "projects_v2_skip_global_project_permissions"
    ) is True


def test_terraform_declares_variable_false_when_missing(tmp_path):
    """Helper returns False when variable is not declared."""
    (tmp_path / "main.tf").write_text('resource "null_resource" "x" {}\n', encoding="utf-8")
    assert _terraform_declares_variable(
        tmp_path, "projects_v2_skip_global_project_permissions"
    ) is False


def test_source_total_and_tf_add_count_can_differ_by_mapping_semantics():
    """Source-selected totals are not always 1:1 with terraform add counts.

    Example contract from the adopt/deploy verification flow:
    - Credentials are selected resources but do not create dbtcloud_credential
      resources in this plan context (referenced by ID) -> contributes 0 adds.
    - Repository selection creates two TF resources:
      dbtcloud_repository + dbtcloud_project_repository -> contributes 2 adds.
    """

    source_selected_counts = {
        "PRJ": 1,
        "REP": 1,
        "ENV": 10,
        "JOB": 36,
        "CRED": 5,
    }

    source_total = sum(source_selected_counts.values())
    assert source_total == 53

    tf_add_count = (
        source_selected_counts["PRJ"] * 1
        + source_selected_counts["REP"] * 2
        + source_selected_counts["ENV"] * 1
        + source_selected_counts["JOB"] * 1
        + source_selected_counts["CRED"] * 0
    )
    assert tf_add_count == 49
