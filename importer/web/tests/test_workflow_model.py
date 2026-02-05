"""Unit tests for the Protection Workflow State Machine Model.

This module tests the WorkflowModel which represents the protection workflow
as a finite state machine with:
- States: Clean, IntentRecorded, YamlUpdated, TfInitialized, TfPlanned, TfApplied
- Actions: select_protect, select_unprotect, generate_changes, terraform_init, etc.
- Invariants: Properties that must always hold true

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.5
"""

import pytest
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Set, Optional, Dict
from copy import deepcopy


# =============================================================================
# State Machine Model
# =============================================================================

class WorkflowState(Enum):
    """States in the protection workflow."""
    CLEAN = auto()              # No pending changes
    INTENT_RECORDED = auto()    # User has selected resources, not yet generated
    YAML_UPDATED = auto()       # Generate completed, YAML and moves file updated
    TF_INITIALIZED = auto()     # terraform init completed
    TF_PLANNED = auto()         # terraform plan completed
    TF_APPLIED = auto()         # terraform apply completed (transitions to CLEAN)


class Action(Enum):
    """Actions that can be performed in the workflow."""
    SELECT_PROTECT = auto()     # Mark a resource for protection
    SELECT_UNPROTECT = auto()   # Mark a resource for unprotection
    GENERATE_CHANGES = auto()   # Generate YAML and TF moves
    TERRAFORM_INIT = auto()     # Run terraform init
    TERRAFORM_PLAN = auto()     # Run terraform plan
    TERRAFORM_APPLY = auto()    # Run terraform apply
    ADD_AFTER_GENERATE = auto() # Add new selection after generate (invalidates)
    RESET = auto()              # Reset to clean state


@dataclass
class ProtectionWorkflowModel:
    """State machine model for the protection workflow.
    
    This models the complete lifecycle of protection changes:
    1. User selects resources to protect/unprotect (INTENT_RECORDED)
    2. User generates changes (YAML_UPDATED)
    3. User runs terraform init (TF_INITIALIZED)
    4. User runs terraform plan (TF_PLANNED)
    5. User runs terraform apply (TF_APPLIED → CLEAN)
    
    Attributes:
        state: Current workflow state
        pending_intents: Resources with recorded but unapplied intent
        applied_to_yaml: Resources whose intent has been applied to YAML
        moves_file_exists: Whether protection_moves.tf exists
        tf_initialized: Whether terraform has been initialized
        tf_plan_exists: Whether a plan file exists
    """
    
    state: WorkflowState = WorkflowState.CLEAN
    pending_intents: Set[str] = field(default_factory=set)
    applied_to_yaml: Set[str] = field(default_factory=set)
    moves_file_exists: bool = False
    tf_initialized: bool = False
    tf_plan_exists: bool = False
    history: List[str] = field(default_factory=list)
    
    # Track intent protection status
    intent_protected: Dict[str, bool] = field(default_factory=dict)
    
    def valid_actions(self) -> List[Action]:
        """Get actions valid from current state."""
        actions = []
        
        # Can always select resources to protect/unprotect
        actions.append(Action.SELECT_PROTECT)
        actions.append(Action.SELECT_UNPROTECT)
        
        if self.state == WorkflowState.CLEAN:
            # No other actions from clean state
            pass
        
        elif self.state == WorkflowState.INTENT_RECORDED:
            # Can generate changes
            actions.append(Action.GENERATE_CHANGES)
        
        elif self.state == WorkflowState.YAML_UPDATED:
            # Can run terraform init, or add more selections (invalidates)
            actions.append(Action.TERRAFORM_INIT)
            actions.append(Action.ADD_AFTER_GENERATE)
        
        elif self.state == WorkflowState.TF_INITIALIZED:
            # Can run terraform plan, or add more selections (invalidates)
            actions.append(Action.TERRAFORM_PLAN)
            actions.append(Action.ADD_AFTER_GENERATE)
        
        elif self.state == WorkflowState.TF_PLANNED:
            # Can run terraform apply, or add more selections (invalidates)
            actions.append(Action.TERRAFORM_APPLY)
            actions.append(Action.ADD_AFTER_GENERATE)
        
        elif self.state == WorkflowState.TF_APPLIED:
            # Transition to CLEAN happens automatically
            pass
        
        # Can always reset
        actions.append(Action.RESET)
        
        return actions
    
    def apply_action(self, action: Action, resource_key: Optional[str] = None) -> 'ProtectionWorkflowModel':
        """Apply action and return new state.
        
        Args:
            action: The action to perform
            resource_key: Resource key for select actions
            
        Returns:
            New model with updated state
            
        Raises:
            ValueError: If action is not valid from current state
        """
        if action not in self.valid_actions():
            raise ValueError(f"Action {action} not valid from state {self.state}")
        
        # Create a copy for immutability
        new_model = ProtectionWorkflowModel(
            state=self.state,
            pending_intents=set(self.pending_intents),
            applied_to_yaml=set(self.applied_to_yaml),
            moves_file_exists=self.moves_file_exists,
            tf_initialized=self.tf_initialized,
            tf_plan_exists=self.tf_plan_exists,
            history=list(self.history),
            intent_protected=dict(self.intent_protected),
        )
        
        if action == Action.SELECT_PROTECT:
            if resource_key:
                new_model.pending_intents.add(resource_key)
                new_model.intent_protected[resource_key] = True
            if new_model.state == WorkflowState.CLEAN:
                new_model.state = WorkflowState.INTENT_RECORDED
            new_model.history.append(f"SELECT_PROTECT({resource_key})")
        
        elif action == Action.SELECT_UNPROTECT:
            if resource_key:
                new_model.pending_intents.add(resource_key)
                new_model.intent_protected[resource_key] = False
            if new_model.state == WorkflowState.CLEAN:
                new_model.state = WorkflowState.INTENT_RECORDED
            new_model.history.append(f"SELECT_UNPROTECT({resource_key})")
        
        elif action == Action.GENERATE_CHANGES:
            new_model.applied_to_yaml = new_model.applied_to_yaml.union(new_model.pending_intents)
            new_model.pending_intents = set()
            new_model.moves_file_exists = True
            new_model.state = WorkflowState.YAML_UPDATED
            new_model.history.append("GENERATE_CHANGES")
        
        elif action == Action.TERRAFORM_INIT:
            new_model.tf_initialized = True
            new_model.state = WorkflowState.TF_INITIALIZED
            new_model.history.append("TERRAFORM_INIT")
        
        elif action == Action.TERRAFORM_PLAN:
            new_model.tf_plan_exists = True
            new_model.state = WorkflowState.TF_PLANNED
            new_model.history.append("TERRAFORM_PLAN")
        
        elif action == Action.TERRAFORM_APPLY:
            # Apply completes - moves file removed, state is clean
            new_model.moves_file_exists = False
            new_model.tf_plan_exists = False
            new_model.state = WorkflowState.CLEAN
            new_model.history.append("TERRAFORM_APPLY")
        
        elif action == Action.ADD_AFTER_GENERATE:
            # Adding selection after generate invalidates the current state
            if resource_key:
                new_model.pending_intents.add(resource_key)
            new_model.state = WorkflowState.INTENT_RECORDED
            new_model.history.append(f"ADD_AFTER_GENERATE({resource_key})")
        
        elif action == Action.RESET:
            new_model = ProtectionWorkflowModel()
            new_model.history = list(self.history)
            new_model.history.append("RESET")
        
        return new_model
    
    def check_invariants(self) -> List[str]:
        """Check all invariants, return list of violations.
        
        Returns:
            List of invariant violation messages (empty if all pass)
        """
        violations = []
        
        # Invariant 1: No duplicate intents (set guarantees this)
        # Already enforced by using Set
        
        # Invariant 2: If moves_file_exists, state should be YAML_UPDATED or later
        if self.moves_file_exists and self.state == WorkflowState.CLEAN:
            violations.append("Invariant: moves_file_exists but state is CLEAN")
        
        # Invariant 3: If tf_plan_exists, should have been initialized
        if self.tf_plan_exists and not self.tf_initialized:
            violations.append("Invariant: tf_plan_exists but not initialized")
        
        # Invariant 4: If state is INTENT_RECORDED, must have pending_intents OR have just gone back
        # (This is a soft invariant - can be empty if all were just generated)
        
        # Invariant 5: applied_to_yaml ⊆ all_intents
        # (Resources can only be applied if they were selected)
        
        # Invariant 6: State consistency
        if self.state == WorkflowState.TF_PLANNED and not self.tf_plan_exists:
            violations.append("Invariant: state is TF_PLANNED but no plan exists")
        
        if self.state == WorkflowState.TF_INITIALIZED and not self.tf_initialized:
            violations.append("Invariant: state is TF_INITIALIZED but tf_initialized is False")
        
        return violations


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def clean_model():
    """Return a fresh model in CLEAN state."""
    return ProtectionWorkflowModel()


@pytest.fixture
def intent_recorded_model():
    """Return a model with intent recorded."""
    model = ProtectionWorkflowModel()
    return model.apply_action(Action.SELECT_PROTECT, "PRJ:my_project")


@pytest.fixture
def yaml_updated_model(intent_recorded_model):
    """Return a model with YAML updated."""
    return intent_recorded_model.apply_action(Action.GENERATE_CHANGES)


@pytest.fixture
def tf_initialized_model(yaml_updated_model):
    """Return a model with terraform initialized."""
    return yaml_updated_model.apply_action(Action.TERRAFORM_INIT)


@pytest.fixture
def tf_planned_model(tf_initialized_model):
    """Return a model with terraform plan complete."""
    return tf_initialized_model.apply_action(Action.TERRAFORM_PLAN)


# =============================================================================
# Tests: State Transitions
# =============================================================================

class TestStateTransitions:
    """Tests for valid state transitions."""
    
    def test_clean_to_intent_recorded(self, clean_model):
        """Test transition from CLEAN to INTENT_RECORDED via select."""
        new_model = clean_model.apply_action(Action.SELECT_PROTECT, "PRJ:test")
        
        assert new_model.state == WorkflowState.INTENT_RECORDED
        assert "PRJ:test" in new_model.pending_intents
    
    def test_intent_recorded_to_yaml_updated(self, intent_recorded_model):
        """Test transition from INTENT_RECORDED to YAML_UPDATED via generate."""
        new_model = intent_recorded_model.apply_action(Action.GENERATE_CHANGES)
        
        assert new_model.state == WorkflowState.YAML_UPDATED
        assert new_model.moves_file_exists is True
        assert len(new_model.pending_intents) == 0
    
    def test_yaml_updated_to_initialized(self, yaml_updated_model):
        """Test transition from YAML_UPDATED to TF_INITIALIZED."""
        new_model = yaml_updated_model.apply_action(Action.TERRAFORM_INIT)
        
        assert new_model.state == WorkflowState.TF_INITIALIZED
        assert new_model.tf_initialized is True
    
    def test_initialized_to_planned(self, tf_initialized_model):
        """Test transition from TF_INITIALIZED to TF_PLANNED."""
        new_model = tf_initialized_model.apply_action(Action.TERRAFORM_PLAN)
        
        assert new_model.state == WorkflowState.TF_PLANNED
        assert new_model.tf_plan_exists is True
    
    def test_planned_to_applied_to_clean(self, tf_planned_model):
        """Test transition from TF_PLANNED to CLEAN via apply."""
        new_model = tf_planned_model.apply_action(Action.TERRAFORM_APPLY)
        
        assert new_model.state == WorkflowState.CLEAN
        assert new_model.moves_file_exists is False
        assert new_model.tf_plan_exists is False
    
    def test_add_after_generate_invalidates(self, yaml_updated_model):
        """Test that adding selection after generate returns to INTENT_RECORDED."""
        new_model = yaml_updated_model.apply_action(Action.ADD_AFTER_GENERATE, "PRJ:another")
        
        assert new_model.state == WorkflowState.INTENT_RECORDED
        assert "PRJ:another" in new_model.pending_intents


# =============================================================================
# Tests: Valid Actions
# =============================================================================

class TestValidActions:
    """Tests for valid_actions in each state."""
    
    def test_clean_state_actions(self, clean_model):
        """Test valid actions in CLEAN state."""
        actions = clean_model.valid_actions()
        
        assert Action.SELECT_PROTECT in actions
        assert Action.SELECT_UNPROTECT in actions
        assert Action.RESET in actions
        assert Action.GENERATE_CHANGES not in actions
        assert Action.TERRAFORM_APPLY not in actions
    
    def test_intent_recorded_actions(self, intent_recorded_model):
        """Test valid actions in INTENT_RECORDED state."""
        actions = intent_recorded_model.valid_actions()
        
        assert Action.SELECT_PROTECT in actions
        assert Action.SELECT_UNPROTECT in actions
        assert Action.GENERATE_CHANGES in actions
        assert Action.TERRAFORM_INIT not in actions
    
    def test_yaml_updated_actions(self, yaml_updated_model):
        """Test valid actions in YAML_UPDATED state."""
        actions = yaml_updated_model.valid_actions()
        
        assert Action.TERRAFORM_INIT in actions
        assert Action.ADD_AFTER_GENERATE in actions
        assert Action.TERRAFORM_PLAN not in actions
    
    def test_tf_initialized_actions(self, tf_initialized_model):
        """Test valid actions in TF_INITIALIZED state."""
        actions = tf_initialized_model.valid_actions()
        
        assert Action.TERRAFORM_PLAN in actions
        assert Action.ADD_AFTER_GENERATE in actions
        assert Action.TERRAFORM_APPLY not in actions
    
    def test_tf_planned_actions(self, tf_planned_model):
        """Test valid actions in TF_PLANNED state."""
        actions = tf_planned_model.valid_actions()
        
        assert Action.TERRAFORM_APPLY in actions
        assert Action.ADD_AFTER_GENERATE in actions


# =============================================================================
# Tests: Invalid Actions
# =============================================================================

class TestInvalidActions:
    """Tests for rejection of invalid actions."""
    
    def test_cannot_generate_from_clean(self, clean_model):
        """Test that GENERATE_CHANGES fails from CLEAN state."""
        with pytest.raises(ValueError, match="not valid"):
            clean_model.apply_action(Action.GENERATE_CHANGES)
    
    def test_cannot_init_from_clean(self, clean_model):
        """Test that TERRAFORM_INIT fails from CLEAN state."""
        with pytest.raises(ValueError, match="not valid"):
            clean_model.apply_action(Action.TERRAFORM_INIT)
    
    def test_cannot_plan_from_intent_recorded(self, intent_recorded_model):
        """Test that TERRAFORM_PLAN fails from INTENT_RECORDED state."""
        with pytest.raises(ValueError, match="not valid"):
            intent_recorded_model.apply_action(Action.TERRAFORM_PLAN)
    
    def test_cannot_apply_from_initialized(self, tf_initialized_model):
        """Test that TERRAFORM_APPLY fails from TF_INITIALIZED state."""
        with pytest.raises(ValueError, match="not valid"):
            tf_initialized_model.apply_action(Action.TERRAFORM_APPLY)


# =============================================================================
# Tests: Invariant Checking
# =============================================================================

class TestInvariantChecking:
    """Tests for invariant validation."""
    
    def test_clean_model_no_violations(self, clean_model):
        """Test that clean model has no invariant violations."""
        violations = clean_model.check_invariants()
        assert len(violations) == 0
    
    def test_valid_workflow_no_violations(self, tf_planned_model):
        """Test that valid workflow has no invariant violations."""
        violations = tf_planned_model.check_invariants()
        assert len(violations) == 0
    
    def test_detects_moves_file_in_clean_state(self):
        """Test detection of moves_file_exists in CLEAN state violation."""
        model = ProtectionWorkflowModel(
            state=WorkflowState.CLEAN,
            moves_file_exists=True,  # Invalid!
        )
        
        violations = model.check_invariants()
        assert len(violations) > 0
        assert any("moves_file_exists" in v for v in violations)
    
    def test_detects_plan_without_init(self):
        """Test detection of plan exists without init violation."""
        model = ProtectionWorkflowModel(
            state=WorkflowState.TF_PLANNED,
            tf_plan_exists=True,
            tf_initialized=False,  # Invalid!
        )
        
        violations = model.check_invariants()
        assert len(violations) > 0
        assert any("not initialized" in v for v in violations)


# =============================================================================
# Tests: Model Immutability
# =============================================================================

class TestModelImmutability:
    """Tests ensuring apply_action returns new model without mutating original."""
    
    def test_apply_returns_new_model(self, clean_model):
        """Test that apply_action returns a new model instance."""
        new_model = clean_model.apply_action(Action.SELECT_PROTECT, "PRJ:test")
        
        assert new_model is not clean_model
    
    def test_original_unchanged(self, clean_model):
        """Test that original model is unchanged after apply."""
        original_state = clean_model.state
        original_intents = set(clean_model.pending_intents)
        
        _ = clean_model.apply_action(Action.SELECT_PROTECT, "PRJ:test")
        
        assert clean_model.state == original_state
        assert clean_model.pending_intents == original_intents
    
    def test_sets_are_copied(self, intent_recorded_model):
        """Test that sets are properly copied, not shared."""
        new_model = intent_recorded_model.apply_action(Action.SELECT_PROTECT, "PRJ:another")
        
        # Modify new model's set
        new_model.pending_intents.add("PRJ:third")
        
        # Original should not be affected
        assert "PRJ:third" not in intent_recorded_model.pending_intents


# =============================================================================
# Tests: History Tracking
# =============================================================================

class TestHistoryTracking:
    """Tests for action history tracking."""
    
    def test_history_records_actions(self, clean_model):
        """Test that actions are recorded in history."""
        model = clean_model.apply_action(Action.SELECT_PROTECT, "PRJ:test")
        
        assert len(model.history) == 1
        assert "SELECT_PROTECT" in model.history[0]
    
    def test_history_accumulates(self, clean_model):
        """Test that history accumulates across actions."""
        model = clean_model.apply_action(Action.SELECT_PROTECT, "PRJ:test")
        model = model.apply_action(Action.GENERATE_CHANGES)
        model = model.apply_action(Action.TERRAFORM_INIT)
        
        assert len(model.history) == 3
        assert "SELECT_PROTECT" in model.history[0]
        assert "GENERATE_CHANGES" in model.history[1]
        assert "TERRAFORM_INIT" in model.history[2]
    
    def test_history_preserved_after_reset(self, intent_recorded_model):
        """Test that history is preserved even after reset."""
        model = intent_recorded_model.apply_action(Action.RESET)
        
        assert len(model.history) > 0
        assert "RESET" in model.history[-1]


# =============================================================================
# Tests: Complete Workflow Scenarios
# =============================================================================

class TestCompleteWorkflowScenarios:
    """Tests for complete workflow scenarios."""
    
    def test_happy_path_workflow(self, clean_model):
        """Test complete happy path: select → generate → init → plan → apply."""
        model = clean_model
        
        # Select resource to protect
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:my_project")
        assert model.state == WorkflowState.INTENT_RECORDED
        
        # Generate changes
        model = model.apply_action(Action.GENERATE_CHANGES)
        assert model.state == WorkflowState.YAML_UPDATED
        assert model.moves_file_exists is True
        
        # Terraform init
        model = model.apply_action(Action.TERRAFORM_INIT)
        assert model.state == WorkflowState.TF_INITIALIZED
        
        # Terraform plan
        model = model.apply_action(Action.TERRAFORM_PLAN)
        assert model.state == WorkflowState.TF_PLANNED
        
        # Terraform apply
        model = model.apply_action(Action.TERRAFORM_APPLY)
        assert model.state == WorkflowState.CLEAN
        
        # No invariant violations throughout
        assert len(model.check_invariants()) == 0
    
    def test_incremental_selection_workflow(self, clean_model):
        """Test workflow with multiple selections before generate."""
        model = clean_model
        
        # Select multiple resources
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:project1")
        model = model.apply_action(Action.SELECT_PROTECT, "PRJ:project2")
        model = model.apply_action(Action.SELECT_UNPROTECT, "REPO:repo1")
        
        assert len(model.pending_intents) == 3
        assert model.intent_protected["PRJ:project1"] is True
        assert model.intent_protected["REPO:repo1"] is False
        
        # Generate should process all
        model = model.apply_action(Action.GENERATE_CHANGES)
        assert len(model.pending_intents) == 0
        assert len(model.applied_to_yaml) == 3
    
    def test_add_after_generate_workflow(self, yaml_updated_model):
        """Test adding selection after generate invalidates state."""
        model = yaml_updated_model
        
        # Add another selection
        model = model.apply_action(Action.ADD_AFTER_GENERATE, "PRJ:new_project")
        
        # State should be back to INTENT_RECORDED
        assert model.state == WorkflowState.INTENT_RECORDED
        assert "PRJ:new_project" in model.pending_intents
        
        # Need to re-generate
        assert Action.GENERATE_CHANGES in model.valid_actions()
