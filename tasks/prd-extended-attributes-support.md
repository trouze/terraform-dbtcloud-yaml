# PRD: Extended Attributes Support

## Overview

Add comprehensive support for dbt Cloud Extended Attributes across the terraform-dbtcloud-yaml importer, web UI, and Terraform modules. Extended attributes allow users to override connection details or credentials at the environment level using a flexible JSON structure.

### What are Extended Attributes?

Extended attributes are a dbt Cloud feature that allows overriding connection configuration at the environment level. They are:
- **Project-scoped**: Created under a project via `/v3/accounts/{account_id}/projects/{project_id}/extended-attributes/`
- **Environment-linked**: Environments reference them via `extended_attributes_id`
- **Flexible JSON**: The `extended_attributes` field is a JSON object with adapter-specific keys (e.g., `catalog`, `http_path`, `type`)
- **Override mechanism**: Values override connection details or credentials set on the environment or project

### Terraform Resource Reference

```hcl
resource "dbtcloud_extended_attributes" "example" {
  project_id = var.project_id
  state      = 1  # 1 = active, 2 = inactive
  extended_attributes = jsonencode({
    type        = "databricks"
    catalog     = "dbt_catalog"
    http_path   = "/sql/your/http/path"
    nested_field = {
      subfield = "value"
    }
  })
}

resource "dbtcloud_environment" "example" {
  # ... other fields ...
  extended_attributes_id = dbtcloud_extended_attributes.example.extended_attributes_id
}
```

### API Structure

```json
{
  "id": 12345,
  "state": 1,
  "account_id": 86165,
  "project_id": 123,
  "extended_attributes": {
    "type": "databricks",
    "catalog": "unity_catalog",
    "http_path": "/sql/1.0/warehouses/abc123"
  }
}
```

---

## User Stories

### Phase 1: Data Model & Fetching

#### US-1.1: Extended Attributes Model
**As a** developer  
**I want** an `ExtendedAttributes` Pydantic model  
**So that** extended attributes data can be represented in the internal model

**Acceptance Criteria:**
- [ ] Create `ExtendedAttributes` class in `importer/models.py`
- [ ] Fields: `id`, `key`, `project_id`, `state`, `extended_attributes` (Dict), `metadata`
- [ ] Model supports serialization to/from JSON
- [ ] Model validates state values (1=active, 2=inactive)

**Technical Notes:**
```python
class ExtendedAttributes(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    project_id: int
    state: int = 1  # 1=active, 2=inactive
    extended_attributes: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

#### US-1.2: Environment Model Update
**As a** developer  
**I want** the `Environment` model to include `extended_attributes_id` and `extended_attributes_key`  
**So that** environments can reference their extended attributes

**Acceptance Criteria:**
- [ ] Add `extended_attributes_id: Optional[int]` to `Environment` model
- [ ] Add `extended_attributes_key: Optional[str]` to `Environment` model
- [ ] Existing tests continue to pass
- [ ] Model serialization includes new fields

#### US-1.3: Project Model Update
**As a** developer  
**I want** the `Project` model to include a list of extended attributes  
**So that** project-level extended attributes are captured

**Acceptance Criteria:**
- [ ] Add `extended_attributes: List[ExtendedAttributes]` to `Project` model
- [ ] Default to empty list for backward compatibility

#### US-1.4: Fetch Extended Attributes
**As a** user  
**I want** extended attributes to be fetched from the dbt Cloud API  
**So that** I can see and migrate extended attributes configuration

**Acceptance Criteria:**
- [ ] Create `_fetch_extended_attributes()` function in `importer/fetcher.py`
- [ ] Fetch from `/v3/accounts/{account_id}/projects/{project_id}/extended-attributes/`
- [ ] Handle pagination if needed
- [ ] Filter out deleted resources (state=2) unless explicitly included
- [ ] Generate unique keys using slugified project name + index or identifier
- [ ] Link to environments via `extended_attributes_id` matching

**Technical Notes:**
```python
def _fetch_extended_attributes(
    client: DbtCloudClient,
    project_id: int,
    progress: Optional[FetchProgressCallback] = None,
) -> List[ExtendedAttributes]:
    """Fetch extended attributes for a project."""
```

#### US-1.5: Link Extended Attributes to Environments
**As a** developer  
**I want** fetched environments to be linked to their extended attributes  
**So that** the relationship is preserved in the data model

**Acceptance Criteria:**
- [ ] During environment fetch, capture `extended_attributes_id` from API response
- [ ] After fetching extended attributes, populate `extended_attributes_key` on environments
- [ ] Handle environments without extended attributes (null/0 ID)

---

### Phase 2: YAML Schema & Serialization

#### US-2.1: Update YAML Schema (v2.json)
**As a** user  
**I want** the YAML schema to support extended attributes  
**So that** my configuration files validate correctly

**Acceptance Criteria:**
- [ ] Add `extendedAttributes` definition to `$defs` in `schemas/v2.json`
- [ ] Add `extended_attributes` array to environment schema
- [ ] Add `extended_attributes_key` optional field to environment
- [ ] Schema validates JSON object structure for `extended_attributes` field

**Schema Definition:**
```json
"extendedAttributes": {
  "type": "object",
  "properties": {
    "key": { "$ref": "#/$defs/slug" },
    "state": {
      "type": "integer",
      "enum": [1, 2],
      "default": 1,
      "description": "1 = active, 2 = inactive"
    },
    "extended_attributes": {
      "type": "object",
      "description": "JSON object with adapter-specific override keys",
      "additionalProperties": true
    }
  },
  "required": ["key", "extended_attributes"],
  "additionalProperties": false
}
```

#### US-2.2: Environment Schema Update
**As a** user  
**I want** environments to reference extended attributes in YAML  
**So that** the configuration captures the relationship

**Acceptance Criteria:**
- [ ] Add `extended_attributes` inline object to environment schema
- [ ] Support both inline definition and key reference
- [ ] Validate that referenced keys exist

**Example YAML:**
```yaml
environments:
  - key: production
    name: Production
    type: deployment
    connection: snowflake_prod
    credential:
      token_name: prod_token
      schema: analytics
    extended_attributes:
      type: snowflake
      catalog: unity_catalog
      warehouse: COMPUTE_WH
```

#### US-2.3: YAML Converter Update
**As a** developer  
**I want** the YAML converter to serialize extended attributes  
**So that** fetched data exports correctly to YAML

**Acceptance Criteria:**
- [ ] Update `importer/yaml_converter.py` to include extended attributes
- [ ] Extended attributes serialized inline on environments
- [ ] Empty extended attributes omitted from output
- [ ] JSON values properly formatted in YAML

---

### Phase 3: Web UI - Explore & Display

#### US-3.1: Extended Attributes in Entity Table
**As a** user  
**I want** to see extended attributes in the Entities tab  
**So that** I can browse all extended attributes in my account

**Acceptance Criteria:**
- [ ] Add "Extended Attributes" as a resource type in entity table
- [ ] Display columns: Name/Key, Project, State, Attributes Preview
- [ ] Attributes preview shows truncated JSON (first 50 chars)
- [ ] Clicking row shows full details

**Filter Integration:**
- [ ] Add "extended_attributes" to resource type filter dropdown
- [ ] Filter works with existing search functionality

#### US-3.2: Extended Attributes in Environment Details
**As a** user  
**I want** to see extended attributes when viewing environment details  
**So that** I understand the complete environment configuration

**Acceptance Criteria:**
- [ ] Environment detail view shows "Extended Attributes" section
- [ ] Display linked extended attributes key and preview
- [ ] Show "None" or hide section if no extended attributes
- [ ] Link to full extended attributes detail view

#### US-3.3: Extended Attributes Detail Dialog
**As a** user  
**I want** to view full extended attributes details in a dialog  
**So that** I can see the complete JSON configuration

**Acceptance Criteria:**
- [ ] Dialog shows extended attributes key, project, state
- [ ] Full JSON displayed in formatted, syntax-highlighted view
- [ ] Copy to clipboard button for JSON
- [ ] List of environments using these extended attributes

#### US-3.4: Resource Counts Include Extended Attributes
**As a** user  
**I want** extended attributes counted in resource summaries  
**So that** I have accurate counts of all resources

**Acceptance Criteria:**
- [ ] Fetch summary shows extended attributes count
- [ ] Header resource counts include extended_attributes
- [ ] Charts include extended attributes where relevant

---

### Phase 4: Web UI - Scope & Selection

#### US-4.1: Extended Attributes in Scope Selection
**As a** user  
**I want** to include/exclude extended attributes from migration scope  
**So that** I control what gets migrated

**Acceptance Criteria:**
- [ ] Add "Extended Attributes" toggle in resource filters
- [ ] Default to included (matches environment behavior)
- [ ] Selection cascades: selecting environment selects its extended attributes
- [ ] Deselecting extended attributes warns about environment dependency

#### US-4.2: Extended Attributes Selection Cascade
**As a** user  
**I want** extended attributes auto-selected when I select an environment  
**So that** dependent resources are included automatically

**Acceptance Criteria:**
- [ ] When environment is selected, its extended attributes are auto-selected
- [ ] Visual indicator shows "auto-selected due to dependency"
- [ ] User can manually deselect (with warning)
- [ ] Cascade logic documented

---

### Phase 5: Web UI - Matching

#### US-5.1: Extended Attributes Matching
**As a** user  
**I want** to match source extended attributes to target extended attributes  
**So that** I can reuse existing configuration

**Acceptance Criteria:**
- [ ] Extended attributes appear in match grid
- [ ] Match suggestions based on:
  - Same project name + same JSON content hash
  - Same project name + similar JSON keys
- [ ] Manual matching supported via dropdown
- [ ] "Create new" option for unmatched

#### US-5.2: Extended Attributes Match Validation
**As a** user  
**I want** validation of extended attributes matches  
**So that** I avoid configuration conflicts

**Acceptance Criteria:**
- [ ] Warn if matched extended attributes have different JSON keys
- [ ] Show diff between source and target JSON
- [ ] Validate state consistency (active/inactive)

---

### Phase 6: Web UI - Credentials Editor

#### US-6.1: Extended Attributes JSON Editor
**As a** user  
**I want** to edit extended attributes using a JSON editor  
**So that** I can modify the raw configuration

**Acceptance Criteria:**
- [ ] JSON editor component with syntax highlighting
- [ ] Real-time JSON validation
- [ ] Error messages for invalid JSON
- [ ] Pretty-print / minify toggle
- [ ] Undo/redo support

**Technical Notes:**
- Use `nicegui` code editor or monaco-editor integration
- Validate JSON on blur and before save

#### US-6.2: Extended Attributes Key-Value Form
**As a** user  
**I want** to edit extended attributes using a key-value form  
**So that** I can easily add/modify fields without writing JSON

**Acceptance Criteria:**
- [ ] Dynamic form with add/remove field buttons
- [ ] Field types: string, number, boolean, nested object
- [ ] Nested objects shown as expandable sections
- [ ] Changes sync to JSON view in real-time

#### US-6.3: Extended Attributes Editor Toggle
**As a** user  
**I want** to toggle between JSON and form views  
**So that** I can use whichever is more convenient

**Acceptance Criteria:**
- [ ] Toggle button: "JSON" / "Form" views
- [ ] State preserved when switching views
- [ ] Invalid JSON prevents switch to form view
- [ ] Form changes reflected in JSON immediately

#### US-6.4: Extended Attributes in Target Credentials Page
**As a** user  
**I want** to configure extended attributes in the Target Credentials step  
**So that** I can set up environment overrides during migration

**Acceptance Criteria:**
- [ ] Extended Attributes section in Target Credentials page
- [ ] Grouped by project, then by environment
- [ ] Shows source values as reference
- [ ] Edit dialog with JSON/form toggle
- [ ] Save to .env or state

---

### Phase 7: Terraform Modules

#### US-7.1: Extended Attributes Terraform Module
**As a** user  
**I want** a Terraform module for extended attributes  
**So that** I can manage them via IaC

**Acceptance Criteria:**
- [ ] Create `modules/extended_attributes/` directory
- [ ] `main.tf`: Creates `dbtcloud_extended_attributes` resources
- [ ] `variables.tf`: Input variables for extended attributes data
- [ ] `outputs.tf`: Output extended_attributes_ids map
- [ ] Support for_each over list of extended attributes

**Module Structure:**
```
modules/extended_attributes/
├── main.tf
├── variables.tf
└── outputs.tf
```

**main.tf:**
```hcl
resource "dbtcloud_extended_attributes" "extended_attrs" {
  for_each = {
    for attr in var.extended_attributes_data :
    attr.key => attr
  }

  project_id          = var.project_id
  state               = lookup(each.value, "state", 1)
  extended_attributes = jsonencode(each.value.extended_attributes)
}
```

#### US-7.2: Update Environments Module
**As a** user  
**I want** the environments module to accept extended_attributes_ids  
**So that** environments can reference extended attributes

**Acceptance Criteria:**
- [ ] Add `extended_attributes_ids` variable (map of env_key -> id)
- [ ] Update `dbtcloud_environment` resource to include `extended_attributes_id`
- [ ] Handle null/missing gracefully
- [ ] Update module documentation

**variables.tf addition:**
```hcl
variable "extended_attributes_ids" {
  description = "Map of environment keys to extended attributes IDs"
  type        = map(number)
  default     = {}
}
```

**main.tf update:**
```hcl
resource "dbtcloud_environment" "environments" {
  # ... existing fields ...
  extended_attributes_id = lookup(var.extended_attributes_ids, each.key, null)
}
```

#### US-7.3: Terraform Generation Updates
**As a** user  
**I want** the Terraform generator to create extended attributes resources  
**So that** my migration includes all configuration

**Acceptance Criteria:**
- [ ] Generate extended_attributes module calls in output
- [ ] Generate proper variable references
- [ ] Handle import blocks for existing extended attributes
- [ ] Order: extended_attributes before environments (dependency)

---

### Phase 8: Normalizer & Converter

#### US-8.1: Normalizer Extended Attributes Support
**As a** developer  
**I want** the normalizer to process extended attributes  
**So that** they are included in normalized output

**Acceptance Criteria:**
- [ ] Update `importer/normalizer/core.py` to handle extended attributes
- [ ] Generate unique keys for extended attributes
- [ ] Handle ID stripping based on options
- [ ] Preserve JSON structure in extended_attributes field

#### US-8.2: Import Mapping for Extended Attributes
**As a** user  
**I want** extended attributes in the importer mapping  
**So that** I can see the mapping between source and target

**Acceptance Criteria:**
- [ ] Add extended_attributes section to `importer_mapping.yml`
- [ ] Include element_type_code for filtering
- [ ] Generate appropriate Terraform import addresses

---

### Phase 9: Reporting

#### US-9.1: Extended Attributes in Reports
**As a** user  
**I want** extended attributes included in fetch reports  
**So that** I have complete documentation

**Acceptance Criteria:**
- [ ] Summary report includes extended attributes count
- [ ] Detailed report lists extended attributes by project
- [ ] Report shows JSON keys (not full values for security)

#### US-9.2: Extended Attributes in Report Items
**As a** developer  
**I want** extended attributes as report items  
**So that** they appear in the entity table

**Acceptance Criteria:**
- [ ] Add extended_attributes to report item generation
- [ ] Include: key, project_name, state, attributes_preview
- [ ] Element type code: "EXT" or "EXTATTR"

---

## Testing Requirements

### Unit Tests

#### Test Suite: Models (`test/test_models.py` - new file)
- [ ] `test_extended_attributes_model_creation`
- [ ] `test_extended_attributes_serialization`
- [ ] `test_extended_attributes_state_validation`
- [ ] `test_environment_with_extended_attributes`
- [ ] `test_project_with_extended_attributes`

#### Test Suite: Fetcher (`test/test_fetcher_extended_attributes.py` - new file)
- [ ] `test_fetch_extended_attributes_success`
- [ ] `test_fetch_extended_attributes_empty`
- [ ] `test_fetch_extended_attributes_pagination`
- [ ] `test_fetch_extended_attributes_filters_deleted`
- [ ] `test_extended_attributes_linked_to_environments`
- [ ] `test_fetch_with_api_error_handling`

#### Test Suite: YAML Converter (`test/test_yaml_converter.py` - update)
- [ ] `test_convert_with_extended_attributes`
- [ ] `test_convert_environment_extended_attributes_inline`
- [ ] `test_convert_empty_extended_attributes_omitted`

#### Test Suite: Normalizer (`test/test_normalizer.py` - update)
- [ ] `test_normalize_extended_attributes`
- [ ] `test_normalize_extended_attributes_key_generation`
- [ ] `test_normalize_extended_attributes_id_stripping`

### Integration Tests

#### Test Suite: End-to-End Fetch (`test/e2e_test/`)
- [ ] `test_e2e_fetch_with_extended_attributes`
- [ ] `test_e2e_extended_attributes_in_yaml_output`
- [ ] `test_e2e_extended_attributes_terraform_generation`

#### Test Suite: Terraform Module (`test/terraform_test.go` - update)
- [ ] `TestExtendedAttributesModuleCreation`
- [ ] `TestExtendedAttributesEnvironmentLinking`
- [ ] `TestExtendedAttributesImport`

### Web UI Tests

#### Test Suite: Web Components (`importer/web/tests/`)
- [ ] `test_extended_attributes_entity_display`
- [ ] `test_extended_attributes_filter`
- [ ] `test_extended_attributes_environment_detail`
- [ ] `test_extended_attributes_json_editor`
- [ ] `test_extended_attributes_form_editor`
- [ ] `test_extended_attributes_editor_toggle`

### Schema Validation Tests

#### Test Suite: Schema (`test/schema_validation_test.py` - update)
- [ ] `test_schema_extended_attributes_valid`
- [ ] `test_schema_extended_attributes_missing_required`
- [ ] `test_schema_environment_with_extended_attributes`
- [ ] `test_schema_extended_attributes_nested_json`

### Test Fixtures

Create test fixtures in `test/fixtures/`:
- [ ] `extended_attributes_sample.json` - API response mock
- [ ] `environment_with_extended_attributes.json` - Environment with linked attrs
- [ ] `extended_attributes_config.yml` - YAML config example

---

## File Changes Summary

### New Files
| File | Description |
|------|-------------|
| `modules/extended_attributes/main.tf` | Terraform resource definitions |
| `modules/extended_attributes/variables.tf` | Module input variables |
| `modules/extended_attributes/outputs.tf` | Module outputs |
| `importer/web/components/extended_attributes_editor.py` | JSON/Form editor component |
| `test/test_models.py` | Model unit tests |
| `test/test_fetcher_extended_attributes.py` | Fetcher tests |
| `test/fixtures/extended_attributes_sample.json` | Test fixture |
| `test/fixtures/extended_attributes_config.yml` | Test fixture |

### Modified Files
| File | Changes |
|------|---------|
| `importer/models.py` | Add ExtendedAttributes model, update Environment/Project |
| `importer/fetcher.py` | Add _fetch_extended_attributes, update environment linking |
| `importer/yaml_converter.py` | Extended attributes serialization |
| `importer/normalizer/core.py` | Extended attributes normalization |
| `importer/reporter.py` | Extended attributes in reports |
| `schemas/v2.json` | Extended attributes schema definition |
| `importer_mapping.yml` | Extended attributes mapping |
| `modules/environments/main.tf` | Add extended_attributes_id |
| `modules/environments/variables.tf` | Add extended_attributes_ids variable |
| `importer/web/state.py` | Extended attributes state tracking |
| `importer/web/pages/explore.py` | Extended attributes display |
| `importer/web/pages/target_credentials.py` | Extended attributes editing |
| `importer/web/components/entity_table.py` | Extended attributes rows |
| `importer/web/utils/yaml_viewer.py` | Extended attributes preview |
| `test/test_normalizer.py` | Extended attributes test cases |
| `test/schema_validation_test.py` | Extended attributes validation |

---

## Implementation Order

### Sprint 1: Foundation
1. US-1.1: Extended Attributes Model
2. US-1.2: Environment Model Update
3. US-1.3: Project Model Update
4. US-1.4: Fetch Extended Attributes
5. US-1.5: Link Extended Attributes to Environments

### Sprint 2: YAML & Schema
1. US-2.1: Update YAML Schema
2. US-2.2: Environment Schema Update
3. US-2.3: YAML Converter Update
4. US-8.1: Normalizer Support
5. US-8.2: Import Mapping

### Sprint 3: Web UI Display
1. US-3.1: Entity Table Integration
2. US-3.2: Environment Details
3. US-3.3: Detail Dialog
4. US-3.4: Resource Counts
5. US-9.1: Reports
6. US-9.2: Report Items

### Sprint 4: Web UI Interaction
1. US-4.1: Scope Selection
2. US-4.2: Selection Cascade
3. US-5.1: Matching
4. US-5.2: Match Validation

### Sprint 5: Editor & Terraform
1. US-6.1: JSON Editor
2. US-6.2: Key-Value Form
3. US-6.3: Editor Toggle
4. US-6.4: Target Credentials Integration
5. US-7.1: Terraform Module
6. US-7.2: Environments Module Update
7. US-7.3: Terraform Generation

---

## Success Metrics

- [ ] All existing tests pass (no regressions)
- [ ] Extended attributes fetched for all test accounts
- [ ] YAML output validates against updated schema
- [ ] Terraform plan succeeds with extended attributes
- [ ] Web UI displays extended attributes correctly
- [ ] Editor saves valid JSON configuration
- [ ] Migration preserves extended attributes configuration

---

## Open Questions

1. **Shared Extended Attributes**: Can multiple environments share the same extended_attributes_id? (Current assumption: yes, handle in UI)

2. **Secret Handling**: Should extended_attributes JSON values be treated as potentially sensitive? (Recommendation: yes, mask in reports)

3. **Backward Compatibility**: How to handle YAML files without extended_attributes section? (Current approach: optional, empty = no extended attributes)

4. **Import Behavior**: When importing existing environments, should we auto-discover their extended attributes? (Recommendation: yes)

---

## References

- [Terraform Provider Docs: Extended Attributes](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/extended_attributes)
- [terraform-provider-dbtcloud/pkg/dbt_cloud/extended_attributes.go](../../../terraform-provider-dbtcloud/pkg/dbt_cloud/extended_attributes.go)
- [terraform-provider-dbtcloud/pkg/framework/objects/extended_attributes/](../../../terraform-provider-dbtcloud/pkg/framework/objects/extended_attributes/)
