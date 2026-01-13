# Importer Implementation Status & Tracking

**Last Updated:** 2026-01-13  
**Current Importer Version:** 0.7.2  
**Status:** Phase 3 Complete + Interactive Mode + Web UI + E2E Testing Infrastructure

> **⚠️ IMPORTANT: Keep This Document Updated**
> 
> This document tracks the implementation status of the dbt Cloud Account Migration Importer project. It must be updated whenever:
> - A phase is completed or status changes
> - New features are added or limitations discovered
> - Version numbers change (importer or Terraform module)
> - Dependencies or requirements change
> 
> **Update Frequency:** After each significant milestone, phase completion, or version bump.

---

## Quick Status Overview

| Phase | Status | Completion Date | Notes |
|-------|--------|----------------|-------|
| **Phase 0** - Schema Baseline | ✅ Complete | 2024-11 | v2 schema defined |
| **Phase 1** - Source Account Analysis | ✅ Complete | 2024-11 | API endpoints documented, fetcher implemented |
| **Phase 2** - YAML Normalization | ✅ Complete | 2024-11-21 | Normalizer implemented, v2 YAML generation working |
| **Phase 3** - Target Account Preparation | ✅ Complete | 2025-01-27 | Terraform v2 module implemented |
| **Phase 4** - Implementation | ✅ Complete | 2024-11 | CLI tool (`fetch` + `normalize`) implemented |
| **Phase 4+** - Interactive Mode | ✅ Complete | 2025-12-10 | InquirerPy-based interactive UI for fetch/normalize |
| **Phase 5** - Testing & Validation | 🔄 In Progress | - | Terratest coverage complete, end-to-end testing pending |

---

## Phase-by-Phase Status

### Phase 0 – Schema Baseline ✅

**Status:** Complete  
**Completion Date:** 2024-11

#### Completed Tasks
- [x] Reviewed `schemas/v1.json` and identified gaps
- [x] Designed v2 schema requirements (`schemas/v2.json`)
- [x] Documented schema differences and migration path

#### Deliverables
- ✅ `schemas/v2.json` - Multi-project schema with globals
- ✅ Schema documentation in `dev_support/phase2_normalization_target.md`

#### Notes
- v2 schema extends v1 with multi-project support, global resources, and key-based references
- Backward compatible: v1 YAMLs continue to work unchanged

---

### Phase 1 – Source Account Analysis ✅

**Status:** Complete  
**Completion Date:** 2024-11

#### Completed Tasks
- [x] Enumerated API endpoints for all resources
- [x] Documented pagination and filtering strategies
- [x] Defined internal data model (`importer/models.py`)
- [x] Implemented API client (`importer/client.py`)
- [x] Implemented fetcher (`importer/fetcher.py`)

#### Deliverables
- ✅ API endpoint inventory (`dev_support/phase1_source_account_analysis.md`)
- ✅ Internal data models with Pydantic
- ✅ Fetch command: `python -m importer fetch`
- ✅ JSON export with enriched metadata

#### Resources Covered
- ✅ Projects, Repositories, Environments, Jobs
- ✅ Environment Variables (project-scoped)
- ✅ Connections (global)
- ✅ Service Tokens, Groups, Notifications
- ✅ Webhook Subscriptions, PrivateLink Endpoints
- ⚠️ Semantic Layer Configs (documented, not implemented)

#### Notes
- All major resources are fetchable via API
- Metadata enrichment includes `element_mapping_id` and `include_in_conversion` flags
- Run tracking via `importer_runs.json`

---

### Phase 2 – YAML Normalization ✅

**Status:** Complete  
**Completion Date:** 2024-11-21

#### Completed Tasks
- [x] Implemented normalizer (`importer/normalizer/core.py`)
- [x] YAML writer (`importer/normalizer/writer.py`)
- [x] Mapping configuration system (`importer_mapping.yml`)
- [x] LOOKUP placeholder generation
- [x] Secret redaction and ID stripping
- [x] Name collision handling

#### Deliverables
- ✅ Normalize command: `python -m importer normalize`
- ✅ v2 YAML output with proper structure
- ✅ Lookups manifest (JSON)
- ✅ Exclusions report (Markdown)
- ✅ Diff JSON for regression testing
- ✅ Normalization logs (DEBUG level)

#### Features Implemented
- ✅ Scope filtering (all_projects, specific_projects, account_level_only)
- ✅ Resource-level filters (exclude_keys, exclude_ids)
- ✅ ID stripping (configurable)
- ✅ LOOKUP placeholder generation
- ✅ Name collision resolution (suffix strategy)
- ✅ Secret redaction (redact, omit, placeholder)
- ✅ Multi-project mode (single_file, per_project)

#### Terraform Compatibility
- ✅ Service tokens: `service_token_permissions` structure
- ✅ Groups: `group_permissions` with SSO mappings
- ✅ Notifications: Numeric types, user_id, job associations
- ⚠️ Connections: Metadata only (provider config manual)

#### Version
- **Importer Version:** 0.3.4-dev
- See `importer/VERSION` and `CHANGELOG.md` for details

---

### Phase 3 – Target Account Preparation ✅

**Status:** Complete  
**Completion Date:** 2025-01-27

#### Completed Tasks
- [x] Cataloged Terraform data sources for lookups
- [x] Implemented LOOKUP placeholder resolution
- [x] Created Terraform v2 module (`modules/projects_v2/`)
- [x] Updated root module with schema detection
- [x] Created test fixtures and Terratest cases
- [x] Updated documentation

#### Deliverables
- ✅ `modules/projects_v2/` - Complete Terraform module
- ✅ Schema version detection in root `main.tf`
- ✅ Test fixtures (`test/fixtures/v2_basic/`, `test/fixtures/v2_complete/`)
- ✅ Terratest coverage (4 new test functions)
- ✅ Updated `PROJECT_OVERVIEW.md` with v2 status

#### Module Components
- ✅ `variables.tf` - Input definitions
- ✅ `main.tf` - Entry point and locals
- ✅ `globals.tf` - Global resources (connections, tokens, groups, notifications)
- ✅ `data_sources.tf` - LOOKUP resolution
- ✅ `projects.tf` - Projects and repositories
- ✅ `environments.tf` - Environments and credentials
- ✅ `jobs.tf` - Jobs with cross-references
- ✅ `environment_vars.tf` - Environment variables and overrides
- ✅ `outputs.tf` - Resource ID outputs

#### Features
- ✅ Automatic schema detection (v1 vs v2)
- ✅ Multi-project support
- ✅ Key-based resource references
- ✅ LOOKUP placeholder resolution via data sources
- ✅ Backward compatible with v1 schema

#### Documentation
- ✅ Phase 3 changelog (`dev_support/phase3_implementation_changelog.md`)
- ✅ This status document (`dev_support/importer_implementation_status.md`)

---

### Phase 4 – Implementation ✅

**Status:** Complete  
**Completion Date:** 2024-11

#### Completed Tasks
- [x] Built CLI tool (`importer/cli.py`)
- [x] Implemented fetch command with retries/backoff
- [x] Implemented normalize command
- [x] Added pagination handling
- [x] Created comprehensive logging

#### Deliverables
- ✅ CLI: `python -m importer fetch` and `python -m importer normalize`
- ✅ Error handling and retry logic
- ✅ Structured logging (console + file)
- ✅ Artifact generation (JSON, YAML, reports, manifests)

#### Notes
- CLI uses Typer for command-line interface
- Rich library for formatted console output
- Python-dotenv for environment variable management

---

### Phase 4+ – Interactive Mode ✅

**Status:** Complete  
**Completion Date:** 2025-12-10

#### Completed Tasks
- [x] Implemented InquirerPy-based interactive UI (`importer/interactive.py`)
- [x] Added `--interactive` / `-i` flag to `fetch` command
- [x] Added `--interactive` / `-i` flag to `normalize` command
- [x] Credential prompting (only for missing values)
- [x] File browser with recent files list
- [x] Post-fetch normalization prompt
- [x] Confirmation screens before execution
- [x] Comprehensive keyboard navigation guide

#### Deliverables
- ✅ Interactive fetch mode with guided prompts
- ✅ Interactive normalize mode with file selection
- ✅ `INTERACTIVE_GUIDE.md` - Complete user guide with keyboard shortcuts
- ✅ `QUICKSTART.md` - Quick reference for getting started
- ✅ `.env.example` - Credential template

#### Features
- ✅ Form-like terminal UI similar to `dbtcloud-terraforming`
- ✅ Smart credential detection (only prompts for missing values)
- ✅ Recent files browser (shows up to 10 most recent JSON exports)
- ✅ Input validation with helpful error messages
- ✅ Secret input for API tokens (hidden with ***)
- ✅ Post-fetch option to immediately run normalization
- ✅ Keyboard shortcuts: Arrow keys, Tab, Enter, Ctrl+C, Ctrl+U

#### Terminology
- Updated normalize terminology to "Normalize Fetch to dbt Cloud Terraform Module YAML format"
- Consistent messaging across interactive and CLI modes

#### Dependencies Added
- `InquirerPy>=0.3.0,<0.4` - Interactive terminal UI library

#### Version
- **Importer Version:** 0.4.1
- See `importer/VERSION` and `CHANGELOG.md` for details

---

### Phase 5 – Testing & Validation 🔄

**Status:** In Progress  
**Target Completion:** TBD

#### Completed Tasks
- [x] Basic Terratest coverage for v1 schema
- [x] Terratest coverage for v2 schema (basic and complete)
- [x] YAML parsing validation tests (`TestV2YAMLParsing`)
- [x] Output validation tests (`TestV2Outputs`)
- [x] Schema validation tests
- [x] v2 Basic configuration test (`TestV2BasicConfiguration`)
- [x] v2 Complete configuration test (`TestV2CompleteConfiguration`)
- [x] Interactive mode import/execution tests

#### Test Coverage Summary
- ✅ **Unit tests**: YAML parsing, normalization logic, schema validation
- ✅ **Integration tests**: Terratest for v1 and v2 schemas (4 v2 test functions)
- ✅ **Test fixtures**: `test/fixtures/v2_basic/`, `test/fixtures/v2_complete/`
- ⚠️ **End-to-end tests**: Pending real account testing

#### End-to-End Testing Readiness Checklist

Before starting end-to-end testing with a real account, verify:

**Environment Setup**
- [ ] **Test account credentials (source account)**
  - [ ] `DBT_SOURCE_ACCOUNT_ID` configured in environment or `.env` file
  - [ ] `DBT_SOURCE_API_TOKEN` with appropriate permissions:
    - Read access to all projects, environments, jobs, and account-level resources
    - Recommended: Account Admin or Developer role
  - [ ] `DBT_SOURCE_HOST` (if not cloud.getdbt.com) - set for multi-tenant or single-tenant instances
  - [ ] Verify connectivity: `curl -H "Authorization: Token $DBT_SOURCE_API_TOKEN" https://cloud.getdbt.com/api/v2/accounts/$DBT_SOURCE_ACCOUNT_ID/`
- [ ] **Target account credentials (if different)**
  - [ ] `DBT_TARGET_ACCOUNT_ID` for Terraform provider (target account)
  - [ ] `DBT_TARGET_API_TOKEN` for Terraform provider with write permissions
  - [ ] `DBT_TARGET_HOST_URL` for Terraform provider (defaults to https://cloud.getdbt.com)
  - [ ] Note: For same-account testing, source and target can be identical
- [ ] **Python environment**
  - [ ] Python 3.9+ installed: `python --version`
  - [ ] Virtual environment created: `python -m venv venv` (recommended)
  - [ ] Dependencies installed: `pip install -r importer/requirements.txt`
  - [ ] Verify importer version: `python -m importer --version` (should show 0.4.0-dev)
- [ ] **Terraform environment**
  - [ ] Terraform 1.5+ installed (recommend 1.14.1 via tfenv): `terraform version`
  - [ ] tfenv installation: `brew install tfenv && tfenv install 1.14.1 && tfenv use 1.14.1`
  - [ ] dbt Cloud provider configured in test directory
  - [ ] Provider initialized: `terraform init` in test directory

**Test Account Characteristics**
- [ ] **Account contains representative data:**
  - [ ] Multiple projects (2-5 recommended for manageable testing)
  - [ ] Various resource types:
    - [ ] At least 1 connection (with credentials)
    - [ ] At least 2 environments per project (dev + prod/staging)
    - [ ] At least 2 jobs (1 scheduled, 1 CI job recommended)
  - [ ] Global resources:
    - [ ] At least 1 service token (if available)
    - [ ] At least 1 group with permissions (if available)
    - [ ] At least 1 notification (if available)
  - [ ] Environment variables with project and environment overrides (if available)
- [ ] **Account is non-production or test-safe**
  - [ ] NOT a production account with live data
  - [ ] Acceptable to export and document configuration
  - [ ] Target account (if different) is empty or can be safely overwritten
- [ ] **Account data can be safely exported/documented**
  - [ ] No sensitive connection strings or credentials in resource names
  - [ ] Acceptable to create JSON/YAML exports for testing

**Pre-Flight Validation**
- [ ] **Importer version verified**
  - [ ] Run: `python -m importer --version`
  - [ ] Expected output: `0.4.1`
- [ ] **API connectivity test**
  - [ ] Interactive mode: `python -m importer fetch --interactive`
  - [ ] OR: Non-interactive with env vars: `python -m importer fetch --dry-run` (if available)
  - [ ] Verify account name is displayed correctly
- [ ] **Clean workspace**
  - [ ] No existing `importer_export/` directory (or delete: `rm -rf importer_export/`)
  - [ ] No existing `importer_runs.json` (or backup: `mv importer_runs.json importer_runs.json.bak`)
  - [ ] Fresh working directory for Terraform testing
- [ ] **Terraform backend configured**
  - [ ] Use `-backend=false` for testing: `terraform init -backend=false`
  - [ ] OR: Configure local backend in test fixtures

**Test Execution Plan**
- [ ] **Fetch Phase**
  1. [ ] Run: `python -m importer fetch` (or with `--interactive`)
  2. [ ] Verify: Check terminal output for completion message
  3. [ ] Verify: `importer_export/` directory created with JSON files
  4. [ ] Inspect: Open account JSON export and spot-check for expected projects
- [ ] **Verify Fetch Results**
  1. [ ] Open: `importer_export/account_{ACCOUNT_ID}_run_{RUN}__{TIMESTAMP}.json`
  2. [ ] Check: `projects` array contains expected projects
  3. [ ] Check: `connections` array contains expected connections
  4. [ ] Check: `global_groups`, `global_service_tokens`, `global_notifications` populated (if applicable)
  5. [ ] Review: `importer_export/account_{ACCOUNT_ID}_run_{RUN}__summary_report.md`
- [ ] **Normalize Phase**
  1. [ ] Run: `python -m importer normalize` with exported JSON path
  2. [ ] OR: Interactive mode: `python -m importer normalize --interactive`
  3. [ ] Verify: Terminal shows normalization progress
  4. [ ] Verify: YAML file generated in output directory
- [ ] **Review Normalized YAML**
  1. [ ] Open: Generated YAML file (e.g., `dbt-cloud-config.yml`)
  2. [ ] Check: `version: 2` present at top
  3. [ ] Check: `globals` section present with connections, tokens, etc.
  4. [ ] Check: `projects` section contains expected projects
  5. [ ] Check: LOOKUP placeholders present (e.g., `LOOKUP[connection:...]`)
  6. [ ] Review: Exclusions report (if generated)
  7. [ ] Review: Lookups manifest JSON
- [ ] **Terraform Validate**
  1. [ ] Copy: YAML file to test directory (e.g., `test/fixtures/e2e_test/`)
  2. [ ] Create: `main.tf` that references root module with `yaml_file = "dbt-cloud-config.yml"`
  3. [ ] Run: `terraform init -backend=false`
  4. [ ] Run: `terraform validate`
  5. [ ] Expected: "Success! The configuration is valid."
- [ ] **Terraform Plan**
  1. [ ] Set: `DBT_TARGET_ACCOUNT_ID`, `DBT_TARGET_API_TOKEN`, and `DBT_TARGET_HOST_URL` for target account
  2. [ ] Run: `terraform plan -out=tfplan`
  3. [ ] Review: Plan output for expected resource creates
  4. [ ] Verify: No errors in plan (warnings acceptable for deprecations)
  5. [ ] Count: Resources to be created match expected count
- [ ] **Terraform Apply (Optional)**
  1. [ ] **CAUTION:** Only run in empty test account or with `-target` for specific resources
  2. [ ] Dry-run option: Use `terraform plan` repeatedly, do NOT apply
  3. [ ] If applying: `terraform apply tfplan`
  4. [ ] Monitor: Apply progress and check for errors
  5. [ ] Verify: Resources created in dbt Cloud UI
  6. [ ] Cleanup: `terraform destroy` when done (if testing in disposable account)

**Success Criteria**
- [ ] **Fetch completes without errors**
  - No API errors or rate limit issues
  - All expected projects and resources fetched
- [ ] **All expected resources captured in JSON export**
  - Project count matches source account
  - Connection count matches source account
  - Global resources present (tokens, groups, notifications)
- [ ] **Normalize completes without errors**
  - YAML generation successful
  - LOOKUP placeholders generated correctly
  - No Python exceptions or warnings
- [ ] **Generated YAML is valid**
  - Schema validation passes (version 2)
  - Well-formed YAML (no syntax errors)
  - All required fields present
- [ ] **Terraform validate passes**
  - No configuration errors
  - Module loads correctly
  - Variables recognized
- [ ] **Terraform plan shows expected resources**
  - No errors (warnings for deprecations acceptable)
  - Resource count reasonable and expected
  - No unexpected data source errors
- [ ] **(Optional) Terraform apply succeeds in target account**
  - All resources created successfully
  - No errors during apply
  - Resources visible in dbt Cloud UI

**Known Risks & Mitigations**
- **Connection provider configs**: Not exported by API → **Mitigation:** Manually add `provider_config` to YAML before apply
- **Credential secrets**: Not exported → **Mitigation:** Provide via `token_map` variable in Terraform
- **PrivateLink endpoints**: Read-only → **Mitigation:** Ensure endpoints exist in target account before apply
- **Module variable recognition**: See [Known Issues](known_issues.md) → **Mitigation:** Use direct module references, not root as module
- **Rate limiting**: API may throttle requests → **Mitigation:** Importer has built-in retry/backoff logic
- **Large accounts**: May take 5-10+ minutes to fetch → **Mitigation:** Use `--scope` flag to filter projects if needed

#### Pending Tasks
- [ ] End-to-end test with real account export (fetch → normalize → apply)
- [ ] Dry-run against non-production account
- [ ] Terraform apply validation on clean workspace
- [ ] Edge case testing (empty jobs, archived resources, disabled integrations)
- [ ] Performance testing with large accounts (100+ projects)
- [ ] Interactive mode edge cases (cancellation, validation errors, file not found)

---

## Version Tracking

### Importer Version
- **Current:** 0.6.11
- **File:** `importer/VERSION`
- **Last Updated:** 2026-01-09

### Terraform Module Version
- **Current:** Supports v1 and v2 schemas
- **Minimum Terraform:** 1.5+ (tested with 1.10.3)
- **Provider Version:** dbt-labs/dbtcloud ~> 1.5

### Schema Versions
- **v1:** Single-project schema (existing, stable)
- **v2:** Multi-project schema with globals (new, stable)

---

## Dependencies & Requirements

### Python
- **Version:** 3.9+
- **Dependencies:** See `importer/requirements.txt`
  - httpx, python-dotenv, pydantic, rich, typer, python-slugify, PyYAML, InquirerPy

### Terraform
- **Version:** 1.5+ (tested with 1.14.1)
- **Installation:** Use `tfenv` (Terraform version manager) instead of Homebrew
  - Homebrew no longer updates Terraform due to HashiCorp BUSL license
  - `tfenv` provides direct access to latest Terraform versions
- **Provider:** dbt-labs/dbtcloud ~> 1.5

### Go (for testing)
- **Version:** 1.21+
- **Used for:** Terratest integration tests

---

## Known Limitations & Gaps

### API Limitations
1. **Connection Provider Config**: Not available from API (security). Must be manually added to YAML.
2. **Credential Secrets**: Never exported. Must be provided via `token_map` variable.
3. **OAuth Configurations**: Not exportable. Requires manual setup in target account.

### Implementation Gaps
1. **Credential Types**: Currently defaults to Databricks. Other types need additional resources.
2. **Semantic Layer**: Documented but not implemented in fetcher/normalizer.
3. **Model Notifications**: Not yet implemented (may require API research).

### Terraform Limitations
1. **State Migration**: v1 → v2 upgrade recreates resources unless using `terraform state mv`.
2. **PrivateLink Endpoints**: Read-only, must exist in target account.
3. **Notification Updates**: Job associations not dynamically updated after job creation.

### Known Issues
1. **Module Variable Recognition**: When root module is used as a child module from test fixtures, Terraform doesn't recognize variables. See `dev_support/known_issues.md` for details and workarounds.
2. **Databricks Credential Deprecation**: `adapter_type` field generates deprecation warning but is still required by provider when `semantic_layer_credential` is false. The warning can be safely ignored until the provider removes the requirement.

---

## Next Steps & Roadmap

### Immediate (Next Sprint)

#### Critical Path
- [ ] **End-to-end testing with real account** (Phase 5)
  - **Blockers:** Access to test account, test data preparation
  - **Dependencies:** None
  - **Details:** Complete fetch → normalize → apply workflow validation
- [ ] **User-facing migration guide**
  - **Blockers:** End-to-end testing results
  - **Dependencies:** End-to-end testing completion
  - **Details:** Step-by-step guide for source → target account migration

#### Parallel Work
- [ ] **Connection config templates for common providers**
  - **Blockers:** None (can start immediately)
  - **Dependencies:** None
  - **Details:** Templates for Snowflake, BigQuery, Redshift, Databricks, PostgreSQL

### Short-Term (Next Month)
- [ ] **Support for non-Databricks credential types**
  - **Blockers:** Terraform provider support for each credential type
  - **Dependencies:** Connection config templates
  - **Details:** Extend normalizer and Terraform module for Snowflake, BigQuery, etc.
  - **Related Known Limitations:** Implementation Gaps #1 (Credential Types)
- [ ] **State migration helpers/tooling**
  - **Blockers:** Understanding common v1→v2 migration patterns
  - **Dependencies:** User feedback from migrations
  - **Details:** Scripts or guides for `terraform state mv` operations
  - **Related Known Limitations:** Terraform Limitations #1 (State Migration)
- [ ] **Performance optimization for large accounts**
  - **Blockers:** Access to large account (100+ projects) for testing
  - **Dependencies:** Performance baseline from Phase 5 testing
  - **Details:** Pagination optimization, parallel fetching, memory management
- [ ] **Bug Fix: Module variable recognition issue**
  - **Blockers:** Root cause analysis
  - **Dependencies:** None
  - **Details:** See [Known Issues](known_issues.md#module-variable-recognition-issue)
  - **Related Known Issues:** #1 (Module Variable Recognition)

### Medium-Term (Next Quarter)
- [ ] **Semantic Layer support**
  - **Blockers:** API endpoint research, Terraform provider support
  - **Dependencies:** API research completion (see Prerequisites below)
  - **Details:** Fetch semantic layer configs and add to normalizer/Terraform module
  - **Related Known Limitations:** Implementation Gaps #2 (Semantic Layer)
  - **See Also:** [Prerequisites for API Research](#prerequisites-for-api-research)
- [ ] **Notification migration mode (`--migrate-notifications`)**
  - **Blockers:** Job ID mapping, Slack integration detection
  - **Dependencies:** Job creation and ID mapping, Slack integration API research
  - **Details:** Separate mode to migrate notifications after jobs are created, including:
    - Job ID mapping (source job IDs → target job IDs)
    - Slack integration detection and configuration
    - User notification migration (if user migration becomes possible via API)
  - **Related Known Limitations:** Notification Migration Limitations (KNOWN_ISSUES.md #5)
  - **Status:** Currently filtered in Terraform (v0.6.3) - user/Slack/job-linked notifications skipped
- [ ] **Model notifications**
  - **Blockers:** API availability unknown
  - **Dependencies:** API research completion (see Prerequisites below)
  - **Details:** If API available, add to fetcher and normalizer
  - **Related Known Limitations:** Implementation Gaps #3 (Model Notifications)
  - **See Also:** [Prerequisites for API Research](#prerequisites-for-api-research)
- [ ] **Enhanced error messages and validation**
  - **Blockers:** None
  - **Dependencies:** User feedback from migrations
  - **Details:** Improve validation, better error messages, pre-flight checks

### Long-Term (Future)
- [ ] **Multi-account orchestration**
  - **Details:** Manage migrations across multiple source/target accounts
- [ ] **Incremental sync capabilities**
  - **Details:** Sync only changed resources instead of full export
- [ ] **Web UI for importer (optional)**
  - **Details:** Optional web interface for non-technical users

---

## Prerequisites for API Research

The following items require API endpoint research before implementation can begin:

### Semantic Layer Support
- **Status:** Documented but not implemented
- **API Endpoint:** v3 `/semantic-layer-credentials/` (assumed)
- **Research Needed:**
  - [ ] Confirm endpoint availability and authentication requirements
  - [ ] Document request/response schema
  - [ ] Verify Terraform provider support for semantic layer credentials
  - [ ] Identify project-level semantic layer configuration fields
- **Target Timeline:** Medium-Term (Next Quarter)
- **Related Roadmap Item:** [Medium-Term: Semantic Layer support](#medium-term-next-quarter)

### Model Notifications
- **Status:** Not yet implemented
- **API Endpoint:** Unknown (may be part of dbt Cloud Discovery or Exposures)
- **Research Needed:**
  - [ ] Discover if API exists for model-level notifications
  - [ ] Check dbt Cloud API documentation for freshness/test notifications
  - [ ] Verify if feature is available via Metadata API or separate endpoint
  - [ ] Document schema if endpoint exists
- **Target Timeline:** Medium-Term (Next Quarter)
- **Related Roadmap Item:** [Medium-Term: Model notifications](#medium-term-next-quarter)

### License Maps / Seats (Optional)
- **Status:** Not documented
- **API Endpoint:** TBD (may be v3 `/license/` or `/seats/`)
- **Research Needed:**
  - [ ] Identify license/seat management endpoints
  - [ ] Determine if data is read-only or manageable via Terraform
  - [ ] Document schema for informational reporting
- **Target Timeline:** Future / As Needed
- **Priority:** Low (read-only informational)

### Account Features / Feature Flags (Optional)
- **Status:** Not documented
- **API Endpoint:** TBD (may be embedded in account response)
- **Research Needed:**
  - [ ] Check if feature flags are exposed via API
  - [ ] Document available features (Unity Catalog, etc.)
  - [ ] Determine if flags are read-only or configurable
- **Target Timeline:** Future / As Needed
- **Priority:** Low (informational only)

---

## Maintenance Instructions

### When to Update This Document

1. **After Phase Completion**
   - Update phase status to ✅ Complete
   - Add completion date
   - Document deliverables and notes

2. **After Version Bump**
   - Update "Current Importer Version" at top
   - Update version in "Version Tracking" section
   - Note changes in relevant phase section

3. **When Adding Features**
   - Add to appropriate phase's "Completed Tasks"
   - Update "Known Limitations" if gaps are addressed
   - Add to "Next Steps" if it's a new capability

4. **When Discovering Limitations**
   - Add to "Known Limitations & Gaps" section
   - Categorize (API Limitations, Implementation Gaps, Terraform Limitations)

5. **When Dependencies Change**
   - Update "Dependencies & Requirements" section
   - Note any breaking changes or migration needs

### Version Update Process

1. **Importer Version** (`importer/VERSION`):
   - Update version number
   - Update this document's "Current Importer Version"
   - Add entry to `CHANGELOG.md`

2. **Terraform Module**:
   - Note any schema changes
   - Update minimum Terraform version if needed
   - Document breaking changes

3. **Documentation**:
   - Update this status document
   - Update `PROJECT_OVERVIEW.md` if architecture changes
   - Update phase-specific docs if needed

---

## Related Documentation

- [Importer Plan](importer_plan.md) - Original phase breakdown
- [Phase 1 Analysis](phase1_source_account_analysis.md) - API endpoints and data model
- [Phase 2 Normalization](phase2_normalization_target.md) - v2 schema and normalization rules
- [Phase 2 Terraform Integration](phase2_terraform_integration.md) - Module architecture design
- [Phase 3 Changelog](phase3_implementation_changelog.md) - Implementation details
- [Phase 5 E2E Testing Guide](phase5_e2e_testing_guide.md) - Complete end-to-end testing procedure
- [Interactive Mode Implementation](interactive_mode_implementation.md) - Interactive UI implementation details
- [Known Issues](known_issues.md) - Current known issues and workarounds
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) - Complete project reference
- [CHANGELOG.md](../CHANGELOG.md) - Detailed version history

---

## Change Log

### 2026-01-09 (v0.6.11)
- **Version:** Incremented to 0.6.11 (patch release - scheduled job configuration)
- **Jobs: schedule normalization**: Fixed scheduled job settings not being applied in the target account.
  - Normalizer now reads schedule fields from the nested Jobs API shape (`settings.schedule.date` / `settings.schedule.time`).
  - Only emits valid Terraform combinations and only when `triggers.schedule` is true.

### 2026-01-08 (v0.6.10)
- **Version:** Incremented to 0.6.10 (patch release - job creation apply stability)
- **Jobs: compare_changes_flags unknown after apply**: Fixed Terraform apply failures where job creation left `compare_changes_flags` unknown, triggering `Provider returned invalid result object after apply`.
  - Provider now sets `compare_changes_flags` to a known value after create (API value or `null`).

### 2026-01-08 (v0.6.9)
- **Version:** Incremented to 0.6.9 (patch release - environment variable environment-specific values)
- **Environment Variable Environment-Specific Values**: Fixed environment-specific values not being set for environment variables
  - Added explicit dependency on `dbtcloud_environment.environments` to ensure environments are created before setting environment-specific values
  - Environment variables with `project` defaults were working, but values for specific environments (e.g., "1 - Prod", "2 - Staging") were not being set
  - The dbt Cloud API requires environments to exist before environment-specific values can be assigned

### 2026-01-08 (v0.6.7)
- **Version:** Incremented to 0.6.7 (patch release - repository replacement prevention)
- **Repository Replacement Prevention**: Fixed unnecessary repository replacements when `github_installation_id` is provided
  - Provider now uses API's returned `git_clone_strategy` value (`github_app`) when `github_installation_id` is set
  - Terraform module automatically sets `git_clone_strategy = "github_app"` when `github_installation_id` is provided
  - Prevents Terraform from detecting configuration drift and replacing repositories unnecessarily

### 2026-01-08 (v0.6.6)
- **Version:** Incremented to 0.6.6 (patch release - environment deployment_type and connection linking)
- **Environment deployment_type**: Added support for `deployment_type` field (production/staging)
  - Fetcher extracts `deployment_type` from environment metadata
  - Normalizer includes `deployment_type` in normalized environment output
  - Terraform module sets `deployment_type` attribute on `dbtcloud_environment` resources
- **Environment Connection Linking**: Fixed environments not being linked to global connections
  - Added connection key registry similar to repository key registry (`connection_key_to_normalized` dict)
  - Added `register_connection_key()` and `resolve_connection_key()` methods to `NormalizationContext`
  - Connection normalization registers original -> normalized key mapping
  - Environment normalization uses connection key resolution first, then falls back to element_mapping_id resolution
  - Environments now resolve connection keys correctly instead of showing `LOOKUP:` placeholders

### 2026-01-08 (v0.6.5)
- **Version:** Incremented to 0.6.5 (patch release - GitLab repository fix)
- **GitLab Repository Creation**: Fixed `gitlab_project_id` not being fetched during import
  - Added undocumented `include_related=["deploy_key","gitlab"]` query parameter to v3 Retrieve Repository API
  - Fetcher now correctly extracts `gitlab_project_id` from nested GitLab integration data
  - Enables proper GitLab repository creation with `deploy_token` strategy
- **GitLab PAT Requirement**: Added automatic PAT detection for GitLab repositories
  - E2E test script (`test/run_e2e_test.sh`) now automatically detects `deploy_token` repos
  - Automatically uses PAT (`DBT_TARGET_PAT`) as main token when GitLab repos exist
  - Warns users if GitLab repos detected but no PAT provided
  - GitLab repositories require user token (PAT), not service token

### 2025-12-20 (v0.6.4)
- **Version:** Incremented to 0.6.4 (patch release - skip all notifications)
- **Skip All Notifications**: Updated notification migration to skip ALL notifications during initial migration
  - Provider requires `user_id` for all notification types (even external email)
  - Since source user IDs cannot be mapped to target user IDs, all notifications are skipped
  - Changed `for_each` filter to `if false` to create empty resource set
  - Added placeholder required fields (`user_id`, `notification_type`, `state`) for schema validation
  - Notifications are still fetched and normalized (preserved in YAML for future migration mode)
  - Future `--migrate-notifications` mode will handle user ID and job ID mapping

### 2025-12-20 (v0.6.3)
- **Version:** Incremented to 0.6.3 (patch release - notification filtering)
- **Notification Migration Filtering**: Added filtering to skip user-level and Slack notifications during initial migration
  - User notifications (type 1): Skipped - source user IDs don't exist in target account
  - Slack notifications (type 2): Skipped - requires Slack integration in target account
  - Job-linked notifications: Skipped - job IDs from source account don't exist in target
  - Only external email notifications (type 4) without job references are created
  - All notifications are still fetched and normalized (preserved in YAML for future migration mode)
  - Updated `modules/projects_v2/globals.tf` with filtering logic and documentation
  - Set `user_id = null` for external email notifications (source user doesn't exist)
- **Documentation**: Added notification migration limitations to `KNOWN_ISSUES.md`
  - Documented current filtering behavior
  - Added roadmap item for future `--migrate-notifications` mode
  - Includes job ID mapping and Slack integration detection requirements

### 2025-12-20 (v0.6.2)
- **Version:** Incremented to 0.6.2 (patch release - critical bug fixes for cross-account migration)
- **Service Token Permission Grants**: Fixed provider to use `permission_grants.permission_set` during service token creation
  - API expects `permission_grants` array in creation request, not `service_token_permissions`
  - Updated `CreateServiceToken()` in provider with correct request structure
  - Added `ServiceTokenPermissionGrant` struct with proper JSON tags
  - Fixed `writable_environment_categories` serialization to include empty arrays (not omit them)
- **Cross-Account Project ID Resolution**: Fixed service token and group permissions to use `project_key` instead of source `project_id`
  - Source account project IDs don't exist in target account, causing 404 errors
  - Added `project_id_to_key` mapping in normalizer to convert source IDs to project keys
  - Added `_build_project_id_mapping()` pre-pass before normalizing permissions
  - Updated `_normalize_service_tokens()` and `_normalize_groups()` to output `project_key` instead of `project_id`
  - Updated Terraform module to resolve `project_key` → target `project_id` at apply time
  - Affects: `service_token_permissions` and `group_permissions` with project-specific access

### 2025-12-20 (v0.6.1)
- **Version:** Incremented to 0.6.1 (patch release - bug fixes and stability improvements)
- **Provider Version Pinning**: Pinned Terraform provider to exact version `= 1.5.1` to prevent version drift
- **Empty Environment Variables**: Added filtering to skip environment variables with no values (prevents 11 API errors)
- **Deprecated dbt Versions**: Added filtering to skip environments with deprecated dbt versions like `latest-fusion` (prevents 7 API errors)
- **Dependency Cascades**: Added explicit `depends_on` blocks for service tokens and groups to ensure proper resource ordering

### 2025-12-20 (v0.6.0)
- **Version:** Incremented to 0.6.0 (minor release - feature enhancements)
- **Test Mode Destroy Flag**: Added `--test-destroy` flag to E2E test script for cleaning up test resources
  - Targets 1-2 resources (connections preferred, groups fallback) using same logic as `--test-plan` and `--test-apply`
  - Supports standalone destroy mode (skips fetch/normalize when only destroy is requested)
  - Includes 10-second warning before destroy execution
  - Usage: `./run_e2e_test.sh --test-destroy` or `./run_e2e_test.sh --test-apply --test-destroy`
- **Test Mode Uses Real Connection Data**: Updated Terraform module to read connection configuration from `provider_config` first (where `.env` values are stored), then fall back to `details` (API data), then defaults
  - Test mode now uses real connection credentials from `.env` files instead of dummy test data
  - Updated connection types: Databricks, Snowflake, BigQuery, Postgres, Redshift
  - Ensures test resources are created with actual configuration values for accurate testing
- **Test Mode Targeting Fix**: Fixed test mode resource targeting by adding `[0]` index to `projects_v2` module path
  - Root cause: `projects_v2` module uses `count = 1`, requiring `module.projects_v2[0]` instead of `module.projects_v2`
  - Test mode now correctly targets and plans/applies 1-2 resources as intended
  - Fix enables successful Terraform plan/apply execution in test mode
- **Technical Details**:
  - Updated `modules/projects_v2/globals.tf` to prioritize `provider_config` over `details` for connection configuration
  - Updated `test/run_e2e_test.sh` to include `[0]` index in target resource paths
  - Added `phase6_destroy()` function with same targeting logic as test-plan/test-apply

### 2025-12-20 (v0.5.3)
- **Version:** Incremented to 0.5.3 (patch release)
- **Terraform Provider Connection Fix**: Fixed "Unsupported Authorization Type" error in E2E test
  - Root cause: Test fixture wasn't passing credential variables to the module, causing provider to use default `https://cloud.getdbt.com`
  - Added variable definitions (`dbt_account_id`, `dbt_token`, `dbt_host_url`) to `test/e2e_test/main.tf`
  - Provider block now uses variables and explicitly passes them to module
  - Enables proper connection to custom domain instances (e.g., `iq919.us1.dbt.com/api`)
- **E2E Test Script Cleanup**: Removed debug instrumentation from provider connection debugging session
  - Removed curl diagnostic calls and debug logging statements
  - Cleaned up unused token manipulation logic
- **Technical Details**:
  - Updated `test/e2e_test/main.tf` to properly configure provider with credential variables
  - Module now receives credentials via explicit variable passing instead of relying on defaults
  - Provider configuration correctly inherits from root module to child modules

### 2025-12-20 (v0.5.2)
- **Version:** Incremented to 0.5.2 (patch release)
- **Connection Type Detection**: Fixed connections showing as "unknown" type
  - Added `_extract_connection_type_from_adapter_version()` function to derive connection type from `adapter_version` field
  - Connection types now correctly display as "databricks", "snowflake", "bigquery", etc.
- **Bracketed Paste Sequences**: Fixed terminal paste issues in interactive prompts
  - Added `_strip_bracketed_paste_sequences()` filter to remove escape sequences from pasted input
- **Terminal Access**: Fixed "Input is not a terminal" warnings in E2E test script
  - Replaced Python heredoc with standalone `test/configure_connections.py` script
- **Environment Variable Standardization**: Changed `DBT_SOURCE_HOST` to `DBT_SOURCE_HOST_URL`
- **E2E Test Script**: Enhanced provider configuration workflow with automatic `.env` injection

### 2025-12-20 (v0.5.1)
- **Version:** Incremented to 0.5.1 (patch release)
- **Environment Variable Standardization**: Fixed inconsistent environment variable naming
  - Changed target account variables from `DBTCLOUD_*` to `DBT_TARGET_*` to match `DBT_SOURCE_*` pattern
  - Fixed target token variable to use `DBT_TARGET_API_TOKEN` instead of `DBT_TARGET_TOKEN`
  - Fixed E2E test script to use `DBT_SOURCE_*` variables instead of `DBT_CLOUD_*` for source account
  - Updated all documentation and E2E test script references
- **Interactive Connection Configuration Enhancement**: Replaced nano editor with Python menu-driven prompts
  - Enhanced `prompt_connection_credentials()` with schema-based field definitions (`CONNECTION_SCHEMAS`)
  - Added required vs optional field indicators with helpful descriptions
  - Improved validation and user experience for connection provider_config entry
  - Supports all connection types: Snowflake, Databricks, BigQuery, Redshift, PostgreSQL, Athena, Fabric, Synapse
  - Created `prompt_connection_credentials_interactive()` wrapper that automatically updates YAML file
  - Updated E2E test script to use Python interactive function instead of nano editor
- **Technical Details**:
  - Updated `test/run_e2e_test.sh` with Python interactive function call
  - Updated `importer/interactive.py` with connection schema definitions and enhanced prompting logic
  - Environment variable mapping: `DBT_TARGET_*` → `TF_VAR_dbt_*` and `DBT_CLOUD_*` for Terraform provider compatibility

### 2025-12-19 (v0.4.1)
- **Version bump:** 0.4.0-dev → 0.4.1
- Created complete Phase 5 E2E testing infrastructure:
  - Phase 5 E2E Testing Guide (677 lines, 6-phase workflow)
  - Automated test script with prerequisite checking and summary generation
  - Test fixture directory structure
- Enhanced documentation:
  - Significantly expanded End-to-End Testing Readiness Checklist (20 → 80+ items)
  - Added "Prerequisites for API Research" section
  - Added explicit blockers/dependencies to all roadmap items
  - Linked Known Issues to roadmap items
  - Aligned Semantic Layer timeline across documents
- Fixed critical bugs:
  - Infinite recursive module loading in test_module_call.tf
  - Provider version conflict (e2e test vs root)
  - Python3 detection in test script
- Updated CHANGELOG.md with comprehensive 0.4.1 release notes

### 2025-12-19 (v0.4.0-dev)
- Enhanced Next Steps & Roadmap section with explicit blockers, dependencies, and related limitations
- Added "Prerequisites for API Research" section for items requiring endpoint discovery
- Aligned Semantic Layer timeline across documents (Medium-Term / Next Quarter)
- Linked Known Issues to relevant roadmap items
- Significantly expanded End-to-End Testing Readiness Checklist with:
  - Detailed step-by-step instructions for each testing phase
  - Specific commands and expected outputs
  - Success criteria with clear verification steps
  - Enhanced known risks and mitigations

### 2025-12-19 (v0.4.3)
- **Version:** Incremented to 0.4.3 (patch release - performance improvements)
- **Performance Enhancement - HTTP Timeout**: Increased default HTTP timeout from 30s to 90s
  - Updated `importer/config.py` default timeout: `30.0` → `90.0`
  - Updated environment variable default: `DBT_SOURCE_API_TIMEOUT` from `"30"` → `"90"`
  - Provides better handling of slow API responses for large accounts
  - Users can still override via environment variable for custom timeout values
- **Performance Enhancement - Gzip Compression**: Added compression support for API requests
  - Added `Accept-Encoding: gzip, deflate` header to both v2 and v3 API clients in `importer/client.py`
  - Expected 70-90% reduction in payload size for typical JSON responses
  - Reduces transfer time and significantly lowers likelihood of timeout errors
  - Transparent to users - `httpx` automatically handles decompression
- **Documentation**: Created `dev_support/VERSION_UPDATE_CHECKLIST.md`
  - Comprehensive guide for version management
  - Lists all files and locations requiring updates when incrementing version
  - Includes semantic versioning guidelines, step-by-step workflow, and verification commands
  - Referenced in CHANGELOG.md header for easy maintainer access
- **Documentation**: Created comprehensive RELEASE_NOTES_v0.4.3.md with performance analysis and testing results

### 2025-12-20 (v0.5.0)
- **Version:** Incremented to 0.5.0 (minor release - new feature)
- **Interactive Credential Saving**: Added ability to save credentials to `.env` file during interactive mode
  - After entering credentials in interactive fetch mode, users are prompted to save them for future sessions
  - Supports saving source account credentials (DBT_SOURCE_*) and connection provider_config credentials (DBT_CONNECTION_*)
  - Automatically sets restrictive file permissions (600) and warns about gitignore status
  - Handles existing `.env` files with append/overwrite options
- **Connection Credential Prompting**: Added interactive prompts for connection provider_config during normalization
  - After normalization completes, users can configure missing connection provider_configs interactively
  - Supports all connection types: Snowflake, Databricks, BigQuery, Redshift, PostgreSQL
  - Type-specific field prompts with validation
  - Option to save connection credentials to `.env` after configuration
- **E2E Test Script Enhancement**: Added option to save connection credentials to `.env` after provider_config setup
  - After adding provider_config (dummy or manual), users can save credentials for future use
  - Extracts provider_config from YAML and writes to `.env` in standardized format
- **New Functions**: Added utility functions in `importer/interactive.py`:
  - `save_credentials_to_env()`: Main function for saving credentials with user prompts
  - `prompt_connection_credentials()`: Interactive prompts for connection provider_config
  - Helper utilities: `_get_env_file_path()`, `_read_existing_env()`, `_write_env_file()`, `_format_env_value()`, `_check_gitignore()`
- **Documentation**: Updated `INTERACTIVE_GUIDE.md` and `README.md` with credential saving feature details

### 2025-12-20 (v0.4.4)
- **Version:** Incremented to 0.4.4 (patch release)
- **Critical Fix**: Filter deleted resources (state=2) at fetch time to prevent Terraform type errors
  - Added `_should_include_resource()` helper function in `importer/fetcher.py`
  - Service tokens with `state: 2` are now filtered out during fetch (skipped with debug log)
  - Notifications with `state: 2` are now filtered out during fetch (skipped with debug log)
  - Deleted resources no longer enter the snapshot, eliminating downstream type inconsistencies
  - Fixes "all list elements must have the same type" errors caused by deleted resources with missing/incomplete fields
- **Type Consistency**: Normalized permission object structures for consistent Terraform types
  - Service token permissions now always include `project_id` and `writable_environment_categories` (null/empty if not applicable)
  - Group permissions now always include `project_id` and `writable_environment_categories` (null/empty if not applicable)
  - Ensures all permission objects have identical structure regardless of permission scope
- **Breaking Change**: JSON exports no longer include deleted resources (cleaner snapshots, but different from v0.4.0-0.4.3)
  - Normalization remains backwards compatible (handles missing fields gracefully)
  - Element IDs/line items no longer include deleted resources
- **Testing**: Verified filtering works correctly (0 state=2 resources in new exports, 15 tokens vs 17 before)

### 2025-12-20 (v0.5.4)
- **Version:** Incremented to 0.5.4 (patch release)
- **Terraform for_each with Sensitive Values**: Fixed "Invalid for_each argument" error in `modules/projects_v2/environments.tf`
  - Root cause: Terraform considers `keys()` of a sensitive map as sensitive, preventing its use in `for_each` filters
  - Solution: Wrapped `keys(var.token_map)` with `nonsensitive()` function to mark keys as non-sensitive
  - Keys (token names) are not sensitive; only the token values are sensitive
  - This allows filtering credentials by token availability without exposing sensitive values
  - Fix enables successful Terraform plan execution (97 resources planned to add)
  - Updated `modules/projects_v2/environments.tf` line 24 to use `nonsensitive(keys(var.token_map))`
  - The `nonsensitive()` function (Terraform 0.14+) is designed for this exact use case

### 2025-12-20 (v0.5.2)
- **Version:** Incremented to 0.5.2 (patch release)
- **Connection Type Detection**: Fixed connections showing as "unknown" type
  - Added `_extract_connection_type_from_adapter_version()` function in `importer/fetcher.py`
  - Extracts connection type from `adapter_version` field (e.g., "databricks_v0" → "databricks")
  - Handles all connection types: databricks, snowflake, bigquery, redshift, postgres, athena, fabric, synapse, starburst, apache_spark, teradata
  - Connection types now correctly display in interactive prompts and E2E test output
- **Bracketed Paste Support**: Fixed terminal paste issues in interactive prompts
  - Added `_strip_bracketed_paste_sequences()` filter function to remove escape sequences from pasted input
  - Handles both `\x1b[200~` (escape character) and `^[[200~` (caret notation) formats
  - Applied to all 23 `inquirer.text()` prompts for seamless paste experience
- **Terminal Access**: Fixed "Input is not a terminal" warnings in E2E test script
  - Created standalone `test/configure_connections.py` script to replace Python heredoc
  - Provides proper terminal access for InquirerPy interactive prompts
  - Eliminates CPR (cursor position request) warnings and terminal compatibility issues
- **Environment Variable Standardization**: Standardized source account credential naming
  - Changed `DBT_SOURCE_HOST` to `DBT_SOURCE_HOST_URL` for consistency with target credentials
  - Maintains backward compatibility by checking both variable names
  - Updated `importer/config.py` and `importer/interactive.py` to support both formats
  - Updated documentation and examples to use new naming convention
- **E2E Test Enhancement**: Added automatic provider_config injection from .env files
  - Created `inject_provider_configs_from_env()` function in E2E test script
  - Automatically reads `DBT_CONNECTION_{CONN_KEY}_{FIELD}` variables from .env files
  - Injects provider_config into YAML before prompting user, reducing manual configuration
  - Checks both project root `.env` and test-specific `.env` files
  - Skips interactive prompts if configs are already available

### 2026-01-13 (v0.7.2)
- **Version:** Incremented to 0.7.2 (patch release)
- **Web UI Rebrand**: Renamed from "Account Migration Tool" to "dbt Magellan: Exploration & Migration Tool"
- **Explore Tab Enhancements**:
  - Entity types now have sort-order prefixes (00-ACC, 10-CON, 30-PRJ, etc.) for logical grouping
  - Default sort order: Project → Type → Name (all ascending)
  - Column visibility selector with persisted preferences
  - Enhanced entity detail dialog with "Details" outline view and "JSON (Full)" tab
- **Layout Fixes**: Fixed CSS grid layout issues where Explore tab panels didn't fill available width/height
- **UX Improvements**: 
  - File upload dialog for loading .env files with macOS hidden file tip
  - "Fetch Complete" panel clears on new fetch or .env load

### 2025-12-19 (v0.4.2)
- **Version:** Incremented to 0.4.2 (patch release)
- **Interactive Provider Config**: Added interactive provider configuration step to E2E test workflow
  - Created `configure_provider_configs()`, `add_dummy_provider_configs()`, and `open_editor_and_wait()` functions
  - Added 4-option interactive prompt (dummy config, editor, skip, abort) with database-specific examples
  - Updated E2E testing guide with comprehensive "Phase 3: Provider Configuration" documentation
- **Critical Terraform Fixes**: Resolved 3 type inconsistency errors preventing terraform plan:
  - Fixed conditional type mismatch in `projects_v2` by removing conditionals from locals
  - Fixed service tokens type inconsistency by normalizing deleted tokens (`state: 2`) missing `service_token_permissions`
  - Fixed groups type inconsistency by normalizing special "Everyone" group missing `group_permissions`
  - Updated `main.tf` to rebuild globals and projects as proper lists with consistent field presence
- **Testing Improvements**: 
  - Added default value to `test_vars.tf` to prevent required variable errors
  - Updated E2E test fixture outputs to use v2-prefixed module outputs
  - E2E test now successfully completes terraform validate and plan phases
- **Documentation**: Created comprehensive RELEASE_NOTES_v0.4.2.md with technical details and root cause analysis

### 2025-12-10
- Enhanced Next Steps & Roadmap section with explicit blockers, dependencies, and related limitations
- Added "Prerequisites for API Research" section for items requiring endpoint discovery
- Aligned Semantic Layer timeline across documents (Medium-Term / Next Quarter)
- Linked Known Issues to relevant roadmap items
- Significantly expanded End-to-End Testing Readiness Checklist with:
  - Detailed step-by-step instructions for each testing phase
  - Specific commands and expected outputs
  - Success criteria with clear verification steps
  - Enhanced known risks and mitigations

### 2025-12-10
- Updated version to 0.4.0-dev
- Added Phase 4+ (Interactive Mode) section
- Updated testing section with completed Terratest coverage
- Updated dependencies (InquirerPy, tfenv installation method)
- Added known issues section
- Updated terminology to "Normalize Fetch to dbt Cloud Terraform Module YAML format"

### 2025-01-27
- Created initial status document
- Marked Phases 0-4 as complete
- Documented Phase 3 completion
- Added maintenance instructions

---

**Remember:** Keep this document updated as the project progresses! 🚀

