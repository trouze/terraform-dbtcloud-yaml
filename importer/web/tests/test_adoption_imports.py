"""Unit tests for adoption import block generation.

Tests for generate_adopt_imports_from_grid(), supports_import_blocks(),
and protected address handling in import blocks.

Reference: PRD 43.01 — Adoption Workflow (Part 1)
Criteria: 1 (UT-AD-01, UT-AD-25), 2 (UT-AD-02), 4 (UT-AD-05), plus UT-AD-10, UT-AD-12
"""

import pytest
from typing import Optional

from importer.web.utils.terraform_import import (
    generate_adopt_imports_from_grid,
    supports_import_blocks,
    RESOURCE_TYPE_TO_TF,
)


# =============================================================================
# Test Fixtures
# =============================================================================


def _make_adopt_row(
    source_type: str,
    source_key: str,
    source_name: str,
    target_id: int,
    project_name: str = "my_project",
    project_id: Optional[int] = None,
    action: str = "adopt",
    protected: bool = False,
) -> dict:
    """Create a minimal grid row dict for testing."""
    row = {
        "source_type": source_type,
        "source_key": source_key,
        "source_name": source_name,
        "target_id": target_id,
        "project_name": project_name,
        "action": action,
        "protected": protected,
    }
    if project_id is not None:
        row["project_id"] = project_id
    return row


@pytest.fixture
def prj_adopt_row() -> dict:
    """A project row with action=adopt."""
    return _make_adopt_row("PRJ", "analytics", "Analytics", 100)


@pytest.fixture
def env_adopt_row() -> dict:
    """An environment row with action=adopt."""
    return _make_adopt_row("ENV", "analytics_prod", "Production", 200, project_name="Analytics")


@pytest.fixture
def job_adopt_row() -> dict:
    """A job row with action=adopt."""
    return _make_adopt_row("JOB", "analytics_daily", "Daily Run", 300, project_name="Analytics")


@pytest.fixture
def rep_adopt_row() -> dict:
    """A repository row with action=adopt (triggers PREP link)."""
    return _make_adopt_row("REP", "analytics_repo", "analytics-repo", 400, project_name="Analytics", project_id=100)


@pytest.fixture
def var_adopt_row() -> dict:
    """An environment variable row with action=adopt."""
    return _make_adopt_row("VAR", "analytics_dbt_target", "DBT_TARGET", 500, project_name="Analytics")


@pytest.fixture
def extattr_adopt_row() -> dict:
    """An extended attributes row with action=adopt."""
    return _make_adopt_row("EXTATTR", "analytics_extattr", "Extended Attrs", 600, project_name="Analytics")


@pytest.fixture
def mixed_grid_rows(prj_adopt_row, env_adopt_row, job_adopt_row) -> list[dict]:
    """Grid with adopt, ignore, and create_new rows."""
    ignore_row = _make_adopt_row("ENV", "marketing_dev", "Dev", 201, action="ignore")
    create_row = _make_adopt_row("JOB", "marketing_daily", "Marketing Daily", 0, action="create_new")
    create_row["target_id"] = None  # create_new has no target_id
    return [prj_adopt_row, env_adopt_row, job_adopt_row, ignore_row, create_row]


# =============================================================================
# UT-AD-01: generate_adopt_imports_from_grid with mixed adopt/ignore rows
# =============================================================================


class TestGenerateAdoptImports:
    """Criterion 1: Import blocks generated only for adopt rows."""

    def test_adopt_rows_produce_import_blocks(self, prj_adopt_row):
        """Adopt rows generate import {} blocks."""
        result = generate_adopt_imports_from_grid([prj_adopt_row])
        assert "import {" in result
        assert '  id = "100"' in result

    def test_ignore_rows_are_excluded(self):
        """Ignore rows do not produce import blocks."""
        ignore_row = _make_adopt_row("ENV", "marketing_dev", "Dev", 201, action="ignore")
        result = generate_adopt_imports_from_grid([ignore_row])
        assert "import {" not in result
        assert "No resources selected" in result

    def test_create_new_rows_are_excluded(self):
        """create_new rows do not produce import blocks."""
        create_row = _make_adopt_row("JOB", "daily", "Daily", 0, action="create_new")
        create_row["target_id"] = None
        result = generate_adopt_imports_from_grid([create_row])
        assert "import {" not in result

    def test_skip_rows_are_excluded(self):
        """skip rows do not produce import blocks."""
        skip_row = _make_adopt_row("JOB", "daily", "Daily", 300, action="skip")
        result = generate_adopt_imports_from_grid([skip_row])
        assert "import {" not in result

    def test_mixed_rows_only_adopt_produces_blocks(self, mixed_grid_rows):
        """In a mixed grid, only adopt rows generate import blocks."""
        result = generate_adopt_imports_from_grid(mixed_grid_rows)
        # 3 adopt rows → 3 import blocks
        assert result.count("import {") == 3
        # Verify specific target IDs are present
        assert '"100"' in result  # PRJ
        assert '"200"' in result  # ENV
        assert '"300"' in result  # JOB

    def test_adopt_row_without_target_id_is_skipped(self):
        """Adopt row with missing target_id is gracefully skipped."""
        row = _make_adopt_row("JOB", "daily", "Daily", 0, action="adopt")
        row["target_id"] = None
        result = generate_adopt_imports_from_grid([row])
        assert "import {" not in result


# =============================================================================
# UT-AD-25: Zero adopt rows produces empty output
# =============================================================================


class TestZeroAdoptRows:
    """Criterion 1 (negative): Empty grid or all-ignore produces no blocks."""

    def test_empty_grid_produces_no_blocks(self):
        """Empty grid produces comment-only output."""
        result = generate_adopt_imports_from_grid([])
        assert "import {" not in result
        assert "No resources selected" in result

    def test_all_ignore_produces_no_blocks(self):
        """All ignore rows produce no import blocks."""
        rows = [
            _make_adopt_row("PRJ", "a", "A", 1, action="ignore"),
            _make_adopt_row("ENV", "b", "B", 2, action="ignore"),
        ]
        result = generate_adopt_imports_from_grid(rows)
        assert "import {" not in result


# =============================================================================
# UT-AD-02: Protected adopt rows use protected_<type> addresses
# =============================================================================


class TestProtectedAdoptAddresses:
    """Criterion 2: Protected rows use protected_<type> Terraform addresses."""

    def test_protected_project_uses_protected_address(self):
        """Protected PRJ row generates import with protected_projects address."""
        row = _make_adopt_row("PRJ", "analytics", "Analytics", 100, protected=True)
        result = generate_adopt_imports_from_grid([row])
        assert "import {" in result
        assert "protected_projects" in result
        assert '"100"' in result

    def test_protected_job_uses_protected_address(self):
        """Protected JOB row generates import with protected_jobs address."""
        row = _make_adopt_row("JOB", "daily_run", "Daily Run", 300, protected=True)
        result = generate_adopt_imports_from_grid([row])
        assert "import {" in result
        assert "protected_jobs" in result

    def test_protected_environment_uses_protected_address(self):
        """Protected ENV row generates import with protected_environments address."""
        row = _make_adopt_row("ENV", "prod", "Production", 200, protected=True)
        result = generate_adopt_imports_from_grid([row])
        assert "import {" in result
        assert "protected_environments" in result

    def test_protected_repository_uses_protected_address(self):
        """Protected REP row generates import with protected_repositories address."""
        row = _make_adopt_row("REP", "my_repo", "my-repo", 400, project_name="Analytics", project_id=100, protected=True)
        result = generate_adopt_imports_from_grid([row])
        assert "import {" in result
        assert "protected_repositories" in result

    def test_unprotected_row_does_not_use_protected_address(self):
        """Non-protected row uses standard address (no protected_ prefix)."""
        row = _make_adopt_row("JOB", "daily", "Daily", 300, protected=False)
        result = generate_adopt_imports_from_grid([row])
        assert "import {" in result
        assert "protected_jobs" not in result

    def test_mixed_protected_and_unprotected(self):
        """Mix of protected and unprotected rows generates correct addresses."""
        rows = [
            _make_adopt_row("JOB", "daily", "Daily", 300, protected=True),
            _make_adopt_row("JOB", "weekly", "Weekly", 301, protected=False),
        ]
        result = generate_adopt_imports_from_grid(rows)
        assert result.count("import {") == 2
        assert "protected_jobs" in result  # for daily (protected)
        # weekly should NOT use protected address
        lines = result.split("\n")
        # Find the block for weekly (target_id=301)
        weekly_block_lines = []
        in_weekly = False
        for line in lines:
            if "301" in line and "id =" in line:
                in_weekly = True
            if in_weekly and "to =" in line:
                assert "protected_" not in line
                break


# =============================================================================
# UT-AD-05: Import block addresses for all resource types
# =============================================================================


class TestResourceTypeAddresses:
    """Criterion 4: All 7 resource types resolve to correct addresses."""

    def test_resource_type_to_tf_includes_all_adoption_types(self):
        """RESOURCE_TYPE_TO_TF includes PRJ, ENV, JOB, REP, PREP, EXTATTR, VAR."""
        required = {"PRJ", "ENV", "JOB", "REP", "PREP", "EXTATTR", "VAR"}
        for code in required:
            assert code in RESOURCE_TYPE_TO_TF, f"{code} missing from RESOURCE_TYPE_TO_TF"

    def test_prj_address_format(self, prj_adopt_row):
        """PRJ resolves to dbtcloud_project address."""
        result = generate_adopt_imports_from_grid([prj_adopt_row])
        assert "dbtcloud_project" in result
        assert "import {" in result

    def test_env_address_format(self, env_adopt_row):
        """ENV resolves to dbtcloud_environment address."""
        result = generate_adopt_imports_from_grid([env_adopt_row])
        assert "dbtcloud_environment" in result

    def test_job_address_format(self, job_adopt_row):
        """JOB resolves to dbtcloud_job address."""
        result = generate_adopt_imports_from_grid([job_adopt_row])
        assert "dbtcloud_job" in result

    def test_rep_address_format(self, rep_adopt_row):
        """REP resolves to dbtcloud_repository address and produces PREP link."""
        result = generate_adopt_imports_from_grid([rep_adopt_row])
        assert "dbtcloud_repository" in result
        # REP with project_id also creates a PREP link import
        assert "dbtcloud_project_repository" in result

    def test_var_address_format(self, var_adopt_row):
        """VAR resolves to dbtcloud_environment_variable address."""
        result = generate_adopt_imports_from_grid([var_adopt_row])
        assert "dbtcloud_environment_variable" in result

    def test_extattr_address_format(self, extattr_adopt_row):
        """EXTATTR resolves to dbtcloud_extended_attributes address."""
        result = generate_adopt_imports_from_grid([extattr_adopt_row])
        assert "dbtcloud_extended_attributes" in result

    def test_prep_address_format(self):
        """PREP resolves to dbtcloud_project_repository address."""
        row = _make_adopt_row("PREP", "analytics_link", "Analytics Link", 700, project_name="Analytics", project_id=100)
        result = generate_adopt_imports_from_grid([row])
        assert "dbtcloud_project_repository" in result


# =============================================================================
# UT-AD-10: supports_import_blocks version detection
# =============================================================================


class TestSupportsImportBlocks:
    """TF version detection for import {} blocks (TF 1.5+)."""

    def test_tf_1_5_0_supported(self):
        assert supports_import_blocks((1, 5, 0)) is True

    def test_tf_1_6_0_supported(self):
        assert supports_import_blocks((1, 6, 0)) is True

    def test_tf_1_9_0_supported(self):
        assert supports_import_blocks((1, 9, 0)) is True

    def test_tf_1_4_6_not_supported(self):
        assert supports_import_blocks((1, 4, 6)) is False

    def test_tf_1_0_0_not_supported(self):
        assert supports_import_blocks((1, 0, 0)) is False

    def test_tf_0_15_0_not_supported(self):
        assert supports_import_blocks((0, 15, 0)) is False

    def test_tf_2_0_0_supported(self):
        assert supports_import_blocks((2, 0, 0)) is True


# =============================================================================
# UT-AD-12: Mixed source-matched and target-only rows
# =============================================================================


# =============================================================================
# UT-AD-06/07: State cross-reference and already-managed exclusion
# =============================================================================


class TestAlreadyManagedExclusion:
    """Criteria 21/23: Already-managed resources excluded from import blocks."""

    def test_in_sync_rows_excluded_from_imports(self):
        """Rows with drift_status=in_sync are action=match, not adopt → excluded."""
        # An in-sync row has action=match, not adopt
        in_sync_row = _make_adopt_row("PRJ", "analytics", "Analytics", 100, action="match")
        result = generate_adopt_imports_from_grid([in_sync_row])
        assert "import {" not in result

    def test_adopt_rows_with_in_sync_drift_excluded(self):
        """Rows with action=adopt but drift_status=in_sync are excluded (UT-AD-06)."""
        # Edge case: user marked adopt but resource is already in sync
        already_managed_row = _make_adopt_row("PRJ", "analytics", "Analytics", 100)
        already_managed_row["drift_status"] = "in_sync"
        already_managed_row["state_id"] = 100
        already_managed_row["state_address"] = 'module.dbt_cloud.dbtcloud_project.projects["analytics"]'
        result = generate_adopt_imports_from_grid([already_managed_row])
        assert "import {" not in result

    def test_adopt_rows_with_id_mismatch_drift_included(self):
        """Rows with action=adopt and drift_status=id_mismatch are included (UT-AD-07)."""
        mismatch_row = _make_adopt_row("PRJ", "analytics", "Analytics", 100)
        mismatch_row["drift_status"] = "id_mismatch"
        mismatch_row["state_id"] = 99  # Different from target_id
        result = generate_adopt_imports_from_grid([mismatch_row])
        assert "import {" in result
        assert '"100"' in result

    def test_adopt_rows_with_not_in_state_drift_included(self):
        """Rows with drift_status=not_in_state are included (normal adopt)."""
        normal_row = _make_adopt_row("PRJ", "analytics", "Analytics", 100)
        normal_row["drift_status"] = "not_in_state"
        result = generate_adopt_imports_from_grid([normal_row])
        assert "import {" in result

    def test_adopt_rows_with_no_state_drift_included(self):
        """Rows with drift_status=no_state (no TF state loaded) are included."""
        no_state_row = _make_adopt_row("PRJ", "analytics", "Analytics", 100)
        no_state_row["drift_status"] = "no_state"
        result = generate_adopt_imports_from_grid([no_state_row])
        assert "import {" in result

    def test_mixed_in_sync_and_not_in_state(self):
        """Only non-in_sync adopt rows produce import blocks."""
        in_sync_row = _make_adopt_row("PRJ", "analytics", "Analytics", 100)
        in_sync_row["drift_status"] = "in_sync"
        in_sync_row["state_id"] = 100
        
        not_in_state_row = _make_adopt_row("ENV", "prod", "Production", 200)
        not_in_state_row["drift_status"] = "not_in_state"
        
        result = generate_adopt_imports_from_grid([in_sync_row, not_in_state_row])
        assert "import {" in result
        # Only the environment import block should be present
        assert '"200"' in result
        assert '"100"' not in result


class TestMixedSourceAndTargetOnlyRows:
    """Criterion 10: Import blocks for mixed source-matched and target-only adopt rows."""

    def test_source_matched_and_target_only_both_produce_blocks(self):
        """Both source-matched and target-only adopt rows generate import blocks."""
        source_matched_row = _make_adopt_row(
            "JOB", "analytics_daily", "Daily Run", 300,
            project_name="Analytics",
        )
        target_only_row = _make_adopt_row(
            "JOB", "target__legacy_sync", "Legacy Sync", 301,
            project_name="Legacy",
        )
        target_only_row["is_target_only"] = True

        result = generate_adopt_imports_from_grid([source_matched_row, target_only_row])
        assert result.count("import {") == 2
        assert '"300"' in result
        assert '"301"' in result

    def test_target_only_with_ignore_excluded(self):
        """Target-only rows with action=ignore are excluded."""
        target_only_ignore = _make_adopt_row(
            "JOB", "target__old_job", "Old Job", 302, action="ignore",
        )
        target_only_ignore["is_target_only"] = True
        target_only_adopt = _make_adopt_row(
            "JOB", "target__new_job", "New Job", 303,
        )
        target_only_adopt["is_target_only"] = True

        result = generate_adopt_imports_from_grid([target_only_ignore, target_only_adopt])
        assert result.count("import {") == 1
        assert '"303"' in result
        assert '"302"' not in result


# =============================================================================
# UT-AD-04: Moved blocks for protection status changes
# =============================================================================


class TestProtectionMovedBlocks:
    """Criterion 29: generate_moved_blocks produces correct HCL for adoption protection."""

    def test_protect_generates_moved_block(self):
        """UT-AD-04: Protecting a resource generates a moved block from normal → protected."""
        from importer.web.utils.protection_manager import ProtectionChange, generate_moved_blocks
        
        change = ProtectionChange(
            resource_key="PRJ:analytics",
            resource_type="PRJ",
            name="analytics",
            direction="protect",
            from_address='module.dbt_cloud.dbtcloud_project.projects["analytics"]',
            to_address='module.dbt_cloud.dbtcloud_project.protected_projects["analytics"]',
        )
        result = generate_moved_blocks([change])
        assert "moved {" in result
        assert 'from = module.dbt_cloud.dbtcloud_project.projects["analytics"]' in result
        assert 'to   = module.dbt_cloud.dbtcloud_project.protected_projects["analytics"]' in result

    def test_unprotect_generates_moved_block(self):
        """Unprotecting a resource generates a moved block from protected → normal."""
        from importer.web.utils.protection_manager import ProtectionChange, generate_moved_blocks
        
        change = ProtectionChange(
            resource_key="ENV:production",
            resource_type="ENV",
            name="production",
            direction="unprotect",
            from_address='module.dbt_cloud.dbtcloud_environment.protected_environments["production"]',
            to_address='module.dbt_cloud.dbtcloud_environment.environments["production"]',
        )
        result = generate_moved_blocks([change])
        assert "moved {" in result
        assert "protected_environments" in result
        assert 'to   = module.dbt_cloud.dbtcloud_environment.environments["production"]' in result

    def test_no_changes_returns_empty(self):
        """No protection changes returns empty string."""
        from importer.web.utils.protection_manager import generate_moved_blocks
        
        result = generate_moved_blocks([])
        assert result == ""

    def test_multiple_changes(self):
        """Multiple changes produce multiple moved blocks."""
        from importer.web.utils.protection_manager import ProtectionChange, generate_moved_blocks
        
        changes = [
            ProtectionChange(
                resource_key="PRJ:a",
                resource_type="PRJ",
                name="a",
                direction="protect",
                from_address='module.dbt_cloud.dbtcloud_project.projects["a"]',
                to_address='module.dbt_cloud.dbtcloud_project.protected_projects["a"]',
            ),
            ProtectionChange(
                resource_key="JOB:b",
                resource_type="JOB",
                name="b",
                direction="protect",
                from_address='module.dbt_cloud.dbtcloud_job.jobs["b"]',
                to_address='module.dbt_cloud.dbtcloud_job.protected_jobs["b"]',
            ),
        ]
        result = generate_moved_blocks(changes)
        assert result.count("moved {") == 2
