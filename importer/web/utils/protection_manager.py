"""Protection manager for tracking and managing protected resources.

This module provides utilities for:
- Tracking protected resources in YAML configurations
- Detecting changes in protection status between YAML versions
- Generating Terraform moved blocks when protection status changes
- Parsing Terraform plans to identify protected resource destruction
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import yaml

logger = logging.getLogger(__name__)


# Map resource type codes to Terraform resource types and names
RESOURCE_TYPE_MAP = {
    "PRJ": ("dbtcloud_project", "projects", "protected_projects"),
    "ENV": ("dbtcloud_environment", "environments", "protected_environments"),
    "JOB": ("dbtcloud_job", "jobs", "protected_jobs"),
    "REP": ("dbtcloud_repository", "repositories", "protected_repositories"),
}


@dataclass
class ProtectedResource:
    """A resource marked as protected."""
    
    resource_key: str  # Composite key e.g., "proj_myjob" or "my_project"
    resource_type: str  # Element type code: PRJ, ENV, JOB, REP
    name: str  # Human-readable name
    protected: bool  # Current protection status
    
    @property
    def protected_address(self) -> str:
        """Get Terraform resource address when protected."""
        return get_resource_address(self.resource_type, self.resource_key, protected=True)
    
    @property
    def unprotected_address(self) -> str:
        """Get Terraform resource address when not protected."""
        return get_resource_address(self.resource_type, self.resource_key, protected=False)


@dataclass
class ProtectionChange:
    """Represents a change in protection status."""
    
    resource_key: str
    resource_type: str  # PRJ, ENV, JOB, REP
    name: str
    direction: str  # "protect" or "unprotect"
    from_address: str
    to_address: str


@dataclass
class ProtectedDestroyWarning:
    """Warning about a protected resource that would be destroyed."""
    
    address: str
    name: str
    resource_type: str
    action: str  # "delete" or "replace"


def get_resource_address(
    resource_type: str,
    key: str,
    protected: bool,
    module_name: str = "dbt_cloud",
) -> str:
    """Get Terraform resource address based on protection status.
    
    Args:
        resource_type: Element type code (PRJ, ENV, JOB, REP)
        key: Resource key (e.g., "my_project" or "proj_myjob")
        protected: Whether the resource is protected
        module_name: Name of the Terraform module
        
    Returns:
        Full Terraform resource address
    """
    if resource_type not in RESOURCE_TYPE_MAP:
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    tf_type, unprotected_name, protected_name = RESOURCE_TYPE_MAP[resource_type]
    resource_name = protected_name if protected else unprotected_name
    
    return f'module.{module_name}.{tf_type}.{resource_name}["{key}"]'


def extract_protected_resources(yaml_config: dict) -> list[ProtectedResource]:
    """Extract all protected resources from a YAML configuration.
    
    Args:
        yaml_config: Parsed YAML configuration
        
    Returns:
        List of ProtectedResource objects
    """
    protected = []
    
    projects = yaml_config.get("projects", [])
    for project in projects:
        project_key = project.get("key", "")
        project_name = project.get("name", project_key)
        
        # Check project protection
        if project.get("protected", False):
            protected.append(ProtectedResource(
                resource_key=project_key,
                resource_type="PRJ",
                name=project_name,
                protected=True,
            ))
        
        # Check environments
        for env in project.get("environments", []):
            env_key = env.get("key", "")
            composite_key = f"{project_key}_{env_key}"
            
            if env.get("protected", False):
                protected.append(ProtectedResource(
                    resource_key=composite_key,
                    resource_type="ENV",
                    name=env.get("name", env_key),
                    protected=True,
                ))
        
        # Check jobs
        for job in project.get("jobs", []):
            job_key = job.get("key", "")
            composite_key = f"{project_key}_{job_key}"
            
            if job.get("protected", False):
                protected.append(ProtectedResource(
                    resource_key=composite_key,
                    resource_type="JOB",
                    name=job.get("name", job_key),
                    protected=True,
                ))
    
    # Check global repositories
    globals_config = yaml_config.get("globals", {})
    for repo in globals_config.get("repositories", []):
        repo_key = repo.get("key", "")
        if repo.get("protected", False):
            protected.append(ProtectedResource(
                resource_key=repo_key,
                resource_type="REP",
                name=repo.get("remote_url", repo_key),
                protected=True,
            ))
    
    return protected


def detect_protection_changes(
    current_yaml: dict,
    previous_yaml: Optional[dict],
) -> list[ProtectionChange]:
    """Detect resources that changed protection status between YAML versions.
    
    Args:
        current_yaml: Current YAML configuration
        previous_yaml: Previous YAML configuration (None if first run)
        
    Returns:
        List of ProtectionChange objects
    """
    if previous_yaml is None:
        return []
    
    changes = []
    
    # Build maps of protection status
    def build_protection_map(yaml_config: dict) -> dict[tuple[str, str], tuple[str, bool]]:
        """Build map of (type, key) -> (name, protected)."""
        result = {}
        
        projects = yaml_config.get("projects", [])
        for project in projects:
            project_key = project.get("key", "")
            project_name = project.get("name", project_key)
            result[("PRJ", project_key)] = (project_name, project.get("protected", False))
            
            for env in project.get("environments", []):
                env_key = env.get("key", "")
                composite_key = f"{project_key}_{env_key}"
                result[("ENV", composite_key)] = (env.get("name", env_key), env.get("protected", False))
            
            for job in project.get("jobs", []):
                job_key = job.get("key", "")
                composite_key = f"{project_key}_{job_key}"
                result[("JOB", composite_key)] = (job.get("name", job_key), job.get("protected", False))
        
        globals_config = yaml_config.get("globals", {})
        for repo in globals_config.get("repositories", []):
            repo_key = repo.get("key", "")
            result[("REP", repo_key)] = (repo.get("remote_url", repo_key), repo.get("protected", False))
        
        return result
    
    current_map = build_protection_map(current_yaml)
    previous_map = build_protection_map(previous_yaml)
    
    # Find resources that exist in both and have changed protection status
    for (resource_type, key), (name, current_protected) in current_map.items():
        if (resource_type, key) in previous_map:
            _, previous_protected = previous_map[(resource_type, key)]
            
            if current_protected and not previous_protected:
                # Resource is now protected
                changes.append(ProtectionChange(
                    resource_key=key,
                    resource_type=resource_type,
                    name=name,
                    direction="protect",
                    from_address=get_resource_address(resource_type, key, protected=False),
                    to_address=get_resource_address(resource_type, key, protected=True),
                ))
            elif not current_protected and previous_protected:
                # Resource is no longer protected
                changes.append(ProtectionChange(
                    resource_key=key,
                    resource_type=resource_type,
                    name=name,
                    direction="unprotect",
                    from_address=get_resource_address(resource_type, key, protected=True),
                    to_address=get_resource_address(resource_type, key, protected=False),
                ))
    
    return changes


def generate_moved_blocks(
    changes: list[ProtectionChange],
    module_name: str = "dbt_cloud",
) -> str:
    """Generate Terraform moved blocks for protection status changes.
    
    Args:
        changes: List of protection changes
        module_name: Name of the Terraform module
        
    Returns:
        Terraform HCL content with moved blocks
    """
    if not changes:
        return ""
    
    lines = [
        "# Auto-generated: Move resources between protected/unprotected resource blocks",
        f"# Generated: {datetime.now().isoformat()}",
        "#",
        "# These moved blocks handle protection status changes.",
        "# After `terraform apply` succeeds, you can delete this file.",
        "",
    ]
    
    for change in changes:
        action_desc = "is now protected" if change.direction == "protect" else "is no longer protected"
        resource_type_name = {
            "PRJ": "Project",
            "ENV": "Environment", 
            "JOB": "Job",
            "REP": "Repository",
        }.get(change.resource_type, change.resource_type)
        
        lines.extend([
            f"# {resource_type_name} \"{change.name}\" {action_desc}",
            "moved {",
            f'  from = {change.from_address}',
            f'  to   = {change.to_address}',
            "}",
            "",
        ])
    
    return "\n".join(lines)


def write_moved_blocks_file(
    changes: list[ProtectionChange],
    output_dir: Union[str, Path],
    filename: str = "protection_moves.tf",
) -> Optional[Path]:
    """Write moved blocks to a Terraform file.
    
    Args:
        changes: List of protection changes
        output_dir: Directory to write to
        filename: Output filename
        
    Returns:
        Path to the file if written, None if no changes
    """
    if not changes:
        return None
    
    content = generate_moved_blocks(changes)
    output_path = Path(output_dir) / filename
    output_path.write_text(content, encoding="utf-8")
    
    logger.info(f"Wrote {len(changes)} moved block(s) to {output_path}")
    return output_path


def check_plan_for_protected_destroys(
    plan_json: dict,
    yaml_config: dict,
) -> list[ProtectedDestroyWarning]:
    """Parse Terraform plan JSON and identify protected resources that would be destroyed.
    
    Args:
        plan_json: Output from `terraform show -json plan.tfplan`
        yaml_config: Current YAML configuration
        
    Returns:
        List of warnings for protected resources that would be destroyed
    """
    warnings = []
    
    # Build set of protected resource addresses
    protected_resources = extract_protected_resources(yaml_config)
    protected_addresses = {r.protected_address for r in protected_resources}
    
    # Also build a map for looking up names
    address_to_resource = {r.protected_address: r for r in protected_resources}
    
    # Check plan for destroy/replace actions
    resource_changes = plan_json.get("resource_changes", [])
    
    for change in resource_changes:
        actions = change.get("change", {}).get("actions", [])
        address = change.get("address", "")
        
        # Check if this is a delete or replace action
        if "delete" in actions or actions == ["delete"]:
            action = "delete"
        elif "create" in actions and "delete" in actions:
            action = "replace"
        else:
            continue
        
        # Check if this address matches a protected resource
        if address in protected_addresses:
            resource = address_to_resource[address]
            warnings.append(ProtectedDestroyWarning(
                address=address,
                name=resource.name,
                resource_type=resource.resource_type,
                action=action,
            ))
    
    return warnings


def format_protection_warnings(warnings: list[ProtectedDestroyWarning]) -> str:
    """Format protection warnings for display.
    
    Args:
        warnings: List of warnings
        
    Returns:
        Formatted warning message
    """
    if not warnings:
        return ""
    
    lines = [
        "⚠️  PROTECTED RESOURCES WOULD BE DESTROYED",
        "",
        "The following protected resources would be affected by this operation:",
        "",
    ]
    
    type_names = {
        "PRJ": "Project",
        "ENV": "Environment",
        "JOB": "Job",
        "REP": "Repository",
    }
    
    for warning in warnings:
        type_name = type_names.get(warning.resource_type, warning.resource_type)
        lines.append(f"  • {type_name}: {warning.name} ({warning.action})")
    
    lines.extend([
        "",
        "Terraform will fail with a 'prevent_destroy' error.",
        "",
        "To proceed, you must first remove protection:",
        "  1. Edit the YAML file and set 'protected: false' for these resources",
        "  2. Regenerate Terraform files",
        "  3. Run 'terraform apply' to move resources to unprotected blocks",
        "  4. Then remove the resources from YAML and apply again",
    ])
    
    return "\n".join(lines)


def load_yaml_config(yaml_path: Union[str, Path]) -> dict:
    """Load and parse a YAML configuration file.
    
    Args:
        yaml_path: Path to YAML file
        
    Returns:
        Parsed YAML as dict
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_plan_json(plan_file: Union[str, Path]) -> dict:
    """Read a Terraform plan JSON file.
    
    Args:
        plan_file: Path to plan JSON file (output of `terraform show -json plan.tfplan`)
        
    Returns:
        Parsed plan as dict
    """
    with open(plan_file, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# Cascade Protection Helpers
# ============================================================================

# Type name labels for UI display
TYPE_LABELS = {
    "ACC": "Account",
    "PRJ": "Project",
    "ENV": "Environment",
    "JOB": "Job",
    "REP": "Repository",
    "CON": "Connection",
    "VAR": "Env Variable",
    "CRD": "Credential",
    "TOK": "Service Token",
    "GRP": "Group",
    "NOT": "Notification",
}


@dataclass
class CascadeResource:
    """A resource in a protection cascade."""
    
    key: str  # source_key or element_mapping_id
    name: str  # Human-readable name
    resource_type: str  # Element type code
    
    @property
    def type_label(self) -> str:
        """Get human-readable type label."""
        return TYPE_LABELS.get(self.resource_type, self.resource_type)


def get_resources_to_protect(
    source_key: str,
    hierarchy_index: "HierarchyIndex",
    source_items: list[dict],
    already_protected: Optional[set[str]] = None,
) -> tuple[CascadeResource, list[CascadeResource]]:
    """Get all resources that need protection when protecting a resource.
    
    When protecting a child resource (e.g., a Job), its parent resources
    (Environment, Project) must also be protected to maintain hierarchy.
    
    Args:
        source_key: The source_key of the resource to protect
        hierarchy_index: HierarchyIndex for parent/child lookups
        source_items: List of source report items
        already_protected: Set of already-protected source_keys (to skip)
        
    Returns:
        Tuple of (target_resource, parents_to_protect)
        - target_resource: The resource being protected
        - parents_to_protect: List of ancestor resources that need protection
    """
    already_protected = already_protected or set()
    
    # Find the entity by source_key or element_mapping_id
    entity = None
    mapping_id = None
    
    for item in source_items:
        item_key = item.get("key") or item.get("element_mapping_id", "")
        if item_key == source_key or item.get("element_mapping_id") == source_key:
            entity = item
            mapping_id = item.get("element_mapping_id")
            break
    
    if not entity:
        # Resource not found - return empty
        return CascadeResource(key=source_key, name=source_key, resource_type="UNK"), []
    
    # Create the target resource
    target = CascadeResource(
        key=source_key,
        name=entity.get("name", source_key),
        resource_type=entity.get("element_type_code", "UNK"),
    )
    
    if not mapping_id:
        return target, []
    
    # Get all required ancestors using hierarchy index
    ancestor_ids = hierarchy_index.get_required_ancestors(mapping_id)
    
    parents_to_protect = []
    for ancestor_id in ancestor_ids:
        ancestor = hierarchy_index.get_entity(ancestor_id)
        if not ancestor:
            continue
        
        ancestor_type = ancestor.get("element_type_code", "")
        
        # Skip Account (ACC) - not protectable
        if ancestor_type == "ACC":
            continue
        
        # Get the ancestor's source_key
        ancestor_key = ancestor.get("key") or ancestor_id
        
        # Skip if already protected
        if ancestor_key in already_protected:
            continue
        
        parents_to_protect.append(CascadeResource(
            key=ancestor_key,
            name=ancestor.get("name", ancestor_id),
            resource_type=ancestor_type,
        ))
    
    # Sort parents by depth (project first, then environment, etc.)
    type_order = {"PRJ": 1, "ENV": 2, "VAR": 3, "JOB": 4, "CRD": 5, "REP": 6}
    parents_to_protect.sort(key=lambda r: type_order.get(r.resource_type, 99))
    
    return target, parents_to_protect


def get_resources_to_unprotect(
    source_key: str,
    hierarchy_index: "HierarchyIndex",
    source_items: list[dict],
    protected_resources: set[str],
) -> tuple[CascadeResource, list[CascadeResource]]:
    """Get all descendant resources that would need unprotection.
    
    When unprotecting a parent resource (e.g., a Project), its protected
    children (Environments, Jobs) should also be considered for unprotection.
    
    Args:
        source_key: The source_key of the resource to unprotect
        hierarchy_index: HierarchyIndex for parent/child lookups
        source_items: List of source report items
        protected_resources: Set of currently protected source_keys
        
    Returns:
        Tuple of (target_resource, protected_children)
        - target_resource: The resource being unprotected
        - protected_children: List of protected descendant resources
    """
    # Find the entity
    entity = None
    mapping_id = None
    
    for item in source_items:
        item_key = item.get("key") or item.get("element_mapping_id", "")
        if item_key == source_key or item.get("element_mapping_id") == source_key:
            entity = item
            mapping_id = item.get("element_mapping_id")
            break
    
    if not entity:
        return CascadeResource(key=source_key, name=source_key, resource_type="UNK"), []
    
    target = CascadeResource(
        key=source_key,
        name=entity.get("name", source_key),
        resource_type=entity.get("element_type_code", "UNK"),
    )
    
    if not mapping_id:
        return target, []
    
    # Get all descendants using hierarchy index
    descendant_ids = hierarchy_index.get_all_descendants(mapping_id)
    
    protected_children = []
    for desc_id in descendant_ids:
        desc = hierarchy_index.get_entity(desc_id)
        if not desc:
            continue
        
        desc_key = desc.get("key") or desc_id
        
        # Only include if currently protected
        if desc_key not in protected_resources:
            continue
        
        desc_type = desc.get("element_type_code", "")
        
        # Skip Account (ACC)
        if desc_type == "ACC":
            continue
        
        protected_children.append(CascadeResource(
            key=desc_key,
            name=desc.get("name", desc_id),
            resource_type=desc_type,
        ))
    
    # Sort children by type
    type_order = {"PRJ": 1, "ENV": 2, "VAR": 3, "JOB": 4, "CRD": 5, "REP": 6}
    protected_children.sort(key=lambda r: type_order.get(r.resource_type, 99))
    
    return target, protected_children


def build_key_to_mapping_id(source_items: list[dict]) -> dict[str, str]:
    """Build a mapping from source_key to element_mapping_id.
    
    Args:
        source_items: List of source report items
        
    Returns:
        Dict mapping source_key -> element_mapping_id
    """
    result = {}
    for item in source_items:
        key = item.get("key") or item.get("element_mapping_id", "")
        mapping_id = item.get("element_mapping_id")
        if key and mapping_id:
            result[key] = mapping_id
            # Also map mapping_id to itself for direct lookups
            result[mapping_id] = mapping_id
    return result
