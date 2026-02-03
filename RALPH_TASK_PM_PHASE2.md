---
task: Project Management - Phase 2 (New Project Wizard)
test_command: "cd importer && python -m pytest web/tests/test_project_manager.py -v"
browser_validation: true
base_url: "http://localhost:8501"
track: project-management
---

# Task: New Project Wizard (Epic 2)

Build the multi-step wizard dialog for creating new projects with credential import options.

**PRD Reference:** `tasks/prd-web-ui-08-project-management.md` - Epic 2 (US-085 through US-089)
**Depends on:** Phase 1 (ProjectManager class)

## Success Criteria

### US-085: Wizard Dialog Component

1. [ ] Create `importer/web/components/new_project_wizard.py`

2. [ ] Dialog opens from "New Project" button (to be added to home page)

3. [ ] Dialog uses pattern: `with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl")`

4. [ ] Close button (X icon) in top-right: `ui.button(icon="close", on_click=dialog.close).props("flat round dense")`

5. [ ] Stepper component shows 4 steps with labels: Basics, Credentials, Output, Summary

6. [ ] Current step highlighted, completed steps show checkmark

7. [ ] "Back" and "Next" buttons for navigation, "Next" disabled until current step valid

8. [ ] "Cancel" button closes dialog without creating project

9. [ ] Dialog is modal, content areas use `ui.scroll_area()` for overflow

### US-086: Wizard Step 1 - Project Basics

10. [ ] Project name input (required), min 3 chars, max 100 chars

11. [ ] Real-time uniqueness validation against existing projects

12. [ ] Generated slug shown below name input

13. [ ] Description textarea (optional), max 500 chars with character counter

14. [ ] Workflow type selection (radio or dropdown): Migration, Account Explorer, Jobs as Code, Import & Adopt

15. [ ] Default workflow type: Migration

16. [ ] Validation errors shown inline

### US-087: Wizard Step 2 - Import Credentials

17. [ ] Three radio options: "Start fresh" (default), "Import from .env file", "Copy from existing project"

18. [ ] File picker for .env import: Browse button, shows selected path, validates file exists

19. [ ] .env preview panel: Shows detected source/target credentials (masked tokens)

20. [ ] Checkboxes: "Import source credentials", "Import target credentials"

21. [ ] Project copy dropdown: Lists all existing projects with name and workflow type

22. [ ] Step is always valid (import is optional)

### US-088: Wizard Step 3 - Output Configuration

23. [ ] Source output directory field, default: `outputs/source/`

24. [ ] Target output directory field, default: `outputs/target/`

25. [ ] Normalized YAML directory field, default: `outputs/normalized/`

26. [ ] Checkbox: "Use timestamped subdirectories" (default: on)

27. [ ] Preview of full paths displayed

28. [ ] Validation: directories must be within project folder (no escape via ../)

### US-089: Wizard Step 4 - Summary & Create

29. [ ] Summary card displays all settings: name, slug, description, workflow type, credential import choice, output config

30. [ ] "Create Project" button with prominent styling

31. [ ] Button shows loading state during creation

32. [ ] On success: notification, dialog closes, project loaded as active, navigate to first workflow step

33. [ ] On error: error notification with details, user can go back to fix

### Browser Validation

34. [ ] Open wizard from home page, navigate all 4 steps, cancel - verify no project created

35. [ ] Enter duplicate name, verify validation error appears

36. [ ] Complete wizard with "Start fresh", verify project folder created with correct structure

37. [ ] Complete wizard with .env import, verify credentials copied

38. [ ] Verify stepper state updates correctly on navigation

## Context

### Dialog Pattern (from ag-grid-standards.mdc)
```python
with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
    with ui.row().classes("w-full justify-between items-center"):
        ui.label("New Project").classes("text-lg font-bold")
        ui.button(icon="close", on_click=dialog.close).props("flat round dense")
    
    with ui.scroll_area().classes("w-full").style("max-height: 60vh;"):
        # Wizard content here
    
    with ui.row().classes("w-full justify-end gap-2 mt-4"):
        ui.button("Cancel", on_click=dialog.close).props("flat")
        ui.button("Back", on_click=prev_step).props("outline")
        ui.button("Next", on_click=next_step).props("color=primary")

dialog.open()
```

## Notes

- Phase 3 adds home page with project list and "New Project" button
- This wizard will be invoked from there
