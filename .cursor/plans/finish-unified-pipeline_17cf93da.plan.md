---
name: finish-unified-pipeline
overview: Complete PRD 43.03 by wiring existing headless pipeline into Adopt and Utilities pages, removing Match-page Terraform execution, and closing remaining test/doc gaps while accounting for intervening repo changes.
todos:
  - id: rewire-adopt
    content: Replace Adopt local generation phases with run_generate_pipeline(include_adopt=True) and use PipelineResult target_flags
    status: completed
  - id: rewire-utilities
    content: Replace Utilities generate_all_pending internals with run_generate_pipeline(include_adopt=False) and keep plan/apply wired to shared flags
    status: completed
  - id: strip-match-exec
    content: Remove Match generation/terraform execution UI and keep intent-only + Continue to Adopt navigation
    status: completed
  - id: update-tests-architecture
    content: Refactor stale architecture tests to pipeline entrypoint and add Match no-terraform regression
    status: completed
  - id: add-missing-harnesses
    content: Add snapshot/property/integration harnesses from PRD 43.03
    status: completed
  - id: sync-docs-status
    content: Update PRD/plan docs to reflect implemented vs pending work after rewiring
    status: completed
isProject: false
---

# Finish PRD 43.03 Wiring

## Current Status (Reconciled 2026-02-18)

Completed:

- `run_generate_pipeline()` and `PipelineResult` exist in [importer/web/utils/generate_pipeline.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/utils/generate_pipeline.py).
- Shared Terraform helpers exist in [importer/web/utils/terraform_helpers.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/utils/terraform_helpers.py).
- `removal_keys` persistence is implemented in [importer/web/state.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/state.py) (`to_dict` + `from_dict`).
- New harnesses are present and passing for pipeline/matrix/key consistency.

Completed since initial draft:

- [importer/web/pages/adopt.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/pages/adopt.py) now executes via `run_generate_pipeline(...)` and consumes pipeline targeting.
- [importer/web/pages/utilities.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/pages/utilities.py) uses pipeline generation for protection-only flows.
- Match execution panel is disabled and intent-only navigation to Adopt is retained in [importer/web/pages/match.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/pages/match.py).
- Regression tests added for adopt/deploy leakage prevention and Match intent-only contract.

## Implementation Plan

### 1) Rewire Adopt Page to Canonical Pipeline

Target file:

- [importer/web/pages/adopt.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/pages/adopt.py)

Actions:

- Replace Phase 3/4 local generation steps (`cleanup_unadopted_yaml_configs`, `inject_adopted_resource_configs`, `apply_protection_from_set`, `apply_unprotection_from_set`, `write_adopt_imports_file`) with a single call:
  - `run_generate_pipeline(state, include_adopt=True, adopt_rows=rows_to_import, include_protection_moves=True)`
- Use `PipelineResult.target_flags` for plan/apply scoping.
- Remove `protection_moves.tf` temporary rename-aside logic.
- Keep current terminal UX and status updates, but report pipeline progress through callback.

### 2) Rewire Utilities Page to Canonical Pipeline

Target file:

- [importer/web/pages/utilities.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/pages/utilities.py)

Actions:

- Replace `generate_all_pending()` internals with:
  - `run_generate_pipeline(state, include_adopt=False, include_protection_moves=True)`
- Preserve current status cards, intent controls, and audit history UI.
- Ensure existing plan/apply buttons consume pipeline output (`target_flags`) and no longer rely on parallel local generation behavior.

### 3) Strip Match Page of Execution Logic

Target file:

- [importer/web/pages/match.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/pages/match.py)

Actions:

- Remove/disable generation + terraform execution handlers (`start_generate_protection_changes`, `do_generate_work`, init/plan/apply command panel).
- Keep intent recording logic (action/protection toggles, dialogs, intent status).
- Add/retain clear navigation CTA: Continue to Adopt & Apply.

### 4) Stabilize Against Intervening Repo Changes

High-conflict files currently changing in branch:

- [importer/web/pages/utilities.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/pages/utilities.py)
- [importer/web/state.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/state.py)
- [importer/web/pages/deploy.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/pages/deploy.py)

Actions:

- Reconcile imports/helper usage so pages only call shared helpers from `terraform_helpers.py`.
- Ensure no reintroduction of page-local env/path helper implementations.

### 5) Close Remaining Test Gaps

Keep passing:

- [importer/web/tests/test_generate_pipeline.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/tests/test_generate_pipeline.py)
- [importer/web/tests/test_action_protection_matrix.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/tests/test_action_protection_matrix.py)
- [importer/web/tests/test_intent_key_consistency.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/tests/test_intent_key_consistency.py)
- [importer/web/tests/test_cross_page_pipeline_consistency.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/tests/test_cross_page_pipeline_consistency.py)

Add/update:

- Rework architecture-stale tests (notably [importer/web/tests/test_generate_consistency.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/tests/test_generate_consistency.py)) to assert pipeline entrypoint behavior.
- Add missing PRD harnesses:
  - `test_terraform_artifact_snapshots.py`
  - `test_protection_state_machine.py`
  - `test_adopt_protect_integration.py`
- Add explicit regression asserting Match page does not execute Terraform.

### 6) Align Documentation with Current Reality

Update docs to reflect completed vs pending work:

- [prd/43.03-Unified-Protect-Adopt-Pipeline.md](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/prd/43.03-Unified-Protect-Adopt-Pipeline.md): mark `removal_keys` persistence as done, add implementation status section.
- [.cursor/plans/consolidate_adopt_and_protect_88ef63c2.plan.md](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/plans/consolidate_adopt_and_protect_88ef63c2.plan.md): align Utilities step language with pipeline replacement.

## Verification

- Run focused test suites for modified pages and pipeline tests.
- Run architecture contract tests in [importer/web/tests/test_contract_enforcement.py](/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/importer/web/tests/test_contract_enforcement.py).
- Browser validation flow:
  - Match: set intents only
  - Navigate to Adopt: generate+plan+apply via pipeline
  - Utilities: generate+plan+apply protection-only via pipeline
  - Confirm cross-page state and targeting behavior remain correct.

## Final Notes

- Keep execution centralized on Adopt/Utilities and avoid reintroducing Match terraform actions.
- Preserve guardrails documented in `.ralph/guardrails.md` and `docs/guides/intent-workflow-guardrails.md`.

