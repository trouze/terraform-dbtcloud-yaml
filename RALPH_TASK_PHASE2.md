---
task: Protection Intent File System - Phase 2 (Match Page Integration)
test_command: "cd importer && python -m pytest web/tests/test_protection_intent.py -v"
browser_validation: true
base_url: "http://localhost:8501"
---

# Task: Match Page Integration

Integrate `ProtectionIntentManager` with the Match page - button handlers record intent, mismatch detection uses effective protection, and UI shows pending status badges.

**Plan Reference:** `.cursor/plans/protection_intent_file_e08a2a4e.plan.md`
**Depends on:** Phase 1 (Core Foundation) - `importer/web/utils/protection_intent.py` must exist

## Success Criteria

### State Integration

1. [ ] Add `protection_intent: ProtectionIntentManager` to `importer/web/state.py` AppState or MapState class

2. [ ] Initialize ProtectionIntentManager in state initialization, using deployment directory path for intent file

3. [ ] Load intent file when state is loaded, save when state is saved

### Button Handler Updates (match.py)

4. [ ] Update "Protect All" button handler to call `protection_intent_manager.set_intent()` for each mismatched resource with `protected=True, source="protect_all_button"`

5. [ ] Update "Unprotect All" button handler to call `set_intent()` with `protected=False, source="unprotect_all_button"`

6. [ ] Ensure buttons call `protection_intent_manager.save()` after setting intents

7. [ ] Remove direct YAML updates from Protect/Unprotect buttons (they now only record intent)

8. [ ] Fix button styling: create with `icon="shield"` for Protect All, `icon="lock_open"` for Unprotect All (not `set_icon()`)

### Mismatch Detection Updates (match_grid.py)

9. [ ] Import ProtectionIntentManager and get instance from state

10. [ ] Update mismatch detection logic to use `get_effective_protection(source_key, yaml_protected)` instead of direct `source_key in protected_resources` check

11. [ ] Ensure mismatch panel shows resources where TF state differs from effective protection (not YAML protection)

### UI Status Badges

12. [ ] Add pending status badge showing "Pending: Generate Protection Changes (N)" in orange when any intent has `applied_to_yaml=False`

13. [ ] Add badge showing "Pending: TF Init/Plan/Apply (N)" in blue when any intent has `applied_to_yaml=True` but `applied_to_tf_state=False`

14. [ ] Add badge showing "Synced (N)" in green when intent has both `applied_to_yaml=True` and `applied_to_tf_state=True`

15. [ ] Badge styling: orange=`classes("bg-amber-100 text-amber-800 px-2 py-1 rounded text-xs")`, blue=`classes("bg-blue-100 text-blue-800 ...")`, green=`classes("bg-green-100 text-green-800 ...")`

### Recent Changes Section

16. [ ] Add expandable "Recent Changes" section in mismatch panel showing last 5 history entries from intent file

17. [ ] Format history entries showing: timestamp, resource key, action (protect/unprotect), source

18. [ ] Add "View full audit trail in Utilities" link (placeholder - Utilities page created in Phase 4)

### Browser Validation

19. [ ] Restart server with `./restart_web.sh`, navigate to Match page, verify mismatch panel loads

20. [ ] Click "Unprotect All", verify intent file is created/updated (check with file read)

21. [ ] Verify orange "Pending: Generate Protection Changes" badge appears after clicking Unprotect All

22. [ ] Verify "Recent Changes" section shows the unprotect action

## Context

### Files to Modify
- `importer/web/state.py` - Add protection_intent field
- `importer/web/pages/match.py` - Button handlers, UI badges
- `importer/web/components/match_grid.py` - Mismatch detection logic

### Key Pattern
```python
# OLD - direct YAML check
is_yaml_protected = source_key in protected_resources

# NEW - intent takes precedence
is_yaml_protected = protection_intent_manager.get_effective_protection(
    source_key, 
    yaml_protected=(source_key in yaml_protected_resources)
)
```

## Notes

- Phase 3 will add "Generate Protection Changes" button
- Buttons now ONLY record intent - they don't update YAML
- User must click "Generate Protection Changes" (Phase 3) to apply to YAML
