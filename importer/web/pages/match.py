"""Match step page - match source resources to existing target resources."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from nicegui import ui

from importer.web.state import AppState, WorkflowStep
from importer.web.components.selection_manager import SelectionManager
from importer.web.utils.mapping_file import (
    save_mapping_file,
    create_mapping_from_confirmations,
)
from importer.web.utils.yaml_viewer import create_yaml_viewer_dialog
from importer.web.utils.terraform_state_reader import read_terraform_state, StateReadResult
from importer.web.utils.target_intent import (
    TargetIntentResult,
    MatchMappings,
    StateToTargetMapping,
    compute_target_intent,
    build_included_globals,
    normalize_target_fetch,
    get_tf_state_project_keys,
    validate_intent_coverage,
)
from importer.web.utils.terraform_import import (
    generate_adopt_imports_from_grid,
    generate_state_rm_commands,
    generate_adoption_script,
    write_adopt_imports_file,
)
from importer.web.utils.protection_manager import (
    get_resources_to_protect,
    get_resources_to_unprotect,
    get_resource_address,
    CascadeResource,
    check_single_resource_protection,
    EXTENDED_RESOURCE_TYPE_MAP,
    generate_repair_moved_blocks,
)
from importer.web.components.hierarchy_index import HierarchyIndex
from importer.web.pages.deploy import _get_terraform_env

if TYPE_CHECKING:
    from importer.web.utils.terraform_state_reader import StateReadResult


# dbt brand colors
DBT_ORANGE = "#FF694A"
DBT_TEAL = "#047377"


def create_match_page(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
) -> None:
    """Create the Match step page for source-to-target resource matching."""
    
    with ui.element("div").classes("w-full max-w-7xl mx-auto p-4").style(
        "display: grid; "
        "grid-template-rows: auto 1fr auto; "
        "height: calc(100vh - 100px); "
        "gap: 8px; "
        "overflow: hidden;"
    ):
        # Row 1: Header
        _create_header(state)
        
        # Check prerequisites
        if not state.map.normalize_complete:
            _create_prerequisite_message(
                "Source Scope Required",
                "Complete the Scope step to normalize source resources first.",
                "Go to Scope",
                WorkflowStep.SCOPE,
                on_step_change,
            )
            return
        
        if not state.target_fetch.fetch_complete:
            _create_prerequisite_message(
                "Target Fetch Required", 
                "Fetch the target account data to match existing resources.",
                "Go to Fetch Target",
                WorkflowStep.FETCH_TARGET,
                on_step_change,
            )
            return
        
        # Load source and target report items
        all_source_items = _load_report_items(state, target=False)
        target_items = _load_report_items(state, target=True)
        
        if not all_source_items:
            _create_no_data_message("No source data available", on_step_change)
            return
        
        if not target_items:
            _create_no_data_message("No target data available", on_step_change)
            return
        
        # Filter source items by selection from Select Source step
        selection_manager = SelectionManager(
            account_id=state.source_account.account_id or "unknown",
            base_url=state.source_account.host_url,
        )
        selection_manager.load()
        selected_ids = selection_manager.get_selected_ids()
        
        # Filter to only selected items
        source_items = [
            item for item in all_source_items 
            if item.get("element_mapping_id") in selected_ids
        ]
        
        total_source_count = len(all_source_items)
        len(source_items)
        
        if not source_items:
            _create_no_selected_message(
                total_source_count,
                on_step_change,
            )
            return
        
        # Row 2: Main content - flex container that allows grid to grow
        # Note: Navigation is created inside _create_matching_content so it has access
        # to the grid data for accurate status display
        with ui.element("div").classes("flex flex-col flex-nowrap").style(
            "width: 100%; height: 100%; overflow: auto; display: flex; flex-direction: column; flex-wrap: nowrap;"
        ):
            _create_matching_content(
                state, 
                source_items, 
                target_items, 
                save_state, 
                total_source_count,
                on_step_change,
            )


def _create_header(state: AppState) -> None:
    """Create the page header."""
    with ui.card().classes("w-full p-4"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("assignment", size="md").style(f"color: {DBT_TEAL};")
                    ui.label("Set Target Intent").classes("text-2xl font-bold")
                
                ui.label(
                    "Define what Terraform should manage: match, adopt, protect, and remove resources"
                ).classes("text-slate-600 dark:text-slate-400")
            
            # Show both account details with ID and URL
            with ui.row().classes("gap-4"):
                if state.fetch.account_name or state.source_account.account_id:
                    with ui.card().classes("p-2"):
                        ui.label("Source").classes("text-xs text-slate-500 font-semibold")
                        ui.label(state.fetch.account_name or "Unknown").classes("font-medium text-sm")
                        with ui.column().classes("gap-0 mt-1"):
                            if state.source_account.account_id:
                                ui.label(f"ID: {state.source_account.account_id}").classes("text-xs text-slate-400 font-mono")
                            if state.source_account.host_url:
                                ui.label(state.source_account.host_url).classes("text-xs text-slate-400 font-mono")
                
                ui.icon("arrow_forward").classes("text-slate-400 self-center")
                
                if state.target_fetch.account_name or state.target_account.account_id:
                    with ui.card().classes("p-2").style(f"border: 1px solid {DBT_TEAL};"):
                        ui.label("Target").classes("text-xs text-slate-500 font-semibold")
                        ui.label(state.target_fetch.account_name or "Unknown").classes("font-medium text-sm")
                        with ui.column().classes("gap-0 mt-1"):
                            if state.target_account.account_id:
                                ui.label(f"ID: {state.target_account.account_id}").classes("text-xs text-slate-400 font-mono")
                            if state.target_account.host_url:
                                ui.label(state.target_account.host_url).classes("text-xs text-slate-400 font-mono")


def _create_prerequisite_message(
    title: str,
    message: str,
    button_text: str,
    target_step: WorkflowStep,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Show message when prerequisites are not met."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("warning", size="3rem").classes("text-amber-500 mx-auto")
        ui.label(title).classes("text-xl font-bold mt-4")
        ui.label(message).classes("text-slate-600 dark:text-slate-400 mt-2")
        ui.button(
            button_text,
            icon="arrow_back",
            on_click=lambda: on_step_change(target_step),
        ).classes("mt-4").style(f"background-color: {DBT_TEAL};")


def _create_no_data_message(message: str, on_step_change: Callable[[WorkflowStep], None]) -> None:
    """Show message when data is missing."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("error_outline", size="3rem").classes("text-red-500 mx-auto")
        ui.label(message).classes("text-xl font-bold mt-4")


def _create_no_selected_message(
    total_count: int,
    on_step_change: Callable[[WorkflowStep], None],
) -> None:
    """Show message when no items are selected."""
    with ui.card().classes("w-full p-8 text-center"):
        ui.icon("filter_list_off", size="3rem").classes("text-amber-500 mx-auto")
        ui.label("No Resources Selected").classes("text-xl font-bold mt-4")
        ui.label(
            f"{total_count} resources are available, but none are selected for matching."
        ).classes("text-slate-600 dark:text-slate-400 mt-2")
        ui.label(
            "Go to Select Source to choose which resources to include."
        ).classes("text-slate-500 dark:text-slate-400")
        ui.button(
            "Adjust Selection",
            icon="tune",
            on_click=lambda: on_step_change(WorkflowStep.SCOPE),
        ).classes("mt-4")


def _load_report_items(state: AppState, target: bool = False) -> list:
    """Load report items from source or target fetch."""
    if target:
        report_file = state.target_fetch.last_report_items_file
    else:
        report_file = state.fetch.last_report_items_file
    
    if not report_file:
        return []
    
    try:
        report_path = Path(report_file)
        if report_path.exists():
            return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        logging.warning(f"Error loading report items: {e}")
    
    return []


def _persist_target_intent_from_match(
    state: AppState,
    state_to_target: Optional[list] = None,
) -> None:
    """Compute and persist the full target intent from Match page data.

    This is the primary entry point for building the authoritative target-intent.json.
    It normalizes target fetch data (lazily), computes dispositions + output_config +
    protection via priority chain, merges match_mappings, and saves everything.
    """
    logger = logging.getLogger(__name__)
    manager = state.get_target_intent_manager()
    previous_intent = manager.load()

    # Build match_mappings from current grid state
    new_mm = MatchMappings.from_confirmed_mappings(state.map.confirmed_mappings)
    if state_to_target is not None:
        if all(isinstance(x, dict) for x in state_to_target):
            new_mm.state_to_target = [StateToTargetMapping.from_dict(x) for x in state_to_target]
        else:
            new_mm.state_to_target = list(state_to_target)
    elif previous_intent and previous_intent.match_mappings.state_to_target:
        new_mm.state_to_target = list(previous_intent.match_mappings.state_to_target)

    # Gather inputs for compute_target_intent
    tf_dir = state.deploy.terraform_dir or "deployments/migration"
    tf_path = Path(tf_dir)
    if not tf_path.is_absolute():
        # match.py is at importer/web/pages/match.py — 4 levels to project root
        project_root = Path(__file__).parent.parent.parent.parent.resolve()
        tf_path = project_root / tf_dir
    tfstate_path = tf_path / "terraform.tfstate"

    source_focus_yaml = getattr(state.map, "last_yaml_file", None)
    removal_keys = set(getattr(state.map, "removal_keys", None) or [])
    adopt_rows = getattr(state.deploy, "reconcile_adopt_rows", []) or []

    # Load target report items
    target_report_items = None
    if getattr(state, "target_fetch", None) and getattr(state.target_fetch, "last_report_items_file", None):
        _tr_path = Path(state.target_fetch.last_report_items_file)
        if _tr_path.exists():
            try:
                with open(_tr_path, "r") as f:
                    target_report_items = json.load(f)
            except Exception:
                pass

    # Normalize target fetch to get baseline YAML (lazy, cached)
    baseline_yaml = normalize_target_fetch(state)
    # Also check for existing dbt-cloud-config.yml as alternative baseline
    existing_yaml_path = tf_path / "dbt-cloud-config.yml"
    if not baseline_yaml and existing_yaml_path.exists():
        baseline_yaml = str(existing_yaml_path)

    # Get protection intent manager for priority chain
    protection_intent_mgr = None
    try:
        protection_intent_mgr = state.get_protection_intent_manager()
    except Exception:
        pass

    # Build included_globals from user selections + TF state safety net
    included_globals = build_included_globals(state)

    # Compute full target intent
    try:
        intent = compute_target_intent(
            tfstate_path=tfstate_path,
            source_focus_yaml=source_focus_yaml,
            baseline_yaml=baseline_yaml,
            target_report_items=target_report_items,
            adopt_rows=adopt_rows,
            removal_keys=removal_keys,
            previous_intent=previous_intent,
            protection_intent_manager=protection_intent_mgr,
            included_globals=included_globals,
        )
        # Override match_mappings with current grid state
        intent.match_mappings = new_mm
        logger.info(
            f"Computed target intent: {len(intent.retained_keys)} retained, "
            f"{len(intent.upserted_keys)} upserted, "
            f"{len(intent.adopted_keys)} adopted, "
            f"{len(intent.removed_keys)} removed"
        )
    except Exception as e:
        logger.warning(f"Failed to compute full target intent: {e}")
        # Fallback: save match_mappings only (backward compat)
        intent = previous_intent if previous_intent else TargetIntentResult(version=2)
        intent.match_mappings = new_mm

    state.save_target_intent(intent)


def _create_matching_content(
    state: AppState,
    source_items: list,
    target_items: list,
    save_state: Callable[[], None],
    total_source_count: int = 0,
    on_step_change: Optional[Callable[[WorkflowStep], None]] = None,
) -> None:
    """Create the main matching interface with editable grid."""
    from importer.web.components.match_grid import (
        build_grid_data,
        create_match_grid,
        create_grid_toolbar,
        export_mappings_to_csv,
        DRIFT_ID_MISMATCH,
        DRIFT_NOT_IN_STATE,
        DRIFT_ATTR_MISMATCH,
        NAME_KEYED_TYPES,
        PROJECT_SCOPED_TYPES,
    )
    from importer.web.components.clone_dialog import show_clone_dialog
    from importer.web.state import CloneConfig
    
    # Mutable container for state result (shared across callbacks)
    state_ref = {
        "state_result": None,
        "state_loaded": state.deploy.reconcile_state_loaded,
    }
    
    # Store target_items for callbacks (since it's a local variable)
    target_items_ref = {"items": target_items}

    # Load persistent target intent and seed confirmed_mappings from it (source of truth)
    try:
        intent = state.get_target_intent_manager().load()
        if intent and intent.match_mappings.source_to_target:
            state.map.confirmed_mappings = intent.match_mappings.to_confirmed_mappings()
    except Exception as e:
        logging.warning(f"Could not load target intent for match page: {e}")

    # Build hierarchy index for parent/child lookups (used for protection cascade)
    hierarchy_index = HierarchyIndex(source_items)
    
    # Try to restore state result if previously loaded
    # (We store serialized state in reconcile_state_resources)
    if state.deploy.reconcile_state_loaded and state.deploy.reconcile_state_resources:
        # Reconstruct a minimal StateReadResult from saved data
        import re
        from importer.web.utils.terraform_state_reader import StateReadResult, StateResource
        state_result = StateReadResult(success=True)
        for res_data in state.deploy.reconcile_state_resources:
            # Get resource_index from cached data, or extract from address as fallback
            resource_index = res_data.get("resource_index")
            address = res_data.get("address", "")
            if resource_index is None and address and "[" in address:
                # Extract index from address like: resource.name["key"] or resource.name[0]
                match = re.search(r'\["([^"]+)"\]$', address)
                if match:
                    resource_index = match.group(1)
                else:
                    match = re.search(r'\[(\d+)\]$', address)
                    if match:
                        resource_index = match.group(1)
            
            resource = StateResource(
                address=address,
                tf_type=res_data.get("tf_type", ""),
                element_code=res_data.get("element_code", ""),
                tf_name=res_data.get("tf_name", ""),
                dbt_id=res_data.get("dbt_id"),
                name=res_data.get("name"),
                project_id=res_data.get("project_id"),
                attributes=res_data.get("attributes", {}),
                resource_index=resource_index,
            )
            state_result.resources.append(resource)
            if resource.dbt_id is not None:
                state_result.resources_by_id[(resource.element_code, resource.dbt_id)] = resource
        state_ref["state_result"] = state_result
    
    # Build grid data from source/target items and existing mappings
    rejected_keys = state.map.rejected_suggestions if isinstance(state.map.rejected_suggestions, set) else set(state.map.rejected_suggestions)
    clone_configs = getattr(state.map, "cloned_resources", [])
    
    # Get protection intent manager for effective protection lookup
    protection_intent_manager = state.get_protection_intent_manager()
    
    grid_row_data = build_grid_data(
        source_items,
        target_items,
        state.map.confirmed_mappings,
        rejected_keys,
        clone_configs,
        state_result=state_ref["state_result"],
        protected_resources=state.map.protected_resources,
        protection_intent_manager=protection_intent_manager,
    )
    
    # Stats from grid data - separate primary resources from derived resources
    # Derived resource types: JEVO (env var overrides), JCTG (job triggers), PREP (project repo links)
    derived_types = {"JEVO", "JCTG", "PREP"}
    primary_rows = [r for r in grid_row_data if r.get("source_type") not in derived_types]
    derived_rows = [r for r in grid_row_data if r.get("source_type") in derived_types]
    
    pending = sum(1 for r in primary_rows if r.get("status") == "pending" and r.get("action") == "match")
    confirmed = sum(1 for r in primary_rows if r.get("status") == "confirmed")
    create_new_primary = sum(1 for r in primary_rows if r.get("action") == "create_new")
    create_new_derived = len(derived_rows)  # All derived resources are create_new
    create_new_total = create_new_primary + create_new_derived
    skipped = sum(1 for r in primary_rows if r.get("action") == "skip")
    adopted = sum(1 for r in primary_rows if r.get("action") == "adopt")
    unadopted = sum(1 for r in primary_rows if r.get("action") == "unadopt")
    
    # Total rows in grid including overrides
    total_grid_rows = len(grid_row_data)
    
    # Stat cards with selection info
    with ui.row().classes("w-full gap-4 mb-4 items-center"):
        _create_stat_card("Pending", pending, "text-amber-600", "hourglass_empty")
        _create_stat_card("Confirmed", confirmed, "text-green-600", "check_circle")
        
        # Create New card - show total with breakdown if overrides exist
        with ui.card().classes("p-3 min-w-[100px]"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("add_circle", size="sm").classes("text-orange-500")
                ui.label(str(create_new_total)).classes("text-2xl font-bold text-orange-500")
            ui.label("Create New").classes("text-xs text-slate-500")
            if create_new_derived > 0:
                ui.label(f"({create_new_primary} + {create_new_derived} derived)").classes(
                    "text-xs text-orange-400"
                )
        
        _create_stat_card("Skip", skipped, "text-slate-500", "block")
        if adopted > 0:
            _create_stat_card("Adopted", adopted, "text-teal-600", "link")
        _create_stat_card("Unadopt", unadopted, "text-purple-500", "link_off")
        
        # Selected source items with total count - shows primary resources + overrides
        with ui.card().classes("p-3 min-w-[120px]"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("upload", size="sm").classes("text-blue-600")
                ui.label(f"{total_grid_rows} of {total_source_count + create_new_derived}").classes(
                    "text-2xl font-bold text-blue-600"
                )
            with ui.row().classes("items-center gap-2"):
                ui.label("Total Resources").classes("text-xs text-slate-500")
                if on_step_change and total_source_count > len(source_items):
                    ui.button(
                        "Adjust",
                        icon="tune",
                        on_click=lambda: on_step_change(WorkflowStep.SCOPE),
                    ).props("flat dense size=xs")
            if create_new_derived > 0:
                ui.label(f"({len(source_items)} selected + {create_new_derived} derived)").classes(
                    "text-xs text-blue-400"
                )
        
        _create_stat_card("Existing Target Items", len(target_items), f"color: {DBT_TEAL}", "download")
        
        # Drift stats (only show if state is loaded)
        drift_count = sum(
            1 for r in grid_row_data 
            if r.get("drift_status") in [DRIFT_ID_MISMATCH, DRIFT_NOT_IN_STATE, DRIFT_ATTR_MISMATCH]
        )
        if state_ref["state_loaded"]:
            with ui.card().classes("p-3 min-w-[100px]"):
                with ui.row().classes("items-center gap-2"):
                    if drift_count > 0:
                        ui.icon("warning", size="sm").classes("text-amber-500")
                        ui.label(str(drift_count)).classes("text-2xl font-bold text-amber-500")
                    else:
                        ui.icon("check_circle", size="sm").classes("text-green-500")
                        ui.label("0").classes("text-2xl font-bold text-green-500")
                ui.label("Drift").classes("text-xs text-slate-500")
    
    # Store grid row data in a mutable container for callbacks
    grid_data_ref = {"data": grid_row_data}
    
    # Reset all mappings function
    def reset_all_mappings():
        """Reset all mappings and re-generate suggestions."""
        # Clear confirmed mappings
        state.map.confirmed_mappings = []
        # Clear suggested matches
        state.map.suggested_matches = []
        # Clear rejected suggestions
        state.map.rejected_suggestions = set()
        # Invalidate mapping file
        state.map.mapping_file_valid = False
        
        # Delete mapping file if exists
        if state.map.mapping_file_path:
            mapping_path = Path(state.map.mapping_file_path)
            if mapping_path.exists():
                try:
                    mapping_path.unlink()
                except Exception as e:
                    logging.warning(f"Could not delete mapping file: {e}")
            state.map.mapping_file_path = None
        
        save_state()
        _persist_target_intent_from_match(state)
        ui.notify("All mappings reset. Suggestions will be regenerated.", type="info")
        ui.navigate.reload()
    
    def accept_all_pending():
        """Accept all pending matches."""
        # Confidence types that represent automatic matching (not manual selection)
        auto_match_types = {
            "exact_match", "state_id_match", "url_match", "github_match", "env_match"
        }
        for row in grid_data_ref["data"]:
            # Include both "match" and "adopt" actions - both represent mapping to existing target resources
            if row.get("status") == "pending" and row.get("action") in ("match", "adopt") and row.get("target_id"):
                confidence = row.get("confidence", "manual")
                state.map.confirmed_mappings.append({
                    "resource_type": row.get("source_type"),
                    "source_name": row.get("source_name"),
                    "source_key": row.get("source_key"),
                    "target_id": row.get("target_id"),
                    "target_name": row.get("target_name"),
                    # Store the action for deploy.py to filter on
                    "action": row.get("action"),
                    # Preserve the actual confidence type for better diagnostics
                    "match_type": confidence if confidence in auto_match_types else "manual",
                })
        save_state()
        _persist_target_intent_from_match(state)
        ui.navigate.reload()
                    
    def reject_all_pending():
        """Reject all pending matches - set them to create new."""
        for row in grid_data_ref["data"]:
            if row.get("status") == "pending" and row.get("action") == "match":
                if isinstance(state.map.rejected_suggestions, set):
                    state.map.rejected_suggestions.add(row.get("source_key"))
                else:
                    state.map.rejected_suggestions = set(state.map.rejected_suggestions)
                    state.map.rejected_suggestions.add(row.get("source_key"))
        save_state()
        _persist_target_intent_from_match(state)
        ui.navigate.reload()
    
    def adopt_all_matched():
        """Bulk adopt all resources that have a target match but aren't already adopted.
        
        Sets action='adopt' for all rows that have a target_id and aren't already
        adopted or unadopted. Adds confirmed mappings for each adopted row.
        """
        if not hasattr(state.map, "confirmed_mappings"):
            state.map.confirmed_mappings = []
        
        adopted_count = 0
        existing_keys = {m.get("source_key") for m in state.map.confirmed_mappings}
        
        for row in grid_data_ref["data"]:
            target_id = row.get("target_id")
            source_key = row.get("source_key", "")
            if (
                target_id
                and row.get("action") not in ("adopt", "unadopt")
                and not row.get("is_state_only")
            ):
                # Remove existing mapping if any
                if source_key in existing_keys:
                    state.map.confirmed_mappings = [
                        m for m in state.map.confirmed_mappings
                        if m.get("source_key") != source_key
                    ]
                
                # Add adopt mapping
                state.map.confirmed_mappings.append({
                    "source_key": source_key,
                    "target_id": target_id,
                    "target_name": row.get("target_name", ""),
                    "match_type": "bulk_adopt",
                    "action": "adopt",
                    "protected": False,
                })
                adopted_count += 1
        
        save_state()
        _persist_target_intent_from_match(state)
        ui.notify(f"Set {adopted_count} matched resources to adopt", type="positive")
        ui.navigate.reload()
    
    def ignore_all_unmatched():
        """Bulk ignore all resources that have no target match.
        
        Sets action='skip' for rows without a target_id. Uses rejected_suggestions
        to mark them as explicitly rejected (create_new → skip).
        """
        ignored_count = 0
        for row in grid_data_ref["data"]:
            if (
                not row.get("target_id")
                and row.get("action") not in ("skip", "ignore", "unadopt")
                and not row.get("is_state_only")
            ):
                source_key = row.get("source_key", "")
                if isinstance(state.map.rejected_suggestions, set):
                    state.map.rejected_suggestions.add(source_key)
                else:
                    state.map.rejected_suggestions = set(state.map.rejected_suggestions)
                    state.map.rejected_suggestions.add(source_key)
                ignored_count += 1
        
        save_state()
        _persist_target_intent_from_match(state)
        ui.notify(f"Set {ignored_count} unmatched resources to skip", type="info")
        ui.navigate.reload()
                    
    async def export_csv():
        """Export current mappings to CSV."""
        csv_content = export_mappings_to_csv(grid_data_ref["data"])
        escaped = csv_content.replace('`', '\\`')
        await ui.run_javascript(f'''
            const blob = new Blob([`{escaped}`], {{type: 'text/csv'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'resource_mappings.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        ''')
        ui.notify("CSV exported", type="positive")
    
    def show_protection_cascade_dialog(
        resource_name: str,
        parents_to_protect: list[CascadeResource],
        on_confirm: Callable[[], None],
    ) -> None:
        """Show dialog confirming protection of resource and its parents."""
        with ui.dialog() as dialog, ui.card().classes("p-4").style("min-width: 450px;"):
            with ui.row().classes("items-center gap-2 mb-4"):
                ui.icon("shield", size="md").classes("text-blue-500")
                ui.label("Protect Resource").classes("text-lg font-bold")
            
            ui.label(
                f"To protect '{resource_name}', the following parent resources must also be protected:"
            ).classes("mb-3")
            
            with ui.column().classes("pl-4 gap-1 mb-4"):
                for res in parents_to_protect:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("subdirectory_arrow_right", size="xs").classes("text-slate-400")
                        ui.badge(res.type_label).props("dense color=blue-grey")
                        ui.label(res.name).classes("text-sm")
            
            ui.label(
                "This ensures Terraform won't destroy parent resources that protected children depend on."
            ).classes("text-xs text-slate-500 mb-4")
            
            with ui.row().classes("gap-2 justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                
                def confirm_and_close():
                    on_confirm()
                    dialog.close()
                
                ui.button(
                    f"Protect All ({len(parents_to_protect) + 1})",
                    on_click=confirm_and_close,
                ).props("color=primary")
        
        dialog.open()
    
    def show_unprotection_cascade_dialog(
        resource_name: str,
        protected_children: list[CascadeResource],
        on_unprotect_all: Callable[[], None],
        on_unprotect_self_only: Callable[[], None],
    ) -> None:
        """Show dialog asking about unprotecting children."""
        with ui.dialog() as dialog, ui.card().classes("p-4").style("min-width: 450px;"):
            with ui.row().classes("items-center gap-2 mb-4"):
                ui.icon("shield_outlined", size="md").classes("text-amber-500")
                ui.label("Unprotect Resource").classes("text-lg font-bold")
            
            ui.label(
                f"'{resource_name}' has {len(protected_children)} protected child resource(s):"
            ).classes("mb-3")
            
            with ui.column().classes("pl-4 gap-1 mb-4"):
                for res in protected_children[:10]:  # Show max 10
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("subdirectory_arrow_right", size="xs").classes("text-slate-400")
                        ui.badge(res.type_label).props("dense color=blue-grey")
                        ui.label(res.name).classes("text-sm")
                if len(protected_children) > 10:
                    ui.label(f"... and {len(protected_children) - 10} more").classes("text-xs text-slate-400 pl-6")
            
            ui.label(
                "Would you like to unprotect the children as well?"
            ).classes("text-sm mb-4")
            
            with ui.row().classes("gap-2 justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                
                def unprotect_self_and_close():
                    on_unprotect_self_only()
                    dialog.close()
                
                def unprotect_all_and_close():
                    on_unprotect_all()
                    dialog.close()
                
                ui.button(
                    "Unprotect This Only",
                    on_click=unprotect_self_and_close,
                ).props("flat color=grey")
                
                ui.button(
                    f"Unprotect All ({len(protected_children) + 1})",
                    on_click=unprotect_all_and_close,
                ).props("color=amber")
        
        dialog.open()
    
    def _get_intent_key_for_row(row_data: dict) -> str:
        """Get the canonical intent key for a grid row.
        
        For sub-project resources (ENV, JOB, EXTATTR), the grid source_key is just the
        resource name (e.g., "dev"), but the TF state key includes the project prefix
        (e.g., "sse_dm_fin_fido_dev"). The intent system must use the TF state key
        to match what the mismatch panel and clarification panel use.
        
        Priority:
        1. Extract from state_address (most reliable, matches TF state)
        2. Fall back to source_key (for resources without state)
        """
        import re
        source_key = row_data.get("source_key", "")
        state_address = row_data.get("state_address", "")
        
        if state_address:
            # Extract key from TF state address: ...["key_here"]
            match = re.search(r'\["([^"]+)"\]$', state_address)
            if match:
                return match.group(1)
        
        # Fallback: use source_key as-is
        return source_key
    
    def _get_intent_key_for_source_key(source_key: str, source_type: str) -> str:
        """Get the canonical intent key for a source_key by looking up the grid row.
        
        Used by bulk protect/unprotect handlers where only source_key is available.
        """
        for row in grid_data_ref["data"]:
            if row.get("source_key") == source_key:
                return _get_intent_key_for_row(row)
        return source_key
    
    # Known resource type prefixes for intent keys
    _KNOWN_TYPE_PREFIXES = frozenset({
        "PRJ:", "ENV:", "JOB:", "CON:", "REP:", "PREP:", "REPO:",
        "VAR:", "JEVO:", "CRD:", "EXTATTR:",
    })
    
    def _make_prefixed_intent_key(source_type: str, intent_key: str) -> str:
        """Build a prefixed intent key like 'ENV:sse_dm_fin_fido_dev'.
        
        Handles project-scoped keys (e.g., 'hash:project_name') correctly by
        checking for known type prefixes rather than just presence of ':'.
        """
        if not source_type:
            return intent_key
        # Check if already prefixed with a known type code
        has_prefix = any(intent_key.startswith(p) for p in _KNOWN_TYPE_PREFIXES)
        if has_prefix:
            return intent_key
        return f"{source_type}:{intent_key}"
    
    def _find_source_key_for_intent_key(prefixed_key: str) -> str:
        """Reverse lookup: find the source_key in grid data for a given intent key.
        
        Intent keys are prefixed like "ENV:sse_dm_fin_fido_dev". We need to find the
        grid row where _get_intent_key_for_row() returns "sse_dm_fin_fido_dev" and
        source_type is "ENV", then return that row's source_key (e.g., "dev").
        
        Returns source_key if found, or None if no match in grid data.
        """
        if ":" in prefixed_key:
            intent_type, intent_resource_key = prefixed_key.split(":", 1)
        else:
            intent_type = ""
            intent_resource_key = prefixed_key
        
        for row in grid_data_ref["data"]:
            row_type = row.get("source_type", "")
            if intent_type and row_type != intent_type:
                continue
            row_intent_key = _get_intent_key_for_row(row)
            if row_intent_key == intent_resource_key:
                return row.get("source_key", "")
        
        # Fallback: intent_resource_key might BE the source_key (for PRJ, REP, PREP)
        return intent_resource_key
    
    def apply_protection(keys_to_protect: list[str]) -> None:
        """Apply protection to multiple resources.
        
        Records protection intent for each resource and updates the protected_resources set.
        Intent is recorded with source="protect_all_button" for bulk actions.
        Keys are always prefixed with TYPE: before storing in intent manager.
        """
        from importer.web.utils.ui_logger import log_action, log_state_change
        before = set(state.map.protected_resources) if state.map.protected_resources else set()
        before_fix_pending = state.map.protection_fix_pending
        
        # Build a lookup from source_key -> source_type from grid data
        key_to_type = {}
        for row in grid_data_ref["data"]:
            sk = row.get("source_key")
            st = row.get("source_type", "")
            if sk and st:
                key_to_type[sk] = st
        
        # Get protection intent manager and record intent for each resource
        protection_intent = state.get_protection_intent_manager()
        for key in keys_to_protect:
            # Get current TF state protection status for this resource
            tf_state_at_decision = None
            for row in grid_data_ref["data"]:
                if row.get("source_key") == key:
                    tf_state_at_decision = "protected" if row.get("state_protected") else "unprotected"
                    yaml_state_before = row.get("yaml_protected", False)
                    break
            else:
                yaml_state_before = key in before
            
            # Always use prefixed key (TYPE:key) for intent manager
            # Use TF state key for sub-project resources (ENV, JOB, EXTATTR)
            source_type = key_to_type.get(key, "")
            intent_key = _get_intent_key_for_source_key(key, source_type)
            prefixed_key = _make_prefixed_intent_key(source_type, intent_key)
            
            # Record intent - this is the source of truth for user decisions
            protection_intent.set_intent(
                key=prefixed_key,
                protected=True,
                source="protect_all_button",
                reason="Bulk protect from Match page",
                resource_type=source_type or None,
                tf_state_at_decision=tf_state_at_decision,
                yaml_state_before=yaml_state_before,
            )
            state.map.protected_resources.add(key)
        
        # Save intent file
        protection_intent.save()
        
        # Reset any stale protection fix state - user has taken a new action
        fix_state_reset = False
        if state.map.protection_fix_pending:
            fix_state_reset = True
            state.map.protection_fix_pending = False
            state.map.protection_fix_file_path = ""
            state.map.protection_fix_action = ""
            state.map.protection_fix_previous_content = ""
            state.map.protection_fix_backup_protected = set()
            state.map.protection_fix_backup_unprotected = set()
        
        log_action("apply_protection", "executed", {
            "keys": keys_to_protect,
            "count": len(keys_to_protect),
            "fix_state_reset": fix_state_reset,
        })
        log_state_change("protected_resources", "add", {"keys": keys_to_protect}, before=before, after=state.map.protected_resources)
        if fix_state_reset:
            log_state_change("protection_fix_pending", "reset", {"reason": "user_protect_action"}, before=before_fix_pending, after=False)
        
        save_state()
        ui.notify(f"Protected {len(keys_to_protect)} resource(s)", type="positive")
        ui.navigate.reload()
    
    def remove_protection(keys_to_unprotect: list[str]) -> None:
        """Remove protection from multiple resources.
        
        Records unprotection intent for each resource and updates the protected_resources set.
        Intent is recorded with source="unprotect_all_button" for bulk actions.
        Keys are always prefixed with TYPE: before storing in intent manager.
        """
        from importer.web.utils.ui_logger import log_action, log_state_change
        before = set(state.map.protected_resources) if state.map.protected_resources else set()
        before_fix_pending = state.map.protection_fix_pending
        
        # Build a lookup from source_key -> source_type from grid data
        key_to_type = {}
        for row in grid_data_ref["data"]:
            sk = row.get("source_key")
            st = row.get("source_type", "")
            if sk and st:
                key_to_type[sk] = st
        
        # Get protection intent manager and record intent for each resource
        protection_intent = state.get_protection_intent_manager()
        for key in keys_to_unprotect:
            # Get current TF state protection status for this resource
            tf_state_at_decision = None
            for row in grid_data_ref["data"]:
                if row.get("source_key") == key:
                    tf_state_at_decision = "protected" if row.get("state_protected") else "unprotected"
                    yaml_state_before = row.get("yaml_protected", False)
                    break
            else:
                yaml_state_before = key in before
            
            # Always use prefixed key (TYPE:key) for intent manager
            # Use TF state key for sub-project resources (ENV, JOB, EXTATTR)
            source_type = key_to_type.get(key, "")
            intent_key = _get_intent_key_for_source_key(key, source_type)
            prefixed_key = _make_prefixed_intent_key(source_type, intent_key)
            
            # Record intent - this is the source of truth for user decisions
            protection_intent.set_intent(
                key=prefixed_key,
                protected=False,
                source="unprotect_all_button",
                reason="Bulk unprotect from Match page",
                resource_type=source_type or None,
                tf_state_at_decision=tf_state_at_decision,
                yaml_state_before=yaml_state_before,
            )
            state.map.protected_resources.discard(key)
        
        # Save intent file
        protection_intent.save()
        
        # Reset any stale protection fix state - user has taken a new action
        fix_state_reset = False
        if state.map.protection_fix_pending:
            fix_state_reset = True
            state.map.protection_fix_pending = False
            state.map.protection_fix_file_path = ""
            state.map.protection_fix_action = ""
            state.map.protection_fix_previous_content = ""
            state.map.protection_fix_backup_protected = set()
            state.map.protection_fix_backup_unprotected = set()
        
        log_action("remove_protection", "executed", {
            "keys": keys_to_unprotect,
            "count": len(keys_to_unprotect),
            "fix_state_reset": fix_state_reset,
        })
        log_state_change("protected_resources", "remove", {"keys": keys_to_unprotect}, before=before, after=state.map.protected_resources)
        if fix_state_reset:
            log_state_change("protection_fix_pending", "reset", {"reason": "user_unprotect_action"}, before=before_fix_pending, after=False)
        
        save_state()
        ui.notify(f"Unprotected {len(keys_to_unprotect)} resource(s)", type="info")
        ui.navigate.reload()
    
    def on_row_change(row_data: dict):
        """Handle row data changes from the grid."""
        source_key = row_data.get("source_key")
        action = row_data.get("action")
        new_protected = row_data.get("protected", False)
        row_data.get("status")
        
        # IMPORTANT: Always update grid_data_ref immediately so dialogs see current state
        # This must happen BEFORE any early returns for cascade dialogs
        # Also update yaml_protected to stay consistent with the user's intent
        row_data["yaml_protected"] = new_protected
        for i, row in enumerate(grid_data_ref["data"]):
            if row.get("source_key") == source_key:
                grid_data_ref["data"][i] = row_data
                break
        
        # Check if protection status changed
        old_protected = source_key in state.map.protected_resources
        
        if new_protected and not old_protected:
            # User is protecting this resource - check for cascade
            target_resource, parents_to_protect = get_resources_to_protect(
                source_key, hierarchy_index, source_items, state.map.protected_resources
            )
            
            if parents_to_protect:
                # Has unprotected parents - show confirmation dialog
                all_keys = [source_key] + [p.key for p in parents_to_protect]
                show_protection_cascade_dialog(
                    target_resource.name,
                    parents_to_protect,
                    on_confirm=lambda keys=all_keys: apply_protection(keys),
                )
                return  # Don't save yet - wait for dialog
            else:
                # No parents to protect, just protect this one
                # Record intent with prefixed key (TYPE:key)
                protection_intent = state.get_protection_intent_manager()
                tf_state_at_decision = "protected" if row_data.get("state_protected") else "unprotected"
                source_type = row_data.get("source_type", "")
                # For sub-project resources (ENV, JOB, EXTATTR), use the TF state key
                # which includes the project prefix (e.g., "sse_dm_fin_fido_dev" not just "dev")
                intent_key = _get_intent_key_for_row(row_data)
                prefixed_key = _make_prefixed_intent_key(source_type, intent_key)
                protection_intent.set_intent(
                    key=prefixed_key,
                    protected=True,
                    source="user_click",
                    reason="Single resource protect from Match grid",
                    resource_type=source_type or None,
                    tf_state_at_decision=tf_state_at_decision,
                    yaml_state_before=old_protected,
                )
                protection_intent.save()
                state.map.protected_resources.add(source_key)
                save_state()
                ui.notify(f"Protected: {target_resource.name}", type="positive")
                # Reload to refresh protection mismatch panel
                ui.navigate.reload()
                return
        
        elif not new_protected and old_protected:
            # User is removing protection - check for protected children
            target_resource, protected_children = get_resources_to_unprotect(
                source_key, hierarchy_index, source_items, state.map.protected_resources
            )
            
            if protected_children:
                # Has protected children - show dialog
                child_keys = [c.key for c in protected_children]
                show_unprotection_cascade_dialog(
                    target_resource.name,
                    protected_children,
                    on_unprotect_all=lambda keys=[source_key] + child_keys: remove_protection(keys),
                    on_unprotect_self_only=lambda: remove_protection([source_key]),
                )
                return  # Don't save yet - wait for dialog
            else:
                # No protected children, just unprotect
                # Record intent with prefixed key (TYPE:key)
                protection_intent = state.get_protection_intent_manager()
                tf_state_at_decision = "protected" if row_data.get("state_protected") else "unprotected"
                source_type = row_data.get("source_type", "")
                # For sub-project resources (ENV, JOB, EXTATTR), use the TF state key
                intent_key = _get_intent_key_for_row(row_data)
                prefixed_key = _make_prefixed_intent_key(source_type, intent_key)
                protection_intent.set_intent(
                    key=prefixed_key,
                    protected=False,
                    source="user_click",
                    reason="Single resource unprotect from Match grid",
                    resource_type=source_type or None,
                    tf_state_at_decision=tf_state_at_decision,
                    yaml_state_before=old_protected,
                )
                protection_intent.save()
                state.map.protected_resources.discard(source_key)
                save_state()
                ui.notify(f"Unprotected: {target_resource.name}", type="info")
                # Reload to refresh protection mismatch panel
                ui.navigate.reload()
                return
        
        # Note: grid_data_ref update now happens at the start of this function
        # to ensure dialogs always see the current state
        
        # If action is match and has valid target, it can be confirmed
        # If action is skip, create_new, or unadopt, remove from confirmed if present
        if action in ("skip", "create_new", "unadopt"):
            state.map.confirmed_mappings = [
                m for m in state.map.confirmed_mappings
                if m.get("source_key") != source_key
            ]
        if action == "unadopt":
            if not isinstance(getattr(state.map, "removal_keys", None), set):
                state.map.removal_keys = set(state.map.removal_keys or [])
            state.map.removal_keys.add(source_key)
        elif hasattr(state.map, "removal_keys") and state.map.removal_keys is not None:
            state.map.removal_keys.discard(source_key)

        save_state()
        _persist_target_intent_from_match(state)
    
    def on_accept(source_key: str):
        """Accept a single suggestion."""
        for row in grid_data_ref["data"]:
            if row.get("source_key") == source_key:
                if row.get("target_id"):
                    state.map.confirmed_mappings.append({
                        "resource_type": row.get("source_type"),
                        "source_name": row.get("source_name"),
                        "source_key": source_key,
                        "target_id": row.get("target_id"),
                        "target_name": row.get("target_name"),
                        "action": row.get("action", "adopt"),  # Include action for deploy.py
                        "match_type": "manual",
                    })
                    row["status"] = "confirmed"
                    break
        save_state()
        _persist_target_intent_from_match(state)
        ui.navigate.reload()
    
    def on_reject(source_key: str):
        """Reject a single suggestion."""
        if isinstance(state.map.rejected_suggestions, set):
            state.map.rejected_suggestions.add(source_key)
        else:
            state.map.rejected_suggestions = set(state.map.rejected_suggestions)
            state.map.rejected_suggestions.add(source_key)
        save_state()
        _persist_target_intent_from_match(state)
        ui.navigate.reload()
    
    def find_source_item(source_key: str) -> Optional[dict]:
        """Find source item by key, checking both 'key' and 'element_mapping_id'.
        
        Handles project-scoped keys for NAME_KEYED_TYPES (VAR, JEVO) where the
        grid may append ':project_name' to make keys unique across projects.
        """
        # First try exact match
        for s in source_items:
            item_key = s.get("key") or s.get("element_mapping_id", "")
            if item_key == source_key:
                return s
        # Fall back: for project-scoped keys like "hash:project_name",
        # try matching base key + project_name from the source item
        if ":" in source_key:
            base_key, proj_suffix = source_key.rsplit(":", 1)
            for s in source_items:
                item_key = s.get("key") or s.get("element_mapping_id", "")
                item_project = s.get("project_name", "") or s.get("project_key", "")
                if item_key == base_key and item_project == proj_suffix:
                    return s
        return None
    
    def on_view_details(source_key: str):
        """View details for a resource."""
        # Check if this is a JEVO (job env var override) - synthetic key format
        if "__override__" in source_key:
            # Extract parent job key and variable name
            parts = source_key.split("__override__", 1)
            parent_job_key = parts[0]
            var_name = parts[1] if len(parts) > 1 else "Unknown"
            
            # Find parent job to get override value
            parent_job = find_source_item(parent_job_key)
            if parent_job:
                overrides = parent_job.get("environment_variable_overrides", {})
                var_value = overrides.get(var_name, "N/A")
                job_name = parent_job.get("name", parent_job_key)
                
                # Show simple dialog for override details
                with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[400px]"):
                    ui.label("Environment Variable Override").classes("text-lg font-bold mb-4")
                    
                    with ui.column().classes("gap-2"):
                        with ui.row().classes("gap-2"):
                            ui.label("Variable:").classes("font-semibold w-24")
                            ui.label(var_name).classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("Value:").classes("font-semibold w-24")
                            # Mask secret values
                            display_value = "********" if "SECRET" in var_name.upper() else str(var_value)
                            ui.label(display_value).classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("Parent Job:").classes("font-semibold w-24")
                            ui.label(job_name).classes("font-mono")
                    
                    ui.button("Close", on_click=dialog.close).classes("mt-4")
                dialog.open()
            else:
                ui.notify(f"Parent job not found for override: {source_key}", type="warning")
            return
        
        # Check if this is a JCTG (job completion trigger) - synthetic key format
        if "__trigger__completion" in source_key:
            parent_job_key = source_key.split("__trigger__completion")[0]
            
            parent_job = find_source_item(parent_job_key)
            if parent_job:
                job_name = parent_job.get("name", parent_job_key)
                jctc = parent_job.get("job_completion_trigger_condition", {})
                
                # Extract trigger details
                trigger_job_id = jctc.get("job_id") or jctc.get("condition", {}).get("job_id")
                statuses = jctc.get("statuses") or jctc.get("condition", {}).get("statuses", [])
                
                # Map status codes to names
                status_map = {10: "Success", 20: "Error", 30: "Cancelled"}
                status_names = [status_map.get(s, str(s)) for s in statuses] if statuses else ["Unknown"]
                
                with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[400px]"):
                    ui.label("Job Completion Trigger").classes("text-lg font-bold mb-4")
                    
                    with ui.column().classes("gap-2"):
                        with ui.row().classes("gap-2"):
                            ui.label("Parent Job:").classes("font-semibold w-28")
                            ui.label(job_name).classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("Trigger Job ID:").classes("font-semibold w-28")
                            ui.label(str(trigger_job_id) if trigger_job_id else "N/A").classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("On Statuses:").classes("font-semibold w-28")
                            ui.label(", ".join(status_names)).classes("font-mono")
                    
                    ui.button("Close", on_click=dialog.close).classes("mt-4")
                dialog.open()
            else:
                ui.notify(f"Parent job not found for trigger: {source_key}", type="warning")
            return
        
        # Check if this is a PREP (project repository link) - synthetic key format
        if "__repo_link__" in source_key:
            parts = source_key.split("__repo_link__", 1)
            parent_project_key = parts[0]
            repo_key = parts[1] if len(parts) > 1 else "Unknown"
            
            parent_project = find_source_item(parent_project_key)
            if parent_project:
                project_name = parent_project.get("name", parent_project_key)
                
                with ui.dialog() as dialog, ui.card().classes("p-4 min-w-[400px]"):
                    ui.label("Project Repository Link").classes("text-lg font-bold mb-4")
                    
                    with ui.column().classes("gap-2"):
                        with ui.row().classes("gap-2"):
                            ui.label("Project:").classes("font-semibold w-28")
                            ui.label(project_name).classes("font-mono")
                        with ui.row().classes("gap-2"):
                            ui.label("Repository:").classes("font-semibold w-28")
                            ui.label(repo_key).classes("font-mono")
                        ui.label(
                            "This resource links the project to its repository in Terraform."
                        ).classes("text-xs text-slate-500 mt-2")
                    
                    ui.button("Close", on_click=dialog.close).classes("mt-4")
                dialog.open()
            else:
                ui.notify(f"Parent project not found for repository link: {source_key}", type="warning")
            return
        
        # Handle state-only resources (in TF state but not in source selection)
        if source_key.startswith("state__"):
            # Find the grid row for this state-only resource
            grid_row = None
            for row in grid_data_ref["data"]:
                if row.get("source_key") == source_key:
                    grid_row = row
                    break
            
            if not grid_row:
                ui.notify(f"Grid row not found for state resource: {source_key}", type="warning")
                return
            
            source_type = grid_row.get("source_type", "")
            target_id = grid_row.get("target_id")
            target_name_val = grid_row.get("target_name", "")
            project_name = grid_row.get("project_name", "")
            state_address = grid_row.get("state_address", "")
            
            # Build a synthetic source_item from state/grid data for the detail dialog
            synthetic_source = {
                "element_type_code": source_type,
                "name": target_name_val or grid_row.get("source_name", ""),
                "key": source_key,
                "element_mapping_id": source_key,
                "project_name": project_name,
                "dbt_id": target_id,
                "is_state_only": True,
            }
            
            # Find target data
            target_data = None
            if target_id and target_id not in ("", "None"):
                for t in target_items_ref.get("items", []):
                    if str(t.get("dbt_id")) == str(target_id):
                        target_data = t
                        break
            
            # Fallback target by (type, project, name)
            if not target_data and target_name_val:
                for t in target_items_ref.get("items", []):
                    t_type = t.get("element_type_code", "")
                    t_name = t.get("name", "")
                    t_proj = t.get("project_name", "")
                    if t_type == source_type and t_name == target_name_val and t_proj == project_name:
                        target_data = t
                        break
            
            # Find state resource
            state_resource = None
            state_id = grid_row.get("state_id")
            if state_ref.get("state_result") and state_ref["state_result"].resources:
                for res in state_ref["state_result"].resources:
                    if res.address == state_address:
                        state_resource = {
                            "address": res.address,
                            "dbt_id": res.dbt_id,
                            "name": res.name,
                            "tf_name": res.tf_name,
                            "element_code": res.element_code,
                            "project_id": res.project_id,
                            "resource_index": res.resource_index,
                            **res.attributes,
                        }
                        break
            
            from importer.web.components.entity_table import show_match_detail_dialog
            show_match_detail_dialog(
                source_data=synthetic_source,
                grid_row=grid_row,
                target_data=target_data,
                state_resource=state_resource,
                has_state_loaded=True,
            )
            return
        
        # Regular resource - use enhanced match detail dialog with drift info
        source_item = find_source_item(source_key)
        if source_item:
            from importer.web.components.entity_table import show_match_detail_dialog
            
            # Find grid row data for this source
            grid_row = None
            for row in grid_data_ref["data"]:
                if row.get("source_key") == source_key:
                    grid_row = row
                    break
            
            if not grid_row:
                grid_row = {"source_key": source_key, "drift_status": "no_state"}
            
            # Find target data if matched
            target_data = None
            target_id = grid_row.get("target_id")
            source_type = source_item.get("element_type_code", "") if source_item else grid_row.get("source_type", "")
            if target_id and target_id not in ("", "None"):
                # Use target_items_ref which stores the target items passed to this function
                for t in target_items_ref.get("items", []):
                    if str(t.get("dbt_id")) == str(target_id):
                        target_data = t
                        break
            
            # Fallback for NAME_KEYED_TYPES (VAR, JEVO) and PROJECT_SCOPED_TYPES:
            # These may not have a usable dbt_id. Match by (type, project, name) instead.
            if not target_data and grid_row.get("target_name"):
                target_name_val = grid_row.get("target_name", "")
                target_project = grid_row.get("project_name", "")
                for t in target_items_ref.get("items", []):
                    t_type = t.get("element_type_code", "")
                    t_name = t.get("name", "")
                    t_proj = t.get("project_name", "")
                    if t_type == source_type and t_name == target_name_val:
                        # For project-scoped types, also require project match
                        if source_type in PROJECT_SCOPED_TYPES:
                            if t_proj == target_project:
                                target_data = t
                                break
                        else:
                            target_data = t
                            break
            
            # Find state resource data if available
            state_resource = None
            state_id = grid_row.get("state_id")
            state_address_from_grid = grid_row.get("state_address", "")
            if state_ref.get("state_result") and state_ref["state_result"].resources:
                if not source_type:
                    source_type = source_item.get("element_type_code", "")
                # Try to find by ID first
                if state_id:
                    for res in state_ref["state_result"].resources:
                        if res.dbt_id == state_id and res.element_code == source_type:
                            state_resource = {
                                "address": res.address,
                                "dbt_id": res.dbt_id,
                                "name": res.name,
                                "tf_name": res.tf_name,
                                "element_code": res.element_code,
                                "project_id": res.project_id,
                                "resource_index": res.resource_index,
                                **res.attributes,
                            }
                            break
                
                # Fallback for NAME_KEYED_TYPES (VAR, JEVO): state_id is always None.
                # Match by state_address (most reliable) or by (element_code, name) with project.
                if not state_resource and source_type in NAME_KEYED_TYPES:
                    source_name_val = grid_row.get("source_name", "") or (source_item.get("name", "") if source_item else "")
                    project_name_val = grid_row.get("project_name", "")
                    # First try matching by state_address from the grid (most precise)
                    if state_address_from_grid:
                        for res in state_ref["state_result"].resources:
                            if res.address == state_address_from_grid:
                                state_resource = {
                                    "address": res.address,
                                    "dbt_id": res.dbt_id,
                                    "name": res.name,
                                    "tf_name": res.tf_name,
                                    "element_code": res.element_code,
                                    "project_id": res.project_id,
                                    "resource_index": res.resource_index,
                                    **res.attributes,
                                }
                                break
                    # Then try by (element_code, project, name) using resource_index
                    if not state_resource and source_name_val:
                        expected_suffix = "_" + source_name_val
                        for res in state_ref["state_result"].resources:
                            if res.element_code == source_type and res.name == source_name_val:
                                # Check project scope via resource_index
                                if project_name_val and res.resource_index and res.resource_index.endswith(expected_suffix):
                                    res_project = res.resource_index[:-len(expected_suffix)]
                                    if res_project == project_name_val:
                                        state_resource = {
                                            "address": res.address,
                                            "dbt_id": res.dbt_id,
                                            "name": res.name,
                                            "tf_name": res.tf_name,
                                            "element_code": res.element_code,
                                            "project_id": res.project_id,
                                            "resource_index": res.resource_index,
                                            **res.attributes,
                                        }
                                        break
            
            # Callback to handle manual target selection from dropdown
            def handle_target_selected(selected_target: dict):
                """Handle when user selects a target from the dropdown."""
                source_key = source_item.get("key") or source_item.get("element_mapping_id", "")
                source_type = source_item.get("element_type_code", "")
                target_id = selected_target.get("dbt_id")
                target_name = selected_target.get("name", "")
                
                # Check if target is in TF state to determine action
                action = "match"
                if state_ref.get("state_result") and state_ref["state_result"].resources:
                    # Check if this target_id is in state
                    found_in_state = False
                    for res in state_ref["state_result"].resources:
                        if res.dbt_id == target_id and res.element_code == source_type:
                            found_in_state = True
                            break
                    if not found_in_state:
                        action = "adopt"  # Target exists but not in TF state - needs adoption
                elif state_ref.get("state_loaded"):
                    # State is loaded but target not found
                    action = "adopt"
                
                # Add to confirmed mappings
                if not hasattr(state.map, "confirmed_mappings"):
                    state.map.confirmed_mappings = []
                
                # Remove any existing mapping for this source
                state.map.confirmed_mappings = [
                    m for m in state.map.confirmed_mappings
                    if m.get("source_key") != source_key
                ]
                
                # Add new mapping with action
                state.map.confirmed_mappings.append({
                    "source_key": source_key,
                    "target_id": target_id,
                    "target_name": target_name,
                    "match_type": "manual",
                    "action": action,  # Store the action with the mapping
                })
                
                # Also remove from rejected keys if it was there
                if hasattr(state.map, "rejected_suggestions"):
                    if isinstance(state.map.rejected_suggestions, set):
                        state.map.rejected_suggestions.discard(source_key)
                    elif isinstance(state.map.rejected_suggestions, list):
                        state.map.rejected_suggestions = [k for k in state.map.rejected_suggestions if k != source_key]
                
                save_state()
                _persist_target_intent_from_match(state)
                ui.notify(f"Matched to {target_name} (ID: {target_id}) with action '{action}'", type="positive")
                ui.navigate.reload()  # Reload to update the grid
            
            # Callback to handle "Set to Adopt" button click
            def handle_adopt(protected: bool = True):
                """Handle when user clicks Set to Adopt button.
                
                Args:
                    protected: Whether to protect this resource from destroy (default: True)
                """
                source_key = source_item.get("key") or source_item.get("element_mapping_id", "")
                source_type = source_item.get("element_type_code", "")
                target_id = grid_row.get("target_id")
                target_name = grid_row.get("target_name", "")
                
                # Add/update confirmed mapping with adopt action
                if not hasattr(state.map, "confirmed_mappings"):
                    state.map.confirmed_mappings = []
                
                # Remove any existing mapping for this source
                state.map.confirmed_mappings = [
                    m for m in state.map.confirmed_mappings
                    if m.get("source_key") != source_key
                ]
                
                # Add new mapping with adopt action and protection flag
                state.map.confirmed_mappings.append({
                    "source_key": source_key,
                    "target_id": target_id,
                    "target_name": target_name,
                    "match_type": "manual",
                    "action": "adopt",
                    "protected": protected,  # Store protection preference
                })
                
                save_state()
                _persist_target_intent_from_match(state)
                protection_msg = " (protected)" if protected else ""
                ui.notify(f"Set {source_item.get('name', source_key)} to adopt{protection_msg}", type="positive")
                ui.navigate.reload()
            
            show_match_detail_dialog(
                source_data=source_item,
                grid_row=grid_row,
                target_data=target_data,
                state_resource=state_resource,
                app_state=state,
                available_targets=target_items_ref.get("items", []),
                has_state_loaded=state_ref.get("state_loaded", False),
                on_target_selected=handle_target_selected,
                on_adopt=handle_adopt,
            )
        else:
            ui.notify(f"Source resource not found: {source_key}", type="warning")
    
    def on_configure_clone(source_key: str):
        """Configure clone for a resource set to Create New."""
        source_item = find_source_item(source_key)
        if not source_item:
            ui.notify(f"Source resource not found: {source_key}", type="negative")
            return
        
        # Check for existing config
        existing_config = None
        cloned_resources = getattr(state.map, "cloned_resources", [])
        for config in cloned_resources:
            if config.source_key == source_key:
                existing_config = config
                break
        
        def save_clone_config(config: CloneConfig):
            """Save clone configuration to state."""
            # Initialize cloned_resources if needed
            if not hasattr(state.map, "cloned_resources"):
                state.map.cloned_resources = []
            
            # Remove existing config if present
            state.map.cloned_resources = [
                c for c in state.map.cloned_resources 
                if c.source_key != config.source_key
            ]
            
            # Add new config
            state.map.cloned_resources.append(config)
            save_state()
            ui.navigate.reload()
        
        show_clone_dialog(
            source_item=source_item,
            all_source_items=source_items,
            state=state,
            on_save=save_clone_config,
            existing_config=existing_config,
        )
    
    # Load Terraform State function
    async def load_terraform_state():
        """Load Terraform state to enable drift detection."""
        # Get terraform directory
        tf_dir = state.deploy.terraform_dir or "deployments/migration"
        tf_path = Path(tf_dir)
        if not tf_path.is_absolute():
            # Make relative to project root
            project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
            tf_path = project_root / tf_dir
        
        ui.notify("Loading Terraform state...", type="info")
        
        result = await read_terraform_state(tf_path)
        
        if not result.success:
            ui.notify(f"Failed to load state: {result.error_message}", type="negative")
            return
        
        if not result.resources:
            ui.notify("Terraform state is empty or no dbt Cloud resources found", type="warning")
            # Still mark as loaded so we can show "not in state" drift
        
        # Save to app state for persistence
        state.deploy.reconcile_state_loaded = True
        state.deploy.reconcile_state_resources = [
            {
                "address": r.address,
                "tf_type": r.tf_type,
                "element_code": r.element_code,
                "tf_name": r.tf_name,
                "dbt_id": r.dbt_id,
                "name": r.name,
                "project_id": r.project_id,
                "attributes": r.attributes,
                "resource_index": r.resource_index,
            }
            for r in result.resources
        ]
        save_state()

        # Compute state-to-target alignment and persist to target-intent.json
        target_items_list = target_items_ref.get("items", [])
        state_to_target_list = []
        for r in result.resources:
            state_key = r.resource_index or r.address
            target_id = ""
            target_name = ""
            match_type = "unmatched"
            for t in target_items_list:
                if t.get("dbt_id") == r.dbt_id and t.get("element_type_code") == r.element_code:
                    target_id = str(t.get("dbt_id", ""))
                    target_name = t.get("name", "")
                    match_type = "auto"
                    break
            state_to_target_list.append({
                "state_key": state_key,
                "state_address": r.address,
                "resource_type": r.element_code,
                "target_id": target_id,
                "target_name": target_name,
                "match_type": match_type,
                "confirmed": False,
            })
        _persist_target_intent_from_match(state, state_to_target=state_to_target_list)

        ui.notify(f"Loaded {len(result.resources)} resources from Terraform state", type="positive")
        ui.navigate.reload()
    
    # Info banner with Reset button and Load State button
    with ui.card().classes("w-full p-3 mb-4").style(f"border-left: 4px solid {DBT_TEAL};"):
        with ui.row().classes("w-full items-start justify-between"):
            with ui.row().classes("items-start gap-2"):
                ui.icon("info", size="sm").style(f"color: {DBT_TEAL};")
                with ui.column().classes("gap-1"):
                    ui.label("How Matching Works").classes("font-semibold text-sm")
                    ui.label(
                        "Resources are auto-matched by exact name. Edit Action to change behavior: "
                        "Match = import existing, Create New = create fresh, Skip = exclude from migration. "
                        "Double-click a row to view details."
                    ).classes("text-xs text-slate-500")
                    if state_ref["state_loaded"]:
                        ui.label(
                            "Terraform state loaded - State ID and Drift columns show reconciliation status."
                        ).classes("text-xs text-green-600")
            
            with ui.row().classes("items-center gap-2"):
                # Load Terraform State button
                if state_ref["state_loaded"]:
                    ui.button(
                        "State Loaded",
                        icon="check_circle",
                        on_click=load_terraform_state,
                    ).props("flat text-color=green-6 size=sm").tooltip(
                        "Click to reload Terraform state"
                    )
                else:
                    ui.button(
                        "Load TF State",
                        icon="cloud_download",
                        on_click=load_terraform_state,
                    ).props("outline size=sm").tooltip(
                        "Load Terraform state to detect drift between state and target"
                    )
                
                # Reset All Mappings button
                ui.button(
                    "Reset All Mappings",
                    icon="refresh",
                    on_click=reset_all_mappings,
                ).props("flat text-color=orange-6 size=sm").tooltip(
                    "Clear all mappings and regenerate suggestions"
                )
    
    # Grid ref for type filter callback (grid is created after toolbar)
    grid_ref: dict = {}
    
    def on_type_filter_change(type_value: str) -> None:
        """Apply type filter to the match grid via AG Grid setFilterModel."""
        g = grid_ref.get("grid")
        if g is None:
            return
        import asyncio
        async def apply() -> None:
            if type_value == "all":
                await g.run_grid_method("setFilterModel", {})
            else:
                await g.run_grid_method(
                    "setFilterModel",
                    {"source_type": {"filterType": "text", "type": "equals", "filter": type_value}},
                )
        asyncio.get_event_loop().create_task(apply())
    
    # Grid toolbar
    create_grid_toolbar(
        grid_row_data,
        on_accept_all=accept_all_pending,
        on_reject_all=reject_all_pending,
        on_reset_all=reset_all_mappings,
        on_export_csv=export_csv,
        on_type_filter_change=on_type_filter_change,
        on_adopt_all_matched=adopt_all_matched,
        on_ignore_all_unmatched=ignore_all_unmatched,
    )
    
    # Main grid in a card - flex container that grows to fill available space
    with ui.card().classes("w-full p-4 flex flex-col flex-grow").style("min-height: 350px;"):
        # Get protection intent manager for effective protection lookup
        protection_intent = state.get_protection_intent_manager()
        
        def on_unadopt(source_key: str) -> None:
            """Called when user sets action to unadopt; state already updated in on_row_change."""
            save_state()
        
        removal_keys_set = set(state.map.removal_keys or [])
        grid, _ = create_match_grid(
            source_items,
            target_items,
            state.map.confirmed_mappings,
            rejected_keys,
            on_row_change=on_row_change,
            on_accept=on_accept,
            on_reject=on_reject,
            on_view_details=on_view_details,
            clone_configs=clone_configs,
            on_configure_clone=on_configure_clone,
            state_result=state_ref["state_result"],
            on_unadopt=on_unadopt,
            removal_keys=removal_keys_set,
            protected_resources=state.map.protected_resources,
            protection_intent_manager=protection_intent,
        )
        grid_ref["grid"] = grid

    # Adopt imports section - show when TF state is loaded so user can adopt resources
    # This section lets users generate import blocks for resources marked with action="adopt"
    adopt_count = sum(1 for r in grid_row_data if r.get("action") == "adopt" and r.get("target_id"))
    # Only count resources that NEED adoption (target exists but not in state, or ID mismatch)
    # Exclude "state_only" - those are orphan resources in state, not adoption candidates
    # Also require that the resource has a target_id (something to adopt)
    drift_needing_adoption = [
        r for r in grid_row_data 
        if r.get("drift_status") in ("not_in_state", "id_mismatch") 
        and r.get("target_id")
        and r.get("action") != "adopt"  # Don't double-count already marked for adopt
    ]
    drift_resources_exist = len(drift_needing_adoption)
    mismatch_count = sum(1 for r in grid_row_data if r.get("action") == "adopt" and r.get("drift_status") == "id_mismatch")
    has_state = state_ref.get("state_result") is not None
    
    # Shared log storage for execution results - persisted in state
    # Format: {"logs": [(timestamp, cmd, success, output, cwd), ...]}
    # Initialize from persisted state so logs survive page reloads
    execution_logs_ref: dict[str, list] = {"logs": state.deploy.reconcile_execution_logs}
    
    def strip_ansi(text: str) -> str:
        """Remove ANSI escape codes from text."""
        import re
        ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
        return ansi_pattern.sub('', text)
    
    # Show adopt section if state is loaded and there are resources that could be adopted
    if has_state and (adopt_count > 0 or drift_resources_exist > 0):
        with ui.card().classes("w-full p-4 mt-4").style("border: 2px solid #8B5CF6;"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("download", size="sm").classes("text-purple-600")
                        ui.label("Adopt Resources into Terraform State").classes("font-semibold")
                    
                    if adopt_count > 0:
                        ui.label(
                            f"{adopt_count} resources marked for adoption"
                        ).classes("text-sm text-purple-600")
                    elif drift_resources_exist > 0:
                        # Show which resources have drift
                        drift_names = [f"{r.get('source_type', '?')}:{r.get('source_name', '?')}" for r in drift_needing_adoption[:3]]
                        drift_preview = ", ".join(drift_names)
                        if len(drift_needing_adoption) > 3:
                            drift_preview += f" (+{len(drift_needing_adoption) - 3} more)"
                        ui.label(
                            f"{drift_resources_exist} resources have drift: {drift_preview}"
                        ).classes("text-sm text-amber-600")
                        ui.label(
                            "Change Action to 'adopt' to import them"
                        ).classes("text-xs text-slate-500")
                    
                    ui.label(
                        "Set Action='adopt' in the grid for resources you want to import, then click Generate"
                    ).classes("text-xs text-slate-500")
                    
                    if state.deploy.reconcile_imports_generated:
                        ui.label("Import blocks generated - run terraform plan/apply").classes(
                            "text-xs text-green-600 mt-1"
                        )
                
                def generate_adopt_imports():
                    # Get terraform directory
                    tf_dir = state.deploy.terraform_dir or "deployments/migration"
                    tf_path = Path(tf_dir)
                    if not tf_path.is_absolute():
                        project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                        tf_path = project_root / tf_dir
                    
                    # Get ALL grid rows - function will filter internally but needs PRJ rows for lookup
                    all_rows = grid_data_ref["data"]
                    adopt_rows = [r for r in all_rows if r.get("action") == "adopt" and r.get("target_id")]
                    
                    if not adopt_rows:
                        # Log the attempt
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        execution_logs_ref["logs"].append((
                            timestamp,
                            "Generate Import Blocks",
                            False,
                            "No resources marked for adoption. Set Action='adopt' in the grid first.",
                            str(tf_path),
                        ))
                        save_state()  # Persist the log entry
                        ui.notify("No resources marked for adoption. Set Action='adopt' in the grid first.", type="warning")
                        return
                    
                    # Generate and write imports file - pass ALL rows so PRJ lookup works
                    output_path, error = write_adopt_imports_file(
                        all_rows,
                        tf_path,
                        filename="adopt_imports.tf",
                    )
                    
                    if error:
                        # Log the failure
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        execution_logs_ref["logs"].append((
                            timestamp,
                            f"Generate Import Blocks ({len(adopt_rows)} resources)",
                            False,
                            f"Error: {error}",
                            str(tf_path),
                        ))
                        save_state()  # Persist the log entry
                        ui.notify(f"Error generating imports: {error}", type="negative")
                        return
                    
                    # Log the success
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Build detailed output message
                    import_summary_lines = ["Generated import blocks for:"]
                    for row in adopt_rows:
                        import_summary_lines.append(f"  - {row.get('source_type', '?')}: {row.get('source_name', row.get('source_key', '?'))} → target ID {row.get('target_id', '?')}")
                    import_summary_lines.append(f"\nOutput file: {output_path}")
                    
                    execution_logs_ref["logs"].append((
                        timestamp,
                        f"Generate Import Blocks ({len(adopt_rows)} resources)",
                        True,
                        "\n".join(import_summary_lines),
                        str(tf_path),
                    ))
                    
                    state.deploy.reconcile_imports_generated = True
                    
                    # Save adopt rows for use in Generate Files (adoption YAML overrides)
                    adopt_rows = [
                        {
                            "source_key": r.get("source_key"),
                            "source_type": r.get("source_type"),
                            "source_name": r.get("source_name"),
                            "target_id": r.get("target_id"),
                            "target_name": r.get("target_name"),
                            "project_name": r.get("project_name"),
                            "project_id": r.get("project_id"),
                            "drift_status": r.get("drift_status"),
                        }
                        for r in all_rows
                        if r.get("action") == "adopt" and r.get("target_id")
                    ]
                    
                    state.deploy.reconcile_adopt_rows = adopt_rows
                    
                    # Log the saved adoption data
                    saved_data_lines = [f"Saved {len(adopt_rows)} resources for adoption override in Deploy:"]
                    for row in adopt_rows:
                        saved_data_lines.append(f"  - {row.get('source_type', '?')}: {row.get('source_key', '?')} (drift: {row.get('drift_status', 'unknown')})")
                    
                    execution_logs_ref["logs"].append((
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        f"Save Adoption Data ({len(adopt_rows)} resources)",
                        True,
                        "\n".join(saved_data_lines),
                        str(tf_path),
                    ))
                    
                    save_state()
                    
                    ui.notify(f"Import blocks written to {output_path}. Re-run 'terraform plan' to see imports.", type="positive", timeout=5000)
                    ui.navigate.reload()
                
                with ui.row().classes("gap-2"):
                    ui.button(
                        "Generate Import Blocks",
                        icon="file_download",
                        on_click=generate_adopt_imports,
                    ).style("background-color: #8B5CF6;")
                    def preview_adopt_imports():
                        # Build preview content - pass ALL rows so PRJ lookup works for project_id
                        all_rows = grid_data_ref["data"]
                        
                        # Get state rm commands for ID mismatches
                        state_rm_cmds = generate_state_rm_commands(all_rows)
                        
                        # Get import blocks
                        import_content = generate_adopt_imports_from_grid(all_rows, module_name="dbt_cloud")
                        adopt_count = sum(1 for r in all_rows if r.get("action") == "adopt" and r.get("target_id"))
                        mismatch_count = sum(1 for r in all_rows if r.get("action") == "adopt" and r.get("drift_status") == "id_mismatch")
                        
                        with ui.dialog().classes("w-3/4") as dialog, ui.card().classes("w-full max-h-screen overflow-auto"):
                            ui.label("Adoption Plan Preview").classes("text-lg font-semibold mb-2")
                            
                            # Show state rm commands if any
                            if state_rm_cmds:
                                with ui.expansion(f"Step 1: Remove Stale State ({len(state_rm_cmds)} commands)", icon="delete_sweep").classes("w-full mb-2").props("default-opened"):
                                    ui.label("These resources have different IDs in Terraform state vs target. The stale state entries must be removed before importing the correct resources.").classes("text-sm text-amber-600 mb-2")
                                    ui.label("This does NOT destroy any actual dbt Cloud resources.").classes("text-xs text-slate-500 mb-2")
                                    state_rm_content = "\n".join(state_rm_cmds)
                                    ui.code(state_rm_content, language="bash").classes("w-full text-xs")
                            else:
                                ui.label("Step 1: No stale state entries to remove").classes("text-sm text-green-600 mb-2")
                            
                            # Show import blocks
                            with ui.expansion(f"Step 2: Import Blocks ({adopt_count} resources)", icon="file_download").classes("w-full").props("default-opened"):
                                ui.code(import_content, language="hcl").classes("w-full text-xs")
                            
                            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                                if state_rm_cmds:
                                    async def run_state_rm():
                                        """Execute state rm commands"""
                                        from datetime import datetime
                                        import subprocess
                                        
                                        # Resolve terraform directory
                                        tf_dir = state.deploy.terraform_dir or "deployments/migration"
                                        tf_path = Path(tf_dir)
                                        if not tf_path.is_absolute():
                                            project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                                            tf_path = project_root / tf_dir
                                        
                                        if not tf_path.exists():
                                            ui.notify(f"Terraform directory not found: {tf_path}", type="negative")
                                            return
                                        
                                        results = []
                                        for cmd in state_rm_cmds:
                                            timestamp = datetime.now().isoformat(timespec='seconds')
                                            try:
                                                result = subprocess.run(
                                                    cmd,
                                                    shell=True,
                                                    cwd=str(tf_path),
                                                    capture_output=True,
                                                    text=True,
                                                )
                                                output = strip_ansi(result.stdout + result.stderr)
                                                results.append((timestamp, cmd, result.returncode == 0, output, str(tf_path)))
                                            except Exception as e:
                                                results.append((timestamp, cmd, False, str(e), str(tf_path)))
                                        
                                        # Store logs for later viewing
                                        execution_logs_ref["logs"].extend(results)
                                        save_state()  # Persist logs
                                        
                                        # Close the preview dialog
                                        dialog.close()
                                        
                                        # Show results in a new dialog
                                        success_count = sum(1 for _, _, ok, _, _ in results if ok)
                                        with ui.dialog().classes("w-3/4") as results_dialog, ui.card().classes("w-full max-h-screen overflow-auto"):
                                            if success_count == len(results):
                                                ui.label("State Removal Complete").classes("text-lg font-semibold text-green-600 mb-2")
                                                ui.label(f"Successfully removed {success_count} stale state entries.").classes("text-sm mb-4")
                                            else:
                                                ui.label("State Removal Results").classes("text-lg font-semibold text-amber-600 mb-2")
                                                ui.label(f"Removed {success_count}/{len(results)} entries.").classes("text-sm mb-4")
                                            
                                            ui.label(f"Working directory: {tf_path}").classes("text-xs text-slate-500 mb-4 font-mono")
                                            
                                            # Show command output
                                            for ts, cmd, ok, output, cwd in results:
                                                status_icon = "check_circle" if ok else "error"
                                                status_color = "text-green-600" if ok else "text-red-600"
                                                with ui.expansion(f"{cmd}", icon=status_icon).classes(f"w-full mb-2 {status_color}").props("default-opened" if not ok else ""):
                                                    ui.label(f"[{ts}]").classes("text-xs text-slate-400 font-mono")
                                                    if output.strip():
                                                        ui.code(output, language="text").classes("w-full text-xs")
                                                    else:
                                                        ui.label("(no output)").classes("text-xs text-slate-500")
                                            
                                            with ui.row().classes("w-full justify-end mt-4"):
                                                ui.button("Close", on_click=results_dialog.close).props("flat")
                                        results_dialog.open()
                                    
                                    ui.button(
                                        "Run State Remove Commands",
                                        icon="delete_sweep",
                                        on_click=run_state_rm,
                                    ).props("color=warning")
                                ui.button("Close", on_click=dialog.close).props("flat")
                        dialog.open()

                    ui.button(
                        "Preview Adoption Plan",
                        icon="visibility",
                        on_click=preview_adopt_imports,
                    ).props("outline").classes("text-purple-600")
                    
                    # Direct Run State Removal button (if there are mismatches)
                    if mismatch_count > 0:
                        async def run_state_removal_direct():
                            """Execute state rm commands directly"""
                            from datetime import datetime
                            import subprocess
                            
                            all_rows = grid_data_ref["data"]
                            state_rm_cmds = generate_state_rm_commands(all_rows)
                            
                            if not state_rm_cmds:
                                ui.notify("No stale state entries to remove", type="info")
                                return
                            
                            # Resolve terraform directory - use deployment dir from state
                            tf_dir = state.deploy.terraform_dir or "deployments/migration"
                            tf_path = Path(tf_dir)
                            if not tf_path.is_absolute():
                                # Make relative to project root
                                project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                                tf_path = project_root / tf_dir
                            
                            if not tf_path.exists():
                                ui.notify(f"Terraform directory not found: {tf_path}", type="negative")
                                return
                            
                            results = []
                            for cmd in state_rm_cmds:
                                timestamp = datetime.now().isoformat(timespec='seconds')
                                try:
                                    result = subprocess.run(
                                        cmd,
                                        shell=True,
                                        cwd=str(tf_path),
                                        capture_output=True,
                                        text=True,
                                    )
                                    output = strip_ansi(result.stdout + result.stderr)
                                    results.append((timestamp, cmd, result.returncode == 0, output, str(tf_path)))
                                except Exception as e:
                                    results.append((timestamp, cmd, False, str(e), str(tf_path)))
                            
                            # Store logs for later viewing
                            execution_logs_ref["logs"].extend(results)
                            save_state()  # Persist logs
                            
                            # Show results dialog
                            success_count = sum(1 for _, _, ok, _, _ in results if ok)
                            with ui.dialog().classes("w-3/4") as results_dialog, ui.card().classes("w-full max-h-screen overflow-auto"):
                                if success_count == len(results):
                                    ui.label("State Removal Complete").classes("text-lg font-semibold text-green-600 mb-2")
                                    ui.label(f"Successfully removed {success_count} stale state entries.").classes("text-sm mb-4")
                                else:
                                    ui.label("State Removal Results").classes("text-lg font-semibold text-amber-600 mb-2")
                                    ui.label(f"Removed {success_count}/{len(results)} entries.").classes("text-sm mb-4")
                                
                                ui.label(f"Working directory: {tf_path}").classes("text-xs text-slate-500 mb-4 font-mono")
                                
                                # Show command output
                                for ts, cmd, ok, output, cwd in results:
                                    status_icon = "check_circle" if ok else "error"
                                    status_color = "text-green-600" if ok else "text-red-600"
                                    with ui.expansion(f"{cmd}", icon=status_icon).classes(f"w-full mb-2 {status_color}").props("default-opened" if not ok else ""):
                                        ui.label(f"[{ts}]").classes("text-xs text-slate-400 font-mono")
                                        if output.strip():
                                            ui.code(output, language="text").classes("w-full text-xs")
                                        else:
                                            ui.label("(no output)").classes("text-xs text-slate-500")
                                
                                with ui.row().classes("w-full justify-end mt-4"):
                                    ui.button("Close", on_click=results_dialog.close).props("flat")
                            results_dialog.open()
                        
                        ui.button(
                            f"Run State Removal ({mismatch_count})",
                            icon="delete_sweep",
                            on_click=run_state_removal_direct,
                        ).props("color=warning")
                    
                    # View Logs button
                    def show_execution_logs():
                        """Show last execution logs in traditional format"""
                        logs = execution_logs_ref.get("logs", [])
                        filter_text = {"value": ""}
                        
                        with ui.dialog().props("maximized") as logs_dialog, ui.card().classes("w-full h-full"):
                            # Header bar
                            with ui.row().classes("w-full items-center justify-between p-4 border-b dark:border-slate-700"):
                                with ui.row().classes("items-center gap-4"):
                                    ui.icon("article", size="md").classes("text-slate-600")
                                    ui.label("Execution Logs").classes("text-xl font-semibold")
                                    if logs:
                                        # Summary badges
                                        total = len(logs)
                                        success = sum(1 for e in logs if (e[2] if len(e) == 5 else e[1]))
                                        failed = total - success
                                        ui.badge(f"{total} total").props("outline")
                                        ui.badge(f"{success} success", color="green")
                                        if failed > 0:
                                            ui.badge(f"{failed} failed", color="red")
                                
                                with ui.row().classes("items-center gap-2"):
                                    if logs:
                                        # Search input
                                        search_input = ui.input(placeholder="Filter logs...").props("dense outlined").classes("w-64")
                                        
                                        def clear_logs():
                                            execution_logs_ref["logs"].clear()  # Clear in-place to preserve reference
                                            state.deploy.reconcile_execution_logs.clear()  # Also clear persisted state
                                            save_state()
                                            logs_dialog.close()
                                            ui.notify("Logs cleared", type="info")
                                        ui.button("Clear All", icon="delete", on_click=clear_logs).props("flat color=negative")
                                    ui.button("Close", icon="close", on_click=logs_dialog.close).props("flat")
                            
                            if not logs:
                                with ui.column().classes("w-full h-full items-center justify-center"):
                                    ui.icon("inbox", size="4rem").classes("text-slate-300 mb-4")
                                    ui.label("No execution logs yet").classes("text-lg text-slate-500")
                                    ui.label("Run a command to see logs here.").classes("text-sm text-slate-400")
                            else:
                                # Main log content area - full height terminal style
                                with ui.scroll_area().classes("w-full flex-grow bg-slate-900 dark:bg-slate-950"):
                                    with ui.element("div").classes("p-6 font-mono text-sm"):
                                        for idx, entry in enumerate(logs):
                                            # Handle both old format (3-tuple) and new format (5-tuple)
                                            if len(entry) == 5:
                                                ts, cmd, ok, output, cwd = entry
                                            else:
                                                cmd, ok, output = entry
                                                ts = "unknown"
                                                cwd = "unknown"
                                            
                                            status_text = "SUCCESS" if ok else "FAILED"
                                            status_color = "text-green-400" if ok else "text-red-400"
                                            bg_color = "bg-green-900/20" if ok else "bg-red-900/20"
                                            
                                            # Log entry container
                                            with ui.element("div").classes(f"mb-4 p-4 rounded-lg {bg_color} border border-slate-700"):
                                                # Header row with timestamp and status
                                                with ui.row().classes("w-full items-center gap-4 mb-2"):
                                                    ui.label(f"#{idx + 1}").classes("text-slate-500 font-bold")
                                                    ui.label(f"[{ts}]").classes("text-slate-400")
                                                    ui.label(status_text).classes(f"{status_color} font-bold px-2 py-0.5 rounded text-xs")
                                                
                                                # Command line
                                                with ui.row().classes("w-full items-start gap-2 mb-2"):
                                                    ui.label("$").classes("text-cyan-400 font-bold")
                                                    ui.label(cmd).classes("text-white break-all whitespace-pre-wrap")
                                                
                                                # Working directory
                                                if cwd and cwd != "unknown":
                                                    ui.label(f"cwd: {cwd}").classes("text-slate-500 text-xs mb-2")
                                                
                                                # Output
                                                if output and output.strip():
                                                    ui.label("Output:").classes("text-slate-400 text-xs mt-2 mb-1")
                                                    with ui.element("pre").classes("text-xs bg-black/30 p-3 rounded overflow-x-auto whitespace-pre-wrap"):
                                                        line_color = "text-red-300" if not ok else "text-slate-300"
                                                        ui.label(output.strip()).classes(f"{line_color}")
                                                elif not ok:
                                                    ui.label("(no output captured)").classes("text-slate-500 text-xs italic")
                        
                        logs_dialog.open()
                    
                    ui.button(
                        "View Logs",
                        icon="article",
                        on_click=show_execution_logs,
                    ).props("flat").classes("text-slate-600")
    
    # Protection mismatch section - detect and fix state/YAML protection mismatches
    # Scan grid data for protection mismatches (state says protected but YAML says not, or vice versa)
    protection_mismatches = []
    
    def _extract_resource_key_from_address(address: str) -> str:
        """Extract the resource key from a Terraform state address.
        
        Address format: module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["key"]
        Returns: "key"
        """
        import re
        match = re.search(r'\["([^"]+)"\]$', address)
        if match:
            return match.group(1)
        return ""
    
    for row in grid_row_data:
        source_type = row.get("source_type", "")
        state_address = row.get("state_address")
        
        if source_type in EXTENDED_RESOURCE_TYPE_MAP and state_address:
            # Use the separate protection fields from grid row
            # yaml_protected = what user wants (from protected_resources set / YAML config)
            # state_protected = what TF state actually has (from address containing "protected_")
            yaml_protected = row.get("yaml_protected", False)
            state_protected = row.get("state_protected", False)
            
            # Check for mismatch
            if state_protected != yaml_protected:
                # Extract resource key from the state address (most reliable source)
                # Address format: module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["key"]
                resource_key = _extract_resource_key_from_address(state_address)
                
                # Fallback to source_key or project_name if extraction failed
                if not resource_key:
                    if source_type == "PRJ":
                        # For projects, source_key is the project key
                        resource_key = row.get("source_key", "")
                    else:
                        # For REP/PREP, project_name is the key (repos are keyed by project)
                        resource_key = row.get("project_name", row.get("source_key", ""))
                
                # Skip if we still don't have a key
                if not resource_key:
                    continue
                
                project_name = row.get("project_name") or resource_key
                protection_mismatches.append({
                    "type": source_type,
                    "key": resource_key,
                    "name": row.get("source_name", resource_key),
                    "state_protected": state_protected,
                    "yaml_protected": yaml_protected,
                    "project_name": project_name,
                })
    
    # Group mismatches by project to identify all related resources
    # And deduplicate since PRJ, REP, PREP may all show for same project
    unique_projects_with_mismatches = set()
    for m in protection_mismatches:
        unique_projects_with_mismatches.add(m.get("project_name") or m.get("key"))
    
    # Protection Intent Status Section
    # Show badges for pending YAML updates, TF state moves, and synced intents
    # Also show Recent Changes section with history from intent file
    _pending_yaml = protection_intent_manager.get_pending_yaml_updates()
    _pending_tf = protection_intent_manager.get_pending_tf_moves()
    _history = protection_intent_manager._history[-5:] if protection_intent_manager._history else []
    
    # Collect synced intents (applied_to_yaml=True AND applied_to_tf_state=True)
    _all_synced_intents = [
        (key, intent) for key, intent in protection_intent_manager._intent.items()
        if intent.applied_to_yaml and intent.applied_to_tf_state
    ]
    
    # Group synced intents by base resource key (PRJ, REP, PREP with same key are grouped)
    # Only show PRJ items in the count - REP/PREP are implicit
    _synced_prj_keys = set()
    _synced_orphan_items = []  # REP/PREP without matching PRJ
    for key, intent in _all_synced_intents:
        if ":" in key:
            rtype, rkey = key.split(":", 1)
        else:
            rtype = intent.resource_type or ""
            rkey = key
        
        if rtype == "PRJ":
            _synced_prj_keys.add(rkey)
        elif rtype in ("REP", "PREP"):
            # Check if there's a PRJ with this key already
            has_prj = any(
                (k == f"PRJ:{rkey}" or (i.resource_type == "PRJ" and k == rkey))
                for k, i in _all_synced_intents
            )
            if not has_prj:
                _synced_orphan_items.append((key, intent))
        else:
            # Other types shown as-is
            _synced_orphan_items.append((key, intent))
    
    # For display, group PRJ items with their linked REP/PREP
    _synced_intents = [(f"PRJ:{k}", protection_intent_manager._intent.get(f"PRJ:{k}") or 
                        protection_intent_manager._intent.get(k)) 
                       for k in _synced_prj_keys 
                       if protection_intent_manager._intent.get(f"PRJ:{k}") or protection_intent_manager._intent.get(k)]
    _synced_intents.extend(_synced_orphan_items)
    _synced_count = len(_synced_prj_keys) + len(_synced_orphan_items)  # Count projects (grouped) + orphans
    
    # Count pending TF applies — only intents that actually need a TF state move.
    # Uses needs_tf_move property which excludes sync_from_tf_state (already in sync)
    # and intents where TF state already matched at decision time.
    _pending_tf_count = sum(
        1 for intent in protection_intent_manager._intent.values()
        if intent.needs_tf_move
    )
    
    # Find mismatches that need intent clarification (no intent recorded yet)
    # Check using prefixed key (TYPE:key) to match intent storage format
    # IMPORTANT: Only show PRJ (project) items - REP and PREP are implicitly coupled
    # When you protect a project, the repo and project-repo link must move together
    _all_mismatches_needing_intent = [
        m for m in protection_mismatches
        if not protection_intent_manager.has_intent(f"{m.get('type', '')}:{m['key']}" if m.get('type') else m['key'])
    ]
    
    # Filter to only show PRJ items in the UI - REP/PREP follow automatically
    # Also show items without a type (legacy) or items that don't have a PRJ counterpart
    _prj_keys = {m['key'] for m in _all_mismatches_needing_intent if m.get('type') == 'PRJ'}
    _mismatches_needing_intent = [
        m for m in _all_mismatches_needing_intent
        if m.get('type') == 'PRJ'  # Show all projects
        or (m.get('type') not in ('REP', 'PREP'))  # Show non-repo types  
        or (m.get('type') in ('REP', 'PREP') and m['key'] not in _prj_keys)  # Show orphan repos without matching project
    ]
    
    # Protection Intent Status section - always show so users know the feature exists
    # Added flex-shrink: 0 and max-width to prevent being pushed sideways by sibling elements
    with ui.card().classes("w-full p-4 mt-4").style("border: 1px solid #CBD5E1; max-width: 100%; flex-shrink: 0; overflow: hidden;"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-2 flex-grow"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("checklist", size="sm").classes("text-slate-600")
                    ui.label("Protection Intent Status").classes("font-semibold text-slate-700")
                
                # Status badges row
                with ui.row().classes("items-center gap-3 mt-2 flex-wrap"):
                    # FIRST: Needs Clarification (red/pink) - most important
                    if len(_mismatches_needing_intent) > 0:
                        ui.label(f"⚠️ Needs Clarification ({len(_mismatches_needing_intent)})").classes(
                            "bg-red-100 text-red-800 px-2 py-1 rounded text-xs font-medium"
                        )
                    
                    # Pending: Generate Protection Changes (orange)
                    if len(_pending_yaml) > 0:
                        ui.label(f"Pending: Generate ({len(_pending_yaml)})").classes(
                            "bg-amber-100 text-amber-800 px-2 py-1 rounded text-xs font-medium"
                        )
                    
                    # Pending: TF Init/Plan/Apply (blue)
                    pending_tf_count = sum(
                        1 for intent in protection_intent_manager._intent.values()
                        if intent.applied_to_yaml and not intent.applied_to_tf_state
                    )
                    if pending_tf_count > 0:
                        ui.label(f"Pending: TF Apply ({pending_tf_count})").classes(
                            "bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-medium"
                        )
                    
                    # Synced (green)
                    if _synced_count > 0:
                        ui.label(f"Synced ({_synced_count})").classes(
                            "bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-medium"
                        )
                    
                    # If nothing at all, show neutral state
                    if len(_mismatches_needing_intent) == 0 and len(_pending_yaml) == 0 and pending_tf_count == 0 and _synced_count == 0:
                        ui.label("No mismatches or pending changes").classes("text-xs text-slate-500")
                
                # Synced intents - expandable section to show details
                if _synced_count > 0:
                    # Split synced intents into protected-first and unprotected
                    _synced_protected = [(k, i) for k, i in _synced_intents if i is not None and i.protected]
                    _synced_unprotected = [(k, i) for k, i in _synced_intents if i is not None and not i.protected]
                    _protected_count = len(_synced_protected)
                    _unprotected_count = len(_synced_unprotected)
                    
                    with ui.expansion(
                        f"✅ View {_synced_count} synced intent(s)",
                        icon="verified"
                    ).classes("w-full mt-3 border border-green-300 rounded"):
                        ui.label(
                            "These resources have protection intent that is fully synced with both YAML and Terraform state. "
                            "Projects (PRJ) include their linked Repository (REP) and Project-Repository (PREP) automatically."
                        ).classes("text-xs opacity-70 mb-3")
                        
                        def _render_synced_intent_card(resource_key, intent):
                            """Render a single synced intent card."""
                            protection_status = "protected" if intent.protected else "unprotected"
                            status_color = "blue" if intent.protected else "grey"
                            status_icon = "shield" if intent.protected else "shield_outlined" if not intent.protected else ""
                            
                            # Parse the key to get type and base key
                            if ":" in resource_key:
                                rtype, rkey = resource_key.split(":", 1)
                            else:
                                rtype = intent.resource_type or ""
                                rkey = resource_key
                            
                            # Check if this is a PRJ with linked resources
                            is_project = rtype == "PRJ"
                            is_orphan = rtype not in ("PRJ", "REP", "PREP") and not rtype
                            
                            # For projects, check for linked REPO
                            linked_resources = []
                            if is_project:
                                repo_key = f"REPO:{rkey}"
                                if repo_key in protection_intent_manager._intent:
                                    linked_resources.append("REPO")
                            
                            # Use different styling based on protection status
                            if is_orphan:
                                card_bg = "bg-amber-500 bg-opacity-10"
                            elif intent.protected:
                                card_bg = "bg-green-500 bg-opacity-10"
                            else:
                                card_bg = "bg-slate-500 bg-opacity-5"
                            
                            with ui.card().classes(f"w-full p-2 mb-2 {card_bg}"):
                                with ui.row().classes("items-center justify-between"):
                                    with ui.column().classes("gap-1 flex-grow"):
                                        # Show resource name with linked indicator for projects
                                        if is_project and linked_resources:
                                            ui.label(f"🔗 {rkey} (PRJ + {' + '.join(linked_resources)})").classes("font-medium text-sm")
                                        else:
                                            ui.label(f"{resource_key}").classes("font-medium text-sm")
                                        
                                        with ui.row().classes("items-center gap-2"):
                                            ui.badge(f"Intent: {protection_status}").props(
                                                f"color={status_color} dense"
                                            )
                                            ui.icon("check_circle", size="xs").classes("text-green-600")
                                            ui.label("YAML ✓").classes("text-xs text-green-700")
                                            ui.icon("check_circle", size="xs").classes("text-green-600")
                                            ui.label("TF State ✓").classes("text-xs text-green-700")
                                        
                                        # Show source/reason if available
                                        if intent.reason:
                                            ui.label(f"Reason: {intent.reason}").classes("text-xs opacity-60")
                                    
                                    # Add delete button for orphan entries
                                    if is_orphan:
                                        def make_delete_handler(rkey=resource_key):
                                            def handler():
                                                # Remove the orphan entry from the intent file
                                                if rkey in protection_intent_manager._intent:
                                                    del protection_intent_manager._intent[rkey]
                                                    protection_intent_manager.save()
                                                    ui.notify(f"Removed orphan intent: {rkey}", type="info")
                                                    ui.navigate.reload()
                                            return handler
                                        
                                        ui.button(
                                            icon="delete",
                                            on_click=make_delete_handler(),
                                        ).props("flat dense color=warning").tooltip("Remove this orphan entry")
                        
                        # Protected intents first (always visible)
                        if _protected_count > 0:
                            ui.label(f"Protected ({_protected_count})").classes("text-xs font-semibold text-green-700 mb-1")
                            for resource_key, intent in _synced_protected:
                                _render_synced_intent_card(resource_key, intent)
                        
                        # Unprotected intents in a nested collapsible section
                        if _unprotected_count > 0:
                            ui.separator().classes("my-2")
                            with ui.expansion(
                                f"Unprotected ({_unprotected_count})",
                                icon="shield_outlined",
                            ).classes("w-full border border-slate-200 rounded").props("dense"):
                                ui.label(
                                    "Resources explicitly marked as unprotected."
                                ).classes("text-xs opacity-60 mb-2")
                                for resource_key, intent in _synced_unprotected:
                                    _render_synced_intent_card(resource_key, intent)
                
                # Mismatches needing clarification - expandable section
                if len(_mismatches_needing_intent) > 0:
                    with ui.expansion(
                        f"⚠️ {len(_mismatches_needing_intent)} project(s) need your intent clarification",
                        icon="help_outline"
                    ).classes("w-full mt-3 border border-red-400 rounded"):
                        ui.label(
                            "These projects have a mismatch between Terraform state and YAML configuration. "
                            "When you protect a project, its linked repository (REP) and project-repository link (PREP) "
                            "are automatically protected together."
                        ).classes("text-xs opacity-70 mb-3")
                        
                        for m in _mismatches_needing_intent[:10]:  # Show first 10
                            resource_key = m["key"]
                            source_type = m["type"]
                            state_protected = m["state_protected"]
                            yaml_protected = m["yaml_protected"]
                            
                            state_label = "protected" if state_protected else "unprotected"
                            yaml_label = "protected" if yaml_protected else "unprotected"
                            
                            with ui.card().classes("w-full p-2 mb-2 bg-red-500 bg-opacity-10"):
                                with ui.row().classes("items-center justify-between"):
                                    with ui.column().classes("gap-1"):
                                        # Show project with indicator that REP/PREP are linked
                                        if source_type == "PRJ":
                                            ui.label(f"🔗 Project: {resource_key}").classes("font-medium text-sm")
                                            ui.label("(includes linked Repository + Project-Repository)").classes("text-xs opacity-60")
                                        else:
                                            ui.label(f"{source_type}: {resource_key}").classes("font-medium text-sm")
                                        with ui.row().classes("items-center gap-2"):
                                            ui.badge(f"State: {state_label}").props(
                                                f"color={'blue' if state_protected else 'grey'} dense"
                                            )
                                            ui.icon("arrow_forward", size="xs").classes("opacity-50")
                                            ui.badge(f"YAML: {yaml_label}").props(
                                                f"color={'blue' if yaml_protected else 'grey'} dense"
                                            )
                                    
                                    # Quick intent buttons
                                    with ui.row().classes("items-center gap-1"):
                                        def make_protect_handler(rkey=resource_key, rtype=source_type):
                                            def handler():
                                                # Set intent for this resource with prefixed key
                                                prefixed_key = f"{rtype}:{rkey}" if rtype else rkey
                                                protection_intent_manager.set_intent(
                                                    key=prefixed_key,
                                                    protected=True,
                                                    source="clarification_panel",
                                                    reason="User clarified intent: protect",
                                                    resource_type=rtype or None,
                                                )
                                                
                                                # CASCADE: When protecting a project, also set intent for linked REPO (covers both dbtcloud_repository and dbtcloud_project_repository)
                                                if rtype == "PRJ":
                                                    protection_intent_manager.set_intent(
                                                        key=f"REPO:{rkey}",
                                                        protected=True,
                                                        source="clarification_panel_cascade",
                                                        reason="Auto-cascaded from project protection (covers repository + project_repository_link)",
                                                        resource_type="REPO",
                                                    )
                                                
                                                protection_intent_manager.save()
                                                ui.notify(f"Intent set: PROTECT {rkey}" + (" (+REP, +PREP)" if rtype == "PRJ" else ""), type="positive")
                                                ui.navigate.reload()
                                            return handler
                                        
                                        def make_unprotect_handler(rkey=resource_key, rtype=source_type):
                                            def handler():
                                                # Set intent for this resource with prefixed key
                                                prefixed_key = f"{rtype}:{rkey}" if rtype else rkey
                                                protection_intent_manager.set_intent(
                                                    key=prefixed_key,
                                                    protected=False,
                                                    source="clarification_panel",
                                                    reason="User clarified intent: unprotect",
                                                    resource_type=rtype or None,
                                                )
                                                
                                                # CASCADE: When unprotecting a project, also set intent for linked REPO (covers both dbtcloud_repository and dbtcloud_project_repository)
                                                if rtype == "PRJ":
                                                    protection_intent_manager.set_intent(
                                                        key=f"REPO:{rkey}",
                                                        protected=False,
                                                        source="clarification_panel_cascade",
                                                        reason="Auto-cascaded from project unprotection (covers repository + project_repository_link)",
                                                        resource_type="REPO",
                                                    )
                                                
                                                protection_intent_manager.save()
                                                ui.notify(f"Intent set: UNPROTECT {rkey}" + (" (+REP, +PREP)" if rtype == "PRJ" else ""), type="info")
                                                ui.navigate.reload()
                                            return handler
                                        
                                        ui.button(
                                            "Protect",
                                            icon="shield",
                                            on_click=make_protect_handler(),
                                        ).props("dense size=sm color=positive")
                                        
                                        ui.button(
                                            "Unprotect",
                                            icon="lock_open",
                                            on_click=make_unprotect_handler(),
                                        ).props("dense size=sm color=warning")
                        
                        if len(_mismatches_needing_intent) > 10:
                            ui.label(f"... and {len(_mismatches_needing_intent) - 10} more").classes("text-xs opacity-60")
                        
                        # Bulk actions
                        ui.separator().classes("my-2")
                        with ui.row().classes("items-center gap-2"):
                            def protect_all_mismatches():
                                count = 0
                                for m in _mismatches_needing_intent:
                                    # Use prefixed key for intent: TYPE:key
                                    resource_type = m.get("type", "")
                                    base_key = m["key"]
                                    prefixed_key = f"{resource_type}:{base_key}" if resource_type else base_key
                                    protection_intent_manager.set_intent(
                                        key=prefixed_key,
                                        protected=True,
                                        source="clarification_bulk",
                                        reason="Bulk protect all mismatches",
                                        resource_type=resource_type or None,
                                    )
                                    count += 1
                                    
                                    # CASCADE: When protecting a project, also set intent for linked REPO (covers both dbtcloud_repository and dbtcloud_project_repository)
                                    if resource_type == "PRJ":
                                        protection_intent_manager.set_intent(
                                            key=f"REPO:{base_key}",
                                            protected=True,
                                            source="clarification_bulk_cascade",
                                            reason="Auto-cascaded from project protection (covers repository + project_repository_link)",
                                            resource_type="REPO",
                                        )
                                        count += 1  # REPO (single intent covers both TF resources)
                                
                                protection_intent_manager.save()
                                ui.notify(f"Set intent to PROTECT for {count} resources (including cascaded)", type="positive")
                                ui.navigate.reload()
                            
                            def unprotect_all_mismatches():
                                count = 0
                                for m in _mismatches_needing_intent:
                                    # Use prefixed key for intent: TYPE:key
                                    resource_type = m.get("type", "")
                                    base_key = m["key"]
                                    prefixed_key = f"{resource_type}:{base_key}" if resource_type else base_key
                                    protection_intent_manager.set_intent(
                                        key=prefixed_key,
                                        protected=False,
                                        source="clarification_bulk",
                                        reason="Bulk unprotect all mismatches",
                                        resource_type=resource_type or None,
                                    )
                                    count += 1
                                    
                                    # CASCADE: When unprotecting a project, also set intent for linked REPO (covers both dbtcloud_repository and dbtcloud_project_repository)
                                    if resource_type == "PRJ":
                                        protection_intent_manager.set_intent(
                                            key=f"REPO:{base_key}",
                                            protected=False,
                                            source="clarification_bulk_cascade",
                                            reason="Auto-cascaded from project unprotection (covers repository + project_repository_link)",
                                            resource_type="REPO",
                                        )
                                        count += 1  # REPO (single intent covers both TF resources)
                                
                                protection_intent_manager.save()
                                ui.notify(f"Set intent to UNPROTECT for {count} resources (including cascaded)", type="info")
                                ui.navigate.reload()
                            
                            ui.button(
                                f"Protect All ({len(_mismatches_needing_intent)})",
                                icon="shield",
                                on_click=protect_all_mismatches,
                            ).props("dense size=sm color=positive outline")
                            
                            ui.button(
                                f"Unprotect All ({len(_mismatches_needing_intent)})",
                                icon="lock_open",
                                on_click=unprotect_all_mismatches,
                            ).props("dense size=sm color=warning outline")
                
                # Pending intents section - show recorded intents with undo option
                _all_pending = [(k, i) for k, i in protection_intent_manager._intent.items() if not i.applied_to_yaml]
                if len(_all_pending) > 0:
                    with ui.expansion(
                        f"📝 Pending Intents ({len(_all_pending)}) - click to review/undo",
                        icon="edit_note"
                    ).classes("w-full mt-3 border border-amber-400 rounded"):
                        ui.label(
                            "These intents have been recorded but not yet applied. "
                            "Click 'Undo' to remove an intent, or 'Generate Protection Changes' to apply them."
                        ).classes("text-xs opacity-70 mb-3")
                        
                        for rkey, intent in _all_pending[:15]:  # Show first 15
                            action_label = "PROTECT" if intent.protected else "UNPROTECT"
                            action_color = "positive" if intent.protected else "warning"
                            
                            with ui.card().classes("w-full p-2 mb-2 bg-amber-500 bg-opacity-10"):
                                with ui.row().classes("items-center justify-between"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(f"{rkey}").classes("font-medium text-sm")
                                        with ui.row().classes("items-center gap-2"):
                                            ui.badge(f"Intent: {action_label}").props(f"color={action_color} dense")
                                            ui.label(f"Set: {intent.set_at[:16]}").classes("text-xs opacity-60")
                                    
                                    # Undo button
                                    def make_undo_handler(key_to_undo=rkey):
                                        def handler():
                                            if protection_intent_manager.has_intent(key_to_undo):
                                                intent_to_undo = protection_intent_manager._intent[key_to_undo]
                                                # Revert protected_resources to match
                                                source_key = _find_source_key_for_intent_key(key_to_undo)
                                                if source_key:
                                                    if intent_to_undo.protected:
                                                        # Was a protect intent → remove from protected_resources
                                                        state.map.protected_resources.discard(source_key)
                                                    else:
                                                        # Was an unprotect intent → add back to protected_resources
                                                        state.map.protected_resources.add(source_key)
                                                del protection_intent_manager._intent[key_to_undo]
                                                protection_intent_manager.save()
                                                save_state()
                                                ui.notify(f"Removed intent for {key_to_undo}", type="info")
                                                ui.navigate.reload()
                                        return handler
                                    
                                    ui.button(
                                        "Undo",
                                        icon="undo",
                                        on_click=make_undo_handler(),
                                    ).props("dense size=sm color=grey flat")
                        
                        if len(_all_pending) > 15:
                            ui.label(f"... and {len(_all_pending) - 15} more").classes("text-xs opacity-60")
                        
                        # Clear all button
                        ui.separator().classes("my-2")
                        def clear_all_pending():
                            for key, intent_obj in _all_pending:
                                if protection_intent_manager.has_intent(key):
                                    # Revert protected_resources for each intent
                                    source_key = _find_source_key_for_intent_key(key)
                                    if source_key:
                                        if intent_obj.protected:
                                            state.map.protected_resources.discard(source_key)
                                        else:
                                            state.map.protected_resources.add(source_key)
                                    del protection_intent_manager._intent[key]
                            protection_intent_manager.save()
                            save_state()
                            ui.notify(f"Cleared {len(_all_pending)} pending intents", type="info")
                            ui.navigate.reload()
                        
                        ui.button(
                            f"Clear All Pending ({len(_all_pending)})",
                            icon="delete_sweep",
                            on_click=clear_all_pending,
                        ).props("dense size=sm color=negative outline")
                
                with ui.row().classes("items-center gap-3 mt-2"):
                        # Copy for AI button
                        def copy_for_ai():
                            """Generate structured markdown summary for AI diagnostics."""
                            from pathlib import Path
                            
                            tf_dir = state.deploy.terraform_dir or "deployments/migration"
                            pending = protection_intent_manager.get_pending_yaml_updates()
                            history = protection_intent_manager._history[-10:]
                            
                            lines = [
                                "## Protection Intent Status",
                                "",
                                f"**Pending Changes:** {protection_intent_manager.intent_count} resources",
                                f"**TF Path:** {tf_dir}",
                                "",
                            ]
                            
                            # Resources with Pending Generate
                            pending_gen_resources = [(k, i) for k, i in protection_intent_manager._intent.items() if not i.applied_to_yaml]
                            if pending_gen_resources:
                                lines.append("### Resources with Pending Generate:")
                                for key, intent in pending_gen_resources:
                                    action = "protect" if intent.protected else "unprotect"
                                    lines.append(f"- {key}: {action} (YAML: protected={intent.protected})")
                                lines.append("")
                            
                            # Resources with Pending TF Apply
                            pending_tf_resources = [(k, i) for k, i in protection_intent_manager._intent.items() if i.applied_to_yaml and not i.applied_to_tf_state]
                            if pending_tf_resources:
                                lines.append("### Resources with Pending TF Apply:")
                                for key, intent in pending_tf_resources:
                                    action = "protect" if intent.protected else "unprotect"
                                    lines.append(f"- {key}: {action} (YAML updated, awaiting TF apply)")
                                lines.append("")
                            
                            # Recent History
                            if history:
                                lines.append("### Recent History:")
                                lines.append("| Timestamp | Resource | Action | Source |")
                                lines.append("|-----------|----------|--------|--------|")
                                for entry in reversed(history):
                                    ts = entry.timestamp[:19].replace("T", " ") if entry.timestamp else ""
                                    lines.append(f"| {ts} | {entry.resource_key} | {entry.action} | {entry.source} |")
                                lines.append("")
                            
                            # Current YAML Protected Resources (from parsed YAML file)
                            yaml_protected = state.map.protected_resources or set()
                            if yaml_protected:
                                lines.append(f"### Current YAML Protected Resources ({len(yaml_protected)}):")
                                for key in sorted(list(yaml_protected)[:20]):
                                    lines.append(f"- {key}")
                                if len(yaml_protected) > 20:
                                    lines.append(f"- ... and {len(yaml_protected) - 20} more")
                                lines.append("")
                            
                            # Synced Intents (intent file - resources with intent decisions)
                            synced_intents = [(k, i) for k, i in protection_intent_manager._intent.items() 
                                              if i.applied_to_yaml and i.applied_to_tf_state]
                            if synced_intents:
                                protected_synced = [(k, i) for k, i in synced_intents if i.protected]
                                unprotected_synced = [(k, i) for k, i in synced_intents if not i.protected]
                                
                                if protected_synced:
                                    lines.append(f"### Synced Protected Intents ({len(protected_synced)}):")
                                    for key, intent in sorted(protected_synced, key=lambda x: x[0])[:20]:
                                        rtype = intent.resource_type or "?"
                                        lines.append(f"- {key} ({rtype})")
                                    if len(protected_synced) > 20:
                                        lines.append(f"- ... and {len(protected_synced) - 20} more")
                                    lines.append("")
                                
                                if unprotected_synced:
                                    lines.append(f"### Synced Unprotected Intents ({len(unprotected_synced)}):")
                                    for key, intent in sorted(unprotected_synced, key=lambda x: x[0])[:10]:
                                        rtype = intent.resource_type or "?"
                                        lines.append(f"- {key} ({rtype})")
                                    if len(unprotected_synced) > 10:
                                        lines.append(f"- ... and {len(unprotected_synced) - 10} more")
                                    lines.append("")
                            
                            summary = "\n".join(lines)
                            ui.run_javascript(f'navigator.clipboard.writeText({repr(summary)})')
                            ui.notify("Copied AI diagnostic summary to clipboard!", type="positive")
                        
                        ui.button(
                            "Copy for AI",
                            icon="psychology",
                            on_click=copy_for_ai,
                        ).props("flat dense").tooltip("Copy structured summary for AI debugging")
                
                # Generate Protection Changes button
                # Enable if there are pending YAML updates OR pending TF apply items (for re-analysis)
                has_pending = len(_pending_yaml) > 0
                can_generate = has_pending or _pending_tf_count > 0
                
                def start_generate_protection_changes():
                    """Start the generate protection changes workflow (creates dialog synchronously)."""
                    from pathlib import Path
                    import asyncio
                    
                    # Create streaming dialog SYNCHRONOUSLY in UI thread
                    dialog = ui.dialog()
                    output_lines = []
                    cancelled = {"value": False}
                    
                    with dialog:
                        with ui.card().classes("p-4").style("width: 800px; max-width: 90vw;"):
                            with ui.row().classes("w-full items-center justify-between mb-4"):
                                ui.label("Generating Protection Changes...").classes("text-lg font-semibold")
                                with ui.row().classes("gap-2"):
                                    def copy_output():
                                        text = "\n".join(output_lines)
                                        ui.run_javascript(f'navigator.clipboard.writeText({repr(text)})')
                                        ui.notify("Copied to clipboard!", type="positive")
                                    
                                    ui.button("Copy", icon="content_copy", on_click=copy_output).props("flat dense")
                                    
                                    def cancel_operation():
                                        cancelled["value"] = True
                                        ui.notify("Operation cancelled", type="warning")
                                    
                                    cancel_btn = ui.button("Cancel", icon="close", on_click=cancel_operation).props("flat dense color=red")
                            
                            output_area = ui.column().classes("w-full").style(
                                "max-height: 400px; overflow-y: auto; background: #1e1e1e; "
                                "padding: 12px; border-radius: 8px; font-family: monospace; font-size: 12px;"
                            )
                            
                            def close_and_reload():
                                """Close dialog and reload page to show Terraform buttons."""
                                dialog.close()
                                ui.navigate.reload()
                            
                            close_btn = ui.button("Close & Continue", on_click=close_and_reload).props("color=primary").classes("mt-4")
                            close_btn.set_visibility(False)  # Show when done
                    
                    def append_output(text: str, color: str = "#e0e0e0"):
                        output_lines.append(text)
                        with output_area:
                            ui.label(text).style(f"color: {color}; white-space: pre-wrap;")
                    
                    # Open dialog synchronously
                    dialog.open()
                    
                    # Now define and run async work
                    async def do_generate_work():
                        await asyncio.sleep(0.1)  # Let dialog render
                        
                        try:
                            # Step 1: Read pending intents (both new and re-analysis)
                            append_output("📋 Reading pending intents...")
                            pending_yaml = protection_intent_manager.get_pending_yaml_updates()
                            pending_tf = {k: i for k, i in protection_intent_manager._intent.items()
                                          if i.applied_to_yaml and not i.applied_to_tf_state}
                            
                            # Combine: new items + re-analysis items
                            pending = {**pending_yaml, **pending_tf}
                            
                            if len(pending_yaml) > 0:
                                append_output(f"   Found {len(pending_yaml)} resources with pending YAML changes", "#10B981")
                            if len(pending_tf) > 0:
                                append_output(f"   Found {len(pending_tf)} resources for re-analysis (pending TF apply)", "#60A5FA")
                            if len(pending) == 0:
                                append_output("   No pending changes found", "#6B7280")
                            await asyncio.sleep(0.2)
                            
                            if cancelled["value"]:
                                append_output("\n❌ Cancelled by user", "#F59E0B")
                                cancel_btn.set_visibility(False)
                                close_btn.set_visibility(True)
                                return
                            
                            # Step 2: Show per-resource updates
                            for key, intent in pending.items():
                                if cancelled["value"]:
                                    break
                                status = "protected" if intent.protected else "unprotected"
                                append_output(f"   - {key}: {status}")
                            await asyncio.sleep(0.2)
                            
                            if cancelled["value"]:
                                append_output("\n❌ Cancelled by user", "#F59E0B")
                                cancel_btn.set_visibility(False)
                                close_btn.set_visibility(True)
                                return
                            
                            # Step 3: Update YAML files
                            append_output("\n📝 Updating YAML files...")
                            
                            # Get terraform directory
                            tf_dir = state.deploy.terraform_dir or "deployments/migration"
                            tf_path = Path(tf_dir)
                            if not tf_path.is_absolute():
                                # Project root is parent of importer directory (not inside importer)
                                project_root = Path(__file__).parent.parent.parent.parent.resolve()
                                tf_path = project_root / tf_dir
                            
                            # Look for YAML config file - check multiple possible locations
                            yaml_file = tf_path / "dbt-cloud-config.yml"
                            if not yaml_file.exists():
                                # Try fetch output dir
                                if state.fetch.output_dir:
                                    fetch_yaml = Path(state.fetch.output_dir) / "dbt-cloud-config.yml"
                                    if fetch_yaml.exists():
                                        yaml_file = fetch_yaml
                            
                            if not yaml_file.exists():
                                # Find any YAML file matching our naming pattern in dev_support/samples
                                samples_dir = Path(__file__).parent.parent.parent.resolve() / "dev_support" / "samples"
                                yaml_files = list(samples_dir.glob("*__yaml__*.yml")) + list(samples_dir.glob("account_*.yml"))
                                if yaml_files:
                                    yaml_file = sorted(yaml_files, key=lambda f: f.stat().st_mtime, reverse=True)[0]
                            
                            if not yaml_file.exists():
                                append_output(f"   ⚠️ YAML file not found: {yaml_file}", "#F59E0B")
                                append_output("   Skipping YAML update - will still generate moved blocks", "#F59E0B")
                            else:
                                from importer.web.utils.adoption_yaml_updater import apply_protection_from_set, apply_unprotection_from_set
                                
                                # Pre-step: Merge missing sub-resources from target baseline
                                # into the deployment YAML. This ensures resources that exist
                                # in the target/state but weren't part of the source selection
                                # are present in the YAML so protection flags can be applied.
                                try:
                                    baseline_yaml_path = normalize_target_fetch(state)
                                    if baseline_yaml_path:
                                        import yaml as _yaml_merge
                                        from importer.web.utils.adoption_yaml_updater import merge_yaml_configs
                                        
                                        with open(baseline_yaml_path, "r") as _bf:
                                            baseline_config = _yaml_merge.safe_load(_bf) or {}
                                        with open(str(yaml_file), "r") as _df:
                                            deploy_config = _yaml_merge.safe_load(_df) or {}
                                        
                                        # Filter baseline to only projects already in deploy config.
                                        # Without this filter, ALL target projects (including ones
                                        # that exist in target but aren't adopted/managed) would be
                                        # introduced into the deploy YAML, causing TF to create them.
                                        # We only want to fill sub-resources (env vars, etc.) within
                                        # projects that the user has already selected for management.
                                        deploy_project_keys = {
                                            p.get("key") for p in deploy_config.get("projects", [])
                                            if p.get("key")
                                        }
                                        if baseline_config.get("projects"):
                                            baseline_config["projects"] = [
                                                p for p in baseline_config["projects"]
                                                if p.get("key") in deploy_project_keys
                                            ]
                                        
                                        # Merge: baseline is the base (preserves all its items),
                                        # deploy is the source (deploy values win where both exist).
                                        # Result: deploy customizations preserved + baseline-only
                                        # sub-resources (like missing env vars) are filled in.
                                        merged = merge_yaml_configs(baseline_config, deploy_config)
                                        
                                        with open(str(yaml_file), "w") as _wf:
                                            _yaml_merge.dump(merged, _wf, default_flow_style=False, sort_keys=False, allow_unicode=True)
                                        append_output("   ✓ Merged target baseline into deployment YAML (fills missing resources)", "#60A5FA")
                                    else:
                                        append_output("   ⚠️ No target baseline available — resources not in YAML may not be updated", "#F59E0B")
                                except Exception as merge_err:
                                    logger.warning(f"Baseline merge failed (non-fatal): {merge_err}")
                                    append_output(f"   ⚠️ Baseline merge skipped: {merge_err}", "#F59E0B")
                                
                                # Separate keys by protection status
                                keys_to_protect = {k for k, i in pending.items() if i.protected}
                                keys_to_unprotect = {k for k, i in pending.items() if not i.protected}
                                
                                if keys_to_protect:
                                    apply_protection_from_set(str(yaml_file), keys_to_protect)
                                    append_output(f"   ✓ Applied protection to {len(keys_to_protect)} resources", "#10B981")
                                
                                if keys_to_unprotect:
                                    apply_unprotection_from_set(str(yaml_file), keys_to_unprotect)
                                    append_output(f"   ✓ Removed protection from {len(keys_to_unprotect)} resources", "#10B981")
                                
                                append_output(f"   Updated {yaml_file.name}")
                            
                            await asyncio.sleep(0.2)
                            
                            if cancelled["value"]:
                                append_output("\n❌ Cancelled by user", "#F59E0B")
                                cancel_btn.set_visibility(False)
                                close_btn.set_visibility(True)
                                return
                            
                            # Step 3b: Regenerate Terraform HCL from the updated YAML
                            # This is CRITICAL - moves resource declarations between
                            # protected/unprotected for_each maps so moved blocks work.
                            append_output("\n🔧 Regenerating Terraform HCL files...")
                            try:
                                from importer.yaml_converter import YamlToTerraformConverter
                                converter = YamlToTerraformConverter()
                                await asyncio.to_thread(
                                    converter.convert,
                                    str(yaml_file),
                                    str(tf_path),
                                )
                                append_output(f"   ✓ Terraform HCL regenerated from {yaml_file.name}", "#10B981")
                            except Exception as e:
                                append_output(f"   ⚠️ HCL regeneration warning: {e}", "#F59E0B")
                                append_output("   Continuing with moved blocks generation...", "#F59E0B")
                            
                            await asyncio.sleep(0.2)
                            
                            if cancelled["value"]:
                                append_output("\n❌ Cancelled by user", "#F59E0B")
                                cancel_btn.set_visibility(False)
                                close_btn.set_visibility(True)
                                return
                            
                            # Step 4: Generate protection_moves.tf
                            append_output("\n🔄 Generating protection_moves.tf...")
                            
                            from importer.web.utils.protection_manager import generate_repair_moved_blocks, ProtectionMismatch, RESOURCE_TYPE_MAP, detect_protection_mismatches
                            
                            # Build ProtectionMismatch objects from pending intents
                            moves_data = []
                            module_prefix = "module.dbt_cloud.module.projects_v2[0]"
                            
                            # Track which resource keys we've added (to avoid duplicates)
                            added_keys = set()
                            
                            def add_mismatch(res_type: str, res_key: str, is_protected: bool):
                                """Helper to add a ProtectionMismatch for a resource.
                                
                                Uses RESOURCE_TYPE_MAP to support all resource types:
                                PRJ, ENV, JOB, REP, PREP, EXTATTR.
                                """
                                combo_key = f"{res_type}:{res_key}"
                                if combo_key in added_keys:
                                    return
                                
                                if res_type not in RESOURCE_TYPE_MAP:
                                    return  # Unknown type not in RESOURCE_TYPE_MAP
                                
                                added_keys.add(combo_key)
                                
                                tf_type, unprotected_name, protected_name = RESOURCE_TYPE_MAP[res_type]
                                
                                if is_protected:
                                    # Moving from unprotected to protected
                                    state_addr = f'{module_prefix}.{tf_type}.{unprotected_name}["{res_key}"]'
                                    expected_addr = f'{module_prefix}.{tf_type}.{protected_name}["{res_key}"]'
                                else:
                                    # Moving from protected to unprotected
                                    state_addr = f'{module_prefix}.{tf_type}.{protected_name}["{res_key}"]'
                                    expected_addr = f'{module_prefix}.{tf_type}.{unprotected_name}["{res_key}"]'
                                
                                mismatch = ProtectionMismatch(
                                    resource_key=res_key,
                                    resource_type=res_type,
                                    yaml_protected=is_protected,
                                    state_protected=not is_protected,
                                    state_address=state_addr,
                                    expected_address=expected_addr,
                                )
                                moves_data.append(mismatch)
                            
                            for key, intent in pending.items():
                                # Parse key to get resource type and resource key
                                # Key format is "TYPE:resource_key" (e.g., "PRJ:my_project", "REPO:my_project")
                                # REPO covers both dbtcloud_repository and dbtcloud_project_repository
                                if ":" in key:
                                    resource_type, resource_key = key.split(":", 1)
                                else:
                                    # Legacy key without type prefix
                                    resource_type = intent.resource_type if intent.resource_type else "PRJ"
                                    resource_key = key
                                
                                yaml_protected = intent.protected
                                
                                # Add the mismatch for this resource
                                add_mismatch(resource_type, resource_key, yaml_protected)
                                
                                # IMPORTANT: When protecting a PROJECT (PRJ), also add moved blocks
                                # for the associated repository (REP) and project-repository link (PREP)
                                # since the module uses project protection status for all three
                                if resource_type == "PRJ":
                                    add_mismatch("REP", resource_key, yaml_protected)
                                    add_mismatch("PREP", resource_key, yaml_protected)
                            
                            # Also detect "orphaned" YAML-vs-TF-state mismatches
                            # (e.g. ENV/JOB/VAR resources marked protected in YAML from a
                            # prior session whose moved blocks were never applied)
                            try:
                                import json as _json_state; import yaml as _yaml_state
                                tf_state_file = tf_path / "terraform.tfstate"
                                if tf_state_file.exists() and yaml_file.exists():
                                    with open(str(tf_state_file), "r") as _sf:
                                        _tf_state_raw = _json_state.load(_sf)
                                    with open(str(yaml_file), "r") as _yf:
                                        _yaml_config = _yaml_state.safe_load(_yf) or {}
                                    
                                    all_mismatches = detect_protection_mismatches(
                                        _yaml_config, _tf_state_raw, module_prefix
                                    )
                                    
                                    # Merge mismatches not already covered by pending intents
                                    _new_mismatch_count = 0
                                    for mm in all_mismatches:
                                        combo_key = f"{mm.resource_type}:{mm.resource_key}"
                                        if combo_key not in added_keys:
                                            added_keys.add(combo_key)
                                            moves_data.append(mm)
                                            _new_mismatch_count += 1
                                    
                                    if _new_mismatch_count > 0:
                                        append_output(f"   ✓ Found {_new_mismatch_count} additional YAML-vs-state mismatches", "#60A5FA")
                                    
                            except Exception as _detect_err:
                                logger.warning(f"detect_protection_mismatches failed (non-fatal): {_detect_err}")
                                append_output(f"   ⚠️ YAML-vs-state detection skipped: {_detect_err}", "#F59E0B")
                            
                            # Determine output path for moved blocks - prefer tf_path, fallback to dev_support/samples
                            if tf_path.exists():
                                moves_file = tf_path / "protection_moves.tf"
                            else:
                                samples_dir = Path(__file__).parent.parent.parent.resolve() / "dev_support" / "samples"
                                samples_dir.mkdir(parents=True, exist_ok=True)
                                moves_file = samples_dir / "protection_moves.tf"
                            
                            moved_blocks = generate_repair_moved_blocks(moves_data, module_prefix)
                            
                            if moved_blocks:
                                # Ensure parent directory exists
                                moves_file.parent.mkdir(parents=True, exist_ok=True)
                                moves_file.write_text(moved_blocks)
                                append_output(f"   ✓ Generated {len(moves_data)} moved blocks", "#10B981")
                                append_output(f"   Written to {moves_file}")
                            else:
                                append_output("   No moved blocks needed", "#6B7280")
                            
                            await asyncio.sleep(0.2)
                            
                            # Step 5: Mark as applied to YAML
                            append_output("\n✅ Marking intents as applied...")
                            protection_intent_manager.mark_applied_to_yaml(set(pending.keys()))
                            protection_intent_manager.save()
                            append_output(f"   Updated {len(pending)} intent records")
                            
                            # Final summary
                            append_output(f"\n{'='*50}", "#6B7280")
                            append_output("✅ Done!", "#10B981")
                            append_output(f"   - Updated YAML with protection flags", "#10B981")
                            if moved_blocks:
                                append_output(f"   - Generated protection_moves.tf", "#10B981")
                            append_output(f"   - Next: Run terraform init/plan/apply", "#60A5FA")
                            
                            # Show completion message - don't auto-close so user can copy output
                            append_output("\n💡 Click 'Close & Continue' to proceed to Terraform commands.", "#60A5FA")
                            cancel_btn.set_visibility(False)
                            close_btn.set_visibility(True)
                            return
                            
                        except Exception as e:
                            append_output(f"\n❌ Error: {e}", "#EF4444")
                        finally:
                            cancel_btn.set_visibility(False)
                            close_btn.set_visibility(True)
                    
                    # Launch the async work
                    asyncio.create_task(do_generate_work())
                
                # Button label depends on what's pending
                if has_pending:
                    btn_label = f"Generate Protection Changes ({len(_pending_yaml)})"
                elif _pending_tf_count > 0:
                    btn_label = f"Re-analyze ({_pending_tf_count} pending TF)"
                else:
                    btn_label = "Generate Protection Changes"
                
                generate_btn = ui.button(
                    btn_label,
                    icon="auto_fix_high",
                    on_click=start_generate_protection_changes,
                ).props("color=green")
                generate_btn.set_enabled(can_generate)
                
                # Terraform Commands Section - always visible
                if True:
                    with ui.expansion("Terraform Commands", icon="terminal").classes("w-full mt-3").style("max-width: 100%; overflow: hidden;"):
                        with ui.column().classes("gap-3 w-full"):
                            # Get terraform directory
                            tf_dir = state.deploy.terraform_dir or "deployments/migration"
                            tf_path_for_cmd = Path(tf_dir)
                            if not tf_path_for_cmd.is_absolute():
                                project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                                tf_path_for_cmd = project_root / tf_dir
                            tf_path_for_cmd = tf_path_for_cmd.resolve()
                            
                            # Build -target flags from pending protection intents
                            # This scopes plan/apply to ONLY the resources with pending protection moves,
                            # avoiding surfacing unrelated drift in the full terraform configuration.
                            # Uses needs_tf_move to exclude sync_from_tf_state entries and intents
                            # where TF state already matched at decision time.
                            # IMPORTANT: Target BOTH source (old) and destination (new) addresses
                            # so Terraform can process moved blocks correctly.
                            _target_addresses = []
                            for _ikey, _intent in protection_intent_manager._intent.items():
                                if _intent.needs_tf_move:
                                    if ":" in _ikey:
                                        # Prefixed key: "TYPE:resource_key"
                                        _rtype, _rkey = _ikey.split(":", 1)
                                    elif _intent.resource_type:
                                        # Unprefixed key with resource_type field
                                        _rtype = _intent.resource_type
                                        _rkey = _ikey
                                    else:
                                        # Unprefixed key without resource_type (legacy project-level intent)
                                        # Target PRJ + REP + PREP for the project key (both old and new)
                                        for _legacy_type in ("PRJ", "REP", "PREP"):
                                            try:
                                                _target_addresses.append(get_resource_address(_legacy_type, _ikey, protected=_intent.protected))
                                                _target_addresses.append(get_resource_address(_legacy_type, _ikey, protected=not _intent.protected))
                                            except (ValueError, KeyError):
                                                pass
                                        continue
                                    try:
                                        # Target BOTH new (destination) and old (source) addresses
                                        _target_addresses.append(get_resource_address(_rtype, _rkey, protected=_intent.protected))
                                        _target_addresses.append(get_resource_address(_rtype, _rkey, protected=not _intent.protected))
                                    except (ValueError, KeyError):
                                        pass  # Skip unknown resource types
                            
                            # Also include targets from protection_moves.tf
                            # (catches YAML-vs-state mismatches not in the intent manager)
                            _moves_tf = tf_path_for_cmd / "protection_moves.tf"
                            if _moves_tf.exists():
                                import re as _re_moves
                                _moves_content = _moves_tf.read_text()
                                # HCL moved blocks use bare references (not quoted):
                                #   from = module.dbt_cloud.module.projects_v2[0].dbtcloud_environment.environments["key"]
                                for _match in _re_moves.finditer(r'(?:from|to)\s*=\s*(module\.\S+)', _moves_content):
                                    _addr_from_tf = _match.group(1)
                                    if _addr_from_tf not in _target_addresses:
                                        _target_addresses.append(_addr_from_tf)
                            
                            _target_flags: list[str] = []
                            for _addr in _target_addresses:
                                _target_flags.extend(["-target", _addr])
                            
                            # Info about what will happen
                            if _target_addresses:
                                ui.label(f"Scoped to {len(_target_addresses)} protection target(s) in: {tf_path_for_cmd}").classes("text-xs text-slate-500")
                                with ui.element("details").classes("text-xs text-slate-400 mt-1"):
                                    ui.element("summary").classes("cursor-pointer").text = "Show targeted resources"
                                    for _addr in _target_addresses:
                                        ui.label(f"  → {_addr}").classes("text-xs text-slate-400 font-mono ml-2")
                            else:
                                ui.label(f"Run terraform commands from: {tf_path_for_cmd}").classes("text-xs text-slate-500")
                            
                            # Terminal output area
                            tf_cmd_output = ui.element("div").classes("w-full")
                            tf_outputs_local = {"init": "", "plan": "", "apply": ""}
                            
                            async def run_tf_init():
                                """Run terraform init."""
                                import asyncio
                                import subprocess
                                with tf_cmd_output:
                                    tf_cmd_output.clear()
                                    ui.label("Running terraform init...").classes("text-xs text-blue-500")
                                
                                env = _get_terraform_env(state)
                                result = await asyncio.to_thread(
                                    subprocess.run,
                                    ["terraform", "init", "-no-color", "-input=false"],
                                    cwd=str(tf_path_for_cmd),
                                    capture_output=True,
                                    text=True,
                                    env=env,
                                )
                                tf_outputs_local["init"] = result.stdout + result.stderr
                                
                                with tf_cmd_output:
                                    tf_cmd_output.clear()
                                    if result.returncode == 0:
                                        ui.label("✅ Init completed").classes("text-xs text-green-600 font-semibold")
                                    else:
                                        ui.label("❌ Init failed").classes("text-xs text-red-600 font-semibold")
                                        ui.label(result.stderr[:200] if result.stderr else "Unknown error").classes("text-xs text-red-500")
                                
                                if result.returncode == 0:
                                    ui.notify("Terraform initialized!", type="positive")
                                else:
                                    ui.notify("Init failed - see output", type="negative")
                        
                        async def run_tf_plan():
                            """Run terraform plan scoped to protection targets."""
                            import asyncio
                            import subprocess
                            with tf_cmd_output:
                                tf_cmd_output.clear()
                                if _target_flags:
                                    ui.label(f"Running terraform plan (targeted: {len(_target_addresses)} resource(s))...").classes("text-xs text-blue-500")
                                else:
                                    ui.label("Running terraform plan...").classes("text-xs text-blue-500")
                            
                            env = _get_terraform_env(state)
                            plan_cmd = ["terraform", "plan", "-no-color", "-input=false"] + _target_flags
                            result = await asyncio.to_thread(
                                subprocess.run,
                                plan_cmd,
                                cwd=str(tf_path_for_cmd),
                                capture_output=True,
                                text=True,
                                env=env,
                            )
                            tf_outputs_local["plan"] = result.stdout + result.stderr
                            
                            with tf_cmd_output:
                                tf_cmd_output.clear()
                                if result.returncode == 0:
                                    ui.label("✅ Plan completed - click View Plan").classes("text-xs text-green-600 font-semibold")
                                else:
                                    ui.label("❌ Plan failed").classes("text-xs text-red-600 font-semibold")
                            
                            if result.returncode == 0:
                                plan_output = tf_outputs_local["plan"]
                                
                                # Check if plan shows no changes needed
                                # Multiple patterns to detect "no changes" state:
                                # 1. Older terraform: "No changes."
                                # 2. Newer terraform: "Your infrastructure matches the configuration"
                                # 3. Also check plan summary format: all zeros for add/change/destroy
                                import re
                                no_changes = (
                                    "No changes." in plan_output 
                                    or "Your infrastructure matches the configuration" in plan_output
                                    or "0 to add, 0 to change, 0 to destroy" in plan_output
                                    # Also detect when the regex pattern shows all zeros
                                    or bool(re.search(r"Plan: 0 to add, 0 to change, 0 to destroy", plan_output))
                                )
                                
                                if no_changes:
                                    ui.notify("No changes needed - infrastructure already matches!", type="positive")
                                    # Mark pending intents as synced since TF state already matches
                                    synced_count = 0
                                    for key, intent in protection_intent_manager._intent.items():
                                        if intent.applied_to_yaml and not intent.applied_to_tf_state:
                                            intent.applied_to_tf_state = True
                                            synced_count += 1
                                    if synced_count > 0:
                                        protection_intent_manager.save()
                                        ui.notify(f"Marked {synced_count} intent(s) as synced - state already matched", type="positive")
                                        # Update the UI status display
                                        with tf_cmd_output:
                                            tf_cmd_output.clear()
                                            ui.label(f"✅ No changes needed - {synced_count} intent(s) synced").classes("text-xs text-green-600 font-semibold")
                                else:
                                    ui.notify("Plan completed!", type="positive")
                                
                                # Auto-open plan viewer
                                from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                                dialog = create_plan_viewer_dialog(plan_output, "Terraform Plan Output")
                                dialog.open()
                            else:
                                ui.notify("Plan failed - see output", type="negative")
                        
                        async def run_tf_apply():
                            """Run terraform apply scoped to protection targets."""
                            import asyncio
                            import subprocess
                            with tf_cmd_output:
                                tf_cmd_output.clear()
                                if _target_flags:
                                    ui.label(f"Running terraform apply (targeted: {len(_target_addresses)} resource(s))...").classes("text-xs text-blue-500")
                                else:
                                    ui.label("Running terraform apply...").classes("text-xs text-blue-500")
                            
                            env = _get_terraform_env(state)
                            apply_cmd = ["terraform", "apply", "-auto-approve", "-no-color", "-input=false"] + _target_flags
                            result = await asyncio.to_thread(
                                subprocess.run,
                                apply_cmd,
                                cwd=str(tf_path_for_cmd),
                                capture_output=True,
                                text=True,
                                env=env,
                            )
                            tf_outputs_local["apply"] = result.stdout + result.stderr
                            
                            with tf_cmd_output:
                                tf_cmd_output.clear()
                                if result.returncode == 0:
                                    ui.label("✅ Apply completed!").classes("text-xs text-green-600 font-semibold")
                                else:
                                    ui.label("❌ Apply failed").classes("text-xs text-red-600 font-semibold")
                            
                            if result.returncode == 0:
                                ui.notify("Terraform apply completed!", type="positive")
                                # Mark pending intents as applied to TF state
                                for key, intent in protection_intent_manager._intent.items():
                                    if intent.applied_to_yaml and not intent.applied_to_tf_state:
                                        intent.applied_to_tf_state = True
                                protection_intent_manager.save()
                                ui.notify("Protection intents marked as synced", type="positive")
                            else:
                                ui.notify("Apply failed - see output", type="negative")
                        
                        def show_plan_output():
                            """Show the plan output in a dialog."""
                            output = tf_outputs_local.get("plan", "")
                            if not output:
                                ui.notify("No plan output available. Run plan first.", type="warning")
                                return
                            from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                            dialog = create_plan_viewer_dialog(output, "Terraform Plan Output")
                            dialog.open()
                        
                        def show_init_output():
                            """Show the init output in a dialog."""
                            output = tf_outputs_local.get("init", "")
                            if not output:
                                ui.notify("No init output available. Run init first.", type="warning")
                                return
                            from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                            dialog = create_plan_viewer_dialog(output, "Terraform Init Output")
                            dialog.open()
                        
                        def show_apply_output():
                            """Show the apply output in a dialog."""
                            output = tf_outputs_local.get("apply", "")
                            if not output:
                                ui.notify("No apply output available. Run apply first.", type="warning")
                                return
                            from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                            dialog = create_plan_viewer_dialog(output, "Terraform Apply Output")
                            dialog.open()
                        
                        def show_generate_output():
                            """Show the generate output in a dialog."""
                            output = tf_outputs_local.get("generate", "")
                            if not output:
                                ui.notify("No generate output available. Run generate first.", type="warning")
                                return
                            from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                            dialog = create_plan_viewer_dialog(output, "Terraform Generate Output")
                            dialog.open()
                        
                        # Generate TF function - regenerates HCL from YAML so resource
                        # declarations move between protected/unprotected for_each maps
                        async def run_tf_generate():
                            """Regenerate Terraform HCL files from the updated YAML.
                            
                            This is the critical step that moves resource declarations
                            between protected_*/unprotected for_each maps so that 
                            `moved` blocks in protection_moves.tf can be processed.
                            """
                            import asyncio
                            from importer.yaml_converter import YamlToTerraformConverter
                            
                            with tf_cmd_output:
                                tf_cmd_output.clear()
                                ui.label("Regenerating Terraform files from YAML...").classes("text-xs text-blue-500")
                            
                            # Find the YAML config file
                            yaml_file = tf_path_for_cmd / "dbt-cloud-config.yml"
                            if not yaml_file.exists():
                                if state.fetch.output_dir:
                                    fetch_yaml = Path(state.fetch.output_dir) / "dbt-cloud-config.yml"
                                    if fetch_yaml.exists():
                                        import shutil
                                        shutil.copy2(fetch_yaml, yaml_file)
                            
                            if not yaml_file.exists():
                                # Try finding any YAML file matching our naming pattern
                                samples_dir = Path(__file__).parent.parent.parent.resolve() / "dev_support" / "samples"
                                yaml_files = list(samples_dir.glob("*__yaml__*.yml")) + list(samples_dir.glob("account_*.yml"))
                                if yaml_files:
                                    yaml_file = sorted(yaml_files, key=lambda f: f.stat().st_mtime, reverse=True)[0]
                            
                            if not yaml_file.exists():
                                with tf_cmd_output:
                                    tf_cmd_output.clear()
                                    ui.label(f"❌ YAML config not found at {yaml_file}").classes("text-xs text-red-600 font-semibold")
                                ui.notify("YAML config file not found", type="negative")
                                return
                            
                            try:
                                converter = YamlToTerraformConverter()
                                await asyncio.to_thread(
                                    converter.convert,
                                    str(yaml_file),
                                    str(tf_path_for_cmd),
                                )
                                
                                gen_msg = f"Terraform files regenerated from YAML\nSource: {yaml_file.name}\nOutput: {tf_path_for_cmd}"
                                tf_outputs_local["generate"] = gen_msg
                                
                                with tf_cmd_output:
                                    tf_cmd_output.clear()
                                    ui.label("✅ Terraform files regenerated from YAML").classes("text-xs text-green-600 font-semibold")
                                    ui.label(f"   Source: {yaml_file.name}").classes("text-xs text-slate-400")
                                    ui.label(f"   Output: {tf_path_for_cmd}").classes("text-xs text-slate-400")
                                
                                ui.notify("Terraform files regenerated! Run Init → Plan next.", type="positive")
                            except Exception as e:
                                gen_err = f"Regeneration failed: {e}"
                                tf_outputs_local["generate"] = gen_err
                                with tf_cmd_output:
                                    tf_cmd_output.clear()
                                    ui.label(f"❌ Regeneration failed: {e}").classes("text-xs text-red-600 font-semibold")
                                ui.notify(f"Failed to regenerate: {e}", type="negative")
                        
                        # Credentials gate: check if API token is available
                        _has_credentials = bool(state.target_credentials.api_token)
                        
                        if not _has_credentials:
                            with ui.row().classes("items-center gap-2 w-full p-2").style(
                                "background-color: #FEF3C7; border: 1px solid #F59E0B; border-radius: 4px;"
                            ):
                                ui.icon("warning", size="sm").style("color: #D97706;")
                                ui.label(
                                    "Credentials needed for Init/Plan/Apply. Load credentials on the Fetch Target page. Generate works without credentials."
                                ).classes("text-xs text-amber-800")
                        
                        # Buttons row - action buttons (disabled if no credentials)
                        with ui.row().classes("gap-2 items-center"):
                            _gen_btn = ui.button("Generate", icon="build", on_click=run_tf_generate).props("color=amber").style("min-width: 100px; color: black !important;").tooltip("Regenerate TF files from YAML so moved blocks work")
                            _init_btn = ui.button("Init", icon="downloading", on_click=run_tf_init).props("outline").style("min-width: 80px;")
                            _plan_btn = ui.button("Plan", icon="visibility", on_click=run_tf_plan).props("outline").style("min-width: 80px;")
                            _apply_btn = ui.button("Apply", icon="play_arrow", on_click=run_tf_apply).props("color=green").style("min-width: 80px;")
                            if not _has_credentials:
                                _init_btn.disable()
                                _plan_btn.disable()
                                _apply_btn.disable()
                        
                        # View output buttons row
                        with ui.row().classes("gap-2 items-center mt-1"):
                            ui.button("View Generate", icon="build_circle", on_click=show_generate_output).props("flat dense").style("min-width: 110px;")
                            ui.button("View Init", icon="article", on_click=show_init_output).props("flat dense").style("min-width: 90px;")
                            ui.button("View Plan", icon="description", on_click=show_plan_output).props("flat dense").style("min-width: 90px;")
                            ui.button("View Apply", icon="fact_check", on_click=show_apply_output).props("flat dense").style("min-width: 90px;")
            
            # Recent Changes Section
            if _history:
                with ui.expansion("Recent Changes", icon="history").classes("w-full mt-3").style("max-width: 100%; overflow: hidden;"):
                    with ui.column().classes("gap-2"):
                        for entry in reversed(_history):  # Most recent first
                            action_emoji = "🛡️" if entry.action == "protect" else "🔓"
                            # Parse and format timestamp
                            try:
                                from datetime import datetime
                                ts = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                                ts_display = ts.strftime("%Y-%m-%d %H:%M")
                            except Exception:
                                ts_display = entry.timestamp[:16] if len(entry.timestamp) > 16 else entry.timestamp
                            
                            with ui.row().classes("items-center gap-2 text-sm"):
                                ui.label(action_emoji)
                                ui.label(ts_display).classes("text-slate-500 font-mono text-xs")
                                ui.label(entry.resource_key).classes("font-medium")
                                ui.label(f"({entry.action})").classes("text-slate-500")
                                ui.label(f"via {entry.source}").classes("text-xs text-slate-400")
                        
                        # Link to Protection Management page
                        ui.separator().classes("my-2")
                        ui.label("View full audit trail in Protection Management →").classes(
                            "text-xs text-blue-600 cursor-pointer hover:underline"
                        ).on("click", lambda: ui.navigate.to("/protection-management"))
    
    # DISABLED: Old protection mismatches panel - replaced by Protection Intent Status panel above
    # The new system uses ProtectionIntentManager to track user intent and generate protection changes
    # This old panel detected drift but didn't integrate with the intent system
    # To re-enable, change `if False and ...` back to `if has_state and ...`
    if False and has_state and protection_mismatches:
        with ui.card().classes("w-full p-4 mt-4").style("border: 2px solid #F59E0B;"):
            # Container for pending status - placed at card level, not inside button row
            fix_status_container = ui.element("div").classes("w-full")
            
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-1 flex-grow"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("warning", size="sm").classes("text-amber-600")
                        ui.label("Protection Mismatches Detected").classes("font-semibold text-amber-600")
                    
                    ui.label(
                        f"{len(protection_mismatches)} resources in {len(unique_projects_with_mismatches)} project(s) have protection status mismatch"
                    ).classes("text-sm text-amber-600")
                    
                    # Show preview of mismatches
                    preview_items = []
                    for m in protection_mismatches[:3]:
                        direction = "protect" if m["yaml_protected"] else "unprotect"
                        preview_items.append(f"{m['type']}:{m['key']} ({direction})")
                    preview_text = ", ".join(preview_items)
                    if len(protection_mismatches) > 3:
                        preview_text += f" (+{len(protection_mismatches) - 3} more)"
                    ui.label(preview_text).classes("text-xs text-slate-500")
                    
                    ui.label(
                        "State protection status differs from YAML config. Generate moved blocks to reconcile."
                    ).classes("text-xs text-slate-500")
                
                with ui.row().classes("gap-2 flex-shrink-0"):
                    def show_protection_details():
                        """Show details of all protection mismatches"""
                        # Use standard dialog with explicit centering via Quasar classes
                        with ui.dialog() as detail_dialog:
                            detail_dialog.props("position=standard")
                            with ui.card().classes("q-pa-md max-h-screen overflow-auto").style("width: 950px; max-width: 90vw; margin: 0 auto;"):
                                ui.label("Protection Mismatches").classes("text-lg font-semibold mb-4")
                                
                                # Group by project
                                by_project: dict[str, list] = {}
                                for m in protection_mismatches:
                                    pkey = m.get("project_name") or m.get("key")
                                    if pkey not in by_project:
                                        by_project[pkey] = []
                                    by_project[pkey].append(m)
                                
                                for project_key, items in sorted(by_project.items()):
                                    direction = "unprotect" if items[0]["state_protected"] else "protect"
                                    with ui.card().classes("w-full p-3 mb-2"):
                                        with ui.row().classes("items-center gap-2 mb-2"):
                                            ui.icon("folder", size="sm").classes("text-blue-500")
                                            ui.label(project_key).classes("font-semibold")
                                            ui.badge(direction, color="amber")
                                        
                                        for m in items:
                                            state_status = "protected" if m["state_protected"] else "unprotected"
                                            yaml_status = "protected" if m["yaml_protected"] else "unprotected"
                                            with ui.row().classes("items-center gap-2 ml-4"):
                                                ui.badge(m["type"], color="grey").props("dense")
                                                ui.label(f"State: {state_status} → YAML: {yaml_status}").classes("text-sm")
                                
                                # AI Debug Summary section
                                ui.separator().classes("my-4")
                                with ui.expansion("AI Debug Summary", icon="smart_toy").classes("w-full"):
                                    # Build AI-friendly summary
                                    ai_summary_lines = [
                                        "# Protection Mismatch Summary",
                                        "",
                                        f"**Total mismatches**: {len(protection_mismatches)} resources in {len(by_project)} project(s)",
                                        "",
                                        "## Mismatches by Project",
                                    ]
                                    
                                    for project_key, items in sorted(by_project.items()):
                                        direction = "unprotect" if items[0]["state_protected"] else "protect"
                                        ai_summary_lines.append(f"\n### Project: `{project_key}` ({direction})")
                                        
                                        for m in items:
                                            state_status = "protected" if m["state_protected"] else "unprotected"
                                            yaml_status = "protected" if m["yaml_protected"] else "unprotected"
                                            # EXTENDED_RESOURCE_TYPE_MAP returns (terraform_resource, unprotected_block, protected_block)
                                            resource_tuple = EXTENDED_RESOURCE_TYPE_MAP.get(m["type"], ("unknown", "unknown", "unknown"))
                                            tf_resource, unprotected_block, protected_block = resource_tuple
                                            
                                            ai_summary_lines.append(f"- **{m['type']}** (`{m['key']}`): {state_status} → {yaml_status}")
                                            ai_summary_lines.append(f"  - Terraform resource: `{tf_resource}`")
                                            if direction == "unprotect":
                                                ai_summary_lines.append(f"  - Move from: `{protected_block}` → `{unprotected_block}`")
                                            else:
                                                ai_summary_lines.append(f"  - Move from: `{unprotected_block}` → `{protected_block}`")
                                    
                                    ai_summary_lines.extend([
                                        "",
                                        "## Required Actions",
                                        "Generate `moved` blocks to reconcile Terraform state with YAML configuration.",
                                        "",
                                        "## Protection Relationships",
                                        "- **PRJ** (Project): Independent - can be protected/unprotected on its own",
                                        "- **REP** (Repository) ↔ **PREP** (Project-Repository): Linked - must move together",
                                    ])
                                    
                                    ai_summary_text = "\n".join(ai_summary_lines)
                                    
                                    with ui.row().classes("w-full justify-end mb-2"):
                                        ui.button(
                                            "Copy to Clipboard",
                                            icon="content_copy",
                                            on_click=lambda: (
                                                ui.run_javascript(f'navigator.clipboard.writeText({repr(ai_summary_text)})'),
                                                ui.notify("Copied to clipboard!", type="positive"),
                                            ),
                                        ).props("flat dense")
                                    
                                    ui.markdown(ai_summary_text).classes("text-sm")
                                
                                ui.button("Close", on_click=detail_dialog.close).props("flat").classes("mt-4")
                        detail_dialog.open()
                    
                    ui.button(
                        "View Details",
                        icon="visibility",
                        on_click=show_protection_details,
                    ).props("outline").classes("text-amber-600")
                    
                    async def sync_protection_from_tf_state():
                        """Reset protected_resources to match actual TF state.
                        
                        This resolves circular mismatch issues by syncing the UI intent
                        with what's actually protected in Terraform state.
                        """
                        ui.notify("Syncing protection state from Terraform...", type="info")
                        
                        try:
                            # Resolve terraform directory (same logic as other TF functions)
                            tf_dir = state.deploy.terraform_dir or "deployments/migration"
                            sync_tf_path = Path(tf_dir)
                            
                            if not sync_tf_path.is_absolute():
                                project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                                sync_tf_path = project_root / tf_dir
                            
                            if not sync_tf_path.exists():
                                ui.notify(f"Terraform directory not found: {sync_tf_path}", type="negative")
                                return
                            
                            # Read current TF state
                            new_state_result = await read_terraform_state(sync_tf_path)
                            if not new_state_result.success:
                                ui.notify(f"Failed to read TF state: {new_state_result.error}", type="negative")
                                return
                            
                            if not new_state_result.resources:
                                ui.notify("No resources found in TF state", type="warning")
                                return
                            
                            # Build new protected_resources set from TF state
                            new_protected: set[str] = set()
                            protected_addresses: list[str] = []  # For debug
                            for res in new_state_result.resources:
                                if ".protected_" in res.address:
                                    protected_addresses.append(res.address)
                                    # Extract key from address
                                    if '["' in res.address and '"]' in res.address:
                                        key_start = res.address.rfind('["') + 2
                                        key_end = res.address.rfind('"]')
                                        if key_start > 1 and key_end > key_start:
                                            resource_key = res.address[key_start:key_end]
                                            new_protected.add(resource_key)
                            
                            # Debug: Show what was found
                            ui.notify(f"Found {len(protected_addresses)} protected resources in TF state", type="info")
                            
                            old_count = len(state.map.protected_resources)
                            old_keys = set(state.map.protected_resources) if state.map.protected_resources else set()
                            state.map.protected_resources = new_protected
                            
                            # Clear any pending protection fixes
                            state.map.protection_fix_pending = False
                            state.map.protection_fix_file_path = ""
                            state.map.protection_fix_action = ""
                            state.map.protection_fix_previous_content = ""
                            
                            save_state()
                            
                            # Show detailed sync results
                            added = new_protected - old_keys
                            removed = old_keys - new_protected
                            ui.notify(
                                f"Synced! {len(new_protected)} protected. Added: {list(added)[:3]}, Removed: {list(removed)[:3]}",
                                type="positive",
                                timeout=10000,
                            )
                            
                            # Reload to refresh the mismatch detection
                            await asyncio.sleep(0.5)
                            ui.navigate.reload()
                            
                        except Exception as e:
                            ui.notify(f"Sync failed: {e}", type="negative")
                    
                    ui.button(
                        "Sync from TF State",
                        icon="sync",
                        on_click=sync_protection_from_tf_state,
                    ).props("outline color=blue").tooltip("Reset protection intent to match actual Terraform state")
                    
                    # Use persistent state for fix tracking (survives page re-renders)
                    # state.map.protection_fix_pending, protection_fix_file_path, protection_fix_previous_content
                    
                    def undo_all_protection_fixes(protect_btn, unprotect_btn, undo_btn, status_container):
                        """Restore the previous protection_moves.tf content."""
                        if not state.map.protection_fix_pending:
                            ui.notify("No pending fix to undo", type="warning")
                            return
                        
                        try:
                            file_path = Path(state.map.protection_fix_file_path)
                            previous = state.map.protection_fix_previous_content
                            
                            if previous:
                                file_path.write_text(previous)
                                ui.notify("Restored previous protection_moves.tf", type="positive")
                            else:
                                # No previous content - clear the file
                                file_path.write_text("# Protection moves cleared\n")
                                ui.notify("Cleared protection_moves.tf", type="positive")
                            
                            # Reset persistent state
                            state.map.protection_fix_pending = False
                            state.map.protection_fix_file_path = ""
                            state.map.protection_fix_previous_content = ""
                            state.map.protection_fix_action = ""
                            
                            # Restore protection sets from backup
                            if state.map.protection_fix_backup_protected:
                                state.map.protected_resources = set(state.map.protection_fix_backup_protected)
                            if state.map.protection_fix_backup_unprotected:
                                state.map.unprotected_keys = set(state.map.protection_fix_backup_unprotected)
                            state.map.protection_fix_backup_protected = set()
                            state.map.protection_fix_backup_unprotected = set()
                            
                            save_state()
                            
                            # Reset button states - enable both, reset colors and text
                            protect_btn.props(remove="disabled")
                            protect_btn.props("color=positive")
                            protect_btn.set_text(f"Protect All ({len(protection_mismatches)})")
                            protect_btn.set_icon("shield")
                            
                            unprotect_btn.props(remove="disabled")
                            unprotect_btn.props("color=warning")
                            unprotect_btn.set_text(f"Unprotect All ({len(protection_mismatches)})")
                            unprotect_btn.set_icon("shield_outlined")
                            
                            undo_btn.set_visibility(False)
                            
                            # Clear status container
                            status_container.clear()
                            
                        except Exception as e:
                            ui.notify(f"Error undoing fix: {e}", type="negative")
                    
                    def apply_protection_fix(action: str, protect_btn, unprotect_btn, undo_btn, status_container):
                        """Generate moved blocks for protection changes.
                        
                        Args:
                            action: Either 'protect' or 'unprotect'
                        """
                        from datetime import datetime
                        
                        # Resolve terraform directory
                        tf_dir = state.deploy.terraform_dir or "deployments/migration"
                        tf_path = Path(tf_dir)
                        if not tf_path.is_absolute():
                            project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                            tf_path = project_root / tf_dir
                        
                        if not tf_path.exists():
                            ui.notify(f"Terraform directory not found: {tf_path}", type="negative")
                            return
                        
                        moves_file = tf_path / "protection_moves.tf"
                        module_prefix = "module.dbt_cloud.module.projects_v2[0]"
                        
                        # Save previous content for undo in persistent state
                        previous_content = ""
                        if moves_file.exists():
                            previous_content = moves_file.read_text()
                        state.map.protection_fix_previous_content = previous_content
                        
                        # Filter mismatches based on action
                        # protect: resources that need moved blocks TO protected (state=unprotected)
                        # unprotect: resources that need moved blocks FROM protected (state=protected)
                        if action == "protect":
                            # For "protect": move unprotected → protected, or keep already-protected
                            # Only need moved blocks for resources currently NOT protected in state
                            target_mismatches = [m for m in protection_mismatches if not m["state_protected"]]
                            # Also handle resources that ARE protected in state but YAML says not protected
                            # These just need YAML updated, no moved blocks
                            yaml_only_updates = [m for m in protection_mismatches if m["state_protected"] and not m["yaml_protected"]]
                        else:  # unprotect
                            # For "unprotect": move protected → unprotected, or keep already-unprotected
                            # Only need moved blocks for resources currently protected in state
                            target_mismatches = [m for m in protection_mismatches if m["state_protected"]]
                            # Also handle resources that are NOT protected in state but YAML says protected
                            # These just need YAML updated, no moved blocks
                            yaml_only_updates = [m for m in protection_mismatches if not m["state_protected"] and m["yaml_protected"]]
                        
                        # Group mismatches by project
                        by_project: dict[str, list] = {}
                        for m in target_mismatches:
                            pkey = m.get("project_name") or m.get("key")
                            if pkey not in by_project:
                                by_project[pkey] = []
                            by_project[pkey].append(m)
                        
                        # Generate moved blocks
                        generated_moves: set[tuple[str, str]] = set()
                        blocks = []
                        block_count = 0
                        
                        for project_key, items in sorted(by_project.items()):
                            blocks.append(f"# {action.upper()} moves for {project_key}")
                            for m in items:
                                rtype = m["type"]
                                rkey = m["key"]
                                
                                if rtype in EXTENDED_RESOURCE_TYPE_MAP and (rtype, rkey) not in generated_moves:
                                    tf_type, unprotected, protected = EXTENDED_RESOURCE_TYPE_MAP[rtype]
                                    
                                    if action == "protect":
                                        from_block = unprotected
                                        to_block = protected
                                    else:
                                        from_block = protected
                                        to_block = unprotected
                                    
                                    blocks.append(f'''moved {{
  from = {module_prefix}.{tf_type}.{from_block}["{rkey}"]
  to   = {module_prefix}.{tf_type}.{to_block}["{rkey}"]
}}''')
                                    block_count += 1
                                    generated_moves.add((rtype, rkey))
                                    
                                    # REP and PREP are linked
                                    if rtype == "REP" and ("PREP", rkey) not in generated_moves:
                                        prep_tf_type, prep_unprotected, prep_protected = EXTENDED_RESOURCE_TYPE_MAP["PREP"]
                                        if action == "protect":
                                            prep_from, prep_to = prep_unprotected, prep_protected
                                        else:
                                            prep_from, prep_to = prep_protected, prep_unprotected
                                        blocks.append(f'''moved {{
  from = {module_prefix}.{prep_tf_type}.{prep_from}["{rkey}"]
  to   = {module_prefix}.{prep_tf_type}.{prep_to}["{rkey}"]
}}''')
                                        block_count += 1
                                        generated_moves.add(("PREP", rkey))
                            blocks.append("")
                        
                        action_label = "PROTECT" if action == "protect" else "UNPROTECT"
                        content = f'''# Generated moved blocks to {action_label} resources
# Action: {action_label}
# Generated: {datetime.now().isoformat()}
# Projects: {', '.join(sorted(by_project.keys())) if by_project else 'None (YAML-only updates)'}

''' + "\n".join(blocks)
                        
                        try:
                            moves_file.write_text(content)
                            
                            # Update persistent state
                            state.map.protection_fix_pending = True
                            state.map.protection_fix_file_path = str(moves_file)
                            state.map.protection_fix_action = action  # Track which action was taken
                            
                            # Backup current protection state for undo
                            state.map.protection_fix_backup_protected = set(state.map.protected_resources)
                            state.map.protection_fix_backup_unprotected = set(state.map.unprotected_keys)
                            
                            # Update YAML protection sets based on action
                            for m in protection_mismatches:
                                rkey = m["key"]
                                if action == "protect":
                                    # Add ALL mismatched resources to protected set
                                    state.map.protected_resources.add(rkey)
                                    state.map.unprotected_keys.discard(rkey)
                                else:  # unprotect
                                    # Remove ALL mismatched resources from protected set
                                    state.map.protected_resources.discard(rkey)
                                    state.map.unprotected_keys.add(rkey)
                            
                            save_state()
                            
                            # Update buttons to show success
                            protect_btn.props("disabled")
                            unprotect_btn.props("disabled")
                            if action == "protect":
                                protect_btn.props("color=positive")
                                protect_btn.set_text("Protection Queued")
                                protect_btn.set_icon("shield")
                            else:
                                unprotect_btn.props("color=positive")
                                unprotect_btn.set_text("Unprotection Queued")
                                unprotect_btn.set_icon("shield_outlined")
                            
                            # Show undo button
                            undo_btn.set_visibility(True)
                            
                            # Show pending status
                            with status_container:
                                status_container.clear()
                                color = "#ECFDF5" if action == "protect" else "#FEF3C7"
                                border_color = "#10B981" if action == "protect" else "#F59E0B"
                                text_color = "green" if action == "protect" else "amber"
                                icon_name = "shield" if action == "protect" else "shield_outlined"
                                
                                with ui.card().classes("w-full p-3 mt-3").style(f"background: {color}; border: 1px solid {border_color};"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon(icon_name, size="sm").classes(f"text-{text_color}-600")
                                        ui.label(f"PENDING {action_label}").classes(f"font-bold text-{text_color}-700")
                                    if block_count > 0:
                                        ui.label(f"Wrote {block_count} moved blocks to: {moves_file.name}").classes(f"text-sm text-{text_color}-700 mt-1")
                                    if yaml_only_updates:
                                        ui.label(f"Plus {len(yaml_only_updates)} YAML-only updates (no state change needed)").classes(f"text-sm text-{text_color}-700")
                                    ui.label("⚠️ Skip Generate! Just run Init → Plan → Apply").classes(f"text-xs text-{text_color}-600 font-bold")
                            
                            ui.notify(f"SUCCESS: {action_label} queued for {len(protection_mismatches)} resource(s)", type="positive")
                        except Exception as e:
                            ui.notify(f"Error writing file: {e}", type="negative")
                    
                    def show_protect_confirmation():
                        """Show confirmation dialog before protecting resources."""
                        # Categorize what will happen
                        need_moved = [m for m in protection_mismatches if not m["state_protected"]]
                        need_yaml_only = [m for m in protection_mismatches if m["state_protected"] and not m["yaml_protected"]]
                        
                        with ui.dialog() as confirm_dialog, ui.card().style("width: 600px; max-width: 90vw;"):
                            ui.label("Confirm: PROTECT Resources").classes("text-xl font-bold text-green-700")
                            ui.separator()
                            
                            ui.markdown(f"""
This will **PROTECT** all {len(protection_mismatches)} mismatched resource(s):

- Resources will be in the **protected_*** Terraform collections
- YAML will have **`protected: true`** for these resources
- Protected resources cannot be destroyed without explicit unprotection
""").classes("text-sm")
                            
                            if need_moved:
                                ui.label(f"State Changes ({len(need_moved)} resources):").classes("font-semibold mt-3")
                                with ui.scroll_area().classes("max-h-32 w-full border rounded p-2"):
                                    for m in need_moved:
                                        tf_type, unprotected, protected = EXTENDED_RESOURCE_TYPE_MAP.get(m["type"], ("?", "?", "?"))
                                        ui.label(f"• {m['type']}:{m['key']} → {unprotected} → {protected}").classes("text-xs font-mono")
                            
                            if need_yaml_only:
                                ui.label(f"YAML-Only Updates ({len(need_yaml_only)} resources):").classes("font-semibold mt-3")
                                with ui.scroll_area().classes("max-h-32 w-full border rounded p-2"):
                                    for m in need_yaml_only:
                                        ui.label(f"• {m['type']}:{m['key']} (already protected in state, add to YAML)").classes("text-xs font-mono")
                            
                            ui.separator().classes("my-3")
                            
                            with ui.row().classes("w-full justify-end gap-2"):
                                ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                                ui.button(
                                    "Yes, Protect All",
                                    icon="shield",
                                    on_click=lambda: (
                                        confirm_dialog.close(),
                                        apply_protection_fix("protect", protect_btn, unprotect_btn, undo_btn, fix_status_container),
                                    ),
                                ).props("color=positive")
                        
                        confirm_dialog.open()
                    
                    def show_unprotect_confirmation():
                        """Show confirmation dialog before unprotecting resources."""
                        need_moved = [m for m in protection_mismatches if m["state_protected"]]
                        need_yaml_only = [m for m in protection_mismatches if not m["state_protected"] and m["yaml_protected"]]
                        
                        with ui.dialog() as confirm_dialog, ui.card().style("width: 600px; max-width: 90vw;"):
                            ui.label("Confirm: UNPROTECT Resources").classes("text-xl font-bold text-amber-700")
                            ui.separator()
                            
                            ui.markdown(f"""
This will **UNPROTECT** all {len(protection_mismatches)} mismatched resource(s):

- Resources will be in the **regular** Terraform collections (not protected_*)
- YAML will **NOT** have `protected: true` for these resources  
- ⚠️ **Warning**: Unprotected resources CAN be destroyed by Terraform
""").classes("text-sm")
                            
                            if need_moved:
                                ui.label(f"State Changes ({len(need_moved)} resources):").classes("font-semibold mt-3")
                                with ui.scroll_area().classes("max-h-32 w-full border rounded p-2"):
                                    for m in need_moved:
                                        tf_type, unprotected, protected = EXTENDED_RESOURCE_TYPE_MAP.get(m["type"], ("?", "?", "?"))
                                        ui.label(f"• {m['type']}:{m['key']} → {protected} → {unprotected}").classes("text-xs font-mono")
                            
                            if need_yaml_only:
                                ui.label(f"YAML-Only Updates ({len(need_yaml_only)} resources):").classes("font-semibold mt-3")
                                with ui.scroll_area().classes("max-h-32 w-full border rounded p-2"):
                                    for m in need_yaml_only:
                                        ui.label(f"• {m['type']}:{m['key']} (already unprotected in state, remove from YAML)").classes("text-xs font-mono")
                            
                            ui.separator().classes("my-3")
                            
                            with ui.row().classes("w-full justify-end gap-2"):
                                ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                                ui.button(
                                    "Yes, Unprotect All",
                                    icon="shield_outlined",
                                    on_click=lambda: (
                                        confirm_dialog.close(),
                                        apply_protection_fix("unprotect", protect_btn, unprotect_btn, undo_btn, fix_status_container),
                                    ),
                                ).props("color=warning")
                        
                        confirm_dialog.open()
                    
                    # Check if there's already a pending fix from persistent state
                    has_pending_fix = state.map.protection_fix_pending
                    pending_action = getattr(state.map, 'protection_fix_action', None)
                    
                    # Count resources by current state for button labels
                    can_protect = sum(1 for m in protection_mismatches if not m["state_protected"] or not m["yaml_protected"])
                    can_unprotect = sum(1 for m in protection_mismatches if m["state_protected"] or m["yaml_protected"])
                    
                    if has_pending_fix:
                        # Show which action was taken
                        if pending_action == "protect":
                            protect_btn = ui.button("Protection Queued", icon="shield").props("color=positive disabled")
                            unprotect_btn = ui.button(f"Unprotect All", icon="lock_open").props("color=grey disabled")
                        else:
                            protect_btn = ui.button(f"Protect All", icon="shield").props("color=grey disabled")
                            unprotect_btn = ui.button("Unprotection Queued", icon="lock_open").props("color=positive disabled")
                    else:
                        # Show both options
                        protect_btn = ui.button(
                            f"Protect All ({len(protection_mismatches)})",
                            icon="shield",
                            on_click=show_protect_confirmation,
                        ).props("color=positive")
                        
                        unprotect_btn = ui.button(
                            f"Unprotect All ({len(protection_mismatches)})",
                            icon="lock_open",
                            on_click=show_unprotect_confirmation,
                        ).props("color=warning")
                    
                    # Undo button - shown if there's a pending fix
                    undo_btn = ui.button(
                        "Undo",
                        icon="undo",
                        on_click=lambda: undo_all_protection_fixes(protect_btn, unprotect_btn, undo_btn, fix_status_container),
                    ).props("color=grey outline")
                    undo_btn.set_visibility(has_pending_fix)
                    
                    # Show pending status if there's already a fix queued
                    if has_pending_fix and state.map.protection_fix_file_path:
                        with fix_status_container:
                            action_label = "PROTECT" if pending_action == "protect" else "UNPROTECT"
                            color = "#ECFDF5" if pending_action == "protect" else "#FEF3C7"
                            border_color = "#10B981" if pending_action == "protect" else "#F59E0B"
                            text_color = "green" if pending_action == "protect" else "amber"
                            icon_name = "shield" if pending_action == "protect" else "lock_open"
                            
                            with ui.card().classes("w-full p-3 mt-3").style(f"background: {color}; border: 1px solid {border_color};"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon(icon_name, size="sm").classes(f"text-{text_color}-600")
                                    ui.label(f"PENDING {action_label}").classes(f"font-bold text-{text_color}-700")
                                moves_file_name = Path(state.map.protection_fix_file_path).name
                                ui.label(f"Moved blocks written to: {moves_file_name}").classes(f"text-sm text-{text_color}-700 mt-1")
                                ui.label("Use the Terraform buttons below to apply the moves").classes(f"text-xs text-{text_color}-600")
            
            # Terraform operations section - only for protection moves
            ui.separator().classes("my-3")
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label("Apply Protection Changes").classes("text-sm font-semibold text-slate-600")
                # Credential status indicator
                if state.target_credentials.api_token and state.target_credentials.account_id:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("check_circle", size="xs").classes("text-green-500")
                        ui.label("Credentials loaded").classes("text-xs text-green-600")
                else:
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("warning", size="xs").classes("text-amber-500")
                        ui.label("Load .env from Fetch Target first").classes("text-xs text-amber-600")
            
            # Get terraform directory
            tf_dir = state.deploy.terraform_dir or "deployments/migration"
            tf_path = Path(tf_dir)
            if not tf_path.is_absolute():
                project_root = Path(state.fetch.output_dir).parent.parent if state.fetch.output_dir else Path.cwd()
                tf_path = project_root / tf_dir
            # Always resolve to absolute path
            tf_path = tf_path.resolve()
            
            # Create a simple terminal output area for this section
            match_terminal_output = ui.element("div").classes("w-full")
            
            # Store output logs for each step
            tf_outputs = {"generate": "", "init": "", "validate": "", "plan": "", "apply": ""}
            # Track running state for plan
            plan_running = {"active": False}
            
            def show_output_dialog(step_name: str, title: str):
                """Show a dialog with the stored output for a step."""
                output = tf_outputs.get(step_name, "")
                
                # Handle plan specially - might be running with partial output
                if step_name == "plan" and not output and plan_running["active"]:
                    ui.notify("Plan is still running in background. Output will be available when complete.", type="info")
                    return
                
                if not output:
                    ui.notify(f"No {step_name} output available. Run {step_name} first.", type="warning")
                    return
                
                # If plan is running, show partial output with a note
                display_title = title
                if step_name == "plan" and plan_running["active"]:
                    display_title = f"{title} (In Progress - Partial Output)"
                    ui.notify("Showing partial output - plan still running", type="info")
                
                from importer.web.utils.yaml_viewer import create_plan_viewer_dialog
                dialog = create_plan_viewer_dialog(output, display_title)
                dialog.open()
            
            with ui.row().classes("w-full items-center gap-2"):
                async def run_generate_moved_blocks():
                    """Generate or regenerate the moved blocks file based on current mismatches.
                    
                    This function:
                    1. Updates the YAML file with protection flags based on mismatches
                    2. Regenerates Terraform files from the updated YAML
                    3. Generates moved blocks to migrate Terraform state
                    """
                    import asyncio
                    import shutil
                    from datetime import datetime
                    from importer.yaml_converter import YamlToTerraformConverter
                    from importer.web.utils.adoption_yaml_updater import apply_protection_from_set, apply_unprotection_from_set
                    
                    moves_file = tf_path / "protection_moves.tf"
                    module_prefix = "module.dbt_cloud.module.projects_v2[0]"
                    
                    with match_terminal_output:
                        match_terminal_output.clear()
                        ui.label("Updating YAML with protection flags...").classes("text-xs text-slate-500")
                    
                    # Step 0: Find the YAML file
                    yaml_file = tf_path / "dbt-cloud-config.yml"
                    if not yaml_file.exists():
                        # Fallback to fetch output dir
                        if state.fetch.output_dir:
                            fetch_yaml = Path(state.fetch.output_dir) / "dbt-cloud-config.yml"
                            if fetch_yaml.exists():
                                # Copy to deployment dir
                                shutil.copy2(fetch_yaml, yaml_file)
                    
                    if not yaml_file.exists():
                        ui.notify(f"YAML config file not found at {yaml_file}", type="negative")
                        return
                    
                    # Step 1: Apply protection changes to the YAML file
                    # Build TYPE-SPECIFIC sets of keys to protect/unprotect based on mismatches
                    # We need to be precise about which resource types to update
                    project_keys_to_protect: set[str] = set()
                    project_keys_to_unprotect: set[str] = set()
                    repo_keys_to_protect: set[str] = set()
                    repo_keys_to_unprotect: set[str] = set()
                    
                    for m in protection_mismatches:
                        rtype = m["type"]
                        rkey = m["key"]
                        yaml_protected = m.get("yaml_protected", False)
                        state_protected = m["state_protected"]
                        
                        if yaml_protected and not state_protected:
                            # User wants protected, state is not - need to add protection
                            if rtype == "PRJ":
                                project_keys_to_protect.add(rkey)
                            elif rtype in ("REP", "PREP"):
                                repo_keys_to_protect.add(rkey)
                        elif not yaml_protected and state_protected:
                            # User doesn't want protected, state is - need to remove protection
                            if rtype == "PRJ":
                                project_keys_to_unprotect.add(rkey)
                            elif rtype in ("REP", "PREP"):
                                repo_keys_to_unprotect.add(rkey)
                    
                    # Combine all keys for the YAML update
                    # Since protection is at the PROJECT level, both PRJ and REP mismatches 
                    # need to update the parent project's protection flag
                    keys_to_protect = project_keys_to_protect | repo_keys_to_protect
                    keys_to_unprotect = project_keys_to_unprotect | repo_keys_to_unprotect
                    
                    # NOTE: Protection is at the PROJECT level in the YAML/Terraform architecture.
                    # When protecting a repository, the parent project is automatically protected too.
                    # This cascades to the moved blocks generation which adds project moves for repo mismatches.
                    
                    try:
                        # Apply protection changes to the YAML file
                        if keys_to_protect:
                            await asyncio.to_thread(
                                apply_protection_from_set,
                                str(yaml_file),
                                keys_to_protect,
                            )
                        
                        if keys_to_unprotect:
                            await asyncio.to_thread(
                                apply_unprotection_from_set,
                                str(yaml_file),
                                keys_to_unprotect,
                            )
                        
                        # CRITICAL: Also sync the UI state (state.map.protected_resources) to match
                        # This prevents the mismatch detection from flip-flopping after reload
                        for key in keys_to_protect:
                            state.map.protected_resources.add(key)
                        for key in keys_to_unprotect:
                            state.map.protected_resources.discard(key)
                        save_state()
                        
                        with match_terminal_output:
                            match_terminal_output.clear()
                            ui.label(f"✅ YAML updated: {len(keys_to_protect)} protected, {len(keys_to_unprotect)} unprotected").classes("text-xs text-green-600 font-semibold")
                        
                    except Exception as e:
                        ui.notify(f"Failed to update YAML: {e}", type="warning")
                        # Continue anyway - we'll try the regeneration
                    
                    with match_terminal_output:
                        match_terminal_output.clear()
                        ui.label("Regenerating Terraform files...").classes("text-xs text-slate-500")
                    
                    # Step 2: Regenerate Terraform files from the updated YAML
                    # This ensures the protected resources are declared in protected_* blocks
                    try:
                        converter = YamlToTerraformConverter()
                        await asyncio.to_thread(
                            converter.convert,
                            str(yaml_file),
                            str(tf_path),
                        )
                        
                        with match_terminal_output:
                            match_terminal_output.clear()
                            ui.label("✅ Terraform files regenerated").classes("text-xs text-green-600 font-semibold")
                        
                    except Exception as e:
                        with match_terminal_output:
                            match_terminal_output.clear()
                            ui.label(f"⚠️ Regen warning: {e}").classes("text-xs text-amber-600")
                        # Continue anyway - the moved blocks might still work
                    
                    # Step 2: Generate moved blocks for all mismatches
                    with match_terminal_output:
                        match_terminal_output.clear()
                        ui.label("Generating moved blocks...").classes("text-xs text-slate-500")
                    
                    # Determine direction based on majority of mismatches
                    protect_count = sum(1 for m in protection_mismatches if not m["state_protected"])
                    unprotect_count = sum(1 for m in protection_mismatches if m["state_protected"])
                    
                    # Generate moved blocks for all mismatches
                    # IMPORTANT: When protecting a REP/PREP, we also need to move the parent PROJECT
                    # because protection is at the project level in the YAML structure
                    generated_moves: set[tuple[str, str]] = set()
                    blocks = []
                    block_count = 0
                    
                    # First pass: identify all unique keys that will need protection changes
                    keys_needing_protection = set()
                    keys_needing_unprotection = set()
                    for m in protection_mismatches:
                        rkey = m["key"]
                        if m["state_protected"]:
                            keys_needing_unprotection.add(rkey)
                        else:
                            keys_needing_protection.add(rkey)
                    
                    for m in protection_mismatches:
                        rtype = m["type"]
                        rkey = m["key"]
                        
                        if rtype in EXTENDED_RESOURCE_TYPE_MAP and (rtype, rkey) not in generated_moves:
                            tf_type, unprotected, protected = EXTENDED_RESOURCE_TYPE_MAP[rtype]
                            
                            # Direction based on current state
                            if m["state_protected"]:
                                # Move from protected to unprotected
                                from_block = protected
                                to_block = unprotected
                                direction = "unprotect"
                            else:
                                # Move from unprotected to protected
                                from_block = unprotected
                                to_block = protected
                                direction = "protect"
                            
                            blocks.append(f'''# {direction} {rkey}
moved {{
  from = {module_prefix}.{tf_type}.{from_block}["{rkey}"]
  to   = {module_prefix}.{tf_type}.{to_block}["{rkey}"]
}}''')
                            block_count += 1
                            generated_moves.add((rtype, rkey))
                            
                            # If this is a REP/PREP mismatch, also generate a PRJ moved block
                            # since protecting a repo means the whole project is protected
                            if rtype in ("REP", "PREP") and ("PRJ", rkey) not in generated_moves:
                                prj_tf_type, prj_unprotected, prj_protected = EXTENDED_RESOURCE_TYPE_MAP["PRJ"]
                                blocks.append(f'''# {direction} {rkey} (project - cascaded from repository)
moved {{
  from = {module_prefix}.{prj_tf_type}.{prj_unprotected if direction == "protect" else prj_protected}["{rkey}"]
  to   = {module_prefix}.{prj_tf_type}.{prj_protected if direction == "protect" else prj_unprotected}["{rkey}"]
}}''')
                                block_count += 1
                                generated_moves.add(("PRJ", rkey))
                            
                            # If this is a PRJ mismatch, also generate a REP moved block
                            # since the repository protection follows the project
                            if rtype == "PRJ" and ("REP", rkey) not in generated_moves:
                                rep_tf_type, rep_unprotected, rep_protected = EXTENDED_RESOURCE_TYPE_MAP["REP"]
                                blocks.append(f'''# {direction} {rkey} (repository - cascaded from project)
moved {{
  from = {module_prefix}.{rep_tf_type}.{rep_unprotected if direction == "protect" else rep_protected}["{rkey}"]
  to   = {module_prefix}.{rep_tf_type}.{rep_protected if direction == "protect" else rep_unprotected}["{rkey}"]
}}''')
                                block_count += 1
                                generated_moves.add(("REP", rkey))
                            
                            # If this is a PRJ or REP mismatch, also generate a PREP moved block
                            # since the project_repository link also needs to move
                            if rtype in ("PRJ", "REP") and ("PREP", rkey) not in generated_moves:
                                prep_tf_type, prep_unprotected, prep_protected = EXTENDED_RESOURCE_TYPE_MAP["PREP"]
                                blocks.append(f'''# {direction} {rkey} (project_repository - cascaded)
moved {{
  from = {module_prefix}.{prep_tf_type}.{prep_unprotected if direction == "protect" else prep_protected}["{rkey}"]
  to   = {module_prefix}.{prep_tf_type}.{prep_protected if direction == "protect" else prep_unprotected}["{rkey}"]
}}''')
                                block_count += 1
                                generated_moves.add(("PREP", rkey))
                    
                    content = f'''# Generated moved blocks for protection status changes
# Generated: {datetime.now().isoformat()}
# Mismatches: {len(protection_mismatches)}

''' + "\n\n".join(blocks)
                    
                    try:
                        moves_file.write_text(content)
                        tf_outputs["generate"] = content
                        
                        with match_terminal_output:
                            match_terminal_output.clear()
                            ui.label(f"✅ Regenerated TF + {block_count} moved blocks").classes("text-xs text-green-600 font-semibold")
                        
                        ui.notify(f"Regenerated Terraform and created {block_count} moved blocks", type="positive")
                    except Exception as e:
                        with match_terminal_output:
                            match_terminal_output.clear()
                            ui.label(f"❌ Failed to generate: {e}").classes("text-xs text-red-600 font-semibold")
                        ui.notify(f"Error: {e}", type="negative")
                
                ui.button("Generate", icon="build", on_click=run_generate_moved_blocks).props("color=amber").style("min-width: 100px; color: black !important;").tooltip("⚠️ Regenerates ALL TF files - skip for protection-only changes!")
                
                def check_credentials() -> bool:
                    """Check if credentials are loaded. Returns True if valid."""
                    if not state.target_credentials.api_token:
                        ui.notify("Missing API token - load .env from Fetch Target screen first", type="negative")
                        return False
                    if not state.target_credentials.account_id:
                        ui.notify("Missing Account ID - load .env from Fetch Target screen first", type="negative")
                        return False
                    return True
                
                async def run_match_init():
                    """Run terraform init for protection moves."""
                    import asyncio
                    import subprocess
                    import os
                    
                    if not check_credentials():
                        return
                    
                    with match_terminal_output:
                        match_terminal_output.clear()
                        ui.label("Running terraform init...").classes("text-xs text-slate-500")
                    
                    # Use the same env setup as deploy/destroy pages
                    env = _get_terraform_env(state)
                    
                    result = await asyncio.to_thread(
                        subprocess.run,
                        ["terraform", "init", "-no-color", "-input=false"],
                        cwd=str(tf_path),
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    
                    # Store output for later viewing
                    tf_outputs["init"] = result.stdout + result.stderr
                    
                    with match_terminal_output:
                        match_terminal_output.clear()
                        if result.returncode == 0:
                            ui.label("✅ Init completed").classes("text-xs text-green-600 font-semibold")
                        else:
                            ui.label("❌ Init failed").classes("text-xs text-red-600 font-semibold")
                            ui.label(result.stderr[:200] if result.stderr else "Unknown error").classes("text-xs text-red-500")
                    
                    if result.returncode == 0:
                        ui.notify("Terraform initialized!", type="positive")
                    else:
                        ui.notify("Init failed - see output", type="negative")
                
                ui.button("Init", icon="downloading", on_click=run_match_init).props("outline").style("min-width: 100px;")
                
                async def run_match_validate():
                    """Run terraform validate for protection moves."""
                    import asyncio
                    import subprocess
                    import os
                    
                    if not check_credentials():
                        return
                    
                    with match_terminal_output:
                        match_terminal_output.clear()
                        ui.label("Running terraform validate...").classes("text-xs text-slate-500")
                    
                    # Use the same env setup as deploy/destroy pages
                    env = _get_terraform_env(state)
                    
                    result = await asyncio.to_thread(
                        subprocess.run,
                        ["terraform", "validate", "-no-color"],
                        cwd=str(tf_path),
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    
                    # Store output for later viewing
                    tf_outputs["validate"] = result.stdout + result.stderr
                    
                    with match_terminal_output:
                        match_terminal_output.clear()
                        if result.returncode == 0:
                            ui.label("✅ Validation passed").classes("text-xs text-green-600 font-semibold")
                        else:
                            ui.label("❌ Validation failed").classes("text-xs text-red-600 font-semibold")
                            ui.label(result.stderr[:200] if result.stderr else "Unknown error").classes("text-xs text-red-500")
                    
                    if result.returncode == 0:
                        ui.notify("Validation passed!", type="positive")
                    else:
                        ui.notify("Validation failed - see output", type="warning")
                
                ui.button("Validate", icon="check_circle", on_click=run_match_validate).props("outline").style("min-width: 100px;")
                
                async def run_match_plan():
                    """Run terraform plan with live streaming output."""
                    import asyncio
                    import os
                    import html as html_module
                    
                    if not check_credentials():
                        return
                    
                    # Mark plan as running and clear any previous output
                    plan_running["active"] = True
                    tf_outputs["plan"] = ""
                    
                    # Use the same env setup as deploy/destroy pages
                    env = _get_terraform_env(state)
                    
                    # Create streaming log viewer dialog with timestamps, levels, search
                    from datetime import datetime
                    output_lines = []  # Raw lines for copy
                    formatted_lines = []  # Lines with timestamps for display
                    process_ref = {"process": None, "cancelled": False}
                    search_state = {"term": "", "count": 0}
                    
                    def get_log_level(line: str) -> tuple[str, str]:
                        """Determine log level and color from line content."""
                        line_lower = line.lower()
                        if "error" in line_lower or "failed" in line_lower:
                            return "ERROR", "text-red-400"
                        elif "warning" in line_lower or "warn" in line_lower:
                            return "WARN", "text-amber-400"
                        elif line.startswith("#") or "will be" in line_lower:
                            return "INFO", "text-blue-400"
                        elif line.startswith("+"):
                            return "ADD", "text-green-400"
                        elif line.startswith("-"):
                            return "DEL", "text-red-400"
                        elif line.startswith("~"):
                            return "CHG", "text-amber-400"
                        else:
                            return "INFO", "text-slate-400"
                    
                    def format_log_line(line: str) -> str:
                        """Format a line with timestamp and level."""
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        level, color = get_log_level(line)
                        escaped_line = html_module.escape(line)
                        return f'<span class="text-slate-500">[{timestamp}]</span> <span class="{color}">[{level:5}]</span> {escaped_line}'
                    
                    with ui.dialog() as stream_dialog, ui.card().classes("w-full h-full").style("width: 90vw; max-width: 90vw; height: 80vh; display: flex; flex-direction: column;"):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            with ui.row().classes("items-center gap-3"):
                                stream_spinner = ui.spinner("dots", size="md").classes("text-primary")
                                stream_title = ui.label("Running terraform plan...").classes("text-xl font-bold")
                            ui.button(icon="close", on_click=stream_dialog.close).props("flat round")
                        
                        ui.label(f"Directory: {tf_path}").classes("text-xs text-slate-500 font-mono mb-2")
                        
                        # Search bar
                        with ui.row().classes("w-full items-center gap-2 mb-2"):
                            search_input = ui.input(placeholder="Search in output...").props("outlined dense clearable").classes("flex-1")
                            search_count_label = ui.label("").classes("text-xs text-slate-400 min-w-[80px]")
                        
                        with ui.scroll_area().classes("w-full flex-grow stream-scroll-area"):
                            stream_log = ui.html('<pre class="text-xs font-mono whitespace-pre-wrap p-2 bg-slate-900 text-slate-100 rounded stream-log-content" style="min-height: 200px;">[Starting terraform plan...]\n</pre>')
                        
                        # Search handler
                        async def on_search(e):
                            term = e.args if e.args else ""
                            search_state["term"] = term
                            if not term:
                                search_count_label.set_text("")
                                return
                            
                            # Count matches in raw output
                            full_output = "\n".join(output_lines)
                            count = full_output.lower().count(term.lower())
                            search_state["count"] = count
                            search_count_label.set_text(f"{count} matches" if count else "No matches")
                            
                            # Highlight in viewer
                            if count > 0:
                                escaped_term = term.replace("'", "\\'").replace('"', '\\"')
                                await ui.run_javascript(f'''
                                    const pre = document.querySelector('.stream-log-content');
                                    if (pre) {{
                                        const html = pre.innerHTML;
                                        const regex = new RegExp('({escaped_term})', 'gi');
                                        pre.innerHTML = html.replace(regex, '<mark class="bg-yellow-500 text-black px-0.5">$1</mark>');
                                        const mark = document.querySelector('.stream-log-content mark');
                                        if (mark) mark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                    }}
                                ''')
                        
                        search_input.on("update:model-value", on_search)
                        
                        with ui.row().classes("w-full justify-between mt-2"):
                            def cancel_plan():
                                if process_ref["process"] and process_ref["process"].returncode is None:
                                    process_ref["cancelled"] = True
                                    process_ref["process"].kill()
                                    cancel_line = "⚠️ CANCELLED: Plan was cancelled by user"
                                    output_lines.append(cancel_line)
                                    formatted_lines.append(format_log_line(cancel_line))
                                    ui.notify("Plan cancelled", type="warning")
                            
                            cancel_btn = ui.button("Cancel", icon="cancel", on_click=cancel_plan).props("outline color=negative")
                            
                            with ui.row().classes("gap-2"):
                                def copy_stream_output():
                                    content = "\n".join(output_lines)
                                    ui.run_javascript(f'navigator.clipboard.writeText({repr(content)})')
                                    ui.notify("Copied to clipboard", type="positive")
                                ui.button("Copy", icon="content_copy", on_click=copy_stream_output).props("outline")
                                ui.button("Close", on_click=stream_dialog.close)
                    
                    stream_dialog.props("maximized")
                    stream_dialog.open()
                    
                    with match_terminal_output:
                        match_terminal_output.clear()
                        ui.label("Running terraform plan...").classes("text-xs text-slate-500")
                    
                    # Run terraform plan with streaming output
                    try:
                        process = await asyncio.create_subprocess_exec(
                            "terraform", "plan", "-no-color", "-input=false",
                            cwd=str(tf_path),
                            env=env,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.STDOUT,
                        )
                        process_ref["process"] = process
                        
                        # Stream output line by line
                        while True:
                            try:
                                line = await asyncio.wait_for(process.stdout.readline(), timeout=300)
                            except asyncio.TimeoutError:
                                timeout_line = "⚠️ TIMEOUT: Plan exceeded 5 minute limit"
                                output_lines.append(timeout_line)
                                formatted_lines.append(format_log_line(timeout_line))
                                process.kill()
                                break
                            
                            if not line:
                                break
                            
                            decoded_line = line.decode('utf-8', errors='replace').rstrip()
                            output_lines.append(decoded_line)
                            formatted_lines.append(format_log_line(decoded_line))
                            
                            # Save output incrementally so it's available if dialog is closed early
                            tf_outputs["plan"] = "\n".join(output_lines)
                            
                            # Update the viewer with formatted output (timestamps + levels)
                            formatted_output = "\n".join(formatted_lines)
                            stream_log.content = f'<pre class="text-xs font-mono whitespace-pre-wrap p-2 bg-slate-900 text-slate-100 rounded stream-log-content" style="min-height: 200px;">{formatted_output}</pre>'
                            stream_log.update()
                        
                        await process.wait()
                        returncode = process.returncode
                        
                    except Exception as e:
                        error_line = f"❌ ERROR: {e}"
                        output_lines.append(error_line)
                        formatted_lines.append(format_log_line(error_line))
                        returncode = 1
                    
                    # Hide cancel button when done
                    cancel_btn.set_visibility(False)
                    
                    plan_output = "\n".join(output_lines)
                    tf_outputs["plan"] = plan_output
                    
                    # Update dialog title and hide spinner
                    stream_spinner.set_visibility(False)
                    if process_ref["cancelled"]:
                        stream_title.set_text("⚠️ Plan Cancelled")
                        ui.notify("Plan was cancelled", type="warning")
                    elif returncode == 0:
                        if "0 to add, 0 to change, 0 to destroy" in plan_output:
                            stream_title.set_text("✅ Plan Complete: Only moves, no real changes")
                        else:
                            stream_title.set_text("⚠️ Plan Complete: Has changes - review carefully")
                        ui.notify("Plan completed", type="positive")
                    else:
                        stream_title.set_text("❌ Plan Failed")
                        ui.notify("Plan failed - see output for details", type="warning")
                    
                    # Update status in the match terminal area
                    with match_terminal_output:
                        match_terminal_output.clear()
                        if process_ref["cancelled"]:
                            ui.label("⚠️ Plan cancelled").classes("text-xs text-amber-600 font-semibold")
                        elif returncode == 0:
                            if "0 to add, 0 to change, 0 to destroy" in plan_output:
                                ui.label("✅ Plan: Only moves, no real changes").classes("text-xs text-green-600 font-semibold")
                            else:
                                ui.label("⚠️ Plan has changes - review carefully").classes("text-xs text-amber-600 font-semibold")
                        else:
                            ui.label("❌ Plan failed").classes("text-xs text-red-600 font-semibold")
                    
                    # Mark plan as complete
                    plan_running["active"] = False
                
                ui.button("Plan", icon="preview", on_click=run_match_plan).props("outline color=primary").style("min-width: 100px;")
                
                async def run_match_apply():
                    """Run terraform apply with live streaming output and detailed confirmation."""
                    import asyncio
                    import os
                    import html as html_module
                    from importer.web.utils.yaml_viewer import parse_plan_stats
                    
                    if not check_credentials():
                        return
                    
                    # Parse plan output to get counts for confirmation
                    plan_output = tf_outputs.get("plan", "")
                    stats = parse_plan_stats(plan_output) if plan_output else {"move": 0, "add": 0, "change": 0, "destroy": 0}
                    
                    has_plan = bool(plan_output)
                    has_destroys = stats.get("destroy", 0) > 0
                    
                    # Confirmation dialog with detailed stats
                    with ui.dialog() as confirm_dialog, ui.card().style("width: 550px;"):
                        with ui.row().classes("w-full items-center gap-3 mb-3"):
                            ui.icon("rocket_launch", size="lg").classes("text-primary")
                            ui.label("Confirm Apply").classes("text-xl font-bold")
                        
                        ui.label(
                            "This will apply the changes to Terraform state. "
                            "Review the plan summary below before proceeding."
                        ).classes("text-sm text-slate-600 mb-4")
                        
                        # Plan summary stats bar
                        if has_plan:
                            with ui.row().classes("w-full gap-4 mb-4 p-3 bg-slate-100 dark:bg-slate-800 rounded items-center"):
                                ui.label("Plan Summary:").classes("font-semibold")
                                
                                if stats.get('move', 0) > 0:
                                    with ui.row().classes("items-center gap-1"):
                                        ui.icon("swap_horiz", size="sm").classes("text-blue-600")
                                        ui.label(f"{stats['move']} to move").classes("text-blue-600 font-medium")
                                
                                if stats.get('add', 0) > 0:
                                    with ui.row().classes("items-center gap-1"):
                                        ui.icon("add_circle", size="sm").classes("text-green-600")
                                        ui.label(f"{stats['add']} to add").classes("text-green-600 font-medium")
                                
                                if stats.get('change', 0) > 0:
                                    with ui.row().classes("items-center gap-1"):
                                        ui.icon("change_circle", size="sm").classes("text-amber-600")
                                        ui.label(f"{stats['change']} to change").classes("text-amber-600 font-medium")
                                
                                if stats.get('destroy', 0) > 0:
                                    with ui.row().classes("items-center gap-1"):
                                        ui.icon("remove_circle", size="sm").classes("text-red-600")
                                        ui.label(f"{stats['destroy']} to destroy").classes("text-red-600 font-medium")
                                
                                # Show "no changes" if everything is 0
                                total_changes = sum(stats.values())
                                if total_changes == 0:
                                    ui.label("No changes").classes("text-slate-500 italic")
                        else:
                            with ui.row().classes("w-full mb-4 p-3 bg-amber-100 dark:bg-amber-900 rounded items-center gap-2"):
                                ui.icon("warning", size="sm").classes("text-amber-600")
                                ui.label("No plan output found. Run Plan first to see what will change.").classes("text-amber-700 dark:text-amber-200 text-sm")
                        
                        # Warning for destroys
                        if has_destroys:
                            with ui.row().classes("w-full mb-4 p-3 bg-red-100 dark:bg-red-900 rounded items-center gap-2"):
                                ui.icon("warning", size="sm").classes("text-red-600")
                                ui.label(f"⚠️ This will DESTROY {stats['destroy']} resource(s)! This cannot be undone.").classes("text-red-700 dark:text-red-200 text-sm font-semibold")
                        
                        with ui.row().classes("w-full justify-end gap-2"):
                            ui.button("Cancel", on_click=confirm_dialog.close).props("flat")
                            
                            async def do_apply():
                                confirm_dialog.close()
                                # Use create_task to ensure dialog opens after confirmation closes
                                await asyncio.sleep(0.1)  # Small delay to let confirmation dialog close
                                await run_apply_streaming()
                            
                            apply_btn = ui.button("Apply", icon="rocket_launch", on_click=do_apply)
                            if has_destroys:
                                apply_btn.props("color=negative")
                            else:
                                apply_btn.props("color=positive")
                    
                    confirm_dialog.open()
                
                async def run_apply_streaming():
                    """Run terraform apply with live streaming output."""
                    import asyncio
                    import os
                    import html as html_module
                    from datetime import datetime
                    
                    # Use the same env setup as deploy/destroy pages
                    env = _get_terraform_env(state)
                    
                    # Create streaming log viewer dialog with timestamps, levels, search
                    output_lines = []  # Raw lines for copy
                    formatted_lines = []  # Lines with timestamps for display
                    process_ref = {"process": None, "cancelled": False}
                    search_state = {"term": "", "count": 0}
                    
                    def get_log_level(line: str) -> tuple[str, str]:
                        """Determine log level and color from line content."""
                        line_lower = line.lower()
                        if "error" in line_lower or "failed" in line_lower:
                            return "ERROR", "text-red-400"
                        elif "warning" in line_lower or "warn" in line_lower:
                            return "WARN", "text-amber-400"
                        elif "apply complete" in line_lower or "resources:" in line_lower:
                            return "DONE", "text-green-400"
                        elif line.startswith("#") or "will be" in line_lower:
                            return "INFO", "text-blue-400"
                        elif "creating" in line_lower or "created" in line_lower:
                            return "ADD", "text-green-400"
                        elif "destroying" in line_lower or "destroyed" in line_lower:
                            return "DEL", "text-red-400"
                        elif "modifying" in line_lower or "modified" in line_lower:
                            return "CHG", "text-amber-400"
                        else:
                            return "INFO", "text-slate-400"
                    
                    def format_log_line(line: str) -> str:
                        """Format a line with timestamp and level."""
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        level, color = get_log_level(line)
                        escaped_line = html_module.escape(line)
                        return f'<span class="text-slate-500">[{timestamp}]</span> <span class="{color}">[{level:5}]</span> {escaped_line}'
                    
                    with ui.dialog() as stream_dialog, ui.card().classes("w-full h-full").style("width: 90vw; max-width: 90vw; height: 80vh; display: flex; flex-direction: column;"):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            with ui.row().classes("items-center gap-3"):
                                stream_spinner = ui.spinner("dots", size="md").classes("text-primary")
                                stream_title = ui.label("Running terraform apply...").classes("text-xl font-bold")
                            ui.button(icon="close", on_click=stream_dialog.close).props("flat round")
                        
                        ui.label(f"Directory: {tf_path}").classes("text-xs text-slate-500 font-mono mb-2")
                        
                        # Search bar
                        with ui.row().classes("w-full items-center gap-2 mb-2"):
                            search_input = ui.input(placeholder="Search in output...").props("outlined dense clearable").classes("flex-1")
                            search_count_label = ui.label("").classes("text-xs text-slate-400 min-w-[80px]")
                        
                        with ui.scroll_area().classes("w-full flex-grow apply-stream-scroll-area"):
                            stream_log = ui.html('<pre class="text-xs font-mono whitespace-pre-wrap p-2 bg-slate-900 text-slate-100 rounded apply-stream-log-content" style="min-height: 200px;">[Starting terraform apply...]\n</pre>')
                        
                        # Search handler
                        async def on_search(e):
                            term = e.args if e.args else ""
                            search_state["term"] = term
                            if not term:
                                search_count_label.set_text("")
                                return
                            
                            # Count matches in raw output
                            full_output = "\n".join(output_lines)
                            count = full_output.lower().count(term.lower())
                            search_state["count"] = count
                            search_count_label.set_text(f"{count} matches" if count else "No matches")
                            
                            # Highlight in viewer
                            if count > 0:
                                escaped_term = term.replace("'", "\\'").replace('"', '\\"')
                                await ui.run_javascript(f'''
                                    const pre = document.querySelector('.apply-stream-log-content');
                                    if (pre) {{
                                        const html = pre.innerHTML;
                                        const regex = new RegExp('({escaped_term})', 'gi');
                                        pre.innerHTML = html.replace(regex, '<mark class="bg-yellow-500 text-black px-0.5">$1</mark>');
                                        const mark = document.querySelector('.apply-stream-log-content mark');
                                        if (mark) mark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                    }}
                                ''')
                        
                        search_input.on("update:model-value", on_search)
                        
                        with ui.row().classes("w-full justify-between mt-2"):
                            def cancel_apply():
                                if process_ref["process"] and process_ref["process"].returncode is None:
                                    process_ref["cancelled"] = True
                                    process_ref["process"].kill()
                                    cancel_line = "⚠️ CANCELLED: Apply was cancelled by user"
                                    output_lines.append(cancel_line)
                                    formatted_lines.append(format_log_line(cancel_line))
                                    ui.notify("Apply cancelled", type="warning")
                            
                            cancel_btn = ui.button("Cancel", icon="cancel", on_click=cancel_apply).props("outline color=negative")
                            
                            with ui.row().classes("gap-2"):
                                def copy_stream_output():
                                    content = "\n".join(output_lines)
                                    ui.run_javascript(f'navigator.clipboard.writeText({repr(content)})')
                                    ui.notify("Copied to clipboard", type="positive")
                                ui.button("Copy", icon="content_copy", on_click=copy_stream_output).props("outline")
                                ui.button("Close", on_click=stream_dialog.close)
                    
                    stream_dialog.props("maximized")
                    stream_dialog.open()
                    
                    with match_terminal_output:
                        match_terminal_output.clear()
                        ui.label("Running terraform apply...").classes("text-xs text-slate-500")
                    
                    # Run terraform apply with streaming output
                    try:
                        process = await asyncio.create_subprocess_exec(
                            "terraform", "apply", "-auto-approve", "-no-color", "-input=false",
                            cwd=str(tf_path),
                            env=env,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.STDOUT,
                        )
                        process_ref["process"] = process
                        
                        # Stream output line by line
                        while True:
                            try:
                                line = await asyncio.wait_for(process.stdout.readline(), timeout=600)  # 10 min timeout for apply
                            except asyncio.TimeoutError:
                                timeout_line = "⚠️ TIMEOUT: Apply exceeded 10 minute limit"
                                output_lines.append(timeout_line)
                                formatted_lines.append(format_log_line(timeout_line))
                                process.kill()
                                break
                            
                            if not line:
                                break
                            
                            decoded_line = line.decode('utf-8', errors='replace').rstrip()
                            output_lines.append(decoded_line)
                            formatted_lines.append(format_log_line(decoded_line))
                            
                            # Save output incrementally so it's available if dialog is closed early
                            tf_outputs["apply"] = "\n".join(output_lines)
                            
                            # Update the viewer with formatted output (timestamps + levels)
                            formatted_output = "\n".join(formatted_lines)
                            stream_log.content = f'<pre class="text-xs font-mono whitespace-pre-wrap p-2 bg-slate-900 text-slate-100 rounded apply-stream-log-content" style="min-height: 200px;">{formatted_output}</pre>'
                            stream_log.update()
                        
                        await process.wait()
                        returncode = process.returncode
                        
                    except Exception as e:
                        error_line = f"❌ ERROR: {e}"
                        output_lines.append(error_line)
                        formatted_lines.append(format_log_line(error_line))
                        returncode = 1
                    
                    # Hide cancel button when done
                    cancel_btn.set_visibility(False)
                    
                    apply_output = "\n".join(output_lines)
                    tf_outputs["apply"] = apply_output
                    
                    # Update dialog title and hide spinner
                    stream_spinner.set_visibility(False)
                    if process_ref["cancelled"]:
                        stream_title.set_text("⚠️ Apply Cancelled")
                        ui.notify("Apply was cancelled", type="warning")
                    elif returncode == 0:
                        stream_title.set_text("✅ Apply Complete!")
                        ui.notify("Apply completed successfully! Syncing state...", type="positive", timeout=5000)
                        # Clear the pending state
                        state.map.protection_fix_pending = False
                        state.map.protection_fix_file_path = ""
                        state.map.protection_fix_action = ""
                        
                        # CRITICAL: Sync protected_resources set with the new TF state
                        # This prevents the protection mismatch from flip-flopping
                        try:
                            new_state_result = await read_terraform_state(tf_path)
                            if new_state_result.success and new_state_result.resources:
                                # Build new protected_resources set based on current TF state
                                new_protected: set[str] = set()
                                for res in new_state_result.resources:
                                    if ".protected_" in res.address:
                                        # Extract key from address and add to protected set
                                        # Address format: module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["key"]
                                        if '["' in res.address and '"]' in res.address:
                                            key_start = res.address.rfind('["') + 2
                                            key_end = res.address.rfind('"]')
                                            if key_start > 1 and key_end > key_start:
                                                resource_key = res.address[key_start:key_end]
                                                new_protected.add(resource_key)
                                # Replace the protected_resources set with the synced version
                                state.map.protected_resources = new_protected
                                ui.notify(f"Synced {len(new_protected)} protected resources from TF state", type="info")
                        except Exception as sync_err:
                            # Don't fail the apply just because sync failed
                            ui.notify(f"Warning: Could not sync protected state: {sync_err}", type="warning")
                        
                        save_state()
                        # Show reload suggestion instead of auto-reload (which clears tf_outputs)
                        ui.notify("Click 'Reload Page' to see updated protection state", type="info", timeout=10000)
                    else:
                        stream_title.set_text("❌ Apply Failed")
                        ui.notify("Apply failed - see output for details", type="negative")
                    
                    # Update status in the match terminal area
                    with match_terminal_output:
                        match_terminal_output.clear()
                        if process_ref["cancelled"]:
                            ui.label("⚠️ Apply cancelled").classes("text-xs text-amber-600 font-semibold")
                        elif returncode == 0:
                            with ui.row().classes("items-center gap-2"):
                                ui.label("✅ Apply completed! Protection moves applied.").classes("text-xs text-green-600 font-semibold")
                                ui.button("Reload Page", icon="refresh", on_click=lambda: ui.navigate.reload()).props("flat dense color=primary").classes("text-xs")
                        else:
                            ui.label("❌ Apply failed").classes("text-xs text-red-600 font-semibold")
                
                ui.button("Apply", icon="rocket_launch", on_click=run_match_apply).props("color=positive").style("min-width: 100px;")
                
                # Spacer
                ui.space()
                
                def show_match_ai_debug():
                    """Show AI debugging summary for protection mismatches."""
                    lines = [
                        "# Protection Mismatch Debug Report (Match Page)",
                        "",
                        f"**Generated**: {__import__('datetime').datetime.now().isoformat()}",
                        f"**Terraform Dir**: `{tf_path}`",
                        "",
                        "## Summary",
                        f"- **Total Mismatches**: {len(protection_mismatches)}",
                        f"- **Unique Projects**: {len(unique_projects_with_mismatches)}",
                        "",
                        "## Mismatches by Project",
                        "",
                    ]
                    
                    by_project: dict[str, list] = {}
                    for m in protection_mismatches:
                        pkey = m.get("project_name") or m.get("key")
                        if pkey not in by_project:
                            by_project[pkey] = []
                        by_project[pkey].append(m)
                    
                    for project_key, items in sorted(by_project.items()):
                        direction = "unprotect" if items[0]["state_protected"] else "protect"
                        lines.append(f"### `{project_key}` ({direction})")
                        lines.append("")
                        
                        for m in items:
                            state_status = "protected" if m["state_protected"] else "unprotected"
                            yaml_status = "protected" if m["yaml_protected"] else "unprotected"
                            lines.append(f"- **{m['type']}** (`{m['key']}`)")
                            lines.append(f"  - State: {state_status}")
                            lines.append(f"  - YAML: {yaml_status}")
                            lines.append(f"  - Action: Move to {direction}ed collection")
                        lines.append("")
                    
                    lines.extend([
                        "## Resolution Steps",
                        "",
                        "1. Click **Protect All** or **Unprotect All** to generate moved blocks",
                        "2. Click **Init** to initialize Terraform",
                        "3. Click **Plan** to preview changes (should show 0 add, 0 destroy)",
                        "4. Click **Apply** to execute the state moves",
                        "",
                        "## Raw Mismatch Data",
                        "",
                        "```python",
                    ])
                    
                    for m in protection_mismatches:
                        lines.append(f"{{")
                        lines.append(f"    'key': '{m['key']}',")
                        lines.append(f"    'type': '{m['type']}',")
                        lines.append(f"    'state_protected': {m['state_protected']},")
                        lines.append(f"    'yaml_protected': {m['yaml_protected']},")
                        lines.append(f"}},")
                    lines.append("```")
                    
                    report = "\n".join(lines)
                    
                    with ui.dialog() as debug_dialog, ui.card().classes("w-full max-h-[90vh] p-6").style("width: 90vw; max-width: 90vw;"):
                        with ui.row().classes("w-full items-center justify-between mb-3"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("bug_report", size="md").classes("text-purple-500")
                                ui.label("AI Debug Report").classes("text-xl font-bold")
                            ui.button(icon="close", on_click=debug_dialog.close).props("flat round size=sm")
                        
                        ui.separator()
                        
                        with ui.scroll_area().classes("w-full").style("max-height: 60vh;"):
                            ui.markdown(report).classes("text-sm")
                        
                        ui.separator()
                        
                        with ui.row().classes("w-full justify-end gap-2 mt-2"):
                            def copy_report():
                                ui.run_javascript(f'navigator.clipboard.writeText({repr(report)})')
                                ui.notify("Copied to clipboard!", type="positive")
                            
                            ui.button("Copy to Clipboard", icon="content_copy", on_click=copy_report).props("outline")
                            ui.button("Close", on_click=debug_dialog.close).props("flat")
                    
                    debug_dialog.open()
                
                ui.button("AI Debug", icon="bug_report", on_click=show_match_ai_debug).props("flat color=purple")
                
                # Pre-create a reusable viewer dialog at page level
                viewer_state = {"content": "", "title": "", "step": ""}
                viewer_dialog = ui.dialog().props("maximized")
                with viewer_dialog:
                    with ui.card().classes("w-full h-full").style("display: flex; flex-direction: column;"):
                        with ui.row().classes("w-full items-center justify-between mb-2"):
                            with ui.row().classes("items-center gap-3"):
                                ui.icon("assignment", size="lg").classes("text-orange-500")
                                viewer_title_label = ui.label("Output Viewer").classes("text-xl font-bold")
                            ui.button(icon="close", on_click=viewer_dialog.close).props("flat round")
                        
                        # Stats bar for plan output (hidden initially)
                        viewer_stats_row = ui.row().classes("w-full gap-4 mb-2 p-3 bg-slate-100 dark:bg-slate-800 rounded items-center")
                        viewer_stats_row.set_visibility(False)
                        with viewer_stats_row:
                            ui.label("Plan Summary:").classes("font-semibold")
                            viewer_stats_move = ui.row().classes("items-center gap-1")
                            with viewer_stats_move:
                                ui.icon("swap_horiz", size="sm").classes("text-blue-600")
                                viewer_stats_move_label = ui.label("0 to move").classes("text-blue-600 font-medium")
                            viewer_stats_add = ui.row().classes("items-center gap-1")
                            with viewer_stats_add:
                                ui.icon("add_circle", size="sm").classes("text-green-600")
                                viewer_stats_add_label = ui.label("0 to add").classes("text-green-600 font-medium")
                            viewer_stats_change = ui.row().classes("items-center gap-1")
                            with viewer_stats_change:
                                ui.icon("change_circle", size="sm").classes("text-amber-600")
                                viewer_stats_change_label = ui.label("0 to change").classes("text-amber-600 font-medium")
                            viewer_stats_destroy = ui.row().classes("items-center gap-1")
                            with viewer_stats_destroy:
                                ui.icon("remove_circle", size="sm").classes("text-red-600")
                                viewer_stats_destroy_label = ui.label("0 to destroy").classes("text-red-600 font-medium")
                        
                        with ui.scroll_area().classes("w-full").style("flex: 1; min-height: 0;"):
                            viewer_code = ui.code("", language="text").classes("w-full text-sm")
                        
                        with ui.row().classes("w-full justify-end gap-2 mt-4"):
                            def copy_viewer_content():
                                ui.run_javascript(f'navigator.clipboard.writeText({repr(viewer_state["content"])})')
                                ui.notify("Copied to clipboard", type="positive")
                            ui.button("Copy to Clipboard", icon="content_copy", on_click=copy_viewer_content).props("outline")
                            ui.button("Close", on_click=viewer_dialog.close)
                
                def show_view_output_menu():
                    """Show a menu to select which output to view."""
                    with ui.dialog() as menu_dialog, ui.card().style("width: 300px;"):
                        ui.label("View Terraform Output").classes("text-lg font-bold mb-3")
                        
                        with ui.column().classes("w-full gap-2"):
                            def view_and_close(step, title):
                                output = tf_outputs.get(step, "")
                                if not output:
                                    ui.notify(f"No {step} output available. Run {step} first.", type="warning")
                                    menu_dialog.close()
                                    return
                                
                                menu_dialog.close()
                                
                                # Update the pre-created viewer dialog
                                viewer_state["content"] = output
                                viewer_state["title"] = title
                                viewer_state["step"] = step
                                viewer_title_label.set_text(title)
                                viewer_code.content = output
                                viewer_code.update()
                                
                                # Show/hide and update stats bar for plan output
                                if step == "plan":
                                    from importer.web.utils.yaml_viewer import parse_plan_stats
                                    stats = parse_plan_stats(output)
                                    viewer_stats_move_label.set_text(f"{stats.get('move', 0)} to move")
                                    viewer_stats_add_label.set_text(f"{stats.get('add', 0)} to add")
                                    viewer_stats_change_label.set_text(f"{stats.get('change', 0)} to change")
                                    viewer_stats_destroy_label.set_text(f"{stats.get('destroy', 0)} to destroy")
                                    # Show move stat only if > 0
                                    viewer_stats_move.set_visibility(stats.get('move', 0) > 0)
                                    viewer_stats_row.set_visibility(True)
                                else:
                                    viewer_stats_row.set_visibility(False)
                                
                                viewer_dialog.open()
                            
                            ui.button(
                                "Generated Moved Blocks",
                                icon="build",
                                on_click=lambda: view_and_close("generate", "Generated Moved Blocks"),
                            ).props("outline color=amber").classes("w-full justify-start")
                            
                            ui.button(
                                "Init Output",
                                icon="downloading",
                                on_click=lambda: view_and_close("init", "Terraform Init Output"),
                            ).props("outline").classes("w-full justify-start")
                            
                            ui.button(
                                "Validate Output",
                                icon="check_circle",
                                on_click=lambda: view_and_close("validate", "Terraform Validate Output"),
                            ).props("outline").classes("w-full justify-start")
                            
                            ui.button(
                                "Plan Output",
                                icon="preview",
                                on_click=lambda: view_and_close("plan", "Terraform Plan Output"),
                            ).props("outline color=primary").classes("w-full justify-start")
                            
                            ui.button(
                                "Apply Output",
                                icon="rocket_launch",
                                on_click=lambda: view_and_close("apply", "Terraform Apply Output"),
                            ).props("outline color=positive").classes("w-full justify-start")
                        
                        ui.button("Close", on_click=menu_dialog.close).props("flat").classes("mt-3")
                    
                    menu_dialog.open()
                
                ui.button("View Output", icon="visibility", on_click=show_view_output_menu).props("flat")
            
            # Output area
            with match_terminal_output:
                ui.label("For protection changes: Skip Generate, just run Init → Plan → Apply").classes("text-xs text-slate-400")
                ui.label("Generate regenerates ALL files which can cause conflicts").classes("text-xs text-amber-500")
    
    # Save target intent section (show if there are any confirmed or pending matches)
    # State-only rows are now counted as regular confirmed/matched rows
    has_matches = any(r.get("action") == "match" and r.get("target_id") for r in grid_row_data)
    confirmed_count = sum(1 for r in grid_row_data if r.get("status") == "confirmed")
    pending_match_count = sum(1 for r in grid_row_data if r.get("status") == "pending" and r.get("action") == "match" and r.get("target_id"))
    
    if has_matches:
        # Added flex-shrink: 0, max-width and overflow: hidden to prevent being pushed sideways by sibling elements
        with ui.card().classes("w-full p-4 mt-4").style(f"border: 2px solid {DBT_TEAL}; max-width: 100%; flex-shrink: 0; overflow: hidden;"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-1"):
                    ui.label("Save Target Intent").classes("font-semibold")
                    if confirmed_count > 0:
                        ui.label(
                            f"{confirmed_count} confirmed mappings"
                        ).classes("text-sm text-green-600")
                    if pending_match_count > 0:
                        ui.label(
                            f"{pending_match_count} pending matches (accept to include)"
                        ).classes("text-sm text-amber-600")
                    
                    if state.map.mapping_file_path:
                        ui.label(f"Last saved: {state.map.mapping_file_path}").classes("text-xs text-green-600 mt-1")
                
                def save_mappings():
                    try:
                        # Confidence types that represent automatic matching (not manual selection)
                        auto_match_types = {
                            "exact_match", "state_id_match", "url_match", "github_match", "env_match"
                        }
                        # Build confirmed mappings from grid data (skip state-only rows)
                        mappings_to_save = []
                        for row in grid_data_ref["data"]:
                            if row.get("is_state_only"):
                                continue  # State-only rows are in state_to_target, not source_to_target
                            if row.get("status") == "confirmed" and row.get("target_id"):
                                confidence = row.get("confidence", "manual")
                                mappings_to_save.append({
                                    "resource_type": row.get("source_type"),
                                    "source_name": row.get("source_name"),
                                    "source_key": row.get("source_key"),
                                    "target_id": row.get("target_id"),
                                    "target_name": row.get("target_name"),
                                    # Preserve the actual confidence type for better diagnostics
                                    "match_type": confidence if confidence in auto_match_types else "manual",
                                })
                        
                        if not mappings_to_save:
                            ui.notify("No confirmed mappings to save. Accept pending matches first.", type="warning")
                            return
                        
                        mapping = create_mapping_from_confirmations(
                            mappings_to_save,
                            state.source_account.account_id or "unknown",
                            state.target_account.account_id or "unknown",
                        )
                        
                        output_dir = Path(state.fetch.output_dir)
                        output_path = output_dir / "target_resource_mapping.yml"
                        
                        error = save_mapping_file(mapping, output_path)
                        if error:
                            ui.notify(f"Error saving: {error}", type="negative")
                        else:
                            state.map.mapping_file_path = str(output_path)
                            state.map.mapping_file_valid = True
                            state.map.confirmed_mappings = mappings_to_save
                            save_state()
                            _persist_target_intent_from_match(state)
                            ui.notify(f"Mapping saved to {output_path}", type="positive")
                            # Reload to update navigation button state
                            ui.navigate.reload()
                            
                    except Exception as e:
                        ui.notify(f"Error: {e}", type="negative")
                
                def view_mapping_file():
                    if state.map.mapping_file_path and Path(state.map.mapping_file_path).exists():
                        dialog = create_yaml_viewer_dialog(
                            state.map.mapping_file_path,
                            title="Target Intent"
                        )
                        dialog.open()
                    else:
                        ui.notify("Mapping file not found. Save the mapping first.", type="warning")
                
                with ui.row().classes("gap-2"):
                    save_btn = ui.button(
                        "Save Target Intent",
                        icon="save",
                        on_click=save_mappings,
                    ).style(f"background-color: {DBT_TEAL};")
                    
                    if confirmed_count == 0:
                        save_btn.disable()
                        save_btn.tooltip("Accept pending matches first")
                    
                    if state.map.mapping_file_path:
                        ui.button(
                            "View Target Intent",
                            icon="visibility",
                            on_click=view_mapping_file,
                        ).props("outline")
    
    # Navigation section - placed inside _create_matching_content to access grid data
    _create_navigation_with_grid_data(
        state, 
        on_step_change, 
        save_state,
        confirmed_count=confirmed_count,
        has_unsaved_confirmed=confirmed_count > 0 and not state.map.mapping_file_valid,
    )


def _create_stat_card(label: str, value: int, color_class: str, icon_name: str) -> None:
    """Create a stat card."""
    with ui.card().classes("p-3 min-w-[120px]"):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon_name, size="sm").classes(color_class)
            ui.label(str(value)).classes(f"text-2xl font-bold {color_class}")
        ui.label(label).classes("text-xs text-slate-500")


def _create_navigation_with_grid_data(
    state: AppState,
    on_step_change: Callable[[WorkflowStep], None],
    save_state: Callable[[], None],
    confirmed_count: int = 0,
    has_unsaved_confirmed: bool = False,
) -> None:
    """Create navigation buttons with grid-aware logic.
    
    Args:
        state: Application state
        on_step_change: Step change callback
        save_state: State save callback  
        confirmed_count: Number of confirmed mappings in current grid
        has_unsaved_confirmed: True if there are confirmed mappings that need saving
    """
    # Added flex-shrink: 0 and max-width to prevent being pushed sideways by sibling elements
    with ui.row().classes("w-full justify-between mt-4").style("max-width: 100%; flex-shrink: 0;"):
        ui.button(
            f"Back to {state.get_step_label(WorkflowStep.EXPLORE_TARGET)}",
            icon="arrow_back",
            on_click=lambda: on_step_change(WorkflowStep.EXPLORE_TARGET),
        ).props("outline")
        
        # Show mapping status and continue button
        with ui.row().classes("items-center gap-4"):
            if state.map.mapping_file_valid and confirmed_count > 0:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("check_circle", size="sm").classes("text-green-500")
                    ui.label("Mapping saved").classes("text-green-600 text-sm")
            elif has_unsaved_confirmed:
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning", size="sm").classes("text-amber-500")
                    ui.label("Save mapping file to continue").classes("text-amber-600 text-sm")
            
            # Allow continue if:
            # - Mapping file is saved and valid, OR
            # - There are no confirmed mappings that need saving (all create-new)
            continue_enabled = state.map.mapping_file_valid or not has_unsaved_confirmed
            
            def on_continue(unsaved=has_unsaved_confirmed):
                # Mark mapping as valid if we're allowing continue without saving
                # (this happens when all items are "Create New" - no matches to save)
                if not unsaved and not state.map.mapping_file_valid:
                    state.map.mapping_file_valid = True
                    save_state()
                on_step_change(WorkflowStep.CONFIGURE)
            
            btn = ui.button(
                f"Continue to {state.get_step_label(WorkflowStep.CONFIGURE)}",
                icon="arrow_forward",
                on_click=on_continue,
            ).style(f"background-color: {DBT_ORANGE};")
            
            if not continue_enabled:
                btn.disable()
