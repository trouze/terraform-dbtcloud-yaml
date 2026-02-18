# Intent Workflow Guardrails

This document captures the protection intent incident fixes and turns them into repeatable rules for all intent-driven workflows (protect, adopt, destroy, and future variants).

## What failed (root causes)

### 1) Split source of truth

The UI mismatch counters were computed from in-memory reconcile data, while move generation used a different source (`terraform.tfstate` on disk).  
Result: UI and generated Terraform artifacts diverged, causing intent drift and repeated failures.

### 2) Stale generated artifacts

`protection_moves.tf` was not always rewritten/cleared when intent deltas became empty.  
Result: stale `moved` blocks survived and triggered `Moved object still exists` failures.

### 3) Incomplete "generate" path

"Generate All Pending" did not always run the full shared generation path (intent -> YAML -> HCL -> moves/imports).  
Result: expected config updates were missing even after "generate".

### 4) Incorrect plan interpretation

Move-only plans and no-change plans were treated too similarly in some cases.  
Result: intents were marked synced when they still required apply, or UI remained stale after sync.

### 5) Missing state refresh after TF actions

After successful plan/apply outcomes, reconcile state was not always refreshed from live Terraform state and UI was not always reloaded.  
Result: false non-zero mismatch/pending counters after success.

### 6) Late failure visibility

Credential and provider failures surfaced too late and were not prominent in output views.  
Result: slower debugging and ambiguous operator actions.

### 7) Intent-only grid omitted state-only resources

Protection grid rows were built only from recorded intents, while summary counters were built from TF state.  
Result: `TF State Protected` showed non-zero while the table showed only `Synced` intents and hid state-only protected resources (for example `GRP:member`).

## Build-it-right checklist (for every intent workflow)

1. **Single source of truth:** define one canonical state for comparison and generation; all UI and artifact logic must consume that same state.
2. **One pipeline entrypoint:** all "Generate" actions call the same headless pipeline; no page-specific side generation logic.
3. **Idempotent artifact writes:** always regenerate derived files from current intent and explicitly clear files when output is empty.
4. **Plan semantics split:**
   - no-change + no-move => eligible to mark synced
   - move-only => must apply, do not auto-sync
   - non-zero add/change/destroy => normal apply path
5. **Post-action reconcile:** after successful plan no-change and after apply success, refresh from `terraform show -json` and reload UI.
6. **Preflight first:** check terraform binary, working directory, credentials, and target scope before invoking plan/apply.
7. **Failure reason first-class:** extract and display top error reason in toasts and output dialogs before raw logs.
8. **Audit trail required:** write intent mutation and synchronization events with enough context to replay decisions.
9. **Visibility parity:** any resource counted in TF-state summary cards must also be representable in the table model, even when it has no explicit intent.
10. **Separate columns for intent vs state:** always show intent target and observed TF state independently so drift is visible at row level.

## Required UI/operator steps

1. Set or adjust intents.
2. Run **Generate All Pending** (full pipeline only).
3. Run **TF Plan Pending**.
4. If plan reports moves, run **TF Apply Pending Intents**.
5. Run/confirm **Refresh TF State**.
6. Verify counters are consistent (`Mismatches=0`, `Pending TF Intents=0`) before sign-off.

## Debugging hints for future incidents

### Symptom: "Moved object still exists"

Check in this order:
1. Is generated moves file stale relative to current intent?
2. Did full pipeline regenerate HCL and moves in same run?
3. Is plan scoped to correct targets?
4. Are UI counters and generated files based on the same reconcile source?

### Symptom: Plan says "No changes" but UI still shows pending mismatch

Check:
1. Was pending intent sync executed?
2. Was reconcile state refreshed from `terraform show -json`?
3. Was page reloaded after refresh?

### Symptom: TF State Protected > 0 but table shows only Synced rows

Check:
1. Is the table sourced from intents only instead of intents + state rows?
2. Are state-only resources rendered with explicit status (for example `State Only`)?
3. Does each row expose both `Intent` and `State` columns?

### Symptom: Plan/apply fails immediately with credential/provider errors

Check:
1. Preflight token/account/host variables present.
2. Current loaded token type (service token vs PAT) and expected provider fields.
3. Failure reason surfaced in output banner (not only raw logs).

## Minimum test coverage for new intent workflows

- Unit tests:
  - source-of-truth consistency (same input drives UI and generation)
  - stale artifact clearing behavior
  - plan classification (no-change vs move-only vs mutable plan)
  - sync + refresh behavior after plan/apply
  - preflight failure matrix (missing token/account/host, no terraform binary)
- Integration/E2E:
  - full intent -> generate -> plan -> apply -> refresh -> zero mismatch path
  - explicit moved-object scenario and recovery
  - output dialog shows the failure reason banner on failed plan

## Adopt/Deploy-specific guardrails (2026-02 learnings)

1. **Unadopt invalidation is immediate**
   - When a row changes from `adopt` to `ignore`/`unadopt`, delete `adopt_imports.tf` and `adopt.tfplan` in the same handler.
   - Rationale: prevents stale import targets from failing Deploy (`Configuration for import target does not exist`).

2. **Zero-adopt must reset deployment YAML**
   - If adopt count reaches zero after previous adopt planning, copy source-normalized YAML (`state.map.last_yaml_file`) over deployment YAML and regenerate HCL.
   - Rationale: removes target baseline artifacts that are valid for scoped adoption but invalid for full Deploy plans.

3. **Adopt baseline merge is project-only**
   - In adopt-mode generate runs, merge only project records from baseline; never baseline globals.
   - Rationale: avoids unrelated global connection/environment leakage into Deploy.

4. **Count reconciliation rule**
   - Do not compare Source Select totals 1:1 with Terraform `to add` without mapping semantics.
   - Expected differences:
     - one source repository can create multiple Terraform resources (for example repository + project_repository link),
     - source credential entries may resolve to IDs and not emit credential creates.

5. **NiceGUI `ui.html` sanitize compatibility**
   - For any raw HTML renderer, use a compatibility call:
     - `try: ui.html(content, sanitize=False)`
     - `except TypeError: ui.html(content)`
   - Rationale: NiceGUI versions differ on whether `sanitize` is required/accepted.
   - Failure signature: `TypeError: __init__() missing 1 required keyword-only argument: 'sanitize'`.

