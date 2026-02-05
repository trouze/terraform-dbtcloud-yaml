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

## Phase 10: Resource Protection Integration

Extended attributes must integrate with the **cascade protection system** defined in `prd-web-ui-09-resource-protection.md` (Section 4.8).

### Cascade Chain Position

Extended Attributes are **project-scoped** resources, so they follow the cascade pattern:

| Resource Type | Parent Chain | Example |
|--------------|--------------|---------|
| Extended Attributes | PRJ | Protect "prod_databricks_config" → protect "Analytics" project |

Additionally, since **Environments reference Extended Attributes** via `extended_attributes_id`:
- Protecting an Environment should prompt to also protect its linked Extended Attributes
- This creates a **sibling dependency** (ENV and EXTATTR both cascade to PRJ)

### US-10.1: Extended Attributes Protection Field
**As a** user  
**I want** to mark extended attributes as protected  
**So that** Terraform prevents accidental destruction

**Acceptance Criteria:**
- [ ] Add `protected: boolean` field to extended attributes in YAML schema
- [ ] Protection checkbox column appears in match grid for extended attributes
- [ ] Default to protected=true for adopted extended attributes
- [ ] Shield icon and blue row styling for protected extended attributes

**Schema Addition:**
```json
"extendedAttributes": {
  "type": "object",
  "properties": {
    "key": { "$ref": "#/$defs/slug" },
    "protected": {
      "type": ["boolean", "null"],
      "default": false,
      "description": "If true, Terraform will prevent this resource from being destroyed"
    },
    "extended_attributes": {
      "type": "object",
      "additionalProperties": true
    }
  }
}
```

### US-10.2: Protected Extended Attributes Terraform Block
**As a** user  
**I want** protected extended attributes in a separate Terraform resource block  
**So that** they have `lifecycle { prevent_destroy = true }`

**Acceptance Criteria:**
- [ ] Create `dbtcloud_extended_attributes.protected_extended_attrs` resource block
- [ ] Protected extended attributes use `lifecycle { prevent_destroy = true }`
- [ ] Unprotected extended attributes use standard resource block
- [ ] Both blocks have identical configuration except lifecycle

**Terraform Implementation:**
```hcl
locals {
  protected_extended_attrs_map = {
    for key, item in local.extended_attrs_map :
    key => item
    if try(item.protected, false) == true
  }
  
  unprotected_extended_attrs_map = {
    for key, item in local.extended_attrs_map :
    key => item
    if try(item.protected, false) != true
  }
}

resource "dbtcloud_extended_attributes" "extended_attrs" {
  for_each = local.unprotected_extended_attrs_map
  
  project_id          = each.value.project_id
  state               = lookup(each.value, "state", 1)
  extended_attributes = jsonencode(each.value.extended_attributes)
}

resource "dbtcloud_extended_attributes" "protected_extended_attrs" {
  for_each = local.protected_extended_attrs_map
  
  project_id          = each.value.project_id
  state               = lookup(each.value, "state", 1)
  extended_attributes = jsonencode(each.value.extended_attributes)
  
  lifecycle {
    prevent_destroy = true
  }
}
```

### US-10.3: Protection Manager Extended Attributes Support
**As a** developer  
**I want** the protection manager to handle extended attributes  
**So that** protection changes generate correct moved blocks and cascade correctly

**Acceptance Criteria:**
- [ ] Add "EXTATTR" resource type to `protection_manager.py`
- [ ] `get_resource_addresses()` returns correct addresses for extended attributes
- [ ] `detect_protection_changes()` detects extended attributes protection changes
- [ ] `generate_moved_blocks()` generates valid moved blocks for extended attributes
- [ ] `get_resources_to_protect()` returns EXTATTR + [PRJ] for cascade
- [ ] `get_resources_to_unprotect()` includes extended attributes when unprotecting PRJ

**Code Addition to `protection_manager.py`:**
```python
# Add to type_map in get_resource_addresses()
type_map = {
    "PRJ": ("dbtcloud_project", "projects", "protected_projects"),
    "ENV": ("dbtcloud_environment", "environments", "protected_environments"),
    "JOB": ("dbtcloud_job", "jobs", "protected_jobs"),
    "REP": ("dbtcloud_repository", "repositories", "protected_repositories"),
    "CRD": ("dbtcloud_credential", "credentials", "protected_credentials"),
    "VAR": ("dbtcloud_environment_variable", "env_vars", "protected_env_vars"),
    "EXTATTR": ("dbtcloud_extended_attributes", "extended_attrs", "protected_extended_attrs"),
}

# Add to PARENT_CHAIN for cascade protection
PARENT_CHAIN = {
    "JOB": ["ENV", "PRJ"],
    "CRD": ["ENV", "PRJ"],
    "ENV": ["PRJ"],
    "VAR": ["PRJ"],
    "REP": ["PRJ"],  # For project-linked repos
    "EXTATTR": ["PRJ"],  # Extended attributes cascade to project
}
```

### US-10.4: Cascade Protection - Extended Attributes to Project
**As a** user  
**I want** protecting extended attributes to cascade to its parent project  
**So that** the project isn't deleted (which would destroy the extended attributes)

**Acceptance Criteria:**
- [ ] Clicking protect on Extended Attributes shows cascade dialog
- [ ] Dialog lists: "To protect 'prod_databricks_config', these parents must also be protected: [Analytics project]"
- [ ] "Protect All (2)" button protects both EXTATTR and PRJ
- [ ] "Cancel" button cancels without protecting anything
- [ ] If PRJ already protected, skip cascade dialog

**UI Flow:**
```
[Cascade Protection Dialog]
  To protect "prod_databricks_config", these parents must also be protected:
  
  ☑ Analytics (Project)
  
  [Cancel] [Protect All (2)]
```

### US-10.5: Environment Protection with Linked Extended Attributes
**As a** user  
**I want** protecting an environment to prompt about its linked extended attributes  
**So that** I don't accidentally leave dependencies unprotected

**Acceptance Criteria:**
- [ ] When protecting ENV that has `extended_attributes_id`, include EXTATTR in cascade
- [ ] Cascade chain becomes: ENV → EXTATTR (sibling) + PRJ (parent)
- [ ] Dialog shows: "To protect 'Production', these resources must also be protected: [prod_databricks_config (Extended Attrs), Analytics (Project)]"
- [ ] Extended attributes shown with "(linked)" indicator

**Updated Cascade for Environment:**
```python
# When protecting an environment with extended_attributes_id:
# 1. Standard cascade: ENV → PRJ
# 2. Plus linked resources: EXTATTR (if extended_attributes_id is set)

def get_resources_to_protect(resource_type: str, resource_key: str, yaml_config: dict):
    resources = [{"type": resource_type, "key": resource_key}]
    
    # Standard parent cascade
    for parent_type in PARENT_CHAIN.get(resource_type, []):
        parent = find_parent(resource_type, resource_key, parent_type, yaml_config)
        if parent:
            resources.append(parent)
    
    # Special case: ENV with linked EXTATTR
    if resource_type == "ENV":
        env = find_resource("ENV", resource_key, yaml_config)
        if env and env.get("extended_attributes_key"):
            resources.append({
                "type": "EXTATTR", 
                "key": env["extended_attributes_key"],
                "reason": "linked"
            })
    
    return resources
```

### US-10.6: Unprotect Project with Extended Attributes Children
**As a** user  
**I want** unprotecting a project to prompt about protected extended attributes  
**So that** I can cascade unprotect or leave children protected

**Acceptance Criteria:**
- [ ] Unprotecting PRJ checks for protected EXTATTR children
- [ ] Dialog: "Would you like to unprotect the children as well?"
- [ ] "Unprotect All (N)" removes protection from PRJ and all EXTATTR
- [ ] "Unprotect This Only" removes protection from PRJ only, EXTATTR stays protected

### US-10.7: Protected Extended Attributes in Deploy Panel
**As a** user  
**I want** to see protected extended attributes in the Deploy page panel  
**So that** I know which extended attributes are protected

**Acceptance Criteria:**
- [ ] Protected extended attributes listed in "Protected Resources" panel
- [ ] Shows: Name/Key, Type (EXTATTR), Project
- [ ] "Remove Protection" button available
- [ ] Warning when removing protection: "Environments may still reference this"

### US-10.8: Match Grid Protection Column for Extended Attributes
**As a** user  
**I want** to see and toggle protection for extended attributes in the match grid  
**So that** I can manage protection alongside other resources

**Acceptance Criteria:**
- [ ] Protection checkbox column (🛡️) shows for EXTATTR rows
- [ ] Clicking checkbox triggers cascade dialog (EXTATTR → PRJ)
- [ ] Protected EXTATTR rows have blue left border styling
- [ ] Row shows shield icon when protected

---

## Phase 12: Destroy Page Integration

Extended attributes must integrate with the Destroy page refactor defined in `prd-web-ui-10-destroy-page-refactor.md`.

### US-12.1: Extended Attributes in Terraform Address Mapping
**As a** developer  
**I want** extended attributes in the Terraform address mapping  
**So that** the destroy page can generate correct Terraform commands

**Acceptance Criteria:**
- [ ] Add `EXTATTR` -> `dbtcloud_extended_attributes` to address mapping
- [ ] Protected EXTATTR uses `dbtcloud_extended_attributes.protected_extended_attrs`
- [ ] Unprotected EXTATTR uses `dbtcloud_extended_attributes.extended_attrs`

**Code Addition to `destroy.py`:**
```python
# Add to Terraform address mapping
TERRAFORM_TYPE_MAP = {
    "PRJ": "dbtcloud_project",
    "ENV": "dbtcloud_environment",
    "JOB": "dbtcloud_job",
    "REP": "dbtcloud_repository",
    "CON": "dbtcloud_connection",
    "EXTATTR": "dbtcloud_extended_attributes",
}

# For protected resources
PROTECTED_RESOURCE_MAP = {
    "PRJ": ("dbtcloud_project", "protected_projects"),
    "ENV": ("dbtcloud_environment", "protected_environments"),
    "JOB": ("dbtcloud_job", "protected_jobs"),
    "REP": ("dbtcloud_repository", "protected_repositories"),
    "EXTATTR": ("dbtcloud_extended_attributes", "protected_extended_attrs"),
}
```

### US-12.2: Extended Attributes in Type Filter Dropdowns
**As a** Terraform operator  
**I want** to filter by Extended Attributes type on the Destroy page  
**So that** I can find and manage extended attributes resources

**Acceptance Criteria:**
- [ ] "Extended Attributes" option appears in Protected Resources type filter
- [ ] "Extended Attributes" option appears in Destroy Resources type filter
- [ ] Filtering by type shows only EXTATTR resources
- [ ] Type label displays as "Extended Attributes" (not "EXTATTR")

### US-12.3: Protected Extended Attributes in Panel
**As a** Terraform operator  
**I want** to see protected extended attributes in the Protected Resources panel  
**So that** I know which extended attributes are protected from destruction

**Acceptance Criteria:**
- [ ] Protected EXTATTR appears in Protected Resources table
- [ ] Row shows: Type="Extended Attributes", Name/Key, ID
- [ ] Clicking row opens detail dialog with all attributes
- [ ] Can select EXTATTR for bulk unprotection

### US-12.4: Extended Attributes Detail Dialog
**As a** Terraform operator  
**I want** to view extended attributes details in the detail popup  
**So that** I can verify the configuration before actions

**Acceptance Criteria:**
- [ ] Detail dialog shows resource type: "Extended Attributes"
- [ ] Shows key, project_id, state, and the JSON attributes
- [ ] Shows Terraform address: `module.dbt_cloud.dbtcloud_extended_attributes.extended_attrs["key"]`
- [ ] JSON attributes displayed in formatted/readable way

### US-12.5: Unprotect Extended Attributes from Destroy Page
**As a** Terraform operator  
**I want** to unprotect extended attributes from the Destroy page  
**So that** I can prepare them for destruction

**Acceptance Criteria:**
- [ ] Can select EXTATTR in Protected Resources panel
- [ ] "Unprotect Selected" removes protection from EXTATTR
- [ ] Unprotected EXTATTR moves to Destroy Resources table
- [ ] Warning shown if environments reference the EXTATTR

### US-12.6: Destroy/Taint Extended Attributes
**As a** Terraform operator  
**I want** to destroy or taint extended attributes  
**So that** I can tear down or refresh these resources

**Acceptance Criteria:**
- [ ] EXTATTR appears in Destroy Resources table
- [ ] Can select EXTATTR for targeted destroy
- [ ] "Taint Selected" generates: `terraform taint 'dbtcloud_extended_attributes.extended_attrs["key"]'`
- [ ] "Destroy Selected" generates: `terraform destroy -target='dbtcloud_extended_attributes.extended_attrs["key"]'`
- [ ] Warning when destroying EXTATTR that environments reference

### US-12.7: Cascade Warning for EXTATTR Destruction
**As a** Terraform operator  
**I want** a warning when destroying extended attributes referenced by environments  
**So that** I don't accidentally break environment configurations

**Acceptance Criteria:**
- [ ] Before destroying EXTATTR, check if any environments reference it
- [ ] Warning dialog: "This extended attributes is used by [N] environment(s): [list]. Destroying will set their extended_attributes_id to null."
- [ ] User can proceed or cancel
- [ ] Same warning for tainting

---

## Phase 11: Matching with Dependency Awareness

### US-11.1: Extended Attributes Match Dependency Indicator
**As a** user  
**I want** to see which environments depend on each extended attribute in the match grid  
**So that** I understand the impact of my matching decisions

**Acceptance Criteria:**
- [ ] Match grid shows "Used by N environments" for extended attributes
- [ ] Hover/click reveals list of dependent environment names
- [ ] If environment is matched but extended attributes is not, show warning
- [ ] Suggest matching extended attributes when matching environment

### US-11.2: Auto-Match Extended Attributes with Environments
**As a** user  
**I want** extended attributes auto-matched when I match an environment  
**So that** dependencies are preserved

**Acceptance Criteria:**
- [ ] When matching source environment to target environment:
  - Check if source has extended_attributes_id
  - Check if target has extended_attributes_id
  - Suggest matching source extended_attributes to target extended_attributes
- [ ] Auto-match option: "Also match linked extended attributes"
- [ ] Show diff between source and target extended_attributes JSON

### US-11.3: Orphan Extended Attributes Warning
**As a** user  
**I want** a warning when extended attributes would become orphaned  
**So that** I don't create unused resources

**Acceptance Criteria:**
- [ ] Warning when extended attributes are selected but no environment references them
- [ ] Option to: "Create anyway" or "Skip this extended attribute"
- [ ] Report orphaned extended attributes in validation summary

---

## Testing Requirements - Protection Integration

### Protection Unit Tests (`test/test_protection_extended_attributes.py`)

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| UT-EA-P01 | `get_resource_addresses()` with EXTATTR protected=True | Returns `protected_extended_attrs` address |
| UT-EA-P02 | `get_resource_addresses()` with EXTATTR protected=False | Returns `extended_attrs` address |
| UT-EA-P03 | `detect_protection_changes()` with EXTATTR protection added | Returns ProtectionChange with direction="protect" |
| UT-EA-P04 | `detect_protection_changes()` with EXTATTR protection removed | Returns ProtectionChange with direction="unprotect" |
| UT-EA-P05 | `generate_moved_blocks()` for EXTATTR protect | Generates valid HCL moved block |
| UT-EA-P06 | `generate_moved_blocks()` for EXTATTR unprotect | Generates reverse moved block |

### Cascade Protection Tests for Extended Attributes

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| CP-EA-01 | Protect Extended Attributes (has PRJ parent) | Dialog shows PRJ to be protected |
| CP-EA-02 | Confirm cascade protection on EXTATTR | EXTATTR and PRJ both marked protected |
| CP-EA-03 | Cancel cascade protection on EXTATTR | No resources protected |
| CP-EA-04 | Protect EXTATTR when PRJ already protected | No dialog, directly protected |
| CP-EA-05 | Protect Environment with linked EXTATTR | Dialog shows EXTATTR + PRJ chain |
| CP-EA-06 | `get_resources_to_protect()` with EXTATTR | Returns EXTATTR + [PRJ] |
| CP-EA-07 | `get_resources_to_protect()` with ENV+EXTATTR link | Returns ENV + [EXTATTR, PRJ] |
| CP-EA-08 | Unprotect PRJ with protected EXTATTR children | Dialog asks about cascade unprotect |
| CP-EA-09 | Choose "Unprotect All" on PRJ | PRJ and all EXTATTR children unprotected |
| CP-EA-10 | Choose "Unprotect This Only" on PRJ | Only PRJ unprotected, EXTATTR stays |
| CP-EA-11 | `get_resources_to_unprotect()` on PRJ | Returns all protected EXTATTR descendants |
| CP-EA-12 | Protected EXTATTR row styling in grid | Blue left border, subtle blue background |
| CP-EA-13 | Protection checkbox column for EXTATTR | Checkbox visible and functional |

### Protection Integration Tests - Terraform

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| IT-EA-P01 | Protected EXTATTR in YAML | EXTATTR in `protected_extended_attrs` block |
| IT-EA-P02 | Unprotected EXTATTR in YAML | EXTATTR in `extended_attrs` block |
| IT-EA-P03 | Mix of protected/unprotected EXTATTR | Split between both resource blocks |
| IT-EA-P04 | `terraform destroy` on protected EXTATTR | Fails with "prevent_destroy" error |
| IT-EA-P05 | `terraform apply` with moved block (protect EXTATTR) | Resource moved, not recreated |
| IT-EA-P06 | `terraform apply` with moved block (unprotect EXTATTR) | Resource moved, not recreated |

### Dependency & Selection Tests

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| DEP-EA-01 | Select environment with linked EXTATTR | EXTATTR auto-selected |
| DEP-EA-02 | Deselect EXTATTR while ENV selected | Warning dialog shown |
| DEP-EA-03 | EXTATTR becomes orphan (no ENV references) | Warning in validation |
| DEP-EA-04 | Match ENV with linked EXTATTR | Suggest matching EXTATTR too |

### Destroy Page Tests

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| DEST-EA-01 | EXTATTR in Terraform address mapping | Returns `dbtcloud_extended_attributes` |
| DEST-EA-02 | Protected EXTATTR address | Returns `protected_extended_attrs["key"]` |
| DEST-EA-03 | EXTATTR in type filter dropdown | "Extended Attributes" option present |
| DEST-EA-04 | Filter Protected Resources by EXTATTR | Shows only EXTATTR resources |
| DEST-EA-05 | Filter Destroy Resources by EXTATTR | Shows only EXTATTR resources |
| DEST-EA-06 | Protected EXTATTR in panel | Row shows type, key, ID |
| DEST-EA-07 | EXTATTR detail dialog | Shows JSON attributes formatted |
| DEST-EA-08 | Select and unprotect EXTATTR | Moves to Destroy Resources |
| DEST-EA-09 | Taint EXTATTR command | Correct `terraform taint` generated |
| DEST-EA-10 | Destroy EXTATTR command | Correct `terraform destroy -target` generated |
| DEST-EA-11 | Destroy EXTATTR with ENV reference | Warning dialog shown |
| DEST-EA-12 | Taint EXTATTR with ENV reference | Warning dialog shown |

---

## Updated File Changes Summary

### Additional New Files for Protection
| File | Description |
|------|-------------|
| `test/test_protection_extended_attributes.py` | Protection unit tests for extended attributes |

### Additional Modified Files for Protection
| File | Changes |
|------|---------|
| `schemas/v2.json` | Add `protected` field to extendedAttributes |
| `modules/extended_attributes/main.tf` | Split into protected/unprotected resource blocks |
| `importer/web/utils/protection_manager.py` | Add EXTATTR resource type, PARENT_CHAIN cascade |
| `importer/web/utils/dependency_analyzer.py` | Add environment→extended_attributes dependency |
| `importer/web/pages/match.py` | Extended attributes dependency indicators, cascade matching |
| `importer/web/pages/deploy.py` | Extended attributes in protected resources panel |
| `importer/web/components/match_grid.py` | "Used by N environments" column, protection checkbox for extended attributes |

### Additional Modified Files for Destroy Page (Sprint 7)
| File | Changes |
|------|---------|
| `importer/web/pages/destroy.py` | Add EXTATTR to TERRAFORM_TYPE_MAP and PROTECTED_RESOURCE_MAP |
| `importer/web/pages/destroy.py` | Add "Extended Attributes" to type filter dropdowns |
| `importer/web/pages/destroy.py` | EXTATTR detail dialog with formatted JSON |
| `importer/web/pages/destroy.py` | Cascade warning when destroying/tainting EXTATTR with ENV references |

---

## Updated Implementation Order

### Sprint 1: Foundation
1. US-1.1: Extended Attributes Model
2. US-1.2: Environment Model Update
3. US-1.3: Project Model Update
4. US-1.4: Fetch Extended Attributes
5. US-1.5: Link Extended Attributes to Environments

### Sprint 2: YAML & Schema
1. US-2.1: Update YAML Schema (including `protected` field)
2. US-2.2: Environment Schema Update
3. US-2.3: YAML Converter Update
4. US-8.1: Normalizer Support
5. US-8.2: Import Mapping

### Sprint 3: Web UI Display
1. US-3.1: Entity Table Integration
2. US-3.2: Environment Details (with extended attributes section)
3. US-3.3: Detail Dialog
4. US-3.4: Resource Counts
5. US-9.1: Reports
6. US-9.2: Report Items

### Sprint 4: Web UI Interaction & Dependencies
1. US-4.1: Scope Selection
2. US-4.2: Selection Cascade (including extended attributes as env dependency)
3. US-5.1: Matching
4. US-5.2: Match Validation
5. US-11.1: Dependency Indicators in Match Grid
6. US-11.2: Auto-Match with Environments
7. US-11.3: Orphan Warning

### Sprint 5: Editor & Terraform
1. US-6.1: JSON Editor
2. US-6.2: Key-Value Form
3. US-6.3: Editor Toggle
4. US-6.4: Target Credentials Integration
5. US-7.1: Terraform Module (with protected blocks)
6. US-7.2: Environments Module Update
7. US-7.3: Terraform Generation

### Sprint 6: Protection Integration
1. US-10.1: Protection Field in Schema
2. US-10.2: Protected Terraform Block
3. US-10.3: Protection Manager Support
4. US-10.4: Cascade Protection to Project
5. US-10.5: Environment Protection with Linked EXTATTR
6. US-10.6: Unprotect Project with EXTATTR Children
7. US-10.7: Deploy Panel Integration
8. US-10.8: Match Grid Protection Column

### Sprint 7: Destroy Page Integration
1. US-12.1: Terraform Address Mapping
2. US-12.2: Type Filter Dropdowns
3. US-12.3: Protected EXTATTR in Panel
4. US-12.4: Extended Attributes Detail Dialog
5. US-12.5: Unprotect EXTATTR from Destroy Page
6. US-12.6: Destroy/Taint Extended Attributes
7. US-12.7: Cascade Warning for EXTATTR Destruction

---

## References

- [Terraform Provider Docs: Extended Attributes](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/extended_attributes)
- [terraform-provider-dbtcloud/pkg/dbt_cloud/extended_attributes.go](../../../terraform-provider-dbtcloud/pkg/dbt_cloud/extended_attributes.go)
- [terraform-provider-dbtcloud/pkg/framework/objects/extended_attributes/](../../../terraform-provider-dbtcloud/pkg/framework/objects/extended_attributes/)
