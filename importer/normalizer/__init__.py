"""Normalization logic for converting importer JSON to v2 YAML."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml
from pydantic import BaseModel, Field

from ..models import AccountSnapshot as AccountSnapshot

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

    @property
    def include_connection_details(self) -> bool:
        """Whether to include provider-specific connection details."""
        return self.normalization_options.get("include_connection_details", True)

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
        self.project_id_to_key: Dict[int, str] = {}  # numeric project ID -> project key
        self.repository_key_to_normalized: Dict[str, str] = {}  # original repository key -> normalized key
        self.connection_key_to_normalized: Dict[str, str] = {}  # original connection key -> normalized key

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

    def get_collision_summary(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get a summary of all key collisions detected during normalization.
        
        Returns:
            Dict mapping namespace to list of collision details:
            {
                "jobs": [
                    {"key": "my_job", "count": 2, "generated_keys": ["my_job", "my_job_2"]}
                ]
            }
        """
        summary: Dict[str, List[Dict[str, Any]]] = {}
        for namespace, keys in self.collisions.items():
            collisions_in_ns = []
            for key, count in keys.items():
                if count > 1:
                    # Generate the list of keys that were created
                    generated = [key] + [f"{key}_{i}" for i in range(2, count + 1)]
                    collisions_in_ns.append({
                        "key": key,
                        "count": count,
                        "generated_keys": generated,
                    })
            if collisions_in_ns:
                summary[namespace] = collisions_in_ns
        return summary

    def get_collision_count(self) -> int:
        """Get total number of collisions (resources with duplicate keys)."""
        total = 0
        for keys in self.collisions.values():
            for count in keys.values():
                if count > 1:
                    total += count - 1  # Each collision after the first
        return total

    def register_element(self, element_id: str, key: str) -> None:
        """Register an element mapping ID to its normalized key."""
        self.element_id_to_key[element_id] = key

    def resolve_element_reference(self, element_id: Optional[str]) -> Optional[str]:
        """Resolve an element_mapping_id to its normalized key."""
        if not element_id:
            return None
        return self.element_id_to_key.get(element_id)

    def register_project(self, project_id: int, key: str) -> None:
        """Register a numeric project ID to its normalized key."""
        self.project_id_to_key[project_id] = key
        log.debug(f"Registered project ID {project_id} -> key '{key}'")

    def resolve_project_id_to_key(self, project_id: Optional[int]) -> Optional[str]:
        """Resolve a numeric project ID to its normalized key."""
        if project_id is None:
            return None
        key = self.project_id_to_key.get(project_id)
        if key is None:
            log.warning(f"Project ID {project_id} not found in mapping - may cause apply errors")
        return key

    def register_repository_key(self, original_key: str, normalized_key: str) -> None:
        """Register mapping from original repository key to normalized key."""
        self.repository_key_to_normalized[original_key] = normalized_key
        log.debug(f"Registered repository key '{original_key}' -> '{normalized_key}'")

    def resolve_repository_key(self, repo_key: Optional[str]) -> Optional[str]:
        """Resolve original repository key to normalized key."""
        if not repo_key:
            return None
        normalized = self.repository_key_to_normalized.get(repo_key)
        if normalized:
            log.debug(f"Resolved repository key '{repo_key}' -> '{normalized}'")
        return normalized

    def register_connection_key(self, original_key: str, normalized_key: str) -> None:
        """Register mapping from original connection key to normalized key."""
        self.connection_key_to_normalized[original_key] = normalized_key
        log.debug(f"Registered connection key '{original_key}' -> '{normalized_key}'")

    def resolve_connection_key(self, conn_key: Optional[str]) -> Optional[str]:
        """Resolve original connection key to normalized key."""
        if not conn_key:
            return None
        normalized = self.connection_key_to_normalized.get(conn_key)
        if normalized:
            log.debug(f"Resolved connection key '{conn_key}' -> '{normalized}'")
        return normalized

