"""Core normalization logic for converting AccountSnapshot to v2 YAML structure."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..models import (
    AccountSnapshot,
    Connection,
    Environment,
    EnvironmentVariable,
    Group,
    Job,
    Notification,
    PrivateLinkEndpoint,
    Project,
    Repository,
    ServiceToken,
)
from . import MappingConfig, NormalizationContext

log = logging.getLogger(__name__)


def _get_element_id(obj: Any) -> Optional[str]:
    """Safely get element_mapping_id from an object, returns None if not present."""
    return getattr(obj, 'element_mapping_id', None)


def _should_include(obj: Any, config: MappingConfig) -> bool:
    """Check if object should be included based on include_in_conversion flag."""
    if config.should_include_inactive():
        return True
    return getattr(obj, 'include_in_conversion', True)


def normalize_snapshot(
    snapshot: AccountSnapshot,
    config: MappingConfig,
    context: NormalizationContext,
) -> Dict[str, Any]:
    """
    Convert an AccountSnapshot to v2 YAML structure.
    
    Returns a dictionary ready for YAML serialization.
    """
    log.info("Starting normalization of account snapshot")
    
    # Build v2 root structure
    v2_data: Dict[str, Any] = {
        "version": 2,
        "account": _normalize_account(snapshot, config),
        "globals": {},
        "projects": [],
    }
    
    # Normalize globals
    if config.is_resource_included("connections"):
        v2_data["globals"]["connections"] = _normalize_connections(
            snapshot.globals.connections, config, context
        )
    
    if config.is_resource_included("repositories"):
        v2_data["globals"]["repositories"] = _normalize_repositories(
            snapshot.globals.repositories, config, context
        )
    
    if config.is_resource_included("privatelink_endpoints"):
        v2_data["globals"]["privatelink_endpoints"] = _normalize_privatelink_endpoints(
            snapshot.globals.privatelink_endpoints, config, context
        )
    
    if config.is_resource_included("service_tokens"):
        v2_data["globals"]["service_tokens"] = _normalize_service_tokens(
            snapshot.globals.service_tokens, config, context
        )
    
    if config.is_resource_included("groups"):
        v2_data["globals"]["groups"] = _normalize_groups(
            snapshot.globals.groups, config, context
        )
    
    if config.is_resource_included("notifications"):
        v2_data["globals"]["notifications"] = _normalize_notifications(
            snapshot.globals.notifications, config, context
        )
    
    # Normalize projects
    if config.is_resource_included("projects"):
        v2_data["projects"] = _normalize_projects(snapshot, config, context)
    
    # Add metadata section if there are placeholders
    if context.placeholders:
        v2_data["metadata"] = {"placeholders": context.placeholders}
    
    log.info(
        f"Normalization complete: {len(v2_data.get('projects', []))} projects, "
        f"{len(context.placeholders)} placeholders, {len(context.exclusions)} exclusions"
    )
    
    return v2_data


def _normalize_account(snapshot: AccountSnapshot, config: MappingConfig) -> Dict[str, Any]:
    """Normalize account-level metadata."""
    account_data = {
        "name": snapshot.account_name or f"Account {snapshot.account_id}",
        "host_url": "https://cloud.getdbt.com",  # Default, should be in metadata
    }
    
    if not config.should_strip_source_ids():
        account_data["id"] = snapshot.account_id
    
    return account_data


def _normalize_connections(
    connections: Dict[str, Connection],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize connections to v2 format."""
    result = []
    exclude_keys = config.get_exclude_keys("connections")
    exclude_ids = config.get_exclude_ids("connections")
    include_only = config.get_include_only_keys("connections")
    
    for key, conn in connections.items():
        element_id = _get_element_id(conn)
        
        # Apply filters
        if key in exclude_keys:
            context.add_exclusion("connection", key, "Excluded by key filter", element_id)
            continue
        
        if element_id and element_id in exclude_ids:
            context.add_exclusion("connection", key, "Excluded by element ID filter", element_id)
            continue
        
        if include_only and key not in include_only:
            context.add_exclusion("connection", key, "Not in include_only whitelist", element_id)
            continue
        
        if not _should_include(conn, config):
            context.add_exclusion("connection", key, "Inactive/soft-deleted", element_id)
            continue
        
        # Normalize key for collisions
        normalized_key = context.resolve_collision(key, namespace="connections")
        if element_id:
            context.register_element(element_id, normalized_key)
        
        conn_data = {
            "key": normalized_key,
            "name": conn.name or key,
            "type": conn.type or "unknown",
        }
        
        # Optionally preserve source ID
        if not config.should_strip_source_ids() and conn.id:
            conn_data["id"] = conn.id
        
        # Resolve PrivateLink endpoint reference
        privatelink_id = conn.details.get("private_link_endpoint_id")
        if privatelink_id:
            # Try to resolve to a key
            pl_key = context.resolve_element_reference(f"PLE_{privatelink_id}")
            if pl_key:
                conn_data["private_link_endpoint_key"] = pl_key
            else:
                # Emit placeholder
                lookup_id = f"LOOKUP:privatelink_{privatelink_id}"
                conn_data["private_link_endpoint_key"] = lookup_id
                context.add_placeholder(lookup_id, f"PrivateLink endpoint ID {privatelink_id}")
        
        # Add provider-specific details
        if conn.details:
            conn_data["details"] = conn.details
        
        result.append(conn_data)
    
    return result


def _normalize_repositories(
    repositories: Dict[str, Repository],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize repositories to v2 format."""
    result = []
    exclude_keys = config.get_exclude_keys("repositories")
    exclude_ids = config.get_exclude_ids("repositories")
    include_only = config.get_include_only_keys("repositories")
    
    for key, repo in repositories.items():
        # Apply filters
        if key in exclude_keys:
            context.add_exclusion("repository", key, "Excluded by key filter", _get_element_id(repo))
            continue
        
        if _get_element_id(repo) and _get_element_id(repo) in exclude_ids:
            context.add_exclusion("repository", key, "Excluded by element ID filter", _get_element_id(repo))
            continue
        
        if include_only and key not in include_only:
            context.add_exclusion("repository", key, "Not in include_only whitelist", _get_element_id(repo))
            continue
        
        if not _should_include(repo, config):
            context.add_exclusion("repository", key, "Inactive/soft-deleted", _get_element_id(repo))
            continue
        
        # Normalize key
        normalized_key = context.resolve_collision(key, namespace="repositories")
        if _get_element_id(repo):
            context.register_element(_get_element_id(repo), normalized_key)
        
        repo_data = {
            "key": normalized_key,
            "remote_url": repo.remote_url,
        }
        
        if repo.git_clone_strategy:
            repo_data["git_clone_strategy"] = repo.git_clone_strategy
        
        # Preserve provider-specific IDs (these are needed for Terraform)
        if repo.metadata.get("github_installation_id"):
            repo_data["github_installation_id"] = repo.metadata["github_installation_id"]
        
        if repo.metadata.get("gitlab_project_id"):
            repo_data["gitlab_project_id"] = repo.metadata["gitlab_project_id"]
        
        if repo.metadata.get("azure_active_directory_project_id"):
            repo_data["azure_active_directory_project_id"] = repo.metadata["azure_active_directory_project_id"]
        
        if repo.metadata.get("azure_active_directory_repository_id"):
            repo_data["azure_active_directory_repository_id"] = repo.metadata["azure_active_directory_repository_id"]
        
        # Optionally preserve source ID
        if not config.should_strip_source_ids() and repo.id:
            repo_data["id"] = repo.id
        
        result.append(repo_data)
    
    return result


def _normalize_privatelink_endpoints(
    endpoints: Dict[str, PrivateLinkEndpoint],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize PrivateLink endpoints to v2 format."""
    result = []
    exclude_keys = config.get_exclude_keys("privatelink_endpoints")
    exclude_ids = config.get_exclude_ids("privatelink_endpoints")
    
    for key, endpoint in endpoints.items():
        if key in exclude_keys or _get_element_id(endpoint) and _get_element_id(endpoint) in exclude_ids:
            context.add_exclusion("privatelink_endpoint", key, "Excluded by filter", _get_element_id(endpoint))
            continue
        
        if not _should_include(endpoint, config):
            context.add_exclusion("privatelink_endpoint", key, "Inactive", _get_element_id(endpoint))
            continue
        
        normalized_key = context.resolve_collision(key, namespace="privatelink_endpoints")
        if _get_element_id(endpoint):
            context.register_element(_get_element_id(endpoint), normalized_key)
        
        endpoint_data = {
            "key": normalized_key,
            "cloud": endpoint.type or "unknown",
            "region": endpoint.metadata.get("region", "unknown"),
            "endpoint_id": endpoint.id or "unknown",
        }
        
        result.append(endpoint_data)
    
    return result


def _normalize_service_tokens(
    tokens: Dict[str, ServiceToken],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize service tokens to v2 format."""
    result = []
    exclude_keys = config.get_exclude_keys("service_tokens")
    exclude_ids = config.get_exclude_ids("service_tokens")
    
    for key, token in tokens.items():
        if key in exclude_keys or _get_element_id(token) and _get_element_id(token) in exclude_ids:
            context.add_exclusion("service_token", key, "Excluded by filter", _get_element_id(token))
            continue
        
        if not _should_include(token, config):
            context.add_exclusion("service_token", key, "Inactive", _get_element_id(token))
            continue
        
        normalized_key = context.resolve_collision(key, namespace="service_tokens")
        if _get_element_id(token):
            context.register_element(_get_element_id(token), normalized_key)
        
        # Use permission_sets directly (already in correct format)
        scopes = token.permission_sets if hasattr(token, 'permission_sets') else []
        
        token_data = {
            "key": normalized_key,
            "name": token.name,
            "scopes": scopes,
        }
        
        if not config.should_strip_source_ids() and token.id:
            token_data["id"] = token.id
        
        result.append(token_data)
    
    return result


def _normalize_groups(
    groups: Dict[str, Group],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize groups to v2 format."""
    result = []
    exclude_keys = config.get_exclude_keys("groups")
    exclude_ids = config.get_exclude_ids("groups")
    
    for key, group in groups.items():
        if key in exclude_keys or _get_element_id(group) and _get_element_id(group) in exclude_ids:
            context.add_exclusion("group", key, "Excluded by filter", _get_element_id(group))
            continue
        
        if not _should_include(group, config):
            context.add_exclusion("group", key, "Inactive", _get_element_id(group))
            continue
        
        normalized_key = context.resolve_collision(key, namespace="groups")
        if _get_element_id(group):
            context.register_element(_get_element_id(group), normalized_key)
        
        group_data = {
            "key": normalized_key,
            "name": group.name,
            "members": [],  # Not available in importer data
        }
        
        if not config.should_strip_source_ids() and group.id:
            group_data["id"] = group.id
        
        result.append(group_data)
    
    return result


def _normalize_notifications(
    notifications: Dict[str, Notification],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize notifications to v2 format."""
    result = []
    exclude_keys = config.get_exclude_keys("notifications")
    exclude_ids = config.get_exclude_ids("notifications")
    
    for key, notif in notifications.items():
        if key in exclude_keys or _get_element_id(notif) and _get_element_id(notif) in exclude_ids:
            context.add_exclusion("notification", key, "Excluded by filter", _get_element_id(notif))
            continue
        
        if not _should_include(notif, config):
            context.add_exclusion("notification", key, "Inactive", _get_element_id(notif))
            continue
        
        normalized_key = context.resolve_collision(key, namespace="notifications")
        if _get_element_id(notif):
            context.register_element(_get_element_id(notif), normalized_key)
        
        # Map notification_type integers to strings
        type_map = {1: "email", 2: "slack", 3: "webhook"}
        notif_type = type_map.get(notif.notification_type, "email")
        
        # Build target object based on type
        target = {}
        if notif_type == "email":
            target["email"] = notif.metadata.get("external_email", "unknown@example.com")
        elif notif_type == "slack":
            target["channel"] = notif.metadata.get("slack_channel_name") or notif.metadata.get("slack_channel_id", "unknown")
        elif notif_type == "webhook":
            target["url"] = notif.metadata.get("url", "https://example.com/webhook")
        
        notif_data = {
            "key": normalized_key,
            "type": notif_type,
            "target": target,
        }
        
        if not config.should_strip_source_ids() and notif.id:
            notif_data["id"] = notif.id
        
        result.append(notif_data)
    
    return result


def _normalize_projects(
    snapshot: AccountSnapshot,
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize projects to v2 format."""
    result = []
    
    # Apply scope filters
    scope_mode = config.get_scope_mode()
    if scope_mode == "account_level_only":
        log.info("Scope mode is 'account_level_only', skipping all projects")
        return result
    
    scope_project_keys = set(config.get_project_keys())
    scope_project_ids = set(config.get_project_ids())
    
    exclude_keys = config.get_exclude_keys("projects")
    exclude_ids = config.get_exclude_ids("projects")
    
    for project in snapshot.projects:
        # Apply scope filter
        if scope_mode == "specific_projects":
            if project.key not in scope_project_keys and project.id not in scope_project_ids:
                context.add_exclusion("project", project.key, "Not in scope filter", _get_element_id(project))
                continue
        
        # Apply exclusion filters
        if project.key in exclude_keys or _get_element_id(project) and _get_element_id(project) in exclude_ids:
            context.add_exclusion("project", project.key, "Excluded by filter", _get_element_id(project))
            continue
        
        if not _should_include(project, config):
            context.add_exclusion("project", project.key, "Inactive", _get_element_id(project))
            continue
        
        # Normalize project
        normalized_key = context.resolve_collision(project.key, namespace="projects")
        if _get_element_id(project):
            context.register_element(_get_element_id(project), normalized_key)
        
        project_data = {
            "key": normalized_key,
            "name": project.name,
        }
        
        # Resolve repository reference
        if project.repository_key:
            repo_key = context.resolve_element_reference(project.repository_key)
            if repo_key:
                project_data["repository"] = repo_key
            else:
                lookup_id = f"LOOKUP:{project.repository_key}"
                project_data["repository"] = lookup_id
                context.add_placeholder(lookup_id, f"Repository for project {project.name}")
        
        # Normalize environments
        if config.is_resource_included("environments"):
            project_data["environments"] = _normalize_environments(project, config, context)
        
        # Normalize jobs
        if config.is_resource_included("jobs"):
            project_data["jobs"] = _normalize_jobs(project, config, context)
        
        # Normalize environment variables
        if config.is_resource_included("environment_variables"):
            project_data["environment_variables"] = _normalize_environment_variables(project, config, context)
        
        result.append(project_data)
    
    return result


def _normalize_environments(
    project: Project,
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize environments for a project."""
    result = []
    exclude_keys = config.get_exclude_keys("environments")
    
    for env in project.environments:
        if env.key in exclude_keys:
            context.add_exclusion("environment", env.key, "Excluded by filter", _get_element_id(env))
            continue
        
        if not _should_include(env, config):
            context.add_exclusion("environment", env.key, "Inactive", _get_element_id(env))
            continue
        
        normalized_key = context.resolve_collision(f"{project.key}_{env.key}", namespace="environments")
        if _get_element_id(env):
            context.register_element(_get_element_id(env), normalized_key)
        
        env_data = {
            "key": env.key,  # Use original key within project scope
            "name": env.name,
            "type": env.type,
        }
        
        # Resolve connection reference
        if env.connection_key:
            conn_key = context.resolve_element_reference(env.connection_key)
            if conn_key:
                env_data["connection"] = conn_key
            else:
                lookup_id = f"LOOKUP:{env.connection_key}"
                env_data["connection"] = lookup_id
                context.add_placeholder(lookup_id, f"Connection for environment {env.name}")
        
        # Credential
        env_data["credential"] = {
            "token_name": env.credential.token_name,
            "schema": env.credential.schema,
        }
        if env.credential.catalog:
            env_data["credential"]["catalog"] = env.credential.catalog
        
        # Optional fields
        if env.dbt_version:
            env_data["dbt_version"] = env.dbt_version
        
        if env.custom_branch:
            env_data["custom_branch"] = env.custom_branch
        
        if env.enable_model_query_history is not None:
            env_data["enable_model_query_history"] = env.enable_model_query_history
        
        result.append(env_data)
    
    return result


def _normalize_jobs(
    project: Project,
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize jobs for a project."""
    result = []
    exclude_keys = config.get_exclude_keys("jobs")
    
    for job in project.jobs:
        if job.key in exclude_keys:
            context.add_exclusion("job", job.key, "Excluded by filter", _get_element_id(job))
            continue
        
        if not _should_include(job, config):
            context.add_exclusion("job", job.key, "Inactive", _get_element_id(job))
            continue
        
        normalized_key = context.resolve_collision(f"{project.key}_{job.key}", namespace="jobs")
        if _get_element_id(job):
            context.register_element(_get_element_id(job), normalized_key)
        
        job_data = {
            "key": job.key,  # Use original key within project scope
            "name": job.name,
            "environment_key": job.environment_key,
            "execute_steps": job.execute_steps,
            "triggers": job.triggers,
        }
        
        # Optional schedule settings
        if job.settings.get("schedule_type"):
            job_data["schedule_type"] = job.settings["schedule_type"]
        
        if job.settings.get("schedule_hours"):
            job_data["schedule_hours"] = job.settings["schedule_hours"]
        
        if job.settings.get("schedule_days"):
            job_data["schedule_days"] = job.settings["schedule_days"]
        
        if job.settings.get("schedule_cron"):
            job_data["schedule_cron"] = job.settings["schedule_cron"]
        
        # Optional job settings
        for field in ["num_threads", "timeout_seconds", "target_name", "dbt_version", "generate_docs", "run_lint", "run_generate_sources", "run_compare_changes"]:
            if field in job.settings and job.settings[field] is not None:
                job_data[field] = job.settings[field]
        
        result.append(job_data)
    
    return result


def _normalize_environment_variables(
    project: Project,
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize environment variables for a project."""
    result = []
    
    for var in project.environment_variables:
        # Skip secrets based on config
        if var.name.startswith("DBT_ENV_SECRET"):
            if config.get_secret_handling() == "omit":
                context.add_exclusion("environment_variable", var.name, "Secret variable omitted", _get_element_id(var))
                continue
        
        if not _should_include(var, config):
            context.add_exclusion("environment_variable", var.name, "Inactive", _get_element_id(var))
            continue
        
        if _get_element_id(var):
            context.register_element(_get_element_id(var), var.name)
        
        env_values = {}
        secret_handling = config.get_secret_handling()
        
        # Handle environment-specific values
        for env_name, value in var.environment_values.items():
            if var.name.startswith("DBT_ENV_SECRET"):
                if secret_handling == "redact":
                    env_values[env_name] = "REDACTED"
                elif secret_handling == "placeholder":
                    env_values[env_name] = f"${{var.{var.name.lower()}}}"
            else:
                env_values[env_name] = value
        
        var_data = {
            "name": var.name,
            "environment_values": env_values,
        }
        
        result.append(var_data)
    
    return result

