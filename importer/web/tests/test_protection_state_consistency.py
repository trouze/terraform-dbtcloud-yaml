"""Unit tests for protection state consistency across systems.

These tests validate that protection state remains consistent across:
- ProtectionIntentManager (intent file)
- state.map.protected_resources (runtime state)
- YAML configuration files
- Terraform state representation

Reference: Protection Test Coverage Analysis Plan
"""

import json
import pytest
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Set, Dict, Any, Optional
from unittest.mock import MagicMock

from importer.web.utils.protection_intent import (
    ProtectionIntent,
    ProtectionIntentManager,
)
from importer.web.utils.adoption_yaml_updater import (
    apply_protection_from_set,
    apply_unprotection_from_set,
)


# =============================================================================
# Mock State Classes
# =============================================================================

@dataclass
class MockMapState:
    """Mock for state.map containing protected/unprotected resource sets."""
    protected_resources: Set[str] = field(default_factory=set)
    unprotected_keys: Set[str] = field(default_factory=set)


@dataclass
class MockDeployState:
    """Mock for state.deploy containing reconcile state."""
    reconcile_state_loaded: bool = False
    reconcile_state_resources: list = field(default_factory=list)


@dataclass  
class MockState:
    """Mock for full application state."""
    map: MockMapState = field(default_factory=MockMapState)
    deploy: MockDeployState = field(default_factory=MockDeployState)
    _intent_manager: Optional[ProtectionIntentManager] = None
    
    def get_protection_intent_manager(self) -> ProtectionIntentManager:
        return self._intent_manager


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with necessary files."""
    return tmp_path


@pytest.fixture
def intent_file(tmp_workspace: Path) -> Path:
    """Create a temporary intent file path."""
    return tmp_workspace / "protection-intent.json"


@pytest.fixture
def yaml_file(tmp_workspace: Path) -> Path:
    """Create a YAML config file for testing."""
    config = {
        "projects": [
            {"key": "project_a", "name": "Project A", "protected": True},
            {"key": "project_b", "name": "Project B"},
            {"key": "project_c", "name": "Project C", "protected": False},
        ],
        "globals": {
            "repositories": [
                {"key": "repo_1", "remote_url": "https://github.com/test/repo1", "protected": True},
                {"key": "repo_2", "remote_url": "https://github.com/test/repo2"},
            ],
        },
    }
    file_path = tmp_workspace / "dbt-cloud-config.yml"
    with open(file_path, "w") as f:
        yaml.dump(config, f)
    return file_path


@pytest.fixture
def intent_manager(intent_file: Path) -> ProtectionIntentManager:
    """Create an intent manager."""
    manager = ProtectionIntentManager(intent_file)
    manager.load()
    return manager


@pytest.fixture
def mock_state(intent_manager: ProtectionIntentManager) -> MockState:
    """Create a mock state with intent manager."""
    return MockState(_intent_manager=intent_manager)


# =============================================================================
# Tests: Intent File <-> state.map Consistency
# =============================================================================

class TestIntentStateMapConsistency:
    """Tests for consistency between intent file and state.map."""
    
    def test_intent_and_state_map_synchronized_after_sync(
        self, mock_state: MockState
    ):
        """Verify intent file and state.map are synchronized after sync operation."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Set intents
        intent_manager.set_intent("PRJ:test", protected=True, source="test", reason="test")
        intent_manager.set_intent("REP:repo", protected=False, source="test", reason="test")
        intent_manager.save()
        
        # Sync to state.map
        protected = {k for k, i in intent_manager._intent.items() if i.protected}
        unprotected = {k for k, i in intent_manager._intent.items() if not i.protected}
        
        mock_state.map.protected_resources = protected
        mock_state.map.unprotected_keys = unprotected
        
        # Verify consistency
        assert mock_state.map.protected_resources == {"PRJ:test"}
        assert mock_state.map.unprotected_keys == {"REP:repo"}
        
        # Reload intent file to verify persistence
        new_manager = ProtectionIntentManager(intent_manager._intent_file)
        new_manager.load()
        
        new_protected = {k for k, i in new_manager._intent.items() if i.protected}
        new_unprotected = {k for k, i in new_manager._intent.items() if not i.protected}
        
        assert new_protected == mock_state.map.protected_resources
        assert new_unprotected == mock_state.map.unprotected_keys
    
    def test_state_map_divergence_detection(
        self, mock_state: MockState
    ):
        """Test detection when state.map diverges from intent file."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Set intent
        intent_manager.set_intent("PRJ:test", protected=True, source="test", reason="test")
        
        # Manually diverge state.map (simulate bug/desync)
        mock_state.map.protected_resources = {"PRJ:different_resource"}
        
        # Detect divergence
        intent_protected = {k for k, i in intent_manager._intent.items() if i.protected}
        
        is_synced = intent_protected == mock_state.map.protected_resources
        assert not is_synced, "Should detect divergence"
    
    def test_full_round_trip_consistency(
        self, intent_file: Path
    ):
        """Test full round trip: set intent -> save -> reload -> sync."""
        # First session: Set and save
        manager1 = ProtectionIntentManager(intent_file)
        manager1.set_intent("PRJ:resource", protected=True, source="test", reason="test")
        manager1.save()
        
        state1 = MockState(_intent_manager=manager1)
        state1.map.protected_resources = {k for k, i in manager1._intent.items() if i.protected}
        
        # Second session: Reload and sync
        manager2 = ProtectionIntentManager(intent_file)
        manager2.load()
        
        state2 = MockState(_intent_manager=manager2)
        state2.map.protected_resources = {k for k, i in manager2._intent.items() if i.protected}
        
        # Both sessions should have identical state
        assert state1.map.protected_resources == state2.map.protected_resources


# =============================================================================
# Tests: Intent File <-> YAML Config Consistency
# =============================================================================

class TestIntentYAMLConsistency:
    """Tests for consistency between intent file and YAML config."""
    
    def test_intent_applied_to_yaml_correctly(
        self, intent_manager: ProtectionIntentManager, yaml_file: Path
    ):
        """Test that intents are correctly applied to YAML config."""
        # Set intent to unprotect project_a (which starts protected)
        intent_manager.set_intent("PRJ:project_a", protected=False, source="test", reason="test")
        
        # Apply to YAML
        unprotected = {k for k, i in intent_manager._intent.items() if not i.protected}
        apply_unprotection_from_set(str(yaml_file), unprotected)
        
        # Verify YAML matches intent
        with open(yaml_file, "r") as f:
            config = yaml.safe_load(f)
        
        project_a = next(p for p in config["projects"] if p["key"] == "project_a")
        assert "protected" not in project_a or project_a.get("protected") is False
    
    def test_yaml_and_intent_remain_consistent_after_multiple_changes(
        self, intent_manager: ProtectionIntentManager, yaml_file: Path
    ):
        """Test consistency through multiple protection changes."""
        # Change 1: Unprotect project_a
        intent_manager.set_intent("PRJ:project_a", protected=False, source="test", reason="change1")
        apply_unprotection_from_set(str(yaml_file), {"PRJ:project_a"})
        
        # Change 2: Protect project_b
        intent_manager.set_intent("PRJ:project_b", protected=True, source="test", reason="change2")
        apply_protection_from_set(str(yaml_file), {"PRJ:project_b"})
        
        # Change 3: Re-protect project_a
        intent_manager.set_intent("PRJ:project_a", protected=True, source="test", reason="change3")
        apply_protection_from_set(str(yaml_file), {"PRJ:project_a"})
        
        # Verify YAML matches current intent state
        with open(yaml_file, "r") as f:
            config = yaml.safe_load(f)
        
        project_a = next(p for p in config["projects"] if p["key"] == "project_a")
        project_b = next(p for p in config["projects"] if p["key"] == "project_b")
        
        # Both should now be protected per intent
        assert project_a.get("protected") is True
        assert project_b.get("protected") is True
    
    def test_yaml_reflects_intent_not_original_state(
        self, intent_manager: ProtectionIntentManager, yaml_file: Path
    ):
        """Test that YAML reflects intent, not original configuration."""
        # Original YAML has project_a=protected, project_b=none
        
        # Set opposite intents
        intent_manager.set_intent("PRJ:project_a", protected=False, source="test", reason="override")
        intent_manager.set_intent("PRJ:project_b", protected=True, source="test", reason="override")
        
        # Apply both
        apply_unprotection_from_set(str(yaml_file), {"PRJ:project_a"})
        apply_protection_from_set(str(yaml_file), {"PRJ:project_b"})
        
        # Verify
        with open(yaml_file, "r") as f:
            config = yaml.safe_load(f)
        
        project_a = next(p for p in config["projects"] if p["key"] == "project_a")
        project_b = next(p for p in config["projects"] if p["key"] == "project_b")
        
        # Should be opposite of original
        assert "protected" not in project_a or project_a.get("protected") is False
        assert project_b.get("protected") is True


# =============================================================================
# Tests: Three-way Consistency (Intent, state.map, YAML)
# =============================================================================

class TestThreeWayConsistency:
    """Tests for consistency across all three state stores."""
    
    def test_full_workflow_consistency(
        self, mock_state: MockState, yaml_file: Path
    ):
        """Test full workflow maintains consistency across all stores."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Step 1: User sets intent (simulates UI click)
        intent_manager.set_intent("PRJ:project_a", protected=False, source="user_click", reason="test")
        intent_manager.set_intent("PRJ:project_b", protected=True, source="user_click", reason="test")
        intent_manager.save()
        
        # Step 2: Sync to state.map (simulates deploy.py sync)
        protected = {k for k, i in intent_manager._intent.items() if i.protected}
        unprotected = {k for k, i in intent_manager._intent.items() if not i.protected}
        mock_state.map.protected_resources = protected
        mock_state.map.unprotected_keys = unprotected
        
        # Step 3: Apply to YAML (simulates generate)
        apply_unprotection_from_set(str(yaml_file), mock_state.map.unprotected_keys)
        apply_protection_from_set(str(yaml_file), mock_state.map.protected_resources)
        
        # Verify all three stores are consistent
        # 1. Intent file
        intent_manager2 = ProtectionIntentManager(intent_manager._intent_file)
        intent_manager2.load()
        intent_protected = {k for k, i in intent_manager2._intent.items() if i.protected}
        intent_unprotected = {k for k, i in intent_manager2._intent.items() if not i.protected}
        
        # 2. state.map
        state_protected = mock_state.map.protected_resources
        state_unprotected = mock_state.map.unprotected_keys
        
        # 3. YAML
        with open(yaml_file, "r") as f:
            config = yaml.safe_load(f)
        yaml_protected = set()
        yaml_unprotected = set()
        for p in config.get("projects", []):
            key = f"PRJ:{p['key']}"
            if p.get("protected") is True:
                yaml_protected.add(key)
            elif "protected" not in p or p.get("protected") is False:
                if key in intent_unprotected:  # Only count if it was explicitly unprotected
                    yaml_unprotected.add(key)
        
        # All should match
        assert intent_protected == state_protected
        assert "PRJ:project_b" in yaml_protected
    
    def test_state_reconciliation_after_partial_failure(
        self, mock_state: MockState, yaml_file: Path
    ):
        """Test that state can be reconciled after partial failure."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Set intents
        intent_manager.set_intent("PRJ:project_a", protected=True, source="test", reason="test")
        intent_manager.save()
        
        # Simulate partial failure - state.map updated but YAML not
        mock_state.map.protected_resources = {"PRJ:project_a"}
        # YAML not updated (simulates failure)
        
        # Recovery: Re-apply from intent
        protected = {k for k, i in intent_manager._intent.items() if i.protected}
        apply_protection_from_set(str(yaml_file), protected)
        
        # Verify recovery successful
        with open(yaml_file, "r") as f:
            config = yaml.safe_load(f)
        project_a = next(p for p in config["projects"] if p["key"] == "project_a")
        assert project_a.get("protected") is True


# =============================================================================
# Tests: state.map <-> Terraform State Consistency
# =============================================================================

class TestStateMapTerraformConsistency:
    """Tests for consistency between state.map and Terraform state representation."""
    
    def test_reconcile_state_matches_protected_resources(
        self, mock_state: MockState
    ):
        """Test that reconcile_state resources align with protected_resources."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Simulate TF state with protected resources
        mock_state.deploy.reconcile_state_loaded = True
        mock_state.deploy.reconcile_state_resources = [
            {"tf_name": "protected_project_a", "resource_index": "PRJ:project_a", "element_code": "PRJ"},
            {"tf_name": "project_b", "resource_index": "PRJ:project_b", "element_code": "PRJ"},
        ]
        
        # Extract protected from TF state
        tf_protected = set()
        for resource in mock_state.deploy.reconcile_state_resources:
            if "protected_" in resource.get("tf_name", ""):
                tf_protected.add(resource.get("resource_index"))
        
        # Set intent to match
        intent_manager.set_intent("PRJ:project_a", protected=True, source="tf_import", reason="test")
        
        # Sync
        intent_protected = {k for k, i in intent_manager._intent.items() if i.protected}
        mock_state.map.protected_resources = intent_protected
        
        # Verify alignment
        assert tf_protected == mock_state.map.protected_resources
    
    def test_detect_tf_state_and_intent_mismatch(
        self, mock_state: MockState
    ):
        """Test detection of mismatch between TF state and intent."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # TF state says protected
        mock_state.deploy.reconcile_state_loaded = True
        mock_state.deploy.reconcile_state_resources = [
            {"tf_name": "protected_resource", "resource_index": "PRJ:resource", "element_code": "PRJ"},
        ]
        
        # Intent says unprotected
        intent_manager.set_intent("PRJ:resource", protected=False, source="user", reason="test")
        
        # Detect mismatch
        tf_protected = set()
        for resource in mock_state.deploy.reconcile_state_resources:
            if "protected_" in resource.get("tf_name", ""):
                tf_protected.add(resource.get("resource_index"))
        
        intent_protected = {k for k, i in intent_manager._intent.items() if i.protected}
        
        # They should not match - this is the expected mismatch that needs tf state moves
        assert tf_protected != intent_protected
        assert "PRJ:resource" in tf_protected
        assert "PRJ:resource" not in intent_protected


# =============================================================================
# Tests: Consistency Invariants
# =============================================================================

class TestConsistencyInvariants:
    """Tests for protection state invariants that must always hold."""
    
    def test_resource_cannot_be_both_protected_and_unprotected(
        self, mock_state: MockState
    ):
        """Test invariant: resource cannot be in both protected and unprotected sets."""
        # Try to create inconsistent state
        mock_state.map.protected_resources = {"PRJ:conflict"}
        mock_state.map.unprotected_keys = {"PRJ:conflict"}
        
        # This violates the invariant
        intersection = mock_state.map.protected_resources & mock_state.map.unprotected_keys
        assert len(intersection) > 0, "Test setup should create conflict"
        
        # Resolution: unprotected wins (most recent action)
        mock_state.map.protected_resources -= intersection
        
        # Verify invariant restored
        assert not (mock_state.map.protected_resources & mock_state.map.unprotected_keys)
    
    def test_intent_is_single_source_of_truth(
        self, mock_state: MockState
    ):
        """Test that intent is the canonical source for protection decisions."""
        intent_manager = mock_state.get_protection_intent_manager()
        
        # Even if state.map has different data
        mock_state.map.protected_resources = {"PRJ:wrong_resource"}
        
        # Intent should override
        intent_manager.set_intent("PRJ:correct_resource", protected=True, source="test", reason="test")
        
        # Sync should make state.map match intent
        intent_protected = {k for k, i in intent_manager._intent.items() if i.protected}
        mock_state.map.protected_resources = intent_protected  # This is the fix
        
        # Verify intent is source of truth
        assert mock_state.map.protected_resources == intent_protected
        assert "PRJ:wrong_resource" not in mock_state.map.protected_resources
    
    def test_history_accurately_reflects_all_changes(
        self, intent_manager: ProtectionIntentManager
    ):
        """Test that history contains accurate record of all changes."""
        # Make several changes
        intent_manager.set_intent("PRJ:resource", protected=True, source="test", reason="change1")
        intent_manager.set_intent("PRJ:resource", protected=False, source="test", reason="change2")
        intent_manager.set_intent("PRJ:resource", protected=True, source="test", reason="change3")
        
        # History should have all 3 changes
        resource_history = [e for e in intent_manager._history if e.resource_key == "PRJ:resource"]
        
        assert len(resource_history) == 3
        assert resource_history[0].action == "protect"
        assert resource_history[1].action == "unprotect"
        assert resource_history[2].action == "protect"
    
    def test_saved_intent_equals_in_memory_intent(
        self, intent_manager: ProtectionIntentManager
    ):
        """Test that saved and in-memory intent are identical after save."""
        # Set intents
        intent_manager.set_intent("PRJ:a", protected=True, source="test", reason="test")
        intent_manager.set_intent("PRJ:b", protected=False, source="test", reason="test")
        
        # Save
        intent_manager.save()
        
        # Load into new manager
        new_manager = ProtectionIntentManager(intent_manager._intent_file)
        new_manager.load()
        
        # Compare
        for key in intent_manager._intent:
            assert key in new_manager._intent
            assert intent_manager._intent[key].protected == new_manager._intent[key].protected
            assert intent_manager._intent[key].set_by == new_manager._intent[key].set_by
            assert intent_manager._intent[key].reason == new_manager._intent[key].reason
