"""Functions to fetch dbt Cloud account data into the internal model."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional, Protocol, runtime_checkable

from slugify import slugify

from .client import DbtCloudClient
from .config import Settings
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


@runtime_checkable
class FetchProgressCallback(Protocol):
    """Protocol for progress reporting during fetch operations."""

    def on_phase(self, phase: str) -> None:
        """Called when entering a major phase (e.g., 'globals', 'projects')."""
        ...

    def on_resource_start(self, resource_type: str, total: Optional[int] = None) -> None:
        """Called when starting to fetch a resource type."""
        ...

    def on_resource_item(self, resource_type: str, key: str) -> None:
        """Called for each item fetched."""
        ...

    def on_resource_done(self, resource_type: str, count: int) -> None:
        """Called when finished fetching a resource type."""
        ...

    def on_project_start(self, project_num: int, total: int, name: str) -> None:
        """Called when starting to fetch a project's resources."""
        ...

    def on_project_done(self, project_num: int) -> None:
        """Called when finished fetching a project's resources."""
        ...


def slug(value: str) -> str:
    return slugify(value, separator="_")


def _should_include_resource(item: Dict[str, Any]) -> bool:
    """Filter out deleted resources (state=2)."""
    state = item.get("state")
    if state == 2:
        return False
    return True


def fetch_account_snapshot(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
    threads: int = 5,
) -> AccountSnapshot:
    """
    Fetch a complete account snapshot from dbt Cloud.

    Args:
        client: The dbt Cloud API client.
        progress: Optional callback for progress reporting.

    Returns:
        An AccountSnapshot containing all fetched resources.
    """
    log.info("Fetching dbt Cloud account snapshot ...")

    # Fetch account information
    log.info("Fetching account details (v2)")
    try:
        account_data = client.get("/", version="v2")
        account_name = account_data.get("data", {}).get("name", None)
    except Exception as exc:
        log.warning("Failed to fetch account name: %s", exc)
        account_name = None

    # Phase 1: Globals
    if progress:
        progress.on_phase("globals")

    if threads < 1:
        threads = 1

    settings: Settings = client.settings

    def _client_task(fn, *args, **kwargs):
        """Run a fetch function with a dedicated client instance (thread-safe)."""
        c = DbtCloudClient.from_settings(settings)
        try:
            return fn(c, *args, **kwargs)
        finally:
            c.close()

    # Fetch globals in parallel (bounded by threads)
    #
    # IMPORTANT: Progress UI updates (Rich Live) are not reliably thread-safe.
    # We therefore avoid invoking progress callbacks from worker threads by
    # passing progress=None into the worker functions, then updating progress
    # in the main thread as futures complete.
    globals_fns = [
        ("connections", _fetch_connections),
        ("repositories", _fetch_repositories),
        ("service_tokens", _fetch_service_tokens),
        ("groups", _fetch_groups),
        ("notifications", _fetch_notifications),
        ("webhooks", _fetch_webhooks),
        ("privatelink_endpoints", _fetch_privatelink_endpoints),
    ]

    globals_results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=threads) as ex:
        future_by_name = {}
        for name, fn in globals_fns:
            if progress:
                progress.on_resource_start(name)
            future_by_name[ex.submit(_client_task, fn, progress=None)] = name
        for fut in as_completed(future_by_name):
            name = future_by_name[fut]
            result = fut.result()
            globals_results[name] = result
            if progress:
                progress.on_resource_done(name, len(result) if hasattr(result, "__len__") else 0)

        globals_model = Globals(
            connections=globals_results["connections"],
            repositories=globals_results["repositories"],
            service_tokens=globals_results["service_tokens"],
            groups=globals_results["groups"],
            notifications=globals_results["notifications"],
            webhooks=globals_results["webhooks"],
            privatelink_endpoints=globals_results["privatelink_endpoints"],
        )

    # Phase 2: Projects
    if progress:
        progress.on_phase("projects")

        progress.on_resource_start("projects")

    # Fetch projects list once (sequential) so we can display totals / submit work
    project_items = list(client.paginate("/projects/"))
    total_projects = len(project_items)


    # Flat, non-nested concurrency to avoid deadlocks: submit env/jobs/envvars tasks per project,
    # then submit overrides tasks for all jobs, then assemble.
    def _fetch_project_environments_raw(project_id: int) -> list[dict[str, Any]]:
        c = DbtCloudClient.from_settings(settings)
        try:
            return list(c.paginate("/environments/", params={"project_id": project_id}))
        finally:
            c.close()

    def _fetch_project_jobs_raw(project_id: int) -> list[dict[str, Any]]:
        c = DbtCloudClient.from_settings(settings)
        try:
            return list(c.paginate("/jobs/", params={"project_id": project_id, "order_by": "id"}))
        finally:
            c.close()

    def _fetch_project_env_vars_raw(project_id: int) -> dict[str, Any]:
        c = DbtCloudClient.from_settings(settings)
        try:
            path = f"/projects/{project_id}/environment-variables/environment/"
            return c.get(path, version="v3").get("data", {}) or {}
        finally:
            c.close()

    def _fetch_job_overrides_raw(project_id: int, job_id: int) -> dict[str, Any]:
        c = DbtCloudClient.from_settings(settings)
        try:
            path = f"/projects/{project_id}/environment-variables/job/"
            return c.get(path, version="v3", params={"job_definition_id": job_id}).get("data", {}) or {}
        finally:
            c.close()

    # Submit all work and assemble projects as they become ready, so the UI can
    # show incremental project/env/job progress even when fetch is parallel.
    env_raw_by_project: dict[int, list[dict[str, Any]]] = {}
    jobs_raw_by_project: dict[int, list[dict[str, Any]]] = {}
    envvars_raw_by_project: dict[int, dict[str, Any]] = {}
    overrides_raw_by_job: dict[tuple[int, int], dict[str, Any]] = {}

    # Track project completeness
    project_name_by_id: dict[int, str] = {}
    project_key_by_id: dict[int, str] = {}
    project_done_flags: dict[int, dict[str, Any]] = {}

    if progress:
        # Show that project processing has started (counts will accumulate)
        # Also track queued projects so the UI can show queued vs completed.
        for item in project_items:
            progress.on_resource_item("projects", slug(item.get("name", "project")))
        progress.on_resource_start("environments")
        progress.on_resource_start("jobs")
        progress.on_resource_start("environment_variables")
        progress.on_resource_start("job_env_var_overrides")

    with ThreadPoolExecutor(max_workers=threads) as ex:
        pending: dict[Any, tuple[str, int, Optional[int]]] = {}

        # Initial per-project tasks
        for item in project_items:
            project_id = int(item.get("id") or 0)
            project_name_by_id[project_id] = item.get("name", "")
            project_key_by_id[project_id] = slug(item.get("name", f"project_{project_id}"))
            project_done_flags[project_id] = {"env": False, "jobs": False, "envvars": False, "overrides": 0, "overrides_done": 0}

            pending[ex.submit(_fetch_project_environments_raw, project_id)] = ("env", project_id, None)
            pending[ex.submit(_fetch_project_jobs_raw, project_id)] = ("jobs", project_id, None)
            pending[ex.submit(_fetch_project_env_vars_raw, project_id)] = ("envvars", project_id, None)

        # Project tasks submitted (no-op marker kept intentionally blank)

        completed_projects = 0
        env_total = 0
        jobs_total = 0
        envvars_total = 0
        overrides_total = 0
        overrides_done = 0
        assembled_by_id: set[int] = set()
        projects: list[Project] = []

        while pending:
            for fut in as_completed(list(pending.keys()), timeout=None):
                kind, pid, job_id = pending.pop(fut)
                result = fut.result()

                if kind == "env":
                    env_raw_by_project[pid] = result
                    project_done_flags[pid]["env"] = True
                    if progress:
                        env_total += len(result)
                        for _ in range(len(result)):
                            progress.on_resource_item("environments", f"{pid}")
                elif kind == "jobs":
                    jobs_raw_by_project[pid] = result
                    project_done_flags[pid]["jobs"] = True
                    if progress:
                        jobs_total += len(result)
                        for _ in range(len(result)):
                            progress.on_resource_item("jobs", f"{pid}")
                    # submit override tasks now that we know job IDs
                    for ji in result:
                        jid = ji.get("id")
                        if isinstance(jid, int) and jid != 0:
                            project_done_flags[pid]["overrides"] += 1
                            overrides_total += 1
                            pending[ex.submit(_fetch_job_overrides_raw, pid, jid)] = ("override", pid, jid)
                elif kind == "envvars":
                    envvars_raw_by_project[pid] = result
                    project_done_flags[pid]["envvars"] = True
                    vars_dict = result.get("variables", {}) if isinstance(result, dict) else {}
                    if progress and isinstance(vars_dict, dict):
                        envvars_total += len(vars_dict)
                        for _ in range(len(vars_dict)):
                            progress.on_resource_item("environment_variables", f"{pid}")
                elif kind == "override":
                    overrides_raw_by_job[(pid, int(job_id or 0))] = result if isinstance(result, dict) else {}
                    project_done_flags[pid]["overrides_done"] += 1
                    overrides_done += 1
                    if progress:
                        progress.on_resource_item("job_env_var_overrides", f"{pid}")

                # If this project is fully ready and not yet assembled, assemble it now.
                flags = project_done_flags[pid]
                if (
                    pid not in assembled_by_id
                    and flags["env"]
                    and flags["jobs"]
                    and flags["envvars"]
                    and flags["overrides_done"] >= flags["overrides"]
                ):
                    completed_projects += 1
                    if progress:
                        progress.on_project_start(completed_projects, total_projects, project_name_by_id.get(pid, ""))
                    assembled_by_id.add(pid)

                    # Assemble the Project model for this pid
                    item = next((p for p in project_items if int(p.get("id") or 0) == pid), None)
                    if item is None:
                        continue

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
                    project_id = int(project.id or 0)

                    # Environments
                    env_items = env_raw_by_project.get(project_id, [])
                    environments: list[Environment] = []
                    for env_item in env_items:
                        env_key = slug(env_item["name"])
                        connection_id = env_item.get("connection_id")
                        connection_key = _find_connection_key(globals_model.connections, connection_id)
                        credential_data = env_item.get("credentials") or env_item.get("credential") or {}
                        credential = Credential(
                            token_name=credential_data.get("token_name", ""),
                            schema=credential_data.get("schema", ""),
                            catalog=credential_data.get("catalog"),
                        )
                        environments.append(
                            Environment(
                                key=env_key,
                                id=env_item.get("id"),
                                name=env_item["name"],
                                type=env_item.get("type", "development"),
                                connection_key=connection_key,
                                credential=credential,
                                dbt_version=env_item.get("dbt_version"),
                                custom_branch=env_item.get("custom_branch"),
                                enable_model_query_history=env_item.get("enable_model_query_history"),
                                deployment_type=env_item.get("deployment_type"),
                                metadata=env_item,
                            )
                        )
                    project.environments = environments

                    env_id_to_key = {e.id: e.key for e in environments if e.id}

                    # Jobs + overrides
                    job_items = jobs_raw_by_project.get(project_id, [])
                    jobs: list[Job] = []
                    for job_item in job_items:
                        job_key = slug(job_item["name"])
                        environment = job_item.get("environment") or {}
                        environment_id = environment.get("id") or job_item.get("environment_id")
                        if environment_id and environment_id in env_id_to_key:
                            environment_key = env_id_to_key[environment_id]
                        elif environment.get("name"):
                            environment_key = slug(environment["name"])
                        else:
                            environment_key = f"env_{environment_id or 'unknown'}"

                        job_id_val = job_item.get("id")
                        raw_overrides = {}
                        if isinstance(job_id_val, int) and job_id_val != 0:
                            raw_overrides = overrides_raw_by_job.get((project_id, job_id_val), {}) or {}

                        env_var_overrides: Dict[str, str] = {}
                        if isinstance(raw_overrides, dict):
                            for var_name, payload in raw_overrides.items():
                                if not isinstance(var_name, str) or not isinstance(payload, dict):
                                    continue
                                job_payload = payload.get("job")
                                if not isinstance(job_payload, dict):
                                    continue
                                raw_value = job_payload.get("value")
                                if not isinstance(raw_value, str):
                                    continue
                                if var_name.startswith("DBT_ENV_SECRET") or raw_value.strip("*") == "":
                                    env_var_overrides[var_name] = f"secret_{var_name}"
                                else:
                                    env_var_overrides[var_name] = raw_value

                        jobs.append(
                            Job(
                                key=job_key,
                                id=job_id_val,
                                name=job_item["name"],
                                environment_key=environment_key,
                                execute_steps=job_item.get("execute_steps", []),
                                triggers=job_item.get("triggers", {}),
                                settings=job_item,
                                environment_variable_overrides=env_var_overrides,
                            )
                        )
                    project.jobs = jobs

                    # Environment variables (project-scoped)
                    env_vars_data = envvars_raw_by_project.get(project_id, {}) or {}
                    variables = env_vars_data.get("variables", {}) if isinstance(env_vars_data, dict) else {}
                    env_vars: list[EnvironmentVariable] = []
                    if isinstance(variables, dict):
                        for var_name, env_values in variables.items():
                            if not isinstance(var_name, str) or not isinstance(env_values, dict):
                                continue
                            project_default = None
                            if "project" in env_values and isinstance(env_values["project"], dict):
                                project_default = env_values["project"].get("value")
                            environment_values = {
                                env_name: details["value"]
                                for env_name, details in env_values.items()
                                if env_name != "project" and isinstance(details, dict) and "value" in details
                            }
                            env_vars.append(
                                EnvironmentVariable(
                                    name=var_name,
                                    project_default=project_default,
                                    environment_values=environment_values,
                                )
                            )
                    project.environment_variables = env_vars

                    projects.append(project)
                    if progress:
                        progress.on_project_done(completed_projects)

                # Exit inner loop early if we haven't assembled everything yet; continue outer while
                if not pending:
                    break

        # Mark these resources done after all projects completed
        if progress:
            progress.on_resource_done("environments", env_total)
            progress.on_resource_done("jobs", jobs_total)
            progress.on_resource_done("environment_variables", envvars_total)
            progress.on_resource_done("job_env_var_overrides", overrides_done)

    # Ensure stable ordering by project key for downstream behavior
    projects.sort(key=lambda p: p.key)

    if progress:
        progress.on_resource_done("projects", len(projects))

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


def _fetch_connections(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, Connection]:
    log.info("Fetching connections (v3)")
    if progress:
        progress.on_resource_start("connections")
    connections: Dict[str, Connection] = {}
    for item in client.paginate("/connections/", version="v3"):
        key = item.get("name") or f"connection_{item['id']}"
        connection_key = slug(key)

        if progress:
            progress.on_resource_item("connections", connection_key)

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
    if progress:
        progress.on_resource_done("connections", len(connections))
    return connections


def _fetch_repositories(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, Repository]:
    log.info("Fetching repositories (v2)")
    if progress:
        progress.on_resource_start("repositories")
    repositories: Dict[str, Repository] = {}
    for item in client.paginate("/repositories/"):
        name = item.get("remote_url", "repo")
        repo_key = slug(item.get("name") or name)

        if progress:
            progress.on_resource_item("repositories", repo_key)

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
    if progress:
        progress.on_resource_done("repositories", len(repositories))
    return repositories


def _fetch_service_tokens(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, ServiceToken]:
    """Fetch service tokens (v3). Secrets are masked by the API."""
    log.info("Fetching service tokens (v3)")
    if progress:
        progress.on_resource_start("service_tokens")
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

                if progress:
                    progress.on_resource_item("service_tokens", key)

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
    if progress:
        progress.on_resource_done("service_tokens", len(service_tokens))
    return service_tokens


def _fetch_groups(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, Group]:
    """Fetch groups (v3). Requires account admin or owner permissions."""
    log.info("Fetching groups (v3)")
    if progress:
        progress.on_resource_start("groups")
    groups = {}
    try:
        for item in client.paginate("/groups/", version="v3"):
            key = slug(item["name"])

            if progress:
                progress.on_resource_item("groups", key)

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
    if progress:
        progress.on_resource_done("groups", len(groups))
    return groups


def _fetch_notifications(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, Notification]:
    """Fetch notifications (v2). Returns email, Slack, and webhook notifications."""
    log.info("Fetching notifications (v2)")
    if progress:
        progress.on_resource_start("notifications")
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

            if progress:
                progress.on_resource_item("notifications", key)

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
    if progress:
        progress.on_resource_done("notifications", len(notifications))
    return notifications


def _fetch_webhooks(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, WebhookSubscription]:
    """Fetch webhook subscriptions (v3)."""
    log.info("Fetching webhook subscriptions (v3)")
    if progress:
        progress.on_resource_start("webhooks")
    webhooks = {}
    try:
        for item in client.paginate("/webhooks/subscriptions", version="v3"):
            webhook_id = item.get("id", "unknown")
            webhook_name = item.get("name") or f"webhook_{webhook_id}"
            key = slug(webhook_name)

            if progress:
                progress.on_resource_item("webhooks", key)

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
    if progress:
        progress.on_resource_done("webhooks", len(webhooks))
    return webhooks


def _fetch_privatelink_endpoints(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, PrivateLinkEndpoint]:
    """Fetch PrivateLink endpoints (v3)."""
    log.info("Fetching PrivateLink endpoints (v3)")
    if progress:
        progress.on_resource_start("privatelink_endpoints")
    privatelink_endpoints = {}
    try:
        for item in client.paginate("/private-link-endpoints/", version="v3"):
            endpoint_id = item.get("id", "unknown")
            endpoint_name = item.get("name") or f"privatelink_{endpoint_id}"
            key = slug(endpoint_name)

            if progress:
                progress.on_resource_item("privatelink_endpoints", key)

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
    if progress:
        progress.on_resource_done("privatelink_endpoints", len(privatelink_endpoints))
    return privatelink_endpoints


def _fetch_projects(
    client: DbtCloudClient,
    globals_model: Globals,
    progress: Optional[FetchProgressCallback] = None,
) -> List[Project]:
    log.info("Fetching projects (v2)")
    if progress:
        progress.on_resource_start("projects")

    # First, collect all project items so we know the total count
    project_items = list(client.paginate("/projects/"))
    total_projects = len(project_items)

    projects: List[Project] = []
    for idx, item in enumerate(project_items, start=1):
        project_key = slug(item["name"])
        project_name = item["name"]

        if progress:
            progress.on_resource_item("projects", project_key)
            progress.on_project_start(idx, total_projects, project_name)

        repository_id = item.get("repository_id")
        repository_key = _find_repo_key(globals_model.repositories, repository_id)
        project = Project(
            key=project_key,
            id=item.get("id"),
            name=project_name,
            repository_key=repository_key,
            metadata=item,
        )
        project_id = project.id or 0
        project.environments = list(
            _fetch_environments(client, project_id, globals_model.connections, progress)
        )
        project.jobs = list(
            _fetch_jobs(client, project_id, project.environments, progress)
        )
        project.environment_variables = list(
            _fetch_environment_variables(client, project_id, progress)
        )
        projects.append(project)

        if progress:
            progress.on_project_done(idx)

    if progress:
        progress.on_resource_done("projects", len(projects))
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
    progress: Optional[FetchProgressCallback] = None,
) -> Iterable[Environment]:
    log.info("Fetching environments for project %s", project_id)
    if progress:
        progress.on_resource_start("environments")
    count = 0
    for item in client.paginate("/environments/", params={"project_id": project_id}):
        env_key = slug(item["name"])

        if progress:
            progress.on_resource_item("environments", env_key)

        connection_id = item.get("connection_id")
        connection_key = _find_connection_key(connections, connection_id)
        credential_data = item.get("credentials") or item.get("credential") or {}
        credential = Credential(
            token_name=credential_data.get("token_name", ""),
            schema=credential_data.get("schema", ""),
            catalog=credential_data.get("catalog"),
        )
        count += 1
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
    if progress:
        progress.on_resource_done("environments", count)


def _fetch_jobs(
    client: DbtCloudClient,
    project_id: int,
    environments: list,
    progress: Optional[FetchProgressCallback] = None,
) -> Iterable[Job]:
    log.info("Fetching jobs for project %s", project_id)
    if progress:
        progress.on_resource_start("jobs")
    # Build a mapping of environment_id -> environment_key
    env_id_to_key = {env.id: env.key for env in environments if env.id}

    count = 0
    params = {"project_id": project_id, "order_by": "id"}
    for item in client.paginate("/jobs/", params=params):
        job_key = slug(item["name"])

        if progress:
            progress.on_resource_item("jobs", job_key)

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

        count += 1
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
    if progress:
        progress.on_resource_done("jobs", count)


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


def _fetch_environment_variables(
    client: DbtCloudClient,
    project_id: int,
    progress: Optional[FetchProgressCallback] = None,
) -> Iterable[EnvironmentVariable]:
    """Fetch project-scoped environment variables (v3)."""
    log.info("Fetching environment variables for project %s (v3)", project_id)
    if progress:
        progress.on_resource_start("environment_variables")
    path = f"/projects/{project_id}/environment-variables/environment/"
    count = 0
    try:
        # This endpoint doesn't paginate - it returns all variables at once
        response = client.get(path, version="v3")

        # The response structure is: {'status': {...}, 'data': {'environments': [...], 'variables': {...}}}
        data = response.get("data", {})
        variables = data.get("variables", {})

        # variables is a dict like: {'VAR_NAME': {'project': {...}, 'EnvName': {...}, ...}}
        for var_name, env_values in variables.items():
            if progress:
                progress.on_resource_item("environment_variables", var_name)

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
            count += 1
            yield EnvironmentVariable(
                name=var_name,
                project_default=project_default,
                environment_values=environment_values
            )
    except Exception as exc:  # pragma: no cover - network dependent
        log.warning("Failed to fetch environment variables for project %s: %s", project_id, exc)
    if progress:
        progress.on_resource_done("environment_variables", count)


def _find_connection_key(connections: Dict[str, Connection], connection_id: int | None) -> str:
    if connection_id is None:
        return "connection_unknown"
    for connection in connections.values():
        if connection.id == connection_id:
            return connection.key
    return f"connection_{connection_id}"


