---
name: migration-webapp-browsermcp
description: Navigates, tests, and debugs the terraform-dbtcloud-yaml migration NiceGUI web app with browsermcp. Use when working on migration workflow pages, browser automation, modal/timeout issues, blank AG Grid behavior, credential bootstrapping, or end-to-end migration validation.
---

# Migration Webapp BrowserMCP

## Scope

Use this skill for the `terraform-dbtcloud-yaml` migration web app only.

- Primary repo: `/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml`
- App URL: `http://127.0.0.1:8080`
- Canonical restart script: `./restart_web.sh`
- Do not use `restart_server.sh` (not canonical in this repo)

If the task is for a different repo or workflow, stop and ask before proceeding.

## Preflight

1. Confirm project identity:
   - current repo root is `terraform-dbtcloud-yaml`
   - intended workflow is Migration (`fetch_source -> ... -> deploy`)
2. Restart app with canonical script:
   - `./restart_web.sh`
3. Assume session state was cleared after restart.
4. Reload credentials before deep testing:
   - `/fetch_target` -> `Load .env` -> handle modal if shown -> verify API token field is populated.

## BrowserMCP Interaction Contract

Always follow this order:

1. `browser_navigate` first (tab must exist)
2. `browser_lock`
3. `browser_snapshot` before any click/type
4. interact using refs from latest snapshot
5. `browser_snapshot` after interactions that change UI
6. `browser_unlock` when done

Use short readiness loops (1-3s + re-snapshot), not one long wait.

## Credential Loading Contract

Credentials are loaded via `Load .env` on:

- `/fetch_source` (source credentials)
- `/fetch_target` (target credentials)

If modal appears (`Existing Fetch Data Detected`):

- choose `Keep Existing Data` to preserve fetched outputs, or
- choose `Reset for Fresh Fetch` for a clean re-fetch, or
- press Escape to dismiss when testing modal handling.

After loading `.env`, the page reloads. Wait for a fresh snapshot before interacting again.

## Migration Workflow Route Sequence

Use this order unless the task explicitly scopes a subset:

1. `/fetch_source`
2. `/explore_source`
3. `/scope`
4. `/fetch_target`
5. `/explore_target`
6. `/match`
7. `/adopt`
8. `/configure`
9. `/target_credentials`
10. `/deploy`

Reference per-step assertions in `workflow-checklist.md`.

## AG Grid Validation Protocol (Required)

When testing Match/Adopt/Destroy-style grid pages:

1. Capture baseline screenshot before interaction.
2. Validate grid renders:
   - visible headers
   - visible rows (not white/blank body)
   - row count roughly consistent with page counters
3. Perform one interaction (filter/action/protection toggle).
4. Capture post-action screenshot.
5. Re-snapshot and verify grid content changed as expected.

If grid is blank/white:

- refresh snapshot refs and re-check after short wait
- verify modal is not blocking interaction
- verify theme/contrast and row data assumptions via debug playbook
- record evidence and stop destructive actions.

## Destructive Action Safety Policy

Default mode is non-destructive:

- allowed without authorization: fetch, inspect, match intent edits, screenshots, plan/validation-style checks.
- not allowed without authorization: deploy/apply execution and destroy execution.

### Session Grant Model

To enable destructive actions, require explicit user token:

- token: `APPROVE_DEBUG_SESSION`
- scope: current repo/workflow session only
- ttl: 240 minutes from grant
- quota:
  - max 10 deploy/apply runs
  - max 3 destroy runs

Treat all other responses as not authorized (`continue`, `looks good`, silence, implied intent).

When ttl/quota is exhausted, request a fresh grant token.

### Authorization Request Template

Use this exact structure when requesting destructive-session authorization:

`Request: destructive debug session authorization`

- `Token requested:` `APPROVE_DEBUG_SESSION`
- `Planned actions:` `<deploy/apply count estimate>`, `<destroy count estimate>`
- `Reason:` `<why destructive steps are needed now>`
- `Expected scope:` `<project/workflow/page or terraform path>`
- `Safety bounds:` `240m ttl, <=10 apply, <=3 destroy`

Proceed only after explicit token grant from the user.

### Audit Log Requirement

For each deploy/apply/destroy run during an authorized session, log:

- action type
- target path/scope
- reason for running
- result summary (success/failure + key output)

## Run Artifact Download Policy

Downloading run artifacts for debugging is allowed.

Requirement: artifacts must end up inside this repo under:

- `dev_support/artifact_analysis/`

Recommended per-run destination:

- `dev_support/artifact_analysis/run_<run_id>_<YYYYMMDD_HHMMSS>/`

Because browser download dialogs may default to arbitrary locations, always do a post-download relocation step:

1. identify downloaded file path
2. move/copy file into the repo-local analysis folder
3. record final repo-local path in notes/audit log

Use helper script:

- `./.cursor/skills/migration-webapp-browsermcp/scripts/store_run_artifacts.sh <run_id> <file1> [file2 ...]`

This script creates the timestamped run folder and copies files there.

## Timeout and Recovery Rules

If commands or browser actions stall:

1. retry once with short wait and fresh snapshot
2. if still blocked, reload page and re-establish refs
3. if still blocked, restart app with `./restart_web.sh`
4. reload credentials on `/fetch_target`
5. resume from nearest validated step in checklist

Prefer deterministic recovery over repeated blind retries.

## Typical Edge Cases To Actively Test

- credentials loaded while existing fetch data exists (modal branch)
- missing target credentials before adopt/deploy paths
- adopt -> unadopt transitions (stale import artifacts risk)
- counters/grid parity issues (rows hidden but summary non-zero)
- post-restart session behavior and project state rehydrate

## Supporting Files

- Detailed migration gates: [workflow-checklist.md](workflow-checklist.md)
- Failure triage and fixes: [debug-playbook.md](debug-playbook.md)
- Lightweight readiness checks: [scripts/smoke_migration_steps.sh](scripts/smoke_migration_steps.sh)
- Artifact relocation helper: [scripts/store_run_artifacts.sh](scripts/store_run_artifacts.sh)
