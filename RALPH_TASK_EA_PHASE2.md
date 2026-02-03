---
task: Extended Attributes - Phase 2 (Web UI Display)
test_command: "cd importer && python -m pytest web/tests/ -v -k extended"
browser_validation: true
base_url: "http://localhost:8501"
track: extended-attributes
---

# Task: Extended Attributes Web UI Display (Sprint 3)

Add extended attributes to the entity table, environment detail views, and create detail dialog.

**Plan Reference:** `.cursor/plans/extended_attributes_support_96c8d11a.plan.md` - Sprint 3
**Depends on:** Phase 1 (Data Model & Fetching)

## Success Criteria

### Entity Table Integration

1. [ ] Add "Extended Attributes" to resource type filter in `importer/web/components/entity_table.py`

2. [ ] Extended attributes rows display in entity table when type filter includes them

3. [ ] Columns: Key, Project, Environment, Attributes (truncated JSON), Protected status

4. [ ] Row click opens extended attributes detail dialog

5. [ ] Resource count in header includes extended attributes

### Environment Detail View

6. [ ] Add "Extended Attributes" section to environment detail view in `importer/web/pages/explore.py`

7. [ ] Section shows: configured (yes/no), attribute count, preview of keys

8. [ ] "View Details" link opens extended attributes detail dialog

9. [ ] Section hidden if environment has no extended attributes

### Extended Attributes Detail Dialog

10. [ ] Create detail dialog component for extended attributes

11. [ ] Dialog shows: ID, Project, Environment link, State, Created/Updated timestamps

12. [ ] JSON attributes displayed with syntax highlighting (read-only in this phase)

13. [ ] Copy JSON button for attributes

14. [ ] "Used by N environments" indicator

15. [ ] Close button per dialog standards

### Explore Page Integration

16. [ ] Extended attributes visible in Explore page entities tab

17. [ ] Filter by "Extended Attributes" type works correctly

18. [ ] Search by key or attribute content finds matching extended attributes

### Resource Reports

19. [ ] Extended attributes included in resource summary counts

20. [ ] "Extended Attributes: N" shown in resource overview panel

### Browser Validation

21. [ ] Navigate to Explore page, filter by "Extended Attributes", verify rows display

22. [ ] Click extended attributes row, verify detail dialog opens with correct data

23. [ ] Navigate to environment detail, verify extended attributes section shows

24. [ ] Verify JSON display is formatted and readable

25. [ ] Test search finds extended attributes by key

## Context

### Entity Table Row Format
```python
{
    "key": "extattr_789_123",
    "type": "EXTATTR",
    "name": "Production Extended Attributes",
    "project": "Analytics",
    "environment": "Production",
    "attributes_preview": '{"type": "databricks", ...}',
    "protected": False,
}
```

### Detail Dialog Pattern
```python
with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[500px] max-h-[80vh]"):
    with ui.row().classes("w-full justify-between items-center"):
        ui.label("Extended Attributes Details").classes("text-lg font-bold")
        ui.button(icon="close", on_click=dialog.close).props("flat round dense")
    
    with ui.scroll_area().classes("w-full").style("max-height: 60vh;"):
        # Metadata section
        # JSON display section
    
dialog.open()
```

## Notes

- Phase 3 will add interaction features (scope selection, matching, editing)
- Phase 4 will add Terraform and protection cascade
