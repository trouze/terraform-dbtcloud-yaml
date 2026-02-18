# Release Notes - v0.23.2

**Date:** 2026-02-18  
**Type:** Patch Release  
**Previous Version:** 0.23.1

## Summary

This patch addresses a NiceGUI compatibility regression (`ui.html` sanitize signature drift) and improves UI responsiveness by reducing runtime log/render pressure and removing stale debug instrumentation from hot paths.

## Key Fixes

### NiceGUI HTML Compatibility
- **Problem**: Some runtime environments require `sanitize` as a keyword-only parameter for `ui.html`, while others reject/ignore it. This caused failures like:
  - `TypeError: __init__() missing 1 required keyword-only argument: 'sanitize'`
- **Fix**: Standardized compatibility usage across affected renderers:
  - `try: ui.html(content, sanitize=False)`
  - `except TypeError: ui.html(content)`
- **Result**: `/explore_target` ERD and HTML-heavy dialogs render reliably across local NiceGUI variants.

### UI Performance / Choppiness Reduction
- **Problem**: Large plan/init output and stale debug file writes were increasing websocket and disk I/O pressure.
- **Fixes**:
  - Bounded rendered Terraform output windows in Adopt/Deploy paths.
  - Bounded terminal rerender behavior when message buffers trim.
  - Removed stale debug file-write instrumentation from `utilities`, `destroy`, and `protection_manager`.
- **Result**: Improved page responsiveness and reduced UI choppiness under log-heavy flows.

### Guardrail Codification
- Added a persistent guardrail for NiceGUI `ui.html` sanitize compatibility in:
  - `.ralph/guardrails.md`
  - `docs/guides/intent-workflow-guardrails.md`

## Files Changed

| File | Change |
|------|--------|
| `importer/web/components/erd_viewer.py` | Added `ui.html` sanitize compatibility fallback |
| `importer/web/components/entity_table.py` | Added fallback for HTML detail renderers |
| `importer/web/pages/match.py` | Added fallback for stream log HTML renderers |
| `importer/web/components/terminal_output.py` | Kept bounded rerender optimization; removed temp perf logger |
| `importer/web/pages/adopt.py` | Bounded terminal output rendering for init/plan |
| `importer/web/pages/deploy.py` | Bounded terminal output rendering for plan stdout/stderr |
| `importer/web/pages/utilities.py` | Removed stale debug file-write path |
| `importer/web/pages/destroy.py` | Removed stale debug file-write path |
| `importer/web/utils/protection_manager.py` | Removed stale debug file-write path |
| `.ralph/guardrails.md` | Added sanitize compatibility sign |
| `docs/guides/intent-workflow-guardrails.md` | Added sanitize compatibility guardrail |
| `importer/VERSION` | 0.23.1 -> 0.23.2 |
| `CHANGELOG.md` | Added 0.23.2 section |
| `dev_support/importer_implementation_status.md` | Updated version metadata + change log |
| `dev_support/phase5_e2e_testing_guide.md` | Updated importer version |

## Verification

1. Restart web UI via `./restart_web.sh`.
2. Open `/explore_target` and click the **ERD** tab.
3. Confirm no `sanitize` TypeError appears in server logs.
4. Run quick route timing sweep and verify all workflow endpoints return `200`.
5. Execute focused tests:
   - `python3 -m pytest importer/web/tests/test_terminal_output_performance.py -q`
