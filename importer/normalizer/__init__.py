"""Normalization logic for converting importer JSON to v2 YAML."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml
from pydantic import BaseModel, Field

from ..models import AccountSnapshot

log = logging.getLogger(__name__)


class MappingConfig(BaseModel):
    """Mapping configuration loaded from importer_mapping.yml."""

    version: int
    scope: Dict[str, Any]
    resource_filters: Dict[str, Any] = Field(default_factory=dict)
    normalization_options: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "MappingConfig":
        """Load mapping config from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def get_scope_mode(self) -> str:
        return self.scope.get("mode", "all_projects")

    def get_project_keys(self) -> List[str]:
        return self.scope.get("project_keys", [])

    def get_project_ids(self) -> List[int]:
        return self.scope.get("project_ids", [])

    def is_resource_included(self, resource_type: str) -> bool:
        """Check if a resource type should be included."""
        filter_config = self.resource_filters.get(resource_type, {})
        return filter_config.get("include", True)

    def get_exclude_keys(self, resource_type: str) -> Set[str]:
        """Get set of keys to exclude for a resource type."""
        filter_config = self.resource_filters.get(resource_type, {})
        return set(filter_config.get("exclude_keys", []))

    def get_exclude_ids(self, resource_type: str) -> Set[str]:
        """Get set of element_mapping_ids to exclude for a resource type."""
        filter_config = self.resource_filters.get(resource_type, {})
        return set(filter_config.get("exclude_ids", []))

    def get_include_only_keys(self, resource_type: str) -> Set[str]:
        """Get whitelist of keys to include (empty = include all)."""
        filter_config = self.resource_filters.get(resource_type, {})
        return set(filter_config.get("include_only_keys", []))

    def should_strip_source_ids(self) -> bool:
        return self.normalization_options.get("strip_source_ids", True)

    def should_preserve_advisory_ids(self) -> bool:
        return self.normalization_options.get("preserve_advisory_ids", False)

    def get_placeholder_strategy(self) -> str:
        return self.normalization_options.get("placeholder_strategy", "lookup")

    def get_name_collision_strategy(self) -> str:
        return self.normalization_options.get("name_collision_strategy", "suffix")

    def get_secret_handling(self) -> str:
        return self.normalization_options.get("secret_handling", "redact")

    def get_multi_project_mode(self) -> str:
        return self.normalization_options.get("multi_project_mode", "single_file")

    def should_include_inactive(self) -> bool:
        return self.normalization_options.get("include_inactive", False)

    def get_yaml_indent(self) -> int:
        yaml_style = self.normalization_options.get("yaml_style", {})
        return yaml_style.get("indent", 2)

    def get_yaml_line_length(self) -> int:
        yaml_style = self.normalization_options.get("yaml_style", {})
        return yaml_style.get("line_length", 120)

    def should_sort_keys(self) -> bool:
        yaml_style = self.normalization_options.get("yaml_style", {})
        return yaml_style.get("sort_keys", False)

    def get_yaml_filename(self) -> str:
        return self.output.get("yaml_file", "dbt-config.yml")

    def get_output_directory(self) -> str:
        return self.output.get("output_directory", "dev_support/samples/normalized/")

    def should_generate_lookups_manifest(self) -> bool:
        manifests = self.output.get("generate_manifests", {})
        return manifests.get("lookups", True)

    def should_generate_exclusions_report(self) -> bool:
        manifests = self.output.get("generate_manifests", {})
        return manifests.get("exclusions", True)

    def should_generate_diff_json(self) -> bool:
        manifests = self.output.get("generate_manifests", {})
        return manifests.get("diff_json", True)


class NormalizationContext:
    """Tracks state during normalization (placeholders, collisions, exclusions)."""

    def __init__(self, config: MappingConfig):
        self.config = config
        self.placeholders: List[Dict[str, str]] = []
        self.exclusions: List[Dict[str, Any]] = []
        self.collisions: Dict[str, Dict[str, int]] = {}  # namespace -> (key -> count)
        self.element_id_to_key: Dict[str, str] = {}  # element_mapping_id -> key

    def add_placeholder(self, lookup_id: str, description: str) -> None:
        """Record a LOOKUP placeholder."""
        self.placeholders.append({"id": lookup_id, "description": description})
        log.info(f"Added placeholder: {lookup_id} - {description}")

    def add_exclusion(self, resource_type: str, key: str, reason: str, element_id: Optional[str] = None) -> None:
        """Record an excluded resource."""
        self.exclusions.append(
            {
                "resource_type": resource_type,
                "key": key,
                "element_mapping_id": element_id,
                "reason": reason,
            }
        )
        log.info(f"Excluded {resource_type} '{key}': {reason}")

    def resolve_collision(self, key: str, namespace: str = "global") -> str:
        """
        Resolve key collision by appending suffix within a specific namespace.
        
        Args:
            key: The key to check for collisions
            namespace: The resource namespace (connections, repositories, projects, etc.)
        
        Returns:
            The original key or a suffixed version if collision detected
        """
        if namespace not in self.collisions:
            self.collisions[namespace] = {}
        
        if key not in self.collisions[namespace]:
            self.collisions[namespace][key] = 1
            return key

        self.collisions[namespace][key] += 1
        collision_count = self.collisions[namespace][key]
        new_key = f"{key}_{collision_count}"
        log.warning(f"Key collision detected in '{namespace}': '{key}' -> '{new_key}'")
        return new_key

    def register_element(self, element_id: str, key: str) -> None:
        """Register an element mapping ID to its normalized key."""
        self.element_id_to_key[element_id] = key

    def resolve_element_reference(self, element_id: Optional[str]) -> Optional[str]:
        """Resolve an element_mapping_id to its normalized key."""
        if not element_id:
            return None
        return self.element_id_to_key.get(element_id)

