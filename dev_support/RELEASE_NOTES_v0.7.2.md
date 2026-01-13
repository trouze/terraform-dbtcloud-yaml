# Release Notes: v0.7.2

**Release Date:** 2026-01-13  
**Release Type:** Patch  
**Previous Version:** 0.7.1

---

## Summary

This patch release rebrands the Web UI to "dbt Magellan: Exploration & Migration Tool" and fixes several layout and UX issues in the Explore step.

---

## Changes

### Web UI Rebrand

The application has been renamed from "Account Migration Tool" to **dbt Magellan: Exploration & Migration Tool**:
- Updated sidebar title and subtitle
- Updated page titles and welcome section
- Updated CLI description and argparse help text

### Home Page Messaging

Updated the home page to emphasize both exploration and migration use cases:
- New description: "Explore, audit, and migrate dbt Platform account configurations"
- Added note: "Use steps 1-2 for account exploration and auditing, or complete all steps for full migration"
- Changed primary button from "Start New Migration" to "Get Started"

### Explore Tab Enhancements

#### Entity Type Sort Order
Entity types now have two-digit sort-order prefixes for logical grouping:
- `00-ACC` Account (global)
- `10-CON` Connection, `11-REP` Repository, `12-TOK` Service Token, etc. (global resources)
- `30-PRJ` Project
- `40-ENV` Environment, `41-VAR` Environment Variable (project-scoped)
- `50-JOB` Job

This allows room for future additions while keeping related types grouped together.

#### Default Sort Order
The entities table now sorts by default: **Project → Type → Name** (all ascending), making it easier to navigate large accounts.

#### Column Visibility
Users can now select which columns are visible in the entities table. Preferences are persisted across sessions via user storage.

#### Enhanced Entity Detail Dialog
Clicking an entity now opens a detail dialog with four tabs:
1. **Overview** - Key info chips and properties
2. **Details** - Expandable outline view of the entity structure
3. **JSON (Summary)** - The simplified report item JSON
4. **JSON (Full)** - Complete entity data from the API snapshot

### Layout Fixes

Fixed CSS grid layout issues in the Explore page:
- Summary, Report, Entities, and Charts tab panels now fill available width
- AGGrid table now fills available vertical space
- Proper `width: 100%` propagation through component hierarchy

### UX Improvements

- **File Upload for .env**: Added file dialog for loading .env files with a tooltip about macOS hidden files (⌘+Shift+.)
- **Fetch Panel Clearing**: The "Fetch Complete" results panel now clears when starting a new fetch or loading a new .env file

---

## Files Changed

### Web UI
- `importer/web/__init__.py` - Updated docstring
- `importer/web/__main__.py` - Updated CLI description
- `importer/web/app.py` - Updated app title
- `importer/web/components/stepper.py` - Updated sidebar branding
- `importer/web/pages/home.py` - Updated welcome section
- `importer/web/pages/explore.py` - Fixed CSS grid layout, added `width: 100%`
- `importer/web/pages/fetch.py` - Added file upload handler, panel clearing
- `importer/web/components/entity_table.py` - Type prefixes, sort order, column visibility, detail dialog
- `importer/web/components/credential_form.py` - File upload with tooltip
- `importer/web/env_manager.py` - Added content-based credential loading
- `importer/web/state.py` - Added `ExploreState.visible_columns` with persistence

---

## Upgrade Notes

No breaking changes. The version increment is automatic when reading from `importer/VERSION`.

---

## Verification

```bash
# Check version
cat importer/VERSION
# Expected: 0.7.2

# Check web UI version display
python -m importer.web --no-open &
# Version should appear in sidebar below "Exploration & Migration Tool"

# Verify CLI help
python -m importer.web --help
# Description should show "dbt Magellan: Exploration & Migration Tool"
```
