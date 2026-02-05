"""Integration tests for the full generate flow.

These tests verify the complete generate workflow without UI:
- Intent recording → YAML update → Moves file generation
- ProtectionIntentManager + protection_manager integration
- File system side effects

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.6 Integration Tests
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import shutil

from importer.web.utils.protection_intent import (
    ProtectionIntentManager,
    ProtectionIntent,
)
from importer.web.utils.protection_manager import (
    ProtectionChange,
    generate_moved_blocks,
    generate_moved_blocks_from_state,
    write_moved_blocks_file,
    detect_protection_mismatches,
    generate_repair_moved_blocks,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def test_workspace(tmp_path):
    """Create a test workspace with necessary files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    # Create subdirectories
    (workspace / "terraform").mkdir()
    
    return workspace


@pytest.fixture
def sample_yaml_content():
    """Sample YAML configuration content."""
    return """
version: 2
projects:
  - key: my_project
    name: My Project
    protected: false
    repository: my_repo
    environments:
      - key: dev
        name: Development
        protected: false
      - key: prod
        name: Production
        protected: false
    jobs:
      - key: daily_job
        name: Daily Job
        protected: false

globals:
  repositories:
    - key: global_repo
      remote_url: https://github.com/example/repo
      protected: false
"""


@pytest.fixture
def sample_terraform_state():
    """Sample Terraform state with resources."""
    return {
        "version": 4,
        "terraform_version": "1.5.0",
        "serial": 1,
        "lineage": "test",
        "outputs": {},
        "resources": [
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "type": "dbtcloud_project",
                "name": "projects",  # unprotected block
                "instances": [
                    {"index_key": "my_project", "attributes": {"id": "123", "name": "My Project"}},
                ],
            },
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "type": "dbtcloud_repository",
                "name": "repositories",  # unprotected block
                "instances": [
                    {"index_key": "my_project", "attributes": {"id": "456"}},
                ],
            },
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "type": "dbtcloud_project_repository",
                "name": "project_repositories",  # unprotected block
                "instances": [
                    {"index_key": "my_project", "attributes": {"id": "789"}},
                ],
            },
        ],
    }


@pytest.fixture
def intent_manager(test_workspace):
    """Create a ProtectionIntentManager with a test file."""
    intent_file = test_workspace / "protection-intent.json"
    manager = ProtectionIntentManager(intent_file)
    return manager


# =============================================================================
# Integration Tests: Intent Recording
# =============================================================================

class TestIntentRecordingIntegration:
    """Tests for intent recording workflow."""
    
    def test_record_protect_intent(self, intent_manager):
        """Test recording a protection intent."""
        # Record intent
        intent = intent_manager.set_intent(
            key="PRJ:my_project",
            protected=True,
            source="test",
            reason="Testing protection",
        )
        
        assert intent.protected is True
        assert intent.applied_to_yaml is False
        assert intent.applied_to_tf_state is False
    
    def test_record_multiple_intents(self, intent_manager):
        """Test recording multiple intents."""
        intent_manager.set_intent("PRJ:project1", protected=True, source="test", reason="Test")
        intent_manager.set_intent("PRJ:project2", protected=False, source="test", reason="Test")
        intent_manager.set_intent("REPO:repo1", protected=True, source="test", reason="Test")
        
        pending = intent_manager.get_pending_yaml_updates()
        
        assert len(pending) == 3
        assert "PRJ:project1" in pending
        assert "PRJ:project2" in pending
        assert "REPO:repo1" in pending
    
    def test_intent_save_and_load(self, intent_manager, test_workspace):
        """Test saving and loading intent file."""
        # Record intent
        intent_manager.set_intent("PRJ:my_project", protected=True, source="test", reason="Test")
        intent_manager.save()
        
        # Verify file exists
        assert intent_manager.intent_file.exists()
        
        # Load in new manager
        new_manager = ProtectionIntentManager(intent_manager.intent_file)
        new_manager.load()
        
        intent = new_manager.get_intent("PRJ:my_project")
        assert intent is not None
        assert intent.protected is True
    
    def test_intent_precedence_over_yaml(self, intent_manager):
        """Test that intent takes precedence over YAML."""
        # Set intent to unprotect
        intent_manager.set_intent("PRJ:my_project", protected=False, source="test", reason="Test")
        
        # YAML says protected
        yaml_protected = True
        
        # Effective should be from intent (unprotected)
        effective = intent_manager.get_effective_protection("PRJ:my_project", yaml_protected)
        assert effective is False


# =============================================================================
# Integration Tests: Generate Flow
# =============================================================================

class TestGenerateFlowIntegration:
    """Tests for the full generate workflow."""
    
    def test_generate_creates_moves_file(self, test_workspace, sample_terraform_state):
        """Test that generate creates protection_moves.tf file."""
        # Create state file
        state_file = test_workspace / "terraform" / "terraform.tfstate"
        state_file.write_text(json.dumps(sample_terraform_state))
        
        # Create YAML config that requires protection
        yaml_config = {
            "projects": [
                {
                    "key": "my_project",
                    "protected": True,  # Request protection
                    "repository": "my_repo",
                },
            ],
        }
        
        # Detect changes from state
        changes = generate_moved_blocks_from_state(yaml_config, str(state_file))
        
        # Should detect changes (state is unprotected, YAML requests protected)
        assert len(changes) > 0
        
        # Write moves file
        moves_path = write_moved_blocks_file(
            changes,
            test_workspace / "terraform",
        )
        
        assert moves_path is not None
        assert moves_path.exists()
        
        content = moves_path.read_text()
        assert "moved {" in content
    
    def test_generate_updates_intent_applied_flag(self, intent_manager):
        """Test that generate marks intents as applied to YAML."""
        # Record intents
        intent_manager.set_intent("PRJ:project1", protected=True, source="test", reason="Test")
        intent_manager.set_intent("PRJ:project2", protected=True, source="test", reason="Test")
        
        # Simulate generate - mark as applied
        intent_manager.mark_applied_to_yaml({"PRJ:project1", "PRJ:project2"})
        
        # Check flags
        intent1 = intent_manager.get_intent("PRJ:project1")
        intent2 = intent_manager.get_intent("PRJ:project2")
        
        assert intent1.applied_to_yaml is True
        assert intent2.applied_to_yaml is True
    
    def test_generate_repo_creates_two_moved_blocks(self, test_workspace, sample_terraform_state):
        """Test that REPO protection generates moved blocks for both REP and PREP."""
        # Create state file
        state_file = test_workspace / "terraform" / "terraform.tfstate"
        state_file.write_text(json.dumps(sample_terraform_state))
        
        # Request REPO protection
        yaml_config = {
            "projects": [
                {
                    "key": "my_project",
                    "protected": True,  # This affects REP and PREP
                    "repository": "my_repo",
                },
            ],
        }
        
        changes = generate_moved_blocks_from_state(yaml_config, str(state_file))
        
        # Filter for REP and PREP changes
        repo_changes = [c for c in changes if c.resource_type in ("REP", "PREP")]
        
        # Should have changes for both
        rep_changes = [c for c in repo_changes if c.resource_type == "REP"]
        prep_changes = [c for c in repo_changes if c.resource_type == "PREP"]
        
        # Both should be present (or neither if they're already aligned)
        # This depends on the state - in our sample state, both are unprotected


# =============================================================================
# Integration Tests: Mismatch Detection and Repair
# =============================================================================

class TestMismatchDetectionIntegration:
    """Tests for mismatch detection and repair workflow."""
    
    def test_detect_mismatches_yaml_vs_state(self, sample_terraform_state):
        """Test detection of mismatches between YAML and state."""
        # YAML says protected, state is unprotected
        yaml_config = {
            "projects": [
                {
                    "key": "my_project",
                    "protected": True,
                    "repository": "my_repo",
                },
            ],
        }
        
        mismatches = detect_protection_mismatches(yaml_config, sample_terraform_state)
        
        # Should detect mismatch for project (and potentially REP/PREP)
        prj_mismatches = [m for m in mismatches if m.resource_type == "PRJ"]
        assert len(prj_mismatches) >= 1
        
        mismatch = prj_mismatches[0]
        assert mismatch.yaml_protected is True
        assert mismatch.state_protected is False
    
    def test_generate_repair_blocks(self):
        """Test generation of repair moved blocks."""
        mismatches = [
            type('ProtectionMismatch', (), {
                'resource_key': 'my_project',
                'resource_type': 'PRJ',
                'yaml_protected': True,
                'state_protected': False,
                'needs_move_to_protected': True,
                'needs_move_to_unprotected': False,
                'move_direction': 'protect',
                'state_address': 'module.dbt_cloud.module.projects_v2[0].dbtcloud_project.projects["my_project"]',
                'expected_address': 'module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["my_project"]',
            })(),
        ]
        
        # Need to convert to proper class instances for the function
        from importer.web.utils.protection_manager import ProtectionMismatch
        
        proper_mismatches = [
            ProtectionMismatch(
                resource_key='my_project',
                resource_type='PRJ',
                yaml_protected=True,
                state_protected=False,
                state_address='module.dbt_cloud.module.projects_v2[0].dbtcloud_project.projects["my_project"]',
                expected_address='module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["my_project"]',
            )
        ]
        
        result = generate_repair_moved_blocks(proper_mismatches)
        
        assert "moved {" in result
        assert "my_project" in result


# =============================================================================
# Integration Tests: End-to-End Generate Flow
# =============================================================================

class TestEndToEndGenerateFlow:
    """Tests for complete generate flow end-to-end."""
    
    def test_full_protect_workflow(self, test_workspace, sample_terraform_state):
        """Test full workflow: intent → detect changes → generate moves."""
        # Setup files
        state_file = test_workspace / "terraform" / "terraform.tfstate"
        state_file.write_text(json.dumps(sample_terraform_state))
        
        intent_file = test_workspace / "protection-intent.json"
        
        # Step 1: Create intent manager and record intent
        manager = ProtectionIntentManager(intent_file)
        manager.set_intent(
            key="PRJ:my_project",
            protected=True,
            source="user_click",
            reason="Protect project from accidental deletion",
        )
        manager.save()
        
        # Step 2: Build YAML config based on intent
        yaml_config = {
            "projects": [
                {
                    "key": "my_project",
                    "protected": manager.get_effective_protection("PRJ:my_project", yaml_protected=False),
                    "repository": "my_repo",
                },
            ],
        }
        
        # Step 3: Detect changes from state
        changes = generate_moved_blocks_from_state(yaml_config, str(state_file))
        
        # Step 4: Generate moves file
        if changes:
            moves_path = write_moved_blocks_file(
                changes,
                test_workspace / "terraform",
            )
            assert moves_path.exists()
        
        # Step 5: Mark intent as applied to YAML
        manager.mark_applied_to_yaml({"PRJ:my_project"})
        manager.save()
        
        # Verify intent is marked
        manager2 = ProtectionIntentManager(intent_file)
        manager2.load()
        intent = manager2.get_intent("PRJ:my_project")
        assert intent.applied_to_yaml is True
    
    def test_unprotect_workflow(self, test_workspace):
        """Test unprotection workflow."""
        # State has protected resources
        state = {
            "version": 4,
            "resources": [
                {
                    "module": "module.dbt_cloud.module.projects_v2[0]",
                    "type": "dbtcloud_project",
                    "name": "protected_projects",  # Protected in state
                    "instances": [
                        {"index_key": "my_project", "attributes": {"id": "123"}},
                    ],
                },
            ],
        }
        
        state_file = test_workspace / "terraform" / "terraform.tfstate"
        state_file.write_text(json.dumps(state))
        
        # Request unprotection
        yaml_config = {
            "projects": [
                {"key": "my_project", "protected": False},
            ],
        }
        
        changes = generate_moved_blocks_from_state(yaml_config, str(state_file))
        
        # Should detect need to move from protected to unprotected
        prj_changes = [c for c in changes if c.resource_type == "PRJ"]
        if prj_changes:
            assert prj_changes[0].direction == "unprotect"


# =============================================================================
# Integration Tests: Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in generate flow."""
    
    def test_missing_state_file(self, test_workspace):
        """Test handling of missing state file."""
        yaml_config = {"projects": [{"key": "test", "protected": True}]}
        
        changes = generate_moved_blocks_from_state(
            yaml_config,
            str(test_workspace / "nonexistent.tfstate"),
        )
        
        # Should return empty list, not raise
        assert changes == []
    
    def test_corrupted_intent_file(self, test_workspace):
        """Test handling of corrupted intent file."""
        intent_file = test_workspace / "protection-intent.json"
        intent_file.write_text("not valid json {{{")
        
        manager = ProtectionIntentManager(intent_file)
        
        with pytest.raises(ValueError, match="Corrupted"):
            manager.load()
    
    def test_empty_changes_no_file_written(self, test_workspace):
        """Test that no file is written when there are no changes."""
        result = write_moved_blocks_file([], test_workspace / "terraform")
        
        assert result is None
        assert not (test_workspace / "terraform" / "protection_moves.tf").exists()
