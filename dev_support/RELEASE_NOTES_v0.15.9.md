# Release Notes - v0.15.9

**Release Date:** 2026-01-30  
**Release Type:** Patch (Debug Logging Standards)  
**Previous Version:** 0.15.8

---

## Summary

This release establishes permanent debug instrumentation and logging standards for the dbt Cloud YAML Importer project. All debug instrumentation added during development must now be preserved and documented, ensuring future debugging capability and maintaining observability across the application.

---

## What's New

### Debug and Logging Standards PRD

Created comprehensive `tasks/prd-web-ui-12-debug-logging-standards.md` documenting:

- **Permanent Instrumentation Policy**: Debug logging must NOT be removed once added
- **Structured Logging**: All logs must be JSON-formatted via `ui_logger` utilities
- **Logging Categories**:
  - UI action logs (button clicks, form submissions)
  - Navigation logs (page transitions, dialog events)
  - State change logs (with before/after values)
  - Generation step logs (multi-step process tracking)
  - Error logs (with context)
  - Function call tracing (via `@traced` decorator)
- **Log File Locations**: `.cursor/ui_actions.log` and `.cursor/debug.log`
- **Log Entry Schema**: Standardized JSON format for all log types

### Debug Instrumentation Rule

Created `.cursor/rules/debug-instrumentation.mdc` enforcing:

- Preservation of all debug instrumentation
- Use of `ui_logger` utilities for structured logging
- Hypothesis markers (`[HA]`, `[HB]`, etc.) for debugging sessions
- Required logging for UI actions, state changes, and errors

### Function Call Tracing

Enhanced `importer/web/utils/ui_logger.py` with new tracing capabilities:

```python
from importer.web.utils.ui_logger import traced, traced_async

@traced
def my_function(arg1, arg2):
    """Automatically logs entry, exit, and errors."""
    return result

@traced(log_args=True, log_result=True)
def complex_function(data: dict) -> list:
    """Full argument and result logging."""
    return processed_data

@traced_async
async def fetch_data(url: str) -> dict:
    """Async version for coroutines."""
    return await client.get(url)
```

Features:
- Automatic function entry/exit logging
- Optional argument and return value logging
- Error tracking with duration measurement
- Safe serialization for non-JSON-serializable types (sets, Path objects, etc.)
- Both sync and async decorator versions

### Protection Manager Tracing

Added `@traced(log_result=True)` decorator to key protection management functions:

- `generate_moved_blocks_from_state()` - Compares YAML with Terraform state
- `detect_protection_mismatches()` - Identifies protection status drift
- `write_moved_blocks_file()` - Generates Terraform moved blocks

---

## Files Changed

### New Files
- `tasks/prd-web-ui-12-debug-logging-standards.md` - Debug and logging PRD
- `.cursor/rules/debug-instrumentation.mdc` - Project rule for instrumentation
- `dev_support/RELEASE_NOTES_v0.15.9.md` - This release notes file

### Modified Files
- `importer/web/utils/ui_logger.py` - Added `@traced` and `@traced_async` decorators
- `importer/web/utils/protection_manager.py` - Added tracing to key functions
- `importer/VERSION` - Updated to 0.15.9
- `CHANGELOG.md` - Added 0.15.9 section
- `dev_support/importer_implementation_status.md` - Updated version and changelog
- `dev_support/phase5_e2e_testing_guide.md` - Updated version reference

---

## Usage Examples

### Adding UI Action Logging

```python
from importer.web.utils.ui_logger import log_action

# Log button click
log_action("protect_button", "clicked", {"resource_key": "bt_data_ops_db"})

# Log form submission
log_action("credentials_form", "submitted", {"target_id": 123})
```

### Adding State Change Logging

```python
from importer.web.utils.ui_logger import log_state_change

before = set(state.map.protected_resources)
state.map.protected_resources.add(key)
log_state_change(
    "protected_resources",
    "add",
    {"key": key},
    before=before,
    after=state.map.protected_resources
)
```

### Adding Function Tracing

```python
from importer.web.utils.ui_logger import traced

@traced
def apply_protection(keys: list[str]) -> None:
    """This function's calls will be automatically logged."""
    for key in keys:
        state.map.protected_resources.add(key)
```

### Analyzing Logs

```bash
# View all logs
cat .cursor/ui_actions.log | jq .

# Filter by type
cat .cursor/ui_actions.log | jq 'select(.type == "action")'

# Find function call errors
cat .cursor/ui_actions.log | jq 'select(.type == "function_call" and .event == "error")'

# Timeline of actions
cat .cursor/ui_actions.log | jq -r '[.timestamp, .type, .component // .function] | @tsv'
```

---

## Migration Notes

No migration required. This release adds new capabilities without changing existing behavior.

### For Existing Code

When modifying code with existing instrumentation:
1. **Keep all existing log calls** - Even if they seem redundant
2. **Update context data** - Ensure data remains relevant
3. **Maintain hypothesis markers** - Keep `[HA]`, `[HB]` prefixes

### For New Features

When implementing new features:
1. Add `log_action()` calls for all button/form handlers
2. Add `log_state_change()` with before/after for state mutations
3. Use `@traced` decorator on complex business logic functions
4. Add `log_error()` in all exception handlers

---

## Testing

Verify instrumentation is working:

```bash
# Clear log
> .cursor/ui_actions.log

# Perform UI actions (protect a resource, generate, etc.)

# Check logs were created
cat .cursor/ui_actions.log | jq 'select(.type == "function_call")'
```

---

## Related Documentation

- **PRD**: `tasks/prd-web-ui-12-debug-logging-standards.md`
- **Rule**: `.cursor/rules/debug-instrumentation.mdc`
- **Implementation**: `importer/web/utils/ui_logger.py`

---

## Upgrade Path

```bash
# Pull latest changes
git pull

# Verify version
cat importer/VERSION
# Should show: 0.15.9

# Test tracing is working
python -c "from importer.web.utils.ui_logger import traced; print('OK')"
```
