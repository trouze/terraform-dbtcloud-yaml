---
task: "PRD 43.01 — Adoption Workflow (Part 1: Migration Adoption)"
test_command: "cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml && python -m pytest importer/web/tests/test_adoption_imports.py importer/web/tests/test_adoption_yaml_updater.py importer/web/tests/test_match_grid.py -v"
browser_validation: true
base_url: "http://127.0.0.1:8080"
---

# Task: PRD 43.01 — Adoption Workflow (Part 1: Migration Adoption)

Implement the Migration Adoption workflow per PRD `prd/43.01-Import-Adopt-Workflow.md`.
Build adoption capabilities in the Match grid, YAML generation, import blocks, TF state awareness,
dependency handling, protection, and deploy integration. All components must be reusable for Part 2.

**PRD Reference:** `prd/43.01-Import-Adopt-Workflow.md`

## Success Criteria

### Phase 1a: Core Adopt Flow (Source-Matched)

1. [x] `generate_adopt_imports_from_grid()` produces import blocks for adopt rows and skips ignore rows (UT-AD-01, UT-AD-25)
2. [x] `generate_adopt_imports_from_grid()` uses `protected_<type>` addresses for protected rows (UT-AD-02)
3. [x] `apply_adoption_overrides()` overwrites YAML with target values and preserves protection flag (UT-AD-03, UT-AD-04)
4. [x] Import block addresses resolve correctly for all 7 resource types: PRJ, ENV, JOB, REP, PREP, EXTATTR, VAR (UT-AD-05)
5. [x] Match grid shows "Adopt Existing" action for source-matched resources; adopt badge visible (E2E, browser_validation: true)
6. [x] "Adopt All Matched" and "Ignore All Unmatched" bulk actions work in grid (E2E, browser_validation: true)
7. [x] Adoption summary card shows correct counts: adopt matched, create, ignore (E2E, browser_validation: true)

### Phase 1b: Target-Only Adoption

8. [x] `build_grid_data()` produces `is_target_only: True` with default action="ignore" and empty source columns (UT-AD-20, UT-AD-21, UT-AD-22)
9. [x] `normalize_target_fetch()` generates valid YAML for target-only resources (UT-AD-11)
10. [x] `generate_adopt_imports_from_grid()` handles mixed source-matched and target-only rows (UT-AD-12)
11. [x] Target-only rows visible in grid with "Target Only" badge and empty Source column (E2E, browser_validation: true)
12. [x] "Show Target-Only Resources" toggle hides/shows target-only rows; "Adopt All Target-Only" bulk action works (E2E, browser_validation: true)

### Phase 1b-ext: Target-Only Preference

13. [x] Project-level preference loads from config and drives grid toggle default (UT-AD-14)
14. [x] First-run dialog triggers only when unmatched target-only resources exist (UT-AD-15)
15. [x] First-run dialog: "Yes, show them" / "No thanks" / "Remember this choice" all work (E2E, browser_validation: true)
16. [x] Configure page toggle changes project-level preference (E2E, browser_validation: true)

### Phase 1b-ext: Scope Visibility Filter

17. [x] Scope filter hides state-only and target-only rows when ON; preserves source-scoped rows (UT-AD-16, UT-AD-17, UT-AD-18)
18. [x] Scope filter does not alter row actions or dispositions (UT-AD-19)
19. [x] "Show Scoped Only" toggle in grid toolbar works and composes with type filter (E2E, browser_validation: true)
20. [x] Summary card updates to show filtered counts with "(filtered — N rows hidden)" note (E2E, browser_validation: true)

### Phase 1c: TF State Awareness

21. [x] State cross-reference identifies already-managed resources including protection mismatch (UT-AD-06, UT-AD-07)
22. [x] "Already Managed" badge and TF state address shown in grid for state-present resources (E2E, browser_validation: true)
23. [x] Already-managed resources excluded from import block output (E2E, browser_validation: true)

### Phase 1d: Dependency Handling

24. [x] Dependency resolution returns correct parent chain for all child types (UT-AD-08, UT-AD-24)
25. [x] Cascade dialog shows when adopting child without parent; "Adopt All" and "Skip" work (E2E, browser_validation: true)
26. [x] "Select Whole Project" dialog shows child counts and supports checkbox customization (E2E, browser_validation: true)

### Phase 1e: Protection Integration

27. [x] Protection checkbox available for adopted resources; cascade dialog suggests parent protection (E2E, browser_validation: true)
28. [x] Protection decisions persist across page navigation Match → Configure → Match (E2E, browser_validation: true)
29. [x] Protected addresses in import blocks and moved blocks for protection status changes (UT-AD-02, UT-AD-04)

### Phase 1f: Deploy Integration

30. [x] Deploy summary shows import count: N to import, M to create, K protected (E2E, browser_validation: true)
31. [x] `terraform plan` shows "will be imported" for adopted resources (E2E, browser_validation: true)
32. [x] `terraform apply` imports adopted resources into state with correct target IDs (E2E, browser_validation: true)
33. [x] Import block cleanup after successful apply (UT or file verification)

### Full Workflow E2E

34. [x] Source-matched adopt end-to-end: Match adopt → Configure → Deploy → verify YAML + imports + summary (E2E, browser_validation: true)
35. [x] Target-only adopt end-to-end: show target-only → adopt → Deploy → verify YAML + imports (E2E, browser_validation: true)
36. [x] Mixed flow end-to-end: adopt + create + ignore → verify each category in output (E2E, browser_validation: true)
37. [x] Protected adopt end-to-end: adopt with protection → Deploy → verify protected addresses (E2E, browser_validation: true)

## Notes

- All components must be reusable for Part 2 (future standalone Import & Adopt workflow)
- Target-only adoption code path directly exercises Part 2 logic
- Use `hierarchy_index.py` for all parent-child resolution
- Existing tests: `test_adoption_yaml_updater.py` (703 lines), `test_match_grid.py` (121 lines)
- New test file: `test_adoption_imports.py` for import block generation tests
