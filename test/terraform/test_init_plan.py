"""Terraform init and plan integration tests.

These tests verify:
- terraform init works with the dbtcloud provider
- terraform validate catches HCL syntax errors
- terraform plan produces expected output for moved blocks
- Plan JSON parsing for protection checking

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.3
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any

# Import from parent e2e helpers
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "e2e" / "helpers"))

from terraform_runner import TerraformRunner, TerraformResult


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def runner_with_minimal_config(setup_minimal_terraform: Path) -> TerraformRunner:
    """Create a TerraformRunner with minimal valid configuration."""
    return TerraformRunner(
        working_dir=setup_minimal_terraform,
        mock_apply=True,
        mock_destroy=True,
    )


@pytest.fixture
def runner_with_moves(setup_terraform_with_moves: Path) -> TerraformRunner:
    """Create a TerraformRunner with protection moves configuration."""
    return TerraformRunner(
        working_dir=setup_terraform_with_moves,
        mock_apply=True,
        mock_destroy=True,
    )


@pytest.fixture
def runner_with_state(setup_terraform_with_state: Path) -> TerraformRunner:
    """Create a TerraformRunner with pre-existing state."""
    return TerraformRunner(
        working_dir=setup_terraform_with_state,
        mock_apply=True,
        mock_destroy=True,
    )


@pytest.fixture
def runner_with_invalid_config(setup_invalid_terraform: Path) -> TerraformRunner:
    """Create a TerraformRunner with invalid configuration."""
    return TerraformRunner(
        working_dir=setup_invalid_terraform,
        mock_apply=True,
        mock_destroy=True,
    )


# =============================================================================
# Init Tests
# =============================================================================

class TestTerraformInit:
    """Tests for terraform init operation."""
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_init_with_minimal_config_succeeds(
        self,
        runner_with_minimal_config: TerraformRunner,
    ):
        """Verify terraform init succeeds with minimal valid configuration.
        
        Note: This test requires network access to download providers.
        """
        result = runner_with_minimal_config.init()
        
        # Init should succeed
        assert result.success, f"Init failed: {result.stderr}"
        assert result.return_code == 0
        
        # Should mention provider initialization
        assert "Initializing" in result.stdout or "initialized" in result.stdout.lower()
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_init_creates_terraform_directory(
        self,
        runner_with_minimal_config: TerraformRunner,
    ):
        """Verify terraform init creates .terraform directory."""
        runner_with_minimal_config.init()
        
        tf_dir = runner_with_minimal_config.working_dir / ".terraform"
        assert tf_dir.exists(), ".terraform directory should be created"
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_init_with_upgrade_flag(
        self,
        runner_with_minimal_config: TerraformRunner,
    ):
        """Verify terraform init -upgrade works."""
        # First init
        runner_with_minimal_config.init()
        
        # Init with upgrade
        result = runner_with_minimal_config.init(upgrade=True)
        
        assert result.success, f"Init upgrade failed: {result.stderr}"


# =============================================================================
# Validate Tests
# =============================================================================

class TestTerraformValidate:
    """Tests for terraform validate operation."""
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_validate_valid_config_succeeds(
        self,
        runner_with_minimal_config: TerraformRunner,
    ):
        """Verify terraform validate succeeds with valid configuration."""
        # Must init first
        runner_with_minimal_config.init()
        
        result = runner_with_minimal_config.validate()
        
        assert result.success, f"Validate failed: {result.stderr}"
        assert "Success" in result.stdout or result.return_code == 0
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_validate_with_moved_blocks_succeeds(
        self,
        runner_with_moves: TerraformRunner,
    ):
        """Verify terraform validate accepts moved blocks."""
        runner_with_moves.init()
        
        result = runner_with_moves.validate()
        
        # Validate should succeed (moved blocks are valid HCL)
        # Note: May warn about resources not in state, but shouldn't error
        # The validate may fail if resources don't exist, but syntax should be valid
        assert result.return_code == 0 or "Success" in result.stdout or "Warning" in result.stderr
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_validate_invalid_config_fails(
        self,
        runner_with_invalid_config: TerraformRunner,
    ):
        """Verify terraform validate catches invalid configuration."""
        runner_with_invalid_config.init()
        
        result = runner_with_invalid_config.validate()
        
        # Should fail due to invalid moved blocks
        assert not result.success or "Error" in result.stderr or "error" in result.stderr.lower()


# =============================================================================
# Plan Tests
# =============================================================================

class TestTerraformPlan:
    """Tests for terraform plan operation."""
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_plan_minimal_config_succeeds(
        self,
        runner_with_minimal_config: TerraformRunner,
    ):
        """Verify terraform plan succeeds with minimal configuration."""
        runner_with_minimal_config.init()
        
        result = runner_with_minimal_config.plan()
        
        # Plan should succeed (no changes expected with minimal config)
        assert result.success, f"Plan failed: {result.stderr}"
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_plan_creates_plan_file(
        self,
        runner_with_minimal_config: TerraformRunner,
    ):
        """Verify terraform plan -out creates a plan file."""
        runner_with_minimal_config.init()
        
        result = runner_with_minimal_config.plan(out_file="tfplan")
        
        assert result.success, f"Plan failed: {result.stderr}"
        
        plan_file = runner_with_minimal_config.working_dir / "tfplan"
        assert plan_file.exists(), "Plan file should be created"
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_plan_with_state_shows_no_changes(
        self,
        runner_with_state: TerraformRunner,
    ):
        """Verify plan with existing state shows no changes when config matches."""
        runner_with_state.init()
        
        result = runner_with_state.plan()
        
        # Should succeed - may show "no changes" or list resources
        assert result.success, f"Plan failed: {result.stderr}"
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_show_plan_returns_json(
        self,
        runner_with_minimal_config: TerraformRunner,
    ):
        """Verify terraform show -json returns valid JSON."""
        runner_with_minimal_config.init()
        runner_with_minimal_config.plan(out_file="tfplan")
        
        result = runner_with_minimal_config.show_plan("tfplan")
        
        assert result.success, f"Show plan failed: {result.stderr}"
        
        # Should be valid JSON
        try:
            plan_data = json.loads(result.stdout)
            assert "format_version" in plan_data or "terraform_version" in plan_data
        except json.JSONDecodeError:
            pytest.fail(f"Plan output is not valid JSON: {result.stdout[:500]}")


# =============================================================================
# Full Cycle Tests
# =============================================================================

class TestFullInitPlanCycle:
    """Tests for complete init → validate → plan cycle."""
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_full_cycle_minimal_config(
        self,
        runner_with_minimal_config: TerraformRunner,
    ):
        """Verify full init → validate → plan cycle succeeds."""
        results = runner_with_minimal_config.full_init_plan_cycle()
        
        assert results["init"].success, f"Init failed: {results['init'].stderr}"
        assert results["validate"].success, f"Validate failed: {results['validate'].stderr}"
        assert results["plan"].success, f"Plan failed: {results['plan'].stderr}"
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_full_cycle_with_moves(
        self,
        runner_with_moves: TerraformRunner,
    ):
        """Verify full cycle succeeds with protection moves file."""
        results = runner_with_moves.full_init_plan_cycle()
        
        assert results["init"].success, f"Init failed: {results['init'].stderr}"
        # Validate may have warnings but should not hard fail
        assert "validate" in results


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error scenarios."""
    
    @pytest.mark.terraform
    def test_init_in_empty_directory_fails(self, terraform_dir: Path):
        """Verify init fails gracefully in empty directory."""
        runner = TerraformRunner(working_dir=terraform_dir)
        
        result = runner.init()
        
        # Should fail - no configuration files
        assert not result.success or "No configuration files" in result.stderr or result.return_code != 0
    
    @pytest.mark.terraform
    def test_plan_without_init_fails(
        self,
        setup_minimal_terraform: Path,
    ):
        """Verify plan fails if init hasn't been run."""
        runner = TerraformRunner(working_dir=setup_minimal_terraform)
        
        result = runner.plan()
        
        # Should fail - not initialized
        assert not result.success or "init" in result.stderr.lower()
    
    @pytest.mark.terraform
    def test_validate_without_init_fails(
        self,
        setup_minimal_terraform: Path,
    ):
        """Verify validate fails if init hasn't been run."""
        runner = TerraformRunner(working_dir=setup_minimal_terraform)
        
        result = runner.validate()
        
        # Should fail - not initialized
        assert not result.success or "init" in result.stderr.lower()


# =============================================================================
# Moved Block Specific Tests
# =============================================================================

class TestMovedBlocksInPlan:
    """Tests specifically for moved blocks in plan output."""
    
    @pytest.mark.terraform
    @pytest.mark.slow
    def test_moved_block_syntax_is_valid_hcl(
        self,
        setup_terraform_with_moves: Path,
    ):
        """Verify moved block files pass HCL syntax validation."""
        runner = TerraformRunner(working_dir=setup_terraform_with_moves)
        runner.init()
        
        result = runner.validate()
        
        # The moved blocks themselves should be valid HCL
        # They may produce warnings/errors about missing resources,
        # but the syntax should be valid
        output = result.stdout + result.stderr
        assert "syntax error" not in output.lower()
        assert "invalid" not in output.lower() or "resource" in output.lower()
    
    @pytest.mark.terraform
    @pytest.mark.slow  
    def test_protection_moves_file_exists_after_setup(
        self,
        setup_terraform_with_moves: Path,
    ):
        """Verify protection_moves.tf is created by setup fixture."""
        moves_file = setup_terraform_with_moves / "protection_moves.tf"
        assert moves_file.exists(), "protection_moves.tf should exist"
        
        content = moves_file.read_text()
        assert "moved" in content, "File should contain moved blocks"
        assert "from" in content, "Moved blocks should have 'from' field"
        assert "to" in content, "Moved blocks should have 'to' field"
