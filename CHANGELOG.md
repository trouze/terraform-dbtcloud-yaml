# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Docs: Introduced `dev_support/versioning.md` outlining module/schema/importer versioning and changelog rules.
- Importer: Added `importer/VERSION` (default `0.1.0-dev`) to drive build-level logging and future release tagging.
- Importer: Created initial Python CLI (`python -m importer`) with API client, Pydantic data model, and fetch command for account snapshots (Phase 1). Uses `DBT_SOURCE_*` environment variables for source account credentials, includes retry/backoff/rate-limit handling.
- Importer: Captured real account snapshot (17 projects, 3 connections, 15 repositories) in `dev_support/samples/account_snapshot.json` for Phase 2 normalization + testing.
- Schema: Created `schemas/v2.json` introducing multi-project/account-aware structure with `version`, `account`, `globals`, `projects[]`, and `metadata.placeholders`. Enables importer output and key-based cross-references.
- Schema: Added `test/schema_validation_test.py` (Python unittest suite) to validate v1/v2 schemas against fixture YAML files.
- Docs: Updated `docs/configuration/yaml-schema.md` with v2 overview showing account-aware root structure and global resource sections.

### Changed

### Fixed

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
