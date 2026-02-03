# Guardrails (Signs)

Lessons learned from previous iterations. Read this FIRST before starting work.

## Parallel Tracks

This project has THREE parallel tracks that can be worked on independently:

### Track 1: Protection Intent (PI) - 5 phases, 163 criteria
```
RALPH_TASK.md           → Phase 1: Core Foundation
RALPH_TASK_PHASE2.md    → Phase 2: Match Page Integration
RALPH_TASK_PHASE3.md    → Phase 3: Generate Protection Changes
RALPH_TASK_PHASE4.md    → Phase 4: Utilities Page
RALPH_TASK_PHASE5.md    → Phase 5: Destroy Page & Completion
```

### Track 2: Project Management (PM) - 4 phases, ~120 criteria
```
RALPH_TASK_PM_PHASE1.md → Phase 1: Infrastructure
RALPH_TASK_PM_PHASE2.md → Phase 2: New Project Wizard
RALPH_TASK_PM_PHASE3.md → Phase 3: Home Page & State
RALPH_TASK_PM_PHASE4.md → Phase 4: Save Dialog & Settings
```

### Track 3: Extended Attributes (EA) - 4 phases, ~100 criteria
```
RALPH_TASK_EA_PHASE1.md → Phase 1: Foundation
RALPH_TASK_EA_PHASE2.md → Phase 2: Web UI Display
RALPH_TASK_EA_PHASE3.md → Phase 3: Interaction & Dependencies
RALPH_TASK_EA_PHASE4.md → Phase 4: Protection & Destroy (requires PI Phase 1)
```

## Phase Transition Protocol

**When current phase is complete (all criteria `[x]`):**

1. Commit with message: `ralph: [phase-complete] - {track} Phase N complete`
2. Copy next phase file to active task file:
   - PI track: `cp RALPH_TASK_PHASE{N+1}.md RALPH_TASK.md`
   - PM track: `cp RALPH_TASK_PM_PHASE{N+1}.md RALPH_TASK_PM.md`
   - EA track: `cp RALPH_TASK_EA_PHASE{N+1}.md RALPH_TASK_EA.md`
3. Output `<ralph>PHASE_COMPLETE:{track}</ralph>`
4. Continue with the new phase

**When a track is fully complete:**
- Output `<ralph>TRACK_COMPLETE:{track}</ralph>`

**When ALL tracks complete:**
- Output `<ralph>COMPLETE</ralph>`

## Track Dependencies

```
Protection Intent Phase 1 ◄─── Extended Attributes Phase 4
        │                        (needs ProtectionIntentManager)
        ▼
   (independent)
        
Project Management ◄─── (independent, can run fully in parallel)
```

## Working on Specific Tracks

To work on a specific track, tell Ralph which one:
- "Work on Protection Intent track" → Uses RALPH_TASK.md
- "Work on Project Management track" → Uses RALPH_TASK_PM_PHASE1.md (or active phase)
- "Work on Extended Attributes track" → Uses RALPH_TASK_EA_PHASE1.md (or active phase)

## Active Guardrails

### Sign: NiceGUI button icons appear in wrong position
- **Trigger**: Creating buttons and calling `set_icon()` dynamically
- **Instruction**: Never use `set_icon()` - always pass `icon=` parameter on button creation
- **Evidence**: Icons appear in middle of text instead of left side
- **Added after**: Previous UI implementation iterations

### Sign: Protection Intent file not persisted
- **Trigger**: Modifying intent dict without saving
- **Instruction**: Always call `protection_intent_manager.save()` after any modification to intent or history
- **Evidence**: Changes lost on page reload
- **Added after**: Plan design requirement

### Sign: Checking YAML protected flag directly
- **Trigger**: Code uses `source_key in protected_resources` pattern
- **Instruction**: Use `get_effective_protection(key, yaml_protected)` instead - intent takes precedence over YAML
- **Evidence**: Protection flip-flopping when intent differs from YAML
- **Added after**: Plan design requirement

### Sign: AG Grid theme mismatch
- **Trigger**: Creating AG Grid tables
- **Instruction**: Always use `theme="quartz"` with `ag-theme-quartz-auto-dark` class, explicit `colId` on all columns
- **Evidence**: Inconsistent styling in dark mode
- **Added after**: AG Grid Standards cursor rule

### Sign: Amber button text invisible
- **Trigger**: Creating amber/warning colored buttons
- **Instruction**: Use `props("color=amber").style("color: black !important;")` for readable text
- **Evidence**: White text on amber background is hard to read
- **Added after**: NiceGUI styling lessons

### Sign: Streaming dialog without cancel
- **Trigger**: Long-running operations in dialogs
- **Instruction**: Always provide Cancel button, use `asyncio.create_task` for non-blocking execution
- **Evidence**: Users can't stop stuck operations
- **Added after**: UX best practices

### Sign: Dialog content not scrollable
- **Trigger**: Creating dialogs with variable content
- **Instruction**: Wrap content in `ui.scroll_area().style("max-height: 60vh;")` and call `dialog.open()` AFTER defining content
- **Evidence**: Long content overflows dialog bounds
- **Added after**: AG Grid Standards cursor rule

### Sign: ProjectManager slug collision
- **Trigger**: Creating projects with similar names
- **Instruction**: Always check `project_exists(slug)` before creating, use clear error message for duplicates
- **Evidence**: Folder overwrite risk
- **Added after**: Project Management PRD requirement

## Resolved Guardrails

<!-- Move fixed guardrails here when they're no longer relevant -->
