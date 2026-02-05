"""State Machine Model for Protection Workflow Testing.

This module provides a state machine model that can be used to:
- Validate workflow state transitions
- Generate random valid test sequences
- Check invariants at each step
- Provide a model for property-based testing

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.5
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Set, Optional, Dict, Tuple
import random


class WorkflowState(Enum):
    """States in the protection workflow."""
    CLEAN = auto()              # No pending changes
    INTENT_RECORDED = auto()    # User has made selections, not generated
    YAML_UPDATED = auto()       # Generate completed
    TF_INITIALIZED = auto()     # terraform init done
    TF_PLANNED = auto()         # terraform plan done
    TF_APPLIED = auto()         # terraform apply done (→ CLEAN)


class Action(Enum):
    """Actions that can be performed."""
    SELECT_PROTECT = auto()
    SELECT_UNPROTECT = auto()
    GENERATE_CHANGES = auto()
    TERRAFORM_INIT = auto()
    TERRAFORM_PLAN = auto()
    TERRAFORM_APPLY = auto()
    ADD_AFTER_GENERATE = auto()
    RESET = auto()


# State transition table: (current_state, action) -> next_state
TRANSITIONS: Dict[Tuple[WorkflowState, Action], WorkflowState] = {
    # From CLEAN
    (WorkflowState.CLEAN, Action.SELECT_PROTECT): WorkflowState.INTENT_RECORDED,
    (WorkflowState.CLEAN, Action.SELECT_UNPROTECT): WorkflowState.INTENT_RECORDED,
    (WorkflowState.CLEAN, Action.RESET): WorkflowState.CLEAN,
    
    # From INTENT_RECORDED
    (WorkflowState.INTENT_RECORDED, Action.SELECT_PROTECT): WorkflowState.INTENT_RECORDED,
    (WorkflowState.INTENT_RECORDED, Action.SELECT_UNPROTECT): WorkflowState.INTENT_RECORDED,
    (WorkflowState.INTENT_RECORDED, Action.GENERATE_CHANGES): WorkflowState.YAML_UPDATED,
    (WorkflowState.INTENT_RECORDED, Action.RESET): WorkflowState.CLEAN,
    
    # From YAML_UPDATED
    (WorkflowState.YAML_UPDATED, Action.SELECT_PROTECT): WorkflowState.YAML_UPDATED,
    (WorkflowState.YAML_UPDATED, Action.SELECT_UNPROTECT): WorkflowState.YAML_UPDATED,
    (WorkflowState.YAML_UPDATED, Action.ADD_AFTER_GENERATE): WorkflowState.INTENT_RECORDED,
    (WorkflowState.YAML_UPDATED, Action.TERRAFORM_INIT): WorkflowState.TF_INITIALIZED,
    (WorkflowState.YAML_UPDATED, Action.RESET): WorkflowState.CLEAN,
    
    # From TF_INITIALIZED
    (WorkflowState.TF_INITIALIZED, Action.SELECT_PROTECT): WorkflowState.TF_INITIALIZED,
    (WorkflowState.TF_INITIALIZED, Action.SELECT_UNPROTECT): WorkflowState.TF_INITIALIZED,
    (WorkflowState.TF_INITIALIZED, Action.ADD_AFTER_GENERATE): WorkflowState.INTENT_RECORDED,
    (WorkflowState.TF_INITIALIZED, Action.TERRAFORM_PLAN): WorkflowState.TF_PLANNED,
    (WorkflowState.TF_INITIALIZED, Action.RESET): WorkflowState.CLEAN,
    
    # From TF_PLANNED
    (WorkflowState.TF_PLANNED, Action.SELECT_PROTECT): WorkflowState.TF_PLANNED,
    (WorkflowState.TF_PLANNED, Action.SELECT_UNPROTECT): WorkflowState.TF_PLANNED,
    (WorkflowState.TF_PLANNED, Action.ADD_AFTER_GENERATE): WorkflowState.INTENT_RECORDED,
    (WorkflowState.TF_PLANNED, Action.TERRAFORM_APPLY): WorkflowState.CLEAN,
    (WorkflowState.TF_PLANNED, Action.RESET): WorkflowState.CLEAN,
}


@dataclass
class ProtectionWorkflowModel:
    """State machine model for protection workflow.
    
    This model tracks:
    - Current workflow state
    - Pending protection intents
    - Applied protection status
    - File system state expectations
    - Action history for debugging
    """
    
    state: WorkflowState = WorkflowState.CLEAN
    
    # Intent tracking
    pending_intents: Set[str] = field(default_factory=set)
    applied_to_yaml: Set[str] = field(default_factory=set)
    applied_to_tf: Set[str] = field(default_factory=set)
    
    # Protection direction tracking
    intent_protected: Dict[str, bool] = field(default_factory=dict)
    
    # File system expectations
    moves_file_exists: bool = False
    tf_initialized: bool = False
    tf_plan_exists: bool = False
    
    # History for debugging
    history: List[str] = field(default_factory=list)
    
    def valid_actions(self) -> List[Action]:
        """Get actions valid from current state."""
        valid = [Action.SELECT_PROTECT, Action.SELECT_UNPROTECT, Action.RESET]
        
        if self.state == WorkflowState.INTENT_RECORDED:
            if self.pending_intents:
                valid.append(Action.GENERATE_CHANGES)
        
        elif self.state == WorkflowState.YAML_UPDATED:
            valid.extend([Action.TERRAFORM_INIT, Action.ADD_AFTER_GENERATE])
        
        elif self.state == WorkflowState.TF_INITIALIZED:
            valid.extend([Action.TERRAFORM_PLAN, Action.ADD_AFTER_GENERATE])
        
        elif self.state == WorkflowState.TF_PLANNED:
            valid.extend([Action.TERRAFORM_APPLY, Action.ADD_AFTER_GENERATE])
        
        return valid
    
    def can_perform(self, action: Action) -> bool:
        """Check if an action can be performed."""
        return action in self.valid_actions()
    
    def apply_action(
        self,
        action: Action,
        resource_key: Optional[str] = None,
    ) -> "ProtectionWorkflowModel":
        """Apply an action and return new state.
        
        Args:
            action: Action to perform
            resource_key: Resource key for select actions
            
        Returns:
            New model with updated state
            
        Raises:
            ValueError: If action is invalid
        """
        if not self.can_perform(action):
            raise ValueError(f"Action {action} invalid from {self.state}")
        
        # Create copy
        new = ProtectionWorkflowModel(
            state=self.state,
            pending_intents=set(self.pending_intents),
            applied_to_yaml=set(self.applied_to_yaml),
            applied_to_tf=set(self.applied_to_tf),
            intent_protected=dict(self.intent_protected),
            moves_file_exists=self.moves_file_exists,
            tf_initialized=self.tf_initialized,
            tf_plan_exists=self.tf_plan_exists,
            history=list(self.history),
        )
        
        # Apply action
        if action == Action.SELECT_PROTECT:
            if resource_key:
                new.pending_intents.add(resource_key)
                new.intent_protected[resource_key] = True
            if new.state == WorkflowState.CLEAN:
                new.state = WorkflowState.INTENT_RECORDED
        
        elif action == Action.SELECT_UNPROTECT:
            if resource_key:
                new.pending_intents.add(resource_key)
                new.intent_protected[resource_key] = False
            if new.state == WorkflowState.CLEAN:
                new.state = WorkflowState.INTENT_RECORDED
        
        elif action == Action.GENERATE_CHANGES:
            new.applied_to_yaml.update(new.pending_intents)
            new.pending_intents = set()
            new.moves_file_exists = True
            new.state = WorkflowState.YAML_UPDATED
        
        elif action == Action.TERRAFORM_INIT:
            new.tf_initialized = True
            new.state = WorkflowState.TF_INITIALIZED
        
        elif action == Action.TERRAFORM_PLAN:
            new.tf_plan_exists = True
            new.state = WorkflowState.TF_PLANNED
        
        elif action == Action.TERRAFORM_APPLY:
            new.applied_to_tf.update(new.applied_to_yaml)
            new.moves_file_exists = False
            new.tf_plan_exists = False
            new.state = WorkflowState.CLEAN
        
        elif action == Action.ADD_AFTER_GENERATE:
            if resource_key:
                new.pending_intents.add(resource_key)
            new.state = WorkflowState.INTENT_RECORDED
        
        elif action == Action.RESET:
            new = ProtectionWorkflowModel()
            new.history = list(self.history)
        
        # Record history
        key_info = f"({resource_key})" if resource_key else ""
        new.history.append(f"{action.name}{key_info}")
        
        return new
    
    def check_invariants(self) -> List[str]:
        """Check all invariants and return violations."""
        violations = []
        
        # Invariant 1: moves_file_exists implies not CLEAN
        if self.moves_file_exists and self.state == WorkflowState.CLEAN:
            violations.append("moves_file_exists but state is CLEAN")
        
        # Invariant 2: tf_plan_exists implies tf_initialized
        if self.tf_plan_exists and not self.tf_initialized:
            violations.append("tf_plan_exists but not initialized")
        
        # Invariant 3: applied_to_tf ⊆ applied_to_yaml
        if not self.applied_to_tf.issubset(self.applied_to_yaml):
            extra = self.applied_to_tf - self.applied_to_yaml
            violations.append(f"applied_to_tf has items not in applied_to_yaml: {extra}")
        
        # Invariant 4: State consistency
        if self.state == WorkflowState.TF_PLANNED and not self.tf_plan_exists:
            violations.append("state is TF_PLANNED but no plan exists")
        
        if self.state == WorkflowState.TF_INITIALIZED and not self.tf_initialized:
            violations.append("state is TF_INITIALIZED but tf_initialized is False")
        
        return violations
    
    def get_state_summary(self) -> Dict:
        """Get a summary of current state for debugging."""
        return {
            "state": self.state.name,
            "pending_intents": list(self.pending_intents),
            "applied_to_yaml": list(self.applied_to_yaml),
            "applied_to_tf": list(self.applied_to_tf),
            "moves_file_exists": self.moves_file_exists,
            "tf_initialized": self.tf_initialized,
            "tf_plan_exists": self.tf_plan_exists,
            "history_length": len(self.history),
        }


# =============================================================================
# Sequence Generation
# =============================================================================

def generate_random_sequence(
    max_length: int = 20,
    available_resources: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> List[Tuple[Action, Optional[str]]]:
    """Generate a random valid action sequence.
    
    Args:
        max_length: Maximum sequence length
        available_resources: List of resource keys to use
        seed: Random seed for reproducibility
        
    Returns:
        List of (action, resource_key) tuples
    """
    if seed is not None:
        random.seed(seed)
    
    if available_resources is None:
        available_resources = [
            "PRJ:project1",
            "PRJ:project2",
            "REPO:repo1",
        ]
    
    model = ProtectionWorkflowModel()
    sequence = []
    
    for _ in range(max_length):
        valid = model.valid_actions()
        
        # Weight selection toward progress (not just selecting)
        progress_actions = [
            a for a in valid 
            if a in (Action.GENERATE_CHANGES, Action.TERRAFORM_INIT, 
                    Action.TERRAFORM_PLAN, Action.TERRAFORM_APPLY)
        ]
        
        if progress_actions and random.random() < 0.4:
            action = random.choice(progress_actions)
        else:
            action = random.choice(valid)
        
        # Determine resource key if needed
        resource_key = None
        if action in (Action.SELECT_PROTECT, Action.SELECT_UNPROTECT, Action.ADD_AFTER_GENERATE):
            resource_key = random.choice(available_resources)
        
        sequence.append((action, resource_key))
        
        # Apply action
        try:
            model = model.apply_action(action, resource_key)
        except ValueError:
            # Shouldn't happen since we check valid_actions, but just in case
            break
        
        # Check invariants
        violations = model.check_invariants()
        if violations:
            # Stop if we hit invariant violation (shouldn't happen)
            break
        
        # Stop if we've completed a full cycle back to CLEAN
        if model.state == WorkflowState.CLEAN and len(sequence) > 3:
            if random.random() < 0.3:  # 30% chance to stop at clean
                break
    
    return sequence


def generate_happy_path_sequence(
    resources_to_protect: List[str],
) -> List[Tuple[Action, Optional[str]]]:
    """Generate a happy path sequence for protecting resources.
    
    Args:
        resources_to_protect: List of resource keys to protect
        
    Returns:
        Sequence that protects all resources
    """
    sequence = []
    
    # Select all resources
    for key in resources_to_protect:
        sequence.append((Action.SELECT_PROTECT, key))
    
    # Generate, init, plan, apply
    sequence.extend([
        (Action.GENERATE_CHANGES, None),
        (Action.TERRAFORM_INIT, None),
        (Action.TERRAFORM_PLAN, None),
        (Action.TERRAFORM_APPLY, None),
    ])
    
    return sequence


def generate_incremental_sequence(
    resources: List[str],
) -> List[Tuple[Action, Optional[str]]]:
    """Generate an incremental workflow sequence.
    
    This simulates:
    1. Protect some resources
    2. Generate and apply
    3. Add more resources
    4. Generate and apply again
    """
    if len(resources) < 2:
        return generate_happy_path_sequence(resources)
    
    # Split resources
    first_batch = resources[:len(resources)//2]
    second_batch = resources[len(resources)//2:]
    
    sequence = []
    
    # First batch
    for key in first_batch:
        sequence.append((Action.SELECT_PROTECT, key))
    
    sequence.extend([
        (Action.GENERATE_CHANGES, None),
        (Action.TERRAFORM_INIT, None),
        (Action.TERRAFORM_PLAN, None),
        (Action.TERRAFORM_APPLY, None),
    ])
    
    # Second batch
    for key in second_batch:
        sequence.append((Action.SELECT_PROTECT, key))
    
    sequence.extend([
        (Action.GENERATE_CHANGES, None),
        (Action.TERRAFORM_INIT, None),
        (Action.TERRAFORM_PLAN, None),
        (Action.TERRAFORM_APPLY, None),
    ])
    
    return sequence
