"""Unit tests for protection edge cases.

These tests cover edge cases in the protection system:
- Key prefix handling (PRJ:, REP:, REPO:, case sensitivity)
- Protection toggle scenarios (protect → unprotect → protect)
- Error recovery scenarios (file deletion, corruption)

Reference: Protection Test Coverage Analysis Plan
"""

import json
import pytest
import yaml
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock
from datetime import datetime

from importer.web.utils.protection_intent import (
    ProtectionIntent,
    ProtectionIntentManager,
)
from importer.web.utils.adoption_yaml_updater import (
    apply_protection_from_set,
    apply_unprotection_from_set,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def intent_file(tmp_path: Path) -> Path:
    """Create a temporary intent file path."""
    return tmp_path / "protection-intent.json"


@pytest.fixture
def intent_manager(intent_file: Path) -> ProtectionIntentManager:
    """Create an intent manager with a temporary file."""
    manager = ProtectionIntentManager(intent_file)
    manager.load()
    return manager


@pytest.fixture
def yaml_config(tmp_path: Path) -> Path:
    """Create a YAML config file for testing."""
    config = {
        "projects": [
            {"key": "test_project", "name": "Test Project", "protected": True},
            {"key": "other_project", "name": "Other Project"},
        ],
        "globals": {
            "repositories": [
                {"key": "test_repo", "remote_url": "https://github.com/test/repo", "protected": True},
            ],
        },
    }
    file_path = tmp_path / "config.yml"
    with open(file_path, "w") as f:
        yaml.dump(config, f)
    return file_path


# =============================================================================
# Tests: Key Prefix Edge Cases
# =============================================================================

class TestKeyPrefixEdgeCases:
    """Tests for key prefix handling in protection system."""
    
    def test_prj_prefix_handling(self, intent_manager: ProtectionIntentManager):
        """Test PRJ: prefix is correctly handled."""
        # Act
        intent_manager.set_intent(
            "PRJ:my_project",
            protected=True,
            source="test",
            reason="Test PRJ prefix",
        )
        
        # Assert
        assert "PRJ:my_project" in intent_manager._intent
        intent = intent_manager._intent["PRJ:my_project"]
        assert intent.protected is True
    
    def test_rep_prefix_handling(self, intent_manager: ProtectionIntentManager):
        """Test REP: prefix is correctly handled."""
        # Act
        intent_manager.set_intent(
            "REP:my_repo",
            protected=True,
            source="test",
            reason="Test REP prefix",
            resource_type="REP",
        )
        
        # Assert
        assert "REP:my_repo" in intent_manager._intent
        intent = intent_manager._intent["REP:my_repo"]
        assert intent.resource_type == "REP"
    
    def test_repo_prefix_handling(self, intent_manager: ProtectionIntentManager):
        """Test REPO: prefix is correctly handled (alternative format)."""
        # Act
        intent_manager.set_intent(
            "REPO:my_repo",
            protected=True,
            source="test",
            reason="Test REPO prefix",
        )
        
        # Assert
        assert "REPO:my_repo" in intent_manager._intent
    
    def test_unprefixed_key_handling(self, intent_manager: ProtectionIntentManager):
        """Test unprefixed keys are handled (legacy format)."""
        # Act
        intent_manager.set_intent(
            "legacy_key_no_prefix",
            protected=True,
            source="test",
            reason="Test legacy key",
        )
        
        # Assert
        assert "legacy_key_no_prefix" in intent_manager._intent
    
    def test_empty_key_handling(self, intent_manager: ProtectionIntentManager):
        """Test that empty keys are still accepted (edge case)."""
        # Note: This tests current behavior - may want to add validation later
        intent_manager.set_intent(
            "",
            protected=True,
            source="test",
            reason="Test empty key",
        )
        
        # Assert - empty key should be accepted (may want to change this behavior)
        assert "" in intent_manager._intent
    
    def test_key_with_special_characters(self, intent_manager: ProtectionIntentManager):
        """Test keys with special characters like dashes and underscores."""
        special_keys = [
            "PRJ:project-with-dashes",
            "REP:repo_with_underscores",
            "PRJ:project.with.dots",
            "REP:repo/with/slashes",  # May occur in repo URLs
        ]
        
        for key in special_keys:
            intent_manager.set_intent(
                key,
                protected=True,
                source="test",
                reason=f"Test special key: {key}",
            )
        
        # Assert all keys were stored
        for key in special_keys:
            assert key in intent_manager._intent
    
    def test_very_long_key(self, intent_manager: ProtectionIntentManager):
        """Test handling of very long keys."""
        long_key = "PRJ:" + "x" * 500
        
        intent_manager.set_intent(
            long_key,
            protected=True,
            source="test",
            reason="Test very long key",
        )
        
        assert long_key in intent_manager._intent
    
    def test_unicode_key(self, intent_manager: ProtectionIntentManager):
        """Test handling of unicode characters in keys."""
        unicode_key = "PRJ:项目_プロジェクト_projekt"
        
        intent_manager.set_intent(
            unicode_key,
            protected=True,
            source="test",
            reason="Test unicode key",
        )
        
        assert unicode_key in intent_manager._intent
        
        # Test save/load roundtrip with unicode
        intent_manager.save()
        
        new_manager = ProtectionIntentManager(intent_manager._intent_file)
        new_manager.load()
        
        assert unicode_key in new_manager._intent
    
    def test_case_sensitivity_of_prefixes(self, intent_manager: ProtectionIntentManager):
        """Test that key prefixes are case-sensitive."""
        # These should be treated as different keys
        intent_manager.set_intent("PRJ:test", protected=True, source="test", reason="uppercase")
        intent_manager.set_intent("prj:test", protected=False, source="test", reason="lowercase")
        intent_manager.set_intent("Prj:test", protected=True, source="test", reason="mixed")
        
        assert "PRJ:test" in intent_manager._intent
        assert "prj:test" in intent_manager._intent
        assert "Prj:test" in intent_manager._intent
        
        # They should have different values
        assert intent_manager._intent["PRJ:test"].protected is True
        assert intent_manager._intent["prj:test"].protected is False
        assert intent_manager._intent["Prj:test"].protected is True


# =============================================================================
# Tests: Protection Toggle Scenarios
# =============================================================================

class TestProtectionToggle:
    """Tests for protection toggle scenarios."""
    
    def test_protect_unprotect_protect_sequence(
        self, intent_manager: ProtectionIntentManager
    ):
        """Test rapid protect → unprotect → protect sequence."""
        key = "PRJ:toggled_project"
        
        # Protect
        intent_manager.set_intent(key, protected=True, source="test", reason="protect")
        assert intent_manager._intent[key].protected is True
        
        # Unprotect
        intent_manager.set_intent(key, protected=False, source="test", reason="unprotect")
        assert intent_manager._intent[key].protected is False
        
        # Protect again
        intent_manager.set_intent(key, protected=True, source="test", reason="reprotect")
        assert intent_manager._intent[key].protected is True
        
        # History should have 3 entries for this key
        key_history = [e for e in intent_manager._history if e.resource_key == key]
        assert len(key_history) == 3
    
    def test_rapid_toggle_preserves_last_intent(
        self, intent_manager: ProtectionIntentManager
    ):
        """Test that rapid toggling preserves only the last intent."""
        key = "PRJ:rapid_toggle"
        
        # Toggle many times
        for i in range(10):
            intent_manager.set_intent(
                key,
                protected=(i % 2 == 0),  # Alternates True/False
                source="test",
                reason=f"toggle {i}",
            )
        
        # Final state should be unprotected (i=9 is odd, so protected=False)
        assert intent_manager._intent[key].protected is False
    
    def test_toggle_with_yaml_application(
        self, intent_manager: ProtectionIntentManager, yaml_config: Path
    ):
        """Test toggling and applying to YAML."""
        key = "PRJ:test_project"
        
        # Set unprotected intent
        intent_manager.set_intent(key, protected=False, source="test", reason="unprotect")
        
        # Apply to YAML
        apply_unprotection_from_set(str(yaml_config), {key})
        
        # Verify YAML updated
        with open(yaml_config, "r") as f:
            config = yaml.safe_load(f)
        project = next(p for p in config["projects"] if p["key"] == "test_project")
        assert "protected" not in project
        
        # Now toggle back to protected
        intent_manager.set_intent(key, protected=True, source="test", reason="reprotect")
        apply_protection_from_set(str(yaml_config), {key})
        
        # Verify YAML updated
        with open(yaml_config, "r") as f:
            config = yaml.safe_load(f)
        project = next(p for p in config["projects"] if p["key"] == "test_project")
        assert project.get("protected") is True
    
    def test_toggle_preserves_history_order(
        self, intent_manager: ProtectionIntentManager
    ):
        """Test that history entries are in chronological order after toggles."""
        key = "PRJ:history_test"
        
        intent_manager.set_intent(key, protected=True, source="test", reason="1")
        intent_manager.set_intent(key, protected=False, source="test", reason="2")
        intent_manager.set_intent(key, protected=True, source="test", reason="3")
        
        key_history = [e for e in intent_manager._history if e.resource_key == key]
        
        # Verify order by checking actions
        assert key_history[0].action == "protect"
        assert key_history[1].action == "unprotect"
        assert key_history[2].action == "protect"
        
        # Verify timestamps are increasing
        timestamps = [e.timestamp for e in key_history]
        assert timestamps == sorted(timestamps)
    
    def test_toggle_multiple_resources_independently(
        self, intent_manager: ProtectionIntentManager
    ):
        """Test toggling multiple resources doesn't affect each other."""
        intent_manager.set_intent("PRJ:a", protected=True, source="test", reason="a")
        intent_manager.set_intent("PRJ:b", protected=False, source="test", reason="b")
        
        # Toggle only 'a'
        intent_manager.set_intent("PRJ:a", protected=False, source="test", reason="a toggle")
        
        # 'b' should be unchanged
        assert intent_manager._intent["PRJ:a"].protected is False
        assert intent_manager._intent["PRJ:b"].protected is False
        
        # Only 'a' should have 2 history entries
        a_history = [e for e in intent_manager._history if e.resource_key == "PRJ:a"]
        b_history = [e for e in intent_manager._history if e.resource_key == "PRJ:b"]
        assert len(a_history) == 2
        assert len(b_history) == 1


# =============================================================================
# Tests: Error Recovery Scenarios
# =============================================================================

class TestErrorRecovery:
    """Tests for error recovery scenarios."""
    
    def test_intent_file_deleted_during_workflow(
        self, intent_manager: ProtectionIntentManager, intent_file: Path
    ):
        """Test recovery when intent file is deleted mid-workflow."""
        # Set some intents and save
        intent_manager.set_intent("PRJ:test", protected=True, source="test", reason="test")
        intent_manager.save()
        
        # Delete the file (simulates corruption/deletion)
        intent_file.unlink()
        
        # Create new manager - should start fresh without error
        new_manager = ProtectionIntentManager(intent_file)
        new_manager.load()  # Should not raise
        
        # Should be empty
        assert len(new_manager._intent) == 0
    
    def test_intent_file_corrupted_json(self, intent_file: Path):
        """Test handling of corrupted JSON in intent file."""
        # Write corrupted JSON
        intent_file.write_text("{ invalid json }")
        
        manager = ProtectionIntentManager(intent_file)
        
        # Should raise ValueError for corrupted JSON
        with pytest.raises(ValueError, match="Corrupted intent file"):
            manager.load()
    
    def test_intent_file_partial_json(self, intent_file: Path):
        """Test handling of partially written JSON."""
        # Write partial JSON (simulates interrupted write)
        intent_file.write_text('{"intent": {"PRJ:test": {"protected": true, "set_at":')
        
        manager = ProtectionIntentManager(intent_file)
        
        with pytest.raises(ValueError, match="Corrupted intent file"):
            manager.load()
    
    def test_yaml_file_missing_during_protection_apply(self, tmp_path: Path):
        """Test handling when YAML file doesn't exist."""
        missing_file = tmp_path / "nonexistent.yml"
        
        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            apply_unprotection_from_set(str(missing_file), {"PRJ:test"})
    
    def test_yaml_file_empty_during_protection_apply(self, tmp_path: Path):
        """Test handling of empty YAML file."""
        empty_file = tmp_path / "empty.yml"
        empty_file.write_text("")
        
        # Should not raise, return file path unchanged
        result = apply_unprotection_from_set(str(empty_file), {"PRJ:test"})
        assert result == str(empty_file)
    
    def test_yaml_file_invalid_structure(self, tmp_path: Path):
        """Test handling of YAML with invalid structure.
        
        When YAML contains a string instead of a dict, the function will raise
        an AttributeError when trying to access .get() on a string.
        """
        invalid_file = tmp_path / "invalid.yml"
        invalid_file.write_text("just a string, not a dict")
        
        # Current behavior raises AttributeError - documents actual behavior
        with pytest.raises(AttributeError):
            apply_unprotection_from_set(str(invalid_file), {"PRJ:test"})
    
    def test_intent_manager_save_failure_recovery(
        self, intent_manager: ProtectionIntentManager, tmp_path: Path
    ):
        """Test recovery when save fails due to permissions."""
        # Set intents in memory
        intent_manager.set_intent("PRJ:test", protected=True, source="test", reason="test")
        
        # Try to save to a read-only directory (simulates permission error)
        # Note: This test may not work on all systems
        with patch.object(Path, 'write_text', side_effect=PermissionError("Read-only")):
            with pytest.raises(PermissionError):
                intent_manager.save()
        
        # In-memory state should still be intact
        assert "PRJ:test" in intent_manager._intent
    
    def test_recovery_after_multiple_failures(
        self, intent_file: Path
    ):
        """Test that system recovers after multiple failures."""
        # First: Corrupted file
        intent_file.write_text("corrupted")
        manager1 = ProtectionIntentManager(intent_file)
        with pytest.raises(ValueError):
            manager1.load()
        
        # Second: Fix the file
        intent_file.write_text('{"intent": {}, "history": []}')
        manager2 = ProtectionIntentManager(intent_file)
        manager2.load()  # Should succeed
        
        # Third: Add data and save
        manager2.set_intent("PRJ:recovered", protected=True, source="test", reason="recovery")
        manager2.save()
        
        # Fourth: Load in new manager
        manager3 = ProtectionIntentManager(intent_file)
        manager3.load()
        
        assert "PRJ:recovered" in manager3._intent
    
    def test_intent_with_missing_required_fields(self, intent_file: Path):
        """Test loading intent file with missing required fields."""
        # Write JSON with missing fields
        data = {
            "intent": {
                "PRJ:test": {
                    "protected": True,
                    # Missing: set_at, set_by, reason
                }
            },
            "history": [],
        }
        intent_file.write_text(json.dumps(data))
        
        manager = ProtectionIntentManager(intent_file)
        manager.load()  # Should handle missing fields gracefully
        
        # Should still load with empty strings for missing fields
        assert "PRJ:test" in manager._intent
        assert manager._intent["PRJ:test"].protected is True
        assert manager._intent["PRJ:test"].set_at == ""


# =============================================================================
# Tests: Concurrent Modification Scenarios (Simulated)
# =============================================================================

class TestConcurrentModification:
    """Tests for concurrent modification scenarios (simulated)."""
    
    def test_multiple_intents_set_rapidly(
        self, intent_manager: ProtectionIntentManager
    ):
        """Test setting many intents rapidly."""
        # Set 100 intents rapidly
        for i in range(100):
            intent_manager.set_intent(
                f"PRJ:project_{i}",
                protected=(i % 2 == 0),
                source="test",
                reason=f"rapid {i}",
            )
        
        # All should be recorded
        assert len(intent_manager._intent) == 100
        
        # Verify pattern
        for i in range(100):
            key = f"PRJ:project_{i}"
            expected_protected = (i % 2 == 0)
            assert intent_manager._intent[key].protected == expected_protected
    
    def test_save_load_cycle_with_many_intents(
        self, intent_manager: ProtectionIntentManager
    ):
        """Test save/load cycle preserves all data."""
        # Set many intents
        for i in range(50):
            intent_manager.set_intent(
                f"PRJ:project_{i}",
                protected=True,
                source="test",
                reason=f"test {i}",
            )
        
        # Save
        intent_manager.save()
        
        # Load in new manager
        new_manager = ProtectionIntentManager(intent_manager._intent_file)
        new_manager.load()
        
        # Verify all data preserved
        assert len(new_manager._intent) == 50
        assert len(new_manager._history) == 50
    
    def test_interleaved_operations(
        self, intent_manager: ProtectionIntentManager
    ):
        """Test interleaved set, save, and mark operations."""
        intent_manager.set_intent("PRJ:a", protected=True, source="test", reason="a")
        intent_manager.save()
        
        intent_manager.set_intent("PRJ:b", protected=False, source="test", reason="b")
        intent_manager.mark_applied_to_yaml({"PRJ:a"})
        
        intent_manager.set_intent("PRJ:c", protected=True, source="test", reason="c")
        intent_manager.save()
        
        # Load fresh
        new_manager = ProtectionIntentManager(intent_manager._intent_file)
        new_manager.load()
        
        assert new_manager._intent["PRJ:a"].applied_to_yaml is True
        assert new_manager._intent["PRJ:b"].applied_to_yaml is False
        assert new_manager._intent["PRJ:c"].applied_to_yaml is False
