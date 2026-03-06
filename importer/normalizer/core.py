"""Core normalization logic for converting AccountSnapshot to v2 YAML structure."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..models import (
    AccountFeatures,
    AccountSnapshot,
    Connection,
    Credential,
    ExtendedAttributes,
    Group,
    IpRestrictionsRule,
    Notification,
    OAuthConfiguration,
    PrivateLinkEndpoint,
    Project,
    Repository,
    ServiceToken,
    UserGroups,
)
from . import MappingConfig, NormalizationContext

log = logging.getLogger(__name__)


# Field mapping from dbt Cloud API connection_details.config to Terraform provider field names.
# These are the non-sensitive fields that can be fetched and pre-populated.
# Sensitive fields (passwords, secrets, keys) are never returned by the API.
# Note: OAuth/SSO credentials are sensitive and must be provided via connection_credentials variable.
CONNECTION_FIELD_MAPPING: Dict[str, Dict[str, str]] = {
    "databricks": {
        # API field -> Terraform field (same names)
        "host": "host",
        "http_path": "http_path",
        "catalog": "catalog",
        # Note: client_id/client_secret are sensitive and not returned by API
    },
    "snowflake": {
        "account": "account",
        "database": "database",
        "warehouse": "warehouse",
        "role": "role",
        "client_session_keep_alive": "client_session_keep_alive",
        "allow_sso": "allow_sso",
        # Note: oauth_client_id/oauth_client_secret are sensitive and not returned by API
    },
    "bigquery": {
        # Required
        "gcp_project_id": "gcp_project_id",
        "project_id": "gcp_project_id",  # API may use project_id
        # Auth type
        "deployment_env_auth_type": "deployment_env_auth_type",
        # Service account (non-sensitive parts)
        "private_key_id": "private_key_id",
        "client_email": "client_email",
        "client_id": "client_id",
        "auth_uri": "auth_uri",
        "token_uri": "token_uri",
        "auth_provider_x509_cert_url": "auth_provider_x509_cert_url",
        "client_x509_cert_url": "client_x509_cert_url",
        # Query configuration
        "timeout_seconds": "timeout_seconds",
        "location": "location",
        "maximum_bytes_billed": "maximum_bytes_billed",
        "priority": "priority",
        "retries": "retries",
        "job_creation_timeout_seconds": "job_creation_timeout_seconds",
        "job_execution_timeout_seconds": "job_execution_timeout_seconds",
        "job_retry_deadline_seconds": "job_retry_deadline_seconds",
        # Execution options
        "execution_project": "execution_project",
        "impersonate_service_account": "impersonate_service_account",
        # Dataproc configuration
        "dataproc_region": "dataproc_region",
        "dataproc_cluster_name": "dataproc_cluster_name",
        "gcs_bucket": "gcs_bucket",
        # Adapter version
        "use_latest_adapter": "use_latest_adapter",
        # Note: private_key and application_id/secret are sensitive
    },
    "redshift": {
        "hostname": "hostname",
        "host": "hostname",  # API may use host
        "port": "port",
        "dbname": "dbname",
        "database": "dbname",  # API may use database
    },
    "postgres": {
        "hostname": "hostname",
        "host": "hostname",  # API may use host
        "port": "port",
        "dbname": "dbname",
        "database": "dbname",  # API may use database
    },
    "athena": {
        "region_name": "region_name",
        "database": "database",
        "s3_staging_dir": "s3_staging_dir",
        "work_group": "work_group",
        "s3_data_dir": "s3_data_dir",
        "s3_tmp_table_dir": "s3_tmp_table_dir",
        "s3_data_naming": "s3_data_naming",
        "spark_work_group": "spark_work_group",
        "num_retries": "num_retries",
        "num_boto3_retries": "num_boto3_retries",
        "num_iceberg_retries": "num_iceberg_retries",
        "poll_interval": "poll_interval",
    },
    "fabric": {
        "server": "server",
        "database": "database",
        "port": "port",
        "login_timeout": "login_timeout",
        "query_timeout": "query_timeout",
        "retries": "retries",
    },
    "synapse": {
        "host": "host",
        "server": "host",  # API may use server
        "database": "database",
        "port": "port",
        "login_timeout": "login_timeout",
        "query_timeout": "query_timeout",
        "retries": "retries",
    },
    "starburst": {
        "host": "host",
        "port": "port",
        "method": "method",
    },
    "apache_spark": {
        "host": "host",
        "cluster": "cluster",
        "method": "method",
        "port": "port",
        "organization": "organization",
        "user": "user",
        "connect_timeout": "connect_timeout",
        "connect_retries": "connect_retries",
    },
    "teradata": {
        "host": "host",
        "port": "port",
        "tmode": "tmode",
        "request_timeout": "request_timeout",
        "retries": "retries",
    },
}


def _map_connection_details_to_terraform(
    connection_type: Optional[str],
    connection_details: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Map dbt Cloud API connection_details to Terraform provider field names.
    
    Args:
        connection_type: The normalized connection type (e.g., 'databricks', 'snowflake')
        connection_details: The connection_details dict from the API response
        
    Returns:
        A dict with Terraform-compatible field names and values
    """
    if not connection_type or not connection_details:
        return {}
    
    # Normalize connection type (handle variants like 'databricks_spark')
    conn_type_lower = connection_type.lower()
    for known_type in CONNECTION_FIELD_MAPPING:
        if known_type in conn_type_lower:
            conn_type_lower = known_type
            break
    
    field_mapping = CONNECTION_FIELD_MAPPING.get(conn_type_lower, {})
    if not field_mapping:
        log.debug(f"No field mapping defined for connection type '{connection_type}'")
        return {}
    
    # Extract config from connection_details (this is where provider-specific fields live)
    config = connection_details.get("config", {})
    if not config:
        # Fallback: check if fields are at the top level of connection_details
        config = connection_details
    
    result = {}
    for api_field, tf_field in field_mapping.items():
        if api_field in config and config[api_field] is not None:
            # Skip empty strings
            value = config[api_field]
            if isinstance(value, str) and not value.strip():
                continue
            result[tf_field] = value
    
    return result


def _build_credential_dict(
    credential: Credential,
    *,
    include_source_id: bool = False,
) -> Dict[str, Any]:
    """Build credential dict with fields appropriate for the credential type.
    
    Different credential types have different fields:
    - databricks: token_name, schema, catalog
    - snowflake: schema, user, auth_type, warehouse, role, database
    - bigquery: schema, dataset
    - postgres/redshift: schema, username, target_name
    - athena: schema
    - fabric/synapse: schema, tenant_id, client_id, authentication
    - starburst: schema, catalog
    - spark: schema
    - teradata: schema
    """
    cred_type = credential.credential_type or ""
    cred_type_lower = cred_type.lower()
    
    # Common field - schema is used by all types
    result: Dict[str, Any] = {
        "schema": credential.schema or "",
    }
    if include_source_id and credential.id:
        result["id"] = credential.id
    
    # Add credential_type if known
    if cred_type:
        result["credential_type"] = cred_type
    
    # Add type-specific fields
    if cred_type_lower == "databricks":
        result["token_name"] = credential.token_name or ""
        result["catalog"] = credential.catalog
    elif cred_type_lower == "snowflake":
        if credential.user:
            result["user"] = credential.user
        if credential.auth_type:
            result["auth_type"] = credential.auth_type
        if credential.warehouse:
            result["warehouse"] = credential.warehouse
        if credential.role:
            result["role"] = credential.role
        if credential.database:
            result["database"] = credential.database
        if credential.num_threads:
            result["num_threads"] = credential.num_threads
    elif cred_type_lower == "bigquery":
        if credential.dataset:
            result["dataset"] = credential.dataset
        if credential.num_threads:
            result["num_threads"] = credential.num_threads
    elif cred_type_lower in ("postgres", "redshift"):
        if credential.username:
            result["username"] = credential.username
        if credential.default_schema:
            result["default_schema"] = credential.default_schema
        if credential.target_name:
            result["target_name"] = credential.target_name
        if credential.num_threads:
            result["num_threads"] = credential.num_threads
    elif cred_type_lower == "athena":
        if credential.num_threads:
            result["num_threads"] = credential.num_threads
    elif cred_type_lower in ("fabric", "synapse"):
        if credential.tenant_id:
            result["tenant_id"] = credential.tenant_id
        if credential.client_id:
            result["client_id"] = credential.client_id
        if credential.authentication:
            result["authentication"] = credential.authentication
        if credential.schema_authorization:
            result["schema_authorization"] = credential.schema_authorization
    elif cred_type_lower in ("starburst", "trino"):
        result["catalog"] = credential.catalog
    else:
        # Unknown type - include common fields for backwards compatibility
        result["token_name"] = credential.token_name or ""
        result["catalog"] = credential.catalog
    
    return result


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

    if config.is_resource_included("account_features") and snapshot.globals.account_features:
        v2_data["globals"]["account_features"] = _normalize_account_features(
            snapshot.globals.account_features, config, context
        )

    if config.is_resource_included("ip_restrictions"):
        v2_data["globals"]["ip_restrictions"] = _normalize_ip_restrictions(
            snapshot.globals.ip_restrictions, config, context
        )

    if config.is_resource_included("oauth_configurations"):
        v2_data["globals"]["oauth_configurations"] = _normalize_oauth_configurations(
            snapshot.globals.oauth_configurations, config, context
        )

    if config.is_resource_included("user_groups"):
        v2_data["globals"]["user_groups"] = _normalize_user_groups(
            snapshot.globals.user_groups, config, context
        )

    # Normalize projects
    if config.is_resource_included("projects"):
        v2_data["projects"] = _normalize_projects(snapshot, config, context)
    
    # Post-processing: align repository keys to project keys.
    # The TF module keys repository resources by project key in for_each,
    # so the YAML repo key must match the project key for consistency with
    # adoption, protection tracking, and Terraform state.
    _align_repository_keys_to_projects(v2_data)
    
    # Add metadata section if there are placeholders
    if context.placeholders:
        v2_data["metadata"] = {"placeholders": context.placeholders}
    
    log.info(
        f"Normalization complete: {len(v2_data.get('projects', []))} projects, "
        f"{len(context.placeholders)} placeholders, {len(context.exclusions)} exclusions"
    )
    
    return v2_data


def _align_repository_keys_to_projects(v2_data: Dict[str, Any]) -> None:
    """Rename global repository keys to match their associated project keys.

    The Terraform module (``modules/projects_v2/projects.tf``) uses the
    **project key** as the ``for_each`` key for repository resources, not the
    global repository key.  If the normalizer-generated repo key differs from
    the project key (e.g. ``dbt_ep_sse_dm_fin_fido`` vs ``sse_dm_fin_fido``),
    the Terraform plan will try to destroy-and-recreate the resource, which
    fails when ``lifecycle.prevent_destroy`` is set.

    This function performs a post-processing pass that renames each global
    repository key to the associated project key when a 1-to-1 mapping exists.
    """
    repos = v2_data.get("globals", {}).get("repositories", [])
    projects = v2_data.get("projects", [])

    if not repos or not projects:
        return

    # Build reverse map: repo_key -> list of (project_index, project_key)
    repo_to_projects: Dict[str, list] = {}
    for idx, project in enumerate(projects):
        repo_ref = project.get("repository")
        if repo_ref and isinstance(repo_ref, str):
            repo_to_projects.setdefault(repo_ref, []).append(
                (idx, project.get("key", ""))
            )

    # Build set of existing repo keys for collision detection
    existing_repo_keys = {r.get("key") for r in repos}

    for repo in repos:
        repo_key = repo.get("key", "")
        associations = repo_to_projects.get(repo_key, [])

        # Only rename when there is exactly one associated project
        if len(associations) != 1:
            continue

        _proj_idx, project_key = associations[0]

        # Already aligned – nothing to do
        if repo_key == project_key:
            continue

        # Skip if the target key already belongs to a different repo
        if project_key in existing_repo_keys:
            log.warning(
                f"Cannot rename repo key '{repo_key}' -> '{project_key}': "
                f"target key already exists as another repo"
            )
            continue

        log.info(
            f"Aligning repository key '{repo_key}' -> '{project_key}' "
            f"(matches project key)"
        )

        # Update the global repo entry
        existing_repo_keys.discard(repo_key)
        existing_repo_keys.add(project_key)
        repo["key"] = project_key

        # Update every project that references this repo
        for pidx, _ in associations:
            projects[pidx]["repository"] = project_key


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
    
    _sorted_connections = sorted(connections.items(), key=lambda kv: (kv[0], kv[1].id or 0))
    for key, conn in _sorted_connections:
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
        
        # Extract provider_config from connection details (fetched from individual endpoint).
        # Config values can appear in two places:
        # 1) conn.details.connection_details.config (include_related payload)
        # 2) conn.details.config (top-level detail payload)
        #
        # We merge both so fields missing from include_related (for example BigQuery
        # private_key_id in some API responses) are backfilled from top-level config.
        provider_config: Dict[str, Any] = {}
        connection_details = conn.details.get("connection_details")
        if connection_details and isinstance(connection_details, dict):
            provider_config.update(
                _map_connection_details_to_terraform(conn.type, connection_details)
            )
        details_config = conn.details.get("config")
        if details_config and isinstance(details_config, dict):
            fallback_provider_config = _map_connection_details_to_terraform(
                conn.type, {"config": details_config}
            )
            for field, value in fallback_provider_config.items():
                provider_config.setdefault(field, value)
        
        if provider_config:
            conn_data["provider_config"] = provider_config
            log.debug(f"Mapped provider_config for {key}: {list(provider_config.keys())}")
        
        # Add only essential provider-specific configuration
        if conn.details and config.include_connection_details:
            essential_fields = {}
            
            # Include adapter version if present
            if "adapter_version" in conn.details:
                essential_fields["adapter_version"] = conn.details["adapter_version"]
            
            # Include SSH tunnel setting if enabled
            if conn.details.get("is_ssh_tunnel_enabled"):
                essential_fields["is_ssh_tunnel_enabled"] = True
            
            # Include provider-specific config if present (legacy - from old fetcher)
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
    
    _sorted_repos = sorted(repositories.items(), key=lambda kv: (kv[0], kv[1].id or 0))
    for key, repo in _sorted_repos:
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
            # ALWAYS include these fields for Terraform type consistency
            # (all list elements must have the same structure)
            "assign_by_default": group.assign_by_default if group.assign_by_default is not None else False,
            "sso_mapping_groups": group.sso_mapping_groups if group.sso_mapping_groups else [],
        }
        
        # Build group_permissions from metadata.group_permissions
        # ALWAYS include this field to ensure Terraform type consistency
        group_data["group_permissions"] = []
        group_permissions = group.metadata.get("group_permissions", [])
        if group_permissions:
            seen_permission_signatures: set[tuple[str, bool, str, tuple[str, ...]]] = set()
            duplicate_permissions_dropped = 0
            for perm in group_permissions:
                source_project_id = perm.get("project_id")
                # Convert source project_id to project_key for cross-account migration
                project_key = context.resolve_project_id_to_key(source_project_id) if source_project_id else None
                writable_categories = perm.get("writable_environment_categories", [])
                if not isinstance(writable_categories, list):
                    writable_categories = []
                writable_categories = [str(x) for x in writable_categories]
                all_projects = source_project_id is None
                permission_set = str(perm.get("permission_set", ""))
                signature = (
                    permission_set,
                    all_projects,
                    str(project_key) if project_key is not None else "",
                    tuple(sorted(writable_categories)),
                )
                if signature in seen_permission_signatures:
                    duplicate_permissions_dropped += 1
                    continue
                seen_permission_signatures.add(signature)
                perm_data = {
                    "permission_set": permission_set,
                    "all_projects": all_projects,
                    # Use project_key instead of project_id for Terraform to resolve to target project
                    "project_key": project_key,
                    # Keep project_id for type consistency but set to None (source IDs don't exist in target)
                    "project_id": None,
                    # Always include writable_environment_categories for type consistency (empty list if not present)
                    "writable_environment_categories": writable_categories,
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


def _normalize_account_features(
    features: AccountFeatures,
    config: MappingConfig,
    context: NormalizationContext,
) -> Dict[str, Any]:
    """Normalize account features to v2 format (singleton)."""
    result: Dict[str, Any] = {}
    if features.advanced_ci is not None:
        result["advanced_ci"] = features.advanced_ci
    if features.partial_parsing is not None:
        result["partial_parsing"] = features.partial_parsing
    if features.repo_caching is not None:
        result["repo_caching"] = features.repo_caching
    return result


def _normalize_ip_restrictions(
    rules: Dict[str, IpRestrictionsRule],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize IP restriction rules to v2 format."""
    result = []
    exclude_keys = config.get_exclude_keys("ip_restrictions")
    exclude_ids = config.get_exclude_ids("ip_restrictions")

    for key, rule in rules.items():
        if key in exclude_keys or _get_element_id(rule) and _get_element_id(rule) in exclude_ids:
            context.add_exclusion("ip_restriction", key, "Excluded by filter", _get_element_id(rule))
            continue

        normalized_key = context.resolve_collision(key, namespace="ip_restrictions")
        if _get_element_id(rule):
            context.register_element(_get_element_id(rule), normalized_key)

        rule_data: Dict[str, Any] = {
            "key": normalized_key,
            "name": rule.name,
            "type": rule.type,
            "description": rule.description,
            "rule_set_enabled": rule.rule_set_enabled if rule.rule_set_enabled is not None else False,
            "cidrs": rule.cidrs if rule.cidrs else [],
        }

        if not config.should_strip_source_ids() and rule.id:
            rule_data["id"] = rule.id

        result.append(rule_data)

    return result


def _normalize_oauth_configurations(
    configs: Dict[str, OAuthConfiguration],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize OAuth configurations to v2 format. client_secret is redacted."""
    result = []
    exclude_keys = config.get_exclude_keys("oauth_configurations")
    exclude_ids = config.get_exclude_ids("oauth_configurations")

    for key, oauth in configs.items():
        if key in exclude_keys or _get_element_id(oauth) and _get_element_id(oauth) in exclude_ids:
            context.add_exclusion("oauth_configuration", key, "Excluded by filter", _get_element_id(oauth))
            continue

        normalized_key = context.resolve_collision(key, namespace="oauth_configurations")
        if _get_element_id(oauth):
            context.register_element(_get_element_id(oauth), normalized_key)

        oauth_data: Dict[str, Any] = {
            "key": normalized_key,
            "name": oauth.name,
            "type": oauth.type,
            "client_id": oauth.client_id,
            "client_secret": "__REDACTED__",
            "authorize_url": oauth.authorize_url,
            "token_url": oauth.token_url,
            "redirect_uri": oauth.redirect_uri,
        }

        if not config.should_strip_source_ids() and oauth.id:
            oauth_data["id"] = oauth.id

        result.append(oauth_data)

    return result


def _normalize_user_groups(
    user_groups: Dict[str, UserGroups],
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize user-group assignments to v2 format."""
    result = []
    exclude_keys = config.get_exclude_keys("user_groups")

    for key, ug in user_groups.items():
        if key in exclude_keys:
            context.add_exclusion("user_groups", key, "Excluded by filter", ug.user_id)
            continue

        normalized_key = context.resolve_collision(key, namespace="user_groups")

        ug_data: Dict[str, Any] = {
            "key": normalized_key,
            "user_id": ug.user_id,
            "email": ug.email,
            "group_ids": ug.group_ids,
        }

        result.append(ug_data)

    return result


def _normalize_lineage_integrations(
    project: Project,
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize lineage integrations for a project. Token is redacted."""
    result = []
    for li in project.lineage_integrations:
        li_data: Dict[str, Any] = {
            "key": li.key,
            "host": li.host,
            "site_id": li.site_id,
            "token_name": li.token_name,
            "token": "__REDACTED__",
        }
        if not config.should_strip_source_ids() and li.id:
            li_data["id"] = li.id
        result.append(li_data)
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
    
    _sorted_projects = sorted(
        snapshot.projects,
        key=lambda p: (0, p.id or 0, p.name, p.key) if p.id else (1, 0, p.name, p.key),
    )
    for project in _sorted_projects:
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
    
    _sorted_projects = sorted(
        snapshot.projects,
        key=lambda p: (0, p.id or 0, p.name, p.key) if p.id else (1, 0, p.name, p.key),
    )
    for project in _sorted_projects:
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

        if not config.should_strip_source_ids() and project.id:
            project_data["id"] = project.id
        
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
        
        # Normalize extended attributes
        if config.is_resource_included("extended_attributes"):
            project_data["extended_attributes"] = _normalize_extended_attributes(project, config, context)
        
        # Normalize jobs
        if config.is_resource_included("jobs"):
            project_data["jobs"] = _normalize_jobs(project, config, context)
        
        # Normalize environment variables
        if config.is_resource_included("environment_variables"):
            project_data["environment_variables"] = _normalize_environment_variables(project, config, context)

        # Project artefacts (docs/freshness job keys)
        # Resolve source job IDs to job keys so the TF module can look up target job IDs.
        if project.docs_job_id or project.freshness_job_id:
            job_id_to_key = {j.id: j.key for j in project.jobs if getattr(j, "id", None)}
            artefacts: Dict[str, Any] = {}
            if project.docs_job_id:
                docs_key = job_id_to_key.get(project.docs_job_id)
                if docs_key:
                    artefacts["docs_job_key"] = docs_key
            if project.freshness_job_id:
                freshness_key = job_id_to_key.get(project.freshness_job_id)
                if freshness_key:
                    artefacts["freshness_job_key"] = freshness_key
            if artefacts:
                project_data["project_artefacts"] = artefacts

        # Lineage integrations
        if project.lineage_integrations:
            project_data["lineage_integrations"] = _normalize_lineage_integrations(
                project, config, context
            )

        # Semantic layer configuration
        if project.semantic_layer_config:
            project_data["semantic_layer_config"] = {
                "environment_id": project.semantic_layer_config.environment_id,
            }
            if not config.should_strip_source_ids() and project.semantic_layer_config.id:
                project_data["semantic_layer_config"]["id"] = project.semantic_layer_config.id

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
    exclude_ids = config.get_exclude_ids("environments")
    
    for env in project.environments:
        element_id = _get_element_id(env)
        
        if env.key in exclude_keys:
            context.add_exclusion("environment", env.key, "Excluded by key filter", element_id)
            continue
        
        if element_id and element_id in exclude_ids:
            context.add_exclusion("environment", env.key, "Excluded by element ID filter", element_id)
            continue
        
        if not _should_include(env, config):
            context.add_exclusion("environment", env.key, "Inactive", element_id)
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
        
        # Credential - output fields based on credential type
        env_data["credential"] = _build_credential_dict(
            env.credential,
            include_source_id=not config.should_strip_source_ids(),
        )
        
        # Optional fields - ALWAYS include to ensure Terraform type consistency
        env_data["dbt_version"] = env.dbt_version or None
        env_data["custom_branch"] = env.custom_branch or None
        env_data["enable_model_query_history"] = env.enable_model_query_history
        env_data["deployment_type"] = env.deployment_type or None
        env_data["extended_attributes_key"] = getattr(env, "extended_attributes_key", None) or None
        if not config.should_strip_source_ids() and env.id:
            env_data["id"] = env.id
        
        result.append(env_data)
    
    return result


def _normalize_extended_attributes(
    project: Project,
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize extended attributes for a project."""
    result = []
    exclude_keys = config.get_exclude_keys("extended_attributes")
    for ext in getattr(project, "extended_attributes", []) or []:
        if ext.key in exclude_keys:
            context.add_exclusion("extended_attributes", ext.key, "Excluded by key filter", str(ext.id) if ext.id else None)
            continue
        item: Dict[str, Any] = {
            "key": ext.key,
            "extended_attributes": ext.extended_attributes,
        }
        if ext.id is not None:
            item["id"] = ext.id
        if ext.state is not None and ext.state != 1:
            item["state"] = ext.state
        if getattr(ext, "protected", False):
            item["protected"] = True
        result.append(item)
    return result


def _normalize_jobs(
    project: Project,
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize jobs for a project."""
    result = []
    exclude_keys = config.get_exclude_keys("jobs")
    exclude_ids = config.get_exclude_ids("jobs")
    
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
        element_id = _get_element_id(job)
        
        if job.key in exclude_keys:
            context.add_exclusion("job", job.key, "Excluded by key filter", element_id)
            continue
        
        if element_id and element_id in exclude_ids:
            context.add_exclusion("job", job.key, "Excluded by element ID filter", element_id)
            continue
        
        if not _should_include(job, config):
            context.add_exclusion("job", job.key, "Inactive", element_id)
            continue
        
        # Resolve collision using full key (project_key + job_key) to ensure uniqueness
        full_key = f"{project.key}_{job.key}"
        normalized_full_key = context.resolve_collision(full_key, namespace="jobs")
        if _get_element_id(job):
            context.register_element(_get_element_id(job), normalized_full_key)
        
        # Extract the job-only portion of the normalized key (strip project prefix)
        # This handles collision suffixes (e.g., "job_name" -> "job_name_2")
        project_prefix = f"{project.key}_"
        resolved_job_key = (
            normalized_full_key[len(project_prefix):]
            if normalized_full_key.startswith(project_prefix)
            else job.key
        )
        
        job_data = {
            "key": resolved_job_key,  # Use collision-resolved key within project scope
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
        
        # Check for self-deferral: when deferring_job_definition_id equals the job's own ID
        deferring_job_id = job.settings.get("deferring_job_definition_id")
        job_id = job.settings.get("id") or job.id
        if deferring_job_id is not None and deferring_job_id == job_id:
            job_data["self_deferring"] = True
        
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

        # job_type: Preserve the API value so Terraform doesn't flip it on plan.
        # Common values: "scheduled", "ci", "merge", "other".
        job_data["job_type"] = job.settings.get("job_type") or None

        # SAO (State-Aware Orchestration) fields
        # Detect CI/Merge jobs: force_node_selection must be omitted for these job types
        # as the dbt Cloud API rejects explicit values for CI/Merge jobs
        is_ci_merge = False
        if isinstance(job.triggers, dict):
            is_ci_merge = (
                job.triggers.get("github_webhook", False) or
                job.triggers.get("git_provider_webhook", False) or
                job.triggers.get("on_merge", False) or
                job.settings.get("job_type") in ("ci", "merge")
            )
        
        # force_node_selection: Only include for non-CI/Merge jobs
        if not is_ci_merge:
            force_node_sel = job.settings.get("force_node_selection")
            job_data["force_node_selection"] = force_node_sel  # Include even if None for consistency
        else:
            job_data["force_node_selection"] = None
        
        # cost_optimization_features: Include if present (applies to all job types)
        cost_opt = job.settings.get("cost_optimization_features")
        job_data["cost_optimization_features"] = cost_opt if cost_opt else None

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
        if not config.should_strip_source_ids() and job.id:
            job_data["id"] = job.id
        
        result.append(job_data)
    
    return result


def _normalize_environment_variables(
    project: Project,
    config: MappingConfig,
    context: NormalizationContext,
) -> List[Dict[str, Any]]:
    """Normalize environment variables for a project."""
    result = []
    exclude_ids = config.get_exclude_ids("environment_variables")
    
    for var in project.environment_variables:
        # Check exclude_ids filter
        element_id = _get_element_id(var)
        if element_id and element_id in exclude_ids:
            context.add_exclusion("environment_variable", var.name, "Excluded by element ID filter", element_id)
            continue
        
        # Skip secrets based on config
        if var.name.startswith("DBT_ENV_SECRET"):
            if config.get_secret_handling() == "omit":
                context.add_exclusion("environment_variable", var.name, "Secret variable omitted", element_id)
                continue
        
        if not _should_include(var, config):
            context.add_exclusion("environment_variable", var.name, "Inactive", element_id)
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
        source_var_id = getattr(var, "id", None)
        if not config.should_strip_source_ids() and source_var_id:
            var_data["id"] = source_var_id
        
        result.append(var_data)
    
    return result

