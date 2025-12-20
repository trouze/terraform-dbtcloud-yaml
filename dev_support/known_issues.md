# Known Issues and Limitations

**Last Updated:** 2025-12-20  
**Provider Version:** `dbt-labs/dbtcloud = 1.5.1`

This document tracks known issues, limitations, and workarounds for the terraform-dbtcloud-yaml importer and the Terraform provider.

---

## Provider Bugs

### 1. Service Token Permission Inconsistency

**Status:** Provider Bug (Upstream Issue)  
**Severity:** High  
**Provider Version:** 1.5.1

**Issue:**
The Terraform provider returns a different structure for `service_token_permissions` than what was planned, causing Terraform to report "Provider produced inconsistent result after apply" errors.

**Error Message:**
```
Error: Provider produced inconsistent result after apply
.service_token_permissions: planned set element does not correlate with any element in actual.
This is a bug in the provider, which should be reported in the provider's own issue tracker.
```

**Impact:**
- Service tokens are created successfully
- Permissions may not be correctly applied or tracked by Terraform state
- Subsequent `terraform apply` runs may attempt to recreate permissions

**Workaround:**
- None - this is a provider bug that needs to be reported/fixed upstream
- Service tokens will still function, but Terraform state may be inconsistent
- Consider manually verifying permissions in the dbt Cloud UI after apply

**Reported:** Not yet reported to provider maintainers

---

## API Requirements and Limitations

### 2. Environment Variables Must Have Values

**Status:** API Requirement  
**Severity:** Medium  
**Fixed:** Yes (filtered in Terraform)

**Issue:**
The dbt Cloud API requires all environment variables to have at least one value set. Environment variables with empty or null values will be rejected.

**Error Message:**
```
Error: Error creating environment variable
Attempted to create an environment variable with no specified values. 
All environment variables must have at least one value set.
```

**Fix:**
The importer now filters out environment variables with empty `environment_values` during Terraform resource creation.

**Location:** `modules/projects_v2/environment_vars.tf`

---

### 3. Deprecated dbt Versions

**Status:** API Limitation  
**Severity:** Medium  
**Fixed:** Yes (filtered in Terraform)

**Issue:**
Some dbt versions (e.g., `latest-fusion`) are deprecated and no longer supported by the dbt Cloud API. Environments using these versions cannot be created or updated.

**Error Message:**
```
Error: Error creating the environment
dbt version latest-fusion is deprecated (unsupported) and cannot be used to update Environments.
```

**Affected Versions:**
- `latest-fusion`
- Any version containing `fusion` in the name

**Fix:**
The importer now filters out environments with deprecated dbt versions during Terraform resource creation.

**Location:** `modules/projects_v2/environments.tf`

**Alternative Solutions:**
- Map deprecated versions to supported versions in the normalizer (`importer/normalizer/core.py`)
- Manually update deprecated versions in the source account before migration

---

## Authentication Requirements

### 4. Service Token vs Personal Access Token (PAT)

**Status:** API Requirement  
**Severity:** High  
**Impact:** Permission assignment failures

**Issue:**
Certain administrative operations require a **Service Token** (`dbtc_` prefix) instead of a **Personal Access Token** (`dbtu_` prefix):

- Creating/managing service tokens
- Assigning permissions to service tokens
- Creating/managing groups
- Assigning permissions to groups
- Some notification operations

**Error Messages:**
```
Error: Unable to assign permissions to the service token
resource-not-found-permissions: The resource was not found
Status: 404

Error: Unable to assign permissions to the group
Error: internal-server-error
Status: 500
```

**Solution:**
Use a **Service Token** (`dbtc_` prefix) for `DBT_TARGET_API_TOKEN` when performing these operations.

**Detection:**
The E2E test script (`test/run_e2e_test.sh`) now detects token type and warns if a PAT is being used for operations that may require a service token.

**Token Types:**
- **Service Token**: Starts with `dbtc_` - Required for administrative operations
- **Personal Access Token (PAT)**: Starts with `dbtu_` - Limited permissions, may fail on admin operations

---

## Cross-Account Migration Limitations

### 5. Notification Migration Limitations

**Status:** Migration Limitation  
**Severity:** High  
**Fix Status:** ✅ Filtered in Terraform (v0.6.3)

**Issue:**
Notifications cannot be migrated during initial account migration due to:
1. **User IDs**: Source account user IDs don't exist in target account
2. **Job IDs**: Source account job IDs don't exist in target account (jobs not yet created/mapped)
3. **Slack Integration**: Slack notifications require Slack integration setup in target account

**Error Messages:**
```
Error: Unable to create notification
User instance with id 103835 does not exist.

Error: Unable to create notification
Jobs definition IDs 526578, 542963, 879560, 577949, 575342 do not exist
```

**Notification Types:**
- **Type 1 (User Email)**: Skipped - requires user migration (not possible via API)
- **Type 2 (Slack)**: Skipped - requires Slack integration in target account
- **Type 4 (External Email)**: Only created if no job references (jobs not yet mapped)

**Current Behavior:**
- All notifications are **fetched and normalized** (preserved in YAML for future use)
- Only external email notifications (type 4) **without job references** are created during initial migration
- User notifications, Slack notifications, and job-linked notifications are **skipped** during Terraform apply

**Fix:**
- Added filtering in `modules/projects_v2/globals.tf` to skip incompatible notifications
- Set `user_id = null` for external email notifications (source user doesn't exist)
- Filter out notifications with job references (jobs not yet mapped)

**Future Enhancement:**
A separate `--migrate-notifications` mode will be implemented to:
- Map source job IDs to target job IDs after jobs are created
- Detect and configure Slack integrations in target account
- Handle user notification migration (if user migration becomes possible via API)

**Location:** `modules/projects_v2/globals.tf` (lines 181-204)

**References:**
- [dbt Cloud Notification API](https://docs.getdbt.com/dbt-cloud/api-v2#/operations/Create%20Notification)

---

## Dependency Cascades

### 7. Service Token Permission Assignment Failures

**Status:** Dependency Cascade  
**Severity:** Medium  
**Mitigation:** Added `depends_on` blocks

**Issue:**
Service token permission assignments fail (404) when:
- Service tokens aren't fully created yet
- Projects referenced in permissions don't exist yet
- Using PAT instead of service token

**Fix:**
Added explicit `depends_on` blocks to ensure projects exist before creating service tokens with project-specific permissions.

**Location:** `modules/projects_v2/globals.tf`

---

### 8. Group Permission Assignment Failures

**Status:** Dependency Cascade  
**Severity:** Medium  
**Mitigation:** Added `depends_on` blocks

**Issue:**
Group permission assignments fail (500) when:
- Groups aren't fully created yet
- Projects referenced in permissions don't exist yet
- Using PAT instead of service token

**Fix:**
Added explicit `depends_on` blocks to ensure projects exist before creating groups with project-specific permissions.

**Location:** `modules/projects_v2/globals.tf`

---

## Version Pinning

### 9. Provider Version Pinned

**Status:** Configuration  
**Severity:** Low  
**Action:** Completed

**Issue:**
Provider version was using `~> 1.5` which allows automatic updates to 1.5.x versions, potentially introducing breaking changes or new bugs.

**Fix:**
Pinned provider version to `= 1.5.1` in:
- `providers.tf`
- `test/e2e_test/main.tf`

**Rationale:**
- Prevents unexpected version updates
- Ensures consistent behavior across environments
- Allows controlled testing of new provider versions

**Updating:**
To update the provider version:
1. Test new version in development environment
2. Update version constraint in both files
3. Run `terraform init -upgrade` to update lock file
4. Test thoroughly before deploying

---

## Summary

| Issue | Status | Severity | Fix Status |
|-------|--------|----------|------------|
| Service Token Permission Inconsistency | Provider Bug | High | None (upstream) |
| Empty Environment Variables | API Requirement | Medium | ✅ Fixed |
| Deprecated dbt Versions | API Limitation | Medium | ✅ Fixed |
| Service Token vs PAT | API Requirement | High | ⚠️ Documented |
| Notification Migration | Migration Limitation | High | ✅ Fixed (filtered) |
| Service Token Dependencies | Dependency Cascade | Medium | ✅ Fixed |
| Group Dependencies | Dependency Cascade | Medium | ✅ Fixed |
| Provider Version | Configuration | Low | ✅ Fixed |

---

## Reporting Issues

### Provider Bugs
Report provider bugs to: https://github.com/dbt-labs/terraform-provider-dbtcloud/issues

### Importer Issues
Report importer issues to: https://github.com/dbt-labs/terraform-dbtcloud-yaml/issues

---

## References

- [Apply Errors Analysis](./APPLY_ERRORS_ANALYSIS.md) - Detailed error analysis from full apply
- [Terraform Provider Documentation](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs)
- [dbt Cloud API Documentation](https://docs.getdbt.com/dbt-cloud/api-v2)
