# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Note:** When updating versions, refer to [Version Update Checklist](dev_support/VERSION_UPDATE_CHECKLIST.md) for all locations that need updates.

## [Unreleased]

## [0.5.3] - 2025-12-20

### Fixed
- **Terraform Provider Connection**: Fixed "Unsupported Authorization Type" error in E2E test
  - Root cause: Test fixture (`test/e2e_test/main.tf`) wasn't passing `dbt_account_id`, `dbt_token`, and `dbt_host_url` variables to the module
  - Module's provider was using default `https://cloud.getdbt.com` instead of actual instance URL (e.g., `https://iq919.us1.dbt.com/api`)
  - Added variable definitions to test fixture and explicitly passed credentials to module
  - Provider now correctly connects to custom domain instances for multi-tenant deployments
- **E2E Test Script**: Cleaned up debug instrumentation from provider connection debugging session

### Changed
- **E2E Test Configuration**: Enhanced test fixture to properly configure Terraform provider
  - Added `dbt_account_id`, `dbt_token`, and `dbt_host_url` variables to `test/e2e_test/main.tf`
  - Provider block now uses variables instead of empty configuration
  - Module call explicitly passes credentials to ensure proper provider inheritance

### Technical Details
- Updated `test/e2e_test/main.tf` to define and pass credential variables to module
- Removed debug instrumentation from `test/run_e2e_test.sh` (curl diagnostics, logging statements)
- Provider configuration now correctly inherits from root module to child modules

## [0.5.2] - 2025-12-20

### Fixed
- **Connection Type Detection**: Fixed connections showing as "unknown" type
  - Added `_extract_connection_type_from_adapter_version()` function to derive connection type from `adapter_version` field
  - The dbt Cloud API v3 returns `"type": null` but provides `"adapter_version": "databricks_v0"` or `"snowflake_v0"`
  - Connection types now correctly display as "databricks", "snowflake", "bigquery", etc. instead of "unknown"
- **Bracketed Paste Sequences**: Fixed terminal paste issues in interactive prompts
  - Added `_strip_bracketed_paste_sequences()` filter to remove escape sequences (`^[[200~`, `^[[201~`) from pasted input
  - Applied filter to all 23 `inquirer.text()` prompts throughout interactive mode
  - Handles both escape character format (`\x1b[200~`) and caret notation (`^[[200~`)
- **Terminal Access**: Fixed "Input is not a terminal" and CPR warnings in E2E test script
  - Replaced Python heredoc (`python - <<'SCRIPT'`) with standalone `test/configure_connections.py` script
  - Provides proper terminal access for InquirerPy interactive prompts
  - Eliminates terminal compatibility warnings when running interactive connection configuration

### Changed
- **Environment Variable Naming**: Standardized source account credential variable names
  - Changed `DBT_SOURCE_HOST` to `DBT_SOURCE_HOST_URL` for consistency with target credentials
  - Maintains backward compatibility by checking both variable names
  - Updated `importer/config.py` to prefer `DBT_SOURCE_HOST_URL` but fall back to legacy `DBT_SOURCE_HOST`
  - Updated documentation and examples to use new naming convention
- **E2E Test Script**: Enhanced provider configuration workflow
  - Added `inject_provider_configs_from_env()` function to automatically inject connection configs from `.env` files
  - Checks both project root `.env` and test-specific `.env` files
  - Reads `DBT_CONNECTION_{CONN_KEY}_{FIELD}` environment variables and converts to YAML `provider_config`
  - Skips interactive prompts if configs are already available in `.env` files
  - Improves test automation and reduces manual configuration steps

### Technical Details
- Updated `importer/fetcher.py` to extract connection type from `adapter_version` when API `type` field is null
- Updated `importer/interactive.py` with bracketed paste filter and standardized variable naming
- Created `test/configure_connections.py` standalone script for proper terminal access
- Updated `test/run_e2e_test.sh` with automatic `.env` injection and improved error handling
- Environment variable format: `DBT_CONNECTION_{CONNECTION_KEY}_{FIELD_NAME}` (e.g., `DBT_CONNECTION_DATABRICKS_DEV_UC_ENABLED_HOST`)

## [0.5.1] - 2025-12-20

### Fixed
- **Environment Variable Naming**: Standardized environment variable names for consistency
  - Changed target account variables from `DBTCLOUD_*` to `DBT_TARGET_*` to match `DBT_SOURCE_*` pattern
  - Fixed target token variable to use `DBT_TARGET_API_TOKEN` instead of `DBT_TARGET_TOKEN`
  - Updated E2E test script and documentation to use consistent naming
- **Source Account Variables**: Fixed E2E test script to use `DBT_SOURCE_*` variables instead of `DBT_CLOUD_*`
  - Updated prerequisite checks and references throughout E2E test script
  - Updated documentation to reflect correct variable names

### Changed
- **Interactive Connection Configuration**: Replaced nano editor with Python menu-driven prompts
  - Enhanced `prompt_connection_credentials()` with schema-based field definitions
  - Added required vs optional field indicators with descriptions
  - Improved validation and user experience for connection provider_config entry
  - Supports all connection types: Snowflake, Databricks, BigQuery, Redshift, PostgreSQL, Athena, Fabric, Synapse
  - Created `CONNECTION_SCHEMAS` dictionary with field requirements and descriptions
  - Added `prompt_connection_credentials_interactive()` wrapper function that updates YAML automatically

### Technical Details
- Updated `test/run_e2e_test.sh` to use Python interactive function instead of nano editor
- Updated `importer/interactive.py` with connection schema definitions and enhanced prompting logic
- Environment variable mapping: `DBT_TARGET_*` → `TF_VAR_dbt_*` and `DBT_CLOUD_*` for Terraform provider compatibility

## [0.5.0] - 2025-12-20

### Added
- **Interactive Credential Saving**: Save credentials to `.env` file during interactive mode
  - After entering credentials in interactive fetch mode, users are prompted to save them to `.env` for future sessions
  - Supports saving source account credentials (DBT_SOURCE_*)
  - Supports saving connection provider_config credentials (DBT_CONNECTION_*)
  - Automatically sets restrictive file permissions (600) and warns about gitignore
  - Handles existing `.env` files with append/overwrite options
- **Connection Credential Prompting**: Interactive prompts for connection provider_config during normalization
  - After normalization, users can configure missing connection provider_configs interactively
  - Supports all connection types: Snowflake, Databricks, BigQuery, Redshift, PostgreSQL
  - Type-specific field prompts with validation
  - Option to save connection credentials to `.env` after configuration
- **E2E Test Script Enhancement**: Added option to save connection credentials to `.env` after provider_config setup
  - After adding provider_config (dummy or manual), users can save credentials for future use
  - Extracts provider_config from YAML and writes to `.env` in standardized format

### Changed
- **Interactive Mode**: Enhanced credential management workflow
  - Credentials entered interactively can now be persisted to disk
  - Better integration between fetch and normalize flows for credential management
  - Improved user experience with clear prompts and helpful warnings

### Technical Details
- New utility functions in `importer/interactive.py`:
  - `save_credentials_to_env()`: Main function for saving credentials with user prompts
  - `prompt_connection_credentials()`: Interactive prompts for connection provider_config
  - `_get_env_file_path()`, `_read_existing_env()`, `_write_env_file()`, `_format_env_value()`: Helper utilities
  - `_check_gitignore()`: Security check for gitignore status
- Connection credentials stored in `.env` with format: `DBT_CONNECTION_{CONN_KEY}_{FIELD}`
- File permissions automatically set to 600 (read/write owner only)
- Gitignore warnings with option to auto-add `.env` to `.gitignore`

## [0.4.4] - 2025-12-20

### Fixed
- **Type Consistency**: Filter deleted resources (state=2) at fetch time to prevent Terraform type errors
  - Added `_should_include_resource()` helper function to filter deleted service tokens and notifications
  - Deleted resources no longer enter the snapshot, eliminating type inconsistencies downstream
  - Fixes "all list elements must have the same type" errors caused by deleted resources with missing fields
- **Type Consistency**: Normalized permission object structures for consistent Terraform types
  - Service token permissions now always include `project_id` and `writable_environment_categories` fields (null/empty if not applicable)
  - Group permissions now always include `project_id` and `writable_environment_categories` fields (null/empty if not applicable)
  - Ensures all permission objects have identical structure regardless of permission scope
- **Type Consistency**: Normalized notification object structures for consistent Terraform types
  - Notifications now always include all optional fields (`on_success`, `on_failure`, `on_cancel`, `on_warning`, `external_email`, `slack_channel_id`, `slack_channel_name`) with empty lists or null defaults
  - Fixes "all list elements must have the same type" errors for notifications
  - Ensures all notification objects have identical structure regardless of notification type

### Changed
- **Fetch Behavior**: Deleted resources (state=2) are now filtered out during fetch phase
  - Service tokens with `state: 2` are skipped with debug log message
  - Notifications with `state: 2` are skipped with debug log message
  - JSON exports no longer include deleted resources (cleaner snapshots)
  - Element IDs/line items no longer include deleted resources

### Technical Details
- Filtering happens in `importer/fetcher.py` before resources enter the snapshot
- Prevents deleted resources from causing type mismatches in Terraform's strict type system
- Deleted resources often have incomplete fields (e.g., empty permission lists) which caused tuple type errors
- This is a breaking change for JSON exports (deleted resources excluded), but normalization remains backwards compatible

## [0.4.3] - 2025-12-19

### Changed
- **Performance**: Increased default HTTP timeout from 30s to 90s for better handling of slow API responses
  - Default timeout in `importer/config.py` increased from `30.0` to `90.0`
  - Environment variable default `DBT_SOURCE_API_TIMEOUT` updated from `"30"` to `"90"`
  - Users can still override via environment variable for custom timeout values
- **Performance**: Added gzip compression support for API requests
  - Added `Accept-Encoding: gzip, deflate` header to both v2 and v3 API clients
  - Expected 70-90% reduction in payload size for typical JSON responses
  - Reduces transfer time and likelihood of timeout errors
  - `httpx` automatically handles decompression

### Added
- Documentation: Created `dev_support/VERSION_UPDATE_CHECKLIST.md` - comprehensive guide for version management
  - Lists all files and locations that need updating when incrementing version
  - Provides semantic versioning guidelines and examples
  - Includes step-by-step workflow and verification commands
  - Referenced in CHANGELOG.md header for easy access

### Technical Details
- Timeout increase helps handle large accounts with hundreds of projects/environments/jobs
- Gzip compression significantly reduces network transfer time (typical 1-2MB vs 10MB uncompressed)
- Both changes work together to dramatically reduce timeout errors during fetch operations
- No breaking changes - fully backwards compatible

## [0.4.2] - 2025-12-19

### Added
- **Interactive Provider Config**: E2E test script now pauses after normalization to configure connection provider_config
  - Added `configure_provider_configs()` function with 4 interactive options (dummy config, manual editor, skip, abort)
  - Added `add_dummy_provider_configs()` function to generate type-specific placeholder configs (Databricks, Snowflake, BigQuery, Redshift, PostgreSQL)
  - Added `open_editor_and_wait()` function to pause and open YAML in user's preferred editor
  - Displays connection details (name, key, type) before prompting user
- Docs: Added comprehensive "Phase 3: Provider Configuration (Interactive)" section to E2E testing guide with examples for all database types

### Changed
- **Version:** Updated from 0.4.1 to 0.4.2
- Testing: E2E test fixture outputs now reference v2-prefixed module outputs (`v2_project_ids`, `v2_environment_ids`, etc.)
- Testing: Added default value to `test_vars.tf` variable to prevent required variable errors when E2E test loads root module

### Fixed
- **Critical Terraform Type Issues**: Fixed 3 type inconsistency errors preventing terraform plan from succeeding
  - **Issue 1 - Conditional Type Mismatch**: Removed conditionals from `locals` that created incompatible tuple types between branches
    - Changed from `local.schema_version == 2 ? try(...) : []` pattern to always processing uniformly with `try()` defaults
  - **Issue 2 - Service Tokens Type Inconsistency**: Normalized deleted service tokens (`state: 2`) missing `service_token_permissions` field
    - Identified via runtime evidence: ALL deleted tokens lack permissions, active tokens (`state: 1`) have them
    - Solution: Added `service_token_permissions: []` to tokens missing this field using `merge()` in for-comprehension
  - **Issue 3 - Groups Type Inconsistency**: Normalized special "Everyone" group missing `group_permissions` field
    - Added `group_permissions: []` to groups missing this field
- Root Module: Updated `main.tf` locals to rebuild `globals_v2` and `projects_v2` as proper lists, preventing Terraform tuple type errors
- Testing: E2E test now successfully completes terraform validate and plan phases

### Technical Details
- Root cause analysis revealed deleted/special resources from API lack optional fields that active resources have
- Terraform sees `{field: [...]}` vs `{no_field}` as incompatible object types in lists
- Solution normalizes all list items to have consistent field presence using `merge()` with default empty lists
- Changed conditional logic from `condition ? value : default` to `try(value, default)` to avoid type unification issues

## [0.4.1] - 2025-12-19

### Added
- **Phase 5 E2E Testing Infrastructure**: Complete end-to-end testing setup with automated test script
- Testing: Created `dev_support/phase5_e2e_testing_guide.md` - 677-line comprehensive testing guide with 6-phase workflow
- Testing: Created `test/e2e_test/` directory structure with `main.tf`, `env.example`, and `README.md`
- Testing: Created `test/run_e2e_test.sh` - Automated E2E test script with prerequisite checking, workspace cleaning, and summary generation
- Testing: Script includes Python/Terraform detection, virtual environment auto-activation, and color-coded console output
- Docs: Significantly expanded End-to-End Testing Readiness Checklist in implementation status document with step-by-step instructions, commands, and verification steps
- Docs: Created "Prerequisites for API Research" section documenting Semantic Layer, Model Notifications, License Maps, and Feature Flags research needs
- Docs: Added explicit blockers, dependencies, and related limitations to all roadmap items in implementation status document
- Docs: Linked Known Issues to relevant roadmap items (e.g., module variable recognition bug linked to short-term roadmap)
- Docs: Updated `test/README.md` with Quick Start section for automated E2E testing
- Docs: Added cross-references between implementation status, E2E testing guide, and known issues documents

### Changed
- **Version:** Updated from 0.4.0-dev to 0.4.1
- Docs: Aligned Semantic Layer timeline across documents from "Near-Term (0.4.0-dev)" to "Medium-Term (Next Quarter)" for consistency
- Docs: Restructured Next Steps & Roadmap in implementation status document with "Critical Path" vs "Parallel Work" sections
- Docs: Enhanced Phase 5 testing section with comprehensive troubleshooting (15+ common issues with solutions)
- Docs: Updated importer_implementation_status.md timestamp to 2025-12-19 with detailed change log
- Testing: Updated test script export directory path from `importer_export/` to `dev_support/samples/` to match actual importer output

### Fixed
- **Critical:** Fixed infinite recursive module loading in `test_module_call.tf` causing filesystem errors
  - Root module was loading itself recursively creating 50+ nested module levels
  - Module names exceeded filesystem path length limits (255+ characters)
  - Solution: Disabled `test_module_call.tf` by renaming to `.disabled`
- Testing: Fixed provider version conflict between e2e test (`~> 0.3`) and root (`~> 1.3`) causing init failures
  - Updated `test/e2e_test/main.tf` to use `dbtcloud ~> 1.3` matching other test fixtures
- Testing: Fixed Python command detection in test script to support `python3` (macOS default) in addition to `python`
- Testing: Added virtual environment auto-detection and activation in test script for missing dependencies
- Gitignore: Added e2e test output files (dbt-cloud-config.yml, test_log.md, test_summary.md, plan_output.txt, tfplan)

### Documentation
- Created comprehensive Phase 5 E2E testing guide covering:
  - Complete 6-phase workflow (Fetch → Normalize → Validate → Plan → Apply → Cleanup)
  - Detailed prerequisites and environment setup instructions
  - Step-by-step instructions with expected outputs for each phase
  - Test results & reporting templates
  - Comprehensive troubleshooting section with 5 categories covering 15+ common issues
  - Success criteria checklist with validation steps
- Enhanced implementation status document with:
  - Detailed step-by-step testing readiness checklist (expanded from 20 to 80+ items)
  - Explicit blockers and dependencies for each roadmap item
  - Prerequisites section for items requiring API endpoint research
  - Cross-references to related limitations and known issues

### Developer Experience
- Testing: Single command E2E test execution: `./test/run_e2e_test.sh`
- Testing: Automatic prerequisite validation (Python, Terraform, credentials, dependencies)
- Testing: Automatic workspace cleanup with backups of existing exports
- Testing: Automatic test summary generation in Markdown format
- Testing: Color-coded console output (info/success/warning/error) for better readability
- Testing: Built-in safety checks for destructive operations (10-second delay before apply)

### Notes
- Phase 5 testing infrastructure is complete and ready for execution
- End-to-end testing requires configuration of test account credentials in `test/e2e_test/.env`
- Automated test script supports both plan-only mode (default) and apply mode (`--apply` flag)
- All documentation improvements support Phase 5 execution and future migration guide creation

## [0.4.0-dev] - 2025-01-27

### Added
- **Phase 3 Complete**: Terraform v2 module (`modules/projects_v2/`) fully implemented for multi-project YAML consumption
- Terraform: Added automatic schema version detection in root `main.tf` (v1 vs v2 routing)
- Terraform: Created `modules/projects_v2/` with complete resource creation logic (globals, projects, environments, jobs, env vars)
- Terraform: Added LOOKUP placeholder resolution via `dbtcloud_global_connections` data source
- Terraform: Added key-based resource reference resolution (connections, repositories, environments)
- Terraform: Added v2-specific outputs (`v2_project_ids`, `v2_environment_ids`, `v2_job_ids`, etc.)
- Testing: Added v2 test fixtures (`test/fixtures/v2_basic/`, `test/fixtures/v2_complete/`)
- Testing: Added Terratest coverage for v2 schema (TestV2BasicConfiguration, TestV2CompleteConfiguration, TestV2YAMLParsing, TestV2Outputs)
- Docs: Created `dev_support/phase3_implementation_changelog.md` documenting Phase 3 implementation
- Docs: Created `dev_support/importer_implementation_status.md` master status tracking document
- Docs: Updated `dev_support/PROJECT_OVERVIEW.md` with v2 module implementation status (Section 19)

### Changed
- Terraform: Root module now conditionally routes to v1 or v2 modules based on YAML schema version
- Terraform: Outputs now support both v1 and v2 schemas with conditional returns
- Environment: Migrated Terraform installation from Homebrew to `tfenv` for access to latest versions (1.14.1)

### Notes
- Phase 3 completes the end-to-end workflow: fetch → normalize → apply
- v2 module supports multi-project configurations with global resources
- Backward compatible: v1 YAML files continue to work unchanged
- See `dev_support/phase3_implementation_changelog.md` for complete implementation details

## [0.3.4-dev] - 2025-11-21

### Added
- Importer: Service tokens now use Terraform-compatible `service_token_permissions` structure with `permission_set`, `all_projects`, `project_id`, and `writable_environment_categories` fields extracted from API metadata
- Importer: Groups now include `assign_by_default` and `sso_mapping_groups` fields in normalized output
- Importer: Groups now include `group_permissions` structure with proper project scoping when permissions are defined
- Importer: Notifications now include all Terraform-required fields: `user_id`, `on_warning`, `external_email`, `slack_channel_id`, `slack_channel_name`
- Importer: Added `on_warning`, `external_email`, `slack_channel_id`, `slack_channel_name` fields to `Notification` model
- Docs: Created `dev_support/terraform_readiness_audit.md` documenting Terraform schema compatibility analysis
- Docs: Created `dev_support/connection_provider_config_research.md` documenting API limitations for connection configuration
- Docs: Created `dev_support/terraform_readiness_implementation.md` with comprehensive implementation summary

### Changed
- Importer: Notification normalization now outputs numeric `notification_type` (1=internal, 2=Slack, 4=external email) instead of string types for Terraform compatibility
- Importer: Notification normalization no longer uses nested `type`/`target` structure, outputs flat Terraform-compatible fields instead
- Importer: Service token normalization now maps `project_id: null` to `all_projects: true` for proper Terraform structure
- Importer: Group normalization now extracts permissions from `metadata.group_permissions` instead of flat `permission_sets` array
- Importer: Updated `_fetch_notifications()` to populate new fields (`on_warning`, `external_email`, `slack_channel_id`, `slack_channel_name`) from API responses

### Fixed
- Importer: Service tokens now properly structured for Terraform `dbtcloud_service_token` resource (was using flat `scopes` array)
- Importer: Groups now properly structured for Terraform `dbtcloud_group` resource (was missing permissions and SSO mappings)
- Importer: Notifications now properly structured for Terraform `dbtcloud_notification` resource (was missing user_id and job associations)

## [0.3.3-dev] - 2025-11-21

### Changed
- Importer: Connection normalization now strips unnecessary source IDs and metadata from `details` object (previously included `id`, `account_id`, `created_at`, `updated_at`, `environment__count`, etc.)
- Importer: Only essential provider-specific configuration (adapter_version, ssh_tunnel, config) is preserved in connection details, making YAML cleaner and more portable

### Added
- Importer: New `include_connection_details` option in mapping configuration (default: `true`) to control whether provider-specific connection details are included in normalized YAML

## [0.3.2-dev] - 2025-11-21

### Fixed
- Importer: Fixed false collision detection by implementing namespace-scoped collision tracking. Resources in different namespaces (e.g., repository `test` and project `test`) no longer collide since they live in separate YAML sections (`globals.repositories[]` vs `projects[]`).

### Changed
- Importer: Collision tracking now operates per-namespace (connections, repositories, projects, service_tokens, groups, notifications, privatelink_endpoints, environments, jobs) instead of globally.

## [0.3.1-dev] - 2025-11-21

### Fixed
- Importer: Fixed PrivateLink endpoint state parsing to handle numeric values from API (now normalizes to string).

### Added
- **Phase 2 Normalization**: Added `python -m importer normalize` command to convert JSON exports into v2 YAML format
- Importer: Created `importer/normalizer/` module with core normalization logic, YAML writer, and mapping config support
- Importer: Added `schemas/importer_mapping.json` schema for normalization configuration with full validation
- Importer: Added `importer_mapping.yml` sample configuration file with documented options
- Importer: Normalization generates timestamped artifacts: YAML output, lookups manifest (JSON), exclusions report (Markdown), diff JSON, and logs
- Importer: Added normalization run tracking (`normalization_runs.json`) with sequential norm run IDs separate from fetch run IDs
- Importer: Added scope filtering (all projects, specific projects, account-level only) and per-resource-type filters
- Importer: Added normalization options: ID stripping, placeholder strategy (LOOKUP/error/omit), name collision handling, secret redaction, multi-project mode
- Importer: Normalization artifacts follow Phase 1 patterns: `account_{ID}_norm_{RUN}__{type}__{TIMESTAMP}.{ext}`
- Importer: Added comprehensive logging for normalization decisions (placeholders, collisions, exclusions, secret handling) at DEBUG level
- Schema: Finalized `schemas/v2.json` schema for multi-project/account-aware configurations with globals, key-based references, and LOOKUP placeholders
- Docs: Added `dev_support/phase2_normalization_target.md` documenting v2 YAML structure and resource mapping
- Docs: Added `dev_support/phase2_terraform_integration.md` documenting Terraform v2 module architecture and migration workflow
- Docs: Added `docs/importer_mapping_reference.md` comprehensive guide to mapping configuration options with examples
- Tests: Added `test/test_normalizer.py` with unit tests for normalization (scope filtering, resource exclusion, collision handling, secrets)
- Importer: `_metadata` now includes `run_label`, `source_url_hash`, `source_url_slug`, `account_source_hash`, and `unique_run_identifier` (12-char SHA-256) for every export
- Importer: Generated `account_{ID}_run_{RUN}__report_items__{TIMESTAMP}.json` containing per-element line items with `element_type_code`, `element_mapping_id`, `line_item_number`, and `include_in_conversion`

### Changed
- Importer: Renamed file outputs to `__json__` (was `__snapshot__`) and `__report__` (was `__details__`) and updated CLI/docs accordingly
- Importer: Added deterministic `element_mapping_id` to every resource and surfaced `include_in_conversion` for honoring inactive/soft-deleted states
- Importer: Updated `importer/README.md` with full Phase 2 workflow documentation (fetch → normalize → apply)
- Importer: Added PyYAML dependency to requirements.txt

## [0.3.0-dev] - 2025-11-20

### Added
- Importer: Added permission sets column to groups table showing all permission_set values for each group.
- Importer: Added notifications to global resources (Email, Slack, Webhook types with job trigger counts).
- Importer: Added permission grants to service tokens table showing permission_set values and project IDs.
- Importer: Added webhook subscriptions to global resources (v3 `/webhooks/subscriptions` endpoint), including Name, Client URL, Event Types, Job IDs, and Active state.
- Importer: Added PrivateLink endpoints to global resources (v3 `/private-link-endpoints/` endpoint), including Name, Type, State, and CIDR Range.
- Importer: Enhanced connections table with Adapter Version, OAuth configuration status, and PrivateLink Endpoint ID columns.

### Changed
- Importer: Enhanced service tokens display with permission sets and scoped project IDs columns.
- Importer: Improved notification type detection based on slack_channel_id, external_email, or url fields.
- Importer: Added destination column to notifications table showing email addresses or Slack channel names.
- Docs: Introduced `dev_support/versioning.md` outlining module/schema/importer versioning and changelog rules.
- Importer: Added `importer/VERSION` (now `0.2.0-dev`) to drive build-level logging and future release tagging.
- Importer: Created initial Python CLI (`python -m importer`) with API client, Pydantic data model, and fetch command for account snapshots (Phase 1). Uses `DBT_SOURCE_*` environment variables for source account credentials, includes retry/backoff/rate-limit handling.
- Importer: Added run tracking system with sequential run IDs per account stored in `importer_runs.json`. All files from the same run share a common timestamp and zero-padded run ID (e.g., `account_86165_run_001__snapshot__20251119_233918.json`).
- Importer: Added automatic generation of timestamped summary and detailed outline markdown reports for each fetch operation.
- Importer: Added service tokens to global resources (masked token values, active/inactive status).
- Importer: Added groups to global resources (name, assign by default, SSO mappings count).
- Importer: Formatted global resources (connections, repositories) and jobs as markdown tables in detailed outline for better readability.
- Importer: Added "Execute Steps" column to job tables showing dbt commands for each job.
- Importer: Added project separators (`---`) between projects in detailed outline.
- Importer: Added version metadata and run ID to all generated files (JSON snapshots and markdown reports).
- Importer: Added structured logging to timestamped log files with standard Python logging format.
- Importer: Improved job-to-environment mapping to correctly nest jobs under their parent environments in the detailed outline.
- Importer: Added job type detection (scheduled/triggered/manual) in the detailed outline based on trigger configuration.
- Importer: Formatted detailed outline with environments as h5 headers, job sections as bullet points, and 4-space indented job items.
- Importer: Improved project header layout with project ID, key, and repository on separate lines for better readability.
- Importer: Added three-letter ID prefixes for all resource types (CON ID, REP ID, PRJ ID, ENV ID, JOB ID) for clarity.
- Importer: Added dbt version display in environment lines of detailed outline (e.g., "Version: `latest`" or "Version: `1.6.0-latest`").
- Importer: Added environment variables display in both summary and detailed reports (shows count of environment-specific values).
- Importer: Added separate "Environment Variable Secrets" section in detailed report for variables prefixed with `DBT_ENV_SECRET`.
- Importer: Added secret variable counts to summary report at both account and project levels.
- Importer: Added environment-specific values display for non-secret variables in detailed report (shows environment name and value for each).
- Importer: Secret environment variables display masked values from API (e.g., `**********`) to indicate values are set without exposing secrets.
- Importer: Added "*No jobs configured*" message for environments without jobs in the detailed outline for clarity.
- Importer: Captured real account snapshot (17 projects, 3 connections, 15 repositories) in `dev_support/samples/account_snapshot.json` for Phase 2 normalization + testing.
- Schema: Created `schemas/v2.json` introducing multi-project/account-aware structure with `version`, `account`, `globals`, `projects[]`, and `metadata.placeholders`. Enables importer output and key-based cross-references.
- Schema: Added `test/schema_validation_test.py` (Python unittest suite) to validate v1/v2 schemas against fixture YAML files.
- Docs: Updated `docs/configuration/yaml-schema.md` with v2 overview showing account-aware root structure and global resource sections.

### Changed

- Importer: Renamed detailed outline report from `*__outline__*.md` to `*__details__*.md` for clarity.
- Importer: Reordered project sections in detailed report to show environment variables before environments.
- Importer: Changed environment variable value display from bullet lists to markdown tables for better readability.

### Fixed

- Importer: Fixed environment variables API parsing to correctly handle v3 endpoint response structure (removed "Unexpected payload structure" warnings).
- Importer: Added capture of project-level default values for environment variables (previously only environment-specific overrides were captured).
- Importer: Fixed job type detection to use `job_type` field from API instead of inferring from triggers (now correctly shows `ci`, `scheduled`, `merge`, `other` types).
- Importer: Added account name fetching from API (previously was always null).
- Importer: Fixed service tokens endpoint to use direct GET instead of pagination (v3 endpoint doesn't support pagination parameters).

### Removed

## [1.0.0] - 2024-01-XX

### Added

- Initial release of dbt Cloud Terraform Modules with YAML configuration support
- Root module wrapper for easy usage as a Terraform module
- Support for dbt Cloud projects, environments, jobs, and credentials
- Environment variables configuration (project-level and job-level)
- Credential management with secure token handling
- Repository configuration for Git integration
- Comprehensive documentation and examples
- Input validation for variables
- Support for multiple credential types

### Module Coverage

- `project` - Create and configure dbt Cloud projects
- `repository` - Configure Git repositories
- `project_repository` - Link repositories to projects
- `credentials` - Manage database credentials
- `environments` - Create development and deployment environments
- `jobs` - Configure dbt Cloud jobs with schedules and triggers
- `environment_variables` - Manage project and job environment variables
- `environment_variable_job_overrides` - Job-specific variable overrides

[Unreleased]: https://github.com/yourusername/dbt-terraform-modules-yaml/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/dbt-terraform-modules-yaml/releases/tag/v1.0.0
