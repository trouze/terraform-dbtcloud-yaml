"""Terminal output component for displaying log messages and progress."""

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from nicegui import ui

from importer.web.utils.log_export import (
    messages_to_otlp_json,
    messages_to_log_text,
    generate_log_filename,
)

_WS_DEBUG_ENABLED = os.getenv("IMPORTER_WS_DEBUG", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

def _dbg_db419a(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    """Write one NDJSON debug record for websocket investigation."""
    if not _WS_DEBUG_ENABLED:
        return
    payload = {
        "sessionId": "db419a",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(
            "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-db419a.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


class LogLevel(Enum):
    """Log level for terminal messages."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class LogMessage:
    """A single log message."""
    text: str
    level: LogLevel = LogLevel.INFO
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().astimezone()  # Timezone-aware local time


class TerminalOutput:
    """Terminal-style output component for streaming logs."""

    # Log level priority (lower = more verbose)
    LEVEL_PRIORITY = {
        LogLevel.DEBUG: 0,
        LogLevel.INFO: 1,
        LogLevel.SUCCESS: 2,
        LogLevel.WARNING: 3,
        LogLevel.ERROR: 4,
    }

    def __init__(
        self,
        max_lines: int = 500,
        auto_scroll: bool = True,
        show_timestamps: bool = True,
        default_level: LogLevel = LogLevel.INFO,
        flush_interval_seconds: float = 0.12,
        max_flush_batch: int = 25,
        max_pending_messages: int = 2000,
        max_line_length: int = 4000,
        stale_client_seconds: float = 30.0,
        idle_shutdown_seconds: float = 10.0,
    ):
        """Initialize terminal output component.

        Args:
            max_lines: Maximum number of lines to keep in buffer
            auto_scroll: Whether to auto-scroll to bottom on new messages
            show_timestamps: Whether to show timestamps for each message
            default_level: Default minimum log level to display
        """
        self.max_lines = max_lines
        self.auto_scroll = auto_scroll
        self.show_timestamps = show_timestamps
        self.messages: list[LogMessage] = []
        self._min_level = default_level
        self._container: Optional[ui.column] = None
        self._scroll_area: Optional[ui.scroll_area] = None
        self._ui_detached = False
        self._detach_notice_added = False
        self._trim_since_rerender = 0
        self._trim_rerender_threshold = 100
        self._needs_rerender = False
        self._pending_messages: list[LogMessage] = []
        self._flush_interval_seconds = flush_interval_seconds
        self._max_flush_batch = max_flush_batch
        self._max_pending_messages = max_pending_messages
        self._max_line_length = max_line_length
        self._stale_client_seconds = stale_client_seconds
        self._idle_shutdown_seconds = idle_shutdown_seconds
        self._flush_timer: Optional[Any] = None
        self._flush_timer_active = False
        self._dropped_pending_messages = 0
        self._last_ui_success_at = time.monotonic()
        self._last_activity_at = time.monotonic()
        self._dbg_last_pending_bucket = -1
        self._dbg_trim_counter = 0

    def create(self, height: str = "300px", title: str = "Output") -> None:
        """Create the terminal output UI component.

        Args:
            height: CSS height for the terminal container
            title: Title to display in the header
        """
        # Search state
        self._search_term = ""
        self._search_count = 0
        self._search_current = 0
        self._current_title = title
        
        with ui.card().classes("w-full").style(
            f"background-color: #1a1a2e; min-height: {height}; max-height: {height};"
        ):
            # Header with title and controls
            with ui.row().classes("w-full items-center justify-between px-3 py-2 border-b border-slate-700"):
                self._title_label = ui.label(title).classes("text-sm font-mono text-slate-400")
                
                with ui.row().classes("gap-3 items-center"):
                    # Search input (wider for better usability)
                    self._search_input = ui.input(
                        placeholder="Search logs...",
                    ).props("dense borderless dark").classes("text-slate-300").style(
                        "width: 320px; background-color: #2d2d4a; border-radius: 4px; padding: 4px 8px;"
                    )
                    self._search_input.on("update:model-value", self._on_search_change)
                    
                    # Search count and navigation
                    self._search_count_label = ui.label("").classes("text-xs text-slate-500 min-w-[60px]")
                    
                    self._search_prev_btn = ui.button(
                        icon="keyboard_arrow_up",
                        on_click=lambda: self._go_to_search_match("prev"),
                    ).props("flat dense size=sm").classes("text-slate-400 hidden")
                    
                    self._search_next_btn = ui.button(
                        icon="keyboard_arrow_down",
                        on_click=lambda: self._go_to_search_match("next"),
                    ).props("flat dense size=sm").classes("text-slate-400 hidden")
                    
                    # Separator
                    ui.element("div").classes("w-px h-5 bg-slate-600")
                    
                    # Log level selector with label
                    ui.label("Log Level:").classes("text-xs text-slate-500")
                    self._level_select = ui.select(
                        options={
                            "error": "ERROR only",
                            "warning": "WARN+",
                            "success": "SUCCESS+",
                            "info": "INFO+",
                            "debug": "DEBUG (all)",
                        },
                        value=self._min_level.value,
                        on_change=self._on_level_change,
                    ).props("dense borderless options-dense").classes("text-slate-300").style(
                        "min-width: 120px; background-color: #2d2d4a; border-radius: 4px;"
                    ).tooltip("Filter messages by minimum severity level")
                    
                    # Separator
                    ui.element("div").classes("w-px h-5 bg-slate-600")
                    
                    # Download logs button with menu
                    with ui.button(icon="download").props("flat dense size=sm").classes("text-slate-400") as download_btn:
                        download_btn.tooltip("Download logs")
                        with ui.menu():
                            ui.menu_item(
                                "Download as .log (human-readable)",
                                on_click=lambda: self._download_logs("log"),
                            )
                            ui.menu_item(
                                "Download as .json (OTLP format)",
                                on_click=lambda: self._download_logs("json"),
                            )
                    
                    ui.button(
                        icon="content_copy",
                        on_click=self._copy_to_clipboard,
                    ).props("flat dense size=sm").classes("text-slate-400").tooltip("Copy to clipboard")
                    
                    ui.button(
                        icon="delete_sweep",
                        on_click=self.clear,
                    ).props("flat dense size=sm").classes("text-slate-400").tooltip("Clear output")

            # Scroll area for log messages
            with ui.scroll_area().classes("w-full flex-grow terminal-scroll-area").style(
                f"height: calc({height} - 50px);"
            ) as scroll:
                self._scroll_area = scroll
                self._container = ui.column().classes("w-full p-2 gap-0.5 terminal-messages")

        # Keep websocket traffic bounded by flushing queued messages in batches.
        if self._flush_timer is None:
            self._flush_timer = ui.timer(
                self._flush_interval_seconds,
                self._flush_pending_messages,
            )
            self._set_flush_timer_active(False)
            # region agent log
            _dbg_db419a(
                "H1",
                "terminal_output.py:create",
                "terminal flush timer initialized",
                {
                    "flush_interval_seconds": self._flush_interval_seconds,
                    "max_flush_batch": self._max_flush_batch,
                    "max_lines": self.max_lines,
                    "max_messages_per_second": round(
                        self._max_flush_batch / self._flush_interval_seconds, 2
                    )
                    if self._flush_interval_seconds > 0
                    else None,
                    "optimization_target": "localhost",
                },
            )
            # endregion

    def _set_flush_timer_active(self, active: bool) -> None:
        """Best-effort timer activation toggle across NiceGUI versions."""
        self._flush_timer_active = active
        if self._flush_timer is None:
            return
        try:
            if hasattr(self._flush_timer, "active"):
                self._flush_timer.active = active
                return
            if active and hasattr(self._flush_timer, "activate"):
                self._flush_timer.activate()
                return
            if not active and hasattr(self._flush_timer, "deactivate"):
                self._flush_timer.deactivate()
                return
        except Exception:
            return

    def _normalize_message_text(self, text: str) -> str:
        """Sanitize and bound payload size before websocket/UI emission."""
        clean = text.replace("\x00", "").replace("\r", "")
        if len(clean) <= self._max_line_length:
            return clean
        omitted = len(clean) - self._max_line_length
        return f"{clean[: self._max_line_length]} ... [truncated {omitted} chars]"

    def _on_level_change(self, e) -> None:
        """Handle log level filter change."""
        self._min_level = LogLevel(e.value)
        self._rerender_messages()

    def _rerender_messages(self) -> None:
        """Re-render all messages with current filter."""
        if self._container is None:
            return
        self._container.clear()
        for msg in self.messages:
            if self._should_display(msg.level):
                self._add_message_to_ui(msg)
        if self.auto_scroll and self._scroll_area is not None:
            self._scroll_area.scroll_to(percent=1.0)

    def _should_display(self, level: LogLevel) -> bool:
        """Check if a message should be displayed based on current filter."""
        return self.LEVEL_PRIORITY.get(level, 1) >= self.LEVEL_PRIORITY.get(self._min_level, 1)

    def log(self, text: str, level: LogLevel = LogLevel.INFO) -> None:
        """Add a log message.

        Args:
            text: Message text
            level: Log level for styling
        """
        msg = LogMessage(text=self._normalize_message_text(text), level=level)
        self.messages.append(msg)
        self._last_activity_at = time.monotonic()

        # Trim old messages
        trimmed = False
        if len(self.messages) > self.max_lines:
            self.messages = self.messages[-self.max_lines:]
            trimmed = True
            self._dbg_trim_counter += 1
            if self._dbg_trim_counter <= 3 or self._dbg_trim_counter % 25 == 0:
                # region agent log
                _dbg_db419a(
                    "H2",
                    "terminal_output.py:log",
                    "message buffer trimmed",
                    {
                        "buffer_len": len(self.messages),
                        "max_lines": self.max_lines,
                        "trim_since_rerender": self._trim_since_rerender,
                        "trim_count": self._dbg_trim_counter,
                    },
                )
                # endregion

        # Queue UI updates and flush in bounded batches to avoid websocket bursts.
        if self._container is not None and self._should_display(level) and not self._ui_detached:
            if len(self._pending_messages) >= self._max_pending_messages:
                self._pending_messages.pop(0)
                self._dropped_pending_messages += 1
            if trimmed:
                self._trim_since_rerender += 1
                if self._trim_since_rerender >= self._trim_rerender_threshold:
                    self._needs_rerender = True
                    self._trim_since_rerender = 0
                    # region agent log
                    _dbg_db419a(
                        "H2",
                        "terminal_output.py:log",
                        "rerender threshold reached after trims",
                        {
                            "trim_rerender_threshold": self._trim_rerender_threshold,
                            "pending_len": len(self._pending_messages),
                            "buffer_len": len(self.messages),
                        },
                    )
                    # endregion
            self._pending_messages.append(msg)
            if not self._flush_timer_active:
                self._set_flush_timer_active(True)
            pending_bucket = len(self._pending_messages) // 100
            if pending_bucket > self._dbg_last_pending_bucket:
                self._dbg_last_pending_bucket = pending_bucket
                if pending_bucket > 0:
                    # region agent log
                    _dbg_db419a(
                        "H3",
                        "terminal_output.py:log",
                        "pending queue reached new bucket",
                        {
                            "pending_len": len(self._pending_messages),
                            "bucket": pending_bucket,
                            "level": level.value,
                            "ui_detached": self._ui_detached,
                        },
                    )
                    # endregion

    def _mark_ui_detached(self, error: RuntimeError) -> None:
        """Disable UI writes after client/slot invalidation."""
        self._ui_detached = True
        self._pending_messages.clear()
        self._set_flush_timer_active(False)
        if not self._detach_notice_added:
            self._detach_notice_added = True
            self.messages.append(
                LogMessage(
                    text=(
                        "Terminal output detached; logging continues in memory for this run."
                    ),
                    level=LogLevel.WARNING,
                )
            )
            if len(self.messages) > self.max_lines:
                self.messages = self.messages[-self.max_lines:]

        # region agent log
        _dbg_db419a(
            "H4",
            "terminal_output.py:_mark_ui_detached",
            "terminal detached, disabling UI log writes",
            {"error": str(error)},
        )
        # endregion

    def _flush_pending_messages(self) -> None:
        """Flush queued messages to UI in bounded batches."""
        if self._ui_detached:
            self._pending_messages.clear()
            self._set_flush_timer_active(False)
            return
        if self._container is None:
            self._set_flush_timer_active(False)
            return
        if not self._pending_messages and not self._needs_rerender:
            if (time.monotonic() - self._last_activity_at) >= self._idle_shutdown_seconds:
                self._set_flush_timer_active(False)
            return

        try:
            if self._pending_messages and (
                time.monotonic() - self._last_ui_success_at
            ) >= self._stale_client_seconds:
                self._mark_ui_detached(RuntimeError("stale client while pending terminal output"))
                return

            if self._needs_rerender:
                # region agent log
                _dbg_db419a(
                    "H2",
                    "terminal_output.py:_flush_pending_messages",
                    "performing full rerender due to trim pressure",
                    {
                        "pending_before": len(self._pending_messages),
                        "buffer_len": len(self.messages),
                    },
                )
                # endregion
                self._rerender_messages()
                self._pending_messages.clear()
                self._needs_rerender = False
                self._last_ui_success_at = time.monotonic()
                return

            if self._dropped_pending_messages > 0:
                dropped_count = self._dropped_pending_messages
                self._dropped_pending_messages = 0
                dropped_msg = LogMessage(
                    text=(
                        f"Terminal stream throttled: dropped {dropped_count} buffered lines "
                        "to keep websocket responsive."
                    ),
                    level=LogLevel.WARNING,
                )
                self.messages.append(dropped_msg)
                if len(self.messages) > self.max_lines:
                    self.messages = self.messages[-self.max_lines:]
                self._add_message_to_ui(dropped_msg)

            batch = self._pending_messages[: self._max_flush_batch]
            del self._pending_messages[: self._max_flush_batch]
            if batch:
                # region agent log
                _dbg_db419a(
                    "H1",
                    "terminal_output.py:_flush_pending_messages",
                    "flushing queued terminal batch",
                    {
                        "batch_size": len(batch),
                        "pending_after": len(self._pending_messages),
                        "max_flush_batch": self._max_flush_batch,
                    },
                )
                # endregion
            for msg in batch:
                self._add_message_to_ui(msg)
            if batch and self.auto_scroll and self._scroll_area is not None:
                self._scroll_area.scroll_to(percent=1.0)
            if batch:
                self._last_ui_success_at = time.monotonic()
            if not self._pending_messages and not self._needs_rerender:
                self._set_flush_timer_active(False)
        except RuntimeError as e:
            if "client this element belongs to has been deleted" in str(e).lower():
                self._mark_ui_detached(e)
            else:
                # region agent log
                _dbg_db419a(
                    "H5",
                    "terminal_output.py:_flush_pending_messages",
                    "runtime error during flush",
                    {"error": str(e), "pending_len": len(self._pending_messages)},
                )
                # endregion
                raise

    def info(self, text: str) -> None:
        """Log an info message."""
        self.log(text, LogLevel.INFO)

    def info_auto(self, text: str) -> None:
        """Log a message with auto-detected level based on content.
        
        Detects 'Warning:' and 'Error:' prefixes and logs at appropriate level.
        """
        text_lower = text.lower()
        if "warning:" in text_lower:
            self.log(text, LogLevel.WARNING)
        elif "error:" in text_lower:
            self.log(text, LogLevel.ERROR)
        else:
            self.log(text, LogLevel.INFO)

    def warning(self, text: str) -> None:
        """Log a warning message."""
        self.log(text, LogLevel.WARNING)

    def error(self, text: str) -> None:
        """Log an error message."""
        self.log(text, LogLevel.ERROR)

    def success(self, text: str) -> None:
        """Log a success message."""
        self.log(text, LogLevel.SUCCESS)

    def debug(self, text: str) -> None:
        """Log a debug message."""
        self.log(text, LogLevel.DEBUG)

    def set_title(self, title: str) -> None:
        """Update the terminal output title.
        
        Args:
            title: New title to display (e.g., "Output - INIT")
        """
        self._current_title = title
        if hasattr(self, '_title_label') and self._title_label is not None:
            self._title_label.set_text(title)

    def clear(self) -> None:
        """Clear all messages."""
        self.messages.clear()
        self._pending_messages.clear()
        self._needs_rerender = False
        self._dropped_pending_messages = 0
        self._set_flush_timer_active(False)
        if self._container is not None:
            self._container.clear()

    def _add_message_to_ui(self, msg: LogMessage) -> None:
        """Add a message element to the UI container."""
        if self._container is None:
            return

        # Determine color and label based on level
        level_config = {
            LogLevel.DEBUG: {"color": "#6b7280", "label": "DEBUG", "bg": "#374151"},
            LogLevel.INFO: {"color": "#e5e7eb", "label": "INFO", "bg": "#1e3a5f"},
            LogLevel.WARNING: {"color": "#fbbf24", "label": "WARN", "bg": "#78350f"},
            LogLevel.ERROR: {"color": "#ef4444", "label": "ERROR", "bg": "#7f1d1d"},
            LogLevel.SUCCESS: {"color": "#22c55e", "label": "SUCCESS", "bg": "#14532d"},
        }
        config = level_config.get(msg.level, level_config[LogLevel.INFO])

        with self._container:
            with ui.row().classes("w-full gap-2 items-start"):
                if self.show_timestamps and msg.timestamp:
                    ui.label(
                        msg.timestamp.strftime("%Y-%m-%dT%H:%M:%S%z")
                    ).classes("text-xs font-mono text-slate-600 w-44 flex-shrink-0")
                
                # Log level badge
                ui.label(config["label"]).classes("text-xs font-mono px-1 rounded flex-shrink-0").style(
                    f"color: {config['color']}; background-color: {config['bg']};"
                )
                
                ui.label(msg.text).classes("text-sm font-mono break-all").style(f"color: {config['color']};")

    async def _copy_to_clipboard(self) -> None:
        """Copy filtered messages to clipboard (respects current filter)."""
        # Only copy messages that pass the current filter
        filtered_messages = [msg for msg in self.messages if self._should_display(msg.level)]
        
        if not filtered_messages:
            ui.notify("No output to copy", type="info")
            return

        # Level labels for text output
        level_labels = {
            LogLevel.DEBUG: "DEBUG",
            LogLevel.INFO: "INFO",
            LogLevel.WARNING: "WARN",
            LogLevel.ERROR: "ERROR",
            LogLevel.SUCCESS: "SUCCESS",
        }

        text_lines = []
        for msg in filtered_messages:
            level_str = level_labels.get(msg.level, "INFO")
            if self.show_timestamps and msg.timestamp:
                text_lines.append(f"[{msg.timestamp.strftime('%H:%M:%S')}] [{level_str}] {msg.text}")
            else:
                text_lines.append(f"[{level_str}] {msg.text}")

        text = "\n".join(text_lines)
        
        # Use JavaScript to copy to clipboard
        await ui.run_javascript(f'''
            navigator.clipboard.writeText({repr(text)}).then(() => {{
                // Success handled by notification below
            }}).catch(err => {{
                console.error('Failed to copy:', err);
            }});
        ''')
        ui.notify(f"Copied {len(filtered_messages)} messages to clipboard", type="positive")

    def get_text(self) -> str:
        """Get all messages as plain text."""
        level_labels = {
            LogLevel.DEBUG: "DEBUG",
            LogLevel.INFO: "INFO",
            LogLevel.SUCCESS: "SUCCESS",
            LogLevel.WARNING: "WARN",
            LogLevel.ERROR: "ERROR",
        }
        
        text_lines = []
        for msg in self.messages:
            level_str = level_labels.get(msg.level, "INFO")
            if self.show_timestamps and msg.timestamp:
                timestamp_str = msg.timestamp.strftime("%H:%M:%S")
                text_lines.append(f"[{timestamp_str}] [{level_str}] {msg.text}")
            else:
                text_lines.append(f"[{level_str}] {msg.text}")
        
        return "\n".join(text_lines)

    def _download_logs(self, format_type: str) -> None:
        """Download logs in the specified format.

        Args:
            format_type: Either "log" for human-readable or "json" for OTLP JSON
        """
        if not self.messages:
            ui.notify("No logs to download", type="info")
            return

        # Generate filename based on current title/context
        title_slug = self._current_title.lower().replace(" ", "-").replace("—", "-")
        title_slug = "".join(c for c in title_slug if c.isalnum() or c == "-")
        prefix = title_slug or "output"

        if format_type == "json":
            # OTLP JSON format
            content = messages_to_otlp_json(
                self.messages,
                operation_name=prefix,
            )
            filename = generate_log_filename(prefix, "json")
            ui.download(content.encode("utf-8"), filename)
            ui.notify(f"Downloaded {filename}", type="positive")
        else:
            # Human-readable .log format
            content = messages_to_log_text(self.messages, include_timestamps=self.show_timestamps)
            filename = generate_log_filename(prefix, "log")
            ui.download(content.encode("utf-8"), filename)
            ui.notify(f"Downloaded {filename}", type="positive")

    async def _on_search_change(self, e) -> None:
        """Handle search input change."""
        search_term = e.args if e.args else ""
        self._search_term = search_term
        
        if not search_term:
            self._search_count = 0
            self._search_current = 0
            self._search_count_label.set_text("")
            self._search_prev_btn.classes("hidden", remove=False)
            self._search_next_btn.classes("hidden", remove=False)
            # Clear highlights
            await ui.run_javascript('''
                document.querySelectorAll('.terminal-messages mark').forEach(m => {
                    m.outerHTML = m.textContent;
                });
            ''')
            return
        
        # Count matches in all displayed messages
        text = self.get_text()
        count = text.lower().count(search_term.lower())
        self._search_count = count
        self._search_current = 1 if count > 0 else 0
        
        if count > 1:
            self._search_count_label.set_text(f"1/{count}")
            self._search_prev_btn.classes(remove="hidden")
            self._search_next_btn.classes(remove="hidden")
        elif count == 1:
            self._search_count_label.set_text("1/1")
            self._search_prev_btn.classes("hidden", remove=False)
            self._search_next_btn.classes("hidden", remove=False)
        else:
            self._search_count_label.set_text("0")
            self._search_prev_btn.classes("hidden", remove=False)
            self._search_next_btn.classes("hidden", remove=False)
        
        # Highlight matches using JavaScript
        escaped_term = re.escape(search_term).replace("'", "\\'").replace('"', '\\"')
        await ui.run_javascript(f'''
            const container = document.querySelector('.terminal-messages');
            if (container) {{
                // Get all text nodes
                const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
                const textNodes = [];
                while (walker.nextNode()) textNodes.push(walker.currentNode);
                
                const regex = new RegExp('({escaped_term})', 'gi');
                textNodes.forEach(node => {{
                    if (regex.test(node.textContent)) {{
                        const span = document.createElement('span');
                        span.innerHTML = node.textContent.replace(regex, '<mark class="bg-yellow-500/50 text-yellow-200 px-0.5 rounded">$1</mark>');
                        node.parentNode.replaceChild(span, node);
                    }}
                }});
                
                // Scroll to first match
                const firstMark = document.querySelector('.terminal-messages mark');
                if (firstMark) {{
                    firstMark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    firstMark.classList.add('ring-2', 'ring-orange-500');
                }}
            }}
        ''')

    async def _go_to_search_match(self, direction: str) -> None:
        """Navigate to next/previous search match."""
        if self._search_count <= 1:
            return
        
        if direction == "next":
            self._search_current = self._search_current + 1 if self._search_current < self._search_count else 1
        else:
            self._search_current = self._search_current - 1 if self._search_current > 1 else self._search_count
        
        self._search_count_label.set_text(f"{self._search_current}/{self._search_count}")
        
        # Navigate to match using JavaScript
        await ui.run_javascript(f'''
            const marks = document.querySelectorAll('.terminal-messages mark');
            marks.forEach((m, i) => {{
                m.classList.remove('ring-2', 'ring-orange-500');
                if (i === {self._search_current - 1}) {{
                    m.classList.add('ring-2', 'ring-orange-500');
                    m.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }});
        ''')


class FetchProgressHandler:
    """Progress handler that streams fetch progress to a TerminalOutput component.
    
    Implements the FetchProgressCallback protocol from importer.fetcher.
    """

    def __init__(self, terminal: TerminalOutput):
        """Initialize progress handler.

        Args:
            terminal: TerminalOutput component to stream to
        """
        self.terminal = terminal
        self._current_phase = ""
        self._project_count = 0
        self._total_projects = 0

    def on_phase(self, phase: str) -> None:
        """Called when entering a major phase."""
        self._current_phase = phase
        self.terminal.info(f"━━━ {phase.upper()} ━━━")

    def on_resource_start(self, resource_type: str, total: Optional[int] = None) -> None:
        """Called when starting to fetch a resource type."""
        if total is not None:
            self.terminal.info(f"Fetching {resource_type} ({total} total)...")
        else:
            self.terminal.info(f"Fetching {resource_type}...")

    def on_resource_item(self, resource_type: str, key: str) -> None:
        """Called for each item fetched."""
        self.terminal.debug(f"  → {resource_type}: {key}")

    def on_resource_done(self, resource_type: str, count: int) -> None:
        """Called when finished fetching a resource type."""
        self.terminal.success(f"✓ {resource_type}: {count} items")

    def on_project_start(self, project_num: int, total: int, name: str) -> None:
        """Called when starting to fetch a project's resources."""
        self._project_count = project_num
        self._total_projects = total
        self.terminal.info(f"Project [{project_num}/{total}]: {name}")

    def on_project_done(self, project_num: int) -> None:
        """Called when finished fetching a project's resources."""
        pass  # Project completion is implicit from next project_start or phase end


class CombinedProgressHandler:
    """Progress handler that updates both terminal and progress tree.
    
    Implements the FetchProgressCallback protocol from importer.fetcher.
    """

    def __init__(self, terminal: TerminalOutput, progress_tree):
        """Initialize combined progress handler.

        Args:
            terminal: TerminalOutput component for log streaming
            progress_tree: ProgressTree component for structured hierarchy
        """
        self.terminal = terminal
        self.progress_tree = progress_tree
        self._current_phase = ""
        self._project_count = 0
        self._total_projects = 0

    def on_phase(self, phase: str) -> None:
        """Called when entering a major phase."""
        self._current_phase = phase
        self.terminal.info(f"━━━ {phase.upper()} ━━━")
        self.progress_tree.on_phase(phase)

    def on_resource_start(self, resource_type: str, total: Optional[int] = None) -> None:
        """Called when starting to fetch a resource type."""
        if total is not None:
            self.terminal.info(f"Fetching {resource_type} ({total} total)...")
        else:
            self.terminal.info(f"Fetching {resource_type}...")
        self.progress_tree.on_resource_start(resource_type, total)

    def on_resource_item(self, resource_type: str, key: str) -> None:
        """Called for each item fetched."""
        self.terminal.debug(f"  → {resource_type}: {key}")
        self.progress_tree.on_resource_item(resource_type, key)

    def on_resource_done(self, resource_type: str, count: int) -> None:
        """Called when finished fetching a resource type."""
        self.terminal.success(f"✓ {resource_type}: {count} items")
        self.progress_tree.on_resource_done(resource_type, count)

    def on_project_start(self, project_num: int, total: int, name: str) -> None:
        """Called when starting to fetch a project's resources."""
        self._project_count = project_num
        self._total_projects = total
        self.terminal.info(f"Project [{project_num}/{total}]: {name}")
        self.progress_tree.on_project_start(project_num, total, name)

    def on_project_done(self, project_num: int) -> None:
        """Called when finished fetching a project's resources."""
        self.progress_tree.on_project_done(project_num)
