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

    # First, register projects and build project_id -> mapping_id lookup
    project_id_to_mapping = {}
    project_key_to_mapping = {}
    for project in payload.get("projects", []):
        project_name = project.get("name") or project.get("key")
        project_mapping_id = _register(
            records,
            project,
            "PRJ",
            name=project_name,
            extra={
                "project_key": project.get("key"),
                "repository_key": project.get("repository_key"),
            },
        )
        
        # Track project mappings for repository linking
        if project.get("id"):
            project_id_to_mapping[project.get("id")] = project_mapping_id
        if project.get("key"):
            project_key_to_mapping[project.get("key")] = project_mapping_id

        # Extended attributes (EXTATTR) - project-scoped
        # #region agent log
        _eat_list = project.get("extended_attributes", [])
        if _eat_list or project.get("id") == 346697:
            try:
                import json, time
                _log_path = "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log"
                with open(_log_path, "a", encoding="utf-8") as _f:
                    _f.write(json.dumps({"timestamp": int(time.time() * 1000), "location": "element_ids.apply_element_ids", "message": "project extended_attributes", "data": {"project_id": project.get("id"), "project_key": project.get("key"), "extended_attributes_count": len(_eat_list), "extended_attributes_keys": [x.get("key") or x.get("id") for x in _eat_list]}, "hypothesisId": "B"}) + "\n")
            except Exception:
                pass
        # #endregion
        for eat in _eat_list:
            eat_key = eat.get("key") or f"ext_attrs_{eat.get('id', '')}"
            _register(
                records,
                eat,
                "EXTATTR",
                name=eat_key,
                identifier=eat.get("id"),
                extra={
                    "project_key": project.get("key"),
                    "project_name": project_name,
                    "parent_project_id": project_mapping_id,
                    "extended_attributes_key": eat_key,
                },
            )

        # Environment variables
        for var in project.get("environment_variables", []):
            variant = "secret" if str(var.get("name", "")).startswith("DBT_ENV_SECRET") else "regular"
            # Use project-scoped identifier so that same-named vars in different
            # projects get distinct element_mapping_ids (e.g. "bt_data_ops_db:DBT_ENVIRONMENT_NAME"
            # vs "sse_dm_fin_fido:DBT_ENVIRONMENT_NAME").
            var_project_key = project.get("key") or ""
            var_name = var.get("name") or ""
            _register(
                records,
                var,
                "VAR",
                name=var_name,
                identifier=f"{var_project_key}:{var_name}" if var_project_key else None,
                extra={
                    "project_key": var_project_key,
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
                    "connection_key": env.get("connection_key"),  # For hierarchy linking
                    "connection_id": env.get("connection_id"),  # For ID-based connection lookup
                },
            )
            
            # Credential as child of environment (if present)
            credential = env.get("credential")
            if credential and isinstance(credential, dict):
                cred_type = credential.get("credential_type") or "unknown"
                cred_id = credential.get("id")
                cred_schema = credential.get("schema") or credential.get("schema_name", "")
                cred_user = credential.get("user") or credential.get("username", "")
                
                # Build credential display name
                cred_name_parts = [cred_type]
                if cred_schema:
                    cred_name_parts.append(f"schema:{cred_schema}")
                if cred_user:
                    cred_name_parts.append(f"user:{cred_user}")
                cred_display_name = f"Credential ({', '.join(cred_name_parts)})"
                
                # Use a stable identifier based on environment
                cred_identifier = f"{env.get('key')}:credential:{cred_id or cred_type}"
                
                _register(
                    records,
                    credential,
                    "CRD",
                    name=cred_display_name,
                    identifier=cred_identifier,
                    extra={
                        "project_key": project.get("key"),
                        "project_name": project_name,
                        "environment_key": env.get("key"),
                        "environment_name": env.get("name"),
                        "parent_environment_id": env_mapping_id,
                        "parent_project_id": project_mapping_id,
                        "credential_type": cred_type,
                        "credential_schema": cred_schema,
                        "credential_user": cred_user,
                        "credential_id": cred_id,
                    },
                )

            # Jobs per environment
            env_key = env.get("key")
            for job in project.get("jobs", []):
                if job.get("environment_key") != env_key:
                    continue
                # Include environment_variable_overrides for derived resource counting
                env_var_overrides = job.get("environment_variable_overrides", {})
                # Include job_completion_trigger_condition for derived resource counting
                job_settings = job.get("settings", {})
                jctc = job_settings.get("job_completion_trigger_condition", {})
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
                        "environment_variable_overrides": env_var_overrides,
                        "job_completion_trigger_condition": jctc,
                    },
                )

    # Now register globals (after projects so we can link repositories)
    globals_block = payload.get("globals") or {}
    for key, label, code in (
        ("connections", "Connections", "CON"),
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
    
    # Register repositories with parent project linking
    repositories = globals_block.get("repositories") or {}
    for resource_key, resource in repositories.items():
        # Get project_id from metadata
        metadata = resource.get("metadata") or {}
        repo_project_id = metadata.get("project_id")
        
        # Find parent project mapping
        parent_project_mapping = None
        parent_project_name = None
        if repo_project_id and repo_project_id in project_id_to_mapping:
            parent_project_mapping = project_id_to_mapping[repo_project_id]
            # Look up project name from records
            for rec in records:
                if rec.get("element_mapping_id") == parent_project_mapping:
                    parent_project_name = rec.get("name")
                    break
        
        # Extract github_installation_id from metadata (fetched via v3 API)
        # See: https://docs.getdbt.com/dbt-cloud/api-v3#/operations/Retrieve%20Repository
        github_installation_id = metadata.get("github_installation_id")
        
        _register(
            records,
            resource,
            "REP",
            name=resource.get("name") or resource_key,
            extra={
                "resource_group": "Repositories",
                "parent_project_id": parent_project_mapping,
                "project_name": parent_project_name,
                "git_clone_strategy": resource.get("git_clone_strategy"),
                "remote_url": resource.get("remote_url"),
                "github_installation_id": github_installation_id,
            },
        )

    # Assign line numbers
    current = start_number
    for record in records:
        record["line_item_number"] = current
        current += 1

    return records

