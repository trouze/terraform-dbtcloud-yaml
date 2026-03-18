"""Target resource matching component for matching source entities to existing target resources."""

from dataclasses import dataclass
from typing import Callable, Optional

from nicegui import ui


# Colors
DBT_TEAL = "#047377"
MATCH_GREEN = "#22C55E"
REJECT_RED = "#EF4444"


@dataclass
class MatchSuggestion:
    """A suggested match between a source entity and target resource."""
    
    source_name: str
    source_key: str
    source_type: str
    source_dbt_id: Optional[int] = None
    target_name: str = ""
    target_id: int = 0
    target_type: str = ""
    confidence: str = "exact_match"  # "exact_match" or "manual"
    status: str = "suggested"  # "suggested", "confirmed", "rejected"


def generate_match_suggestions(
    source_report_items: list[dict],
    target_report_items: list[dict],
) -> list[MatchSuggestion]:
    """Generate auto-match suggestions based on exact name matching.
    
    Matches are made when:
    - Resource types match (element_type_code)
    - Resource names match exactly (case-sensitive)
    
    Args:
        source_report_items: Report items from source fetch
        target_report_items: Report items from target fetch
        
    Returns:
        List of MatchSuggestion objects for suggested matches
    """
    suggestions = []
    
    # Build lookup of target items by (type, name)
    target_by_type_name: dict[tuple[str, str], dict] = {}
    for item in target_report_items:
        key = (item.get("element_type_code", ""), item.get("name", ""))
        # If multiple targets have same type+name, keep the first one
        if key not in target_by_type_name:
            target_by_type_name[key] = item
    
    # Find matches for each source item
    for source_item in source_report_items:
        source_type = source_item.get("element_type_code", "")
        source_name = source_item.get("name", "")
        
        # Skip items without names
        if not source_name:
            continue
        
        lookup_key = (source_type, source_name)
        if lookup_key in target_by_type_name:
            target_item = target_by_type_name[lookup_key]
            
            suggestion = MatchSuggestion(
                source_name=source_name,
                source_key=source_item.get("key", ""),
                source_type=source_type,
                source_dbt_id=source_item.get("dbt_id"),
                target_name=target_item.get("name", ""),
                target_id=target_item.get("dbt_id", 0),
                target_type=target_item.get("element_type_code", ""),
                confidence="exact_match",
                status="suggested",
            )
            suggestions.append(suggestion)
    
    return suggestions


def get_unmatched_source_items(
    source_report_items: list[dict],
    suggestions: list[MatchSuggestion],
    confirmed_mappings: list[dict],
) -> list[dict]:
    """Get source items that don't have a suggested or confirmed match.
    
    Args:
        source_report_items: All source report items
        suggestions: Current match suggestions
        confirmed_mappings: Already confirmed mappings
        
    Returns:
        List of source items without matches
    """
    # Collect keys that are already matched
    matched_keys = set()
    for s in suggestions:
        matched_keys.add(s.source_key)
    for m in confirmed_mappings:
        matched_keys.add(m.get("source_key", ""))
    
    # Return unmatched items
    return [
        item for item in source_report_items
        if item.get("key") not in matched_keys
    ]


def get_unmatched_target_items(
    target_report_items: list[dict],
    suggestions: list[MatchSuggestion],
    confirmed_mappings: list[dict],
) -> list[dict]:
    """Get target items that don't have a suggested or confirmed match.
    
    Args:
        target_report_items: All target report items
        suggestions: Current match suggestions
        confirmed_mappings: Already confirmed mappings
        
    Returns:
        List of target items without matches
    """
    # Collect target IDs that are already matched
    matched_ids = set()
    for s in suggestions:
        if s.status != "rejected":
            matched_ids.add(s.target_id)
    for m in confirmed_mappings:
        matched_ids.add(m.get("target_id", 0))
    
    # Return unmatched items
    return [
        item for item in target_report_items
        if item.get("dbt_id") not in matched_ids
    ]


# Resource type display names
RESOURCE_TYPE_LABELS = {
    "ACC": "Account",
    "CON": "Connection",
    "REP": "Repository",
    "TOK": "Service Token",
    "GRP": "Group",
    "NOT": "Notification",
    "WEB": "Webhook",
    "PLE": "PrivateLink",
    "PRJ": "Project",
    "ENV": "Environment",
    "PRF": "Profile",
    "VAR": "Env Variable",
    "JOB": "Job",
    "JCTG": "Job Completion Trigger",
    "JEVO": "Env Var Job Override",
    "EXTATTR": "Extended Attributes",
    "ACFT": "Account Features",
    "IPRST": "IP Restrictions",
    "LNGI": "Lineage Integration",
    "OAUTH": "OAuth Configuration",
    "PARFT": "Project Artefacts",
    "USRGRP": "User Groups",
    "SLCFG": "Semantic Layer Config",
    "SLSTM": "SL Credential Mapping",
}


def create_suggestions_table(
    suggestions: list[MatchSuggestion],
    on_confirm: Callable[[MatchSuggestion], None],
    on_reject: Callable[[MatchSuggestion], None],
    on_confirm_all: Callable[[], None],
    on_reject_all: Callable[[], None],
) -> None:
    """Create the suggested matches table UI.
    
    Args:
        suggestions: List of match suggestions to display
        on_confirm: Callback when a suggestion is confirmed
        on_reject: Callback when a suggestion is rejected
        on_confirm_all: Callback to confirm all suggestions
        on_reject_all: Callback to reject all suggestions
    """
    # Filter to only show suggested (not yet actioned)
    pending_suggestions = [s for s in suggestions if s.status == "suggested"]
    
    if not pending_suggestions:
        with ui.card().classes("w-full p-4"):
            ui.label("No pending match suggestions").classes("text-slate-500")
        return
    
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between p-3 border-b"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("auto_fix_high", size="sm").style(f"color: {DBT_TEAL};")
                ui.label(f"Suggested Matches ({len(pending_suggestions)})").classes("font-semibold")
            
            with ui.row().classes("gap-2"):
                ui.button(
                    "Confirm All",
                    icon="check",
                    on_click=on_confirm_all,
                ).props("size=sm color=positive outline")
                ui.button(
                    "Reject All",
                    icon="close",
                    on_click=on_reject_all,
                ).props("size=sm color=negative outline")
        
        # Table
        with ui.element("div").classes("w-full overflow-x-auto"):
            with ui.element("table").classes("w-full"):
                # Header
                with ui.element("thead").classes("bg-slate-100 dark:bg-slate-800"):
                    with ui.element("tr"):
                        for header in ["Type", "Source Name", "→", "Target Name", "Target ID", "Actions"]:
                            with ui.element("th").classes("px-3 py-2 text-left text-sm font-medium"):
                                ui.label(header)
                
                # Body
                with ui.element("tbody"):
                    for suggestion in pending_suggestions:
                        with ui.element("tr").classes("border-b hover:bg-slate-50 dark:hover:bg-slate-800"):
                            # Type
                            with ui.element("td").classes("px-3 py-2"):
                                type_label = RESOURCE_TYPE_LABELS.get(
                                    suggestion.source_type, suggestion.source_type
                                )
                                ui.label(type_label).classes("text-sm")
                            
                            # Source name
                            with ui.element("td").classes("px-3 py-2"):
                                ui.label(suggestion.source_name).classes("text-sm font-mono")
                            
                            # Arrow
                            with ui.element("td").classes("px-3 py-2 text-center"):
                                ui.icon("arrow_forward", size="xs").classes("text-slate-400")
                            
                            # Target name
                            with ui.element("td").classes("px-3 py-2"):
                                ui.label(suggestion.target_name).classes("text-sm font-mono")
                            
                            # Target ID
                            with ui.element("td").classes("px-3 py-2"):
                                ui.label(str(suggestion.target_id)).classes("text-sm text-slate-500")
                            
                            # Actions
                            with ui.element("td").classes("px-3 py-2"):
                                with ui.row().classes("gap-1"):
                                    ui.button(
                                        icon="check",
                                        on_click=lambda s=suggestion: on_confirm(s),
                                    ).props("size=sm color=positive flat round")
                                    ui.button(
                                        icon="close",
                                        on_click=lambda s=suggestion: on_reject(s),
                                    ).props("size=sm color=negative flat round")


def create_confirmed_mappings_table(
    confirmed_mappings: list[dict],
    on_remove: Callable[[dict], None],
    on_edit: Callable[[dict], None],
) -> None:
    """Create the confirmed mappings table UI.
    
    Args:
        confirmed_mappings: List of confirmed mapping dictionaries
        on_remove: Callback to remove a mapping
        on_edit: Callback to edit a mapping
    """
    if not confirmed_mappings:
        with ui.card().classes("w-full p-4"):
            ui.label("No confirmed mappings yet").classes("text-slate-500")
        return
    
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between p-3 border-b"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("link", size="sm").style(f"color: {MATCH_GREEN};")
                ui.label(f"Confirmed Mappings ({len(confirmed_mappings)})").classes("font-semibold")
        
        # Table
        with ui.element("div").classes("w-full overflow-x-auto"):
            with ui.element("table").classes("w-full"):
                # Header
                with ui.element("thead").classes("bg-slate-100 dark:bg-slate-800"):
                    with ui.element("tr"):
                        for header in ["Type", "Source Name", "→", "Target Name", "Target ID", "Match", "Actions"]:
                            with ui.element("th").classes("px-3 py-2 text-left text-sm font-medium"):
                                ui.label(header)
                
                # Body
                with ui.element("tbody"):
                    for mapping in confirmed_mappings:
                        with ui.element("tr").classes("border-b hover:bg-slate-50 dark:hover:bg-slate-800"):
                            # Type
                            with ui.element("td").classes("px-3 py-2"):
                                type_label = RESOURCE_TYPE_LABELS.get(
                                    mapping.get("resource_type", ""), mapping.get("resource_type", "")
                                )
                                ui.label(type_label).classes("text-sm")
                            
                            # Source name
                            with ui.element("td").classes("px-3 py-2"):
                                ui.label(mapping.get("source_name", "")).classes("text-sm font-mono")
                            
                            # Arrow
                            with ui.element("td").classes("px-3 py-2 text-center"):
                                ui.icon("arrow_forward", size="xs").classes("text-slate-400")
                            
                            # Target name
                            with ui.element("td").classes("px-3 py-2"):
                                ui.label(mapping.get("target_name", "")).classes("text-sm font-mono")
                            
                            # Target ID
                            with ui.element("td").classes("px-3 py-2"):
                                ui.label(str(mapping.get("target_id", ""))).classes("text-sm text-slate-500")
                            
                            # Match type
                            with ui.element("td").classes("px-3 py-2"):
                                match_type = mapping.get("match_type", "auto")
                                badge_color = "positive" if match_type == "auto" else "primary"
                                ui.badge(match_type.title(), color=badge_color).props("dense")
                            
                            # Actions
                            with ui.element("td").classes("px-3 py-2"):
                                with ui.row().classes("gap-1"):
                                    ui.button(
                                        icon="edit",
                                        on_click=lambda m=mapping: on_edit(m),
                                    ).props("size=sm flat round")
                                    ui.button(
                                        icon="delete",
                                        on_click=lambda m=mapping: on_remove(m),
                                    ).props("size=sm color=negative flat round")


def create_manual_mapping_dialog(
    source_items: list[dict],
    target_items: list[dict],
    on_save: Callable[[dict], None],
    existing_mapping: Optional[dict] = None,
) -> ui.dialog:
    """Create a dialog for manually mapping a source to target resource.
    
    Args:
        source_items: Unmatched source items to choose from
        target_items: Unmatched target items to choose from
        on_save: Callback when mapping is saved
        existing_mapping: Optional existing mapping to edit
        
    Returns:
        The dialog element
    """
    dialog = ui.dialog()
    
    with dialog, ui.card().classes("w-[600px]"):
        ui.label("Manual Resource Mapping").classes("text-lg font-semibold mb-4")
        
        # State for selections
        selected_source = {"value": existing_mapping.get("source_key") if existing_mapping else None}
        selected_target = {"value": existing_mapping.get("target_id") if existing_mapping else None}
        selected_type = {"value": existing_mapping.get("resource_type") if existing_mapping else None}
        
        # Type filter
        type_options = sorted(set(item.get("element_type_code", "") for item in source_items))
        type_labels = [RESOURCE_TYPE_LABELS.get(t, t) for t in type_options]
        
        def on_type_change(e):
            selected_type["value"] = type_options[type_labels.index(e.value)] if e.value else None
        
        ui.select(
            label="Resource Type",
            options=type_labels,
            on_change=on_type_change,
        ).classes("w-full mb-4")
        
        # Source selector
        def get_source_options():
            if not selected_type["value"]:
                return []
            return [
                {"label": f"{item.get('name', '')} ({item.get('key', '')})", "value": item.get("key")}
                for item in source_items
                if item.get("element_type_code") == selected_type["value"]
            ]
        
        ui.select(
            label="Source Resource",
            options=[],
        ).classes("w-full mb-4")
        
        # Target selector
        def get_target_options():
            if not selected_type["value"]:
                return []
            return [
                {"label": f"{item.get('name', '')} (ID: {item.get('dbt_id', '')})", "value": item.get("dbt_id")}
                for item in target_items
                if item.get("element_type_code") == selected_type["value"]
            ]
        
        ui.select(
            label="Target Resource",
            options=[],
        ).classes("w-full mb-4")
        
        # Buttons
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            
            def save_mapping():
                if not selected_source["value"] or not selected_target["value"]:
                    ui.notify("Please select both source and target", type="warning")
                    return
                
                # Find the source and target items
                source_item = next(
                    (i for i in source_items if i.get("key") == selected_source["value"]),
                    None
                )
                target_item = next(
                    (i for i in target_items if i.get("dbt_id") == selected_target["value"]),
                    None
                )
                
                if source_item and target_item:
                    mapping = {
                        "resource_type": source_item.get("element_type_code", ""),
                        "source_name": source_item.get("name", ""),
                        "source_key": source_item.get("key", ""),
                        "target_id": target_item.get("dbt_id", 0),
                        "target_name": target_item.get("name", ""),
                        "match_type": "manual",
                    }
                    on_save(mapping)
                    dialog.close()
            
            ui.button("Save Mapping", on_click=save_mapping).props("color=primary")
    
    return dialog
