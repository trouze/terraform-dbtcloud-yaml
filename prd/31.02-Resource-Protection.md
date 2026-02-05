# PRD: Resource Protection for Adopted Resources

## 1. Overview

This PRD defines the implementation of **resource protection** for adopted resources in the dbt Cloud Importer Web UI. When users adopt existing infrastructure into Terraform management, they can optionally protect those resources from accidental destruction.

The implementation uses a **hybrid approach**:
1. **Native Terraform Protection**: Generate separate resource blocks with `lifecycle { prevent_destroy = true }`
2. **Plan-Time Validation**: Parse plan output to provide friendly warnings before Terraform errors
3. **Moved Blocks Generation**: Auto-generate `moved` blocks when protection status changes

This is **Part 9** in the Web UI PRD series.  
**Depends on:** Part 5 (Deploy), Part 6 (Enhanced Matching)

---

## 2. Goals

- Allow users to mark adopted resources as "protected" during the adoption workflow
- Provide true Terraform-native protection using `lifecycle { prevent_destroy = true }`
- Support protection for all resource types: projects, environments, jobs, repositories, connections
- Generate `moved` blocks automatically when protection status changes
- Provide clear UX warnings when protected resources would be affected
- Enable users to view and manage protected resources from the Deploy page

---

## 3. Non-Goals

- Providing protection outside of Terraform (e.g., dbt Cloud UI or API)
- Automatic protection based on environment type (e.g., all prod environments)
- Automatic cascade protection without user confirmation

---

## 4. User Stories

### 4.1 Protection During Adoption

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-RP-01 | As a user, I want to see a "Protect from destroy" checkbox when adopting a resource | Checkbox appears in match detail dialog when action is "adopt" |
| US-RP-02 | As a user, I want protection to be enabled by default for adopted resources | Checkbox is pre-checked when dialog opens for adopt action |
| US-RP-03 | As a user, I want to uncheck protection if I don't want it for a specific resource | Checkbox is interactive and saves state when unchecked |
| US-RP-04 | As a user, I want to see a tooltip explaining what protection does | Hover text: "Adds lifecycle.prevent_destroy - Terraform will refuse to destroy this resource" |
| US-RP-05 | As a user, I want to see which resources are protected in the match grid | Shield icon or "Protected" badge in grid row for protected resources |
| US-RP-06 | As a user, I want to bulk-set protection for multiple selected resources | "Set Protected" button in bulk actions applies to selected rows |

### 4.2 YAML Configuration

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-RP-10 | As a user, I want protected resources to have `protected: true` in the generated YAML | YAML output includes `protected: true` field for protected resources |
| US-RP-11 | As a user, I want to manually edit the YAML to add/remove protection | `protected` field is optional, defaults to false if omitted |
| US-RP-12 | As a user, I want the YAML schema to validate the protected field | JSON schema validates `protected` as boolean or null |
| US-RP-13 | As a user, I want protection status preserved when regenerating YAML | Regenerate operation maintains existing `protected: true` settings |

### 4.3 Terraform Generation

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-RP-20 | As a user, I want protected resources to use separate Terraform resource blocks | Protected jobs go to `dbtcloud_job.protected_jobs`, not `dbtcloud_job.jobs` |
| US-RP-21 | As a user, I want the protected resource blocks to have `lifecycle { prevent_destroy = true }` | Generated TF has literal `prevent_destroy = true` in lifecycle block |
| US-RP-22 | As a user, I want `terraform destroy` to fail for protected resources | Running `terraform destroy` shows error: "Instance cannot be destroyed" |
| US-RP-23 | As a user, I want protected/unprotected resources to have identical configuration except lifecycle | All resource attributes are the same, only lifecycle block differs |

### 4.4 Protection Status Changes

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-RP-30 | As a user, I want to change a resource from unprotected to protected | Change `protected: false` to `protected: true` in YAML |
| US-RP-31 | As a user, I want a `moved` block generated when protection status changes | `moved { from = ...jobs["x"] to = ...protected_jobs["x"] }` generated |
| US-RP-32 | As a user, I want `terraform apply` to move the resource without recreating | Apply shows "moved" action, not "destroy" + "create" |
| US-RP-33 | As a user, I want to remove protection from a resource | Change `protected: true` to `protected: false` or remove field |
| US-RP-34 | As a user, I want the reverse `moved` block for unprotecting | `moved { from = ...protected_jobs["x"] to = ...jobs["x"] }` generated |
| US-RP-35 | As a user, I want `moved` blocks to be cleaned up after successful apply | Old `moved` blocks removed after state reflects new addresses |

### 4.5 Plan-Time Validation

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-RP-40 | As a user, I want a friendly warning before Terraform's cryptic error | Warning shown in UI before `terraform plan` output appears |
| US-RP-41 | As a user, I want to see which protected resources would be destroyed | List of affected resources with names and types displayed |
| US-RP-42 | As a user, I want instructions on how to proceed | "To destroy: remove protected: true from YAML and regenerate" |
| US-RP-43 | As a user, I want the warning to appear for both plan and apply | Validation runs before both operations |
| US-RP-44 | As a user, I want to see the Terraform error if I proceed anyway | Full Terraform output shown after warning |

### 4.6 Protected Resources Management UI

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-RP-50 | As a user, I want to see a list of all protected resources on the Deploy page | "Protected Resources" section/expander shows list |
| US-RP-51 | As a user, I want to see resource name, type, and when it was protected | Table columns: Name, Type, Protected Since |
| US-RP-52 | As a user, I want to remove protection from the Deploy page | "Remove Protection" button per resource |
| US-RP-53 | As a user, I want confirmation before removing protection | Dialog: "Remove protection from [Resource]? This will require regenerating Terraform files." |
| US-RP-54 | As a user, I want to export protected resources list | "Export to CSV" button downloads list |
| US-RP-55 | As a user, I want to see count of protected resources in Deploy summary | "5 protected resources" shown in summary panel |

### 4.7 Edge Cases

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-RP-60 | ~~As a user, I want protection to work with dependent resources~~ | Superseded by US-RP-70+ (Cascade Protection) |
| US-RP-61 | As a user, I want warning when deleting protected resource from YAML | Warning: "Protected resource removed from YAML - will cause Terraform error" |
| US-RP-62 | As a user, I want to handle orphaned protection entries | Protection entry removed when resource no longer exists in YAML |
| US-RP-63 | As a user, I want protection to survive YAML regeneration | Regenerating from source preserves protection status |
| US-RP-64 | As a user, I want clear error when Terraform version doesn't support moved blocks | Error: "Terraform 1.1+ required for protection status changes" |

### 4.8 Cascade Protection (Parent-Child Dependencies)

When protecting a child resource, its parent resources must also be protected. Otherwise, Terraform could delete a parent (destroying all children) even though children are marked as protected.

**Cascade Chain:**
| Resource Type | Parent Chain | Example |
|--------------|--------------|---------|
| Job | ENV → PRJ | Protect "Daily Build" → protect "Production" env → protect "Analytics" project |
| Credential | ENV → PRJ | Protect databricks creds → protect "Production" env → protect "Analytics" project |
| Environment | PRJ | Protect "Production" → protect "Analytics" project |
| Env Variable | PRJ | Protect "DBT_TARGET" → protect "Analytics" project |
| Repository (project-linked) | PRJ | Protect "jaffle-shop" repo → protect "Analytics" project |
| Repository (orphan) | (none) | Global repo, no cascade needed |
| Connection | (none) | Global connection, no cascade needed |
| Project | (none) | Top-level, no cascade needed |

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-RP-70 | As a user, I want to mark any resource as protected in the match grid | Protection checkbox column visible in match grid for all resource types |
| US-RP-71 | As a user, I want protecting a child to auto-protect its parents | Protecting a Job shows dialog listing Environment and Project to be protected |
| US-RP-72 | As a user, I want to see a confirmation dialog listing parent resources to protect | Dialog shows: "To protect 'Daily Build', these parents must also be protected: [Production env, Analytics project]" |
| US-RP-73 | As a user, I want to confirm or cancel the cascade protection | "Protect All (3)" and "Cancel" buttons in dialog |
| US-RP-74 | As a user, I want protected rows highlighted in the grid | Blue left border and subtle blue background on protected rows |
| US-RP-75 | As a user, I want to unprotect a parent with protected children | Dialog asks: "Would you like to unprotect the children as well?" |
| US-RP-76 | As a user, I want to cascade unprotect to all children | "Unprotect All (5)" button removes protection from parent and all protected descendants |
| US-RP-77 | As a user, I want to unprotect only the parent (not children) | "Unprotect This Only" button removes protection from parent only, children stay protected |
| US-RP-78 | As a user, I want credentials (CRD) to cascade to ENV → PRJ | Protecting a credential cascades through its parent environment to project |
| US-RP-79 | As a user, I want env variables (VAR) to cascade to PRJ | Protecting an env variable cascades to its parent project |
| US-RP-80 | As a user, I want project-linked repos to cascade to PRJ | Protecting a repository that belongs to a project cascades to that project |

---

## 5. Technical Implementation

### 5.1 YAML Schema Changes (`schemas/v2.json`)

Add `protected` property to each resource definition:

```json
{
  "$defs": {
    "project": {
      "type": "object",
      "properties": {
        "key": { "type": "string" },
        "name": { "type": "string" },
        "protected": {
          "type": ["boolean", "null"],
          "default": false,
          "description": "If true, Terraform will prevent this resource from being destroyed"
        }
      }
    },
    "environment": {
      "type": "object", 
      "properties": {
        "protected": {
          "type": ["boolean", "null"],
          "default": false
        }
      }
    },
    "job": {
      "type": "object",
      "properties": {
        "protected": {
          "type": ["boolean", "null"], 
          "default": false
        }
      }
    },
    "repository": {
      "type": "object",
      "properties": {
        "protected": {
          "type": ["boolean", "null"],
          "default": false
        }
      }
    }
  }
}
```

### 5.2 Module Changes

#### 5.2.1 Jobs (`modules/projects_v2/jobs.tf`)

```hcl
locals {
  # Split jobs into protected and unprotected maps
  protected_jobs_map = {
    for key, item in local.jobs_map :
    key => item
    if try(item.job_data.protected, false) == true
  }
  
  unprotected_jobs_map = {
    for key, item in local.jobs_map :
    key => item
    if try(item.job_data.protected, false) != true
  }
}

# Unprotected jobs - standard lifecycle
resource "dbtcloud_job" "jobs" {
  for_each = local.unprotected_jobs_map
  
  project_id     = each.value.project_id
  name           = each.value.job_data.name
  environment_id = each.value.environment_id
  execute_steps  = each.value.job_data.execute_steps
  triggers       = each.value.job_data.triggers
  # ... all other fields ...
  
  lifecycle {
    ignore_changes = [job_completion_trigger_condition]
  }
}

# Protected jobs - prevent_destroy lifecycle
resource "dbtcloud_job" "protected_jobs" {
  for_each = local.protected_jobs_map
  
  project_id     = each.value.project_id
  name           = each.value.job_data.name
  environment_id = each.value.environment_id
  execute_steps  = each.value.job_data.execute_steps
  triggers       = each.value.job_data.triggers
  # ... all other fields (identical to unprotected) ...
  
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [job_completion_trigger_condition]
  }
}
```

Same pattern applies to:
- `modules/projects_v2/environments.tf` → `dbtcloud_environment.environments` / `dbtcloud_environment.protected_environments`
- `modules/projects_v2/projects.tf` → `dbtcloud_project.projects` / `dbtcloud_project.protected_projects`

### 5.3 Protection Manager (`importer/web/utils/protection_manager.py`)

```python
"""Protection manager for tracking and managing protected resources."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

@dataclass
class ProtectionChange:
    """Represents a change in protection status."""
    resource_key: str
    resource_type: str  # PRJ, ENV, JOB, REP
    name: str
    direction: str  # "protect" or "unprotect"
    from_address: str
    to_address: str

def get_resource_addresses(resource_type: str, key: str, protected: bool) -> str:
    """Get Terraform resource address based on protection status."""
    type_map = {
        "PRJ": ("dbtcloud_project", "projects", "protected_projects"),
        "ENV": ("dbtcloud_environment", "environments", "protected_environments"),
        "JOB": ("dbtcloud_job", "jobs", "protected_jobs"),
        "REP": ("dbtcloud_repository", "repositories", "protected_repositories"),
    }
    tf_type, unprotected_name, protected_name = type_map[resource_type]
    resource_name = protected_name if protected else unprotected_name
    return f'module.dbt_cloud.{tf_type}.{resource_name}["{key}"]'

def detect_protection_changes(
    current_yaml: dict,
    previous_yaml: Optional[dict],
) -> list[ProtectionChange]:
    """Detect resources that changed protection status between YAML versions."""
    ...

def generate_moved_blocks(changes: list[ProtectionChange]) -> str:
    """Generate Terraform moved blocks for protection status changes."""
    lines = [
        "# Auto-generated: Move resources between protected/unprotected",
        f"# Generated: {datetime.now().isoformat()}",
        "",
    ]
    for change in changes:
        lines.extend([
            f"# {change.name} ({change.resource_type}) is now {'protected' if change.direction == 'protect' else 'unprotected'}",
            "moved {",
            f'  from = {change.from_address}',
            f'  to   = {change.to_address}',
            "}",
            "",
        ])
    return "\n".join(lines)

def check_plan_for_protected_destroys(
    plan_json: dict,
    yaml_config: dict,
) -> list[dict]:
    """Parse Terraform plan JSON and identify protected resources that would be destroyed."""
    affected = []
    
    # Build set of protected resource addresses
    protected_addresses = set()
    for project in yaml_config.get("projects", []):
        if project.get("protected"):
            addr = get_resource_addresses("PRJ", project["key"], True)
            protected_addresses.add(addr)
        # ... same for environments, jobs, etc.
    
    # Check plan for destroy/replace actions
    resource_changes = plan_json.get("resource_changes", [])
    for change in resource_changes:
        actions = change.get("change", {}).get("actions", [])
        if "delete" in actions or "replace" in actions:
            address = change.get("address", "")
            if address in protected_addresses:
                affected.append({
                    "address": address,
                    "name": change.get("change", {}).get("before", {}).get("name", "Unknown"),
                    "type": change.get("type", ""),
                    "action": "delete" if "delete" in actions else "replace",
                })
    
    return affected
```

### 5.4 UI Components

#### Match Dialog Update (`importer/web/pages/match.py`)

```python
def show_match_detail_dialog(...):
    # ... existing dialog code ...
    
    # Protection checkbox (only shown for adopt action)
    if grid_row.get("action") == "adopt":
        with ui.row().classes("items-center gap-2 mt-4"):
            protect_checkbox = ui.checkbox(
                "Protect from destroy",
                value=True,  # Default to protected
            ).props("dense")
            ui.icon("shield", size="sm").classes("text-blue-500")
            with ui.element("span").classes("text-caption text-grey"):
                ui.label("Terraform will refuse to destroy this resource")
        
        # Store protection preference
        def on_protect_change(e):
            grid_row["protected"] = e.value
            # Update confirmed_mappings
            ...
        
        protect_checkbox.on("change", on_protect_change)
```

#### Deploy Page Protection Panel (`importer/web/pages/deploy.py`)

```python
def render_protected_resources_panel(state: AppState):
    """Render panel showing protected resources."""
    protected = get_protected_resources_from_yaml(state.map.last_yaml_file)
    
    with ui.expansion("Protected Resources", icon="shield").classes("w-full"):
        if not protected:
            ui.label("No protected resources").classes("text-grey")
        else:
            ui.label(f"{len(protected)} protected resource(s)").classes("text-caption")
            
            with ui.element("table").classes("w-full"):
                # Header
                with ui.element("tr"):
                    ui.element("th").text("Name")
                    ui.element("th").text("Type")
                    ui.element("th").text("Actions")
                
                # Rows
                for resource in protected:
                    with ui.element("tr"):
                        ui.element("td").text(resource["name"])
                        ui.element("td").text(resource["type"])
                        with ui.element("td"):
                            ui.button(
                                "Remove Protection",
                                on_click=lambda r=resource: remove_protection(r),
                            ).props("flat dense")
```

---

## 6. Test Plan

### 6.1 Unit Tests

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| UT-RP-01 | `get_resource_addresses()` with protected=True | Returns `protected_jobs` address |
| UT-RP-02 | `get_resource_addresses()` with protected=False | Returns `jobs` address |
| UT-RP-03 | `detect_protection_changes()` with new protection | Returns ProtectionChange with direction="protect" |
| UT-RP-04 | `detect_protection_changes()` with removed protection | Returns ProtectionChange with direction="unprotect" |
| UT-RP-05 | `detect_protection_changes()` with no changes | Returns empty list |
| UT-RP-06 | `generate_moved_blocks()` with protect change | Generates valid HCL moved block |
| UT-RP-07 | `generate_moved_blocks()` with unprotect change | Generates reverse moved block |
| UT-RP-08 | `check_plan_for_protected_destroys()` with destroy action | Returns affected protected resource |
| UT-RP-09 | `check_plan_for_protected_destroys()` with no destroys | Returns empty list |
| UT-RP-10 | `check_plan_for_protected_destroys()` with unprotected destroy | Returns empty list (not protected) |

### 6.2 Integration Tests - YAML Schema

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| IT-RP-01 | YAML with `protected: true` on project | Validates successfully |
| IT-RP-02 | YAML with `protected: false` on job | Validates successfully |
| IT-RP-03 | YAML with `protected: null` on environment | Validates successfully, treated as false |
| IT-RP-04 | YAML with `protected: "yes"` (invalid) | Validation fails with type error |
| IT-RP-05 | YAML without `protected` field | Validates successfully, defaults to false |

### 6.3 Integration Tests - Terraform Module

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| IT-RP-10 | Protected job in YAML | Job created in `dbtcloud_job.protected_jobs` |
| IT-RP-11 | Unprotected job in YAML | Job created in `dbtcloud_job.jobs` |
| IT-RP-12 | Mix of protected/unprotected jobs | Jobs split between both resource blocks |
| IT-RP-13 | Protected environment in YAML | Environment in `protected_environments` |
| IT-RP-14 | Protected project in YAML | Project in `protected_projects` |
| IT-RP-15 | `terraform validate` with protected resources | Validation passes |
| IT-RP-16 | `terraform plan` with protected resources | Plan shows correct resource addresses |

### 6.4 Integration Tests - Terraform Behavior

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| IT-RP-20 | `terraform destroy` on protected job | Fails with "prevent_destroy" error |
| IT-RP-21 | `terraform destroy` on unprotected job | Succeeds (job destroyed) |
| IT-RP-22 | `terraform apply` with moved block (protect) | Resource moved, not recreated |
| IT-RP-23 | `terraform apply` with moved block (unprotect) | Resource moved, not recreated |
| IT-RP-24 | Remove protected resource from YAML | Plan shows destroy, apply fails |
| IT-RP-25 | Remove unprotected resource from YAML | Plan shows destroy, apply succeeds |

### 6.5 E2E Tests - Adoption Flow

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| E2E-RP-01 | Adopt resource with protection enabled | YAML has `protected: true`, TF uses protected block |
| E2E-RP-02 | Adopt resource with protection disabled | YAML has no protected field, TF uses standard block |
| E2E-RP-03 | Adopt multiple resources, mixed protection | Each resource in correct block based on setting |
| E2E-RP-04 | Change protection after initial adoption | Moved block generated, apply moves resource |
| E2E-RP-05 | Full workflow: adopt → protect → unprotect → delete | All state transitions work correctly |

### 6.6 E2E Tests - UI Behavior

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| E2E-RP-10 | Open adopt dialog | Protection checkbox visible and checked by default |
| E2E-RP-11 | Uncheck protection in dialog | Protection saved as false |
| E2E-RP-12 | View match grid after adoption | Protected resources show shield icon |
| E2E-RP-13 | View Deploy page protected panel | Lists all protected resources |
| E2E-RP-14 | Click "Remove Protection" in panel | Confirmation dialog appears |
| E2E-RP-15 | Confirm protection removal | YAML updated, regenerate prompt shown |
| E2E-RP-16 | Run plan with protected destroy | Warning message shown before TF error |

### 6.7 Edge Case Tests

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| EC-RP-01 | Protect resource then delete from YAML without unprotecting | Clear error message, plan fails |
| EC-RP-02 | Two resources with same name, one protected | Correct resource in correct block |
| EC-RP-03 | Change protection status twice before apply | Only final state reflected |
| EC-RP-04 | Regenerate YAML after protection changes | Protection status preserved |
| EC-RP-05 | Import existing state with protected resources | State correctly identifies protected resources |
| EC-RP-06 | Terraform < 1.1 with moved blocks | Clear error about version requirement |

### 6.8 Cascade Protection Tests

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| CP-RP-01 | Protect a Job (has ENV, PRJ parents) | Dialog shows ENV and PRJ to be protected |
| CP-RP-02 | Confirm cascade protection on Job | Job, ENV, and PRJ all marked protected |
| CP-RP-03 | Cancel cascade protection on Job | No resources protected |
| CP-RP-04 | Protect an Environment (has PRJ parent) | Dialog shows PRJ to be protected |
| CP-RP-05 | Protect a Project (no parents) | No dialog, directly protected |
| CP-RP-06 | Protect Credential (has ENV→PRJ) | Dialog shows ENV and PRJ chain |
| CP-RP-07 | Protect Env Variable (has PRJ) | Dialog shows PRJ to be protected |
| CP-RP-08 | Protect project-linked Repository | Dialog shows parent PRJ |
| CP-RP-09 | Protect orphan Repository (no project) | No dialog, directly protected |
| CP-RP-10 | Protect global Connection | No dialog, directly protected |
| CP-RP-11 | Unprotect parent with protected children | Dialog asks about cascade unprotect |
| CP-RP-12 | Choose "Unprotect All" | Parent and all children unprotected |
| CP-RP-13 | Choose "Unprotect This Only" | Only parent unprotected, children stay |
| CP-RP-14 | Protected row styling in grid | Blue left border, subtle blue background |
| CP-RP-15 | Protection indicator in grid | Shield icon shown for protected resources |
| CP-RP-16 | `get_resources_to_protect()` with Job | Returns Job + [ENV, PRJ] |
| CP-RP-17 | `get_resources_to_unprotect()` on PRJ | Returns all protected descendants |
| CP-RP-18 | Protect when parent already protected | Parent skipped in dialog, only new resources shown |

### 6.9 Manual Testing Checklist

#### Adoption Flow
- [ ] Open Match page and select a resource for adoption
- [ ] Verify "Protect from destroy" checkbox appears
- [ ] Verify checkbox is checked by default
- [ ] Uncheck checkbox and verify state saves
- [ ] Complete adoption and verify YAML contains `protected: true`
- [ ] Verify match grid shows protection indicator

#### Terraform Operations
- [ ] Generate Terraform files and verify protected resources in separate blocks
- [ ] Run `terraform init` successfully
- [ ] Run `terraform plan` and verify correct resource addresses
- [ ] Run `terraform apply` and verify resources created
- [ ] Attempt `terraform destroy` and verify protected resources fail

#### Protection Status Changes
- [ ] Edit YAML to change `protected: true` to `protected: false`
- [ ] Regenerate Terraform files
- [ ] Verify `moved` block generated in `protection_moves.tf`
- [ ] Run `terraform apply` and verify resource moved (not recreated)
- [ ] Verify old moved block can be deleted after apply

#### Deploy Page UI
- [ ] Navigate to Deploy page
- [ ] Verify "Protected Resources" panel visible
- [ ] Verify all protected resources listed
- [ ] Click "Remove Protection" and verify confirmation dialog
- [ ] Confirm removal and verify YAML updated
- [ ] Verify regenerate prompt appears

#### Cascade Protection (Grid-based)
- [ ] Open Match page and view the grid
- [ ] Verify protection checkbox column visible (🛡️ header)
- [ ] Click protection checkbox on a Job
- [ ] Verify cascade dialog shows Environment and Project
- [ ] Click "Protect All (3)" and verify all three protected
- [ ] Verify protected rows have blue left border styling
- [ ] Unprotect the Project (has protected children)
- [ ] Verify dialog asks about cascade unprotection
- [ ] Choose "Unprotect All" and verify children unprotected
- [ ] Protect a Credential and verify ENV→PRJ cascade
- [ ] Protect an Env Variable and verify PRJ cascade
- [ ] Protect a project-linked Repository and verify PRJ cascade
- [ ] Protect an orphan Repository (no dialog expected)

---

## 7. Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `schemas/v2.json` | Modify | Add `protected` field to project, environment, job, repository |
| `modules/projects_v2/jobs.tf` | Modify | Add protected_jobs_map, protected_jobs resource block |
| `modules/projects_v2/environments.tf` | Modify | Add protected_environments_map, protected_environments resource block |
| `modules/projects_v2/projects.tf` | Modify | Add protected_projects_map, protected_projects resource block |
| `importer/web/utils/protection_manager.py` | Create | Core protection tracking, validation, and cascade logic |
| `importer/web/utils/adoption_yaml_updater.py` | Modify | Set `protected: true` for adopted resources, add `apply_protection_from_set()` |
| `importer/web/pages/match.py` | Modify | Add protection checkbox to adopt dialog, cascade dialogs, protection handling |
| `importer/web/pages/deploy.py` | Modify | Add protected resources panel, plan validation, apply protection from set |
| `importer/web/components/match_grid.py` | Modify | Add protection checkbox column, protected row styling |
| `importer/web/components/hierarchy_index.py` | Reference | Used for parent/child lookups in cascade protection |
| `importer/web/state.py` | Modify | Add `protected_resources` set to MapState, track previous YAML |
| `test/test_protection_manager.py` | Create | Unit tests for protection_manager.py including cascade helpers |
| `test/terraform/protected_resources/` | Create | Terraform integration test fixtures |

---

## 8. Implementation Phases

### Phase 1: Schema & Module Foundation
1. Update `schemas/v2.json` with `protected` field
2. Update module locals to split protected/unprotected maps
3. Add protected resource blocks with `lifecycle { prevent_destroy = true }`
4. Verify `terraform validate` passes

### Phase 2: Protection Manager Utility
1. Create `protection_manager.py`
2. Implement protection change detection
3. Implement moved blocks generation
4. Implement plan parsing for protected destroys
5. Add unit tests

### Phase 3: Adoption UI Integration
1. Add protection checkbox to match detail dialog
2. Update `adoption_yaml_updater.py` to set protected flag
3. Add protection indicator to match grid
4. Test adoption flow end-to-end

### Phase 4: Deploy Page Integration
1. Add protected resources panel to Deploy page
2. Implement plan-time validation and warnings
3. Add "Remove Protection" functionality
4. Test full workflow

### Phase 5: Moved Blocks Automation
1. Track previous YAML state for change detection
2. Auto-generate moved blocks on regenerate
3. Clean up old moved blocks after successful apply
4. Test protection status change workflow

---

## 9. Acceptance Criteria Summary

### Must Have
- [ ] `protected: true` field supported in YAML for projects, environments, jobs
- [ ] Protected resources use separate Terraform resource blocks with `prevent_destroy = true`
- [ ] `terraform destroy` fails for protected resources
- [ ] Protection checkbox in adopt dialog (default: checked)
- [ ] Protected resources visible in match grid

### Should Have
- [ ] Moved blocks auto-generated when protection status changes
- [ ] Plan-time warning before Terraform error
- [ ] Protected resources panel on Deploy page
- [ ] Remove protection functionality

### Nice to Have
- [ ] CSV export of protected resources
- [ ] Bulk protection toggle in match grid
- [ ] Protection status preserved on YAML regeneration

---

## 10. Open Questions

1. **Should connections support protection?** - Connections are often shared and have different lifecycle considerations.

2. **Should we auto-protect certain resource types?** - e.g., always protect production environments by default.

3. **How to handle protection in CI/CD pipelines?** - Should there be an override flag for automated workflows?

4. **What happens to protection when cloning?** - Should cloned resources inherit protection status?
