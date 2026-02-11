# Release Notes - v0.18.0

**Release Date:** 2026-02-09  
**Release Type:** Minor (Target Intent as Authoritative State File + Protection as Disposition Property)  
**Previous Version:** 0.17.0

---

## Summary

This release promotes `target-intent.json` to be the single, self-contained authoritative state file for deployment. It now contains dispositions, `output_config` (the merged YAML dict), match mappings, and per-resource protection decisions. The Match page computes the full intent once; the Deploy page loads and re-validates it rather than recomputing from scratch. Protection is unified as a property of each resource disposition with a 4-level priority chain, eliminating the disconnect between protection decisions and YAML generation.

---

## Key Changes

### Target Intent as Authoritative State File

Previously, target intent was fragmented:
- Match page saved only `match_mappings` to `target-intent.json`
- Deploy page recomputed `compute_target_intent()` from scratch with insufficient inputs (source focus had only selected projects, baseline was often empty)
- This caused Terraform to plan ~300 destroys for retained projects missing from the generated YAML

Now:
- **Match page** computes the full intent (dispositions + output_config + protection) and persists everything in `target-intent.json`
- **Deploy page** loads the persisted intent, re-validates against current TF state, and uses `output_config` directly
- `normalize_target_fetch()` lazily normalizes target fetch data into a baseline YAML so retained projects have config
- Falls back to recompute for backward compatibility when no persisted `output_config` exists

### Protection as a Disposition Property

Previously, protection lived in a separate `protection-intent.json` file disconnected from resource dispositions.

Now:
- Each `ResourceDisposition` has `protected`, `protection_set_by`, and `protection_set_at` fields
- Protection is resolved via a **4-level priority chain**:
  1. **Default**: `protected: false` (every resource starts unprotected)
  2. **TF state override**: resources in `dbtcloud_project.protected_projects` -> `protected: true`
  3. **Protection intent file**: `protection-intent.json` entry overrides TF state default
  4. **User edit**: `protection_set_by == "user"` in previous target intent has highest priority
- Deploy reads protection directly from dispositions instead of syncing from `ProtectionIntentManager` separately

### Write-Through Protection Sync

- When users toggle protection in the UI, the write order is strict:
  1. `ProtectionIntentManager.set_intent()` writes to `protection-intent.json`
  2. Callback syncs to the matching `ResourceDisposition.protected` in `target-intent.json`
- This ensures both files stay in sync automatically

---

## Files Changed

| File | Change |
|------|--------|
| `importer/web/utils/target_intent.py` | Added protection fields to `ResourceDisposition`, protection priority chain in `compute_target_intent()`, `get_tf_state_protected_project_keys()`, `normalize_target_fetch()`, `sync_protection_to_disposition()` on manager, `output_config` persistence |
| `importer/web/state.py` | Added `target_baseline_yaml` to `TargetFetchState`, `sync_protection_to_target_intent()` on `AppState`, wired protection callback |
| `importer/web/pages/match.py` | Rebuilt `_persist_target_intent_from_match()` to compute full intent |
| `importer/web/pages/deploy.py` | Deploy uses persisted intent, builds protection from dispositions |
| `importer/web/utils/protection_intent.py` | Added dirty-key tracking and `_on_intent_changed` callback in `save()` |
| `importer/web/tests/test_target_intent.py` | 17 new tests for protection + output_config + retained config + sync |

---

## Test Coverage

- **48 tests** in `test_target_intent.py` (17 new)
- **389 total tests** pass across all web test files
- New test classes:
  - `TestProtectionDefaults` (6 tests): default false, TF state override, intent override, user edit override
  - `TestResourceDispositionProtection` (2 tests): serialization round-trip, defaults when missing
  - `TestOutputConfigRoundTrip` (3 tests): save/load preserves output_config and protection
  - `TestRetainedProjectConfig` (2 tests): retained projects get config from baseline
  - `TestSyncProtectionToDisposition` (4 tests): sync updates, prefixed keys, missing key, no intent

---

## Migration Notes

- Existing `target-intent.json` files without `output_config` are handled gracefully (Deploy falls back to recompute)
- Existing `protection-intent.json` files continue to work as Level 3 in the priority chain
- No breaking changes to the UI workflow
