# Release Notes - v0.25.0

**Release Date:** 2026-03-05  
**Release Type:** Minor (State Management Expansion + Bug Fixes)  
**Previous Version:** 0.24.0

---

## Summary

This release expands the State Management utility with refresh-only workflows, fixes repository clone strategy preservation and target job visibility bugs, and documents the GitLab deploy_token API 500 root cause (with a backend PR filed against dbt-cloud).

---

## What's New

### State Management Refresh-Only Workflows

The `/removal-management` page (State Management) now supports refresh-only workflows that allow state inspection without requiring destructive `terraform state rm` operations. This enables safer operational patterns where teams can audit state before committing to removal actions.

### GitLab Deploy Token Bug Documentation

Documented the root cause of GitLab `deploy_token` repository creation 500 errors via Datadog APM trace analysis. The actual crash is `GitlabGetError: 404 Project Not Found` — an unhandled exception class in `legacy_create.py`. A backend fix PR has been filed at [dbt-labs/dbt-cloud#16687](https://github.com/dbt-labs/dbt-cloud/pull/16687).

---

## Bug Fixes

### Repository Clone Strategy Preservation

**Problem:** When source YAML explicitly set `git_clone_strategy: deploy_token`, the normalizer would override it back to `deploy_key` during processing.

**Fix:** The normalizer now preserves explicit `git_clone_strategy` values from source YAML, only applying defaults when no strategy is specified.

### Target Job Rows with Null Environment Credentials

**Problem:** Target job rows disappeared from the match grid when the associated environment had null credentials, causing mismatches in the migration view.

**Fix:** Job rows are now retained in the match grid regardless of environment credential state, preventing invisible data loss during reconciliation.

---

## Files Changed

### New Files
- `dev_support/RELEASE_NOTES_v0.25.0.md` — This release notes file
- `bugs/bug3-gitlab-deploy-token-pat.md` — GitLab deploy_token 500 root cause analysis

### Modified Files
- `importer/VERSION` — Updated to 0.25.0
- `CHANGELOG.md` — Added 0.25.0 section
- `dev_support/importer_implementation_status.md` — Updated version and changelog
- `dev_support/phase5_e2e_testing_guide.md` — Updated version reference
- `importer/web/pages/removal_management.py` — Expanded with refresh-only workflows
- `importer/web/state.py` — State management updates
- `importer/fetcher.py` — Job row retention fix
- `importer/element_ids.py` — Element ID updates
- `modules/projects_v2/projects.tf` — Clone strategy preservation

---

## Migration Notes

No migration required. All changes are backwards-compatible.

---

## Testing

```bash
# Verify version
cat importer/VERSION
# Should show: 0.25.0

python3 -c "from importer import get_version; print(get_version())"

# Run existing tests
python3 -m pytest importer/web/tests/ -v
```

---

## Related

- **Backend PR:** [dbt-labs/dbt-cloud#16687](https://github.com/dbt-labs/dbt-cloud/pull/16687) — Catches `GitlabGetError` (404 Project Not Found) in repository creation
- **Bug Report:** `bugs/bug3-gitlab-deploy-token-pat.md`

---

## Upgrade Path

```bash
git pull
cat importer/VERSION
# Should show: 0.25.0
```
