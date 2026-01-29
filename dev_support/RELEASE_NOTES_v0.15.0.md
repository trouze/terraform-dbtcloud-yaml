# Release Notes - v0.15.0

**Release Date:** 2026-01-29  
**Release Type:** Minor (New Feature)  
**Previous Version:** 0.14.0

---

## Summary

Version 0.15.0 introduces **Destroy Page Protection Enhancements**, completing the resource protection workflow. Protected resources are now automatically skipped during destroy operations, eliminating Terraform errors and providing a smooth user experience. This release also includes Terraform module updates to support the `lifecycle.prevent_destroy` attribute and fixes for drift detection accuracy.

---

## New Features

### Destroy Section with Auto-Skip Protection

A new **Destroy Resources** section has been added to the Deploy page:

- **Auto-Skip Protected**: Destroy automatically skips resources with `protected_` in their Terraform address
- **Targeted Destroy**: Uses `-target` flags to only destroy unprotected resources
- **Skip Notification**: Terminal shows "Skipping N protected resources" with list of preserved items
- **Graceful Handling**: No Terraform errors when protected resources exist

### Protected Resources Panel

An informational panel displays protected resources during destroy:

- **Grouped by Type**: Projects, Environments, Jobs, Repositories shown separately
- **Count Badges**: Shows number of protected items per type
- **Blue Styling**: Matches the protection visual theme

### Unprotect All Option

For users who want to remove protection before destroying:

- **Explicit Action**: "Unprotect All" button in the protection panel
- **Confirmation Dialog**: Warning about consequences with resource list
- **Regenerate Required**: Notification to regenerate Terraform after unprotecting

### Destroy Confirmation Dialog

Added confirmation before destroy operations:

- **Warning Icon**: Clear visual indicator of destructive action
- **Clear Message**: "This will destroy all unprotected resources"
- **Protection Note**: Reminds user that protected resources will be skipped

---

## Terraform Module Updates

### Split Resources for Protection Support

All resource types now support `lifecycle.prevent_destroy`:

| Module | Protected Resource | Unprotected Resource |
|--------|-------------------|---------------------|
| `projects.tf` | `dbtcloud_project.protected_projects` | `dbtcloud_project.projects` |
| `projects.tf` | `dbtcloud_repository.protected_repositories` | `dbtcloud_repository.repositories` |
| `environments.tf` | `dbtcloud_environment.protected_environments` | `dbtcloud_environment.environments` |
| `jobs.tf` | `dbtcloud_job.protected_jobs` | `dbtcloud_job.jobs` |

### Project ID Lookups

Updated lookups to work with both protected and unprotected projects:

- **`environment_vars.tf`**: Added `env_var_project_id_lookup` local
- **`globals.tf`**: Uses `coalesce()` to check both project maps
- **`outputs.tf`**: Merged outputs include both protected and unprotected resources

### Schema Updates

Added `protected` field to resource definitions in `schemas/v2.json`:

```json
"protected": {
  "type": ["boolean", "null"],
  "default": false,
  "description": "If true, adds lifecycle.prevent_destroy to prevent accidental deletion"
}
```

---

## Bug Fixes

### Drift Detection Accuracy

Fixed the "2 resources have drift" message appearing when no actual drift exists:

- **Excluded State-Only**: Orphan resources in TF state no longer count as drift
- **Target Required**: Only counts resources with actual target_id
- **Better Diagnostics**: Shows which specific resources have drift

---

## Technical Implementation

### New Files

| File | Description |
|------|-------------|
| None | All changes in existing files |

### Modified Files

| File | Changes |
|------|---------|
| `importer/web/pages/deploy.py` | Added `_create_destroy_section()`, `_create_destroy_protection_panel()`, `_show_destroy_unprotection_dialog()`, modified `_run_terraform_destroy()` |
| `importer/web/pages/match.py` | Fixed `drift_resources_exist` calculation to exclude state-only orphans |
| `modules/projects_v2/projects.tf` | Split into protected/unprotected maps and resource blocks |
| `modules/projects_v2/environments.tf` | Added `protected_environments` resource block |
| `modules/projects_v2/jobs.tf` | Added `protected_jobs` resource block |
| `modules/projects_v2/environment_vars.tf` | Added `env_var_project_id_lookup` local |
| `modules/projects_v2/globals.tf` | Updated project_id lookups with `coalesce()` |
| `modules/projects_v2/outputs.tf` | Merged outputs from protected and unprotected resources |
| `schemas/v2.json` | Added `protected` field to project, environment, job, repository |

---

## User Workflow

### Destroying with Protected Resources

1. Navigate to **Deploy** tab
2. Scroll to **Destroy Resources** section
3. Review the **Protected Resources** panel (if any exist)
4. Click **Destroy All** button
5. Confirm in the dialog
6. Watch terminal: protected resources are skipped, unprotected are destroyed

### Removing Protection Before Destroy

1. In the **Protected Resources** panel, click **Unprotect All**
2. Review the confirmation dialog showing resources to unprotect
3. Click **Unprotect All** to confirm
4. Click **Generate Terraform** to apply the changes
5. Now **Destroy All** will affect all resources

---

## Breaking Changes

None. This release is fully backward-compatible.

---

## Migration Guide

No migration required. Existing configurations will continue to work:

- Resources without `protected: true` behave as before
- Destroy operations automatically detect and skip protected resources
- No configuration changes needed

---

## Known Issues

None identified.

---

## Dependencies

No new dependencies added.

---

## Verification

After updating, verify the version:

```bash
# Check version
cat importer/VERSION
# Expected: 0.15.0

# Verify import
python3 -c "from importer import get_version; print(get_version())"
# Expected: 0.15.0

# Check Terraform modules
grep -r "prevent_destroy" modules/projects_v2/
# Should show protected resource blocks
```

---

**Full Changelog:** See [CHANGELOG.md](../CHANGELOG.md)  
**Previous Release:** See [RELEASE_NOTES_v0.14.0.md](RELEASE_NOTES_v0.14.0.md)
