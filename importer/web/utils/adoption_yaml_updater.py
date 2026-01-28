"""Utility to update YAML config with target account values for adopted resources."""

import logging
from pathlib import Path
from typing import Any, Optional, Union

import yaml

logger = logging.getLogger(__name__)


def apply_adoption_overrides(
    yaml_file: str,
    adopt_data: Union[dict, list],
    target_report_items: list[dict],
    output_path: Optional[str] = None,
) -> str:
    """Update YAML config with target values for resources marked for adoption.
    
    For resources with action='adopt', this replaces the source account values
    with the actual target account values so Terraform config matches the target.
    
    Args:
        yaml_file: Path to the source YAML config file
        adopt_data: Either:
            - List of adopt rows from reconcile_adopt_rows (has source_type, target_id, etc.)
            - Dict of source_key -> {action, target_id, ...} (legacy confirmed_mappings format)
        target_report_items: List of report items from target account fetch
        output_path: Optional path to write updated YAML (defaults to overwriting input)
        
    Returns:
        Path to the updated YAML file
    """
    if not adopt_data:
        logger.info("No adoption data to apply")
        return yaml_file
    
    # Normalize to list format
    if isinstance(adopt_data, dict):
        # Legacy format: dict of source_key -> mapping
        adopt_rows = [
            {**mapping, "source_key": key}
            for key, mapping in adopt_data.items()
            if mapping.get("action") == "adopt" and mapping.get("target_id")
        ]
    else:
        # New format: list of adopt rows
        adopt_rows = [
            row for row in adopt_data
            if row.get("target_id")
        ]
    
    if not adopt_rows:
        logger.info("No adoption mappings to apply")
        return yaml_file
    
    logger.info(f"Applying {len(adopt_rows)} adoption overrides to YAML")
    
    # Debug: log adopt rows
    for i, row in enumerate(adopt_rows):
        logger.info(f"  Adopt row {i}: source_key={row.get('source_key')}, source_type={row.get('source_type')}, target_id={row.get('target_id')}")
    
    # Build lookup of target resources by ID and type
    # Note: target report items use element_type_code (not element_type) and dbt_id (not id)
    target_by_id: dict[tuple[str, int], dict] = {}
    for item in target_report_items:
        element_type = item.get("element_type_code") or item.get("element_type") or item.get("type")
        item_id = item.get("dbt_id") or item.get("id")
        if element_type and item_id:
            target_by_id[(element_type, int(item_id))] = item
    
    logger.info(f"  Built target lookup with {len(target_by_id)} entries")
    # Debug: log some sample keys
    sample_keys = list(target_by_id.keys())[:5]
    logger.info(f"  Sample lookup keys: {sample_keys}")
    
    # Load the YAML
    yaml_path = Path(yaml_file)
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)
    
    if not config:
        logger.warning("Empty YAML config")
        return yaml_file
    
    changes_made = 0
    
    # Process each adoption row
    for row in adopt_rows:
        source_key = row.get("source_key")
        target_id = row.get("target_id")
        resource_type = row.get("source_type")  # Element code like REP, ENV, JOB
        project_name = row.get("project_name")
        
        if not source_key or not target_id:
            continue
        
        # If we don't have resource_type, try to infer from source_key or skip
        if not resource_type:
            logger.warning(f"No resource type for {source_key}, skipping")
            continue
        
        # Find the target resource data
        try:
            target_id_int = int(target_id)
        except (ValueError, TypeError):
            logger.warning(f"Invalid target_id {target_id} for {source_key}")
            continue
            
        target_data = target_by_id.get((resource_type, target_id_int))
        if not target_data:
            logger.warning(f"Target data not found for {resource_type} ID {target_id}")
            continue
        
        # Apply updates based on resource type
        if resource_type == "REP":
            changes_made += _update_repository(config, source_key, target_data, project_name)
        elif resource_type == "ENV":
            changes_made += _update_environment(config, source_key, target_data)
        elif resource_type == "JOB":
            changes_made += _update_job(config, source_key, target_data)
        elif resource_type == "CON":
            changes_made += _update_connection(config, source_key, target_data)
        # Add more resource types as needed
    
    if changes_made == 0:
        logger.info("No changes made to YAML")
        return yaml_file
    
    # Write the updated YAML
    output_file = output_path or yaml_file
    with open(output_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    logger.info(f"Applied {changes_made} adoption overrides to {output_file}")
    return output_file


def _update_repository(config: dict, source_key: str, target_data: dict, project_name: Optional[str] = None) -> int:
    """Update repository config with target values.
    
    Repositories can be:
    1. Top-level in config["repositories"]
    2. Nested under projects in config["projects"][i]["repositories"]
    """
    # Get target repository details - data may be at top level or in metadata
    # Target report items typically have values at top level (remote_url, git_clone_strategy, etc.)
    metadata = target_data.get("metadata", {})
    
    logger.info(f"  Target data for {source_key}: remote_url={target_data.get('remote_url')}, git_clone_strategy={target_data.get('git_clone_strategy')}, github_installation_id={target_data.get('github_installation_id')}")
    
    # Helper to get value from target_data or metadata
    def get_target_value(key: str) -> Any:
        return target_data.get(key) or metadata.get(key)
    
    def apply_updates(repo: dict) -> bool:
        """Apply target values to a repository config dict."""
        updated = False
        remote_url = get_target_value("remote_url")
        if remote_url:
            old_val = repo.get("remote_url")
            repo["remote_url"] = remote_url
            if old_val != remote_url:
                logger.info(f"  Updated remote_url: {old_val} -> {remote_url}")
                updated = True
        
        git_clone_strategy = get_target_value("git_clone_strategy")
        if git_clone_strategy:
            old_val = repo.get("git_clone_strategy")
            repo["git_clone_strategy"] = git_clone_strategy
            if old_val != git_clone_strategy:
                logger.info(f"  Updated git_clone_strategy: {old_val} -> {git_clone_strategy}")
                updated = True
        
        github_installation_id = get_target_value("github_installation_id")
        if github_installation_id:
            old_val = repo.get("github_installation_id")
            repo["github_installation_id"] = github_installation_id
            if old_val != github_installation_id:
                logger.info(f"  Updated github_installation_id: {old_val} -> {github_installation_id}")
                updated = True
        elif "github_installation_id" in repo and not github_installation_id:
            # Target report doesn't have github_installation_id, but if strategy is github_app,
            # we need SOME value to prevent module fallback to deploy_key
            # Keep the existing value for now - it won't affect the resource identity
            # The module will discover the actual target account's installation ID at runtime
            target_strategy = get_target_value("git_clone_strategy")
            if target_strategy == "github_app":
                logger.info(f"  Keeping existing github_installation_id={repo.get('github_installation_id')} (target uses github_app but report doesn't include installation_id)")
            else:
                # Remove if not using github_app
                old_val = repo.pop("github_installation_id", None)
                logger.info(f"  Removed github_installation_id: {old_val}")
                updated = True
        return updated
    
    # Extract the repo key from source_key
    # Format could be "repo_key" or "project_key_repo_key"
    repo_key = source_key
    
    # First check top-level repositories
    for repo in config.get("repositories", []):
        if repo.get("key") == repo_key:
            if apply_updates(repo):
                logger.info(f"Updated top-level repository {repo_key} with target values")
                return 1
    
    # Check globals.repositories (v2 schema)
    globals_section = config.get("globals", {})
    for repo in globals_section.get("repositories", []):
        if repo.get("key") == repo_key:
            if apply_updates(repo):
                logger.info(f"Updated globals.repositories {repo_key} with target values")
                return 1
    
    # Then check project-level repositories
    for project in config.get("projects", []):
        # If we know the project, filter to it
        if project_name and project.get("name") != project_name and project.get("key") != project_name:
            continue
            
        for repo in project.get("repositories", []):
            # Check if key matches directly or with project prefix
            project_key = project.get("key", "")
            if repo.get("key") == repo_key or f"{project_key}_{repo.get('key')}" == repo_key:
                if apply_updates(repo):
                    logger.info(f"Updated project repository {repo_key} (project: {project.get('name')}) with target values")
                    return 1
    
    logger.warning(f"Repository {repo_key} not found in YAML (checked: repositories, globals.repositories, projects.*.repositories)")
    return 0


def _update_environment(config: dict, source_key: str, target_data: dict) -> int:
    """Update environment config with target values."""
    # Environments are nested under projects
    projects = config.get("projects", [])
    
    for project in projects:
        for env in project.get("environments", []):
            env_key = f"{project.get('key')}_{env.get('key')}"
            if env_key == source_key:
                metadata = target_data.get("metadata", {})
                
                # Update relevant fields
                if metadata.get("name"):
                    env["name"] = metadata["name"]
                if metadata.get("dbt_version"):
                    env["dbt_version"] = metadata["dbt_version"]
                
                logger.info(f"Updated environment {env_key} with target values")
                return 1
    
    return 0


def _update_job(config: dict, source_key: str, target_data: dict) -> int:
    """Update job config with target values."""
    projects = config.get("projects", [])
    
    for project in projects:
        for job in project.get("jobs", []):
            job_key = f"{project.get('key')}_{job.get('key')}"
            if job_key == source_key:
                metadata = target_data.get("metadata", {})
                
                # Update relevant fields
                if metadata.get("name"):
                    job["name"] = metadata["name"]
                if metadata.get("execute_steps"):
                    job["execute_steps"] = metadata["execute_steps"]
                
                logger.info(f"Updated job {job_key} with target values")
                return 1
    
    return 0


def _update_connection(config: dict, source_key: str, target_data: dict) -> int:
    """Update connection config with target values."""
    connections = config.get("connections", [])
    
    for conn in connections:
        if conn.get("key") == source_key:
            metadata = target_data.get("metadata", {})
            
            # Update connection-specific fields
            if metadata.get("name"):
                conn["name"] = metadata["name"]
            
            logger.info(f"Updated connection {source_key} with target values")
            return 1
    
    return 0
