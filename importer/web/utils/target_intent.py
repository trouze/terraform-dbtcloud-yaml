"""Target intent: first-class artifact for what Terraform should manage.

Computes target intent from:
- Terraform state (floor: default retain all project keys)
- Source focus YAML (upserts)
- Adopt rows (adopted)
- Removal keys (removed)
- Target fetch (orphan detection: in state but not in target account)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from importer.web.utils.adoption_yaml_updater import merge_yaml_configs

logger = logging.getLogger(__name__)


def _dbg_db419a(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    """Write one NDJSON debug record for target-intent diagnostics."""
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

# Disposition values
DISP_RETAINED = "retained"
DISP_UPSERTED = "upserted"
DISP_ADOPTED = "adopted"
DISP_REMOVED = "removed"
DISP_ORPHAN_FLAGGED = "orphan_flagged"
DISP_ORPHAN_RETAINED = "orphan_retained"


@dataclass
class ResourceDisposition:
    """Disposition of a single resource in the target intent."""

    key: str
    resource_type: str  # e.g. "PRJ"
    disposition: str
    source: str
    config_source: Optional[str] = None
    tf_state_address: Optional[str] = None
    confirmed: bool = False
    confirmed_at: Optional[str] = None
    # Protection fields — explicit intent per resource
    protected: bool = False
    protection_set_by: Optional[str] = None  # "default_unprotected", "tf_state_default", "protection_intent", "user"
    protection_set_at: Optional[str] = None
    # Config preference: which value source to use when generating YAML
    # "target" = use target/TF state values (for retained, adopted/matched resources)
    # "source" = use source YAML values (for upserted/new resources)
    config_preference: str = "target"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "resource_type": self.resource_type,
            "disposition": self.disposition,
            "source": self.source,
            "config_source": self.config_source,
            "tf_state_address": self.tf_state_address,
            "confirmed": self.confirmed,
            "confirmed_at": self.confirmed_at,
            "protected": self.protected,
            "protection_set_by": self.protection_set_by,
            "protection_set_at": self.protection_set_at,
            "config_preference": self.config_preference,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceDisposition:
        return cls(
            key=data.get("key", ""),
            resource_type=data.get("resource_type", "PRJ"),
            disposition=data.get("disposition", DISP_RETAINED),
            source=data.get("source", ""),
            config_source=data.get("config_source"),
            tf_state_address=data.get("tf_state_address"),
            confirmed=data.get("confirmed", False),
            confirmed_at=data.get("confirmed_at"),
            protected=data.get("protected", False),
            protection_set_by=data.get("protection_set_by"),
            protection_set_at=data.get("protection_set_at"),
            config_preference=data.get("config_preference", "target"),
        )


@dataclass
class SourceToTargetMapping:
    """A source-to-target match mapping entry (replaces confirmed_mappings in session state)."""

    source_key: str
    resource_type: str = "PRJ"  # e.g. "PRJ", "ENV"
    target_id: str = ""
    target_name: str = ""
    match_type: str = "manual"  # "manual", "exact_match", "state_id_match", etc.
    action: str = "match"  # "match" or "adopt"
    confirmed: bool = False
    confirmed_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_key": self.source_key,
            "resource_type": self.resource_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "match_type": self.match_type,
            "action": self.action,
            "confirmed": self.confirmed,
            "confirmed_at": self.confirmed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceToTargetMapping:
        return cls(
            source_key=data.get("source_key", ""),
            resource_type=data.get("resource_type", "PRJ"),
            target_id=data.get("target_id", ""),
            target_name=data.get("target_name", ""),
            match_type=data.get("match_type", "manual"),
            action=data.get("action", "match"),
            confirmed=data.get("confirmed", False),
            confirmed_at=data.get("confirmed_at"),
        )

    @classmethod
    def from_confirmed_mapping(cls, cm: dict[str, Any]) -> SourceToTargetMapping:
        """Convert a confirmed_mappings session-state dict into a typed mapping."""
        return cls(
            source_key=cm.get("source_key", ""),
            resource_type=cm.get("resource_type", "PRJ"),
            target_id=cm.get("target_id", ""),
            target_name=cm.get("target_name", ""),
            match_type=cm.get("match_type", "manual"),
            action=cm.get("action", "match"),
            confirmed=True,
            confirmed_at=cm.get("confirmed_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    def to_confirmed_mapping(self) -> dict[str, Any]:
        """Convert back to confirmed_mappings session-state dict format."""
        return {
            "source_key": self.source_key,
            "resource_type": self.resource_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "match_type": self.match_type,
            "action": self.action,
        }


@dataclass
class StateToTargetMapping:
    """A TF-state-to-target match mapping entry (which state resource maps to which target)."""

    state_key: str
    state_address: str = ""
    resource_type: str = "PRJ"
    target_id: str = ""
    target_name: str = ""
    match_type: str = "auto"  # "auto", "manual", "unmatched"
    confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_key": self.state_key,
            "state_address": self.state_address,
            "resource_type": self.resource_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "match_type": self.match_type,
            "confirmed": self.confirmed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateToTargetMapping:
        return cls(
            state_key=data.get("state_key", ""),
            state_address=data.get("state_address", ""),
            resource_type=data.get("resource_type", "PRJ"),
            target_id=data.get("target_id", ""),
            target_name=data.get("target_name", ""),
            match_type=data.get("match_type", "auto"),
            confirmed=data.get("confirmed", False),
        )


@dataclass
class MatchMappings:
    """Container for both source-to-target and state-to-target match mappings."""

    source_to_target: list[SourceToTargetMapping] = field(default_factory=list)
    state_to_target: list[StateToTargetMapping] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_to_target": [m.to_dict() for m in self.source_to_target],
            "state_to_target": [m.to_dict() for m in self.state_to_target],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MatchMappings:
        return cls(
            source_to_target=[
                SourceToTargetMapping.from_dict(m)
                for m in data.get("source_to_target", [])
            ],
            state_to_target=[
                StateToTargetMapping.from_dict(m)
                for m in data.get("state_to_target", [])
            ],
        )

    def source_key_set(self) -> set[str]:
        """Return set of source_keys that have mappings."""
        return {m.source_key for m in self.source_to_target}

    def state_key_set(self) -> set[str]:
        """Return set of state_keys that have mappings."""
        return {m.state_key for m in self.state_to_target}

    def to_confirmed_mappings(self) -> list[dict[str, Any]]:
        """Convert source_to_target to confirmed_mappings format for session state."""
        return [m.to_confirmed_mapping() for m in self.source_to_target]

    @classmethod
    def from_confirmed_mappings(cls, confirmed: list[dict[str, Any]]) -> MatchMappings:
        """Create MatchMappings with source_to_target from confirmed_mappings dicts."""
        return cls(
            source_to_target=[
                SourceToTargetMapping.from_confirmed_mapping(cm)
                for cm in confirmed
            ],
        )


@dataclass
class TargetIntentResult:
    """Result of computing target intent: dispositions + merged config + match mappings + warnings."""

    version: int = 2
    computed_at: str = ""
    dispositions: dict[str, ResourceDisposition] = field(default_factory=dict)
    match_mappings: MatchMappings = field(default_factory=MatchMappings)
    output_config: dict[str, Any] = field(default_factory=dict)
    coverage_warnings: list[str] = field(default_factory=list)
    drift_warnings: list[str] = field(default_factory=list)
    tf_state_path: Optional[str] = None
    source_focus_path: Optional[str] = None
    source_focus_base_folder: Optional[str] = None
    baseline_path: Optional[str] = None
    workflow_state: dict[str, Any] = field(default_factory=dict)

    # ── Workflow state helpers ────────────────────────────────────────

    def get_adopt_state(self) -> dict[str, Any]:
        """Return the adopt step sub-dict from workflow_state (empty dict if missing)."""
        return self.workflow_state.get("adopt", {})

    def set_adopt_state(
        self,
        *,
        complete: bool,
        skipped: bool = False,
        imported_count: int = 0,
        completed_at: str = "",
    ) -> None:
        """Record adopt step outcome in workflow_state (caller must save the intent)."""
        from datetime import datetime

        self.workflow_state["adopt"] = {
            "complete": complete,
            "skipped": skipped,
            "imported_count": imported_count,
            "completed_at": completed_at or datetime.utcnow().isoformat() + "Z",
        }

    def clear_adopt_state(self) -> None:
        """Remove adopt state from workflow_state (caller must save the intent)."""
        self.workflow_state.pop("adopt", None)

    @property
    def retained_keys(self) -> set[str]:
        return {
            k
            for k, d in self.dispositions.items()
            if d.disposition == DISP_RETAINED
        }

    @property
    def upserted_keys(self) -> set[str]:
        return {
            k
            for k, d in self.dispositions.items()
            if d.disposition == DISP_UPSERTED
        }

    @property
    def adopted_keys(self) -> set[str]:
        return {
            k
            for k, d in self.dispositions.items()
            if d.disposition == DISP_ADOPTED
        }

    @property
    def removed_keys(self) -> set[str]:
        return {
            k
            for k, d in self.dispositions.items()
            if d.disposition == DISP_REMOVED
        }

    @property
    def orphan_flagged_keys(self) -> set[str]:
        return {
            k
            for k, d in self.dispositions.items()
            if d.disposition == DISP_ORPHAN_FLAGGED
        }

    @property
    def orphan_retained_keys(self) -> set[str]:
        return {
            k
            for k, d in self.dispositions.items()
            if d.disposition == DISP_ORPHAN_RETAINED
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "computed_at": self.computed_at,
            "provenance": {
                "tf_state_path": self.tf_state_path,
                "source_focus_path": self.source_focus_path,
                "source_focus_base_folder": self.source_focus_base_folder,
                "baseline_path": self.baseline_path,
            },
            "dispositions": {k: v.to_dict() for k, v in self.dispositions.items()},
            "match_mappings": self.match_mappings.to_dict(),
            "tf_state_keys": list(
                {k for k, d in self.dispositions.items() if d.tf_state_address}
            ),
            "retained_keys": list(self.retained_keys),
            "upserted_keys": list(self.upserted_keys),
            "adopted_keys": list(self.adopted_keys),
            "removed_keys": list(self.removed_keys),
            "orphan_flagged_keys": list(self.orphan_flagged_keys),
            "orphan_retained_keys": list(self.orphan_retained_keys),
            "coverage_warnings": self.coverage_warnings,
            "drift_warnings": self.drift_warnings,
            "workflow_state": self.workflow_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TargetIntentResult:
        dispositions = {}
        for k, v in data.get("dispositions", {}).items():
            dispositions[k] = ResourceDisposition.from_dict({**v, "key": k})
        # Version 1 files have no match_mappings; default to empty MatchMappings
        raw_mm = data.get("match_mappings")
        if isinstance(raw_mm, dict) and ("source_to_target" in raw_mm or "state_to_target" in raw_mm):
            match_mappings = MatchMappings.from_dict(raw_mm)
        else:
            match_mappings = MatchMappings()
        return cls(
            version=data.get("version", 1),
            computed_at=data.get("computed_at", ""),
            dispositions=dispositions,
            match_mappings=match_mappings,
            output_config=data.get("output_config", {}),
            coverage_warnings=data.get("coverage_warnings", []),
            drift_warnings=data.get("drift_warnings", []),
            tf_state_path=data.get("provenance", {}).get("tf_state_path"),
            source_focus_path=data.get("provenance", {}).get("source_focus_path"),
            source_focus_base_folder=(
                data.get("provenance", {}).get("source_focus_base_folder")
                or (
                    str(Path(data.get("provenance", {}).get("source_focus_path")).parent)
                    if data.get("provenance", {}).get("source_focus_path")
                    else None
                )
            ),
            baseline_path=data.get("provenance", {}).get("baseline_path"),
            workflow_state=data.get("workflow_state", {}),
        )


def get_tf_state_global_sections(tfstate_path: Path) -> dict[str, int]:
    """Return global section keys that have resources in TF state, with counts.

    Scans terraform.tfstate for resource types that map to global YAML sections
    (groups, service_tokens, notifications, webhooks, privatelink_endpoints).
    Connections and repositories are excluded since they are always included.

    Returns:
        dict mapping global section key -> resource instance count.
        E.g. {"groups": 3, "service_tokens": 1}
    """
    from importer.web.utils.terraform_state_reader import TF_TYPE_TO_GLOBAL_SECTION

    # Sections we're interested in for safety-net detection (exclude always-included)
    _safety_net_sections = {"groups", "service_tokens", "notifications", "webhooks", "privatelink_endpoints"}

    result: dict[str, int] = {}
    if not tfstate_path.exists():
        return result
    try:
        with open(tfstate_path, "r") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read Terraform state for global sections: {e}")
        return result

    resources = state.get("resources", [])
    for res in resources:
        tf_type = res.get("type", "")
        section = TF_TYPE_TO_GLOBAL_SECTION.get(tf_type)
        if section and section in _safety_net_sections:
            instance_count = len(res.get("instances", []))
            if instance_count > 0:
                result[section] = result.get(section, 0) + instance_count
    return result


def build_included_globals(state: Any) -> set[str]:
    """Build the included_globals set from state flags.

    Always includes connections and repositories (project dependencies).
    Adds groups, service_tokens, etc. based on state.map.include_* flags.

    Also auto-retains any global sections present in TF state to prevent
    accidental resource destruction (safety net).

    Args:
        state: AppState instance with map.include_* flags and deploy.terraform_dir.

    Returns:
        Set of global section keys to include in target intent output.
    """
    result = {"connections", "repositories"}  # always included

    # User selections from Configure page checkboxes
    if getattr(state.map, "include_groups", False):
        result.add("groups")
    if getattr(state.map, "include_service_tokens", False):
        result.add("service_tokens")
    # notifications/privatelink/webhooks: future — not yet manageable in TF
    # if getattr(state.map, "include_notifications", False):
    #     result.add("notifications")
    # if getattr(state.map, "include_webhooks", False):
    #     result.add("webhooks")

    # Safety net: auto-retain globals present in TF state
    tf_dir = getattr(state.deploy, "terraform_dir", None) or "deployments/migration"
    tf_path = Path(tf_dir)
    if not tf_path.is_absolute():
        # Resolve relative to project root (4 levels up from this file)
        project_root = Path(__file__).parent.parent.parent.parent.resolve()
        tf_path = project_root / tf_path
    tfstate_path = tf_path / "terraform.tfstate"

    if tfstate_path.exists():
        tf_globals = get_tf_state_global_sections(tfstate_path)
        for section, count in tf_globals.items():
            if section not in result:
                logger.warning(
                    "Auto-retaining globals.%s (%d resource(s) in TF state) "
                    "despite not being selected — prevents destruction",
                    section,
                    count,
                )
                result.add(section)

    # region agent log
    _dbg_db419a(
        "H70",
        "target_intent.py:build_included_globals",
        "resolved included global sections for target intent",
        {
            "included_globals": sorted(list(result)),
            "include_groups_flag": bool(getattr(state.map, "include_groups", False)),
            "include_service_tokens_flag": bool(getattr(state.map, "include_service_tokens", False)),
        },
    )
    # endregion
    return result


def get_tf_state_project_keys(tfstate_path: Path) -> set[str]:
    """Parse terraform.tfstate JSON and return all managed project keys.

    Looks for resources with type=dbtcloud_project, name=projects or
    name=protected_projects and collects index_key from each instance.
    Fast JSON parse, no subprocess.
    """
    keys: set[str] = set()
    if not tfstate_path.exists():
        logger.warning(f"Terraform state file not found: {tfstate_path}")
        return keys
    try:
        with open(tfstate_path, "r") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read Terraform state: {e}")
        return keys

    resources = state.get("resources", [])
    for res in resources:
        if res.get("type") != "dbtcloud_project":
            continue
        if res.get("name") not in ("projects", "protected_projects"):
            continue
        for inst in res.get("instances", []):
            idx = inst.get("index_key")
            if idx is not None:
                keys.add(str(idx))
    return keys


def get_tf_state_protected_project_keys(tfstate_path: Path) -> set[str]:
    """Return project keys that are protected in TF state (name=protected_projects)."""
    keys: set[str] = set()
    if not tfstate_path.exists():
        return keys
    try:
        with open(tfstate_path, "r") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read Terraform state for protection: {e}")
        return keys

    resources = state.get("resources", [])
    for res in resources:
        if res.get("type") != "dbtcloud_project" or res.get("name") != "protected_projects":
            continue
        for inst in res.get("instances", []):
            idx = inst.get("index_key")
            if idx is not None:
                keys.add(str(idx))
    return keys


def _project_keys_in_target_fetch(target_report_items: Optional[list[dict]]) -> set[str]:
    """Extract project keys (element_mapping_id or name) for type PRJ from target report items."""
    keys: set[str] = set()
    if not target_report_items:
        return keys
    for item in target_report_items:
        code = item.get("element_type_code") or item.get("type") or item.get("resource_type")
        if code != "PRJ":
            continue
        # Prefer element_mapping_id (project key), fallback to name
        key = item.get("element_mapping_id") or item.get("name") or item.get("source_key")
        if key:
            keys.add(str(key))
    return keys


def _prune_globals_to_project_references(config: dict[str, Any]) -> tuple[int, int, int, int]:
    """Prune global sections to only resources referenced by kept projects.

    Returns a tuple of:
    (connections_before, connections_after, repositories_before, repositories_after)
    """
    if not isinstance(config, dict):
        return (0, 0, 0, 0)
    globals_obj = config.get("globals")
    projects = config.get("projects") or []
    if not isinstance(globals_obj, dict) or not isinstance(projects, list):
        return (0, 0, 0, 0)

    referenced_connections: set[str] = set()
    referenced_repositories: set[str] = set()
    for project in projects:
        if not isinstance(project, dict):
            continue
        repo_key = project.get("repository")
        if repo_key:
            referenced_repositories.add(str(repo_key))
        for env in project.get("environments", []) or []:
            if not isinstance(env, dict):
                continue
            conn_key = env.get("connection")
            if conn_key:
                referenced_connections.add(str(conn_key))
        for profile in project.get("profiles", []) or []:
            if not isinstance(profile, dict):
                continue
            conn_key = profile.get("connection_key")
            if conn_key:
                referenced_connections.add(str(conn_key))

    connections = globals_obj.get("connections") or []
    repositories = globals_obj.get("repositories") or []
    conn_before = len(connections) if isinstance(connections, list) else 0
    repo_before = len(repositories) if isinstance(repositories, list) else 0

    if isinstance(connections, list):
        globals_obj["connections"] = [
            c for c in connections
            if isinstance(c, dict) and str(c.get("key", "")) in referenced_connections
        ]
    if isinstance(repositories, list):
        globals_obj["repositories"] = [
            r for r in repositories
            if isinstance(r, dict) and str(r.get("key", "")) in referenced_repositories
        ]

    conn_after = len(globals_obj.get("connections") or []) if isinstance(globals_obj.get("connections"), list) else 0
    repo_after = len(globals_obj.get("repositories") or []) if isinstance(globals_obj.get("repositories"), list) else 0
    return (conn_before, conn_after, repo_before, repo_after)


def compute_target_intent(
    tfstate_path: Path,
    source_focus_yaml: str,
    baseline_yaml: Optional[str],
    target_report_items: Optional[list[dict]],
    adopt_rows: list[dict],
    removal_keys: set[str],
    previous_intent: Optional[TargetIntentResult] = None,
    protection_intent_manager: Optional[Any] = None,
    included_globals: Optional[set[str]] = None,
) -> TargetIntentResult:
    """Compute the complete target intent.

    Args:
        included_globals: Explicit set of global section keys to include in output_config.
            Only these sections will be kept under ``globals`` in the merged YAML.
            Default (None) keeps only ``connections`` and ``repositories`` (project
            dependencies).  Other sections (``groups``, ``service_tokens``,
            ``notifications``, ``privatelink_endpoints``, ``webhooks``) are stripped
            unless explicitly listed here.

    Algorithm:
    1. Read all project keys from terraform.tfstate -> default disposition retained.
    2. Cross-reference with target fetch: keys in state but not in target -> orphan_flagged.
    3. Apply removal_keys -> disposition removed (excluded from output).
    4. Build baseline config from baseline_yaml (or empty).
    5. Upsert source focus into baseline (source focus wins) -> upserted for those keys.
    6. Add adopted project keys from adopt_rows -> adopted.
    7. Preserve confirmed dispositions from previous_intent.
    8. Build output_config via merge_yaml_configs(baseline, source_focus).
    9. Apply protection priority chain (default -> TF state -> protection intent -> user edit).
    10. Validate coverage.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_focus_base_folder = str(Path(source_focus_yaml).parent) if source_focus_yaml else ""
    # region agent log
    _dbg_db419a(
        "H20",
        "target_intent.py:compute_target_intent",
        "compute_target_intent called with source focus provenance",
        {
            "source_focus_yaml": source_focus_yaml,
            "source_focus_base_folder": source_focus_base_folder,
            "baseline_yaml": baseline_yaml,
            "adopt_rows_count": len(adopt_rows),
            "removal_keys_count": len(removal_keys),
        },
    )
    # endregion
    tf_state_keys = get_tf_state_project_keys(tfstate_path)
    target_project_keys = _project_keys_in_target_fetch(target_report_items)
    # Only treat "not in target" as orphan when key spaces align: at least one TF state key
    # must appear in target report. Otherwise (e.g. target report uses different naming)
    # we would falsely orphan retained projects.
    orphan_detection_active = (
        target_report_items is not None
        and target_project_keys is not None
        and len(target_project_keys) > 0
        and bool(tf_state_keys & target_project_keys)
    )

    # Load configs
    source_config: dict[str, Any] = {}
    if source_focus_yaml and Path(source_focus_yaml).exists():
        try:
            with open(source_focus_yaml, "r") as f:
                source_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load source focus YAML: {e}")

    baseline_config: dict[str, Any] = {}
    if baseline_yaml and Path(baseline_yaml).exists():
        try:
            with open(baseline_yaml, "r") as f:
                baseline_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load baseline YAML: {e}")

    # region agent log
    _dbg_db419a(
        "H71",
        "target_intent.py:compute_target_intent",
        "loaded source and baseline config shape",
        {
            "source_projects_count": len(source_config.get("projects", []) if isinstance(source_config, dict) else []),
            "source_globals_connections_count": len(
                (((source_config.get("globals") or {}).get("connections")) or [])
                if isinstance(source_config, dict)
                else []
            ),
            "baseline_projects_count": len(baseline_config.get("projects", []) if isinstance(baseline_config, dict) else []),
            "baseline_globals_connections_count": len(
                (((baseline_config.get("globals") or {}).get("connections")) or [])
                if isinstance(baseline_config, dict)
                else []
            ),
            "baseline_globals_jobs_count": len(
                (((baseline_config.get("globals") or {}).get("jobs")) or [])
                if isinstance(baseline_config, dict)
                else []
            ),
        },
    )
    # endregion

    source_focus_project_keys = {p.get("key") for p in source_config.get("projects", []) if p.get("key")}
    adopted_project_keys: set[str] = set()
    for row in adopt_rows:
        if (row.get("source_type") or "").strip() == "PRJ":
            key = row.get("source_key") or row.get("source_name")
            if key:
                adopted_project_keys.add(str(key))

    # Dispositions: start from TF state as floor
    dispositions: dict[str, ResourceDisposition] = {}
    for key in tf_state_keys:
        if key in removal_keys:
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_REMOVED,
                source="removal_intent",
                config_preference="target",
            )
        elif orphan_detection_active and key not in target_project_keys:
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_ORPHAN_FLAGGED,
                source="orphan_detection",
                config_source=baseline_yaml,
                config_preference="target",
            )
        elif key in source_focus_project_keys:
            # Project is in both TF state AND source focus -- it's being upserted
            # but since it already exists on target, prefer target values for
            # sub-resources (repos, envs) unless user explicitly overrides
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_UPSERTED,
                source="source_focus",
                config_source=source_focus_yaml,
                config_preference="source",
            )
        else:
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_RETAINED,
                source="tf_state_default",
                config_source=baseline_yaml,
                config_preference="target",
            )

    # Add source focus projects not in TF state (new)
    for key in source_focus_project_keys:
        if key not in dispositions:
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_UPSERTED,
                source="source_focus",
                config_source=source_focus_yaml,
                config_preference="source",
            )

    # Adopted (from adopt_rows, usually already in source_focus; mark as adopted if not in state)
    for key in adopted_project_keys:
        if key not in tf_state_keys and key not in dispositions:
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_ADOPTED,
                source="adopt_rows",
                config_preference="target",
            )

    # Preserve confirmed dispositions from previous intent
    if previous_intent:
        for k, d in previous_intent.dispositions.items():
            if d.confirmed and k in dispositions:
                dispositions[k] = ResourceDisposition(
                    key=k,
                    resource_type=d.resource_type,
                    disposition=d.disposition,
                    source=d.source,
                    config_source=d.config_source,
                    tf_state_address=d.tf_state_address,
                    confirmed=True,
                    confirmed_at=d.confirmed_at,
                    config_preference=d.config_preference,
                )

    # Protection priority chain: default < TF state < protection intent < user edit
    # Level 1: Default - all unprotected
    for key, disp in dispositions.items():
        disp.protected = False
        disp.protection_set_by = "default_unprotected"

    # Level 2: TF state override - protected_projects resource name means protected
    tf_state_protected_keys = get_tf_state_protected_project_keys(tfstate_path)
    for key in tf_state_protected_keys:
        if key in dispositions:
            dispositions[key].protected = True
            dispositions[key].protection_set_by = "tf_state_default"

    # Level 3: Protection intent file override
    if protection_intent_manager:
        for key, disp in dispositions.items():
            # Try both unprefixed and PRJ-prefixed keys
            intent = protection_intent_manager.get_intent(key)
            if intent is None:
                intent = protection_intent_manager.get_intent(f"PRJ:{key}")
            if intent is not None:
                disp.protected = intent.protected
                disp.protection_set_by = "protection_intent"

    # Level 4: User edits from previous target intent (highest priority)
    if previous_intent:
        for k, prev_disp in previous_intent.dispositions.items():
            if k in dispositions and prev_disp.protection_set_by == "user":
                dispositions[k].protected = prev_disp.protected
                dispositions[k].protection_set_by = prev_disp.protection_set_by
                dispositions[k].protection_set_at = prev_disp.protection_set_at

    # Merged config: baseline + source focus (source wins). Exclude removed and orphan_flagged from output.
    include_keys = {
        k for k, d in dispositions.items()
        if d.disposition not in (DISP_REMOVED, DISP_ORPHAN_FLAGGED)
    }
    merged = merge_yaml_configs(baseline_config, source_config)
    # region agent log
    _dbg_db419a(
        "H21",
        "target_intent.py:compute_target_intent",
        "merged output_config base-folder fields snapshot",
        {
            "has_output_metadata": isinstance(merged.get("metadata"), dict),
            "metadata_keys": sorted(list(merged.get("metadata", {}).keys()))
            if isinstance(merged.get("metadata"), dict)
            else [],
            "has_base_folder": "base_folder" in merged,
            "has_project_base_folder": any(
                isinstance(p, dict) and "base_folder" in p
                for p in merged.get("projects", [])
            ),
            "projects_count": len(merged.get("projects", [])),
        },
    )
    # endregion
    # Filter projects to only those we intend to keep
    all_projects = merged.get("projects", [])
    merged["projects"] = [p for p in all_projects if (p.get("key") or "") in include_keys]

    # Filter globals to only explicitly included sections.
    # Connections and repositories are kept by default (project dependencies).
    # Other global objects (groups, service_tokens, notifications, etc.) are
    # excluded unless the caller explicitly opts them in via included_globals.
    _default_globals = {"connections", "repositories"}
    _allowed_globals = included_globals if included_globals is not None else _default_globals
    if "globals" in merged and isinstance(merged["globals"], dict):
        stripped_keys = [k for k in merged["globals"] if k not in _allowed_globals]
        for k in stripped_keys:
            count = len(merged["globals"][k]) if isinstance(merged["globals"][k], list) else 1
            logger.info("Stripping globals.%s (%d item(s)) from output_config — not in included_globals", k, count)
            del merged["globals"][k]

    _conn_before_prune, _conn_after_prune, _repo_before_prune, _repo_after_prune = _prune_globals_to_project_references(merged)

    # region agent log
    _merged_connections = (
        (((merged.get("globals") or {}).get("connections")) or [])
        if isinstance(merged, dict)
        else []
    )
    _merged_conn_keys = [
        str(c.get("key", ""))
        for c in _merged_connections
        if isinstance(c, dict)
    ]
    _merged_jobs = (
        (((merged.get("globals") or {}).get("jobs")) or [])
        if isinstance(merged, dict)
        else []
    )
    _dbg_db419a(
        "H72",
        "target_intent.py:compute_target_intent",
        "post-filter merged globals footprint",
        {
            "allowed_globals": sorted(list(_allowed_globals)),
            "merged_globals_connections_count": len(_merged_connections),
            "merged_globals_jobs_count": len(_merged_jobs),
            "project_ref_prune": {
                "connections_before": _conn_before_prune,
                "connections_after": _conn_after_prune,
                "repositories_before": _repo_before_prune,
                "repositories_after": _repo_after_prune,
            },
            "merged_connection_keys_sample": sorted(_merged_conn_keys)[:40],
            "merged_non_conn_prefix_sample": sorted(
                [k for k in _merged_conn_keys if not k.startswith("conn_sse")]
            )[:40],
        },
    )
    # endregion

    coverage_warnings: list[str] = []
    for key in tf_state_keys:
        if key in removal_keys:
            continue
        if key not in include_keys:
            coverage_warnings.append(f"TF state project '{key}' is excluded (removed or orphan_flagged)")
    for key in include_keys:
        if key not in {p.get("key") for p in merged.get("projects", [])} and key in tf_state_keys:
            coverage_warnings.append(f"Project '{key}' is in TF state but has no config in merged YAML")

    # Preserve match_mappings from previous intent (user decisions persist)
    preserved_mappings = previous_intent.match_mappings if previous_intent else MatchMappings()

    return TargetIntentResult(
        version=2,
        computed_at=now,
        dispositions=dispositions,
        match_mappings=preserved_mappings,
        output_config=merged,
        coverage_warnings=coverage_warnings,
        drift_warnings=[],
        tf_state_path=str(tfstate_path) if tfstate_path else None,
        source_focus_path=source_focus_yaml or None,
        source_focus_base_folder=source_focus_base_folder or None,
        baseline_path=baseline_yaml or None,
    )


def validate_intent_coverage(
    intent: TargetIntentResult,
    tf_state_keys: set[str],
    removal_keys: set[str],
) -> list[str]:
    """Validate that every TF state key is accounted for. Returns list of warnings."""
    warnings: list[str] = []
    accounted = removal_keys | intent.retained_keys | intent.upserted_keys | intent.adopted_keys | intent.orphan_flagged_keys | intent.orphan_retained_keys
    for key in tf_state_keys:
        if key not in accounted:
            warnings.append(f"TF state project '{key}' has no disposition")
    return warnings


def normalize_target_fetch(state: Any) -> Optional[str]:
    """Lazily normalize target fetch data to produce a full-account baseline YAML.

    Uses the same normalizer as the Scope step but applied to the target fetch snapshot.
    Result is cached in state.target_fetch.target_baseline_yaml.

    Args:
        state: AppState instance with target_fetch.last_fetch_file populated.

    Returns:
        Path to the normalized YAML, or None if target fetch data is unavailable.
    """
    # Check if already cached and file still exists
    cached = getattr(state.target_fetch, "target_baseline_yaml", None)
    if cached and Path(cached).exists():
        return cached

    fetch_file = getattr(state.target_fetch, "last_fetch_file", None)
    if not fetch_file or not Path(fetch_file).exists():
        logger.warning("Cannot normalize target fetch: no last_fetch_file available")
        return None

    try:
        # Import the normalizer function (same one used by Scope step)
        from importer.web.pages.mapping import _do_normalize

        output_dir = getattr(state.target_fetch, "output_dir", "dev_support/samples/target")
        result = _do_normalize(
            input_file=fetch_file,
            exclude_by_type={},  # No exclusions — include everything
            output_dir=output_dir,
        )
        yaml_path = result.get("yaml_file")
        if yaml_path:
            state.target_fetch.target_baseline_yaml = yaml_path
            logger.info(f"Normalized target fetch data -> {yaml_path}")
            return yaml_path
        else:
            logger.warning("Target fetch normalization produced no YAML file")
            return None
    except Exception as e:
        logger.warning(f"Failed to normalize target fetch data: {e}")
        return None


class TargetIntentManager:
    """Load/save target intent artifact and write merged YAML."""

    def __init__(self, deployment_dir: Path):
        self.deployment_dir = Path(deployment_dir)
        self.intent_path = self.deployment_dir / "target-intent.json"
        self.merged_path = self.deployment_dir / "dbt-cloud-config-merged.yml"

    def load(self) -> Optional[TargetIntentResult]:
        """Load target intent from target-intent.json if it exists.

        output_config is restored from the file (self-contained state file).
        """
        if not self.intent_path.exists():
            # region agent log
            _dbg_db419a(
                "H32",
                "target_intent.py:TargetIntentManager.load",
                "target intent file missing at resolved path",
                {
                    "deployment_dir": str(self.deployment_dir),
                    "intent_path": str(self.intent_path),
                },
            )
            # endregion
            return None
        try:
            with open(self.intent_path, "r") as f:
                data = json.load(f)
            result = TargetIntentResult.from_dict(data)
            # region agent log
            _dbg_db419a(
                "H32",
                "target_intent.py:TargetIntentManager.load",
                "loaded target intent from resolved path",
                {
                    "deployment_dir": str(self.deployment_dir),
                    "intent_path": str(self.intent_path),
                    "source_focus_base_folder": result.source_focus_base_folder,
                    "source_focus_path": result.source_focus_path,
                },
            )
            # endregion
            return result
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load target intent: {e}")
            return None

    def save(self, intent: TargetIntentResult) -> None:
        """Persist target intent to target-intent.json (self-contained: includes output_config)."""
        _conn_before = _conn_after = _repo_before = _repo_after = 0
        if isinstance(intent.output_config, dict):
            _conn_before, _conn_after, _repo_before, _repo_after = _prune_globals_to_project_references(intent.output_config)
            # region agent log
            _dbg_db419a(
                "H73",
                "target_intent.py:TargetIntentManager.save",
                "pruned globals to project references before save",
                {
                    "connections_before": _conn_before,
                    "connections_after": _conn_after,
                    "repositories_before": _repo_before,
                    "repositories_after": _repo_after,
                },
            )
            # endregion
        data = intent.to_dict()
        # Include output_config for self-contained state file
        if intent.output_config:
            data["output_config"] = intent.output_config
        # region agent log
        _dbg_db419a(
            "H22",
            "target_intent.py:TargetIntentManager.save",
            "saving target intent with provenance and output_config shape",
            {
                "deployment_dir": str(self.deployment_dir),
                "intent_path": str(self.intent_path),
                "source_focus_path": intent.source_focus_path,
                "source_focus_base_folder": intent.source_focus_base_folder,
                "has_output_config": bool(intent.output_config),
                "has_output_metadata": isinstance(intent.output_config.get("metadata"), dict)
                if isinstance(intent.output_config, dict)
                else False,
                "has_output_base_folder": "base_folder" in intent.output_config
                if isinstance(intent.output_config, dict)
                else False,
            },
        )
        # endregion
        try:
            self.deployment_dir.mkdir(parents=True, exist_ok=True)
            with open(self.intent_path, "w") as f:
                json.dump(data, f, indent=2, sort_keys=False)
        except OSError as e:
            logger.warning(f"Failed to save target intent: {e}")

    def write_merged_yaml(self, intent: TargetIntentResult) -> str:
        """Write intent.output_config to dbt-cloud-config-merged.yml; return path."""
        with open(self.merged_path, "w") as f:
            yaml.dump(
                intent.output_config,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
        return str(self.merged_path)

    def sync_protection_to_disposition(
        self,
        resource_key: str,
        protected: bool,
    ) -> bool:
        """Update a disposition's protected field after a protection intent edit.

        Called AFTER ProtectionIntentManager.set_intent() writes to protection-intent.json.
        Loads the persisted target intent, updates the matching disposition, and saves.

        Args:
            resource_key: The resource key (may be prefixed like "PRJ:key" or unprefixed).
            protected: The new protection value.

        Returns:
            True if a disposition was found and updated, False otherwise.
        """
        intent = self.load()
        if intent is None:
            return False

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Try unprefixed key first, then strip prefix
        bare_key = resource_key.split(":", 1)[1] if ":" in resource_key else resource_key
        updated = False

        for key in (bare_key, resource_key):
            if key in intent.dispositions:
                intent.dispositions[key].protected = protected
                intent.dispositions[key].protection_set_by = "user"
                intent.dispositions[key].protection_set_at = now
                updated = True
                break

        if updated:
            self.save(intent)
        return updated
