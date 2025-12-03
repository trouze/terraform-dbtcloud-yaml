# dbt Cloud Migration Workflow Guide

**Version:** 0.4.0-dev  
**Date:** 2025-12-03

This guide documents the complete workflow for migrating dbt Cloud accounts using the `terraform-dbtcloud-yaml` importer and Terraform module. It covers extracting configuration from a source account, normalizing it into Terraform-ready YAML, and applying it to a target account.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [What Cannot Be Migrated](#2-what-cannot-be-migrated)
3. [Prerequisites](#3-prerequisites)
4. [Phase 1: Fetch (Extract Source Account)](#4-phase-1-fetch-extract-source-account)
5. [Phase 2: Normalize (Convert to v2 YAML)](#5-phase-2-normalize-convert-to-v2-yaml)
6. [Phase 3: Review and Resolve Placeholders](#6-phase-3-review-and-resolve-placeholders)
7. [Phase 4: Prepare Customer Deliverables](#7-phase-4-prepare-customer-deliverables)
8. [Migration Day Execution](#8-migration-day-execution)
9. [Post-Migration Steps](#9-post-migration-steps)
10. [Optional: Deactivate Jobs in Source Account](#10-optional-deactivate-jobs-in-source-account)
11. [Appendix: Tool Comparison](#11-appendix-tool-comparison)

---

## 1. Introduction

This workflow replaces the legacy `dbtcloud-terraforming` approach with a more robust, YAML-first migration process.

### Workflow Comparison

| Aspect | Legacy Workflow | New Workflow |
|--------|-----------------|--------------|
| **Tool** | Go CLI (`dbtcloud-terraforming`) | Python importer (`python -m importer`) |
| **Output** | HCL (Terraform) files directly | YAML configuration consumed by Terraform module |
| **Multi-Project** | Requires separate runs per project | Single YAML with `projects[]` array |
| **Review Artifacts** | Manual HCL inspection | Summary, report, lookups, exclusions manifests |
| **Schema Validation** | None | JSON Schema + IDE autocomplete |
| **Placeholder Resolution** | Manual tfvars population | `LOOKUP:` placeholders + Terraform data sources |

### Benefits of the New Workflow

- **Multi-project support**: Migrate entire accounts with multiple projects in a single YAML
- **Schema validation**: IDE autocomplete and validation via JSON Schema (`schemas/v2.json`)
- **Artifact manifests**: Machine-readable lookups and exclusions reports for review
- **LOOKUP resolution**: Missing references emit `LOOKUP:<name>` placeholders that Terraform data sources can auto-resolve
- **Reproducible**: Timestamped artifacts with sequential run IDs for traceability

### Legacy Workflow Reference

For users who need the legacy `dbtcloud-terraforming` approach, see:
- [Prior Method: Terraforming Workflow](prior_method/terraforming_workflow.md)
- [dbtcloud-terraforming README](https://github.com/dbt-labs/dbtcloud-terraforming)

---

## 2. What Cannot Be Migrated

The following items **cannot** be migrated with automated tooling and require manual intervention:

### Secrets and Credentials
- **Warehouse passwords/tokens**: Users must provide these via the `token_map` Terraform variable
- **Developer credentials**: Each developer must re-enter credentials after migration

### Historical Data
- **Job history and run logs**: Not portable between accounts
- **Audit logs**: Account-specific, cannot be transferred

### Code and Repositories
- **Code from managed repos**: Users must save/export to their own git provider before migration
- **Uncommitted code**: Any code in the IDE that isn't committed will be lost

### Integrations (Manual Setup Required)
- **SSO configuration**: Must be manually configured in the target account
- **Git integration**: OAuth connections must be re-established
- **Slack notifications**: Workspace connections must be reconfigured
- **External Systems dbt API endpoints**: External systems must be updated with new URLs

### Experimental Features
- **SSO group mappings**: Work best when users authenticate via SSO; manual user-to-group assignment is experimental
- **License maps**: May require manual configuration

---

## 3. Prerequisites

### 3.1 Source Account Requirements

**API Access:**
- Account-wide read-only token (Service Token)
- Token must have sufficient scopes to read:
  - Projects, environments, jobs
  - Connections, repositories
  - Service tokens, groups
  - Notifications, webhooks
  - Environment variables
- Minimum dbt RBAC Role: "Account Viewer"
  - Non-Enterprise Customers will need to issue an "Owner" token

**Information Gathering:**
- List of projects to migrate (all or specific project IDs)
- Decision: Should jobs be created activated or deactivated in the target account?
- Identify any managed repositories that need code exported

### 3.2 Target Account Setup (Customer Responsibility)

The customer must complete these steps **before** migration day:

**Integrations:**
- [ ] Set up SSO integration (if applicable)
- [ ] Configure git provider integration (GitHub, GitLab, Azure DevOps, Bitbucket)
- [ ] Connect Slack workspace (if using Slack notifications)
- [ ] Configure any other third-party integrations

**Network and Security:**
- [ ] Allow new dbt Cloud IPs in warehouse firewall (if IP restrictions are in place)
- [ ] Request PrivateLink connections (if using PrivateLink)
- [ ] Configure any VPN or network peering requirements

**API Access:**
- [ ] Create a service token with **Account Admin** scope for Terraform operations
- [ ] Note the new account ID and API host URL

---

## 4. Phase 1: Fetch (Extract Source Account)

The `fetch` command extracts the complete account configuration from the dbt Cloud API.

### 4.1 Setup Environment

Create a `.env` file at the repository root (or export environment variables):

```bash
# Required
DBT_SOURCE_HOST=https://cloud.getdbt.com
DBT_SOURCE_ACCOUNT_ID=12345
DBT_SOURCE_API_TOKEN=your_read_only_token_here

# Optional tuning
DBT_SOURCE_API_TIMEOUT=30           # Client timeout in seconds
DBT_SOURCE_API_MAX_RETRIES=5        # Max retry attempts on 5xx/429
DBT_SOURCE_API_BACKOFF_FACTOR=1.5   # Exponential backoff multiplier
```

**Note:** For non-US hosted accounts, adjust `DBT_SOURCE_HOST`:
- EMEA: `https://emea.dbt.com`
- AU: `https://au.dbt.com`
- Single-tenant: Your custom host URL

### 4.2 Run the Fetch Command

```bash
# Activate virtualenv
source .venv/bin/activate

# Run fetch
python -m importer fetch \
  --output dev_support/samples/account.json \
  --reports-dir dev_support/samples
```

### 4.3 Generated Artifacts

The fetch command generates timestamped files with sequential run IDs:

| Artifact | Filename Pattern | Description |
|----------|------------------|-------------|
| **JSON Export** | `account_{ID}_run_{RUN}__json__{TIMESTAMP}.json` | Full account snapshot with enriched metadata |
| **Summary** | `account_{ID}_run_{RUN}__summary__{TIMESTAMP}.md` | High-level counts and per-project breakdown |
| **Report** | `account_{ID}_run_{RUN}__report__{TIMESTAMP}.md` | Detailed tree showing IDs, names, nested structure |
| **Report Items** | `account_{ID}_run_{RUN}__report_items__{TIMESTAMP}.json` | Machine-readable list with `element_mapping_id` |
| **Logs** | `account_{ID}_run_{RUN}__logs__{TIMESTAMP}.log` | DEBUG-level execution logs |

**Example output:**
```
dev_support/samples/
├── account_86165_run_001__json__20251121_120000.json
├── account_86165_run_001__summary__20251121_120000.md
├── account_86165_run_001__report__20251121_120000.md
├── account_86165_run_001__report_items__20251121_120000.json
├── account_86165_run_001__logs__20251121_120000.log
└── importer_runs.json
```

### 4.4 Review the Fetch Output

Before proceeding to normalization, review the generated reports:

1. **Summary report**: Verify project counts, environment counts, job counts
2. **Detailed report**: Check the hierarchy of environments and jobs per project
3. **Logs**: Look for warnings about unexpected data structures or API errors

**Red flags to investigate:**
- Missing projects (check API token permissions)
- Unexpected environment or job counts
- Warnings about connections or repositories not found

---

## 5. Phase 2: Normalize (Convert to v2 YAML)

The `normalize` command converts the JSON export into Terraform-ready v2 YAML format.

### 5.1 Configure the Mapping File

Create or edit `importer_mapping.yml` to control normalization behavior:

```yaml
# yaml-language-server: $schema=schemas/importer_mapping.json

version: 1

scope:
  mode: all_projects  # Options: all_projects, specific_projects, account_level_only
  # project_keys: [analytics, marketing]  # Used with specific_projects mode

resource_filters:
  connections:
    include: true
  repositories:
    include: true
  service_tokens:
    include: true
  groups:
    include: true
  notifications:
    include: true
  webhooks:
    include: false  # Often not Terraform-manageable
  environments:
    include: true
    # exclude_keys: [dev, local]  # Optional: exclude specific environments
  jobs:
    include: true
  environment_variables:
    include: true

normalization_options:
  strip_source_ids: true          # Remove source IDs (recommended for clean migration)
  placeholder_strategy: lookup    # Emit LOOKUP: for missing refs
  name_collision_strategy: suffix # Handle duplicate keys with _2, _3 suffixes
  secret_handling: redact         # Show REDACTED for secrets
  multi_project_mode: single_file # Single YAML with all projects
  include_inactive: false         # Exclude soft-deleted resources
  include_connection_details: true

output:
  yaml_file: dbt-config.yml
  output_directory: dev_support/samples/normalized/
  generate_manifests:
    lookups: true
    exclusions: true
    diff_json: true
```

**Common scope configurations:**

```yaml
# Migrate everything
scope:
  mode: all_projects

# Migrate specific projects only
scope:
  mode: specific_projects
  project_keys:
    - analytics
    - marketing

# Export globals only (connections, repos, tokens, groups)
scope:
  mode: account_level_only
```

See [Importer Mapping Reference](../docs/importer_mapping_reference.md) for complete configuration documentation.

### 5.2 Run the Normalize Command

```bash
python -m importer normalize \
  dev_support/samples/account_86165_run_001__json__20251121_120000.json \
  --config importer_mapping.yml
```

### 5.3 Generated Artifacts

| Artifact | Filename Pattern | Description |
|----------|------------------|-------------|
| **YAML** | `account_{ID}_norm_{RUN}__yaml__{TIMESTAMP}.yml` | Terraform-ready v2 YAML configuration |
| **Lookups** | `account_{ID}_norm_{RUN}__lookups__{TIMESTAMP}.json` | LOOKUP: placeholders needing resolution |
| **Exclusions** | `account_{ID}_norm_{RUN}__exclusions__{TIMESTAMP}.md` | Resources filtered out with reasons |
| **Diff JSON** | `account_{ID}_norm_{RUN}__diff__{TIMESTAMP}.json` | Diff-friendly JSON for regression testing |
| **Logs** | `account_{ID}_norm_{RUN}__logs__{TIMESTAMP}.log` | DEBUG-level normalization decisions |

**Example output:**
```
dev_support/samples/normalized/
├── account_86165_norm_001__yaml__20251121_121500.yml
├── account_86165_norm_001__lookups__20251121_121500.json
├── account_86165_norm_001__exclusions__20251121_121500.md
├── account_86165_norm_001__diff__20251121_121500.json
├── account_86165_norm_001__logs__20251121_121500.log
└── normalization_runs.json
```

---

## 6. Phase 3: Review and Resolve Placeholders

### 6.1 Review Checklist

Before proceeding, review all normalization artifacts:

- [ ] **Exclusions report**: Verify no resources were unintentionally excluded
- [ ] **Lookups manifest**: Identify all `LOOKUP:` placeholders that need resolution
- [ ] **YAML structure**: Validate environment/job hierarchy matches expectations
- [ ] **Logs**: Check for warnings about collisions, missing references, or secrets

### 6.2 Understanding LOOKUP Placeholders

When a resource references something that doesn't exist in the source export (e.g., a connection created outside the account, or filtered out), the normalizer emits a `LOOKUP:` placeholder:

```yaml
environments:
  - name: Production
    connection: "LOOKUP:snowflake_prod"  # Must be resolved
```

**Example lookups manifest:**
```json
{
  "placeholders": [
    {
      "id": "LOOKUP:snowflake_prod",
      "description": "Connection for environment Production"
    }
  ]
}
```

### 6.3 Resolving LOOKUP Placeholders

**Option A: Create resources in target account first**
1. Manually create the connection/repository in the target dbt Cloud account
2. Terraform data sources will auto-resolve by name during `terraform apply`
3. No changes needed to the YAML

**Option B: Update YAML to reference existing resources**
1. If the resource already exists in the target account, find its key/name
2. Replace `LOOKUP:name` with the actual key in the YAML
3. Ensure the key matches what Terraform will look up

**Option C: Accept LOOKUP and let Terraform resolve**
1. Leave `LOOKUP:` placeholders in the YAML
2. The Terraform module (v2) will use data sources to resolve by name
3. Resources must exist in the target account before `terraform apply`

**Recommendation:** For clean migrations, prefer Option A or B. Option C is useful for incremental migrations where some resources already exist.

---

## 7. Phase 4: Prepare Customer Deliverables

### 7.1 Files to Share with Customer

Prepare the following deliverables for the customer:

1. **Generated v2 YAML**
   - The main configuration file
   - Document any `LOOKUP:` placeholders that need attention

2. **Lookups Manifest**
   - JSON file listing all placeholders
   - Include instructions for resolution

3. **terraform.tfvars Template**
   ```hcl
   # Target account configuration
   dbt_account_id = ""  # New account ID
   dbt_token      = ""  # Account admin service token
   dbt_pat        = ""  # Personal access token (for repository operations)
   
   # Warehouse credentials
   # Each entry corresponds to a credential.token_name in the YAML
   token_map = {
     "snowflake_prod"    = "your_snowflake_password"
     "snowflake_staging" = "your_snowflake_password"
     "databricks_token"  = "your_databricks_token"
   }
   ```

4. **Variable Definitions**
   - Descriptions of each variable
   - Links to relevant documentation
   - References to source account for context

### 7.2 Customer Responsibilities

The customer must complete these items before migration day:

- [ ] Populate `token_map` with all warehouse credentials
- [ ] Provide connection details for any `LOOKUP:` resources
- [ ] Verify `LOOKUP:` resolutions match their target account
- [ ] Review and approve job activation settings
- [ ] Confirm target account prerequisites are complete (Section 3.2)

---

## 8. Migration Day Execution

### 8.1 Pre-Flight Checklist

Before starting, confirm:

- [ ] Target account prerequisites complete
- [ ] Customer has provided all credentials (`token_map`)
- [ ] All `LOOKUP:` placeholders are resolvable
- [ ] Customer is available for questions during migration

### 8.2 Setup Terraform Workspace

```bash
# Navigate to or create Terraform workspace
cd target-terraform-workspace

# Ensure provider is configured for target account
cat > providers.tf << 'EOF'
terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = ">= 0.3.0"
    }
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_token
}

provider "dbtcloud" {
  alias      = "pat_provider"
  account_id = var.dbt_account_id
  token      = var.dbt_pat
}
EOF

# Initialize Terraform
terraform init
```

### 8.3 Execute Migration

```bash
# Plan first - review for errors
terraform plan -var-file=target.tfvars

# Apply the configuration
terraform apply -var-file=target.tfvars
```

### 8.4 Troubleshooting Common Issues

**Hardcoded IDs from source account:**
- Symptom: Errors referencing IDs that don't exist
- Fix: Regenerate YAML with `strip_source_ids: true` in mapping config

**Missing connections:**
- Symptom: `Error: Connection not found`
- Fix: Check lookups manifest, create connection in target account first

**Credential/token errors:**
- Symptom: Authentication failures during environment creation
- Fix: Verify `token_map` entries match `credential.token_name` in YAML

**Repository access errors:**
- Symptom: Git clone failures
- Fix: Ensure git integration is configured in target account, re-authorize if needed

**Resource already exists:**
- Symptom: `Error: Resource already exists`
- Fix: Import existing resource or remove from YAML if managed elsewhere

### 8.5 Verify Migration

After successful `terraform apply`:

1. **Log into target dbt Cloud account**
2. **Verify projects** are created with correct names
3. **Check environments** have correct connections and credentials
4. **Review jobs** have correct schedules and commands
5. **Test a manual job run** to validate configuration

---

## 9. Post-Migration Steps

### 9.1 Developer Actions Required

All developers must complete these steps after migration:

**Account Access:**
- Re-invite via SSO URL or manual invitation
- Accept invitation and activate account

**Git Integration:**
- Reconnect personal git account (GitHub, GitLab, etc.)
- Re-authorize OAuth if using native git integration
- Set up signed commits (if used)

**Credentials:**
- Re-enter warehouse credentials for each project
- This cannot be automated; each developer must do this manually

**Code:**
- Commit any uncommitted code in the old account **before** migration
- Clone repositories in the new IDE environment

### 9.2 External Integration Updates

Update all external systems that interact with dbt Cloud:

**API Consumers:**
- Update base URL to new account endpoint
- Update API tokens to use new account credentials
- Update Account ID in API calls

**Job Triggers:**
- Update Job IDs in external orchestration (Airflow, Prefect, etc.)
- Use the Job ID mapping script to find new IDs:

```bash
# Extract old-to-new job ID mapping from Terraform state
cat terraform.tfstate | jq '[
  .resources[] 
  | select(.type == "dbtcloud_job") 
  | {
      "job_name": .name,
      "new_id": .instances[0].attributes.id
    }
]'
```

**Webhooks:**
- Reconfigure webhook endpoints to point to new account
- Update any CI/CD pipelines that use dbt Cloud webhooks

**Monitoring:**
- Update dashboards and alerts to use new Job IDs
- Reconfigure any Slack notifications

### 9.3 Account Transition

**Decide timeline with customer:**
- When can old account jobs be deactivated?
- When can old account be locked/disabled?
- Who needs continued access to old account (for history)?

**Lock old account:**
- Contact dbt Labs support to lock the old account when ready
- This prevents accidental job runs in the old account

---

## 10. Optional: Deactivate Jobs in Source Account

If the customer wants to keep the old account accessible but deactivate all jobs:

### 10.1 Using Legacy dbtcloud-terraforming

The legacy tool can manage existing resources in the source account:

```bash
# Generate import blocks for jobs only
dbtcloud-terraforming genimport \
  --resource-types dbtcloud_job \
  --parameterize-jobs \
  --output source_jobs.tf

# Apply to import existing jobs into state
terraform apply

# Modify locals to deactivate all schedules
# Then apply again to deactivate
terraform apply
```

### 10.2 Manual Deactivation

Alternatively, deactivate jobs manually:
1. Go to each job in the dbt Cloud UI
2. Edit the job and disable the schedule
3. Or use the dbt Cloud API to bulk-update job triggers

---

## 11. Appendix: Tool Comparison

### Installation

| Tool | Installation |
|------|-------------|
| **Legacy (dbtcloud-terraforming)** | `brew install dbt-labs/dbt-cli/dbtcloud-terraforming` |
| **New (terraform-dbtcloud-yaml)** | `pip install -r importer/requirements.txt` |

### Feature Comparison

| Feature | Legacy | New |
|---------|--------|-----|
| Output format | HCL (Terraform) | YAML (v2 schema) |
| Multi-project support | Separate runs per project | Single YAML with `projects[]` array |
| Review artifacts | Manual HCL inspection | Summary, report, lookups, exclusions |
| Schema validation | None | JSON Schema + IDE support |
| Placeholder resolution | Manual tfvars | `LOOKUP:` + data sources |
| Run tracking | None | Sequential run IDs with timestamps |
| Regression testing | Manual diff | `diff_json` artifact |

### When to Use Each Tool

**Use the new workflow when:**
- Migrating to a new account (fresh start)
- Managing multiple projects together
- Need schema validation and review artifacts
- Want reproducible, traceable migrations

**Use the legacy workflow when:**
- Importing existing resources into Terraform state
- Managing a single project with existing Terraform
- Need to generate import blocks for `terraform import`
- Deactivating jobs in an existing account

---

## Related Documentation

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) - Technical architecture and module reference
- [Phase 2 Normalization Target](phase2_normalization_target.md) - v2 YAML structure details
- [Phase 2 Terraform Integration](phase2_terraform_integration.md) - Module implementation details
- [Importer README](../importer/README.md) - CLI command reference
- [Importer Mapping Reference](../docs/importer_mapping_reference.md) - Full configuration options
- [Prior Method: Terraforming Workflow](prior_method/terraforming_workflow.md) - Legacy workflow reference

