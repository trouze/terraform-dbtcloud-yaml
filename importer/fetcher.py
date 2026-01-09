"""Functions to fetch dbt Cloud account data into the internal model."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional

from slugify import slugify

from .client import DbtCloudClient
from .models import (
    AccountSnapshot,
    Connection,
    Credential,
    Environment,
    EnvironmentVariable,
    Globals,
    Group,
    Job,
    Notification,
    PrivateLinkEndpoint,
    Project,
    Repository,
    ServiceToken,
    WebhookSubscription,
)

log = logging.getLogger(__name__)


def slug(value: str) -> str:
    return slugify(value, separator="_")


def _should_include_resource(item: Dict[str, Any]) -> bool:
    """Filter out deleted resources (state=2)."""
    state = item.get("state")
    if state == 2:
        return False
    return True


def fetch_account_snapshot(client: DbtCloudClient) -> AccountSnapshot:
    log.info("Fetching dbt Cloud account snapshot ...")
    
    # Fetch account information
    log.info("Fetching account details (v2)")
    try:
        account_data = client.get("/", version="v2")
        account_name = account_data.get("data", {}).get("name", None)
    except Exception as exc:
        log.warning("Failed to fetch account name: %s", exc)
        account_name = None
    
    globals_model = Globals(
        connections=_fetch_connections(client),
        repositories=_fetch_repositories(client),
        service_tokens=_fetch_service_tokens(client),
        groups=_fetch_groups(client),
        notifications=_fetch_notifications(client),
        webhooks=_fetch_webhooks(client),
        privatelink_endpoints=_fetch_privatelink_endpoints(client),
    )

    projects = _fetch_projects(client, globals_model)

    return AccountSnapshot(
        account_id=client.settings.account_id,
        account_name=account_name,
        globals=globals_model,
        projects=projects,
    )


def _extract_connection_type_from_adapter_version(adapter_version: Optional[str]) -> Optional[str]:
    """
    Extract connection type from adapter_version.
    
    The dbt Cloud API v3 returns adapter_version (e.g., "databricks_v0", "snowflake_v0")
    but the 'type' field is often null. This function extracts the connection type
    from the adapter_version string.
    
    Examples:
        "databricks_v0" -> "databricks"
        "snowflake_v0" -> "snowflake"
        "bigquery_v1" -> "bigquery"
        "databricks_spark_v0" -> "databricks"
        "trino_v0" -> "starburst" (Terraform uses "starburst" for Trino/Starburst)
    
    Returns None if adapter_version is None or doesn't match expected pattern.
    """
    if not adapter_version:
        return None
    
    # Handle special cases first
    if adapter_version.startswith("databricks"):
        return "databricks"
    elif adapter_version.startswith("snowflake"):
        return "snowflake"
    elif adapter_version.startswith("bigquery"):
        return "bigquery"
    elif adapter_version.startswith("postgres"):
        return "postgres"
    elif adapter_version.startswith("redshift"):
        return "redshift"
    elif adapter_version.startswith("athena"):
        return "athena"
    elif adapter_version.startswith("fabric"):
        return "fabric"
    elif adapter_version.startswith("synapse"):
        return "synapse"
    elif adapter_version.startswith("trino") or adapter_version.startswith("starburst"):
        return "starburst"
    elif adapter_version.startswith("apache_spark"):
        return "apache_spark"
    elif adapter_version.startswith("teradata"):
        return "teradata"
    else:
        # Generic fallback: remove _v0, _v1, etc. suffix
        match = re.match(r"^(.+?)_v\d+$", adapter_version)
        if match:
            return match.group(1)
        return None


def _fetch_connections(client: DbtCloudClient) -> Dict[str, Connection]:
    log.info("Fetching connections (v3)")
    connections: Dict[str, Connection] = {}
    for item in client.paginate("/connections/", version="v3"):
        key = item.get("name") or f"connection_{item['id']}"
        connection_key = slug(key)
        
        # Extract connection type: prefer API 'type' field, fall back to adapter_version
        # According to API docs, 'type' is often null, so we derive it from adapter_version
        conn_type = item.get("type")
        adapter_version = item.get("adapter_version")
        
        if not conn_type and adapter_version:
            conn_type = _extract_connection_type_from_adapter_version(adapter_version)
            if conn_type:
                log.debug(f"Derived connection type '{conn_type}' from adapter_version '{adapter_version}' for connection {connection_key}")
            else:
                log.warning(f"Could not extract connection type from adapter_version '{adapter_version}' for connection {connection_key}")
        
        connections[connection_key] = Connection(
            key=connection_key,
            id=item.get("id"),
            name=item.get("name"),
            type=conn_type,
            details=item,
        )
    return connections


def _fetch_repositories(client: DbtCloudClient) -> Dict[str, Repository]:
    log.info("Fetching repositories (v2)")
    repositories: Dict[str, Repository] = {}
    for item in client.paginate("/repositories/"):
        name = item.get("remote_url", "repo")
        repo_key = slug(item.get("name") or name)
        
        # For GitLab repositories (deploy_token strategy), fetch detailed info via v3
        # to get the gitlab object with gitlab_project_id
        metadata = item.copy()
        if item.get("git_clone_strategy") == "deploy_token" or item.get("remote_backend") == "gitlab":
            repo_id = item.get("id")
            project_id = item.get("project_id")
            if repo_id and project_id:
                try:
                    log.info(f"Fetching detailed GitLab repository info for {repo_key} (v3)")
                    # Use include_related to get the gitlab object with gitlab_project_id (undocumented API feature)
                    detailed = client.get(
                        f"/projects/{project_id}/repositories/{repo_id}/",
                        version="v3",
                        params={"include_related": '["deploy_key","gitlab"]'}
                    )
                    if detailed and detailed.get("data"):
                        repo_data = detailed["data"]
                        # Merge the gitlab object into metadata
                        if repo_data.get("gitlab"):
                            metadata["gitlab"] = repo_data["gitlab"]
                            # Also extract gitlab_project_id to top level for easier access
                            gitlab_project_id = repo_data["gitlab"].get("gitlab_project_id")
                            if gitlab_project_id:
                                metadata["gitlab_project_id"] = gitlab_project_id
                                log.info(f"Found gitlab_project_id={gitlab_project_id} for {repo_key}")
                except Exception as exc:
                    log.warning(f"Failed to fetch detailed repository info for {repo_key}: {exc}")
        
        repositories[repo_key] = Repository(
            key=repo_key,
            id=item.get("id"),
            remote_url=item["remote_url"],
            git_clone_strategy=item.get("git_clone_strategy"),
            metadata=metadata,
        )
    return repositories


def _fetch_service_tokens(client: DbtCloudClient) -> Dict[str, ServiceToken]:
    """Fetch service tokens (v3). Secrets are masked by the API."""
    log.info("Fetching service tokens (v3)")
    service_tokens = {}
    try:
        # Service tokens endpoint doesn't support pagination parameters
        response = client.get("/service-tokens/", version="v3")
        data = response.get("data", [])
        
        if isinstance(data, list):
            for item in data:
                if not _should_include_resource(item):
                    log.debug(f"Skipping deleted service token: {item.get('name')} (state={item.get('state')})")
                    continue
                key = slug(item["name"])
                
                # Extract permission sets and project IDs from permission_grants
                permission_sets = []
                project_ids = []
                if item.get("permission_grants"):
                    perm_sets = set()
                    proj_ids = set()
                    for grant in item["permission_grants"]:
                        if grant.get("permission_set"):
                            perm_sets.add(grant["permission_set"])
                        if grant.get("project_id"):
                            proj_ids.add(grant["project_id"])
                    permission_sets = sorted(list(perm_sets))
                    project_ids = sorted(list(proj_ids))
                
                service_tokens[key] = ServiceToken(
                    key=key,
                    id=item.get("id"),
                    name=item["name"],
                    state=item.get("state"),
                    token_string=item.get("token_string"),
                    permission_sets=permission_sets,
                    project_ids=project_ids,
                    metadata=item,
                )
        else:
            log.warning("Unexpected response structure for service tokens: %s", response)
    except Exception as exc:
        log.warning("Failed to fetch service tokens (may require Owner permissions): %s", exc)
    return service_tokens


def _fetch_groups(client: DbtCloudClient) -> Dict[str, Group]:
    """Fetch groups (v3). Requires account admin or owner permissions."""
    log.info("Fetching groups (v3)")
    groups = {}
    try:
        for item in client.paginate("/groups/", version="v3"):
            key = slug(item["name"])
            sso_mappings = []
            if item.get("sso_mapping_groups"):
                sso_mappings = item["sso_mapping_groups"]
            
            # Extract unique permission sets from group_permissions
            permission_sets = []
            if item.get("group_permissions"):
                perms = set()
                for perm in item["group_permissions"]:
                    if perm.get("permission_set"):
                        perms.add(perm["permission_set"])
                permission_sets = sorted(list(perms))
            
            groups[key] = Group(
                key=key,
                id=item.get("id"),
                name=item["name"],
                assign_by_default=item.get("assign_by_default"),
                sso_mapping_groups=sso_mappings,
                permission_sets=permission_sets,
                metadata=item,
            )
    except Exception as exc:
        log.warning("Failed to fetch groups (may require Owner permissions): %s", exc)
    return groups


def _fetch_notifications(client: DbtCloudClient) -> Dict[str, Notification]:
    """Fetch notifications (v2). Returns email, Slack, and webhook notifications."""
    log.info("Fetching notifications (v2)")
    notifications = {}
    try:
        for item in client.paginate("/notifications/", version="v2"):
            if not _should_include_resource(item):
                log.debug(f"Skipping deleted notification: {item.get('id')} (state={item.get('state')})")
                continue
            notif_id = item.get("id", 0)
            
            # Determine notification type based on available fields
            notif_type = 0  # Unknown
            type_name = "unknown"
            
            if item.get("slack_channel_id") or item.get("slack_channel_name"):
                notif_type = 2
                type_name = "slack"
                channel = item.get("slack_channel_name", item.get("slack_channel_id", "unknown"))
                key = f"slack_{slug(str(channel))}_{notif_id}"
            elif item.get("external_email"):
                notif_type = 1
                type_name = "email"
                email = item.get("external_email", "unknown")
                key = f"email_{slug(str(email))}_{notif_id}"
            elif item.get("url"):
                notif_type = 3
                type_name = "webhook"
                key = f"webhook_{notif_id}"
            else:
                key = f"{type_name}_{notif_id}"
            
            notifications[key] = Notification(
                key=key,
                id=item.get("id"),
                notification_type=item.get("type") or notif_type,  # Use API type if available
                state=item.get("state"),
                user_id=item.get("user_id"),
                on_success=item.get("on_success", []),
                on_failure=item.get("on_failure", []),
                on_cancel=item.get("on_cancel", []),
                on_warning=item.get("on_warning", []),
                external_email=item.get("external_email"),
                slack_channel_id=item.get("slack_channel_id"),
                slack_channel_name=item.get("slack_channel_name"),
                metadata=item,
            )
    except Exception as exc:
        log.warning("Failed to fetch notifications: %s", exc)
    return notifications


def _fetch_webhooks(client: DbtCloudClient) -> Dict[str, WebhookSubscription]:
    """Fetch webhook subscriptions (v3)."""
    log.info("Fetching webhook subscriptions (v3)")
    webhooks = {}
    try:
        for item in client.paginate("/webhooks/subscriptions", version="v3"):
            webhook_id = item.get("id", "unknown")
            webhook_name = item.get("name") or f"webhook_{webhook_id}"
            key = slug(webhook_name)
            
            # Extract job IDs from event_types if they're job-specific
            job_ids = []
            for event_type in item.get("event_types", []):
                if isinstance(event_type, dict) and event_type.get("job_id"):
                    job_ids.append(event_type["job_id"])
            
            webhooks[key] = WebhookSubscription(
                key=key,
                id=item.get("id"),
                name=item.get("name"),
                client_url=item.get("client_url"),
                event_types=item.get("event_types", []),
                job_ids=job_ids,
                active=item.get("active", True),
                metadata=item,
            )
    except Exception as exc:
        log.warning("Failed to fetch webhook subscriptions: %s", exc)
    return webhooks


def _fetch_privatelink_endpoints(client: DbtCloudClient) -> Dict[str, PrivateLinkEndpoint]:
    """Fetch PrivateLink endpoints (v3)."""
    log.info("Fetching PrivateLink endpoints (v3)")
    privatelink_endpoints = {}
    try:
        for item in client.paginate("/private-link-endpoints/", version="v3"):
            endpoint_id = item.get("id", "unknown")
            endpoint_name = item.get("name") or f"privatelink_{endpoint_id}"
            key = slug(endpoint_name)
            state_value = item.get("state")
            if state_value is not None:
                state = str(state_value)
            else:
                state = None
            
            privatelink_endpoints[key] = PrivateLinkEndpoint(
                key=key,
                id=item.get("id"),
                name=item.get("name"),
                type=item.get("type"),
                state=state,
                cidr_range=item.get("cidr_range"),
                metadata=item,
            )
    except Exception as exc:
        log.warning("Failed to fetch PrivateLink endpoints: %s", exc)
    return privatelink_endpoints


def _fetch_projects(client: DbtCloudClient, globals_model: Globals) -> List[Project]:
    log.info("Fetching projects (v2)")
    projects: List[Project] = []
    for item in client.paginate("/projects/"):
        project_key = slug(item["name"])
        repository_id = item.get("repository_id")
        repository_key = _find_repo_key(globals_model.repositories, repository_id)
        project = Project(
            key=project_key,
            id=item.get("id"),
            name=item["name"],
            repository_key=repository_key,
            metadata=item,
        )
        project_id = project.id or 0
        project.environments = list(_fetch_environments(client, project_id, globals_model.connections))
        project.jobs = list(_fetch_jobs(client, project_id, project.environments))
        project.environment_variables = list(_fetch_environment_variables(client, project_id))
        projects.append(project)
    return projects


def _find_repo_key(repositories: Dict[str, Repository], repo_id: int | None) -> str | None:
    if repo_id is None:
        return None
    for repo in repositories.values():
        if repo.id == repo_id:
            return repo.key
    return None


def _fetch_environments(
    client: DbtCloudClient,
    project_id: int,
    connections: Dict[str, Connection],
) -> Iterable[Environment]:
    log.info("Fetching environments for project %s", project_id)
    for item in client.paginate("/environments/", params={"project_id": project_id}):
        env_key = slug(item["name"])
        connection_id = item.get("connection_id")
        connection_key = _find_connection_key(connections, connection_id)
        credential_data = item.get("credentials") or item.get("credential") or {}
        credential = Credential(
            token_name=credential_data.get("token_name", ""),
            schema=credential_data.get("schema", ""),
            catalog=credential_data.get("catalog"),
        )
        yield Environment(
            key=env_key,
            id=item.get("id"),
            name=item["name"],
            type=item.get("type", "development"),
            connection_key=connection_key,
            credential=credential,
            dbt_version=item.get("dbt_version"),
            custom_branch=item.get("custom_branch"),
            enable_model_query_history=item.get("enable_model_query_history"),
            deployment_type=item.get("deployment_type"),
            metadata=item,
        )


def _fetch_jobs(client: DbtCloudClient, project_id: int, environments: list) -> Iterable[Job]:
    log.info("Fetching jobs for project %s", project_id)
    # Build a mapping of environment_id -> environment_key
    env_id_to_key = {env.id: env.key for env in environments if env.id}
    
    params = {"project_id": project_id, "order_by": "id"}
    for item in client.paginate("/jobs/", params=params):
        job_key = slug(item["name"])
        # Try to get environment from the embedded object first, then from environment_id
        environment = item.get("environment") or {}
        environment_id = environment.get("id") or item.get("environment_id")
        
        # Map environment_id to key, or fallback to slug of environment name
        if environment_id and environment_id in env_id_to_key:
            environment_key = env_id_to_key[environment_id]
        elif environment.get("name"):
            environment_key = slug(environment["name"])
        else:
            environment_key = f"env_{environment_id or 'unknown'}"
        
        job_id = item.get("id")
        env_var_overrides: Dict[str, str] = {}
        if isinstance(job_id, int) and job_id != 0:
            env_var_overrides = _fetch_job_env_var_overrides(client, project_id, job_id)

        yield Job(
            key=job_key,
            id=job_id,
            name=item["name"],
            environment_key=environment_key,
            execute_steps=item.get("execute_steps", []),
            triggers=item.get("triggers", {}),
            settings=item,
            environment_variable_overrides=env_var_overrides,
        )


def _fetch_job_env_var_overrides(
    client: DbtCloudClient,
    project_id: int,
    job_definition_id: int,
) -> Dict[str, str]:
    """
    Fetch job-level environment variable overrides (v3).
    Endpoint: /projects/{project_id}/environment-variables/job/?job_definition_id={job_id}

    Response format (data) is a map like:
      { "VAR_NAME": { "project": {...}, "environment": {...}, "job": { "id": 123, "value": "X" } }, ... }
    """
    overrides: Dict[str, str] = {}
    try:
        path = f"/projects/{project_id}/environment-variables/job/"
        resp = client.get(path, version="v3", params={"job_definition_id": job_definition_id})
        data = resp.get("data", {})
        if not isinstance(data, dict):
            return overrides

        for var_name, payload in data.items():
            if not isinstance(var_name, str) or not isinstance(payload, dict):
                continue
            job_payload = payload.get("job")
            if not isinstance(job_payload, dict):
                continue
            raw_value = job_payload.get("value")
            if not isinstance(raw_value, str):
                continue

            # Secrets cannot be recovered from the source.
            # If the name looks like a secret or the value is masked, store a token_map placeholder.
            if var_name.startswith("DBT_ENV_SECRET") or raw_value.strip("*") == "":
                overrides[var_name] = f"secret_{var_name}"
            else:
                overrides[var_name] = raw_value
    except Exception as exc:  # pragma: no cover - network dependent
        log.warning(
            "Failed to fetch job env var overrides for project %s job %s: %s",
            project_id,
            job_definition_id,
            exc,
        )
    return overrides


def _fetch_environment_variables(client: DbtCloudClient, project_id: int) -> Iterable[EnvironmentVariable]:
    """Fetch project-scoped environment variables (v3)."""
    log.info("Fetching environment variables for project %s (v3)", project_id)
    path = f"/projects/{project_id}/environment-variables/environment/"
    try:
        # This endpoint doesn't paginate - it returns all variables at once
        response = client.get(path, version="v3")
        
        # The response structure is: {'status': {...}, 'data': {'environments': [...], 'variables': {...}}}
        data = response.get("data", {})
        variables = data.get("variables", {})
        
        # variables is a dict like: {'VAR_NAME': {'project': {...}, 'EnvName': {...}, ...}}
        for var_name, env_values in variables.items():
            # env_values is a dict with environment names as keys (plus 'project' for the default)
            # Extract the project default value
            project_default = None
            if "project" in env_values and isinstance(env_values["project"], dict):
                project_default = env_values["project"].get("value")
            
            # Extract environment-specific values (excluding project default)
            environment_values = {
                env_name: details["value"]
                for env_name, details in env_values.items()
                if env_name != "project" and isinstance(details, dict) and "value" in details
            }
            yield EnvironmentVariable(
                name=var_name,
                project_default=project_default,
                environment_values=environment_values
            )
    except Exception as exc:  # pragma: no cover - network dependent
        log.warning("Failed to fetch environment variables for project %s: %s", project_id, exc)


def _find_connection_key(connections: Dict[str, Connection], connection_id: int | None) -> str:
    if connection_id is None:
        return "connection_unknown"
    for connection in connections.values():
        if connection.id == connection_id:
            return connection.key
    return f"connection_{connection_id}"


