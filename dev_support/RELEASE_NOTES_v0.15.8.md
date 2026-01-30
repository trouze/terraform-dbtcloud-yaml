# Release Notes v0.15.8

**Release Date:** 2026-01-30  
**Type:** Patch Release (Bug Fix)

---

## Summary

This patch release fixes a critical bug where adoption overrides were not being applied during the Generate step, causing Terraform plans to show unnecessary resource replacements for adopted repositories.

---

## Bug Fixes

### Adoption Override Data Flow Fix

**Problem:** When adopting existing target resources (e.g., repositories), the YAML configuration was not being updated with target account values (`remote_url`, `git_clone_strategy`). This caused Terraform plans to show resource replacement actions, even when the resources should be adopted without changes.

**Root Cause:** 
1. The `confirmed_mappings` in `match.py` was not storing the `action` field when mappings were created
2. `deploy.py` was filtering for `action == "adopt"` to determine which resources needed adoption overrides
3. Since `action` was never stored, the filter always returned an empty list, and adoption overrides were never applied

**Fix Applied:**
1. Updated `auto_match_all()` in `match.py` to:
   - Include both "match" and "adopt" actions (both represent mapping to existing target resources)
   - Store the `action` field in the mapping dictionary
   
2. Updated `on_accept()` in `match.py` to:
   - Include the `action` field when storing accepted mappings

3. Updated `deploy.py` to:
   - Accept `action` of "match", "adopt", or `None` (for backward compatibility with existing mappings)

**Result:** Repository `remote_url` and `git_clone_strategy` now correctly inherit target account values during adoption, resulting in clean `Plan: 0 to add, 0 to change, 0 to destroy` outputs for properly matched resources.

---

## Files Changed

- `importer/web/pages/match.py` - Store action field in confirmed_mappings, include both match and adopt actions
- `importer/web/pages/deploy.py` - Accept match, adopt, or None actions for backward compatibility

---

## Testing Performed

1. Verified adoption override data flow with debug instrumentation
2. Confirmed `apply_adoption_overrides()` is now called with correct data
3. Verified Terraform plan shows only `moved` blocks for protected resources (no replacements)
4. Tested with `dbt_ep_sse_dm_fin_fido` repository - confirmed target `remote_url` and `git_clone_strategy` are applied

---

## Upgrade Notes

- No breaking changes
- Existing mappings without `action` field will continue to work (backward compatible)
- Users experiencing adoption issues should:
  1. Go to Match Resources page
  2. Click "Accept All Pending" to repopulate mappings with the action field
  3. Go to Deploy page and click "Generate"

---

## Known Issues

None introduced by this release.

---

## Related Issues

- Fixes repository adoption causing `lifecycle.prevent_destroy` errors
- Fixes `remote_url` and `git_clone_strategy` not being updated from target values
