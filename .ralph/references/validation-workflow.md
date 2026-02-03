# Browser Validation Workflow

This document provides step-by-step patterns for common browser validation scenarios in the Ralph Wiggum methodology.

## Overview

Browser validation is used to verify UI-related success criteria. Each criterion that mentions UI behavior, page navigation, button clicks, or visual elements should be validated with the browser.

## General Pattern

```
FOR EACH UI criterion:
  1. Navigate to page (if not already there)
  2. Lock browser
  3. Snapshot to see current state
  4. Interact (click, type, fill)
  5. Wait 2-3 seconds
  6. Snapshot to verify result
  7. Screenshot for evidence
  8. Unlock browser
  9. Mark criterion [x]
  10. Commit: ralph: [N] - description
```

## Pattern 1: Verify Page Loads

**Use when:** Criterion says "Navigate to X page", "Page renders", "Page loads"

```
Example: "Navigate to Match page, verify it loads"

Steps:
1. browser_tabs (list) → check current state
2. browser_navigate "http://localhost:8501" → open app
3. browser_lock → lock for safety
4. browser_snapshot → verify page structure
   - Look for expected elements (title, buttons, panels)
   - Verify no error messages
5. browser_screenshot → save to .ralph/screenshots/
6. browser_unlock → release
7. Update progress.md with screenshot reference
8. Mark criterion [x]
9. Commit: ralph: [N] - verify Match page loads successfully
```

## Pattern 2: Verify Button Click

**Use when:** Criterion says "Click button X", "Button handler does Y"

```
Example: "Click 'Unprotect All' button, verify intent file created"

Steps:
1. browser_navigate "http://localhost:8501" (if not there)
2. browser_lock
3. browser_snapshot → find button by text
4. browser_click (ref: "button with text 'Unprotect All'")
5. wait 2 seconds → allow state to update
6. Read file: {deployment_dir}/protection-intent.json → verify exists
7. browser_snapshot → verify UI updated
8. browser_screenshot → capture result
9. browser_unlock
10. Mark criterion [x]
11. Commit: ralph: [N] - implement Unprotect All button handler
```

## Pattern 3: Verify Badge/Status Appears

**Use when:** Criterion says "Badge shows X", "Status displays Y"

```
Example: "Verify orange 'Pending' badge appears"

Steps:
1. browser_navigate "http://localhost:8501"
2. browser_lock
3. browser_click (ref: "button to trigger state change")
4. wait 2 seconds
5. browser_snapshot → search output for badge text
   - Look for: "Pending: Generate Protection Changes"
   - Look for: orange/amber styling
6. browser_screenshot → capture badge
7. browser_unlock
8. Mark criterion [x]
9. Commit: ralph: [N] - add pending status badge to UI
```

## Pattern 4: Verify AG Grid Displays

**Use when:** Criterion says "Grid shows X", "Table displays Y"

```
Example: "AG Grid displays intents with correct columns"

Steps:
1. browser_navigate "http://localhost:8501/utilities"
2. browser_lock
3. browser_snapshot → verify grid container exists
4. browser_scroll (if needed to see all content)
5. browser_snapshot → verify:
   - Column headers present
   - Data rows visible
   - Expected data in cells
6. browser_screenshot → capture grid
7. browser_unlock
8. Mark criterion [x]
9. Commit: ralph: [N] - implement AG Grid for protection intents
```

## Pattern 5: Verify Form Interaction

**Use when:** Criterion says "Form accepts input", "Dialog opens"

```
Example: "Edit button opens dialog with form fields"

Steps:
1. browser_navigate "http://localhost:8501/utilities"
2. browser_lock
3. browser_snapshot → find Edit button
4. browser_click (ref: "button with text 'Edit'")
5. wait 2 seconds → dialog animation
6. browser_snapshot → verify:
   - Dialog is open
   - Form fields present
   - Current values populated
7. browser_fill (ref: "textarea with label 'Reason'", text: "Test reason")
8. browser_click (ref: "button with text 'Save'")
9. wait 2 seconds
10. browser_snapshot → verify dialog closed, data updated
11. browser_screenshot → capture result
12. browser_unlock
13. Mark criterion [x]
14. Commit: ralph: [N] - add edit dialog for protection intents
```

## Pattern 6: Verify Filter/Search

**Use when:** Criterion says "Filter by X", "Search for Y"

```
Example: "Status filter dropdown filters grid"

Steps:
1. browser_navigate "http://localhost:8501/utilities"
2. browser_lock
3. browser_snapshot → find filter dropdown
4. browser_click (ref: "select/dropdown for status filter")
5. browser_click (ref: "option with text 'Pending Generate'")
6. wait 2 seconds
7. browser_snapshot → verify:
   - Grid shows only matching rows
   - Count updated
8. browser_screenshot → capture filtered state
9. browser_unlock
10. Mark criterion [x]
11. Commit: ralph: [N] - implement status filter for intents grid
```

## Pattern 7: Verify Multi-Step Flow

**Use when:** Criterion involves multiple pages/steps

```
Example: "Successful action redirects and shows success message"

Steps:
1. browser_navigate "http://localhost:8501/match"
2. browser_lock
3. browser_snapshot → initial state
4. browser_click (ref: "button 'Generate Protection Changes'")
5. wait 3 seconds → longer for processing
6. browser_snapshot → verify:
   - Page redirected or dialog opened
   - Success message visible
   - State updated
7. browser_screenshot → capture success state
8. browser_navigate "http://localhost:8501/utilities" → next page
9. browser_snapshot → verify changes persisted
10. browser_screenshot → capture persistence
11. browser_unlock
12. Mark criterion [x]
13. Commit: ralph: [N] - implement generate protection changes flow
```

## Pattern 8: Verify Error State

**Use when:** Criterion says "Shows error", "Validation fails"

```
Example: "Dialog shows error for invalid input"

Steps:
1. browser_navigate "http://localhost:8501/utilities"
2. browser_lock
3. browser_click (ref: "button with text 'Reset All'")
4. browser_snapshot → verify confirmation dialog
5. browser_click (ref: "button with text 'Confirm'")
6. wait 2 seconds
7. browser_snapshot → verify:
   - Error message if expected
   - Or success state if valid
8. browser_screenshot → capture state
9. browser_unlock
10. Mark criterion [x]
11. Commit: ralph: [N] - add confirmation dialog for reset all
```

## Combining Multiple Criteria

Sometimes multiple related criteria can be validated in one browser session:

```
Example: Criteria 19-22 all related to Match page

Steps:
1. browser_navigate "http://localhost:8501"
2. browser_lock

3. [Criterion 19] Verify page loads
   - browser_snapshot
   - browser_screenshot → phase2-criterion-19.png
   - Mark [x], commit

4. [Criterion 20] Click Unprotect All
   - browser_click
   - wait 2s
   - Read file to verify
   - browser_screenshot → phase2-criterion-20.png
   - Mark [x], commit

5. [Criterion 21] Verify badge appears
   - browser_snapshot → find badge text
   - browser_screenshot → phase2-criterion-21.png
   - Mark [x], commit

6. [Criterion 22] Verify Recent Changes section
   - browser_scroll to section
   - browser_snapshot → verify entries
   - browser_screenshot → phase2-criterion-22.png
   - Mark [x], commit

7. browser_unlock
```

## Pre-Validation Checklist

Before starting browser validation:

- [ ] Server is running (`./restart_web.sh` or check `ps aux | grep web.app`)
- [ ] Test command passes (backend works)
- [ ] You know which page to navigate to
- [ ] You know which elements to interact with
- [ ] You have screenshot naming planned

## Post-Validation Checklist

After completing browser validation:

- [ ] Screenshot saved to `.ralph/screenshots/`
- [ ] Screenshot referenced in `progress.md`
- [ ] Criterion marked `[x]` in `RALPH_TASK.md`
- [ ] Committed with `ralph: [N] - description`
- [ ] Browser unlocked (if locked)

## Common Issues

### Issue: Element not found

**Solution:**
```
1. browser_snapshot → see what elements are actually there
2. Check if element text matches exactly (case-sensitive)
3. Check if page fully loaded (wait longer)
4. Check if element is in a different section (scroll)
```

### Issue: State doesn't update after click

**Solution:**
```
1. Verify button click succeeded (check snapshot after click)
2. Wait longer (try 3-4 seconds instead of 2)
3. Check backend logs for errors
4. Verify save() is called in button handler
5. Read file directly to verify it changed
```

### Issue: Screenshot shows wrong state

**Solution:**
```
1. Take screenshot AFTER snapshot confirms state
2. Don't screenshot too quickly after interaction
3. Use browser_snapshot to verify first, then screenshot
```

## Tips for Efficient Validation

1. **Group related criteria** - Validate multiple criteria in one browser session
2. **Keep browser locked** - Don't unlock/lock repeatedly within one session
3. **Use snapshot liberally** - It's free and helps verify state
4. **Name screenshots clearly** - `phase{N}-criterion-{M}-{what}.png`
5. **Wait consistently** - 2 seconds after most interactions, 3-4s for heavy operations
6. **Read files when needed** - Verify backend state, not just UI
7. **Commit frequently** - One commit per criterion completed
