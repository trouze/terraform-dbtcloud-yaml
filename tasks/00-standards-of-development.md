# 0. Standards of Development

This document establishes the development methodology, quality standards, and tooling requirements for the dbt Cloud YAML Importer project.

---

## 0.1 Development Methodology

### Project Context

This project provides a **NiceGUI-based web UI** for adopting dbt Cloud resources into Terraform management. Key technologies:

- **Python 3.12+** with type annotations
- **NiceGUI** for the web interface
- **AG Grid** for data tables
- **Terraform** for infrastructure as code
- **YAML** for configuration management

### Task Management

All development work is tracked in PRD (Product Requirements Document) files in the `tasks/` folder:

| PRD Pattern | Purpose |
|-------------|---------|
| `prd-web-ui-XX-*.md` | Web UI feature PRDs |
| `prd-*.md` | General feature PRDs |
| `00-standards-of-development.md` | This standards document |

### State Management

The application uses in-memory session state via `importer/web/state.py`. Key considerations:

- **Server restart clears all state** - Always reload credentials after restart
- **State persists in `AppState`** - Access via `state.map`, `state.fetch`, etc.
- **YAML files are the source of truth** - For configuration and mappings

---

## 0.2 Quality Standards

### Code Quality

| Standard | Requirement |
|----------|-------------|
| **Python Version** | 3.12+ |
| **Type Hints** | Required on all function parameters and returns |
| **Linting** | No linting errors in committed code |
| **Formatting** | Consistent formatting (use IDE auto-format) |
| **Documentation** | Docstrings for public functions and classes |

#### Python Style Reference

```python
from typing import Optional

async def update_protection(
    resource_key: str,
    protected: bool,
    *,
    reason: str | None = None,
) -> dict:
    """
    Update the protection status of a resource.
    
    Args:
        resource_key: The unique resource identifier (e.g., "PRJ:my_project")
        protected: Whether to protect or unprotect
        reason: Optional reason for the change
    
    Returns:
        Dict with updated protection status and metadata
    
    Raises:
        ValueError: If resource_key is invalid
    """
    pass
```

### Testing Requirements

| Level | When Required | Tools |
|-------|---------------|-------|
| **Unit Tests** | Business logic, utilities | pytest |
| **Browser Tests** | UI changes, user flows | cursor-browser-extension MCP |
| **Integration Tests** | API endpoints, state management | pytest + fixtures |

### Commit Standards (Conventional Commits)

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`

**Examples:**
```
feat(match): add protection intent recording
fix(grid): prevent phantom column bug with explicit colId
docs(prd): add user stories for protection workflow
refactor(state): migrate to ProtectionIntentManager
```

---

## 0.3 Definition of Done

A user story or criterion is complete when:

- [ ] Code implemented and compiles without errors
- [ ] Linter passes (`ReadLints` shows no new errors)
- [ ] Unit tests pass for new functionality
- [ ] Browser validation passes (if UI change)
- [ ] Debug instrumentation added (`@traced`, `log_action`, `log_state_change`)
- [ ] Changes committed with descriptive message
- [ ] PRD user story checkbox marked `[x]`

---

## 0.4 Session Protocol

### Starting a Session

1. **Read the relevant PRD** - Understand current task and find unchecked criteria
2. **Check recent logs** - Review `.cursor/debug.log` for errors from last session
3. **Restart server if testing UI** - Run `./restart_web.sh` for clean state
4. **Load credentials** - Navigate to `/fetch_target` and click "Load .env"
5. **Review guardrails** - Check `.ralph/guardrails.md` for known pitfalls

### Ending a Session

1. **Save all changes** - Ensure files are written and saved
2. **Run tests** - Verify nothing is broken
3. **Update PRD checkboxes** - Mark completed criteria as `[x]`
4. **Commit work** - Use conventional commit format
5. **Note blockers** - Document any issues for next session

### Browser Testing Workflow

```bash
# 1. Restart server
./restart_web.sh

# 2. Wait for startup, then navigate and test
# Use cursor-browser-extension MCP tools:
# - browser_navigate
# - browser_snapshot
# - browser_click
# - browser_fill
```

---

## 0.5 Guardrails

Guardrails are lessons learned from failures. They prevent repeating mistakes.

### Format

```markdown
### Sign: [Short description]
- **Trigger**: When this situation occurs
- **Instruction**: What to do instead
- **Evidence**: Error message or symptom
- **Added after**: Session/PR that caused this
```

### Active Guardrails

See `.ralph/guardrails.md` for the full list. Key guardrails include:

#### Sign: AG Grid phantom columns
- **Trigger**: Adding sorting or new columns to AG Grid
- **Instruction**: Always add explicit `colId` to every column definition
- **Evidence**: Column headers show "Name 3", "Sort Key 2"
- **Added after**: PRD-11 Grid Standardization

#### Sign: Button icon in middle of text
- **Trigger**: Adding icons to NiceGUI buttons
- **Instruction**: Pass `icon=` parameter on button creation, never use `set_icon()` dynamically
- **Evidence**: Icon appears in middle of button text instead of left side
- **Added after**: Protection Intent planning session

#### Sign: Observable type crashes AG Grid
- **Trigger**: Passing NiceGUI reactive data to AG Grid
- **Instruction**: Convert to plain dicts: `[dict(item) for item in data]`
- **Evidence**: Grid crashes or shows incorrect data
- **Added after**: PRD-06 Enhanced Matching

#### Sign: Protection state desync
- **Trigger**: Protection changes not reflecting in UI or Terraform
- **Instruction**: Use `ProtectionIntentManager` (when implemented), always save intent file after changes
- **Evidence**: Protection status flip-flops between operations
- **Added after**: Protection workflow debugging session

---

## 0.6 Tips for AI Agents

> **Common Pitfalls to Avoid**

### NiceGUI / UI

- **Never use `set_icon()` dynamically** - Pass `icon=` on button creation
- **Amber buttons need text fix** - Use `props("color=amber").style("color: black !important;")`
- **Always restart server before testing** - Run `./restart_web.sh`
- **Load credentials after restart** - Navigate to `/fetch_target`, click "Load .env"
- **Handle dialogs in snapshots** - Dialogs appear at end of browser snapshots

### AG Grid

- **Always use both theme settings** - `theme="quartz"` AND `.classes("ag-theme-quartz-auto-dark")`
- **Explicit `colId` on every column** - Prevents phantom column bug
- **Pre-sort data in Python** - Never use `initialState.sortModel` or column `sort` properties
- **Use `cellDataType: False` for booleans** - Prevents unwanted checkbox rendering
- **Use `run_grid_method` for updates** - Never mutate `grid.options` directly
- **Convert Observable types** - `[dict(item) for item in data]` before passing to grid

### Debug Instrumentation

- **Never remove logging code** - Even "temporary" debugging instrumentation stays
- **Use `@traced` decorator** - On complex functions, protection logic, state mutations
- **Use logging utilities** - `log_action`, `log_state_change`, `log_error` from `ui_logger`
- **Keep hypothesis markers** - `[HA]`, `[HB]` prefixes indicate active debugging
- **Log before/after for state changes** - Include both values in `log_state_change`

### Terraform Generation

- **Preserve `protection_moves.tf` structure** - Don't accidentally overwrite with full generate
- **Use `moved` blocks for state migration** - Required for protection changes
- **Check for existing imports** - Before regenerating import blocks
- **Run init/plan/apply sequence** - Always in order after generating TF files

### Protection Workflow

- **Use `ProtectionIntentManager`** - When implemented, this is the source of truth
- **Check `get_effective_protection()`** - Not YAML `protected:` flag directly
- **Save intent file after modifications** - Persistence is explicit, not automatic
- **Record intent before YAML update** - Intent file tracks user decisions

### File Operations

- **Read before editing** - Always use Read tool before StrReplace
- **Check lints after edits** - Use ReadLints on modified files
- **Don't create unnecessary files** - Prefer editing existing files

---

## 0.7 Debug Instrumentation

**Full Reference:** [`tasks/prd-web-ui-12-debug-logging-standards.md`](prd-web-ui-12-debug-logging-standards.md)

### Log File Locations

| Log Type | Path | Format |
|----------|------|--------|
| UI Actions | `.cursor/ui_actions.log` | JSON Lines |
| Debug Log | `.cursor/debug.log` | Standard logging |

### Quick Reference

```python
from importer.web.utils.ui_logger import (
    log_action,
    log_navigation,
    log_state_change,
    log_generate_step,
    log_error,
    traced,
)

# Button click
log_action("protect_button", "clicked", {"resource_key": key})

# State change with before/after
log_state_change(
    "protected_resources",
    "add",
    {"keys": keys},
    before=before_set,
    after=after_set
)

# Function tracing
@traced
def apply_protection(keys: list[str]) -> None:
    pass
```

### Analyzing Logs

```bash
# View all logs
cat .cursor/ui_actions.log | jq .

# Filter by type
cat .cursor/ui_actions.log | jq 'select(.type == "action")'

# Find errors
cat .cursor/ui_actions.log | jq 'select(.type == "error")'

# Timeline
cat .cursor/ui_actions.log | jq -r '[.timestamp, .type, .component // .function] | @tsv'
```

---

## 0.8 AG Grid Standards

**Full Reference:** [`.cursor/rules/ag-grid-standards.mdc`](../.cursor/rules/ag-grid-standards.mdc)

### Theme Requirements

```python
# CORRECT - both are required
grid = ui.aggrid(options, theme="quartz").classes("w-full h-full ag-theme-quartz-auto-dark")
```

### Column Definition Pattern

```python
column_defs = [
    {
        "field": "name",
        "colId": "name",  # REQUIRED - prevents phantom columns
        "headerName": "Name",
        "sortable": True,
        "filter": True,
    },
    {
        "field": "is_protected",
        "colId": "is_protected",
        "headerName": "Protected",
        "cellDataType": False,  # Prevents unwanted checkbox
        ":valueFormatter": "params => params.value ? '✓' : ''",
    },
]
```

### Row Selection (AG Grid v32+)

```python
grid_options = {
    "rowSelection": {
        "mode": "multiRow",
        "headerCheckbox": True,
        "checkboxes": True,
    },
    "suppressRowClickSelection": True,
}
```

### Dialog Pattern

```python
def show_dialog(data: dict) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl"):
        # Header with close button
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Title").classes("text-xl font-bold")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense")
        
        # Content
        with ui.scroll_area().style("height: 60vh;"):
            # ... content ...
    
    dialog.open()  # IMPORTANT: call after definition
```

---

## 0.9 Browser Testing

**Full Reference:** [`.cursor/rules/browser-testing.mdc`](../.cursor/rules/browser-testing.mdc)

### Standard Workflow

1. **Restart server**: `./restart_web.sh`
2. **Navigate**: `browser_navigate` to target page
3. **Load credentials**: Go to `/fetch_target`, click "Load .env"
4. **Snapshot**: `browser_snapshot` to see current state
5. **Interact**: Use refs from snapshot to click/fill
6. **Verify**: Take another snapshot to confirm changes

### MCP Tools

| Tool | Purpose |
|------|---------|
| `browser_navigate` | Navigate to URL |
| `browser_snapshot` | Capture page state with element refs |
| `browser_click` | Click element by ref |
| `browser_fill` | Clear and fill input |
| `browser_press_key` | Send keyboard input (e.g., "Escape") |

### Tips

- Dialogs appear at end of snapshots
- Use `Grep` on snapshot files to find elements in large pages
- Session state clears on server restart - always reload credentials

---

## 0.10 Project Structure

```
terraform-dbtcloud-yaml/
├── importer/
│   ├── web/
│   │   ├── pages/              # UI pages
│   │   │   ├── match.py        # Resource matching
│   │   │   ├── destroy.py      # Resource destruction
│   │   │   ├── fetch_target.py # Credential management
│   │   │   └── ...
│   │   ├── components/         # Reusable UI components
│   │   │   ├── match_grid.py   # Mismatch grid component
│   │   │   └── ...
│   │   ├── utils/              # Utilities
│   │   │   ├── ui_logger.py    # Logging utilities
│   │   │   ├── adoption_yaml_updater.py
│   │   │   └── ...
│   │   ├── state.py            # Application state (AppState)
│   │   └── project_manager.py  # Project-based state (when implemented)
│   ├── core/                   # Business logic
│   └── tests/                  # Test files
├── tasks/                      # PRD documents
├── .cursor/
│   ├── rules/                  # Cursor rules for AI agents
│   ├── plans/                  # Active development plans
│   ├── ui_actions.log          # UI action log
│   └── debug.log               # Debug log
├── .ralph/                     # Development methodology state
│   ├── guardrails.md           # Lessons learned
│   └── screenshots/            # Browser test evidence
├── test/                       # Integration tests
├── dev_support/                # Development YAML samples
└── restart_web.sh              # Server restart script
```

---

## 0.11 PRD Structure Template

All PRDs should follow this structure:

```markdown
# PRD: [Feature Name]

**PRD ID:** prd-web-ui-XX
**Status:** Draft | Active | Complete
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
**Version:** X.Y.Z

---

## Executive Summary

[1-2 paragraph overview of the feature]

---

## Goals

1. [Primary goal]
2. [Secondary goal]

---

## Non-Goals

- [What this PRD does NOT cover]

---

## User Stories

### US-XX-01: [Story Title]

**As a** [user type],
**I want** [capability],
**So that** [benefit].

**Acceptance Criteria:**
- [ ] [Criterion 1]
- [ ] [Criterion 2]

---

## Technical Implementation

### Files to Modify

| File | Changes |
|------|---------|
| `path/to/file.py` | Description of changes |

### Key Components

[Technical details, code patterns, architecture decisions]

---

## Test Plan

### Unit Tests

| Test ID | Description | Status |
|---------|-------------|--------|
| UT-XX-01 | [Test description] | [ ] |

### Browser Tests

| Test ID | Description | Status |
|---------|-------------|--------|
| E2E-XX-01 | [Test description] | [ ] |

---

## Definition of Done

See [Section 0.3](#03-definition-of-done) of Standards of Development.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | YYYY-MM-DD | Initial version |
```

---

## 0.12 Navigation

### PRD Documents

| PRD | Title | Status |
|-----|-------|--------|
| [00](00-standards-of-development.md) | Standards of Development | Active |
| [01](prd-web-ui-01-core-shell.md) | Core Shell | Complete |
| [02](prd-web-ui-02-fetch.md) | Fetch | Complete |
| [03](prd-web-ui-03-explore.md) | Explore | Complete |
| [04](prd-web-ui-04-map.md) | Map | Complete |
| [05](prd-web-ui-05-deploy.md) | Deploy | Complete |
| [06](prd-web-ui-06-enhanced-matching.md) | Enhanced Matching | Complete |
| [07](prd-web-ui-07-jobs-as-code-generator.md) | Jobs as Code Generator | Active |
| [08](prd-web-ui-08-project-management.md) | Project Management | Active |
| [09](prd-web-ui-09-resource-protection.md) | Resource Protection | Active |
| [10](prd-web-ui-10-destroy-page-refactor.md) | Destroy Page Refactor | Active |
| [11](prd-web-ui-11-grid-standardization.md) | Grid Standardization | Complete |
| [12](prd-web-ui-12-debug-logging-standards.md) | Debug Logging Standards | Active |

### Cursor Rules

| Rule | Purpose |
|------|---------|
| [ag-grid-standards.mdc](../.cursor/rules/ag-grid-standards.mdc) | AG Grid patterns and requirements |
| [debug-instrumentation.mdc](../.cursor/rules/debug-instrumentation.mdc) | Logging and tracing standards |
| [browser-testing.mdc](../.cursor/rules/browser-testing.mdc) | Browser testing workflow |

### Plans (Active Development)

Plans are stored in `.cursor/plans/` and track in-progress features:

- Protection Intent File System
- Project-Based State Management
- Extended Attributes Support

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-29 | Initial version - consolidated from cursor rules and cursor-command templates |
