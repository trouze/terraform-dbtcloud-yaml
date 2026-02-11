# Release Notes - v0.21.2

**Date:** 2026-02-11  
**Type:** Patch Release  
**Previous Version:** 0.21.1

## Summary

Fixes the deploy page's `terraform plan` failure when resources were moved to protected TF state blocks by the match page's protection apply but the YAML never had `protected: true` for those resources.

## Key Fixes

### Deploy Page State-Based Protection Detection
- **Problem**: After using the match page to protect/unprotect resources (which moves them in TF state via `moved` blocks), running plan from the deploy page would fail with "Instance cannot be destroyed" because the deploy generate only compared YAML-vs-YAML (finding no changes) and never checked YAML-vs-State for mismatches.
- **Fix**: Deploy page generate now **always** runs `generate_moved_blocks_from_state` as a safety net after the YAML-vs-YAML comparison, detecting and generating moved blocks for any resources where the TF state doesn't match the YAML.

### VAR Support in State-Based Detection
- Added `dbtcloud_environment_variable` to `generate_moved_blocks_from_state`'s `type_map` and YAML protection map builder, so environment variables in protected TF state blocks are properly detected and receive moved blocks.

### Stale Moved Blocks Cleanup
- When no protection changes are detected, any leftover `protection_moves.tf` from previous runs is removed to prevent stale moved blocks from causing errors.

## Files Changed

| File | Change |
|------|--------|
| `importer/web/pages/deploy.py` | Restructured protection detection to always run state-based check; added dedup; added stale moves cleanup |
| `importer/web/utils/protection_manager.py` | Added VAR to `generate_moved_blocks_from_state` type_map and YAML protection map |
| `importer/VERSION` | 0.21.1 → 0.21.2 |
| `CHANGELOG.md` | Added 0.21.2 section |
| `dev_support/importer_implementation_status.md` | Updated version and change log |
| `dev_support/phase5_e2e_testing_guide.md` | Updated version |

## Testing Verification

1. Protect resources on match page → TF apply moves them to protected blocks in state
2. Navigate to deploy page → Generate → Init → Plan
3. **Before fix**: Plan failed with "Instance cannot be destroyed" (protected resources being moved back without moved blocks)
4. **After fix**: Plan shows "3 to move, 0 to destroy" — all resources cleanly moved via generated moved blocks
