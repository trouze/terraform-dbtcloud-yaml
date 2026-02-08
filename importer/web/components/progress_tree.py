"""Progress tree component for visualizing fetch progress."""

from typing import Optional

from nicegui import ui


# Resource types in fetch order (matching CLI)
GLOBAL_RESOURCES = [
    ("connections", "Connections"),
    ("repositories", "Repositories"),
    ("service_tokens", "Service Tokens"),
    ("groups", "Groups"),
    ("notifications", "Notifications"),
    ("webhooks", "Webhooks"),
    ("privatelink_endpoints", "PrivateLink Endpoints"),
]

PROJECT_RESOURCES = [
    ("environments", "Environments"),
    ("extended_attributes", "Extended Attributes (EXTATTR)"),
    ("credentials", "Credential Metadata (No Secret Values)"),
    ("jobs", "Jobs"),
    ("environment_variables", "Env Variables (No Secret Values)"),
    ("job_env_var_overrides", "Job Overrides"),
]


class ProgressTree:
    """A progress tree component that shows fetch progress hierarchy.
    
    Similar to the CLI Rich tree, shows phases and resources with status indicators.
    """
    
    def __init__(self):
        """Initialize the progress tree."""
        self._phase = ""
        self._resource_counts: dict[str, int] = {}
        self._resource_done: dict[str, bool] = {}
        self._resource_in_progress: dict[str, bool] = {}
        self._current_project_num = 0
        self._total_projects = 0
        self._current_project_name = ""
        self._is_fetching = False
        
        # UI elements for updates
        self._container: Optional[ui.column] = None
        self._phase_label: Optional[ui.label] = None
        self._global_items: dict[str, dict] = {}
        self._project_items: dict[str, dict] = {}
        self._project_header: Optional[ui.row] = None
    
    def create(self, compact: bool = False) -> ui.column:
        """Create the progress tree UI component.
        
        Args:
            compact: If True, use two-column layout for global/project resources
        """
        with ui.column().classes("w-full") as container:
            self._container = container
            
            # Header with overall status
            with ui.row().classes("w-full items-center gap-2 pb-2 border-b border-slate-200 dark:border-slate-700"):
                self._status_icon = ui.icon("hourglass_empty", size="sm").classes("text-slate-400")
                self._status_label = ui.label("Ready to fetch").classes("font-medium")
            
            if compact:
                # Two-column layout: Global Resources | Project Resources
                with ui.row().classes("w-full mt-3 gap-6"):
                    # Global Resources Column
                    with ui.column().classes("flex-1 gap-1"):
                        ui.label("Global Resources").classes("text-xs text-slate-500 font-semibold uppercase tracking-wide")
                        
                        with ui.column().classes("w-full gap-0.5"):
                            for resource_key, display_name in GLOBAL_RESOURCES:
                                self._global_items[resource_key] = self._create_resource_row(resource_key, display_name)
                    
                    # Projects Column
                    with ui.column().classes("flex-1 gap-1"):
                        with ui.row().classes("items-center gap-2") as project_header:
                            self._project_header = project_header
                            ui.label("Projects").classes("text-xs text-slate-500 font-semibold uppercase tracking-wide")
                            self._project_counter = ui.label("").classes("text-xs text-slate-400")
                        
                        with ui.column().classes("w-full gap-0.5"):
                            self._project_name_label = ui.label("").classes("text-sm text-slate-600 dark:text-slate-400 italic hidden")
                            
                            for resource_key, display_name in PROJECT_RESOURCES:
                                self._project_items[resource_key] = self._create_resource_row(resource_key, display_name)
            else:
                # Original single-column layout
                # Global Resources Section
                with ui.column().classes("w-full mt-3 gap-1"):
                    ui.label("Global Resources").classes("text-xs text-slate-500 font-semibold uppercase tracking-wide")
                    
                    with ui.column().classes("w-full pl-2 gap-0.5"):
                        for resource_key, display_name in GLOBAL_RESOURCES:
                            self._global_items[resource_key] = self._create_resource_row(resource_key, display_name)
                
                # Projects Section
                with ui.column().classes("w-full mt-3 gap-1"):
                    with ui.row().classes("items-center gap-2") as project_header:
                        self._project_header = project_header
                        ui.label("Projects").classes("text-xs text-slate-500 font-semibold uppercase tracking-wide")
                        self._project_counter = ui.label("").classes("text-xs text-slate-400")
                    
                    with ui.column().classes("w-full pl-2 gap-0.5"):
                        self._project_name_label = ui.label("").classes("text-sm text-slate-600 dark:text-slate-400 italic")
                        
                        for resource_key, display_name in PROJECT_RESOURCES:
                            self._project_items[resource_key] = self._create_resource_row(resource_key, display_name)
        
        return container
    
    def _create_resource_row(self, resource_key: str, display_name: str) -> dict:
        """Create a resource row with status icon and count."""
        with ui.row().classes("w-full items-center gap-2 py-0.5"):
            icon = ui.icon("radio_button_unchecked", size="xs").classes("text-slate-400")
            label = ui.label(display_name).classes("text-sm text-slate-500 flex-grow")
            count = ui.label("").classes("text-xs text-slate-400 font-mono")
        
        return {"icon": icon, "label": label, "count": count}
    
    def start(self) -> None:
        """Start the fetch progress display."""
        self._is_fetching = True
        self._resource_counts.clear()
        self._resource_done.clear()
        self._resource_in_progress.clear()
        
        self._status_icon.props("name=sync")
        self._status_icon.classes(
            "text-blue-500 animate-spin",
            remove="text-slate-400 text-green-500 text-red-500",
        )
        self._status_label.set_text("Fetching...")
        
        # Reset project counter and name
        self._project_counter.set_text("")
        self._project_name_label.set_text("")
        
        # Reset all resource rows — remove every possible state class
        for items in [self._global_items, self._project_items]:
            for row in items.values():
                row["icon"].props("name=radio_button_unchecked")
                row["icon"].classes(
                    "text-slate-400",
                    remove="text-green-500 text-yellow-500 text-orange-400 animate-spin",
                )
                row["label"].classes(
                    "text-slate-500",
                    remove="text-slate-700 dark:text-slate-300 font-medium",
                )
                row["count"].set_text("")
                row["count"].classes("text-slate-400", remove="text-green-600")
    
    def complete(self) -> None:
        """Mark fetch as complete."""
        self._is_fetching = False
        self._status_icon.props("name=check_circle")
        self._status_icon.classes("text-green-500", remove="text-blue-500 animate-spin")
        self._status_label.set_text("Fetch Complete")
    
    def error(self, message: str = "Fetch failed") -> None:
        """Mark fetch as failed."""
        self._is_fetching = False
        self._status_icon.props("name=error")
        self._status_icon.classes("text-red-500", remove="text-blue-500 animate-spin")
        self._status_label.set_text(message)
        
        # Stop all per-resource spinners that are still in progress
        for items in [self._global_items, self._project_items]:
            for resource_key, row in items.items():
                if self._resource_in_progress.get(resource_key) and not self._resource_done.get(resource_key):
                    row["icon"].props("name=cancel")
                    row["icon"].classes("text-orange-400", remove="text-yellow-500 animate-spin")
        self._resource_in_progress.clear()
    
    def on_phase(self, phase: str) -> None:
        """Update the current phase."""
        self._phase = phase
    
    def on_resource_start(self, resource_type: str, total: Optional[int] = None) -> None:
        """Mark a resource as in progress."""
        self._resource_in_progress[resource_type] = True
        self._resource_counts[resource_type] = 0
        
        # Find and update the row
        row = self._global_items.get(resource_type) or self._project_items.get(resource_type)
        if row:
            row["icon"].props("name=sync")
            row["icon"].classes("text-yellow-500 animate-spin", remove="text-slate-400 text-green-500 text-orange-400")
            row["label"].classes("text-slate-700 dark:text-slate-300 font-medium", remove="text-slate-500")
            if total is not None:
                row["count"].set_text(f"0/{total}")
    
    def on_resource_item(self, resource_type: str, key: str) -> None:
        """Increment the count for a resource."""
        self._resource_counts[resource_type] = self._resource_counts.get(resource_type, 0) + 1
        count = self._resource_counts[resource_type]
        
        row = self._global_items.get(resource_type) or self._project_items.get(resource_type)
        if row:
            row["count"].set_text(str(count))
    
    def on_resource_done(self, resource_type: str, count: int) -> None:
        """Mark a resource as complete."""
        self._resource_done[resource_type] = True
        self._resource_in_progress[resource_type] = False
        self._resource_counts[resource_type] = count
        
        row = self._global_items.get(resource_type) or self._project_items.get(resource_type)
        if row:
            row["icon"].props("name=check_circle")
            row["icon"].classes("text-green-500", remove="text-slate-400 text-yellow-500 text-orange-400 animate-spin")
            row["label"].classes("text-slate-700 dark:text-slate-300", remove="text-slate-500 font-medium")
            row["count"].set_text(str(count))
            row["count"].classes("text-green-600", remove="text-slate-400")
    
    def on_project_start(self, project_num: int, total: int, name: str) -> None:
        """Update project progress."""
        self._current_project_num = project_num
        self._total_projects = total
        self._current_project_name = name
        
        self._project_counter.set_text(f"({project_num}/{total})")
        self._project_name_label.set_text(f"→ {name}")
    
    def on_project_done(self, project_num: int) -> None:
        """Mark a project as complete."""
        pass  # Projects complete implicitly
