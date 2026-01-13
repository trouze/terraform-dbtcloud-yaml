# PRD: Web UI - Part 3: Explore Step

## Introduction

The Explore step of the dbt Cloud Importer Web UI. This provides rich data exploration capabilities including summary reports, filterable entity tables, visualizations, and CSV export functionality.

This is **Part 3 of 5** in the Web UI PRD series.  
**Depends on:** Part 1 (Core Shell), Part 2 (Fetch)

## Goals

- Display fetched account data in multiple complementary views
- Provide powerful filtering and searching across all entities
- Visualize resource distribution with interactive charts
- Enable CSV export for external analysis

## User Stories

### US-015: View Summary Report
**Description:** As a user, I want to see a high-level summary of my fetched account so that I understand the scope of the migration.

**Acceptance Criteria:**
- [ ] Summary tab displays rendered markdown from `*__summary__*.md`
- [ ] Shows account name and ID prominently
- [ ] Global resource counts: connections, repositories, service tokens, groups
- [ ] Per-project breakdown with environment/job counts
- [ ] Summary auto-updates when new fetch is performed
- [ ] "Refresh" button reloads from file if edited externally
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-016: View Detailed Report
**Description:** As a user, I want to see the detailed hierarchical report so that I can understand resource relationships.

**Acceptance Criteria:**
- [ ] Report tab displays rendered markdown from `*__report__*.md`
- [ ] Hierarchical structure visible (Account → Projects → Environments → Jobs)
- [ ] IDs and keys shown for each resource
- [ ] Collapsible sections for large reports
- [ ] Search within report content
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-017: Browse Entities in Data Table
**Description:** As a user, I want to browse all fetched entities in a filterable table so that I can find and review specific resources.

**Acceptance Criteria:**
- [ ] Entities tab shows AGGrid table with all `report_items`
- [ ] Columns: Type, Name, Key, dbt ID, Include, Line Item #
- [ ] Column headers clickable for sorting (asc/desc)
- [ ] Filter icon on each column header for column-specific filtering
- [ ] Pagination or virtual scrolling for large datasets (1000+ rows)
- [ ] Row count displayed (e.g., "Showing 150 of 423 items")
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-018: Filter Entities by Type
**Description:** As a user, I want to filter the entity table by resource type so that I can focus on specific categories.

**Acceptance Criteria:**
- [ ] Dropdown filter above table with resource types
- [ ] Options: All, Connections, Repositories, Projects, Environments, Jobs, etc.
- [ ] Multi-select supported (e.g., show Connections AND Jobs)
- [ ] Filter count shown (e.g., "Connections (57)")
- [ ] Table updates immediately on filter change
- [ ] Filter state preserved when switching tabs
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-019: Search Entities
**Description:** As a user, I want to search across all entities so that I can quickly find items by name or key.

**Acceptance Criteria:**
- [ ] Global search box above the entity table
- [ ] Searches across: name, key, dbt_id columns
- [ ] Search is case-insensitive
- [ ] Results update as user types (debounced, 300ms)
- [ ] Clear button (X) to reset search
- [ ] Search term highlighted in results
- [ ] Works in combination with type filter
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-020: Export Entities to CSV
**Description:** As a user, I want to export the entity list to CSV so that I can analyze or share it externally.

**Acceptance Criteria:**
- [ ] "Export CSV" button above the table
- [ ] Exports currently filtered/searched view (not all data)
- [ ] CSV includes all table columns
- [ ] Filename format: `entities_{account_id}_{timestamp}.csv`
- [ ] Download triggers immediately (browser download)
- [ ] Success notification shown
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-021: View Resource Distribution Bar Chart
**Description:** As a user, I want to see a bar chart of resource counts by type so that I can understand the account composition.

**Acceptance Criteria:**
- [ ] Charts tab shows Plotly bar chart
- [ ] X-axis: resource types (Connections, Jobs, Environments, etc.)
- [ ] Y-axis: count
- [ ] Bars colored by type
- [ ] Hover shows exact count
- [ ] Click bar to filter entity table to that type
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-022: View Jobs by Project Treemap
**Description:** As a user, I want to see a treemap of jobs grouped by project so that I can identify which projects have the most jobs.

**Acceptance Criteria:**
- [ ] Treemap visualization showing jobs nested in projects
- [ ] Box size proportional to job count
- [ ] Color coding by project
- [ ] Hover shows project name and job count
- [ ] Click project to filter entity table to that project's resources
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-023: View Connection Types Pie Chart
**Description:** As a user, I want to see a pie chart of connection types so that I can understand what data platforms are in use.

**Acceptance Criteria:**
- [ ] Pie chart showing connection type distribution
- [ ] Slices: Snowflake, Databricks, BigQuery, Redshift, etc.
- [ ] Percentage labels on slices
- [ ] Legend with type names
- [ ] Hover shows count and percentage
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-024: View Entity Details
**Description:** As a user, I want to view full details of a specific entity so that I can inspect its configuration.

**Acceptance Criteria:**
- [ ] Click row in entity table to open detail panel
- [ ] Detail panel shows all fields from the entity
- [ ] JSON view toggle for raw data
- [ ] Copy JSON button
- [ ] Close button or click-outside to dismiss
- [ ] Typecheck passes
- [ ] Verify in browser

## Functional Requirements

- **FR-1:** Explore step must have tabs for Summary, Report, Entities, and Charts
- **FR-2:** Entity table must load data from `report_items` JSON
- **FR-3:** Entity table must support sorting, filtering, and searching
- **FR-4:** CSV export must export the current filtered view
- **FR-5:** Charts must be interactive (hover details, click to filter)
- **FR-6:** Entity detail panel must show full JSON data

## Non-Goals (Out of Scope)

- Editing entities in the Explore step (that's Map step)
- Comparing two different fetches
- Exporting to formats other than CSV (Excel, JSON export handled separately)
- Custom chart building

## Technical Considerations

### AGGrid Configuration
```python
grid = ui.aggrid({
    'columnDefs': [
        {'field': 'element_type_code', 'headerName': 'Type', 'filter': True, 'sortable': True},
        {'field': 'name', 'headerName': 'Name', 'filter': 'agTextColumnFilter', 'sortable': True},
        {'field': 'key', 'headerName': 'Key', 'filter': True, 'sortable': True},
        {'field': 'dbt_id', 'headerName': 'dbt ID', 'filter': 'agNumberColumnFilter', 'sortable': True},
        {'field': 'include_in_conversion', 'headerName': 'Include', 'cellRenderer': 'agCheckboxCellRenderer'},
        {'field': 'line_item_number', 'headerName': 'Line #', 'sortable': True},
    ],
    'rowData': report_items,
    'pagination': True,
    'paginationPageSize': 50,
    'domLayout': 'autoHeight',
})
```

### Chart Libraries
- Use Plotly for all charts (already specified in deps)
- `plotly.express` for quick chart creation
- Enable `config={'displayModeBar': True}` for chart controls

### File Structure Addition
```
importer/web/
├── pages/
│   └── explore.py            # Explore step page
└── components/
    ├── entity_table.py       # AGGrid wrapper with filtering
    ├── charts.py             # Chart generation functions
    └── entity_detail.py      # Detail panel component
```

### Data Loading
```python
def load_report_items(output_dir: str, account_id: int) -> list[dict]:
    """Find and load the most recent report_items JSON."""
    pattern = f"account_{account_id}_run_*__report_items__*.json"
    files = sorted(Path(output_dir).glob(pattern), reverse=True)
    if files:
        return json.loads(files[0].read_text())
    return []
```

## Success Metrics

- Entity table renders 1000+ rows without noticeable lag
- Filtering updates results in under 200ms
- CSV export of 1000 rows completes in under 2 seconds
- Charts render in under 1 second

## Open Questions

1. Should we add a "Compare" feature to compare two different fetch runs?
2. Should charts support fullscreen mode?
3. Should we add export to Excel (xlsx) in addition to CSV?
