# PRD: Destroy Page Refactor

## Overview

Refactor both panes on the Destroy page to be self-contained with filters, multi-selection, detail popups, and inline action buttons. Remove the separate actions row. Fix gear icon link and add account name to target info.

## Current State

The destroy page layout in `importer/web/pages/destroy.py` currently renders:
1. Actions row (Select All, Clear, Taint/Destroy buttons)
2. Protected Resources panel (compact, limited features)
3. "Select Resources" table (full-featured with filters, selection, detail popups)

## Proposed Changes

### 1. Reorder Page Layout and Remove Actions Row

Simplify to just two panes - each self-contained with their own actions:

```python
# Protected resources panel (full width)
_create_destroy_protection_panel(state, save_state, destroy_state)

# Destroy resources table (full width)
_create_resource_table(state, destroy_state, terminal, save_state)
```

Remove the `_create_actions_row` call entirely.

### 2. Rename "Select Resources" to "Destroy Resources"

In `_create_resource_table`, change the label:
```python
ui.label("Destroy Resources").classes("font-semibold")
```

### 3. Move Destroy Actions into Destroy Resources Pane

Update `_create_resource_table` to include (in order):
1. Action buttons row: Select All, Clear, Taint Selected, Destroy Selected, Destroy All
2. Filter row: Type dropdown, Search input, Selection counter
3. Table

This requires passing `terminal` and `save_state` to `_create_resource_table`.

### 4. Refactor `_create_destroy_protection_panel`

Transform the panel to be self-contained (in order):

**A. Action buttons row (first, below header):**
- Select All / Clear buttons (operate on filtered results)
- "Unprotect Selected (N)" button (amber, black text)
- "Unprotect All" button
- Remove the "Manage..." button (dialog no longer needed)

**B. Filter row:**
- Type filter dropdown (Projects, Environments, Jobs, etc.)
- Search input for name/ID filtering
- Selection counter / "X shown / Y total" when filtered

**C. Table with selection:**
- Enable `selection=multiple` on the table

**D. Detail popup on row click:**
- Call `_show_resource_detail_dialog` when clicking a row
- Construct Terraform address: `dbtcloud_{type}.{name}`

### 5. Update Function Signatures

**Protected Resources panel:**
```python
def _create_destroy_protection_panel(
    state: AppState,
    save_state: Callable[[], None],
    destroy_state: dict,  # Added for state file access
) -> None:
```

**Destroy Resources table:**
```python
def _create_resource_table(
    state: AppState,
    destroy_state: dict,
    terminal: ui.element,  # Added for taint/destroy commands
    save_state: Callable[[], None],  # Added for state updates
) -> None:
```

### 6. Remove Obsolete Code

- Delete `_create_actions_row` function (actions now in panes)
- Delete `_show_selective_unprotect_dialog` function (inline in panel)

### 7. Fix Configure Gear Icon Link

The gear icon in the top section currently links to the wrong page. Update the `on_click` handler to navigate to `/fetch_target`.

### 8. Show Account Name in Target Info

Add the account name to the target info section at the top of the page, alongside the existing account ID and URL display.

## UI Layout Structure

```
+------------------------------------------------------------+
| Protected Resources (2)  [Will be SKIPPED]                 |
|------------------------------------------------------------|
| [SELECT ALL] [CLEAR] [UNPROTECT SELECTED] [UNPROTECT ALL]  |
|------------------------------------------------------------|
| Filter: [All Types v]  Search: [______]    Selected: 0     |
|------------------------------------------------------------|
| [ ] Type        Name              ID                       |
| [x] Project     sse_dm_fin_fido   123                      |
| [ ] Environment prod_env          456                      |
+------------------------------------------------------------+

+------------------------------------------------------------+
| Destroy Resources  [336 managed]                           |
|------------------------------------------------------------|
| [SELECT ALL] [CLEAR] [TAINT SEL] [DESTROY SEL] [DESTROY ALL]|
|------------------------------------------------------------|
| Filter: [All Types v]  Search: [______]    Selected: 0     |
|------------------------------------------------------------|
| [ ] Type        Name              ID                       |
| [x] Project     my_project        123                      |
| [ ] Environment staging           456                      |
+------------------------------------------------------------+
```

Action buttons above filters - each pane is self-contained.

## Key Implementation Details

1. **Terraform address mapping** for protected resources:
   - `PRJ` -> `dbtcloud_project`
   - `ENV` -> `dbtcloud_environment`
   - `JOB` -> `dbtcloud_job`
   - `REP` -> `dbtcloud_repository`
   - `CON` -> `dbtcloud_connection`

2. **Reuse existing patterns** from Select Resources:
   - Filter state dictionary
   - `update_table()` function pattern
   - `on_type_change` / `on_search_change` handlers
   - Selection tracking via `on("selection", ...)` event

3. **Button styling** consistency:
   - Use `size=sm padding='4px 12px'` for action buttons
   - Amber buttons with `style("color: black !important;")`

4. **Protection Intent Integration** (see [Protection Intent File plan](/.cursor/plans/protection_intent_file_e08a2a4e.plan.md)):
   - Unprotect Selected/All must write to `protection-intent.json`, NOT `state.map.unprotected_keys`
   - Show same status badges as Match page: "Pending: Generate Protection Changes", "Pending: TF Init/Plan/Apply"
   - Add link: "Apply protection changes on Match page"
   - Protection panel reads effective protection from `ProtectionIntentManager.get_effective_protection()`

---

## User Stories

### US-1: View Protected Resources with Filters
**As a** Terraform operator  
**I want to** filter protected resources by type and search by name  
**So that** I can quickly find specific protected resources in large deployments

**Acceptance Criteria:**
- Type dropdown shows all resource types present in protected resources
- Search input filters by name or ID (case-insensitive)
- "X shown / Y total" badge updates when filters applied
- Filters persist during session

### US-2: Select Protected Resources for Bulk Unprotection
**As a** Terraform operator  
**I want to** select multiple protected resources using checkboxes  
**So that** I can unprotect them in bulk rather than one at a time

**Acceptance Criteria:**
- Table rows have checkboxes for multi-selection
- "Select All" selects all currently filtered resources
- "Clear" deselects all selected resources
- Selection counter shows "Selected: N"

### US-3: View Protected Resource Details
**As a** Terraform operator  
**I want to** click a protected resource row to see its full details  
**So that** I can verify resource attributes before unprotecting

**Acceptance Criteria:**
- Clicking a row opens detail dialog
- Dialog shows resource type, name, ID, and Terraform address
- Dialog shows target resource details from state file
- Dialog can be dismissed with Escape or close button

### US-4: Unprotect Selected Resources
**As a** Terraform operator  
**I want to** unprotect only my selected resources  
**So that** I have fine-grained control over which resources become destroyable

**Acceptance Criteria:**
- "Unprotect Selected (N)" button shows count of selected resources
- Button is disabled when no resources selected
- Clicking removes protection from selected resources only
- Table updates to remove unprotected resources

### US-5: Unprotect All Protected Resources
**As a** Terraform operator  
**I want to** unprotect all protected resources at once  
**So that** I can quickly prepare for a full environment teardown

**Acceptance Criteria:**
- "Unprotect All" button removes protection from all resources
- Confirmation dialog warns about the action
- Protected Resources panel becomes empty after action

### US-6: View Destroy Resources with Filters
**As a** Terraform operator  
**I want to** filter destroyable resources by type and search by name  
**So that** I can target specific resources for destruction

**Acceptance Criteria:**
- Type dropdown shows all resource types in state
- Search input filters by name or ID
- Filters work independently and together
- Table updates immediately on filter change

### US-7: Select Resources for Targeted Destruction
**As a** Terraform operator  
**I want to** select specific resources for destruction  
**So that** I can perform surgical teardowns

**Acceptance Criteria:**
- Multi-select via checkboxes
- "Select All" / "Clear" buttons operate on filtered view
- Selection persists when filters change (if resources still visible)

### US-8: View Resource Details Before Destruction
**As a** Terraform operator  
**I want to** click a resource to see its full state details  
**So that** I can confirm I'm destroying the right resource

**Acceptance Criteria:**
- Row click opens detail dialog with full resource attributes
- Shows Terraform address and resource type
- Shows all attributes from state file

### US-9: Taint Selected Resources
**As a** Terraform operator  
**I want to** taint selected resources  
**So that** they will be recreated on next apply

**Acceptance Criteria:**
- "Taint Selected" button runs `terraform taint` for each selected resource
- Terminal shows command output
- Button disabled when no resources selected

### US-10: Destroy Selected Resources
**As a** Terraform operator  
**I want to** destroy only my selected resources  
**So that** I can perform targeted teardowns

**Acceptance Criteria:**
- "Destroy Selected" generates destroy command targeting selected resources
- Protected resources are automatically excluded
- Terminal shows command execution

### US-11: Destroy All Resources
**As a** Terraform operator  
**I want to** destroy all non-protected resources  
**So that** I can tear down an entire environment

**Acceptance Criteria:**
- "Destroy All" button available
- Protected resources are skipped
- Terminal shows full destroy execution

### US-12: Navigate to Fetch Target Configuration
**As a** Terraform operator  
**I want to** click the gear icon to go to target configuration  
**So that** I can change my target environment

**Acceptance Criteria:**
- Gear icon in top section navigates to `/fetch_target`
- Navigation preserves session state

### US-13: View Account Name in Target Info
**As a** Terraform operator  
**I want to** see the account name alongside ID and URL  
**So that** I can confirm I'm working with the correct dbt Cloud account

**Acceptance Criteria:**
- Account name displayed in target info section
- Shows alongside existing account ID and URL

---

## Test Plan

### Prerequisites
1. Server running at `http://localhost:8082`
2. Valid `.env` credentials loaded via `/fetch_target`
3. Terraform state file with resources
4. At least 2 protected resources configured

### Test Execution Tools
- **Browser automation**: `cursor-browser-extension` MCP tools
- **Server management**: `restart_web.sh` script
- **State inspection**: Python scripts or direct file reads

---

### Test Suite: Protected Resources Pane

#### TC-PR-01: Verify Pane Layout
**Steps:**
1. Navigate to `/destroy`
2. Take browser snapshot
3. Verify Protected Resources pane appears above Destroy Resources pane
4. Verify action buttons row appears above filter row

**Expected:** Pane order is Header > Actions > Filters > Table

#### TC-PR-02: Type Filter Functionality
**Steps:**
1. Navigate to `/destroy`
2. Click type filter dropdown
3. Select specific type (e.g., "Projects")
4. Verify table shows only that type

**Expected:** Table filters to show only selected type

#### TC-PR-03: Search Filter Functionality
**Steps:**
1. Navigate to `/destroy`
2. Type partial resource name in search input
3. Verify table filters to matching resources

**Expected:** Only resources matching search term displayed

#### TC-PR-04: Combined Filters
**Steps:**
1. Select type filter "Environments"
2. Type search term
3. Verify both filters apply together

**Expected:** Results match both type AND search criteria

#### TC-PR-05: Select All Button
**Steps:**
1. Apply a type filter to show subset
2. Click "Select All"
3. Verify all visible rows are selected
4. Verify selection counter shows correct count

**Expected:** All filtered resources selected, counter accurate

#### TC-PR-06: Clear Button
**Steps:**
1. Select multiple resources
2. Click "Clear"
3. Verify no rows selected
4. Verify selection counter shows 0

**Expected:** All selections cleared

#### TC-PR-07: Row Click Detail Popup
**Steps:**
1. Click on a protected resource row
2. Verify detail dialog opens
3. Verify dialog shows resource type, name, ID
4. Verify dialog shows Terraform address
5. Verify dialog shows target resource details
6. Press Escape to close

**Expected:** Detail dialog displays complete resource information

#### TC-PR-08: Unprotect Selected
**Steps:**
1. Select 1 protected resource
2. Verify "Unprotect Selected (1)" button shows count
3. Click button
4. Verify selected resource removed from protected list
5. Verify resource appears in Destroy Resources pane

**Expected:** Selected resource unprotected and moved

#### TC-PR-09: Unprotect All
**Steps:**
1. Click "Unprotect All"
2. Confirm in dialog (if any)
3. Verify Protected Resources pane is empty
4. Verify all resources now in Destroy Resources

**Expected:** All protections removed

---

### Test Suite: Destroy Resources Pane

#### TC-DR-01: Verify Pane Layout
**Steps:**
1. Take browser snapshot of Destroy Resources pane
2. Verify title is "Destroy Resources" (not "Select Resources")
3. Verify action buttons above filters

**Expected:** Renamed title and correct layout order

#### TC-DR-02: Type Filter Functionality
**Steps:**
1. Click type filter in Destroy Resources pane
2. Select "Jobs"
3. Verify only job resources shown

**Expected:** Filter works correctly

#### TC-DR-03: Search Filter Functionality
**Steps:**
1. Type resource name in search
2. Verify table updates

**Expected:** Search filters resources

#### TC-DR-04: Select All / Clear Buttons
**Steps:**
1. Click "Select All"
2. Verify all visible resources selected
3. Click "Clear"
4. Verify all deselected

**Expected:** Buttons work as expected

#### TC-DR-05: Row Click Detail Popup
**Steps:**
1. Click resource row
2. Verify detail dialog opens
3. Verify shows all resource attributes from state

**Expected:** Detail popup works

#### TC-DR-06: Taint Selected Button
**Steps:**
1. Select 1 resource
2. Click "Taint Selected"
3. Verify terminal shows taint command

**Expected:** Taint command executes

#### TC-DR-07: Destroy Selected Button
**Steps:**
1. Select 2 resources
2. Click "Destroy Selected"
3. Verify terminal shows destroy command targeting selected

**Expected:** Destroy targets only selected resources

#### TC-DR-08: Destroy All Button
**Steps:**
1. Click "Destroy All"
2. Verify destroy command generated
3. Verify protected resources excluded

**Expected:** Full destroy excluding protected

---

### Test Suite: Target Info and Navigation

#### TC-TI-01: Gear Icon Navigation
**Steps:**
1. Navigate to `/destroy`
2. Find gear icon in target info section
3. Click gear icon
4. Verify navigation to `/fetch_target`

**Expected:** Navigates to correct page

#### TC-TI-02: Account Name Display
**Steps:**
1. Navigate to `/destroy`
2. Locate target info section
3. Verify account name displayed
4. Verify account ID displayed
5. Verify URL displayed

**Expected:** All three pieces of account info visible

---

### Test Suite: Edge Cases

#### TC-EC-01: Empty Protected Resources
**Steps:**
1. Unprotect all resources
2. Verify Protected Resources pane shows empty state
3. Verify action buttons disabled or hidden appropriately

**Expected:** Graceful handling of empty state

#### TC-EC-02: No Search Results
**Steps:**
1. Type non-matching search term "zzzzzzzzz"
2. Verify table shows empty
3. Verify filter badge shows "0 shown / N total"

**Expected:** Clear indication of no matches

#### TC-EC-03: Filter Then Select All
**Steps:**
1. Filter to show 3 of 10 resources
2. Click "Select All"
3. Clear filter to show all 10
4. Verify only the 3 are selected

**Expected:** Select All operates on filtered view only

---

### Automated Test Script Outline

```python
# test_destroy_page.py
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8082"

async def setup_session(page):
    """Load credentials and navigate to destroy page."""
    await page.goto(f"{BASE_URL}/fetch_target")
    await page.click("text=Load .env")
    # Handle existing data dialog if present
    await page.goto(f"{BASE_URL}/destroy")

async def test_protected_resources_filters(page):
    """TC-PR-02, TC-PR-03, TC-PR-04"""
    # Test type filter
    await page.click("[data-testid='protected-type-filter']")
    await page.click("text=Projects")
    rows = await page.query_selector_all(".protected-resources-table tr")
    # Assert all rows are projects
    
    # Test search filter
    await page.fill("[data-testid='protected-search']", "test")
    # Assert filtered results
    
async def test_protected_resources_selection(page):
    """TC-PR-05, TC-PR-06"""
    await page.click("text=Select All")
    counter = await page.text_content(".selection-counter")
    assert "Selected:" in counter
    
    await page.click("text=Clear")
    counter = await page.text_content(".selection-counter")
    assert "Selected: 0" in counter

async def test_detail_popup(page):
    """TC-PR-07"""
    await page.click(".protected-resources-table tr:first-child")
    dialog = await page.wait_for_selector(".resource-detail-dialog")
    assert dialog is not None
    await page.keyboard.press("Escape")

async def test_gear_navigation(page):
    """TC-TI-01"""
    await page.click("[data-testid='configure-gear']")
    assert "/fetch_target" in page.url

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await setup_session(page)
        
        await test_protected_resources_filters(page)
        await test_protected_resources_selection(page)
        await test_detail_popup(page)
        await test_gear_navigation(page)
        
        await browser.close()
        print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Manual Browser Testing Workflow

Using `cursor-browser-extension` MCP tools:

```
1. Restart server:
   ./restart_web.sh

2. Load credentials:
   browser_navigate -> http://localhost:8082/fetch_target
   browser_snapshot -> find "Load .env" button
   browser_click -> click button
   browser_snapshot -> handle dialog if present

3. Navigate to destroy page:
   browser_navigate -> http://localhost:8082/destroy
   browser_snapshot -> verify layout

4. Test each feature:
   - Filters: browser_click on dropdowns, browser_fill for search
   - Selection: browser_click on checkboxes and buttons
   - Popups: browser_click on rows, browser_press_key Escape to close
   - Navigation: browser_click on gear icon
```
