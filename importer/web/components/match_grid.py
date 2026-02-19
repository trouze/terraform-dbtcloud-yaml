"""Editable AG Grid component for resource matching."""

from dataclasses import dataclass
import json
import time
from typing import Callable, Optional, TYPE_CHECKING

from nicegui import ui

from importer.web.state import CloneConfig

if TYPE_CHECKING:
    from importer.web.utils.terraform_state_reader import StateReadResult
    from importer.web.utils.protection_intent import ProtectionIntentManager



# Colors
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"

# Display prefixes used for hierarchy visualization
DISPLAY_PREFIXES = ("    ↳ ", "  ↳ ")  # Double-indented first (longer match)


def _normalize_name_for_lookup(name: str) -> str:
    """Strip display prefixes from names for lookup purposes.
    
    Names like "  ↳ repo_name" are display-formatted for hierarchy visualization
    but need to be normalized to "repo_name" for matching against target names.
    """
    for prefix in DISPLAY_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


@dataclass
class GridRow:
    """A row in the mapping grid."""
    
    source_key: str
    source_name: str
    source_type: str
    source_id: Optional[int]
    action: str  # "match", "create_new", "skip"
    target_id: str  # String to allow empty/partial input
    target_name: str
    status: str  # "pending", "confirmed", "error", "skipped"
    confidence: str  # "exact_match", "fuzzy", "manual", "none"
    project_name: str = ""
    clone_configured: bool = False  # Whether clone config exists
    clone_name: str = ""  # Name for the clone (if configured)


# Drift status values
DRIFT_NO_STATE = "no_state"  # No Terraform state loaded
DRIFT_IN_SYNC = "in_sync"    # State ID matches target ID
DRIFT_ID_MISMATCH = "id_mismatch"  # State has different ID than target
DRIFT_NOT_IN_STATE = "not_in_state"  # Target exists but not in state
DRIFT_STATE_ONLY = "state_only"  # Resource in state but no target matched
DRIFT_ATTR_MISMATCH = "attr_mismatch"  # ID matches but identity attrs differ (e.g. remote_url)

# Resource types that are keyed by name, not by numeric ID
# These don't have a single dbt_id - they use composite keys like project_id:name
NAME_KEYED_TYPES = {"VAR", "JEVO"}

# Resource types that are project-scoped (names can repeat across projects)
# These need project-scoped matching to avoid cross-project collisions
# Derived from ENTITY_PARENT_TYPES hierarchy: types with PRJ as a (direct/indirect) parent
# CRD is excluded because it has its own environment-based matching (target_crd_by_env)
# REP is excluded because it has its own repository-based matching (target_repo_by_remote_url)
PROJECT_SCOPED_TYPES = {"ENV", "JOB", "VAR", "JEVO", "EXTATTR"}


def _dbg_db419a(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "db419a",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(
            "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-db419a.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


def _compute_drift_status(
    source_type: str,
    source_name: str,
    target_id: Optional[int],
    state_by_name: dict[tuple, dict],
    has_state: bool,
    state_by_id: Optional[dict[tuple[str, int], dict]] = None,
    project_name: Optional[str] = None,
    state_repo_by_project: Optional[dict[str, dict]] = None,
    source_remote_url: Optional[str] = None,
) -> tuple[Optional[int], str, Optional[str]]:
    """Compute state_id, drift_status, and state_address for a resource.
    
    Compares the MATCHED TARGET against Terraform state. Source IDs are never used
    since source is from a different account and its IDs are irrelevant.
    
    Note: Some resource types (VAR, JEVO) are name-keyed, not ID-keyed. They use
    composite keys like project_id:name and don't have a single numeric dbt_id.
    
    Args:
        source_type: Element type code (PRJ, ENV, etc.)
        source_name: Name of the source resource (used only for name-based fallback)
        target_id: ID of the matched target resource (if any)
        state_by_name: Lookup dict from (element_code, name) to state resource
        has_state: Whether Terraform state is loaded
        state_by_id: Optional lookup dict from (element_code, dbt_id) to state resource
        project_name: Optional project name (for repository lookups)
        state_repo_by_project: Optional lookup dict from project_name to repo state resource
        source_remote_url: Optional source repo remote_url for attribute-level drift detection
        
    Returns:
        Tuple of (state_id, drift_status, state_address)
    """
    if not has_state:
        return None, DRIFT_NO_STATE, None
    
    # Normalize source_name by stripping display prefixes (e.g., "  ↳ ")
    # These are added for hierarchy visualization but shouldn't affect lookups
    source_name = _normalize_name_for_lookup(source_name)
    
    # Name-keyed resources (VAR, JEVO) don't have single numeric IDs
    # They use composite keys like project_id:name, so we check by (type, project, name)
    if source_type in NAME_KEYED_TYPES:
        # Try project-scoped lookup first (3-tuple key)
        state_resource = state_by_name.get((source_type, project_name, source_name))
        # Fallback to unscoped key for backward compat (old state without resource_index)
        if not state_resource:
            state_resource = state_by_name.get((source_type, source_name))
        if state_resource:
            # Found by name - that's all we can check for name-keyed resources
            return None, DRIFT_IN_SYNC, state_resource.get("address")
        else:
            # Not found by name - no state tracking for this variable
            return None, DRIFT_NO_STATE, None
    
    state_resource = None
    
    # PRIORITY 1: If we have a matched target_id, look up state by that ID
    # This is the primary and most reliable lookup - does state track this exact resource?
    if state_by_id and target_id is not None:
        state_resource = state_by_id.get((source_type, target_id))
    
    # PRIORITY 2: Fall back to name lookup only when no target_id (unmatched/create new)
    # This helps detect if state already has a resource with the same name
    if not state_resource and target_id is None:
        state_resource = state_by_name.get((source_type, source_name))
    
    # PRIORITY 3: For ID mismatch detection, also check by name to find stale entries
    # This catches cases where state has resource with same name but different ID
    if not state_resource and target_id is not None:
        name_match = state_by_name.get((source_type, source_name))
        if name_match and name_match.get("dbt_id") != target_id:
            # State has same-named resource with different ID - stale entry
            state_resource = name_match
    
    # PRIORITY 4: For repositories, also check by project_name
    # This handles cases where source repo name differs from terraform key
    if not state_resource and source_type == "REP" and project_name and state_repo_by_project:
        project_match = state_repo_by_project.get(project_name)
        if project_match:
            if target_id is None:
                state_resource = project_match
            elif project_match.get("dbt_id") != target_id:
                # State has repo for this project but with different ID
                state_resource = project_match
    
    if state_resource:
        state_id = state_resource.get("dbt_id")
        state_address = state_resource.get("address")
        
        # Only consider it "in state" if we have a valid state ID
        # A None state_id means the TF state entry has no real ID to track
        if state_id is None:
            # State entry exists but has no ID - treat as not in state
            if target_id:
                return None, DRIFT_NOT_IN_STATE, None
            else:
                return None, DRIFT_NO_STATE, None
        
        if target_id is None:
            # Have state with valid ID but no target matched - resource is in TF state
            # but user is trying to create new (no match found)
            # This is potentially problematic - show that state exists
            return state_id, DRIFT_STATE_ONLY, state_address
        
        if state_id == target_id:
            # ID matches — but for REP resources, also check identity attributes
            # A repo with the same ID but different remote_url will cause TF to
            # destroy+recreate, which is dangerous for protected resources.
            if source_type == "REP" and source_remote_url:
                state_url = state_resource.get("remote_url", "")
                if state_url and source_remote_url != state_url:
                    return state_id, DRIFT_ATTR_MISMATCH, state_address
            return state_id, DRIFT_IN_SYNC, state_address
        else:
            return state_id, DRIFT_ID_MISMATCH, state_address
    else:
        # Not in state
        if target_id:
            return None, DRIFT_NOT_IN_STATE, None
        else:
            return None, DRIFT_NO_STATE, None  # Neither in state nor targeting - no drift info


# Resource type display info
RESOURCE_TYPE_INFO = {
    "ACC": {"name": "Account", "icon": "cloud", "color": "#3B82F6"},
    "CON": {"name": "Connection", "icon": "storage", "color": "#10B981"},
    "REP": {"name": "Repository", "icon": "source", "color": "#8B5CF6"},
    "TOK": {"name": "Service Token", "icon": "key", "color": "#EC4899"},
    "GRP": {"name": "Group", "icon": "group", "color": "#6366F1"},
    "NOT": {"name": "Notification", "icon": "notifications", "color": "#F97316"},
    "WEB": {"name": "Webhook", "icon": "webhook", "color": "#84CC16"},
    "PLE": {"name": "PrivateLink", "icon": "lock", "color": "#14B8A6"},
    "PRJ": {"name": "Project", "icon": "folder", "color": "#F59E0B"},
    "ENV": {"name": "Environment", "icon": "layers", "color": "#06B6D4"},
    "VAR": {"name": "Env Variable", "icon": "code", "color": "#A855F7"},
    "JOB": {"name": "Job", "icon": "schedule", "color": "#EF4444"},
    "JEVO": {"name": "EnvVar Ovr", "icon": "tune", "color": "#F472B6"},  # Job Env Var Override
    "JCTG": {"name": "Job Trigger", "icon": "play_circle", "color": "#FB923C"},  # Job Completion Trigger
    "PREP": {"name": "Repo Link", "icon": "link", "color": "#C084FC"},  # Project Repository link
}


def build_grid_data(
    source_items: list[dict],
    target_items: list[dict],
    confirmed_mappings: list[dict],
    rejected_keys: set[str],
    clone_configs: Optional[list[CloneConfig]] = None,
    state_result: Optional["StateReadResult"] = None,
    state_loaded: bool = False,
    protected_resources: Optional[set[str]] = None,
    protection_intent_manager: Optional["ProtectionIntentManager"] = None,
    removal_keys: Optional[set[str]] = None,
) -> list[dict]:
    """Build grid row data from source/target items and existing mappings.
    
    Args:
        source_items: Report items from source account
        target_items: Report items from target account
        confirmed_mappings: Already confirmed source->target mappings
        rejected_keys: Set of source keys that were rejected
        clone_configs: Optional list of clone configurations
        state_result: Optional Terraform state for drift detection
        state_loaded: Whether Terraform state has been loaded (including empty state)
        protected_resources: Optional set of source_keys that are protected (YAML config)
        protection_intent_manager: Optional intent manager for effective protection lookup
        removal_keys: Optional set of source_keys marked for unadopt (removal from TF state)
        
    Returns:
        List of row dictionaries for AG Grid
    """
    # Distinguish "state loaded but empty" from "state not loaded".
    has_loaded_state = state_loaded or state_result is not None

    # Initialize protected_resources set if None
    protected_resources = protected_resources or set()
    removal_keys = removal_keys or set()
    
    # Build clone config lookup
    clone_by_key = {}
    if clone_configs:
        for config in clone_configs:
            clone_by_key[config.source_key] = config
    
    # Build state lookup by (element_code, dbt_id) for finding state resources
    # Also build name-based lookup as fallback for "create new" scenarios
    state_by_name: dict[tuple, dict] = {}  # Keys: (type, name) or (type, project, name) for NAME_KEYED
    state_by_id: dict[tuple[str, int], dict] = {}
    if state_result and state_result.resources:
        for res in state_result.resources:
            # Normalize dbt_id to int to ensure consistent lookups
            dbt_id_normalized = res.dbt_id
            if isinstance(dbt_id_normalized, str):
                try:
                    dbt_id_normalized = int(dbt_id_normalized)
                except ValueError:
                    pass
            state_info = {
                "address": res.address,
                "dbt_id": dbt_id_normalized,
                "name": res.name,
                "tf_name": res.tf_name,
                "element_code": res.element_code,
                "project_id": res.project_id,
            }
            # Index by name if available (used only for "create new" scenarios)
            # For NAME_KEYED_TYPES, scope by project to avoid cross-project collisions
            if res.name:
                if res.element_code in NAME_KEYED_TYPES and res.resource_index and res.name:
                    # Extract project key from resource_index (e.g., "sse_mlp_fs_DBT_ENVIRONMENT_NAME" → "sse_mlp_fs")
                    suffix = "_" + res.name
                    if res.resource_index.endswith(suffix):
                        state_project_key = res.resource_index[:-len(suffix)]
                        key = (res.element_code, state_project_key, res.name)
                    else:
                        key = (res.element_code, res.name)
                else:
                    key = (res.element_code, res.name)
                state_by_name[key] = state_info
            # Also index by tf_name as fallback (for repos without name field)
            if res.tf_name:
                key = (res.element_code, res.tf_name)
                if key not in state_by_name:
                    state_by_name[key] = state_info
            # Index by dbt_id - this is the PRIMARY lookup for drift detection
            if dbt_id_normalized is not None:
                state_by_id[(res.element_code, dbt_id_normalized)] = state_info
    
    # Build additional lookup for repositories by project_name (resource_index)
    # For for_each resources, the key comes from the resource_index field
    state_repo_by_project: dict[str, dict] = {}
    if state_result and state_result.resources:
        for res in state_result.resources:
            if res.element_code == "REP":
                # Use resource_index (for_each key) if available
                repo_key = res.resource_index
                
                # Fallback: extract from address if resource_index is None
                # Address format: ...protected_repositories["sse_dm_fin_fido"]
                if not repo_key and res.address and "[" in res.address:
                    import re
                    match = re.search(r'\["([^"]+)"\]$', res.address)
                    if match:
                        repo_key = match.group(1)
                
                if repo_key:
                    # Normalize dbt_id to int to ensure consistent lookups
                    dbt_id_normalized = res.dbt_id
                    if isinstance(dbt_id_normalized, str):
                        try:
                            dbt_id_normalized = int(dbt_id_normalized)
                        except ValueError:
                            pass
                    state_repo_by_project[repo_key] = {
                        "address": res.address,
                        "dbt_id": dbt_id_normalized,
                        "name": res.name,
                        "tf_name": res.tf_name,
                        "element_code": res.element_code,
                        "project_id": res.project_id,
                        "resource_index": repo_key,  # Use the extracted key
                    }
    
    # Build target lookup by (type, name) for auto-matching
    # Note: Source IDs are from a different account and should NEVER be used for lookups
    target_by_type_name: dict[tuple[str, str], dict] = {}
    target_by_id: dict[int, dict] = {}
    # For repositories, also build lookup by remote_url and github_repo
    # This allows matching repos that point to same Git repo but have different names
    target_repo_by_remote_url: dict[str, dict] = {}
    target_repo_by_github_repo: dict[str, dict] = {}
    # For credentials (CRD), build lookup by (project_name, environment_name) 
    # since credentials are 1:1 with environments and name matching doesn't work well
    target_crd_by_env: dict[tuple[str, str], dict] = {}
    
    for item in target_items:
        element_type = item.get("element_type_code", "")
        name = item.get("name", "")
        
        # Global lookup by (type, name) for auto-matching
        # For PROJECT_SCOPED_TYPES, scope by project to avoid cross-project collisions
        # (e.g., "PROD_CI" env exists in many projects, "DBT_ENVIRONMENT_NAME" var likewise)
        if element_type in PROJECT_SCOPED_TYPES:
            proj = item.get("project_name", "")
            key = (element_type, proj, name)
        else:
            key = (element_type, name)
        if key not in target_by_type_name:
            target_by_type_name[key] = item
        
        dbt_id = item.get("dbt_id")
        if dbt_id:
            target_by_id[dbt_id] = item
            # For composite IDs like "605:556", also index by the numeric part
            # This allows matching when state extracts just the resource ID (556)
            if isinstance(dbt_id, str) and ":" in dbt_id:
                parts = dbt_id.split(":")
                try:
                    numeric_id = int(parts[-1])
                    target_by_id[numeric_id] = item
                except ValueError:
                    pass
            # Also try to index by int conversion of the full ID
            elif isinstance(dbt_id, str):
                try:
                    target_by_id[int(dbt_id)] = item
                except ValueError:
                    pass
        
        # For repositories, also index by remote_url and github_repo
        if element_type == "REP":
            remote_url = item.get("remote_url") or item.get("metadata", {}).get("remote_url")
            if remote_url:
                target_repo_by_remote_url[remote_url] = item
            github_repo = item.get("github_repo") or item.get("metadata", {}).get("github_repo")
            if github_repo:
                target_repo_by_github_repo[github_repo] = item
        
        # For credentials, index by (project_name, environment_name)
        if element_type == "CRD":
            proj_name = item.get("project_name", "")
            env_name = item.get("environment_name", "")
            if proj_name and env_name:
                crd_key = (proj_name, env_name)
                if crd_key not in target_crd_by_env:
                    target_crd_by_env[crd_key] = item
    
    # Build confirmed mapping lookup
    confirmed_by_source_key = {
        m.get("source_key"): m for m in confirmed_mappings
    }
    # region agent log
    _dbg_db419a(
        "H47",
        "match_grid.py:build_grid_data",
        "confirmed mapping lookup built",
        {
            "confirmed_count": len(confirmed_mappings),
            "lookup_key_count": len(confirmed_by_source_key),
            "lookup_keys_sample": [str(k) for k in list(confirmed_by_source_key.keys())[:30]],
        },
    )
    # endregion
    
    # Build repository lookup by key for project linking
    repo_by_key: dict[str, dict] = {}
    repo_by_parent_project: dict[str, dict] = {}
    for item in source_items:
        if item.get("element_type_code") == "REP":
            repo_key = item.get("key") or item.get("element_mapping_id", "")
            if repo_key:
                repo_by_key[repo_key] = item
            # Also index by parent project mapping id
            parent_project_id = item.get("parent_project_id")
            if parent_project_id:
                repo_by_parent_project[parent_project_id] = item
    
    # Track which repositories have been added (to avoid duplicates)
    added_repo_keys: set[str] = set()
    
    rows = []
    for source in source_items:
        # Use key if available, otherwise fall back to element_mapping_id
        # (Environment variables often have key=null)
        source_key = source.get("key") or source.get("element_mapping_id", "")
        source_name = source.get("name", "")
        source_type = source.get("element_type_code", "")
        source_id = source.get("dbt_id")
        project_name = source.get("project_name", "")
        # For NAME_KEYED_TYPES (VAR, JEVO), ensure source_key is project-scoped.
        # Same-named vars in different projects must have distinct keys for the grid
        # to correctly track confirmed mappings and diagnostic lookups.
        if source_type in NAME_KEYED_TYPES and project_name and source_key:
            project_scoped_key = f"{source_key}:{project_name}"
            # Only apply if the key isn't already project-scoped
            # (new element_ids.py generates unique keys, this is defense-in-depth)
            if source_key == source.get("element_mapping_id", ""):
                source_key = project_scoped_key
        project_id = source_id if source_type == "PRJ" else (
            source.get("project_id") or (source.get("metadata") or {}).get("project_id")
        )
        
        # Skip if no key (should rarely happen now with element_mapping_id fallback)
        if not source_key:
            continue
        
        # Skip repositories that were already added under their parent project
        if source_type == "REP" and source_key in added_repo_keys:
            continue
        
        # Check if this source is already confirmed
        confirmed = confirmed_by_source_key.get(source_key)
        # Fallback for NAME_KEYED_TYPES: old confirmed mappings may store the bare
        # element_mapping_id before the project-scoped key was introduced.
        if not confirmed and source_type in NAME_KEYED_TYPES:
            bare_key = source.get("element_mapping_id", "")
            if bare_key and bare_key != source_key:
                confirmed = confirmed_by_source_key.get(bare_key)
        if confirmed:
            target_id_val = confirmed.get("target_id", "")
            target_name = confirmed.get("target_name", "")
            
            # Compute drift status - compare matched target against TF state
            target_id_int = None
            if target_id_val:
                if isinstance(target_id_val, str) and target_id_val.lower() == "none":
                    target_id_int = None
                else:
                    try:
                        target_id_int = int(target_id_val)
                    except (TypeError, ValueError):
                        pass
            state_id, drift_status, state_address = _compute_drift_status(
                source_type, source_name, target_id_int, state_by_name, has_loaded_state,
                state_by_id=state_by_id,
                project_name=project_name,
                state_repo_by_project=state_repo_by_project,
            )
            
            # Determine action: use stored action, or default to "match"
            # Adoption requires explicit user opt-in (bulk "Adopt All" or per-row dropdown)
            # However, if the resource is in_sync, override any stored "adopt" back to "match"
            # since the resource is already correctly managed in TF state.
            # IMPORTANT: If drift_status is "not_in_state", the resource needs adoption
            # (import) — leaving it as "match" would cause Terraform to create a duplicate.
            stored_action = confirmed.get("action")
            if stored_action == "adopt" and drift_status not in (
                DRIFT_NOT_IN_STATE,
                DRIFT_ID_MISMATCH,
                DRIFT_ATTR_MISMATCH,
                DRIFT_NO_STATE,
            ):
                action = "match"  # Resource is in_sync — adopt is no longer needed
                # region agent log
                _dbg_db419a(
                    "H49",
                    "match_grid.py:build_grid_rows:adopt_override",
                    "stored adopt overridden to match due drift status",
                    {
                        "source_key": source_key,
                        "source_type": source_type,
                        "stored_action": stored_action,
                        "drift_status": drift_status,
                    },
                )
                # endregion
            elif stored_action == "match" and (
                drift_status == DRIFT_NOT_IN_STATE
                or (drift_status == DRIFT_NO_STATE and source_type == "CON")
            ):
                action = "adopt"  # Stored "match" is stale — resource not in TF state, needs import
                # #region agent log
                import json as _json_dbg_sa, time as _time_dbg_sa; open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a").write(_json_dbg_sa.dumps({"timestamp": int(_time_dbg_sa.time()*1000), "location": "match_grid.py:confirmed_path:stale_match_override", "message": "Overrode stale stored 'match' to 'adopt' for not_in_state resource", "hypothesisId": "STALE", "data": {"source_key": source_key, "source_type": source_type, "drift_status": drift_status, "stored_action": stored_action, "final_action": "adopt"}}) + "\n")
                # #endregion
            elif stored_action:
                action = stored_action
            elif drift_status == DRIFT_NOT_IN_STATE or (
                drift_status == DRIFT_NO_STATE and source_type == "CON"
            ):
                action = "adopt"  # Not in TF state — needs import, not match
            else:
                action = "match"
            # region agent log
            if source_type == "PRJ" and stored_action == "match":
                _dbg_db419a(
                    "H44",
                    "match_grid.py:build_grid_rows:confirmed_path",
                    "resolved confirmed PRJ row action from stored match",
                    {
                        "source_key": source_key,
                        "target_id": target_id_val,
                        "stored_action": stored_action,
                        "drift_status": drift_status,
                        "state_id": state_id,
                        "final_action": action,
                        "has_state_result": has_loaded_state,
                    },
                )
            # endregion
            
            row = {
                "source_key": source_key,
                "source_name": source_name,
                "source_type": source_type,
                "source_id": source_id,
                "project_name": project_name,
                "project_id": project_id,
                "action": action,
                "target_id": str(target_id_val) if target_id_val else "",
                "target_name": target_name,
                "status": "confirmed",
                "confidence": confirmed.get("match_type", "manual"),
                "clone_configured": False,
                "clone_name": "",
                "state_id": state_id,
                "drift_status": drift_status,
                "state_address": state_address,
            }
            # region agent log
            if source_type == "ENV":
                _dbg_db419a(
                    "H48",
                    "match_grid.py:build_grid_data:confirmed_env",
                    "ENV row resolved from confirmed mapping",
                    {
                        "source_key": source_key,
                        "source_name": source_name,
                        "project_name": project_name,
                        "stored_action": stored_action,
                        "final_action": action,
                        "drift_status": drift_status,
                    },
                )
            # endregion
            rows.append(row)
            continue
        
        # Check if rejected
        if source_key in rejected_keys:
            clone_config = clone_by_key.get(source_key)
            
            # Compute drift status (no target for create_new)
            state_id, drift_status, state_address = _compute_drift_status(
                source_type, source_name, None, state_by_name, has_loaded_state,
                state_by_id=state_by_id,
                project_name=project_name,
                state_repo_by_project=state_repo_by_project,
            )
            
            row = {
                "source_key": source_key,
                "source_name": source_name,
                "source_type": source_type,
                "source_id": source_id,
                "project_name": project_name,
                "action": "create_new",
                "target_id": "",
                "target_name": "",
                "status": "skipped",
                "confidence": "none",
                "clone_configured": clone_config is not None,
                "clone_name": clone_config.new_name if clone_config else "",
                "state_id": state_id,
                "drift_status": drift_status,
                "state_address": state_address,
            }
            rows.append(row)
            continue
        
        # Try auto-match by exact name in target
        # Note: We match by name only. Source IDs are from different account and not used.
        # Strip display prefixes (e.g., "  ↳ ") for lookup - these are added for hierarchy display
        normalized_source_name = _normalize_name_for_lookup(source_name)
        # For PROJECT_SCOPED_TYPES, scope lookup by project to avoid cross-project collisions
        if source_type in PROJECT_SCOPED_TYPES:
            lookup_key = (source_type, project_name, normalized_source_name)
        else:
            lookup_key = (source_type, normalized_source_name)
        clone_config = clone_by_key.get(source_key)
        target = target_by_type_name.get(lookup_key)
        match_confidence = "exact_match" if target else "none"
        # Special handling for CRD (credentials) - match by parent environment instead of name
        # since credential names are generic like "Credential (snowflake)" and often don't match exactly
        if source_type == "CRD" and not target:
            source_proj_name = source.get("project_name", "")
            source_env_name = source.get("environment_name", "")
            if source_proj_name and source_env_name:
                crd_lookup = (source_proj_name, source_env_name)
                target = target_crd_by_env.get(crd_lookup)
                if target:
                    match_confidence = "env_match"  # Matched by environment
        
        # STATE-AWARE AUTO-MATCHING: If no target found by name but resource is in TF state,
        # look up the state's ID in targets and auto-suggest that match. This handles cases
        # where source name differs from target name but the resource was already imported.
        if not target and state_result:
            state_resource = None
            # For repositories, check by project_name first (handles project-linked repos)
            if source_type == "REP" and project_name:
                state_resource = state_repo_by_project.get(project_name)
            # Fall back to name-based lookup for other types or if not found
            # Use normalized name to strip display prefixes
            # For NAME_KEYED_TYPES, use project-scoped key first
            if not state_resource:
                if source_type in NAME_KEYED_TYPES:
                    state_resource = state_by_name.get((source_type, project_name, normalized_source_name))
                if not state_resource:
                    state_resource = state_by_name.get((source_type, normalized_source_name))
            
            # If we have a state resource with a valid ID, look up in targets
            if state_resource and state_resource.get("dbt_id"):
                state_dbt_id = state_resource.get("dbt_id")
                # Normalize to int for lookup (handles potential type mismatch from state storage)
                if isinstance(state_dbt_id, str):
                    try:
                        state_dbt_id = int(state_dbt_id)
                    except ValueError:
                        pass
                # Try lookup with normalized ID
                target_from_state = target_by_id.get(state_dbt_id)
                # Fallback: try with original value if int conversion didn't help
                if not target_from_state and state_resource.get("dbt_id") != state_dbt_id:
                    target_from_state = target_by_id.get(state_resource.get("dbt_id"))
                if target_from_state and target_from_state.get("element_type_code") == source_type:
                    target = target_from_state
                    match_confidence = "state_id_match"  # Found via Terraform state ID lookup
        
        if target:
            target_id_int = target.get("dbt_id")
            
            # For REP resources, get source remote_url for attribute-level drift detection
            _src_remote_url = None
            if source_type == "REP":
                _src_remote_url = source.get("remote_url") or (source.get("metadata") or {}).get("remote_url")

            # Compute drift status - compare matched target against TF state
            state_id, drift_status, state_address = _compute_drift_status(
                source_type, source_name, target_id_int, state_by_name, has_loaded_state,
                state_by_id=state_by_id,
                project_name=project_name,
                state_repo_by_project=state_repo_by_project,
                source_remote_url=_src_remote_url,
            )
            
            # Default to "match" — adoption requires explicit user opt-in.
            # EXCEPTION: when state is loaded and drift shows the matched target
            # is not tracked by TF ("not_in_state" or "no_state"), default to
            # "adopt" to prevent duplicate-create behavior.
            default_action = (
                "adopt"
                if drift_status == DRIFT_NOT_IN_STATE
                or (drift_status == DRIFT_NO_STATE and source_type == "CON")
                else "match"
            )
            # region agent log
            if source_type == "CON":
                _dbg_db419a(
                    "H50",
                    "match_grid.py:build_grid_data:auto_match_action",
                    "auto-match action selected for connection row",
                    {
                        "source_key": source_key,
                        "source_name": source_name,
                        "target_id": target_id_int,
                        "drift_status": drift_status,
                        "has_loaded_state": has_loaded_state,
                        "default_action": default_action,
                    },
                )
            # endregion
            
            # #region agent log
            if drift_status == DRIFT_NOT_IN_STATE:
                import json as _json_dbg_nis, time as _time_dbg_nis; open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a").write(_json_dbg_nis.dumps({"timestamp": int(_time_dbg_nis.time()*1000), "location": "match_grid.py:build_grid_rows:auto_match", "message": "not_in_state resource auto-set to adopt", "hypothesisId": "NIS", "data": {"source_key": source_key, "source_type": source_type, "source_name": source_name, "drift_status": drift_status, "default_action": default_action}}) + "\n")
            # #endregion
            
            row = {
                "source_key": source_key,
                "source_name": source_name,
                "source_type": source_type,
                "source_id": source_id,
                "project_name": project_name,
                "action": default_action,
                "target_id": str(target.get("dbt_id") or ""),
                "target_name": target.get("name", ""),
                "status": "pending",
                "confidence": match_confidence,  # Use tracked confidence (exact_match, state_id_match, etc.)
                "clone_configured": False,
                "clone_name": "",
                "state_id": state_id,
                "drift_status": drift_status,
                "state_address": state_address,
            }
            # region agent log
            if source_type == "ENV" and source_key in confirmed_by_source_key:
                _dbg_db419a(
                    "H48",
                    "match_grid.py:build_grid_data:env_collision",
                    "ENV row used auto-match branch despite confirmed key",
                    {
                        "source_key": source_key,
                        "source_name": source_name,
                        "project_name": project_name,
                        "default_action": default_action,
                        "drift_status": drift_status,
                    },
                )
            # endregion
        else:
            # No match found - check for clone config
            # Compute drift status (no target for create_new)
            state_id, drift_status, state_address = _compute_drift_status(
                source_type, source_name, None, state_by_name, has_loaded_state,
                state_by_id=state_by_id,
                project_name=project_name,
                state_repo_by_project=state_repo_by_project,
            )
            
            row = {
                "source_key": source_key,
                "source_name": source_name,
                "source_type": source_type,
                "source_id": source_id,
                "project_name": project_name,
                "action": "create_new",
                "target_id": "",
                "target_name": "",
                "status": "pending",
                "confidence": "none",
                "clone_configured": clone_config is not None,
                "clone_name": clone_config.new_name if clone_config else "",
                "state_id": state_id,
                "drift_status": drift_status,
                "state_address": state_address,
            }
        
        rows.append(row)
        
        # Track repositories to avoid duplicate entries under parent project
        if source_type == "REP":
            added_repo_keys.add(source_key)
        
        # If this is a "create_new" job, add its derived resources after it
        if source_type == "JOB" and row["action"] == "create_new":
            # Add job environment variable override rows
            overrides = source.get("environment_variable_overrides", {})
            if overrides:
                for var_name, var_value in sorted(overrides.items()):
                    override_key = f"{source_key}__override__{var_name}"
                    override_row = {
                        "source_key": override_key,
                        "source_name": f"  ↳ {var_name}",  # Indented to show hierarchy
                        "source_type": "JEVO",  # Job Env Var Override
                        "source_id": None,
                        "project_name": project_name,
                        "action": "create_new",  # Overrides are always new
                        "target_id": "",
                        "target_name": "",
                        "status": "pending",
                        "confidence": "derived",  # Derived from job definition
                        "clone_configured": False,
                        "clone_name": "",
                        "parent_job_key": source_key,  # Reference to parent job
                        "parent_job_name": source_name,
                        "state_id": None,  # Derived resources don't have state
                        "drift_status": DRIFT_NO_STATE if not state_result else DRIFT_IN_SYNC,
                    }
                    rows.append(override_row)
            
            # Add job completion trigger row if present
            jctc = source.get("job_completion_trigger_condition", {})
            # Check if it has meaningful content (job_id or condition)
            has_trigger = False
            if isinstance(jctc, dict):
                has_trigger = bool(jctc.get("job_id") or jctc.get("condition"))
            if has_trigger:
                trigger_key = f"{source_key}__trigger__completion"
                trigger_row = {
                    "source_key": trigger_key,
                    "source_name": "  ↳ Completion Trigger",
                    "source_type": "JCTG",  # Job Completion Trigger
                    "source_id": None,
                    "project_name": project_name,
                    "action": "create_new",
                    "target_id": "",
                    "target_name": "",
                    "status": "pending",
                    "confidence": "derived",
                    "clone_configured": False,
                    "clone_name": "",
                    "parent_job_key": source_key,
                    "parent_job_name": source_name,
                    "state_id": None,
                    "drift_status": DRIFT_NO_STATE if not state_result else DRIFT_IN_SYNC,
                }
                rows.append(trigger_row)
        
        # If this is a project, add its repository and repo link underneath
        if source_type == "PRJ":
            # Find the repository linked to this project
            repo = repo_by_parent_project.get(source.get("element_mapping_id"))
            if not repo:
                # Try by repository_key
                repo_key = source.get("repository_key")
                if repo_key:
                    repo = repo_by_key.get(repo_key)
            
            if repo:
                repo_source_key = repo.get("key") or repo.get("element_mapping_id", "")
                if repo_source_key and repo_source_key not in added_repo_keys:
                    added_repo_keys.add(repo_source_key)
                    repo_name = repo.get("name", "")
                    repo_id = repo.get("dbt_id")
                    
                    # Check if repository is confirmed
                    repo_confirmed = confirmed_by_source_key.get(repo_source_key)
                    if repo_confirmed:
                        repo_target_id = repo_confirmed.get("target_id")
                        repo_target_id_int = int(repo_target_id) if repo_target_id else None
                        repo_state_id, repo_drift, repo_state_addr = _compute_drift_status(
                            "REP", repo_name, repo_target_id_int, state_by_name, has_loaded_state,
                            state_by_id=state_by_id,
                            project_name=source_name,  # Parent project name
                            state_repo_by_project=state_repo_by_project,
                        )
                        repo_row = {
                            "source_key": repo_source_key,
                            "source_name": f"  ↳ {repo_name}",  # Indented under project
                            "source_type": "REP",
                            "source_id": repo_id,
                            "project_name": source_name,
                            "action": "match",
                            "target_id": str(repo_confirmed.get("target_id", "")),
                            "target_name": repo_confirmed.get("target_name", ""),
                            "status": "confirmed",
                            "confidence": repo_confirmed.get("match_type", "manual"),
                            "clone_configured": False,
                            "clone_name": "",
                            "state_id": repo_state_id,
                            "drift_status": repo_drift,
                            "state_address": repo_state_addr,
                        }
                    else:
                        # Try auto-match for repository
                        # Priority: 1) remote_url, 2) github_repo, 3) name
                        repo_lookup_key = ("REP", repo_name)
                        repo_clone_config = clone_by_key.get(repo_source_key)
                        
                        # Get remote_url and github_repo from source repo
                        source_remote_url = repo.get("remote_url") or repo.get("metadata", {}).get("remote_url")
                        source_github_repo = repo.get("github_repo") or repo.get("metadata", {}).get("github_repo")
                        
                        # Try to find target repo by remote_url or github_repo first
                        target_repo = None
                        match_confidence = "none"
                        if source_remote_url and source_remote_url in target_repo_by_remote_url:
                            target_repo = target_repo_by_remote_url[source_remote_url]
                            match_confidence = "url_match"
                        elif source_github_repo and source_github_repo in target_repo_by_github_repo:
                            target_repo = target_repo_by_github_repo[source_github_repo]
                            match_confidence = "github_match"
                        elif repo_lookup_key in target_by_type_name:
                            target_repo = target_by_type_name[repo_lookup_key]
                            match_confidence = "exact_match"
                        
                        # STATE-AWARE MATCHING for repositories: If no match found but repo is in TF state,
                        # look up target by state's dbt_id. This handles adopted repos with different names.
                        if not target_repo and state_result and state_repo_by_project:
                            state_repo = state_repo_by_project.get(source_name)  # source_name is parent project name
                            if state_repo and state_repo.get("dbt_id"):
                                state_dbt_id = state_repo.get("dbt_id")
                                # Normalize to int for lookup
                                if isinstance(state_dbt_id, str):
                                    try:
                                        state_dbt_id = int(state_dbt_id)
                                    except ValueError:
                                        pass
                                # Look up target by state ID
                                target_from_state = target_by_id.get(state_dbt_id)
                                if target_from_state and target_from_state.get("element_type_code") == "REP":
                                    target_repo = target_from_state
                                    match_confidence = "state_id_match"
                        
                        if repo_source_key in rejected_keys:
                            repo_state_id, repo_drift, repo_state_addr = _compute_drift_status(
                                "REP", repo_name, None, state_by_name, has_loaded_state,
                                state_by_id=state_by_id,
                                project_name=source_name,
                                state_repo_by_project=state_repo_by_project,
                            )
                            repo_row = {
                                "source_key": repo_source_key,
                                "source_name": f"  ↳ {repo_name}",
                                "source_type": "REP",
                                "source_id": repo_id,
                                "project_name": source_name,
                                "project_id": (
                                    repo_item.get("project_id")
                                    or (repo_item.get("metadata") or {}).get("project_id")
                                    or source.get("dbt_id")
                                ),
                                "action": "create_new",
                                "target_id": "",
                                "target_name": "",
                                "status": "skipped",
                                "confidence": "none",
                                "clone_configured": repo_clone_config is not None,
                                "clone_name": repo_clone_config.new_name if repo_clone_config else "",
                                "state_id": repo_state_id,
                                "drift_status": repo_drift,
                                "state_address": repo_state_addr,
                            }
                        elif target_repo:
                            # Found a target repo match (by url, github_repo, or name)
                            repo_target_id_int = target_repo.get("dbt_id")
                            repo_state_id, repo_drift, repo_state_addr = _compute_drift_status(
                                "REP", repo_name, repo_target_id_int, state_by_name, has_loaded_state,
                                state_by_id=state_by_id,
                                project_name=source_name,
                                state_repo_by_project=state_repo_by_project,
                            )
                            # If matched but not in state, or ID mismatch, default to "adopt"
                            if repo_drift in (DRIFT_NOT_IN_STATE, DRIFT_ID_MISMATCH):
                                repo_default_action = "adopt"
                            else:
                                repo_default_action = "match"
                            repo_row = {
                                "source_key": repo_source_key,
                                "source_name": f"  ↳ {repo_name}",
                                "source_type": "REP",
                                "source_id": repo_id,
                                "project_name": source_name,
                                "action": repo_default_action,
                                "target_id": str(target_repo.get("dbt_id", "")),
                                "target_name": target_repo.get("name", ""),
                                "status": "pending",
                                "confidence": match_confidence,  # url_match, github_match, or exact_match
                                "clone_configured": False,
                                "clone_name": "",
                                "state_id": repo_state_id,
                                "drift_status": repo_drift,
                                "state_address": repo_state_addr,
                            }
                        else:
                            repo_state_id, repo_drift, repo_state_addr = _compute_drift_status(
                                "REP", repo_name, None, state_by_name, has_loaded_state,
                                state_by_id=state_by_id,
                                project_name=source_name,
                                state_repo_by_project=state_repo_by_project,
                            )
                            repo_row = {
                                "source_key": repo_source_key,
                                "source_name": f"  ↳ {repo_name}",
                                "source_type": "REP",
                                "source_id": repo_id,
                                "project_name": source_name,
                                "action": "create_new",
                                "target_id": "",
                                "target_name": "",
                                "status": "pending",
                                "confidence": "none",
                                "clone_configured": repo_clone_config is not None,
                                "clone_name": repo_clone_config.new_name if repo_clone_config else "",
                                "state_id": repo_state_id,
                                "drift_status": repo_drift,
                                "state_address": repo_state_addr,
                            }
                    rows.append(repo_row)
                    
                    # Add repo link (derived resource) if project is create_new
                    if row["action"] == "create_new":
                        link_key = f"{source_key}__repo_link__{repo_source_key}"
                        link_row = {
                            "source_key": link_key,
                            "source_name": "    ↳ Link",  # Double indented under repo
                            "source_type": "PREP",
                            "source_id": None,
                            "project_name": source_name,
                            "action": "create_new",
                            "target_id": "",
                            "target_name": "",
                            "status": "pending",
                            "confidence": "derived",
                            "clone_configured": False,
                            "clone_name": "",
                            "parent_project_key": source_key,
                            "repository_key": repo_source_key,
                            "state_id": None,
                            "drift_status": DRIFT_NO_STATE if not state_result else DRIFT_IN_SYNC,
                        }
                        rows.append(link_row)
    
    # Append state-only rows: state resources that are NOT already represented by a source row.
    # These are resources managed by Terraform in the target but not part of the source migration.
    if state_result and state_result.resources:
        # Collect (element_code, dbt_id) pairs already covered by existing rows
        covered_state_ids: set[tuple[str, int]] = set()
        for row in rows:
            # A row covers a state resource if its matched target_id matches the state dbt_id
            row_type = row.get("source_type", "")
            row_state_id = row.get("state_id")
            if row_state_id is not None:
                try:
                    covered_state_ids.add((row_type, int(row_state_id)))
                except (TypeError, ValueError):
                    pass
            # Also cover by target_id (in case state_id wasn't set but target was matched)
            row_target_id = row.get("target_id")
            if row_target_id:
                try:
                    covered_state_ids.add((row_type, int(row_target_id)))
                except (TypeError, ValueError):
                    pass

        for res in state_result.resources:
            dbt_id = res.dbt_id
            if isinstance(dbt_id, str):
                try:
                    dbt_id = int(dbt_id)
                except ValueError:
                    continue
            if dbt_id is None:
                continue
            if (res.element_code, dbt_id) in covered_state_ids:
                continue

            # Look up the matching target to get a proper name
            target_item = target_by_id.get(dbt_id)
            target_name = ""
            target_project = ""
            if target_item:
                target_name = target_item.get("name", "")
                target_project = target_item.get("project_name", "")
            else:
                target_name = res.name or res.tf_name or ""

            project_name = target_project or res.resource_index or ""

            state_row = {
                "source_key": f"state__{res.address}",
                "source_name": target_name,
                "source_type": res.element_code,
                "source_id": None,
                "project_name": project_name,
                "action": "match",
                "target_id": str(dbt_id),
                "target_name": target_name,
                "status": "confirmed",
                "confidence": "state_match",
                "clone_configured": False,
                "clone_name": "",
                "state_id": dbt_id,
                "drift_status": DRIFT_IN_SYNC,
                "state_address": res.address,
                "is_state_only": True,
            }
            rows.append(state_row)
            # Mark as covered to avoid duplicates from multi-address resources
            covered_state_ids.add((res.element_code, dbt_id))

    # Append target-only rows: target resources that are NOT matched to any source
    # item and NOT already represented by a state-only row. These are resources
    # that exist in the target account but have no corresponding source resource.
    # They default to action="ignore" — the user explicitly opts in to adopt them.
    if target_items:
        # Collect target IDs already covered by existing rows (source-matched or state-only)
        covered_target_ids: set[int] = set()
        for row in rows:
            tid = row.get("target_id")
            if tid:
                try:
                    covered_target_ids.add(int(tid))
                except (TypeError, ValueError):
                    pass
            sid = row.get("state_id")
            if sid:
                try:
                    covered_target_ids.add(int(sid))
                except (TypeError, ValueError):
                    pass
        
        for item in target_items:
            dbt_id = item.get("dbt_id")
            if dbt_id is None:
                continue
            try:
                dbt_id_int = int(dbt_id)
            except (TypeError, ValueError):
                continue
            if dbt_id_int in covered_target_ids:
                continue
            
            element_type = item.get("element_type_code", "UNK")
            item_name = item.get("name", "")
            item_key = item.get("key", "") or f"target__{element_type}_{dbt_id_int}"
            project_name = item.get("project_name", "")
            
            target_source_key = f"target__{item_key}"
            
            # Check if this target-only resource has a confirmed mapping (e.g., adopt)
            confirmed = confirmed_by_source_key.get(target_source_key)
            confirmed_action = confirmed.get("action", "ignore") if confirmed else "ignore"
            target_only_row = {
                "source_key": target_source_key,
                "source_name": "",  # Empty source column for target-only
                "source_type": element_type,
                "source_id": None,
                "project_name": project_name,
                "action": confirmed_action,  # Use confirmed action or default to ignore
                "target_id": str(dbt_id_int),
                "target_name": item_name,
                "status": "confirmed" if confirmed else "pending",
                "confidence": "target_only",
                "clone_configured": False,
                "clone_name": "",
                "state_id": None,
                "drift_status": DRIFT_NOT_IN_STATE,
                "state_address": "",
                "is_target_only": True,
            }
            rows.append(target_only_row)

    # Post-process: Add protection status to all rows
    # We track THREE separate protection fields:
    # 1. yaml_protected: What's in the YAML config (from protected_resources set)
    # 2. state_protected: Actual TF state (from state_address containing ".protected_")
    # 3. protected: Effective protection (intent takes precedence over YAML if available)
    import re as _re_prot
    for row in rows:
        source_key = row.get("source_key", "")
        state_address = row.get("state_address", "")
        source_type = row.get("source_type", "")
        
        # Check if resource is in a protected Terraform map (e.g., protected_repositories, protected_projects)
        is_state_protected = ".protected_" in state_address if state_address else False
        
        # Check if user wants it protected (from YAML config)
        # protected_resources should store bare keys (e.g. "everyone"),
        # but legacy data may have "target__" prefixed keys. Check all forms:
        #   1. Exact match (works for bare or prefixed)
        #   2. Strip "target__" from source_key (for target-only rows)
        #   3. Add "target__" to source_key (for legacy prefixed stored keys)
        is_yaml_protected = source_key in protected_resources
        if not is_yaml_protected and source_key.startswith("target__"):
            is_yaml_protected = source_key[len("target__"):] in protected_resources
        if not is_yaml_protected and not source_key.startswith("target__"):
            is_yaml_protected = f"target__{source_key}" in protected_resources
        
        # For state-only resources, the source_key is "state__<full_tf_address>"
        # but the protection intent system stores keys as "TYPE:short_tf_key"
        # (extracted from the ["key"] portion of the state address).
        # For target-only resources, source_key is "target__<name>" but intent
        # is stored as "TYPE:name" — build the prefixed key.
        # Normalize the lookup key to match the intent system's key format.
        # Intent keys are stored as "TYPE:name" (e.g. "GRP:everyone").
        # Source keys arrive in different formats depending on the page:
        #   - Match page: "target__everyone" (target-only) or "state__<address>" (state-only)
        #   - Adopt page: "everyone" (bare key, no prefix)
        # All must be normalized to "TYPE:name" for intent lookup.
        intent_lookup_key = source_key
        if source_key.startswith("state__") and state_address:
            _m = _re_prot.search(r'\["([^"]+)"\]$', state_address)
            if _m:
                short_key = _m.group(1)
                intent_lookup_key = f"{source_type}:{short_key}" if source_type else short_key
        elif source_key.startswith("target__"):
            _bare = source_key[len("target__"):]
            intent_lookup_key = f"{source_type}:{_bare}" if source_type else _bare
        elif source_type and ":" not in source_key:
            # Bare key (e.g. "everyone") from Adopt page — add TYPE prefix
            intent_lookup_key = f"{source_type}:{source_key}"
        
        # Use protection intent manager if available to get effective protection
        # Intent takes precedence over YAML to prevent "flip-flopping"
        if protection_intent_manager is not None:
            is_effective_protected = protection_intent_manager.get_effective_protection(
                intent_lookup_key, yaml_protected=is_yaml_protected
            )
        else:
            # Fallback: use YAML protection directly
            is_effective_protected = is_yaml_protected
        
        # #region agent log
        if source_type == "GRP":
            import json as _json_dbg2, time as _time_dbg2
            _dbg_entry2 = {"timestamp": int(_time_dbg2.time()*1000), "location": "match_grid.py:build_grid_data:protection_check", "message": f"GRP protection check for {source_key}", "hypothesisId": "B", "data": {"source_key": source_key, "is_yaml_protected": is_yaml_protected, "is_state_protected": is_state_protected, "is_effective_protected": is_effective_protected, "intent_lookup_key": intent_lookup_key, "action": row.get("action", ""), "has_intent_mgr": protection_intent_manager is not None, "protected_resources_sample": sorted(list(protected_resources))[:20]}}
            with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as _f2:
                _f2.write(_json_dbg2.dumps(_dbg_entry2) + "\n")
        # #endregion
        
        # Store all values for mismatch detection and UI
        row["yaml_protected"] = is_effective_protected  # User's intended state (intent or YAML)
        row["state_protected"] = is_state_protected     # Actual TF state
        
        # Combined value for UI display (protected if either source says so)
        row["protected"] = is_effective_protected or is_state_protected
        
        # Suppress protection for non-management actions.
        # Protection only applies to resources that Terraform will manage (match/adopt).
        # For ignore/skip/unadopt/create_new, force protected=False to prevent
        # stale shields from appearing in the grid.
        if row.get("action", "") in ("ignore", "skip", "unadopt", "create_new"):
            row["protected"] = False
            row["yaml_protected"] = False
        
        # Protection mismatch: resource is in TF state but protection level disagrees
        # with what the user intends (e.g., state has protected but user wants unprotected,
        # or state has unprotected but user wants protected)
        drift = row.get("drift_status", "")
        has_state = drift in (DRIFT_IN_SYNC, DRIFT_ID_MISMATCH, DRIFT_ATTR_MISMATCH)
        row["protection_mismatch"] = (
            has_state and is_effective_protected != is_state_protected
        )
    
    # Post-process: Apply removal_keys (unadopt) so persisted intent shows on load
    for row in rows:
        if row.get("source_key") in removal_keys:
            row["action"] = "unadopt"
            row["status"] = "unadopted"
    
    # Post-process: CRD drift status inheritance from parent ENV
    # CRDs don't exist in Terraform state directly - they're embedded in environment resources.
    # If the parent ENV is in_sync, the CRD should show as in_sync for better UX.
    if state_result:
        # Build lookup of ENV drift status by (project_name, env_name)
        env_drift_by_key: dict[tuple[str, str], str] = {}
        for row in rows:
            if row.get("source_type") == "ENV":
                proj = row.get("project_name", "")
                env_name = row.get("source_name", "")
                drift = row.get("drift_status", "")
                if proj and env_name and drift:
                    env_drift_by_key[(proj, env_name)] = drift
        
        # Now update CRD rows to inherit parent ENV drift status
        for row in rows:
            if row.get("source_type") == "CRD":
                proj = row.get("project_name", "")
                # CRD source_name is often like "Credential (snowflake, ...)" but we need env_name
                # Look for environment_name in the source item or derive from context
                # Since CRD is matched by (proj, env) key, we can extract env_name from source data
                crd_drift = row.get("drift_status", "")
                
                # Only inherit if CRD has no meaningful drift status
                if crd_drift in (DRIFT_NO_STATE, None, ""):
                    # Try to find matching source item to get environment_name
                    crd_source_key = row.get("source_key", "")
                    for source in source_items:
                        if source.get("key") == crd_source_key:
                            env_name = source.get("environment_name", "")
                            if proj and env_name:
                                parent_drift = env_drift_by_key.get((proj, env_name))
                                if parent_drift == DRIFT_IN_SYNC:
                                    row["drift_status"] = DRIFT_IN_SYNC
                            break
    
    return rows


def create_match_grid(
    source_items: list[dict],
    target_items: list[dict],
    confirmed_mappings: list[dict],
    rejected_keys: set[str],
    on_row_change: Callable[[dict], None],
    on_accept: Callable[[str], None],
    on_reject: Callable[[str], None],
    on_view_details: Callable[[str], None],
    clone_configs: Optional[list[CloneConfig]] = None,
    on_configure_clone: Optional[Callable[[str], None]] = None,
    state_result: Optional["StateReadResult"] = None,
    state_loaded: bool = False,
    on_adopt: Optional[Callable[[str], None]] = None,
    on_unadopt: Optional[Callable[[str], None]] = None,
    removal_keys: Optional[set[str]] = None,
    protected_resources: Optional[set[str]] = None,
    protection_intent_manager: Optional["ProtectionIntentManager"] = None,
    row_data_override: Optional[list[dict]] = None,
) -> tuple:
    """Create the editable matching grid.
    
    Args:
        source_items: Report items from source account
        target_items: Report items from target account
        confirmed_mappings: Already confirmed mappings
        rejected_keys: Set of rejected source keys
        on_row_change: Callback when a row value changes
        on_accept: Callback when accept button clicked (source_key)
        on_reject: Callback when reject button clicked (source_key)
        on_view_details: Callback when details button clicked (source_key)
        clone_configs: Optional list of existing clone configurations
        on_configure_clone: Callback when configure clone button clicked (source_key)
        state_result: Optional Terraform state for drift detection
        state_loaded: Whether Terraform state has been loaded (including empty state)
        on_adopt: Callback when adopt button clicked (source_key) for drift resolution
        on_unadopt: Callback when unadopt action is set (source_key) for removal from TF state
        removal_keys: Optional set of source_keys marked for unadopt (persisted, applied on load)
        protected_resources: Optional set of source_keys that are protected
        protection_intent_manager: Optional intent manager for effective protection lookup
        row_data_override: Optional pre-filtered row data; when provided, skips build_grid_data
        
    Returns:
        Tuple of (grid component, row data list)
    """
    # Build row data (or use override if provided, e.g. for filtered views)
    if row_data_override is not None:
        row_data = row_data_override
    else:
        removal_keys = removal_keys or set()
        row_data = build_grid_data(
            source_items, target_items, confirmed_mappings, rejected_keys, clone_configs,
            state_result=state_result,
            state_loaded=state_loaded,
            protected_resources=protected_resources,
            protection_intent_manager=protection_intent_manager,
            removal_keys=removal_keys,
        )
    
    # Build target options for autocomplete
    target_options = [
        {
            "id": str(t.get("dbt_id", "")),
            "name": t.get("name", ""),
            "type": t.get("element_type_code", ""),
        }
        for t in target_items if t.get("dbt_id")
    ]
    
    # Column definitions - using proper NiceGUI AG Grid format
    # Note: cellClassRules work better than cellRenderer for styling in NiceGUI
    column_defs = [
        {
            "field": "details_btn",
            "colId": "details_btn",
            "headerName": "",
            "width": 50,
            "maxWidth": 50,
            "sortable": False,
            "filter": False,
            "resizable": False,
            "cellStyle": {"textAlign": "center", "cursor": "pointer"},
            ":cellRenderer": """params => '<span style="font-size: 16px; cursor: pointer;" title="View Details">🔍</span>'""",
        },
        {
            "field": "source_type",
            "colId": "source_type",
            "headerName": "Type",
            "width": 110,
            # Use valueFormatter for display text
            ":valueFormatter": """params => {
                const types = {
                    'ACC': 'Account', 'CON': 'Connection', 'REP': 'Repository',
                    'TOK': 'Token', 'GRP': 'Group', 'NOT': 'Notify',
                    'WEB': 'Webhook', 'PLE': 'PrivateLink', 'PRJ': 'Project',
                    'ENV': 'Environment', 'VAR': 'EnvVar', 'JOB': 'Job',
                    'JEVO': 'EnvVar Ovr', 'JCTG': 'Job Trigger', 'PREP': 'Repo Link',
                };
                return types[params.value] || params.value;
            }""",
            "cellClassRules": {
                "type-project": "x === 'PRJ'",
                "type-environment": "x === 'ENV'",
                "type-job": "x === 'JOB'",
                "type-connection": "x === 'CON'",
                "type-repository": "x === 'REP'",
                "type-envvar": "x === 'VAR'",
                "type-override": "x === 'JEVO'",
                "type-trigger": "x === 'JCTG'",
                "type-projrepo": "x === 'PREP'",
                "type-other": "!['PRJ','ENV','JOB','CON','REP','VAR','JEVO','JCTG','PREP'].includes(x)",
            },
        },
        {
            "field": "row_origin",
            "colId": "row_origin",
            "headerName": "Origin",
            "headerTooltip": "Resource origin: source-matched, target-only, in TF state, or managed",
            "width": 100,
            "sortable": True,
            "filter": True,
            ":valueGetter": """params => {
                if (!params.data) return '';
                if (params.data.is_target_only) return 'target_only';
                if (params.data.is_state_only) return 'state_only';
                if (params.data.drift_status === 'in_sync') return 'managed';
                return 'source';
            }""",
            ":cellRenderer": """params => {
                if (!params.data) return '';
                if (params.data.is_target_only) {
                    return '<span style="background: #0D9488; color: white; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-family: sans-serif;">Target Only</span>';
                }
                if (params.data.is_state_only) {
                    return '<span style="background: #6366F1; color: white; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-family: sans-serif;">In State</span>';
                }
                if (params.data.drift_status === 'in_sync') {
                    return '<span style="background: #6366F1; color: white; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-family: sans-serif;">Managed</span>';
                }
                return '<span style="color: #94A3B8; font-size: 11px;">Source</span>';
            }""",
        },
        {
            "field": "source_name",
            "colId": "source_name",
            "headerName": "Source Name",
            "width": 200,
            "filter": "agTextColumnFilter",
            "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
            ":cellRenderer": """params => {
                var val = params.value || '';
                if (params.data && params.data.drift_status === 'in_sync') {
                    var addr = params.data.state_address || '';
                    var addrHtml = addr ? ' <span style="color: #6366F1; font-size: 10px; font-family: monospace;" title="' + addr + '">' + addr + '</span>' : '';
                    return val + addrHtml;
                }
                return val;
            }""",
        },
        {
            "field": "source_id",
            "colId": "source_id",
            "headerName": "Source ID",
            "width": 90,
            "cellStyle": {"fontFamily": "monospace", "fontSize": "11px"},
        },
        {
            "field": "action",
            "colId": "action",
            "headerName": "Action",
            "width": 130,
            "editable": True,
            "cellEditor": "agSelectCellEditor",
            "cellEditorParams": {
                "values": ACTION_VALUES,
            },
            ":valueFormatter": """params => {
                const labels = {
                    'match': '⛓️ Match',
                    'create_new': '➕ Create New',
                    'skip': '⏭️ Skip',
                    'adopt': '📥 Adopt',
                    'unadopt': '🔓 Unadopt',
                    'ignore': '🚫 Ignore',
                };
                return labels[params.value] || params.value;
            }""",
            "cellClassRules": {
                "action-match": "x === 'match'",
                "action-create": "x === 'create_new'",
                "action-skip": "x === 'skip'",
                "action-adopt": "x === 'adopt'",
                "action-unadopt": "x === 'unadopt'",
                "action-ignore": "x === 'ignore'",
            },
        },
        {
            "field": "protected",
            "colId": "protected",
            "headerName": "🛡️",
            "headerTooltip": "Protect from destroy - Terraform will refuse to delete protected resources",
            "width": 55,
            "maxWidth": 55,
            "editable": False,  # Handle toggle via cellClicked, not built-in editor
            "cellStyle": {"textAlign": "center", "cursor": "pointer"},
            ":cellRenderer": """params => params.value ? '<span style="color: #3B82F6; font-size: 16px;" title="Protected from destroy - click to unprotect">🛡️</span>' : '<span style="color: #D1D5DB; font-size: 14px;" title="Click to protect">○</span>'""",
        },
        {
            "field": "target_id",
            "colId": "target_id",
            "headerName": "Target ID",
            "width": 100,
            "editable": True,
            "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
        },
        {
            "field": "target_name",
            "colId": "target_name",
            "headerName": "Target Name",
            "width": 180,
            "cellStyle": {"fontFamily": "monospace", "fontSize": "12px"},
            "cellClassRules": {
                "target-matched": "x && x.length > 0",
                "target-empty": "!x || x.length === 0",
            },
        },
        {
            "field": "state_id",
            "colId": "state_id",
            "headerName": "State ID",
            "width": 90,
            "cellStyle": {"fontFamily": "monospace", "fontSize": "11px"},
            ":valueFormatter": "params => params.value != null ? params.value : '-'",
        },
        {
            "field": "drift_status",
            "colId": "drift_status",
            "headerName": "Drift",
            "width": 110,
            ":valueFormatter": """params => {
                const labels = {
                    'no_state': '—',
                    'in_sync': '✓ In Sync',
                    'id_mismatch': '⚠️ Mismatch',
                    'not_in_state': '➕ Not in TF',
                    'state_only': '📌 In State',
                    'attr_mismatch': '⚠️ Attr Diff',
                };
                var label = labels[params.value] || params.value || '—';
                if (params.data && params.data.protection_mismatch) {
                    label += ' 🛡️';
                }
                return label;
            }""",
            "cellClassRules": {
                "drift-sync": "x === 'in_sync'",
                "drift-mismatch": "x === 'id_mismatch' || x === 'attr_mismatch'",
                "drift-missing": "x === 'not_in_state'",
                "drift-state-only": "x === 'state_only'",
                "drift-none": "x === 'no_state' || !x",
            },
        },
        {
            "field": "state_address",
            "colId": "state_address",
            "headerName": "TF Address",
            "headerTooltip": "Terraform state resource address (shown when resource is already managed)",
            "width": 180,
            "hide": True,  # Hidden by default; user can enable via column menu
            "cellStyle": {"fontFamily": "monospace", "fontSize": "10px", "color": "#6366F1"},
            ":valueFormatter": "params => params.value || ''",
        },
        {
            "field": "status",
            "colId": "status",
            "headerName": "Status",
            "width": 110,
            ":valueFormatter": """params => {
                const labels = {
                    'pending': '⏳ Pending',
                    'confirmed': '✓ Confirmed',
                    'error': '✗ Error',
                    'skipped': '⊘ Skipped',
                    'unadopted': '🔓 Unadopted',
                };
                return labels[params.value] || params.value;
            }""",
            "cellClassRules": {
                "status-pending": "x === 'pending'",
                "status-confirmed": "x === 'confirmed'",
                "status-error": "x === 'error'",
                "status-skipped": "x === 'skipped'",
                "status-unadopted": "x === 'unadopted'",
            },
        },
        {
            "field": "project_name",
            "colId": "project_name",
            "headerName": "Project",
            "width": 140,
            "filter": "agTextColumnFilter",
            "cellStyle": {"fontSize": "11px"},
        },
        {
            "field": "clone_name",
            "colId": "clone_name",
            "headerName": "Clone Name",
            "width": 160,
            "cellStyle": {"fontSize": "12px"},
        },
    ]
    
    # Grid options - note: getRowId must be a JS string function for AG Grid
    grid_options = {
        "columnDefs": column_defs,
        "rowData": row_data,
        "pagination": False,  # Show all rows - grid has good scrolling behavior
        "rowHeight": 40,
        "headerHeight": 36,
        "defaultColDef": {
            "resizable": True,
            "sortable": True,
            "filter": True,
        },
        "rowClassRules": {
            "row-matched": "data.action === 'match' && data.target_id && data.target_id.length > 0",
            "row-confirmed": "data.status === 'confirmed'",
            "row-error": "data.status === 'error'",
            "row-skipped": "data.status === 'skipped' || data.action === 'skip'",
            "row-unadopted": "data.action === 'unadopt'",
            "row-protected": "data.protected === true",
        },
        "stopEditingWhenCellsLoseFocus": True,
        "singleClickEdit": True,
        "animateRows": False,  # Stability - per ag-grid-standards.mdc
        # Remove getRowId - can cause issues with NiceGUI's AG Grid wrapper
    }
    
    # Create the grid - use quartz theme for automatic dark/light mode support
    # Use flex-grow to fill available space, with min-height for smaller viewports
    # CRITICAL: Set width: 100% and overflow to enable horizontal scrolling within the grid
    grid = ui.aggrid(grid_options, theme="quartz").classes("w-full flex-grow ag-theme-quartz-auto-dark").style("height: 100%; min-height: 300px; width: 100%; overflow-x: auto;")
    
    # Handle cell value changes
    def on_cell_changed(e):
        if e.args:
            data = e.args.get("data", {})
            col = e.args.get("colId", "")
            new_val = e.args.get("newValue")
            
            if col == "action":
                # When action changes, update the row
                data["action"] = new_val
                if new_val == "skip":
                    data["status"] = "skipped"
                    data["target_id"] = ""
                    data["target_name"] = ""
                elif new_val == "create_new":
                    data["target_id"] = ""
                    data["target_name"] = ""
                    data["status"] = "pending"
                elif new_val == "adopt":
                    # Adopt keeps the current target_id (adopts target resource into TF state)
                    # The resource will need an import block generated
                    data["status"] = "pending"
                    # If there's no target_id but we have drift info, that's still valid
                    # The import will use the target_id from the grid
                elif new_val == "match":
                    # Switching back to match - restore pending status
                    data["status"] = "pending"
                elif new_val == "unadopt":
                    # Unadopt: remove resource from TF management (terraform state rm)
                    # Keep target_id for reference but mark as removal candidate
                    data["status"] = "unadopted"
                
                on_row_change(data)
                
                # If adopt action and on_adopt callback exists, trigger it
                if new_val == "adopt" and on_adopt:
                    source_key = data.get("source_key", "")
                    if source_key:
                        on_adopt(source_key)
                # If unadopt action and on_unadopt callback exists, trigger it
                if new_val == "unadopt" and on_unadopt:
                    source_key = data.get("source_key", "")
                    if source_key:
                        on_unadopt(source_key)
            
            elif col == "target_id":
                # Validate target ID
                data["target_id"] = new_val
                if new_val:
                    # Look up target name
                    target = next(
                        (t for t in target_options if t["id"] == str(new_val)),
                        None
                    )
                    if target:
                        # Validate type matches
                        if target["type"] == data.get("source_type"):
                            data["target_name"] = target["name"]
                            data["status"] = "pending"
                        else:
                            data["target_name"] = f"Type mismatch: {target['type']}"
                            data["status"] = "error"
                    else:
                        data["target_name"] = ""
                        data["status"] = "error"
                else:
                    data["target_name"] = ""
                    data["status"] = "pending" if data.get("action") == "create_new" else "error"
                
                on_row_change(data)
            
            # Note: protected column is handled via cellClicked for immediate response
    
    grid.on("cellValueChanged", on_cell_changed)
    
    # Handle cell click - trigger details when clicking the details button column
    # Also handle protection toggle immediately (don't wait for blur)
    def on_cell_clicked(e):
        if e.args:
            col = e.args.get("colId", "")
            # #region agent log
            import json as _json_dbg_cc, time as _time_dbg_cc; open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a").write(_json_dbg_cc.dumps({"timestamp": int(_time_dbg_cc.time()*1000), "location": "match_grid.py:on_cell_clicked", "message": "cellClicked fired", "hypothesisId": "A", "data": {"colId": col, "has_data": bool(e.args.get("data")), "source_key": e.args.get("data", {}).get("source_key", ""), "current_protected": e.args.get("data", {}).get("protected", "MISSING")}}) + "\n")
            # #endregion
            if col == "details_btn":
                data = e.args.get("data", {})
                source_key = data.get("source_key", "")
                if source_key and on_view_details:
                    on_view_details(source_key)
            elif col == "protected":
                # Toggle protection immediately on click (don't wait for blur)
                data = e.args.get("data", {})
                if data:
                    # Toggle the protection value
                    new_protected = not data.get("protected", False)
                    data["protected"] = new_protected
                    # #region agent log
                    open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a").write(_json_dbg_cc.dumps({"timestamp": int(_time_dbg_cc.time()*1000), "location": "match_grid.py:on_cell_clicked:protected_toggle", "message": "Toggling protection", "hypothesisId": "C", "data": {"source_key": data.get("source_key", ""), "new_protected": new_protected, "old_protected_in_data": not new_protected}}) + "\n")
                    # #endregion
                    # Trigger the row change handler immediately
                    on_row_change(data)
    
    grid.on("cellClicked", on_cell_clicked)
    
    # Also handle cell double-click anywhere to view details
    def on_cell_double_clicked(e):
        if e.args:
            data = e.args.get("data", {})
            source_key = data.get("source_key", "")
            if source_key and on_view_details:
                on_view_details(source_key)
    
    grid.on("cellDoubleClicked", on_cell_double_clicked)
    
    # Custom CSS for cell class rules and row classes - with dark mode support
    ui.add_css("""
        /* Row background colors based on match/status - high specificity to override AG Grid defaults */
        .ag-theme-quartz .ag-row.row-matched,
        .ag-theme-quartz-auto-dark .ag-row.row-matched {
            background-color: rgba(16, 185, 129, 0.12) !important;
        }
        .ag-theme-quartz .ag-row.row-confirmed,
        .ag-theme-quartz-auto-dark .ag-row.row-confirmed {
            background-color: rgba(16, 185, 129, 0.20) !important;
        }
        .ag-theme-quartz .ag-row.row-error,
        .ag-theme-quartz-auto-dark .ag-row.row-error {
            background-color: rgba(239, 68, 68, 0.15) !important;
        }
        .ag-theme-quartz .ag-row.row-skipped,
        .ag-theme-quartz-auto-dark .ag-row.row-skipped {
            background-color: rgba(156, 163, 175, 0.15) !important;
        }
        .ag-theme-quartz .ag-row.row-protected,
        .ag-theme-quartz-auto-dark .ag-row.row-protected {
            background-color: rgba(59, 130, 246, 0.08) !important;
            border-left: 3px solid #3B82F6 !important;
        }
        
        /* Legacy selectors for backwards compatibility */
        .row-matched {
            background-color: rgba(16, 185, 129, 0.12) !important;
        }
        .row-confirmed {
            background-color: rgba(16, 185, 129, 0.20) !important;
        }
        .row-error {
            background-color: rgba(239, 68, 68, 0.15) !important;
        }
        .row-skipped {
            background-color: rgba(156, 163, 175, 0.15) !important;
        }
        .row-protected {
            background-color: rgba(59, 130, 246, 0.08) !important;
            border-left: 3px solid #3B82F6 !important;
        }
        
        /* Type column colors */
        .type-project { color: #F59E0B !important; font-weight: 600; }
        .type-environment { color: #06B6D4 !important; font-weight: 600; }
        .type-job { color: #EF4444 !important; font-weight: 600; }
        .type-connection { color: #10B981 !important; font-weight: 600; }
        .type-repository { color: #8B5CF6 !important; font-weight: 600; }
        .type-envvar { color: #6B8E6B !important; font-weight: 600; }
        .type-override { color: #EAB308 !important; font-weight: 600; }
        .type-trigger { color: #FB923C !important; font-weight: 600; }
        .type-projrepo { color: #C084FC !important; font-weight: 600; }
        .type-other { color: #6B7280 !important; }
        
        /* Action column colors */
        .action-match { color: #047377 !important; font-weight: 500; }
        .action-create { color: #F59E0B !important; font-weight: 500; }
        .action-skip { color: #6B7280 !important; font-style: italic; }
        .action-adopt { color: #8B5CF6 !important; font-weight: 600; background-color: rgba(139, 92, 246, 0.15) !important; }
        .action-ignore { color: #9CA3AF !important; font-style: italic; text-decoration: line-through; }
        
        /* Status column colors */
        .status-pending { color: #D97706 !important; }
        .status-confirmed { color: #059669 !important; font-weight: 600; }
        .status-error { color: #DC2626 !important; font-weight: 600; }
        .status-skipped { color: #6B7280 !important; font-style: italic; }
        
        /* Target column */
        .target-matched { color: #10B981 !important; }
        .target-empty { color: #9CA3AF !important; }
        
        /* Drift status column colors */
        .drift-sync { color: #059669 !important; }
        .drift-mismatch { color: #D97706 !important; font-weight: 600; background-color: rgba(217, 119, 6, 0.15) !important; }
        .drift-missing { color: #F59E0B !important; }
        .drift-state-only { color: #3B82F6 !important; font-weight: 600; background-color: rgba(59, 130, 246, 0.15) !important; }
        .drift-none { color: #9CA3AF !important; }
        
        /* Dark mode overrides - high specificity to override AG Grid defaults */
        .dark .ag-theme-quartz .ag-row.row-matched,
        .body--dark .ag-theme-quartz .ag-row.row-matched,
        .dark .ag-theme-quartz-auto-dark .ag-row.row-matched,
        .body--dark .ag-theme-quartz-auto-dark .ag-row.row-matched {
            background-color: rgba(16, 185, 129, 0.20) !important;
        }
        .dark .ag-theme-quartz .ag-row.row-confirmed,
        .body--dark .ag-theme-quartz .ag-row.row-confirmed,
        .dark .ag-theme-quartz-auto-dark .ag-row.row-confirmed,
        .body--dark .ag-theme-quartz-auto-dark .ag-row.row-confirmed {
            background-color: rgba(16, 185, 129, 0.30) !important;
        }
        .dark .ag-theme-quartz .ag-row.row-error,
        .body--dark .ag-theme-quartz .ag-row.row-error,
        .dark .ag-theme-quartz-auto-dark .ag-row.row-error,
        .body--dark .ag-theme-quartz-auto-dark .ag-row.row-error {
            background-color: rgba(239, 68, 68, 0.25) !important;
        }
        .dark .ag-theme-quartz .ag-row.row-skipped,
        .body--dark .ag-theme-quartz .ag-row.row-skipped,
        .dark .ag-theme-quartz-auto-dark .ag-row.row-skipped,
        .body--dark .ag-theme-quartz-auto-dark .ag-row.row-skipped {
            background-color: rgba(156, 163, 175, 0.25) !important;
        }
        .dark .ag-theme-quartz .ag-row.row-protected,
        .body--dark .ag-theme-quartz .ag-row.row-protected,
        .dark .ag-theme-quartz-auto-dark .ag-row.row-protected,
        .body--dark .ag-theme-quartz-auto-dark .ag-row.row-protected {
            background-color: rgba(59, 130, 246, 0.20) !important;
        }
        
        /* Legacy dark mode selectors */
        .dark .row-matched, .body--dark .row-matched {
            background-color: rgba(16, 185, 129, 0.20) !important;
        }
        .dark .row-confirmed, .body--dark .row-confirmed {
            background-color: rgba(16, 185, 129, 0.30) !important;
        }
        .dark .row-error, .body--dark .row-error {
            background-color: rgba(239, 68, 68, 0.25) !important;
        }
        .dark .row-skipped, .body--dark .row-skipped {
            background-color: rgba(156, 163, 175, 0.25) !important;
        }
        .dark .row-protected, .body--dark .row-protected {
            background-color: rgba(59, 130, 246, 0.20) !important;
        }
        
        /* Dark mode type colors - brighter for visibility */
        .dark .type-project, .body--dark .type-project { color: #FBBF24 !important; }
        .dark .type-environment, .body--dark .type-environment { color: #22D3EE !important; }
        .dark .type-job, .body--dark .type-job { color: #F87171 !important; }
        .dark .type-connection, .body--dark .type-connection { color: #34D399 !important; }
        .dark .type-repository, .body--dark .type-repository { color: #A78BFA !important; }
        .dark .type-envvar, .body--dark .type-envvar { color: #8FBC8F !important; }
        .dark .type-override, .body--dark .type-override { color: #FACC15 !important; }
        .dark .type-trigger, .body--dark .type-trigger { color: #FDBA74 !important; }
        .dark .type-projrepo, .body--dark .type-projrepo { color: #D8B4FE !important; }
        
        /* Dark mode status colors */
        .dark .status-pending, .body--dark .status-pending { color: #FCD34D !important; }
        .dark .status-confirmed, .body--dark .status-confirmed { color: #6EE7B7 !important; }
        .dark .status-error, .body--dark .status-error { color: #FCA5A5 !important; }
        
        /* Dark mode target */
        .dark .target-matched, .body--dark .target-matched { color: #34D399 !important; }
        .dark .target-empty, .body--dark .target-empty { color: #6B7280 !important; }
        
        /* Dark mode drift colors */
        .dark .drift-sync, .body--dark .drift-sync { color: #6EE7B7 !important; }
        .dark .drift-mismatch, .body--dark .drift-mismatch { color: #FBBF24 !important; background-color: rgba(251, 191, 36, 0.25) !important; }
        .dark .drift-missing, .body--dark .drift-missing { color: #FCD34D !important; }
        .dark .drift-state-only, .body--dark .drift-state-only { color: #60A5FA !important; background-color: rgba(96, 165, 250, 0.25) !important; }
        .dark .drift-none, .body--dark .drift-none { color: #6B7280 !important; }
    """)
    
    return grid, row_data


# Allowed values for the Action column (match grid)
ACTION_VALUES = ["match", "create_new", "skip", "adopt", "unadopt", "ignore"]

# Type labels for match grid filter dropdown (same codes as source_type column)
MATCH_GRID_TYPE_LABELS = {
    "ACC": "Account",
    "CON": "Connection",
    "REP": "Repository",
    "TOK": "Token",
    "GRP": "Group",
    "NOT": "Notify",
    "WEB": "Webhook",
    "PLE": "PrivateLink",
    "PRJ": "Project",
    "ENV": "Environment",
    "VAR": "EnvVar",
    "JOB": "Job",
    "JEVO": "EnvVar Ovr",
    "JCTG": "Job Trigger",
    "PREP": "Repo Link",
}


def create_grid_toolbar(
    row_data: list[dict],
    on_accept_all: Callable[[], None],
    on_reject_all: Callable[[], None],
    on_reset_all: Callable[[], None],
    on_export_csv: Callable[[], None],
    on_type_filter_change: Optional[Callable[[str], None]] = None,
    on_adopt_all_matched: Optional[Callable[[], None]] = None,
    on_ignore_all_unmatched: Optional[Callable[[], None]] = None,
    on_adopt_all_target_only: Optional[Callable[[], None]] = None,
    on_toggle_target_only: Optional[Callable[[str], None]] = None,
    show_target_only: bool = True,
    target_only_exclusive: bool = False,
    target_only_total: int = 0,
    on_toggle_scope_only: Optional[Callable[[bool], None]] = None,
    show_scope_only: bool = False,
    hidden_by_scope: int = 0,
    on_select_project: Optional[Callable[[str], None]] = None,
) -> None:
    """Create the toolbar above the grid with bulk actions and type filter.
    
    Args:
        row_data: Current row data for counting
        on_accept_all: Callback for Accept All button
        on_reject_all: Callback for Reject All button
        on_reset_all: Callback for Reset All button
        on_export_csv: Callback for Export CSV button
        on_type_filter_change: Optional callback when type filter dropdown changes (filter value string)
        on_adopt_all_matched: Optional callback for "Adopt All Matched" bulk action
        on_ignore_all_unmatched: Optional callback for "Ignore All Unmatched" bulk action
        on_adopt_all_target_only: Optional callback for "Adopt All Target-Only" bulk action
        on_toggle_target_only: Optional callback when target-only filter changes (receives "hide"/"include"/"only")
        show_target_only: Current state of the target-only visibility toggle
        target_only_exclusive: When True, show ONLY target-only rows
        target_only_total: Total target-only rows in unfiltered data (for showing the dropdown even when hidden)
        on_toggle_scope_only: Optional callback when "Show Source Selected Only" toggle changes
        show_scope_only: Current state of scope visibility filter
        hidden_by_scope: Number of rows hidden by scope filter (for display)
    """
    # Count stats
    pending = sum(1 for r in row_data if r.get("status") == "pending" and r.get("action") == "match")
    confirmed = sum(1 for r in row_data if r.get("status") == "confirmed")
    create_new = sum(1 for r in row_data if r.get("action") == "create_new")
    skipped = sum(1 for r in row_data if r.get("action") == "skip")
    adopted = sum(1 for r in row_data if r.get("action") == "adopt")
    unadopted = sum(1 for r in row_data if r.get("action") == "unadopt")
    clones = sum(1 for r in row_data if r.get("clone_configured"))
    # Count rows eligible for bulk adopt (have a target match but not yet adopted)
    adoptable_matched = sum(
        1 for r in row_data
        if r.get("target_id") and r.get("action") not in ("adopt", "unadopt")
        and not r.get("is_state_only")
    )
    # Count rows without target match that could be ignored
    unmatched_pending = sum(
        1 for r in row_data
        if not r.get("target_id") and r.get("action") not in ("skip", "ignore")
        and not r.get("is_state_only")
    )
    # Count target-only rows
    target_only_count = sum(1 for r in row_data if r.get("is_target_only"))
    target_only_adoptable = sum(
        1 for r in row_data
        if r.get("is_target_only") and r.get("action") != "adopt"
    )
    
    with ui.row().classes("w-full items-center justify-between mb-3 flex-wrap gap-2"):
        # Type filter dropdown (like explore grids)
        types_in_data = sorted(set(r.get("source_type", "UNK") for r in row_data))
        type_counts: dict[str, int] = {}
        for r in row_data:
            t = r.get("source_type", "UNK")
            type_counts[t] = type_counts.get(t, 0) + 1
        filter_options: dict[str, str] = {"all": f"All Types ({len(row_data)})"}
        for t in types_in_data:
            label = MATCH_GRID_TYPE_LABELS.get(t, t)
            filter_options[t] = f"{label} ({t}) [{type_counts.get(t, 0)}]"
        ui.select(
            options=filter_options,
            value="all",
            on_change=lambda e: on_type_filter_change(e.value) if on_type_filter_change else None,
        ).props("outlined dense").classes("min-w-[200px]")
        
        # Target-only filter (3-way dropdown when target-only rows exist in unfiltered data)
        _to_total = target_only_total if target_only_total > 0 else target_only_count
        if _to_total > 0 and on_toggle_target_only is not None:
            target_filter_options = {
                "hide": f"Hide Target-Only ({_to_total})",
                "include": f"Include Target-Only ({_to_total})",
                "only": f"Target-Only Only ({_to_total})",
            }
            # Derive initial value from current state
            if target_only_exclusive:
                _initial_target_filter = "only"
            elif show_target_only:
                _initial_target_filter = "include"
            else:
                _initial_target_filter = "hide"
            ui.select(
                options=target_filter_options,
                value=_initial_target_filter,
                on_change=lambda e: on_toggle_target_only(e.value),
            ).props("outlined dense").classes("min-w-[200px] text-sm")
        
        # Source-selected visibility filter toggle
        if on_toggle_scope_only is not None:
            scope_label = "Show Source Selected Only"
            if show_scope_only and hidden_by_scope > 0:
                scope_label += f" ({hidden_by_scope} hidden)"
            ui.switch(
                scope_label,
                value=show_scope_only,
                on_change=lambda e: on_toggle_scope_only(e.value),
            ).props("dense color=blue-grey").classes("text-sm")
        
        # Stats
        with ui.row().classes("items-center gap-4"):
            with ui.row().classes("items-center gap-1"):
                ui.badge(str(pending), color="amber").props("dense")
                ui.label("Pending").classes("text-sm")
            
            with ui.row().classes("items-center gap-1"):
                ui.badge(str(confirmed), color="green").props("dense")
                ui.label("Confirmed").classes("text-sm")
            
            with ui.row().classes("items-center gap-1"):
                ui.badge(str(create_new), color="orange").props("dense")
                ui.label("Create New").classes("text-sm")
            
            with ui.row().classes("items-center gap-1"):
                ui.badge(str(skipped), color="grey").props("dense")
                ui.label("Skip").classes("text-sm")
            
            if adopted > 0:
                with ui.row().classes("items-center gap-1"):
                    ui.badge(str(adopted), color="teal").props("dense")
                    ui.label("Adopted").classes("text-sm")
            
            with ui.row().classes("items-center gap-1"):
                ui.badge(str(unadopted), color="purple").props("dense")
                ui.label("Unadopt").classes("text-sm")
            
            if clones > 0:
                with ui.row().classes("items-center gap-1"):
                    ui.badge(str(clones), color="amber").props("dense")
                    ui.label("Clones").classes("text-sm")
        
        # Actions - use flat buttons with explicit colors for dark mode visibility
        with ui.row().classes("items-center gap-2"):
            ui.button(
                f"Accept All ({pending})",
                icon="check",
                on_click=on_accept_all,
            ).props("size=sm flat text-color=green-6").set_enabled(pending > 0)
            
            ui.button(
                "Reject All",
                icon="close",
                on_click=on_reject_all,
            ).props("size=sm flat text-color=red-6").set_enabled(pending > 0)
            
            ui.button(
                "Reset",
                icon="refresh",
                on_click=on_reset_all,
            ).props("size=sm flat")
            
            ui.button(
                "Export CSV",
                icon="download",
                on_click=on_export_csv,
            ).props("size=sm flat")
            
            # Adoption bulk actions
            if on_adopt_all_matched is not None:
                ui.button(
                    f"Adopt All Matched ({adoptable_matched})",
                    icon="link",
                    on_click=on_adopt_all_matched,
                ).props("size=sm flat text-color=teal-6").set_enabled(adoptable_matched > 0)
            
            if on_ignore_all_unmatched is not None:
                ui.button(
                    f"Ignore Unmatched ({unmatched_pending})",
                    icon="visibility_off",
                    on_click=on_ignore_all_unmatched,
                ).props("size=sm flat text-color=grey-6").set_enabled(unmatched_pending > 0)
            
            if on_adopt_all_target_only is not None and target_only_count > 0:
                ui.button(
                    f"Adopt All Target-Only ({target_only_adoptable})",
                    icon="input",
                    on_click=on_adopt_all_target_only,
                ).props("size=sm flat text-color=teal-6").set_enabled(target_only_adoptable > 0)
            
            # "Select Project" dropdown - lists available projects for bulk adoption
            if on_select_project is not None:
                project_names = sorted(set(
                    r.get("project_name", "") or r.get("source_name", "")
                    for r in row_data
                    if r.get("source_type") == "PRJ" and (r.get("project_name") or r.get("source_name"))
                ))
                if project_names:
                    with ui.dropdown_button(
                        "Select Project",
                        icon="folder_open",
                    ).props("size=sm flat text-color=blue-6 dropdown-icon=arrow_drop_down"):
                        for pname in project_names:
                            ui.item(
                                pname,
                                on_click=lambda p=pname: on_select_project(p),
                            )


def export_mappings_to_csv(row_data: list[dict]) -> str:
    """Export mapping data to CSV format.
    
    Args:
        row_data: Grid row data
        
    Returns:
        CSV string
    """
    lines = ["source_key,source_name,source_type,action,target_id,target_name,status,clone_configured,clone_name"]
    
    for row in row_data:
        line = ",".join([
            f'"{row.get("source_key", "")}"',
            f'"{row.get("source_name", "")}"',
            f'"{row.get("source_type", "")}"',
            f'"{row.get("action", "")}"',
            f'"{row.get("target_id", "")}"',
            f'"{row.get("target_name", "")}"',
            f'"{row.get("status", "")}"',
            f'"{row.get("clone_configured", False)}"',
            f'"{row.get("clone_name", "")}"',
        ])
        lines.append(line)
    
    return "\n".join(lines)
