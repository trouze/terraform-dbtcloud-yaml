---
task: Extended Attributes - Phase 3 (Interaction & Dependencies)
test_command: "cd importer && python -m pytest web/tests/ -v -k extended"
browser_validation: true
base_url: "http://localhost:8501"
track: extended-attributes
---

# Task: Extended Attributes Interaction & Dependencies (Sprint 4-5)

Implement scope selection with cascade logic, matching grid integration, editor component, and Terraform modules.

**Plan Reference:** `.cursor/plans/extended_attributes_support_96c8d11a.plan.md` - Sprint 4, Sprint 5
**Depends on:** Phase 2 (Web UI Display)

## Success Criteria

### Sprint 4: Scope Selection & Dependencies

1. [ ] Add Environment→ExtendedAttributes dependency to `importer/web/utils/dependency_analyzer.py`

2. [ ] Selecting an Environment auto-selects its linked Extended Attributes

3. [ ] Deselecting Extended Attributes warns if Environment still selected

4. [ ] Orphan detection: Extended Attributes with no Environment references shows warning

5. [ ] "Used by N environments" indicator in scope selection UI

### Sprint 4: Matching Grid Integration

6. [ ] Add Extended Attributes rows to matching grid in `importer/web/components/match_grid.py`

7. [ ] Columns: Key, Source Attributes, Target Attributes, Match Status, Actions

8. [ ] JSON diff view for comparing source vs target attributes

9. [ ] "Auto-match by environment" option that matches EXTATTR when ENV matched

10. [ ] Dependency indicators showing linked environments

11. [ ] Match validation: flag significant JSON differences

### Sprint 5: Extended Attributes Editor

12. [ ] Create `importer/web/components/extended_attributes_editor.py`

13. [ ] JSON editor with syntax highlighting (Monaco or similar)

14. [ ] Key-value form editor as alternative view

15. [ ] Toggle button to switch between JSON/form views

16. [ ] Validation of JSON syntax

17. [ ] "Reset to original" button

18. [ ] "Copy from source" button (in target context)

### Sprint 5: Target Credentials Integration

19. [ ] Add Extended Attributes editing section to `importer/web/pages/target_credentials.py`

20. [ ] Section shows per-environment extended attributes configuration

21. [ ] Edit button opens extended attributes editor dialog

22. [ ] Changes saved to state for deployment

### Sprint 5: Terraform Module

23. [ ] Create `modules/extended_attributes/` directory

24. [ ] Create `modules/extended_attributes/main.tf` with unprotected and protected resource blocks

25. [ ] Create `modules/extended_attributes/variables.tf` with `extended_attrs_map` and `protected_extended_attrs_map`

26. [ ] Create `modules/extended_attributes/outputs.tf` with extended attributes IDs

27. [ ] Protected resource block includes `lifecycle { prevent_destroy = true }`

28. [ ] Update `modules/environments/main.tf` to reference extended_attributes_id

29. [ ] Update `modules/environments/variables.tf` to accept extended_attributes_ids input

### Browser Validation

30. [ ] Select environment in scope, verify linked EXTATTR auto-selected

31. [ ] Deselect EXTATTR with ENV still selected, verify warning appears

32. [ ] View matching grid with extended attributes, verify JSON diff displays

33. [ ] Open extended attributes editor, modify JSON, verify syntax validation

34. [ ] Toggle between JSON and form views in editor

35. [ ] Verify Terraform modules generate correct resource blocks

## Context

### Dependency Graph
```
Environment ────depends on────> Extended Attributes
    │                                   │
    ▼                                   ▼
(auto-select)                    (auto-select)
```

### Terraform Module Pattern
```hcl
# modules/extended_attributes/main.tf

resource "dbtcloud_extended_attributes" "extended_attrs" {
  for_each = local.unprotected_extended_attrs_map
  
  project_id = each.value.project_id
  extended_attributes = jsonencode(each.value.attributes)
}

resource "dbtcloud_extended_attributes" "protected_extended_attrs" {
  for_each = local.protected_extended_attrs_map
  
  project_id = each.value.project_id
  extended_attributes = jsonencode(each.value.attributes)
  
  lifecycle {
    prevent_destroy = true
  }
}
```

## Notes

- Phase 4 will add protection cascade integration with ProtectionIntentManager
- This phase creates the Terraform module but protection logic is in Phase 4
