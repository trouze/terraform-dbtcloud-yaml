# State Files Specification

The `.ralph/` directory contains state files that persist across sessions. This is the "memory" of the Ralph Wiggum methodology.

## Directory Structure

```
.ralph/
├── progress.md          # Session history and accomplishments
├── guardrails.md        # Lessons learned (Signs)
├── screenshots/         # Browser validation evidence
└── references/          # Methodology documentation
    ├── task-format.md
    ├── state-files.md
    ├── browser-tools.md
    └── validation-workflow.md
```

## progress.md

Tracks what has been accomplished across sessions.

### Format

```markdown
# Progress Log

## Track Overview

| Track | Phases | Total Criteria | Status |
|-------|--------|----------------|--------|
| Protection Intent (PI) | 5 | ~163 | Phase 1 in progress |
| Project Management (PM) | 4 | ~120 | Ready to start |
| Extended Attributes (EA) | 4 | ~100 | Ready to start |

---

## Protection Intent Track

### Phase 1: Core Foundation - IN PROGRESS
- File: `RALPH_TASK.md`
- Criteria: 22
- Focus: ProtectionIntentManager class + unit tests
- Completed: 10/22

### Phase 2-5: Pending
- Match Page Integration, Generate Protection Changes, Utilities Page, Destroy Page

---

## Session History

### Session 1 (2024-02-02) - Protection Intent Phase 1

**Completed:**
- [x] Criterion 1 - Create ProtectionIntentManager class
  - Commit: abc1234
  - Notes: Basic class structure with __init__ and file path
  
- [x] Criterion 2 - Add set_intent() method
  - Commit: def5678
  - Notes: Accepts resource_key, protected, source parameters

**Current Focus:**
Working on Criterion 3 - Add get_effective_protection() method

**Blockers Encountered:**
- None so far

**Guardrails Added:**
- None this session

---

## Session Template

### Session N (YYYY-MM-DD) - [Track Name]

**Completed:**
<!-- List completed criteria with [x] -->

**Current Focus:**
<!-- What criterion you're working on -->

**Blockers Encountered:**
<!-- Any issues and how they were resolved -->

**Guardrails Added:**
<!-- Any new guardrails discovered -->
```

### Update Rules

1. Update track overview when phase changes
2. Create new session header at start of each session
3. Add completed criteria with commit hash
4. Include screenshot references for UI validations
5. Note any blockers and their resolution
6. Update "Current Focus" when switching criteria

## guardrails.md

Contains lessons learned from failures. The agent reads this FIRST before starting work.

### Format

```markdown
# Guardrails (Signs)

Lessons learned from previous iterations. Read this FIRST before starting work.

## Parallel Tracks

This project has THREE parallel tracks that can be worked on independently:

### Track 1: Protection Intent (PI) - 5 phases, 163 criteria
\```
RALPH_TASK.md           → Phase 1: Core Foundation
RALPH_TASK_PHASE2.md    → Phase 2: Match Page Integration
...
\```

## Phase Transition Protocol

**When current phase is complete (all criteria `[x]`):**

1. Commit with message: `ralph: [phase-complete] - {track} Phase N complete`
2. Copy next phase file to active task file
3. Output `<ralph>PHASE_COMPLETE:{track}</ralph>`
4. Continue with the new phase

## Track Dependencies

\```
Protection Intent Phase 1 ◄─── Extended Attributes Phase 4
        │                        (needs ProtectionIntentManager)
        ▼
   (independent)
\```

## Active Guardrails

### Sign: NiceGUI button icons appear in wrong position
- **Trigger**: Creating buttons and calling `set_icon()` dynamically
- **Instruction**: Never use `set_icon()` - always pass `icon=` parameter on button creation
- **Evidence**: Icons appear in middle of text instead of left side
- **Added after**: Previous UI implementation iterations

### Sign: Protection Intent file not persisted
- **Trigger**: Modifying intent dict without saving
- **Instruction**: Always call `protection_intent_manager.save()` after any modification
- **Evidence**: Changes lost on page reload
- **Added after**: Plan design requirement

## Resolved Guardrails

<!-- Move guardrails here when the underlying issue is permanently fixed -->
```

### Guardrail Structure

Each guardrail must have:

| Field | Required | Description |
|-------|----------|-------------|
| **Trigger** | Yes | When this guardrail applies |
| **Instruction** | Yes | What to do instead |
| **Evidence** | Yes | Screenshot, log, or error message |
| **Added after** | Yes | Iteration/session and reason |

### Adding Guardrails

Add a new guardrail when:
1. The same error occurs twice
2. A subtle bug is discovered that could recur
3. A non-obvious requirement is learned
4. Browser interactions fail due to timing
5. Framework-specific patterns cause issues (NiceGUI, AG Grid, etc.)

### Guardrail Lifecycle

```
Error occurs → Analyze pattern → 
Add to guardrails.md → Future sessions follow it →
If permanently fixed → Move to "Resolved" section
```

## screenshots/

Directory for browser validation evidence.

### Naming Convention

```
.ralph/screenshots/
├── phase1-criterion-7-match-page-loads.png
├── phase2-criterion-20-unprotect-button.png
├── phase2-criterion-21-pending-badge.png
└── error-dialog-not-opening.png
```

### When to Capture

1. After completing UI-related criteria (evidence)
2. When browser interactions fail (debugging)
3. When visual state needs to be recorded
4. Before and after major UI changes (visual diff)

### Referencing in Progress

```markdown
### Completed
- [x] Criterion 7 - Navigate to Match page
  - Commit: abc123
  - Screenshot: .ralph/screenshots/phase1-criterion-7-match-page-loads.png
  - Notes: Page loads without errors, mismatch panel visible
```

## Git Integration

### What to Track

| File | Git Status | Reason |
|------|------------|--------|
| `progress.md` | ✅ Track | Persists accomplishments |
| `guardrails.md` | ✅ Track | Persists lessons learned |
| `screenshots/` | ✅ Track | Evidence of completion |
| `references/` | ✅ Track | Documentation |

### .gitignore Entry

The `.ralph/` directory should be fully tracked - no gitignore needed for these files.

## Initialization

The `.ralph/` directory is already initialized with:
- `progress.md` - Session tracking
- `guardrails.md` - Lessons learned
- `screenshots/` - Browser evidence
- `references/` - This documentation
