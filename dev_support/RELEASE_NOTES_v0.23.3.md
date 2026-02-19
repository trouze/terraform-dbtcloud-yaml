# Release Notes - v0.23.3

**Date:** 2026-02-19  
**Type:** Patch Release  
**Previous Version:** 0.23.2

## Summary

This patch consolidates Adopt/Match workflow stabilizations completed during iterative debugging, adds AG Grid regression guardrails, and hardens repository hygiene by excluding local runtime logs and machine artifacts from version control.

## Key Fixes

### Adopt AG Grid Visibility + Data Shaping
- **Problem**: Adopt page could show correct counts while the AG Grid appeared blank/white (headers/rows not visible).
- **Fixes**:
  - Standardized Adopt AG Grid theme usage to stable quartz behavior.
  - Preserved row/action shaping contracts for actionable Adopt candidates.
  - Guarded against target-only row leakage into Adopt-visible grid payloads.
- **Result**: Adopt row counts and visible grid rows stay aligned and readable.

### Adopt Plan Reliability
- **Problem**: Adopt plan failures could occur from missing module install state or fallback generation ordering.
- **Fixes**:
  - Hardened fallback generation/init sequencing before plan execution.
  - Added defensive retry behavior for transient "module not installed" failures.
- **Result**: More stable and repeatable adopt plan/apply runs in project-scoped workflows.

### Match/Intent Consistency
- **Problem**: State-loaded indicators and pending/action behavior could drift across page transitions/reset paths.
- **Fixes**:
  - Tightened match/adopt action default behavior in state-aware scenarios.
  - Corrected stale state-loaded reporting and pending status semantics.
- **Result**: Cross-page behavior is now consistent with actual TF state availability.

## Standards + Guardrails

- Added AG Grid regression standards and decisions in:
  - `docs/guides/intent-workflow-guardrails.md`
  - `prd/00.01-Standards-of-Development.md`
  - `.ralph/guardrails.md`
- Added contract tests to prevent regressions in Adopt AG Grid theme selection:
  - `importer/web/tests/test_contract_enforcement.py`

## Repository Hygiene

- Updated `.gitignore` to keep local runtime artifacts out of commits:
  - `.cursor/debug*.log`
  - `.cursor/ui_actions.log*`
  - `.DS_Store`
  - local debug/sample output folders under `dev_support/bt*`
- Removed tracked log artifacts from the index so future commits remain clean.

## Verification

1. Run focused regression tests:
   - `python3 -m pytest importer/web/tests/test_adopt_summary.py importer/web/tests/test_contract_enforcement.py`
2. Run targeted workflow tests touched by this patch train:
   - `python3 -m pytest importer/web/tests/test_match_grid.py importer/web/tests/test_generate_pipeline.py`
3. Confirm local log files are ignored:
   - `git status --short` should not show `.cursor/debug*.log` or `.cursor/ui_actions.log*`.

