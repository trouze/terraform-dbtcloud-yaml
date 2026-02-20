# Release Notes - v0.23.4

**Date:** 2026-02-20  
**Type:** Patch Release  
**Previous Version:** 0.23.3

## Summary

This patch improves UI responsiveness by removing a blocking startup account-verification call from route initialization. The change keeps explicit credential validation behavior intact while preventing intermittent first-navigation stalls.

## Key Fixes

### Startup Route Latency
- **Problem**: Initial navigation into fetch routes could intermittently stall for ~1.6 seconds even when websocket streaming was stable.
- **Root Cause**: `get_state()` startup refresh synchronously called account-name verification (`fetch_account_name`) for source and target credentials, introducing network-bound delay into page render paths.
- **Fix**:
  - Added `verify_account_name` parameter to `load_account_info_from_env(...)`.
  - Disabled account-name verification during startup-only refresh in `app.py::_refresh_account_info(...)`.
  - Preserved verification behavior for explicit credential/test operations.
- **Result**: Startup and first-route navigation are consistently responsive.

## Files Updated

- `importer/web/env_manager.py`
- `importer/web/app.py`
- `CHANGELOG.md`
- `importer/VERSION`
- `dev_support/importer_implementation_status.md`
- `dev_support/phase5_e2e_testing_guide.md`

## Verification

1. Open app and perform repeated navigation between `/fetch_source` and `/fetch_target`.
2. Confirm no first-load stall and no reconnect-loop behavior.
3. Confirm explicit credential validation still resolves account details when invoked from page actions.

