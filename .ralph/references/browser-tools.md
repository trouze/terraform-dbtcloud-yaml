# MCP Browser Tools Integration

This document describes how to use MCP (Model Context Protocol) browser tools for UI validation in the Ralph Wiggum methodology.

## Overview

MCP browser tools allow the agent to:
- Navigate to web pages (Streamlit app at http://localhost:8501)
- Interact with UI elements (click buttons, fill forms)
- Capture screenshots as evidence
- Validate UI state after implementation

## Available Tools

### Core Browser Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| `browser_tabs` | List/manage browser tabs | Check existing tabs, get current URL |
| `browser_navigate` | Navigate to URL | Open pages for testing |
| `browser_lock` | Lock browser for interactions | Required before interactions |
| `browser_unlock` | Release browser | Required after interactions complete |
| `browser_snapshot` | Get page structure | Inspect elements before interacting |
| `browser_click` | Click an element | Buttons, links, checkboxes |
| `browser_type` | Type text (append) | Text inputs |
| `browser_fill` | Fill input (replace) | Form fields, also works on contenteditable |
| `browser_scroll` | Scroll page or element | Reveal hidden content |
| `browser_screenshot` | Capture screenshot | Evidence collection |

## Standard Workflow

### 1. Check Browser State
```
browser_tabs (action: "list")
→ See what tabs are open, check current URL
```

### 2. Navigate to Target
```
browser_navigate (url: "http://localhost:8501")
→ Opens Streamlit app, waits for initial load
```

### 3. Lock Browser
```
browser_lock
→ Required before any interactions
→ Prevents concurrent access issues
```

### 4. Inspect Page
```
browser_snapshot
→ Returns page structure with element refs
→ Use refs for subsequent interactions
→ ALWAYS call this before clicking/typing
```

### 5. Interact
```
browser_click (ref: "button with text 'Unprotect All'")
browser_fill (ref: "input#search", text: "PRJ_12345")
```

### 6. Wait and Verify
```
// Short wait for UI to update
sleep 2 seconds

browser_snapshot
→ Verify expected state after interaction
```

### 7. Capture Evidence
```
browser_screenshot
→ Save to .ralph/screenshots/phase1-criterion-7.png
```

### 8. Release Browser
```
browser_unlock
→ Always release when done
→ Allows other processes to use browser
```

## Validation Pattern for Ralph Tasks

For each UI-related criterion in RALPH_TASK.md:

```
1. Navigate to relevant page (e.g., Match page)
2. Lock browser
3. Snapshot to verify initial state
4. Perform required interactions (click buttons, etc.)
5. Short wait (1-3 seconds)
6. Snapshot to verify final state
7. Screenshot for evidence
8. Unlock browser
9. Update progress.md with screenshot reference
10. Mark criterion [x] in RALPH_TASK.md
11. Commit: ralph: [N] - description
```

## Project-Specific Patterns

### Streamlit App Testing

Our app runs at `http://localhost:8501` (NiceGUI-based Streamlit replacement).

Common pages:
- `/` - Home/Dashboard
- Match page - Resource matching and protection
- Utilities page - Protection management
- Generate page - YAML generation

### NiceGUI Specifics

- Use `browser_snapshot` to find elements by text content
- Buttons often referenced by their visible text
- Wait after button clicks for state updates
- AG Grid tables may need scrolling to see all rows

### Restart Server

Before browser testing, restart the server:
```bash
./restart_web.sh
```

Or manually:
```bash
cd importer
pkill -f "python -m web.app"
python -m web.app &
```

## Waiting Strategy

**DO:** Use short incremental waits with snapshot checks

```
browser_click (ref: "button with text 'Unprotect All'")
wait 2 seconds
browser_snapshot → check if state updated
if not updated:
  wait 2 seconds
  browser_snapshot → check again
```

**DON'T:** Use single long waits

```
browser_click (ref: "button")
wait 10 seconds  // BAD - wastes time if page updates quickly
```

## Error Handling

### Element Not Found

If `browser_click` or `browser_fill` fails with "element not found":

1. Call `browser_snapshot` to see current page state
2. Check if page has fully loaded
3. Check if element requires scrolling into view
4. Verify element text/ref matches exactly
5. Add guardrail if timing issue is recurring

### Navigation Timeout

If `browser_navigate` times out:

1. Check if server is running: `curl http://localhost:8501`
2. Try navigating to root first: `/`
3. Check terminal for server errors

### State Not Updating

If clicking button doesn't update state:

1. Verify button click succeeded (check snapshot)
2. Check if save() was called in backend
3. Verify file was written (read protection-intent.json)
4. Check for errors in server logs

## Screenshot Best Practices

### Naming Convention

```
.ralph/screenshots/
├── phase1-criterion-7-match-page-loads.png
├── phase1-criterion-8-manager-initialized.png
├── phase2-criterion-20-unprotect-button.png
├── phase2-criterion-21-pending-badge.png
├── phase4-criterion-36-ag-grid-displays.png
```

Format: `phase{N}-criterion-{M}-{short-description}.png`

### When to Screenshot

1. **After completing UI criteria** - Evidence of completion
2. **After form submissions** - Verify success state
3. **When errors occur** - Debugging information
4. **Before and after major interactions** - Visual diff

### Referencing in Progress

```markdown
### Completed
- [x] Criterion 20 - Click Unprotect All button
  - Commit: abc123
  - Screenshot: .ralph/screenshots/phase2-criterion-20-unprotect-button.png
  - Notes: Button click creates protection-intent.json file
```

## Common Scenarios

### Scenario: Verify button click creates file

```
1. browser_navigate "http://localhost:8501"
2. browser_lock
3. browser_snapshot → verify button visible
4. browser_click (ref: "button with text 'Unprotect All'")
5. wait 2 seconds
6. Read file: protection-intent.json → verify exists
7. browser_screenshot → capture UI state
8. browser_unlock
```

### Scenario: Verify badge appears

```
1. browser_navigate "http://localhost:8501"
2. browser_lock
3. browser_click (ref: "button with text 'Unprotect All'")
4. wait 2 seconds
5. browser_snapshot → search for "Pending: Generate Protection Changes"
6. browser_screenshot → capture badge
7. browser_unlock
```

### Scenario: Verify AG Grid displays data

```
1. browser_navigate "http://localhost:8501/utilities"
2. browser_lock
3. browser_snapshot → verify grid container exists
4. browser_scroll (to reveal all rows if needed)
5. browser_snapshot → verify data in grid
6. browser_screenshot → capture full grid
7. browser_unlock
```

## Troubleshooting

### "No server found with tool: browser_navigate"

MCP browser server may not be registered. Check:
1. Cursor settings for MCP servers
2. Restart Cursor to reload MCP configuration

### Browser opens but interactions fail

1. Ensure `browser_lock` was called before interactions
2. Check element refs from latest `browser_snapshot`
3. Element may have changed after page update

### Screenshots are blank or wrong page

1. Wait for page to fully load before screenshot
2. Use `browser_snapshot` to verify correct page
3. Check if page redirected unexpectedly

## Integration with RALPH_TASK.md

Enable browser validation in task frontmatter:

```yaml
---
task: Protection Intent - Phase 2 Integration
test_command: "cd importer && python -m pytest web/tests/test_protection_intent.py -v"
browser_validation: true
base_url: "http://localhost:8501"
---
```

Mark UI criteria that need browser validation:

```markdown
## Success Criteria

### Browser Validation

19. [ ] Navigate to Match page, verify mismatch panel loads
20. [ ] Click "Unprotect All", verify intent file is created
21. [ ] Verify orange "Pending" badge appears
```
