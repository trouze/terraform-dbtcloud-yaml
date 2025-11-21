"""Functions to fetch dbt Cloud account data into the internal model."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List

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


def _fetch_connections(client: DbtCloudClient) -> Dict[str, Connection]:
    log.info("Fetching connections (v3)")
    connections: Dict[str, Connection] = {}
    for item in client.paginate("/connections/", version="v3"):
        key = item.get("name") or f"connection_{item['id']}"
        connection_key = slug(key)
        connections[connection_key] = Connection(
            key=connection_key,
            id=item.get("id"),
            name=item.get("name"),
            type=item.get("type"),
            details=item,
        )
    return connections


def _fetch_repositories(client: DbtCloudClient) -> Dict[str, Repository]:
    log.info("Fetching repositories (v2)")
    repositories: Dict[str, Repository] = {}
    for item in client.paginate("/repositories/"):
        name = item.get("remote_url", "repo")
        repo_key = slug(item.get("name") or name)
        repositories[repo_key] = Repository(
            key=repo_key,
            id=item.get("id"),
            remote_url=item["remote_url"],
            git_clone_strategy=item.get("git_clone_strategy"),
            metadata=item,
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
                notification_type=notif_type,
                state=item.get("state"),
                user_id=item.get("user_id"),
                on_success=item.get("on_success", []),
                on_failure=item.get("on_failure", []),
                on_cancel=item.get("on_cancel", []),
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
        
        yield Job(
            key=job_key,
            id=item.get("id"),
            name=item["name"],
            environment_key=environment_key,
            execute_steps=item.get("execute_steps", []),
            triggers=item.get("triggers", {}),
            settings=item,
        )


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


