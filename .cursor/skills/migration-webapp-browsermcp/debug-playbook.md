# Migration Debug Playbook

Use this when browser automation or migration flow behavior is unstable.

## 1) Modal blocks interaction

Symptoms:

- click/typing does nothing
- refs appear valid but page seems frozen

Actions:

1. snapshot again (modal is often at end of tree)
2. dismiss dialog (`Escape`) or click modal button explicitly
3. re-snapshot and continue with fresh refs

Common modal:

- `Existing Fetch Data Detected` after `Load .env`

## 2) Browser element ref failures or stale refs

Symptoms:

- element not found
- click points to outdated element

Actions:

1. do not reuse old refs after navigation/reload
2. take new snapshot
3. retry interaction once with new ref

## 3) Timeout (browser or command)

Symptoms:

- route/action hangs
- command exceeds expected runtime

Actions:

1. short wait + snapshot loop (1-3s intervals)
2. retry once
3. hard recover:
   - reload current page
   - if still stuck: `./restart_web.sh`
   - reload credentials on `/fetch_target`
4. resume from last validated checklist step

## 4) Blank/white AG Grid

Symptoms:

- counters present but table appears empty/white
- headers or rows not visible

Actions:

1. capture screenshot immediately (baseline evidence)
2. snapshot to verify whether rows exist in accessibility tree
3. ensure modal/dialog is not overlaying the grid
4. perform small interaction (filter or row action), then resnapshot
5. capture second screenshot and compare
6. if still blank, stop destructive actions and report with evidence

Minimum AG Grid evidence:

- screenshot before action
- screenshot after action
- note on header visibility
- note on row visibility and counter parity

## 5) Credentials appear missing after restart

Symptoms:

- token/account fields blank
- downstream steps fail due to credentials

Actions:

1. navigate to `/fetch_target`
2. click `Load .env`
3. handle existing fetch modal (keep/reset)
4. wait for page reload
5. verify API token field is populated

## 6) Plan/apply state mismatch in UI

Symptoms:

- plan/apply completes but mismatch counters look stale

Actions:

1. verify post-command refresh occurred
2. reload page and re-check counters/table parity
3. compare summary cards with table rows (state vs intent visibility)
4. report any divergence with screenshots and command output summary

## 7) Destructive actions without clear permission

Rule:

- no deploy/apply/destroy without active session grant

Required token:

- `APPROVE_DEBUG_SESSION`

Grant constraints:

- valid 240 minutes
- up to 10 deploy/apply runs
- up to 3 destroy runs

If no active grant:

- continue with non-destructive checks only
- request grant token once with concise reason and expected actions

## 8) Downloaded artifacts saved outside repo

Symptoms:

- browser downloads succeeded but file landed in `Downloads` or unknown OS path
- analysis artifacts are not traceable from repo history/context

Actions:

1. identify downloaded file path(s)
2. run:
   - `./.cursor/skills/migration-webapp-browsermcp/scripts/store_run_artifacts.sh <run_id> <file1> [file2 ...]`
3. verify files now exist under:
   - `dev_support/artifact_analysis/run_<run_id>_<timestamp>/`
4. record final repo-local path in task notes

Rule:

- do not leave run-debug artifacts only in external folders
