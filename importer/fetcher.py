"""Functions to fetch dbt Cloud account data into the internal model."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple, TypeVar, runtime_checkable

from slugify import slugify

from .client import DbtCloudClient
from .config import Settings
from .models import (
    AccountFeatures,
    AccountSnapshot,
    Connection,
    Credential,
    Environment,
    EnvironmentVariable,
    ExtendedAttributes,
    Globals,
    Group,
    IpRestrictionsRule,
    Job,
    LineageIntegration,
    Notification,
    OAuthConfiguration,
    PrivateLinkEndpoint,
    Project,
    Repository,
    SemanticLayerConfiguration,
    ServiceToken,
    UserGroups,
    WebhookSubscription,
)

log = logging.getLogger(__name__)

# Types for retry decorator
F = TypeVar("F", bound=Callable[..., Any])

# Transient network errors that should trigger retry
TRANSIENT_ERRORS: Tuple[type, ...] = (OSError, ConnectionError, TimeoutError)
def _safe_credential_error_summary(exc: Exception) -> str:
    """Return a concise credential fetch error summary for debug logs."""
    text = str(exc).strip()
    if len(text) > 400:
        return text[:400] + "..."
    return text


def with_retry(max_retries: int = 3, backoff: float = 1.0) -> Callable[[F], F]:
    """Decorator to add retry logic for transient network errors.
    
    Args:
        max_retries: Maximum number of attempts (default 3)
        backoff: Base backoff time in seconds, doubles each retry (default 1.0)
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Optional[Exception] = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except TRANSIENT_ERRORS as e:
                    last_exc = e
                    if attempt < max_retries - 1:
                        sleep_time = backoff * (2 ** attempt)
                        log.warning(
                            "Transient error in %s (attempt %d/%d): %s. Retrying in %.1fs...",
                            fn.__name__, attempt + 1, max_retries, e, sleep_time
                        )
                        time.sleep(sleep_time)
            log.error("All %d retries failed for %s: %s", max_retries, fn.__name__, last_exc)
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


class FetchCancelledException(Exception):
    """Raised when a fetch operation is cancelled by the user."""

    pass


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
    threads: int = 50,
    cancel_event: Optional[threading.Event] = None,
) -> AccountSnapshot:
    """
    Fetch a complete account snapshot from dbt Cloud.

    Args:
        client: The dbt Cloud API client.
        progress: Optional callback for progress reporting.
        threads: Number of concurrent threads for parallel fetching.
        cancel_event: Optional threading.Event to signal cancellation.

    Returns:
        An AccountSnapshot containing all fetched resources.

    Raises:
        FetchCancelledException: If the cancel_event is set during fetch.
    """

    _repo_root = Path(__file__).resolve().parent.parent
    _DEBUG_LOG = _repo_root / ".cursor" / "debug.log"
    _DEBUG_FALLBACK = _repo_root / "dev_support" / "debug.log"
    _DEBUG_TMP = Path("/tmp/terraform_dbtcloud_fetch_debug.log")

    def _check_cancelled():
        """Check if cancellation was requested and raise if so."""
        if cancel_event and cancel_event.is_set():
            _payload = json.dumps({
                "location": "fetcher:_check_cancelled",
                "message": "raising FetchCancelledException because cancel_event.is_set()",
                "event_is_set": cancel_event.is_set(),
                "event_id": id(cancel_event),
                "timestamp": time.time(),
            }) + "\n"
            for _path in (_DEBUG_LOG, _DEBUG_FALLBACK, _DEBUG_TMP):
                try:
                    if _path.parent != Path("/tmp"):
                        _path.parent.mkdir(parents=True, exist_ok=True)
                    _path.open("a").write(_payload)
                    break
                except Exception:
                    continue
            log.info("Fetch cancelled by user")
            raise FetchCancelledException("Fetch operation was cancelled by the user")

    log.info("Fetching dbt Cloud account snapshot ...")

    # Check for cancellation at start
    _check_cancelled()

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
        ("account_features", _fetch_account_features),
        ("ip_restrictions", _fetch_ip_restrictions),
        ("oauth_configurations", _fetch_oauth_configurations),
        ("user_groups", _fetch_user_groups),
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
            account_features=globals_results.get("account_features"),
            ip_restrictions=globals_results.get("ip_restrictions", {}),
            oauth_configurations=globals_results.get("oauth_configurations", {}),
            user_groups=globals_results.get("user_groups", {}),
        )

    # Check for cancellation after globals phase
    _check_cancelled()

    # Phase 2: Projects
    if progress:
        progress.on_phase("projects")

        progress.on_resource_start("projects")

    # Fetch projects list once (sequential) so we can display totals / submit work
    project_items = list(client.paginate("/projects/"))
    total_projects = len(project_items)
    # Flat, non-nested concurrency to avoid deadlocks: submit env/jobs/envvars tasks per project,
    # then submit overrides tasks for all jobs, then assemble.
    # All fetch functions include retry logic for transient network errors.
    
    def _fetch_with_retry(
        fn_name: str,
        fetch_fn: Callable[[], Any],
        max_retries: int = 3,
        backoff: float = 1.0,
    ) -> Any:
        """Execute a fetch function with retry logic for transient errors."""
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            # Check cancellation before each attempt so we don't keep
            # retrying after the user clicked Cancel
            _check_cancelled()
            try:
                return fetch_fn()
            except TRANSIENT_ERRORS as e:
                last_exc = e
                if attempt < max_retries - 1:
                    sleep_time = backoff * (2 ** attempt)
                    log.warning(
                        "Transient error in %s (attempt %d/%d): %s. Retrying in %.1fs...",
                        fn_name, attempt + 1, max_retries, e, sleep_time
                    )
                    # Sleep in small increments so cancellation is responsive
                    _sleep_end = time.time() + sleep_time
                    while time.time() < _sleep_end:
                        _check_cancelled()
                        time.sleep(min(0.25, _sleep_end - time.time()))
        log.error("All %d retries failed for %s: %s", max_retries, fn_name, last_exc)
        raise last_exc  # type: ignore[misc]

    def _fetch_project_environments_raw(project_id: int) -> list[dict[str, Any]]:
        def _do_fetch() -> list[dict[str, Any]]:
            c = DbtCloudClient.from_settings(settings)
            try:
                return list(c.paginate("/environments/", params={"project_id": project_id}))
            finally:
                c.close()
        return _fetch_with_retry(f"environments(project={project_id})", _do_fetch)

    def _fetch_project_jobs_raw(project_id: int) -> list[dict[str, Any]]:
        def _do_fetch() -> list[dict[str, Any]]:
            c = DbtCloudClient.from_settings(settings)
            try:
                return list(c.paginate("/jobs/", params={"project_id": project_id, "order_by": "id"}))
            finally:
                c.close()
        return _fetch_with_retry(f"jobs(project={project_id})", _do_fetch)

    def _fetch_project_env_vars_raw(project_id: int) -> dict[str, Any]:
        def _do_fetch() -> dict[str, Any]:
            c = DbtCloudClient.from_settings(settings)
            try:
                path = f"/projects/{project_id}/environment-variables/environment/"
                return c.get(path, version="v3").get("data", {}) or {}
            finally:
                c.close()
        return _fetch_with_retry(f"env_vars(project={project_id})", _do_fetch)

    def _fetch_job_overrides_raw(project_id: int, job_id: int) -> dict[str, Any]:
        def _do_fetch() -> dict[str, Any]:
            c = DbtCloudClient.from_settings(settings)
            try:
                path = f"/projects/{project_id}/environment-variables/job/"
                return c.get(path, version="v3", params={"job_definition_id": job_id}).get("data", {}) or {}
            finally:
                c.close()
        return _fetch_with_retry(f"job_overrides(project={project_id}, job={job_id})", _do_fetch)

    def _fetch_extended_attributes_raw(
        project_id: int,
        extended_attributes_id: int,
    ) -> dict[str, Any] | None:
        """Fetch a single extended attributes resource by project and id (v3 API)."""
        def _do_fetch() -> dict[str, Any] | None:
            if not extended_attributes_id or extended_attributes_id == 0:
                return None
            c = DbtCloudClient.from_settings(settings)
            try:
                path = f"/projects/{project_id}/extended-attributes/{extended_attributes_id}/"
                resp = c.get(path, version="v3")
                data = resp.get("data")
                if isinstance(data, dict):
                    return data
                return None
            except Exception as exc:
                log.warning(
                    "Failed to fetch extended attributes project=%s id=%s: %s",
                    project_id,
                    extended_attributes_id,
                    exc,
                )
                return None
            finally:
                c.close()
        return _fetch_with_retry(
            f"extended_attributes(project={project_id}, id={extended_attributes_id})",
            _do_fetch,
        )

    def _fetch_credential_details_raw(
        project_id: int,
        credential_id: int,
        connection_type: Optional[str],
    ) -> dict[str, Any]:
        """Fetch credential details with retry logic."""
        def _do_fetch() -> dict[str, Any]:
            if not credential_id or credential_id == 0:
                return {}
            c = DbtCloudClient.from_settings(settings)
            try:
                path = f"/projects/{project_id}/credentials/{credential_id}/"
                response = c.get(path, version="v3")
                data = response.get("data", {})
                if data:
                    api_type = data.get("type")
                    if api_type == "adapter":
                        adapter_version = data.get("adapter_version", "")
                        if adapter_version:
                            cred_type = adapter_version.rsplit("_v", 1)[0]
                        else:
                            cred_type = connection_type
                    else:
                        cred_type = api_type
                    data["credential_type"] = cred_type
                    return data
                return {"credential_type": connection_type}
            except Exception as e:
                log.warning(f"Failed to fetch credential {credential_id}: {e}")
                with credential_fetch_warning_lock:
                    credential_fetch_warnings.append(
                        {
                            "warning_type": "credential_detail_fetch_failed",
                            "project_id": project_id,
                            "credential_id": credential_id,
                            "connection_type": connection_type,
                            "path": f"/projects/{project_id}/credentials/{credential_id}/",
                            "error_summary": _safe_credential_error_summary(e),
                        }
                    )
                return {"credential_type": connection_type}
            finally:
                c.close()
        return _fetch_with_retry(f"credential(project={project_id}, cred={credential_id})", _do_fetch)

    # Submit all work and assemble projects as they become ready, so the UI can
    # show incremental project/env/job progress even when fetch is parallel.
    env_raw_by_project: dict[int, list[dict[str, Any]]] = {}
    jobs_raw_by_project: dict[int, list[dict[str, Any]]] = {}
    envvars_raw_by_project: dict[int, dict[str, Any]] = {}
    overrides_raw_by_job: dict[tuple[int, int], dict[str, Any]] = {}
    # Credentials keyed by (project_id, credential_id)
    credentials_raw_by_cred: dict[tuple[int, int], dict[str, Any]] = {}
    credential_fetch_warnings: list[dict[str, Any]] = []
    credential_fetch_warning_lock = threading.Lock()
    credential_context_by_cred: dict[tuple[int, int], dict[str, Any]] = {}

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
        progress.on_resource_start("extended_attributes")
        progress.on_resource_start("credentials")
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
            project_done_flags[project_id] = {
                "env": False, "jobs": False, "envvars": False,
                "overrides": 0, "overrides_done": 0,
                "creds": 0, "creds_done": 0,
            }

            pending[ex.submit(_fetch_project_environments_raw, project_id)] = ("env", project_id, None)
            pending[ex.submit(_fetch_project_jobs_raw, project_id)] = ("jobs", project_id, None)
            pending[ex.submit(_fetch_project_env_vars_raw, project_id)] = ("envvars", project_id, None)

        # Project tasks submitted (no-op marker kept intentionally blank)

        completed_projects = 0
        env_total = 0
        extended_attributes_total = 0
        creds_total = 0
        jobs_total = 0
        envvars_total = 0
        overrides_total = 0
        overrides_done = 0
        assembled_by_id: set[int] = set()
        projects: list[Project] = []

        while pending:
            # Check for cancellation at start of each iteration
            _check_cancelled()

            for fut in as_completed(list(pending.keys()), timeout=None):
                # Check cancellation between each future completion so we
                # don't keep processing hundreds of job-override results
                # after the user clicks Cancel.
                try:
                    _check_cancelled()
                except FetchCancelledException:
                    # Cancel any futures that haven't started yet
                    for p_fut in list(pending.keys()):
                        p_fut.cancel()
                    pending.clear()
                    raise

                kind, pid, job_id = pending.pop(fut)
                
                # Handle task completion with error resilience
                # job_id is reused for credential_id when kind == "cred"
                aux_id = job_id  # This is job_id for "override" or credential_id for "cred"
                try:
                    result = fut.result()
                except Exception as e:
                    if kind == "override":
                        # Job overrides are non-critical - log warning and continue
                        log.warning(
                            "Failed to fetch job override for project=%s job=%s: %s (continuing without overrides)",
                            pid, aux_id, e
                        )
                        # Use empty dict as fallback and mark as done
                        overrides_raw_by_job[(pid, int(aux_id or 0))] = {}
                        project_done_flags[pid]["overrides_done"] += 1
                        overrides_done += 1
                        if progress:
                            progress.on_resource_item("job_env_var_overrides", f"{pid}")
                        continue
                    elif kind == "cred":
                        # Credentials are non-critical - log warning and continue
                        log.warning(
                            "Failed to fetch credential for project=%s cred=%s: %s (continuing without credential details)",
                            pid, aux_id, e
                        )
                        context = credential_context_by_cred.get((pid, int(aux_id or 0)), {})
                        with credential_fetch_warning_lock:
                            credential_fetch_warnings.append(
                                {
                                    "warning_type": "credential_detail_fetch_future_failed",
                                    "project_id": pid,
                                    "credential_id": int(aux_id or 0),
                                    "environment_id": context.get("environment_id"),
                                    "environment_name": context.get("environment_name"),
                                    "error_summary": _safe_credential_error_summary(e),
                                }
                            )
                        # Use empty dict as fallback and mark as done
                        credentials_raw_by_cred[(pid, int(aux_id or 0))] = {}
                        project_done_flags[pid]["creds_done"] += 1
                        creds_total += 1
                        if progress:
                            progress.on_resource_item("credentials", f"{aux_id}")
                        continue
                    else:
                        # Critical resources (env, jobs, envvars) - log and re-raise
                        log.error(
                            "Failed to fetch %s for project=%s (project_name=%s): %s",
                            kind, pid, project_name_by_id.get(pid, "unknown"), e
                        )
                        raise

                if kind == "env":
                    env_raw_by_project[pid] = result
                    project_done_flags[pid]["env"] = True
                    if progress:
                        env_total += len(result)
                        for _ in range(len(result)):
                            progress.on_resource_item("environments", f"{pid}")
                    # Submit credential fetch tasks for each environment with credentials_id
                    for env_item in result:
                        cred_id = _extract_environment_credential_id(env_item)
                        if cred_id and isinstance(cred_id, int) and cred_id != 0:
                            # Get connection_type for this environment's connection
                            conn_id = env_item.get("connection_id")
                            conn_type = _get_connection_type(globals_model.connections, conn_id)
                            cred_key = (pid, cred_id)
                            if cred_key not in credential_context_by_cred:
                                credential_context_by_cred[cred_key] = {
                                    "environment_id": env_item.get("id"),
                                    "environment_name": env_item.get("name"),
                                    "project_id": pid,
                                }
                            project_done_flags[pid]["creds"] += 1
                            pending[ex.submit(_fetch_credential_details_raw, pid, cred_id, conn_type)] = ("cred", pid, cred_id)
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
                    overrides_raw_by_job[(pid, int(aux_id or 0))] = result if isinstance(result, dict) else {}
                    project_done_flags[pid]["overrides_done"] += 1
                    overrides_done += 1
                    if progress:
                        progress.on_resource_item("job_env_var_overrides", f"{pid}")
                elif kind == "cred":
                    credentials_raw_by_cred[(pid, int(aux_id or 0))] = result if isinstance(result, dict) else {}
                    project_done_flags[pid]["creds_done"] += 1
                    creds_total += 1
                    context = credential_context_by_cred.get((pid, int(aux_id or 0)), {})
                    if isinstance(result, dict) and result.get("id") is None and result.get("credential_type") is not None:
                        with credential_fetch_warning_lock:
                            credential_fetch_warnings.append(
                                {
                                    "warning_type": "credential_detail_fallback_only",
                                    "project_id": pid,
                                    "credential_id": int(aux_id or 0),
                                    "environment_id": context.get("environment_id"),
                                    "environment_name": context.get("environment_name"),
                                    "result_keys": sorted(list(result.keys())),
                                }
                            )
                    if progress:
                        progress.on_resource_item("credentials", f"{aux_id}")

                # If this project is fully ready and not yet assembled, assemble it now.
                flags = project_done_flags[pid]
                if (
                    pid not in assembled_by_id
                    and flags["env"]
                    and flags["jobs"]
                    and flags["envvars"]
                    and flags["overrides_done"] >= flags["overrides"]
                    and flags["creds_done"] >= flags["creds"]
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
                        docs_job_id=item.get("docs_job_id") or None,
                        freshness_job_id=item.get("freshness_job_id") or None,
                        metadata=item,
                    )
                    project_id = int(project.id or 0)

                    # Extended attributes: collect unique IDs from environments and fetch in parallel
                    env_items = env_raw_by_project.get(project_id, [])
                    ext_attr_ids = set()
                    for env_item in env_items:
                        eid = env_item.get("extended_attributes_id")
                        if isinstance(eid, int) and eid != 0:
                            ext_attr_ids.add(eid)
                    extended_attributes_list: list[ExtendedAttributes] = []
                    ext_attr_id_to_key: dict[int, str] = {}
                    if ext_attr_ids:
                        # Fetch all extended attributes in parallel
                        ext_raw_by_id: dict[int, dict] = {}
                        with ThreadPoolExecutor(max_workers=min(len(ext_attr_ids), 20)) as ext_ex:
                            ext_futures = {
                                ext_ex.submit(_fetch_extended_attributes_raw, project_id, eid): eid
                                for eid in sorted(ext_attr_ids)
                            }
                            for ext_fut in as_completed(ext_futures):
                                eid = ext_futures[ext_fut]
                                raw = ext_fut.result()
                                if raw:
                                    ext_raw_by_id[eid] = raw
                        # Assemble in sorted order for deterministic output
                        for eid in sorted(ext_raw_by_id.keys()):
                            raw = ext_raw_by_id[eid]
                            if progress:
                                extended_attributes_total += 1
                                progress.on_resource_item("extended_attributes", f"{project_id}_{eid}")
                            ext_key = f"ext_attrs_{eid}"
                            ext_attr_id_to_key[eid] = ext_key
                            # API may return extended_attributes as JSON string or dict
                            ext_attrs_val = raw.get("extended_attributes")
                            if isinstance(ext_attrs_val, str):
                                try:
                                    ext_attrs_dict = json.loads(ext_attrs_val)
                                except Exception:
                                    ext_attrs_dict = {}
                            elif isinstance(ext_attrs_val, dict):
                                ext_attrs_dict = ext_attrs_val
                            else:
                                ext_attrs_dict = {}
                            extended_attributes_list.append(
                                ExtendedAttributes(
                                    key=ext_key,
                                    id=raw.get("id") or eid,
                                    project_id=raw.get("project_id") or project_id,
                                    state=raw.get("state", 1),
                                    extended_attributes=ext_attrs_dict,
                                    metadata=raw,
                                )
                            )
                    project.extended_attributes = extended_attributes_list

                    # Environments
                    environments: list[Environment] = []
                    for env_item in env_items:
                        env_key = slug(env_item["name"])
                        connection_id = env_item.get("connection_id")
                        connection_key = _find_connection_key(globals_model.connections, connection_id)
                        connection_type = _get_connection_type(globals_model.connections, connection_id)
                        
                        # Look up pre-fetched credential details
                        credentials_id = _extract_environment_credential_id(env_item)
                        credential_details: dict[str, Any] = {}
                        if credentials_id:
                            # Credentials were fetched in parallel when environments were received
                            credential_details = credentials_raw_by_cred.get((project_id, credentials_id), {})
                        
                        # Build credential with all available details
                        credential = _build_credential_from_api_data(
                            env_item, credential_details, connection_type
                        )

                        ext_attr_id = env_item.get("extended_attributes_id")
                        ext_attr_key = ext_attr_id_to_key.get(ext_attr_id) if isinstance(ext_attr_id, int) else None
                        
                        environments.append(
                            Environment(
                                key=env_key,
                                id=env_item.get("id"),
                                name=env_item["name"],
                                type=env_item.get("type", "development"),
                                connection_key=connection_key,
                                connection_id=connection_id,  # Store original API connection ID
                                credential=credential,
                                extended_attributes_key=ext_attr_key,
                                extended_attributes_id=ext_attr_id if isinstance(ext_attr_id, int) and ext_attr_id else None,
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

                    project.lineage_integrations = list(
                        _fetch_lineage_integrations(client, project_id, progress=None)
                    )
                    project.semantic_layer_config = _fetch_semantic_layer_config(
                        client, project_id, progress=None
                    )

                    projects.append(project)
                    if progress:
                        progress.on_project_done(completed_projects)

                # Exit inner loop early if we haven't assembled everything yet; continue outer while
                if not pending:
                    break

        # Mark these resources done after all projects completed
        if progress:
            progress.on_resource_done("environments", env_total)
            progress.on_resource_done("extended_attributes", extended_attributes_total)
            progress.on_resource_done("credentials", creds_total)
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
        fetch_warnings=credential_fetch_warnings,
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
    
    # First, list all connections to get IDs (list endpoint doesn't return full config)
    connection_list = list(client.paginate("/connections/", version="v3"))
    log.info(f"Found {len(connection_list)} connections, fetching detailed config in parallel")

    # Fetch detailed config for each connection in parallel using per-thread clients
    settings = client.settings

    def _fetch_detail(item: dict) -> dict:
        """Fetch detailed connection config with a dedicated client (thread-safe)."""
        conn_id = item.get("id")
        c = DbtCloudClient.from_settings(settings)
        try:
            detailed = c.get(
                f"/connections/{conn_id}/",
                version="v3",
                params={"include_related": '["connection_details"]'}
            )
            if detailed.get("data"):
                return {**item, **detailed["data"]}
        except Exception as e:
            log.warning(f"Failed to fetch details for connection {conn_id}: {e}")
        finally:
            c.close()
        return item

    # Run detail fetches in parallel (bounded by number of connections, max 50)
    detail_workers = min(len(connection_list), 50)
    if detail_workers > 0:
        with ThreadPoolExecutor(max_workers=detail_workers) as detail_ex:
            future_to_item = {
                detail_ex.submit(_fetch_detail, item): item
                for item in connection_list
            }
            for fut in as_completed(future_to_item):
                item = fut.result()
                conn_id = item.get("id")
                key = item.get("name") or f"connection_{conn_id}"
                connection_key = slug(key)

                if progress:
                    progress.on_resource_item("connections", connection_key)

                # Extract connection type: prefer API 'type' field, fall back to adapter_version
                conn_type = item.get("type")
                adapter_version = item.get("adapter_version")

                if not conn_type and adapter_version:
                    conn_type = _extract_connection_type_from_adapter_version(adapter_version)
                    if conn_type:
                        log.debug(f"Derived connection type '{conn_type}' from adapter_version '{adapter_version}' for connection {connection_key}")
                    else:
                        log.warning(f"Could not extract connection type from adapter_version '{adapter_version}' for connection {connection_key}")
                
                conn_details = item.get("connection_details")
                if conn_details:
                    config = conn_details.get("config") if isinstance(conn_details, dict) else None
                    log.debug(f"Connection {connection_key} connection_details: keys={list(conn_details.keys()) if isinstance(conn_details, dict) else 'non-dict'}, config={config}")

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

    # First pass: list all repositories
    repo_items = list(client.paginate("/repositories/"))
    log.info(f"Found {len(repo_items)} repositories")
    repo_keys = [slug(item.get("name") or item.get("remote_url", "repo")) for item in repo_items]
    key_counts: dict[str, int] = {}
    for key in repo_keys:
        key_counts[key] = key_counts.get(key, 0) + 1

    # Identify repos that need v3 detail fetches
    settings = client.settings
    needs_detail: list[dict] = []
    for item in repo_items:
        git_clone_strategy = item.get("git_clone_strategy")
        if (
            git_clone_strategy == "deploy_token"
            or item.get("remote_backend") == "gitlab"
            or git_clone_strategy == "github_app"
        ):
            repo_id = item.get("id")
            project_id = item.get("project_id")
            if repo_id and project_id:
                needs_detail.append(item)

    # Fetch v3 details in parallel for repos that need it
    detail_results: dict[int, dict] = {}  # repo_id -> detailed data
    if needs_detail:
        log.info(f"Fetching v3 details for {len(needs_detail)} repositories in parallel")

        def _fetch_repo_detail(item: dict) -> tuple[int, Optional[dict]]:
            repo_id = item["id"]
            project_id = item["project_id"]
            repo_key = slug(item.get("name") or item.get("remote_url", "repo"))
            c = DbtCloudClient.from_settings(settings)
            try:
                detailed = c.get(
                    f"/projects/{project_id}/repositories/{repo_id}/",
                    version="v3",
                    params={"include_related": '["deploy_key","gitlab"]'},
                )
                if detailed and detailed.get("data"):
                    return (repo_id, detailed["data"])
            except Exception as exc:
                log.warning(f"Failed to fetch detailed repository info for {repo_key}: {exc}")
            finally:
                c.close()
            return (repo_id, None)

        with ThreadPoolExecutor(max_workers=min(len(needs_detail), 20)) as detail_ex:
            for repo_id, data in detail_ex.map(_fetch_repo_detail, needs_detail):
                if data:
                    detail_results[repo_id] = data

    # Assemble Repository objects
    for item in repo_items:
        name = item.get("remote_url", "repo")
        repo_id = item.get("id")
        base_repo_key = slug(item.get("name") or name)
        repo_key = base_repo_key
        if key_counts.get(base_repo_key, 0) > 1 and repo_id is not None:
            repo_key = f"{base_repo_key}_{repo_id}"

        if progress:
            progress.on_resource_item("repositories", repo_key)

        metadata = item.copy()
        repo_id = item.get("id")

        # Merge in v3 detail data if available
        if repo_id in detail_results:
            repo_data = detail_results[repo_id]
            if repo_data.get("gitlab"):
                metadata["gitlab"] = repo_data["gitlab"]
                gitlab_project_id = repo_data["gitlab"].get("gitlab_project_id")
                if gitlab_project_id:
                    metadata["gitlab_project_id"] = gitlab_project_id
                    log.info(f"Found gitlab_project_id={gitlab_project_id} for {repo_key}")
            github_installation_id = repo_data.get("github_installation_id")
            if github_installation_id:
                metadata["github_installation_id"] = github_installation_id
                log.info(f"Found github_installation_id={github_installation_id} for {repo_key}")

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


def _fetch_account_features(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Optional[AccountFeatures]:
    """Fetch account feature flags (private API). Returns None if unavailable."""
    log.info("Fetching account features (private API)")
    if progress:
        progress.on_resource_start("account_features")
    try:
        resp = client.get(f"/private/accounts/{client.settings.account_id}/features/")
        data = resp.get("data", resp) if isinstance(resp, dict) else {}
        features = AccountFeatures(
            advanced_ci=data.get("advanced_ci"),
            partial_parsing=data.get("partial_parsing"),
            repo_caching=data.get("repo_caching"),
            metadata=data if isinstance(data, dict) else {},
        )
        if progress:
            progress.on_resource_done("account_features", 1)
        return features
    except Exception as exc:
        log.warning("Failed to fetch account features (private API may not be available): %s", exc)
        if progress:
            progress.on_resource_done("account_features", 0)
        return None


def _fetch_ip_restrictions(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, IpRestrictionsRule]:
    """Fetch IP restriction rules (v3)."""
    log.info("Fetching IP restrictions (v3)")
    if progress:
        progress.on_resource_start("ip_restrictions")
    rules: Dict[str, IpRestrictionsRule] = {}
    try:
        for item in client.paginate("/ip-restrictions/", version="v3"):
            rule_name = item.get("name") or f"ip_rule_{item.get('id', 'unknown')}"
            key = slug(rule_name)

            if progress:
                progress.on_resource_item("ip_restrictions", key)

            rules[key] = IpRestrictionsRule(
                key=key,
                id=item.get("id"),
                name=rule_name,
                type=item.get("type"),
                description=item.get("description"),
                rule_set_enabled=item.get("rule_set_enabled"),
                cidrs=item.get("cidrs", []),
                metadata=item,
            )
    except Exception as exc:
        log.warning("Failed to fetch IP restrictions: %s", exc)
    if progress:
        progress.on_resource_done("ip_restrictions", len(rules))
    return rules


def _fetch_oauth_configurations(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, OAuthConfiguration]:
    """Fetch OAuth configurations (v3). Sensitive fields are not returned by API."""
    log.info("Fetching OAuth configurations (v3)")
    if progress:
        progress.on_resource_start("oauth_configurations")
    configs: Dict[str, OAuthConfiguration] = {}
    try:
        for item in client.paginate("/oauth-configurations/", version="v3"):
            config_name = item.get("name") or item.get("type") or f"oauth_{item.get('id', 'unknown')}"
            key = slug(config_name)

            if progress:
                progress.on_resource_item("oauth_configurations", key)

            configs[key] = OAuthConfiguration(
                key=key,
                id=item.get("id"),
                name=config_name,
                type=item.get("type"),
                client_id=item.get("client_id"),
                authorize_url=item.get("authorize_url"),
                token_url=item.get("token_url"),
                redirect_uri=item.get("redirect_uri"),
                metadata=item,
            )
    except Exception as exc:
        log.warning("Failed to fetch OAuth configurations: %s", exc)
    if progress:
        progress.on_resource_done("oauth_configurations", len(configs))
    return configs


def _fetch_user_groups(
    client: DbtCloudClient,
    progress: Optional[FetchProgressCallback] = None,
) -> Dict[str, UserGroups]:
    """Fetch users and their group assignments (v2)."""
    log.info("Fetching user group assignments (v2)")
    if progress:
        progress.on_resource_start("user_groups")
    user_groups: Dict[str, UserGroups] = {}
    try:
        for item in client.paginate("/users/"):
            user_id = item.get("id")
            email = item.get("email") or ""
            if not user_id:
                continue
            key = slug(email or f"user_{user_id}")

            if progress:
                progress.on_resource_item("user_groups", key)

            permissions = item.get("permissions", [])
            group_ids = sorted(set(
                p.get("group_id") for p in permissions
                if isinstance(p, dict) and p.get("group_id") is not None
            ))

            user_groups[key] = UserGroups(
                key=key,
                user_id=user_id,
                email=email,
                group_ids=group_ids,
                metadata=item,
            )
    except Exception as exc:
        log.warning("Failed to fetch user group assignments: %s", exc)
    if progress:
        progress.on_resource_done("user_groups", len(user_groups))
    return user_groups


def _fetch_lineage_integrations(
    client: DbtCloudClient,
    project_id: int,
    progress: Optional[FetchProgressCallback] = None,
) -> List[LineageIntegration]:
    """Fetch lineage integrations for a project (v3)."""
    integrations: List[LineageIntegration] = []
    try:
        for item in client.paginate(
            f"/projects/{project_id}/integrations/lineage/",
            version="v3",
        ):
            name = item.get("name") or item.get("host") or f"lineage_{item.get('id', 'unknown')}"
            key = slug(name)
            integrations.append(LineageIntegration(
                key=key,
                id=item.get("id"),
                name=name,
                host=item.get("host"),
                site_id=item.get("site_id"),
                token_name=item.get("token_name"),
                metadata=item,
            ))
    except Exception as exc:
        log.debug("No lineage integrations for project %s: %s", project_id, exc)
    return integrations


def _fetch_semantic_layer_config(
    client: DbtCloudClient,
    project_id: int,
    progress: Optional[FetchProgressCallback] = None,
) -> Optional[SemanticLayerConfiguration]:
    """Fetch semantic layer configuration for a project (v3). Singleton per project."""
    try:
        items = list(client.paginate(
            f"/projects/{project_id}/semantic-layer-configurations/",
            version="v3",
        ))
        if items:
            item = items[0]
            return SemanticLayerConfiguration(
                key=f"sl_config_{project_id}",
                id=item.get("id"),
                environment_id=item.get("environment_id"),
                metadata=item,
            )
    except Exception as exc:
        log.debug("No semantic layer config for project %s: %s", project_id, exc)
    return None


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
            docs_job_id=item.get("docs_job_id") or None,
            freshness_job_id=item.get("freshness_job_id") or None,
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
        project.lineage_integrations = list(
            _fetch_lineage_integrations(client, project_id, progress)
        )
        project.semantic_layer_config = _fetch_semantic_layer_config(
            client, project_id, progress
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
        connection_type = _get_connection_type(connections, connection_id)
        
        # Fetch detailed credential information if credentials_id is present
        credentials_id = _extract_environment_credential_id(item)
        credential_details: dict[str, Any] = {}
        if credentials_id:
            credential_details = _fetch_credential_details(
                client.settings, project_id, credentials_id, connection_type
            )
        
        # Build credential with all available details
        credential = _build_credential_from_api_data(
            item, credential_details, connection_type
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


def _get_connection_type(connections: Dict[str, Connection], connection_id: int | None) -> Optional[str]:
    """Get the connection type (adapter) for a given connection ID."""
    if connection_id is None:
        return None
    for connection in connections.values():
        if connection.id == connection_id:
            return connection.type
    return None


def _extract_environment_credential_id(env_item: dict[str, Any]) -> Optional[int]:
    """Resolve environment credential ID across API shape variations."""
    raw_candidates = [
        env_item.get("credentials_id"),
        env_item.get("credential_id"),
    ]

    nested_credential = env_item.get("credential")
    if isinstance(nested_credential, dict):
        raw_candidates.append(nested_credential.get("id"))

    nested_credentials = env_item.get("credentials")
    if isinstance(nested_credentials, dict):
        raw_candidates.append(nested_credentials.get("id"))

    for raw in raw_candidates:
        if isinstance(raw, int) and raw != 0:
            return raw
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped.isdigit():
                parsed = int(stripped)
                if parsed != 0:
                    return parsed
    return None


def _fetch_credential_details(
    settings: Settings,
    project_id: int,
    credential_id: int,
    connection_type: Optional[str],
) -> dict[str, Any]:
    """Fetch credential details from dbt Cloud API.
    
    Uses the v3 credentials API endpoint:
    GET /api/v3/accounts/{account_id}/projects/{project_id}/credentials/{credential_id}/
    
    Args:
        settings: API settings for creating client
        project_id: The project ID
        credential_id: The credential ID to fetch
        connection_type: The connection type (snowflake, databricks, etc.) - used as fallback
    
    Returns:
        Dict with credential details including 'credential_type', or empty dict on failure
    """
    if not credential_id or credential_id == 0:
        return {}
    
    log.info(f"Fetching credential {credential_id} for project {project_id}...")
    
    c = DbtCloudClient.from_settings(settings)
    try:
        # Use the standard credentials endpoint (no type in path)
        path = f"/projects/{project_id}/credentials/{credential_id}/"
        log.debug(f"Fetching credential details: {path}")
        
        response = c.get(path, version="v3")
        data = response.get("data", {})
        
        if data:
            # The API returns 'type' field with values like 'postgres', 'snowflake', 'bigquery', 'adapter'
            # Map to our credential_type field
            api_type = data.get("type")
            # For 'adapter' type, try to determine from adapter_version or fall back to connection_type
            if api_type == "adapter":
                adapter_version = data.get("adapter_version", "")
                # adapter_version looks like 'databricks_v0', 'athena_v0', etc.
                if adapter_version:
                    cred_type = adapter_version.rsplit("_v", 1)[0]  # 'databricks_v0' -> 'databricks'
                else:
                    cred_type = connection_type
            else:
                cred_type = api_type
            
            data["credential_type"] = cred_type
            log.info(f"Fetched credential {credential_id}: type={cred_type}, schema={data.get('default_schema')}, user={data.get('username')}")
            return data
        
        return {"credential_type": connection_type}
    except Exception as e:
        # Credential endpoint might not exist or require different permissions
        log.warning(f"Failed to fetch credential {credential_id}: {e}")
        return {"credential_type": connection_type}
    finally:
        c.close()


def _build_credential_from_api_data(
    env_item: dict[str, Any],
    credential_details: dict[str, Any],
    connection_type: Optional[str],
) -> Credential:
    """Build a Credential object from environment item and fetched credential details.
    
    Combines data from the environment API response with detailed credential data.
    
    API returns fields like:
    - type: 'postgres', 'redshift', 'snowflake', 'bigquery', 'adapter'
    - threads: int
    - username: str (for postgres/redshift)
    - default_schema: str
    - target_name: str
    - adapter_version: str (for adapter type, e.g. 'databricks_v0')
    """
    # Start with basic credential data from environment
    basic_cred = env_item.get("credentials") or env_item.get("credential") or {}
    credentials_id = _extract_environment_credential_id(env_item)
    if credentials_id is None:
        details_id = credential_details.get("id")
        if isinstance(details_id, int) and details_id != 0:
            credentials_id = details_id
    
    # Determine credential type
    cred_type = credential_details.get("credential_type") or connection_type
    
    # API uses 'threads' not 'num_threads', and 'default_schema' for schema
    schema = (
        credential_details.get("default_schema") or 
        credential_details.get("schema") or 
        basic_cred.get("schema", "")
    )
    
    # Build the credential with all available fields
    return Credential(
        # Core fields
        id=credentials_id,
        credential_type=cred_type,
        schema_name=schema,
        num_threads=credential_details.get("threads") or credential_details.get("num_threads"),
        is_active=credential_details.get("state", 1) == 1,  # state=1 means active
        
        # Snowflake-specific (user for snowflake, username for postgres/redshift)
        auth_type=credential_details.get("auth_type"),
        user=credential_details.get("user") or credential_details.get("username"),
        warehouse=credential_details.get("warehouse"),
        role=credential_details.get("role"),
        database=credential_details.get("database"),
        
        # Databricks-specific
        token_name=basic_cred.get("token_name") or credential_details.get("token_name", ""),
        catalog=basic_cred.get("catalog") or credential_details.get("catalog"),
        adapter_type=credential_details.get("adapter_version"),  # API uses adapter_version
        
        # BigQuery-specific
        dataset=credential_details.get("dataset"),
        
        # Postgres/Redshift-specific
        default_schema=credential_details.get("default_schema"),
        username=credential_details.get("username"),
        target_name=credential_details.get("target_name"),
        
        # Fabric/Synapse-specific
        tenant_id=credential_details.get("tenant_id"),
        client_id=credential_details.get("client_id"),
        schema_authorization=credential_details.get("schema_authorization"),
        authentication=credential_details.get("authentication"),
        
        # Store full API response for reference
        metadata=credential_details if credential_details else basic_cred,
    )


