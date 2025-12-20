# Release Notes: v0.4.4

**Release Date:** 2025-12-20  
**Type:** Patch Release (Critical Bug Fixes)  
**Status:** ✅ Ready for Use

---

## Overview

Version 0.4.4 fixes **critical type consistency issues** that were preventing Terraform plan/apply from succeeding. This release filters deleted resources at fetch time and normalizes permission object structures to ensure consistent types throughout the pipeline.

### Key Fixes

- **Filter Deleted Resources**: Deleted resources (state=2) no longer enter the snapshot
- **Consistent Permission Types**: All permission objects have identical structure
- **Eliminates Type Errors**: Fixes "all list elements must have the same type" Terraform errors
- **Cleaner Exports**: JSON exports no longer include deleted resources

---

## What's Fixed

### 1. Filter Deleted Resources at Fetch Time

**Problem Solved:**  
Deleted resources (service tokens and notifications with `state: 2`) were being fetched and included in the snapshot. These deleted resources often had incomplete or missing fields (e.g., empty `service_token_permissions`, missing `group_permissions`), causing Terraform to fail with "all list elements must have the same type" errors.

**Solution:**  
Added filtering logic in the fetch phase to skip deleted resources before they enter the snapshot.

**Technical Changes:**
- **File:** `importer/fetcher.py`
- **New Function:** `_should_include_resource(item: Dict[str, Any]) -> bool`
  - Returns `False` if `item.get("state") == 2`
  - Returns `True` otherwise
- **Applied to:**
  - `_fetch_service_tokens()`: Skips tokens with `state: 2` (logs debug message)
  - `_fetch_notifications()`: Skips notifications with `state: 2` (logs debug message)

**User Impact:**
- ✅ **No more type errors** from deleted resources
- ✅ **Cleaner JSON exports** (only active resources included)
- ✅ **Smaller export files** (deleted resources excluded)
- ✅ **Better element IDs** (deleted resources not in line items)

**Example:**
```python
# Before: 17 service tokens (2 deleted with state=2)
# After:  15 service tokens (deleted ones filtered out)
```

**Breaking Change:**
- JSON exports from v0.4.4+ will **not** include deleted resources
- This is intentional - deleted resources shouldn't be migrated anyway
- Normalization remains backwards compatible (handles missing fields gracefully)

---

### 2. Normalize Permission Object Structures

**Problem Solved:**  
Permission objects (for service tokens and groups) had inconsistent structures:
- Some had `project_id` field, others didn't
- Some had `writable_environment_categories` field, others didn't
- This created different tuple types in Terraform, causing "all list elements must have the same type" errors

**Solution:**  
Normalizer now always includes all fields, using `null` or empty list as defaults when values aren't present.

**Technical Changes:**
- **File:** `importer/normalizer/core.py`
- **Service Token Permissions** (lines 339-351):
  - Always includes `project_id` (null if `all_projects=True`)
  - Always includes `writable_environment_categories` (empty list if not present)
- **Group Permissions** (lines 400-410):
  - Always includes `project_id` (null if `all_projects=True`)
  - Always includes `writable_environment_categories` (empty list if not present)

**Before:**
```yaml
service_token_permissions:
  - permission_set: "member"
    all_projects: true
  # Missing project_id and writable_environment_categories
```

**After:**
```yaml
service_token_permissions:
  - permission_set: "member"
    all_projects: true
    project_id: null
    writable_environment_categories: []
```

**User Impact:**
- ✅ **Consistent types** across all permission objects
- ✅ **Terraform validation passes** without type errors
- ✅ **Terraform plan succeeds** without type mismatches

---

## Testing & Verification

### E2E Test Results

**Filtering Verification:**
```bash
# Before filtering: 2 deleted tokens (state=2) in export
# After filtering:  0 deleted tokens in export
grep -c '"state": 2' export.json
# Result: 0
```

**Type Consistency Verification:**
- ✅ All service token permissions have identical structure
- ✅ All group permissions have identical structure
- ✅ Terraform validation passes
- ✅ No "inconsistent type" errors

### Test Account Results

- **Service Tokens:** 17 total → 15 after filtering (2 deleted removed)
- **Notifications:** 14 total → 14 after filtering (none deleted in test account)
- **Groups:** 5 total (all active, no filtering needed)
- **Projects:** 17 total (all active)

---

## Upgrade Instructions

### For Users

1. **Update Importer:**
   ```bash
   git pull origin main
   # Or update your installation method
   ```

2. **Re-fetch if Needed:**
   - If you have existing JSON exports from v0.4.0-0.4.3, they will still normalize correctly
   - New fetches from v0.4.4+ will exclude deleted resources automatically
   - No manual filtering needed

3. **No Configuration Changes:**
   - Filtering happens automatically
   - No new environment variables or settings

### For Developers

- Review `importer/fetcher.py` for the new filtering logic
- Review `importer/normalizer/core.py` for permission normalization changes
- Test with accounts that have deleted resources to verify filtering

---

## Technical Details

### Why Filter at Fetch?

**Alternative Considered:** Filter in normalizer  
**Why Rejected:** Filtering at fetch is cleaner because:
- Deleted resources never enter the snapshot
- Smaller export files
- Element IDs/line items don't include deleted resources
- Simpler data model throughout the pipeline

### Type Consistency Strategy

Terraform's strict type system requires all elements in a list to have identical structure. By always including optional fields (with null/empty defaults), we ensure:
- Consistent tuple types across all permission objects
- No conditional type mismatches
- Predictable Terraform behavior

---

## Known Limitations

- **Groups:** State field exists in API metadata but isn't promoted to top-level, so no filtering needed
- **PrivateLinkEndpoint:** Uses string state values ("active", "creating"), not int, so not affected by this change
- **Backwards Compatibility:** JSON exports from v0.4.4+ differ from v0.4.0-0.4.3 (deleted resources excluded)

---

## Next Steps

After upgrading to v0.4.4:
1. Run a fresh fetch to get clean exports without deleted resources
2. Verify Terraform validation and plan succeed
3. Report any remaining type errors (should be resolved)

---

## Related Issues

- Fixes type inconsistency errors preventing Terraform plan/apply
- Resolves "all list elements must have the same type" errors
- Eliminates need for defensive field defaulting in Terraform modules

---

**For questions or issues, please refer to:**
- [Implementation Status](importer_implementation_status.md)
- [E2E Testing Guide](phase5_e2e_testing_guide.md)
- [Version Update Checklist](VERSION_UPDATE_CHECKLIST.md)

