# PROJECT OVERVIEW

> Purpose-built reference for AI agents and contributors who need to understand, extend, or refactor `terraform-dbtcloud-yaml`. This document assumes the reader can open files locally and knows how to run Terraform/Terratest workflows.

## 1. Executive Summary

- **Objective**: Turn YAML-first configuration into dbt Cloud infrastructure via Terraform. The root module loads a single YAML definition and orchestrates dbt Cloud projects, repositories, credentials, environments, jobs, and environment variables.
- **Value proposition**: Data teams stay in the familiar YAML language while inheriting full Terraform lifecycle controls, versioning, and CI/CD integration.
- **Target users**: Data engineers who manage dbt Cloud resources, SREs who automate deployments, and AI agents tasked with analyzing or extending the stack.
- **Key capabilities**:
  - YAML schema validation (`schemas/v1.json`)
  - Modular Terraform composition (`main.tf` references 8 modules)
  - Dual provider support for API token and PAT-based operations
  - Terratest coverage for basic/complete scenarios (`test/terraform_test.go`)

## 2. Technical Architecture

- **Entry point**: `main.tf` decodes `var.yaml_file` via `yamldecode(file(var.yaml_file))` and exposes `local.project_config`.
- **Module orchestration**:
  1. `project` → creates `dbtcloud_project`.
  2. `repository` → configures Git repository with provider detection + validations.
  3. `project_repository` → attaches the repo to the project.
  4. `credentials` → builds credential map (token names → dbt credential IDs).
  5. `environments` → creates environments, linking to credentials.
  6. `jobs` → flattens env/job hierarchy into `dbtcloud_job` resources.
  7. `environment_variables` → creates project-scoped env vars covering all environments.
  8. `environment_variable_job_overrides` → layers job-level overrides.
- **Data flow**: YAML → `local.project_config` → module inputs → Terraform resources → dbt Cloud.
- **Dependency graph**: Each module depends on the previous output (e.g., `jobs` needs `environment_ids`), so `main.tf` chains them via module outputs and `depends_on`.
- **Provider strategy**: `providers.tf` registers two `dbtcloud` providers—one default for standard API token use, and an alias (`pat_provider`) consumed by `modules/repository` to configure Git repositories that require dbt PATs.

### Sample snippet

```terraform
module "jobs" {
  source = "${path.module}/modules/jobs"

  project_id        = module.project.project_id
  environments_data = local.project_config.project.environments
  environment_ids   = module.environments.environment_ids
}
```

## 3. File Structure & Organization

| Path | Purpose |
| --- | --- |
| `main.tf`, `variables.tf`, `outputs.tf`, `providers.tf` | Root orchestrator. Reads YAML, wires in providers, exposes outputs for environments/credentials/jobs, and runs top-level validation. |
| `modules/*` | Each submodule isolates a dbt Cloud domain (project, repository, credentials, etc.). Expect `main.tf`, `variables.tf`, and `outputs.tf` in each. |
| `schemas/v1.json` | JSON Schema used by IDEs (per YAML header) to provide autocomplete + validation. |
| `examples/` | Ready-to-run Terraform + YAML combos for quickstart. |
| `test/fixtures/` | Terratest fixtures mirroring basic/complete setups. |
| `test/terraform_test.go` | Terratest harness. |
| `docs/` | Markdown docs (configuration guides, best practices, etc.). |
| `dev_support/` | New documentation for AI agents (this directory). |

## 4. Module Deep Dive

### 4.1 `modules/project`

- **Purpose**: Creates the dbt Cloud project, surfaces `project_id`.
- **Inputs**: `project_name`, `target_name`.
- **Outputs**: `project_id`.
- **Notes**: Minimal logic reads names and builds `dbtcloud_project`.

### 4.2 `modules/repository`

- **Purpose**: Validates git provider + adds repository via `dbtcloud_repository`.
- **Inputs**: `repository_data`, `project_id`.
- **Key logic**: Auto-detects provider by regex, infers `git_clone_strategy`, and uses `null_resource.validation` to abort on invalid combos. Uses `dbtcloud.pat_provider` for PAT usage.
- **Outputs**: `project_repository_id`, `repository_id`.

### 4.3 `modules/project_repository`

- **Purpose**: Associates repository with project.
- **Inputs**: `repository_id`, `project_id`.
- **Outputs**: None.
- **Notes**: Simple wrapper around `dbtcloud_project_repository` resource.

### 4.4 `modules/credentials`

- **Purpose**: Creates dbt credentials per environment, referencing `token_map`.
- **Inputs**: `environments_data`, `project_id`, `token_map`.
- **Logic**: Iterates over environments → `try()` to look up token values, constructs `flattened_creds`.
- **Outputs**: `credential_ids` map (environment name → credential ID).

### 4.5 `modules/environments`

- **Purpose**: Creates dbt environments per YAML entry.
- **Inputs**: `project_id`, `environments_data`, `credential_ids`.
- **Outputs**: `environment_ids`.
- **Notes**: Maps environment name to credential via `lookup(var.credential_ids, each.key, null)`.

### 4.6 `modules/jobs`

- **Purpose**: Creates jobs by flattening environment → job combos.
- **Inputs**: `project_id`, `environments_data`, `environment_ids`.
- **Key pattern**: `flattened_jobs` local + `jobs_map` for `for_each`. Ensures environment name is reused to look up `environment_id`.
- **Optional fields**: numerous `lookup()` calls (`schedule_type`, `num_threads`, `generate_docs`, etc.).
- **Outputs**: `job_ids`.

### 4.7 `modules/environment_variables`

- **Purpose**: Creates project-level env vars and attaches per environment.
- **Inputs**: `project_id`, `environment_variables`, `environment_ids`, `token_map`.
- **Notes**: Iterates through `[var.environment_variables]` and publishes values scoped per env.

### 4.8 `modules/environment_variable_job_overrides`

- **Purpose**: Adds job-level overrides to account for job-specific env var values.
- **Inputs**: `project_id`, `environments_data`, `job_ids`.
- **Dependencies**: `depends_on = [module.environment_variables]` ensures base vars exist first.
- **Outputs**: None.

## 5. YAML Configuration Schema

- Source: `schemas/v1.json`.
- The YAML header (`# yaml-language-server: $schema=.../schemas/v1.json`) provides IDE validation.
- **Structure**: `project.name`, `project.repository`, `project.environments` array, and optional `environment_variables`.
- **Validation highlights**:
  - `repository.remote_url` must match provider regex.
  - `environments[].credential.token_name` ties to `token_map`.
  - Job triggers must explicitly define all boolean flags.
- **YAML → Terraform mapping**:
  - `project.repository` → `modules/repository`.
  - `environments` array populates credentials → envs → jobs.

### Example snippet from schema

```json
"project": {
  "properties": {
    "repository": {
      "properties": {
        "remote_url": {
          "oneOf": [
            { "pattern": "^https://github\\.com/..." },
            ...
          ]
        }
      }
    }
  }
}
```

## 6. Code Patterns & Conventions

- **Flatten nested structures**: `modules/jobs` uses `flatten([... for env in var.environments_data])` to build a `jobs_map` keyed by `${environment}_${job}`.
- **`lookup()` for optional inputs**: Most modules guard optional YAML values via `lookup(each.value, "field", null)` to avoid Terraform errors.
- **`try()` for safer defaults**: Credentials and repository logic rely on `try(var.whatever, null)` when fields might be missing.
- **Map construction**: `modules/credentials` builds `credential_ids` map so downstream modules can reference IDs by name.
- **Resource naming**: Resources often use `each.key` or `split("_", each.key)` to keep Terraform addressability stable.
- **Error messages**: The repository module constructs `local.validation_errors` to provide actionable guidance when YAML misconfigurations occur.

## 7. Provider Configuration

- `providers.tf` defines two `dbtcloud` providers:
  - Default provider (`dbt_account_id`, `dbt_token`) for general resource creation.
  - `dbtcloud.pat_provider` (`alias = "pat_provider"`, `token = var.dbt_pat`) used where PAT-specific access is required (especially repository creation).
- This dual-provider pattern ensures the module can operate with both API tokens and PATs without reinitializing Terraform.

## 8. Testing Architecture

- **Framework**: Go + Terratest (`test/terraform_test.go`).
- **Test cases**:
  1. `TestBasicConfiguration`: ensures `module.dbt_cloud` exists without real creds by running `terraform plan`.
  2. `TestCompleteConfiguration`: exercises advanced YAML features (multiple envs, extra jobs).
  3. `TestYAMLParsing`: checks the YAML fixture contains expected sections.
  4. `TestVariableValidation`: intentionally feeds invalid `dbt_account_id` to trigger validation.
  5. `TestOutputs`: asserts module outputs include `project_id`, `repository_id`, etc.
  6. `TestPathModule` + `TestModuleStructure` + `TestDocumentation`: ensure Terraform hygiene (module references, docs).
- **Fixtures**: `test/fixtures/basic` + `test/fixtures/complete` hold `main.tf`, `variables.tf`, and `dbt-config.yml`.
- **Helper functions**: `copyDir`, `findString`, and JSON parsing utilities support the tests.

## 9. Extension Points

- **Add new dbt Cloud resources**: Create a new module under `modules/`, define inputs/outputs, then wire it in `main.tf` after appropriate dependencies.
- **New Git providers**: Extend `modules/repository` detection logic (exist `detected_provider` local) and update schema regexes in `schemas/v1.json`.
- **Extend YAML schema**: Edit `schemas/v1.json` (and the YAML sample header) and ensure Terraform modules consume new fields with `lookup()` or `try()`.
- **Add validation rules**: Update `modules/repository` `local.validation_errors` or insert new `precondition`s.
- **Module composition**: Follow pattern: `module "X"` uses `${path.module}/modules/x`, passes necessary data, and surfaces outputs via `outputs.tf`.

## 10. State Management

- Terraform tracks dbt Cloud IDs via module outputs (`module.project.project_id`, `module.repository.project_repository_id`, `module.jobs.job_ids`, etc.).
- Re-applying updates will diff against YAML-derived definitions, so maintain consistent YAML formatting and names.
- To import existing resources, match YAML values and run `terraform import <module>.resource <id>`, then ensure future runs keep the YAML definition in sync.

## 11. Common Patterns to Understand

### Flattening nested YAML
`local.flattened_jobs = flatten([for env in var.environments_data : [for job in env.jobs : {...}]])`.

### Cross-module maps
`modules/credentials` outputs `credential_ids`, which `modules/environments` and `modules/jobs` consume via `lookup(var.credential_ids, env_name, null)`.

### Environment name → ID mapping
Jobs reference environments by name (`split("_", each.key)`), but Terraform needs numeric IDs (`environment_ids` map from module output).

## 12. Known Limitations & Future Enhancements

- Currently focused on the dbt Cloud provider with GitHub/GitLab/Azure DevOps/Bitbucket; adding other SCM hosts requires schema/provider logic updates.
- Repository validation relies on regexes—complex URL formats may need tweaks.
- No native support for multi-workspace or workspace sharing; future work could include multi-account orchestration via separate `var.yaml_file`s per workspace.
- Documented ideas live in `CHANGELOG.md` under "Unreleased" for tracked enhancements.

## 13. Development Workflow

1. Update `schemas/v1.json` when adding YAML fields; ensure IDE header or `yaml-language-server` references the schema.
2. Update modules and `outputs.tf` to expose new IDs.
3. Run `terraform fmt` in each module and `go test ./test` for Terratest.
4. Use fixtures (`test/fixtures/...`) as templates for new scenarios.
5. Document changes in `docs/` and `CHANGELOG.md`.

## 14. Critical Files Reference

| Task | Files to open first |
| --- | --- |
| Understand module wiring | `main.tf`, `variables.tf`, `outputs.tf` |
| Add new dbt Cloud resource | `modules/<resource>/main.tf`, `outputs.tf`, `variables.tf` |
| Modify credential handling | `modules/credentials/main.tf`, `variables.tf`, `outputs.tf` |
| Extend YAML schema | `schemas/v1.json`, `examples/basic/dbt-config.yml` |
| Update docs | `docs/steer > docs/index.md` plus targeted guide |
| Add tests | `test/terraform_test.go`, `test/fixtures/...` |

## 15. Troubleshooting Guide for AI Agents

- **Validation errors**: `modules/repository` populates `local.validation_errors`; inspect `null_resource.validation` to see formatted guidance.
- **Secret/token issues**: Ensure `.env` or pipeline secrets set `TF_VAR_dbt_token`, `TF_VAR_dbt_pat`, and `TF_VAR_token_map` entries that correspond to `credential.token_name`.
- **Module dependency failures**: Check module outputs referenced in the next module (e.g., `module.jobs` depends on `module.environments.environment_ids`).
- **YAML parsing issues**: Use `yamldecode()` to derive structures—malformed YAML will surface as Terraform errors before provider calls.
- **Terratest failures**: Look at `test/terraform_test.go` to understand the expectations and fixtures used.

## 16. Importer Metadata & Hashing Reference

- Every importer run writes enriched metadata to `_metadata` inside the JSON export:
  | Field | Example | Notes |
  | --- | --- | --- |
  | `run_label` | `run_034` | Zero-padded run counter from `importer_runs.json`. |
  | `source_url_hash` | `0f3a2bc19d21` | First 12 chars of `sha256(host)` for privacy. |
  | `source_url_slug` | `cloud_getdbt_com` | Snake-case host, easier to read in reports. |
  | `account_source_hash` | `c7ee2a913b40` | `sha256("{account_id}|{host}")[:12]` to identify the source pairing. |
  | `unique_run_identifier` | `YzdlZTJhOTEzYjQwX3J1bl8wMzQ` | URL-safe base64 of `{account_source_hash}_{run_label}`. |

- Each resource gains an `element_mapping_id = sha256("{TYPE}:{name_or_id}")[:12]` plus `include_in_conversion` (false for inactive/soft-deleted states). Type codes currently include:

  | Code | Element | Identifier Source |
  | --- | --- | --- |
  | `ACC` | Account root | `account_id` |
  | `CON` | Connections | `id` ➜ `name` ➜ `key` |
  | `REP` | Repositories | `id` ➜ `name` |
  | `TOK` | Service Tokens | `id` ➜ `name` |
  | `GRP` | Groups | `id` ➜ `name` |
  | `NOT` | Notifications | `id` ➜ `name` |
  | `WEB` | Webhook subscriptions | `id` ➜ `name` |
  | `PLE` | PrivateLink endpoints | `id` ➜ `name` |
  | `PRJ` | Projects | `id` ➜ `name` ➜ `key` |
  | `ENV` | Environments | `id` ➜ `name` ➜ `key` |
  | `JOB` | Jobs | `id` ➜ `name` |
  | `VAR` | Environment variables | `name` |

- A new machine-readable export `account_{ACCOUNT_ID}_run_{RUN}__report_items__{TIMESTAMP}.json` lists every element with `line_item_number` (default `1001`, configurable via `DBT_REPORT_LINE_ITEM_START`), `element_type_code`, `element_mapping_id`, and a boolean `include_in_conversion`. Downstream tooling can filter by this flag to skip soft-deleted/inactive resources without mutating the source JSON export.

- Human-readable markdown reports now rely on the same hashes and slugs, so docs and automation share a consistent identifier scheme going into Phase 2.

## API Reference Directory

- `dev_support/api_reference/` exists to store up-to-date API specifications:
  - **dbt Cloud REST API**: Document endpoint behavior, required scopes, and usage patterns for projects, repos, environments, jobs, and environment variables.
  - **Terraform dbtcloud provider**: Capture schema for resources the module uses (`dbtcloud_project`, `dbtcloud_job`, etc.), including known bugs or options.
  - **Other dependencies**: SSH key authorship, GitHub/GitLab/Azure DevOps webhook requirements, or database credential APIs should go here.
- Keep both `dbt_api_v2.yaml` and `dbt_api_v2 with references.yaml` in this directory. Use the clean OpenAPI file when you need a minimal, machine-readable contract (e.g., tooling or client generation), and rely on the “with references” version when you are planning, understanding, or writing enhancements because it adds prose, usage guidance, and links back to canonical dbt docs.

## 17. Provider Capabilities & Migration Strategy

- **Provider surface area**: The official provider (`/Users/operator/Documents/git/dbt-labs/terraform-provider-dbtcloud/docs/`) includes resources for every dbt Cloud object we care about—projects, repositories, project repositories, environments, jobs, environment variables, job overrides, plus warehouse credentials (Snowflake/Databricks/BigQuery/etc.), notifications, service tokens, global/extended connections, PrivateLink endpoints, semantic layer configs, groups/permissions, IP restrictions, lineage integrations, license maps, and more. The matching `dbtcloud_*` data sources mirror those resources so Terraform can look up existing objects by ID.
- **Using data sources during migration**: When targeting a fresh account, leverage data sources like `dbtcloud_environment`, `dbtcloud_repository`, `dbtcloud_global_connection`, `dbtcloud_group`, and credential-specific sources to fetch IDs for integrations or infrastructure that already exist. Feed these IDs into the YAML (for example via `token_map`, connection IDs, or repository metadata) so Terraform links to the right objects without hard-coding source-account IDs.
- **Importer workflow (Phase 1 + Phase 2)**:
  1. **Phase 1 - Extract** (via `python -m importer fetch`): Capture metadata from source account via dbt Cloud APIs (projects, repos, credentials, environments, jobs, env vars, notifications, tokens, groups, webhooks, PrivateLink endpoints). Generate JSON export, summary/report markdown, report items, and logs.
  2. **Phase 2 - Normalize** (via `python -m importer normalize`): Convert JSON export into v2 YAML format using `importer_mapping.yml` configuration. Apply scope filters (all projects, specific projects, account-level only), resource filters (exclude by key/ID), normalization options (ID stripping, placeholder strategy, secret handling). Generate YAML output, lookups manifest (LOOKUP: placeholders), exclusions report (filtered resources), diff JSON (regression testing), and logs.
  3. **Map IDs**: For resources marked with `LOOKUP:` placeholders (connections, repos, etc. that don't exist in source export), either create them in target account or let Terraform data sources auto-resolve by name.
  4. **Apply** the Terraform module with generated v2 YAML to create resources in target account. Terraform module detects schema version (v1 vs v2) and routes to appropriate logic.
  5. **Iterate** by re-running fetch/normalize with updated filters or applying incremental changes via Terraform.

## 18. Phase 2 Normalization & v2 Schema

### v2 Schema Overview

The v2 schema (`schemas/v2.json`) extends v1 with multi-project support:
- **Root structure**: `version: 2`, `account`, `globals`, `projects[]`, `metadata.placeholders`
- **Globals**: Reusable account-level resources (connections, repositories, service tokens, groups, notifications, PrivateLink endpoints) referenced by key
- **Key-based references**: Projects reference globals by slugified key instead of numeric ID (e.g., `connection: "snowflake_prod"`)
- **LOOKUP placeholders**: When a resource doesn't exist in source export but is needed, emit `LOOKUP:<name>` for Terraform data source resolution
- **Multi-project**: Single YAML can define multiple projects with shared globals

### Mapping Configuration

`importer_mapping.yml` controls normalization behavior:
- **Scope**: `all_projects`, `specific_projects` (by key/ID), or `account_level_only`
- **Resource filters**: Per-type inclusion rules with `exclude_keys`, `exclude_ids`, `include_only_keys` whitelisting
- **Normalization options**:
  - `strip_source_ids`: Remove source IDs (default true)
  - `placeholder_strategy`: How to handle missing refs (`lookup` emits LOOKUP:, `error` fails, `omit` skips)
  - `name_collision_strategy`: Duplicate key handling (`suffix` adds _2/_3, `error` fails, `skip` omits)
  - `secret_handling`: Secret redaction (`redact` shows REDACTED, `omit` skips, `placeholder` shows ${var.X})
  - `multi_project_mode`: `single_file` (one YAML) or `per_project` (split YAMLs)
  - `include_inactive`: Include soft-deleted/inactive resources (default false)

### Normalization Artifacts

All artifacts follow consistent naming: `account_{ID}_norm_{RUN}__{type}__{TIMESTAMP}.{ext}`

- **YAML**: Terraform-ready v2 configuration
- **Lookups manifest** (JSON): List of LOOKUP: placeholders with descriptions
- **Exclusions report** (Markdown): Resources filtered out with reasons (by type, by reason)
- **Diff JSON**: Sorted, deterministic JSON for regression testing
- **Logs**: DEBUG-level decisions (filters, placeholders, collisions, secrets)

### Terraform v2 Integration

The root Terraform module will detect `version` field in YAML:
- **v1 path**: Existing single-project workflow (no changes to current users)
- **v2 path**: New `modules/projects_v2` that:
  1. Creates global resources first (connections, repos, tokens, groups)
  2. Iterates over `projects[]` array
  3. Resolves key-based references to global resource IDs
  4. Uses data sources to resolve LOOKUP: placeholders by name
  5. Creates project-scoped resources (environments, jobs, env vars)

**State migration**: Upgrading v1 → v2 will recreate resources (new module paths) unless using `terraform state mv`.

For complete v2 details:
- [Phase 2 Normalization Target](phase2_normalization_target.md): Resource mapping, reference resolution, secret handling
- [Phase 2 Terraform Integration](phase2_terraform_integration.md): Module architecture, schema dispatch, LOOKUP resolution workflow
- [Importer Mapping Reference](../docs/importer_mapping_reference.md): Full config options with examples

