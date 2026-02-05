# PRD: Grid Standardization and Theme Migration

## Overview

Standardize all AG Grid implementations across the web UI to use the `quartz` theme and provide consistent features including selection, filtering, search, export to CSV, and detail popups. Ensure all grids work correctly in both light and dark modes.

## Reference

**All implementations MUST follow the comprehensive AG Grid standards defined in:**

`.cursor/rules/ag-grid-standards.mdc`

This rule contains:
- Critical MUST DO / MUST NOT rules
- Required standard features
- Column definition patterns (colId, boolean handling)
- Layout and container patterns (CSS Grid for sizing)
- Selection patterns (AG Grid v32+ API)
- Event handling patterns
- Dialog patterns with sizing standards
- Styling patterns with dark mode CSS
- Troubleshooting guide

## Current State

Grid implementations have inconsistent themes and feature coverage:

| Grid | Theme | Selection | Filter | Export | Pagination | Inline Edit |
|------|-------|-----------|--------|--------|------------|-------------|
| `match_grid.py` | balham | ❌ | ✅ | ✅ | ❌ | ✅ |
| `entity_table.py` | quartz | ✅ (single) | ✅ | ✅ | ✅ | ❌ |
| `destroy.py` | quartz | ❌ (checkbox col) | ✅ | ❌ | ❌ | ✅ (checkbox) |
| `mapping.py` | quartz | ❌ (checkbox col) | ✅ | ❌ | ✅ | ✅ (checkbox) |
| `scope.py` | quartz | ❌ (checkbox col) | ✅ | ❌ | ✅ | ✅ (checkbox) |
| `job_grid.py` | default | ✅ (multi) | ✅ | ❌ | ❌ | ✅ |

### Issues

1. **Theme inconsistency**: `match_grid.py` uses `balham`, `job_grid.py` uses default theme
2. **Export missing**: Only 2 of 6 grids have CSV export
3. **Selection inconsistency**: Mix of row selection vs checkbox columns
4. **Dark mode**: Manual CSS overrides needed for non-quartz themes

## Target State

All grids use:
- `theme="quartz"` for automatic dark/light mode support
- Consistent feature set based on grid purpose (read-only vs editable)
- Standard patterns from `.cursor/rules/ag-grid-standards.mdc`

## Proposed Changes

### 1. Migrate `match_grid.py` to Quartz Theme

**File:** `importer/web/components/match_grid.py`

**Changes:**
- Change `theme="balham"` to `theme="quartz"` (line ~1189)
- Remove manual dark mode CSS overrides for `.ag-theme-balham` (lines ~1376-1410)
- Test all custom cell styling (action colors, drift status badges) with quartz theme
- Adjust CSS variables if needed for quartz compatibility

**Risk:** Custom cell styling may need adjustment. The balham theme's styling hooks differ from quartz.

### 2. Migrate `job_grid.py` to Quartz Theme

**File:** `importer/web/workflows/jobs_as_code/components/job_grid.py`

**Changes:**
- Add `theme="quartz"` to `ui.aggrid()` call
- Verify dark mode appearance

### 3. Add Export to CSV to All Grids

Add export button to grids that don't have it:
- `destroy.py`
- `mapping.py`
- `scope.py`
- `job_grid.py`

**Implementation:** See "Export to CSV" section in `.cursor/rules/ag-grid-standards.mdc`

### 4. Standardize Selection Patterns

**For read-only/select-only grids** (entity_table pattern):
- Use AG Grid v32+ row selection API
- Handle `selectionChanged` event
- Remove custom `_selected` checkbox columns where appropriate

**For editable grids** (match_grid, job_grid):
- Keep inline editing patterns
- Use `cellValueChanged` for edit handling

**Implementation:** See "Selection Patterns" section in `.cursor/rules/ag-grid-standards.mdc`

### 5. Add Quick Filter/Search to All Grids

Ensure all grids have a search input.

**Implementation:** See "Search/Quick Filter" section in `.cursor/rules/ag-grid-standards.mdc`

### 6. Add Detail Popup Support

For grids without detail popups, add row click handler with proper dialog sizing.

**Implementation:** See "Dialog Patterns" section in `.cursor/rules/ag-grid-standards.mdc`

Standard dialog sizes:
- **Detail/Large:** `max-w-6xl`, `height: 80vh;`, content scroll `55vh`
- **Config/Picker:** `min-w-[400px] max-h-[80vh]`, content scroll `max-height: 400px`
- **Maximized:** `dialog.props("maximized")`

---

## User Stories

### US-1: Consistent Visual Theme Across All Grids
**As a** user of the web UI  
**I want** all data grids to have the same visual appearance  
**So that** the application feels cohesive and professional

**Acceptance Criteria:**
- All grids use the quartz theme
- Visual styling is consistent across all grid pages
- No jarring visual differences when navigating between pages

### US-2: Dark Mode Support for All Grids
**As a** user who prefers dark mode  
**I want** all grids to automatically adapt to dark mode  
**So that** I can use the application comfortably in low-light environments

**Acceptance Criteria:**
- All grids respond to system/browser dark mode preference
- All grids respond to application dark mode toggle
- Text remains readable in both light and dark modes
- Custom cell styling (colors, badges) works in both modes
- No manual CSS overrides required for dark mode

### US-3: Export Data to CSV from Any Grid
**As a** user viewing data in a grid  
**I want** to export the current data to CSV  
**So that** I can analyze it in spreadsheets or share with others

**Acceptance Criteria:**
- Export button available on all grids
- Exports currently filtered/visible data
- CSV includes all visible columns
- Filename is descriptive (includes resource type/context)
- Export works in both light and dark modes

### US-4: Search/Filter Data in All Grids
**As a** user looking for specific items  
**I want** to quickly search and filter grid data  
**So that** I can find what I need without scrolling

**Acceptance Criteria:**
- Search input available above all grids
- Search filters across all text columns
- Search is case-insensitive
- Results update as I type
- Clear button to reset search

### US-5: Column Filtering on All Grids
**As a** user analyzing data  
**I want** to filter individual columns  
**So that** I can focus on specific subsets of data

**Acceptance Criteria:**
- Filter icon appears on column headers
- Click opens filter menu
- Support for text contains, equals, etc.
- Multiple column filters combine (AND logic)
- Filters can be cleared individually or all at once

### US-6: Sortable Columns on All Grids
**As a** user viewing tabular data  
**I want** to sort by any column  
**So that** I can organize data in meaningful ways

**Acceptance Criteria:**
- Click column header to sort ascending
- Click again to sort descending
- Click again to clear sort
- Sort indicator shows current sort state
- Multi-column sort supported (shift+click)

### US-7: Row Selection for Read-Only Grids
**As a** user selecting items from a grid  
**I want** consistent row selection behavior  
**So that** I know how to select items across all pages

**Acceptance Criteria:**
- Click row to select (for single-select grids)
- Checkbox column for multi-select grids
- Selected rows visually highlighted
- Selection persists during filtering/sorting
- Clear selection button available

### US-8: Detail Popup on Row Click
**As a** user viewing summarized data  
**I want** to click a row to see full details  
**So that** I can inspect items without leaving the page

**Acceptance Criteria:**
- Clicking a row opens a detail popup/dialog
- Popup shows all available fields for the item
- Popup can be dismissed with Escape or close button
- Popup doesn't interfere with row selection (if both needed)

### US-9: Resizable Columns on All Grids
**As a** user viewing grids with varying content lengths  
**I want** to resize columns  
**So that** I can see full content or make room for other columns

**Acceptance Criteria:**
- Drag column borders to resize
- Double-click border to auto-fit content
- Column widths persist during session
- Minimum column width prevents columns from disappearing

### US-10: Inline Editing Where Appropriate
**As a** user modifying data directly in grids  
**I want** inline editing capabilities  
**So that** I can make changes efficiently without separate forms

**Acceptance Criteria:**
- Editable cells clearly indicated (if applicable)
- Single-click or double-click to enter edit mode (consistent)
- Changes saved on blur or Enter
- Validation feedback for invalid input
- Undo capability for accidental changes

---

## Test Plan

### Prerequisites
1. Server running at `http://localhost:8082`
2. Valid `.env` credentials loaded
3. Test data available (source and target accounts with resources)

### Dark/Light Mode Testing

For EACH grid page, test in both modes:

#### TC-THEME-01: Light Mode Appearance
**Steps:**
1. Ensure system/browser is in light mode
2. Navigate to grid page
3. Take screenshot
4. Verify text is readable
5. Verify custom styling (badges, colors) is visible

**Expected:** Grid renders correctly with readable text and visible styling

#### TC-THEME-02: Dark Mode Appearance
**Steps:**
1. Toggle to dark mode (system preference or app toggle)
2. Navigate to grid page
3. Take screenshot
4. Verify text is readable (light text on dark background)
5. Verify custom styling adapts appropriately

**Expected:** Grid automatically adapts to dark mode

#### TC-THEME-03: Mode Toggle While Viewing
**Steps:**
1. Open grid page in light mode
2. Toggle to dark mode
3. Verify grid updates without refresh

**Expected:** Grid theme changes dynamically

### Feature Testing (Per Grid)

#### TC-FEAT-01: Quick Filter/Search
**Steps:**
1. Load grid with multiple rows
2. Type partial text in search input
3. Verify rows filter to matches
4. Clear search
5. Verify all rows return

**Expected:** Search filters and clears correctly

#### TC-FEAT-02: Column Filter
**Steps:**
1. Click filter icon on a column
2. Enter filter criteria
3. Verify rows filter
4. Clear filter

**Expected:** Column filters work

#### TC-FEAT-03: Column Sort
**Steps:**
1. Click column header
2. Verify ascending sort
3. Click again
4. Verify descending sort
5. Click again
6. Verify sort cleared

**Expected:** Sorting cycles through states

#### TC-FEAT-04: Export to CSV
**Steps:**
1. Apply a filter to show subset
2. Click Export CSV button
3. Verify file downloads
4. Open CSV and verify:
   - Contains only filtered rows
   - All visible columns present
   - Data matches grid display

**Expected:** CSV export includes filtered data

#### TC-FEAT-05: Row Selection (read-only grids)
**Steps:**
1. Click a row
2. Verify row highlights
3. Click another row
4. Verify selection moves (single-select) or adds (multi-select)

**Expected:** Selection works as designed

#### TC-FEAT-06: Detail Popup
**Steps:**
1. Click a row
2. Verify detail popup opens
3. Verify popup contains row data
4. Press Escape
5. Verify popup closes

**Expected:** Detail popup works

#### TC-FEAT-07: Column Resize
**Steps:**
1. Hover between two column headers
2. Drag to resize
3. Verify column width changes
4. Double-click border
5. Verify auto-fit to content

**Expected:** Columns resize correctly

### Grid-Specific Tests

#### Match Grid (`/match`)
- TC-MATCH-01: Quartz theme renders correctly
- TC-MATCH-02: Action dropdown still editable
- TC-MATCH-03: Target ID field still editable
- TC-MATCH-04: Protected checkbox still works
- TC-MATCH-05: Drift status badges visible in both modes
- TC-MATCH-06: Confidence badges visible in both modes

#### Entity Browser (`/explore`)
- TC-ENT-01: Single row selection works
- TC-ENT-02: Pagination controls work
- TC-ENT-03: Type filter dropdown works
- TC-ENT-04: Detail panel updates on selection

#### Destroy Page (`/destroy`)
- TC-DEST-01: Protected resources grid has export
- TC-DEST-02: Destroy resources grid has export
- TC-DEST-03: Selection works for both grids

#### Mapping Page (`/mapping`)
- TC-MAP-01: Checkbox selection works
- TC-MAP-02: Export CSV added and works
- TC-MAP-03: Pagination works with large datasets

#### Scope Page (`/scope`)
- TC-SCOPE-01: Checkbox selection works
- TC-SCOPE-02: Export CSV added and works
- TC-SCOPE-03: Resource counts accurate

#### Jobs as Code Grid
- TC-JAC-01: Quartz theme renders correctly
- TC-JAC-02: Multi-row selection works
- TC-JAC-03: Identifier editing still works
- TC-JAC-04: Export CSV added and works

---

## Implementation Order

1. **Phase 1: Theme Migration**
   - Migrate `match_grid.py` to quartz (highest risk, most complex)
   - Migrate `job_grid.py` to quartz
   - Add explicit `colId` to all columns (prevent phantom column bug)
   - Pre-sort data in Python, set `animateRows: False`
   - Test dark/light mode for all grids

2. **Phase 2: Export Feature**
   - Add export to `destroy.py`
   - Add export to `mapping.py`
   - Add export to `scope.py`
   - Add export to `job_grid.py`

3. **Phase 3: Selection Standardization**
   - Migrate to AG Grid v32+ row selection API
   - Remove deprecated `checkboxSelection` column properties
   - Audit checkbox columns vs row selection
   - Standardize patterns per grid purpose

4. **Phase 4: Detail Popups**
   - Add detail popups where missing
   - Standardize popup sizing per rule (80vh detail, 400px config)
   - Ensure close buttons on all dialogs

5. **Phase 5: Cleanup**
   - Delete `dev_support/AGGRID_NICEGUI_PATTERNS.md` (superseded by `.cursor/rules/ag-grid-standards.mdc`)
   - Verify all grids follow the rule

---

## Files to Modify

1. `importer/web/components/match_grid.py` - Theme migration, CSS cleanup, add colId
2. `importer/web/components/entity_table.py` - Verify compliance (already quartz)
3. `importer/web/pages/destroy.py` - Add export, verify colId
4. `importer/web/pages/mapping.py` - Add export, verify colId
5. `importer/web/pages/scope.py` - Add export, verify colId
6. `importer/web/workflows/jobs_as_code/components/job_grid.py` - Theme, export, colId
7. `importer/web/workflows/jobs_as_code/pages/jobs.py` - Verify/update grid usage

## Files to Delete

1. `dev_support/AGGRID_NICEGUI_PATTERNS.md` - Superseded by `.cursor/rules/ag-grid-standards.mdc`

---

## Success Criteria

- [ ] All grids use `theme="quartz"`
- [ ] All grids work in light mode
- [ ] All grids work in dark mode
- [ ] All grids have Export CSV button
- [ ] All grids have search/quick filter
- [ ] All grids have column filtering
- [ ] All grids have column sorting
- [ ] All grids have column resizing
- [ ] All grids have explicit `colId` on every column
- [ ] All grids pre-sort data in Python (no AG Grid default sort)
- [ ] All grids use `animateRows: False` for stability
- [ ] Selection patterns use AG Grid v32+ API (no deprecated `checkboxSelection`)
- [ ] Detail dialogs follow standard sizing (see rule)
- [ ] No manual dark mode CSS overrides required
- [ ] `dev_support/AGGRID_NICEGUI_PATTERNS.md` deleted (superseded by rule)
