# Release Notes: v0.6.1

**Release Date:** 2025-12-20  
**Version:** 0.6.1 (Patch Release)  
**Type:** Bug Fixes & Stability Improvements

---

## Summary

This patch release addresses several stability and error prevention improvements. The provider version is now pinned to prevent unexpected updates, and filtering has been added to skip problematic resources (empty environment variables and deprecated dbt versions) that cause API errors. Additionally, explicit dependency declarations ensure proper resource ordering.

---

## 🐛 Bug Fixes

### Provider Version Pinning

**Issue:** Provider version constraint `~> 1.5` allowed automatic updates to any 1.5.x version, potentially introducing breaking changes or new bugs.

**Fix:** Pinned provider version to exact version `= 1.5.1` in:
- `providers.tf`
- `test/e2e_test/main.tf`

**Impact:** Prevents unexpected version updates and ensures consistent behavior across environments.

**Upgrade Path:** To update the provider version:
1. Test new version in development environment
2. Update version constraint in both files
3. Run `terraform init -upgrade` to update lock file
4. Test thoroughly before deploying

---

### Empty Environment Variables Filtering

**Issue:** The dbt Cloud API rejects environment variables with no values, causing 11 API errors during Terraform apply.

**Error Message:**
```
Error: Error creating environment variable
Attempted to create an environment variable with no specified values. 
All environment variables must have at least one value set.
```

**Fix:** Added filtering in `modules/projects_v2/environment_vars.tf` to skip environment variables with empty `environment_values`:

```terraform
env_vars_map = {
  for item in local.all_environment_variables :
  "${item.project_key}_${item.env_var_key}" => item
  if length(try(item.env_var_data.environment_values, {})) > 0
}
```

**Impact:** Prevents 11 API errors during apply. Environment variables with no values are silently skipped (as they cannot be created anyway).

---

### Deprecated dbt Versions Filtering

**Issue:** Some environments use deprecated dbt versions (e.g., `latest-fusion`) that are no longer supported by the API, causing 7 API errors and cascading failures.

**Error Message:**
```
Error: Error creating the environment
dbt version latest-fusion is deprecated (unsupported) and cannot be used to update Environments.
```

**Fix:** Added filtering in `modules/projects_v2/environments.tf` to skip environments with deprecated versions:

```terraform
resource "dbtcloud_environment" "environments" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if !can(regex("latest-fusion|fusion", try(item.env_data.dbt_version, "")))
  }
  # ... rest of resource
}
```

**Impact:** 
- Prevents 7 API errors during apply
- Prevents cascading failures (jobs, credentials, etc. that depend on these environments)
- Environments with deprecated versions are skipped (as they cannot be created)

**Alternative Solutions:**
- Map deprecated versions to supported versions in the normalizer (`importer/normalizer/core.py`)
- Manually update deprecated versions in the source account before migration

---

### Dependency Cascade Prevention

**Issue:** Service tokens and groups with project-specific permissions were being created before projects existed, causing permission assignment failures.

**Fix:** Added explicit `depends_on` blocks in `modules/projects_v2/globals.tf`:

```terraform
resource "dbtcloud_service_token" "service_tokens" {
  # ... existing config
  depends_on = [
    dbtcloud_project.projects
  ]
}

resource "dbtcloud_group" "groups" {
  # ... existing config
  depends_on = [
    dbtcloud_project.projects
  ]
}
```

**Impact:** Ensures projects exist before creating tokens/groups with project-specific permissions, preventing dependency ordering issues.

---

## 📋 Technical Details

### Files Modified

- `providers.tf` - Pinned provider version to `= 1.5.1`
- `test/e2e_test/main.tf` - Pinned provider version to `= 1.5.1`
- `modules/projects_v2/environment_vars.tf` - Added filtering for empty env vars (line 26)
- `modules/projects_v2/environments.tf` - Added filtering for deprecated versions (line 83)
- `modules/projects_v2/globals.tf` - Added `depends_on` blocks for service tokens and groups

### Error Prevention Summary

| Issue | Errors Prevented | Fix Location |
|-------|------------------|--------------|
| Empty Environment Variables | 11 | `environment_vars.tf` |
| Deprecated dbt Versions | 7 | `environments.tf` |
| Dependency Cascades | Variable | `globals.tf` |

---

## 🔄 Migration Guide

### No Action Required

This is a patch release with bug fixes and stability improvements. No migration steps are required.

### Recommended Actions

1. **Update Provider Lock File:**
   ```bash
   terraform init -upgrade
   ```

2. **Review Skipped Resources:**
   - Check Terraform plan output for any skipped environment variables or environments
   - Manually create skipped resources if needed (with proper values/versions)

3. **Verify Dependencies:**
   - Ensure service tokens and groups are created after projects
   - Review `depends_on` relationships if customizing module usage

---

## 📚 Related Documentation

- [Known Issues](./KNOWN_ISSUES.md) - Comprehensive list of known issues and limitations
- [Apply Errors Analysis](./APPLY_ERRORS_ANALYSIS.md) - Detailed analysis of apply errors
- [Version Update Checklist](./VERSION_UPDATE_CHECKLIST.md) - Version management guide

---

## ✅ Testing

This release has been tested with:
- E2E test suite (`test/run_e2e_test.sh --test-apply`)
- Terraform plan/validate on multiple account configurations
- Provider version pinning verification

---

## 🙏 Acknowledgments

- Provider bug fix collaboration with terraform-provider-dbtcloud team
- Error analysis and categorization from E2E test results

---

**Next Steps:**
- Continue monitoring for additional API errors or edge cases
- Consider adding user ID mapping for notifications (cross-account references)
- Investigate service token permission assignment 404s (may require service token instead of PAT)

