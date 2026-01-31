# PRD: Debug and Logging Standards

**PRD ID:** prd-web-ui-12  
**Status:** Active  
**Created:** 2026-01-30  
**Last Updated:** 2026-01-30  
**Version:** 1.1.0

---

## Executive Summary

This PRD establishes permanent debug instrumentation and logging standards for the dbt Cloud YAML Importer project. All implemented debug instrumentation MUST be kept and documented, not removed. This ensures future debugging capability and maintains observability across the application.

---

## Goals

1. **Preserve Debugging Capability**: All debug instrumentation added during development MUST remain in the codebase
2. **Standardize Logging**: Establish consistent patterns for logging across UI, state changes, and function execution
3. **Enable Traceability**: Provide end-to-end tracing of user actions through the system
4. **Support Post-Mortem Analysis**: Log files must support debugging issues after they occur

---

## Non-Goals

- Real-time monitoring dashboards
- Log aggregation infrastructure
- Performance monitoring (APM)
- External log shipping

---

## Core Principles

### Principle 1: Never Remove Debug Instrumentation

Once debug logging is added to the codebase, it MUST NOT be removed. Reasons:

1. **Future Debugging**: The same issue may reoccur
2. **Related Issues**: Similar code paths may have related problems
3. **Regression Detection**: Logs help identify when fixes regress
4. **Knowledge Preservation**: Instrumentation documents developer intent

### Principle 2: Structured Logging

All logs MUST be structured (JSON format) to enable:

1. Parsing and searching
2. Correlation across requests
3. Automated analysis
4. Filtering by type/component

### Principle 3: Contextual Information

Every log entry MUST include:

1. **Timestamp**: ISO 8601 format with milliseconds
2. **Type**: Category of log entry (action, navigation, state_change, error, function_call)
3. **Component/Function**: Source of the log
4. **Session ID**: For correlating related entries

---

## Logging Categories

### 1. UI Action Logs

Log all user interactions:

```python
from importer.web.utils.ui_logger import log_action

# Button clicks
log_action("protect_button", "clicked", {"resource_key": "bt_data_ops_db"})

# Form submissions
log_action("credentials_form", "submitted", {"target_id": 123})

# Toggle interactions
log_action("protection_checkbox", "toggled", {"resource": "PRJ:bt_data_ops_db", "value": True})
```

**Required for:**
- All button clicks
- Form submissions
- Checkbox/toggle changes
- Dropdown selections
- Grid cell edits

### 2. Navigation Logs

Log all page transitions:

```python
from importer.web.utils.ui_logger import log_navigation

log_navigation("match", "deploy", {"protected_count": 5})
```

**Required for:**
- Step navigation (wizard steps)
- Tab switches
- Dialog open/close
- Page reloads

### 3. State Change Logs

Log all application state mutations:

```python
from importer.web.utils.ui_logger import log_state_change

log_state_change(
    "protected_resources",
    "add",
    {"keys": ["PRJ:bt_data_ops_db"]},
    before=set(),
    after={"PRJ:bt_data_ops_db"}
)
```

**Required for:**
- Protected resources changes
- Mapping confirmations
- Configuration updates
- Any `state.*` mutations

### 4. Generation Step Logs

Log each step of multi-step processes:

```python
from importer.web.utils.ui_logger import log_generate_step

log_generate_step("yaml_protection_applied", {
    "protected_count": 4,
    "unprotected_count": 0,
    "yaml_file": str(yaml_path)
})

log_generate_step("moved_blocks_generated", {
    "count": 3,
    "file": "protection_moves.tf"
})
```

**Required for:**
- Generate workflow steps
- Import block generation
- Terraform file creation
- YAML modifications

### 5. Error Logs

Log all errors with context:

```python
from importer.web.utils.ui_logger import log_error

log_error(
    "generate_terraform",
    str(exception),
    {"yaml_file": str(yaml_path), "step": "protection_changes"}
)
```

**Required for:**
- All caught exceptions
- Validation failures
- API errors
- State inconsistencies

### 6. Function Call Tracing

Use the `@traced` decorator for complex functions:

```python
from importer.web.utils.ui_logger import traced

@traced
def apply_protection(keys_to_protect: list[str]) -> None:
    """Apply protection to multiple resources."""
    # Function body...
    pass

@traced(log_args=True, log_result=True)
def detect_protection_changes(current_yaml: dict, previous_yaml: dict) -> list[dict]:
    """Detect changes in protection status."""
    # Function body...
    return changes
```

**Required for:**
- Protection/unprotection functions
- State mutation functions
- Complex business logic
- Multi-step operations

---

## Log File Locations

### UI Action Log

**Path:** `.cursor/ui_actions.log`  
**Format:** JSON Lines (one JSON object per line)  

### Standard Python Logging

**Path:** `.cursor/debug.log`  
**Format:** Standard logging format  
**Configuration:** Set via logging config

---

## Log Rotation and Retention

### Rotation Policy

Logs are rotated based on **file size**, not application restarts. This preserves continuity across restarts while preventing unbounded growth.

#### Size-Based Rotation

| Log File | Max Size | Backup Count |
|----------|----------|--------------|
| `ui_actions.log` | 5 MB | 3 |
| `debug.log` | 10 MB | 5 |

**Rotation behavior:**
- When a log file exceeds its max size, it is renamed with a numeric suffix
- Example: `ui_actions.log` → `ui_actions.log.1` → `ui_actions.log.2` → `ui_actions.log.3`
- When backup count is exceeded, oldest backup is deleted
- Active log file is always the one without a suffix

#### Implementation

```python
import logging
from logging.handlers import RotatingFileHandler

# UI Actions Log (5MB, 3 backups)
ui_handler = RotatingFileHandler(
    ".cursor/ui_actions.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8"
)

# Debug Log (10MB, 5 backups)
debug_handler = RotatingFileHandler(
    ".cursor/debug.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding="utf-8"
)
```

### Retention Policy

Logs have different staleness thresholds based on their utility for debugging.

#### Staleness Rules

| Log Type | Stale After | Rationale |
|----------|-------------|-----------|
| UI action logs | 7 days | User actions lose context after a week |
| Debug logs | 14 days | May need longer history for regression analysis |
| Error logs | 30 days | Errors may take time to reproduce/investigate |

#### Auto-Cleanup (Optional)

The `ui_logger` provides optional cleanup utilities:

```python
from importer.web.utils.ui_logger import cleanup_stale_logs

# Remove log entries older than retention period
cleanup_stale_logs(days=7)  # Default: 7 days for UI logs

# Remove all logs older than a specific date
cleanup_stale_logs(before_date="2026-01-23")
```

**When to run cleanup:**
- NOT automatically on every startup (preserves debugging context)
- Manually when disk space is a concern
- Before starting a fresh test session (if desired)
- Via a scheduled maintenance script (if deployed)

#### What NOT to Purge

Even during cleanup, preserve:
- **Error entries**: May be needed for post-mortem
- **Last 1000 entries**: Minimum recent history regardless of age
- **Entries with hypothesis markers**: `[HA]`, `[HB]`, etc. indicate active debugging

### Manual Log Management

```bash
# Check log sizes
ls -lh .cursor/*.log*

# View log file count and total size
du -sh .cursor/

# Archive old logs before cleanup (optional)
tar -czf logs_backup_$(date +%Y%m%d).tar.gz .cursor/*.log*

# Clear all logs (start fresh - use sparingly)
rm .cursor/*.log*
```

### Configuration

Rotation and retention can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `UI_LOG_MAX_SIZE_MB` | 5 | Max size before rotation (MB) |
| `UI_LOG_BACKUP_COUNT` | 3 | Number of backup files to keep |
| `UI_LOG_RETENTION_DAYS` | 7 | Days before entries are considered stale |
| `DEBUG_LOG_MAX_SIZE_MB` | 10 | Max debug log size (MB) |
| `DEBUG_LOG_BACKUP_COUNT` | 5 | Debug log backup count |

---

## Implementation Patterns

### Pattern 1: Function Entry/Exit Tracing

```python
from importer.web.utils.ui_logger import traced

@traced
def my_function(arg1: str, arg2: int) -> dict:
    """Function with automatic tracing."""
    result = do_work(arg1, arg2)
    return result
```

This automatically logs:
- Function entry with arguments
- Function exit with return value
- Execution duration
- Any exceptions raised

### Pattern 2: State Change with Before/After

```python
from importer.web.utils.ui_logger import log_state_change

def apply_protection(keys: list[str]) -> None:
    before = set(state.map.protected_resources) if state.map.protected_resources else set()
    
    for key in keys:
        state.map.protected_resources.add(key)
    
    log_state_change(
        "protected_resources",
        "add",
        {"keys": keys},
        before=before,
        after=state.map.protected_resources
    )
```

### Pattern 3: Hypothesis Instrumentation

When debugging complex issues, add hypothesis markers:

```python
import logging
logger = logging.getLogger(__name__)

# Hypothesis A: Check if YAML is loaded correctly
logger.debug(f"[HA] YAML loaded: {len(yaml_config.get('projects', []))} projects")

# Hypothesis B: Check protection status
logger.debug(f"[HB] Protection status: {yaml_config.get('protected', False)}")
```

**Naming Convention:**
- Use `[H<letter>]` prefix for hypothesis markers
- Document the hypothesis being tested
- Keep markers even after issue is resolved

---

## Log Entry Schema

### Base Fields (All Entries)

```json
{
  "type": "action|navigation|state_change|generate_step|error|function_call",
  "timestamp": "2026-01-30T14:55:09.123456",
  "timestamp_ms": 1706633709123,
  "session_id": "default"
}
```

### Action Entry

```json
{
  "type": "action",
  "component": "protect_button",
  "action": "clicked",
  "data": {"resource_key": "bt_data_ops_db"}
}
```

### Navigation Entry

```json
{
  "type": "navigation",
  "from_page": "match",
  "to_page": "deploy",
  "data": {}
}
```

### State Change Entry

```json
{
  "type": "state_change",
  "state_key": "protected_resources",
  "operation": "add",
  "data": {"keys": ["PRJ:bt_data_ops_db"]},
  "before": [],
  "after": ["PRJ:bt_data_ops_db"]
}
```

### Function Call Entry

```json
{
  "type": "function_call",
  "function": "apply_protection",
  "module": "importer.web.pages.match",
  "event": "entry|exit|error",
  "args": {"keys_to_protect": ["PRJ:bt_data_ops_db"]},
  "result": null,
  "duration_ms": 45,
  "error": null
}
```

---

## Debug Instrumentation Checklist

When adding new features, ensure the following are instrumented:

### UI Components

- [ ] Button click handlers
- [ ] Form submission handlers
- [ ] Grid cell change handlers
- [ ] Dialog open/close handlers
- [ ] Navigation handlers

### State Management

- [ ] State property setters
- [ ] Collection modifications (add/remove)
- [ ] State persistence (save/load)

### Business Logic

- [ ] Protection changes
- [ ] Mapping operations
- [ ] YAML modifications
- [ ] Terraform generation
- [ ] Import block generation

### Error Handling

- [ ] Try/except blocks with logging
- [ ] Validation failures
- [ ] API errors

---

## Testing Debug Instrumentation

### Verify Log Output

After implementing instrumentation, verify logs are generated:

```bash
# Clear existing logs
> .cursor/ui_actions.log

# Perform actions in UI

# Check log content
cat .cursor/ui_actions.log | jq .

# Filter by type
cat .cursor/ui_actions.log | jq 'select(.type == "action")'

# Filter by component
cat .cursor/ui_actions.log | jq 'select(.component == "protect_button")'
```

### Verify Function Tracing

```bash
# Check function call logs
cat .cursor/ui_actions.log | jq 'select(.type == "function_call")'

# Check for errors
cat .cursor/ui_actions.log | jq 'select(.type == "function_call" and .event == "error")'
```

---

## Migration Guidelines

### Adding Instrumentation to Existing Code

1. **Identify entry points**: Button handlers, form handlers, navigation
2. **Add UI action logs**: `log_action()` calls
3. **Add state change logs**: `log_state_change()` with before/after
4. **Add function tracing**: `@traced` decorator on key functions
5. **Test**: Verify logs are generated correctly

### Preserving Existing Instrumentation

When refactoring code with existing instrumentation:

1. **Keep all log calls**: Even if they seem redundant
2. **Update context data**: Ensure data is still relevant
3. **Maintain markers**: Keep hypothesis markers (`[HA]`, `[HB]`, etc.)
4. **Document changes**: Note any changes in log format

---

## Appendix A: Complete ui_logger API

```python
# UI Actions
log_action(component: str, action: str, data: dict = None, *, session_id: str = "default")

# Navigation
log_navigation(from_page: str, to_page: str, data: dict = None, *, session_id: str = "default")

# State Changes
log_state_change(state_key: str, operation: str, data: dict = None, *, before: Any = None, after: Any = None, session_id: str = "default")

# Generate Steps
log_generate_step(step: str, data: dict = None, *, session_id: str = "default")

# Errors
log_error(context: str, error: str, data: dict = None, *, session_id: str = "default")

# Function Tracing Decorator
@traced(log_args: bool = True, log_result: bool = False, session_id: str = "default")

# Utility
clear_log()  # Clear the UI action log file

# Rotation and Retention
cleanup_stale_logs(days: int = 7)  # Remove entries older than N days
cleanup_stale_logs(before_date: str)  # Remove entries before date (ISO 8601)
```

---

## Appendix B: Related Documents

- `.cursor/rules/debug-instrumentation.mdc` - Project rule enforcing these standards
- `importer/web/utils/ui_logger.py` - Implementation of logging utilities
- `.cursor/ui_actions.log` - UI action log file
- `.cursor/debug.log` - Standard Python debug log

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2026-01-30 | Added log rotation (size-based) and retention policies |
| 1.0.0 | 2026-01-30 | Initial version with comprehensive logging standards |
