---
name: Protection Intent File
overview: Introduce a separate protection intent file that serves as the authoritative source for user protection decisions, independent of YAML config and TF state, with full audit trail.
todos:
  - id: create-prd
    content: Create `tasks/prd-web-ui-13-protection-intent.md` with full PRD following established format
    status: in_progress
  - id: create-intent-manager
    content: Create `importer/web/utils/protection_intent.py` with ProtectionIntentManager class
    status: pending
  - id: integrate-project-manager
    content: Add protection intent methods to ProjectManager (get_protection_intent_path, load_protection_intent)
    status: pending
  - id: update-mismatch-detection
    content: Update `match_grid.py` to use intent manager for yaml_protected determination
    status: pending
  - id: update-protect-buttons
    content: Update match.py protect/unprotect handlers to write to intent file (no YAML update)
    status: pending
  - id: add-generate-protection-button
    content: Add "Generate Protection Changes" button that updates YAML + writes protection_moves.tf
    status: pending
  - id: add-generate-warning
    content: Add warning tooltip to existing Generate button about full regeneration
    status: pending
  - id: update-apply-success
    content: Update apply success handler to mark intents as applied to TF state
    status: pending
  - id: add-migration
    content: Add migration logic to initialize intent file from existing YAML/TF state
    status: pending
  - id: add-ui-indicators
    content: Add UI indicators showing intent status (pending, synced) on Match page
    status: pending
  - id: create-utilities-page
    content: Create new utilities.py page with Protection Management section (audit trail, bulk actions, manual editor)
    status: pending
  - id: update-destroy-page
    content: Update destroy.py protection panel to use ProtectionIntentManager instead of state.map.unprotected_keys
    status: pending
  - id: deprecate-protected-resources
    content: Deprecate state.map.protected_resources and state.map.unprotected_keys in favor of intent manager
    status: pending
  - id: add-test-cases
    content: Add comprehensive test cases for workflow variations (browser + unit tests)
    status: pending
  - id: fix-button-styling
    content: Fix Protect/Unprotect All button styling - create with icon= parameter, not set_icon()
    status: pending
  - id: add-streaming-output
    content: Add streaming progress dialog for "Generate Protection Changes" with Copy button
    status: pending
  - id: add-ai-diagnostic-copy
    content: Add "Copy for AI" button that generates structured diagnostic summary
    status: pending
  - id: create-guardrails-file
    content: Create `.ralph/guardrails.md` to track lessons learned during implementation
    status: completed
isProject: false
---

# Protection Intent File System

## Problem Statement

The current system conflates three different sources of truth:

1. **TF State** - what's currently protected in Terraform
2. **YAML config** - `protected: true` flags that drive TF module
3. **UI state** (`state.map.protected_resources`) - ephemeral, gets out of sync

This causes "flip-flopping" where:

- User clicks "Unprotect" -> YAML updated -> Generate regenerates from stale state -> Protection flag reappears
- Apply succeeds -> Page reloads -> UI state reset -> Mismatch appears again

## Solution: Protection Intent File

A separate `protection-intent.json` file that:

- Records explicit user intent with full audit trail
- Takes precedence over YAML `protected:` flags
- Tracks whether each intent has been applied to YAML and TF state
- **Lives in the project folder** (per project-based state management plan)

## PRD Enhancements (from cursor-command templates)

The PRD will include these additional sections adopted from cursor-command standards:

### Definition of Done

A user story is complete when:

- Code implemented and linter passes (`ReadLints` shows no new errors)
- Unit tests pass for new functionality
- Browser validation passes (if UI change)
- Debug instrumentation added (`@traced`, `log_action`, `log_state_change`)
- Changes committed with descriptive message
- PRD user story checkbox marked complete

### Tips for AI Agents

Common pitfalls to avoid in this implementation:

**NiceGUI Buttons:**

- Never use `set_icon()` dynamically - pass `icon=` on button creation
- Use `props("color=amber").style("color: black !important;")` for amber buttons

**AG Grid (Utilities page):**

- Always use `theme="quartz"` with `ag-theme-quartz-auto-dark` class
- Explicit `colId` on every column
- Pre-sort data in Python, not via AG Grid `initialState.sortModel`

**Protection Intent:**

- Always save intent file after modifications
- Use `get_effective_protection()` not direct YAML checks
- Check `applied_to_yaml` before updating YAML again

**Streaming Output:**

- Use `asyncio.create_task` for non-blocking subprocess execution
- Always provide Cancel button for long operations
- Store output in dict for "View Output" button persistence

### Guardrails (Lessons Learned)

Document failures and fixes here during implementation:

```markdown
### Sign: [Short description]
- **Trigger**: When this situation occurs
- **Instruction**: What to do instead  
- **Added after**: Session/PR that caused this
```

### Session Protocol

**Starting a session:**

1. Read `protection-intent.json` to understand current state
2. Check for pending intents (`applied_to_yaml=false` or `applied_to_tf_state=false`)
3. Review `.cursor/debug.log` for recent errors
4. Run `./restart_web.sh` to ensure clean server state

**Ending a session:**

1. Ensure all pending changes are saved to intent file
2. Update progress in plan todos
3. Document any guardrails discovered
4. Commit work with descriptive message

## Cursor Rules Compliance

This implementation MUST follow these cursor rules:

- **AG Grid Standards** (`.cursor/rules/ag-grid-standards.mdc`):
  - Current Intents table in Utilities page uses AG Grid with `theme="quartz"` + `ag-theme-quartz-auto-dark`
  - Explicit `colId` on all columns
  - `rowSelection` for multi-select with checkboxes
  - Audit History table follows same patterns
- **Debug Instrumentation** (`.cursor/rules/debug-instrumentation.mdc`):
  - Use `@traced` decorator on `ProtectionIntentManager` methods
  - `log_action()` for all button clicks (Protect All, Unprotect All, Generate Protection Changes)
  - `log_state_change()` when intent file is modified
  - `log_generate_step()` during Generate Protection Changes process
  - Hypothesis markers `[HPI]` for protection intent debugging
- **Browser Testing** (`.cursor/rules/browser-testing.mdc`):
  - All E2E tests use cursor-browser-extension MCP
  - Restart server via `./restart_web.sh` before testing
  - Load credentials via `/fetch_target` after restart

## Related Plans

This plan integrates with:

- **[Project-Based State Management](project-based_state_management_697cfb3e.plan.md)** - Implements the `per-project-protection` todo; protection-intent.json lives in project folder
- **[Extended Attributes Support](extended_attributes_support_96c8d11a.plan.md)** - Sprint 6 cascade protection uses ProtectionIntentManager; added `sprint6-intent-integration` todo
- **[Destroy Page Refactor PRD](../tasks/prd-web-ui-10-destroy-page-refactor.md)** - Destroy page protection panel must use ProtectionIntentManager instead of `state.map.unprotected_keys`

## Integration with Project-Based State Management

This plan implements the `per-project-protection` todo from the [project-based state management plan](project-based_state_management_697cfb3e.plan.md).

**Project folder structure (updated):**

```
projects/
  my-migration/
    .gitignore
    project.json              # ProjectConfig metadata
    state.json                # Full AppState
    protection-intent.json    # NEW: Protection decisions with audit trail
    .env.source
    .env.target
    outputs/
      source/
      target/
      normalized/
```

**Key integration points:**

- `ProjectManager.create_project()` - Initialize empty protection-intent.json
- `ProjectManager.load_project()` - Load protection intent alongside state
- `ProjectManager.save_project()` - Save protection intent with state
- Per-project isolation - Each project has independent protection decisions

## File Format

The intent file uses prefixed keys to distinguish protection scope:

- `PRJ:{name}` - Project resource protection (independent)
- `REPO:{name}` - Repository + PREP protection (single key covers both TF resources)

**IMPORTANT: REPO Consolidation (2026-02-04)**

Do NOT use separate `REP:` and `PREP:` keys - these have been deprecated and consolidated into a single `REPO:` key. A single `REPO:` intent generates TWO Terraform moved blocks.

```json
{
  "version": 1,
  "updated_at": "2026-02-02T14:30:00Z",
  "intent": {
    "PRJ:sse_dm_fin_fido": {
      "protected": false,
      "set_at": "2026-02-02T10:00:00Z",
      "set_by": "user_click",
      "reason": "Unprotect project only",
      "resource_type": "PRJ",
      "applied_to_yaml": true,
      "applied_to_tf_state": false,
      "tf_state_at_decision": "protected"
    },
    "REPO:sse_dm_fin_fido": {
      "protected": true,
      "set_at": "2026-02-02T10:00:00Z",
      "set_by": "user_click",
      "reason": "Keep repo+prep protected (covers both TF resources)",
      "resource_type": "REPO",
      "applied_to_yaml": true,
      "applied_to_tf_state": true,
      "tf_state_at_decision": "protected"
    }
  },
  "history": [
    {
      "resource_key": "PRJ:sse_dm_fin_fido",
      "action": "unprotect",
      "timestamp": "2026-02-02T10:00:00Z",
      "source": "unprotect_project_button",
      "tf_state_before": "protected",
      "yaml_state_before": true
    }
  ]
}
```

**When a `REPO:{name}` intent is applied**, it generates `moved` blocks for BOTH:

1. `dbtcloud_repository.{name}`
2. `dbtcloud_project_repository.{name}`

This ensures repository and project_repository_link always move together as required by the TF module architecture.

## Key Design Decisions

- **Intent takes precedence**: If intent file says "unprotected", ignore YAML `protected: true`
- **YAML as fallback**: If no intent for a resource, fall back to YAML flag
- **Track application status**: Know if intent has been applied to YAML and TF state
- **History for audit**: Full trail of who changed what and when
- **TF state reference**: Track what TF state was when decision was made

## Protection Architecture (Critical)

**The Terraform module has TWO INDEPENDENT protection scopes:**

### 1. Project Protection (Independent)

A **project** is protected independently. A protected project:

- Cannot be destroyed or replaced
- CAN have its repository/prep replaced or destroyed (if they are unprotected)
- Protection status has no effect on child resources

### 2. Repository + PREP Protection (Paired)

A **repository** and its **project-repository link (PREP)** are ALWAYS protected together as a pair:

- A repository cannot exist without a PREP (1:1 relationship)
- If you protect a repository, the PREP is automatically protected
- If you unprotect a repository, the PREP is automatically unprotected
- They are created/destroyed together

### Protection Matrix


| Scenario        | Project Protected | Repo/PREP Protected | Allowed Operations                 |
| --------------- | ----------------- | ------------------- | ---------------------------------- |
| Fully protected | Yes               | Yes                 | None - all frozen                  |
| Project only    | Yes               | No                  | Can replace/destroy repo+prep      |
| Repo only       | No                | Yes                 | Can replace/destroy project (rare) |
| Unprotected     | No                | No                  | Can replace/destroy all            |


### Intent File Key Format

The intent file tracks protection at the **resource** level with these keys:

- `PRJ:{name}` - Project protection intent (independent)
- `REPO:{name}` - Repository + PREP protection intent (single intent covers both TF resources)

**IMPORTANT: REPO Consolidation**

The `REPO:` key is a single intent that generates TWO Terraform moved blocks:

1. `dbtcloud_repository.{name}`
2. `dbtcloud_project_repository.{name}`

Do NOT use separate `REP:` and `PREP:` keys - these have been deprecated and consolidated into `REPO:`.

When recording a "repository" protection intent, the system automatically applies it to both the repository resource and the project-repository link resource in Terraform.

### Examples

**Protecting only the project:**

```json
{
  "intent": {
    "PRJ:analytics_prod": {
      "protected": true,
      "set_by": "user_click",
      "resource_type": "PRJ"
    }
  }
}
```

**Protecting only the repo+prep (project stays unprotected):**

```json
{
  "intent": {
    "REPO:analytics_prod": {
      "protected": true,
      "set_by": "user_click",
      "resource_type": "REPO"
    }
  }
}
```

**Common case - protecting everything:**

```json
{
  "intent": {
    "PRJ:analytics_prod": { "protected": true, "resource_type": "PRJ" },
    "REPO:analytics_prod": { "protected": true, "resource_type": "REPO" }
  }
}
```

## Implementation

### 1. Create Protection Intent Manager

**New file:** `importer/web/utils/protection_intent.py`

```python
@dataclass
class ProtectionIntent:
    protected: bool
    set_at: str  # ISO timestamp
    set_by: str  # "user_click", "sync_from_tf", "yaml_import"
    reason: str
    applied_to_yaml: bool
    applied_to_tf_state: bool
    tf_state_at_decision: str  # "protected", "unprotected", "unknown"

class ProtectionIntentManager:
    def __init__(self, intent_file: Path):
        self.intent_file = intent_file
        self.intent: dict[str, ProtectionIntent] = {}
        self.history: list[dict] = []
    
    def load(self) -> None
    def save(self) -> None
    def set_intent(self, key: str, protected: bool, source: str, reason: str) -> None
    def get_intent(self, key: str) -> Optional[ProtectionIntent]
    def get_effective_protection(self, key: str, yaml_protected: bool) -> bool
    def mark_applied_to_yaml(self, keys: set[str]) -> None
    def mark_applied_to_tf_state(self, keys: set[str]) -> None
    def get_pending_yaml_updates(self) -> dict[str, bool]
    def get_pending_tf_moves(self) -> list[dict]
```

### 2. Update Mismatch Detection

**File:** `importer/web/components/match_grid.py`

Current logic (line 967):

```python
is_yaml_protected = source_key in protected_resources
```

New logic:

```python
# Get effective protection from intent file (falls back to YAML)
intent = protection_intent_manager.get_intent(source_key)
if intent:
    is_yaml_protected = intent.protected
else:
    is_yaml_protected = source_key in yaml_protected_resources
```

### 3. Update Button Handlers and Add New Button

**File:** `importer/web/pages/match.py`

**Protection Scope Separation in UI:**

The Match page needs to support the two independent protection scopes:


| Button                 | Records Intent For            | TF Resources Affected                                               |
| ---------------------- | ----------------------------- | ------------------------------------------------------------------- |
| Protect All Projects   | `PRJ:{name}` for each project | `dbtcloud_project.{name}`                                           |
| Protect All Repos      | `REPO:{name}` for each repo   | `dbtcloud_repository.{name}` + `dbtcloud_project_repository.{name}` |
| Unprotect All Projects | `PRJ:{name}` for each project | `dbtcloud_project.{name}`                                           |
| Unprotect All Repos    | `REPO:{name}` for each repo   | `dbtcloud_repository.{name}` + `dbtcloud_project_repository.{name}` |


**Or simplified approach (single buttons with scope selection):**

- "Protect All" + scope dropdown: [Projects Only | Repos Only | Both]
- "Unprotect All" + scope dropdown: [Projects Only | Repos Only | Both]

**Intent recording (for each button click):**

1. Write intent to `protection-intent.json` with `applied_to_yaml=False, applied_to_tf_state=False`
2. Use the correct key prefix: `PRJ:{name}` or `REPO:{name}`
3. Add history entry
4. UI shows badge: "Pending: Generate Protection Changes" (orange)
5. Do NOT immediately update YAML

**NEW "Generate Protection Changes" button:**

1. Read pending intents where `applied_to_yaml=False`
2. Update YAML `protected:` flags for those resources
3. Generate `protection_moves.tf` with moved blocks:
  - For `PRJ:{name}` intents: one moved block for project
  - For `REPO:{name}` intents: TWO moved blocks (repo + prep)
4. Mark `applied_to_yaml=True` in intent file
5. UI shows badge: "Pending: TF Init/Plan/Apply" (blue)

**Streaming output for "Generate Protection Changes":**

Show progress dialog with:

- Real-time log of changes being made
- List of YAML files updated
- List of moved blocks generated
- Copy button for output
- Summary at completion

```python
async def run_generate_protection_streaming():
    with ui.dialog() as dialog, ui.card().classes("w-[800px] max-h-[600px]"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Generating Protection Changes...").classes("text-lg font-bold")
            with ui.row().classes("gap-2"):
                ui.button("Copy", icon="content_copy", on_click=copy_output).props("outline")
                ui.button("Close", on_click=dialog.close).props("flat")
        
        output_area = ui.scroll_area().classes("w-full h-[400px] bg-slate-900 p-2")
        with output_area:
            log_container = ui.column().classes("w-full font-mono text-xs text-white")
        
        # Stream progress updates
        log_line("Reading pending intents...")
        log_line(f"Found {n} resources with pending changes")
        log_line("Updating YAML files...")
        for key in pending_keys:
            log_line(f"  - {key}: {'protected' if intent.protected else 'unprotected'}")
        log_line("Generating protection_moves.tf...")
        log_line(f"Generated {m} moved blocks")
        log_line("Done!")
```

**Existing Generate button:**

- Keep for full TF file regeneration
- Add warning tooltip: "Regenerates ALL TF files - use 'Generate Protection Changes' for protection-only updates"

**When TF Apply succeeds:**

1. Read TF state to verify moves completed
2. Mark matching intents as `applied_to_tf_state=True`
3. UI shows "Synced" (green) or removes mismatch indicator

### 4. UI Design (Two-Tier Approach)

**Match Page (Quick Actions):**

- Protect/Unprotect All buttons (existing, now write to intent file)
- NEW "Generate Protection Changes" button (updates YAML + writes moved blocks)
- Intent status badges in mismatch panel:
  - "Pending: Generate Protection Changes" (orange) - intent recorded, not yet generated
  - "Pending: TF Init/Plan/Apply" (blue) - generated, awaiting TF workflow
  - "Synced" (green) - fully applied
- Expandable "Recent Changes" section showing last 5 intent changes
- Link to "View full audit trail in Utilities"
- Warning tooltip on existing "Generate" button about full regeneration
- "Copy for AI" button that generates diagnostic summary (see below)

**AI Diagnostic Copy Feature:**

Add "Copy for AI" button that generates a structured summary for pasting to AI assistants:

```markdown
## Protection Intent Status

**Pending Changes:** 3 resources
**TF Path:** /path/to/terraform

### Resources with Pending Generate:
- sse_dm_fin_fido: unprotect (TF state: protected, YAML: protected)
- bt_data_ops_db: protect (TF state: unprotected, YAML: unprotected)

### Resources with Pending TF Apply:
- analytics_prod: protect (YAML updated, awaiting TF apply)

### Recent History:
| Timestamp | Resource | Action | Source |
|-----------|----------|--------|--------|
| 2026-02-02 10:00 | sse_dm_fin_fido | unprotect | Unprotect All |

### Current YAML Protected Resources:
[list of keys]

### Current TF State Protected Resources:
[list of addresses]
```

**Utilities Page Layout (detailed):**

Inspired by Match page mismatch panel and Destroy page protection panel:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  Protection Management                                                          │
├────────────────────────────────────────────────────────────────────────────────┤
│  Status Summary:                                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ Pending Generate│  │ Pending TF Apply│  │ Synced          │                │
│  │      3          │  │      2          │  │     45          │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
├────────────────────────────────────────────────────────────────────────────────┤
│  Actions:                                                                      │
│  [Reset All to YAML] [Sync from TF State] [Export JSON] [Generate All Pending]│
├────────────────────────────────────────────────────────────────────────────────┤
│  Current Intents                                                               │
│  Filter: [All Status v]  [All Scopes v]  Search: [______]    Showing: 50/50   │
├────────────────────────────────────────────────────────────────────────────────┤
│  Resource Name   │ Scope│ Intent    │ Status           │ Set At     │ Actions │
│  ────────────────┼──────┼───────────┼──────────────────┼────────────┼─────────│
│  sse_dm_fin_fido │ PRJ  │ Unprotect │ Pending Generate │ 2026-02-02 │ [Edit]  │
│  sse_dm_fin_fido │ REPO │ Protect   │ Synced           │ 2026-02-02 │ [Edit]  │
│  bt_data_ops_db  │ PRJ  │ Protect   │ Pending TF Apply │ 2026-02-01 │ [Edit]  │
│  bt_data_ops_db  │ REPO │ Protect   │ Pending TF Apply │ 2026-02-01 │ [Edit]  │
│  analytics_prod  │ PRJ  │ Protect   │ Synced           │ 2026-01-15 │ [Edit]  │
│  analytics_prod  │ REPO │ Protect   │ Synced           │ 2026-01-15 │ [Edit]  │
├────────────────────────────────────────────────────────────────────────────────┤
│  Audit History (last 20)                                          [View All]   │
├────────────────────────────────────────────────────────────────────────────────┤
│  Timestamp           │ Resource              │ Action    │ Source            │  │
│  ────────────────────┼───────────────────────┼───────────┼───────────────────│  │
│  2026-02-02 10:00:00 │ PRJ:sse_dm_fin_fido   │ unprotect │ Unprotect Project │  │
│  2026-02-02 09:45:00 │ REPO:bt_data_ops_db   │ protect   │ Protect Repo+PREP │  │
│  2026-02-01 14:30:00 │ PRJ:analytics_prod    │ protect   │ Manual edit       │  │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Scope Column Values:**

- **PRJ** = Project protection (independent)
- **REPO** = Repository + PREP protection (paired, a single intent covers both TF resources)

**Key features:**

- Status summary cards at top (count by status)
- Bulk action buttons (same pattern as Destroy page)
- AG Grid for current intents with filters (same pattern as Destroy page)
- **Scope filter**: Filter by PRJ (project only) or REPO (repository+prep)
- Audit history table with expandable "View All"
- Edit button on each row opens manual intent editor dialog

**UI Behavior for Repo+PREP pairing:**

When the user protects/unprotects a "REPO" scope item, the intent system automatically:

1. Records a single intent for `REPO:{name}`
2. When generating moves, creates TWO moved blocks:
  - `dbtcloud_repository.{name}` to protected/unprotected module
  - `dbtcloud_project_repository.{name}` to protected/unprotected module

### 5. Destroy Page Integration

**File:** `importer/web/pages/destroy.py`

The Destroy page currently has its own protection panel that uses `state.map.unprotected_keys` to track which resources have been unprotected. This needs to be migrated to use `ProtectionIntentManager`.

**Current code (lines 902-906):**

```python
# Filter out resources that the user has unprotected
unprotected_keys = state.map.unprotected_keys or set()
protected_resources = [
    r for r in all_protected_resources
    if r.resource_key not in unprotected_keys
]
```

**New code:**

```python
# Get effective protection from intent manager
protected_resources = [
    r for r in all_protected_resources
    if protection_intent_manager.get_effective_protection(r.resource_key, yaml_protected=True)
]
```

**Unprotect button handlers** must write to intent file:

```python
async def on_unprotect_selected():
    for key in selected_keys:
        protection_intent_manager.set_intent(
            key=key,
            protected=False,
            source="destroy_page_unprotect_selected",
            reason=f"Unprotected from Destroy page ({len(selected_keys)} selected)"
        )
    protection_intent_manager.save()
    ui.notify("Intent recorded - click 'Generate Protection Changes' on Match page to apply")
```

**UI changes:**

- Add same status badges as Match page: "Pending: Generate Protection Changes", "Pending: TF Init/Plan/Apply"
- Add link to Match page: "Apply protection changes on Match page"
- Keep the unprotect functionality but make it record intent only

### 6. ProjectManager Integration

**File:** `importer/web/project_manager.py` (from project-based state plan)

Add methods for protection intent:

```python
class ProjectManager:
    # ... existing methods ...
    
    def get_protection_intent_path(self, slug: str) -> Path:
        return self.get_project_path(slug) / "protection-intent.json"
    
    def load_protection_intent(self, slug: str) -> ProtectionIntentManager:
        """Load protection intent for a project."""
        intent_path = self.get_protection_intent_path(slug)
        manager = ProtectionIntentManager(intent_path)
        manager.load()
        return manager
    
    def create_project(self, name, workflow_type, description):
        # ... existing logic ...
        # Initialize empty protection-intent.json
        intent_manager = ProtectionIntentManager(project_path / "protection-intent.json")
        intent_manager.save()  # Creates empty file
```

### 6. Files to Modify


| File                                          | Changes                                                                                      |
| --------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `importer/web/utils/protection_intent.py`     | NEW - Intent manager class                                                                   |
| `importer/web/project_manager.py`             | Add protection intent methods (ties to project-based state plan)                             |
| `importer/web/pages/match.py`                 | Use intent manager, add "Recent Changes" section, link to Utilities                          |
| `importer/web/pages/utilities.py`             | NEW - Create Utilities page with "Protected Resource Management" section                     |
| `importer/web/components/match_grid.py`       | Use intent for mismatch detection                                                            |
| `importer/web/state.py`                       | Add `protection_intent: ProtectionIntentManager` field, deprecate `protected_resources`      |
| `importer/web/utils/adoption_yaml_updater.py` | Read from intent file instead of direct sets                                                 |
| `importer/web/pages/destroy.py`               | Update protection panel to use ProtectionIntentManager instead of state.map.unprotected_keys |


## Migration Path

**For project-based workflow (after project-based state management is implemented):**

1. When creating a new project via `ProjectManager.create_project()`:
  - Initialize empty `protection-intent.json` in project folder
2. When loading a project with existing YAML but no intent file:
  - Read current YAML `protected: true` flags
  - Read current TF state protected resources
  - Initialize intent file with current state (marked as `applied_to_yaml=true, applied_to_tf_state=true`)

**For legacy workflow (before project-based state management):**

1. On first load of a deployment, if no `protection-intent.json` exists:
  - Create it in the deployment directory (e.g., `deployments/migration/protection-intent.json`)
  - Read current YAML `protected: true` flags
  - Read current TF state protected resources
  - Initialize intent file with current state (marked as applied)
2. Existing `state.map.protected_resources` can be deprecated and removed after migration

**Backward compatibility:**

- If no active project, fall back to deployment directory for intent file
- `ProtectionIntentManager` accepts a path, works the same regardless of location

## Workflow Diagram

```
User clicks "Protect All" or "Unprotect All"
        |
        v
Write intent: {protected: bool, applied_to_yaml: false, applied_to_tf_state: false}
        |
        v
UI shows: "Pending: Generate Protection Changes" (orange badge)
        |
        v
User clicks "Generate Protection Changes"
        |
        v
Update YAML protected: flags -> Generate protection_moves.tf -> Mark applied_to_yaml=true
        |
        v
UI shows: "Pending: TF Init/Plan/Apply" (blue badge)
        |
        v
User runs Init -> Plan -> Apply (existing buttons)
        |
        v
On success: Read TF state -> Mark applied_to_tf_state=true
        |
        v
UI shows: "Synced" (green) or mismatch removed
```

## User Stories (for PRD)

### 4.1 Intent Recording (Match Page)


| ID       | Story                                                                                                  | Acceptance Criteria                                                     |
| -------- | ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| US-PI-01 | As a user, I want clicking "Protect All" to record my intent without immediately changing YAML         | Intent written to `protection-intent.json` with `applied_to_yaml=false` |
| US-PI-02 | As a user, I want clicking "Unprotect All" to record my intent without immediately changing YAML       | Intent written with `protected=false`, `applied_to_yaml=false`          |
| US-PI-03 | As a user, I want to see an orange badge "Pending: Generate Protection Changes" after recording intent | Badge appears in mismatch panel with count of pending resources         |
| US-PI-04 | As a user, I want to change my mind and click the opposite button before generating                    | New intent overwrites previous, history records both actions            |
| US-PI-05 | As a user, I want the intent to include timestamp and source for audit                                 | `set_at`, `set_by`, `reason` fields populated                           |
| US-PI-06 | As a user, I want buttons to have proper icons (shield for protect, lock_open for unprotect)           | Icons appear left of text, not in middle                                |


### 4.2 Generate Protection Changes


| ID       | Story                                                                                          | Acceptance Criteria                                                   |
| -------- | ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| US-PI-10 | As a user, I want a "Generate Protection Changes" button separate from full Generate           | New button in mismatch panel, distinct from TF workflow Generate      |
| US-PI-11 | As a user, I want clicking "Generate Protection Changes" to update YAML `protected:` flags     | YAML files modified for all pending intents                           |
| US-PI-12 | As a user, I want `protection_moves.tf` generated with moved blocks                            | File created with correct `moved { from = ... to = ... }` blocks      |
| US-PI-13 | As a user, I want to see streaming progress during generation                                  | Dialog shows: reading intents, updating YAML, generating moved blocks |
| US-PI-14 | As a user, I want a Copy button in the streaming dialog                                        | Copies full output to clipboard                                       |
| US-PI-15 | As a user, I want the badge to change to "Pending: TF Init/Plan/Apply" (blue) after generation | Badge color and text update to indicate next step                     |
| US-PI-16 | As a user, I want intent marked as `applied_to_yaml=true` after generation                     | Intent file updated, prevents duplicate YAML changes                  |


### 4.3 Terraform Workflow Integration


| ID       | Story                                                                                | Acceptance Criteria                                                                       |
| -------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| US-PI-20 | As a user, I want a warning tooltip on the existing Generate button                  | Tooltip: "Regenerates ALL TF files - use Generate Protection Changes for protection-only" |
| US-PI-21 | As a user, I want successful TF Apply to mark intents as `applied_to_tf_state=true`  | After apply success, intent file updated                                                  |
| US-PI-22 | As a user, I want the badge to show "Synced" (green) or mismatch removed after apply | Visual confirmation that protection changes are complete                                  |
| US-PI-23 | As a user, I want View Output button to show apply logs with protection moves        | Output includes `moved` actions from Terraform                                            |


### 4.4 AI Diagnostic Copy


| ID       | Story                                                                               | Acceptance Criteria                                                     |
| -------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| US-PI-30 | As a user, I want a "Copy for AI" button in the mismatch panel                      | Button generates structured markdown summary                            |
| US-PI-31 | As a user, I want the AI summary to include pending changes with before/after state | Shows resource key, intended protection, current YAML, current TF state |
| US-PI-32 | As a user, I want the AI summary to include recent history                          | Last 5-10 intent changes with timestamps                                |
| US-PI-33 | As a user, I want the AI summary to include TF path and file locations              | Context for debugging                                                   |


### 4.5 Utilities Page - Protection Management


| ID       | Story                                                                                | Acceptance Criteria                                                    |
| -------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| US-PI-40 | As a user, I want a "Protection Management" section on a new Utilities page          | New page accessible from navigation                                    |
| US-PI-41 | As a user, I want status summary cards showing counts by status                      | Cards: Pending Generate, Pending TF Apply, Synced                      |
| US-PI-42 | As a user, I want an AG Grid showing all current intents                             | Grid with columns: Resource Key, Type, Intent, Status, Set At, Actions |
| US-PI-43 | As a user, I want to filter intents by status (Pending Generate, Pending TF, Synced) | Dropdown filter above grid                                             |
| US-PI-44 | As a user, I want to filter intents by resource type (PRJ, ENV, JOB, etc.)           | Type dropdown filter                                                   |
| US-PI-45 | As a user, I want to search intents by resource key                                  | Quick search input                                                     |
| US-PI-46 | As a user, I want an Edit button to manually modify an intent                        | Opens dialog to change protected status                                |
| US-PI-47 | As a user, I want to export intents to JSON                                          | Download button for `protection-intent.json`                           |


### 4.6 Utilities Page - Bulk Actions


| ID       | Story                                                    | Acceptance Criteria                                       |
| -------- | -------------------------------------------------------- | --------------------------------------------------------- |
| US-PI-50 | As a user, I want a "Reset All to YAML" button           | Clears all intents, falls back to YAML `protected:` flags |
| US-PI-51 | As a user, I want a confirmation dialog before Reset All | "This will clear all intent history. Continue?"           |
| US-PI-52 | As a user, I want a "Sync from TF State" button          | Reads TF state, sets intents to match current reality     |
| US-PI-53 | As a user, I want a "Generate All Pending" button        | Processes all Pending Generate intents at once            |


### 4.7 Utilities Page - Audit History


| ID       | Story                                                               | Acceptance Criteria                           |
| -------- | ------------------------------------------------------------------- | --------------------------------------------- |
| US-PI-60 | As a user, I want to see an Audit History table with recent changes | Table: Timestamp, Resource, Action, Source    |
| US-PI-61 | As a user, I want history sorted newest first                       | Most recent at top                            |
| US-PI-62 | As a user, I want a "View All" link to see full history             | Expands or opens dialog with complete history |
| US-PI-63 | As a user, I want to copy audit history for documentation           | Copy button for history                       |


### 4.8 Destroy Page Integration


| ID       | Story                                                                                               | Acceptance Criteria                                                 |
| -------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| US-PI-70 | As a user, I want "Unprotect Selected" on Destroy page to record intent (not change state directly) | Writes to intent file, shows pending badge                          |
| US-PI-71 | As a user, I want "Unprotect All" on Destroy page to record intent                                  | All selected resources get intent recorded                          |
| US-PI-72 | As a user, I want to see the same pending badges on Destroy page as Match page                      | Orange/blue/green badges consistent                                 |
| US-PI-73 | As a user, I want a link "Apply protection changes on Match page"                                   | Navigates to Match page for Generate/Apply workflow                 |
| US-PI-74 | As a user, I want the protection panel to read effective protection from intent file                | Uses `get_effective_protection()`, not `state.map.unprotected_keys` |


### 4.9 Migration and Initialization


| ID       | Story                                                                            | Acceptance Criteria                                           |
| -------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| US-PI-80 | As a user, I want automatic migration when no intent file exists                 | On first load, creates intent file from YAML + TF state       |
| US-PI-81 | As a user, I want existing YAML `protected:` flags honored during migration      | Migration reads YAML, marks as `applied_to_yaml=true`         |
| US-PI-82 | As a user, I want existing TF state protected resources honored during migration | Migration reads TF state, marks as `applied_to_tf_state=true` |
| US-PI-83 | As a user, I want graceful handling if intent file is corrupted                  | Error message with option to reset                            |


### 4.10 Edge Cases


| ID       | Story                                                             | Acceptance Criteria                                     |
| -------- | ----------------------------------------------------------------- | ------------------------------------------------------- |
| US-PI-90 | As a user, I want intent preserved if I navigate away and return  | Intent file persists, UI shows correct badges on reload |
| US-PI-91 | As a user, I want concurrent browser tabs to see consistent state | Last write wins, no crashes                             |
| US-PI-92 | As a user, I want clear error if TF state is unavailable          | Warning message, allows manual workflow                 |
| US-PI-93 | As a user, I want intent for deleted resources handled gracefully | Orphan intents cleaned up or marked                     |


## Test Cases

### Unit Tests (pytest)

**ProtectionIntentManager tests:**


| Test ID | Description                                                                  |
| ------- | ---------------------------------------------------------------------------- |
| PI-01   | `set_intent()` creates new intent with correct timestamps and flags          |
| PI-02   | `set_intent()` overwrites existing intent, adds to history                   |
| PI-03   | `get_effective_protection()` returns intent value when exists                |
| PI-04   | `get_effective_protection()` falls back to yaml_protected when no intent     |
| PI-05   | `mark_applied_to_yaml()` sets flag, preserves other fields                   |
| PI-06   | `mark_applied_to_tf_state()` sets flag, preserves other fields               |
| PI-07   | `get_pending_yaml_updates()` returns only intents with applied_to_yaml=False |
| PI-08   | `get_pending_tf_moves()` returns only intents with applied_to_tf_state=False |
| PI-09   | `load()` handles missing file gracefully (creates empty)                     |
| PI-10   | `save()` and `load()` roundtrip preserves all data                           |


### Browser Tests (cursor-browser-extension MCP)

**Match Page Workflow Tests:**


| Test ID | Description                                                                                         |
| ------- | --------------------------------------------------------------------------------------------------- |
| MW-01   | Click "Protect All" records intent, shows orange badge "Pending: Generate Protection Changes"       |
| MW-02   | Click "Generate Protection Changes" updates YAML, shows blue badge "Pending: TF Init/Plan/Apply"    |
| MW-03   | Successful Apply marks intent synced, shows green badge or removes mismatch                         |
| MW-04   | Multiple select-generate-plan cycles: select A, generate, select B, generate - both intents tracked |
| MW-05   | Abandon workflow: select A, generate, then select different B without apply - A stays pending TF    |
| MW-06   | Cancel intent: record unprotect, then change mind and record protect for same resource              |
| MW-07   | Mixed batch: protect some, unprotect others in same session, generate handles both                  |


**Destroy Page Workflow Tests:**


| Test ID | Description                                                                            |
| ------- | -------------------------------------------------------------------------------------- |
| DW-01   | Unprotect Selected records intent to intent file (not just state.map.unprotected_keys) |
| DW-02   | Unprotect All records multiple intents, all show pending status                        |
| DW-03   | Unprotect on Destroy page shows same pending badges as Match page                      |
| DW-04   | Navigate Match -> Destroy -> Match: intent state persists                              |


**Utilities Page Tests:**


| Test ID | Description                                                   |
| ------- | ------------------------------------------------------------- |
| UP-01   | Status summary cards show correct counts                      |
| UP-02   | Filter by status shows only matching intents                  |
| UP-03   | "Reset All to YAML" clears all intents, UI updates            |
| UP-04   | "Sync from TF State" reads TF state, updates intents          |
| UP-05   | "Generate All Pending" processes all pending-generate intents |
| UP-06   | Edit button opens dialog, changes are saved                   |
| UP-07   | Audit history shows recent changes in correct order           |


**Streaming and Output Tests:**


| Test ID | Description                                                          |
| ------- | -------------------------------------------------------------------- |
| SO-01   | "Generate Protection Changes" shows streaming progress dialog        |
| SO-02   | Streaming dialog shows YAML files updated and moved blocks generated |
| SO-03   | Copy button in streaming dialog copies full output to clipboard      |
| SO-04   | "Copy for AI" generates structured diagnostic summary                |
| SO-05   | View Output buttons work for Generate, Init, Plan, Apply steps       |
| SO-06   | Output persists after dialog close (can re-open and view)            |
| SO-07   | Search in streaming dialog finds matching lines                      |
| SO-08   | Cancel button in streaming dialog cancels running operation          |


**Edge Case Tests:**


| Test ID | Description                                                       |
| ------- | ----------------------------------------------------------------- |
| EC-01   | No intent file exists - migration creates from YAML + TF state    |
| EC-02   | Intent file corrupted JSON - graceful error, option to reset      |
| EC-03   | Resource deleted from YAML but intent exists - handled gracefully |
| EC-04   | TF state unavailable - shows warning, allows manual workflow      |
| EC-05   | Concurrent edits (two browser tabs) - last write wins, no crash   |


## Match Page Button Layout and Styling

**Protection Scope Separation:**

Since projects and repos+prep have independent protection, the UI needs to handle both:

**Option A: Scope Dropdown (Recommended)**

```
Scope: [▼ Both]  [🛡 Protect All]  [🔓 Unprotect All]
       ├─ Both
       ├─ Projects Only  
       └─ Repos Only (includes PREP)
```

**Option B: Separate Buttons**

```
Projects: [🛡 Protect All Projects]  [🔓 Unprotect All Projects]
Repos:    [🛡 Protect All Repos]     [🔓 Unprotect All Repos]
```

**Button styling requirements:**

- Consistent sizing: `props("size=sm")` with `style("min-width: 120px")`
- Color scheme:
  - "Protect All" - primary (blue)
  - "Unprotect All" - amber with black text: `props("color=amber").style("color: black !important;")`
  - "Generate Protection Changes" - green: `props("color=green")`

**BUG FIX: Icons appearing in middle of text**

Current code uses `set_icon()` dynamically which causes icons to appear in wrong position:

```python
# BAD - causes icon positioning issues
protect_btn.set_icon("shield")
```

Fix: Create buttons with `icon=` parameter initially:

```python
# GOOD - icon positioned correctly
protect_btn = ui.button("Protect All", icon="shield").props("color=positive")
```

- "Protect All" - `icon="shield"`
- "Unprotect All" - `icon="lock_open"`
- "Generate Protection Changes" - `icon="auto_fix_high"`
- Badge styling:
  - Orange badge: `classes("bg-amber-100 text-amber-800 px-2 py-1 rounded text-xs")`
  - Blue badge: `classes("bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs")`
  - Green badge: `classes("bg-green-100 text-green-800 px-2 py-1 rounded text-xs")`

**Layout:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Protection Mismatch (3 projects, 3 repos)                  [Recent Changes]│
├─────────────────────────────────────────────────────────────────────────────┤
│  Actions:                                                                   │
│  Scope: [▼ Both]  [🛡 Protect All]  [🔓 Unprotect All]                     │
│         ├─ Both                                                             │
│         ├─ Projects Only                                                    │
│         └─ Repos Only (includes PREP)                                       │
│                                                                             │
│  [⚙ Generate Protection Changes]                                           │
│                                                                             │
│  Status: ┌─────────────────────────────────────────────────┐               │
│          │ Pending: Generate Protection Changes            │ (orange badge) │
│          │ 2 projects, 1 repo                              │               │
│          └─────────────────────────────────────────────────┘               │
│                                                                             │
│  Mismatched resources listed below...                                       │
│  (Grid shows both project and repo mismatches with scope indicator)         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  Terraform Workflow                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Generate ⚠️]  [Init]  [Plan]  [Apply]  [View Output]                     │
│  └── Warning tooltip: "Regenerates ALL TF files..."                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Important Note on Repo+PREP Behavior:**

When "Repos Only" is selected and user clicks "Protect All" or "Unprotect All":

- Intent is recorded for `REPO:{name}` (single key)
- When Generate Protection Changes runs, it creates TWO moved blocks:
  1. `moved { from = module.unprotected.dbtcloud_repository.{name} to = module.protected... }`
  2. `moved { from = module.unprotected.dbtcloud_project_repository.{name} to = module.protected... }`
- This ensures repo and PREP always move together as required by the TF module architecture

