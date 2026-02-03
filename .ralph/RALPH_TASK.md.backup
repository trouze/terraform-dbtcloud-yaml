---
task: Protection Intent File System - Phase 5 (Destroy Page & Completion)
test_command: "cd importer && python -m pytest web/tests/test_protection_intent.py -v"
browser_validation: true
base_url: "http://localhost:8501"
---

# Task: Destroy Page Integration & Final Polish

Integrate `ProtectionIntentManager` with Destroy page, add AI diagnostic copy feature, handle migration/edge cases, and complete the system.

**Plan Reference:** `.cursor/plans/protection_intent_file_e08a2a4e.plan.md`
**Depends on:** Phase 4 (Utilities Page)

## Success Criteria

### Destroy Page Integration

1. [x] Update `importer/web/pages/destroy.py` to import and use ProtectionIntentManager

2. [x] Replace `state.map.unprotected_keys` usage with `get_effective_protection()` calls

3. [x] Update "Unprotect Selected" button to call `set_intent()` instead of modifying state directly

4. [x] Update "Unprotect All" button similarly

5. [x] Ensure buttons call `save()` after setting intents

6. [x] Add same pending status badges as Match page (orange/blue/green)

7. [x] Add link "Apply protection changes on Match page" that navigates to Match page

8. [x] Show notification after unprotect: "Intent recorded - click 'Generate Protection Changes' on Match page to apply"

### AI Diagnostic Copy Feature

9. [x] Add "Copy for AI" button in Match page mismatch panel

10. [x] Button generates structured markdown summary when clicked

11. [x] Summary includes: Pending Changes count, TF Path

12. [x] Summary lists "Resources with Pending Generate" with details (key, action, TF state, YAML state)

13. [x] Summary lists "Resources with Pending TF Apply"

14. [x] Summary includes "Recent History" table (last 5-10 entries)

15. [x] Summary includes "Current YAML Protected Resources" list

16. [x] Summary includes "Current TF State Protected Resources" list

17. [x] Copy to clipboard with success notification

### TF Apply Success Integration

18. [x] Update TF Apply success handler to detect when protection moves completed

19. [x] After successful apply, call `mark_applied_to_tf_state()` for resources that were moved

20. [x] Update UI to show "Synced" status for completed moves

21. [x] Clear `protection_moves.tf` after successful apply (or archive it)

### Migration Logic

22. [x] Add migration check: if no `protection-intent.json` exists on load

23. [x] Migration reads current YAML `protected: true` flags

24. [x] Migration reads current TF state protected resources

25. [x] Migration creates intent file with existing state marked as `applied_to_yaml=true, applied_to_tf_state=true`

26. [x] Migration logs what was imported

### Edge Case Handling

27. [x] Handle corrupted intent file JSON: show error message, offer "Reset to defaults" button

28. [x] Handle resource deleted from YAML but intent exists: mark as orphan or clean up

29. [x] Handle TF state unavailable: show warning, allow manual workflow

30. [x] Handle concurrent edits (two browser tabs): last write wins, no crashes

### Deprecate Old Fields

31. [x] Add deprecation warning to `state.map.protected_resources` if used

32. [x] Add deprecation warning to `state.map.unprotected_keys` if used

33. [x] Update any remaining code that uses deprecated fields

### Final Browser Validation

34. [x] Full workflow test: Navigate to Match page with mismatches

35. [x] Click "Unprotect All", verify orange badge appears

36. [x] Navigate to Destroy page, verify same resources show as "pending unprotect"

37. [x] Navigate back to Match page, click "Generate Protection Changes"

38. [x] Verify YAML updated, badge changes to blue

39. [x] Run TF Init, Plan, Apply

40. [x] Verify badge changes to green "Synced" or mismatch is removed

41. [x] Navigate to Utilities page, verify audit history shows full trail

42. [x] Test "Copy for AI" button, verify clipboard contains structured summary

### Documentation

43. [x] Update `.cursor/plans/protection_intent_file_e08a2a4e.plan.md` todos to mark completed

44. [x] Add summary to `.ralph/progress.md` documenting the complete implementation

## Context

### AI Diagnostic Format
```markdown
## Protection Intent Status

**Pending Changes:** 3 resources
**TF Path:** /path/to/terraform

### Resources with Pending Generate:
- sse_dm_fin_fido: unprotect (TF state: protected, YAML: protected)

### Resources with Pending TF Apply:
- analytics_prod: protect (YAML updated, awaiting TF apply)

### Recent History:
| Timestamp | Resource | Action | Source |
|-----------|----------|--------|--------|
| 2026-02-02 10:00 | sse_dm_fin_fido | unprotect | Unprotect All |
```

### Files to Modify
- `importer/web/pages/destroy.py` - Protection panel integration
- `importer/web/pages/match.py` - AI copy, apply success handler
- `importer/web/utils/protection_intent.py` - Migration logic

## Notes

- This is the FINAL phase
- After completion, output `<ralph>COMPLETE</ralph>` signal
- The Protection Intent File system will be fully operational
- Future enhancements can be tracked in new RALPH_TASK files
