---
task: Project Management - Phase 4 (Save Dialog & Settings Persistence)
test_command: "cd importer && python -m pytest web/tests/test_project_manager.py -v"
browser_validation: true
base_url: "http://localhost:8501"
track: project-management
---

# Task: Save .env Dialog & Settings Persistence (Epic 4, 6, 7)

Build the Save .env dialog, fetch page integration, and settings preservation features.

**PRD Reference:** `tasks/prd-web-ui-08-project-management.md` - Epic 4 (US-094 through US-096), Epic 6 (US-101, US-102), Epic 7 (US-103 through US-109)
**Depends on:** Phase 3 (Home Page & State Persistence)

## Success Criteria

### US-094: Save .env Dialog Component

1. [ ] Create `importer/web/components/save_env_dialog.py`

2. [ ] Dialog opens when clicking "Save to .env" button

3. [ ] Dialog pattern: `ui.card().classes("p-4 min-w-[400px] max-h-[80vh]")`

4. [ ] Close button (X) in header

5. [ ] Shows current project context (if active)

6. [ ] File path input with default based on context (`.env.source` or `.env.target`)

7. [ ] Browse button for file selection

8. [ ] Overwrite warning if file exists

9. [ ] "Save" (primary) and "Cancel" (flat) buttons

### US-095: Save .env Preview

10. [ ] Preview panel shows credentials to be saved

11. [ ] Tokens/secrets masked (show last 4 chars only)

12. [ ] Shows environment variable names

13. [ ] Preview updates if user changes path

### US-096: Save .env Execution

14. [ ] Clicking "Save" writes to specified path

15. [ ] Creates parent directories if needed

16. [ ] Preserves existing keys not being updated

17. [ ] Success notification with file path, dialog closes

18. [ ] Error notification on failure

### US-101: Project-Aware Output Directories

19. [ ] When project active, fetch outputs go to `{project}/outputs/source/` or `{project}/outputs/target/`

20. [ ] When no project, falls back to root output directory

21. [ ] Output directory shown in fetch form (read-only when project active)

### US-102: Save Button Opens Dialog

22. [ ] "Save to .env" button opens SaveEnvDialog

23. [ ] Dialog pre-populated with project context

24. [ ] Source fetch page defaults to `.env.source`, target to `.env.target`

25. [ ] After save, credentials marked as "saved to {path}"

### US-103: Preserve Settings on Re-Fetch

26. [ ] `disable_job_triggers` NOT reset when fetching new data

27. [ ] `import_mode` NOT reset when fetching new data

28. [ ] `confirmed_mappings` NOT cleared when fetching (may need revalidation)

29. [ ] `protected_resources` NOT cleared when fetching

30. [ ] `scope_mode` and `resource_filters` NOT reset when fetching

31. [ ] Notification shown if mappings need revalidation after fetch

### US-104: Per-Project Protected Resources

32. [ ] `protected_resources` stored in project's `state.json`

33. [ ] Protection status restored when loading a project

34. [ ] Protection isolated between projects (A's protection doesn't affect B)

35. [ ] Protecting/unprotecting resources auto-saves to project state

### US-105: Per-Project Confirmed Mappings

36. [ ] `confirmed_mappings` stored in project's `state.json`

37. [ ] `rejected_suggestions` stored in project's `state.json`

38. [ ] `cloned_resources` stored in project's `state.json`

39. [ ] Mappings restored when loading a project

40. [ ] Stale mappings detected if source/target data changed (show warning)

### US-106: Per-Project Deploy Settings

41. [ ] `disable_job_triggers` stored in project's `state.json`

42. [ ] `import_mode` stored in project's `state.json`

43. [ ] `terraform_dir` stored in project's `state.json`

44. [ ] Settings restored when loading a project

### US-107: Per-Project Mapping Configuration

45. [ ] `scope_mode` stored in project's `state.json`

46. [ ] `selected_project_ids` stored in project's `state.json`

47. [ ] `resource_filters` stored in project's `state.json`

48. [ ] `normalization_options` stored in project's `state.json`

### US-108: Settings Validation on Fetch

49. [ ] After fetch, check if confirmed_mappings reference resources that no longer exist

50. [ ] Show warning banner if mappings are stale: "X mappings may need review"

51. [ ] Mark stale mappings in Match UI (different color/icon)

52. [ ] Option to "Clear stale mappings" or "Review mappings"

53. [ ] Protected resources that no longer exist are cleaned up automatically

### US-109: Import Settings from Another Project

54. [ ] In wizard Step 2, "Copy from project" option includes settings checkbox

55. [ ] Can selectively import: Deploy settings, Mapping configuration (NOT mappings or protected resources)

56. [ ] Preview shows which settings will be imported

### Browser Validation

57. [ ] Save credentials via dialog, verify file created correctly

58. [ ] Set disable_job_triggers=true, fetch, verify still true

59. [ ] Protect resources in Project A, switch to Project B, verify not protected in B

60. [ ] Confirm mappings, close app, reopen, verify mappings preserved

61. [ ] Delete mapped source resource, re-fetch, verify stale warning appears

## Context

### Settings Preservation Logic
```python
def fetch_source(self):
    # Save current settings before fetch
    saved_settings = self.state.settings.copy()
    
    # Perform fetch (which may reset some state)
    self._do_fetch()
    
    # Restore settings that should persist
    self.state.settings.disable_job_triggers = saved_settings.disable_job_triggers
    self.state.settings.import_mode = saved_settings.import_mode
    # ... etc
```

## Notes

- This is the FINAL phase for Project Management track
- After completion, output `<ralph>COMPLETE</ralph>` for this track
