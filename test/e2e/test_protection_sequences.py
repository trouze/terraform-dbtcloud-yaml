"""Sequence tests for protection workflow.

These tests verify complex operation sequences using:
- Explicit scenario tests for critical paths
- State machine model for invariant checking
- Random sequence generation for edge case discovery

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.6 Sequence Tests
"""

import pytest
from typing import List, Tuple, Optional

from helpers import (
    ProtectionWorkflowModel,
    WorkflowState,
    Action,
    StateVerifier,
    TerraformRunner,
)
from helpers.state_machine import (
    generate_random_sequence,
    generate_happy_path_sequence,
    generate_incremental_sequence,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def workflow_model() -> ProtectionWorkflowModel:
    """Create a fresh workflow model."""
    return ProtectionWorkflowModel()


@pytest.fixture
def test_resources() -> List[str]:
    """Sample resource keys for testing."""
    return [
        "PRJ:project_alpha",
        "PRJ:project_beta",
        "REPO:repo_alpha",
        "REPO:repo_beta",
    ]


# =============================================================================
# Explicit Scenario Tests
# =============================================================================

class TestHappyPathScenario:
    """Tests for the standard happy path workflow."""
    
    def test_select_generate_init_plan_apply(self, workflow_model: ProtectionWorkflowModel):
        """Test complete happy path: select → generate → init → plan → apply."""
        model = workflow_model
        
        # Step 1: Select resource for protection
        assert Action.SELECT_PROTECT in model.valid_actions()
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:test_project")
        assert model.state == WorkflowState.INTENT_RECORDED
        assert "PRJ:test_project" in model.pending_intents
        
        # Step 2: Generate changes
        assert Action.GENERATE_CHANGES in model.valid_actions()
        model = model.apply_action(Action.GENERATE_CHANGES)
        assert model.state == WorkflowState.YAML_UPDATED
        assert model.moves_file_exists
        assert "PRJ:test_project" in model.applied_to_yaml
        
        # Step 3: Terraform init
        assert Action.TERRAFORM_INIT in model.valid_actions()
        model = model.apply_action(Action.TERRAFORM_INIT)
        assert model.state == WorkflowState.TF_INITIALIZED
        assert model.tf_initialized
        
        # Step 4: Terraform plan
        assert Action.TERRAFORM_PLAN in model.valid_actions()
        model = model.apply_action(Action.TERRAFORM_PLAN)
        assert model.state == WorkflowState.TF_PLANNED
        assert model.tf_plan_exists
        
        # Step 5: Terraform apply
        assert Action.TERRAFORM_APPLY in model.valid_actions()
        model = model.apply_action(Action.TERRAFORM_APPLY)
        assert model.state == WorkflowState.CLEAN
        assert not model.moves_file_exists
        assert "PRJ:test_project" in model.applied_to_tf
        
        # Verify no invariant violations
        violations = model.check_invariants()
        assert len(violations) == 0, f"Invariant violations: {violations}"
    
    def test_multiple_resources_in_batch(self, workflow_model: ProtectionWorkflowModel):
        """Test protecting multiple resources in one batch."""
        model = workflow_model
        
        # Select multiple resources
        resources = ["PRJ:proj1", "PRJ:proj2", "REPO:repo1"]
        for key in resources:
            model = model.apply_action(Action.SELECT_PROTECT, key)
        
        assert len(model.pending_intents) == 3
        
        # Generate once for all
        model = model.apply_action(Action.GENERATE_CHANGES)
        assert len(model.applied_to_yaml) == 3
        
        # Complete workflow
        model = model.apply_action(Action.TERRAFORM_INIT)
        model = model.apply_action(Action.TERRAFORM_PLAN)
        model = model.apply_action(Action.TERRAFORM_APPLY)
        
        assert model.state == WorkflowState.CLEAN
        assert len(model.applied_to_tf) == 3


class TestIncrementalScenario:
    """Tests for incremental workflow scenarios."""
    
    def test_add_selection_after_generate(self, workflow_model: ProtectionWorkflowModel):
        """Test adding selection after generate invalidates state."""
        model = workflow_model
        
        # First batch
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:proj1")
        model = model.apply_action(Action.GENERATE_CHANGES)
        assert model.state == WorkflowState.YAML_UPDATED
        
        # Add another selection - should go back to INTENT_RECORDED
        model = model.apply_action(Action.ADD_AFTER_GENERATE, "PRJ:proj2")
        assert model.state == WorkflowState.INTENT_RECORDED
        assert "PRJ:proj2" in model.pending_intents
        
        # Need to re-generate
        assert Action.GENERATE_CHANGES in model.valid_actions()
    
    def test_add_selection_after_init(self, workflow_model: ProtectionWorkflowModel):
        """Test adding selection after init returns to INTENT_RECORDED."""
        model = workflow_model
        
        # Progress through init
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:proj1")
        model = model.apply_action(Action.GENERATE_CHANGES)
        model = model.apply_action(Action.TERRAFORM_INIT)
        assert model.state == WorkflowState.TF_INITIALIZED
        
        # Add selection
        model = model.apply_action(Action.ADD_AFTER_GENERATE, "PRJ:proj2")
        assert model.state == WorkflowState.INTENT_RECORDED
    
    def test_add_selection_after_plan(self, workflow_model: ProtectionWorkflowModel):
        """Test adding selection after plan returns to INTENT_RECORDED."""
        model = workflow_model
        
        # Progress through plan
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:proj1")
        model = model.apply_action(Action.GENERATE_CHANGES)
        model = model.apply_action(Action.TERRAFORM_INIT)
        model = model.apply_action(Action.TERRAFORM_PLAN)
        assert model.state == WorkflowState.TF_PLANNED
        
        # Add selection
        model = model.apply_action(Action.ADD_AFTER_GENERATE, "PRJ:proj2")
        assert model.state == WorkflowState.INTENT_RECORDED
    
    def test_two_complete_cycles(self, workflow_model: ProtectionWorkflowModel):
        """Test two complete protection cycles."""
        model = workflow_model
        
        # First cycle
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:proj1")
        model = model.apply_action(Action.GENERATE_CHANGES)
        model = model.apply_action(Action.TERRAFORM_INIT)
        model = model.apply_action(Action.TERRAFORM_PLAN)
        model = model.apply_action(Action.TERRAFORM_APPLY)
        assert model.state == WorkflowState.CLEAN
        assert "PRJ:proj1" in model.applied_to_tf
        
        # Second cycle
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:proj2")
        model = model.apply_action(Action.GENERATE_CHANGES)
        model = model.apply_action(Action.TERRAFORM_INIT)
        model = model.apply_action(Action.TERRAFORM_PLAN)
        model = model.apply_action(Action.TERRAFORM_APPLY)
        assert model.state == WorkflowState.CLEAN
        assert "PRJ:proj2" in model.applied_to_tf


class TestCascadeScenario:
    """Tests for cascading protection scenarios."""
    
    def test_protect_child_with_parent_cascade(self, workflow_model: ProtectionWorkflowModel):
        """Test protecting a child triggers parent cascade awareness."""
        model = workflow_model
        
        # Protect a child resource (conceptually - model doesn't enforce hierarchy)
        model = model.apply_action(Action.SELECT_PROTECT, "ENV:proj1_prod")
        
        # In real application, this would trigger cascade dialog
        # Here we simulate selecting the parent as well
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:proj1")
        
        assert "ENV:proj1_prod" in model.pending_intents
        assert "PRJ:proj1" in model.pending_intents
    
    def test_unprotect_parent_with_children(self, workflow_model: ProtectionWorkflowModel):
        """Test unprotecting parent shows children cascade."""
        model = workflow_model
        
        # First protect parent and children
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:proj1")
        model = model.apply_action(Action.SELECT_PROTECT, "ENV:proj1_dev")
        model = model.apply_action(Action.SELECT_PROTECT, "ENV:proj1_prod")
        
        # Complete first cycle
        model = model.apply_action(Action.GENERATE_CHANGES)
        model = model.apply_action(Action.TERRAFORM_INIT)
        model = model.apply_action(Action.TERRAFORM_PLAN)
        model = model.apply_action(Action.TERRAFORM_APPLY)
        
        # Now unprotect parent
        model = model.apply_action(Action.SELECT_UNPROTECT, "PRJ:proj1")
        # In real app, cascade would show children to unprotect
        
        assert model.state == WorkflowState.INTENT_RECORDED


class TestRecoveryScenario:
    """Tests for recovery from incomplete states."""
    
    def test_reset_from_any_state(self, workflow_model: ProtectionWorkflowModel):
        """Test reset returns to CLEAN from any state."""
        model = workflow_model
        
        # Progress to various states and reset
        states_to_test = [
            [],  # CLEAN
            [Action.SELECT_PROTECT],  # INTENT_RECORDED
            [Action.SELECT_PROTECT, Action.GENERATE_CHANGES],  # YAML_UPDATED
            [Action.SELECT_PROTECT, Action.GENERATE_CHANGES, Action.TERRAFORM_INIT],  # TF_INITIALIZED
            [Action.SELECT_PROTECT, Action.GENERATE_CHANGES, Action.TERRAFORM_INIT, Action.TERRAFORM_PLAN],  # TF_PLANNED
        ]
        
        for actions in states_to_test:
            model = ProtectionWorkflowModel()
            for action in actions:
                if action == Action.SELECT_PROTECT:
                    model = model.apply_action(action, "PRJ:test")
                else:
                    model = model.apply_action(action)
            
            # Reset should always be valid
            assert Action.RESET in model.valid_actions()
            model = model.apply_action(Action.RESET)
            assert model.state == WorkflowState.CLEAN


# =============================================================================
# State Machine Generated Tests
# =============================================================================

class TestRandomSequences:
    """Tests using randomly generated sequences."""
    
    def test_random_sequence_no_invariant_violations(self, test_resources: List[str]):
        """Test that random sequences don't violate invariants."""
        # Generate 10 random sequences with different seeds
        for seed in range(10):
            sequence = generate_random_sequence(
                max_length=15,
                available_resources=test_resources,
                seed=seed,
            )
            
            # Execute sequence and check invariants
            model = ProtectionWorkflowModel()
            
            for action, resource_key in sequence:
                if action in model.valid_actions():
                    model = model.apply_action(action, resource_key)
                    
                    violations = model.check_invariants()
                    assert len(violations) == 0, \
                        f"Invariant violation after {action} (seed={seed}): {violations}\n" \
                        f"History: {model.history}"
    
    def test_happy_path_sequence_succeeds(self, test_resources: List[str]):
        """Test that generated happy path completes successfully."""
        sequence = generate_happy_path_sequence(test_resources[:2])
        
        model = ProtectionWorkflowModel()
        
        for action, resource_key in sequence:
            model = model.apply_action(action, resource_key)
        
        # Should end in CLEAN state
        assert model.state == WorkflowState.CLEAN
        
        # All resources should be in applied_to_tf
        for key in test_resources[:2]:
            assert key in model.applied_to_tf
    
    def test_incremental_sequence_succeeds(self, test_resources: List[str]):
        """Test that incremental sequence completes successfully."""
        sequence = generate_incremental_sequence(test_resources)
        
        model = ProtectionWorkflowModel()
        
        for action, resource_key in sequence:
            model = model.apply_action(action, resource_key)
        
        # Should end in CLEAN state
        assert model.state == WorkflowState.CLEAN


# =============================================================================
# Invariant Tests
# =============================================================================

class TestInvariants:
    """Tests specifically for invariant checking."""
    
    def test_moves_file_implies_not_clean(self):
        """Test: moves_file_exists → state != CLEAN."""
        model = ProtectionWorkflowModel(
            state=WorkflowState.CLEAN,
            moves_file_exists=True,
        )
        
        violations = model.check_invariants()
        assert len(violations) > 0
        assert any("moves_file" in v for v in violations)
    
    def test_plan_implies_init(self):
        """Test: tf_plan_exists → tf_initialized."""
        model = ProtectionWorkflowModel(
            state=WorkflowState.TF_PLANNED,
            tf_plan_exists=True,
            tf_initialized=False,
        )
        
        violations = model.check_invariants()
        assert len(violations) > 0
        assert any("init" in v.lower() for v in violations)
    
    def test_valid_state_has_no_violations(self, workflow_model: ProtectionWorkflowModel):
        """Test that properly constructed states have no violations."""
        model = workflow_model
        
        # Progress through valid states
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:test")
        assert len(model.check_invariants()) == 0
        
        model = model.apply_action(Action.GENERATE_CHANGES)
        assert len(model.check_invariants()) == 0
        
        model = model.apply_action(Action.TERRAFORM_INIT)
        assert len(model.check_invariants()) == 0
        
        model = model.apply_action(Action.TERRAFORM_PLAN)
        assert len(model.check_invariants()) == 0
        
        model = model.apply_action(Action.TERRAFORM_APPLY)
        assert len(model.check_invariants()) == 0


# =============================================================================
# History and Debugging Tests
# =============================================================================

class TestHistoryTracking:
    """Tests for action history tracking."""
    
    def test_history_contains_all_actions(self, workflow_model: ProtectionWorkflowModel):
        """Test that history records all actions."""
        model = workflow_model
        
        actions = [
            (Action.SELECT_PROTECT, "PRJ:test"),
            (Action.GENERATE_CHANGES, None),
            (Action.TERRAFORM_INIT, None),
        ]
        
        for action, key in actions:
            model = model.apply_action(action, key)
        
        assert len(model.history) == 3
        assert "SELECT_PROTECT" in model.history[0]
        assert "GENERATE_CHANGES" in model.history[1]
        assert "TERRAFORM_INIT" in model.history[2]
    
    def test_history_includes_resource_keys(self, workflow_model: ProtectionWorkflowModel):
        """Test that history includes resource keys for select actions."""
        model = workflow_model
        
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:my_project")
        
        assert "PRJ:my_project" in model.history[0]
