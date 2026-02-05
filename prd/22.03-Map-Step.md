# PRD: Web UI - Part 4: Map Step

## Introduction

The Map step of the dbt Cloud Importer Web UI. This allows users to interactively select which entities to include in the migration, configure normalization options, and run the normalize operation to generate Terraform-ready YAML. When migrating to an account with existing infrastructure, this step also supports creating and managing a **target resource mapping file** that links source entities to existing target resources.

This is **Part 4 of 5** in the Web UI PRD series.  
**Depends on:** Part 1 (Core Shell), Part 2 (Fetch), Part 3 (Explore)

## Goals

- Enable interactive selection of entities for migration
- Provide visual configuration of mapping/normalization options
- Execute normalization and display results
- Generate Terraform-ready YAML with user-controlled scope
- **Support creating/editing a target resource mapping file for matching existing target infrastructure**
- **Validate mapping file entries against source and target data**
- **Enable manual confirmation of auto-suggested matches before import**

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

---

## Target Resource Mapping Sub-Flow

When migrating to an account with existing infrastructure, users need to map source resources to existing target resources. This prevents "resource already exists" errors during Terraform apply and enables Terraform to take over management of existing resources via import.

### US-037: Enable Target Matching Mode
**Description:** As a user, I want to enable target matching mode so that I can map source resources to existing target resources.

**Acceptance Criteria:**
- [ ] Toggle or checkbox to enable "Match Existing Target Resources" mode
- [ ] Mode only available if target fetch has been completed
- [ ] Warning if enabled without target fetch data
- [ ] When enabled, shows target matching UI components
- [ ] Disabled by default (opt-in for users who need it)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-038: View Auto-Suggested Matches
**Description:** As a user, I want to see auto-suggested matches between source and target resources so that I can quickly identify resources that already exist.

**Acceptance Criteria:**
- [ ] Auto-match suggestions based on exact name match (case-sensitive)
- [ ] Suggestions displayed in a dedicated "Suggested Matches" table
- [ ] Columns: Source Name, Source Type, Target Name, Target ID, Confidence, Action
- [ ] Confidence indicator: "Exact Match" for name matches
- [ ] Filter by resource type
- [ ] Sort by confidence, name, or type
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-039: Confirm or Reject Match Suggestions
**Description:** As a user, I want to confirm or reject each suggested match so that I control exactly which resources are linked.

**Acceptance Criteria:**
- [ ] "Confirm" button accepts a suggested match
- [ ] "Reject" button dismisses a suggestion (resource will be created new)
- [ ] Confirmed matches move to "Confirmed Mappings" section
- [ ] Bulk confirm/reject for multiple suggestions
- [ ] Undo action for accidental confirms/rejects
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-040: Manually Add Resource Mapping
**Description:** As a user, I want to manually add a mapping between source and target resources so that I can handle cases where names don't match exactly.

**Acceptance Criteria:**
- [ ] "Add Manual Mapping" button opens mapping form
- [ ] Source resource selector (dropdown of source entities)
- [ ] Target resource selector (dropdown of target entities, filtered by type)
- [ ] Only shows resources of matching type (can't map a Job to a Project)
- [ ] Validation: cannot map same source twice, cannot map same target twice
- [ ] Manual mappings shown in "Confirmed Mappings" section
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-041: View Confirmed Mappings
**Description:** As a user, I want to see all confirmed mappings in one place so that I can review what will be imported.

**Acceptance Criteria:**
- [ ] "Confirmed Mappings" table shows all accepted mappings
- [ ] Columns: Source Name, Source Key, Target Name, Target ID, Match Type (Auto/Manual)
- [ ] Delete button to remove a mapping
- [ ] Edit button to change target selection
- [ ] Count displayed (e.g., "15 mappings confirmed")
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-042: Load Target Resource Mapping File
**Description:** As a user, I want to load an existing mapping file so that I can reuse mappings from a previous session.

**Acceptance Criteria:**
- [ ] "Load Mapping File" button opens file browser
- [ ] Supports YAML format (`target_resource_mapping.yml`)
- [ ] Loaded mappings populate the confirmed mappings table
- [ ] Validation errors shown for invalid entries (missing source, missing target, type mismatch)
- [ ] Warning for mappings that reference non-existent source/target resources
- [ ] Shows loaded filename
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-043: Save Target Resource Mapping File
**Description:** As a user, I want to save my confirmed mappings to a file so that I can reuse them or share with teammates.

**Acceptance Criteria:**
- [ ] "Save Mapping File" button saves confirmed mappings to YAML file
- [ ] Default filename: `target_resource_mapping.yml`
- [ ] File includes metadata (source account ID, target account ID, timestamp)
- [ ] Each entry includes: resource_type, source_name, source_key, target_id, target_name
- [ ] Overwrites existing file with confirmation
- [ ] Success notification with file path
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-044: Validate Mapping File
**Description:** As a user, I want the mapping file to be validated so that I catch errors before the deploy step.

**Acceptance Criteria:**
- [ ] Validation runs on load and before proceeding to deploy
- [ ] Checks: all source references exist in source data
- [ ] Checks: all target references exist in target data
- [ ] Checks: resource types match between source and target
- [ ] Checks: no duplicate source mappings
- [ ] Checks: no duplicate target mappings (one target can't be claimed by multiple sources)
- [ ] Validation errors displayed with specific line/entry information
- [ ] "Fix" suggestions where possible (e.g., "Did you mean target ID 12345?")
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-045: Mapping File Required for Deploy
**Description:** As a user, I want to be blocked from deploying until I've saved a valid mapping file so that I don't accidentally create duplicate resources.

**Acceptance Criteria:**
- [ ] When target matching mode is enabled, mapping file is required
- [ ] "Continue to Deploy" button disabled until mapping file saved and valid
- [ ] Clear message explaining why proceed is blocked
- [ ] Option to explicitly skip matching (creates all resources new, ignores target data)
- [ ] Skip requires confirmation ("I understand existing resources will not be imported")
- [ ] Typecheck passes
- [ ] Verify in browser

## Functional Requirements

- **FR-1:** Map step must allow toggling `include_in_conversion` per entity
- **FR-2:** Bulk selection operations must work on filtered views
- **FR-3:** Scope and filter settings must map to `importer_mapping.yml` format
- **FR-4:** Normalization must call existing `importer.normalizer.normalize()` function
- **FR-5:** Generated YAML must be previewable in the UI
- **FR-6:** Lookups and exclusions reports must be displayed
- **FR-7:** Target matching mode must be available when target fetch data exists
- **FR-8:** Auto-match suggestions must use exact name matching (case-sensitive)
- **FR-9:** Manual mapping must be supported for cases where names differ
- **FR-10:** Target resource mapping file must be loadable and savable in YAML format
- **FR-11:** Mapping file must be validated before proceeding to deploy
- **FR-12:** When target matching is enabled, a valid mapping file must be required before deploy (unless explicitly skipped)

## Non-Goals (Out of Scope)

- Direct YAML editing (edit the file externally if needed)
- Resolving LOOKUP placeholders in the UI
- Dependency auto-resolution (auto-selecting required entities)
- Multi-file output mode
- Fuzzy name matching or similarity scoring (exact match only; manual override for edge cases)
- Automatic ownership transfer without explicit user confirmation

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
    
    # Target matching state
    target_matching_enabled: bool = False
    suggested_matches: list[dict] = field(default_factory=list)
    confirmed_mappings: list[dict] = field(default_factory=list)
    mapping_file_path: Optional[str] = None
    mapping_file_valid: bool = False
```

### Target Resource Mapping File Schema
```yaml
# target_resource_mapping.yml
version: 1
metadata:
  source_account_id: 12345
  target_account_id: 67890
  created_at: "2026-01-15T10:30:00Z"
  created_by: "web-ui"

mappings:
  - resource_type: "project"
    source_name: "Analytics Project"
    source_key: "project__analytics_project"
    target_id: 98765
    target_name: "Analytics Project"  # Optional, for documentation
    match_type: "auto"  # "auto" or "manual"
  
  - resource_type: "environment"
    source_name: "Production"
    source_key: "environment__analytics_project__production"
    target_id: 54321
    target_name: "Production"
    match_type: "manual"
  
  - resource_type: "global_connection"
    source_name: "Snowflake Prod"
    source_key: "global_connection__snowflake_prod"
    target_id: 11111
    target_name: "Snowflake Production"
    match_type: "manual"
```

### Mapping File Validation
```python
@dataclass
class MappingValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]

def validate_mapping_file(
    mapping_data: dict,
    source_report_items: list[dict],
    target_report_items: list[dict]
) -> MappingValidationResult:
    """Validate mapping file against source and target data."""
    errors = []
    warnings = []
    
    source_keys = {item['key'] for item in source_report_items}
    target_ids = {item['dbt_id'] for item in target_report_items}
    target_by_id = {item['dbt_id']: item for item in target_report_items}
    
    seen_sources = set()
    seen_targets = set()
    
    for mapping in mapping_data.get('mappings', []):
        source_key = mapping.get('source_key')
        target_id = mapping.get('target_id')
        resource_type = mapping.get('resource_type')
        
        # Check source exists
        if source_key not in source_keys:
            errors.append(f"Source key '{source_key}' not found in source data")
        
        # Check target exists
        if target_id not in target_ids:
            errors.append(f"Target ID {target_id} not found in target data")
        
        # Check type match
        if target_id in target_by_id:
            target_type = target_by_id[target_id].get('element_type_code')
            if target_type != resource_type:
                errors.append(f"Type mismatch: source is {resource_type}, target is {target_type}")
        
        # Check duplicates
        if source_key in seen_sources:
            errors.append(f"Duplicate source mapping: {source_key}")
        seen_sources.add(source_key)
        
        if target_id in seen_targets:
            errors.append(f"Duplicate target mapping: {target_id}")
        seen_targets.add(target_id)
    
    return MappingValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
```

### Auto-Match Suggestion Logic
```python
def generate_match_suggestions(
    source_report_items: list[dict],
    target_report_items: list[dict]
) -> list[dict]:
    """Generate auto-match suggestions based on exact name matching."""
    suggestions = []
    
    # Group target items by type and name for fast lookup
    target_by_type_name: dict[tuple[str, str], dict] = {}
    for item in target_report_items:
        key = (item['element_type_code'], item['name'])
        target_by_type_name[key] = item
    
    for source_item in source_report_items:
        lookup_key = (source_item['element_type_code'], source_item['name'])
        
        if lookup_key in target_by_type_name:
            target_item = target_by_type_name[lookup_key]
            suggestions.append({
                'source_name': source_item['name'],
                'source_key': source_item['key'],
                'source_type': source_item['element_type_code'],
                'target_name': target_item['name'],
                'target_id': target_item['dbt_id'],
                'confidence': 'exact_match',
            })
    
    return suggestions
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
    ├── yaml_preview.py       # YAML preview modal
    ├── target_matcher.py     # Target matching UI components
    └── mapping_file.py       # Mapping file load/save/validate
```

## Success Metrics

- Toggling entity selection responds in under 100ms
- Bulk selection of 500 items completes in under 500ms
- Normalization progress updates in real-time
- Preview loads YAML files up to 1MB without lag
- Auto-match suggestions generated in under 2 seconds for 500 source + 500 target items
- Mapping file validation completes in under 1 second
- Mapping file load/save operations complete in under 500ms

## Open Questions

1. Should we warn about circular dependencies (e.g., job references missing environment)?
2. Should there be an "auto-select dependencies" feature?
3. Should we support "profiles" for common selection patterns?
4. How should we handle name collisions (multiple resources with the same name in source or target)?
5. Should we support partial matching (match some resources, create others new)?
6. Should mapping file support regex or pattern-based matching for bulk operations?
7. Should we track mapping file history/versions for audit purposes?