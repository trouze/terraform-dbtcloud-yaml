# Custom Task File Names with ralph-wiggum-cursor

## Problem

The ralph-wiggum-cursor automation scripts **hardcode** `RALPH_TASK.md` as the task filename. They cannot directly read:
- `RALPH_TASK_EA_PHASE1.md`
- `RALPH_TASK_PM_PHASE1.md`
- `RALPH_TASK_PHASE2.md`
- etc.

All scripts look for: `$workspace/RALPH_TASK.md`

## Solutions

### Solution 1: Symlink (Recommended for Testing)

Create a symbolic link to the phase you want to work on:

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml

# Work on Extended Attributes Phase 1
ln -sf RALPH_TASK_EA_PHASE1.md RALPH_TASK.md

# Run automation
./.cursor/ralph-scripts/ralph-setup.sh

# When done, switch to another phase
rm RALPH_TASK.md
ln -sf RALPH_TASK_PM_PHASE1.md RALPH_TASK.md
./.cursor/ralph-scripts/ralph-setup.sh
```

**Pros:**
- ✅ No script modifications needed
- ✅ Easy to switch between phases
- ✅ Git-friendly (symlink can be ignored)

**Cons:**
- ⚠️ Only one phase at a time
- ⚠️ Must manually switch phases

### Solution 2: Copy Phase File to RALPH_TASK.md (Simplest)

Copy the phase file you want to work on:

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml

# Work on Extended Attributes Phase 1
cp RALPH_TASK_EA_PHASE1.md RALPH_TASK.md

# Run automation
./.cursor/ralph-scripts/ralph-setup.sh

# When complete, copy changes back to phase file
cp RALPH_TASK.md RALPH_TASK_EA_PHASE1.md
git add RALPH_TASK_EA_PHASE1.md
git commit -m "ralph: EA Phase 1 complete"

# Move to next phase
cp RALPH_TASK_EA_PHASE2.md RALPH_TASK.md
```

**Pros:**
- ✅ Simple, no symlinks
- ✅ No script modifications

**Cons:**
- ⚠️ Must remember to copy changes back
- ⚠️ Risk of losing changes if you forget

### Solution 3: Wrapper Script (Advanced)

Create a custom wrapper that handles phase switching:

```bash
#!/bin/bash
# ralph-phase.sh - Wrapper for running specific phase files

set -euo pipefail

PHASE_FILE="${1:-}"
shift || true

if [[ -z "$PHASE_FILE" ]]; then
  echo "Usage: ./ralph-phase.sh RALPH_TASK_EA_PHASE1.md [ralph-script-options]"
  exit 1
fi

if [[ ! -f "$PHASE_FILE" ]]; then
  echo "Error: $PHASE_FILE not found"
  exit 1
fi

WORKSPACE="$(pwd)"
BACKUP="$WORKSPACE/RALPH_TASK.md.backup"

# Backup existing RALPH_TASK.md if it exists
if [[ -f "$WORKSPACE/RALPH_TASK.md" ]]; then
  mv "$WORKSPACE/RALPH_TASK.md" "$BACKUP"
fi

# Copy phase file to RALPH_TASK.md
cp "$PHASE_FILE" "$WORKSPACE/RALPH_TASK.md"

echo "Running automation with $PHASE_FILE..."

# Run the automation
./.cursor/ralph-scripts/ralph-setup.sh "$@"

# Copy changes back to phase file
cp "$WORKSPACE/RALPH_TASK.md" "$PHASE_FILE"

# Restore backup if it existed
if [[ -f "$BACKUP" ]]; then
  mv "$BACKUP" "$WORKSPACE/RALPH_TASK.md"
fi

echo "Changes synced back to $PHASE_FILE"
```

Save as `ralph-phase.sh`, make executable:

```bash
chmod +x ralph-phase.sh

# Use it:
./ralph-phase.sh RALPH_TASK_EA_PHASE1.md
./ralph-phase.sh RALPH_TASK_PM_PHASE1.md --parallel
```

**Pros:**
- ✅ Automatic syncing
- ✅ Handles any phase file
- ✅ Restores state after

**Cons:**
- ⚠️ More complex
- ⚠️ Custom script to maintain

### Solution 4: Patch the Scripts (Advanced)

Modify the automation scripts to accept a `RALPH_TASK_FILE` environment variable:

**Changes needed in each script:**

Replace:
```bash
local task_file="$workspace/RALPH_TASK.md"
```

With:
```bash
local task_file="${RALPH_TASK_FILE:-$workspace/RALPH_TASK.md}"
```

This would need to be done in:
- `scripts/ralph-common.sh` (6 locations)
- `scripts/ralph-loop.sh` (1 location)
- `scripts/ralph-once.sh` (1 location)
- `scripts/ralph-setup.sh` (1 location)
- `scripts/task-parser.sh` (6 locations)

Then use:
```bash
RALPH_TASK_FILE=RALPH_TASK_EA_PHASE1.md ./.cursor/ralph-scripts/ralph-setup.sh
```

**Pros:**
- ✅ Most flexible
- ✅ Works with any filename

**Cons:**
- ⚠️ Must patch 15+ locations
- ⚠️ Custom fork to maintain
- ⚠️ Won't get upstream updates easily

### Solution 5: Use Parallel Mode with Master Task File (Best for Multiple Phases)

Create a master `RALPH_TASK.md` that references your phase files:

```markdown
---
task: Multi-Phase Development
test_command: "cd importer && python -m pytest -v"
---

# Task: All Phases

Run multiple phases in parallel or sequence.

## Success Criteria

### Extended Attributes - Phase 1 <!-- group: 1 -->
1. [ ] EA Phase 1: Complete all criteria in RALPH_TASK_EA_PHASE1.md <!-- group: 1 -->

### Project Management - Phase 1 <!-- group: 1 -->
2. [ ] PM Phase 1: Complete all criteria in RALPH_TASK_PM_PHASE1.md <!-- group: 1 -->

### Protection Intent - Phase 2 <!-- group: 2 -->
3. [ ] PI Phase 2: Complete all criteria in RALPH_TASK_PHASE2.md <!-- group: 2 -->

## Notes

Each criterion above represents completing an entire phase file.
The agent should open the referenced file and work through its criteria.
```

**Pros:**
- ✅ Works with standard automation
- ✅ Can run phases in parallel
- ✅ Clear progress tracking

**Cons:**
- ⚠️ Abstract criteria (not detailed)
- ⚠️ Agent must open sub-files

## Recommendation by Use Case

### For Sequential Work (One Phase at a Time):
**Use Solution 1 (Symlink):**
```bash
ln -sf RALPH_TASK_EA_PHASE1.md RALPH_TASK.md
./.cursor/ralph-scripts/ralph-setup.sh
```

### For Parallel Work (Multiple Phases):
**Use Solution 5 (Master Task File)** or manual Cursor chat

### For Maximum Control:
**Don't use automation** - stick with manual Cursor chat and our enhanced methodology

### For Custom Workflow:
**Use Solution 3 (Wrapper Script)** - best balance of automation and flexibility

## Our Current Workflow (Manual)

Remember, you don't HAVE to use the automation. Your current workflow works great:

1. Work on phase files manually via Cursor chat
2. Use our parallel tracks structure
3. Use our enhanced documentation
4. Commit with `ralph: [N] - description` format
5. Switch phases by changing which file you reference in chat

The automation is an **option**, not a requirement!

## Quick Answer

**Can the script handle custom names?** No, not directly.

**Easiest workaround?** Symlink:
```bash
ln -sf RALPH_TASK_EA_PHASE1.md RALPH_TASK.md
```

**Best approach for you?** Probably stick with **manual Cursor chat** for now, since you have:
- Multiple parallel tracks
- Phase dependencies
- Complex project-specific guardrails
- Well-defined task files

The automation is best for "set it and forget it" single-track tasks. Your multi-track approach benefits from manual control.
