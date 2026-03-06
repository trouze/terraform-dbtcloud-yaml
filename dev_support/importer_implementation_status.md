# Importer Implementation Status & Tracking

**Last Updated:** 2026-03-05  
**Current Importer Version:** 0.25.0  
**Status:** Phase 3 Complete + Interactive Mode + Web UI + E2E Testing Infrastructure + Destroy Workflow + Target Match Feature + Jobs as Code Generator + dbt-jobs-as-code Validation + SAO Support + Native Integration Detection + Target Credentials Redesign + Resource Protection with Cascade + Destroy Page Enhancements + State-Aware Matching Fix + Match Diagnostics Improvements + AG Grid Standardization + Dialog Width Fix + Protection Mismatch Fix + Adoption Override Data Flow Fix + Debug Logging Standards + View Output Plan Dialog Fix + Independent Protection Architecture + Comprehensive Protection Unit Tests + Repository Key Prefix Matching Fix + Extended Attributes (EXTATTR) Support + Target Intent State File + Protection as Disposition Property + Explicit Global Intent Filtering + Drift Detection + TF State Repo Identity Fixup + Global Resources Configuration + Protection Intent Key Fix + EnvVar Protection + State-Only Resource Fixes + TF Plan Stability + Plan Targeting Fix + Deploy Page State-Based Protection

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
- **Current:** 0.25.0
- **File:** `importer/VERSION`
- **Last Updated:** 2026-03-05

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

### 2026-03-05 (v0.25.0)
- **Version:** Incremented to 0.25.0 (minor release - state management refresh-only workflows + clone strategy and job row fixes)
- **Added:** State Management refresh-only workflows for safe state inspection
- **Fixed:** Repository clone strategy preservation during normalization
- **Fixed:** Target job rows retained when environment credentials are null
- **Documented:** GitLab deploy_token API 500 root cause via Datadog traces (backend PR #16687)

### 2026-03-02 (v0.24.0)
- **Version:** Incremented to 0.24.0 (minor release - removal management utility + normalization and workflow hardening)
- Added dedicated Removal Management utility page (`/removal-management`) for explicit `terraform state rm` workflows with filtering, preview, and confirmation.
- Fixed object-type filtering on Removal Management to support persistent multi-select behavior and show per-type counts.
- Hardened match/unadopt intent replay by supporting `removal_keys` values with and without the `target__` prefix.
- Deduplicated normalized group permissions to avoid Terraform set collisions for duplicate permission payloads.

### 2026-02-20 (v0.23.4)
- **Version:** Incremented to 0.23.4 (patch release - startup navigation latency hardening)
- Removed blocking account-name API verification from startup state refresh so initial page transitions no longer incur intermittent ~1.6s delays.
- Added `verify_account_name` control to account-info loading, preserving explicit verification behavior in credential/test flows while keeping route startup lightweight.
- Verified improved route responsiveness across repeated `fetch_source ↔ fetch_target` navigation cycles.

### 2026-02-19 (v0.23.3)
- **Version:** Incremented to 0.23.3 (patch release - Adopt/Match stability + AG Grid regression hardening + repo hygiene)
- Fixed Adopt-page AG Grid regressions where counts were correct but rows/headers were visually blank under certain theme and row-shaping conditions.
- Hardened adopt plan execution with safer fallback config/init sequencing and retry handling around transient module-install failures.
- Improved Match/Target Intent consistency for state-loaded indicators, pending/action status behavior, and cross-page transitions.
- Added AG Grid standards/guardrails + contract tests to prevent reintroduction of Adopt whiteout regressions.
- Expanded ignore coverage and removed local runtime log artifacts from tracked release content.

### 2026-02-18 (v0.23.2)
- **Version:** Incremented to 0.23.2 (patch release - UI compatibility + performance stabilization)
- Fixed `ui.html` sanitize-signature regression in ERD and HTML detail renderers via compatibility fallback pattern.
- Removed stale debug instrumentation file writes from runtime hotspots (`utilities`, `destroy`, `protection_manager`, temporary perf logging).
- Bounded terminal and Terraform output rendering in Adopt/Deploy flows to reduce websocket pressure and improve perceived responsiveness.
- Added and documented guardrail for NiceGUI `ui.html` sanitize compatibility to prevent reintroduction.

### 2026-02-18 (v0.23.1)
- **Version:** Incremented to 0.23.1 (patch release - Adopt output dialog stability)
- Fixed NiceGUI compatibility issue where `View Output` could crash with `TypeError: __init__() got an unexpected keyword argument 'sanitize'`
- `create_plan_viewer_dialog` now uses a version-compatible fallback for `ui.html` rendering, preserving output viewer functionality across local NiceGUI variants
- Browser validation confirmed stable output dialog behavior on `/adopt` after repeated Plan + View Output cycles

### 2026-02-17 (v0.23.0)
- **Version:** Incremented to 0.23.0 (minor release - Protection Management Overhaul + Workflow Alignment + Architecture Docs)
- Protection Management page upgraded to full intent editing surface with Intent + State columns and state-only resource visibility
- Canonical shared contracts defined for reconcile source, generate entrypoint, and terraform helpers
- Shared `terraform_helpers.py` module consolidates `get_terraform_env`, `resolve_deployment_paths`, `run_terraform_command`
- `adopt.py`, `deploy.py`, `destroy.py` delegate to shared helpers instead of inline copies
- 37 new tests: contract enforcement, state visibility regression, cross-page pipeline consistency, terraform helpers equivalence
- Architecture docs: `canonical-contracts.md`, `workflow-mapping.md`, `refactoring-tasks.md`
- PRD governance updates: reuse-first + test-gate requirements added to all intent-related PRDs
- Match page stat tiles replaced with compact chip bar
- Fixed: protected `GRP:member` visibility, unprotection loop (`sse_dm_fin_fido`), misleading toast on move-only plans, preflight credential validation, reconcile state refresh after plan/apply, Python 3.9 compatibility

### 2026-02-12 (v0.22.0)
- **Version:** Incremented to 0.22.0 (minor release - Dedicated Adopt Resources Page)
- New `/adopt` page with AG Grid, two-step Plan/Apply workflow, targeted TF plan, auto YAML injection/cleanup
- Comprehensive resource type address mapping for `projects_v2` module
- State backup & restore for safe rollback

### 2026-02-11 (v0.21.2)
- **Version:** Incremented to 0.21.2 (patch - Deploy Page State-Based Protection Detection)
- Deploy page generate now always runs YAML-vs-State comparison, not just when no previous YAML exists
- Added `dbtcloud_environment_variable` to `generate_moved_blocks_from_state` type_map and YAML protection map
- Stale `protection_moves.tf` cleanup when no protection changes detected

### 2026-02-11 (v0.21.1)
- **Version:** Incremented to 0.21.1 (patch - Plan Targeting Fix + Sub-Resource Mismatch Detection)
- Terraform plan `-target` flags now include all moved block addresses from `protection_moves.tf`, fixing "Moved resource instances excluded by targeting" errors
- `detect_protection_mismatches` extended to cover ENV, JOB, VAR, and EXTATTR resources, catching orphaned YAML protection flags from prior sessions

### 2026-02-11 (v0.21.0)
- **Version:** Incremented to 0.21.0 (minor release - EnvVar Protection + State-Only Resource Fixes + TF Plan Stability)
- Full protection lifecycle for dbt Cloud environment variables (VARs) — TF module split, protection manager, YAML updater
- State-only resource detail panel now correctly displays target/state data
- Terraform plan no longer destroys protected VARs when deploy YAML has empty `environment_variables: []`
- Baseline merge no longer introduces target-only projects (e.g., `not_terraform`) into deploy config
- Protection key mismatch fixed for state-only resources (normalized `state__<tf_address>` → `TYPE:short_key`)
- Project-scoped element IDs prevent cross-project VAR matching collisions

### 2026-02-11 (v0.20.0)
- **Version:** Incremented to 0.20.0 (minor release - Global Resources Configuration + Protection Intent Key Fix + Undo Handler Fix)
- Global Resources card on Configure page with TF state safety-net detection
- Protection intent key normalization for sub-project resources (ENV, JOB, EXTATTR)
- Undo/Clear pending intents now revert protected_resources state
- Synced intents panel: protected first, unprotected below the fold

### 2026-02-10 (v0.19.0)
- **Version:** Incremented to 0.19.0 (minor release - Explicit Global Intent Filtering + Drift Detection + TF State Repo Identity Fixup)
- Explicit `included_globals` parameter on `compute_target_intent()` to control which global sections (groups, service_tokens, etc.) appear in output config
- `config_preference` field on `ResourceDisposition` for target vs source value tracking
- TF state repo identity fixup prevents protected repository destruction from attribute drift
- `job_type` serialized in normalizer; `compare_changes_flags` always passed through in TF module
- Provider-side fixes for `cost_optimization_features`, `job_type`, `compare_changes_flags` `(known after apply)` noise

### 2026-02-09 (v0.18.0)
- **Version:** Incremented to 0.18.0 (minor release - Target Intent State File + Protection as Disposition Property)
- **Target Intent as Authoritative State File**: `target-intent.json` is now the single, self-contained source of truth for deployment
  - `output_config` (merged YAML dict) persisted directly inside `target-intent.json`
  - Match page computes full target intent (dispositions + output_config + protection) and persists it
  - Deploy page loads persisted intent, re-validates against current TF state, uses `output_config` directly
  - `normalize_target_fetch()` utility lazily normalizes target fetch data for retained project config
- **Protection as a Disposition Property**: Per-resource `protected` field on `ResourceDisposition`
  - 4-level priority chain: default false < TF state override < protection-intent.json < user edit
  - Write-through sync: UI protection edits automatically update target intent dispositions
  - Deploy sources protection from dispositions instead of separate `ProtectionIntentManager`
- **New Tests**: 17 new unit tests for protection defaults, output_config round-trip, retained project config, disposition sync

### 2026-01-27 (v0.17.0)
- **Version:** Incremented to 0.17.0 (minor release - Extended Attributes Support)
- **Extended Attributes (EXTATTR) Full Support**: End-to-end support for `dbtcloud_extended_attributes` resource
  - Data model: `ExtendedAttributes` Pydantic model with `extended_attributes` payload dict
  - Fetcher: Project-level extended attributes fetched and included in account snapshots
  - Element IDs: EXTATTR entities registered with project context and unique keys
  - Reporter: EXTATTR counts in summary and detailed reports
  - Normalizer: EXTATTR normalization to Terraform YAML format
  - Schema: v2.json updated with `extended_attributes` definitions
  - Terraform module: `extended_attributes.tf` resource generation
- **UI Coverage Across All Screens**:
  - Fetch Source/Target: EXTATTR progress tracking and completion summary counts
  - Explore Source/Target: EXTATTR entities in entity grid with type filter, detail popup showing attribute payload values
  - Select Source (scope.py): EXTATTR in TYPE_CODE_MAP
  - Match Existing (mapping.py): EXTATTR in RESOURCE_TYPES, TYPE_CODE_MAP, resource_filter_map, type_to_filter
  - Deploy: EXTATTR in type_labels for protected resources, confirmed mappings, and destroy warnings
  - Protection Manager: EXTATTR in TYPE_LABELS, format_protection_warnings, detect_protection_mismatches, generate_repair_moved_blocks, format_mismatches_for_display
  - Entity Detail Popup: New "Attribute Payload" section showing actual connection override key-value pairs
  - Dialog title fallback: Uses `key` when `name` is absent (benefits EXTATTR and similar keyless entities)
- **PRD Updates**: Created PRD 41.02 (Adding New Terraform Object Support) with comprehensive checklist, debugging standards, abbreviation standards, and file touchpoint reference
- **Abbreviation Standardization**: Renamed all `EAT` references to `EXTATTR` across codebase

### 2026-01-30 (v0.15.9)
- **Version:** Incremented to 0.15.9 (patch release - Debug Logging Standards)
- **Debug and Logging Standards PRD**: Created comprehensive `tasks/prd-web-ui-12-debug-logging-standards.md`
  - Permanent instrumentation policy - debug logging must NOT be removed
  - Structured logging patterns for UI actions, state changes, and errors
  - Function call tracing standards using `@traced` decorator
  - Log file locations and schema definitions
- **Debug Instrumentation Rule**: Created `.cursor/rules/debug-instrumentation.mdc` enforcing preservation of all debug code
- **Function Call Tracing**: Enhanced `importer/web/utils/ui_logger.py` with:
  - `@traced` decorator for automatic function entry/exit logging
  - `@traced_async` decorator for async functions
  - Safe serialization for non-JSON-serializable types
- **Protection Manager Tracing**: Added `@traced` decorator to key functions:
  - `generate_moved_blocks_from_state()`
  - `detect_protection_mismatches()`
  - `write_moved_blocks_file()`

### 2026-01-30 (v0.15.8)
- **Version:** Incremented to 0.15.8 (patch release - Adoption Override Data Flow Fix)
- **Critical Bug Fix**: Fixed adoption overrides not being applied during Generate step
  - `confirmed_mappings` in match.py was not storing the `action` field
  - deploy.py's filter for `action == "adopt"` always failed because action was never stored
- **Match Mapping Updates**: Fixed `auto_match_all()` and `on_accept()` to store `action` field in mappings
- **Action Filter Fix**: Updated deploy.py to accept "match", "adopt", or `None` for backward compatibility
- **Repository Adoption**: Repository `remote_url` and `git_clone_strategy` now correctly inherit target account values

### 2026-01-29 (v0.15.7)
- **Version:** Incremented to 0.15.7 (patch release - Protection Mismatch Fix)
- **Critical Bug Fix**: Fixed catastrophic bug in `apply_adoption_overrides` that defaulted `protected=True` for ALL adopted resources
  - Changed default from `protected=True` to `protected=False` - protection must be explicitly opted-in
  - Prevented Terraform from destroying and recreating all projects when only one resource needed status change
- **State Persistence**: Fixed JSON serialization of protection sets in `MapState.to_dict()`
- **Unprotection Logic**: Added `apply_unprotection_from_set()` to explicitly remove `protected: true` flags

### 2026-01-29 (v0.15.1)
- **Version:** Incremented to 0.15.1 (patch release - State-Aware Matching Fix)
- **Match Debug Tab**: New debugging tab in resource detail popup with diagnostics and LLM report
- **State-Aware Repo Matching**: Fixed project-linked repositories not matching when names differ
- **Composite ID Parsing**: Fixed extraction of resource IDs from composite Terraform IDs (e.g., "605:556")
- **Type Normalization**: Fixed type mismatches in state-to-target ID lookups

### 2026-01-29 (v0.15.0)
- **Version:** Incremented to 0.15.0 (minor release - Destroy Page Protection Enhancements)
- **Destroy Section**: New destroy section in Deploy page with auto-skip protected resources
- **Target-Based Destroy**: Uses `-target` flags to only destroy unprotected resources
- **Protection Panel**: Displays protected resources grouped by type with unprotect option
- **Unprotect Dialog**: Confirmation dialog for explicit unprotection before destroy
- **Module Updates**: Split all resources into protected/unprotected maps with `prevent_destroy` lifecycle
- **Schema Updates**: Added `protected` field to project, environment, job, repository in v2 schema
- **Drift Detection Fix**: Improved drift counting to exclude "state_only" orphan resources
- **Project ID Lookups**: Added `coalesce()`-based lookups in globals.tf and env_var_project_id_lookup in environment_vars.tf

### 2026-01-28 (v0.14.0)
- **Version:** Incremented to 0.14.0 (minor release - Resource Protection with Cascade)
- **Protection Grid Column**: Added protection checkbox column (🛡️) to Match Existing grid
- **Cascade Protection**: Protecting a child auto-protects parents (Job→ENV→PRJ, Credential→ENV→PRJ, etc.)
- **Confirmation Dialogs**: Shows parent resources to be protected, asks about cascade unprotection
- **Protected Row Styling**: Blue left border and subtle background for protected resources
- **State Persistence**: `protected_resources` set tracked in MapState for session persistence
- **YAML Integration**: `apply_protection_from_set()` applies protection flags during Terraform generation
- **PRD Update**: Added cascade protection user stories (US-RP-70 to US-RP-80) and test cases (CP-RP-01 to CP-RP-18)

### 2026-01-28 (v0.13.1)
- **Version:** Incremented to 0.13.1 (patch release - CRD Matching Fix)
- **Credential Matching**: Fixed CRD items showing "create new" when they should match target credentials
- **Environment-Based Lookup**: Added `target_crd_by_env` dictionary to match credentials by parent environment
- **Matching Logic**: CRD items now fall back to `(project_name, environment_name)` lookup when exact name match fails

### 2026-01-28 (v0.13.0)
- **Version:** Incremented to 0.13.0 (minor release - Enhanced Plan Summary & Persistent Execution Logs)
- **Plan Import Count**: Plan summary now correctly parses and displays "X to import" alongside add/change/destroy
- **Plan Viewer Updates**: Purple badge for imports, purple highlighting for import-related lines
- **Persistent Execution Logs**: Added `reconcile_execution_logs` to DeployState for logs that survive page reloads
- **View Logs Enhancement**: Generate Import Blocks operations now logged and viewable in Match Existing page

### 2026-01-22 (v0.12.5)
- **Version:** Incremented to 0.12.5 (patch release - Connection ID-Based Dependency Resolution)
- **Connection ID Field**: Added `connection_id` to Environment model for reliable ID-based lookups
- **ID-Based Index**: Added `_connection_by_id` index to HierarchyIndex with `get_connection_by_id()` method
- **Select Parents Fix**: Changed connection lookup from key-based to ID-based with key fallback
- **Unit Tests**: Added comprehensive tests for HierarchyIndex connection ID functionality
- **Backward Compatibility**: Existing report items without `connection_id` still work via key-based fallback

### 2026-01-22 (v0.12.4)
- **Version:** Incremented to 0.12.4 (patch release - Private Key Validation & Normalization)
- **PEM Validator Module**: New `pem_validator.py` with validation and normalization functions
- **Auto-Normalization**: Private keys auto-reformatted on blur (fixes single-line pasted keys)
- **Validation Badges**: Real-time UI feedback showing Valid/Invalid status with tooltips
- **Enhanced Input**: Multi-line textarea for private key entry with monospace font
- **Server-Side Normalization**: Keys normalized before saving to `.env` file

### 2026-01-22 (v0.12.3)
- **Version:** Incremented to 0.12.3 (patch release - Private Key Escaping Fix)
- **Private Key HCL Escaping**: Fixed multi-line PEM keys causing Terraform parse errors in `secrets.auto.tfvars`
- **Valid Dummy Private Key**: Replaced invalid placeholder with syntactically valid 2048-bit RSA key (PKCS#8)
- **Dummy Credential Indicator**: Changed to environment name suffix `[DUMMY CREDENTIALS]` for better UI visibility

### 2026-01-16 (v0.11.1)
- **Version:** Incremented to 0.11.1 (patch release - Native Integration Detection)
- **Native Integration Detection**: Auto-detects GitHub App, GitLab, Azure DevOps native integrations from source repositories
- **PAT Auto-Switch**: Auto-switches target credentials to PAT when native integrations detected
- **Warning Banner**: Displays warning on Fetch Target page when source has native integration repos
- **Token Type Auto-Detection**: Token type detected from prefix (`dbtc_*` = Service Token, `dbtu_*` = PAT)
- **Terraform Plan Logging**: Added terminal output showing token type and PAT configuration status
- **git_clone_strategy Fix**: Fixed showing as `(sensitive value)` in Terraform plan output
- **GitHub Integration Debug**: Enhanced Terraform module output for debugging GitHub App integration discovery

### 2026-01-16 (v0.11.0)
- **Version:** Incremented to 0.11.0 (minor release - SAO Support)
- **SAO Support**: Added `force_node_selection` and `cost_optimization_features` fields to job normalization
- **SAO Support**: Automatic CI/Merge job detection to omit `force_node_selection` (API requirement)
- **Terraform Module**: Updated `jobs.tf` with SAO attribute handling and CI/Merge job detection
- **YAML Schema**: Updated v2 schema with SAO field definitions
- **Jobs as Code Generator**: Extended `_build_job_dict()` to include SAO fields with CI/Merge job handling
- **Documentation**: Added SAO section in `importer/README.md` with migration guide

### 2026-01-15 (v0.9.1)
- **Version:** Incremented to 0.9.1 (patch release - Bug fixes)
- **Target Match Feature**: Added Source/Target toggle to Fetch page for target infrastructure fetching
- **Target Match Feature**: New target_matcher.py component for exact name matching between source and target resources
- **Target Match Feature**: New mapping_file.py utility for creating/loading target resource mapping files
- **Target Match Feature**: New terraform_import.py utility for generating TF 1.5+ import blocks
- **Test Suite Fix**: Fixed `test_name_collision_handling` - assertion was checking wrong dict level
- **Python 3.9 Fix**: Changed `str | Path` union syntax to `Union[str, Path]` for compatibility

### 2026-01-15 (v0.8.1)
- **Version:** Incremented to 0.8.1 (patch release - Deploy page UI polish)
- **Deploy Page**: Dynamic Output panel title showing current step (GENERATE, INIT, VALIDATE, etc.)
- **Deploy Page**: Status colors for buttons - green (success), yellow (warnings), red (errors)
- **Terminal Output**: ISO8601 timestamps with timezone offset
- **Terminal Output**: Auto-detection of warning/error messages from terraform output
- **Terminal Output**: Wider search bar (250px)
- **Deploy Page**: Buttons properly reset visual state when regenerating files

### 2026-01-14 (v0.8.0)
- **Version:** Incremented to 0.8.0 (minor release - OAuth/SSO credential support)
- **OAuth/SSO Support**: Full OAuth credential configuration for Snowflake, Databricks, and BigQuery connections
- **Connection Credentials Variable**: New `connection_credentials` Terraform variable for passing OAuth secrets
- **Secrets Auto-Generation**: `secrets.auto.tfvars` file generated with OAuth credentials (auto-loaded by Terraform)
- **OAuth Warning Cards**: Warning in Target page explaining OAuth integrations cannot be reused from source
- **Documentation Links**: Links to dbt platform OAuth setup guides (Snowflake SSO, External OAuth, Databricks, BigQuery)
- **Terraform Module**: Added OAuth fields to `globals.tf` for all connection types
- **Target Page**: OAuth fields grouped under "OAuth / SSO Configuration" section
- **Target Page**: Source reference card now displays host URL
- **Deploy Page**: Apply checkmark shows after successful deployment, all checkmarks reset on regenerate
- **Credential Loading Fix**: Fixed regex pattern to correctly parse multi-part field names from .env

### 2026-01-14 (v0.7.9)
- **Version:** Incremented to 0.7.9 (patch release - Job deferral fixes, Deploy page improvements)
- **Job Deferral Fixes**: Fixed `self_deferring` and `deferring_environment_id` conflict handling
- **Normalizer**: Added self-deferral detection from `deferring_job_definition_id`
- **Job Validation**: `run_compare_changes` disabled when job defers to same environment (API requirement)
- **Deploy Page**: Added View Output buttons for Generate/Init/Validate, View Apply logs button
- **Deploy Page**: Added Terraform validate step, auto-open View Plan after successful plan
- **Deploy Page**: Redesigned layout with horizontal tiles and side-by-side Plan/Apply with terminal
- **Map Page**: Renamed scope controls, fixed connection dependency warnings, auto-refresh on bulk select

### 2026-01-14 (v0.7.8)
- **Version:** Incremented to 0.7.8 (patch release - Phase 2 Map complete)
- **YAML Preview Search**: Real-time search with highlighting, match count ("X of Y"), and prev/next navigation
- **Phase 2 Map Complete**: All Map step user stories fully implemented (US-028 through US-036)

### 2026-01-14 (v0.7.7)
- **Version:** Incremented to 0.7.7 (patch release - Map entity popup, fetch timing, UI improvements)
- **Map Page: Entity Detail Popup**: Click any row to view entity details (same as Explore tab)
- **Fetch Page: Total Time Log**: Fetch duration displayed in final summary
- **Fetch Page: Threads Fix**: Threads setting now correctly persists and applies via `e.args` event handling
- **Entity Detail Dialog**: Resized to match View YAML popup (height: 80vh, width: max-w-4xl)
- **Map Page: Selection Summary**: Progress bar shows percentage instead of decimal

### 2026-01-13 (v0.7.6)
- **Version:** Incremented to 0.7.6 (patch release - Fetch cancel button, threads option, Explore type codes)
- **Fetch Page: Cancel Button**: Cancel fetch operations in progress
- **Fetch Page: Threads Option**: Configurable threads input (1-20) for parallel API requests
- **Explore Tab: Display Codes**: Type dropdown shows "Name (CODE) [count]" format
- **Explore Tab: Entity Dialog**: Badge and Type chip show "Name (CODE)" format
- **Fetcher**: `fetch_account_snapshot` accepts optional `cancel_event` parameter for cancellation

### 2026-01-13 (v0.7.5)
- **Version:** Incremented to 0.7.5 (patch release - Scope/Resource filters functional, repository-project linking)
- **Map Page: Scope Settings Functional**: Filter by All Projects, Specific Projects, or Account Only
- **Map Page: Resource Filters Functional**: Toggle entity types on/off for target config generation
- **Map Page: Selection Summary Enhanced**: Shows "Effective (after filters)" count with per-type breakdown
- **Map Page: Reset Filters Button**: Reset to "All Types" with "Selected Only" off
- **Map Page: Auto-cascade Fix**: State updates immediately when toggle clicked (timing bug fixed)
- **Map Page: Parent-child Selection**: Account entity excluded from cascade operations
- **Normalizer Fixes**: Added `exclude_ids` filtering to environments, jobs, environment_variables
- **Normalizer Fix**: Resource filter key mismatch corrected
- **Pydantic Models**: Added `extra='allow'` to preserve `element_mapping_id` fields
- **Repositories**: Now linked to parent projects via `metadata.project_id`
- **Explore Tab**: Repositories show Project name and ID columns

### 2026-01-13 (v0.7.4)
- **Version:** Incremented to 0.7.4 (patch release - Map page filter persistence)
- **Map Page: Filter State Persistence**: Filters now survive theme toggles, normalization, and page reloads
  - Type filter selection persists in session state
  - "Selected Only" filter toggle persists in session state
  - Filters applied on initial grid render from persisted state
- **Map Page: Visual State**: "Selected Only" button shows correct highlighted state on page load when active

### 2026-01-13 (v0.7.3)
- **Version:** Incremented to 0.7.3 (patch release - Web UI entity table fixes)
- **Web UI: Entity Table Column Visibility**: Fixed column selector not properly updating grid display
  - Using AG Grid's `setGridOption` API for reliable column updates
- **Web UI: Duplicate Column Names**: Fixed "Sort Key 2", "Name 3", "Project 1" appearing in table headers
  - Root cause: AG Grid's `initialState.sortModel` and column-level `sort`/`sortIndex` properties creating phantom columns
  - Removed all sorting-related properties that caused conflicts with NiceGUI's AGGrid component
- **Web UI: Column Selector Enhancements**: Added "Default" button to reset to optimized columns per entity type
- **Web UI: Column Header**: Changed "#" to "Line #" for clarity

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

### 2026-01-21 (v0.12.0)
- **Version:** Incremented to 0.12.0 (minor release - significant new features)
- **Target Credentials Page Redesign**: Complete overhaul of environment credentials editing
  - Edit dialog with CSS Grid columnar layout for consistent field alignment
  - "From source" (green) and "Override" (yellow) indicators for field values
  - Per-field reset buttons to restore individual fields to source values
  - "Use Dummy Credentials" toggle with source vs dummy comparison table
  - Authentication type selector with source/override indicators and reset
  - "Reset to Dummy Credentials" button in environment actions
- **Credential Metadata Extraction**: Enhanced source value extraction from YAML
  - Extracts auth_type, authentication, auth_method fields
  - Automatic auth_type inference for Snowflake from private_key/password presence
- **Progress Visibility**: Renamed "Credentials" to "Credential Metadata (No Secret Values)"
  - Renamed "Env Variables" to "Env Variables (No Secret Values)"
- **Workflow Changes**: "Fetch Target" now accessible at any time
  - "Match Existing" requires both source and target fetch completion
- **Layout Stability**: Eliminated fetch page layout shift issues
  - Redesigned to vertical stack layout
  - Compact credential input forms

### 2026-01-16 (v0.10.1)
- **Version:** Incremented to 0.10.1 (patch release - feature enhancement)
- **dbt-jobs-as-code Validation**: Optional integration with `dbt-jobs-as-code` for native schema validation
  - Runtime detection of package availability
  - "Validate with dbt-jobs-as-code" button on Generate page
  - Structured validation results with job count and detailed errors
  - Fallback UI with install instructions when package not available
- **Auto-deduplication**: Automatic identifier deduplication for duplicate job names
  - Appends numeric suffixes (_2, _3, etc.) to duplicate identifiers
  - Non-blocking warnings in amber banner on Generate page
- **Bug Fix**: Fixed NiceGUI ObservableDict/ObservableList leaking into YAML output

### 2026-01-16 (v0.10.0)
- **Version:** Incremented to 0.10.0 (minor release - new feature)
- **Jobs as Code Generator Workflow**: New web UI workflow for generating `dbt-jobs-as-code` compatible YAML files
  - Workflow Selection Page with "Adopt Existing Jobs" and "Clone / Migrate Jobs" options
  - Fetch Jobs Page for entering dbt Cloud credentials
  - Select Jobs Page with interactive job selection grid
  - Configure Jobs Page for job naming and output format settings
  - Generate YAML Page with preview, validation, and export
- **State Management**: Added `JobsAsCodeState` dataclass with full serialization/deserialization
- **Utility Modules**: Created job_fetcher.py, yaml_generator.py, and validator.py
- **UI Components**: Created job_grid.py, mapping_table.py, and yaml_preview.py
- **Bug Fix**: Fixed workflow selection cards not updating visually when clicked

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

### 2026-01-27 (v0.12.6)
- **Version:** Incremented to 0.12.6 (patch release)
- **GitHub Installations API Error Handling**: Fixed Terraform plan failure when GitHub integration is disassociated
  - API returns error string instead of expected array, which `jsondecode()` parses as a string
  - Caused "Inconsistent conditional result types" error in `modules/projects_v2/data_sources.tf`
  - Solution: Wrapped decode in `try(tolist(jsondecode(...)), [])` to ensure consistent list type

### 2026-02-05 (v0.16.2)
- **Version:** Incremented to 0.16.2 (patch release - bug fix)
- **Repository Key Prefix Matching Fix**: Fixed bug where `apply_protection_from_set` failed to match repository keys with prefixes
  - YAML repository keys have prefixes like `dbt_ep_` (e.g., `dbt_ep_sse_dm_fin_fido`)
  - Intent keys use base names (e.g., `REP:sse_dm_fin_fido`)
  - Now uses flexible matching: exact match first, then checks if `repo_key.endswith(base_key)` or `base_key in repo_key`
  - This fixes the "Moved object still exists" terraform error when protection intent repair failed to update YAML
- **New Tests**: Added 8 tests for repository key prefix matching (`TestRepositoryKeyPrefixMatching`, `TestIntentYamlRepairWithPrefixedRepos`)

### 2026-02-05 (v0.16.1)
- **Version:** Incremented to 0.16.1 (patch release - testing)
- **Comprehensive Protection System Unit Tests**: Added 162 protection-related unit tests
  - `test_adoption_yaml_updater.py` (22 tests): Tests for YAML modification functions
  - `test_protection_edge_cases.py` (26 tests): Key prefix, toggle, error recovery scenarios
  - `test_protection_state_consistency.py` (14 tests): Cross-system state validation
  - `test_protection_sync.py` (16 tests): Protection intent to state.map sync
  - `test_protection_manager.py` (52 tests): Moved blocks, cascade functions, mismatch detection
  - Enhanced `test_protection_intent.py` (+12 edge case tests)
- **PRD Organization**: Reorganized PRD documents using Johnny Decimal methodology

### 2026-02-02 (v0.16.0)
- **Version:** Incremented to 0.16.0 (minor release - new feature)
- **Independent Protection Architecture**: Implemented separate protection scopes for projects vs repositories
  - Project protection (PRJ:) is independent - protecting a project does not affect its repository or project-repository link
  - Repository + PREP protection (REPO:) is paired - they are always protected/unprotected together
  - Added `repository_protected` YAML field for explicit control
  - Updated Terraform module with independent repository protection routing logic
  - Consolidated Protection Intent keys from `REP:` + `PREP:` to single `REPO:` prefix
- **Bug Fix**: Fixed `Moved object still exists` Terraform error when using independent protection

### 2026-01-29 (v0.15.2)
- **Version:** Incremented to 0.15.2 (patch release)
- **Match Diagnostics Improvements**: Comprehensive fixes for key comparison in Match Debug tab
  - Added project-prefixed key recognition (`{project_name}_{source_key}` patterns)
  - Added deduplication suffix support (`_2`, `_3` patterns from Terraform key collisions)
  - Added name-keyed resource handling (VAR, JEVO matched by name, not key)
  - Added no-state handling for resources without Terraform state tracking
  - Added normalized key support for Terraform (hyphens → underscores in for_each keys)
  - Fixed confidence tracking to preserve specific match types (state_id_match, env_match, etc.)
  - Key mismatches now correctly identified as cosmetic vs actual issues

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

