# Release Notes - v0.21.0

**Release Date:** 2026-02-11  
**Release Type:** Minor (EnvVar Protection + State-Only Resource Fixes + Terraform Plan Stability)  
**Previous Version:** 0.20.0

---

## Summary

This release adds full protection lifecycle support for dbt Cloud environment variables (VARs), fixes several critical Terraform plan stability issues (unwanted destroys, unwanted creates), and resolves the protection key mismatch bug that prevented state-only resources from persisting their protection status in the UI.

---

## Key Changes

### EnvVar (VAR) Protection Support

Environment variables are now fully supported as protectable dbt Cloud resources:

- **Terraform module**: `environment_vars.tf` splits into `protected_environment_variables` and `unprotected_environment_variables` locals, with a dedicated `resource "dbtcloud_environment_variable" "protected_environment_variables"` block that includes `lifecycle { prevent_destroy = true }`
- **Protection manager**: `RESOURCE_TYPE_MAP` and `EXTENDED_RESOURCE_TYPE_MAP` include VAR entries for moved block generation and mismatch detection
- **YAML updater**: `apply_protection_from_set` and `apply_unprotection_from_set` handle composite VAR keys (`{project_key}_{env_var_name}`)
- **Element IDs**: Project-scoped `element_mapping_id` prevents cross-project collisions for VARs with the same name (e.g., `DBT_ENVIRONMENT_NAME` across multiple projects)

### State-Only Resource Detail Panel

Clicking the detail view icon on state-only resources (resources that exist in Terraform state but are not part of the source selection set) now correctly displays target and state data. Previously, this showed a "Source resource not found" toast error.

### Terraform Plan Stability Fixes

1. **Protected VARs no longer destroyed**: When `dbt-cloud-config.yml` contained `environment_variables: []` for a project, the deep merge would clobber populated baseline data. The `_deep_merge_dict` function now preserves populated keyed lists when the source provides an empty list.

2. **Target-only projects no longer created**: The baseline merge in `start_generate_protection_changes` now filters `baseline_config["projects"]` to only include projects already present in the deploy config, preventing unmanaged target-only projects from being introduced.

3. **Protection key mismatch resolved**: The grid protection status post-processing now normalizes `state__<tf_address>` keys to `TYPE:short_key` format before looking up intents, matching the write path storage format. State-only resources now correctly show and persist protection status.

---

## Files Changed

| File | Change |
|------|--------|
| `importer/VERSION` | 0.20.0 → 0.21.0 |
| `importer/element_ids.py` | Project-scoped element IDs for VARs |
| `importer/web/components/entity_table.py` | State-only resource detail dialog support |
| `importer/web/components/match_grid.py` | Protection key normalization for state-only rows |
| `importer/web/pages/match.py` | State-only detail handler, baseline merge filter, protection flow |
| `importer/web/utils/adoption_yaml_updater.py` | VAR protection YAML updates, deep merge empty list fix |
| `importer/web/utils/protection_manager.py` | VAR entries in resource type maps |
| `modules/projects_v2/environment_vars.tf` | Protected/unprotected VAR resource split |
| `modules/projects_v2/jobs.tf` | Minor job module adjustments |
| `prd/41.02-Adding-New-Terraform-Object-Support.md` | VAR abbreviation clarification |
| `prd/42.01-Global-Resources-Target-Intent.md` | Updated AD-3 for VAR protection coverage |

---

## Upgrade Notes

- **No breaking changes** — this is a backwards-compatible minor release
- After upgrading, run "Generate Protection Changes" to pick up any existing VAR protection intents
- Existing `dbt-cloud-config.yml` files with `environment_variables: []` will now correctly preserve target baseline data during merges

---

## Testing

- Browser-verified protection toggle for state-only resources persists across grid refreshes
- Debug logs confirm key normalization: `state__<tf_address>` → `TYPE:short_key` round-trips correctly
- Terraform plan verified: 0 to add, 0 to change, 0 to destroy after protection changes applied
