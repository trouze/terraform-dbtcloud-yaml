# RALPH_TASK.md Specification

This document defines the format for task definition files used in the Ralph Wiggum methodology.

## File Location

Place `RALPH_TASK.md` in the project root directory. For multi-track projects, use:
- `RALPH_TASK.md` - Protection Intent track (active phase)
- `RALPH_TASK_PM_PHASE{N}.md` - Project Management track phases
- `RALPH_TASK_EA_PHASE{N}.md` - Extended Attributes track phases

## Structure

```markdown
---
task: Short description of what to build
test_command: "command to run tests"
browser_validation: true|false
base_url: "http://localhost:8501"
---

# Task: [Title]

[Optional description of the overall task]

**Plan Reference:** Path to detailed plan document
**Depends on:** Prerequisites from other phases

## Success Criteria

### Category Name (optional grouping)

1. [ ] First criterion - specific, testable outcome
2. [ ] Second criterion - another testable outcome
3. [ ] Third criterion - and so on

### Another Category

4. [ ] Fourth criterion
5. [ ] Fifth criterion

### Browser Validation (if applicable)

N. [ ] Navigate to page X, verify Y
N+1. [ ] Test interaction Z, verify result

## Context

- Technology stack details
- API documentation links
- Constraints and requirements
- Key patterns to follow

## Notes

- Guidelines for the agent
- Special considerations
- Which criteria require browser validation
```

## Frontmatter Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `task` | string | Brief description of what to build (1-100 chars) |
| `test_command` | string | Shell command to validate work (e.g., `cd importer && python -m pytest -v`) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `browser_validation` | boolean | `false` | Enable MCP browser tool validation |
| `base_url` | string | - | Base URL for browser testing |

## Success Criteria Format

### Rules

1. Use numbered list with checkbox syntax: `1. [ ] Criterion`
2. Group related criteria under section headings (### Category Name)
3. Each criterion must be:
   - **Specific** - Clear what "done" looks like
   - **Testable** - Can be verified programmatically or visually
   - **Atomic** - Completable in a single iteration
   - **Independent** - Minimal dependencies on other criteria (when possible)

4. Mark completed criteria: `1. [x] Criterion`

### Good Examples

```markdown
## Success Criteria

### Core Infrastructure

1. [ ] ProtectionIntentManager class created in `importer/web/utils/protection_intent.py`
2. [ ] Class has `set_intent()` method accepting resource_key, protected bool, source string
3. [ ] Class has `get_effective_protection()` method returning intent or YAML fallback

### File Persistence

4. [ ] Intent file saves to `{deployment_dir}/protection-intent.json`
5. [ ] File format includes intents dict and history list
6. [ ] Load method restores both intents and history from existing file

### Browser Validation

7. [ ] Navigate to Match page, verify it loads without errors
8. [ ] Click "Unprotect All" button, verify intent file is created
```

### Bad Examples

```markdown
## Success Criteria

1. [ ] Make it work  # Too vague
2. [ ] Build the entire authentication system  # Too large
3. [ ] Fix bugs  # Not specific
4. [ ] Improve performance  # Not testable
```

## Context Section

Provide information the agent needs:

```markdown
## Context

### Files to Create/Modify
- `importer/web/utils/protection_intent.py` - NEW file
- `importer/web/state.py` - Add protection_intent field
- `importer/web/pages/match.py` - Update button handlers

### Key Pattern
\```python
# OLD - direct YAML check
is_protected = source_key in protected_resources

# NEW - intent takes precedence
is_protected = protection_intent_manager.get_effective_protection(
    source_key, 
    yaml_protected=(source_key in protected_resources)
)
\```

### Constraints
- Must work with existing NiceGUI state management
- File format must be JSON for easy inspection
- History entries must be immutable append-only
```

## Notes Section

Include guidance for the agent:

```markdown
## Notes

- Run `./restart_web.sh` to restart server after changes
- Use existing state patterns from `importer/web/state.py`
- Commit after each criterion with `ralph: [N] - description` prefix
- Browser validation required for criteria 7-8
- Phase 2 depends on this being complete
```

## Dependencies Between Phases

When a phase depends on another:

```markdown
**Depends on:** Phase 1 (Core Foundation) - `importer/web/utils/protection_intent.py` must exist
```

## Validation

The task file is valid when:

1. Frontmatter contains required `task` and `test_command` fields
2. At least one success criterion exists with `[ ]` checkbox
3. Criteria are numbered sequentially
4. No duplicate criterion numbers
5. Browser validation criteria clearly marked if `browser_validation: true`
