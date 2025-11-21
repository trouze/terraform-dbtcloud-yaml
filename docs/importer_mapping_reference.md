# Importer Mapping Configuration Reference

**Version:** 0.4.0-dev  
**Date:** 2025-11-21

This document provides a comprehensive reference for the importer mapping configuration file (`importer_mapping.yml`), which controls how the Phase 2 normalizer converts JSON exports into v2 YAML format.

---

## Overview

The mapping configuration file is a YAML file that defines:
- **Scope**: Which projects and resources to include
- **Filters**: Per-resource-type inclusion/exclusion rules
- **Normalization Options**: How to transform data (ID stripping, placeholders, collisions, secrets)
- **Output Options**: File naming, artifact generation, YAML formatting

The configuration is validated against `schemas/importer_mapping.json` for type safety and IDE autocomplete support.

---

## Schema Version

```yaml
version: 1
```

**Required**: Yes  
**Type**: Integer  
**Values**: `1` (current version)

The mapping config schema version. Must be `1`. Future versions may introduce breaking changes.

---

## Scope Configuration

Controls which projects to include in the normalization.

```yaml
scope:
  mode: all_projects  # or specific_projects, account_level_only
  project_keys: []    # Used when mode is specific_projects
  project_ids: []     # Alternative to project_keys
```

### `scope.mode`

**Required**: Yes  
**Type**: String  
**Values**: `all_projects` | `specific_projects` | `account_level_only`  
**Default**: `all_projects`

- **`all_projects`**: Include all projects from the source export
- **`specific_projects`**: Include only projects listed in `project_keys` or `project_ids`
- **`account_level_only`**: Include only global resources (connections, repos, tokens, groups), no projects

### `scope.project_keys`

**Required**: Only if `mode` is `specific_projects`  
**Type**: Array of strings  
**Default**: `[]`

List of project keys (slugified names) to include. Keys must match those in the JSON export.

**Example**:
```yaml
scope:
  mode: specific_projects
  project_keys:
    - analytics
    - marketing
```

### `scope.project_ids`

**Required**: No  
**Type**: Array of integers  
**Default**: `[]`

Alternative to `project_keys`: specify projects by numeric ID. IDs will be resolved to keys during normalization.

**Example**:
```yaml
scope:
  mode: specific_projects
  project_ids:
    - 12345
    - 67890
```

---

## Resource Filters

Per-resource-type control over what gets included in the output.

```yaml
resource_filters:
  <resource_type>:
    include: true              # Include this resource type
    exclude_keys: []           # List of keys to exclude
    exclude_ids: []            # List of element_mapping_ids to exclude
    include_only_keys: []      # Whitelist: include only these keys (overrides exclude_keys)
```

### Supported Resource Types

- `connections`
- `repositories`
- `privatelink_endpoints`
- `service_tokens`
- `groups`
- `notifications`
- `webhooks`
- `projects`
- `environments`
- `jobs`
- `environment_variables`

### Filter Options

#### `include`

**Type**: Boolean  
**Default**: `true`

Whether to include this resource type at all. If `false`, all resources of this type are omitted.

**Example** (exclude all webhooks):
```yaml
resource_filters:
  webhooks:
    include: false
```

#### `exclude_keys`

**Type**: Array of strings  
**Default**: `[]`

List of resource keys to explicitly exclude. Matching resources will not appear in the output.

**Example** (exclude specific connections):
```yaml
resource_filters:
  connections:
    include: true
    exclude_keys:
      - legacy_connection
      - deprecated_snowflake
```

#### `exclude_ids`

**Type**: Array of strings  
**Default**: `[]`

List of `element_mapping_id` values to exclude. Useful when you have the mapping IDs from a previous run's `report_items` export.

**Example**:
```yaml
resource_filters:
  jobs:
    include: true
    exclude_ids:
      - JOB_a1b2c3d4e5f6
      - JOB_f6e5d4c3b2a1
```

#### `include_only_keys`

**Type**: Array of strings  
**Default**: `[]`

Whitelist mode: if non-empty, **only** these keys will be included. This overrides `exclude_keys`.

**Example** (include only production environments):
```yaml
resource_filters:
  environments:
    include: true
    include_only_keys:
      - production
      - prod
```

---

## Normalization Options

Controls how data is transformed during normalization.

```yaml
normalization_options:
  strip_source_ids: true
  preserve_advisory_ids: false
  placeholder_strategy: lookup
  name_collision_strategy: suffix
  secret_handling: redact
  multi_project_mode: single_file
  include_inactive: false
  yaml_style:
    indent: 2
    line_length: 120
    sort_keys: false
```

### `strip_source_ids`

**Type**: Boolean  
**Default**: `true`

Whether to remove source account IDs from the output. Recommended for clean migration (IDs are source-specific and not portable).

- `true`: IDs are omitted from the output
- `false`: IDs are preserved (useful for debugging or reference)

### `preserve_advisory_ids`

**Type**: Boolean  
**Default**: `false`

If `true` and `strip_source_ids` is `true`, IDs are kept as comments or in a separate metadata field. Not yet implemented in 0.4.0-dev.

### `placeholder_strategy`

**Type**: String  
**Values**: `lookup` | `error` | `omit`  
**Default**: `lookup`

How to handle missing cross-references (e.g., connection referenced by environment but not in globals):

- **`lookup`**: Emit `LOOKUP:<name>` placeholder; user resolves via Terraform data sources
- **`error`**: Fail normalization with an error message
- **`omit`**: Skip the resource that references the missing item

**Example** (strict mode - fail on missing refs):
```yaml
normalization_options:
  placeholder_strategy: error
```

### `name_collision_strategy`

**Type**: String  
**Values**: `suffix` | `error` | `skip`  
**Default**: `suffix`

How to handle duplicate keys (when two resources normalize to the same slug):

- **`suffix`**: Append `_2`, `_3`, etc. to duplicates
- **`error`**: Fail normalization if collision detected
- **`skip`**: Omit all but the first resource with that key

**Example**:
```yaml
normalization_options:
  name_collision_strategy: error  # Strict: no duplicates allowed
```

### `secret_handling`

**Type**: String  
**Values**: `redact` | `omit` | `placeholder`  
**Default**: `redact`

How to handle secret values (environment variables prefixed with `DBT_ENV_SECRET`):

- **`redact`**: Show `REDACTED` in place of the value
- **`omit`**: Skip the secret variable entirely
- **`placeholder`**: Show `${var.<secret_name>}` as a Terraform variable reference

**Example** (omit all secrets from YAML):
```yaml
normalization_options:
  secret_handling: omit
```

### `multi_project_mode`

**Type**: String  
**Values**: `single_file` | `per_project`  
**Default**: `single_file`

Output format:

- **`single_file`**: One YAML with all projects in the `projects[]` array
- **`per_project`**: Separate YAML file for each project (each with its own `globals` and `projects[0]`)

**Example** (split into per-project files):
```yaml
normalization_options:
  multi_project_mode: per_project
```

**Note**: `per_project` mode not yet fully implemented in 0.4.0-dev (generates separate files but shares globals).

### `include_inactive`

**Type**: Boolean  
**Default**: `false`

Whether to include resources marked as `include_in_conversion: false` in the source export. These are typically inactive, soft-deleted, or archived resources.

- `false`: Exclude inactive resources
- `true`: Include all resources regardless of active status

### `yaml_style`

**Type**: Object

YAML formatting preferences.

#### `yaml_style.indent`

**Type**: Integer  
**Default**: `2`  
**Range**: `2-4`

Number of spaces per indentation level.

#### `yaml_style.line_length`

**Type**: Integer  
**Default**: `120`  
**Range**: `80-200`

Maximum line length before wrapping (YAML dumper hint).

#### `yaml_style.sort_keys`

**Type**: Boolean  
**Default**: `false`

Whether to alphabetically sort keys within each object. `false` preserves schema order.

---

## Output Configuration

Controls output file naming and artifact generation.

```yaml
output:
  yaml_file: dbt-config.yml
  output_directory: dev_support/samples/normalized/
  generate_manifests:
    lookups: true
    exclusions: true
    diff_json: true
```

### `output.yaml_file`

**Type**: String  
**Default**: `dbt-config.yml`

Base filename for the YAML output. Actual filename will be timestamped: `account_<ID>_norm_<RUN>__yaml__<TIMESTAMP>.yml`.

### `output.output_directory`

**Type**: String  
**Default**: `dev_support/samples/normalized/`

Directory where all normalization artifacts will be written (YAML, manifests, logs).

### `output.generate_manifests`

**Type**: Object

Controls which companion manifest files are generated.

#### `lookups`

**Type**: Boolean  
**Default**: `true`

Generate a JSON manifest of all `LOOKUP:` placeholders that need manual resolution.

**Output**: `account_<ID>_norm_<RUN>__lookups__<TIMESTAMP>.json`

#### `exclusions`

**Type**: Boolean  
**Default**: `true`

Generate a markdown report of all excluded/filtered resources with reasons.

**Output**: `account_<ID>_norm_<RUN>__exclusions__<TIMESTAMP>.md`

#### `diff_json`

**Type**: Boolean  
**Default**: `true`

Generate a diff-friendly JSON file for regression testing (sorted keys, consistent formatting).

**Output**: `account_<ID>_norm_<RUN>__diff__<TIMESTAMP>.json`

---

## Complete Example

```yaml
# yaml-language-server: $schema=../schemas/importer_mapping.json

version: 1

scope:
  mode: specific_projects
  project_keys:
    - analytics
    - marketing

resource_filters:
  connections:
    include: true
  
  repositories:
    include: true
    exclude_keys:
      - legacy_repo
  
  service_tokens:
    include: true
  
  groups:
    include: true
  
  notifications:
    include: true
  
  webhooks:
    include: false  # Not Terraform-manageable
  
  environments:
    include: true
    exclude_keys:
      - dev
      - local
  
  jobs:
    include: true
    exclude_keys:
      - test_job
  
  environment_variables:
    include: true

normalization_options:
  strip_source_ids: true
  preserve_advisory_ids: false
  placeholder_strategy: lookup
  name_collision_strategy: suffix
  secret_handling: redact
  multi_project_mode: single_file
  include_inactive: false
  
  yaml_style:
    indent: 2
    line_length: 120
    sort_keys: false

output:
  yaml_file: dbt-config.yml
  output_directory: dev_support/samples/normalized/
  
  generate_manifests:
    lookups: true
    exclusions: true
    diff_json: true
```

---

## Common Use Cases

### Use Case 1: Full Account Export (Default)

**Goal**: Export entire account, all projects, all resources.

```yaml
version: 1
scope:
  mode: all_projects
resource_filters: {}  # Include everything
normalization_options:
  strip_source_ids: true
output:
  output_directory: dev_support/samples/normalized/
```

### Use Case 2: Single Project Migration

**Goal**: Migrate only the "Analytics" project.

```yaml
version: 1
scope:
  mode: specific_projects
  project_keys:
    - analytics
normalization_options:
  strip_source_ids: true
```

### Use Case 3: Account-Level Globals Only

**Goal**: Export connections, repositories, tokens, groups (no projects).

```yaml
version: 1
scope:
  mode: account_level_only
normalization_options:
  strip_source_ids: true
```

### Use Case 4: Production Resources Only

**Goal**: Export only production environments and jobs (exclude dev/test).

```yaml
version: 1
scope:
  mode: all_projects
resource_filters:
  environments:
    include_only_keys:
      - production
      - prod
  jobs:
    include: true
    # Exclude by naming pattern (manual list)
    exclude_keys:
      - dev_job
      - test_job
      - ci_check
normalization_options:
  strip_source_ids: true
```

### Use Case 5: Audit Mode (Preserve IDs)

**Goal**: Keep source IDs for reference/debugging.

```yaml
version: 1
scope:
  mode: all_projects
normalization_options:
  strip_source_ids: false  # Keep IDs
```

---

## Troubleshooting

### Problem: "LOOKUP placeholders for everything"

**Cause**: Cross-references not resolved because resources were excluded by filters.

**Solution**: Check `exclusions` report to see what was filtered out. If connections/repositories are excluded but referenced by environments, they'll become LOOKUP placeholders. Either include them or accept manual resolution.

### Problem: "Too many name collisions"

**Cause**: Multiple resources with similar names (e.g., "Prod Connection", "Prod-Connection") normalize to the same key.

**Solution**:
1. Review `exclusions` report for collision warnings
2. Rename resources in source account for uniqueness
3. OR accept suffixed keys (`prod_connection`, `prod_connection_2`)

### Problem: "Secret values in YAML output"

**Cause**: `secret_handling` is set to something other than `redact` or `omit`.

**Solution**: Ensure `secret_handling: redact` to mask secrets, or `omit` to exclude them entirely.

### Problem: "Missing projects in output"

**Cause**: Scope filter or project-level exclusions.

**Solution**: Check:
1. `scope.mode` is `all_projects` or `specific_projects` with correct keys
2. `resource_filters.projects` is not excluding them
3. `include_inactive: false` might exclude soft-deleted projects

---

## Next Steps

- See [Phase 2 Normalization Target Specification](phase2_normalization_target.md) for YAML structure details
- See [Phase 2 Terraform Integration](phase2_terraform_integration.md) for deployment workflow
- See [Importer README](../importer/README.md) for CLI usage

