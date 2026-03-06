# Release Notes — v0.27.0

**Date:** 2026-03-05  
**Type:** Minor release  
**Previous:** v0.26.0

---

## Summary

Full-stack implementation of 8 new resource types (S4 account-level, S5 project-level, S6 semantic layer) across the entire migration pipeline: Pydantic models, API fetching, YAML normalization, Terraform modules, element ID registration, reporting, and UI integration. Also fixes a scope page bug where connections were not all selected in "All Projects" mode.

---

## Changes

### Added

- **Account-level resources (S4)**:
  - `dbtcloud_account_features` (ACFT) — account feature flags
  - `dbtcloud_ip_restrictions_rule` (IPRST) — IP restriction rules
  - `dbtcloud_oauth_configuration` (OAUTH) — OAuth configurations with `client_secret` redaction
  - `dbtcloud_user_groups` (USRGRP) — user group definitions with `group_permissions`

- **Project-level resources (S5)**:
  - `dbtcloud_project_artefacts` (PARFT) — `docs_job_id` and `freshness_job_id` per project
  - `dbtcloud_lineage_integration` (LNGI) — lineage integrations with `token` redaction

- **Semantic layer resources (S6)**:
  - `dbtcloud_semantic_layer_configuration` (SLCFG) — semantic layer configs per environment
  - `dbtcloud_semantic_layer_credential_service_token_mapping` (SLSTM) — credential-to-token mappings

- **Terraform modules**: 7 new `.tf` files in `modules/projects_v2/`:
  `account_features.tf`, `ip_restrictions.tf`, `oauth_configurations.tf`, `user_groups.tf`, `project_artefacts.tf`, `lineage_integrations.tf`, `semantic_layer.tf`

- **Sensitive variable support**: New `oauth_client_secrets` and `lineage_tokens` sensitive variables for passing redacted secrets at apply time

- **Element IDs**: All 8 types registered in `apply_element_ids()` with proper hierarchy placement

- **Reporter**: Summary and detailed report sections for all new resource types

- **Entity table**: Type definitions, default columns, and data loaders for all 8 types

### Fixed

- **Scope page "All Projects" connection selection** — When scope mode is `all_projects`, all connections are now selected unconditionally. Previously, only connections referenced by environments were selected, causing 36 of 67 connections to be missed (legacy, unused, or project-level-only connections that no environment references).

### Changed

- **UI maps updated across 12 files** for type codes, filters, labels, and sort orders:
  `scope.py`, `mapping.py`, `deploy.py`, `destroy.py`, `target_matcher.py`, `terraform_import.py`, `protection_manager.py`, `hierarchy_index.py`, `terraform_state_reader.py`, `progress_tree.py`, `fetch_source.py`, `fetch_target.py`

---

## Files Changed

| File | Change |
|------|--------|
| `importer/models.py` | New Pydantic models for 6 resource types |
| `importer/fetcher.py` | Fetch functions for account-level and project-level resources |
| `importer/normalizer/core.py` | Normalization with sensitive data redaction |
| `importer/element_ids.py` | Element ID registration for 8 types |
| `importer/reporter.py` | Summary and detail report sections |
| `importer/web/components/entity_table.py` | Type definitions, columns, data loaders |
| `importer/web/components/hierarchy_index.py` | Hierarchy placement for new types |
| `importer/web/components/progress_tree.py` | Sidebar display names |
| `importer/web/components/target_matcher.py` | Resource type labels |
| `importer/web/pages/scope.py` | Type maps + connection selection fix |
| `importer/web/pages/mapping.py` | Type maps and filters |
| `importer/web/pages/deploy.py` | Type labels |
| `importer/web/pages/destroy.py` | Type labels and TF type maps |
| `importer/web/pages/fetch_source.py` | Resource counts and progress tree |
| `importer/web/pages/fetch_target.py` | Resource counts and progress tree |
| `importer/web/utils/protection_manager.py` | Resource type names (5 locations) |
| `importer/web/utils/terraform_import.py` | TF resource type mappings |
| `importer/web/utils/terraform_state_reader.py` | TF type to global section maps |
| `modules/projects_v2/account_features.tf` | New: account features resource |
| `modules/projects_v2/ip_restrictions.tf` | New: IP restrictions resource |
| `modules/projects_v2/oauth_configurations.tf` | New: OAuth configuration resource |
| `modules/projects_v2/user_groups.tf` | New: user groups resource |
| `modules/projects_v2/project_artefacts.tf` | New: project artefacts resource |
| `modules/projects_v2/lineage_integrations.tf` | New: lineage integration resource |
| `modules/projects_v2/semantic_layer.tf` | New: semantic layer config + mapping |
| `modules/projects_v2/main.tf` | Locals for new global resource processing |
| `modules/projects_v2/variables.tf` | Sensitive variables for secrets |

---

## Verification

```bash
cat importer/VERSION
# Expected: 0.27.0

python3 -c "from importer import get_version; print(get_version())"
# Expected: 0.27.0
```

For scope fix: navigate to `/scope`, select "All Projects", click "Apply Scope", and verify all connections are selected.
