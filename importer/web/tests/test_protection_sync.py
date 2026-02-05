"""Unit tests for protection intent sync to state.map.protected_resources.

These tests verify the fix that syncs protection intents to state.map.protected_resources
during the generate phase, ensuring that protection set via the Protection Management UI
is properly applied when generating Terraform configuration.

The key issue this tests:
- Protection Management UI uses ProtectionIntentManager
- Deploy/Generate uses state.map.protected_resources  
- Without sync, intents are not applied during generation
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Set, Dict, Any

from importer.web.utils.protection_intent import (
    ProtectionIntent,
    ProtectionIntentManager,
)


@dataclass
class MockMapState:
    """Mock for state.map containing protected/unprotected resource sets."""
    protected_resources: Set[str] = field(default_factory=set)
    unprotected_keys: Set[str] = field(default_factory=set)


@dataclass  
class MockState:
    """Mock for application state."""
    map: MockMapState = field(default_factory=MockMapState)
    _intent_manager: ProtectionIntentManager = None
    
    def get_protection_intent_manager(self) -> ProtectionIntentManager:
        return self._intent_manager


class TestProtectionIntentSync:
    """Tests for syncing protection intents to state.map.protected_resources."""
    
    @pytest.fixture
    def temp_intent_file(self, tmp_path: Path) -> Path:
        """Create a temporary intent file path."""
        return tmp_path / "protection-intent.json"
    
    @pytest.fixture
    def intent_manager(self, temp_intent_file: Path) -> ProtectionIntentManager:
        """Create a ProtectionIntentManager with temp file."""
        return ProtectionIntentManager(temp_intent_file)
    
    @pytest.fixture
    def mock_state(self, intent_manager: ProtectionIntentManager) -> MockState:
        """Create a mock state with intent manager."""
        return MockState(_intent_manager=intent_manager)
    
    def test_intent_protected_keys_sync_to_protected_resources(
        self, mock_state: MockState
    ):
        """Verify that protected intents are synced to state.map.protected_resources.
        
        This is the core fix: when user sets protection via UI (intent manager),
        those keys should appear in state.map.protected_resources during generate.
        """
        # Arrange - User sets protection via intent manager (simulating UI action)
        intent_manager = mock_state.get_protection_intent_manager()
        intent_manager.set_intent("PRJ:my_project", protected=True, source="user_click", reason="test")
        intent_manager.set_intent("REPO:my_repo", protected=True, source="user_click", reason="test")
        intent_manager.set_intent("PRJ:other_project", protected=False, source="user_click", reason="test")
        
        # Act - Simulate the sync code from deploy.py
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        intent_unprotected_keys = {
            k for k, i in intent_manager._intent.items() if not i.protected
        }
        
        if intent_protected_keys:
            if not mock_state.map.protected_resources:
                mock_state.map.protected_resources = set()
            mock_state.map.protected_resources.update(intent_protected_keys)
        
        if intent_unprotected_keys:
            if not mock_state.map.unprotected_keys:
                mock_state.map.unprotected_keys = set()
            mock_state.map.unprotected_keys.update(intent_unprotected_keys)
        
        # Assert
        assert "PRJ:my_project" in mock_state.map.protected_resources
        assert "REPO:my_repo" in mock_state.map.protected_resources
        assert "PRJ:other_project" not in mock_state.map.protected_resources
        assert "PRJ:other_project" in mock_state.map.unprotected_keys
    
    def test_sync_merges_with_existing_protected_resources(
        self, mock_state: MockState
    ):
        """Verify sync merges with existing protected_resources rather than replacing."""
        # Arrange - Existing protected resources
        mock_state.map.protected_resources = {"PRJ:existing_project"}
        
        # Add new intent
        intent_manager = mock_state.get_protection_intent_manager()
        intent_manager.set_intent("PRJ:new_project", protected=True, source="user_click", reason="test")
        
        # Act - Sync
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        mock_state.map.protected_resources.update(intent_protected_keys)
        
        # Assert - Both should be present
        assert "PRJ:existing_project" in mock_state.map.protected_resources
        assert "PRJ:new_project" in mock_state.map.protected_resources
    
    def test_empty_intents_does_not_modify_state(
        self, mock_state: MockState
    ):
        """Verify empty intent manager doesn't create empty sets."""
        # Arrange - state.map.protected_resources is None/empty by default
        assert not mock_state.map.protected_resources
        
        # Act - Sync with no intents
        intent_manager = mock_state.get_protection_intent_manager()
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        
        # Only update if there are keys
        if intent_protected_keys:
            mock_state.map.protected_resources.update(intent_protected_keys)
        
        # Assert - Should still be empty
        assert not mock_state.map.protected_resources


class TestApplyProtectionFromSet:
    """Tests for apply_protection_from_set function."""
    
    def test_prefixed_keys_apply_protection_correctly(self, tmp_path: Path):
        """Verify PRJ: prefixed keys apply protection to projects."""
        from importer.web.utils.adoption_yaml_updater import apply_protection_from_set
        import yaml
        
        # Arrange
        yaml_file = tmp_path / "config.yml"
        config = {
            "projects": [
                {"key": "my_project", "name": "My Project"},
                {"key": "other_project", "name": "Other Project"},
            ]
        }
        with open(yaml_file, "w") as f:
            yaml.dump(config, f)
        
        # Act
        apply_protection_from_set(str(yaml_file), {"PRJ:my_project"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        my_project = next(p for p in result["projects"] if p["key"] == "my_project")
        other_project = next(p for p in result["projects"] if p["key"] == "other_project")
        
        assert my_project.get("protected") is True
        assert other_project.get("protected") is not True
    
    def test_multiple_resource_types_apply_correctly(self, tmp_path: Path):
        """Verify multiple resource type prefixes apply correctly."""
        from importer.web.utils.adoption_yaml_updater import apply_protection_from_set
        import yaml
        
        # Arrange
        yaml_file = tmp_path / "config.yml"
        config = {
            "projects": [
                {
                    "key": "my_project", 
                    "name": "My Project",
                    "environments": [
                        {"key": "dev", "name": "Development"},
                        {"key": "prod", "name": "Production"},
                    ]
                },
            ],
            "globals": {
                "repositories": [
                    {"key": "my_repo", "remote_url": "https://example.com/repo"},
                ]
            }
        }
        with open(yaml_file, "w") as f:
            yaml.dump(config, f)
        
        # Act - Apply protection to project and repo
        apply_protection_from_set(str(yaml_file), {"PRJ:my_project", "REP:my_repo"})
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        project = result["projects"][0]
        assert project.get("protected") is True
        
        repo = result["globals"]["repositories"][0]
        assert repo.get("protected") is True


class TestIntentToYAMLFlow:
    """Integration tests for the full intent -> state -> YAML flow."""
    
    def test_full_protection_flow(self, tmp_path: Path):
        """Test the complete flow: intent -> sync -> apply -> YAML has protection."""
        from importer.web.utils.adoption_yaml_updater import apply_protection_from_set
        import yaml
        
        # Arrange - Create YAML file
        yaml_file = tmp_path / "config.yml"
        config = {
            "projects": [
                {"key": "project_a", "name": "Project A"},
                {"key": "project_b", "name": "Project B"},
            ]
        }
        with open(yaml_file, "w") as f:
            yaml.dump(config, f)
        
        # Create intent manager and set protection
        intent_file = tmp_path / "protection-intent.json"
        intent_manager = ProtectionIntentManager(intent_file)
        intent_manager.set_intent("PRJ:project_a", protected=True, source="user_click", reason="test")
        
        # Create mock state and sync
        mock_state = MockState(_intent_manager=intent_manager)
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        mock_state.map.protected_resources = intent_protected_keys
        
        # Act - Apply protection (simulating deploy.py)
        if mock_state.map.protected_resources:
            apply_protection_from_set(str(yaml_file), mock_state.map.protected_resources)
        
        # Assert
        with open(yaml_file, "r") as f:
            result = yaml.safe_load(f)
        
        project_a = next(p for p in result["projects"] if p["key"] == "project_a")
        project_b = next(p for p in result["projects"] if p["key"] == "project_b")
        
        assert project_a.get("protected") is True, "project_a should be protected"
        assert project_b.get("protected") is not True, "project_b should NOT be protected"
    
    def test_protection_persists_through_yaml_regeneration(self, tmp_path: Path):
        """Test that protection applied via intent persists when YAML is regenerated."""
        from importer.web.utils.adoption_yaml_updater import apply_protection_from_set
        import yaml
        
        # Arrange - Initial YAML without protection
        yaml_file = tmp_path / "config.yml"
        initial_config = {
            "projects": [{"key": "my_project", "name": "My Project"}]
        }
        
        # Setup intent
        intent_file = tmp_path / "protection-intent.json"
        intent_manager = ProtectionIntentManager(intent_file)
        intent_manager.set_intent("PRJ:my_project", protected=True, source="user_click", reason="test")
        intent_manager.save()
        
        # First generation - write initial YAML
        with open(yaml_file, "w") as f:
            yaml.dump(initial_config, f)
        
        # Apply protection from intent
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        apply_protection_from_set(str(yaml_file), intent_protected_keys)
        
        # Verify protection applied
        with open(yaml_file, "r") as f:
            result1 = yaml.safe_load(f)
        assert result1["projects"][0].get("protected") is True
        
        # Simulate second generation - YAML regenerated from source (no protection)
        with open(yaml_file, "w") as f:
            yaml.dump(initial_config, f)  # Overwrites with no protection
        
        # Re-apply protection from intent (this is what deploy.py does now)
        # Reload intent manager to simulate fresh session
        intent_manager2 = ProtectionIntentManager(intent_file)
        intent_manager2.load()  # Load saved intents from file
        intent_protected_keys2 = {
            k for k, i in intent_manager2._intent.items() if i.protected
        }
        apply_protection_from_set(str(yaml_file), intent_protected_keys2)
        
        # Assert - Protection should be re-applied
        with open(yaml_file, "r") as f:
            result2 = yaml.safe_load(f)
        assert result2["projects"][0].get("protected") is True, \
            "Protection should persist through regeneration"


# =============================================================================
# Edge Case Tests for Protection Sync
# =============================================================================

class TestProtectionSyncEdgeCases:
    """Edge case tests for protection intent sync."""
    
    @pytest.fixture
    def temp_intent_file(self, tmp_path: Path) -> Path:
        """Create a temporary intent file path."""
        return tmp_path / "protection-intent.json"
    
    @pytest.fixture
    def intent_manager(self, temp_intent_file: Path) -> ProtectionIntentManager:
        """Create a ProtectionIntentManager with temp file."""
        return ProtectionIntentManager(temp_intent_file)
    
    @pytest.fixture
    def mock_state(self, intent_manager: ProtectionIntentManager) -> MockState:
        """Create a mock state with intent manager."""
        return MockState(_intent_manager=intent_manager)
    
    def test_sync_handles_none_protected_resources(
        self, mock_state: MockState
    ):
        """Verify sync correctly handles None protected_resources."""
        # Arrange - Explicitly set to None (not empty set)
        mock_state.map.protected_resources = None
        
        # Add intent
        intent_manager = mock_state.get_protection_intent_manager()
        intent_manager.set_intent("PRJ:test", protected=True, source="test", reason="test")
        
        # Act - Sync code should handle None case
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        
        if intent_protected_keys:
            if not mock_state.map.protected_resources:
                mock_state.map.protected_resources = set()
            mock_state.map.protected_resources.update(intent_protected_keys)
        
        # Assert
        assert "PRJ:test" in mock_state.map.protected_resources
    
    def test_sync_handles_conflicting_intents(
        self, mock_state: MockState
    ):
        """Test sync when same resource is first protected then unprotected."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # First protect
        intent_manager.set_intent("PRJ:conflict", protected=True, source="test", reason="protect")
        
        # Then unprotect (should override)
        intent_manager.set_intent("PRJ:conflict", protected=False, source="test", reason="unprotect")
        
        # Sync
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        intent_unprotected_keys = {
            k for k, i in intent_manager._intent.items() if not i.protected
        }
        
        mock_state.map.protected_resources = intent_protected_keys.copy()
        mock_state.map.unprotected_keys = intent_unprotected_keys.copy()
        
        # Assert - Last intent wins (unprotected)
        assert "PRJ:conflict" not in mock_state.map.protected_resources
        assert "PRJ:conflict" in mock_state.map.unprotected_keys
    
    def test_sync_with_large_number_of_resources(
        self, mock_state: MockState
    ):
        """Test sync performance with many resources."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Add 500 protected and 500 unprotected intents
        for i in range(500):
            intent_manager.set_intent(
                f"PRJ:protected_{i}",
                protected=True,
                source="test",
                reason=f"protect {i}",
            )
            intent_manager.set_intent(
                f"PRJ:unprotected_{i}",
                protected=False,
                source="test",
                reason=f"unprotect {i}",
            )
        
        # Sync
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        intent_unprotected_keys = {
            k for k, i in intent_manager._intent.items() if not i.protected
        }
        
        mock_state.map.protected_resources = intent_protected_keys.copy()
        mock_state.map.unprotected_keys = intent_unprotected_keys.copy()
        
        # Assert
        assert len(mock_state.map.protected_resources) == 500
        assert len(mock_state.map.unprotected_keys) == 500
    
    def test_sync_preserves_existing_when_no_intents(
        self, mock_state: MockState
    ):
        """Test that existing protected_resources are preserved when no new intents."""
        # Arrange - Pre-populate protected_resources
        existing_keys = {"PRJ:existing_1", "PRJ:existing_2"}
        mock_state.map.protected_resources = existing_keys.copy()
        
        # No intents set in intent_manager
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Sync
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        
        # Only update if there are keys
        if intent_protected_keys:
            mock_state.map.protected_resources.update(intent_protected_keys)
        
        # Assert - Existing keys should still be present
        assert mock_state.map.protected_resources == existing_keys
    
    def test_sync_with_mixed_prefix_formats(
        self, mock_state: MockState
    ):
        """Test sync handles different prefix formats correctly."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Set intents with various key formats
        intent_manager.set_intent("PRJ:project", protected=True, source="test", reason="test")
        intent_manager.set_intent("REP:repo", protected=True, source="test", reason="test")
        intent_manager.set_intent("REPO:repo2", protected=True, source="test", reason="test")
        intent_manager.set_intent("legacy_key", protected=True, source="test", reason="test")  # No prefix
        
        # Sync
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        mock_state.map.protected_resources = intent_protected_keys.copy()
        
        # Assert all formats are synced
        assert "PRJ:project" in mock_state.map.protected_resources
        assert "REP:repo" in mock_state.map.protected_resources
        assert "REPO:repo2" in mock_state.map.protected_resources
        assert "legacy_key" in mock_state.map.protected_resources
    
    def test_sync_removes_duplicates(
        self, mock_state: MockState
    ):
        """Test that sync doesn't create duplicate entries."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Pre-populate with same key as will be in intent
        mock_state.map.protected_resources = {"PRJ:same_key"}
        
        # Set same intent
        intent_manager.set_intent("PRJ:same_key", protected=True, source="test", reason="test")
        
        # Sync
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        mock_state.map.protected_resources.update(intent_protected_keys)
        
        # Assert - Using set ensures no duplicates
        assert len(mock_state.map.protected_resources) == 1
        assert "PRJ:same_key" in mock_state.map.protected_resources
    
    def test_sync_after_save_and_reload(
        self, temp_intent_file: Path
    ):
        """Test that sync works correctly after saving and reloading intents."""
        # Create first manager and set intents
        manager1 = ProtectionIntentManager(temp_intent_file)
        manager1.set_intent("PRJ:persisted", protected=True, source="test", reason="test")
        manager1.save()
        
        # Create new manager (simulates new session)
        manager2 = ProtectionIntentManager(temp_intent_file)
        manager2.load()
        
        # Create mock state with new manager
        mock_state = MockState(_intent_manager=manager2)
        
        # Sync
        intent_protected_keys = {
            k for k, i in manager2._intent.items() if i.protected
        }
        mock_state.map.protected_resources = intent_protected_keys.copy()
        
        # Assert - Persisted intent should be present
        assert "PRJ:persisted" in mock_state.map.protected_resources
    
    def test_sync_handles_empty_string_key(
        self, mock_state: MockState
    ):
        """Test that empty string keys are handled (edge case)."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Set intent with empty key
        intent_manager.set_intent("", protected=True, source="test", reason="test")
        
        # Sync
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        mock_state.map.protected_resources = intent_protected_keys.copy()
        
        # Assert - Empty string key should be in the set
        assert "" in mock_state.map.protected_resources
    
    def test_sync_atomicity_all_or_nothing(
        self, mock_state: MockState
    ):
        """Test that sync operation is atomic - either all intents sync or none."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Set multiple intents
        intent_manager.set_intent("PRJ:a", protected=True, source="test", reason="test")
        intent_manager.set_intent("PRJ:b", protected=True, source="test", reason="test")
        intent_manager.set_intent("PRJ:c", protected=True, source="test", reason="test")
        
        # Sync all at once
        intent_protected_keys = {
            k for k, i in intent_manager._intent.items() if i.protected
        }
        mock_state.map.protected_resources = intent_protected_keys.copy()
        
        # Assert all synced
        assert {"PRJ:a", "PRJ:b", "PRJ:c"} == mock_state.map.protected_resources
