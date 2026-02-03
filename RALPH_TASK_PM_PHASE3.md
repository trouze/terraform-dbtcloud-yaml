---
task: Project Management - Phase 3 (Home Page & State Persistence)
test_command: "cd importer && python -m pytest web/tests/test_project_manager.py -v"
browser_validation: true
base_url: "http://localhost:8501"
track: project-management
---

# Task: Home Page Project Selector & State Persistence (Epic 3, 5)

Build the home page project selector with hybrid card/AG Grid view and implement state auto-save.

**PRD Reference:** `tasks/prd-web-ui-08-project-management.md` - Epic 3 (US-090 through US-093), Epic 5 (US-097 through US-100)
**Depends on:** Phase 2 (New Project Wizard)

## Success Criteria

### US-090: Project List Display (Hybrid Card/Grid)

1. [ ] Add "Your Projects" section to home page

2. [ ] Hybrid display: <10 projects shows card grid, ≥10 projects shows AG Grid

3. [ ] Toggle button to manually switch between Card/Grid views

4. [ ] User preference persisted in browser storage

5. [ ] Projects sorted by last modified (most recent first)

6. [ ] "No projects yet" message when list empty

7. [ ] "New Project" button prominently displayed

### Card View (< 10 projects)

8. [ ] Projects displayed as cards in responsive grid

9. [ ] Each card shows: name (title), workflow type badge (colored), description (2 lines), last modified (relative)

10. [ ] Cards show source/target account info if configured

11. [ ] Click card to load project

12. [ ] Delete button (trash icon) with confirmation dialog

### AG Grid View (≥ 10 projects)

13. [ ] Use `theme="quartz"` with `ag-theme-quartz-auto-dark` class

14. [ ] Columns with explicit `colId`: name, workflow_type, description, source_account, target_account, updated_at, actions

15. [ ] workflow_type column with dropdown filter and colored badges

16. [ ] source_account/target_account columns formatted as `{host} / Account {id}`

17. [ ] updated_at with relative date formatter

18. [ ] actions column with Load/Delete buttons, pinned right

19. [ ] `defaultColDef`: sortable, filter, resizable

20. [ ] Quick search input with `setGridOption('quickFilterText', ...)`

21. [ ] Export to CSV button

22. [ ] Pre-sort data in Python, NOT via AG Grid sort properties

23. [ ] Row click loads the project

### US-091: Load Existing Project

24. [ ] Clicking project card/row loads that project

25. [ ] Loading indicator during project load

26. [ ] AppState restored from `state.json`

27. [ ] Credentials loaded from `.env.source` and `.env.target`

28. [ ] `active_project` field set in AppState

29. [ ] Navigate to appropriate workflow step based on state

30. [ ] Success notification: "Loaded project: {name}"

### US-092: Delete Project

31. [ ] Delete button with confirmation dialog showing project name

32. [ ] Warning about permanent deletion

33. [ ] On confirm: folder deleted, project removed from list, success notification

34. [ ] Cannot delete currently active project (must switch first)

### US-093: Project Search/Filter

35. [ ] Search input filters by name and description (card view)

36. [ ] Filter chips for workflow type

37. [ ] Filter dropdowns for source/target account

38. [ ] "No matching projects" message when filter returns empty

39. [ ] Clear all filters button

### US-097: AppState Project Fields

40. [ ] Add `active_project: Optional[str]` field (slug) to AppState

41. [ ] Add `project_path: Optional[Path]` field

42. [ ] Fields included in `to_dict()` and `from_dict()`

### US-098: Full AppState Serialization

43. [ ] `to_dict()` serializes all nested dataclasses

44. [ ] `from_dict()` restores all nested dataclasses

45. [ ] Handles None, missing keys, datetime, enum fields gracefully

### US-099: Auto-Save State to Project

46. [ ] State saved automatically when project is active

47. [ ] Save triggered on significant state changes (credential changes, fetch completion, selection changes)

48. [ ] Debounced saving (max 1 save per second)

49. [ ] Save happens in background (non-blocking)

50. [ ] Errors logged but don't interrupt user workflow

### US-100: Load Last Active Project on Startup

51. [ ] Last active project slug stored in browser storage

52. [ ] On app startup, auto-load last project if exists

53. [ ] If last project no longer exists, clear stored slug, show home page

### Browser Validation

54. [ ] Create 3 projects, verify card view displayed

55. [ ] Create 10+ projects, verify AG Grid view displayed

56. [ ] Toggle between card/grid views, verify preference persists

57. [ ] Load project, make changes, close app, reopen - verify state restored

58. [ ] Delete project, verify removed from list

59. [ ] Test AG Grid filters and search

## Context

### AG Grid Columns Pattern
```python
column_defs = [
    {"field": "name", "colId": "name", "headerName": "Project", "flex": 2},
    {"field": "workflow_type", "colId": "workflow_type", "headerName": "Type", "width": 150,
     "cellClassRules": {...}},  # Color-coded badges
    {"field": "source_account", "colId": "source_account", "headerName": "Source", "width": 200},
    {"field": "target_account", "colId": "target_account", "headerName": "Target", "width": 200},
    {"field": "updated_at", "colId": "updated_at", "headerName": "Modified", "width": 140},
    {"field": "actions", "colId": "actions", "headerName": "", "width": 100, "pinned": "right"},
]
```

## Notes

- Phase 4 adds Save .env Dialog and Fetch Page Integration
- Phase 5 adds Settings Preservation features
