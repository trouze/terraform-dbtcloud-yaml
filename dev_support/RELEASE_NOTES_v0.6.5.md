# Release Notes - v0.6.5

**Release Date:** 2026-01-08  
**Type:** Patch Release (Bug Fix)

---

## Summary

This release fixes GitLab repository creation during account migration. The fetcher now correctly retrieves `gitlab_project_id` from the dbt Cloud v3 API using an undocumented query parameter, enabling proper GitLab repository creation with the `deploy_token` strategy.

---

## Key Changes

### GitLab Repository Support

**Problem:** GitLab repositories with `deploy_token` strategy were failing to create because `gitlab_project_id` was not being fetched from the source account.

**Root Cause:** The dbt Cloud v3 Retrieve Repository API does not return the `gitlab` object (containing `gitlab_project_id`) by default. An undocumented `include_related` query parameter is required.

**Solution:**
1. Added `include_related=["deploy_key","gitlab"]` parameter to the v3 Repository API call
2. Fetcher now extracts `gitlab_project_id` from the nested `gitlab` object
3. E2E test script automatically detects GitLab repos and uses PAT as main token

### PAT Requirement for GitLab

**Discovery:** GitLab repositories require a Personal Access Token (PAT) for creation. Service tokens are not supported by the dbt Cloud provider.

**Solution:** The E2E test script (`test/run_e2e_test.sh`) now:
- Detects `deploy_token` strategy repos in the YAML config
- Automatically uses `DBT_TARGET_PAT` as `TF_VAR_dbt_token` when GitLab repos exist
- Warns users if GitLab repos are detected but no PAT is provided

---

## Technical Details

### API Discovery

The v3 Retrieve Repository endpoint (`/api/v3/accounts/{account_id}/projects/{project_id}/repositories/{repository_id}/`) supports an undocumented `include_related` query parameter:

```
GET /api/v3/accounts/{account_id}/projects/{project_id}/repositories/{repository_id}/?include_related=["deploy_key","gitlab"]
```

This returns the full `gitlab` object containing:
- `gitlab_project_id` (required for `deploy_token` strategy)
- Integration metadata (created_at, updated_at, state)

### Files Changed

- `importer/fetcher.py`: Added `include_related` parameter to v3 API call
- `test/run_e2e_test.sh`: Added GitLab detection and automatic PAT usage

---

## Upgrade Notes

### For Users with GitLab Repositories

1. Ensure `DBT_TARGET_PAT` is set in your `.env` file
2. The PAT must be a user token (`dbtu_*` prefix), not a service token (`dbtc_*`)
3. Re-run fetch to get updated repository metadata with `gitlab_project_id`

### No Breaking Changes

This release is backward compatible. No configuration changes are required for non-GitLab repositories.

---

## Known Limitations

- GitLab repository creation requires a PAT (user token)
- Service tokens cannot be used for GitLab repository operations
- This is a limitation of the dbt Cloud provider, not the importer

---

## Contributors

- dbt Labs Professional Services Team

---

**Previous Version:** [v0.6.4](RELEASE_NOTES_v0.6.4.md)

