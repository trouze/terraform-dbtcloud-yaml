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

1. [x] Add "Generate Protection Changes" button in mismatch panel, below Protect/Unprotect buttons

2. [x] Button styling: `icon="auto_fix_high"`, `props("color=green")`

3. [x] Button disabled when no pending intents (`get_pending_yaml_updates()` returns empty)

4. [x] Button shows count: "Generate Protection Changes (3)" when 3 pending

### Streaming Progress Dialog

5. [x] Create streaming progress dialog that opens when button clicked

6. [x] Dialog layout: title "Generating Protection Changes...", Copy button, Close button

7. [x] Dialog shows scrollable output area with monospace font, dark background

8. [x] Stream progress messages: "Reading pending intents...", "Found N resources with pending changes"

9. [x] Stream per-resource updates: "  - resource_key: protected/unprotected"

10. [x] Stream YAML update progress: "Updating YAML files...", "Updated file.yml"

11. [x] Stream moved block generation: "Generating protection_moves.tf...", "Generated N moved blocks"

12. [x] Final message: "Done!" with summary

13. [x] Copy button copies full output to clipboard

14. [x] Use `asyncio.create_task` for non-blocking execution

15. [x] Add Cancel button that stops the operation

### YAML Update Logic

16. [x] Read pending intents from `get_pending_yaml_updates()`

17. [x] For each pending intent, find the resource's YAML file

18. [x] Update `protected: true/false` in YAML based on intent

19. [x] Save modified YAML files

20. [x] Call `mark_applied_to_yaml()` for all processed keys

### Protection Moves Generation

21. [x] Generate `protection_moves.tf` file in TF directory

22. [x] For each resource changing protection status, add `moved { from = ... to = ... }` block

23. [x] Use correct TF address format: `module.adoption["key"].resource_type.resource` to `module.adoption_protected["key"].resource_type.resource` (or vice versa)

24. [x] Handle both protect (unprotected -> protected) and unprotect (protected -> unprotected) moves

### UI Updates After Generation

25. [x] After successful generation, update badge to "Pending: TF Init/Plan/Apply" (blue)

26. [x] Refresh mismatch panel to show updated state

27. [x] Intent file shows `applied_to_yaml=true` for processed resources

### Warning on Existing Generate Button

28. [x] Add tooltip to existing "Generate" button in TF workflow section

29. [x] Tooltip text: "Regenerates ALL TF files - use 'Generate Protection Changes' for protection-only updates"

### Browser Validation

30. [x] Click "Unprotect All" to create pending intents

31. [x] Verify "Generate Protection Changes" button is enabled with count

32. [x] Click button, verify streaming dialog appears with progress

33. [x] Verify YAML files are updated with new protected values

34. [x] Verify `protection_moves.tf` is created with correct moved blocks

35. [x] Verify badge changes to blue "Pending: TF Init/Plan/Apply"

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
