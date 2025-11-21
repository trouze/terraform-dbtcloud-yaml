# Phase 2 Terraform Compatibility & Integration

**Version:** 0.4.0-dev  
**Date:** 2025-11-21

This document describes how Phase 2 normalized v2 YAML files integrate with the existing Terraform modules and how to maintain backward compatibility with v1 schema.

---

## Schema Dispatch

The root Terraform module must detect the YAML schema version and route to appropriate logic.

### Detection Strategy

```terraform
# main.tf
locals {
  yaml_content = yamldecode(file(var.yaml_file))
  schema_version = try(local.yaml_content.version, 1)  # default to v1 if not specified
  
  # v1 schema (existing)
  project_config_v1 = local.schema_version == 1 ? local.yaml_content.project : null
  
  # v2 schema (new)
  account_config_v2 = local.schema_version == 2 ? local.yaml_content.account : null
  globals_v2 = local.schema_version == 2 ? local.yaml_content.globals : null
  projects_v2 = local.schema_version == 2 ? local.yaml_content.projects : []
}
```

### Module Routing

**v1 Path (Single Project)**:
```terraform
# Current behavior - single project workflow
module "project" {
  source = "${path.module}/modules/project"
  count  = local.schema_version == 1 ? 1 : 0
  
  project_name = local.project_config_v1.name
  target_name  = local.project_config_v1.target_name
}
```

**v2 Path (Multi-Project)**:
```terraform
# New multi-project workflow
module "projects_v2" {
  source   = "${path.module}/modules/projects_v2"
  count    = local.schema_version == 2 ? 1 : 0
  
  account  = local.account_config_v2
  globals  = local.globals_v2
  projects = local.projects_v2
}
```

---

## v2 Module Architecture

### New `modules/projects_v2` Structure

```
modules/projects_v2/
├── main.tf              # Orchestrates all v2 resources
├── variables.tf         # Accepts account, globals, projects
├── outputs.tf           # Exposes IDs for all resources
├── globals.tf           # Creates global resources (connections, repos, tokens, groups)
├── projects.tf          # Iterates over projects array
├── environments.tf      # Creates environments per project
├── jobs.tf              # Creates jobs per project
└── environment_vars.tf  # Creates env vars per project
```

### Key Differences from v1

| Aspect | v1 (Single Project) | v2 (Multi-Project) |
|--------|---------------------|-------------------|
| **Projects** | Single project, direct reference | Array of projects, `for_each` iteration |
| **Global Resources** | Inline within project | Separate `globals` block, referenced by key |
| **Cross-References** | Direct IDs | Key-based lookups or LOOKUP data sources |
| **Repository** | Inline object or single reference | Global repository pool, referenced by key |
| **Credentials** | Per-environment, token_map | Same, but scoped to project environments |

---

## LOOKUP Placeholder Resolution

v2 YAML may contain `LOOKUP:` placeholders for resources that don't exist in the source export but are needed in the target account.

### Terraform Data Source Pattern

When the normalizer emits a placeholder like:
```yaml
environments:
  - name: "Production"
    connection: "LOOKUP:prod_snowflake"
```

The Terraform module must resolve it via data source:

```terraform
# In modules/projects_v2/data_sources.tf
data "dbtcloud_connection" "lookups" {
  for_each = toset([
    for conn_ref in local.all_connection_references :
    conn_ref if startswith(conn_ref, "LOOKUP:")
  ])
  
  # Strip "LOOKUP:" prefix to get the connection name
  name = replace(each.key, "LOOKUP:", "")
  account_id = var.account_id
}

# Then in environments.tf
locals {
  resolved_connection_id = startswith(each.value.connection, "LOOKUP:") ? 
    data.dbtcloud_connection.lookups[each.value.connection].id :
    module.globals.connection_ids[each.value.connection]
}
```

### User Manual Steps

1. **Identify placeholders**: The `lookups` manifest lists all LOOKUP items.
2. **Create resources in target**: Via UI or separate Terraform.
3. **Run Terraform**: Data sources auto-resolve by name.
4. **Optional cleanup**: Replace LOOKUP: with actual key if resource is now managed.

---

## Migration from v1 to v2

### For Single-Project Users

**Option A: Stay on v1**
- No changes required
- Existing YAMLs continue to work
- Recommended for simple, single-project setups

**Option B: Upgrade to v2**
1. Run importer `fetch` to get JSON export
2. Run importer `normalize` with single-project scope
3. Update `main.tf` call to use v2 module path
4. `terraform init` to update modules
5. `terraform plan` to verify no unintended changes

### For Multi-Project Users

**Required: Adopt v2**
1. Run importer against source account
2. Configure `importer_mapping.yml` for multi-project scope
3. Run `normalize` to generate v2 YAML
4. Update Terraform workspace to use v2 module
5. Apply incrementally per project or all at once

---

## Module Graph Changes

### v1 Dependency Flow
```
main.tf
  ├── module.project
  ├── module.repository (depends_on project)
  ├── module.project_repository (depends_on repository)
  ├── module.credentials (depends_on repository)
  ├── module.environments (depends_on credentials)
  ├── module.jobs (depends_on environments)
  ├── module.environment_variables (depends_on environments)
  └── module.environment_variable_job_overrides (depends_on env_vars)
```

### v2 Dependency Flow
```
main.tf
  └── module.projects_v2
       ├── module.globals
       │    ├── dbtcloud_connection (for_each)
       │    ├── dbtcloud_repository (for_each)
       │    ├── dbtcloud_service_token (for_each)
       │    └── dbtcloud_group (for_each)
       ├── module.project[project_key]
       │    ├── dbtcloud_project
       │    ├── module.environments (depends_on globals)
       │    ├── module.jobs (depends_on environments)
       │    └── module.environment_variables (depends_on environments)
       └── (repeat for each project)
```

**Key Insight**: Globals are created first, then projects reference them by key.

---

## Provider Requirements

### v1 Provider Usage
```terraform
provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_token
}

provider "dbtcloud" {
  alias      = "pat_provider"
  account_id = var.dbt_account_id
  token      = var.dbt_pat
}
```

### v2 Provider Usage (Same)
No changes to provider configuration. Both v1 and v2 use the same providers.

### Token Map Variable
```terraform
variable "token_map" {
  type        = map(string)
  description = "Map of token names to warehouse credentials"
  sensitive   = true
}
```

**v1**: Single project, all environments reference this map.  
**v2**: Multi-project, all projects' environments reference the same map (ensure unique token names across projects).

---

## State Management

### v1 State Structure
```
module.project.dbtcloud_project.this
module.repository.dbtcloud_repository.this
module.environments.dbtcloud_environment["production"]
module.jobs.dbtcloud_job["production_daily_build"]
```

### v2 State Structure
```
module.projects_v2.module.globals.dbtcloud_connection["snowflake_prod"]
module.projects_v2.module.globals.dbtcloud_repository["jaffle_shop"]
module.projects_v2.module.project["analytics"].dbtcloud_project.this
module.projects_v2.module.project["analytics"].dbtcloud_environment["production"]
module.projects_v2.module.project["analytics"].dbtcloud_job["production_daily_build"]
```

**Migration Note**: Upgrading from v1 to v2 will result in resource recreation unless you use `terraform state mv` to migrate addresses. For most users, recreating resources is acceptable (they're declarative).

---

## Workflow Summary

### Phase 2 End-to-End Workflow

1. **Export Source Account**
   ```bash
   python -m importer fetch --output dev_support/samples/account.json
   ```

2. **Configure Mapping**
   Edit `importer_mapping.yml`:
   - Set scope (all projects, specific projects, account-only)
   - Configure filters (exclude dev environments, CI jobs, etc.)
   - Choose multi-project vs per-project output

3. **Normalize to v2 YAML**
   ```bash
   python -m importer normalize dev_support/samples/account_86165_run_001__json__20251121_120000.json
   ```
   
   Outputs:
   - `account_*_norm_001__yaml__*.yml` (main YAML)
   - `account_*_norm_001__lookups__*.json` (placeholders)
   - `account_*_norm_001__exclusions__*.md` (excluded resources)
   - `account_*_norm_001__diff__*.json` (diff-friendly JSON)
   - `account_*_norm_001__logs__*.log` (normalization logs)

4. **Review Artifacts**
   - Check exclusions report for unintended omissions
   - Review lookups manifest for manual resolution steps
   - Validate YAML syntax and structure

5. **Prepare Target Terraform**
   - Update `main.tf` to detect v2 schema (or create new workspace)
   - Ensure `modules/projects_v2` module exists
   - Configure `token_map` variable with all credentials

6. **Resolve LOOKUP Placeholders** (if any)
   - Create missing resources in target account (connections, etc.)
   - Terraform data sources will auto-resolve by name
   - OR manually update YAML to use target IDs

7. **Apply Terraform**
   ```bash
   terraform init
   terraform plan -var-file=target.tfvars
   terraform apply
   ```

8. **Verify & Iterate**
   - Check dbt Cloud UI for created resources
   - Run test jobs to validate configuration
   - Adjust mapping config and re-normalize if needed

---

## Compatibility Matrix

| Feature | v1 Schema | v2 Schema | Notes |
|---------|-----------|-----------|-------|
| Single Project | ✅ | ✅ | v2 supports single-project YAMLs |
| Multiple Projects | ❌ | ✅ | v1 requires multiple YAML files + workspaces |
| Global Resources | ❌ | ✅ | v1 inlines connections/repos per project |
| Key-based References | ❌ | ✅ | v1 uses IDs or inline objects |
| LOOKUP Placeholders | ❌ | ✅ | v2 supports manual resolution via data sources |
| Importer Workflow | ❌ | ✅ | v1 is manual YAML authoring only |
| Schema Validation | ✅ | ✅ | Both have JSON Schema + IDE support |

---

## Next Steps

- **Implement `modules/projects_v2`**: Create new module with v2 logic
- **Update root `main.tf`**: Add schema version detection and routing
- **Test migration**: Run end-to-end test with sample v2 YAML
- **Document breaking changes**: Clarify state migration implications
- **Release notes**: Announce v2 schema support in CHANGELOG

---

## Rollback Strategy

If v2 adoption fails:
1. **Keep v1 YAML files**: Do not delete existing v1 configurations
2. **Separate workspaces**: Use new workspace for v2 testing
3. **Rollback**: `git checkout` previous Terraform code, `terraform init`, `terraform apply`
4. **Report issues**: File GitHub issue with normalization logs and exclusions report

