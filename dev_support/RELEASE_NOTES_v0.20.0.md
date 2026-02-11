# Release Notes - v0.20.0

**Release Date:** 2026-02-11  
**Release Type:** Minor (Global Resources Configuration + Protection Intent Key Fix)  
**Previous Version:** 0.19.0

---

## Summary

This release adds a Global Resources configuration card on the Configure page, allowing users to opt-in/out of account-level resource sections (groups, service tokens, notifications, webhooks, PrivateLink endpoints) with TF state safety-net detection. It also fixes a critical bug where protection intents for sub-project resources (environments, jobs, extended attributes) used inconsistent keys, causing duplicate entries and false clarification panel prompts.

---

## Key Changes

### Global Resources Configuration

The Configure page now includes a **Global Resources** card that lets users control which account-level resource sections are included in the generated Terraform configuration:

- **Toggle controls** for groups, service tokens, notifications, webhooks, and PrivateLink endpoints
- **TF state safety net**: Automatically detects global sections already managed in Terraform state and warns before excluding them, preventing accidental resource destruction
- `get_tf_state_global_sections()` scans `terraform.tfstate` for managed global resource types
- `build_included_globals()` constructs the included set from user preferences and safety-net detection

### Target Intent Summary Card

The Configure page now shows a **Target Intent** status card with:
- File saved/unsaved status with path
- Disposition counts (match, create_new, skip, unadopt)
- Link back to Set Target Intent page when not saved

### Protection Intent Key Normalization

Sub-project resources (ENV, JOB, EXTATTR) now consistently use the TF state key (e.g., `ENV:sse_dm_fin_fido_dev`) instead of the grid `source_key` (e.g., `ENV:dev`). This affected four code paths:
- `on_row_change` protect handler
- `on_row_change` unprotect handler
- `apply_protection` bulk handler
- `remove_protection` bulk handler

New helpers:
- `_get_intent_key_for_row()` extracts the canonical key from TF state address
- `_get_intent_key_for_source_key()` resolves source_key to intent key via grid lookup
- `_find_source_key_for_intent_key()` reverse-maps intent key back to source_key

### Undo/Clear Intent Fixes

The Undo and Clear All Pending handlers now properly revert `protected_resources` state when removing intents, preventing phantom "Needs Clarification" entries after undoing a protect/unprotect action.

### Protection Intent `needs_tf_move` Property

New computed property on `ProtectionIntent` determines if a TF state move is actually required, excluding no-op cases:
- Intents derived from TF state (`sync_from_tf_state`)
- Intents where TF state already matched at decision time

Auto-marks these no-op intents as `applied_to_tf_state=True` during file load cleanup.

### UI Improvements

- **Synced intents panel**: Protected intents shown first; unprotected intents collapsed in a nested "below the fold" expansion

---

## Files Changed

| File | Changes |
|------|---------|
| `importer/web/pages/match.py` | Protection key normalization, undo handler fix, synced panel ordering, debug cleanup |
| `importer/web/pages/configure.py` | Global Resources card, Target Intent summary card |
| `importer/web/pages/deploy.py` | Minor intent loading updates |
| `importer/web/pages/utilities.py` | Minor updates |
| `importer/web/utils/protection_intent.py` | `needs_tf_move` property, auto-mark no-op cleanup |
| `importer/web/utils/target_intent.py` | `get_tf_state_global_sections()`, `build_included_globals()` |
| `importer/web/utils/terraform_state_reader.py` | `TF_TYPE_TO_GLOBAL_SECTION` mapping |
| `importer/web/tests/test_target_intent.py` | New unit tests for global section detection |

---

## Migration Notes

No breaking changes. The protection intent key normalization will correctly handle new intents going forward. Existing stale entries with old-format keys (e.g., `ENV:dev`) should be manually cleaned up if present.
