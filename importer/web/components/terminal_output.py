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
                
                with ui.row().classes("gap-2 items-center"):
                    # Log level selector - ordered from least to most verbose (ERROR shows least, DEBUG shows all)
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
                        "min-width: 110px; background-color: #2d2d4a; border-radius: 4px;"
                    ).tooltip("Minimum log level to show")
                    
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
        msg = LogMessage(text=text, level=level)
        self.messages.append(msg)

        # Trim old messages
        if len(self.messages) > self.max_lines:
            self.messages = self.messages[-self.max_lines:]

        # Add to UI if container exists and level passes filter
        if self._container is not None and self._should_display(level):
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
                        msg.timestamp.strftime("%H:%M:%S")
                    ).classes("text-xs font-mono text-slate-600 w-16 flex-shrink-0")
                
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
