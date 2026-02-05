# PRD: Web UI - Part 2: Fetch Step

## Introduction

The Fetch step of the dbt Cloud Importer Web UI. This allows users to configure source account credentials and execute the fetch operation to download account data from dbt Cloud. It also supports fetching target account data for migration scenarios where existing infrastructure must be matched.

This is **Part 2 of 5** in the Web UI PRD series.  
**Depends on:** Part 1 (Core Shell)

## Goals

- Provide a form for entering source dbt Cloud credentials
- Support loading/saving credentials from/to `.env` files
- Execute the fetch operation with real-time progress feedback
- Display fetch results and automatically transition to Explore step
- **Support fetching target account data separately from source data**
- **Produce target artifacts in the same normalized format for comparison/matching**
- **Keep source and target outputs distinct (never overwrite source with target)**

## User Stories

### US-007: Configure Source Credentials Form
**Description:** As a user, I want to enter my source dbt Cloud account credentials so that the importer can fetch my account data.

**Acceptance Criteria:**
- [ ] Form fields for: Host URL, Account ID, API Token
- [ ] Host URL has sensible default (`https://cloud.getdbt.com`)
- [ ] Account ID field accepts only numeric input
- [ ] API Token field is password-masked (with show/hide toggle)
- [ ] All fields show validation state (valid/invalid/empty)
- [ ] Error messages displayed inline below invalid fields
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-008: Load Credentials from Environment
**Description:** As a user, I want to load credentials from my `.env` file so that I don't have to re-enter them each time.

**Acceptance Criteria:**
- [ ] "Load from .env" button populates form from `.env` file
- [ ] Reads `DBT_SOURCE_HOST_URL`, `DBT_SOURCE_ACCOUNT_ID`, `DBT_SOURCE_API_TOKEN`
- [ ] Shows success notification when loaded
- [ ] Shows warning if `.env` file not found
- [ ] Shows warning if specific keys are missing
- [ ] File path is configurable (default: repo root `.env`)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-009: Save Credentials to Environment
**Description:** As a user, I want to save my credentials to `.env` so that I can reuse them later.

**Acceptance Criteria:**
- [ ] "Save to .env" button writes current form values to `.env`
- [ ] Writes `DBT_SOURCE_HOST_URL`, `DBT_SOURCE_ACCOUNT_ID`, `DBT_SOURCE_API_TOKEN`
- [ ] Preserves other existing keys in the `.env` file
- [ ] Shows success notification when saved
- [ ] Creates `.env` file if it doesn't exist
- [ ] Confirmation prompt if overwriting existing values
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-010: Configure Fetch Options
**Description:** As a user, I want to configure fetch options so that I can control where output is saved.

**Acceptance Criteria:**
- [ ] Output directory field with file browser button
- [ ] Default value from `importer_mapping.yml` or sensible default
- [ ] Toggle for auto-timestamp filenames (default: on)
- [ ] Advanced options collapsible section:
  - API timeout (seconds)
  - Max retries
  - SSL verification toggle
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-011: Execute Fetch Operation
**Description:** As a user, I want to fetch my dbt Cloud account data so that I can explore what will be migrated.

**Acceptance Criteria:**
- [ ] "Fetch Account Data" button triggers fetch
- [ ] Button disabled while fetch in progress
- [ ] Validation runs before fetch (all required fields filled)
- [ ] Progress spinner/indicator during fetch
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-012: View Fetch Progress Output
**Description:** As a user, I want to see real-time progress during fetch so that I know it's working.

**Acceptance Criteria:**
- [ ] Terminal-style output panel shows log messages
- [ ] Messages appear in real-time (streamed, not batched)
- [ ] Shows API calls being made (e.g., "Fetching projects...")
- [ ] Shows resource counts as discovered
- [ ] Panel is scrollable with auto-scroll to bottom
- [ ] "Copy logs" button to copy output to clipboard
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-013: Handle Fetch Success
**Description:** As a user, I want clear feedback when fetch succeeds so that I know I can proceed.

**Acceptance Criteria:**
- [ ] Success notification with summary stats
- [ ] Stats include: X projects, Y environments, Z jobs, etc.
- [ ] Shows paths to generated files (JSON, summary, report)
- [ ] "Continue to Explore" button appears
- [ ] Clicking continue navigates to Explore step
- [ ] Account data loaded into session state
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-014: Handle Fetch Errors
**Description:** As a user, I want clear error messages when fetch fails so that I can fix the issue.

**Acceptance Criteria:**
- [ ] Error notification with user-friendly message
- [ ] Common errors have specific guidance:
  - 401: "Invalid API token or insufficient permissions"
  - 404: "Account not found - check Account ID"
  - Network error: "Cannot connect - check Host URL"
- [ ] Full error details available in expandable section
- [ ] "Retry" button to attempt fetch again
- [ ] Form remains editable to fix credentials
- [ ] Typecheck passes
- [ ] Verify in browser

---

## Target Fetch Sub-Flow

The Target Fetch sub-flow enables fetching data from the **target** dbt Cloud account (the destination for migration). This is essential when migrating to an account that already has existing infrastructure that must be matched and imported into Terraform state.

### US-015: Switch Between Source and Target Fetch Modes
**Description:** As a user, I want to switch between fetching source and target accounts so that I can gather data from both sides of a migration.

**Acceptance Criteria:**
- [ ] Tab or toggle to switch between "Source Fetch" and "Target Fetch" modes
- [ ] Clear visual distinction between source and target modes (different accent color/icon)
- [ ] Mode indicator always visible (e.g., "Fetching: SOURCE" or "Fetching: TARGET")
- [ ] Each mode maintains its own credential state
- [ ] Switching modes does not clear the other mode's data
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-016: Configure Target Credentials Form
**Description:** As a user, I want to enter my target dbt Cloud account credentials so that the importer can fetch the target account data.

**Acceptance Criteria:**
- [ ] Form fields for: Target Host URL, Target Account ID, Target API Token
- [ ] Uses `DBT_TARGET_*` environment variable naming (distinct from `DBT_SOURCE_*`)
- [ ] "Load from .env" / "Save to .env" buttons for target credentials
- [ ] Reads/writes `DBT_TARGET_HOST_URL`, `DBT_TARGET_ACCOUNT_ID`, `DBT_TARGET_API_TOKEN`
- [ ] Validation identical to source form (URL format, numeric ID, non-empty token)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-017: Execute Target Fetch Operation
**Description:** As a user, I want to fetch my target dbt Cloud account data so that I can identify existing resources to match during migration.

**Acceptance Criteria:**
- [ ] "Fetch Target Account Data" button triggers fetch with target credentials
- [ ] Uses same fetcher logic as source fetch (`importer.fetcher.fetch_account()`)
- [ ] Progress indicator and real-time log output (same as source fetch)
- [ ] Output files saved to separate target-specific directory or with target prefix
- [ ] Output filenames include `_target_` marker (e.g., `account_12345_target_run_001__raw__.json`)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-018: Target Fetch Output Separation
**Description:** As a user, I want target fetch outputs to be clearly separated from source outputs so that I never accidentally overwrite or confuse source data.

**Acceptance Criteria:**
- [ ] Target fetch outputs use distinct directory or filename convention
- [ ] Option A: Separate subdirectory (e.g., `output/target/`)
- [ ] Option B: Filename prefix/suffix (e.g., `*_target_*`)
- [ ] UI clearly shows which output set is being viewed (source vs. target)
- [ ] Cannot overwrite source outputs when running target fetch
- [ ] Session state tracks both source and target fetch results independently
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-019: View Target Fetch Summary
**Description:** As a user, I want to see a summary of the target account after fetch so that I understand what already exists in the destination.

**Acceptance Criteria:**
- [ ] Target summary tab/panel shows account name and resource counts
- [ ] Summary displays: X projects, Y environments, Z jobs, N connections, etc.
- [ ] Clear label indicating this is "Target Account" data
- [ ] Side-by-side or tabbed comparison with source summary (if both fetched)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-020: Target Fetch for Matching Workflow
**Description:** As a user, I want the target fetch data to be available for the matching workflow so that I can identify which source resources map to existing target resources.

**Acceptance Criteria:**
- [ ] Target fetch artifacts are normalized using the same YAML pipeline as source
- [ ] Target `report_items` JSON available for matching logic in later steps
- [ ] Target data accessible from Map and Deploy steps for comparison
- [ ] Warning if attempting to proceed to Map/Deploy without target fetch (when target matching is enabled)
- [ ] Typecheck passes
- [ ] Verify in browser

## Functional Requirements

- **FR-1:** Fetch form must include Host URL, Account ID, and API Token fields
- **FR-2:** Credentials must be loadable from `.env` files
- **FR-3:** Credentials must be savable to `.env` files
- **FR-4:** Fetch must call the existing `importer.fetcher.fetch_account()` function
- **FR-5:** Fetch progress must be streamed to the UI in real-time
- **FR-6:** Fetch errors must display user-friendly messages with remediation hints
- **FR-7:** Successful fetch must store account data in session state
- **FR-8:** Target fetch must use separate credentials (`DBT_TARGET_*` environment variables)
- **FR-9:** Target fetch outputs must be stored separately from source outputs (different directory or filename convention)
- **FR-10:** Target fetch must produce artifacts in the same normalized format as source fetch
- **FR-11:** Session state must track source and target fetch results independently
- **FR-12:** UI must clearly indicate whether source or target mode is active

## Non-Goals (Out of Scope)

- Partial fetch (fetching only specific resource types)
- Scheduling recurring fetches
- Fetch from multiple accounts simultaneously
- Automated diffing/comparison logic in the Fetch step (comparison happens in Map/Deploy)

## Technical Considerations

### Integration with Existing Fetcher
```python
from importer.fetcher import fetch_account
from importer.config import Config

async def run_fetch(host_url: str, account_id: int, api_token: str, output_dir: str):
    config = Config(
        source_host_url=host_url,
        source_account_id=account_id,
        source_api_token=api_token,
    )
    # fetch_account is sync, run in thread pool
    result = await asyncio.to_thread(fetch_account, config, output_dir)
    return result
```

### Target Fetch Integration
```python
async def run_target_fetch(host_url: str, account_id: int, api_token: str, output_dir: str):
    """Fetch target account data with separate output path."""
    config = Config(
        source_host_url=host_url,  # Reuse same Config, just different credentials
        source_account_id=account_id,
        source_api_token=api_token,
    )
    # Use target-specific output directory
    target_output_dir = Path(output_dir) / "target"
    target_output_dir.mkdir(parents=True, exist_ok=True)
    
    result = await asyncio.to_thread(fetch_account, config, str(target_output_dir))
    return result
```

### Output Directory Structure
```
output/
├── source/                          # Source account fetch outputs
│   ├── account_12345_run_001__raw__.json
│   ├── account_12345_run_001__summary__.md
│   └── account_12345_run_001__report_items__.json
└── target/                          # Target account fetch outputs
    ├── account_67890_run_001__raw__.json
    ├── account_67890_run_001__summary__.md
    └── account_67890_run_001__report_items__.json
```

### Log Streaming
- Capture log output by adding a custom log handler
- Push log messages to UI via NiceGUI's `ui.log` or custom component
- Use `asyncio.Queue` for thread-safe message passing

### File Structure Addition
```
importer/web/
├── pages/
│   └── fetch.py              # Fetch step page (source + target modes)
└── components/
    ├── credential_form.py    # Reusable credential form (used for both)
    └── terminal_output.py    # Log/terminal output component
```

### Session State for Dual Fetch
```python
@dataclass
class FetchState:
    # Source fetch state
    source_credentials: dict = field(default_factory=dict)
    source_fetch_complete: bool = False
    source_account_data: Optional[dict] = None
    source_output_dir: str = ""
    
    # Target fetch state
    target_credentials: dict = field(default_factory=dict)
    target_fetch_complete: bool = False
    target_account_data: Optional[dict] = None
    target_output_dir: str = ""
    
    # Current mode
    active_mode: str = "source"  # "source" or "target"
```

## Success Metrics

- Credentials load from `.env` in under 500ms
- Fetch progress updates appear within 1 second of occurrence
- Error messages are actionable (user knows what to fix)
- Full fetch of 100-resource account completes without UI freezing
- Target fetch produces artifacts in identical format to source fetch
- Switching between source/target modes takes under 100ms
- Source and target outputs never overwrite each other

## Open Questions

1. Should we support profile-based credential sets (e.g., "production", "staging")?
2. Should there be a "test connection" button before full fetch?
3. Should target fetch be required before proceeding to Map/Deploy, or optional?
4. Should we support fetching source and target in parallel (two concurrent fetch operations)?
5. How should we handle the case where source and target are the same account (same-account migration)?