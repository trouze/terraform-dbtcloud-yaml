# PRD: Web UI - Part 4: Map Step

## Introduction

The Map step of the dbt Cloud Importer Web UI. This allows users to interactively select which entities to include in the migration, configure normalization options, and run the normalize operation to generate Terraform-ready YAML.

This is **Part 4 of 5** in the Web UI PRD series.  
**Depends on:** Part 1 (Core Shell), Part 2 (Fetch), Part 3 (Explore)

## Goals

- Enable interactive selection of entities for migration
- Provide visual configuration of mapping/normalization options
- Execute normalization and display results
- Generate Terraform-ready YAML with user-controlled scope

## User Stories

### US-025: Select Entities for Migration
**Description:** As a user, I want to select which entities to include in the migration so that I can control what gets deployed.

**Acceptance Criteria:**
- [ ] Entity table shows checkbox column for selection
- [ ] Checkboxes reflect current `include_in_conversion` state
- [ ] Clicking checkbox toggles selection immediately
- [ ] Selection state persisted in session
- [ ] Batch operations available (see next story)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-026: Bulk Select/Deselect Entities
**Description:** As a user, I want to select or deselect multiple entities at once so that I can quickly adjust scope.

**Acceptance Criteria:**
- [ ] "Select All" button selects all visible (filtered) entities
- [ ] "Deselect All" button deselects all visible entities
- [ ] "Select by Type" dropdown for bulk type selection
- [ ] Options: Select all Connections, Select all Jobs, etc.
- [ ] "Invert Selection" button toggles all selections
- [ ] Selection count displayed (e.g., "127 of 423 selected")
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-027: Filter While Selecting
**Description:** As a user, I want to filter the entity list while selecting so that I can find and select specific items.

**Acceptance Criteria:**
- [ ] All Explore filters available (type filter, search)
- [ ] Selections persist when filters change
- [ ] Filtered-out items retain their selection state
- [ ] "Show selected only" toggle to see just selected items
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-028: Configure Scope Settings
**Description:** As a user, I want to configure the migration scope so that I can control which projects are included.

**Acceptance Criteria:**
- [ ] Scope mode selector: All Projects / Specific Projects / Account Level Only
- [ ] When "Specific Projects" selected, show project multi-select
- [ ] Project selector shows project names with entity counts
- [ ] Scope changes update the preview (see US-030)
- [ ] Settings map to `importer_mapping.yml` scope section
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-029: Configure Resource Filters
**Description:** As a user, I want to configure which resource types to include so that I can exclude entire categories.

**Acceptance Criteria:**
- [ ] Toggle switches for each resource type:
  - Connections, Repositories, Service Tokens, Groups
  - Projects, Environments, Jobs, Environment Variables
  - Notifications, Webhooks, PrivateLink Endpoints
- [ ] Toggles show count (e.g., "Connections (57)")
- [ ] Disabling a type deselects all entities of that type
- [ ] Settings map to `importer_mapping.yml` resource_filters
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-030: Preview Selected Entities
**Description:** As a user, I want to preview what will be included before normalizing so that I can verify my selections.

**Acceptance Criteria:**
- [ ] Preview panel shows summary of selected entities
- [ ] Grouped by type with counts
- [ ] Updates in real-time as selections change
- [ ] Warning if no entities selected
- [ ] Warning if dependencies are missing (e.g., job selected but not its environment)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-031: Configure Normalization Options
**Description:** As a user, I want to configure how entities are normalized so that I can control the output format.

**Acceptance Criteria:**
- [ ] Advanced options section (collapsible)
- [ ] Strip Source IDs toggle (default: on)
- [ ] Secret Handling selector: Redact / Omit / Placeholder
- [ ] Name Collision Strategy: Suffix / Error / Skip
- [ ] Settings map to `importer_mapping.yml` normalization_options
- [ ] Tooltips explain each option
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-032: Load Mapping Configuration
**Description:** As a user, I want to load an existing mapping config file so that I can reuse previous configurations.

**Acceptance Criteria:**
- [ ] "Load Config" button opens file browser
- [ ] Supports loading `importer_mapping.yml` files
- [ ] Loaded config populates all form fields
- [ ] Shows loaded filename
- [ ] Validation errors if config is malformed
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-033: Save Mapping Configuration
**Description:** As a user, I want to save my mapping configuration so that I can reuse it later.

**Acceptance Criteria:**
- [ ] "Save Config" button saves current settings to file
- [ ] Default filename: `importer_mapping.yml`
- [ ] File browser for custom location
- [ ] Overwrites existing file with confirmation
- [ ] Success notification with file path
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-034: Run Normalization
**Description:** As a user, I want to run the normalization step so that I can generate Terraform-ready YAML.

**Acceptance Criteria:**
- [ ] "Normalize" button triggers normalization
- [ ] Uses current selections and config settings
- [ ] Progress indicator during normalization
- [ ] Log output shown in terminal panel
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-035: View Normalization Results
**Description:** As a user, I want to see the results of normalization so that I can review what was generated.

**Acceptance Criteria:**
- [ ] Success panel shows generated files:
  - YAML file path and size
  - Lookups manifest (count of items needing resolution)
  - Exclusions report (count of excluded items)
- [ ] "View YAML" button shows preview (see US-036)
- [ ] "View Lookups" shows items needing manual resolution
- [ ] "View Exclusions" shows what was filtered out
- [ ] "Continue to Target" button navigates to next step
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-036: Preview Generated YAML
**Description:** As a user, I want to preview the generated YAML so that I can verify the output before deployment.

**Acceptance Criteria:**
- [ ] Modal or panel shows YAML content
- [ ] Syntax highlighting for YAML
- [ ] Collapsible sections by resource type
- [ ] Search within YAML content
- [ ] "Download" button to save locally
- [ ] "Copy" button to copy to clipboard
- [ ] Typecheck passes
- [ ] Verify in browser

## Functional Requirements

- **FR-1:** Map step must allow toggling `include_in_conversion` per entity
- **FR-2:** Bulk selection operations must work on filtered views
- **FR-3:** Scope and filter settings must map to `importer_mapping.yml` format
- **FR-4:** Normalization must call existing `importer.normalizer.normalize()` function
- **FR-5:** Generated YAML must be previewable in the UI
- **FR-6:** Lookups and exclusions reports must be displayed

## Non-Goals (Out of Scope)

- Direct YAML editing (edit the file externally if needed)
- Resolving LOOKUP placeholders in the UI
- Dependency auto-resolution (auto-selecting required entities)
- Multi-file output mode

## Technical Considerations

### Selection State Management
```python
# In state.py
@dataclass
class MapState:
    selected_entities: set[str] = field(default_factory=set)  # element_mapping_ids
    scope_mode: str = 'all_projects'
    selected_project_ids: list[int] = field(default_factory=list)
    resource_filters: dict[str, bool] = field(default_factory=lambda: {
        'connections': True,
        'repositories': True,
        'service_tokens': True,
        # ... etc
    })
    normalization_options: dict = field(default_factory=dict)
```

### Config Generation
```python
def generate_mapping_config(state: MapState) -> dict:
    """Generate importer_mapping.yml content from UI state."""
    return {
        'version': 1,
        'scope': {
            'mode': state.scope_mode,
            'project_ids': state.selected_project_ids if state.scope_mode == 'specific_projects' else [],
        },
        'resource_filters': {
            k: {'include': v} for k, v in state.resource_filters.items()
        },
        'normalization_options': state.normalization_options,
        # ... etc
    }
```

### Integration with Normalizer
```python
from importer.normalizer import normalize

async def run_normalize(input_json: str, config: dict, output_dir: str):
    # Write temp config file
    config_path = Path(output_dir) / 'temp_mapping.yml'
    config_path.write_text(yaml.dump(config))
    
    # Run normalizer
    result = await asyncio.to_thread(normalize, input_json, str(config_path), output_dir)
    return result
```

### File Structure Addition
```
importer/web/
├── pages/
│   └── mapping.py            # Map step page
└── components/
    ├── entity_selector.py    # Table with selection checkboxes
    ├── config_form.py        # Mapping config form
    └── yaml_preview.py       # YAML preview modal
```

## Success Metrics

- Toggling entity selection responds in under 100ms
- Bulk selection of 500 items completes in under 500ms
- Normalization progress updates in real-time
- Preview loads YAML files up to 1MB without lag

## Open Questions

1. Should we warn about circular dependencies (e.g., job references missing environment)?
2. Should there be an "auto-select dependencies" feature?
3. Should we support "profiles" for common selection patterns?
