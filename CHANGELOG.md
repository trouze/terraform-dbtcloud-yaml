# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Note:** When updating versions, refer to [Version Update Checklist](dev_support/VERSION_UPDATE_CHECKLIST.md) for all locations that need updates.

## [Unreleased]

## [0.16.0] - 2026-02-02

### Added
- **Independent Protection Architecture**: Implemented separate protection scopes for projects vs repositories
  - **Project Protection (PRJ:)**: Projects can be protected independently without affecting their associated repository or project-repository link
  - **Repository + PREP Protection (REPO:)**: Repository and project-repository link are always protected/unprotected together as a paired unit
  - Added `repository_protected` field to YAML schema for explicit repository protection control
  - Updated Terraform module (`projects.tf`) with independent repository protection logic
  - Protection Intent Manager now uses consolidated `REPO:` prefix instead of separate `REP:` and `PREP:` keys

### Changed
- **Terraform Module**: Updated `modules/projects_v2/projects.tf` to support independent repository protection
  - Added `effective_repository_protected`, `protected_repositories_map`, and `unprotected_repositories_map` locals
  - Repository resources now route to protected/unprotected blocks based on `repository_protected` field (with fallback to project protection)
  - Project-repository links follow repository protection status
- **Protection Intent File**: Consolidated key format from `REP:` + `PREP:` to single `REPO:` prefix

### Fixed
- **Terraform `Moved object still exists` Error**: Fixed conflict between `moved` blocks and new independent protection logic
  - Removed repository and project-repository `moved` blocks that conflicted with `repository_protected: false` setting

## [0.15.10] - 2026-02-02

### Fixed
- **View Output Plan Dialog**: Fixed issue where clicking "View Output" > "Plan Output" on the Match page would not open the plan viewer dialog
  - Replaced dynamic dialog creation with pre-created viewer dialog pattern for NiceGUI compatibility
  - Added stats bar to the pre-created viewer that dynamically shows plan statistics (to move, to add, to change, to destroy)
  - Stats bar only displays when viewing plan output, hidden for other output types

### Changed
- **Plan Viewer Stats**: Enhanced plan output viewer with move count display
  - Added blue "X to move" indicator in stats bar for moved blocks
  - Move stat only appears when there are resources to move (>0)

## [0.15.9] - 2026-01-30

### Added
- **Debug and Logging Standards PRD**: Created comprehensive `tasks/prd-web-ui-12-debug-logging-standards.md` documenting:
  - Permanent instrumentation policy - debug logging must NOT be removed
  - Structured logging patterns for UI actions, state changes, and errors
  - Function call tracing standards using `@traced` decorator
  - Log file locations and schema definitions

- **Debug Instrumentation Rule**: Created `.cursor/rules/debug-instrumentation.mdc` enforcing:
  - Preservation of all debug instrumentation
  - Structured logging via `ui_logger` utilities
  - Hypothesis markers (`[HA]`, `[HB]`, etc.) for debugging

- **Function Call Tracing**: Enhanced `importer/web/utils/ui_logger.py` with:
  - `@traced` decorator for automatic function entry/exit logging
  - `@traced_async` decorator for async functions
  - Argument and return value logging options
  - Error tracking with duration measurement
  - Safe serialization for non-JSON-serializable types

- **Protection Manager Tracing**: Added `@traced` decorator to key functions:
  - `generate_moved_blocks_from_state()`
  - `detect_protection_mismatches()`
  - `write_moved_blocks_file()`

## [0.15.8] - 2026-01-30

### Fixed
- **Adoption Override Data Flow**: Fixed critical bug where adoption overrides were not being applied during Generate
  - `confirmed_mappings` in match.py was not storing the `action` field, causing deploy.py's filter for `action == "adopt"` to always fail
  - Fixed `auto_match_all()` and `on_accept()` to include the `action` field in mappings
  - Fixed both functions to include rows with action "match" AND "adopt" (both represent mapping to existing target resources)
  - Updated deploy.py to accept `action` of "match", "adopt", or `None` for backward compatibility
- **Repository Adoption**: Repository `remote_url` and `git_clone_strategy` now correctly inherit target account values during adoption
  - Previously, adopted repositories would show plan changes to replace with source values
  - Now adoption overrides correctly update YAML with target values, resulting in no-change plans

## [0.15.7] - 2026-01-29

### Fixed
- **Protection Mismatch Fix**: Fixed catastrophic bug where adoption overrides defaulted `protected=True` for ALL adopted resources
  - Changed default in `apply_adoption_overrides` from `protected=True` to `protected=False`
  - This prevented Terraform from destroying and recreating all projects as "protected" when only one resource needed protection status change
  - Protection status is now opt-in rather than opt-out
- **State Persistence**: Fixed protection state persistence for `protected_resources`, `unprotected_keys`, and related backup fields
  - Sets are now properly converted to lists for JSON serialization in `MapState.to_dict()`
- **Unprotection Logic**: Added `apply_unprotection_from_set()` function to explicitly remove `protected: true` flags from resources

## [0.15.6] - 2026-01-30

### Fixed
- **Protection Mismatch Dialog**: Fixed dialog width and centering issues in the View Details dialog
  - Dialog now properly centers with `position=standard` Quasar prop
  - Set width to 950px (max 90vw) for better readability with AI Debug Summary expanded
  - Fixed layout issues where dialog was offset to the left

### Changed
- **Protection Mismatch Panel**: Improved layout of "Pending Fix" status tile
  - Moved fix status container to card level for proper proportions
  - Added `flex-grow` and `flex-shrink-0` for better button row layout

## [0.15.5] - 2026-01-29

### Fixed
- **Name Lookup Matching**: Fixed auto-matching failing for hierarchical resources (repositories, env vars) due to display prefixes
  - Added `_normalize_name_for_lookup()` helper to strip display prefixes ("  ↳ ", "    ↳ ") before lookups
  - Updated `build_grid_rows()` to use normalized names for `target_by_type_name` and `state_by_name` lookups
  - Updated `_compute_drift_status()` to normalize names consistently
  - Improved diagnostic output to show both original and normalized names when they differ

## [0.15.4] - 2026-01-29

### Fixed
- **Dialog Width Consistency**: Fixed confirmation dialogs being too wide (90vw) and AG Grid popups being too narrow
  - Removed global 90vw CSS rule that affected all dialogs
  - Small confirmation dialogs (e.g., "Existing Fetch Data Detected") now use appropriate content-based widths (`max-w-md`)
  - Large data dialogs (entity detail, YAML preview, resource detail) now have explicit `width: 90vw; max-width: 90vw` to override Tailwind constraints
  - Fixed dialogs: explore source/target entity popups, destroy resource detail, scope/mapping YAML preview, target credentials edit, jobs detail

## [0.15.3] - 2026-01-29

### Changed
- **AG Grid Standardization**: Migrated all grids to use `quartz` theme for automatic dark/light mode support
  - `match_grid.py`: Migrated from `balham` to `quartz`, removed manual dark mode CSS overrides
  - `job_grid.py`: Added `quartz` theme, migrated to AG Grid v32+ row selection API
  - Added `colId` to all column definitions to prevent phantom column bug
  - Added `animateRows: False` for stability across all grids
  
- **Export CSV Feature**: Added export functionality to all data grids
  - `mapping.py`: Added Export CSV button to toolbar
  - `scope.py`: Added Export CSV button to toolbar  
  - `job_grid.py`: Added `create_export_button()` helper function

### Added
- **AG Grid Standards Rule**: Created comprehensive `.cursor/rules/ag-grid-standards.mdc` with:
  - Critical MUST DO / MUST NOT rules
  - Column definition patterns (colId, boolean handling)
  - Layout patterns (CSS Grid for sizing)
  - Selection patterns (AG Grid v32+ API)
  - Dialog patterns with standard sizing
  - Dark mode CSS patterns
  - Troubleshooting guide

- **Grid Standardization PRD**: Created `tasks/prd-web-ui-11-grid-standardization.md` documenting:
  - Current state analysis of all grids
  - Migration plan and user stories
  - Test plan for dark/light mode

### Removed
- **Deprecated Patterns Doc**: Removed `dev_support/AGGRID_NICEGUI_PATTERNS.md` (superseded by `.cursor/rules/ag-grid-standards.mdc`)

## [0.15.2] - 2026-01-29

### Fixed
- **Match Diagnostics Improvements**: Comprehensive fixes for key comparison in Match Debug tab
  - Added project-prefixed key recognition (`{project_name}_{source_key}` patterns)
  - Added deduplication suffix support (`_2`, `_3` patterns from Terraform key collisions)
  - Added name-keyed resource handling (VAR, JEVO matched by name, not key)
  - Added no-state handling for resources without Terraform state tracking
  - Added normalized key support for Terraform (hyphens → underscores in for_each keys)
  - Fixed confidence tracking to preserve specific match types (state_id_match, env_match, etc.)
  - Key mismatches now correctly identified as cosmetic vs actual issues

## [0.15.1] - 2026-01-29

### Added
- **Match Debug Tab**: New debugging tab in resource detail popup for troubleshooting matching issues
  - Shows matching strategy, key comparison, and lookup diagnostics
  - Displays Terraform import address preview
  - LLM Diagnostic Report with "Copy for AI" button for easy diagnosis
  - Raw grid row JSON for detailed inspection

### Fixed
- **State-Aware Repository Matching**: Fixed matching for adopted repositories with different names
  - Project-linked repositories now use state ID to find target matches
  - Handles cases where source repo name differs from target repo name after adoption
  - Correctly shows "Match" action instead of "Create New" for adopted repos
- **Composite ID Parsing**: Fixed extraction of numeric IDs from composite Terraform IDs
  - Handles IDs like "605:556" by extracting the resource ID portion (556)
  - Normalizes `dbt_id` to integers for consistent lookups
- **Type Normalization**: Fixed type mismatches in state-to-target ID lookups
  - Ensures consistent integer types when comparing state IDs to target IDs

## [0.15.0] - 2026-01-29

### Added
- **Destroy Page Protection Enhancements**: Enhanced Destroy Target Resources tab with protection support
  - Auto-skips protected resources using `-target` flags (no more Terraform errors)
  - Shows "Skipping N protected resources" notification with list of preserved resources
  - Protected Resources panel displays resources grouped by type
  - "Unprotect All" button with confirmation dialog for explicit unprotection
  - Handles edge case where all resources are protected
  - Shows "(N protected resource(s) preserved)" in destroy summary

- **Terraform Module Protection Support**: Enhanced modules to support `lifecycle.prevent_destroy`
  - Split resources into `protected` and `unprotected` maps in all modules
  - `projects.tf`: `protected_projects` and `protected_repositories` with `prevent_destroy = true`
  - `environments.tf`: `protected_environments` with `prevent_destroy = true`
  - `jobs.tf`: `protected_jobs` with `prevent_destroy = true`
  - `environment_vars.tf`: Added `env_var_project_id_lookup` for protected project support
  - `globals.tf`: Updated `project_id` lookups to use `coalesce()` for protected projects
  - `outputs.tf`: Merged outputs include both protected and unprotected resources

- **YAML Schema Updates**: Added `protected` field to resource definitions
  - `schemas/v2.json`: Added `protected: boolean` to project, environment, job, repository

### Changed
- **Drift Detection Logic**: Improved accuracy of drift counting in Match Existing page
  - Only counts resources that actually need adoption (have target_id + not_in_state/id_mismatch)
  - Excludes "state_only" orphan resources from drift count
  - Shows which specific resources have drift for easier debugging

### Fixed
- Protected resources no longer cause Terraform destroy to fail
- Drift message no longer shows phantom "2 resources have drift" after applying moves

## [0.14.0] - 2026-01-28

### Added
- **Resource Protection with Cascade**: Comprehensive protection system for Terraform-managed resources
  - Protection checkbox column (🛡️) in Match Existing grid allows protecting any resource
  - Cascade protection: protecting a child resource auto-protects its parent chain
    - Job → Environment → Project
    - Credential → Environment → Project
    - Environment → Project
    - Env Variable → Project
    - Repository (project-linked) → Project
  - Confirmation dialog shows parent resources that will be protected
  - Unprotection cascade: dialog asks whether to unprotect children when unprotecting a parent
  - Protected rows highlighted with blue left border and subtle blue background
  - `protected_resources` set persisted in session state
  - `apply_protection_from_set()` function applies protection flags to YAML during generation

- **Protection Manager Utilities** (`importer/web/utils/protection_manager.py`):
  - `get_resources_to_protect()` - Returns resource and all unprotected ancestors
  - `get_resources_to_unprotect()` - Returns all protected descendants
  - `CascadeResource` dataclass for cascade dialog display

### Changed
- `MapState` now includes `protected_resources: set` for tracking protected source keys
- Match grid passes `protected_resources` to `build_grid_data()` and `create_match_grid()`
- Deploy page applies protection from set before Terraform generation

### Documentation
- Updated PRD (`tasks/prd-web-ui-09-resource-protection.md`) with:
  - Section 4.8: Cascade Protection user stories (US-RP-70 to US-RP-80)
  - Section 6.8: Cascade Protection test cases (CP-RP-01 to CP-RP-18)
  - Updated manual testing checklist for cascade protection
  - Complete cascade chain documentation

## [0.13.1] - 2026-01-28

### Fixed
- **Credential (CRD) Matching**: Fixed credentials showing as "create new" instead of matching existing target credentials
  - Credential names are dynamically generated (e.g., "Credential (snowflake, schema:ABC)") and often don't match exactly between source and target
  - Added environment-based matching: credentials now match by `(project_name, environment_name)` when exact name match fails
  - Since credentials are 1:1 with environments, this reliably matches credentials when their parent environment matches

## [0.13.0] - 2026-01-28

### Added
- **Terraform Plan Import Count**: Plan summary now correctly displays import counts alongside add/change/destroy
  - Updated `_parse_plan_summary()` in deploy.py to parse "X to import" from plan output
  - Plan viewer dialog shows purple "X to import" badge when imports are present
  - Apply confirmation dialog displays import count with purple styling
  - Import-related lines in plan output now highlighted in purple

- **Persistent Execution Logs**: "View Logs" button in Match Existing page now shows Generate Import process logs
  - Added `reconcile_execution_logs` field to `DeployState` for persistent log storage
  - Logs survive page reloads (previously lost on `ui.navigate.reload()`)
  - Logs include: Generate Import Blocks operations, Save Adoption Data, State Removal commands
  - Each log entry shows timestamp, operation name, success/failure status, detailed output, and working directory

### Changed
- Execution logs now stored in AppState rather than local function scope

## [0.12.6] - 2026-01-27

### Fixed
- **GitHub Installations API Error Handling**: Fixed Terraform plan failure when GitHub integration is disassociated
  - API returns error string `"Github installations failed to load, account disassociated"` instead of expected array
  - `jsondecode()` successfully parses this as a JSON string, causing type mismatch with empty list fallback
  - Solution: Wrapped decode in `try(tolist(jsondecode(...)), [])` to ensure consistent list type
  - Affected file: `modules/projects_v2/data_sources.tf`

## [0.12.5] - 2026-01-22

### Fixed
- **Connection Dependency Resolution**: Fixed "Select Parents" not auto-selecting connections referenced by environments
  - Root cause: Environment-to-connection lookup used string keys, which failed for fallback keys like `connection_1559`
  - Solution: Added `connection_id` field to Environment model and report items for ID-based lookups
  - Changed lookup logic to match by dbt Cloud connection ID first, with key-based fallback for backward compatibility
  - Prevents YAML output containing unresolved `LOOKUP:connection_*` placeholders

### Added
- `connection_id` field on Environment model in `models.py`
- Connection ID-based index (`_connection_by_id`) in HierarchyIndex
- `get_connection_by_id()` method in HierarchyIndex for ID-based lookups
- Unit tests for HierarchyIndex connection ID functionality

### Changed
- `fetcher.py`: Now stores `connection_id` when building Environment objects
- `element_ids.py`: Environment report items now include `connection_id`
- `scope.py` and `mapping.py`: "Select Parents" logic uses connection ID for reliable lookups

## [0.12.4] - 2026-01-22

### Added
- **Private Key Validation & Normalization**: Robust client-side and server-side handling for PEM private keys
  - New `pem_validator.py` module with `normalize_private_key()`, `validate_private_key()`, and `get_validation_status()` functions
  - Auto-reformats malformed keys on blur (fixes single-line pasted keys, normalizes whitespace, ensures 64-char line wrapping)
  - Real-time validation badges: green "Valid", yellow "Valid" (with warning for PKCS#1), red "Invalid" with error tooltip
  - Server-side normalization in `env_manager.py` before saving to `.env` file
  - Support for PKCS#8 (preferred) and PKCS#1 PEM formats with appropriate warnings
- **Enhanced Private Key Input**: Replaced single-line input with multi-line textarea
  - 6-row monospace textarea with placeholder showing expected PEM format
  - Help text explaining auto-formatting behavior

## [0.12.3] - 2026-01-22

### Fixed
- **Private Key HCL Escaping**: Fixed multi-line private keys in `secrets.auto.tfvars` causing Terraform parse errors
  - Newlines in PEM keys are now properly escaped as `\n` for HCL format
  - Added `escape_hcl_string()` helper function for consistent string escaping

### Changed
- **Valid Dummy Private Key**: Replaced invalid placeholder with a syntactically valid 2048-bit RSA key (PKCS#8 PEM)
  - Ensures Terraform validation passes even with dummy credentials
  - Key stored as `DUMMY_PRIVATE_KEY_PEM` constant in `credential_schemas.py`
- **Dummy Credential Indicator**: Changed from description prefix to name suffix
  - Environment names now suffixed with `[DUMMY CREDENTIALS]` instead of description prefix
  - More visible in dbt Cloud UI since environments don't prominently display descriptions

## [0.12.2] - 2026-01-22

### Fixed
- **Terraform Plan Visibility**: Removed `sensitive = true` from `environment_credentials` variable
  - Fields like `user`, `schema`, `num_threads` now visible in terraform plan output
  - Actual secrets (password, private_key, tokens) remain protected by state encryption
  - Fixed regeneration issue where template was overwriting user's manual fix

## [0.12.1] - 2026-01-22

### Changed
- **Workflow Card Layout**: Improved workflow tile consistency on home page
  - Updated Jobs as Code Generator description for two-line wrapping
  - All workflow cards now have naturally matching heights
  - Fixed description text: "Generate jobs-as-code YAML outputs from selected jobs and environments."

## [0.12.0] - 2026-01-21

### Added
- **Target Credentials Page Redesign**: Complete overhaul of the environment credentials editing experience
  - Edit dialog with columnar CSS Grid layout for consistent field alignment
  - "From source" (green) and "Override" (yellow) indicators showing which values match source account
  - Per-field reset buttons to restore individual fields to source values
  - "Use Dummy Credentials" toggle with visual comparison table (source vs dummy values)
  - "Overrides Source" indicator when dummy credentials override real source values
  - Authentication type selector with source/override indicators and reset functionality
  - "Reset to Dummy Credentials" button in environment actions
- **Credential Metadata Extraction**: Enhanced source value extraction from YAML
  - Extracts `auth_type`, `authentication`, and `auth_method` fields
  - Automatic `auth_type` inference for Snowflake (from `private_key`/`password` presence)
  - Comprehensive field extraction including `user`, `schema`, `database`, `warehouse`, `role`, `num_threads`
- **Progress Visibility Improvements**: Credential and environment variable counters in fetch progress
  - Renamed "Credentials" to "Credential Metadata (No Secret Values)" for clarity
  - Renamed "Env Variables" to "Env Variables (No Secret Values)" for clarity
  - Added credential count tiles on fetch complete pages

### Changed
- **Workflow Lockout Logic**: Adjusted step accessibility for better flexibility
  - "Fetch Target" step now accessible at any time (no longer requires source selection)
  - "Match Existing" step requires both source and target fetch completion
- **Fetch Page Layout**: Redesigned to vertical stack layout
  - Eliminated two-column structure that caused layout shift issues
  - Compact credential input forms with inline fields
  - Fixed scrollbar issues in progress sections
- **Credential Form Compaction**: Source/target credential forms now more compact
  - Single-row layout for Host URL, Account ID, and API Token
  - Dense styling with narrower Account ID field
  - Inline token type indicator chip
- **Edit Dialog Improvements**: Wider dialog (max-w-6xl) with better field organization
  - CSS Grid layout ensuring consistent column alignment
  - 140px label column, flexible input column, 100px indicator column, 40px reset column

### Fixed
- **Layout Stability**: Eliminated layout shift between "ready to fetch" and "fetch complete" states
- **State Preservation**: Fetch complete no longer clears logs and progress information
- **Authentication Indicator**: Fixed authentication type selector not showing source/override badges

## [0.11.1] - 2026-01-16

### Added
- **Native Integration Detection**: Automatically detects GitHub App, GitLab, and Azure DevOps native integrations from source repositories
  - Warning banner on Fetch Target page when source has native integration repos
  - Lists affected repositories and explains PAT requirement
  - Auto-switches target credentials to "User Token (PAT)" when native integrations detected
  - Runtime warnings if user attempts to fetch with service token when native integrations are present
- **GitHub Integration Debug Output**: Enhanced Terraform module output for debugging GitHub App integration discovery
  - Shows PAT status, HTTP response code, and installation count
  - Helps diagnose why `github_installation_id` might not be discovered

### Changed
- **Token Type Auto-Detection**: Token type is now automatically detected from the token prefix
  - `dbtc_*` tokens are identified as Service Tokens
  - `dbtu_*` tokens are identified as Personal Access Tokens (PAT)
  - Replaced manual token type dropdown with read-only indicator chip
  - Token type indicator updates dynamically when token value changes
  - Load .env now always auto-detects from prefix (ignores stale `DBT_*_TOKEN_TYPE` values)
  - Added `token_type` field to `SourceCredentials` (previously only on `TargetCredentials`)
  - Save to .env now stores auto-detected `DBT_SOURCE_TOKEN_TYPE` and `DBT_TARGET_TOKEN_TYPE`
- **Terraform Plan Logging**: Added terminal output showing token type and PAT configuration status during plan

### Fixed
- **git_clone_strategy Sensitivity**: Fixed `git_clone_strategy` showing as `(sensitive value)` in Terraform plan output
  - Wrapped strategy value in `nonsensitive()` since it's just a strategy name, not sensitive data
- **Report Items**: Added `git_clone_strategy` and `remote_url` to report items for proper native integration detection
- **Token Type Corruption**: Fixed bug where `token_type` could be corrupted to a dictionary instead of string

## [0.11.0] - 2026-01-16

### Added
- **State-Aware Orchestration (SAO) Support**: Full support for SAO fields across all job-related workflows
  - Added `force_node_selection` and `cost_optimization_features` fields to job normalization
  - Automatic CI/Merge job detection to omit `force_node_selection` (API requirement)
  - Updated Terraform module (`jobs.tf`) with SAO attribute handling
  - Updated v2 YAML schema with SAO field definitions
  - Added SAO documentation section in `importer/README.md` with migration guide

### Changed
- **Jobs as Code Generator**: Extended `_build_job_dict()` to include SAO fields with CI/Merge job handling
- **Normalizer**: Enhanced `_normalize_jobs()` to extract and properly handle SAO fields from API responses

## [0.10.1] - 2026-01-16

### Added
- **dbt-jobs-as-code Validation**: Optional integration with `dbt-jobs-as-code` for native schema validation
  - Runtime detection of `dbt-jobs-as-code` package availability
  - "Validate with dbt-jobs-as-code" button on Generate page (enabled when package installed)
  - Structured validation results with job count and detailed error messages
  - Fallback UI with install instructions when package not available
- **Auto-deduplication**: Automatic identifier deduplication for jobs with duplicate names
  - Appends numeric suffixes (`_2`, `_3`, etc.) to duplicate identifiers
  - Non-blocking warnings displayed in amber banner on Generate page
  - Expandable section showing which identifiers were auto-renamed

### Fixed
- **YAML Generator**: Fixed NiceGUI `ObservableDict`/`ObservableList` objects leaking into YAML output
  - Added `_to_plain_python()` recursive conversion before serialization
  - Ensures clean YAML that passes dbt-jobs-as-code validation

## [0.10.0] - 2026-01-16

### Added
- **Jobs as Code Generator Workflow**: New web UI workflow for generating `dbt-jobs-as-code` compatible YAML files
  - **Workflow Selection Page**: Choose between "Adopt Existing Jobs" (with `linked_id`) or "Clone / Migrate Jobs" (templated)
  - **Fetch Jobs Page**: Enter dbt Cloud credentials to fetch all jobs from source account
  - **Select Jobs Page**: Interactive job selection grid with search, filter, and bulk selection
  - **Configure Jobs Page**: Configure job naming (prefix/suffix), triggers, and output format
  - **Generate YAML Page**: Preview and export generated YAML with validation
- **State Management**: New `JobsAsCodeState` dataclass with full serialization/deserialization support
- **Utility Modules**: Job fetcher (`job_fetcher.py`), YAML generator (`yaml_generator.py`), and validator (`validator.py`)
- **UI Components**: Job selection grid (`job_grid.py`), mapping table (`mapping_table.py`), and YAML preview (`yaml_preview.py`)
- **Workflow Navigation**: 5-step workflow integrated into sidebar with step locking and progress tracking

### Changed
- **Web UI**: Added "Jobs as Code Generator" to workflow dropdown menu
- **State Module**: Extended `WorkflowStep` enum with JAC workflow steps (JAC_SELECT through JAC_GENERATE)
- **App Routes**: Added routes for all Jobs as Code Generator pages

### Fixed
- **Select Page**: Fixed workflow selection cards not updating visually when clicked (moved state read inside `@ui.refreshable` function)

## [0.9.1] - 2026-01-15

### Fixed
- **Test Suite**: Fixed `test_name_collision_handling` assertion that was checking the wrong level of nested `collisions` dictionary structure
- **Python 3.9 Compatibility**: Fixed `str | Path` union type syntax in `mapping_file.py` and `terraform_import.py` to use `Union[str, Path]` for Python 3.9 support

## [0.9.0] - 2026-01-15

### Added
- **Destroy Page**: Full destroy workflow with plan preview before destruction
- **Destroy Page**: Resource selection table with Type and Name columns (cleaner than full addresses)
- **Destroy Page**: Row click opens detailed resource popup with full state attributes
- **Destroy Page**: Sensitive value masking with show/hide toggle in resource detail popup
- **Destroy Page**: Cascade warning when dependent resources will also be destroyed
- **Destroy Page**: "View Plan" button in destroy confirmation dialog
- **Destroy Page**: Target info panel showing account ID and host URL
- **Destroy Page**: State file panel with "View State" button
- **Destroy Page**: Prerequisite checks for credentials and state file existence
- **Deploy Page**: Apply confirmation dialog with change summary (X to add, Y to change, Z to destroy)
- **Deploy Page**: "View Plan" button in apply confirmation dialog
- **State Viewer**: Resource count now shows all instances (not just resource blocks)
- **State Viewer**: Excludes data sources from resource count

### Changed
- **Destroy Page**: Buttons now match Deploy page styling (larger, more readable)
- **Destroy Page**: "Destroy Selected" button has red background with white text
- **Destroy Page**: "Destroy All" includes plan preview and type-to-confirm safety
- **Destroy Page**: Resource table defaults to showing all rows (no pagination)
- **Destroy Page**: Table selection now properly accumulates (incremental add/remove)
- **Destroy Page**: Table refresh now works correctly after destroy operations
- **Destroy Page**: Output log window height increased to 520px
- **Credentials**: Removed auto-loading of .env credentials; must explicitly load via Target page
- **Navigation**: Destroy step accessible when state file exists (not just after apply in current session)

### Fixed
- **Destroy Page**: Multi-select now works correctly (was only selecting last item)
- **Destroy Page**: Refresh button properly updates table with in-place list modification
- **State Viewer**: Resource count matches destroy page count (filters data sources)

## [0.8.1] - 2026-01-15

### Added
- **Deploy Page**: Dynamic Output panel title showing current step (GENERATE, INIT, VALIDATE, PLAN, APPLY, DESTROY)
- **Deploy Page**: Status colors for buttons - green (success), yellow (warnings), red (errors)
- **Terminal Output**: Auto-detection of warning/error messages from terraform output
- **Terminal Output**: New `set_title()` method for dynamic title updates
- **Terminal Output**: New `info_auto()` method for log level auto-detection

### Changed
- **Terminal Output**: Timestamps now in ISO8601 format with timezone offset (e.g., `2026-01-15T07:36:21-0800`)
- **Terminal Output**: Search bar width increased from 150px to 250px
- **Terminal Output**: Timestamp label width increased to accommodate longer format
- **Deploy Page**: Removed duplicate "Output" label (terminal has its own header)
- **Deploy Page**: "This will create/modify resources" message changed from WARN to INFO level

### Fixed
- **Deploy Page**: Buttons now properly reset visual state (outline, opacity) when regenerating files
- **Deploy Page**: Button styles properly cleared before applying new colors

## [0.8.0] - 2026-01-14

### Added
- **OAuth/SSO Support**: Full OAuth credential configuration for Snowflake, Databricks, and BigQuery connections
- **Connection Credentials Variable**: New `connection_credentials` Terraform variable for passing OAuth secrets securely
- **Secrets Auto-Generation**: `secrets.auto.tfvars` file generated with OAuth credentials (auto-loaded by Terraform)
- **OAuth Warning Cards**: Warning cards in Target page explaining OAuth integrations cannot be reused from source
- **Documentation Links**: Links to dbt platform OAuth setup guides for each provider (Snowflake SSO, Snowflake External OAuth, Databricks, BigQuery)
- **Terraform Module**: Added OAuth fields to `globals.tf` for all connection types (Snowflake, Databricks, BigQuery, Postgres, Redshift)

### Changed
- **Target Page**: OAuth fields now grouped under "OAuth / SSO Configuration" section
- **Target Page**: Source reference card now displays host URL
- **Connection Config**: Databricks `client_id`/`client_secret` moved to OAuth section
- **Deploy Page**: Apply checkmark now shows after successful deployment
- **Deploy Page**: All checkmarks reset when regenerating Terraform files

### Fixed
- **Credential Loading**: Fixed regex pattern in `load_connection_configs()` to correctly parse multi-part field names
- **Secrets Passing**: OAuth credentials now properly passed to Terraform via `secrets.auto.tfvars`

## [0.7.9] - 2026-01-14

### Added
- **Deploy Page**: View Output buttons for Generate, Init, and Validate steps
- **Deploy Page**: View Apply logs button after apply completes
- **Deploy Page**: Terraform validate step between Init and Plan
- **Deploy Page**: Auto-open View Plan dialog after successful plan
- **Normalizer**: Self-deferral detection from `deferring_job_definition_id`

### Changed
- **Deploy Page**: Redesigned layout with horizontal tiles (Generate/Init/Validate) and side-by-side Plan/Apply with terminal
- **Deploy Page**: Compact deployment summary with resource tiles on right
- **Map Page**: Renamed "Scope Settings" to "Bulk Project Selector" and "Apply Scope Selection" to "Bulk Select Resources"

### Fixed
- **Job Deferral**: `self_deferring` now correctly omitted when `deferring_environment_id` is set (they conflict)
- **Job Deferral**: `deferring_job_id` removed from Terraform resource (conflicts with environment deferral)
- **Job Deferral**: `run_compare_changes` disabled when job defers to same environment (API requirement)
- **Deploy Page**: Green checkmarks now appear after Generate, Init, Validate, and Plan complete
- **Deploy Page**: Apply button correctly enables after successful plan
- **Map Page**: Fixed "Missing Dependencies" warnings for connections (removed incorrect parent link)
- **Map Page**: Grid auto-refreshes after "Bulk Select Resources" when filter is active

## [0.7.8] - 2026-01-14

### Added
- **YAML Preview Search**: Real-time search with highlighting, match count, and next/previous navigation
- **Phase 2 Map Complete**: All Map step user stories implemented (US-028 through US-036)

### Changed
- **YAML Preview**: Search shows "X of Y" format with orange highlight on current match

## [0.7.7] - 2026-01-14

### Added
- **Map Page**: Entity detail popup - click any row to view entity details (same as Explore tab)
- **Fetch Page**: Total fetch time displayed in final summary ("Total time: X.Xs")
- **Fetch Page**: Threads value log message confirms configured thread count

### Changed
- **Entity Detail Dialog**: Resized to match View YAML popup (height: 80vh, width: max-w-4xl)
- **Fetch Page**: Threads input now properly saves/loads via `e.args` event handling

### Fixed
- **Fetch Page**: Threads setting now correctly persists and applies to fetch operations

## [0.7.6] - 2026-01-13

### Added
- **Fetch Page**: Cancel button to stop fetch operations in progress
- **Fetch Page**: Configurable threads input (1-20) for parallel API requests
- **Explore Tab**: Display codes added to RESOURCE_TYPES (ACCNT, CONN, REPO, SRVTKN, etc.)

### Changed
- **Explore Tab**: Type dropdown now shows format "Name (CODE) [count]"
- **Explore Tab**: Entity detail dialog badge shows "Name (CODE)"
- **Explore Tab**: Summary tab Type chip shows "Name (CODE)"
- **Fetcher**: `fetch_account_snapshot` accepts optional `cancel_event` parameter

## [0.7.5] - 2026-01-13

### Added
- **Map Page**: "Reset Filters" button to reset to "All Types" with "Selected Only" off
- **Map Page**: Scope Settings now functional - filter by All Projects, Specific Projects, or Account Only
- **Map Page**: Resource Filters now functional - toggle entity types on/off for target config generation
- **Map Page**: Selection Summary shows "Effective (after filters)" count with per-type breakdown
- **Repositories**: Now linked to their parent projects via `metadata.project_id`
- **Explore Tab**: Repository entities now show Project name and ID columns

### Fixed
- **Map Page**: Auto-cascade timing bug - state now updates immediately when toggle clicked
- **Map Page**: Parent-child selection excludes Account entity from cascade operations
- **Map Page**: Scope and Resource filters now properly exclude items from generated YAML
- **Normalizer**: Added `exclude_ids` filtering to `_normalize_environment_variables`, `_normalize_environments`, `_normalize_jobs`
- **Normalizer**: Fixed resource filter key mismatch (`privatelinks` → `privatelink_endpoints`, `env_vars` → `environment_variables`)
- **Pydantic Models**: Added `extra='allow'` to preserve `element_mapping_id` fields during JSON deserialization

### Changed
- **Hierarchy Index**: Repositories treated as project children (like ENV, VAR, JOB)
- **Element IDs**: Projects registered first to enable repository-project linking

## [0.7.4] - 2026-01-13

### Added
- **Map Page**: Filter state persistence across theme toggles and page reloads
  - Type filter selection now persists in session state
  - "Selected Only" filter toggle persists in session state
  - Filters survive normalization operation (which triggers page reload)

### Fixed
- **Map Page**: "Selected Only" button now correctly shows highlighted state on page load when active
- **Map Page**: Grid applies persisted filters on initial render

## [0.7.3] - 2026-01-13

### Added
- **Explore Entities Tab**: "Default" button in column selector resets to optimized columns per entity type
- **Explore Entities Tab**: Explicit `colId` on all columns prevents AG Grid auto-numbering issues

### Changed
- **Explore Entities Tab**: Column header changed from "#" to "Line #" for clarity

### Fixed
- **Explore Entities Tab**: Column visibility selector now properly updates grid using AG Grid's `setGridOption` API
- **Explore Entities Tab**: Fixed duplicate column names ("Sort Key 2", "Name 3") caused by AG Grid sorting properties
- **Explore Entities Tab**: Removed `initialState.sortModel` and column-level `sort`/`sortIndex` properties that created phantom columns

## [0.7.2] - 2026-01-13

### Changed
- **Web UI Rebrand**: Renamed from "Account Migration Tool" to "dbt Magellan: Exploration & Migration Tool"
- **Home Page**: Updated messaging to emphasize both exploration/auditing and migration use cases
- **Explore Entities Tab**: Entity types now have sort-order prefixes (00-ACC, 10-CON, 30-PRJ, etc.) for logical grouping
- **Explore Entities Tab**: Default sort order is now Project → Type → Name (all ascending)

### Added
- **Explore Entities Tab**: Column visibility selector with preferences persisted across sessions
- **Explore Entities Tab**: Enhanced entity detail dialog with "Details" outline view and "JSON (Full)" tab showing all API fields
- **Fetch Page**: File upload dialog for loading .env files with macOS hidden file tip (⌘+Shift+.)

### Fixed
- **Explore Page Layout**: Fixed CSS grid layout issue where Summary, Report, Entities, and Charts tabs didn't fill available width
- **Explore Entities Table**: Fixed AGGrid not filling available vertical space in panel
- **Fetch Page**: "Fetch Complete" panel now clears when starting a new fetch or loading a new .env file

## [0.7.1] - 2026-01-13

### Added
- **Fetch parallelism**: Parallelized Phase 1 fetch across globals + projects + job env-var overrides with configurable worker count.
  - New CLI flag: `python -m importer fetch --threads N`
  - New env var: `DBT_SOURCE_FETCH_THREADS` (default 5)

### Changed
- **Fetch UX**: Progress UI shows thread count and makes it clearer why projects complete more slowly (job env-var overrides dominate runtime on some accounts).

### Fixed
- **Terraform v2**: Hardened job scheduling config to avoid invalid schedule field combinations during plan/apply.
- **E2E runner**: Avoid false-positive “Errors detected” output by matching real Terraform `Error:` lines only.

## [0.7.0] - 2026-01-13

### Added
- **Web UI: Account Migration Tool**: New NiceGUI-based web interface for the importer workflow
  - Interactive 5-step workflow: Fetch → Explore → Map → Target → Deploy
  - Dark/light theme toggle with dbt brand colors
  - Session state persistence across page refreshes
  - Recent runs dashboard showing previous fetch/normalize operations
  - Sidebar navigation with step locking based on progress
  - Launch via `python -m importer.web` with `--port`, `--no-open`, `--reload` flags

### Changed
- Renamed "Importer" to "Account Migration Tool" in web UI branding

## [0.6.11] - 2026-01-09

### Fixed
- **Jobs: schedule normalization**: Fixed scheduled job configuration not being applied in the target account.
  - Normalizer now reads schedule fields from the nested Jobs API shape (`settings.schedule.date` / `settings.schedule.time`) instead of expecting flat `schedule_*` fields.
  - Avoids invalid Terraform/provider combinations by only emitting `schedule_cron` for `custom_cron`, selecting `schedule_hours` vs `schedule_interval` based on `schedule.time.type`, and omitting schedule fields entirely unless `triggers.schedule` is true.

## [0.6.10] - 2026-01-08

### Fixed
- **Jobs: compare_changes_flags unknown after apply**: Fixed Terraform apply failures where the provider left `compare_changes_flags` unknown post-create, producing `Provider returned invalid result object after apply`.
  - Provider now ensures `compare_changes_flags` is always known after job creation (set from API when present, otherwise `null`).
  - This unblocks E2E applies when creating jobs, even when state-aware orchestration is disabled.

## [0.6.9] - 2026-01-08

### Fixed
- **Environment Variable Environment-Specific Values**: Fixed environment-specific values not being set for environment variables
  - Added explicit dependency on `dbtcloud_environment.environments` to ensure environments are created before setting environment-specific values
  - Environment variables with `project` defaults were working, but values for specific environments (e.g., "1 - Prod", "2 - Staging") were not being set
  - The dbt Cloud API requires environments to exist before environment-specific values can be assigned

### Technical Details
- Terraform module changes in `modules/projects_v2/environment_vars.tf`:
  - Added `depends_on = [dbtcloud_environment.environments]` to `dbtcloud_environment_variable.environment_variables` resource
  - Ensures proper resource creation order: environments → environment variables → environment-specific values

## [0.6.8] - 2026-01-08

### Fixed
- **GitHub App Repository OAuth**: Fixed "Token refresh failure" for GitHub App repositories created via Terraform
  - Provider now always sends `remote_backend` field based on integration type (github, gitlab, azure_active_directory, manual_config)
  - Fixed double `/api/api/` URL bug in GitHub installations discovery endpoint
  - Fixed empty PAT export bug that caused GitHub installations API call to fail
  - Terraform module now always uses discovered target account's `github_installation_id` instead of invalid source account IDs

### Technical Details
- Provider changes in `terraform-provider-dbtcloud/pkg/dbt_cloud/repository.go`:
  - Always send `remote_backend` field derived from integration type
  - Added `omitempty` to `GitCloneStrategy` field
- Terraform module changes in `modules/projects_v2/projects.tf`:
  - Always use target account's discovered `github_installation_id` for `github_app` strategy repos
  - Ignore source account installation IDs which are invalid in target account
- Terraform module changes in `modules/projects_v2/data_sources.tf`:
  - Strip `/api` suffix from host URL to prevent double `/api/api/` in API calls
- E2E test script changes in `test/run_e2e_test.sh`:
  - Use PAT for both GitHub App and GitLab repos (both require PAT for OAuth binding)
  - Only export `TF_VAR_dbt_pat` if PAT is actually set (not empty string)
  - Fixed `DBT_CLOUD_TOKEN` to use effective token (PAT) instead of original service token

## [0.6.7] - 2026-01-08

### Fixed
- **Repository Replacement Prevention**: Fixed unnecessary repository replacements when `github_installation_id` is provided
  - Provider now uses API's returned `git_clone_strategy` value (`github_app`) when `github_installation_id` is set
  - Terraform module automatically sets `git_clone_strategy = "github_app"` when `github_installation_id` is provided
  - Prevents Terraform from detecting configuration drift and replacing repositories unnecessarily
  - API automatically changes `git_clone_strategy` from `deploy_key` to `github_app` when GitHub installation ID is provided

### Technical Details
- Provider changes in `terraform-provider-dbtcloud/pkg/framework/objects/repository/resource.go`:
  - Create function now uses API's returned `git_clone_strategy` when `github_installation_id` is provided
  - Ensures state matches API behavior to avoid replacement triggers
- Terraform module changes in `modules/projects_v2/projects.tf`:
  - `effective_git_clone_strategy` now automatically sets `github_app` when `github_installation_id` is provided
  - Matches API's automatic behavior to prevent configuration drift

## [0.6.6] - 2026-01-08

### Fixed
- **Environment deployment_type**: Added support for `deployment_type` field (production/staging)
  - Fetcher now extracts `deployment_type` from environment metadata
  - Normalizer includes `deployment_type` in normalized environment output
  - Terraform module sets `deployment_type` attribute on `dbtcloud_environment` resources
- **Environment Connection Linking**: Fixed environments not being linked to global connections
  - Added connection key registry similar to repository key registry
  - Environments now resolve connection keys correctly instead of showing `LOOKUP:` placeholders
  - Connection key resolution uses original key -> normalized key mapping

### Technical Details
- Model changes in `importer/models.py`:
  - Added `deployment_type: Optional[str] = None` to `Environment` class
- Fetcher changes in `importer/fetcher.py`:
  - Extract `deployment_type` from environment item metadata
- Normalizer changes in `importer/normalizer/__init__.py` and `importer/normalizer/core.py`:
  - Added `connection_key_to_normalized` dict and `register_connection_key()`/`resolve_connection_key()` methods
  - Connection normalization registers original -> normalized key mapping
  - Environment normalization uses connection key resolution first, then falls back to element_mapping_id resolution
  - Include `deployment_type` in normalized environment output
- Terraform changes in `modules/projects_v2/environments.tf`:
  - Added `deployment_type` attribute to `dbtcloud_environment` resource

## [0.6.5] - 2026-01-08

### Fixed
- **GitLab Repository Creation**: Fixed `gitlab_project_id` not being fetched during import
  - Added undocumented `include_related=["deploy_key","gitlab"]` query parameter to v3 Retrieve Repository API
  - Fetcher now correctly extracts `gitlab_project_id` from GitLab integration data
  - Enables proper GitLab repository creation with `deploy_token` strategy
- **GitLab PAT Requirement**: Added automatic PAT detection for GitLab repositories
  - E2E test script now automatically uses PAT as main token when GitLab repos detected
  - Added warning when GitLab repos exist but no PAT provided
  - GitLab repositories require user token (PAT), not service token

### Technical Details
- Fetcher changes in `importer/fetcher.py`:
  - Added `include_related` parameter to v3 Repository API call
  - Extracts `gitlab_project_id` from nested `gitlab` object
- E2E test script changes in `test/run_e2e_test.sh`:
  - Detects `deploy_token` strategy repos in YAML
  - Automatically switches to PAT as `TF_VAR_dbt_token` for GitLab support

## [0.6.4] - 2025-12-20

### Fixed
- **Skip All Notifications During Migration**: The dbt Cloud provider requires `user_id` for all notification types
  - Provider documentation: "we still need the ID of a user in dbt Cloud even though it is not used for sending notifications"
  - Since source user IDs cannot be mapped to target user IDs, all notifications are now skipped
  - Notifications are still fetched and normalized (preserved in YAML for future migration mode)
  - Future `--migrate-notifications` mode will handle user ID and job ID mapping

### Technical Details
- Terraform changes in `modules/projects_v2/globals.tf`:
  - Changed `for_each` filter to `if false` to skip all notifications
  - Added placeholder required fields (`user_id`, `notification_type`, `state`) for schema validation
  - Provider validates required fields even when `for_each` is empty

## [0.6.3] - 2025-12-20

### Fixed
- **Notification Migration Filtering**: Added filtering to skip user-level and Slack notifications during initial migration
  - User notifications (type 1): Skipped - source user IDs don't exist in target account
  - Slack notifications (type 2): Skipped - requires Slack integration in target account
  - Job-linked notifications: Skipped - job IDs from source account don't exist in target
  - External email notifications (type 4): Skipped - `user_id` is still required by provider
  - All notifications are still fetched and normalized (preserved in YAML for future migration mode)

### Changed
- **Notification Resource Filtering**: Updated Terraform module to filter notifications at apply time
  - Added comprehensive filtering logic in `modules/projects_v2/globals.tf`
  - Added inline documentation explaining filtering strategy
  - Future: `--migrate-notifications` mode will handle job ID mapping and Slack integration

### Technical Details
- Terraform changes in `modules/projects_v2/globals.tf`:
  - Added `for_each` filter to skip incompatible notifications
  - Filter out notifications with job references (jobs not yet mapped)
- Documentation updates:
  - Added notification migration limitations to `dev_support/KNOWN_ISSUES.md`
  - Added roadmap item for future notification migration mode
  - Updated `dev_support/importer_implementation_status.md` with notification migration details

## [0.6.2] - 2025-12-20

### Fixed
- **Service Token Permission Grants**: Fixed provider to use `permission_grants.permission_set` during service token creation
  - API expects `permission_grants` array in creation request, not `service_token_permissions`
  - Updated `CreateServiceToken()` to use correct request structure
  - Added `ServiceTokenPermissionGrant` struct with proper JSON tags
  - Fixed `writable_environment_categories` serialization to include empty arrays (not omit them)

- **Cross-Account Project ID Resolution**: Fixed service token and group permissions to use `project_key` instead of source `project_id`
  - Source account project IDs don't exist in target account, causing 404 errors
  - Added `project_id_to_key` mapping in normalizer to convert source IDs to project keys
  - Added `_build_project_id_mapping()` pre-pass before normalizing permissions
  - Updated Terraform module to resolve `project_key` → target `project_id` at apply time
  - Affects: `service_token_permissions` and `group_permissions` with project-specific access

### Technical Details
- Provider changes in `pkg/dbt_cloud/service_token.go`:
  - Added `ServiceTokenPermissionGrant` and `CreateServiceTokenRequest` structs
  - Changed `WritableEnvironmentCategories` to pointer type for proper empty array serialization
- Provider changes in `pkg/framework/objects/service_token/model.go`:
  - Added `ConvertServiceTokenPermissionModelToGrant()` function
- Normalizer changes in `importer/normalizer/__init__.py`:
  - Added `project_id_to_key` mapping and helper methods
- Normalizer changes in `importer/normalizer/core.py`:
  - Added `_build_project_id_mapping()` pre-pass
  - Updated `_normalize_service_tokens()` and `_normalize_groups()` to use `project_key`
- Terraform changes in `modules/projects_v2/globals.tf`:
  - Updated permission blocks to resolve `project_key` to target `project_id`

## [0.6.1] - 2025-12-20

### Fixed
- **Provider Version Pinning**: Pinned Terraform provider to exact version `= 1.5.1` to prevent version drift
  - Updated `providers.tf` and `test/e2e_test/main.tf` to use exact version constraint
  - Prevents unexpected updates that may introduce breaking changes or bugs
- **Empty Environment Variables**: Added filtering to skip environment variables with no values
  - API rejects environment variables with empty `environment_values`
  - Prevents 11 API errors during Terraform apply
  - Updated `modules/projects_v2/environment_vars.tf` to filter out empty env vars
- **Deprecated dbt Versions**: Added filtering to skip environments with deprecated dbt versions
  - Prevents errors for environments using `latest-fusion` (no longer supported)
  - Prevents 7 API errors and cascading failures
  - Updated `modules/projects_v2/environments.tf` to filter deprecated versions
- **Dependency Cascades**: Added explicit `depends_on` blocks for service tokens and groups
  - Ensures projects exist before creating tokens/groups with project-specific permissions
  - Updated `modules/projects_v2/globals.tf` with dependency declarations

### Technical Details
- Provider version pinned in `providers.tf` and `test/e2e_test/main.tf`
- Environment variable filtering in `modules/projects_v2/environment_vars.tf` line 26
- Deprecated version filtering in `modules/projects_v2/environments.tf` line 83
- Dependency blocks added to service tokens and groups resources

## [0.6.0] - 2025-12-20

### Added
- **Test Mode Destroy Flag**: Added `--test-destroy` flag to E2E test script for cleaning up test resources
  - Targets 1-2 resources (connections preferred, groups fallback) using same logic as `--test-plan` and `--test-apply`
  - Supports standalone destroy mode (skips fetch/normalize when only destroy is requested)
  - Includes 10-second warning before destroy execution
  - Usage: `./run_e2e_test.sh --test-destroy` or `./run_e2e_test.sh --test-apply --test-destroy`

### Changed
- **Test Mode Uses Real Connection Data**: Updated Terraform module to read connection configuration from `provider_config` first (where `.env` values are stored), then fall back to `details` (API data), then defaults
  - Test mode now uses real connection credentials from `.env` files instead of dummy test data
  - Updated connection types: Databricks, Snowflake, BigQuery, Postgres, Redshift
  - Ensures test resources are created with actual configuration values for accurate testing

### Fixed
- **Test Mode Targeting**: Fixed test mode resource targeting by adding `[0]` index to `projects_v2` module path
  - Root cause: `projects_v2` module uses `count = 1`, requiring `module.projects_v2[0]` instead of `module.projects_v2`
  - Test mode now correctly targets and plans/applies 1-2 resources as intended
  - Fix enables successful Terraform plan/apply execution in test mode

### Technical Details
- Updated `modules/projects_v2/globals.tf` to prioritize `provider_config` over `details` for connection configuration
- Updated `test/run_e2e_test.sh` to include `[0]` index in target resource paths
- Added `phase6_destroy()` function with same targeting logic as test-plan/test-apply

## [0.5.4] - 2025-12-20

### Fixed
- **Terraform for_each with Sensitive Values**: Fixed "Invalid for_each argument" error in `modules/projects_v2/environments.tf`
  - Root cause: Terraform considers `keys()` of a sensitive map as sensitive, preventing its use in `for_each` filters
  - Solution: Wrapped `keys(var.token_map)` with `nonsensitive()` function to mark keys as non-sensitive
  - Keys (token names) are not sensitive; only the token values are sensitive
  - This allows filtering credentials by token availability without exposing sensitive values
  - Fix enables successful Terraform plan execution (97 resources planned to add)

### Technical Details
- Updated `modules/projects_v2/environments.tf` line 24 to use `nonsensitive(keys(var.token_map))`
- The `nonsensitive()` function (Terraform 0.14+) is designed for this exact use case
- Terraform plan now completes successfully without for_each errors

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
