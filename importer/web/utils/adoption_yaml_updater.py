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
    # #region agent log
    import json as _json
    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
        f.write(_json.dumps({"location": "adoption_yaml_updater.py:entry", "message": "apply_adoption_overrides called", "data": {"adopt_data_type": str(type(adopt_data)), "adopt_data_len": len(adopt_data) if adopt_data else 0, "target_items_len": len(target_report_items) if target_report_items else 0}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H0"}) + "\n")
    # #endregion
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
    
    # #region agent log
    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
        adopt_summary = [{"source_key": r.get("source_key"), "source_type": r.get("source_type"), "target_id": r.get("target_id")} for r in adopt_rows]
        f.write(_json.dumps({"location": "adoption_yaml_updater.py:after_normalize", "message": "adopt_rows after normalization", "data": {"adopt_rows_count": len(adopt_rows), "adopt_rows": adopt_summary}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H0b"}) + "\n")
    # #endregion
    
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
        
        # Skip if target_id is the string "None" (common for unmatched resources like credentials)
        if target_id == "None" or target_id is None:
            continue
        
        # If we don't have resource_type, try to infer from source_key or skip
        if not resource_type:
            logger.debug(f"No resource type for {source_key}, skipping")
            continue
        
        # Find the target resource data
        try:
            target_id_int = int(target_id)
        except (ValueError, TypeError):
            logger.debug(f"Invalid target_id {target_id} for {source_key}")
            continue
            
        target_data = target_by_id.get((resource_type, target_id_int))
        if not target_data:
            logger.warning(f"Target data not found for {resource_type} ID {target_id}")
            continue
        
        # Get protection flag from adoption data
        # IMPORTANT: Default to False - protection should be explicitly opted-in
        # Setting protected=True would move resources to protected_projects collection
        # which requires corresponding moved blocks to avoid destroy+recreate
        protected = row.get("protected", False)
        
        # Apply updates based on resource type
        if resource_type == "REP":
            # region agent log
            try:
                with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                    import json as _json
                    f.write(_json.dumps({"location": "adoption_yaml_updater.py:apply_adoption_overrides:REP", "message": "Processing REP adoption", "data": {"source_key": source_key, "target_id": target_id, "protected": protected, "target_remote_url": target_data.get("remote_url"), "target_git_clone_strategy": target_data.get("git_clone_strategy")}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H1"}) + "\n")
            except: pass
            # endregion
            changes_made += _update_repository(config, source_key, target_data, project_name, protected)
        elif resource_type == "ENV":
            changes_made += _update_environment(config, source_key, target_data, protected)
        elif resource_type == "JOB":
            changes_made += _update_job(config, source_key, target_data, protected)
        elif resource_type == "CON":
            changes_made += _update_connection(config, source_key, target_data, protected)
        elif resource_type == "PRJ":
            changes_made += _update_project(config, source_key, target_data, protected)
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


def _update_repository(config: dict, source_key: str, target_data: dict, project_name: Optional[str] = None, protected: bool = True) -> int:
    """Update repository config with target values.
    
    Repositories can be:
    1. Top-level in config["repositories"]
    2. Nested under projects in config["projects"][i]["repositories"]
    
    Args:
        config: YAML config dict
        source_key: Source resource key
        target_data: Target resource data
        project_name: Optional project name filter
        protected: Whether to mark this resource as protected from destroy
    """
    # Get target repository details - data may be at top level or in metadata
    # Target report items typically have values at top level (remote_url, git_clone_strategy, etc.)
    metadata = target_data.get("metadata", {})
    
    logger.info(f"  Target data for {source_key}: remote_url={target_data.get('remote_url')}, git_clone_strategy={target_data.get('git_clone_strategy')}, github_installation_id={target_data.get('github_installation_id')}, protected={protected}")
    
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
        
        # Set protection status
        if protected:
            repo["protected"] = True
            logger.info(f"  Set protected=True")
            updated = True
        elif "protected" in repo:
            del repo["protected"]
            logger.info(f"  Removed protected flag")
            updated = True
            
        return updated
    
    # Extract the repo key from source_key
    # Format could be "repo_key" or "project_key_repo_key"
    repo_key = source_key
    
    # Build a list of keys to try matching
    # This handles the case where source_key is the project key but the
    # repository has a different key (e.g., project_key="sse_dm_fin_fido" 
    # but repo_key="dbt_ep_sse_dm_fin_fido")
    keys_to_try = [repo_key]
    
    # Check if source_key matches a project key, and if so, get the project's repository reference
    for project in config.get("projects", []):
        if project.get("key") == source_key or project.get("name") == source_key:
            # This project matches the source_key - get its repository reference
            project_repo_ref = project.get("repository")
            if project_repo_ref and project_repo_ref not in keys_to_try:
                keys_to_try.append(project_repo_ref)
                logger.info(f"  Found project '{source_key}' references repository '{project_repo_ref}'")
            break
    
    logger.info(f"  Trying to find repository with keys: {keys_to_try}")
    
    # region agent log
    try:
        with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
            import json as _json
            globals_repo_keys = [r.get("key") for r in config.get("globals", {}).get("repositories", [])]
            f.write(_json.dumps({"location": "adoption_yaml_updater.py:_update_repository:lookup", "message": "Looking for repository", "data": {"keys_to_try": keys_to_try, "globals_repo_keys_sample": globals_repo_keys[:10] if globals_repo_keys else []}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H2"}) + "\n")
    except: pass
    # endregion
    
    # First check top-level repositories
    for repo in config.get("repositories", []):
        if repo.get("key") in keys_to_try:
            if apply_updates(repo):
                logger.info(f"Updated top-level repository {repo.get('key')} with target values")
                return 1
    
    # Check globals.repositories (v2 schema)
    globals_section = config.get("globals", {})
    for repo in globals_section.get("repositories", []):
        if repo.get("key") in keys_to_try:
            # region agent log
            try:
                with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                    import json as _json
                    f.write(_json.dumps({"location": "adoption_yaml_updater.py:_update_repository:found_match", "message": "Found matching repository in globals", "data": {"repo_key": repo.get("key"), "old_remote_url": repo.get("remote_url"), "target_remote_url": target_data.get("remote_url")}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "hypothesisId": "H3"}) + "\n")
            except: pass
            # endregion
            if apply_updates(repo):
                logger.info(f"Updated globals.repositories {repo.get('key')} with target values")
                return 1
    
    # Then check project-level repositories
    for project in config.get("projects", []):
        # If we know the project, filter to it
        if project_name and project.get("name") != project_name and project.get("key") != project_name:
            continue
            
        for repo in project.get("repositories", []):
            # Check if key matches directly or with project prefix
            project_key = project.get("key", "")
            if repo.get("key") in keys_to_try or f"{project_key}_{repo.get('key')}" in keys_to_try:
                if apply_updates(repo):
                    logger.info(f"Updated project repository {repo.get('key')} (project: {project.get('name')}) with target values")
                    return 1
    
    logger.warning(f"Repository not found in YAML for keys: {keys_to_try} (checked: repositories, globals.repositories, projects.*.repositories)")
    return 0


def _update_environment(config: dict, source_key: str, target_data: dict, protected: bool = True) -> int:
    """Update environment config with target values.
    
    Args:
        config: YAML config dict
        source_key: Source resource key (format: project_key_env_key)
        target_data: Target resource data
        protected: Whether to mark this resource as protected from destroy
    """
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
                
                # Set protection status
                if protected:
                    env["protected"] = True
                    logger.info(f"  Set protected=True for environment {env_key}")
                elif "protected" in env:
                    del env["protected"]
                
                logger.info(f"Updated environment {env_key} with target values")
                return 1
    
    return 0


def _update_job(config: dict, source_key: str, target_data: dict, protected: bool = True) -> int:
    """Update job config with target values.
    
    Args:
        config: YAML config dict
        source_key: Source resource key (format: project_key_job_key)
        target_data: Target resource data
        protected: Whether to mark this resource as protected from destroy
    """
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
                
                # Set protection status
                if protected:
                    job["protected"] = True
                    logger.info(f"  Set protected=True for job {job_key}")
                elif "protected" in job:
                    del job["protected"]
                
                logger.info(f"Updated job {job_key} with target values")
                return 1
    
    return 0


def _update_connection(config: dict, source_key: str, target_data: dict, protected: bool = True) -> int:
    """Update connection config with target values.
    
    Args:
        config: YAML config dict
        source_key: Source resource key
        target_data: Target resource data
        protected: Whether to mark this resource as protected from destroy
    """
    connections = config.get("connections", [])
    
    for conn in connections:
        if conn.get("key") == source_key:
            metadata = target_data.get("metadata", {})
            
            # Update connection-specific fields
            if metadata.get("name"):
                conn["name"] = metadata["name"]
            
            # Set protection status
            if protected:
                conn["protected"] = True
                logger.info(f"  Set protected=True for connection {source_key}")
            elif "protected" in conn:
                del conn["protected"]
            
            logger.info(f"Updated connection {source_key} with target values")
            return 1
    
    # Also check globals.connections (v2 schema)
    globals_section = config.get("globals", {})
    for conn in globals_section.get("connections", []):
        if conn.get("key") == source_key:
            metadata = target_data.get("metadata", {})
            
            if metadata.get("name"):
                conn["name"] = metadata["name"]
            
            if protected:
                conn["protected"] = True
                logger.info(f"  Set protected=True for globals.connection {source_key}")
            elif "protected" in conn:
                del conn["protected"]
            
            logger.info(f"Updated globals.connection {source_key} with target values")
            return 1
    
    return 0


def _update_project(config: dict, source_key: str, target_data: dict, protected: bool = True) -> int:
    """Update project config with target values.
    
    Args:
        config: YAML config dict
        source_key: Source resource key
        target_data: Target resource data
        protected: Whether to mark this resource as protected from destroy
    """
    projects = config.get("projects", [])
    
    for project in projects:
        if project.get("key") == source_key:
            metadata = target_data.get("metadata", {})
            
            # Update relevant fields
            if metadata.get("name"):
                project["name"] = metadata["name"]
            
            # Set protection status
            if protected:
                project["protected"] = True
                logger.info(f"  Set protected=True for project {source_key}")
            elif "protected" in project:
                del project["protected"]
            
            logger.info(f"Updated project {source_key} with target values")
            return 1
    
    return 0


def apply_protection_from_set(
    yaml_file: str,
    protected_keys: set[str],
    output_path: Optional[str] = None,
) -> str:
    """Apply protection flag to all resources in the protected_keys set.
    
    This function scans the YAML config and sets protected=True on any
    resources whose key matches one in the protected_keys set.
    
    Args:
        yaml_file: Path to the YAML config file
        protected_keys: Set of source_keys that should be marked as protected.
            Keys may be prefixed with type (e.g., "PRJ:bt_data_ops_db") or unprefixed.
        output_path: Optional path to write updated YAML (defaults to overwriting input)
        
    Returns:
        Path to the updated YAML file
    """
    # #region agent log
    import json as _json_prot
    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
        f.write(_json_prot.dumps({"hypothesisId": "H_APPLY_PROT", "location": "adoption_yaml_updater.py:apply_protection_from_set:entry", "message": "apply_protection_from_set called", "data": {"yaml_file": yaml_file, "protected_keys": list(protected_keys), "output_path": output_path}, "timestamp": __import__("time").time()}) + "\n")
    # #endregion
    
    if not protected_keys:
        logger.info("No protected resources to apply")
        return yaml_file
    
    # Load YAML
    with open(yaml_file, "r") as f:
        config = yaml.safe_load(f)
    
    if not config:
        logger.warning(f"Empty YAML config: {yaml_file}")
        return yaml_file
    
    # Build lookup sets for each resource type from prefixed keys
    # Keys can be "TYPE:key" (e.g., "PRJ:bt_data_ops_db") or just "key"
    project_keys_to_protect = set()
    repo_keys_to_protect = set()
    prep_keys_to_protect = set()  # Project-repository links
    env_keys_to_protect = set()
    job_keys_to_protect = set()
    conn_keys_to_protect = set()
    var_keys_to_protect = set()  # Environment variables
    all_unprefixed = set()  # Fallback for unprefixed keys
    
    for key in protected_keys:
        if ":" in key:
            prefix, resource_key = key.split(":", 1)
            if prefix == "PRJ":
                project_keys_to_protect.add(resource_key)
            elif prefix == "REP":
                repo_keys_to_protect.add(resource_key)
                # REP: uses the project key — also protect the project itself
                # so the TF module sees repository_protected via project.protected
                project_keys_to_protect.add(resource_key)
            elif prefix == "REPO":
                # REPO: is the consolidated repo+project-repo-link intent key.
                # It uses the project key, so protect both repo and project.
                repo_keys_to_protect.add(resource_key)
                prep_keys_to_protect.add(resource_key)
                project_keys_to_protect.add(resource_key)
            elif prefix == "PREP":
                prep_keys_to_protect.add(resource_key)
            elif prefix == "ENV":
                env_keys_to_protect.add(resource_key)
            elif prefix == "JOB":
                job_keys_to_protect.add(resource_key)
            elif prefix == "CON":
                conn_keys_to_protect.add(resource_key)
            elif prefix == "VAR":
                var_keys_to_protect.add(resource_key)
            else:
                # Unknown prefix, add to unprefixed set
                all_unprefixed.add(resource_key)
        else:
            # No prefix - add to all sets for backward compatibility
            all_unprefixed.add(key)
    
    updated_count = 0
    projects_in_yaml = [p.get("key") for p in config.get("projects", [])]
    
    # #region agent log
    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
        f.write(_json_prot.dumps({"hypothesisId": "H_APPLY_PROT", "location": "adoption_yaml_updater.py:apply_protection_from_set:projects_loaded", "message": "Projects loaded from YAML", "data": {"num_projects": len(projects_in_yaml), "sample_projects": projects_in_yaml[:10], "project_keys_to_protect": list(project_keys_to_protect), "all_unprefixed": list(all_unprefixed)}, "timestamp": __import__("time").time()}) + "\n")
    # #endregion
    
    # Process projects
    matched_projects = []
    for project in config.get("projects", []):
        project_key = project.get("key", "")
        # Check if project should be protected (PRJ: prefix or unprefixed match)
        if project_key in project_keys_to_protect or project_key in all_unprefixed:
            project["protected"] = True
            updated_count += 1
            matched_projects.append(project_key)
            logger.info(f"  Set protected=True for project {project_key}")
        # Don't remove protection here - that's handled by apply_unprotection_from_set
        
        # Process environments within project
        for env in project.get("environments", []):
            env_key = env.get("key", "")
            full_env_key = f"{project_key}_{env_key}" if env_key else ""
            
            # Check both standalone key and project-prefixed key against ENV keys or unprefixed
            if (env_key in env_keys_to_protect or full_env_key in env_keys_to_protect or 
                env_key in all_unprefixed or full_env_key in all_unprefixed):
                env["protected"] = True
                updated_count += 1
                logger.info(f"  Set protected=True for environment {env_key}")
            
            # Process jobs within environment (legacy structure)
            for job in env.get("jobs", []):
                job_key = job.get("key", "")
                full_job_key = f"{project_key}_{job_key}" if job_key else ""
                
                if (job_key in job_keys_to_protect or full_job_key in job_keys_to_protect or
                    job_key in all_unprefixed or full_job_key in all_unprefixed):
                    job["protected"] = True
                    updated_count += 1
                    logger.info(f"  Set protected=True for job {job_key} (in env)")
        
        # Process jobs at project level (current YAML structure)
        for job in project.get("jobs", []):
            job_key = job.get("key", "")
            full_job_key = f"{project_key}_{job_key}" if job_key else ""
            
            # #region agent log
            import json as _json_prot2
            with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
                f.write(_json_prot2.dumps({"hypothesisId": "H1_JOB_MATCH", "location": "adoption_yaml_updater.py:apply_protection_from_set:project_job_check", "message": "Checking project-level job", "data": {"job_key": job_key, "full_job_key": full_job_key, "in_job_keys": job_key in job_keys_to_protect, "full_in_job_keys": full_job_key in job_keys_to_protect, "job_keys_to_protect": list(job_keys_to_protect)}, "timestamp": __import__("time").time()}) + "\n")
            # #endregion
            
            if (job_key in job_keys_to_protect or full_job_key in job_keys_to_protect or
                job_key in all_unprefixed or full_job_key in all_unprefixed):
                job["protected"] = True
                updated_count += 1
                logger.info(f"  Set protected=True for job {job_key} (project-level)")
        
        # Process repository in project (inline repository definition)
        if "repository" in project and isinstance(project["repository"], dict):
            repo = project["repository"]
            repo_key = repo.get("key", "")
            # Check multiple key formats:
            # 1. repo's own key
            # 2. project_key (repos often use project key as their identifier)
            # 3. project_key_repo suffix format
            possible_keys = [k for k in [repo_key, project_key, f"{project_key}_repo"] if k]
            
            if any(k in repo_keys_to_protect or k in all_unprefixed for k in possible_keys):
                repo["protected"] = True
                updated_count += 1
                logger.info(f"  Set protected=True for repository (keys: {possible_keys})")
        
        # Process environment variables within project
        for env_var in project.get("environment_variables", []):
            env_var_name = env_var.get("name", "")
            # VAR key format: project_key_VAR_NAME (composite key matching TF for_each)
            full_var_key = f"{project_key}_{env_var_name}" if env_var_name else ""
            
            if (env_var_name in var_keys_to_protect or full_var_key in var_keys_to_protect or
                env_var_name in all_unprefixed or full_var_key in all_unprefixed):
                env_var["protected"] = True
                updated_count += 1
                logger.info(f"  Set protected=True for env var {env_var_name} (project {project_key})")
    
    # Process globals section
    globals_section = config.get("globals", {})
    
    # Process global connections
    for conn in globals_section.get("connections", []):
        conn_key = conn.get("key", "")
        if conn_key in conn_keys_to_protect or conn_key in all_unprefixed:
            conn["protected"] = True
            updated_count += 1
            logger.info(f"  Set protected=True for connection {conn_key}")
    
    # Process global repositories
    for repo in globals_section.get("repositories", []):
        repo_key = repo.get("key", "")
        # Check exact match first
        if repo_key in repo_keys_to_protect or repo_key in all_unprefixed:
            repo["protected"] = True
            updated_count += 1
            logger.info(f"  Set protected=True for global repository {repo_key}")
        else:
            # Fuzzy fallback: check if repo_key contains or ends with any
            # protected key.  This handles legacy cases where the normalizer
            # produced a prefixed repo key (e.g. dbt_ep_{project_key}).
            # With the key-alignment fix in the normalizer this path should
            # rarely trigger; log a warning when it does.
            for prot_key in repo_keys_to_protect | all_unprefixed:
                if prot_key and (prot_key in repo_key or repo_key.endswith(prot_key)):
                    repo["protected"] = True
                    updated_count += 1
                    logger.warning(
                        f"  Set protected=True for global repository {repo_key} "
                        f"via fuzzy match on '{prot_key}' — consider aligning "
                        f"the repository key to the project key"
                    )
                    break
    
    # Save updated YAML
    output = output_path or yaml_file
    
    # #region agent log
    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
        f.write(_json_prot.dumps({"hypothesisId": "H_APPLY_PROT", "location": "adoption_yaml_updater.py:apply_protection_from_set:before_save", "message": "About to save YAML", "data": {"output": output, "updated_count": updated_count, "matched_projects": matched_projects}, "timestamp": __import__("time").time()}) + "\n")
    # #endregion
    
    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    # #region agent log
    with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as f:
        f.write(_json_prot.dumps({"hypothesisId": "H_APPLY_PROT", "location": "adoption_yaml_updater.py:apply_protection_from_set:after_save", "message": "YAML saved", "data": {"output": output, "updated_count": updated_count}, "timestamp": __import__("time").time()}) + "\n")
    # #endregion
    
    logger.info(f"Applied protection to {updated_count} resources in {output}")
    
    return output


def apply_unprotection_from_set(
    yaml_file: str,
    unprotected_keys: set[str],
    output_path: Optional[str] = None,
) -> str:
    """Remove protection flag from all resources in the unprotected_keys set.
    
    This function scans the YAML config and removes the protected flag or sets 
    protected=False on any resources whose key matches one in the unprotected_keys set.
    
    Args:
        yaml_file: Path to the YAML config file
        unprotected_keys: Set of source_keys that should have protection removed.
            Keys may be prefixed with type (e.g., "PRJ:bt_data_ops_db") or unprefixed.
        output_path: Optional path to write updated YAML (defaults to overwriting input)
        
    Returns:
        Path to the updated YAML file
    """
    if not unprotected_keys:
        logger.info("No resources to unprotect")
        return yaml_file
    
    # Load YAML
    with open(yaml_file, "r") as f:
        config = yaml.safe_load(f)
    
    if not config:
        logger.warning(f"Empty YAML config: {yaml_file}")
        return yaml_file
    
    # Build lookup sets for each resource type from prefixed keys
    project_keys_to_unprotect = set()
    repo_keys_to_unprotect = set()
    prep_keys_to_unprotect = set()
    env_keys_to_unprotect = set()
    job_keys_to_unprotect = set()
    conn_keys_to_unprotect = set()
    var_keys_to_unprotect = set()  # Environment variables
    all_unprefixed = set()
    
    for key in unprotected_keys:
        if ":" in key:
            prefix, resource_key = key.split(":", 1)
            if prefix == "PRJ":
                project_keys_to_unprotect.add(resource_key)
            elif prefix == "REP":
                repo_keys_to_unprotect.add(resource_key)
                # REP: uses the project key — also unprotect the project itself
                project_keys_to_unprotect.add(resource_key)
            elif prefix == "REPO":
                # REPO: is the consolidated repo+project-repo-link intent key.
                repo_keys_to_unprotect.add(resource_key)
                project_keys_to_unprotect.add(resource_key)
            elif prefix == "PREP":
                prep_keys_to_unprotect.add(resource_key)
            elif prefix == "ENV":
                env_keys_to_unprotect.add(resource_key)
            elif prefix == "JOB":
                job_keys_to_unprotect.add(resource_key)
            elif prefix == "CON":
                conn_keys_to_unprotect.add(resource_key)
            elif prefix == "VAR":
                var_keys_to_unprotect.add(resource_key)
            else:
                all_unprefixed.add(resource_key)
        else:
            all_unprefixed.add(key)
    
    updated_count = 0
    
    # Process projects
    for project in config.get("projects", []):
        project_key = project.get("key", "")
        # Check project key against PRJ keys or unprefixed
        if project_key in project_keys_to_unprotect or project_key in all_unprefixed:
            if "protected" in project:
                del project["protected"]
                updated_count += 1
                logger.info(f"  Removed protection from project {project_key}")
        
        # Process environments within project
        for env in project.get("environments", []):
            env_key = env.get("key", "")
            full_env_key = f"{project_key}_{env_key}" if env_key else ""
            
            if (env_key in env_keys_to_unprotect or full_env_key in env_keys_to_unprotect or
                env_key in all_unprefixed or full_env_key in all_unprefixed):
                if "protected" in env:
                    del env["protected"]
                    updated_count += 1
                    logger.info(f"  Removed protection from environment {env_key}")
            
            # Process jobs within environment (legacy structure)
            for job in env.get("jobs", []):
                job_key = job.get("key", "")
                full_job_key = f"{project_key}_{job_key}" if job_key else ""
                
                if (job_key in job_keys_to_unprotect or full_job_key in job_keys_to_unprotect or
                    job_key in all_unprefixed or full_job_key in all_unprefixed):
                    if "protected" in job:
                        del job["protected"]
                        updated_count += 1
                        logger.info(f"  Removed protection from job {job_key} (in env)")
        
        # Process jobs at project level (current YAML structure)
        for job in project.get("jobs", []):
            job_key = job.get("key", "")
            full_job_key = f"{project_key}_{job_key}" if job_key else ""
            
            if (job_key in job_keys_to_unprotect or full_job_key in job_keys_to_unprotect or
                job_key in all_unprefixed or full_job_key in all_unprefixed):
                if "protected" in job:
                    del job["protected"]
                    updated_count += 1
                    logger.info(f"  Removed protection from job {job_key} (project-level)")
        
        # Process repository in project
        if "repository" in project and isinstance(project["repository"], dict):
            repo = project["repository"]
            repo_key = repo.get("key", "")
            possible_keys = [k for k in [repo_key, project_key, f"{project_key}_repo"] if k]
            
            if any(k in repo_keys_to_unprotect or k in all_unprefixed for k in possible_keys):
                if "protected" in repo:
                    del repo["protected"]
                    updated_count += 1
                    logger.info(f"  Removed protection from repository (key: {repo_key or project_key})")
        
        # Process environment variables within project
        for env_var in project.get("environment_variables", []):
            env_var_name = env_var.get("name", "")
            full_var_key = f"{project_key}_{env_var_name}" if env_var_name else ""
            
            if (env_var_name in var_keys_to_unprotect or full_var_key in var_keys_to_unprotect or
                env_var_name in all_unprefixed or full_var_key in all_unprefixed):
                if "protected" in env_var:
                    del env_var["protected"]
                    updated_count += 1
                    logger.info(f"  Removed protection from env var {env_var_name} (project {project_key})")
    
    # Process globals section
    globals_section = config.get("globals", {})
    
    # Process global repositories
    for repo in globals_section.get("repositories", []):
        repo_key = repo.get("key", "")
        should_unprotect = False
        matched_key = None
        fuzzy = False
        
        # Check exact match first
        if repo_key in repo_keys_to_unprotect or repo_key in all_unprefixed:
            should_unprotect = True
            matched_key = repo_key
        else:
            # Fuzzy fallback (legacy prefixed repo keys)
            for unprot_key in repo_keys_to_unprotect | all_unprefixed:
                if unprot_key and (unprot_key in repo_key or repo_key.endswith(unprot_key)):
                    should_unprotect = True
                    matched_key = unprot_key
                    fuzzy = True
                    break
        
        if should_unprotect and "protected" in repo:
            del repo["protected"]
            updated_count += 1
            if fuzzy:
                logger.warning(
                    f"  Removed protection from global repository {repo_key} "
                    f"via fuzzy match on '{matched_key}' — consider aligning "
                    f"the repository key to the project key"
                )
            else:
                logger.info(f"  Removed protection from global repository {repo_key} (matched {matched_key})")
    
    # Save updated YAML
    output = output_path or yaml_file
    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    logger.info(f"Removed protection from {updated_count} resources in {output}")
    
    return output


def merge_yaml_configs(base_yaml: dict, source_yaml: dict) -> dict:
    """Merge source-selected resources into existing base YAML.
    
    This is the critical function that prevents deploy generate from
    overwriting an existing deployment YAML (with all managed projects)
    with a source-selected subset YAML (containing only cherry-picked projects).
    
    Merge rules:
    - Projects in source that aren't in base: ADD
    - Projects in source that ARE in base: UPDATE (source values win)
    - Projects in base that aren't in source: PRESERVE (critical!)
    - Same logic for globals sections (repositories, connections, etc.)
    - Top-level fields (version, account, etc.) preserved from base
    
    Args:
        base_yaml: The existing deployment YAML (full set of managed resources).
                   Can be None or empty for fresh migrations.
        source_yaml: The source-selected YAML (subset being added/updated).
                     Can be None or empty if no new selections.
    
    Returns:
        Merged dict ready to be written as YAML.
    """
    if not base_yaml and not source_yaml:
        return {}
    if not base_yaml:
        return dict(source_yaml) if source_yaml else {}
    if not source_yaml:
        return dict(base_yaml) if base_yaml else {}
    
    import copy
    merged = copy.deepcopy(base_yaml)
    
    # Merge projects by key
    _merge_list_by_key(merged, source_yaml, "projects")
    
    # Merge globals sections
    base_globals = merged.get("globals", {})
    source_globals = source_yaml.get("globals", {})
    
    if source_globals:
        if not base_globals:
            merged["globals"] = copy.deepcopy(source_globals)
        else:
            # Merge each globals sub-section that is a list of keyed items
            for section_key in ("repositories", "connections", "service_tokens",
                                "notification_configs", "webhooks"):
                if section_key in source_globals:
                    if section_key not in base_globals:
                        base_globals[section_key] = []
                    _merge_list_by_key_inline(
                        base_globals[section_key],
                        source_globals[section_key],
                    )
            
            # Preserve any scalar/dict globals fields from source that aren't lists
            for gk, gv in source_globals.items():
                if gk not in base_globals and not isinstance(gv, list):
                    base_globals[gk] = copy.deepcopy(gv)
            
            merged["globals"] = base_globals
    
    # Preserve top-level scalar fields from source if not in base
    # (e.g., version, account fields that source might update)
    for key in source_yaml:
        if key not in ("projects", "globals") and key not in merged:
            merged[key] = copy.deepcopy(source_yaml[key])
    
    logger.info(
        f"Merged YAML: base had {len(base_yaml.get('projects', []))} projects, "
        f"source had {len(source_yaml.get('projects', []))} projects, "
        f"merged has {len(merged.get('projects', []))} projects"
    )
    
    return merged


def _get_item_identifier(item: dict):
    """Get the merge identifier for a list item.
    
    Tries 'key' first (most resource types), then 'name' (environment_variables).
    """
    return item.get("key") or item.get("name")


def _deep_merge_dict(base: dict, source: dict) -> dict:
    """Deep-merge source into base, recursively merging keyed sub-lists.
    
    This enables source-selecting at any granularity (a single job, env, envvar)
    while preserving everything else from the base. Merge rules:
    - Scalar/dict fields: source wins
    - Lists of keyed dicts (have 'key' or 'name'): merge by identifier recursively
    - Lists of non-keyed items: source wins
    - Base fields not in source: preserved
    """
    import copy
    merged = copy.deepcopy(base)
    
    for key, source_value in source.items():
        base_value = merged.get(key)
        
        if isinstance(source_value, list) and isinstance(base_value, list):
            if (source_value and isinstance(source_value[0], dict)
                    and _get_item_identifier(source_value[0]) is not None):
                # Both are lists of keyed dicts -- merge by identifier recursively
                _merge_keyed_list_inplace(merged[key], source_value)
            elif (not source_value and base_value
                    and isinstance(base_value[0], dict)
                    and _get_item_identifier(base_value[0]) is not None):
                # Empty source list should NOT clobber a populated base keyed list.
                # An empty [] from the deploy YAML means "not defined yet",
                # not "intentionally remove all items".
                pass  # keep base value
            else:
                # Non-keyed list or both empty -- source wins
                merged[key] = copy.deepcopy(source_value)
        else:
            # Scalar, dict, or new field -- source wins
            merged[key] = copy.deepcopy(source_value)
    
    return merged


def _merge_keyed_list_inplace(target_list: list, source_list: list) -> None:
    """Merge source keyed items into target list in-place, recursively.
    
    Items matched by identifier are deep-merged (preserving base sub-resources).
    Items only in source are appended. Items only in target are preserved.
    """
    import copy
    
    if not source_list:
        return
    
    existing = {}
    for i, item in enumerate(target_list):
        if isinstance(item, dict):
            ident = _get_item_identifier(item)
            if ident:
                existing[ident] = i
    
    for source_item in source_list:
        if not isinstance(source_item, dict):
            continue
        ident = _get_item_identifier(source_item)
        if not ident:
            continue
        
        if ident in existing:
            # UPDATE: recursive deep merge (source wins, base preserved)
            idx = existing[ident]
            target_list[idx] = _deep_merge_dict(target_list[idx], source_item)
        else:
            # ADD: new item from source
            target_list.append(copy.deepcopy(source_item))


def _merge_list_by_key(target: dict, source: dict, list_key: str) -> None:
    """Merge a list of keyed dicts from source into target.
    
    Items are matched by identifier ('key' or 'name'). Existing items are
    deep-merged (source wins, base sub-resources preserved). New items are
    appended. Items only in target are preserved.
    """
    source_list = source.get(list_key, [])
    
    if not source_list:
        return
    
    if list_key not in target:
        import copy
        target[list_key] = copy.deepcopy(source_list)
        return
    
    _merge_keyed_list_inplace(target[list_key], source_list)


def _merge_list_by_key_inline(target_list: list, source_list: list) -> None:
    """Merge source keyed items into target list in-place.
    
    Same recursive deep-merge logic as _merge_list_by_key.
    """
    _merge_keyed_list_inplace(target_list, source_list)
