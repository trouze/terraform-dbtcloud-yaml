"""Permanent UI action logging for debugging and tracking.

This module provides persistent logging of UI actions like button clicks,
navigation events, and state changes to help debug issues.

IMPORTANT: Debug instrumentation added to this codebase MUST NOT be removed.
See tasks/prd-web-ui-12-debug-logging-standards.md for full guidelines.

Log Rotation:
    Logs are rotated based on SIZE, not application restarts. This preserves
    debugging continuity across restarts. Configure via environment variables:
    - UI_LOG_MAX_SIZE_MB: Max file size before rotation (default: 5)
    - UI_LOG_BACKUP_COUNT: Number of backup files to keep (default: 3)
    - UI_LOG_RETENTION_DAYS: Days before entries are stale (default: 7)

Usage:
    from importer.web.utils.ui_logger import (
        log_action,
        log_navigation,
        log_state_change,
        log_generate_step,
        log_error,
        traced,
        cleanup_stale_logs,
    )

    # Log a button click
    log_action("protect_button", "clicked", {"resource_key": "bt_data_ops_db"})

    # Log navigation
    log_navigation("match", "deploy")

    # Log state change
    log_state_change("protected_resources", "add", {"key": "bt_data_ops_db"})

    # Trace function calls with decorator
    @traced
    def my_function(arg1, arg2):
        return result

    @traced(log_args=True, log_result=True)
    def complex_function(data: dict) -> list:
        return processed_data

    # Clean up old log entries (preserves errors and hypothesis markers)
    cleanup_stale_logs(days=7)  # Remove entries older than 7 days
    cleanup_stale_logs(before_date="2026-01-20")  # Remove before specific date
"""

import functools
import inspect
import json
import logging
import os
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

# Type variable for the traced decorator
T = TypeVar("T")

# Log file path - can be overridden by environment variable
_LOG_FILE: Optional[Path] = None

# Rotation and retention configuration (can be overridden via environment variables)
UI_LOG_MAX_SIZE_MB = int(os.environ.get("UI_LOG_MAX_SIZE_MB", "5"))
UI_LOG_BACKUP_COUNT = int(os.environ.get("UI_LOG_BACKUP_COUNT", "3"))
UI_LOG_RETENTION_DAYS = int(os.environ.get("UI_LOG_RETENTION_DAYS", "7"))


def _get_log_file() -> Path:
    """Get the log file path, creating it if necessary."""
    global _LOG_FILE
    if _LOG_FILE is None:
        # Use a fixed path in the workspace
        _LOG_FILE = Path("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/ui_actions.log")
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    return _LOG_FILE


def _rotate_if_needed() -> None:
    """Rotate the log file if it exceeds the maximum size.
    
    Rotation is size-based, not restart-based, to preserve debugging continuity.
    Creates backup files like ui_actions.log.1, ui_actions.log.2, etc.
    """
    try:
        log_file = _get_log_file()
        if not log_file.exists():
            return
        
        max_bytes = UI_LOG_MAX_SIZE_MB * 1024 * 1024
        current_size = log_file.stat().st_size
        
        if current_size < max_bytes:
            return
        
        # Rotate existing backups (shift .2 -> .3, .1 -> .2, etc.)
        for i in range(UI_LOG_BACKUP_COUNT - 1, 0, -1):
            old_backup = log_file.with_suffix(f".log.{i}")
            new_backup = log_file.with_suffix(f".log.{i + 1}")
            if old_backup.exists():
                if i + 1 > UI_LOG_BACKUP_COUNT:
                    old_backup.unlink()  # Delete oldest if exceeds count
                else:
                    old_backup.rename(new_backup)
        
        # Move current log to .1
        backup_path = log_file.with_suffix(".log.1")
        log_file.rename(backup_path)
        
        # Create fresh log file
        log_file.touch()
        logger.debug(f"Rotated UI log file (was {current_size / 1024 / 1024:.1f}MB)")
        
    except Exception as e:
        logger.warning(f"Failed to rotate UI log: {e}")


def _write_log_entry(entry: dict) -> None:
    """Write a log entry to the log file, rotating if necessary."""
    try:
        _rotate_if_needed()
        log_file = _get_log_file()
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write UI log: {e}")


def log_action(
    component: str,
    action: str,
    data: Optional[dict[str, Any]] = None,
    *,
    session_id: str = "default",
) -> None:
    """Log a UI action (button click, form submit, etc.).

    Args:
        component: Name of the UI component (e.g., "protect_button", "generate_btn")
        action: Type of action (e.g., "clicked", "submitted", "toggled")
        data: Additional context data
        session_id: Optional session identifier for grouping related actions
    """
    entry = {
        "type": "action",
        "component": component,
        "action": action,
        "data": data or {},
        "timestamp": datetime.now().isoformat(),
        "timestamp_ms": int(time.time() * 1000),
        "session_id": session_id,
    }
    _write_log_entry(entry)


def log_navigation(
    from_page: str,
    to_page: str,
    data: Optional[dict[str, Any]] = None,
    *,
    session_id: str = "default",
) -> None:
    """Log a page navigation event.

    Args:
        from_page: Page being navigated from
        to_page: Page being navigated to
        data: Additional context data
        session_id: Optional session identifier
    """
    entry = {
        "type": "navigation",
        "from_page": from_page,
        "to_page": to_page,
        "data": data or {},
        "timestamp": datetime.now().isoformat(),
        "timestamp_ms": int(time.time() * 1000),
        "session_id": session_id,
    }
    _write_log_entry(entry)


def log_state_change(
    state_key: str,
    operation: str,
    data: Optional[dict[str, Any]] = None,
    *,
    before: Any = None,
    after: Any = None,
    session_id: str = "default",
) -> None:
    """Log a state change event.

    Args:
        state_key: The state property being changed (e.g., "protected_resources")
        operation: Type of operation (e.g., "add", "remove", "update", "clear")
        data: Additional context data
        before: State value before the change (optional)
        after: State value after the change (optional)
        session_id: Optional session identifier
    """
    entry = {
        "type": "state_change",
        "state_key": state_key,
        "operation": operation,
        "data": data or {},
        "timestamp": datetime.now().isoformat(),
        "timestamp_ms": int(time.time() * 1000),
        "session_id": session_id,
    }
    if before is not None:
        # Convert sets to lists for JSON serialization
        entry["before"] = list(before) if isinstance(before, set) else before
    if after is not None:
        entry["after"] = list(after) if isinstance(after, set) else after
    _write_log_entry(entry)


def log_generate_step(
    step: str,
    data: Optional[dict[str, Any]] = None,
    *,
    session_id: str = "default",
) -> None:
    """Log a step during the Generate process.

    Args:
        step: Name of the generation step
        data: Additional context data
        session_id: Optional session identifier
    """
    entry = {
        "type": "generate_step",
        "step": step,
        "data": data or {},
        "timestamp": datetime.now().isoformat(),
        "timestamp_ms": int(time.time() * 1000),
        "session_id": session_id,
    }
    _write_log_entry(entry)


def log_error(
    context: str,
    error: str,
    data: Optional[dict[str, Any]] = None,
    *,
    session_id: str = "default",
) -> None:
    """Log an error event.

    Args:
        context: Where the error occurred
        error: Error message
        data: Additional context data
        session_id: Optional session identifier
    """
    entry = {
        "type": "error",
        "context": context,
        "error": error,
        "data": data or {},
        "timestamp": datetime.now().isoformat(),
        "timestamp_ms": int(time.time() * 1000),
        "session_id": session_id,
    }
    _write_log_entry(entry)


def clear_log() -> None:
    """Clear the UI action log file."""
    try:
        log_file = _get_log_file()
        if log_file.exists():
            log_file.write_text("")
    except Exception as e:
        logger.warning(f"Failed to clear UI log: {e}")


def cleanup_stale_logs(
    days: Optional[int] = None,
    before_date: Optional[str] = None,
    preserve_errors: bool = True,
    preserve_hypothesis: bool = True,
    min_entries: int = 1000,
) -> dict[str, int]:
    """Remove stale log entries based on retention policy.
    
    This function filters the log file to remove old entries while preserving
    important debugging information.
    
    Args:
        days: Remove entries older than N days (default: UI_LOG_RETENTION_DAYS)
        before_date: Remove entries before this date (ISO 8601 format, e.g., "2026-01-23")
        preserve_errors: Keep error entries regardless of age (default: True)
        preserve_hypothesis: Keep entries with hypothesis markers [HA], [HB], etc. (default: True)
        min_entries: Always keep at least this many recent entries (default: 1000)
    
    Returns:
        dict with counts: {"removed": N, "preserved": M, "errors_preserved": E}
    
    Usage:
        # Remove entries older than 7 days (default)
        cleanup_stale_logs()
        
        # Remove entries older than 14 days
        cleanup_stale_logs(days=14)
        
        # Remove entries before a specific date
        cleanup_stale_logs(before_date="2026-01-20")
    """
    if days is None and before_date is None:
        days = UI_LOG_RETENTION_DAYS
    
    try:
        log_file = _get_log_file()
        if not log_file.exists():
            return {"removed": 0, "preserved": 0, "errors_preserved": 0}
        
        # Calculate cutoff timestamp
        if before_date:
            cutoff = datetime.fromisoformat(before_date)
        else:
            cutoff = datetime.now() - timedelta(days=days)
        
        cutoff_ms = int(cutoff.timestamp() * 1000)
        
        # Read all entries
        entries = []
        with open(log_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        # Filter entries
        preserved = []
        removed_count = 0
        errors_preserved = 0
        
        for entry in entries:
            entry_ts = entry.get("timestamp_ms", 0)
            entry_type = entry.get("type", "")
            
            # Check if this is an error entry
            is_error = entry_type == "error" or entry.get("event") == "error"
            
            # Check for hypothesis markers in any string field
            has_hypothesis = False
            if preserve_hypothesis:
                for value in entry.values():
                    if isinstance(value, str) and any(f"[H{c}]" in value for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
                        has_hypothesis = True
                        break
            
            # Decide whether to keep
            if entry_ts >= cutoff_ms:
                # Not stale - keep it
                preserved.append(entry)
            elif preserve_errors and is_error:
                # Error entry - preserve
                preserved.append(entry)
                errors_preserved += 1
            elif has_hypothesis:
                # Hypothesis marker - preserve
                preserved.append(entry)
            else:
                removed_count += 1
        
        # Ensure minimum entries are kept (most recent)
        if len(preserved) < min_entries and len(entries) > 0:
            # Sort by timestamp and keep the most recent
            all_sorted = sorted(entries, key=lambda e: e.get("timestamp_ms", 0), reverse=True)
            preserved = all_sorted[:min_entries]
            removed_count = len(entries) - len(preserved)
        
        # Write back preserved entries (sorted by timestamp)
        preserved.sort(key=lambda e: e.get("timestamp_ms", 0))
        with open(log_file, "w") as f:
            for entry in preserved:
                f.write(json.dumps(entry) + "\n")
        
        result = {
            "removed": removed_count,
            "preserved": len(preserved),
            "errors_preserved": errors_preserved,
        }
        logger.info(f"Log cleanup complete: {result}")
        return result
        
    except Exception as e:
        logger.warning(f"Failed to cleanup stale logs: {e}")
        return {"removed": 0, "preserved": 0, "errors_preserved": 0, "error": str(e)}


def log_function_call(
    function_name: str,
    module_name: str,
    event: str,
    *,
    args: Optional[dict[str, Any]] = None,
    result: Any = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
    session_id: str = "default",
) -> None:
    """Log a function call event (entry, exit, or error).

    Args:
        function_name: Name of the function
        module_name: Module containing the function
        event: Type of event ("entry", "exit", "error")
        args: Function arguments (optional)
        result: Return value (optional, for exit events)
        error: Error message (optional, for error events)
        duration_ms: Execution time in milliseconds (optional)
        session_id: Optional session identifier
    """
    entry = {
        "type": "function_call",
        "function": function_name,
        "module": module_name,
        "event": event,
        "timestamp": datetime.now().isoformat(),
        "timestamp_ms": int(time.time() * 1000),
        "session_id": session_id,
    }
    if args is not None:
        # Safely serialize args, handling non-JSON-serializable types
        entry["args"] = _safe_serialize(args)
    if result is not None:
        entry["result"] = _safe_serialize(result)
    if error is not None:
        entry["error"] = error
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms
    _write_log_entry(entry)


def _safe_serialize(obj: Any) -> Any:
    """Safely serialize an object for JSON, handling common non-serializable types."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "__dict__"):
        # For objects, try to get a reasonable representation
        return f"<{type(obj).__name__}>"
    # Fallback to string representation
    try:
        return str(obj)
    except Exception:
        return f"<{type(obj).__name__}>"


def traced(
    _func: Optional[Callable[..., T]] = None,
    *,
    log_args: bool = True,
    log_result: bool = False,
    session_id: str = "default",
) -> Union[Callable[[Callable[..., T]], Callable[..., T]], Callable[..., T]]:
    """Decorator to trace function calls with automatic logging.

    This decorator logs function entry, exit, and any errors. It's designed
    for debugging complex operations and state mutations.

    IMPORTANT: Once this decorator is added to a function, it should NOT be removed.
    See tasks/prd-web-ui-12-debug-logging-standards.md for guidelines.

    Usage:
        @traced
        def simple_function(arg1, arg2):
            return result

        @traced(log_args=True, log_result=True)
        def complex_function(data: dict) -> list:
            return processed_data

        @traced(log_result=True)
        def get_data() -> dict:
            return {"key": "value"}

    Args:
        _func: The function to decorate (used when called without arguments)
        log_args: Whether to log function arguments (default: True)
        log_result: Whether to log the return value (default: False)
        session_id: Session identifier for log correlation

    Returns:
        Decorated function with automatic tracing
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            func_name = func.__name__
            module_name = func.__module__

            # Prepare arguments for logging
            logged_args: Optional[dict[str, Any]] = None
            if log_args:
                try:
                    # Get function signature to map positional args to names
                    sig = inspect.signature(func)
                    bound = sig.bind_partial(*args, **kwargs)
                    bound.apply_defaults()
                    logged_args = dict(bound.arguments)
                except Exception:
                    # Fallback if signature binding fails
                    logged_args = {"args": args, "kwargs": kwargs}

            # Log entry
            log_function_call(
                func_name,
                module_name,
                "entry",
                args=logged_args,
                session_id=session_id,
            )

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)

                # Log exit
                log_function_call(
                    func_name,
                    module_name,
                    "exit",
                    result=result if log_result else None,
                    duration_ms=duration_ms,
                    session_id=session_id,
                )
                return result

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                error_msg = f"{type(e).__name__}: {str(e)}"

                # Log error with traceback
                log_function_call(
                    func_name,
                    module_name,
                    "error",
                    error=error_msg,
                    duration_ms=duration_ms,
                    session_id=session_id,
                )

                # Also log to standard logger for visibility
                logger.error(f"[TRACED] {module_name}.{func_name} raised {error_msg}")
                raise

        return wrapper

    # Handle both @traced and @traced() syntax
    if _func is not None:
        return decorator(_func)
    return decorator


def traced_async(
    _func: Optional[Callable[..., T]] = None,
    *,
    log_args: bool = True,
    log_result: bool = False,
    session_id: str = "default",
) -> Union[Callable[[Callable[..., T]], Callable[..., T]], Callable[..., T]]:
    """Async version of the traced decorator for coroutines.

    Usage:
        @traced_async
        async def fetch_data(url: str) -> dict:
            return await client.get(url)

        @traced_async(log_result=True)
        async def process_items(items: list) -> list:
            return [await process(item) for item in items]
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            func_name = func.__name__
            module_name = func.__module__

            # Prepare arguments for logging
            logged_args: Optional[dict[str, Any]] = None
            if log_args:
                try:
                    sig = inspect.signature(func)
                    bound = sig.bind_partial(*args, **kwargs)
                    bound.apply_defaults()
                    logged_args = dict(bound.arguments)
                except Exception:
                    logged_args = {"args": args, "kwargs": kwargs}

            # Log entry
            log_function_call(
                func_name,
                module_name,
                "entry",
                args=logged_args,
                session_id=session_id,
            )

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)

                # Log exit
                log_function_call(
                    func_name,
                    module_name,
                    "exit",
                    result=result if log_result else None,
                    duration_ms=duration_ms,
                    session_id=session_id,
                )
                return result

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                error_msg = f"{type(e).__name__}: {str(e)}"

                log_function_call(
                    func_name,
                    module_name,
                    "error",
                    error=error_msg,
                    duration_ms=duration_ms,
                    session_id=session_id,
                )

                logger.error(f"[TRACED] {module_name}.{func_name} raised {error_msg}")
                raise

        return wrapper

    if _func is not None:
        return decorator(_func)
    return decorator
