# Adapting Our Setup for ralph-wiggum-cursor Automation

## What ralph-wiggum-cursor Expects

The automation framework works with RALPH_TASK.md files that have:
1. **Checkboxes** for task tracking: `- [ ]` or `- [x]`
2. **YAML frontmatter** (optional but helpful)
3. **Git repository** (already have ✅)
4. **cursor-agent CLI** (already have ✅)

## Our Current Setup: Already Compatible! ✅

Good news: Our RALPH_TASK.md files **already work** with the automation!

**What we have:**
```markdown
---
task: Protection Intent File System - Phase 1
test_command: "cd importer && python -m pytest web/tests/test_protection_intent.py -v"
browser_validation: true
base_url: "http://localhost:8501"
---

## Success Criteria

1. [ ] Create ProtectionIntentManager class
2. [ ] Add set_intent() method
3. [ ] Add get_effective_protection() method
```

**What ralph-wiggum-cursor expects:**
- ✅ Numbered checkboxes with `[ ]` and `[x]` - we have this
- ✅ YAML frontmatter with task info - we have this
- ✅ Clear criteria descriptions - we have this
- ✅ Git repository - we have this

## Optional Enhancements for Automation

### 1. Add Parallel Execution Groups (Optional)

If you want to use `ralph-parallel.sh` to run tasks in parallel:

```markdown
## Success Criteria

### Phase 1: Foundation (runs first)
1. [ ] Create database schema <!-- group: 1 -->
2. [ ] Create User model <!-- group: 1 -->
3. [ ] Create Post model <!-- group: 1 -->

### Phase 2: Relationships (runs after Phase 1)
4. [ ] Add relationships between models <!-- group: 2 -->
5. [ ] Add migration scripts <!-- group: 2 -->

### Phase 3: API (runs after Phase 2)
6. [ ] Build API endpoints <!-- group: 3 -->
7. [ ] Add authentication <!-- group: 3 -->

### Final (runs last - no annotation)
8. [ ] Update README
9. [ ] Update CHANGELOG
```

**Group rules:**
- `<!-- group: N -->` at end of line
- Lower numbers run first
- Unannotated tasks run LAST (default)
- Within each group, tasks run in parallel (up to --max-parallel)

### 2. Ensure .ralph/ Directory Structure

The automation uses slightly different files than our manual setup:

**What we have:**
```
.ralph/
├── progress.md          ✅ (compatible)
├── guardrails.md        ✅ (compatible)
├── screenshots/         ✅ (compatible)
└── references/          ℹ️ (our addition, won't interfere)
```

**What automation adds:**
```
.ralph/
├── activity.log         # Real-time tool call log (automation writes)
├── errors.log           # Failure detection (automation writes)
├── tasks.yaml           # Cached task state (automation writes)
├── tasks.mtime          # Cache invalidation (automation writes)
└── .iteration           # Current iteration (automation writes)
```

**Action needed:** None - automation will create these files.

### 3. Adjust .gitignore (Optional)

The automation logs can be noisy. Consider:

```gitignore
# Ralph Wiggum automation (logs)
.ralph/activity.log
.ralph/errors.log
.ralph/tasks.yaml
.ralph/tasks.mtime
.ralph/.iteration

# Ralph Wiggum state (keep tracked)
# .ralph/progress.md       # DON'T ignore - track this
# .ralph/guardrails.md     # DON'T ignore - track this
# .ralph/screenshots/      # DON'T ignore - track this
```

Or keep them all tracked for debugging - your choice.

## How Automation Will Work With Our Files

### Our Parallel Tracks Structure

We have:
- `RALPH_TASK.md` - Protection Intent Phase 1
- `RALPH_TASK_PHASE2.md` - Protection Intent Phase 2
- `RALPH_TASK_PM_PHASE1.md` - Project Management Phase 1
- etc.

**For automation:**

**Option 1: Sequential execution (one track at a time)**
```bash
# Run Protection Intent Phase 1
./.cursor/ralph-scripts/ralph-setup.sh

# When complete, manually switch to next phase
cp RALPH_TASK_PHASE2.md RALPH_TASK.md
./.cursor/ralph-scripts/ralph-setup.sh
```

**Option 2: Parallel execution (multiple tracks simultaneously)**

Create a master RALPH_TASK.md that references all tracks:

```markdown
---
task: Multi-Track Development - All Features
test_command: "cd importer && python -m pytest -v"
---

## Success Criteria

### Protection Intent Track <!-- group: 1 -->
1. [ ] Complete PI Phase 1 - Core Foundation <!-- group: 1 -->
2. [ ] Complete PI Phase 2 - Match Page Integration <!-- group: 1 -->
3. [ ] Complete PI Phase 3 - Generate Changes <!-- group: 1 -->

### Project Management Track <!-- group: 1 -->
4. [ ] Complete PM Phase 1 - Infrastructure <!-- group: 1 -->
5. [ ] Complete PM Phase 2 - New Project Wizard <!-- group: 1 -->

### Extended Attributes Track <!-- group: 2 -->
6. [ ] Complete EA Phase 1 - Foundation <!-- group: 2 -->
7. [ ] Complete EA Phase 2 - Web UI Display <!-- group: 2 -->
```

Then run:
```bash
./.cursor/ralph-scripts/ralph-setup.sh --parallel --max-parallel 3
```

**Option 3: Keep manual approach (recommended for learning)**
- Use our existing workflow with Cursor chat
- Use automation scripts occasionally for long-running tasks
- Hybrid: manual for complex work, automation for grunt work

## Testing The Automation

### Step 1: Verify Prerequisites

```bash
# Check cursor-agent
which cursor-agent
# /Users/operator/.local/bin/cursor-agent ✅

# Check git
which git
# /usr/bin/git ✅

# Check jq (for JSON parsing)
which jq
# /usr/bin/jq ✅

# (Optional) Install gum for pretty UI
brew install gum
```

### Step 2: Install ralph-wiggum-cursor

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml

# Run installer
/Users/operator/Documents/git/will-sargent-dbtlabs/ralph-wiggum-cursor/install.sh .
```

This will:
- Create `.cursor/ralph-scripts/` with all automation scripts
- Keep your existing `.ralph/` files (progress, guardrails)
- Keep your existing `.cursor/rules/ralph-wiggum.mdc`
- Keep your existing `RALPH_TASK.md` files

### Step 3: Test Single Iteration

```bash
# Run ONE iteration to test
./.cursor/ralph-scripts/ralph-once.sh

# This will:
# - Read RALPH_TASK.md
# - Read .ralph/guardrails.md
# - Run cursor-agent with our enhanced prompt
# - Work on first [ ] criterion
# - Update files and commit
# - Stop for your review
```

### Step 4: Review Results

```bash
# Check what was done
git log --oneline -5

# Check progress
cat .ralph/progress.md

# Check activity log
tail -50 .ralph/activity.log
```

### Step 5: Run Full Loop (Optional)

If step 3 worked well:

```bash
# Interactive setup with gum UI
./.cursor/ralph-scripts/ralph-setup.sh

# Or CLI mode for scripting
./.cursor/ralph-scripts/ralph-loop.sh -n 20 -m opus-4.5-thinking
```

## Recommendations

### For Initial Testing:
1. ✅ Install ralph-wiggum-cursor automation
2. ✅ Keep your existing RALPH_TASK.md files (they're compatible)
3. ✅ Run `ralph-once.sh` to test a single iteration
4. ✅ Review the results
5. ⚠️ Only use full automation after you trust it

### For Production Use:
- **Simple tasks**: Use automation (`ralph-setup.sh`)
- **Complex decisions**: Use manual Cursor chat
- **Long grunt work**: Use parallel execution (`--parallel`)
- **Learning/debugging**: Use manual with our enhanced docs

### What NOT to Change:
- ❌ Don't change our existing RALPH_TASK.md format - it already works
- ❌ Don't change our guardrails.md - automation will read them
- ❌ Don't change our progress.md structure - automation will append to it
- ❌ Don't remove our .ralph/references/ - they won't interfere

### What TO Consider Adding:
- ✅ Group annotations if using parallel execution
- ✅ .gitignore entries for automation logs (optional)
- ✅ Test with `ralph-once.sh` before committing to full loop

## Summary

**You don't need to change anything!** Your setup is already compatible.

The automation framework:
- ✅ Reads your existing RALPH_TASK.md format
- ✅ Respects your existing guardrails
- ✅ Appends to your existing progress.md
- ✅ Works with your existing git workflow
- ✅ Adds token tracking and error detection on top

**Next step:** Just install and test with `ralph-once.sh`
