"""Tests for ProtectionIntentManager.

Tests the core functionality of the protection intent system that serves
as the single source of truth for user protection decisions.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from importer.web.utils.protection_intent import (
    ProtectionIntent,
    ProtectionIntentManager,
    HistoryEntry,
)


@pytest.fixture
def temp_intent_file(tmp_path: Path) -> Path:
    """Create a temporary intent file path."""
    return tmp_path / "protection-intent.json"


@pytest.fixture
def manager(temp_intent_file: Path) -> ProtectionIntentManager:
    """Create a ProtectionIntentManager with a temp file."""
    return ProtectionIntentManager(temp_intent_file)


class TestSetIntent:
    """Tests for set_intent() method."""
    
    def test_set_intent_creates_intent_with_correct_timestamps_and_flags(
        self, manager: ProtectionIntentManager
    ):
        """Criterion 12: set_intent() creates intent with correct timestamps and flags."""
        # Arrange
        key = "my_project"
        
        # Act
        intent = manager.set_intent(
            key=key,
            protected=False,
            source="user_click",
            reason="Unprotect for deletion",
            tf_state_at_decision="protected",
        )
        
        # Assert
        assert intent.protected is False
        assert intent.set_by == "user_click"
        assert intent.reason == "Unprotect for deletion"
        assert intent.tf_state_at_decision == "protected"
        
        # Flags should be False for new intent
        assert intent.applied_to_yaml is False
        assert intent.applied_to_tf_state is False
        
        # Timestamp should be valid ISO format
        assert intent.set_at is not None
        assert intent.set_at.endswith("Z")
        datetime.fromisoformat(intent.set_at.replace("Z", "+00:00"))
        
        # Should be retrievable
        retrieved = manager.get_intent(key)
        assert retrieved is not None
        assert retrieved.protected == intent.protected
    
    def test_set_intent_overwrites_existing_and_adds_to_history(
        self, manager: ProtectionIntentManager
    ):
        """Criterion 13: set_intent() overwrites existing intent and adds to history."""
        # Arrange
        key = "my_project"
        
        # Act - set first intent
        manager.set_intent(
            key=key,
            protected=True,
            source="initial_import",
            reason="Initial state",
        )
        
        # Act - overwrite with second intent
        manager.set_intent(
            key=key,
            protected=False,
            source="user_click",
            reason="Changed mind",
        )
        
        # Assert - only one intent for the key
        intent = manager.get_intent(key)
        assert intent is not None
        assert intent.protected is False
        assert intent.set_by == "user_click"
        assert intent.reason == "Changed mind"
        
        # History should have 2 entries
        assert manager.history_count == 2


class TestGetEffectiveProtection:
    """Tests for get_effective_protection() method."""
    
    def test_get_effective_protection_returns_intent_when_exists(
        self, manager: ProtectionIntentManager
    ):
        """Criterion 14: get_effective_protection() returns intent value when exists."""
        # Arrange
        key = "my_project"
        manager.set_intent(
            key=key,
            protected=False,
            source="user_click",
            reason="Unprotect",
        )
        
        # Act - YAML says protected, but intent says unprotected
        effective = manager.get_effective_protection(key, yaml_protected=True)
        
        # Assert - intent takes precedence
        assert effective is False
    
    def test_get_effective_protection_falls_back_to_yaml_when_no_intent(
        self, manager: ProtectionIntentManager
    ):
        """Criterion 15: get_effective_protection() falls back to yaml_protected when no intent."""
        # Arrange - no intent set
        key = "other_project"
        
        # Act
        effective_protected = manager.get_effective_protection(key, yaml_protected=True)
        effective_unprotected = manager.get_effective_protection(key, yaml_protected=False)
        
        # Assert - falls back to YAML value
        assert effective_protected is True
        assert effective_unprotected is False


class TestMarkAppliedToYaml:
    """Tests for mark_applied_to_yaml() method."""
    
    def test_mark_applied_to_yaml_sets_flag_and_preserves_other_fields(
        self, manager: ProtectionIntentManager
    ):
        """Criterion 16: mark_applied_to_yaml() sets flag and preserves other fields."""
        # Arrange
        key = "my_project"
        manager.set_intent(
            key=key,
            protected=False,
            source="user_click",
            reason="Unprotect",
            tf_state_at_decision="protected",
        )
        
        # Capture original values
        original_intent = manager.get_intent(key)
        original_protected = original_intent.protected
        original_reason = original_intent.reason
        original_tf_state = original_intent.tf_state_at_decision
        
        # Act
        manager.mark_applied_to_yaml({key})
        
        # Assert
        updated_intent = manager.get_intent(key)
        assert updated_intent.applied_to_yaml is True
        
        # Other fields preserved
        assert updated_intent.protected == original_protected
        assert updated_intent.reason == original_reason
        assert updated_intent.tf_state_at_decision == original_tf_state
        assert updated_intent.applied_to_tf_state is False  # Should not change


class TestMarkAppliedToTfState:
    """Tests for mark_applied_to_tf_state() method."""
    
    def test_mark_applied_to_tf_state_sets_flag_and_preserves_other_fields(
        self, manager: ProtectionIntentManager
    ):
        """Criterion 17: mark_applied_to_tf_state() sets flag and preserves other fields."""
        # Arrange
        key = "my_project"
        manager.set_intent(
            key=key,
            protected=False,
            source="user_click",
            reason="Unprotect",
        )
        manager.mark_applied_to_yaml({key})  # Mark YAML applied first
        
        # Capture original values
        original_intent = manager.get_intent(key)
        original_protected = original_intent.protected
        original_reason = original_intent.reason
        
        # Act
        manager.mark_applied_to_tf_state({key})
        
        # Assert
        updated_intent = manager.get_intent(key)
        assert updated_intent.applied_to_tf_state is True
        
        # Other fields preserved
        assert updated_intent.protected == original_protected
        assert updated_intent.reason == original_reason
        assert updated_intent.applied_to_yaml is True  # Should not change


class TestGetPendingYamlUpdates:
    """Tests for get_pending_yaml_updates() method."""
    
    def test_get_pending_yaml_updates_returns_only_unapplied(
        self, manager: ProtectionIntentManager
    ):
        """Criterion 18: get_pending_yaml_updates() returns only intents with applied_to_yaml=False."""
        # Arrange
        manager.set_intent("project_a", protected=False, source="user", reason="A")
        manager.set_intent("project_b", protected=True, source="user", reason="B")
        manager.set_intent("project_c", protected=False, source="user", reason="C")
        
        # Mark only project_b as applied
        manager.mark_applied_to_yaml({"project_b"})
        
        # Act
        pending = manager.get_pending_yaml_updates()
        
        # Assert
        assert len(pending) == 2
        assert "project_a" in pending
        assert "project_c" in pending
        assert "project_b" not in pending


class TestLoad:
    """Tests for load() method."""
    
    def test_load_handles_missing_file_gracefully(
        self, temp_intent_file: Path
    ):
        """Criterion 19: load() handles missing file gracefully (creates empty)."""
        # Arrange - ensure file doesn't exist
        assert not temp_intent_file.exists()
        
        manager = ProtectionIntentManager(temp_intent_file)
        
        # Act - should not raise
        manager.load()
        
        # Assert - empty state
        assert manager.intent_count == 0
        assert manager.history_count == 0
        
        # Should be able to use manager normally
        manager.set_intent("test", protected=True, source="test", reason="test")
        assert manager.intent_count == 1


class TestSaveLoadRoundtrip:
    """Tests for save() and load() roundtrip."""
    
    def test_save_and_load_roundtrip_preserves_all_data(
        self, temp_intent_file: Path
    ):
        """Criterion 20: save() and load() roundtrip preserves all data."""
        # Arrange - create manager and populate with data
        manager1 = ProtectionIntentManager(temp_intent_file)
        
        manager1.set_intent(
            key="project_a",
            protected=False,
            source="user_click",
            reason="Unprotect for deletion",
            tf_state_at_decision="protected",
            yaml_state_before=True,
        )
        manager1.set_intent(
            key="project_b",
            protected=True,
            source="import",
            reason="Initial protected state",
        )
        manager1.mark_applied_to_yaml({"project_a"})
        manager1.mark_applied_to_tf_state({"project_a"})
        
        # Act - save
        manager1.save()
        
        # Act - load in new manager
        manager2 = ProtectionIntentManager(temp_intent_file)
        manager2.load()
        
        # Assert - all data preserved
        assert manager2.intent_count == 2
        assert manager2.history_count == 2
        
        # Check project_a intent
        intent_a = manager2.get_intent("project_a")
        assert intent_a is not None
        assert intent_a.protected is False
        assert intent_a.set_by == "user_click"
        assert intent_a.reason == "Unprotect for deletion"
        assert intent_a.tf_state_at_decision == "protected"
        assert intent_a.applied_to_yaml is True
        assert intent_a.applied_to_tf_state is True
        
        # Check project_b intent
        intent_b = manager2.get_intent("project_b")
        assert intent_b is not None
        assert intent_b.protected is True
        assert intent_b.set_by == "import"
        assert intent_b.applied_to_yaml is False
        assert intent_b.applied_to_tf_state is False


class TestLoadCorruptedFile:
    """Tests for load() with corrupted files."""
    
    def test_load_raises_on_corrupted_json(self, temp_intent_file: Path):
        """load() raises ValueError on corrupted JSON."""
        # Arrange - write invalid JSON
        temp_intent_file.write_text("{ invalid json }", encoding="utf-8")
        
        manager = ProtectionIntentManager(temp_intent_file)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Corrupted intent file"):
            manager.load()


class TestHistoryEntry:
    """Tests for HistoryEntry dataclass."""
    
    def test_history_entry_roundtrip(self):
        """HistoryEntry serializes and deserializes correctly."""
        entry = HistoryEntry(
            resource_key="my_project",
            action="unprotect",
            timestamp="2026-02-02T10:00:00Z",
            source="user_click",
            tf_state_before="protected",
            yaml_state_before=True,
        )
        
        data = entry.to_dict()
        restored = HistoryEntry.from_dict(data)
        
        assert restored.resource_key == entry.resource_key
        assert restored.action == entry.action
        assert restored.timestamp == entry.timestamp
        assert restored.source == entry.source
        assert restored.tf_state_before == entry.tf_state_before
        assert restored.yaml_state_before == entry.yaml_state_before


class TestProtectionIntentDataclass:
    """Tests for ProtectionIntent dataclass."""
    
    def test_protection_intent_roundtrip(self):
        """ProtectionIntent serializes and deserializes correctly."""
        intent = ProtectionIntent(
            protected=False,
            set_at="2026-02-02T10:00:00Z",
            set_by="user_click",
            reason="Testing",
            applied_to_yaml=True,
            applied_to_tf_state=False,
            tf_state_at_decision="protected",
        )
        
        data = intent.to_dict()
        restored = ProtectionIntent.from_dict(data)
        
        assert restored.protected == intent.protected
        assert restored.set_at == intent.set_at
        assert restored.set_by == intent.set_by
        assert restored.reason == intent.reason
        assert restored.applied_to_yaml == intent.applied_to_yaml
        assert restored.applied_to_tf_state == intent.applied_to_tf_state
        assert restored.tf_state_at_decision == intent.tf_state_at_decision


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestIntentEdgeCases:
    """Edge case tests for ProtectionIntentManager."""
    
    def test_set_intent_with_very_long_reason(
        self, manager: ProtectionIntentManager
    ):
        """Test that very long reasons are handled correctly."""
        long_reason = "A" * 10000
        
        intent = manager.set_intent(
            key="test",
            protected=True,
            source="test",
            reason=long_reason,
        )
        
        assert intent.reason == long_reason
        
        # Should persist through save/load
        manager.save()
        
        new_manager = ProtectionIntentManager(manager._intent_file)
        new_manager.load()
        
        assert new_manager.get_intent("test").reason == long_reason
    
    def test_set_intent_with_special_characters_in_reason(
        self, manager: ProtectionIntentManager
    ):
        """Test that special characters in reason are handled."""
        special_reason = 'Test with "quotes" and\nnewlines\tand\ttabs'
        
        intent = manager.set_intent(
            key="test",
            protected=True,
            source="test",
            reason=special_reason,
        )
        
        assert intent.reason == special_reason
        
        # Should persist through JSON serialization
        manager.save()
        
        new_manager = ProtectionIntentManager(manager._intent_file)
        new_manager.load()
        
        assert new_manager.get_intent("test").reason == special_reason
    
    def test_set_intent_with_unicode_key(
        self, manager: ProtectionIntentManager
    ):
        """Test that unicode keys are handled correctly."""
        unicode_key = "项目_プロジェクト"
        
        manager.set_intent(
            key=unicode_key,
            protected=True,
            source="test",
            reason="Unicode test",
        )
        
        assert manager.get_intent(unicode_key) is not None
        
        # Should persist
        manager.save()
        
        new_manager = ProtectionIntentManager(manager._intent_file)
        new_manager.load()
        
        assert new_manager.get_intent(unicode_key) is not None
    
    def test_clear_all_intents(
        self, manager: ProtectionIntentManager
    ):
        """Test clearing all intents."""
        # Add several intents
        manager.set_intent("a", protected=True, source="test", reason="a")
        manager.set_intent("b", protected=False, source="test", reason="b")
        manager.set_intent("c", protected=True, source="test", reason="c")
        
        assert manager.intent_count == 3
        
        # Clear by resetting internal state
        manager._intent = {}
        manager.save()
        
        # Reload
        new_manager = ProtectionIntentManager(manager._intent_file)
        new_manager.load()
        
        assert new_manager.intent_count == 0
    
    def test_batch_mark_applied_to_yaml(
        self, manager: ProtectionIntentManager
    ):
        """Test batch marking multiple intents as applied."""
        # Add several intents
        keys = [f"project_{i}" for i in range(10)]
        for key in keys:
            manager.set_intent(key, protected=True, source="test", reason="test")
        
        # Mark all as applied in one call
        manager.mark_applied_to_yaml(set(keys))
        
        # All should be marked
        for key in keys:
            assert manager.get_intent(key).applied_to_yaml is True
    
    def test_get_pending_with_no_intents(
        self, manager: ProtectionIntentManager
    ):
        """Test get_pending_yaml_updates with no intents."""
        pending = manager.get_pending_yaml_updates()
        assert len(pending) == 0
    
    def test_get_pending_after_all_applied(
        self, manager: ProtectionIntentManager
    ):
        """Test get_pending_yaml_updates when all intents are applied."""
        manager.set_intent("a", protected=True, source="test", reason="test")
        manager.set_intent("b", protected=False, source="test", reason="test")
        
        manager.mark_applied_to_yaml({"a", "b"})
        
        pending = manager.get_pending_yaml_updates()
        assert len(pending) == 0
    
    def test_history_count_matches_actual_changes(
        self, manager: ProtectionIntentManager
    ):
        """Test that history_count accurately reflects all changes."""
        # Make 5 changes
        for i in range(5):
            manager.set_intent(f"key_{i}", protected=True, source="test", reason=f"change {i}")
        
        assert manager.history_count == 5
        
        # Make 3 more changes (including overwrites)
        manager.set_intent("key_0", protected=False, source="test", reason="overwrite")
        manager.set_intent("key_1", protected=False, source="test", reason="overwrite")
        manager.set_intent("new_key", protected=True, source="test", reason="new")
        
        assert manager.history_count == 8
    
    def test_intent_count_reflects_unique_keys(
        self, manager: ProtectionIntentManager
    ):
        """Test that intent_count only counts unique keys."""
        manager.set_intent("key_a", protected=True, source="test", reason="first")
        manager.set_intent("key_a", protected=False, source="test", reason="second")
        manager.set_intent("key_a", protected=True, source="test", reason="third")
        
        # Only 1 unique key even with 3 changes
        assert manager.intent_count == 1
    
    def test_effective_protection_with_none_yaml_protected(
        self, manager: ProtectionIntentManager
    ):
        """Test get_effective_protection when yaml_protected is None."""
        # When no intent and yaml_protected is None, should return False
        effective = manager.get_effective_protection("unknown", yaml_protected=None)
        assert effective is None or effective is False
    
    def test_multiple_resource_types_same_base_name(
        self, manager: ProtectionIntentManager
    ):
        """Test that different prefixes for same base name are treated separately."""
        manager.set_intent("PRJ:resource", protected=True, source="test", reason="project")
        manager.set_intent("REP:resource", protected=False, source="test", reason="repo")
        
        assert manager.get_intent("PRJ:resource").protected is True
        assert manager.get_intent("REP:resource").protected is False
        
        # They're different keys
        assert manager.intent_count == 2


class TestIntentConcurrency:
    """Tests for concurrent-like operations on intents."""
    
    def test_rapid_save_load_cycles(
        self, temp_intent_file: Path
    ):
        """Test rapid save/load cycles don't corrupt data."""
        for i in range(20):
            manager = ProtectionIntentManager(temp_intent_file)
            manager.load()
            manager.set_intent(f"key_{i % 5}", protected=(i % 2 == 0), source="test", reason=f"cycle {i}")
            manager.save()
        
        # Final state should be consistent
        final_manager = ProtectionIntentManager(temp_intent_file)
        final_manager.load()
        
        # Should have exactly 5 keys
        assert final_manager.intent_count == 5
        
        # All history entries should be preserved
        assert final_manager.history_count == 20
