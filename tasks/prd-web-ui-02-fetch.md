# PRD: Web UI - Part 2: Fetch Step

## Introduction

The Fetch step of the dbt Cloud Importer Web UI. This allows users to configure source account credentials and execute the fetch operation to download account data from dbt Cloud.

This is **Part 2 of 5** in the Web UI PRD series.  
**Depends on:** Part 1 (Core Shell)

## Goals

- Provide a form for entering source dbt Cloud credentials
- Support loading/saving credentials from/to `.env` files
- Execute the fetch operation with real-time progress feedback
- Display fetch results and automatically transition to Explore step

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

## Functional Requirements

- **FR-1:** Fetch form must include Host URL, Account ID, and API Token fields
- **FR-2:** Credentials must be loadable from `.env` files
- **FR-3:** Credentials must be savable to `.env` files
- **FR-4:** Fetch must call the existing `importer.fetcher.fetch_account()` function
- **FR-5:** Fetch progress must be streamed to the UI in real-time
- **FR-6:** Fetch errors must display user-friendly messages with remediation hints
- **FR-7:** Successful fetch must store account data in session state

## Non-Goals (Out of Scope)

- Partial fetch (fetching only specific resource types)
- Fetch comparison (comparing two accounts)
- Scheduling recurring fetches
- Fetch from multiple accounts simultaneously

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

### Log Streaming
- Capture log output by adding a custom log handler
- Push log messages to UI via NiceGUI's `ui.log` or custom component
- Use `asyncio.Queue` for thread-safe message passing

### File Structure Addition
```
importer/web/
├── pages/
│   └── fetch.py              # Fetch step page
└── components/
    ├── credential_form.py    # Reusable credential form
    └── terminal_output.py    # Log/terminal output component
```

## Success Metrics

- Credentials load from `.env` in under 500ms
- Fetch progress updates appear within 1 second of occurrence
- Error messages are actionable (user knows what to fix)
- Full fetch of 100-resource account completes without UI freezing

## Open Questions

1. Should we support profile-based credential sets (e.g., "production", "staging")?
2. Should there be a "test connection" button before full fetch?
