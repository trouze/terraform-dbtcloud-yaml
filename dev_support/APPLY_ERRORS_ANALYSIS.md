# Terraform Apply Errors Analysis

**Date:** 2025-12-20  
**Account:** 725 (Target)  
**Resources Planned:** 97 to add  
**Resources Created:** ~60+ (partial success)

---

## Error Categories

### 1. Service Token Permission Inconsistencies (Provider Bug)
**Count:** 11 errors  
**Lines:** 594-691

**Error Message:**
```
Error: Provider produced inconsistent result after apply
.service_token_permissions: planned set element does not correlate with any element in actual.
This is a bug in the provider, which should be reported in the provider's own issue tracker.
```

**Affected Tokens:**
- `test_analysit`, `tf_migrator`, `terraforming_admin`, `postman_20250416`, `gtok_admin`, `account_admin`, `discoveryapi` (2 errors), `getting_to_ok_account_admin`, `tf_migrate_service12`, `job_runner`, `another_account_admin`

**Root Cause:** The Terraform provider is returning a different structure for `service_token_permissions` than what was planned. This is a known provider bug.

**Impact:** Service tokens are created but permissions may not be correctly applied.

**Workaround:** None - this is a provider bug that needs to be reported/fixed upstream.

---

### 2. Environment Variables with No Values
**Count:** 5 errors  
**Lines:** 702-750

**Error Message:**
```
Error: Error creating envrionment variable
Attempted to create an environment variable with no specified values. 
All environment variables must have at least one value set.
```

**Affected Variables:**
- `test_admin_project_DBT_ENV_SECRET_PASSWORD`
- `getting_to_ok_clone_and_defer_DBT_SHARED_SVCS_REV`
- `test_admin_project_DBT_SECRET_PASSWORD`
- `getting_to_ok_clone_and_defer_DBT_ENV_SECRET_GITHUB_TOKEN`
- `getting_to_ok_clone_and_defer_DBT_MODEL_VOLUMES`

**Root Cause:** These environment variables have empty/null values in the source account. The API requires at least one value to be set.

**Fix Required:** Filter out environment variables with no values during normalization or Terraform resource creation.

**Recommendation:** Add validation in `modules/projects_v2/environment_vars.tf` to skip creation of env vars with no values.

---

### 3. Deprecated dbt Versions
**Count:** 7 errors  
**Lines:** 752-820

**Error Message:**
```
Error: Error creating the environment
dbt version latest-fusion is deprecated (unsupported) and cannot be used to update Environments.
```

**Affected Environments:**
- `fusion_scd2_workspace_1_1_prod_snowflake`
- `fusion_scd2_workspace_1_2_prod_databricks`
- `will_sargent_fusion_migration_sandbox_development`
- `getting_to_ok_clone_and_defer_1_2_prod_databricks`
- `getting_to_ok_clone_and_defer_2_staging`
- `fusion_scd2_workspace_development`
- `will_sargent_fusion_migration_sandbox_fusion_prod`

**Root Cause:** Source account uses deprecated dbt versions (`latest-fusion`) that are no longer supported in the target account.

**Fix Required:** 
1. Detect deprecated dbt versions during fetch/normalize
2. Either skip these environments or map to a supported version
3. Add warning/error handling for deprecated versions

**Recommendation:** Add version validation in normalizer to detect and handle deprecated versions.

---

### 4. Service Token Permission Assignment 404s
**Count:** 5 errors  
**Lines:** 822-885

**Error Message:**
```
Error: Unable to assign permissions to the service token
resource-not-found-permissions: The resource was not found
Status: 404
```

**Affected Tokens:**
- `tf_dev_team_admin` (2733581)
- `team_general` (2733574)
- `gtok_sl` (2733579)
- `team_prod` (2733577)
- `team_dev` (2733575)

**Root Cause Hypothesis:** ⚠️ **LIKELY CAUSE**: These operations may require a **service token (dbtc_)** instead of a **PAT (dbtu_)**. Administrative operations like:
- Assigning permissions to service tokens
- Creating/managing service tokens
- Assigning permissions to groups

May require service token authentication. If `DBT_TARGET_API_TOKEN` is a PAT (starts with `dbtu_`), these operations will fail with 404.

**Alternative Causes:**
- Timing issue (token not fully created yet)
- Permissions endpoint issue
- Token ID mismatch

**Impact:** Tokens exist but permissions are not assigned.

**Recommendation:** 
1. **Verify token type**: Check if `DBT_TARGET_API_TOKEN` is a PAT (`dbtu_`) or service token (`dbtc_`)
2. **Use service token**: If using PAT, switch to service token for these operations
3. **Test**: Re-run apply with service token to verify hypothesis

---

### 5. Group Permission Assignment 500s
**Count:** 3 errors  
**Lines:** 887-912

**Error Message:**
```
Error: Unable to assign permissions to the group
Error: internal-server-error
Status: 500
```

**Affected Groups:**
- `terraform_project_grou`
- `hackathon`
- `member`

**Root Cause Hypothesis:** ⚠️ **LIKELY CAUSE**: Similar to service token permissions, assigning permissions to groups may require a **service token (dbtc_)** instead of a **PAT (dbtu_)**. The 500 error might be a misleading response when the API rejects PAT authentication for this operation.

**Alternative Cause:** Server-side error when assigning permissions to groups. This is an API/server issue, not a client issue.

**Impact:** Groups are created but permissions are not assigned.

**Recommendation:** 
1. **Verify token type**: Check if `DBT_TARGET_API_TOKEN` is a PAT (`dbtu_`) or service token (`dbtc_`)
2. **Use service token**: If using PAT, switch to service token for group permission operations
3. **Test**: Re-run apply with service token to verify hypothesis

---

### 6. Notification Errors (Cross-Account References)
**Count:** 14 errors  
**Lines:** 914-1053

**Error Message:**
```
Error: Unable to create notification
User instance with id 103835 does not exist.
Jobs definition IDs 542963 do not exist
```

**Root Cause:** 
- **User IDs don't exist**: Users from source account (86165) don't exist in target account (725)
- **Job IDs don't exist**: Jobs referenced in notifications haven't been created yet (dependency ordering issue)

**Affected Notifications:**
- Multiple notifications referencing non-existent users (103835, 115902)
- Multiple notifications referencing non-existent jobs (542963, 526578, 679404, etc.)

**Fix Required:**
1. **User ID Mapping**: Map source user IDs to target user IDs, or skip notifications with invalid user IDs
2. **Job Dependency**: Create notifications after jobs are created, or use job keys instead of IDs

**Recommendation:** 
- Add user ID validation/mapping in normalizer
- Reorder resource creation: Projects → Jobs → Notifications
- Use job keys/names instead of IDs in notification references

---

## Summary Statistics

| Category | Count | Severity | Fix Required |
|----------|-------|----------|--------------|
| Provider Bugs | 11 | High | Report upstream |
| Empty Env Vars | 5 | Medium | Filter in normalizer/Terraform |
| Deprecated Versions | 7 | Medium | Version validation/mapping |
| Permission 404s | 5 | Medium | Retry logic or provider fix |
| Permission 500s | 3 | Low | Retry logic or API fix |
| Cross-Account Refs | 14 | High | User mapping, dependency ordering |
| **Total** | **45** | | |

---

## Immediate Actions Required

### High Priority
1. **Verify Token Type**: Check if `DBT_TARGET_API_TOKEN` is PAT (`dbtu_`) or service token (`dbtc_`)
2. **Use Service Token**: If using PAT, switch to service token for:
   - Creating/managing service tokens
   - Assigning permissions to service tokens
   - Creating/managing groups
   - Assigning permissions to groups
   - Some notification operations
3. **Filter Empty Environment Variables**: Skip creation of env vars with no values
4. **Handle Deprecated dbt Versions**: Detect and map/skip deprecated versions
5. **Fix Notification Dependencies**: Create notifications after jobs, or use job keys

### Medium Priority
6. **Add Retry Logic**: For permission assignment 404s/500s (if not token-related)
7. **User ID Mapping**: Map source user IDs to target user IDs for notifications

### Low Priority
8. **Report Provider Bugs**: Service token permission inconsistencies
9. **Investigate Permission 404s**: Determine if timing issue or provider bug (if not token-related)

---

## Success Metrics

- **Resources Created:** ~60+ out of 97 planned (62%+ success rate)
- **Connections:** ✅ All 3 created successfully
- **Projects:** ✅ All 17 created successfully  
- **Environments:** ✅ Most created (7 failed due to deprecated versions)
- **Service Tokens:** ⚠️ Created but permissions inconsistent
- **Groups:** ⚠️ Created but permissions failed
- **Notifications:** ❌ Most failed due to cross-account references

---

## Next Steps

1. Run `./run_e2e_test.sh --destroy` to clean up partially created resources
2. Implement fixes for empty env vars and deprecated versions
3. Fix notification dependency ordering
4. Re-run apply to verify fixes

