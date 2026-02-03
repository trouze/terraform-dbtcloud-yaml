"""Utilities page for protection intent management and advanced tools."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from importer.web.state import AppState, WorkflowStep


def create_utilities_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Optional[Callable[[], None]] = None,
) -> None:
    """Create the utilities page content.
    
    Args:
        state: Current application state
        on_step_change: Callback to navigate to a step
        save_state: Callback to persist state changes
    """
    with ui.column().classes("w-full max-w-6xl mx-auto p-8 gap-6"):
        # Page header
        with ui.row().classes("w-full items-center gap-3 mb-4"):
            ui.icon("build", size="lg").classes("text-slate-600")
            ui.label("Utilities").classes("text-2xl font-bold")
        
        # Protection Management Section
        _create_protection_management_section(state, save_state)


def _create_protection_management_section(
    state: AppState,
    save_state: Optional[Callable[[], None]] = None,
) -> None:
    """Create the protection management section."""
    
    # Get protection intent manager
    protection_intent = state.get_protection_intent_manager()
    
    # Calculate counts
    pending_generate = len(protection_intent.get_pending_yaml_updates())
    pending_tf = sum(
        1 for intent in protection_intent._intent.values()
        if intent.applied_to_yaml and not intent.applied_to_tf_state
    )
    synced = sum(
        1 for intent in protection_intent._intent.values()
        if intent.applied_to_yaml and intent.applied_to_tf_state
    )
    total_intents = protection_intent.intent_count
    
    with ui.card().classes("w-full p-6"):
        with ui.row().classes("w-full items-center gap-2 mb-4"):
            ui.icon("shield", size="md").classes("text-slate-600")
            ui.label("Protection Management").classes("text-xl font-semibold")
        
        # Status Summary Cards
        with ui.row().classes("w-full gap-4 mb-6"):
            # Pending Generate card
            with ui.card().classes("flex-1 p-4").style("border: 2px solid #F59E0B;"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("pending_actions", size="sm").classes("text-amber-600")
                    ui.label("Pending Generate").classes("font-semibold text-amber-600")
                ui.label(str(pending_generate)).classes("text-3xl font-bold text-amber-700 mt-2")
                ui.label("Need YAML updates").classes("text-xs text-slate-500")
            
            # Pending TF Apply card
            with ui.card().classes("flex-1 p-4").style("border: 2px solid #3B82F6;"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("cloud_sync", size="sm").classes("text-blue-600")
                    ui.label("Pending TF Apply").classes("font-semibold text-blue-600")
                ui.label(str(pending_tf)).classes("text-3xl font-bold text-blue-700 mt-2")
                ui.label("Need terraform apply").classes("text-xs text-slate-500")
            
            # Synced card
            with ui.card().classes("flex-1 p-4").style("border: 2px solid #10B981;"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("check_circle", size="sm").classes("text-green-600")
                    ui.label("Synced").classes("font-semibold text-green-600")
                ui.label(str(synced)).classes("text-3xl font-bold text-green-700 mt-2")
                ui.label("Fully applied").classes("text-xs text-slate-500")
        
        # Filters and Search
        filter_state = {"status": "all", "type": "all", "search": ""}
        
        with ui.row().classes("w-full gap-4 mb-4 items-end"):
            # Status filter
            status_select = ui.select(
                label="Status",
                options=[
                    {"label": "All Status", "value": "all"},
                    {"label": "Pending Generate", "value": "pending_generate"},
                    {"label": "Pending TF Apply", "value": "pending_tf"},
                    {"label": "Synced", "value": "synced"},
                ],
                value="all",
                on_change=lambda e: _update_filter(filter_state, "status", e.value, grid_ref),
            ).props("dense outlined").classes("w-40")
            
            # Type filter
            type_options = [{"label": "All Types", "value": "all"}]
            unique_types = set()
            for key in protection_intent._intent.keys():
                # Extract type from key (e.g., "PRJ:myproject" -> "PRJ")
                if ":" in key:
                    rtype = key.split(":")[0]
                else:
                    rtype = "UNKNOWN"
                unique_types.add(rtype)
            for t in sorted(unique_types):
                type_options.append({"label": t, "value": t})
            
            type_select = ui.select(
                label="Type",
                options=type_options,
                value="all",
                on_change=lambda e: _update_filter(filter_state, "type", e.value, grid_ref),
            ).props("dense outlined").classes("w-32")
            
            # Search input
            search_input = ui.input(
                label="Search Resource Key",
                placeholder="Type to filter...",
                on_change=lambda e: _update_filter(filter_state, "search", e.value, grid_ref),
            ).props("dense outlined clearable").classes("flex-grow")
            
            # Showing count
            showing_label = ui.label(f"Showing: {total_intents}/{total_intents}").classes("text-sm text-slate-500")
        
        # Bulk Action Buttons
        with ui.row().classes("w-full gap-2 mb-4"):
            def reset_all_to_yaml():
                """Reset all intents, falling back to YAML flags."""
                async def do_reset():
                    dialog = ui.dialog()
                    confirmed = {"value": False}
                    
                    with dialog:
                        with ui.card().classes("p-4"):
                            ui.label("Reset All to YAML").classes("text-lg font-semibold mb-2")
                            ui.label("This will clear all intent history. Protection status will fall back to YAML configuration.").classes("text-sm text-slate-500 mb-4")
                            
                            with ui.row().classes("gap-2 justify-end"):
                                ui.button("Cancel", on_click=dialog.close).props("flat")
                                
                                def confirm_reset():
                                    confirmed["value"] = True
                                    dialog.close()
                                
                                ui.button("Reset All", on_click=confirm_reset).props("color=red")
                    
                    dialog.open()
                    await dialog
                    
                    if confirmed["value"]:
                        protection_intent._intent.clear()
                        protection_intent._history.clear()
                        protection_intent.save()
                        ui.notify("All intents reset to YAML defaults", type="positive")
                        ui.navigate.reload()
                
                asyncio.create_task(do_reset())
            
            ui.button(
                "Reset All to YAML",
                icon="restart_alt",
                on_click=reset_all_to_yaml,
            ).props("outline color=red").tooltip("Clear all intents, fall back to YAML flags")
            
            def sync_from_tf_state():
                """Sync intents from current TF state."""
                ui.notify("Sync from TF State: Feature coming soon", type="info")
            
            ui.button(
                "Sync from TF State",
                icon="cloud_download",
                on_click=sync_from_tf_state,
            ).props("outline").tooltip("Read TF state and set intents to match current reality")
            
            async def generate_all_pending():
                """Process all pending-generate intents at once."""
                pending = protection_intent.get_pending_yaml_updates()
                if not pending:
                    ui.notify("No pending intents to generate", type="warning")
                    return
                
                # Reuse the same logic from match.py's generate_protection_changes
                from pathlib import Path
                
                tf_dir = state.deploy.terraform_dir or "deployments/migration"
                tf_path = Path(tf_dir)
                if not tf_path.is_absolute():
                    project_root = Path(__file__).parent.parent.parent.resolve()
                    tf_path = project_root / tf_dir
                
                yaml_file = tf_path / "dbt-cloud-config.yml"
                if not yaml_file.exists():
                    ui.notify(f"YAML file not found: {yaml_file}", type="negative")
                    return
                
                from importer.web.utils.adoption_yaml_updater import apply_protection_from_set, apply_unprotection_from_set
                
                keys_to_protect = {k for k, i in pending.items() if i.protected}
                keys_to_unprotect = {k for k, i in pending.items() if not i.protected}
                
                if keys_to_protect:
                    apply_protection_from_set(str(yaml_file), keys_to_protect)
                if keys_to_unprotect:
                    apply_unprotection_from_set(str(yaml_file), keys_to_unprotect)
                
                protection_intent.mark_applied_to_yaml(set(pending.keys()))
                protection_intent.save()
                
                ui.notify(f"Generated protection changes for {len(pending)} resources", type="positive")
                ui.navigate.reload()
            
            generate_btn = ui.button(
                f"Generate All Pending ({pending_generate})" if pending_generate > 0 else "Generate All Pending",
                icon="auto_fix_high",
                on_click=lambda: asyncio.create_task(generate_all_pending()),
            ).props("color=green")
            generate_btn.set_enabled(pending_generate > 0)
            
            def export_json():
                """Download protection-intent.json."""
                intent_data = {
                    "intent": {k: v.__dict__ for k, v in protection_intent._intent.items()},
                    "history": [h.__dict__ for h in protection_intent._history],
                }
                json_str = json.dumps(intent_data, indent=2, default=str)
                ui.download(json_str.encode(), "protection-intent.json")
                ui.notify("Exported protection-intent.json", type="positive")
            
            ui.button(
                "Export JSON",
                icon="download",
                on_click=export_json,
            ).props("outline").tooltip("Download protection-intent.json")
        
        # AG Grid for Current Intents
        if total_intents > 0:
            # Build row data
            row_data = []
            for key, intent in protection_intent._intent.items():
                # Extract type from key
                if ":" in key:
                    rtype = key.split(":")[0]
                else:
                    rtype = "UNKNOWN"
                
                # Determine status
                if not intent.applied_to_yaml:
                    status = "Pending Generate"
                    status_class = "bg-amber-100 text-amber-800"
                elif not intent.applied_to_tf_state:
                    status = "Pending TF Apply"
                    status_class = "bg-blue-100 text-blue-800"
                else:
                    status = "Synced"
                    status_class = "bg-green-100 text-green-800"
                
                row_data.append({
                    "resource_key": key,
                    "type": rtype,
                    "intent": "Protect" if intent.protected else "Unprotect",
                    "status": status,
                    "status_class": status_class,
                    "set_at": intent.set_at[:19].replace("T", " ") if intent.set_at else "",
                    "intent_obj": intent,
                })
            
            # Pre-sort by set_at descending
            row_data.sort(key=lambda r: r.get("set_at", ""), reverse=True)
            
            # Column definitions with explicit colId
            column_defs = [
                {"field": "resource_key", "colId": "resource_key", "headerName": "Resource Key", "flex": 2, "checkboxSelection": True, "headerCheckboxSelection": True},
                {"field": "type", "colId": "type", "headerName": "Type", "width": 80},
                {"field": "intent", "colId": "intent", "headerName": "Intent", "width": 100},
                {"field": "status", "colId": "status", "headerName": "Status", "width": 140},
                {"field": "set_at", "colId": "set_at", "headerName": "Set At", "width": 160},
                {"field": "actions", "colId": "actions", "headerName": "Actions", "width": 100, "cellRenderer": "agGroupCellRenderer"},
            ]
            
            # Store grid reference for filtering
            grid_ref = {"grid": None}
            
            grid = ui.aggrid({
                "columnDefs": column_defs,
                "rowData": row_data,
                "rowSelection": "multiple",
                "defaultColDef": {
                    "sortable": True,
                    "resizable": True,
                },
                "pagination": True,
                "paginationPageSize": 20,
            }, theme="quartz").classes("w-full ag-theme-quartz-auto-dark").style("height: 400px;")
            
            grid_ref["grid"] = grid
            
            # Add custom slot for edit button
            grid.add_slot("body-cell-actions", '''
                <q-td :props="props">
                    <q-btn flat dense icon="edit" size="sm" @click="$parent.$emit('edit-intent', props.row)" />
                </q-td>
            ''')
            
            def handle_edit(row):
                """Open edit dialog for an intent."""
                key = row.get("resource_key", "")
                intent = protection_intent._intent.get(key)
                if not intent:
                    ui.notify(f"Intent not found: {key}", type="warning")
                    return
                
                dialog = ui.dialog()
                new_protected = {"value": intent.protected}
                new_reason = {"value": ""}
                
                with dialog:
                    with ui.card().classes("p-4").style("width: 500px;"):
                        ui.label("Edit Protection Intent").classes("text-lg font-semibold mb-4")
                        
                        # Resource Key (readonly)
                        ui.input(
                            label="Resource Key",
                            value=key,
                        ).props("dense outlined readonly").classes("w-full mb-4")
                        
                        # Intent toggle
                        with ui.row().classes("w-full items-center gap-4 mb-4"):
                            ui.label("Protection Intent:").classes("font-medium")
                            ui.toggle(
                                {True: "Protect", False: "Unprotect"},
                                value=intent.protected,
                                on_change=lambda e: new_protected.update({"value": e.value}),
                            )
                        
                        # Reason input
                        ui.input(
                            label="Reason (optional)",
                            placeholder="Why are you changing this?",
                            on_change=lambda e: new_reason.update({"value": e.value}),
                        ).props("dense outlined").classes("w-full mb-4")
                        
                        # Buttons
                        with ui.row().classes("w-full gap-2 justify-end"):
                            ui.button("Cancel", on_click=dialog.close).props("flat")
                            
                            def save_changes():
                                protection_intent.set_intent(
                                    key=key,
                                    protected=new_protected["value"],
                                    source="utilities_edit",
                                    reason=new_reason["value"] or "Edited via Utilities page",
                                )
                                protection_intent.save()
                                dialog.close()
                                ui.notify(f"Updated intent for {key}", type="positive")
                                ui.navigate.reload()
                            
                            ui.button("Save", on_click=save_changes).props("color=primary")
                
                dialog.open()
            
            grid.on("edit-intent", lambda e: handle_edit(e.args))
        else:
            with ui.card().classes("w-full p-6 text-center"):
                ui.icon("inbox", size="xl").classes("text-slate-300 mb-2")
                ui.label("No protection intents recorded").classes("text-lg text-slate-500")
                ui.label("Click Protect/Unprotect on the Match page to record intents").classes("text-sm text-slate-400")
        
        ui.separator().classes("my-6")
        
        # Audit History Section
        _create_audit_history_section(protection_intent)


def _create_audit_history_section(protection_intent) -> None:
    """Create the audit history section."""
    history = protection_intent._history
    
    with ui.row().classes("w-full items-center justify-between mb-4"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("history", size="md").classes("text-slate-600")
            ui.label(f"Audit History (last 20 of {len(history)})").classes("text-lg font-semibold")
        
        def copy_history():
            """Copy history to clipboard."""
            lines = []
            for entry in reversed(history):
                ts = entry.timestamp[:19].replace("T", " ") if entry.timestamp else ""
                lines.append(f"{ts} | {entry.resource_key} | {entry.action} | {entry.source}")
            text = "\n".join(lines)
            ui.run_javascript(f'navigator.clipboard.writeText({repr(text)})')
            ui.notify("Copied history to clipboard!", type="positive")
        
        ui.button(
            "Copy History",
            icon="content_copy",
            on_click=copy_history,
        ).props("flat dense")
    
    if history:
        # Show last 20 entries (newest first)
        recent_history = list(reversed(history[-20:]))
        
        # Build table data
        table_data = []
        for entry in recent_history:
            ts = entry.timestamp[:19].replace("T", " ") if entry.timestamp else ""
            table_data.append({
                "timestamp": ts,
                "resource": entry.resource_key,
                "action": entry.action,
                "source": entry.source,
            })
        
        columns = [
            {"name": "timestamp", "label": "Timestamp", "field": "timestamp", "align": "left"},
            {"name": "resource", "label": "Resource", "field": "resource", "align": "left"},
            {"name": "action", "label": "Action", "field": "action", "align": "left"},
            {"name": "source", "label": "Source", "field": "source", "align": "left"},
        ]
        
        table = ui.table(columns=columns, rows=table_data, row_key="timestamp").classes("w-full")
        
        # View All link
        if len(history) > 20:
            def view_all_history():
                """Show full history in a dialog."""
                dialog = ui.dialog()
                with dialog:
                    with ui.card().classes("p-4").style("width: 900px; max-width: 95vw; max-height: 90vh; overflow-y: auto;"):
                        ui.label(f"Full Audit History ({len(history)} entries)").classes("text-lg font-semibold mb-4")
                        
                        all_data = []
                        for entry in reversed(history):
                            ts = entry.timestamp[:19].replace("T", " ") if entry.timestamp else ""
                            all_data.append({
                                "timestamp": ts,
                                "resource": entry.resource_key,
                                "action": entry.action,
                                "source": entry.source,
                            })
                        
                        ui.table(columns=columns, rows=all_data, row_key="timestamp").classes("w-full")
                        
                        ui.button("Close", on_click=dialog.close).props("flat").classes("mt-4")
                
                dialog.open()
            
            ui.label(f"View all {len(history)} entries →").classes(
                "text-sm text-blue-600 cursor-pointer hover:underline mt-2"
            ).on("click", view_all_history)
    else:
        with ui.card().classes("w-full p-4 text-center"):
            ui.icon("history", size="lg").classes("text-slate-300 mb-2")
            ui.label("No history recorded yet").classes("text-slate-500")


def _update_filter(filter_state: dict, key: str, value: str, grid_ref: dict) -> None:
    """Update filter state and refresh grid."""
    filter_state[key] = value
    grid = grid_ref.get("grid")
    if grid:
        # Use AG Grid's built-in filtering
        # For now, just notify about filtering (full implementation would use quick filter)
        ui.notify(f"Filter updated: {key}={value}", type="info")
