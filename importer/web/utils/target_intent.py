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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from importer.web.utils.adoption_yaml_updater import merge_yaml_configs

logger = logging.getLogger(__name__)

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
    baseline_path: Optional[str] = None

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
            baseline_path=data.get("provenance", {}).get("baseline_path"),
        )


def get_tf_state_project_keys(tfstate_path: Path) -> set[str]:
    """Parse terraform.tfstate JSON and return all managed project keys.

    Looks for resources with type=dbtcloud_project, name=projects and
    collects index_key from each instance. Fast JSON parse, no subprocess.
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
        if res.get("type") != "dbtcloud_project" or res.get("name") != "projects":
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


def compute_target_intent(
    tfstate_path: Path,
    source_focus_yaml: str,
    baseline_yaml: Optional[str],
    target_report_items: Optional[list[dict]],
    adopt_rows: list[dict],
    removal_keys: set[str],
    previous_intent: Optional[TargetIntentResult] = None,
) -> TargetIntentResult:
    """Compute the complete target intent.

    Algorithm:
    1. Read all project keys from terraform.tfstate -> default disposition retained.
    2. Cross-reference with target fetch: keys in state but not in target -> orphan_flagged.
    3. Apply removal_keys -> disposition removed (excluded from output).
    4. Build baseline config from baseline_yaml (or empty).
    5. Upsert source focus into baseline (source focus wins) -> upserted for those keys.
    6. Add adopted project keys from adopt_rows -> adopted.
    7. Preserve confirmed dispositions from previous_intent.
    8. Build output_config via merge_yaml_configs(baseline, source_focus).
    9. Validate coverage.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
            )
        elif orphan_detection_active and key not in target_project_keys:
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_ORPHAN_FLAGGED,
                source="orphan_detection",
                config_source=baseline_yaml,
            )
        elif key in source_focus_project_keys:
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_UPSERTED,
                source="source_focus",
                config_source=source_focus_yaml,
            )
        else:
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_RETAINED,
                source="tf_state_default",
                config_source=baseline_yaml,
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
            )

    # Adopted (from adopt_rows, usually already in source_focus; mark as adopted if not in state)
    for key in adopted_project_keys:
        if key not in tf_state_keys and key not in dispositions:
            dispositions[key] = ResourceDisposition(
                key=key,
                resource_type="PRJ",
                disposition=DISP_ADOPTED,
                source="adopt_rows",
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
                )

    # Merged config: baseline + source focus (source wins). Exclude removed and orphan_flagged from output.
    include_keys = {
        k for k, d in dispositions.items()
        if d.disposition not in (DISP_REMOVED, DISP_ORPHAN_FLAGGED)
    }
    merged = merge_yaml_configs(baseline_config, source_config)
    # Filter projects to only those we intend to keep
    all_projects = merged.get("projects", [])
    merged["projects"] = [p for p in all_projects if (p.get("key") or "") in include_keys]

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


class TargetIntentManager:
    """Load/save target intent artifact and write merged YAML."""

    def __init__(self, deployment_dir: Path):
        self.deployment_dir = Path(deployment_dir)
        self.intent_path = self.deployment_dir / "target-intent.json"
        self.merged_path = self.deployment_dir / "dbt-cloud-config-merged.yml"

    def load(self) -> Optional[TargetIntentResult]:
        """Load target intent from target-intent.json if it exists."""
        if not self.intent_path.exists():
            return None
        try:
            with open(self.intent_path, "r") as f:
                data = json.load(f)
            # Don't restore output_config from file (recompute); keep dispositions for confirmed
            result = TargetIntentResult.from_dict(data)
            result.output_config = {}
            return result
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load target intent: {e}")
            return None

    def save(self, intent: TargetIntentResult) -> None:
        """Persist target intent to target-intent.json (metadata only; output_config lives in merged YAML)."""
        data = intent.to_dict()
        data.pop("output_config", None)
        try:
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
