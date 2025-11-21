"""YAML writer and artifact generation for normalized data."""

from __future__ import annotations

import json
import logging
from datetime import datetime as dt
from pathlib import Path
from typing import Any, Dict

import yaml

from . import MappingConfig, NormalizationContext

log = logging.getLogger(__name__)


class YAMLWriter:
    """Handles YAML serialization and artifact generation."""

    def __init__(self, config: MappingConfig, context: NormalizationContext):
        self.config = config
        self.context = context

    def write_all_artifacts(
        self,
        normalized_data: Dict[str, Any],
        output_dir: Path,
        run_id: int,
        timestamp: str,
        account_id: int,
    ) -> Dict[str, Path]:
        """
        Write all normalization artifacts (YAML, manifests, logs).
        
        Returns a dict mapping artifact type to file path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        artifacts = {}
        
        # Write main YAML file
        yaml_path = self._write_yaml(normalized_data, output_dir, run_id, timestamp, account_id)
        artifacts["yaml"] = yaml_path
        log.info(f"Wrote YAML to {yaml_path}")
        
        # Write manifests if configured
        if self.config.should_generate_lookups_manifest():
            lookups_path = self._write_lookups_manifest(output_dir, run_id, timestamp, account_id)
            artifacts["lookups"] = lookups_path
            log.info(f"Wrote lookups manifest to {lookups_path}")
        
        if self.config.should_generate_exclusions_report():
            exclusions_path = self._write_exclusions_report(output_dir, run_id, timestamp, account_id)
            artifacts["exclusions"] = exclusions_path
            log.info(f"Wrote exclusions report to {exclusions_path}")
        
        if self.config.should_generate_diff_json():
            diff_path = self._write_diff_json(normalized_data, output_dir, run_id, timestamp, account_id)
            artifacts["diff_json"] = diff_path
            log.info(f"Wrote diff JSON to {diff_path}")
        
        return artifacts

    def _write_yaml(
        self,
        data: Dict[str, Any],
        output_dir: Path,
        run_id: int,
        timestamp: str,
        account_id: int,
    ) -> Path:
        """Write normalized data to YAML file."""
        base_filename = self.config.get_yaml_filename()
        filename = f"account_{account_id}_norm_{run_id:03d}__yaml__{timestamp}.yml"
        output_path = output_dir / filename
        
        # Add metadata comment header
        header_lines = [
            f"# dbt Cloud Configuration (v2 Schema)",
            f"# Generated: {dt.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"# Normalization Run: {run_id:03d}",
            f"# Source Account: {account_id}",
            "",
        ]
        
        # Serialize to YAML with custom options
        yaml_output = yaml.dump(
            data,
            default_flow_style=False,
            sort_keys=self.config.should_sort_keys(),
            indent=self.config.get_yaml_indent(),
            width=self.config.get_yaml_line_length(),
            allow_unicode=True,
        )
        
        # Combine header and YAML
        full_output = "\n".join(header_lines) + yaml_output
        
        output_path.write_text(full_output, encoding="utf-8")
        return output_path

    def _write_lookups_manifest(
        self,
        output_dir: Path,
        run_id: int,
        timestamp: str,
        account_id: int,
    ) -> Path:
        """Write manifest of LOOKUP placeholders that need manual resolution."""
        filename = f"account_{account_id}_norm_{run_id:03d}__lookups__{timestamp}.json"
        output_path = output_dir / filename
        
        manifest = {
            "_metadata": {
                "generated_at": dt.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat() + "Z",
                "run_id": run_id,
                "account_id": account_id,
                "total_placeholders": len(self.context.placeholders),
            },
            "placeholders": self.context.placeholders,
            "instructions": (
                "This file lists all LOOKUP: placeholders in the generated YAML. "
                "Each placeholder represents a resource that must exist in the target account. "
                "To resolve: 1) Create the resource in target if it doesn't exist, "
                "2) Note its ID or key, 3) Update the YAML to reference it."
            ),
        }
        
        output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return output_path

    def _write_exclusions_report(
        self,
        output_dir: Path,
        run_id: int,
        timestamp: str,
        account_id: int,
    ) -> Path:
        """Write report of excluded/filtered resources."""
        filename = f"account_{account_id}_norm_{run_id:03d}__exclusions__{timestamp}.md"
        output_path = output_dir / filename
        
        lines = [
            "# Normalization Exclusions Report",
            "",
            f"**Generated:** {dt.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Normalization Run:** {run_id:03d}",
            f"**Source Account:** {account_id}",
            "",
            "## Summary",
            "",
            f"**Total Exclusions:** {len(self.context.exclusions)}",
            "",
        ]
        
        if not self.context.exclusions:
            lines.append("*No resources were excluded during normalization.*")
        else:
            # Group by resource type
            by_type: Dict[str, list] = {}
            for exclusion in self.context.exclusions:
                resource_type = exclusion["resource_type"]
                if resource_type not in by_type:
                    by_type[resource_type] = []
                by_type[resource_type].append(exclusion)
            
            # Count by reason
            by_reason: Dict[str, int] = {}
            for exclusion in self.context.exclusions:
                reason = exclusion["reason"]
                by_reason[reason] = by_reason.get(reason, 0) + 1
            
            lines.extend([
                "### By Resource Type",
                "",
            ])
            for resource_type in sorted(by_type.keys()):
                lines.append(f"- **{resource_type}:** {len(by_type[resource_type])}")
            
            lines.extend([
                "",
                "### By Reason",
                "",
            ])
            for reason in sorted(by_reason.keys(), key=lambda r: by_reason[r], reverse=True):
                lines.append(f"- **{reason}:** {by_reason[reason]}")
            
            lines.extend([
                "",
                "---",
                "",
                "## Detailed Exclusions",
                "",
            ])
            
            for resource_type in sorted(by_type.keys()):
                lines.extend([
                    f"### {resource_type.replace('_', ' ').title()}",
                    "",
                    "| Key | Element Mapping ID | Reason |",
                    "|-----|-------------------|--------|",
                ])
                for exclusion in by_type[resource_type]:
                    key = exclusion["key"]
                    element_id = exclusion["element_mapping_id"] or "N/A"
                    reason = exclusion["reason"]
                    lines.append(f"| `{key}` | `{element_id}` | {reason} |")
                lines.append("")
        
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    def _write_diff_json(
        self,
        data: Dict[str, Any],
        output_dir: Path,
        run_id: int,
        timestamp: str,
        account_id: int,
    ) -> Path:
        """Write diff-friendly JSON for regression testing."""
        filename = f"account_{account_id}_norm_{run_id:03d}__diff__{timestamp}.json"
        output_path = output_dir / filename
        
        # Add metadata
        diff_data = {
            "_metadata": {
                "generated_at": dt.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat() + "Z",
                "run_id": run_id,
                "account_id": account_id,
                "purpose": "Diff-friendly JSON for regression testing normalized YAML output",
            },
            "normalized": data,
        }
        
        # Write with consistent sorting for diffs
        output_path.write_text(json.dumps(diff_data, indent=2, sort_keys=True), encoding="utf-8")
        return output_path

