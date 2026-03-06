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

from importer.web.utils.ui_logger import traced

logger = logging.getLogger(__name__)

def _agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict,
    *,
    run_id: str = "run1",
) -> None:
    _ = (hypothesis_id, location, message, data, run_id)


# Map resource type codes to Terraform resource types and names
RESOURCE_TYPE_MAP = {
    "PRJ": ("dbtcloud_project", "projects", "protected_projects"),
    "ENV": ("dbtcloud_environment", "environments", "protected_environments"),
    "JOB": ("dbtcloud_job", "jobs", "protected_jobs"),
    "JCTG": ("dbtcloud_job_completion_trigger", "job_completion_triggers", "protected_job_completion_triggers"),
    "JEVO": ("dbtcloud_environment_variable_job_override", "environment_variable_job_overrides", "protected_environment_variable_job_overrides"),
    "REP": ("dbtcloud_repository", "repositories", "protected_repositories"),
    "PREP": ("dbtcloud_project_repository", "project_repositories", "protected_project_repositories"),
    "EXTATTR": ("dbtcloud_extended_attributes", "extended_attrs", "protected_extended_attrs"),
    "VAR": ("dbtcloud_environment_variable", "environment_variables", "protected_environment_variables"),
    # Global resources — protected variants with lifecycle.prevent_destroy
    "GRP": ("dbtcloud_group", "groups", "protected_groups"),
    "CON": ("dbtcloud_global_connection", "connections", "protected_connections"),
    "TOK": ("dbtcloud_service_token", "service_tokens", "protected_service_tokens"),
    "NOT": ("dbtcloud_notification", "notifications", "notifications"),  # Notifications skipped in TF (user_id mapping)
    # --- S4: Account-level ---
    "ACFT": ("dbtcloud_account_features", "account_features", "protected_account_features"),
    "IPRST": ("dbtcloud_ip_restrictions_rule", "ip_restrictions_rules", "protected_ip_restrictions_rules"),
    "LNGI": ("dbtcloud_lineage_integration", "lineage_integrations", "protected_lineage_integrations"),
    "OAUTH": ("dbtcloud_oauth_configuration", "oauth_configurations", "protected_oauth_configurations"),
    # --- S5: Project-level ---
    "PARFT": ("dbtcloud_project_artefacts", "project_artefacts", "protected_project_artefacts"),
    "USRGRP": ("dbtcloud_user_groups", "user_groups", "protected_user_groups"),
    # --- S6: Semantic Layer ---
    "SLCFG": ("dbtcloud_semantic_layer_configuration", "semantic_layer_configurations", "protected_semantic_layer_configurations"),
    "SLSTM": ("dbtcloud_semantic_layer_credential_service_token_mapping", "semantic_layer_credential_service_token_mappings", "protected_semantic_layer_credential_service_token_mappings"),
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
    sub_module: str = "module.projects_v2[0]",
) -> str:
    """Get Terraform resource address based on protection status.
    
    Args:
        resource_type: Element type code (PRJ, ENV, JOB, REP)
        key: Resource key (e.g., "my_project" or "proj_myjob")
        protected: Whether the resource is protected
        module_name: Name of the Terraform module
        sub_module: Sub-module path (default: "module.projects_v2[0]")
        
    Returns:
        Full Terraform resource address
    """
    if resource_type not in RESOURCE_TYPE_MAP:
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    tf_type, unprotected_name, protected_name = RESOURCE_TYPE_MAP[resource_type]
    resource_name = protected_name if protected else unprotected_name
    
    # Build the full module path
    if sub_module:
        return f'module.{module_name}.{sub_module}.{tf_type}.{resource_name}["{key}"]'
    else:
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

        # Check extended attributes
        for ext in project.get("extended_attributes", []):
            ext_key = ext.get("key", "")
            composite_key = f"{project_key}_{ext_key}"
            if ext.get("protected", False):
                protected.append(ProtectedResource(
                    resource_key=composite_key,
                    resource_type="EXTATTR",
                    name=ext_key,
                    protected=True,
                ))

        # Check environment variables
        for env_var in project.get("environment_variables", []):
            env_var_name = env_var.get("name", "")
            composite_key = f"{project_key}_{env_var_name}"
            if env_var.get("protected", False):
                protected.append(ProtectedResource(
                    resource_key=composite_key,
                    resource_type="VAR",
                    name=env_var_name,
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

    # region agent log
    try:
        _agent_debug_log(
            "D4",
            "protection_manager.py:extract_protected_resources",
            "extracted protected resources from yaml",
            {
                "protected_count": len(protected),
                "has_globals_groups": bool(globals_config.get("groups")),
                "globals_group_keys": [g.get("key", "") for g in globals_config.get("groups", [])[:10]],
                "protected_group_keys_in_yaml": [
                    g.get("key", "") for g in globals_config.get("groups", []) if g.get("protected", False)
                ][:10],
                "contains_member_in_extracted": any(r.resource_key == "member" for r in protected),
                "extracted_types": sorted({r.resource_type for r in protected}),
            },
        )
    except Exception:
        pass
    # endregion
    
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

            for ext in project.get("extended_attributes", []):
                ext_key = ext.get("key", "")
                composite_key = f"{project_key}_{ext_key}"
                result[("EXTATTR", composite_key)] = (ext_key, ext.get("protected", False))

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
            "JCTG": "Job Completion Trigger",
            "JEVO": "Env Var Job Override",
            "REP": "Repository",
            "EXTATTR": "Extended Attributes",
            "VAR": "Env Variable",
            "CON": "Connection",
            "TOK": "Service Token",
            "GRP": "Group",
            "NOT": "Notification",
            "ACFT": "Account Features",
            "IPRST": "IP Restrictions Rule",
            "LNGI": "Lineage Integration",
            "OAUTH": "OAuth Configuration",
            "PARFT": "Project Artefacts",
            "USRGRP": "User Groups",
            "SLCFG": "Semantic Layer Config",
            "SLSTM": "SL Credential Mapping",
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


@traced(log_result=True)
def generate_moved_blocks_from_state(
    yaml_config: dict,
    state_file: str,
) -> list[ProtectionChange]:
    """Generate protection changes by comparing YAML config with Terraform state.
    
    This is used when there's no previous YAML to compare against, such as after
    terraform apply when the user changes protection status.
    
    Args:
        yaml_config: Current YAML configuration (with protection flags)
        state_file: Path to terraform.tfstate file
        
    Returns:
        List of ProtectionChange objects for resources that need to be moved
    """
    import json
    
    changes = []
    
    try:
        with open(state_file, "r") as f:
            state = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read state file {state_file}: {e}")
        return changes
    
    # Build map of YAML protection status
    yaml_protection: dict[tuple[str, str], bool] = {}  # (type, key) -> protected
    
    # Track project keys for later linking with repositories
    project_keys = set()
    
    # Protection model:
    # - PRJ protection is INDEPENDENT (does NOT cascade to children)
    # - REP protection → PREP protection (linked)
    # - ENV protection is INDEPENDENT (explicit only, NOT inherited from PRJ)
    # - JOB protection is INDEPENDENT (explicit only, NOT inherited from PRJ)
    
    for project in yaml_config.get("projects", []):
        project_key = project.get("key", "")
        project_protected = project.get("protected", False)
        yaml_protection[("PRJ", project_key)] = project_protected
        project_keys.add(project_key)
        
        # Environments - only protected if EXPLICITLY marked, NOT inherited from project
        for env in project.get("environments", []):
            env_key = env.get("key", "")
            composite_key = f"{project_key}_{env_key}"
            yaml_protection[("ENV", composite_key)] = env.get("protected", False)  # Default False, not project_protected
        
        # Jobs - only protected if EXPLICITLY marked, NOT inherited from project
        for job in project.get("jobs", []):
            job_key = job.get("key", "")
            composite_key = f"{project_key}_{job_key}"
            yaml_protection[("JOB", composite_key)] = job.get("protected", False)  # Default False, not project_protected
        
        # Environment Variables - only protected if EXPLICITLY marked, NOT inherited from project
        for var in project.get("environment_variables", []):
            var_key = var.get("key", "") or var.get("name", "")
            composite_key = f"{project_key}_{var_key}"
            yaml_protection[("VAR", composite_key)] = var.get("protected", False)  # Default False, not project_protected
    
    # Process repositories - PREP inherits protection from REP
    # NOTE: YAML repo keys are like "dbt_ep_bt_data_ops_db" but Terraform uses "bt_data_ops_db"
    # So we need to store protection under BOTH keys for proper lookup
    for repo in yaml_config.get("globals", {}).get("repositories", []):
        repo_key = repo.get("key", "")
        repo_protected = repo.get("protected", False)
        yaml_protection[("REP", repo_key)] = repo_protected
        
        # PREP (project_repository) protection follows REP, not PRJ
        # The PREP Terraform key matches the project key, but we need to find which project
        # corresponds to this repository. The repo key often has a prefix like "dbt_ep_"
        # and the project key is embedded in it (e.g., "dbt_ep_bt_data_ops_db" -> "bt_data_ops_db")
        for project_key in project_keys:
            # Check if repo key contains the project key (common pattern: dbt_ep_{project_key})
            if project_key in repo_key or repo_key.endswith(project_key):
                # Store REP protection under project_key as well (for Terraform state lookup)
                yaml_protection[("REP", project_key)] = repo_protected
                yaml_protection[("PREP", project_key)] = repo_protected
                break

    # region agent log
    _agent_debug_log(
        "H2",
        "protection_manager.py:generate_moved_blocks_from_state",
        "yaml protection snapshot for sse_dm_fin_fido",
        {
            "state_file": str(state_file),
            "yaml_PRJ": yaml_protection.get(("PRJ", "sse_dm_fin_fido")),
            "yaml_REP": yaml_protection.get(("REP", "sse_dm_fin_fido")),
            "yaml_PREP": yaml_protection.get(("PREP", "sse_dm_fin_fido")),
            "project_count": len(yaml_config.get("projects", [])),
            "repo_count": len(yaml_config.get("globals", {}).get("repositories", [])),
        },
    )
    # endregion
    
    # Parse Terraform state to find current resource locations
    resources = state.get("resources", [])
    
    # Map resource types to their unprotected/protected block names
    type_map = {
        "dbtcloud_project": ("PRJ", "projects", "protected_projects"),
        "dbtcloud_environment": ("ENV", "environments", "protected_environments"),
        "dbtcloud_job": ("JOB", "jobs", "protected_jobs"),
        "dbtcloud_repository": ("REP", "repositories", "protected_repositories"),
        "dbtcloud_project_repository": ("PREP", "project_repositories", "protected_project_repositories"),
        "dbtcloud_environment_variable": ("VAR", "environment_variables", "protected_environment_variables"),
    }
    
    for resource in resources:
        resource_type = resource.get("type", "")
        resource_name = resource.get("name", "")
        
        if resource_type not in type_map:
            continue
        
        type_code, unprotected_name, protected_name = type_map[resource_type]
        
        # Determine if resource is currently in protected or unprotected block
        state_protected = (resource_name == protected_name)
        
        # Process each instance
        for instance in resource.get("instances", []):
            index_key = instance.get("index_key", "")
            if not index_key:
                continue
            
            # Check YAML protection status
            yaml_protected = yaml_protection.get((type_code, index_key), False)
            
            # If mismatch, generate a change
            if yaml_protected and not state_protected:
                # YAML says protected, but state has it in unprotected block
                changes.append(ProtectionChange(
                    resource_key=index_key,
                    resource_type=type_code,
                    name=index_key,
                    direction="protect",
                    from_address=get_resource_address(type_code, index_key, protected=False),
                    to_address=get_resource_address(type_code, index_key, protected=True),
                ))
                # region agent log
                if index_key == "sse_dm_fin_fido" and type_code in {"PRJ", "REP", "PREP"}:
                    _agent_debug_log(
                        "H3",
                        "protection_manager.py:generate_moved_blocks_from_state",
                        "detected protect direction for sse_dm_fin_fido",
                        {
                            "resource_type": type_code,
                            "resource_name": resource_name,
                            "index_key": index_key,
                            "yaml_protected": yaml_protected,
                            "state_protected": state_protected,
                        },
                    )
                # endregion
            elif not yaml_protected and state_protected:
                # YAML says unprotected, but state has it in protected block
                changes.append(ProtectionChange(
                    resource_key=index_key,
                    resource_type=type_code,
                    name=index_key,
                    direction="unprotect",
                    from_address=get_resource_address(type_code, index_key, protected=True),
                    to_address=get_resource_address(type_code, index_key, protected=False),
                ))
                # region agent log
                if index_key == "sse_dm_fin_fido" and type_code in {"PRJ", "REP", "PREP"}:
                    _agent_debug_log(
                        "H3",
                        "protection_manager.py:generate_moved_blocks_from_state",
                        "detected unprotect direction for sse_dm_fin_fido",
                        {
                            "resource_type": type_code,
                            "resource_name": resource_name,
                            "index_key": index_key,
                            "yaml_protected": yaml_protected,
                            "state_protected": state_protected,
                        },
                    )
                # endregion
    
    # region agent log
    fido_changes = [
        {"type": c.resource_type, "direction": c.direction, "from": c.from_address, "to": c.to_address}
        for c in changes
        if c.resource_key == "sse_dm_fin_fido"
    ]
    _agent_debug_log(
        "H4",
        "protection_manager.py:generate_moved_blocks_from_state",
        "generated changes summary for sse_dm_fin_fido",
        {"fido_change_count": len(fido_changes), "fido_changes": fido_changes},
    )
    # endregion

    logger.info(f"State-based protection detection found {len(changes)} change(s)")
    return changes


@traced(log_result=True)
def write_moved_blocks_file(
    changes: list[ProtectionChange],
    output_dir: Union[str, Path],
    filename: str = "protection_moves.tf",
    preserve_existing: bool = True,
) -> Optional[Path]:
    """Write moved blocks to a Terraform file.
    
    Args:
        changes: List of protection changes
        output_dir: Directory to write to
        filename: Output filename
        preserve_existing: If True, preserve existing manual blocks and append new ones
        
    Returns:
        Path to the file if written, None if no changes
    """
    if not changes:
        return None
    
    output_path = Path(output_dir) / filename
    new_content = generate_moved_blocks(changes)
    
    # If preserve_existing is True and file exists, check for existing blocks
    if preserve_existing and output_path.exists():
        existing_content = output_path.read_text(encoding="utf-8")
        
        # Don't overwrite if the file has substantial content that's not just a placeholder
        if existing_content.strip() and not existing_content.strip().startswith("# Protection moves cleared"):
            # Extract resource keys from new changes to avoid duplicates
            new_keys = set()
            for change in changes:
                new_keys.add(f'"{change.resource_key}"')
            
            # Check if any of our new keys already exist in the file
            has_overlap = any(key in existing_content for key in new_keys)
            
            if not has_overlap:
                # No overlap - append new blocks to existing content
                merged_content = existing_content.rstrip() + "\n\n# Additional protection changes (auto-detected)\n" + new_content
                output_path.write_text(merged_content, encoding="utf-8")
                logger.info(f"Appended {len(changes)} moved block(s) to existing {output_path}")
                return output_path
            else:
                # Overlap exists - preserve existing file, don't overwrite
                logger.info(f"Skipping write to {output_path} - existing file contains matching resources")
                return output_path
    
    # No existing file or preserve_existing is False - write new content
    output_path.write_text(new_content, encoding="utf-8")
    # region agent log
    fido_lines = [line for line in new_content.splitlines() if "sse_dm_fin_fido" in line]
    _agent_debug_log(
        "H5",
        "protection_manager.py:write_moved_blocks_file",
        "wrote protection_moves content for sse_dm_fin_fido",
        {
            "output_path": str(output_path),
            "change_count": len(changes),
            "fido_line_count": len(fido_lines),
            "fido_lines": fido_lines,
        },
    )
    # endregion
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
        "JCTG": "Job Completion Trigger",
        "JEVO": "Env Var Job Override",
        "REP": "Repository",
        "EXTATTR": "Extended Attributes",
        "VAR": "Env Variable",
        "CON": "Connection",
        "TOK": "Service Token",
        "GRP": "Group",
        "NOT": "Notification",
        "ACFT": "Account Features",
        "IPRST": "IP Restrictions Rule",
        "LNGI": "Lineage Integration",
        "OAUTH": "OAuth Configuration",
        "PARFT": "Project Artefacts",
        "USRGRP": "User Groups",
        "SLCFG": "Semantic Layer Config",
        "SLSTM": "SL Credential Mapping",
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
    "JCTG": "Job Completion Trigger",
    "JEVO": "Env Var Job Override",
    "REP": "Repository",
    "CON": "Connection",
    "VAR": "Env Variable",
    "CRD": "Credential",
    "TOK": "Service Token",
    "GRP": "Group",
    "NOT": "Notification",
    "EXTATTR": "Extended Attributes",
    "ACFT": "Account Features",
    "IPRST": "IP Restrictions Rule",
    "LNGI": "Lineage Integration",
    "OAUTH": "OAuth Configuration",
    "PARFT": "Project Artefacts",
    "USRGRP": "User Groups",
    "SLCFG": "Semantic Layer Configuration",
    "SLSTM": "Semantic Layer Credential Mapping",
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
    
    # ENV↔EXTATTR linked-resource cascade: add linked EXTATTR when protecting ENV, linked ENV(s) when protecting EXTATTR
    entity_type = entity.get("element_type_code", "")
    if entity_type == "ENV":
        ext_key = entity.get("extended_attributes_key") or ""
        project_key = entity.get("project_key") or (source_key.rsplit("_", 1)[0] if "_" in source_key else "")
        if ext_key and project_key:
            eat_composite = f"{project_key}_{ext_key}"
            for item in source_items:
                if item.get("element_type_code") == "EXTATTR" and (item.get("key") or item.get("element_mapping_id")) == eat_composite:
                    eat_key = item.get("key") or item.get("element_mapping_id")
                    if eat_key and eat_key not in already_protected:
                        parents_to_protect.append(CascadeResource(
                            key=eat_key,
                            name=item.get("name", ext_key),
                            resource_type="EXTATTR",
                        ))
                    break
    elif entity_type == "EXTATTR":
        project_key = entity.get("project_key") or (source_key.rsplit("_", 1)[0] if "_" in source_key else "")
        # ext_key is the extended-attributes key (name), not the composite resource key
        ext_key = entity.get("name") or (source_key.rsplit("_", 1)[1] if "_" in source_key else "")
        if project_key and ext_key:
            for item in source_items:
                if item.get("element_type_code") != "ENV":
                    continue
                item_project = item.get("project_key") or (item.get("key") or "").rsplit("_", 1)[0] if "_" in (item.get("key") or "") else ""
                if item_project != project_key:
                    continue
                if (item.get("extended_attributes_key") or "") != ext_key:
                    continue
                env_key = item.get("key") or item.get("element_mapping_id")
                if env_key and env_key not in already_protected:
                    parents_to_protect.append(CascadeResource(
                        key=env_key,
                        name=item.get("name", env_key),
                        resource_type="ENV",
                    ))

    # Sort parents by depth (project first, then environment, etc.)
    type_order = {"PRJ": 1, "ENV": 2, "EXTATTR": 2, "VAR": 3, "JOB": 4, "CRD": 5, "REP": 6}
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

    # ENV↔EXTATTR linked-resource cascade: add linked EXTATTR when unprotecting ENV, linked ENV(s) when unprotecting EXTATTR
    entity_type = entity.get("element_type_code", "")
    if entity_type == "ENV":
        ext_key = entity.get("extended_attributes_key") or ""
        project_key = entity.get("project_key") or (source_key.rsplit("_", 1)[0] if "_" in source_key else "")
        if ext_key and project_key:
            eat_composite = f"{project_key}_{ext_key}"
            if eat_composite in protected_resources:
                for item in source_items:
                    if item.get("element_type_code") == "EXTATTR" and (item.get("key") or item.get("element_mapping_id")) == eat_composite:
                        protected_children.append(CascadeResource(
                            key=eat_composite,
                            name=item.get("name", ext_key),
                            resource_type="EXTATTR",
                        ))
                        break
    elif entity_type == "EXTATTR":
        project_key = entity.get("project_key") or (source_key.rsplit("_", 1)[0] if "_" in source_key else "")
        ext_key = entity.get("name") or (source_key.rsplit("_", 1)[1] if "_" in source_key else "")
        if project_key and ext_key:
            for item in source_items:
                if item.get("element_type_code") != "ENV":
                    continue
                item_project = item.get("project_key") or (item.get("key") or "").rsplit("_", 1)[0] if "_" in (item.get("key") or "") else ""
                if item_project != project_key or (item.get("extended_attributes_key") or "") != ext_key:
                    continue
                env_key = item.get("key") or item.get("element_mapping_id")
                if env_key and env_key in protected_resources:
                    protected_children.append(CascadeResource(
                        key=env_key,
                        name=item.get("name", env_key),
                        resource_type="ENV",
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


# ============================================================================
# Protection Mismatch Detection and Repair
# ============================================================================

@dataclass
class ProtectionMismatch:
    """A mismatch between YAML config and Terraform state protection status."""
    
    resource_key: str  # e.g., "sse_dm_fin_fido"
    resource_type: str  # PRJ, REP, PREP (project_repository)
    yaml_protected: bool  # Protection status in YAML
    state_protected: bool  # Protection status in Terraform state
    state_address: str  # Current address in state
    expected_address: str  # Expected address based on YAML
    
    @property
    def needs_move_to_protected(self) -> bool:
        """True if resource needs to move from unprotected to protected."""
        return self.yaml_protected and not self.state_protected
    
    @property
    def needs_move_to_unprotected(self) -> bool:
        """True if resource needs to move from protected to unprotected."""
        return not self.yaml_protected and self.state_protected
    
    @property
    def move_direction(self) -> str:
        """'protect' or 'unprotect'."""
        return "protect" if self.needs_move_to_protected else "unprotect"


@dataclass
class ProtectionRepairResult:
    """Result of protection mismatch detection and repair."""
    
    mismatches: list[ProtectionMismatch]
    moved_blocks_content: str
    repair_applied: bool = False
    repair_path: Optional[Path] = None
    error_message: Optional[str] = None


# Extended resource type map including project_repository and extended_attributes
EXTENDED_RESOURCE_TYPE_MAP = {
    "PRJ": ("dbtcloud_project", "projects", "protected_projects"),
    "REP": ("dbtcloud_repository", "repositories", "protected_repositories"),
    "PREP": ("dbtcloud_project_repository", "project_repositories", "protected_project_repositories"),
    "ENV": ("dbtcloud_environment", "environments", "protected_environments"),
    "JOB": ("dbtcloud_job", "jobs", "protected_jobs"),
    "JCTG": ("dbtcloud_job_completion_trigger", "job_completion_triggers", "protected_job_completion_triggers"),
    "JEVO": ("dbtcloud_environment_variable_job_override", "environment_variable_job_overrides", "protected_environment_variable_job_overrides"),
    "EXTATTR": ("dbtcloud_extended_attributes", "extended_attrs", "protected_extended_attrs"),
    "VAR": ("dbtcloud_environment_variable", "environment_variables", "protected_environment_variables"),
    # Global resources — protected variants with lifecycle.prevent_destroy
    "GRP": ("dbtcloud_group", "groups", "protected_groups"),
    "CON": ("dbtcloud_global_connection", "connections", "protected_connections"),
    "TOK": ("dbtcloud_service_token", "service_tokens", "protected_service_tokens"),
    # --- S4: Account-level ---
    "ACFT": ("dbtcloud_account_features", "account_features", "protected_account_features"),
    "IPRST": ("dbtcloud_ip_restrictions_rule", "ip_restrictions_rules", "protected_ip_restrictions_rules"),
    "LNGI": ("dbtcloud_lineage_integration", "lineage_integrations", "protected_lineage_integrations"),
    "OAUTH": ("dbtcloud_oauth_configuration", "oauth_configurations", "protected_oauth_configurations"),
    # --- S5: Project-level ---
    "PARFT": ("dbtcloud_project_artefacts", "project_artefacts", "protected_project_artefacts"),
    "USRGRP": ("dbtcloud_user_groups", "user_groups", "protected_user_groups"),
    # --- S6: Semantic Layer ---
    "SLCFG": ("dbtcloud_semantic_layer_configuration", "semantic_layer_configurations", "protected_semantic_layer_configurations"),
    "SLSTM": ("dbtcloud_semantic_layer_credential_service_token_mapping", "semantic_layer_credential_service_token_mappings", "protected_semantic_layer_credential_service_token_mappings"),
}


@dataclass
class SingleResourceProtectionInfo:
    """Protection analysis for a single resource."""
    
    resource_type: str
    resource_key: str
    state_protected: Optional[bool]  # None if not in state
    yaml_protected: bool
    has_mismatch: bool
    mismatch_direction: Optional[str]  # "protect" or "unprotect" or None
    linked_resources: list[str]  # For REP/PREP, lists related resource types that would also need moving
    
    @property
    def state_address_prefix(self) -> str:
        """Get the state address prefix (protected vs unprotected)."""
        if self.state_protected is None:
            return "not_in_state"
        tf_type, unprotected, protected = EXTENDED_RESOURCE_TYPE_MAP.get(
            self.resource_type, ("unknown", "unknown", "unknown")
        )
        return protected if self.state_protected else unprotected
    
    @property
    def expected_address_prefix(self) -> str:
        """Get the expected address prefix based on YAML."""
        tf_type, unprotected, protected = EXTENDED_RESOURCE_TYPE_MAP.get(
            self.resource_type, ("unknown", "unknown", "unknown")
        )
        return protected if self.yaml_protected else unprotected


def check_single_resource_protection(
    resource_type: str,
    resource_key: str,
    state_address: Optional[str],
    yaml_protected: bool,
    project_has_repository: bool = True,
) -> SingleResourceProtectionInfo:
    """Check protection status for a single resource.
    
    This is useful for diagnostic displays and per-row analysis.
    
    Args:
        resource_type: Element type code (PRJ, ENV, JOB, REP, PREP)
        resource_key: Resource key (e.g., project name for REP)
        state_address: Full Terraform state address (None if not in state)
        yaml_protected: Whether the resource should be protected per YAML
        project_has_repository: Whether the project has a repository (for REP/PREP linking)
        
    Returns:
        SingleResourceProtectionInfo with analysis
    """
    # Determine state protection status from address
    state_protected: Optional[bool] = None
    if state_address:
        state_protected = "protected_" in state_address
    
    # Determine if there's a mismatch
    has_mismatch = False
    mismatch_direction = None
    
    if state_protected is not None and state_protected != yaml_protected:
        has_mismatch = True
        mismatch_direction = "protect" if yaml_protected else "unprotect"
    
    # Determine linked resources
    linked_resources = []
    if resource_type in ("REP", "PREP") and project_has_repository:
        # REP and PREP are linked to each other
        if resource_type == "REP":
            linked_resources = ["PREP"]
        else:
            linked_resources = ["REP"]
    
    return SingleResourceProtectionInfo(
        resource_type=resource_type,
        resource_key=resource_key,
        state_protected=state_protected,
        yaml_protected=yaml_protected,
        has_mismatch=has_mismatch,
        mismatch_direction=mismatch_direction,
        linked_resources=linked_resources,
    )


@traced(log_result=True)
def detect_protection_mismatches(
    yaml_config: dict,
    terraform_state: dict,
    module_prefix: str = "module.dbt_cloud.module.projects_v2[0]",
) -> list[ProtectionMismatch]:
    """Detect mismatches between YAML protection status and Terraform state.
    
    This checks if resources in state are in the correct protected/unprotected
    resource block based on the YAML configuration.
    
    Protection rules:
    - Project (PRJ): Completely independent - can be protected/unprotected on its own
    - Repository (REP) and Project_Repository (PREP): Linked to EACH OTHER (not to project)
      - If REP is protected, PREP must also be protected
      - If PREP is protected, REP must also be protected
      - Their expected protection status comes from the YAML project config
    
    Args:
        yaml_config: Parsed YAML configuration
        terraform_state: Parsed terraform.tfstate JSON
        module_prefix: Module path prefix for resources
        
    Returns:
        List of detected mismatches
    """
    mismatches = []
    
    # Build map of project keys and their protection status from YAML
    # Also track which projects have repositories
    yaml_protection = {}  # key -> protected (bool)
    projects_with_repos = set()  # keys of projects that have repositories
    
    for project in yaml_config.get("projects", []):
        project_key = project.get("key", "")
        if project_key:
            yaml_protection[project_key] = project.get("protected", False)
            # Check if project has a repository reference
            if project.get("repository"):
                projects_with_repos.add(project_key)
    
    # Parse Terraform state to find resource addresses
    state_resources = {}  # (type, key) -> info dict
    
    for resource in terraform_state.get("resources", []):
        module = resource.get("module", "")
        rtype = resource.get("type", "")
        name = resource.get("name", "")
        
        # Only process relevant dbt Cloud resources
        if not rtype.startswith("dbtcloud_"):
            continue
        
        for inst in resource.get("instances", []):
            index_key = inst.get("index_key")
            if index_key is None:
                continue
            
            # Build full address
            if module:
                base = f"{module}.{rtype}.{name}"
            else:
                base = f"{rtype}.{name}"
            
            if isinstance(index_key, str):
                full_address = f'{base}["{index_key}"]'
            else:
                full_address = f"{base}[{index_key}]"
            
            # Determine if in protected or unprotected block
            is_protected_in_state = "protected_" in name
            
            # Map resource type to our codes
            type_code = None
            if rtype == "dbtcloud_project":
                type_code = "PRJ"
            elif rtype == "dbtcloud_repository":
                type_code = "REP"
            elif rtype == "dbtcloud_project_repository":
                type_code = "PREP"
            elif rtype == "dbtcloud_extended_attributes":
                type_code = "EXTATTR"
            elif rtype == "dbtcloud_environment_variable":
                type_code = "VAR"
            elif rtype == "dbtcloud_environment":
                type_code = "ENV"
            elif rtype == "dbtcloud_job":
                type_code = "JOB"
            
            if type_code:
                state_resources[(type_code, index_key)] = {
                    "address": full_address,
                    "protected": is_protected_in_state,
                    "name": name,
                    "module": module,
                }
    
    # Build per-resource protection map from YAML (environments, jobs, env vars)
    # These use individual protected flags, not the project-level flag
    sub_resource_protection = {}  # (type_code, tf_key) -> yaml_protected
    
    for project in yaml_config.get("projects", []):
        project_key = project.get("key", "")
        if not project_key:
            continue
        
        # Environments: TF key = "{project_key}_{env_key}"
        for env in project.get("environments", []):
            env_key = env.get("key", "")
            if env_key:
                tf_key = f"{project_key}_{env_key}"
                sub_resource_protection[("ENV", tf_key)] = env.get("protected", False)
        
        # Jobs at project level: TF key = "{project_key}_{job_key}"
        for job in project.get("jobs", []):
            job_key = job.get("key", "")
            if job_key:
                tf_key = f"{project_key}_{job_key}"
                sub_resource_protection[("JOB", tf_key)] = job.get("protected", False)
        
        # Jobs within environments (legacy structure)
        for env in project.get("environments", []):
            for job in env.get("jobs", []):
                job_key = job.get("key", "")
                if job_key:
                    tf_key = f"{project_key}_{job_key}"
                    sub_resource_protection[("JOB", tf_key)] = job.get("protected", False)
        
        # Environment variables: TF key = "{project_key}_{var_name}"
        for var in project.get("environment_variables", []):
            var_name = var.get("name", "")
            if var_name:
                tf_key = f"{project_key}_{var_name}"
                sub_resource_protection[("VAR", tf_key)] = var.get("protected", False)
    
    # Compare YAML protection with state for each project
    for project_key, yaml_protected in yaml_protection.items():
        # Check PROJECT protection status - completely independent
        prj_state_info = state_resources.get(("PRJ", project_key))
        if prj_state_info:
            state_protected = prj_state_info["protected"]
            if yaml_protected != state_protected:
                tf_type, unprotected_name, protected_name = EXTENDED_RESOURCE_TYPE_MAP["PRJ"]
                resource_name = protected_name if yaml_protected else unprotected_name
                expected_address = f'{module_prefix}.{tf_type}.{resource_name}["{project_key}"]'
                
                mismatches.append(ProtectionMismatch(
                    resource_key=project_key,
                    resource_type="PRJ",
                    yaml_protected=yaml_protected,
                    state_protected=state_protected,
                    state_address=prj_state_info["address"],
                    expected_address=expected_address,
                ))
        
        # Check REPOSITORY and PROJECT_REPOSITORY
        # These are linked to EACH OTHER - if one needs to move, both need to move
        # Only check if project has a repository
        if project_key not in projects_with_repos:
            continue
        
        rep_state_info = state_resources.get(("REP", project_key))
        prep_state_info = state_resources.get(("PREP", project_key))
        
        # Check if either REP or PREP has a mismatch with YAML protection
        rep_needs_move = rep_state_info and rep_state_info["protected"] != yaml_protected
        prep_needs_move = prep_state_info and prep_state_info["protected"] != yaml_protected
        
        # If either needs to move, add mismatches for BOTH (they're linked)
        if rep_needs_move or prep_needs_move:
            # Add REP mismatch if it exists in state
            if rep_state_info:
                tf_type, unprotected_name, protected_name = EXTENDED_RESOURCE_TYPE_MAP["REP"]
                resource_name = protected_name if yaml_protected else unprotected_name
                expected_address = f'{module_prefix}.{tf_type}.{resource_name}["{project_key}"]'
                
                mismatches.append(ProtectionMismatch(
                    resource_key=project_key,
                    resource_type="REP",
                    yaml_protected=yaml_protected,
                    state_protected=rep_state_info["protected"],
                    state_address=rep_state_info["address"],
                    expected_address=expected_address,
                ))
            
            # Add PREP mismatch if it exists in state
            if prep_state_info:
                tf_type, unprotected_name, protected_name = EXTENDED_RESOURCE_TYPE_MAP["PREP"]
                resource_name = protected_name if yaml_protected else unprotected_name
                expected_address = f'{module_prefix}.{tf_type}.{resource_name}["{project_key}"]'
                
                mismatches.append(ProtectionMismatch(
                    resource_key=project_key,
                    resource_type="PREP",
                    yaml_protected=yaml_protected,
                    state_protected=prep_state_info["protected"],
                    state_address=prep_state_info["address"],
                    expected_address=expected_address,
                ))
    
    # Compare sub-resource protection (ENV, JOB, VAR) with TF state
    for (type_code, tf_key), yaml_sub_protected in sub_resource_protection.items():
        state_info = state_resources.get((type_code, tf_key))
        if state_info and state_info["protected"] != yaml_sub_protected:
            if type_code in EXTENDED_RESOURCE_TYPE_MAP:
                tf_type, unprotected_name, protected_name = EXTENDED_RESOURCE_TYPE_MAP[type_code]
                resource_name = protected_name if yaml_sub_protected else unprotected_name
                expected_address = f'{module_prefix}.{tf_type}.{resource_name}["{tf_key}"]'
                
                mismatches.append(ProtectionMismatch(
                    resource_key=tf_key,
                    resource_type=type_code,
                    yaml_protected=yaml_sub_protected,
                    state_protected=state_info["protected"],
                    state_address=state_info["address"],
                    expected_address=expected_address,
                ))
    
    return mismatches


def generate_repair_moved_blocks(
    mismatches: list[ProtectionMismatch],
    module_prefix: str = "module.dbt_cloud.module.projects_v2[0]",
) -> str:
    """Generate Terraform moved blocks to repair protection mismatches.
    
    Args:
        mismatches: List of detected mismatches
        module_prefix: Module path prefix
        
    Returns:
        Terraform HCL content with moved blocks
    """
    if not mismatches:
        return ""
    
    lines = [
        "# Generated moved blocks for protection status changes",
        "# These tell Terraform to move existing resources between protected/unprotected blocks",
        "# without destroying and recreating them",
        "",
    ]
    
    # Group mismatches by project key for better organization
    by_project = {}
    for m in mismatches:
        if m.resource_key not in by_project:
            by_project[m.resource_key] = []
        by_project[m.resource_key].append(m)
    
    type_names = {
        "PRJ": "project",
        "ENV": "environment",
        "JOB": "job",
        "JCTG": "job_completion_trigger",
        "JEVO": "environment_variable_job_override",
        "REP": "repository",
        "PREP": "project_repository link",
        "EXTATTR": "extended_attributes",
        "VAR": "environment_variable",
        "GRP": "group",
        "CON": "connection",
        "TOK": "service_token",
        "NOT": "notification",
        "ACFT": "account_features",
        "IPRST": "ip_restrictions_rule",
        "LNGI": "lineage_integration",
        "OAUTH": "oauth_configuration",
        "PARFT": "project_artefacts",
        "USRGRP": "user_groups",
        "SLCFG": "semantic_layer_configuration",
        "SLSTM": "semantic_layer_credential_service_token_mapping",
    }
    
    for project_key, project_mismatches in sorted(by_project.items()):
        direction = project_mismatches[0].move_direction
        action = "protected back to unprotected" if direction == "unprotect" else "unprotected to protected"
        lines.append(f"# Move {project_key} resources from {action}")
        
        for m in sorted(project_mismatches, key=lambda x: x.resource_type):
            tf_type, unprotected_name, protected_name = EXTENDED_RESOURCE_TYPE_MAP[m.resource_type]
            
            # Determine from/to addresses based on direction
            if m.needs_move_to_unprotected:
                from_name = protected_name
                to_name = unprotected_name
            else:
                from_name = unprotected_name
                to_name = protected_name
            
            from_addr = f'{module_prefix}.{tf_type}.{from_name}["{m.resource_key}"]'
            to_addr = f'{module_prefix}.{tf_type}.{to_name}["{m.resource_key}"]'
            
            type_name = type_names.get(m.resource_type, m.resource_type)
            lines.extend([
                f"# Move {type_name} from {('protected' if m.state_protected else 'unprotected')} to {('protected' if m.yaml_protected else 'unprotected')}",
                "moved {",
                f'  from = {from_addr}',
                f'  to   = {to_addr}',
                "}",
                "",
            ])
    
    return "\n".join(lines)


def detect_and_repair_protection_mismatches(
    yaml_path: Union[str, Path],
    terraform_dir: Union[str, Path],
    module_prefix: str = "module.dbt_cloud.module.projects_v2[0]",
    auto_repair: bool = False,
) -> ProtectionRepairResult:
    """Detect protection mismatches and optionally repair them.
    
    This function:
    1. Loads the YAML config and Terraform state
    2. Detects mismatches between protection status
    3. Generates correct moved blocks
    4. Optionally writes the repair file
    
    Args:
        yaml_path: Path to YAML config file
        terraform_dir: Directory containing Terraform files and state
        module_prefix: Module path prefix for resources
        auto_repair: If True, write the repair file automatically
        
    Returns:
        ProtectionRepairResult with mismatches and repair content
    """
    yaml_path = Path(yaml_path)
    terraform_dir = Path(terraform_dir)
    state_file = terraform_dir / "terraform.tfstate"
    
    result = ProtectionRepairResult(mismatches=[], moved_blocks_content="")
    
    # Load YAML config
    try:
        yaml_config = load_yaml_config(yaml_path)
    except Exception as e:
        result.error_message = f"Failed to load YAML config: {e}"
        return result
    
    # Load Terraform state
    if not state_file.exists():
        result.error_message = "Terraform state file not found"
        return result
    
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            terraform_state = json.load(f)
    except Exception as e:
        result.error_message = f"Failed to load Terraform state: {e}"
        return result
    
    # Detect mismatches
    result.mismatches = detect_protection_mismatches(
        yaml_config, terraform_state, module_prefix
    )
    
    if not result.mismatches:
        return result
    
    # Generate repair moved blocks
    result.moved_blocks_content = generate_repair_moved_blocks(
        result.mismatches, module_prefix
    )
    
    # Optionally apply repair
    if auto_repair and result.moved_blocks_content:
        repair_path = terraform_dir / "protection_moves.tf"
        try:
            repair_path.write_text(result.moved_blocks_content, encoding="utf-8")
            result.repair_applied = True
            result.repair_path = repair_path
            logger.info(f"Wrote protection repair to {repair_path}")
        except Exception as e:
            result.error_message = f"Failed to write repair file: {e}"
    
    return result


def parse_terraform_validate_errors(output: str) -> list[dict]:
    """Parse terraform validate output for protection-related errors.
    
    Looks for:
    - "Moved object still exists" errors
    - "Instance cannot be destroyed" errors with lifecycle.prevent_destroy
    
    Args:
        output: Combined stdout/stderr from terraform validate
        
    Returns:
        List of dicts with error details
    """
    errors = []
    
    # Pattern for "Moved object still exists"
    # Example: "module.dbt_cloud.module.projects_v2[0].dbtcloud_project.projects["sse_dm_fin_fido"]"
    import re
    
    moved_pattern = re.compile(
        r'Moved object still exists.*?'
        r'from\s+([\w\.\[\]"_]+).*?'
        r'still declared at',
        re.DOTALL | re.IGNORECASE
    )
    
    for match in moved_pattern.finditer(output):
        address = match.group(1).strip()
        errors.append({
            "type": "moved_object_exists",
            "address": address,
            "message": "Resource still exists in original location - move direction may be wrong",
        })
    
    # Pattern for "Instance cannot be destroyed"
    destroy_pattern = re.compile(
        r'Instance cannot be destroyed.*?'
        r'Resource\s+([\w\.\[\]"_]+).*?'
        r'lifecycle\.prevent_destroy',
        re.DOTALL | re.IGNORECASE
    )
    
    for match in destroy_pattern.finditer(output):
        address = match.group(1).strip()
        errors.append({
            "type": "prevent_destroy",
            "address": address,
            "message": "Protected resource would be destroyed - missing moved block",
        })
    
    return errors


def format_mismatches_for_display(mismatches: list[ProtectionMismatch]) -> str:
    """Format mismatches for user display.
    
    Args:
        mismatches: List of mismatches
        
    Returns:
        Human-readable summary
    """
    if not mismatches:
        return "No protection mismatches detected."
    
    lines = [
        f"Found {len(mismatches)} protection mismatch(es):",
        "",
    ]
    
    type_names = {
        "PRJ": "Project",
        "ENV": "Environment",
        "JOB": "Job",
        "JCTG": "Job Completion Trigger",
        "JEVO": "Env Var Job Override",
        "REP": "Repository",
        "PREP": "Project-Repository Link",
        "EXTATTR": "Extended Attributes",
        "VAR": "Env Variable",
        "GRP": "Group",
        "CON": "Connection",
        "TOK": "Service Token",
        "NOT": "Notification",
        "ACFT": "Account Features",
        "IPRST": "IP Restrictions Rule",
        "LNGI": "Lineage Integration",
        "OAUTH": "OAuth Configuration",
        "PARFT": "Project Artefacts",
        "USRGRP": "User Groups",
        "SLCFG": "Semantic Layer Config",
        "SLSTM": "SL Credential Mapping",
    }
    
    by_project = {}
    for m in mismatches:
        if m.resource_key not in by_project:
            by_project[m.resource_key] = []
        by_project[m.resource_key].append(m)
    
    for project_key, project_mismatches in sorted(by_project.items()):
        direction = project_mismatches[0].move_direction
        yaml_status = "protected" if project_mismatches[0].yaml_protected else "unprotected"
        state_status = "protected" if project_mismatches[0].state_protected else "unprotected"
        
        lines.append(f"📦 {project_key}:")
        lines.append(f"   YAML: {yaml_status}, State: {state_status}")
        lines.append(f"   Action needed: Move from {state_status} → {yaml_status}")
        
        for m in project_mismatches:
            type_name = type_names.get(m.resource_type, m.resource_type)
            lines.append(f"   • {type_name}")
        
        lines.append("")
    
    return "\n".join(lines)
