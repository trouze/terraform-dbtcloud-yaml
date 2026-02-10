"""Protection Intent Manager - Single source of truth for user protection decisions.

This module provides the ProtectionIntentManager class that tracks explicit user
intent for resource protection, with full audit trail. Intent takes precedence
over YAML configuration to prevent "flip-flopping" of protection flags.

Protection Architecture (Two Independent Scopes):
-------------------------------------------------
1. PROJECT (PRJ:) - Protected independently
   - Key format: "PRJ:{resource_name}"
   - TF resource: dbtcloud_project.{name}
   - Can be protected/unprotected without affecting repo

2. REPOSITORY (REPO:) - Repository + PREP always protected together
   - Key format: "REPO:{resource_name}"
   - TF resources: dbtcloud_repository.{name} AND dbtcloud_project_repository.{name}
   - A single REPO intent generates TWO moved blocks in TF
   - These resources are architecturally paired - cannot exist separately

Key Design Decisions:
- Intent takes precedence: If intent file says "unprotected", ignore YAML `protected: true`
- YAML as fallback: If no intent for a resource, fall back to YAML flag
- History for audit: Full trail of who changed what and when
- REPO consolidation: Single intent key covers both repository and project_repository_link

IMPORTANT: Debug instrumentation in this module MUST NOT be removed.
See tasks/prd-web-ui-12-debug-logging-standards.md for guidelines.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from importer.web.utils.ui_logger import traced, log_state_change

logger = logging.getLogger(__name__)


@dataclass
class ProtectionIntent:
    """A single protection intent for a resource.
    
    This represents a user's explicit decision about whether a resource
    should be protected, along with metadata about when and why the
    decision was made, and whether it has been applied.
    
    Attributes:
        protected: Whether the resource should be protected
        set_at: ISO timestamp when the intent was set
        set_by: Source of the intent (e.g., "user_click", "unprotect_all", "import")
        reason: Human-readable reason for the decision
        resource_type: Resource type code (PRJ, REPO) for display purposes. REPO covers both repository and project_repository_link.
        applied_to_yaml: Whether this intent has been written to YAML config
        applied_to_tf_state: Whether TF state has been moved to match this intent
        tf_state_at_decision: Protection status in TF state when decision was made
    """
    
    protected: bool
    set_at: str
    set_by: str
    reason: str
    resource_type: Optional[str] = None  # PRJ, REP, PREP - added for display
    applied_to_yaml: bool = False
    applied_to_tf_state: bool = False
    tf_state_at_decision: Optional[str] = None  # "protected", "unprotected", or None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "protected": self.protected,
            "set_at": self.set_at,
            "set_by": self.set_by,
            "reason": self.reason,
            "resource_type": self.resource_type,
            "applied_to_yaml": self.applied_to_yaml,
            "applied_to_tf_state": self.applied_to_tf_state,
            "tf_state_at_decision": self.tf_state_at_decision,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProtectionIntent":
        """Create from dictionary."""
        return cls(
            protected=data.get("protected", False),
            set_at=data.get("set_at", ""),
            set_by=data.get("set_by", ""),
            reason=data.get("reason", ""),
            resource_type=data.get("resource_type"),
            applied_to_yaml=data.get("applied_to_yaml", False),
            applied_to_tf_state=data.get("applied_to_tf_state", False),
            tf_state_at_decision=data.get("tf_state_at_decision"),
        )


@dataclass
class HistoryEntry:
    """An entry in the protection intent history.
    
    Records each protection change for audit purposes.
    """
    
    resource_key: str
    action: str  # "protect" or "unprotect"
    timestamp: str
    source: str
    tf_state_before: Optional[str] = None
    yaml_state_before: Optional[bool] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "resource_key": self.resource_key,
            "action": self.action,
            "timestamp": self.timestamp,
            "source": self.source,
            "tf_state_before": self.tf_state_before,
            "yaml_state_before": self.yaml_state_before,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        """Create from dictionary."""
        return cls(
            resource_key=data.get("resource_key", ""),
            action=data.get("action", ""),
            timestamp=data.get("timestamp", ""),
            source=data.get("source", ""),
            tf_state_before=data.get("tf_state_before"),
            yaml_state_before=data.get("yaml_state_before"),
        )


class ProtectionIntentManager:
    """Manages protection intent for all resources.
    
    This is the single source of truth for user protection decisions.
    Intent takes precedence over YAML configuration.
    
    Usage:
        manager = ProtectionIntentManager(Path("protection-intent.json"))
        manager.load()
        
        # Set a new intent
        manager.set_intent("my_project", protected=False, source="user_click", reason="Unprotect for deletion")
        
        # Get effective protection (intent or YAML fallback)
        is_protected = manager.get_effective_protection("my_project", yaml_protected=True)
        
        # Mark as applied after writing to YAML
        manager.mark_applied_to_yaml({"my_project"})
    """
    
    FILE_VERSION = 1
    
    def __init__(self, intent_file: Path) -> None:
        """Initialize the manager with a path to the intent file.
        
        Args:
            intent_file: Path to the protection-intent.json file
        """
        self._intent_file = intent_file
        self._intent: dict[str, ProtectionIntent] = {}
        self._history: list[HistoryEntry] = []
        # Callback fired after save() writes to protection-intent.json for each dirty key.
        # Signature: (resource_key: str, protected: bool) -> None
        self._on_intent_changed: Optional[callable] = None
        # Keys modified since last save, for syncing to target intent
        self._dirty_keys: set[str] = set()
    
    @traced
    def load(self) -> None:
        """Load intent data from the JSON file.
        
        Handles:
        - Missing file: Creates empty intent (no error)
        - Corrupted JSON: Raises ValueError
        """
        if not self._intent_file.exists():
            # Missing file is OK - start with empty intent
            logger.info(f"Intent file not found, starting fresh: {self._intent_file}")
            self._intent = {}
            self._history = []
            return
        
        try:
            content = self._intent_file.read_text(encoding="utf-8")
            data = json.loads(content)
            
            # Load intents
            self._intent = {}
            for key, intent_data in data.get("intent", {}).items():
                self._intent[key] = ProtectionIntent.from_dict(intent_data)
            
            # Load history
            self._history = []
            for entry_data in data.get("history", []):
                self._history.append(HistoryEntry.from_dict(entry_data))
            
            logger.info(f"Loaded {len(self._intent)} intent(s) and {len(self._history)} history entries")
            
            # CLEANUP: Remove unprefixed keys when a prefixed equivalent exists
            # This handles stale entries from older code that didn't always prefix keys
            unprefixed_to_remove = []
            prefixed_base_keys = {}
            for key in self._intent:
                if ":" in key:
                    _, base = key.split(":", 1)
                    prefixed_base_keys[base] = key
            for key in self._intent:
                if ":" not in key and key in prefixed_base_keys:
                    logger.warning(
                        f"Removing stale unprefixed intent key '{key}' "
                        f"(superseded by '{prefixed_base_keys[key]}')"
                    )
                    unprefixed_to_remove.append(key)
            if unprefixed_to_remove:
                for key in unprefixed_to_remove:
                    del self._intent[key]
                self.save()
                logger.info(f"Cleaned up {len(unprefixed_to_remove)} stale unprefixed intent(s)")
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted intent file: {e}")
    
    @traced
    def save(self) -> None:
        """Save intent data to the JSON file.
        
        Writes with version and updated_at fields for tracking.
        """
        data = {
            "version": self.FILE_VERSION,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "intent": {key: intent.to_dict() for key, intent in self._intent.items()},
            "history": [entry.to_dict() for entry in self._history],
        }
        
        # Ensure parent directory exists
        self._intent_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._intent_file.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        
        log_state_change(
            "protection_intent_file",
            "save",
            data={"intent_count": len(self._intent), "history_count": len(self._history)},
        )
        logger.info(f"Saved intent file: {self._intent_file}")

        # After writing protection-intent.json, sync dirty keys to target intent dispositions
        if self._on_intent_changed and self._dirty_keys:
            for key in self._dirty_keys:
                intent_entry = self._intent.get(key)
                if intent_entry is not None:
                    try:
                        self._on_intent_changed(key, intent_entry.protected)
                    except Exception as e:
                        logger.warning(f"Failed to sync protection to target intent for '{key}': {e}")
            self._dirty_keys.clear()
    
    @traced(log_result=True)
    def set_intent(
        self,
        key: str,
        protected: bool,
        source: str,
        reason: str,
        *,
        resource_type: Optional[str] = None,
        tf_state_at_decision: Optional[str] = None,
        yaml_state_before: Optional[bool] = None,
    ) -> ProtectionIntent:
        """Set or update protection intent for a resource.
        
        Creates a new intent or overwrites an existing one. Always adds a
        history entry to track the change.
        
        Args:
            key: Resource key, MUST be prefixed with TYPE: (e.g., "PRJ:my_project", "REPO:my_repo").
                Unprefixed keys are accepted for backward compatibility but a warning is logged.
            protected: Whether the resource should be protected
            source: Source of the intent (e.g., "user_click", "unprotect_all")
            reason: Human-readable reason for the decision
            resource_type: Resource type code (PRJ, REP, PREP) for display
            tf_state_at_decision: Current TF state protection status
            yaml_state_before: Current YAML protection status before this change
            
        Returns:
            The created/updated ProtectionIntent
        """
        # DEFENSIVE: Warn if key is unprefixed - callers should always prefix with TYPE:
        # Auto-prefix if resource_type is provided but key is missing prefix
        if ":" not in key:
            if resource_type:
                old_key = key
                key = f"{resource_type}:{key}"
                logger.warning(f"Auto-prefixed unprefixed intent key '{old_key}' → '{key}' (source={source})")
            else:
                logger.warning(f"Unprefixed intent key '{key}' with no resource_type (source={source}) - this may cause UNKNOWN type in UI")
        
        # Check if intent already exists with same protection value
        # Skip recording duplicate history if nothing actually changed
        existing_intent = self._intent.get(key)
        if existing_intent is not None and existing_intent.protected == protected:
            logger.debug(f"Intent for '{key}' already set to {protected}, skipping duplicate history entry")
            return existing_intent
        
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Create new intent (resets applied flags)
        intent = ProtectionIntent(
            protected=protected,
            set_at=timestamp,
            set_by=source,
            reason=reason,
            resource_type=resource_type,
            applied_to_yaml=False,
            applied_to_tf_state=False,
            tf_state_at_decision=tf_state_at_decision,
        )
        
        # Record history (only when intent actually changes)
        action = "protect" if protected else "unprotect"
        history_entry = HistoryEntry(
            resource_key=key,
            action=action,
            timestamp=timestamp,
            source=source,
            tf_state_before=tf_state_at_decision,
            yaml_state_before=yaml_state_before,
        )
        self._history.append(history_entry)
        
        # Store intent
        self._intent[key] = intent
        self._dirty_keys.add(key)
        
        log_state_change(
            "protection_intent",
            "set",
            data={"key": key, "protected": protected, "source": source},
        )
        
        return intent
    
    @traced(log_result=True)
    def get_intent(self, key: str) -> Optional[ProtectionIntent]:
        """Get the protection intent for a resource.
        
        Args:
            key: Resource key
            
        Returns:
            ProtectionIntent if one exists, None otherwise
        """
        return self._intent.get(key)
    
    def has_intent(self, key: str) -> bool:
        """Check if a resource has a recorded protection intent.
        
        Args:
            key: Resource key
            
        Returns:
            True if intent exists for this resource, False otherwise
        """
        return key in self._intent
    
    @traced(log_result=True)
    def get_effective_protection(self, key: str, yaml_protected: bool) -> bool:
        """Get the effective protection status for a resource.
        
        Intent takes precedence over YAML. If no intent exists for the resource,
        falls back to the YAML protection flag.
        
        Args:
            key: Resource key
            yaml_protected: Protection status from YAML config
            
        Returns:
            Effective protection status (True = protected)
        """
        intent = self._intent.get(key)
        if intent is not None:
            return intent.protected
        return yaml_protected
    
    @traced
    def mark_applied_to_yaml(self, keys: set[str]) -> None:
        """Mark intents as applied to YAML configuration.
        
        Args:
            keys: Set of resource keys that have been written to YAML
        """
        for key in keys:
            if key in self._intent:
                self._intent[key].applied_to_yaml = True
        
        log_state_change(
            "protection_intent",
            "mark_applied_to_yaml",
            data={"keys": list(keys)},
        )
    
    @traced
    def mark_applied_to_tf_state(self, keys: set[str]) -> None:
        """Mark intents as applied to Terraform state.
        
        Args:
            keys: Set of resource keys that have been moved in TF state
        """
        for key in keys:
            if key in self._intent:
                self._intent[key].applied_to_tf_state = True
        
        log_state_change(
            "protection_intent",
            "mark_applied_to_tf_state",
            data={"keys": list(keys)},
        )
    
    @traced(log_result=True)
    def get_pending_yaml_updates(self) -> dict[str, ProtectionIntent]:
        """Get intents that haven't been applied to YAML yet.
        
        Returns:
            Dict of resource_key -> ProtectionIntent for pending updates
        """
        return {
            key: intent
            for key, intent in self._intent.items()
            if not intent.applied_to_yaml
        }
    
    @traced(log_result=True)
    def get_pending_tf_moves(self) -> list[ProtectionIntent]:
        """Get intents that haven't been applied to Terraform state.
        
        Returns:
            List of ProtectionIntent objects pending TF state moves
        """
        return [
            intent
            for intent in self._intent.values()
            if not intent.applied_to_tf_state
        ]
    
    @property
    def intent_file(self) -> Path:
        """Get the path to the intent file."""
        return self._intent_file
    
    @property
    def intent_count(self) -> int:
        """Get the number of intents."""
        return len(self._intent)
    
    @property
    def history_count(self) -> int:
        """Get the number of history entries."""
        return len(self._history)
