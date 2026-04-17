#!/usr/bin/env python3
"""
Detect drift between the dbtcloud Terraform provider schema and schemas/v1.json.

Findings:
  UNMAPPED            — provider arg not in resource_mapping.yml (blocking)
  MISSING_FROM_SCHEMA — registry says yaml but field absent from v1.json (blocking)
  MISSING_FROM_MODULE — registry says yaml but arg absent from module .tf files (blocking)
  STALE_YAML          — v1.json field not covered by any mapping (warning; blocking with --fail-on-stale)
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

SCHEMA_ONLY_FIELDS = {
    "key",
    "protected",
    "id",
    "connection",
    "primary_profile_key",
    "connection_key",
    "credential",
    "extended_attributes_key",
    "deferring_environment_key",
    "deferring_job_key",
    "notification_keys",
    "environment_variable_overrides",
    "cost_optimization_features",
}

PROVIDER_REGISTRY = "registry.terraform.io/dbt-labs/dbtcloud"


def get_provider_schema(terraform_dir: Path, cached_path: "Path | None") -> dict:
    if cached_path and cached_path.exists():
        print(f"Loading provider schema from cache: {cached_path}")
        return json.loads(cached_path.read_text())

    print("Running: terraform providers schema -json")
    result = subprocess.run(
        ["terraform", "providers", "schema", "-json"],
        cwd=terraform_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: terraform providers schema failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def extract_provider_args(raw_schema: dict) -> "dict[str, dict[str, set[str]]]":
    """Returns per-resource {"attributes": set, "block_types": set}."""
    provider_schemas = raw_schema.get("provider_schemas", {})
    provider = provider_schemas.get(PROVIDER_REGISTRY, {})
    resource_schemas = provider.get("resource_schemas", {})

    result: "dict[str, dict[str, set[str]]]" = {}
    for resource_name, resource_schema in resource_schemas.items():
        block = resource_schema.get("block", {})
        result[resource_name] = {
            "attributes": set(block.get("attributes", {}).keys()),
            "block_types": set(block.get("block_types", {}).keys()),
        }
    return result


def load_registry(mapping_path: Path) -> dict:
    return yaml.safe_load(mapping_path.read_text())


def load_module_tf(modules_root: Path, module_dir: str) -> str:
    """Concatenate all .tf file content from a module directory."""
    mod_path = modules_root / module_dir
    if not mod_path.is_dir():
        return ""
    return "\n".join(tf.read_text() for tf in sorted(mod_path.glob("*.tf")))


def load_schema_props(schema_path: Path) -> "dict[str, set[str]]":
    schema = json.loads(schema_path.read_text())
    defs = schema.get("$defs", {})
    return {
        key: set(defn.get("properties", {}).keys())
        for key, defn in defs.items()
    }


def run(ns: argparse.Namespace) -> int:
    mapping_path = Path(ns.mapping)
    schema_path = Path(ns.schema)
    terraform_dir = Path(ns.terraform_dir)
    modules_root = Path(ns.modules_dir)
    cached_path = Path(ns.provider_schema) if ns.provider_schema else None

    raw_schema = get_provider_schema(terraform_dir, cached_path)
    provider_args = extract_provider_args(raw_schema)

    registry = load_registry(mapping_path)
    resources = registry.get("resources", {})

    # Build classified: fields + nested_block names, so both count as "classified"
    classified: "dict[str, dict[str, dict]]" = {}
    yaml_field_claims: "dict[str, set[str]]" = {}
    # schema_only_by_defs: per-$defs-key fields exempt from STALE_YAML (cross-refs, sub-resources, etc.)
    schema_only_by_defs: "dict[str, set[str]]" = {}

    for resource_name, resource_cfg in resources.items():
        all_classified = dict(resource_cfg.get("fields", {}))
        all_classified.update({k: {} for k in resource_cfg.get("nested_blocks", {})})
        classified[resource_name] = all_classified

        defs_key = resource_cfg["yaml_defs_key"]
        coverage = resource_cfg.get("yaml_coverage", "")

        # Register schema_only_fields regardless of coverage mode
        for f in resource_cfg.get("schema_only_fields", []):
            schema_only_by_defs.setdefault(defs_key, set()).add(f)

        # Always build yaml_field_claims for explicit yaml fields — even for passthrough
        # resources — so connection.name etc. don't appear as STALE_YAML.
        claims = yaml_field_claims.setdefault(defs_key, set())
        for field_cfg in resource_cfg.get("fields", {}).values():
            if field_cfg.get("disposition") == "yaml":
                claims.add(field_cfg["yaml_field"])
        if coverage not in ("details_passthrough", "variable_passthrough"):
            for block_cfg in resource_cfg.get("nested_blocks", {}).values():
                if block_cfg.get("yaml_coverage") == "yaml":
                    claims.add(block_cfg["yaml_field"])

    schema_props = load_schema_props(schema_path)

    unmapped: "list[str]" = []
    missing_from_schema: "list[str]" = []
    missing_from_module: "list[str]" = []
    stale_yaml: "list[str]" = []

    # UNMAPPED: provider arg not classified in registry.
    # For details_passthrough resources, block_types are implicitly covered — skip them.
    for resource_name, arg_sets in provider_args.items():
        if resource_name not in classified:
            continue
        coverage = resources.get(resource_name, {}).get("yaml_coverage", "")
        args_to_check = set(arg_sets["attributes"])
        if coverage not in ("details_passthrough", "variable_passthrough"):
            args_to_check |= arg_sets["block_types"]
        for arg in sorted(args_to_check):
            if arg not in classified[resource_name]:
                unmapped.append(f"  {resource_name}.{arg}")

    # MISSING_FROM_SCHEMA: registry says yaml but field absent from v1.json
    for resource_name, resource_cfg in resources.items():
        coverage = resource_cfg.get("yaml_coverage", "")
        if coverage in ("details_passthrough", "variable_passthrough"):
            continue
        defs_key = resource_cfg["yaml_defs_key"]
        props = schema_props.get(defs_key, set())
        for arg, field_cfg in resource_cfg.get("fields", {}).items():
            if field_cfg.get("disposition") == "yaml":
                yaml_field = field_cfg["yaml_field"]
                if yaml_field not in props:
                    missing_from_schema.append(
                        f"  {resource_name}.{arg} → $defs/{defs_key}.{yaml_field} missing"
                    )

    # MISSING_FROM_MODULE: registry says yaml but provider arg absent from module .tf files
    for resource_name, resource_cfg in resources.items():
        module_dir = resource_cfg.get("module_dir")
        if not module_dir:
            continue
        coverage = resource_cfg.get("yaml_coverage", "")
        tf_content = load_module_tf(modules_root, module_dir)
        if not tf_content:
            missing_from_module.append(
                f"  {resource_name}: module_dir '{module_dir}' not found under {modules_root}"
            )
            continue
        for arg, field_cfg in resource_cfg.get("fields", {}).items():
            if field_cfg.get("disposition") == "yaml":
                if not re.search(rf"\b{re.escape(arg)}\b", tf_content):
                    yaml_field = field_cfg["yaml_field"]
                    missing_from_module.append(
                        f"  {resource_name}.{arg} (→ schema: {yaml_field}) not in modules/{module_dir}"
                    )
        if coverage not in ("details_passthrough", "variable_passthrough"):
            for block_name, block_cfg in resource_cfg.get("nested_blocks", {}).items():
                if block_cfg.get("yaml_coverage") == "yaml":
                    if not re.search(rf"\b{re.escape(block_name)}\b", tf_content):
                        missing_from_module.append(
                            f"  {resource_name} block:{block_name} not in modules/{module_dir}"
                        )

    # STALE_YAML: v1.json field not covered by any yaml mapping
    schema_only_defs_set = set(registry.get("schema_only_defs", []))
    for defs_key, props in schema_props.items():
        if defs_key in schema_only_defs_set:
            continue
        claimed = yaml_field_claims.get(defs_key, set())
        extra_exempt = schema_only_by_defs.get(defs_key, set())
        stale = props - claimed - SCHEMA_ONLY_FIELDS - extra_exempt
        for field in sorted(stale):
            stale_yaml.append(f"  $defs/{defs_key}.{field}")

    print("\n=== Schema Drift Report ===\n")

    if unmapped:
        print("UNMAPPED — classify these in scripts/resource_mapping.yml:")
        print("\n".join(unmapped))
        print()

    if missing_from_schema:
        print("MISSING_FROM_SCHEMA — add to schemas/v1.json or reclassify in mapping:")
        print("\n".join(missing_from_schema))
        print()

    if missing_from_module:
        print("MISSING_FROM_MODULE — yaml-classified arg not found in module .tf files:")
        print("\n".join(missing_from_module))
        print()

    if stale_yaml:
        label = "STALE_YAML (warning)" if not ns.fail_on_stale else "STALE_YAML"
        print(f"{label} — in schemas/v1.json but not covered by any mapping:")
        print("\n".join(stale_yaml))
        print()

    n_unmapped = len(unmapped)
    n_missing = len(missing_from_schema)
    n_module = len(missing_from_module)
    n_stale = len(stale_yaml)
    print(f"Summary: {n_unmapped} UNMAPPED, {n_missing} MISSING_FROM_SCHEMA, {n_module} MISSING_FROM_MODULE, {n_stale} STALE_YAML")

    exit_code = 0
    if unmapped or missing_from_schema or missing_from_module:
        exit_code = 1
    if ns.fail_on_stale and stale_yaml:
        exit_code = 1

    print(f"Exit: {exit_code}")
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", default="scripts/resource_mapping.yml")
    parser.add_argument("--schema", default="schemas/v1.json")
    parser.add_argument("--terraform-dir", default=".")
    parser.add_argument("--modules-dir", default="modules",
                        help="Root directory containing Terraform submodules (default: modules/)")
    parser.add_argument("--provider-schema", default=None,
                        help="Path to cached terraform providers schema JSON (skips terraform call)")
    parser.add_argument("--fail-on-stale", action="store_true",
                        help="Exit 1 on STALE_YAML findings in addition to blocking findings")
    ns = parser.parse_args()
    sys.exit(run(ns))


if __name__ == "__main__":
    main()
