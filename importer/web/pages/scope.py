"""Scope step page - select entities for migration and run normalization."""

import asyncio
import json
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.element_ids import apply_element_ids
from importer.web.state import AppState, WorkflowStep, STEP_NAMES
from importer.web.components.stepper import DBT_ORANGE
from importer.web.components.selection_manager import SelectionManager
from importer.web.components.hierarchy_index import HierarchyIndex
from importer.web.components.entity_table import show_entity_detail_dialog

# Resource type display info with new abbreviation codes
RESOURCE_TYPES = {
    "ACC": {"name": "Account", "code": "ACCNT", "icon": "cloud", "color": "#3B82F6"},
    "CON": {"name": "Connection", "code": "CONN", "icon": "storage", "color": "#10B981"},
    "REP": {"name": "Repository", "code": "REPO", "icon": "source", "color": "#8B5CF6"},
    "TOK": {"name": "Service Token", "code": "SRVTKN", "icon": "key", "color": "#EC4899"},
    "GRP": {"name": "Group", "code": "GRP", "icon": "group", "color": "#6366F1"},
    "NOT": {"name": "Notification", "code": "NOTIFY", "icon": "notifications", "color": "#F97316"},
    "WEB": {"name": "Webhook", "code": "WBHK", "icon": "webhook", "color": "#84CC16"},
    "PLE": {"name": "PrivateLink", "code": "PRVLNK", "icon": "lock", "color": "#14B8A6"},
    "PRJ": {"name": "Project", "code": "PRJCT", "icon": "folder", "color": "#F59E0B"},
    "ENV": {"name": "Environment", "code": "ENV", "icon": "layers", "color": "#06B6D4"},
    "PRF": {"name": "Profile", "code": "PRF", "icon": "badge", "color": "#0891B2"},
    "EXTATTR": {"name": "Extended Attributes", "code": "EXTATTR", "icon": "tune", "color": "#0EA5E9"},
    "CRD": {"name": "Credential", "code": "CRED", "icon": "vpn_key", "color": "#78716C"},
    "VAR": {"name": "Env Variable", "code": "ENVVAR", "icon": "code", "color": "#A855F7"},
    "JOB": {"name": "Job", "code": "JOB", "icon": "schedule", "color": "#EF4444"},
    "JCTG": {"name": "Job Completion Trigger", "code": "JCTG", "icon": "play_circle_outline", "color": "#F97316"},
    "JEVO": {"name": "Env Var Job Override", "code": "JEVO", "icon": "tune", "color": "#14B8A6"},
    "ACFT": {"name": "Account Features", "code": "ACFT", "icon": "settings", "color": "#6366F1"},
    "IPRST": {"name": "IP Restrictions", "code": "IPRST", "icon": "security", "color": "#DC2626"},
    "LNGI": {"name": "Lineage Integration", "code": "LNGI", "icon": "account_tree", "color": "#0EA5E9"},
    "OAUTH": {"name": "OAuth Config", "code": "OAUTH", "icon": "vpn_key", "color": "#D97706"},
    "PARFT": {"name": "Project Artefacts", "code": "PARFT", "icon": "inventory_2", "color": "#059669"},
    "USRGRP": {"name": "User Groups", "code": "USRGRP", "icon": "group", "color": "#7C3AED"},
    "SLCFG": {"name": "Semantic Layer Config", "code": "SLCFG", "icon": "layers", "color": "#EC4899"},
    "SLSTM": {"name": "SL Credential Mapping", "code": "SLSTM", "icon": "link", "color": "#F43F5E"},
}


def _dbg_a7dab6(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "a7dab6",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(__import__("time").time() * 1000),
    }
    try:
        with open(
            "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-a7dab6.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


def create_scope_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Scope step page - select resources for migration."""
    
    # Main container
    with ui.element("div").classes("w-full max-w-7xl mx-auto p-4").style(
        "display: grid; "
        "grid-template-rows: auto 1fr auto; "
        "height: calc(100vh - 100px); "
        "gap: 8px; "
        "overflow: hidden;"
    ):
        # Row 1: Header
        _create_header(state)
        
        # Check if data is available
        if not state.fetch.fetch_complete:
            _create_no_data_message(on_step_change)
            return
        
        # Load report items
        report_items = _load_report_items(state)
        if not report_items:
            _create_no_data_message(on_step_change)
            return
        
        # Build hierarchy index for parent-child relationships
        hierarchy_index = HierarchyIndex(report_items)
        
        # Sort items in hierarchical order
        hierarchical_order = hierarchy_index.get_hierarchical_order()
        report_items_ordered = []
        items_by_id = {r.get("element_mapping_id"): r for r in report_items}
        for mapping_id in hierarchical_order:
            if mapping_id in items_by_id:
                item = items_by_id[mapping_id]
                # Add depth for visual indentation
                item["_depth"] = hierarchy_index.get_depth(mapping_id)
                report_items_ordered.append(item)
        
        # Initialize selection manager
        selection_manager = SelectionManager(
            account_id=state.source_account.account_id or "unknown",
            base_url=state.source_account.host_url,
        )
        selection_manager.load()
        
        # Reconcile selections with current entities
        selection_manager.reconcile_with_entities(report_items_ordered)
        
        # Update state counts
        counts = selection_manager.get_selection_counts()
        state.map.selection_counts = counts
        
        # Row 2: Main content (split into selection panel and results panel)
        # Ref for summary refresh callback
        summary_refresh_ref = {"refresh": None}
        # Ref for grid refresh callback (used when selections change externally)
        grid_refresh_ref = {"refresh": None}
        
        with ui.element("div").style(
            "display: grid; "
            "grid-template-columns: 1fr 350px; "
            "gap: 16px; "
            "overflow: hidden; "
            "min-height: 0;"
        ):
            # Left: Entity selection
            _create_selection_panel(report_items_ordered, selection_manager, state, save_state, summary_refresh_ref, hierarchy_index, grid_refresh_ref)
            
            # Right: Results/action panel
            _create_action_panel(state, selection_manager, report_items_ordered, on_step_change, save_state, summary_refresh_ref, hierarchy_index, grid_refresh_ref)
        
        # Row 3: Navigation
        _create_navigation(state, on_step_change)


def _create_header(state: AppState) -> None:
    """Create the page header."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-1"):
                ui.label("Select Entities for Migration").classes("text-2xl font-bold")
                ui.label(
                    "Select which entities to include in the Terraform configuration"
                ).classes("text-slate-600 dark:text-slate-400")
            
            if state.fetch.account_name:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("cloud", size="sm").classes("text-slate-500")
                    ui.label(state.fetch.account_name).classes("font-medium")


def _create_no_data_message(on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Show message when no fetch data is available."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("warning", size="3rem").classes("text-amber-500 mx-auto")
        ui.label("No Data Available").classes("text-xl font-bold mt-4")
        ui.label("Complete the Fetch Source step first to scope entities.").classes(
            "text-slate-600 dark:text-slate-400 mt-2"
        )
        ui.button(
            f"Go to {STEP_NAMES[WorkflowStep.FETCH_SOURCE]}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.FETCH_SOURCE),
        ).classes("mt-4")


def _load_report_items(state: AppState) -> list:
    """Load report items, preferring derivation from account JSON so extended_attributes (EXTATTR) are included."""
    # Prefer: derive from account JSON so EXTATTR and other project-level items stay in sync
    if state.fetch.last_fetch_file:
        json_path = Path(state.fetch.last_fetch_file)
        if json_path.exists():
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
                if payload and payload.get("projects"):
                    items = apply_element_ids(payload)
                    return items
            except (json.JSONDecodeError, TypeError, IOError):
                pass
    # Fallback: load pre-written report_items file
    if state.fetch.last_report_items_file:
        try:
            path = Path(state.fetch.last_report_items_file)
            if path.exists():
                items = json.loads(path.read_text(encoding="utf-8"))
                return items
        except (json.JSONDecodeError, IOError):
            pass
    # Fallback: derive from JSON in same dir as summary (e.g. when last_fetch_file not in state)
    if state.fetch.last_summary_file:
        summary_path = Path(state.fetch.last_summary_file)
        parts = summary_path.stem.split("__")
        if len(parts) >= 3:
            prefix, timestamp = parts[0], parts[-1]
            for name in (f"{prefix}__json__{timestamp}.json", f"{prefix}__report_items__{timestamp}.json"):
                candidate = summary_path.parent / name
                if not candidate.exists():
                    continue
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                    if "__json__" in name and isinstance(data, dict) and data.get("projects"):
                        items = apply_element_ids(data)
                        return items
                    if "__report_items__" in name and isinstance(data, list):
                        return data
                except (json.JSONDecodeError, TypeError, IOError):
                    pass
    return []


def _create_selection_panel(
    report_items: list,
    selection_manager: SelectionManager,
    state: AppState,
    save_state: Callable[[], None],
    summary_refresh_ref: dict,
    hierarchy_index: HierarchyIndex,
    grid_refresh_ref: dict,
) -> None:
    """Create the entity selection panel with table and controls."""
    
    with ui.card().classes("w-full h-full p-4").style("overflow: hidden; display: flex; flex-direction: column;"):
        # Track UI refs
        grid_ref = {"grid": None}
        count_ref = {"label": None}
        # Initialize from persisted state
        filter_ref = {
            "type": state.map.type_filter,
            "selected_only": state.map.selected_only_filter
        }
        show_selected_btn_ref = {"button": None}
        type_select_ref = {"select": None}
        hierarchy_ref = {"index": hierarchy_index}
        # Flag to prevent circular updates
        programmatic_update = {"active": False}
        
        def update_count_display():
            """Update the selection count display."""
            counts = selection_manager.get_selection_counts()
            state.map.selection_counts = counts
            if count_ref["label"]:
                count_ref["label"].set_text(f"{counts['selected']} of {counts['total']} selected")
            # Also refresh the summary panel
            if summary_refresh_ref.get("refresh"):
                summary_refresh_ref["refresh"]()
        
        def get_visible_ids() -> set:
            """Get IDs of currently visible (filtered) entities."""
            filter_type = filter_ref["type"]
            if filter_type == "all":
                return {e.get("element_mapping_id") for e in report_items if e.get("element_mapping_id")}
            return {
                e.get("element_mapping_id") 
                for e in report_items 
                if e.get("element_type_code") == filter_type and e.get("element_mapping_id")
            }
        
        async def on_select_all():
            visible_ids = get_visible_ids()
            selection_manager.select_all(visible_ids)
            update_count_display()
            if grid_ref["grid"]:
                programmatic_update["active"] = True
                # If "selected only" filter is active, refresh the filtered view
                if filter_ref.get("selected_only") and filter_ref.get("refresh_grid"):
                    filter_ref["refresh_grid"]()
                else:
                    await _refresh_grid_selections(grid_ref["grid"], selection_manager, True)
                programmatic_update["active"] = False
        
        async def on_deselect_all():
            visible_ids = get_visible_ids()
            selection_manager.deselect_all(visible_ids)
            update_count_display()
            if grid_ref["grid"]:
                programmatic_update["active"] = True
                # If "selected only" filter is active, refresh the filtered view
                if filter_ref.get("selected_only") and filter_ref.get("refresh_grid"):
                    filter_ref["refresh_grid"]()
                else:
                    await _refresh_grid_selections(grid_ref["grid"], selection_manager, False)
                programmatic_update["active"] = False
        
        async def on_invert():
            visible_ids = get_visible_ids()
            selection_manager.invert_selection(visible_ids)
            update_count_display()
            if grid_ref["grid"]:
                programmatic_update["active"] = True
                # If "selected only" filter is active, refresh the filtered view
                if filter_ref.get("selected_only") and filter_ref.get("refresh_grid"):
                    filter_ref["refresh_grid"]()
                else:
                    await _refresh_grid_selections(grid_ref["grid"], selection_manager, None)
                programmatic_update["active"] = False
        
        # Header row with controls
        with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap mb-2"):
            # Type filter
            types_in_data = sorted(
                set(item.get("element_type_code", "UNK") for item in report_items)
            )
            type_options = {"all": "All Types"} | {
                t: f"{RESOURCE_TYPES.get(t, {}).get('name', t)} ({RESOURCE_TYPES.get(t, {}).get('code', t)})" 
                for t in types_in_data
            }
            
            async def on_type_change(e):
                filter_ref["type"] = e.value
                # Persist to state
                state.map.type_filter = e.value
                save_state()
                if grid_ref["grid"]:
                    filtered = _get_filtered_items(report_items, e.value)
                    # Apply selected_only filter if active
                    if filter_ref["selected_only"]:
                        filtered = [r for r in filtered if selection_manager.is_selected(r.get("element_mapping_id"))]
                    grid_ref["grid"].options["rowData"] = _add_selection_column(filtered, selection_manager)
                    grid_ref["grid"].update()
            
            type_select_ref["select"] = ui.select(
                options=type_options,
                value=filter_ref["type"],  # Use persisted value
                on_change=on_type_change,
            ).props("outlined dense").classes("min-w-[150px]")
            
            # Selection controls
            with ui.row().classes("gap-2"):
                ui.button("Select All", icon="check_box", on_click=on_select_all).props("outline dense")
                ui.button("Deselect All", icon="check_box_outline_blank", on_click=on_deselect_all).props("outline dense")
                ui.button("Invert", icon="flip", on_click=on_invert).props("outline dense")
            
            # Cascade selection controls
            cascade_btns_ref = {"children": None, "parents": None}
            
            async def on_select_children():
                """Select all children of currently selected entities (excludes account-level cascade)."""
                selected_ids = selection_manager.get_selected_ids()
                new_selections = set()
                
                for mapping_id in selected_ids:
                    # Skip account entity - selecting account children is effectively "select all"
                    entity = hierarchy_ref["index"].get_entity(mapping_id)
                    if entity and entity.get("element_type_code") == "ACC":
                        continue
                    
                    descendants = hierarchy_ref["index"].get_all_descendants(mapping_id)
                    new_selections.update(descendants)
                    # ENV↔EXTATTR: also select linked extended attributes / environments
                    linked = hierarchy_ref["index"].get_linked_entities(mapping_id)
                    new_selections.update(linked)
                
                if new_selections:
                    selection_manager.select_all(new_selections)
                    update_count_display()
                    if grid_ref["grid"]:
                        programmatic_update["active"] = True
                        if filter_ref.get("selected_only") and filter_ref.get("refresh_grid"):
                            filter_ref["refresh_grid"]()
                        else:
                            await _refresh_grid_selections(grid_ref["grid"], selection_manager, True)
                        programmatic_update["active"] = False
                    ui.notify(f"Selected {len(new_selections)} child entities", type="positive")
                else:
                    ui.notify("No children found for selected entities", type="info")
            
            async def on_select_parents():
                """Select all required parents of currently selected entities (excludes account)."""
                selected_ids = selection_manager.get_selected_ids()
                new_selections = set()
                hierarchy = hierarchy_ref["index"]
                
                for mapping_id in selected_ids:
                    ancestors = hierarchy.get_required_ancestors(mapping_id)
                    # Filter out account entity - don't auto-select account
                    for ancestor_id in ancestors:
                        ancestor = hierarchy.get_entity(ancestor_id)
                        if ancestor and ancestor.get("element_type_code") != "ACC":
                            new_selections.add(ancestor_id)
                    # ENV↔EXTATTR: also select linked extended attributes / environments
                    linked = hierarchy.get_linked_entities(mapping_id)
                    new_selections.update(linked)
                
                # Only add parents that aren't already selected
                new_selections -= selected_ids
                
                if new_selections:
                    selection_manager.select_all(new_selections)
                    update_count_display()
                    if grid_ref["grid"]:
                        programmatic_update["active"] = True
                        if filter_ref.get("selected_only") and filter_ref.get("refresh_grid"):
                            filter_ref["refresh_grid"]()
                        else:
                            await _refresh_grid_selections(grid_ref["grid"], selection_manager, True)
                        programmatic_update["active"] = False
                    ui.notify(f"Selected {len(new_selections)} parent entities", type="positive")
                else:
                    ui.notify("All required parents already selected", type="info")
            
            with ui.row().classes("gap-2"):
                cascade_btns_ref["children"] = ui.button(
                    "Select Children", 
                    icon="account_tree", 
                    on_click=on_select_children
                ).props("outline dense").tooltip("Select all descendants of selected entities")
                
                cascade_btns_ref["parents"] = ui.button(
                    "Select Parents", 
                    icon="north", 
                    on_click=on_select_parents
                ).props("outline dense").tooltip("Select required parent entities")
            
            # Auto-cascade toggle with confirmation
            auto_cascade_ref = {"switch": None, "enabled": state.map.auto_cascade_children}
            
            async def confirm_auto_cascade():
                """Show confirmation dialog when enabling auto-cascade."""
                result = await ui.run_javascript(
                    'confirm("Enable auto-cascade?\\n\\n'
                    'When ON, selecting a parent entity will automatically select all its children.\\n\\n'
                    'Note: This will NOT retroactively cascade existing selections.")'
                )
                return result
            
            async def on_auto_cascade_change(e):
                new_value = e.value
                
                # Update immediately so checkbox clicks work while confirmation is shown
                auto_cascade_ref["enabled"] = new_value
                state.map.auto_cascade_children = new_value
                
                if new_value:
                    # Enabling - show confirmation
                    confirmed = await confirm_auto_cascade()
                    if not confirmed:
                        # User cancelled - revert state
                        auto_cascade_ref["enabled"] = False
                        state.map.auto_cascade_children = False
                        if auto_cascade_ref["switch"]:
                            auto_cascade_ref["switch"].set_value(False)
                        return
                
                save_state()
                
                if new_value:
                    ui.notify("Auto-cascade enabled. Selecting parents will auto-select children.", type="info")
                else:
                    ui.notify("Auto-cascade disabled.", type="info")
            
            with ui.row().classes("gap-2 items-center"):
                auto_cascade_ref["switch"] = ui.switch(
                    "Auto-cascade",
                    value=state.map.auto_cascade_children,
                    on_change=on_auto_cascade_change
                ).tooltip("When ON, selecting a parent auto-selects all its children")
                
                # Toggle to show only selected
                def refresh_grid_with_filters():
                    """Refresh grid respecting current filter settings."""
                    if grid_ref["grid"]:
                        # Get items based on type filter first
                        filtered = _get_filtered_items(report_items, filter_ref["type"])
                        # Then filter by selected if toggle is on
                        if filter_ref["selected_only"]:
                            filtered = [r for r in filtered if selection_manager.is_selected(r.get("element_mapping_id"))]
                        grid_ref["grid"].options["rowData"] = _add_selection_column(filtered, selection_manager)
                        grid_ref["grid"].update()
                
                def toggle_selected_only():
                    filter_ref["selected_only"] = not filter_ref["selected_only"]
                    # Persist to state
                    state.map.selected_only_filter = filter_ref["selected_only"]
                    save_state()
                    refresh_grid_with_filters()
                    # Update button appearance
                    _update_selected_only_button_style()
                
                def _update_selected_only_button_style():
                    if show_selected_btn_ref["button"]:
                        if filter_ref["selected_only"]:
                            show_selected_btn_ref["button"].props(remove="outline")
                            show_selected_btn_ref["button"].style(f"background-color: {DBT_ORANGE};")
                        else:
                            show_selected_btn_ref["button"].props("outline")
                            show_selected_btn_ref["button"].style("background-color: transparent;")
                
                # Store refresh function for use by select all/deselect all
                filter_ref["refresh_grid"] = refresh_grid_with_filters
                # Also store in shared ref for external callers (like Bulk Select Resources)
                grid_refresh_ref["refresh"] = refresh_grid_with_filters
                
                # Create button with initial state from persistence
                if filter_ref["selected_only"]:
                    show_selected_btn_ref["button"] = ui.button(
                        "Selected Only", 
                        icon="filter_list", 
                        on_click=toggle_selected_only
                    ).props("dense").style(f"background-color: {DBT_ORANGE};")
                else:
                    show_selected_btn_ref["button"] = ui.button(
                        "Selected Only", 
                        icon="filter_list", 
                        on_click=toggle_selected_only
                    ).props("outline dense")
                
                def reset_filters():
                    """Reset filters to defaults (All Types, Selected Only off) without changing selections."""
                    # Reset type filter
                    filter_ref["type"] = "all"
                    state.map.type_filter = "all"
                    if type_select_ref.get("select"):
                        type_select_ref["select"].set_value("all")
                    
                    # Reset selected only
                    filter_ref["selected_only"] = False
                    state.map.selected_only_filter = False
                    _update_selected_only_button_style()
                    
                    save_state()
                    refresh_grid_with_filters()
                    ui.notify("Filters reset", type="info")
                
                ui.button(
                    "Reset Filters", 
                    icon="filter_alt_off", 
                    on_click=reset_filters
                ).props("outline dense").tooltip("Reset to All Types with Selected Only off")
                
                # Export CSV button
                def export_csv():
                    if grid_ref["grid"]:
                        grid_ref["grid"].run_grid_method('exportDataAsCsv', {
                            'fileName': 'scope_entities.csv',
                            'columnSeparator': ',',
                        })
                
                ui.button(
                    "Export CSV",
                    icon="download",
                    on_click=export_csv
                ).props("outline dense")
            
            # Count display
            counts = selection_manager.get_selection_counts()
            count_ref["label"] = ui.label(f"{counts['selected']} of {counts['total']} selected").classes(
                "text-sm font-medium"
            )
        
        # Entity table with checkboxes
        with ui.element("div").classes("w-full flex-1").style("overflow: hidden; min-height: 200px;"):
            _create_selection_grid(report_items, selection_manager, grid_ref, count_ref, state, programmatic_update, summary_refresh_ref, filter_ref, hierarchy_ref, auto_cascade_ref)


def _get_filtered_items(report_items: list, type_filter: str) -> list:
    """Filter report items by type."""
    if type_filter == "all":
        return report_items
    return [r for r in report_items if r.get("element_type_code") == type_filter]


# Map old type codes to new display codes
TYPE_CODE_MAP = {
    "ACC": "ACCNT", "CON": "CONN", "REP": "REPO", "TOK": "SRVTKN",
    "GRP": "GRP", "NOT": "NOTIFY", "WEB": "WBHK", "PLE": "PRVLNK",
    "PRJ": "PRJCT", "ENV": "ENV", "PRF": "PRF", "CRD": "CRED", "VAR": "ENVVAR", "JOB": "JOB",
    "JCTG": "JCTG", "JEVO": "JEVO",
    "EXTATTR": "EXTATTR",
    "ACFT": "ACFT", "IPRST": "IPRST", "LNGI": "LNGI", "OAUTH": "OAUTH",
    "PARFT": "PARFT", "USRGRP": "USRGRP", "SLCFG": "SLCFG", "SLSTM": "SLSTM",
}


def _add_selection_column(items: list, selection_manager: SelectionManager) -> list:
    """Add selection state and display type to items for grid display."""
    result = []
    for item in items:
        item_copy = dict(item)
        mapping_id = item.get("element_mapping_id")
        item_copy["_selected"] = selection_manager.is_selected(mapping_id) if mapping_id else True
        # Add display type with new code
        old_type = item.get("element_type_code", "")
        item_copy["_display_type"] = TYPE_CODE_MAP.get(old_type, old_type)
        result.append(item_copy)
    return result


async def _refresh_grid_selections(grid, selection_manager: SelectionManager, select_all: Optional[bool]) -> None:
    """Refresh the visual state of checkboxes in the grid by updating row data.
    
    Args:
        grid: The AG Grid component
        selection_manager: The selection manager instance
        select_all: Not used - we update based on SelectionManager state
    """
    try:
        # Update _selected field in row data based on SelectionManager
        row_data = grid.options.get("rowData", [])
        for row in row_data:
            mapping_id = row.get("element_mapping_id")
            if mapping_id:
                row["_selected"] = selection_manager.is_selected(mapping_id)
        
        # Trigger grid update to reflect changes
        grid.update()
    except Exception as e:
        print(f"Error refreshing grid selections: {e}")


def _create_selection_grid(
    report_items: list,
    selection_manager: SelectionManager,
    grid_ref: dict,
    count_ref: dict,
    state: AppState,
    programmatic_update: dict,
    summary_refresh_ref: dict,
    filter_ref: dict,
    hierarchy_ref: dict,
    auto_cascade_ref: dict,
) -> None:
    """Create the AG Grid with selection checkboxes."""
    
    # Apply initial filters from persisted state
    filtered_items = _get_filtered_items(report_items, filter_ref.get("type", "all"))
    if filter_ref.get("selected_only", False):
        filtered_items = [r for r in filtered_items if selection_manager.is_selected(r.get("element_mapping_id"))]
    
    # Prepare data with selection column
    row_data = _add_selection_column(filtered_items, selection_manager)
    
    # Column definitions - use _selected as a visible checkbox indicator
    column_defs = [
        {
            "field": "_selected",
            "colId": "_selected",
            "headerName": "✓",
            "width": 50,
            "pinned": "left",
            "cellRenderer": "agCheckboxCellRenderer",  # Use AG Grid's checkbox renderer
            "editable": True,  # Make it editable to allow clicking
            "cellStyle": {"textAlign": "center"},
        },
        {
            "field": "_display_type",  # Use pre-computed display type
            "colId": "element_type_code", 
            "headerName": "Type",
            "width": 90,
        },
        {
            "field": "name",
            "colId": "name",
            "headerName": "Name",
            "width": 300,
            "filter": "agTextColumnFilter",
            # Custom cell renderer for indentation based on depth
            "cellRenderer": "function(params) { "
                "var depth = params.data._depth || 0; "
                "var indent = depth * 20; "
                "var name = params.value || ''; "
                "return '<span style=\"padding-left: ' + indent + 'px;\">' + name + '</span>'; "
            "}",
        },
        {
            "field": "project_name",
            "colId": "project_name",
            "headerName": "Project",
            "width": 180,
            "filter": "agTextColumnFilter",
        },
        {
            "field": "key",
            "colId": "key",
            "headerName": "Key",
            "width": 200,
        },
        {
            "field": "element_mapping_id",
            "colId": "element_mapping_id",
            "headerName": "Mapping ID",
            "width": 140,
        },
    ]
    
    grid = ui.aggrid({
        "columnDefs": column_defs,
        "rowData": row_data,
        "pagination": True,
        "paginationPageSize": 200,
        "paginationPageSizeSelector": [100, 200, 500, 1000],
        "headerHeight": 36,
        "defaultColDef": {
            "resizable": True,
            "sortable": True,
            "filter": True,
        },
        "stopEditingWhenCellsLoseFocus": True,
        "animateRows": False,  # Stability - per ag-grid-standards.mdc
    }, theme="quartz").classes("w-full h-full ag-theme-quartz-auto-dark")
    
    grid_ref["grid"] = grid
    
    # Handle cell value changes (when checkbox is toggled)
    def on_cell_value_changed(e):
        """Handle when a cell value changes (checkbox toggled)."""
        if programmatic_update.get("active", False):
            return
            
        try:
            if e.args and e.args.get("colId") == "_selected":
                row_data_item = e.args.get("data", {})
                mapping_id = row_data_item.get("element_mapping_id")
                new_value = e.args.get("newValue", False)
                
                if mapping_id:
                    selection_manager.set_selected(mapping_id, new_value)
                    
                    # Auto-cascade: if enabling and auto-cascade is on, select children
                    # Skip cascade for account entity - that's effectively "select all"
                    cascade_count = 0
                    auto_cascade_enabled = auto_cascade_ref.get("enabled", False)
                    if new_value and auto_cascade_enabled and hierarchy_ref.get("index"):
                        entity = hierarchy_ref["index"].get_entity(mapping_id)
                        if not entity or entity.get("element_type_code") != "ACC":
                            descendants = hierarchy_ref["index"].get_all_descendants(mapping_id)
                            linked = hierarchy_ref["index"].get_linked_entities(mapping_id)
                            to_select = descendants | linked
                            if to_select:
                                selection_manager.select_all(to_select, auto_save=False)
                                cascade_count = len(to_select)
                                selection_manager.save()  # Save once after all updates
                    
                    # Update count display
                    counts = selection_manager.get_selection_counts()
                    state.map.selection_counts = counts
                    if count_ref["label"]:
                        count_ref["label"].set_text(f"{counts['selected']} of {counts['total']} selected")
                    
                    # If we cascaded, update the grid to reflect child selections
                    if cascade_count > 0:
                        programmatic_update["active"] = True
                        # Refresh row data to show updated selections
                        current_row_data = grid.options.get("rowData", [])
                        for row in current_row_data:
                            rid = row.get("element_mapping_id")
                            if rid:
                                row["_selected"] = selection_manager.is_selected(rid)
                        grid.update()
                        programmatic_update["active"] = False
                    
                    # Refresh summary panel
                    if summary_refresh_ref.get("refresh"):
                        summary_refresh_ref["refresh"]()
        except Exception as ex:
            print(f"Cell value change error: {ex}")
    
    grid.on("cellValueChanged", on_cell_value_changed)
    
    # Handle cell click to show entity detail popup
    def on_cell_clicked(e):
        """Handle cell click to show entity details."""
        # Don't show popup for checkbox column clicks
        if e.args and e.args.get("colId") == "_selected":
            return
        if e.args and "data" in e.args:
            row_data_item = e.args["data"]
            show_entity_detail_dialog(row_data_item, state)
    
    grid.on("cellClicked", on_cell_clicked)


def _create_action_panel(
    state: AppState,
    selection_manager: SelectionManager,
    report_items: list,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
    summary_refresh_ref: dict,
    hierarchy_index: HierarchyIndex,
    grid_refresh_ref: dict,
) -> None:
    """Create the right-side action panel with normalize button and results."""
    
    with ui.card().classes("w-full h-full p-4").style("overflow-y: auto; overflow-x: hidden;"):
        # Selection summary
        ui.label("Selection Summary").classes("text-lg font-bold mb-2")
        
        summary_container = ui.column().classes("w-full gap-2 mb-4")
        
        # Create a refreshable summary
        @ui.refreshable
        def refreshable_summary():
            counts = selection_manager.get_selection_counts()
            _create_summary_stats(counts, report_items, selection_manager, hierarchy_index, state)
        
        with summary_container:
            refreshable_summary()
        
        # Store the refresh function so it can be called from elsewhere
        summary_refresh_ref["refresh"] = refreshable_summary.refresh
        
        ui.separator()
        
        # Bulk Project Selector (US-028)
        with ui.expansion("Bulk Project Selector", icon="checklist").classes("w-full"):
            ui.label("Control which projects are included in the configuration.").classes(
                "text-xs text-slate-600 dark:text-slate-400 mb-2"
            )
            
            # Get list of projects from report items
            projects_in_data = []
            for item in report_items:
                if item.get("element_type_code") == "PRJ":
                    projects_in_data.append({
                        "id": item.get("element_mapping_id"),
                        "name": item.get("name", "Unknown"),
                        "key": item.get("key", ""),
                    })
            
            # Scope mode radio
            scope_options = {
                "all_projects": "All Projects",
                "specific_projects": "Specific Projects",
                "account_only": "Account Level Only (globals)",
            }
            
            project_select_container = ui.column().classes("w-full")
            
            def on_project_select_change(e):
                state.map.selected_project_ids = list(e.value)
                save_state()
                if summary_refresh_ref.get("refresh"):
                    summary_refresh_ref["refresh"]()
            
            def on_scope_change(e):
                state.map.scope_mode = e.value
                save_state()
                # Show/hide project picker
                project_select_container.clear()
                if e.value == "specific_projects" and projects_in_data:
                    with project_select_container:
                        project_options = {p["id"]: p["name"] for p in projects_in_data}
                        ui.select(
                            options=project_options,
                            value=state.map.selected_project_ids,
                            multiple=True,
                            label="Select Projects",
                            on_change=on_project_select_change,
                        ).props("outlined dense use-chips").classes("w-full")
                # Refresh summary to show filter impact
                if summary_refresh_ref.get("refresh"):
                    summary_refresh_ref["refresh"]()
            
            ui.radio(
                options=scope_options,
                value=state.map.scope_mode,
                on_change=on_scope_change,
            ).classes("w-full")
            
            # Initial project picker if needed
            if state.map.scope_mode == "specific_projects" and projects_in_data:
                with project_select_container:
                    project_options = {p["id"]: p["name"] for p in projects_in_data}
                    ui.select(
                        options=project_options,
                        value=state.map.selected_project_ids,
                        multiple=True,
                        label="Select Projects",
                        on_change=on_project_select_change,
                    ).props("outlined dense use-chips").classes("w-full")
            
            # Global resource inclusion toggles
            ui.label("Include Globals").classes("text-sm font-medium mt-4 mb-2")
            ui.label("Select which account-level resources to include.").classes(
                "text-xs text-slate-600 dark:text-slate-400 mb-2"
            )
            
            def make_global_toggle_handler(field_name: str):
                def handler(e):
                    setattr(state.map, field_name, e.value)
                    save_state()
                return handler
            
            with ui.row().classes("flex-wrap gap-x-4 gap-y-2"):
                ui.checkbox(
                    "Groups", 
                    value=state.map.include_groups,
                    on_change=make_global_toggle_handler("include_groups")
                ).props("dense")
                ui.checkbox(
                    "Notifications", 
                    value=state.map.include_notifications,
                    on_change=make_global_toggle_handler("include_notifications")
                ).props("dense")
                ui.checkbox(
                    "Service Tokens", 
                    value=state.map.include_service_tokens,
                    on_change=make_global_toggle_handler("include_service_tokens")
                ).props("dense")
                ui.checkbox(
                    "Webhooks", 
                    value=state.map.include_webhooks,
                    on_change=make_global_toggle_handler("include_webhooks")
                ).props("dense")
                ui.checkbox(
                    "PrivateLink", 
                    value=state.map.include_privatelink,
                    on_change=make_global_toggle_handler("include_privatelink")
                ).props("dense")
            
            # Bulk Select Resources button
            ui.button(
                "Bulk Select Resources",
                icon="filter_alt",
                on_click=lambda: _apply_scope_selection(
                    state, selection_manager, report_items, hierarchy_index, save_state, summary_refresh_ref, grid_refresh_ref
                ),
            ).props("outline dense").classes("w-full mt-4")
        
        # Resource Filters (US-029)
        with ui.expansion("Resource Filters", icon="tune").classes("w-full"):
            ui.label("Enable/disable resource types for configuration generation.").classes(
                "text-xs text-slate-600 dark:text-slate-400 mb-2"
            )
            
            # Count entities by type
            type_counts = {}
            for item in report_items:
                type_code = item.get("element_type_code", "UNK")
                if type_code not in type_counts:
                    type_counts[type_code] = 0
                type_counts[type_code] += 1
            
            # Resource filter mapping
            resource_filter_map = {
                "CON": ("connections", "Connections"),
                "REP": ("repositories", "Repositories"),
                "TOK": ("service_tokens", "Service Tokens"),
                "GRP": ("groups", "Groups"),
                "NOT": ("notifications", "Notifications"),
                "WEB": ("webhooks", "Webhooks"),
                "PLE": ("privatelink_endpoints", "PrivateLink Endpoints"),
                "PRJ": ("projects", "Projects"),
                "ENV": ("environments", "Environments"),
                "PRF": ("profiles", "Profiles"),
                "EXTATTR": ("extended_attributes", "Extended Attributes"),
                "JOB": ("jobs", "Jobs"),
                "JCTG": ("job_completion_triggers", "Job Triggers"),
                "JEVO": ("environment_variable_job_overrides", "Env Var Job Overrides"),
                "VAR": ("environment_variables", "Env Variables"),
                "ACFT": ("account_features", "Account Features"),
                "IPRST": ("ip_restrictions", "IP Restrictions"),
                "LNGI": ("lineage_integrations", "Lineage Integrations"),
                "OAUTH": ("oauth_configurations", "OAuth Configurations"),
                "PARFT": ("project_artefacts", "Project Artefacts"),
                "USRGRP": ("user_groups", "User Groups"),
                "SLCFG": ("semantic_layer_configs", "Semantic Layer Configs"),
                "SLSTM": ("sl_credential_mappings", "SL Credential Mappings"),
            }
            
            def create_filter_toggle(type_code: str, filter_key: str, label: str, count: int):
                """Create a toggle for a resource type."""
                type_info = RESOURCE_TYPES.get(type_code, {"icon": "help", "color": "#6B7280", "code": type_code})
                code = type_info.get("code", type_code)
                
                def on_toggle(e):
                    state.map.resource_filters[filter_key] = e.value
                    save_state()
                    # Refresh summary to show filter impact
                    if summary_refresh_ref.get("refresh"):
                        summary_refresh_ref["refresh"]()
                
                with ui.row().classes("w-full justify-between items-center py-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon(type_info["icon"], size="xs").style(f"color: {type_info['color']};")
                        ui.label(f"{label} ({code}) [{count}]").classes("text-sm")
                    ui.switch(
                        value=state.map.resource_filters.get(filter_key, True),
                        on_change=on_toggle,
                    )
            
            # Create toggles for each resource type
            for type_code, (filter_key, label) in resource_filter_map.items():
                count = type_counts.get(type_code, 0)
                if count > 0:  # Only show if there are entities of this type
                    create_filter_toggle(type_code, filter_key, label, count)
        
        # Normalization Options (US-031)
        with ui.expansion("Advanced Options", icon="settings").classes("w-full"):
            ui.label("Configure how entities are normalized for Terraform.").classes(
                "text-xs text-slate-600 dark:text-slate-400 mb-2"
            )
            
            # Strip Source IDs toggle
            with ui.row().classes("w-full justify-between items-center py-1"):
                with ui.column().classes("gap-0"):
                    ui.label("Strip Source IDs").classes("text-sm font-medium")
                    ui.label("Remove dbt Cloud IDs from output YAML").classes("text-xs text-slate-500")
                ui.switch(
                    value=state.map.normalization_options.get("strip_source_ids", False),
                    on_change=lambda e: (
                        state.map.normalization_options.update({"strip_source_ids": e.value}),
                        save_state()
                    ),
                )
            
            ui.separator().classes("my-2")
            
            # Secret Handling dropdown
            ui.label("Secret Handling").classes("text-sm font-medium")
            ui.label("How to handle sensitive values (API keys, tokens, etc.)").classes(
                "text-xs text-slate-500 mb-1"
            )
            secret_options = {
                "redact": "Redact - Replace with [REDACTED]",
                "omit": "Omit - Remove secret fields entirely",
                "placeholder": "Placeholder - Use LOOKUP placeholders",
            }
            ui.select(
                options=secret_options,
                value=state.map.normalization_options.get("secret_handling", "redact"),
                on_change=lambda e: (
                    state.map.normalization_options.update({"secret_handling": e.value}),
                    save_state()
                ),
            ).props("outlined dense").classes("w-full")
            
            ui.separator().classes("my-2")
            
            # Name Collision Strategy dropdown
            ui.label("Name Collision Strategy").classes("text-sm font-medium")
            ui.label("What to do when entity names would conflict").classes(
                "text-xs text-slate-500 mb-1"
            )
            collision_options = {
                "suffix": "Suffix - Add numeric suffix (_1, _2, etc.)",
                "error": "Error - Fail if names conflict",
                "skip": "Skip - Skip duplicate entities",
            }
            ui.select(
                options=collision_options,
                value=state.map.normalization_options.get("name_collision_strategy", "suffix"),
                on_change=lambda e: (
                    state.map.normalization_options.update({"name_collision_strategy": e.value}),
                    save_state()
                ),
            ).props("outlined dense").classes("w-full")
        
        ui.separator()
        
        # Config file management (US-032, US-033)
        ui.label("Configuration Files").classes("text-lg font-bold mt-2 mb-2")
        
        config_status = ui.label("").classes("text-xs text-slate-500 mb-2")
        
        async def on_load_config(e):
            """Load configuration from uploaded YAML file."""
            import yaml
            try:
                content = e.content.read().decode("utf-8")
                config_data = yaml.safe_load(content)
                
                if not isinstance(config_data, dict):
                    ui.notify("Invalid config file format", type="negative")
                    return
                
                # Apply scope settings
                scope = config_data.get("scope", {})
                state.map.scope_mode = scope.get("mode", "all_projects")
                state.map.selected_project_ids = scope.get("project_ids", [])
                
                # Apply resource filters
                resource_filters = config_data.get("resource_filters", {})
                for key, value in resource_filters.items():
                    if isinstance(value, dict):
                        state.map.resource_filters[key] = value.get("include", True)
                    else:
                        state.map.resource_filters[key] = bool(value)
                
                # Apply normalization options
                norm_opts = config_data.get("normalization_options", {})
                state.map.normalization_options.update(norm_opts)
                
                save_state()
                config_status.set_text(f"Loaded: {e.name}")
                ui.notify(f"Configuration loaded from {e.name}", type="positive")
                
                # Reload page to reflect changes
                ui.navigate.reload()
                
            except yaml.YAMLError as ye:
                ui.notify(f"YAML parsing error: {ye}", type="negative")
            except Exception as ex:
                ui.notify(f"Error loading config: {ex}", type="negative")
        
        async def on_save_config():
            """Save current configuration to YAML file."""
            import yaml
            from datetime import datetime
            
            config = {
                "version": 1,
                "generated_at": datetime.now().isoformat(),
                "scope": {
                    "mode": state.map.scope_mode,
                    "project_ids": state.map.selected_project_ids,
                },
                "resource_filters": {
                    k: {"include": v} for k, v in state.map.resource_filters.items()
                },
                "normalization_options": state.map.normalization_options,
            }
            
            yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=False)
            
            # Use JavaScript to trigger download
            # Escape backticks for JS template literal
            escaped_yaml = yaml_content.replace('`', '\\`')
            js_code = f'''
                const blob = new Blob([`{escaped_yaml}`], {{type: 'text/yaml'}});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'importer_mapping.yml';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            '''
            await ui.run_javascript(js_code)
            ui.notify("Configuration saved to importer_mapping.yml", type="positive")
        
        with ui.row().classes("w-full gap-2"):
            ui.upload(
                label="Load Config",
                auto_upload=True,
                on_upload=on_load_config,
            ).props("accept=.yml,.yaml flat dense").classes("flex-1")
            
            ui.button(
                "Save Config",
                icon="download",
                on_click=on_save_config,
            ).props("outline dense")
        
        ui.separator()
        
        # Normalize section
        ui.label("Generate Configuration").classes("text-lg font-bold mt-4 mb-2")
        ui.label(
            "Run normalization to generate Terraform-ready YAML from selected entities."
        ).classes("text-sm text-slate-600 dark:text-slate-400 mb-4")
        
        # Progress/status area
        status_container = ui.column().classes("w-full gap-2 mb-4")
        
        # Normalize button
        async def on_normalize():
            await _run_normalize(state, selection_manager, report_items, status_container, save_state)
        
        ui.button(
            "Generate Selected YAML",
            icon="settings_suggest",
            on_click=on_normalize,
        ).style(f"background-color: {DBT_ORANGE};").classes("w-full")
        
        # Results section (shown after normalize)
        results_container = ui.column().classes("w-full gap-2 mt-4")
        
        with results_container:
            if state.map.normalize_complete and state.map.last_yaml_file:
                _create_results_display(state, on_step_change)


def _apply_scope_selection(
    state: AppState,
    selection_manager: SelectionManager,
    report_items: list,
    hierarchy_index: HierarchyIndex,
    save_state: Callable[[], None],
    summary_refresh_ref: dict,
    grid_refresh_ref: dict,
) -> None:
    """Bulk select resources: clear all selections and select scoped resources.
    
    This clears all selections, then selects:
    1. Projects based on scope mode (all or specific)
    2. All descendants of those projects (environments, jobs, variables)
    3. Connections referenced by the selected environments
    4. Global resources based on toggle settings (groups, notifications, etc.)
    """
    # Build lookup maps
    item_by_id = {item.get("element_mapping_id"): item for item in report_items}
    
    # 1. Clear all selections
    selection_manager.deselect_all(auto_save=False)
    
    # 2. Get target projects based on scope mode
    if state.map.scope_mode == "all_projects":
        target_projects = {
            item.get("element_mapping_id") 
            for item in report_items 
            if item.get("element_type_code") == "PRJ"
        }
    elif state.map.scope_mode == "specific_projects":
        target_projects = set(state.map.selected_project_ids)
    else:  # account_only
        target_projects = set()
    
    # 3. Select projects and cascade to all descendants (ENV, JOB, VAR, REP)
    selected_env_ids = set()
    for project_id in target_projects:
        selection_manager.set_selected(project_id, True, auto_save=False)
        for child_id in hierarchy_index.get_all_descendants(project_id):
            selection_manager.set_selected(child_id, True, auto_save=False)
            # Track environments for connection lookup
            child_item = item_by_id.get(child_id)
            if child_item and child_item.get("element_type_code") == "ENV":
                selected_env_ids.add(child_id)
    
    # 4. Select connections
    # all_projects: include ALL connections (global resources needed for full migration).
    # specific_projects: only connections referenced by selected environments.
    if state.map.scope_mode == "all_projects":
        for item in report_items:
            if item.get("element_type_code") == "CON":
                selection_manager.set_selected(item.get("element_mapping_id"), True, auto_save=False)
    else:
        used_connection_ids: set[int] = set()
        used_connection_keys: set[str] = set()
        for env_id in selected_env_ids:
            env_item = item_by_id.get(env_id)
            if env_item:
                conn_id = env_item.get("connection_id")
                conn_key = env_item.get("connection_key")
                if conn_id:
                    used_connection_ids.add(conn_id)
                elif conn_key:
                    used_connection_keys.add(conn_key)
        for item in report_items:
            if item.get("element_type_code") == "CON":
                conn_dbt_id = item.get("dbt_id")
                conn_key = item.get("key")
                if conn_dbt_id and conn_dbt_id in used_connection_ids:
                    selection_manager.set_selected(item.get("element_mapping_id"), True, auto_save=False)
                elif conn_key and conn_key in used_connection_keys:
                    selection_manager.set_selected(item.get("element_mapping_id"), True, auto_save=False)
    
    # 5. Select globals based on toggle settings
    global_toggles = {
        "GRP": state.map.include_groups,
        "NOT": state.map.include_notifications,
        "TOK": state.map.include_service_tokens,
        "WEB": state.map.include_webhooks,
        "PLE": state.map.include_privatelink,
    }
    for item in report_items:
        type_code = item.get("element_type_code")
        if type_code in global_toggles and global_toggles[type_code]:
            selection_manager.set_selected(item.get("element_mapping_id"), True, auto_save=False)
    
    # Save selections
    selection_manager.save()
    
    # Update selection counts in state
    counts = selection_manager.get_selection_counts()
    state.map.selection_counts = counts
    save_state()
    
    # Refresh summary display
    if summary_refresh_ref.get("refresh"):
        summary_refresh_ref["refresh"]()
    
    # Refresh grid (especially important when "Selected Only" filter is active)
    if grid_refresh_ref.get("refresh"):
        grid_refresh_ref["refresh"]()
    
    ui.notify(f"Bulk selected {counts['selected']} resources", type="positive")


def _get_effective_selection(
    selection_manager: SelectionManager,
    report_items: list,
    state: AppState,
    hierarchy_index: Optional[HierarchyIndex] = None,
) -> tuple[set, dict]:
    """Get effective selection after applying scope and resource filters.
    
    Returns:
        Tuple of (effective_ids set, filter_stats dict with counts)
    """
    selected_ids = selection_manager.get_selected_ids()
    
    # Build lookup maps
    item_by_id = {item.get("element_mapping_id"): item for item in report_items}
    
    # Get project IDs and their children for scope filtering
    project_children = {}  # project_id -> set of child entity IDs
    for item in report_items:
        mapping_id = item.get("element_mapping_id")
        parent_project_id = item.get("parent_project_id")
        if parent_project_id:
            if parent_project_id not in project_children:
                project_children[parent_project_id] = set()
            project_children[parent_project_id].add(mapping_id)
    
    # Resource filter mapping (type_code -> filter_key)
    # Must match keys in resource_filter_map used by the UI toggles
    type_to_filter = {
        "CON": "connections", "REP": "repositories", "TOK": "service_tokens",
        "GRP": "groups", "NOT": "notifications", "WEB": "webhooks",
        "PLE": "privatelink_endpoints", "PRJ": "projects", "ENV": "environments", "PRF": "profiles",
        "EXTATTR": "extended_attributes", "VAR": "environment_variables", "JOB": "jobs",
        "JCTG": "job_completion_triggers", "JEVO": "environment_variable_job_overrides",
        "ACFT": "account_features", "IPRST": "ip_restrictions", "LNGI": "lineage_integrations",
        "OAUTH": "oauth_configurations", "PARFT": "project_artefacts", "USRGRP": "user_groups",
        "SLCFG": "semantic_layer_configs", "SLSTM": "sl_credential_mappings",
    }
    
    effective_ids = set()
    filter_stats = {
        "raw_selected": len(selected_ids),
        "scope_excluded": 0,
        "resource_excluded": 0,
        "dependency_added": 0,
    }
    
    for mapping_id in selected_ids:
        item = item_by_id.get(mapping_id)
        if not item:
            continue
        
        type_code = item.get("element_type_code", "")
        
        # Apply scope filter
        scope_mode = state.map.scope_mode
        if scope_mode == "account_only":
            # Only include globals (no parent_project_id) and account itself
            if item.get("parent_project_id"):
                filter_stats["scope_excluded"] += 1
                continue
        elif scope_mode == "specific_projects":
            selected_project_ids = set(state.map.selected_project_ids)
            if type_code == "PRJ":
                # Only include selected projects
                if mapping_id not in selected_project_ids:
                    filter_stats["scope_excluded"] += 1
                    continue
            elif item.get("parent_project_id"):
                # Only include children of selected projects
                if item.get("parent_project_id") not in selected_project_ids:
                    filter_stats["scope_excluded"] += 1
                    continue
        # "all_projects" includes everything
        
        # Apply resource filter
        filter_key = type_to_filter.get(type_code)
        if filter_key and not state.map.resource_filters.get(filter_key, True):
            filter_stats["resource_excluded"] += 1
            continue
        
        effective_ids.add(mapping_id)
    
    if hierarchy_index is not None and effective_ids:
        expanded_ids = set(effective_ids)
        dependency_ids = set()
        to_visit = list(effective_ids)
        while to_visit:
            mapping_id = to_visit.pop()
            for linked_id in hierarchy_index.get_linked_entities(mapping_id):
                if linked_id in expanded_ids:
                    continue
                linked_entity = hierarchy_index.get_entity(linked_id)
                if not linked_entity or linked_entity.get("element_type_code") == "ACC":
                    continue
                expanded_ids.add(linked_id)
                dependency_ids.add(linked_id)
                to_visit.append(linked_id)
        effective_ids = expanded_ids
        filter_stats["dependency_added"] = len(dependency_ids)
    
    filter_stats["effective_count"] = len(effective_ids)
    return effective_ids, filter_stats


def _create_summary_stats(
    counts: dict, 
    report_items: list, 
    selection_manager: SelectionManager,
    hierarchy_index: HierarchyIndex,
    state: AppState,
) -> None:
    """Create summary statistics display with dependency warnings."""
    
    # Get effective selection after filters
    effective_ids, filter_stats = _get_effective_selection(selection_manager, report_items, state, hierarchy_index)
    has_filters = (
        filter_stats["scope_excluded"] > 0
        or filter_stats["resource_excluded"] > 0
        or filter_stats["dependency_added"] > 0
    )
    
    # Overall count - show raw and filtered if different
    with ui.row().classes("w-full justify-between items-center"):
        ui.label("Selected").classes("text-sm")
        ui.label(f"{counts['selected']} / {counts['total']}").classes("font-bold")
    
    # Show effective count if filters applied
    if has_filters:
        with ui.row().classes("w-full justify-between items-center bg-blue-50 dark:bg-blue-900/30 p-1 rounded"):
            with ui.row().classes("items-center gap-1"):
                ui.icon("filter_alt", size="xs").classes("text-blue-600 dark:text-blue-400")
                ui.label("Effective (after filters)").classes("text-sm text-blue-700 dark:text-blue-300")
            ui.label(f"{filter_stats['effective_count']}").classes("font-bold text-blue-700 dark:text-blue-300")
        
        # Filter breakdown
        with ui.column().classes("w-full text-xs text-slate-500 dark:text-slate-400 ml-2"):
            if filter_stats["scope_excluded"] > 0:
                ui.label(f"• Scope filter: -{filter_stats['scope_excluded']}")
            if filter_stats["resource_excluded"] > 0:
                ui.label(f"• Resource filter: -{filter_stats['resource_excluded']}")
            if filter_stats["dependency_added"] > 0:
                ui.label(f"• Linked dependencies: +{filter_stats['dependency_added']}")
    
    # Progress bar
    if counts['total'] > 0:
        pct = (counts['selected'] / counts['total']) * 100
        ui.linear_progress(value=pct/100, show_value=False).classes("w-full")
        ui.label(f"{pct:.0f}% selected").classes("text-xs text-center text-slate-500 dark:text-slate-400")
    
    # By type breakdown - use report_items to get type info
    ui.label("By Type:").classes("text-sm font-medium mt-2")
    
    # Count by type using report items (raw selected and effective)
    type_counts = {}
    for item in report_items:
        type_code = item.get("element_type_code", "UNK")
        mapping_id = item.get("element_mapping_id")
        
        if type_code not in type_counts:
            type_counts[type_code] = {"selected": 0, "effective": 0, "total": 0}
        type_counts[type_code]["total"] += 1
        
        if mapping_id:
            if selection_manager.is_selected(mapping_id):
                type_counts[type_code]["selected"] += 1
            if mapping_id in effective_ids:
                type_counts[type_code]["effective"] += 1
    
    for type_code in sorted(type_counts.keys()):
        tc = type_counts[type_code]
        type_info = RESOURCE_TYPES.get(type_code, {"name": type_code, "icon": "help", "color": "#6B7280"})
        
        # Check if this type has filtered items
        type_has_filter = tc["selected"] != tc["effective"]
        
        with ui.row().classes("w-full justify-between items-center"):
            with ui.row().classes("items-center gap-1"):
                ui.icon(type_info["icon"], size="xs").style(f"color: {type_info['color']};")
                ui.label(f"{type_info['name']} ({type_info.get('code', type_code)})").classes("text-xs")
            
            if type_has_filter and has_filters:
                # Show both raw and effective with strikethrough on raw
                with ui.row().classes("items-center gap-1"):
                    ui.label(f"{tc['selected']}").classes("text-xs line-through text-slate-400")
                    ui.label(f"→ {tc['effective']}/{tc['total']}").classes("text-xs font-medium text-blue-600 dark:text-blue-400")
            else:
                ui.label(f"{tc['selected']}/{tc['total']}").classes("text-xs font-medium")
    
    # Dependency warnings - use effective_ids (after scope/resource filters)
    # rather than raw selected_ids to avoid showing warnings for filtered-out entities
    warnings = hierarchy_index.check_missing_dependencies(effective_ids)
    
    if warnings:
        ui.separator().classes("my-2")
        with ui.card().classes("w-full p-2 bg-amber-50 dark:bg-amber-900/30"):
            with ui.row().classes("items-center gap-2 mb-1"):
                ui.icon("warning", size="sm").classes("text-amber-600 dark:text-amber-400")
                ui.label(f"{len(warnings)} Missing Dependencies").classes(
                    "text-sm font-bold text-amber-700 dark:text-amber-300"
                )
            
            # Show first few warnings with details
            shown_warnings = warnings[:5]
            for w in shown_warnings:
                with ui.row().classes("items-center gap-1 ml-6"):
                    ui.label(f"• {w['entity']}").classes("text-xs text-amber-700 dark:text-amber-300")
                    ui.label(f"→ needs {w['missing_type']} '{w['missing']}'").classes(
                        "text-xs text-amber-600 dark:text-amber-400"
                    )
            
            if len(warnings) > 5:
                ui.label(f"  ... and {len(warnings) - 5} more").classes(
                    "text-xs text-amber-600 dark:text-amber-400 ml-6"
                )
            
            ui.label(
                "Tip: Use 'Select Parents' to add missing dependencies."
            ).classes("text-xs text-amber-600 dark:text-amber-400 mt-2 italic")


async def _run_normalize(
    state: AppState,
    selection_manager: SelectionManager,
    report_items: list,
    status_container,
    save_state: Callable[[], None],
) -> None:
    """Run the normalization process."""
    
    # Clear status container
    status_container.clear()
    
    with status_container:
        ui.label("Normalizing...").classes("text-sm font-medium")
        ui.spinner(size="sm")
    
    state.map.normalize_running = True
    state.map.normalize_error = None
    
    try:
        # Get effective selection after applying scope and resource filters
        hierarchy_index = HierarchyIndex(report_items)
        effective_ids, filter_stats = _get_effective_selection(
            selection_manager, report_items, state, hierarchy_index
        )

        item_by_id = {
            item.get("element_mapping_id"): item
            for item in report_items
            if item.get("element_mapping_id")
        }
        selected_connections_by_id = {
            int(item.get("dbt_id"))
            for mapping_id, item in item_by_id.items()
            if mapping_id in effective_ids
            and item.get("element_type_code") == "CON"
            and item.get("dbt_id") is not None
        }
        selected_connections_by_key = {
            str(item.get("key"))
            for mapping_id, item in item_by_id.items()
            if mapping_id in effective_ids
            and item.get("element_type_code") == "CON"
            and item.get("key")
        }
        selected_extattrs = {
            str(item.get("key"))
            for mapping_id, item in item_by_id.items()
            if mapping_id in effective_ids
            and item.get("element_type_code") == "EXTATTR"
            and item.get("key")
        }
        selected_credentials_by_id = {
            int(item.get("dbt_id"))
            for mapping_id, item in item_by_id.items()
            if mapping_id in effective_ids
            and item.get("element_type_code") == "CRD"
            and item.get("dbt_id") is not None
        }
        selected_profiles = []
        missing_connection = 0
        missing_extattr = 0
        missing_credential = 0
        for mapping_id, item in item_by_id.items():
            if mapping_id not in effective_ids or item.get("element_type_code") != "PRF":
                continue
            project_key = str(item.get("project_key") or "")
            ext_key = str(item.get("extended_attributes_key") or "")
            ext_lookup_key = f"{project_key}_{ext_key}" if project_key and ext_key else ""
            connection_id = item.get("connection_id")
            credentials_id = item.get("credentials_id")
            connection_selected = (
                connection_id in selected_connections_by_id
                if connection_id is not None
                else False
            ) or (str(item.get("connection_key") or "") in selected_connections_by_key)
            extattr_selected = (ext_lookup_key in selected_extattrs) if ext_lookup_key else True
            credential_selected = (
                credentials_id in selected_credentials_by_id
                if credentials_id is not None
                else True
            )
            if not connection_selected:
                missing_connection += 1
            if not extattr_selected:
                missing_extattr += 1
            if not credential_selected:
                missing_credential += 1
            selected_profiles.append(
                {
                    "mapping_id": mapping_id,
                    "project_key": project_key,
                    "profile_key": str(item.get("profile_key") or item.get("key") or ""),
                    "connection_key": str(item.get("connection_key") or ""),
                    "connection_id": connection_id,
                    "connection_selected": connection_selected,
                    "credentials_id": credentials_id,
                    "credential_selected": credential_selected,
                    "extended_attributes_key": ext_key,
                    "extended_attributes_id": item.get("extended_attributes_id"),
                    "extended_attributes_selected": extattr_selected,
                }
            )
        # region agent log
        _dbg_a7dab6(
            "H1",
            "scope.py:_run_normalize",
            "effective selection dependency coverage for selected profiles",
            {
                "scope_mode": state.map.scope_mode,
                "raw_selected": len(selection_manager.get_selected_ids()),
                "effective_selected": len(effective_ids),
                "filter_stats": filter_stats,
                "selected_type_counts": {
                    type_code: sum(
                        1
                        for mapping_id in effective_ids
                        if item_by_id.get(mapping_id, {}).get("element_type_code") == type_code
                    )
                    for type_code in ("PRJ", "PRF", "CON", "CRD", "EXTATTR", "ENV")
                },
                "selected_profile_count": len(selected_profiles),
                "missing_connection_count": missing_connection,
                "missing_credential_count": missing_credential,
                "missing_extattr_count": missing_extattr,
                "selected_profiles": selected_profiles[:25],
            },
        )
        # endregion
        
        # Build exclusion map by type (mapping_id -> type_code)
        item_type_map = {
            item.get("element_mapping_id"): item.get("element_type_code")
            for item in report_items if item.get("element_mapping_id")
        }
        
        # Compute exclusion IDs grouped by type
        all_ids = set(item_type_map.keys())
        exclude_ids = all_ids - effective_ids
        
        # Group exclusions by type for the normalizer
        exclude_by_type = {}
        for eid in exclude_ids:
            type_code = item_type_map.get(eid)
            if type_code:
                if type_code not in exclude_by_type:
                    exclude_by_type[type_code] = []
                exclude_by_type[type_code].append(eid)
        
        # Run normalize in background thread
        result = await asyncio.to_thread(
            _do_normalize,
            state.fetch.last_fetch_file,
            exclude_by_type,
            state.fetch.output_dir,
        )
        
        # Update state with results
        state.map.normalize_complete = True
        state.map.last_yaml_file = result.get("yaml_file")
        state.map.last_lookups_file = result.get("lookups_file")
        state.map.last_exclusions_file = result.get("exclusions_file")
        state.map.lookups_count = result.get("lookups_count", 0)
        state.map.exclusions_count = result.get("exclusions_count", 0)
        
        # Store collision warnings for display in UI
        collision_count = result.get("collision_count", 0)
        collision_summary = result.get("collision_summary", {})
        if collision_summary:
            state.data_quality_warnings["source"] = {
                "collisions": collision_summary,
                "collision_count": collision_count,
            }
        
        save_state()
        
        # Update status
        status_container.clear()
        with status_container:
            ui.icon("check_circle", size="sm").classes("text-green-500")
            ui.label("Normalization complete!").classes("text-sm text-green-600")
        
        # Show results
        ui.notify("Normalization complete!", type="positive")
        
        # Show collision warning if any
        if collision_count > 0:
            ui.notify(
                f"⚠️ Data quality: {collision_count} duplicate key(s) found and auto-resolved",
                type="warning",
                timeout=10000,
            )
        
        # Trigger page refresh to show results
        ui.navigate.reload()
        
    except Exception as e:
        state.map.normalize_error = str(e)
        status_container.clear()
        with status_container:
            ui.icon("error", size="sm").classes("text-red-500")
            ui.label(f"Error: {e}").classes("text-sm text-red-600")
        ui.notify(f"Normalization failed: {e}", type="negative")
    
    finally:
        state.map.normalize_running = False


def _do_normalize(
    input_file: str,
    exclude_by_type: dict,
    output_dir: str,
) -> dict:
    """Perform the actual normalization (runs in background thread).
    
    Args:
        input_file: Path to the snapshot JSON file
        exclude_by_type: Dict mapping type_code -> list of mapping IDs to exclude
        output_dir: Directory for output files
    """
    from pathlib import Path
    
    from importer.models import AccountSnapshot
    from importer.normalizer import MappingConfig, NormalizationContext
    from importer.normalizer.core import normalize_snapshot
    from importer.normalizer.writer import YAMLWriter
    from importer.norm_tracker import NormalizationRunTracker
    
    # Load snapshot
    input_path = Path(input_file)
    snapshot_data = json.loads(input_path.read_text(encoding="utf-8"))
    
    # Get metadata
    metadata = snapshot_data.get("_metadata", {})
    account_id = metadata.get("account_id") or snapshot_data.get("account_id", 0)
    fetch_run_id = metadata.get("run_id", 0)
    
    # Reconstruct snapshot
    snapshot = AccountSnapshot(**snapshot_data)
    
    # Map type codes to resource filter names
    type_to_filter = {
        "CON": "connections",
        "REP": "repositories", 
        "TOK": "service_tokens",
        "GRP": "groups",
        "NOT": "notifications",
        "WEB": "webhooks",
        "PLE": "privatelink_endpoints",
        "PRJ": "projects",
        "ENV": "environments",
        "PRF": "profiles",
        "EXTATTR": "extended_attributes",
        "JOB": "jobs",
        "JCTG": "job_completion_triggers",
        "JEVO": "environment_variable_job_overrides",
        "VAR": "environment_variables",
        "ACFT": "account_features",
        "IPRST": "ip_restrictions",
        "LNGI": "lineage_integrations",
        "OAUTH": "oauth_configurations",
        "PARFT": "project_artefacts",
        "USRGRP": "user_groups",
        "SLCFG": "semantic_layer_configs",
        "SLSTM": "sl_credential_mappings",
    }
    
    # Create mapping config with exclusions
    config_data = {
        "version": 1,
        "scope": {"mode": "all_projects"},
        "resource_filters": {},
        "normalization_options": {
            "strip_source_ids": False,
            "secret_handling": "redact",
        },
    }
    
    # Add exclusions to resource filters (already grouped by type)
    if exclude_by_type:
        for type_code, ids in exclude_by_type.items():
            filter_name = type_to_filter.get(type_code)
            if filter_name and ids:
                config_data["resource_filters"][filter_name] = {"exclude_ids": ids}
    
    config = MappingConfig(**config_data)
    
    # Initialize tracking
    norm_output_dir = Path(output_dir)
    norm_tracker = NormalizationRunTracker(norm_output_dir / "normalization_runs.json")
    norm_run_id, timestamp = norm_tracker.start_run(account_id, fetch_run_id)
    
    # Initialize context
    context = NormalizationContext(config)
    
    # Normalize
    normalized_data = normalize_snapshot(snapshot, config, context)
    
    # Write artifacts
    writer = YAMLWriter(config, context)
    artifacts = writer.write_all_artifacts(
        normalized_data,
        norm_output_dir,
        norm_run_id,
        timestamp,
        account_id,
    )
    
    return {
        "yaml_file": str(artifacts.get("yaml")),
        "lookups_file": str(artifacts.get("lookups")) if artifacts.get("lookups") else None,
        "exclusions_file": str(artifacts.get("exclusions")) if artifacts.get("exclusions") else None,
        "lookups_count": len(context.placeholders),
        "exclusions_count": len(context.exclusions),
        "collision_summary": context.get_collision_summary(),
        "collision_count": context.get_collision_count(),
    }


def _create_results_display(state: AppState, on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Create the results display after normalization."""
    
    ui.separator()
    ui.label("Results").classes("text-lg font-bold mt-4 mb-2")
    
    # YAML file
    if state.map.last_yaml_file:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("description", size="sm").classes("text-green-500")
            ui.label("YAML Config:").classes("text-sm font-medium")
        
        yaml_path = Path(state.map.last_yaml_file)
        ui.label(yaml_path.name).classes("text-xs text-slate-500 ml-6")
        
        if yaml_path.exists():
            size_kb = yaml_path.stat().st_size / 1024
            ui.label(f"({size_kb:.1f} KB)").classes("text-xs text-slate-400 ml-6")
            
            # View YAML button
            async def show_yaml_preview():
                """Show YAML preview in a modal."""
                try:
                    yaml_content = yaml_path.read_text(encoding="utf-8")
                    
                    with ui.dialog() as dialog, ui.card().classes("w-full").style("width: 90vw; max-width: 90vw; max-height: 80vh;"):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            ui.label("Generated YAML Preview").classes("text-lg font-bold")
                            ui.button(icon="close", on_click=dialog.close).props("flat round")
                        
                        # Search state
                        search_results = {"count": 0, "current": 0}
                        
                        # Search input with result count and navigation
                        search_container = ui.row().classes("w-full mb-2 items-center gap-2")
                        with search_container:
                            search_input = ui.input(
                                placeholder="Search in YAML...",
                            ).props("outlined dense clearable").classes("flex-1")
                            
                            # Navigation buttons (hidden initially)
                            with ui.row().classes("items-center gap-1"):
                                prev_btn = ui.button(icon="keyboard_arrow_up", on_click=lambda: None).props(
                                    "flat dense round size=sm"
                                ).classes("hidden")
                                next_btn = ui.button(icon="keyboard_arrow_down", on_click=lambda: None).props(
                                    "flat dense round size=sm"
                                ).classes("hidden")
                            
                            search_count_label = ui.label("").classes("text-xs text-slate-400 min-w-[100px]")
                            ui.label(f"{len(yaml_content)} chars").classes("text-xs text-slate-400")
                        
                        # YAML content with syntax highlighting
                        with ui.scroll_area().classes("w-full").style("height: 50vh;"):
                            ui.code(yaml_content, language="yaml").classes("w-full text-sm yaml-preview-code")
                        
                        # JavaScript for search highlighting
                        async def on_search(e):
                            # For on("update:model-value"), value is in e.args
                            search_term = e.args if e.args else ""
                            if not search_term:
                                search_count_label.set_text("")
                                search_results["count"] = 0
                                search_results["current"] = 0
                                prev_btn.classes("hidden", remove=False)
                                next_btn.classes("hidden", remove=False)
                                # Clear highlights
                                await ui.run_javascript('''
                                    document.querySelectorAll('.yaml-preview-code mark').forEach(m => {
                                        m.outerHTML = m.textContent;
                                    });
                                ''')
                                return
                            
                            # Count matches
                            count = yaml_content.lower().count(search_term.lower())
                            search_results["count"] = count
                            search_results["current"] = 1 if count > 0 else 0
                            
                            if count > 1:
                                search_count_label.set_text(f"1 of {count}")
                                prev_btn.classes(remove="hidden")
                                next_btn.classes(remove="hidden")
                            elif count == 1:
                                search_count_label.set_text("1 of 1")
                                prev_btn.classes("hidden", remove=False)
                                next_btn.classes("hidden", remove=False)
                            else:
                                search_count_label.set_text("No matches")
                                prev_btn.classes("hidden", remove=False)
                                next_btn.classes("hidden", remove=False)
                            
                            # Highlight matches using JavaScript
                            escaped_term = search_term.replace("'", "\\'").replace('"', '\\"')
                            await ui.run_javascript(f'''
                                const codeEl = document.querySelector('.yaml-preview-code code');
                                if (codeEl) {{
                                    // Restore original text first
                                    const originalText = codeEl.textContent;
                                    const regex = new RegExp('(' + '{escaped_term}'.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
                                    const highlighted = originalText.replace(regex, '<mark style="background-color: #fef08a; color: #000;">$1</mark>');
                                    codeEl.innerHTML = highlighted;
                                    
                                    // Highlight first match as current
                                    const marks = codeEl.querySelectorAll('mark');
                                    if (marks.length > 0) {{
                                        marks[0].style.backgroundColor = '#f97316';
                                        marks[0].scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                    }}
                                }}
                            ''')
                        
                        async def go_to_match(direction):
                            count = search_results["count"]
                            if count <= 1:
                                return
                            
                            current = search_results["current"]
                            if direction == "next":
                                new_idx = current + 1 if current < count else 1
                            else:
                                new_idx = current - 1 if current > 1 else count
                            
                            search_results["current"] = new_idx
                            search_count_label.set_text(f"{new_idx} of {count}")
                            
                            # Update highlighting in JavaScript
                            await ui.run_javascript(f'''
                                const marks = document.querySelectorAll('.yaml-preview-code mark');
                                marks.forEach((m, i) => {{
                                    m.style.backgroundColor = (i === {new_idx - 1}) ? '#f97316' : '#fef08a';
                                }});
                                if (marks[{new_idx - 1}]) {{
                                    marks[{new_idx - 1}].scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                }}
                            ''')
                        
                        prev_btn.on("click", lambda: go_to_match("prev"))
                        next_btn.on("click", lambda: go_to_match("next"))
                        search_input.on("update:model-value", on_search)
                        
                        # Action buttons
                        with ui.row().classes("w-full justify-end gap-2 mt-4"):
                            # Escape backticks for JS template literals
                            escaped_content = yaml_content.replace('`', '\\`')
                            
                            async def copy_yaml():
                                await ui.run_javascript(
                                    f'navigator.clipboard.writeText(`{escaped_content}`)'
                                )
                                ui.notify("Copied to clipboard", type="positive")
                            
                            async def download_yaml():
                                fname = yaml_path.name
                                js_code = f'''
                                    const blob = new Blob([`{escaped_content}`], {{type: 'text/yaml'}});
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement('a');
                                    a.href = url;
                                    a.download = '{fname}';
                                    document.body.appendChild(a);
                                    a.click();
                                    document.body.removeChild(a);
                                    URL.revokeObjectURL(url);
                                '''
                                await ui.run_javascript(js_code)
                            
                            ui.button("Copy", icon="content_copy", on_click=copy_yaml).props("outline")
                            ui.button("Download", icon="download", on_click=download_yaml).props("outline")
                    
                    dialog.open()
                    
                except Exception as ex:
                    ui.notify(f"Error loading YAML: {ex}", type="negative")
            
            ui.button(
                "View YAML",
                icon="visibility",
                on_click=show_yaml_preview,
            ).props("outline dense").classes("ml-6 mt-1")
    
    # Lookups count
    if state.map.lookups_count > 0:
        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.icon("warning", size="sm").classes("text-amber-500")
            ui.label(f"{state.map.lookups_count} LOOKUP placeholders").classes("text-sm")
        ui.label("Need manual resolution before deploy").classes("text-xs text-slate-500 ml-6")
    
    # Exclusions count
    if state.map.exclusions_count > 0:
        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.icon("info", size="sm").classes("text-blue-500")
            ui.label(f"{state.map.exclusions_count} resources excluded").classes("text-sm")
    
    # Continue button - go to Fetch Target next
    ui.button(
        f"Continue to {state.get_step_label(WorkflowStep.FETCH_TARGET)}",
        icon="arrow_forward",
        on_click=lambda: on_step_change(WorkflowStep.FETCH_TARGET),
    ).style(f"background-color: {DBT_ORANGE};").classes("w-full mt-4")


def _create_navigation(state: AppState, on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Create navigation buttons."""
    with ui.row().classes("w-full justify-between mt-4"):
        ui.button(
            f"Back to {state.get_step_label(WorkflowStep.EXPLORE_SOURCE)}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.EXPLORE_SOURCE),
        ).props("outline")
        
        if state.map.normalize_complete:
            ui.button(
                f"Continue to {state.get_step_label(WorkflowStep.FETCH_TARGET)}",
                icon="arrow_forward",
                on_click=lambda: on_step_change(WorkflowStep.FETCH_TARGET),
            ).style(f"background-color: {DBT_ORANGE};")
