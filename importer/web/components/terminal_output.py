"""Terminal output component for displaying log messages and progress."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from nicegui import ui


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
            self.timestamp = datetime.now()


class TerminalOutput:
    """Terminal-style output component for streaming logs."""

    def __init__(
        self,
        max_lines: int = 500,
        auto_scroll: bool = True,
        show_timestamps: bool = True,
    ):
        """Initialize terminal output component.

        Args:
            max_lines: Maximum number of lines to keep in buffer
            auto_scroll: Whether to auto-scroll to bottom on new messages
            show_timestamps: Whether to show timestamps for each message
        """
        self.max_lines = max_lines
        self.auto_scroll = auto_scroll
        self.show_timestamps = show_timestamps
        self.messages: list[LogMessage] = []
        self._container: Optional[ui.column] = None
        self._scroll_area: Optional[ui.scroll_area] = None

    def create(self, height: str = "300px") -> None:
        """Create the terminal output UI component.

        Args:
            height: CSS height for the terminal container
        """
        with ui.card().classes("w-full").style(
            f"background-color: #1a1a2e; min-height: {height}; max-height: {height};"
        ):
            # Header with title and controls
            with ui.row().classes("w-full items-center justify-between px-3 py-2 border-b border-slate-700"):
                ui.label("Output").classes("text-sm font-mono text-slate-400")
                
                with ui.row().classes("gap-2"):
                    ui.button(
                        icon="content_copy",
                        on_click=self._copy_to_clipboard,
                    ).props("flat dense size=sm").classes("text-slate-400").tooltip("Copy to clipboard")
                    
                    ui.button(
                        icon="delete_sweep",
                        on_click=self.clear,
                    ).props("flat dense size=sm").classes("text-slate-400").tooltip("Clear output")

            # Scroll area for log messages
            with ui.scroll_area().classes("w-full flex-grow").style(
                f"height: calc({height} - 50px);"
            ) as scroll:
                self._scroll_area = scroll
                self._container = ui.column().classes("w-full p-2 gap-0.5")

    def log(self, text: str, level: LogLevel = LogLevel.INFO) -> None:
        """Add a log message.

        Args:
            text: Message text
            level: Log level for styling
        """
        msg = LogMessage(text=text, level=level)
        self.messages.append(msg)

        # Trim old messages
        if len(self.messages) > self.max_lines:
            self.messages = self.messages[-self.max_lines:]

        # Add to UI if container exists
        if self._container is not None:
            self._add_message_to_ui(msg)

            # Auto-scroll if enabled
            if self.auto_scroll and self._scroll_area is not None:
                self._scroll_area.scroll_to(percent=1.0)

    def info(self, text: str) -> None:
        """Log an info message."""
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

    def clear(self) -> None:
        """Clear all messages."""
        self.messages.clear()
        if self._container is not None:
            self._container.clear()

    def _add_message_to_ui(self, msg: LogMessage) -> None:
        """Add a message element to the UI container."""
        if self._container is None:
            return

        # Determine color based on level
        color_map = {
            LogLevel.DEBUG: "#6b7280",    # gray
            LogLevel.INFO: "#e5e7eb",     # light gray
            LogLevel.WARNING: "#fbbf24",  # yellow
            LogLevel.ERROR: "#ef4444",    # red
            LogLevel.SUCCESS: "#22c55e",  # green
        }
        color = color_map.get(msg.level, "#e5e7eb")

        with self._container:
            with ui.row().classes("w-full gap-2 items-start"):
                if self.show_timestamps and msg.timestamp:
                    ui.label(
                        msg.timestamp.strftime("%H:%M:%S")
                    ).classes("text-xs font-mono text-slate-600 w-16 flex-shrink-0")
                
                ui.label(msg.text).classes("text-sm font-mono break-all").style(f"color: {color};")

    async def _copy_to_clipboard(self) -> None:
        """Copy all messages to clipboard."""
        if not self.messages:
            ui.notify("No output to copy", type="info")
            return

        text_lines = []
        for msg in self.messages:
            if self.show_timestamps and msg.timestamp:
                text_lines.append(f"[{msg.timestamp.strftime('%H:%M:%S')}] {msg.text}")
            else:
                text_lines.append(msg.text)

        text = "\n".join(text_lines)
        
        # Use JavaScript to copy to clipboard
        await ui.run_javascript(f'''
            navigator.clipboard.writeText({repr(text)}).then(() => {{
                // Success handled by notification below
            }}).catch(err => {{
                console.error('Failed to copy:', err);
            }});
        ''')
        ui.notify("Copied to clipboard", type="positive")


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
