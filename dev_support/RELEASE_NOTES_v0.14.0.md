# Release Notes - v0.14.0

**Release Date:** 2026-01-28  
**Release Type:** Minor (New Feature)  
**Previous Version:** 0.13.1

---

## Summary

Version 0.14.0 introduces **Resource Protection with Cascade**, a comprehensive system for protecting Terraform-managed resources from accidental destruction. Users can now mark any resource as protected directly from the Match Existing grid, with intelligent cascade logic that automatically protects parent resources in the hierarchy.

---

## New Features

### Resource Protection Grid Column

A new protection checkbox column (🛡️) has been added to the Match Existing grid:

- **Visual Indicator**: Shield icon shows protected status at a glance
- **One-Click Toggle**: Click to protect/unprotect any resource
- **Protected Row Styling**: Blue left border and subtle blue background highlight protected rows
- **Tooltip**: Hover explains that protection adds `lifecycle.prevent_destroy` to Terraform

### Cascade Protection

When protecting a child resource, the system automatically protects its parent hierarchy:

| Resource Type | Parent Chain |
|---------------|--------------|
| Job | Environment → Project |
| Credential | Environment → Project |
| Environment | Project |
| Env Variable | Project |
| Repository (project-linked) | Project |
| Repository (orphan) | (none) |
| Connection | (none) |
| Project | (none) |

**Behavior:**
- **Protecting a child**: Shows confirmation dialog listing parent resources to be protected
- **Confirming cascade**: All resources (child + parents) are marked protected
- **Canceling**: No changes made

### Unprotection Cascade

When unprotecting a parent with protected children:

- **Dialog prompt**: "Would you like to unprotect the children as well?"
- **Unprotect All**: Removes protection from parent and all protected descendants
- **Unprotect This Only**: Removes protection only from the parent; children stay protected

### State Persistence

- `protected_resources` set added to `MapState` for session persistence
- Protection status survives page reloads
- Protection flags applied to YAML during Terraform file generation

---

## Technical Implementation

### New Files

| File | Description |
|------|-------------|
| `importer/web/utils/protection_manager.py` | Cascade protection helper functions |

### Modified Files

| File | Changes |
|------|---------|
| `importer/web/state.py` | Added `protected_resources: set` to `MapState` |
| `importer/web/components/match_grid.py` | Added protection column, row styling, cascade handling |
| `importer/web/pages/match.py` | Added cascade dialogs, protection toggle logic |
| `importer/web/utils/adoption_yaml_updater.py` | Added `apply_protection_from_set()` |
| `importer/web/pages/deploy.py` | Apply protection from set during generation |
| `tasks/prd-web-ui-09-resource-protection.md` | Added cascade protection user stories and tests |

### Key Functions

```python
# protection_manager.py
get_resources_to_protect(source_key, hierarchy_index, source_items, already_protected)
get_resources_to_unprotect(source_key, hierarchy_index, source_items, protected_resources)

# adoption_yaml_updater.py
apply_protection_from_set(yaml_file, protected_keys, output_path)
```

---

## User Stories Added

| ID | Story |
|----|-------|
| US-RP-70 | Mark any resource as protected in the match grid |
| US-RP-71 | Protecting a child auto-protects its parents |
| US-RP-72 | Confirmation dialog lists parent resources to protect |
| US-RP-73 | Confirm or cancel the cascade protection |
| US-RP-74 | Protected rows highlighted in the grid |
| US-RP-75 | Unprotect a parent with protected children |
| US-RP-76 | Cascade unprotect to all children |
| US-RP-77 | Unprotect only the parent (not children) |
| US-RP-78 | Credentials cascade to ENV → PRJ |
| US-RP-79 | Env variables cascade to PRJ |
| US-RP-80 | Project-linked repos cascade to PRJ |

---

## Test Cases Added

18 new test cases for cascade protection (CP-RP-01 through CP-RP-18):

- Cascade dialog behavior for each resource type
- Confirm/cancel actions
- Protected row styling
- `get_resources_to_protect()` and `get_resources_to_unprotect()` functions
- Edge cases (parent already protected, etc.)

---

## Breaking Changes

None. This release is fully backward-compatible.

---

## Migration Guide

No migration required. Existing configurations will continue to work. Resources are unprotected by default.

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
# Expected: 0.14.0

# Verify import
python3 -c "from importer import get_version; print(get_version())"
# Expected: 0.14.0
```

---

**Full Changelog:** See [CHANGELOG.md](../CHANGELOG.md)  
**PRD:** See [prd-web-ui-09-resource-protection.md](../tasks/prd-web-ui-09-resource-protection.md)
