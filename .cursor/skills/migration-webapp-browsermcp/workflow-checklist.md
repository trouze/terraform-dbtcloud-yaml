# Migration Workflow Checklist

Copy this checklist into task notes and mark each gate.

## Session Setup

- [ ] Confirm repo is `terraform-dbtcloud-yaml`
- [ ] Start/restart app with `./restart_web.sh`
- [ ] Open app at `http://127.0.0.1:8080`
- [ ] Navigate to `/` and select `PS Sandbox` project after each restart
- [ ] Confirm migration workflow scope (not Jobs-as-Code / Account Explorer)

## Credential Bootstrap

- [ ] Navigate to `/fetch_source`, click `Load .env`, verify source token/account fields
- [ ] Navigate to `/fetch_target`, click `Load .env`, verify target token/account fields
- [ ] If `Existing Fetch Data Detected` appears, intentionally choose keep/reset path and verify behavior
- [ ] Capture one screenshot after credentials are visible

## Source Side

- [ ] `/fetch_source`: run fetch and verify output file path(s) displayed
- [ ] `/explore_source`: verify source data renders
- [ ] `/scope`: apply scope selection and confirm normalization completed

## Target Side

- [ ] `/fetch_target`: run fetch and verify output file path(s) displayed
- [ ] `/explore_target`: verify target data renders

## Match Intent

- [ ] `/match`: verify grid renders with visible headers and visible rows
- [ ] Take baseline screenshot before editing any row
- [ ] Change at least one row action (match/adopt/ignore) and re-snapshot
- [ ] Toggle one protection intent path and verify state reflects change
- [ ] Take post-change screenshot

## Adopt Step

- [ ] `/adopt`: verify grid renders (headers, rows, non-blank body)
- [ ] Confirm only intended rows are set to adopt
- [ ] If testing unadopt path, verify follow-up state does not keep stale import intent
- [ ] Capture before/after screenshots for any adopt/unadopt change

## Configure + Target Credentials

- [ ] `/configure`: verify deployment path/settings are set correctly
- [ ] `/target_credentials`: verify required connection/env credentials are present

## Deploy Gate

- [ ] Confirm whether destructive execution is authorized for this session
- [ ] If not authorized, stop at non-destructive validation
- [ ] If authorized, record the action in session audit log before/after execution

## State Management Utility

- [ ] `/removal-management`: verify page title is **State Management**
- [ ] Verify both sections render: **State Refresh** and **State Removal**
- [ ] Verify `Refresh Selected` is disabled when no rows are selected
- [ ] Run `Refresh All In State` plan path and confirm `View Plan Output` becomes enabled
- [ ] Open `View Plan Output` and confirm the shared viewer dialog renders
- [ ] Verify removal actions remain available and unchanged in behavior (preview + execute controls)

## Destroy Gate

- [ ] Confirm destroy quota remains and session grant is still valid
- [ ] If not explicitly authorized, do not execute destroy
- [ ] If authorized, record pre-state and post-state evidence

## AG Grid Evidence Standard

For each grid-tested page (at minimum Match and Adopt):

- [ ] screenshot before interaction
- [ ] screenshot after interaction
- [ ] snapshot evidence that row/header visibility is intact
- [ ] note any summary count vs row visibility mismatch

## Completion Evidence

- [ ] Final URL captured
- [ ] Key screenshots attached (credential-loaded, match grid, adopt grid)
- [ ] Any downloaded run artifacts copied to `dev_support/artifact_analysis/run_<run_id>_<timestamp>/`
- [ ] Final repo-local artifact path(s) recorded in notes
- [ ] Failures include actionable reason + attempted recovery steps
