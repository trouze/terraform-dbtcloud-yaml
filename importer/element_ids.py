"""Generate deterministic element IDs and line items for reports."""

from __future__ import annotations

from typing import Any, Dict, List

from .utils import short_hash


def _extract_state(data: Dict[str, Any]) -> Any:
    if "state" in data and data["state"] is not None:
        return data["state"]
    for key in ("metadata", "details"):
        block = data.get(key)
        if isinstance(block, dict) and block.get("state") is not None:
            return block.get("state")
    return None


def _is_inactive_state(state: Any) -> bool:
    if state is None:
        return False
    if isinstance(state, (int, float)):
        return int(state) in {0, 2}
    if isinstance(state, str):
        normalized = state.strip().lower()
        return normalized in {"inactive", "deleted", "soft_deleted", "disabled"}
    return False


def _register(
    records: List[Dict[str, Any]],
    data: Dict[str, Any],
    element_type_code: str,
    *,
    name: str | None = None,
    identifier: Any | None = None,
    extra: Dict[str, Any] | None = None,
) -> str:
    """Assign an element mapping ID to a resource and record it."""
    identifier_value = identifier or data.get("id") or data.get("name") or data.get("key")
    identifier_str = str(identifier_value or name or element_type_code)
    mapping_id = short_hash(f"{element_type_code}:{identifier_str}")
    data["element_mapping_id"] = mapping_id

    state = _extract_state(data)
    record = {
        "element_type_code": element_type_code,
        "element_mapping_id": mapping_id,
        "name": name or data.get("name") or data.get("key") or identifier_str,
        "dbt_id": data.get("id"),
        "key": data.get("key"),
        "state": state,
        "include_in_conversion": not _is_inactive_state(state),
    }
    if extra:
        record.update(extra)
    records.append(record)
    return mapping_id


def apply_element_ids(payload: Dict[str, Any], start_number: int = 1001) -> List[Dict[str, Any]]:
    """Inject element_mapping_id into the payload and produce line items."""
    records: List[Dict[str, Any]] = []

    account_name = payload.get("account_name") or f"Account {payload.get('account_id')}"
    _register(
        records,
        payload,
        "ACC",
        name=account_name,
        identifier=payload.get("account_id"),
    )

    globals_block = payload.get("globals") or {}
    for key, label, code in (
        ("connections", "Connections", "CON"),
        ("repositories", "Repositories", "REP"),
        ("service_tokens", "Service Tokens", "TOK"),
        ("groups", "Groups", "GRP"),
        ("notifications", "Notifications", "NOT"),
        ("webhooks", "Webhooks", "WEB"),
        ("privatelink_endpoints", "PrivateLink Endpoints", "PLE"),
    ):
        resources = globals_block.get(key) or {}
        for resource_key, resource in resources.items():
            _register(
                records,
                resource,
                code,
                name=resource.get("name") or resource_key,
                extra={"resource_group": label},
            )

    for project in payload.get("projects", []):
        project_name = project.get("name") or project.get("key")
        project_mapping_id = _register(
            records,
            project,
            "PRJ",
            name=project_name,
            extra={"project_key": project.get("key")},
        )

        # Environment variables
        for var in project.get("environment_variables", []):
            variant = "secret" if str(var.get("name", "")).startswith("DBT_ENV_SECRET") else "regular"
            _register(
                records,
                var,
                "VAR",
                name=var.get("name"),
                extra={
                    "project_key": project.get("key"),
                    "project_name": project_name,
                    "variant": variant,
                    "parent_project_id": project_mapping_id,
                },
            )

        # Environments
        for env in project.get("environments", []):
            env_mapping_id = _register(
                records,
                env,
                "ENV",
                name=env.get("name"),
                extra={
                    "project_key": project.get("key"),
                    "project_name": project_name,
                    "parent_project_id": project_mapping_id,
                },
            )

            # Jobs per environment
            env_key = env.get("key")
            for job in project.get("jobs", []):
                if job.get("environment_key") != env_key:
                    continue
                _register(
                    records,
                    job,
                    "JOB",
                    name=job.get("name"),
                    extra={
                        "project_key": project.get("key"),
                        "project_name": project_name,
                        "environment_key": env_key,
                        "environment_mapping_id": env_mapping_id,
                        "parent_project_id": project_mapping_id,
                    },
                )

    # Assign line numbers
    current = start_number
    for record in records:
        record["line_item_number"] = current
        current += 1

    return records

