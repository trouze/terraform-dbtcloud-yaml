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
    
    # FIRST PASS: Build project ID -> key mapping before normalizing service tokens/groups
    # This is needed because service tokens and groups reference projects by ID
    _build_project_id_mapping(snapshot, config, context)
    
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
        # Register connection key mapping for environment lookups
        context.register_connection_key(key, normalized_key)
        
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
        
        # Add only essential provider-specific configuration
        if conn.details and config.include_connection_details:
            essential_fields = {}
            
            # Include adapter version if present
            if "adapter_version" in conn.details:
                essential_fields["adapter_version"] = conn.details["adapter_version"]
            
            # Include SSH tunnel setting if enabled
            if conn.details.get("is_ssh_tunnel_enabled"):
                essential_fields["is_ssh_tunnel_enabled"] = True
            
            # Include provider-specific config if present
            if conn.details.get("config"):
                essential_fields["config"] = conn.details["config"]
            
            # Only add details if we have essential fields
            if essential_fields:
                conn_data["details"] = essential_fields
        
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
        # Register repository key mapping for project lookups
        context.register_repository_key(key, normalized_key)
        
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
    """Normalize service tokens to v2 format with service_token_permissions structure."""
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
        
        token_data = {
            "key": normalized_key,
            "name": token.name,
        }
        
        # Add state if present
        if token.state:
            token_data["state"] = token.state
        
        # Build service_token_permissions from metadata.permission_grants
        # ALWAYS include this field to ensure Terraform type consistency
        token_data["service_token_permissions"] = []
        permission_grants = token.metadata.get("permission_grants", [])
        if permission_grants:
            for grant in permission_grants:
                source_project_id = grant.get("project_id")
                # Convert source project_id to project_key for cross-account migration
                project_key = context.resolve_project_id_to_key(source_project_id) if source_project_id else None
                
                perm = {
                    "permission_set": grant["permission_set"],
                    "all_projects": source_project_id is None,
                    # Use project_key instead of project_id for Terraform to resolve to target project
                    "project_key": project_key,
                    # Keep project_id for type consistency but note it's the SOURCE ID (for reference only)
                    # Terraform should use project_key to look up the target project_id
                    "project_id": None,  # Don't use source ID - it won't exist in target
                    # Always include writable_environment_categories for type consistency (empty list if not present)
                    "writable_environment_categories": grant.get("writable_environment_categories", []),
                }
                
                token_data["service_token_permissions"].append(perm)
        
        if not config.should_strip_source_ids() and token.id:
            token_data["id"] = token.id
        
        result.append(token_data)
    
    return result


def _normalize_groups(
    groups: Dict[str, Group],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize groups to v2 format with group_permissions structure."""
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
        }
        
        # Add assign_by_default if present
        if group.assign_by_default is not None:
            group_data["assign_by_default"] = group.assign_by_default
        
        # Add sso_mapping_groups if present and non-empty
        if group.sso_mapping_groups:
            group_data["sso_mapping_groups"] = group.sso_mapping_groups
        
        # Build group_permissions from metadata.group_permissions
        # ALWAYS include this field to ensure Terraform type consistency
        group_data["group_permissions"] = []
        group_permissions = group.metadata.get("group_permissions", [])
        if group_permissions:
            for perm in group_permissions:
                source_project_id = perm.get("project_id")
                # Convert source project_id to project_key for cross-account migration
                project_key = context.resolve_project_id_to_key(source_project_id) if source_project_id else None
                
                perm_data = {
                    "permission_set": perm["permission_set"],
                    "all_projects": source_project_id is None,
                    # Use project_key instead of project_id for Terraform to resolve to target project
                    "project_key": project_key,
                    # Keep project_id for type consistency but set to None (source IDs don't exist in target)
                    "project_id": None,
                    # Always include writable_environment_categories for type consistency (empty list if not present)
                    "writable_environment_categories": perm.get("writable_environment_categories", []),
                }
                
                group_data["group_permissions"].append(perm_data)
        
        if not config.should_strip_source_ids() and group.id:
            group_data["id"] = group.id
        
        result.append(group_data)
    
    return result


def _normalize_notifications(
    notifications: Dict[str, Notification],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize notifications to v2 format with Terraform-compatible structure."""
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
        
        notif_data = {
            "key": normalized_key,
            # Always include all optional fields for type consistency
            "user_id": notif.user_id if notif.user_id else None,
            "notification_type": notif.notification_type if notif.notification_type else None,
            "state": notif.state if notif.state else None,
            # Always include job trigger lists (empty if not present)
            "on_success": notif.on_success if notif.on_success else [],
            "on_failure": notif.on_failure if notif.on_failure else [],
            "on_cancel": notif.on_cancel if notif.on_cancel else [],
            "on_warning": notif.on_warning if notif.on_warning else [],
            # Type-specific fields (null if not applicable)
            "external_email": notif.external_email if notif.external_email else None,
            "slack_channel_id": notif.slack_channel_id if notif.slack_channel_id else None,
            "slack_channel_name": notif.slack_channel_name if notif.slack_channel_name else None,
        }
        
        if not config.should_strip_source_ids() and notif.id:
            notif_data["id"] = notif.id
        
        result.append(notif_data)
    
    return result


def _build_project_id_mapping(
    snapshot: AccountSnapshot,
    config: MappingConfig,
    context: NormalizationContext,
) -> None:
    """
    Pre-pass: Build mapping of project IDs to project keys.
    
    This must run before normalizing service tokens and groups,
    as they reference projects by ID and need to convert to keys.
    """
    scope_mode = config.get_scope_mode()
    if scope_mode == "account_level_only":
        return
    
    scope_project_keys = set(config.get_project_keys())
    scope_project_ids = set(config.get_project_ids())
    exclude_keys = config.get_exclude_keys("projects")
    exclude_ids = config.get_exclude_ids("projects")
    
    for project in snapshot.projects:
        # Apply same filters as _normalize_projects
        if scope_mode == "specific_projects":
            if project.key not in scope_project_keys and project.id not in scope_project_ids:
                continue
        
        if project.key in exclude_keys or _get_element_id(project) and _get_element_id(project) in exclude_ids:
            continue
        
        if not _should_include(project, config):
            continue
        
        # Register project ID -> key mapping
        if project.id:
            normalized_key = context.resolve_collision(project.key, namespace="projects_prepass")
            context.register_project(project.id, normalized_key)
    
    log.info(f"Built project ID mapping with {len(context.project_id_to_key)} projects")


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
        
        # Register project ID -> key mapping for permission resolution
        if project.id:
            context.register_project(project.id, normalized_key)
        
        project_data = {
            "key": normalized_key,
            "name": project.name,
        }
        
        # Resolve repository reference - ALWAYS include for Terraform type consistency
        if project.repository_key:
            # First try to resolve by repository key mapping
            repo_key = context.resolve_repository_key(project.repository_key)
            if repo_key:
                project_data["repository"] = repo_key
            else:
                # Fallback to element reference
                repo_key = context.resolve_element_reference(project.repository_key)
                if repo_key:
                    project_data["repository"] = repo_key
                else:
                    lookup_id = f"LOOKUP:{project.repository_key}"
                    project_data["repository"] = lookup_id
                    context.add_placeholder(lookup_id, f"Repository for project {project.name}")
        else:
            # No repository key - set to null for type consistency
            project_data["repository"] = None
        
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
        
        # Resolve connection reference - ALWAYS include for Terraform type consistency
        # First try to resolve using connection key mapping (original key -> normalized key)
        # Then fall back to element_mapping_id resolution
        if env.connection_key:
            conn_key = context.resolve_connection_key(env.connection_key)
            if not conn_key:
                # Fall back to element_mapping_id resolution
                conn_key = context.resolve_element_reference(env.connection_key)
            if conn_key:
                env_data["connection"] = conn_key
            else:
                lookup_id = f"LOOKUP:{env.connection_key}"
                env_data["connection"] = lookup_id
                context.add_placeholder(lookup_id, f"Connection for environment {env.name}")
        else:
            env_data["connection"] = None
        
        # Credential - ALWAYS include all fields for Terraform type consistency
        env_data["credential"] = {
            "token_name": env.credential.token_name or "",
            "schema": env.credential.schema or "",
            "catalog": env.credential.catalog or None,
        }
        
        # Optional fields - ALWAYS include to ensure Terraform type consistency
        env_data["dbt_version"] = env.dbt_version or None
        env_data["custom_branch"] = env.custom_branch or None
        env_data["enable_model_query_history"] = env.enable_model_query_history
        env_data["deployment_type"] = env.deployment_type or None
        
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
    
    # Build mapping of environment_id -> environment_key for deferral resolution
    env_id_to_key = {env.id: env.key for env in project.environments if env.id}

    # Build mapping of job_id -> job_key for job completion trigger condition resolution
    job_id_to_key = {j.id: j.key for j in project.jobs if getattr(j, "id", None)}

    # Precompute job chaining edges (job_key -> trigger_job_key) for same-project triggers,
    # so we can detect cycles and avoid generating Terraform dependency cycles.
    trigger_key_by_job_key: Dict[str, str] = {}
    for j in project.jobs:
        jctc = j.settings.get("job_completion_trigger_condition")
        trigger_condition = None
        if isinstance(jctc, dict):
            if isinstance(jctc.get("condition"), dict):
                trigger_condition = jctc.get("condition")
            else:
                trigger_condition = jctc
        if not isinstance(trigger_condition, dict):
            continue
        src_trigger_job_id = trigger_condition.get("job_id")
        src_trigger_project_id = trigger_condition.get("project_id")
        # Only same-project chaining can be resolved automatically.
        if (
            isinstance(src_trigger_job_id, int)
            and src_trigger_project_id == project.id
            and src_trigger_job_id in job_id_to_key
        ):
            trigger_job_key = job_id_to_key[src_trigger_job_id]
            # Avoid trivial self-dependency
            if trigger_job_key and trigger_job_key != j.key:
                trigger_key_by_job_key[j.key] = trigger_job_key

    def _cycle_nodes(edges: Dict[str, str]) -> set[str]:
        """Return the set of nodes that participate in any directed cycle in edges."""
        visiting: set[str] = set()
        visited: set[str] = set()
        cycles: set[str] = set()

        def dfs(n: str, stack: List[str]) -> None:
            if n in visiting:
                # Mark the cycle portion of the current stack
                if n in stack:
                    cycles.update(stack[stack.index(n):])
                else:
                    cycles.add(n)
                return
            if n in visited:
                return
            visiting.add(n)
            stack.append(n)
            nxt = edges.get(n)
            if nxt:
                dfs(nxt, stack)
            stack.pop()
            visiting.remove(n)
            visited.add(n)

        for node in edges.keys():
            if node not in visited:
                dfs(node, [])
        return cycles

    cycle_job_keys = _cycle_nodes(trigger_key_by_job_key)
    
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
        
        # Extract deferring_environment_id and map to environment_key
        # Always include this field (even if null) for Terraform type consistency
        deferring_env_id = job.settings.get("deferring_environment_id")
        if deferring_env_id and deferring_env_id in env_id_to_key:
            job_data["deferring_environment_key"] = env_id_to_key[deferring_env_id]
        else:
            # Explicitly set to null to ensure all jobs have the same structure
            job_data["deferring_environment_key"] = None
        
        # Schedule settings - ALWAYS include for Terraform type consistency
        #
        # Important: the dbt Cloud Jobs API returns schedule nested:
        #   settings.schedule.date.{type,days,cron}
        #   settings.schedule.time.{type,interval,hours}
        #
        # Terraform provider validation enforces mutually exclusive combinations:
        # - schedule_cron cannot be set with schedule_interval or schedule_hours
        # - schedule_hours cannot be set with schedule_interval (and vice versa)
        # Only populate schedule fields for *scheduled* jobs.
        # The Jobs API often includes a schedule object even when triggers.schedule is false,
        # and Terraform/provider validation enforces mutually exclusive combinations.
        is_scheduled = False
        if isinstance(job.triggers, dict):
            is_scheduled = bool(job.triggers.get("schedule", False))

        if not is_scheduled:
            job_data["schedule_type"] = None
            job_data["schedule_days"] = None
            job_data["schedule_hours"] = None
            job_data["schedule_interval"] = None
            job_data["schedule_cron"] = None
        else:
            schedule = job.settings.get("schedule") if isinstance(job.settings.get("schedule"), dict) else {}
            schedule_date = schedule.get("date") if isinstance(schedule.get("date"), dict) else {}
            schedule_time = schedule.get("time") if isinstance(schedule.get("time"), dict) else {}

            schedule_type = schedule_date.get("type") or job.settings.get("schedule_type") or None
            schedule_days = schedule_date.get("days") or job.settings.get("schedule_days") or None
            schedule_time_type = schedule_time.get("type")

            # Decide whether to emit schedule_hours vs schedule_interval based on schedule_time.type
            schedule_hours = None
            schedule_interval = None
            if schedule_time_type == "at_exact_hours":
                schedule_hours = schedule_time.get("hours") or job.settings.get("schedule_hours") or None
                schedule_interval = None
            elif schedule_time_type == "every_hour":
                schedule_interval = schedule_time.get("interval") or job.settings.get("schedule_interval") or None
                schedule_hours = None
            else:
                # Fallback: prefer hours if present, else interval
                schedule_hours = schedule_time.get("hours") or job.settings.get("schedule_hours") or None
                schedule_interval = schedule_time.get("interval") or job.settings.get("schedule_interval") or None
                if schedule_hours is not None and schedule_interval is not None:
                    # If both present, drop interval (provider disallows the combo)
                    schedule_interval = None

            # Only emit schedule_cron for custom_cron schedules.
            # The API often includes a computed schedule.cron even for non-cron schedules; that must be ignored.
            schedule_cron = None
            if schedule_type == "custom_cron":
                schedule_cron = schedule_date.get("cron") or job.settings.get("schedule_cron") or None

            job_data["schedule_type"] = schedule_type
            job_data["schedule_days"] = schedule_days
            job_data["schedule_hours"] = schedule_hours
            job_data["schedule_interval"] = schedule_interval
            job_data["schedule_cron"] = schedule_cron
        
        # Optional job settings - ALWAYS include for Terraform type consistency
        #
        # Important: the dbt Cloud Jobs API returns some settings nested:
        # - threads/target_name under settings.settings
        # - timeout_seconds under settings.execution
        # Preserve those values first, then fall back to older flat keys.
        nested_settings = job.settings.get("settings") if isinstance(job.settings.get("settings"), dict) else {}
        nested_execution = job.settings.get("execution") if isinstance(job.settings.get("execution"), dict) else {}

        job_data["num_threads"] = (
            nested_settings.get("threads")
            or job.settings.get("num_threads")
            or None
        )
        job_data["timeout_seconds"] = (
            nested_execution.get("timeout_seconds")
            or job.settings.get("timeout_seconds")
            or None
        )
        job_data["target_name"] = (
            nested_settings.get("target_name")
            or job.settings.get("target_name")
            or None
        )
        job_data["dbt_version"] = job.settings.get("dbt_version") or None
        job_data["generate_docs"] = job.settings.get("generate_docs", False)
        job_data["run_lint"] = job.settings.get("run_lint", False)
        # Propagate lint failure behavior when run_lint is enabled.
        # If absent in the source snapshot, leave as null so Terraform can apply its default.
        job_data["errors_on_lint_failure"] = job.settings.get("errors_on_lint_failure")
        job_data["run_generate_sources"] = job.settings.get("run_generate_sources", False)
        job_data["run_compare_changes"] = job.settings.get("run_compare_changes", False)
        job_data["compare_changes_flags"] = job.settings.get("compare_changes_flags") or None

        # Job completion trigger condition (job chaining)
        # Source API represents this as:
        #   job.settings.job_completion_trigger_condition.condition = { job_id, project_id, statuses: [10,20,30] }
        jctc = job.settings.get("job_completion_trigger_condition")
        trigger_condition = None
        if isinstance(jctc, dict):
            # v3 shape has { "condition": {...} }
            if isinstance(jctc.get("condition"), dict):
                trigger_condition = jctc.get("condition")
            else:
                trigger_condition = jctc

        resolved_trigger = None
        if isinstance(trigger_condition, dict):
            src_trigger_job_id = trigger_condition.get("job_id")
            src_trigger_project_id = trigger_condition.get("project_id")
            src_statuses = trigger_condition.get("statuses") or []

            # Only resolve job chaining within the same project (cross-project requires additional lookups).
            if isinstance(src_trigger_job_id, int) and src_trigger_project_id == project.id and src_trigger_job_id in job_id_to_key:
                status_map = {10: "success", 20: "error", 30: "canceled"}
                resolved_statuses = [
                    status_map[s] for s in src_statuses if isinstance(s, int) and s in status_map
                ]
                resolved_trigger = {
                    "job_key": job_id_to_key[src_trigger_job_id],
                    "statuses": resolved_statuses,
                }
            elif src_trigger_job_id is not None:
                lookup_id = f"LOOKUP:job_completion_trigger_{project.key}_{job.key}"
                context.add_placeholder(lookup_id, "Job completion trigger condition requires manual resolution (cross-project or unknown job)")

        # If this project has cyclic job-chaining, omit those edges so Terraform can plan/apply.
        # We'll surface them via LOOKUP placeholders for a later, dedicated job-chaining migration step.
        if resolved_trigger and job.key in cycle_job_keys:
            lookup_id = f"LOOKUP:job_completion_trigger_cycle_{project.key}_{job.key}"
            context.add_placeholder(
                lookup_id,
                "Job completion trigger condition is part of a cycle and cannot be applied in a single Terraform graph",
            )
            resolved_trigger = None

        # Always include for Terraform type consistency
        job_data["job_completion_trigger_condition"] = resolved_trigger

        # Job-level environment variable overrides.
        # Always include for Terraform type consistency.
        job_data["environment_variable_overrides"] = getattr(job, "environment_variable_overrides", {}) or {}
        
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
        
        # Handle project default value (maps to special "project" key)
        if var.project_default:
            if var.name.startswith("DBT_ENV_SECRET"):
                if secret_handling == "redact":
                    env_values["project"] = "REDACTED"
                elif secret_handling == "placeholder":
                    env_values["project"] = f"${{var.{var.name.lower()}}}"
                # If omit, don't include project default for secrets
            else:
                env_values["project"] = var.project_default
        
        # Handle environment-specific values
        for env_name, value in var.environment_values.items():
            if var.name.startswith("DBT_ENV_SECRET"):
                if secret_handling == "redact":
                    env_values[env_name] = "REDACTED"
                elif secret_handling == "placeholder":
                    env_values[env_name] = f"${{var.{var.name.lower()}}}"
            else:
                env_values[env_name] = value
        
        # Skip variables with no values at all
        if not env_values:
            context.add_exclusion("environment_variable", var.name, "No values set", _get_element_id(var))
            continue
        
        var_data = {
            "name": var.name,
            "environment_values": env_values,
        }
        
        result.append(var_data)
    
    return result

