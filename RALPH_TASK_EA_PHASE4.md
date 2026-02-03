---
task: Extended Attributes - Phase 4 (Protection & Destroy Integration)
test_command: "cd importer && python -m pytest web/tests/ -v -k 'extended or protection'"
browser_validation: true
base_url: "http://localhost:8501"
track: extended-attributes
---

# Task: Extended Attributes Protection & Destroy Integration (Sprint 6-7)

Implement cascade protection using ProtectionIntentManager and integrate with Destroy page.

**Plan Reference:** `.cursor/plans/extended_attributes_support_96c8d11a.plan.md` - Sprint 6, Sprint 7
**Depends on:** Phase 3 (Interaction & Dependencies), Protection Intent track Phase 1+

## Success Criteria

### Sprint 6: Protection Manager Integration

1. [ ] Add EXTATTR to `protection_manager.py` type_map

2. [ ] Add EXTATTR to PARENT_CHAIN: `"EXTATTR": ["PRJ"]`

3. [ ] Update `get_resources_to_protect()` for EXTATTR → PRJ cascade

4. [ ] Update `get_resources_to_protect()` for ENV with linked EXTATTR → includes EXTATTR + PRJ

5. [ ] Update `get_resources_to_unprotect()` to include EXTATTR children when unprotecting PRJ

### Sprint 6: Protection Intent Integration

6. [ ] Cascade protection dialogs write to `ProtectionIntentManager` (not directly to YAML)

7. [ ] "Protect All (N)" button records intent for EXTATTR + cascade parents

8. [ ] "Generate Protection Changes" processes EXTATTR intents along with others

9. [ ] Intent status badges show EXTATTR protection status

### Sprint 6: Match Grid Protection UI

10. [ ] Protection checkbox column in match grid for EXTATTR rows

11. [ ] Blue row styling for protected EXTATTR (same pattern as other protected resources)

12. [ ] Cascade dialog when clicking protect on EXTATTR: "Also protect Analytics (Project)?"

13. [ ] Cascade dialog when protecting ENV with linked EXTATTR: "Also protect prod_config (EXTATTR) + Analytics (PRJ)?"

14. [ ] Warning when unprotecting EXTATTR that environments reference

### Sprint 6: Deploy Page Protection Panel

15. [ ] Protected EXTATTR appear in Deploy page protection panel

16. [ ] Warning when protected EXTATTR would be modified

17. [ ] Same removal workflow as other protected resources

### Sprint 7: Destroy Page Integration

18. [ ] Add EXTATTR to `TERRAFORM_TYPE_MAP` in `importer/web/pages/destroy.py`: `"EXTATTR": "dbtcloud_extended_attributes"`

19. [ ] Add EXTATTR to `PROTECTED_RESOURCE_MAP`: `"EXTATTR": ("dbtcloud_extended_attributes", "protected_extended_attrs")`

20. [ ] Add "Extended Attributes" to type filter dropdowns (both panels)

21. [ ] EXTATTR rows display in Protected Resources panel

22. [ ] EXTATTR rows display in Destroy Resources table

23. [ ] Detail dialog shows formatted JSON attributes for EXTATTR

24. [ ] Taint command: `terraform taint 'dbtcloud_extended_attributes.extended_attrs["key"]'`

25. [ ] Destroy command: `terraform destroy -target='dbtcloud_extended_attributes.extended_attrs["key"]'`

26. [ ] Cascade warning when destroying/tainting EXTATTR referenced by environments

### Protection Tests

27. [ ] Test CP-EA-01: Protect EXTATTR cascades to PRJ

28. [ ] Test CP-EA-02: Protect ENV with EXTATTR cascades to EXTATTR + PRJ

29. [ ] Test CP-EA-03: Unprotect PRJ prompts about EXTATTR children

30. [ ] Test CP-EA-04: Protected EXTATTR has blue row styling

31. [ ] Test CP-EA-05: Protection checkbox toggles correctly

32. [ ] Test CP-EA-06: Intent file updated when protecting EXTATTR

33. [ ] Test CP-EA-07: Generate Protection Changes processes EXTATTR

### Destroy Page Tests

34. [ ] Test DEST-EA-01: EXTATTR type appears in filter dropdown

35. [ ] Test DEST-EA-02: EXTATTR rows display with correct data

36. [ ] Test DEST-EA-03: Detail dialog shows JSON attributes

37. [ ] Test DEST-EA-04: Taint command generated correctly

38. [ ] Test DEST-EA-05: Destroy command generated correctly

39. [ ] Test DEST-EA-06: Cascade warning when EXTATTR has ENV references

### Browser Validation

40. [ ] Click protect on EXTATTR, verify cascade dialog appears

41. [ ] Accept cascade, verify intent recorded for EXTATTR + PRJ

42. [ ] Click "Generate Protection Changes", verify EXTATTR processed

43. [ ] Navigate to Destroy page, filter by Extended Attributes

44. [ ] Click EXTATTR row, verify detail dialog shows JSON

45. [ ] Generate taint command, verify correct format

## Context

### Protection Cascade Flow
```
1. User clicks protect on EXTATTR
   └──► Cascade dialog: "Also protect Analytics (Project)?"
        └──► "Protect All (2)" → Intent recorded for both
        └──► User clicks "Generate Protection Changes" → YAML updated
        └──► User runs Init → Plan → Apply → Synced
```

### Terraform Address Mappings
```python
TERRAFORM_TYPE_MAP = {
    "PRJ": "dbtcloud_project",
    "ENV": "dbtcloud_environment", 
    "EXTATTR": "dbtcloud_extended_attributes",
    # ...
}

PROTECTED_RESOURCE_MAP = {
    "PRJ": ("dbtcloud_project", "protected_projects"),
    "ENV": ("dbtcloud_environment", "protected_environments"),
    "EXTATTR": ("dbtcloud_extended_attributes", "protected_extended_attrs"),
    # ...
}
```

## Notes

- This is the FINAL phase for Extended Attributes track
- After completion, output `<ralph>COMPLETE</ralph>` for this track
- Requires Protection Intent track Phase 1 to be complete (ProtectionIntentManager exists)
