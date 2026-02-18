# Ralph Guardrails (Signs)

> Lessons learned from past failures. READ THESE BEFORE ACTING.

## Core Signs

### Sign: Read Before Writing
- **Trigger**: Before modifying any file
- **Instruction**: Always read the existing file first
- **Added after**: Core principle

### Sign: Test After Changes
- **Trigger**: After any code change
- **Instruction**: Run tests to verify nothing broke
- **Added after**: Core principle

### Sign: Commit Checkpoints
- **Trigger**: Before risky changes
- **Instruction**: Commit current working state first
- **Added after**: Core principle

---

## Learned Signs

(Signs added from observed failures will appear below)

### Sign: One Reconcile Truth
- **Trigger**: Any intent workflow computes mismatches, generates artifacts, or marks sync
- **Instruction**: Use a single canonical reconcile source for UI and generation; do not mix in-memory reconcile and direct tfstate parsing without explicit reconciliation
- **Evidence**: Protection mismatch drift and stale `moved` behavior despite successful plan/apply
- **Added after**: 2026-02-17 protection workflow incident

### Sign: Refresh After Sync
- **Trigger**: plan/apply indicates intent synchronization
- **Instruction**: Immediately refresh reconcile state from `terraform show -json`, persist, and reload UI before reporting final counters
- **Evidence**: Plan showed no changes while UI still reported non-zero mismatch/pending intents
- **Added after**: 2026-02-17 protection workflow incident

### Sign: Clear Empty Derived Artifacts
- **Trigger**: computed intent deltas are empty during generation
- **Instruction**: Explicitly clear generated move/import artifacts to avoid stale operations
- **Evidence**: stale `protection_moves.tf` produced recurring `Moved object still exists`
- **Added after**: 2026-02-17 protection workflow incident

### Sign: Summary/Table Parity
- **Trigger**: UI summary cards and table rows disagree on protected or pending counts
- **Instruction**: Build table rows from the same reconcile source as summary cards; include state-only rows and keep `Intent` and `State` distinct
- **Evidence**: `TF State Protected = 1` while intent table showed only synced rows and hid `GRP:member`
- **Added after**: 2026-02-18 protection visibility incident

### Sign: Unadopt Must Clear Artifacts
- **Trigger**: User changes an Adopt row back to `ignore`/`unadopt`
- **Instruction**: Immediately delete stale `adopt_imports.tf` and `adopt.tfplan`; never allow Deploy to consume prior adopt artifacts.
- **Evidence**: Deploy failed with `Configuration for import target does not exist` after a previously adopted project was ignored.
- **Added after**: 2026-02-18 stale import target incident

### Sign: Zero-Adopt Reset Baseline
- **Trigger**: Adopt selection count becomes zero after prior adopt planning
- **Instruction**: Reset `deployments/migration/dbt-cloud-config.yml` from source-normalized YAML (`state.map.last_yaml_file`) and regenerate HCL to remove baseline-injected target globals.
- **Evidence**: Full Deploy plan showed unrelated global connections after unadopt unless deployment YAML was reset.
- **Added after**: 2026-02-18 adopt/deploy leakage incident

### Sign: Adopt Baseline Merge Scope
- **Trigger**: Running generate pipeline in adopt mode (`include_adopt=true`, no protection-moves run)
- **Instruction**: Merge only project records from target baseline in adopt-mode; do not merge baseline globals.
- **Evidence**: Baseline global merge produced large unrelated `+ create` plans in Deploy.
- **Added after**: 2026-02-18 adopt baseline merge incident

### Sign: Scope Count vs TF Count
- **Trigger**: Source Select resource total differs from Terraform `Plan: X to add`
- **Instruction**: Cross-reference by Terraform resource shape before calling it a bug (for example: one source repo may map to `dbtcloud_repository` + `dbtcloud_project_repository`; credential entries may be referenced IDs, not `+ create` resources).
- **Evidence**: Source total `53` vs TF plan `49` was valid after accounting for resource mapping semantics.
- **Added after**: 2026-02-18 count reconciliation review

### Sign: NiceGUI HTML Sanitize Compatibility
- **Trigger**: Rendering HTML with `ui.html(...)` in any page/component.
- **Instruction**: Use compatibility wrapper pattern: `try: ui.html(content, sanitize=False) except TypeError: ui.html(content)` to support both NiceGUI signatures.
- **Evidence**: `TypeError: __init__() missing 1 required keyword-only argument: 'sanitize'` in Explore Target ERD (`erd_viewer.py`) and other HTML renderers.
- **Added after**: 2026-02-18 UI sanitize API regression

