# Release Notes — v0.21.1

**Date:** 2026-02-11  
**Type:** Patch Release  
**Previous Version:** 0.21.0

---

## Summary

Fixes Terraform plan failures caused by incomplete `-target` flags when protection moved blocks span multiple resource types (ENV, JOB, VAR). Also extends YAML-vs-state mismatch detection to all sub-resource types.

## Key Fixes

### Terraform Plan Targeting for Moved Blocks
- **Problem:** After generating protection changes that included ENV and JOB moved blocks (via `detect_protection_mismatches`), the Terraform plan failed with "Moved resource instances excluded by targeting" because the `-target` flags only included addresses from pending intents (REP, PREP, VAR), missing the ENV/JOB addresses.
- **Fix:** The plan command now parses `protection_moves.tf` to extract all `from`/`to` addresses and adds them to the `-target` flags. This ensures all resources referenced in moved blocks are included in the plan scope.
- **Files:** `importer/web/pages/match.py`

### Sub-Resource Mismatch Detection
- **Problem:** `detect_protection_mismatches` only compared PRJ, REP, and PREP resources against TF state, missing environments, jobs, environment variables, and extended attributes that had `protected: true` in YAML but were still in unprotected TF state blocks.
- **Fix:** Extended the function to build a `sub_resource_protection` map from YAML for ENV, JOB, VAR, and EXTATTR resources, then compares each against its TF state address. Orphaned protection flags now generate proper `ProtectionMismatch` objects and corresponding moved blocks.
- **Files:** `importer/web/utils/protection_manager.py`

## Files Changed

| File | Change |
|------|--------|
| `importer/VERSION` | `0.21.0` → `0.21.1` |
| `importer/web/pages/match.py` | Parse `protection_moves.tf` for target addresses; call `detect_protection_mismatches` after pending intents |
| `importer/web/utils/protection_manager.py` | Extend `detect_protection_mismatches` for ENV, JOB, VAR, EXTATTR |
| `CHANGELOG.md` | Added 0.21.1 entry |
| `dev_support/importer_implementation_status.md` | Version bump + change log entry |
| `dev_support/phase5_e2e_testing_guide.md` | Version bump |

## Upgrade Notes

- No breaking changes
- No configuration changes required
- Protection moves from v0.21.0 are fully compatible

## Testing Verification

Verified end-to-end via browser:
1. Protected an environment variable (`DBT_ENVIRONMENT_NAME` for `sse_dm_fin_fido`)
2. Generated protection changes — detected 5 mismatches (REP, PREP, VAR + ENV QA + JOB)
3. Plan showed **"3 to move, 0 to add, 0 to change, 0 to destroy"** — all resources correctly moved from unprotected to protected blocks
4. Previously this plan failed with "Moved resource instances excluded by targeting"
