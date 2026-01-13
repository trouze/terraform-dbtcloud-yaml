# Release Notes - v0.7.5

**Release Date:** 2026-01-13  
**Type:** Patch Release  
**Focus:** Scope Settings, Resource Filters, Repository-Project Linking

---

## Summary

This release makes Scope Settings and Resource Filters fully functional in the Map step, fixing multiple issues that prevented these UI controls from affecting the generated target configuration. Additionally, repositories are now properly linked to their parent projects throughout the UI.

---

## What's New

### Map Page: Scope Settings Functional
- **All Projects**: Include all projects (default)
- **Specific Projects**: Filter to selected projects only
- **Account Only**: Include only global resources (connections, tokens, etc.)

### Map Page: Resource Filters Functional
- Toggle entity types on/off for target config generation
- Disabled types are excluded from the generated YAML

### Map Page: Selection Summary Enhanced
- Shows "Effective (after filters)" count when filters reduce selection
- Per-type breakdown shows strikethrough on filtered counts
- Filter impact breakdown (scope: -X, resource: -Y)

### Map Page: Reset Filters Button
- Resets to "All Types" with "Selected Only" off
- Does not change entity selections

### Repositories Linked to Projects
- Repositories now show their parent project in the Project column
- "Select Children" on a project includes its repository
- Scope filtering properly includes/excludes repositories

---

## Bug Fixes

### Auto-cascade Timing Bug
- **Problem**: Clicking a checkbox while confirmation dialog was open didn't cascade
- **Fix**: State now updates immediately when toggle clicked, reverts if cancelled

### Parent-child Selection Logic
- **Problem**: "Select Children" on Account selected everything
- **Fix**: Account entity excluded from cascade operations

### Normalizer exclude_ids Support
- **Problem**: Resource filters didn't affect generated YAML
- **Fix**: Added `exclude_ids` filtering to:
  - `_normalize_environment_variables`
  - `_normalize_environments`
  - `_normalize_jobs`

### Resource Filter Key Mismatch
- **Problem**: Some filters used wrong keys (`privatelinks` vs `privatelink_endpoints`)
- **Fix**: Aligned all filter keys between UI and backend

### Pydantic Model Extra Fields
- **Problem**: `element_mapping_id` stripped when loading JSON into models
- **Fix**: Added `extra='allow'` to `ImporterBaseModel`

---

## Technical Details

### Files Changed
- `importer/web/pages/mapping.py` - Scope/resource filter logic, auto-cascade fix
- `importer/normalizer/core.py` - Added exclude_ids to normalizer functions
- `importer/models.py` - Added `extra='allow'` to Pydantic config
- `importer/element_ids.py` - Repository-project linking via metadata.project_id
- `importer/web/components/hierarchy_index.py` - Repositories as project children
- `importer/web/components/entity_table.py` - Repository project_name population

### New Helper Function
- `_get_effective_selection()` - Computes effective selection after applying scope and resource filters

---

## Upgrade Notes

- No breaking changes
- Re-fetch recommended to pick up repository-project linking in report_items
- Existing selections are preserved

---

## Testing Checklist

- [ ] Scope Settings: "Specific Projects" excludes other projects from YAML
- [ ] Scope Settings: "Account Only" excludes all project-level items
- [ ] Resource Filters: Toggling off Jobs excludes jobs from YAML
- [ ] Selection Summary: Shows effective count when filters active
- [ ] Auto-cascade: Selecting project auto-selects children when toggle ON
- [ ] Repositories: Show project name in both Explore and Map tables
