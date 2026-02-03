---
task: Extended Attributes - Phase 1 (Foundation)
test_command: "cd importer && python -m pytest tests/test_models.py tests/test_fetcher.py -v -k extended"
browser_validation: false
base_url: "http://localhost:8501"
track: extended-attributes
---

# Task: Extended Attributes Foundation (Sprint 1-2)

Build the data model, API fetching, and YAML serialization for Extended Attributes.

**Plan Reference:** `.cursor/plans/extended_attributes_support_96c8d11a.plan.md` - Sprint 1, Sprint 2

## Success Criteria

### Sprint 1: Data Model

1. [ ] Create `ExtendedAttributes` Pydantic model in `importer/models.py` with fields: `id`, `extended_attributes_id`, `project_id`, `state`, `extended_attributes` (dict), `created_at`, `updated_at`

2. [ ] Add `key` property that generates unique identifier (e.g., `extattr_{project_id}_{id}`)

3. [ ] Add `protected: bool = False` field for protection tracking

4. [ ] Update `Environment` model to add `extended_attributes_id: Optional[int]` field

5. [ ] Update `Environment` model to add `extended_attributes_key: Optional[str]` field (populated during linking)

6. [ ] Update `Project` model to add `extended_attributes: list[ExtendedAttributes] = []` field

7. [ ] Run typecheck: `cd importer && pyright models.py`

### Sprint 1: API Fetching

8. [ ] Add `_fetch_extended_attributes()` method to `importer/fetcher.py`

9. [ ] Fetch from `/api/v3/accounts/{account_id}/extended-attributes/` endpoint

10. [ ] Parse response into `ExtendedAttributes` model instances

11. [ ] Link extended attributes to environments via `extended_attributes_id` matching

12. [ ] Populate `environment.extended_attributes_key` when linking

13. [ ] Add extended attributes to project's `extended_attributes` list

14. [ ] Handle environments with no extended attributes gracefully

15. [ ] Add logging for extended attributes fetch: `log.info(f"Fetched {len(attrs)} extended attributes")`

### Sprint 2: Schema Updates

16. [ ] Update `schemas/v2.json` with `extendedAttributes` definition

17. [ ] Schema includes: `type`, `extended_attributes` (object), `protected` (boolean), environment reference

18. [ ] Validate schema with existing test suite

### Sprint 2: YAML Serialization

19. [ ] Update `importer/yaml_converter.py` to serialize extended attributes

20. [ ] Extended attributes nested under environments in YAML output:
    ```yaml
    environments:
      - name: Production
        extended_attributes:
          type: databricks
          catalog: unity
          protected: true
    ```

21. [ ] Update `importer/normalizer/core.py` to process extended attributes in normalization

22. [ ] Handle extended attributes in import mapping

### Unit Tests

23. [ ] Test: ExtendedAttributes model instantiation and key generation

24. [ ] Test: Environment linking via extended_attributes_id

25. [ ] Test: YAML serialization includes extended attributes

26. [ ] Test: YAML deserialization restores extended attributes

27. [ ] Test: Schema validation passes for extended attributes YAML

28. [ ] Test: Environments without extended attributes serialize correctly

## Context

### API Response Format
```json
{
  "data": [
    {
      "id": 123,
      "extended_attributes_id": 456,
      "project_id": 789,
      "state": 1,
      "extended_attributes": {
        "type": "databricks",
        "catalog": "unity",
        "schema": "analytics"
      },
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

### YAML Output Format
```yaml
projects:
  - name: Analytics
    id: 789
    environments:
      - name: Production
        id: 101
        extended_attributes:
          type: databricks
          catalog: unity
          schema: analytics
          protected: false
```

## Notes

- Phase 2 will add Web UI display (entity table, detail views)
- Phase 3 will add interaction, dependencies, and editor
- Phase 4 will add Terraform modules and protection cascade
