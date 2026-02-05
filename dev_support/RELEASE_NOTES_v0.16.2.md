# Release Notes - v0.16.2

**Release Date:** 2026-02-05  
**Release Type:** Patch (Bug Fix - Repository Key Prefix Matching)  
**Previous Version:** 0.16.1

---

## Summary

This release fixes a bug where `apply_protection_from_set` and `apply_unprotection_from_set` failed to match repository keys that have prefixes (e.g., `dbt_ep_sse_dm_fin_fido`) when the intent keys use base names (e.g., `REP:sse_dm_fin_fido`). This caused the "Moved object still exists" Terraform error when protection intent repair failed to update the YAML.

---

## Problem Description

### Symptoms
- Deploy Generate shows "Found 3 intent/YAML mismatch(es) - fixing..." but the repair fails silently
- Subsequent `terraform plan` fails with "Error: Moved object still exists"
- The generated `protection_moves.tf` contains incorrect moved blocks (opposite direction from intent)

### Root Cause

Repository keys in the YAML configuration often have prefixes like `dbt_ep_`:

```yaml
# dbt-cloud-config.yml
globals:
  repositories:
    - key: dbt_ep_sse_dm_fin_fido  # <-- prefixed key
      remote_url: git://github.com/example/repo.git
```

However, the Protection Intent keys use the base project name:

```
REP:sse_dm_fin_fido  # <-- base key without prefix
```

The original code in `apply_protection_from_set` used exact matching:

```python
# OLD (broken)
if repo_key in repo_keys_to_protect:  # Never matches!
    repo["protected"] = True
```

Since `"dbt_ep_sse_dm_fin_fido" != "sse_dm_fin_fido"`, the match failed and the YAML was not updated.

---

## The Fix

Added flexible key matching that:
1. First checks for exact match (backwards compatible)
2. Then checks if the YAML key `contains` or `ends with` the intent's base key

```python
# NEW (fixed)
for prot_key in repo_keys_to_protect:
    if prot_key and (prot_key in repo_key or repo_key.endswith(prot_key)):
        repo["protected"] = True
        break
```

This mirrors the flexible matching already used in `generate_moved_blocks_from_state`, ensuring consistency across the protection workflow.

---

## Files Changed

### Modified Files
- `importer/web/utils/adoption_yaml_updater.py`
  - `apply_protection_from_set`: Added flexible key matching for global repositories
  - `apply_unprotection_from_set`: Added flexible key matching for global repositories
- `importer/web/tests/test_generate_consistency.py` - Added 8 new tests
- `importer/VERSION` - Updated to 0.16.2
- `CHANGELOG.md` - Added 0.16.2 section
- `dev_support/importer_implementation_status.md` - Updated version and changelog
- `dev_support/phase5_e2e_testing_guide.md` - Updated version reference
- `dev_support/RELEASE_NOTES_v0.16.2.md` - This release notes file

---

## New Tests

### `TestRepositoryKeyPrefixMatching` (6 tests)

Tests flexible key matching for protection and unprotection operations:

| Test | Description |
|------|-------------|
| `test_apply_protection_matches_prefixed_repo_with_base_key` | Protects `dbt_ep_X` repo when intent has `REP:X` |
| `test_apply_unprotection_matches_prefixed_repo_with_base_key` | Unprotects `dbt_ep_X` repo when intent has `REP:X` |
| `test_apply_protection_still_works_with_exact_key_match` | Exact matches still work (backwards compat) |
| `test_apply_unprotection_still_works_with_exact_key_match` | Exact matches still work (backwards compat) |
| `test_apply_protection_handles_multiple_prefixed_repos` | Multiple repos with different prefixes |
| `test_apply_unprotection_handles_multiple_prefixed_repos` | Multiple repos with different prefixes |

### `TestIntentYamlRepairWithPrefixedRepos` (2 tests)

Integration tests for full repair flow:

| Test | Description |
|------|-------------|
| `test_repair_protects_prefixed_repos_matching_intent` | Full workflow: intent → repair → YAML protected |
| `test_repair_unprotects_prefixed_repos_matching_intent` | Full workflow: intent → repair → YAML unprotected |

---

## Running Tests

```bash
# Run new prefix matching tests
python3 -m pytest importer/web/tests/test_generate_consistency.py -v -k "Prefix"

# Run all tests to verify no regressions
python3 -m pytest importer/web/tests/ -v

# Expected: 147 passed, 1 xfailed
```

---

## Migration Notes

No migration required. This is a backwards-compatible bug fix. Existing exact key matches continue to work; the fix only adds support for prefix matching when exact matches fail.

---

## Related Documentation

- **Protection Manager**: `importer/web/utils/protection_manager.py` - Already had flexible matching
- **Adoption YAML Updater**: `importer/web/utils/adoption_yaml_updater.py` - Fixed in this release
- **Deploy Page**: `importer/web/pages/deploy.py` - Uses both components

---

## Upgrade Path

```bash
# Pull latest changes
git pull

# Verify version
cat importer/VERSION
# Should show: 0.16.2

# Run tests to verify
python3 -m pytest importer/web/tests/test_generate_consistency.py -v -k "Prefix"
# Should show: 8 passed
```
