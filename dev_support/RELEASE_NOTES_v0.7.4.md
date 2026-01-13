# Release Notes v0.7.4

**Release Date:** 2026-01-13  
**Type:** Patch Release  
**Focus:** Map Page Filter Persistence

---

## Summary

This patch release adds filter state persistence to the Map page in the Web UI. Previously, toggling light/dark mode, clicking "Normalize Selected Entities", or refreshing the page would reset the type filter and "Selected Only" toggle. Now these filter states are persisted in the session storage and survive page reloads.

---

## Changes

### Added

- **Map Page Filter Persistence**
  - Type filter selection now persists across page reloads
  - "Selected Only" toggle state now persists across page reloads
  - Filters survive theme toggles (light/dark mode switch)
  - Filters survive normalization operation (which triggers page reload)

### Fixed

- **Map Page Visual State**
  - "Selected Only" button correctly shows highlighted (orange) state on page load when filter was previously active
  - Grid correctly applies persisted filters on initial render

---

## Technical Details

### State Model Updates

Added two new fields to `MapState` dataclass:
- `type_filter: str = "all"` - Stores selected entity type filter
- `selected_only_filter: bool = False` - Stores whether "Selected Only" is active

### Persistence Flow

1. When user changes type filter → `state.map.type_filter` updated → `save_state()` called
2. When user toggles "Selected Only" → `state.map.selected_only_filter` updated → `save_state()` called
3. On page load → filter values restored from `state.map.*` → grid filtered accordingly
4. Button styling applied based on persisted state

---

## Upgrade Notes

No breaking changes. This is a backwards-compatible enhancement.

---

## Files Modified

- `importer/web/state.py` - Added `type_filter` and `selected_only_filter` fields to `MapState`
- `importer/web/pages/mapping.py` - Implemented filter persistence and restoration logic
- `importer/VERSION` - Bumped to 0.7.4
- `CHANGELOG.md` - Added 0.7.4 section
- `dev_support/importer_implementation_status.md` - Updated version and changelog
- `dev_support/phase5_e2e_testing_guide.md` - Updated importer version

---

**Previous Version:** [0.7.3](RELEASE_NOTES_v0.7.3.md)
