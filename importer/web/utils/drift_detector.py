"""Drift detection utility.

Compares Terraform state resources with current target account data
to identify drift that needs reconciliation.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from importer.web.utils.terraform_state_reader import StateReadResult, StateResource


logger = logging.getLogger(__name__)


class DriftType(Enum):
    """Types of drift between state and target."""
    
    # State has resource but it doesn't exist in target
    MISSING_IN_TARGET = "missing_in_target"
    # Target has resource but it's not in state
    MISSING_IN_STATE = "missing_in_state"
    # State points to different ID than what exists in target
    ID_MISMATCH = "id_mismatch"
    # Same ID but different attributes
    ATTRIBUTE_DRIFT = "attribute_drift"
    # No drift - state matches target
    NO_DRIFT = "no_drift"


@dataclass
class DriftResult:
    """Result of drift detection for a single resource."""
    
    # Type of drift detected
    drift_type: DriftType
    # Element code (PRJ, ENV, JOB, etc.)
    element_code: str
    # Resource name (for display)
    resource_name: str
    
    # State information (if exists)
    state_address: Optional[str] = None
    state_id: Optional[int] = None
    state_name: Optional[str] = None
    
    # Target information (if exists)
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    
    # Human-readable description of the drift
    description: str = ""
    
    # Whether user has selected to adopt this resource
    adopt: bool = False
    
    # Additional context (e.g., project name for scoped resources)
    context: dict = field(default_factory=dict)


@dataclass
class DriftSummary:
    """Summary of all drift detection results."""
    
    # Total resources checked
    total_checked: int = 0
    # Count by drift type
    missing_in_target: int = 0
    missing_in_state: int = 0
    id_mismatch: int = 0
    attribute_drift: int = 0
    no_drift: int = 0
    
    # All drift results
    results: list[DriftResult] = field(default_factory=list)
    
    @property
    def has_drift(self) -> bool:
        """Check if any drift was detected."""
        return (
            self.missing_in_target > 0
            or self.missing_in_state > 0
            or self.id_mismatch > 0
            or self.attribute_drift > 0
        )
    
    @property
    def drift_count(self) -> int:
        """Total number of resources with drift."""
        return (
            self.missing_in_target
            + self.missing_in_state
            + self.id_mismatch
            + self.attribute_drift
        )


def detect_drift(
    state_result: StateReadResult,
    target_items: list[dict],
    check_attributes: bool = False,
) -> DriftSummary:
    """Detect drift between Terraform state and target account data.
    
    Args:
        state_result: Parsed Terraform state
        target_items: Report items from target account fetch
        check_attributes: If True, also check for attribute drift (slower)
        
    Returns:
        DriftSummary with all drift results
    """
    summary = DriftSummary()
    
    # Build target lookup by (element_code, dbt_id)
    target_by_id: dict[tuple[str, int], dict] = {}
    # Also by (element_code, name) for name-based matching
    target_by_name: dict[tuple[str, str], dict] = {}
    
    for item in target_items:
        element_code = item.get("element_type_code", "")
        dbt_id = item.get("dbt_id")
        name = item.get("name", "")
        
        if dbt_id is not None:
            target_by_id[(element_code, dbt_id)] = item
        if name:
            target_by_name[(element_code, name)] = item
    
    # Track which target resources we've matched
    matched_target_ids: set[tuple[str, int]] = set()
    
    # Check each state resource against target
    for state_resource in state_result.resources:
        summary.total_checked += 1
        
        element_code = state_resource.element_code
        state_id = state_resource.dbt_id
        state_name = state_resource.name
        
        # Look up in target by ID
        target_item = None
        if state_id is not None:
            target_item = target_by_id.get((element_code, state_id))
        
        if target_item:
            # Found matching target by ID
            matched_target_ids.add((element_code, state_id))
            
            if check_attributes:
                # Check for attribute drift (future enhancement)
                # For now, just mark as no drift
                pass
            
            drift_result = DriftResult(
                drift_type=DriftType.NO_DRIFT,
                element_code=element_code,
                resource_name=state_name or state_resource.tf_name,
                state_address=state_resource.address,
                state_id=state_id,
                state_name=state_name,
                target_id=target_item.get("dbt_id"),
                target_name=target_item.get("name"),
                description="State matches target",
            )
            summary.no_drift += 1
            
        else:
            # State resource not found in target by ID
            # Check if there's a resource with the same name but different ID
            target_by_same_name = target_by_name.get((element_code, state_name)) if state_name else None
            
            if target_by_same_name:
                # ID mismatch - state has different ID than target
                target_id = target_by_same_name.get("dbt_id")
                matched_target_ids.add((element_code, target_id))
                
                drift_result = DriftResult(
                    drift_type=DriftType.ID_MISMATCH,
                    element_code=element_code,
                    resource_name=state_name or state_resource.tf_name,
                    state_address=state_resource.address,
                    state_id=state_id,
                    state_name=state_name,
                    target_id=target_id,
                    target_name=target_by_same_name.get("name"),
                    description=f"State has ID {state_id}, but target '{state_name}' has ID {target_id}",
                    context={
                        "project_name": target_by_same_name.get("project_name"),
                    },
                )
                summary.id_mismatch += 1
                
            else:
                # Resource in state doesn't exist in target at all
                drift_result = DriftResult(
                    drift_type=DriftType.MISSING_IN_TARGET,
                    element_code=element_code,
                    resource_name=state_name or state_resource.tf_name,
                    state_address=state_resource.address,
                    state_id=state_id,
                    state_name=state_name,
                    description=f"Resource '{state_name}' (ID {state_id}) exists in state but not in target",
                )
                summary.missing_in_target += 1
        
        summary.results.append(drift_result)
    
    # Check for target resources not in state (optional, for completeness)
    # This finds resources that exist in target but aren't managed by Terraform
    for (element_code, dbt_id), target_item in target_by_id.items():
        if (element_code, dbt_id) not in matched_target_ids:
            # Target resource not in state
            drift_result = DriftResult(
                drift_type=DriftType.MISSING_IN_STATE,
                element_code=element_code,
                resource_name=target_item.get("name", "Unknown"),
                target_id=dbt_id,
                target_name=target_item.get("name"),
                description=f"Resource '{target_item.get('name')}' (ID {dbt_id}) exists in target but not in state",
                context={
                    "project_name": target_item.get("project_name"),
                },
            )
            summary.results.append(drift_result)
            summary.missing_in_state += 1
            summary.total_checked += 1
    
    logger.info(
        f"Drift detection complete: {summary.drift_count} drifted out of {summary.total_checked} resources "
        f"(ID mismatch: {summary.id_mismatch}, missing in target: {summary.missing_in_target}, "
        f"missing in state: {summary.missing_in_state})"
    )
    
    return summary


def get_adoptable_drifts(summary: DriftSummary) -> list[DriftResult]:
    """Get drift results that can be adopted (imported into state).
    
    Adoptable drifts are:
    - ID_MISMATCH: State points to wrong ID, adopt the correct target ID
    - MISSING_IN_STATE: Target exists but not in state, can import it
    
    Args:
        summary: Drift summary from detect_drift
        
    Returns:
        List of DriftResult that can be adopted
    """
    adoptable_types = {DriftType.ID_MISMATCH, DriftType.MISSING_IN_STATE}
    return [
        result for result in summary.results
        if result.drift_type in adoptable_types
    ]


def get_drift_display_info(drift: DriftResult) -> dict:
    """Get display information for a drift result.
    
    Args:
        drift: A drift result
        
    Returns:
        Dictionary with display-friendly information
    """
    type_labels = {
        DriftType.MISSING_IN_TARGET: "Missing in Target",
        DriftType.MISSING_IN_STATE: "Not in State",
        DriftType.ID_MISMATCH: "ID Mismatch",
        DriftType.ATTRIBUTE_DRIFT: "Attribute Changed",
        DriftType.NO_DRIFT: "In Sync",
    }
    
    type_colors = {
        DriftType.MISSING_IN_TARGET: "red",
        DriftType.MISSING_IN_STATE: "orange",
        DriftType.ID_MISMATCH: "amber",
        DriftType.ATTRIBUTE_DRIFT: "yellow",
        DriftType.NO_DRIFT: "green",
    }
    
    type_icons = {
        DriftType.MISSING_IN_TARGET: "error",
        DriftType.MISSING_IN_STATE: "add_circle",
        DriftType.ID_MISMATCH: "swap_horiz",
        DriftType.ATTRIBUTE_DRIFT: "edit",
        DriftType.NO_DRIFT: "check_circle",
    }
    
    element_labels = {
        "PRJ": "Project",
        "REP": "Repository",
        "ENV": "Environment",
        "JOB": "Job",
        "CON": "Connection",
        "TOK": "Service Token",
        "GRP": "Group",
        "NOT": "Notification",
        "WEB": "Webhook",
        "VAR": "Env Variable",
        "PLE": "PrivateLink",
        "PREP": "Project Repo",
    }
    
    return {
        "drift_type_label": type_labels.get(drift.drift_type, str(drift.drift_type)),
        "drift_type_color": type_colors.get(drift.drift_type, "grey"),
        "drift_type_icon": type_icons.get(drift.drift_type, "help"),
        "element_label": element_labels.get(drift.element_code, drift.element_code),
        "resource_name": drift.resource_name,
        "state_id": drift.state_id,
        "target_id": drift.target_id,
        "description": drift.description,
        "can_adopt": drift.drift_type in {DriftType.ID_MISMATCH, DriftType.MISSING_IN_STATE},
    }
