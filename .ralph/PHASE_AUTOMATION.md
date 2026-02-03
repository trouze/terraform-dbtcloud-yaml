# Using ralph-wiggum-cursor Automation with Phase Files

## Quick Answer

**No, the scripts don't handle custom filenames.** They hardcode `RALPH_TASK.md`.

**Solution:** Use the `ralph-phase.sh` wrapper script I created for you!

## Usage

```bash
# Single iteration test on EA Phase 1
./ralph-phase.sh RALPH_TASK_EA_PHASE1.md --once

# Full automation on PM Phase 1
./ralph-phase.sh RALPH_TASK_PM_PHASE1.md

# Full loop with 20 iterations on PI Phase 2
./ralph-phase.sh RALPH_TASK_PHASE2.md --loop -n 20
```

## How ralph-phase.sh Works

1. **Temporarily copies** your phase file to `RALPH_TASK.md`
2. **Runs** the chosen ralph automation script
3. **Syncs changes back** to your phase file
4. **Restores** original `RALPH_TASK.md` (if it existed)

This lets you use any phase file with the automation!

## Modes

| Mode | Script | Description |
|------|--------|-------------|
| `--setup` | ralph-setup.sh | Interactive (default) |
| `--once` | ralph-once.sh | Single iteration |
| `--loop` | ralph-loop.sh | Full loop |

## Examples

```bash
# Test EA Phase 1 with single iteration
./ralph-phase.sh RALPH_TASK_EA_PHASE1.md --once

# Review results
git log --oneline -5
cat .ralph/activity.log

# If good, run full automation
./ralph-phase.sh RALPH_TASK_EA_PHASE1.md

# When Phase 1 complete, move to Phase 2
./ralph-phase.sh RALPH_TASK_EA_PHASE2.md
```

## Parallel Execution

```bash
# Run PM Phase 1 with parallel execution
./ralph-phase.sh RALPH_TASK_PM_PHASE1.md --loop --parallel --max-parallel 3
```

## What Gets Synced

- ✅ Checkbox changes: `[ ]` → `[x]`
- ✅ Content changes made by agent
- ✅ Any edits to the task file

Your phase file is automatically updated after the automation runs!

## Alternative: Symlink (Simpler)

If you only want to work on one phase at a time:

```bash
# Create symlink
ln -sf RALPH_TASK_EA_PHASE1.md RALPH_TASK.md

# Run automation normally
./.cursor/ralph-scripts/ralph-setup.sh

# Switch to another phase
rm RALPH_TASK.md
ln -sf RALPH_TASK_PM_PHASE1.md RALPH_TASK.md
```

## When to Use What

| Scenario | Recommendation |
|----------|----------------|
| **Testing automation** | `ralph-phase.sh --once` |
| **Single phase automation** | `ralph-phase.sh` or symlink |
| **Complex multi-phase** | Manual Cursor chat |
| **Learning Ralph** | Manual Cursor chat |
| **Simple grunt work** | `ralph-phase.sh --loop` |

## Remember

You don't HAVE to use automation! Your manual workflow with:
- Multiple parallel tracks
- Enhanced documentation
- Project-specific guardrails

...is perfectly valid and often better for complex work!

The automation is for "set it and forget it" tasks. Use it when appropriate, not for everything.
