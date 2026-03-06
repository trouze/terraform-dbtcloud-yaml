"""Generate deterministic element IDs and line items for reports."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from .utils import short_hash


def _dbg_25ac29(hypothesis_id: str, location: str, message: str, data: Dict[str, Any]) -> None:
    payload = {
        "sessionId": "25ac29",
        "runId": "post-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(
            "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-25ac29.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


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

    # Deduplicate project keys: multiple projects may share the same key
    # (e.g. three projects all named "Analytics" with key "analytics").
    # Apply the same suffix strategy the normalizer uses so that downstream
    # lookups in match_grid can distinguish them.
    _project_key_counts: Dict[str, int] = {}

    def _dedup_project_key(raw_key: str) -> str:
        if raw_key not in _project_key_counts:
            _project_key_counts[raw_key] = 1
            return raw_key
        _project_key_counts[raw_key] += 1
        return f"{raw_key}_{_project_key_counts[raw_key]}"

    # Sort projects by ID for deterministic dedup: lowest ID gets base key.
    # Fallback to (name, key) for projects without IDs.
    _raw_projects = payload.get("projects", [])
    _sorted_projects = sorted(
        _raw_projects,
        key=lambda p: (0, p.get("id") or 0, p.get("name", ""), p.get("key", ""))
        if p.get("id")
        else (1, 0, p.get("name", ""), p.get("key", "")),
    )

    # region agent log
    _colliding_keys: Dict[str, List[Any]] = {}
    for _p in _sorted_projects:
        _pk = _p.get("key", "")
        _colliding_keys.setdefault(_pk, []).append(_p.get("id"))
    _collisions = {k: v for k, v in _colliding_keys.items() if len(v) > 1}
    if _collisions:
        _dbg_25ac29(
            "H-DEDUP",
            "element_ids.py:apply_element_ids",
            "project dedup: sorted order for colliding keys",
            {"collisions": {k: [str(i) for i in v] for k, v in _collisions.items()}},
        )
    # endregion

    # First, register projects and build project_id -> mapping_id lookup
    project_id_to_mapping = {}
    project_key_to_mapping = {}
    for project in _sorted_projects:
        project_name = project.get("name") or project.get("key")
        raw_project_key = project.get("key") or ""
        _project_jobs = project.get("jobs", []) or []
        deduped_project_key = _dedup_project_key(raw_project_key)
        project_mapping_id = _register(
            records,
            project,
            "PRJ",
            name=project_name,
            extra={
                "project_key": deduped_project_key,
                "repository_key": project.get("repository_key"),
            },
        )
        
        # Track project mappings for repository linking
        if project.get("id"):
            project_id_to_mapping[project.get("id")] = project_mapping_id
        if deduped_project_key:
            project_key_to_mapping[deduped_project_key] = project_mapping_id

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
                    "project_key": deduped_project_key,
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
            var_name = var.get("name") or ""
            _register(
                records,
                var,
                "VAR",
                name=var_name,
                identifier=f"{deduped_project_key}:{var_name}" if deduped_project_key else None,
                extra={
                    "project_key": deduped_project_key,
                    "project_name": project_name,
                    "variant": variant,
                    "parent_project_id": project_mapping_id,
                },
            )

        # Environments
        project_job_total = len(project.get("jobs", []) or [])
        project_job_matched = 0
        project_job_skipped_env_mismatch = 0
        project_crd_total = 0
        project_crd_with_id = 0
        project_crd_skipped_null_id = 0
        for env in project.get("environments", []):
            env_mapping_id = _register(
                records,
                env,
                "ENV",
                name=env.get("name"),
                extra={
                    "project_key": deduped_project_key,
                    "project_name": project_name,
                    "parent_project_id": project_mapping_id,
                    "connection_key": env.get("connection_key"),  # For hierarchy linking
                    "connection_id": env.get("connection_id"),  # For ID-based connection lookup
                },
            )
            
            # Credential as child of environment (if present)
            credential = env.get("credential")
            if credential and isinstance(credential, dict):
                project_crd_total += 1
                cred_type = credential.get("credential_type") or "unknown"
                cred_id = credential.get("id") or env.get("credentials_id") or env.get("credential_id")
                if isinstance(cred_id, str):
                    stripped_cred_id = cred_id.strip()
                    cred_id = int(stripped_cred_id) if stripped_cred_id.isdigit() else None
                cred_schema = credential.get("schema") or credential.get("schema_name", "")
                cred_user = credential.get("user") or credential.get("username", "")
                # region agent log
                _dbg_25ac29(
                    "H26",
                    "element_ids.py:apply_element_ids:credential_row_build",
                    "resolved CRD identifier fields from environment and credential payload",
                    {
                        "project_key": deduped_project_key,
                        "raw_project_key": raw_project_key,
                        "environment_key": env.get("key"),
                        "environment_name": env.get("name"),
                        "credential_type": cred_type,
                        "credential_id_from_credential": credential.get("id"),
                        "credentials_id_from_env": env.get("credentials_id"),
                        "credential_id_from_env": env.get("credential_id"),
                        "resolved_credential_id": cred_id,
                    },
                )
                # endregion
                
                # Build credential display name
                cred_name_parts = [cred_type]
                if cred_schema:
                    cred_name_parts.append(f"schema:{cred_schema}")
                if cred_user:
                    cred_name_parts.append(f"user:{cred_user}")
                cred_display_name = f"Credential ({', '.join(cred_name_parts)})"
                
                # Scope by deduped project key so identical credentials in
                # different projects with the same display name get distinct IDs.
                cred_identifier = f"{deduped_project_key}:{env.get('key')}:credential:{cred_id or cred_type}"
                
                # Dev environment credentials have null IDs (user-specific, not
                # project-level). They can't be managed in Terraform, so skip them.
                if cred_id is None:
                    project_crd_skipped_null_id += 1
                else:
                    project_crd_with_id += 1

                    crd_extra: Dict[str, Any] = {
                        "dbt_id": cred_id,
                        "project_key": deduped_project_key,
                        "project_name": project_name,
                        "environment_key": env.get("key"),
                        "environment_name": env.get("name"),
                        "parent_environment_id": env_mapping_id,
                        "parent_project_id": project_mapping_id,
                        "credential_type": cred_type,
                        "credential_schema": cred_schema,
                        "credential_user": cred_user,
                        "credential_id": cred_id,
                    }
                    _register(
                        records,
                        credential,
                        "CRD",
                        name=cred_display_name,
                        identifier=cred_identifier,
                        extra=crd_extra,
                    )

            # Jobs per environment
            env_key = env.get("key")
            for job in project.get("jobs", []):
                if job.get("environment_key") != env_key:
                    project_job_skipped_env_mismatch += 1
                    continue
                project_job_matched += 1
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
                        "project_key": deduped_project_key,
                        "project_name": project_name,
                        "environment_key": env_key,
                        "environment_mapping_id": env_mapping_id,
                        "parent_project_id": project_mapping_id,
                        "environment_variable_overrides": env_var_overrides,
                        "job_completion_trigger_condition": jctc,
                    },
                )
        # Project Artefacts (PARFT) - derived from docs_job_id / freshness_job_id
        if project.get("docs_job_id") or project.get("freshness_job_id"):
            parft_data = {
                "docs_job_id": project.get("docs_job_id"),
                "freshness_job_id": project.get("freshness_job_id"),
            }
            _register(
                records,
                parft_data,
                "PARFT",
                name=f"{project_name} Artefacts",
                identifier=f"{deduped_project_key}:artefacts",
                extra={
                    "project_key": deduped_project_key,
                    "project_name": project_name,
                    "parent_project_id": project_mapping_id,
                },
            )

        # Lineage Integrations (LNGI) - per-project collection
        for lngi in project.get("lineage_integrations", []):
            _register(
                records,
                lngi,
                "LNGI",
                name=lngi.get("name") or f"Lineage Integration {lngi.get('id', '')}",
                extra={
                    "project_key": deduped_project_key,
                    "project_name": project_name,
                    "parent_project_id": project_mapping_id,
                },
            )

        # Semantic Layer Configuration (SLCFG) - per-project singleton
        sl_config = project.get("semantic_layer_config")
        if sl_config and isinstance(sl_config, dict):
            _register(
                records,
                sl_config,
                "SLCFG",
                name=f"{project_name} Semantic Layer Config",
                identifier=f"{deduped_project_key}:slcfg",
                extra={
                    "project_key": deduped_project_key,
                    "project_name": project_name,
                    "parent_project_id": project_mapping_id,
                },
            )

        # region agent log
        _dbg_25ac29(
            "H70",
            "element_ids.py:apply_element_ids:project_job_crd_summary",
            "summarized project-level JOB and CRD extraction decisions",
            {
                "project_id": project.get("id"),
                "project_name": project_name,
                "project_key_raw": raw_project_key,
                "project_key_deduped": deduped_project_key,
                "environments_count": len(project.get("environments", []) or []),
                "jobs_total_in_payload": project_job_total,
                "jobs_emitted": project_job_matched,
                "jobs_skipped_env_mismatch": project_job_skipped_env_mismatch,
                "credentials_total_in_payload": project_crd_total,
                "credentials_emitted_with_id": project_crd_with_id,
                "credentials_skipped_null_id": project_crd_skipped_null_id,
            },
        )
        # endregion

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
    
    # Register additional global resource types (S4-S6)
    for key, label, code in (
        ("ip_restrictions", "IP Restrictions", "IPRST"),
        ("oauth_configurations", "OAuth Configurations", "OAUTH"),
        ("user_groups", "User Groups", "USRGRP"),
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

    # Account features (singleton, not a dict collection)
    account_features = globals_block.get("account_features")
    if account_features and isinstance(account_features, dict):
        _register(
            records,
            account_features,
            "ACFT",
            name="Account Features",
            identifier=payload.get("account_id"),
            extra={"resource_group": "Account Features"},
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

    # region agent log
    missing_dbt_id_by_type: Dict[str, int] = {}
    counts_by_type: Dict[str, int] = {}
    for record in records:
        element_type = str(record.get("element_type_code", "UNK"))
        counts_by_type[element_type] = counts_by_type.get(element_type, 0) + 1
        if record.get("dbt_id") is None:
            missing_dbt_id_by_type[element_type] = missing_dbt_id_by_type.get(element_type, 0) + 1
    _dbg_25ac29(
        "H27",
        "element_ids.py:apply_element_ids:dbt_id_audit",
        "computed dbt_id coverage across generated report items",
        {
            "total_records": len(records),
            "counts_by_type": counts_by_type,
            "missing_dbt_id_by_type": missing_dbt_id_by_type,
        },
    )
    # endregion
    return records

