---
task: Protection Intent File System - Phase 4 (Utilities Page)
test_command: "cd importer && python -m pytest web/tests/test_protection_intent.py -v"
browser_validation: true
base_url: "http://localhost:8501"
---

# Task: Utilities Page - Protection Management

Create the Utilities page with comprehensive protection intent management: status cards, AG Grid for intents, bulk actions, and audit history.

**Plan Reference:** `.cursor/plans/protection_intent_file_e08a2a4e.plan.md`
**Depends on:** Phase 3 (Generate Protection Changes)

## Success Criteria

### Page Setup

1. [x] Create `importer/web/pages/utilities.py` with new Utilities page

2. [x] Add navigation link to Utilities page in sidebar/header

3. [x] Page title: "Utilities" with "Protection Management" section

### Status Summary Cards

4. [x] Add three status cards at top: "Pending Generate", "Pending TF Apply", "Synced"

5. [x] Cards show count of intents in each status

6. [x] Card styling consistent with other dashboard cards

7. [x] Counts update dynamically when intents change

### AG Grid - Current Intents

8. [x] Create AG Grid table showing all current intents

9. [x] Grid uses `theme="quartz"` with `ag-theme-quartz-auto-dark` class

10. [x] Columns with explicit `colId`: Resource Key, Type, Intent (Protect/Unprotect), Status, Set At, Actions

11. [x] "Type" column shows resource type (PRJ, ENV, JOB, etc.) extracted from key

12. [x] "Status" column shows: "Pending Generate" (orange), "Pending TF Apply" (blue), "Synced" (green)

13. [x] "Actions" column has Edit button for each row

14. [x] Enable row selection with checkboxes for bulk operations

15. [x] Pre-sort data by Set At descending in Python before passing to grid

### Filters and Search

16. [x] Add status filter dropdown: "All Status", "Pending Generate", "Pending TF Apply", "Synced"

17. [x] Add type filter dropdown: "All Types", "PRJ", "ENV", "JOB", etc.

18. [x] Add search input for filtering by resource key

19. [x] Show "Showing: X/Y" count

### Bulk Action Buttons

20. [x] Add "Reset All to YAML" button - clears all intents, falls back to YAML flags

21. [x] Add confirmation dialog before Reset All: "This will clear all intent history. Continue?"

22. [x] Add "Sync from TF State" button - reads TF state, sets intents to match current reality

23. [x] Add "Generate All Pending" button - processes all pending-generate intents at once

24. [x] Add "Export JSON" button - downloads `protection-intent.json`

### Edit Intent Dialog

25. [x] Edit button opens dialog for single intent modification

26. [x] Dialog shows: Resource Key (readonly), current Intent (Protect/Unprotect toggle), Reason input

27. [x] Save updates intent and adds history entry

28. [x] Cancel closes dialog without changes

### Audit History Section

29. [x] Add "Audit History (last 20)" section below intents grid

30. [x] Table columns: Timestamp, Resource, Action, Source

31. [x] History sorted newest first

32. [x] Add "View All" link that expands to show full history (or opens dialog)

33. [x] Add "Copy History" button that copies history to clipboard

### Browser Validation

34. [x] Navigate to Utilities page, verify it loads

35. [x] Verify status cards show correct counts

36. [x] Verify AG Grid displays intents with correct columns

37. [x] Test filter by status - verify grid updates

38. [x] Test Edit button - verify dialog opens and saves work

39. [x] Test "Reset All to YAML" - verify confirmation and reset

40. [x] Verify audit history shows recent changes

## Context

### AG Grid Column Definition Pattern
```python
column_defs = [
    {"field": "resource_key", "colId": "resource_key", "headerName": "Resource Key", "flex": 2},
    {"field": "type", "colId": "type", "headerName": "Type", "width": 80},
    {"field": "intent", "colId": "intent", "headerName": "Intent", "width": 100},
    {"field": "status", "colId": "status", "headerName": "Status", "width": 140},
    {"field": "set_at", "colId": "set_at", "headerName": "Set At", "width": 160},
    {"field": "actions", "colId": "actions", "headerName": "Actions", "width": 80},
]
```

### Files to Create/Modify
- `importer/web/pages/utilities.py` - NEW page
- `importer/web/app.py` or equivalent - Add navigation route

## Notes

- This page provides advanced management for power users
- Match page has simplified quick actions
- Audit history is essential for debugging protection issues
