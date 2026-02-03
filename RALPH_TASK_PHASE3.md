---
task: Protection Intent File System - Phase 3 (Generate Protection Changes)
test_command: "cd importer && python -m pytest web/tests/test_protection_intent.py -v"
browser_validation: true
base_url: "http://localhost:8501"
---

# Task: Generate Protection Changes Button

Add the "Generate Protection Changes" button that processes pending intents - updates YAML `protected:` flags and generates `protection_moves.tf` with moved blocks.

**Plan Reference:** `.cursor/plans/protection_intent_file_e08a2a4e.plan.md`
**Depends on:** Phase 2 (Match Page Integration)

## Success Criteria

### New Button

1. [ ] Add "Generate Protection Changes" button in mismatch panel, below Protect/Unprotect buttons

2. [ ] Button styling: `icon="auto_fix_high"`, `props("color=green")`

3. [ ] Button disabled when no pending intents (`get_pending_yaml_updates()` returns empty)

4. [ ] Button shows count: "Generate Protection Changes (3)" when 3 pending

### Streaming Progress Dialog

5. [ ] Create streaming progress dialog that opens when button clicked

6. [ ] Dialog layout: title "Generating Protection Changes...", Copy button, Close button

7. [ ] Dialog shows scrollable output area with monospace font, dark background

8. [ ] Stream progress messages: "Reading pending intents...", "Found N resources with pending changes"

9. [ ] Stream per-resource updates: "  - resource_key: protected/unprotected"

10. [ ] Stream YAML update progress: "Updating YAML files...", "Updated file.yml"

11. [ ] Stream moved block generation: "Generating protection_moves.tf...", "Generated N moved blocks"

12. [ ] Final message: "Done!" with summary

13. [ ] Copy button copies full output to clipboard

14. [ ] Use `asyncio.create_task` for non-blocking execution

15. [ ] Add Cancel button that stops the operation

### YAML Update Logic

16. [ ] Read pending intents from `get_pending_yaml_updates()`

17. [ ] For each pending intent, find the resource's YAML file

18. [ ] Update `protected: true/false` in YAML based on intent

19. [ ] Save modified YAML files

20. [ ] Call `mark_applied_to_yaml()` for all processed keys

### Protection Moves Generation

21. [ ] Generate `protection_moves.tf` file in TF directory

22. [ ] For each resource changing protection status, add `moved { from = ... to = ... }` block

23. [ ] Use correct TF address format: `module.adoption["key"].resource_type.resource` to `module.adoption_protected["key"].resource_type.resource` (or vice versa)

24. [ ] Handle both protect (unprotected -> protected) and unprotect (protected -> unprotected) moves

### UI Updates After Generation

25. [ ] After successful generation, update badge to "Pending: TF Init/Plan/Apply" (blue)

26. [ ] Refresh mismatch panel to show updated state

27. [ ] Intent file shows `applied_to_yaml=true` for processed resources

### Warning on Existing Generate Button

28. [ ] Add tooltip to existing "Generate" button in TF workflow section

29. [ ] Tooltip text: "Regenerates ALL TF files - use 'Generate Protection Changes' for protection-only updates"

### Browser Validation

30. [ ] Click "Unprotect All" to create pending intents

31. [ ] Verify "Generate Protection Changes" button is enabled with count

32. [ ] Click button, verify streaming dialog appears with progress

33. [ ] Verify YAML files are updated with new protected values

34. [ ] Verify `protection_moves.tf` is created with correct moved blocks

35. [ ] Verify badge changes to blue "Pending: TF Init/Plan/Apply"

## Context

### Moved Block Format
```hcl
moved {
  from = module.adoption["resource_key"].dbtcloud_project.project
  to   = module.adoption_protected["resource_key"].dbtcloud_project.project
}
```

### Files to Modify
- `importer/web/pages/match.py` - New button, streaming dialog
- `importer/web/utils/adoption_yaml_updater.py` - YAML update logic (may need new methods)

## Notes

- After this phase, the full workflow is: Click Unprotect → Click Generate → Run TF Init/Plan/Apply
- Phase 4 adds Utilities page for detailed management
- Phase 5 updates Destroy page to use intent manager
