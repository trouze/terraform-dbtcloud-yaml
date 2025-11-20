# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
