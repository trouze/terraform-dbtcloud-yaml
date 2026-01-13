"""Selection manager for persistent entity selection storage."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

# Default storage directory for selections
SELECTIONS_DIR = ".magellan/selections"


def _generate_url_hash(base_url: str) -> str:
    """Generate a short hash from a URL for unique identification."""
    return hashlib.sha256(base_url.encode()).hexdigest()[:8]


def _get_storage_key(account_id: str, base_url: str) -> str:
    """Generate a storage filename key from account ID and URL."""
    url_hash = _generate_url_hash(base_url)
    return f"{account_id}_{url_hash}"


class SelectionManager:
    """Manages persistent entity selections for an account.
    
    Selections are stored separately from fetched data, keyed by account ID
    and URL hash. This allows selections to persist across refetches and
    handles new/missing entities gracefully.
    """
    
    def __init__(self, account_id: str, base_url: str, storage_dir: Optional[str] = None):
        """Initialize the selection manager.
        
        Args:
            account_id: The dbt Cloud account ID
            base_url: The base URL of the dbt Cloud instance
            storage_dir: Optional custom storage directory (defaults to .magellan/selections)
        """
        self.account_id = account_id
        self.base_url = base_url
        self.url_hash = _generate_url_hash(base_url)
        self.storage_key = _get_storage_key(account_id, base_url)
        
        # Storage path
        self.storage_dir = Path(storage_dir) if storage_dir else Path(SELECTIONS_DIR)
        self.storage_file = self.storage_dir / f"{self.storage_key}.json"
        
        # In-memory selections: element_mapping_id -> selected (True/False)
        self._selections: Dict[str, bool] = {}
        self._last_updated: Optional[datetime] = None
        self._loaded = False
    
    @property
    def selections(self) -> Dict[str, bool]:
        """Get the current selections dictionary."""
        return self._selections
    
    def load(self) -> bool:
        """Load selections from storage file.
        
        Returns:
            True if selections were loaded, False if file doesn't exist
        """
        if not self.storage_file.exists():
            self._loaded = True
            return False
        
        try:
            data = json.loads(self.storage_file.read_text(encoding="utf-8"))
            
            # Validate account ID matches
            if data.get("account_id") != self.account_id:
                # Mismatched account, start fresh
                self._selections = {}
                self._loaded = True
                return False
            
            self._selections = data.get("selections", {})
            
            if data.get("last_updated"):
                self._last_updated = datetime.fromisoformat(data["last_updated"])
            
            self._loaded = True
            return True
            
        except (json.JSONDecodeError, IOError, KeyError):
            # Corrupted file, start fresh
            self._selections = {}
            self._loaded = True
            return False
    
    def save(self) -> bool:
        """Save selections to storage file.
        
        Returns:
            True if saved successfully, False on error
        """
        try:
            # Ensure storage directory exists
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            
            self._last_updated = datetime.now()
            
            data = {
                "account_id": self.account_id,
                "base_url": self.base_url,
                "url_hash": self.url_hash,
                "last_updated": self._last_updated.isoformat(),
                "version": 1,
                "selections": self._selections,
            }
            
            self.storage_file.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8"
            )
            return True
            
        except (IOError, OSError) as e:
            print(f"Error saving selections: {e}")
            return False
    
    def reconcile_with_entities(
        self, 
        entities: List[Dict], 
        default_selected: bool = True
    ) -> Dict[str, any]:
        """Reconcile stored selections with current entity list.
        
        This handles:
        - New entities (in fetch, not in selections): use default
        - Missing entities (in selections, not in fetch): remove from selections
        - Existing entities: preserve stored selection
        
        Args:
            entities: List of entity dicts with 'element_mapping_id' key
            default_selected: Default selection state for new entities
            
        Returns:
            Dict with reconciliation stats
        """
        if not self._loaded:
            self.load()
        
        # Get current entity IDs from the fetch
        current_ids = {
            e.get("element_mapping_id") 
            for e in entities 
            if e.get("element_mapping_id")
        }
        
        # Get stored selection IDs
        stored_ids = set(self._selections.keys())
        
        # Find new entities (in fetch, not in selections)
        new_ids = current_ids - stored_ids
        
        # Find missing entities (in selections, not in fetch)
        missing_ids = stored_ids - current_ids
        
        # Find existing entities (in both)
        existing_ids = current_ids & stored_ids
        
        # Apply defaults for new entities
        for entity_id in new_ids:
            # Look up the entity to check its include_in_conversion default
            entity = next(
                (e for e in entities if e.get("element_mapping_id") == entity_id), 
                None
            )
            if entity:
                # Use entity's include_in_conversion if present, else default
                self._selections[entity_id] = entity.get("include_in_conversion", default_selected)
        
        # Remove missing entities from selections
        for entity_id in missing_ids:
            del self._selections[entity_id]
        
        # Auto-save after reconciliation
        self.save()
        
        return {
            "new_count": len(new_ids),
            "missing_count": len(missing_ids),
            "existing_count": len(existing_ids),
            "total_selected": sum(1 for v in self._selections.values() if v),
            "total_entities": len(current_ids),
        }
    
    def is_selected(self, element_mapping_id: str) -> bool:
        """Check if an entity is selected.
        
        Args:
            element_mapping_id: The entity's mapping ID
            
        Returns:
            True if selected, False otherwise
        """
        return self._selections.get(element_mapping_id, True)
    
    def set_selected(self, element_mapping_id: str, selected: bool, auto_save: bool = True) -> None:
        """Set the selection state for an entity.
        
        Args:
            element_mapping_id: The entity's mapping ID
            selected: Whether the entity should be selected
            auto_save: Whether to auto-save after change (default True)
        """
        self._selections[element_mapping_id] = selected
        if auto_save:
            self.save()
    
    def toggle_selection(self, element_mapping_id: str, auto_save: bool = True) -> bool:
        """Toggle the selection state for an entity.
        
        Args:
            element_mapping_id: The entity's mapping ID
            auto_save: Whether to auto-save after change (default True)
            
        Returns:
            The new selection state
        """
        current = self._selections.get(element_mapping_id, True)
        new_state = not current
        self._selections[element_mapping_id] = new_state
        if auto_save:
            self.save()
        return new_state
    
    def select_all(self, entity_ids: Optional[Set[str]] = None, auto_save: bool = True) -> int:
        """Select all entities (or a subset).
        
        Args:
            entity_ids: Optional set of IDs to select (all if None)
            auto_save: Whether to auto-save after change
            
        Returns:
            Number of entities selected
        """
        ids_to_select = entity_ids if entity_ids else set(self._selections.keys())
        count = 0
        for entity_id in ids_to_select:
            if entity_id in self._selections:
                self._selections[entity_id] = True
                count += 1
        if auto_save:
            self.save()
        return count
    
    def deselect_all(self, entity_ids: Optional[Set[str]] = None, auto_save: bool = True) -> int:
        """Deselect all entities (or a subset).
        
        Args:
            entity_ids: Optional set of IDs to deselect (all if None)
            auto_save: Whether to auto-save after change
            
        Returns:
            Number of entities deselected
        """
        ids_to_deselect = entity_ids if entity_ids else set(self._selections.keys())
        count = 0
        for entity_id in ids_to_deselect:
            if entity_id in self._selections:
                self._selections[entity_id] = False
                count += 1
        if auto_save:
            self.save()
        return count
    
    def invert_selection(self, entity_ids: Optional[Set[str]] = None, auto_save: bool = True) -> None:
        """Invert selection for all entities (or a subset).
        
        Args:
            entity_ids: Optional set of IDs to invert (all if None)
            auto_save: Whether to auto-save after change
        """
        ids_to_invert = entity_ids if entity_ids else set(self._selections.keys())
        for entity_id in ids_to_invert:
            if entity_id in self._selections:
                self._selections[entity_id] = not self._selections[entity_id]
        if auto_save:
            self.save()
    
    def get_selected_ids(self) -> Set[str]:
        """Get the set of selected entity IDs.
        
        Returns:
            Set of element_mapping_ids that are selected
        """
        return {k for k, v in self._selections.items() if v}
    
    def get_deselected_ids(self) -> Set[str]:
        """Get the set of deselected entity IDs.
        
        Returns:
            Set of element_mapping_ids that are deselected
        """
        return {k for k, v in self._selections.items() if not v}
    
    def get_selection_counts(self) -> Dict[str, int]:
        """Get selection counts.
        
        Returns:
            Dict with 'selected', 'deselected', 'total' counts
        """
        selected = sum(1 for v in self._selections.values() if v)
        total = len(self._selections)
        return {
            "selected": selected,
            "deselected": total - selected,
            "total": total,
        }
    
    def clear(self, auto_save: bool = True) -> None:
        """Clear all selections.
        
        Args:
            auto_save: Whether to auto-save after clear
        """
        self._selections.clear()
        if auto_save:
            self.save()
