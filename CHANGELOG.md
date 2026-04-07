# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

- Documentation now matches the **YAML schema version 1** layout: `version: 1`, `account`, `globals` (connections, service tokens, groups, notifications, PrivateLink), environment field **`connection`** (not `connection_key`), `project_artefacts` / `semantic_layer_config`, and job **`environment_variable_overrides`**. Examples and troubleshooting were updated accordingly.

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

[Unreleased]: https://github.com/dbt-labs/terraform-dbtcloud-as-yaml/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/dbt-labs/terraform-dbtcloud-as-yaml/releases/tag/v1.0.0
