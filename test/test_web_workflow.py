"""Comprehensive tests for the new 9-step workflow.

Tests cover:
1. State management (WorkflowStep enum, STEP_NAMES, STEP_ICONS)
2. Step accessibility (workflow progression, locking)
3. State persistence (serialization round-trips)
4. Target matching logic
5. Mapping file operations
6. Module imports
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import List

from importer.web.state import (
    AppState,
    WorkflowStep,
    WorkflowType,
    FetchState,
    TargetFetchState,
    MapState,
    DeployState,
    STEP_NAMES,
    STEP_ICONS,
    WORKFLOW_STEPS,
)


class TestWorkflowSteps:
    """Test WorkflowStep enum and configuration."""
    
    def test_workflow_step_enum_values(self):
        """Verify all 10 workflow steps exist with correct order."""
        expected_steps = [
            ("HOME", 0),
            ("FETCH_SOURCE", 1),
            ("EXPLORE_SOURCE", 2),
            ("SCOPE", 3),
            ("FETCH_TARGET", 4),
            ("EXPLORE_TARGET", 5),
            ("MATCH", 6),
            ("CONFIGURE", 7),
            ("TARGET_CREDENTIALS", 8),
            ("DEPLOY", 9),
            ("DESTROY", 10),
        ]
        
        for name, expected_value in expected_steps:
            assert hasattr(WorkflowStep, name), f"WorkflowStep.{name} should exist"
            assert getattr(WorkflowStep, name).value == expected_value, \
                f"WorkflowStep.{name} should have value {expected_value}"
    
    def test_migration_workflow_has_all_steps(self):
        """Verify WORKFLOW_STEPS[MIGRATION] contains 9 steps in order (DESTROY is utility)."""
        migration_steps = WORKFLOW_STEPS[WorkflowType.MIGRATION]
        
        expected = [
            WorkflowStep.FETCH_SOURCE,
            WorkflowStep.EXPLORE_SOURCE,
            WorkflowStep.SCOPE,
            WorkflowStep.FETCH_TARGET,
            WorkflowStep.EXPLORE_TARGET,
            WorkflowStep.MATCH,
            WorkflowStep.CONFIGURE,
            WorkflowStep.TARGET_CREDENTIALS,
            WorkflowStep.DEPLOY,
        ]
        
        assert len(migration_steps) == 9, "Migration workflow should have 9 steps"
        assert migration_steps == expected, "Migration workflow steps should be in order"
    
    def test_step_names_complete(self):
        """All WorkflowStep values have entries in STEP_NAMES."""
        for step in WorkflowStep:
            assert step in STEP_NAMES, f"STEP_NAMES should have entry for {step.name}"
            assert isinstance(STEP_NAMES[step], str), f"STEP_NAMES[{step.name}] should be a string"
            assert len(STEP_NAMES[step]) > 0, f"STEP_NAMES[{step.name}] should not be empty"
    
    def test_step_icons_complete(self):
        """All WorkflowStep values have entries in STEP_ICONS."""
        for step in WorkflowStep:
            assert step in STEP_ICONS, f"STEP_ICONS should have entry for {step.name}"
            assert isinstance(STEP_ICONS[step], str), f"STEP_ICONS[{step.name}] should be a string"
            assert len(STEP_ICONS[step]) > 0, f"STEP_ICONS[{step.name}] should not be empty"


class TestStepAccessibility:
    """Test workflow progression and step locking."""
    
    def test_fetch_source_always_accessible(self):
        """First step is always accessible."""
        state = AppState()
        assert state.step_is_accessible(WorkflowStep.FETCH_SOURCE) is True
    
    def test_explore_source_requires_fetch_complete(self):
        """Explore Source locked until Fetch Source complete."""
        state = AppState()
        
        # Initially locked
        assert state.step_is_accessible(WorkflowStep.EXPLORE_SOURCE) is False
        
        # After fetch complete
        state.fetch.fetch_complete = True
        assert state.step_is_accessible(WorkflowStep.EXPLORE_SOURCE) is True
    
    def test_scope_requires_fetch_complete(self):
        """Scope locked until Fetch Source complete."""
        state = AppState()
        
        assert state.step_is_accessible(WorkflowStep.SCOPE) is False
        
        state.fetch.fetch_complete = True
        assert state.step_is_accessible(WorkflowStep.SCOPE) is True
    
    def test_fetch_target_always_accessible(self):
        """Fetch Target is always accessible - can fetch target anytime."""
        state = AppState()
        
        # FETCH_TARGET is always accessible regardless of other step completion
        assert state.step_is_accessible(WorkflowStep.FETCH_TARGET) is True
        
        # Still accessible even without scope complete
        state.fetch.fetch_complete = True
        state.map.normalize_complete = True
        assert state.step_is_accessible(WorkflowStep.FETCH_TARGET) is True
    
    def test_explore_target_requires_fetch_target_complete(self):
        """Explore Target locked until Fetch Target complete."""
        state = AppState()
        
        assert state.step_is_accessible(WorkflowStep.EXPLORE_TARGET) is False
        
        state.target_fetch.fetch_complete = True
        assert state.step_is_accessible(WorkflowStep.EXPLORE_TARGET) is True
    
    def test_match_requires_both_normalizes_and_target_fetch(self):
        """Match requires both source scoped and target fetched."""
        state = AppState()
        
        assert state.step_is_accessible(WorkflowStep.MATCH) is False
        
        # Need both
        state.map.normalize_complete = True
        assert state.step_is_accessible(WorkflowStep.MATCH) is False
        
        state.target_fetch.fetch_complete = True
        assert state.step_is_accessible(WorkflowStep.MATCH) is True
    
    def test_configure_accessible_with_mapping_valid(self):
        """Configure accessible when mapping file is valid."""
        state = AppState()
        
        # Set up required preconditions
        state.map.normalize_complete = True
        state.target_fetch.fetch_complete = True
        state.map.mapping_file_valid = True
        
        assert state.step_is_accessible(WorkflowStep.CONFIGURE) is True
    
    def test_configure_accessible_without_mappings(self):
        """Configure accessible when no mappings needed (empty list)."""
        state = AppState()
        
        # Even without mappings, CONFIGURE is accessible if mapping step can be skipped
        # The actual logic allows it when mapping_file_valid OR confirmed_mappings is empty
        state.map.normalize_complete = True
        state.target_fetch.fetch_complete = True
        state.map.mapping_file_valid = False
        state.map.confirmed_mappings = []
        
        assert state.step_is_accessible(WorkflowStep.CONFIGURE) is True
    
    def test_deploy_requires_target_credentials_complete(self):
        """Deploy locked until target_credentials complete (or no environments)."""
        state = AppState()
        # When there are no selected environments, Deploy is accessible
        state.env_credentials.selected_env_ids = set()
        assert state.step_is_accessible(WorkflowStep.DEPLOY) is True
        
        # When there are selected environments, env_credentials must be complete
        state.env_credentials.selected_env_ids = {"123"}
        state.env_credentials.step_complete = False
        assert state.step_is_accessible(WorkflowStep.DEPLOY) is False
        
        state.env_credentials.step_complete = True
        assert state.step_is_accessible(WorkflowStep.DEPLOY) is True
    
    def test_destroy_method_exists(self):
        """Destroy step has state file check method."""
        state = AppState()
        
        # Test that the method exists
        assert hasattr(state.deploy, 'has_state_file')
        assert callable(state.deploy.has_state_file)


class TestStatePersistence:
    """Test state serialization and restoration."""
    
    def test_fetch_state_to_dict_round_trip(self):
        """FetchState survives to_dict/from_dict cycle."""
        state = AppState()
        state.fetch.fetch_complete = True
        state.fetch.last_fetch_file = "/path/to/data.json"
        state.fetch.account_name = "Test Account"
        state.fetch.resource_counts = {"projects": 5, "jobs": 10}
        
        data = state.to_dict()
        restored = AppState.from_dict(data)
        
        assert restored.fetch.fetch_complete is True
        assert restored.fetch.last_fetch_file == "/path/to/data.json"
        assert restored.fetch.account_name == "Test Account"
        assert restored.fetch.resource_counts == {"projects": 5, "jobs": 10}
    
    def test_target_fetch_state_to_dict_round_trip(self):
        """TargetFetchState survives to_dict/from_dict cycle."""
        state = AppState()
        state.target_fetch.fetch_complete = True
        state.target_fetch.last_fetch_file = "/path/to/target_data.json"
        state.target_fetch.account_name = "Target Account"
        state.target_fetch.output_dir = "custom/target/dir"
        
        data = state.to_dict()
        restored = AppState.from_dict(data)
        
        assert restored.target_fetch.fetch_complete is True
        assert restored.target_fetch.last_fetch_file == "/path/to/target_data.json"
        assert restored.target_fetch.account_name == "Target Account"
        assert restored.target_fetch.output_dir == "custom/target/dir"
    
    def test_app_state_preserves_new_steps(self):
        """AppState.current_step works with all new WorkflowStep values."""
        for step in WorkflowStep:
            state = AppState()
            state.current_step = step
            
            data = state.to_dict()
            restored = AppState.from_dict(data)
            
            assert restored.current_step == step, f"Failed to restore {step.name}"
    
    def test_map_state_with_matching_fields(self):
        """MapState matching fields survive round-trip."""
        state = AppState()
        state.map.target_matching_enabled = True
        state.map.confirmed_mappings = [
            {"source_key": "proj_1", "target_id": "123"},
        ]
        state.map.mapping_file_path = "/path/to/mapping.yml"
        state.map.mapping_file_valid = True
        
        data = state.to_dict()
        restored = AppState.from_dict(data)
        
        assert restored.map.target_matching_enabled is True
        assert len(restored.map.confirmed_mappings) == 1
        assert restored.map.mapping_file_path == "/path/to/mapping.yml"
        assert restored.map.mapping_file_valid is True


class TestTargetMatching:
    """Test source-to-target resource matching logic."""
    
    def test_exact_name_match_same_type(self):
        """Resources with same name and type match."""
        from importer.web.components.target_matcher import generate_match_suggestions
        
        source_items = [
            {"key": "project_1", "name": "MyProject", "element_type_code": "PRJ", "dbt_id": 100},
        ]
        target_items = [
            {"key": "target_proj", "name": "MyProject", "element_type_code": "PRJ", "dbt_id": 200},
        ]
        
        suggestions = generate_match_suggestions(source_items, target_items)
        
        assert len(suggestions) == 1
        assert suggestions[0].source_name == "MyProject"
        assert suggestions[0].target_name == "MyProject"
        assert suggestions[0].confidence == "exact_match"
    
    def test_no_match_different_types(self):
        """Resources with same name but different types don't match."""
        from importer.web.components.target_matcher import generate_match_suggestions
        
        source_items = [
            {"key": "job_1", "name": "DailyJob", "element_type_code": "JOB", "dbt_id": 100},
        ]
        target_items = [
            {"key": "env_1", "name": "DailyJob", "element_type_code": "ENV", "dbt_id": 200},
        ]
        
        suggestions = generate_match_suggestions(source_items, target_items)
        
        assert len(suggestions) == 0
    
    def test_no_match_different_names(self):
        """Resources with different names don't match."""
        from importer.web.components.target_matcher import generate_match_suggestions
        
        source_items = [
            {"key": "proj_1", "name": "ProjectA", "element_type_code": "PRJ", "dbt_id": 100},
        ]
        target_items = [
            {"key": "proj_2", "name": "ProjectB", "element_type_code": "PRJ", "dbt_id": 200},
        ]
        
        suggestions = generate_match_suggestions(source_items, target_items)
        
        assert len(suggestions) == 0
    
    def test_case_sensitive_matching(self):
        """Matching is case-sensitive."""
        from importer.web.components.target_matcher import generate_match_suggestions
        
        source_items = [
            {"key": "proj_1", "name": "myproject", "element_type_code": "PRJ", "dbt_id": 100},
        ]
        target_items = [
            {"key": "proj_2", "name": "MyProject", "element_type_code": "PRJ", "dbt_id": 200},
        ]
        
        suggestions = generate_match_suggestions(source_items, target_items)
        
        # Should NOT match due to case difference
        assert len(suggestions) == 0
    
    def test_generate_suggestions_returns_all_matches(self):
        """All matchable resources appear in suggestions."""
        from importer.web.components.target_matcher import generate_match_suggestions
        
        source_items = [
            {"key": "proj_1", "name": "ProjectA", "element_type_code": "PRJ", "dbt_id": 100},
            {"key": "proj_2", "name": "ProjectB", "element_type_code": "PRJ", "dbt_id": 101},
            {"key": "job_1", "name": "JobA", "element_type_code": "JOB", "dbt_id": 200},
        ]
        target_items = [
            {"key": "t_proj_1", "name": "ProjectA", "element_type_code": "PRJ", "dbt_id": 500},
            {"key": "t_job_1", "name": "JobA", "element_type_code": "JOB", "dbt_id": 600},
        ]
        
        suggestions = generate_match_suggestions(source_items, target_items)
        
        # Should match ProjectA and JobA (2 matches)
        assert len(suggestions) == 2
        
        matched_names = {s.source_name for s in suggestions}
        assert "ProjectA" in matched_names
        assert "JobA" in matched_names


class TestMappingFile:
    """Test mapping file creation and validation."""
    
    def test_create_mapping_from_confirmations(self):
        """Confirmed mappings convert to TargetResourceMapping."""
        from importer.web.utils.mapping_file import create_mapping_from_confirmations
        
        confirmations = [
            {
                "resource_type": "PRJ",
                "source_name": "Project1",
                "source_key": "proj_1",
                "target_id": "123",
                "target_name": "Project1",
                "match_type": "auto",
            }
        ]
        
        mapping = create_mapping_from_confirmations(confirmations, "source_acc", "target_acc")
        
        assert mapping is not None
        assert mapping.version == 1
        assert mapping.metadata.get("source_account_id") == "source_acc"
        assert mapping.metadata.get("target_account_id") == "target_acc"
        assert len(mapping.mappings) == 1
        assert mapping.mappings[0]["source_key"] == "proj_1"
        assert mapping.mappings[0]["target_id"] == "123"
    
    def test_mapping_file_round_trip_yaml(self):
        """Save and load YAML mapping file preserves data."""
        from importer.web.utils.mapping_file import (
            TargetResourceMapping,
            save_mapping_file,
            load_mapping_file,
        )
        
        # Use the factory method to create properly
        mapping = TargetResourceMapping.create(
            source_account_id="source_123",
            target_account_id="target_456",
            mappings=[
                {
                    "source_key": "proj_1",
                    "target_id": "789",
                    "resource_type": "PRJ",
                    "source_name": "MyProject",
                    "target_name": "MyProject",
                }
            ]
        )
        
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            error = save_mapping_file(mapping, temp_path)
            assert error is None, f"Save failed: {error}"
            
            loaded, load_error = load_mapping_file(temp_path)
            assert load_error is None, f"Load failed: {load_error}"
            assert loaded is not None
            
            assert loaded.version == mapping.version
            assert loaded.metadata.get("source_account_id") == mapping.metadata.get("source_account_id")
            assert loaded.metadata.get("target_account_id") == mapping.metadata.get("target_account_id")
            assert len(loaded.mappings) == 1
            assert loaded.mappings[0]["source_key"] == "proj_1"
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_mapping_validation_detects_duplicates(self):
        """Validation catches duplicate source or target mappings."""
        from importer.web.utils.mapping_file import (
            TargetResourceMapping,
            validate_mapping_file,
        )
        
        mapping = TargetResourceMapping(
            version=1,
            metadata={},
            mappings=[
                {"source_key": "proj_1", "target_id": 123},
                {"source_key": "proj_1", "target_id": 456},  # Duplicate source_key
            ]
        )
        
        # Need sample source and target items for validation
        source_items = [{"key": "proj_1", "element_type_code": "PRJ", "dbt_id": 100}]
        target_items = [
            {"key": "t1", "element_type_code": "PRJ", "dbt_id": 123},
            {"key": "t2", "element_type_code": "PRJ", "dbt_id": 456},
        ]
        
        result = validate_mapping_file(mapping, source_items, target_items)
        assert result.valid is False
        assert len(result.errors) > 0
        assert any("duplicate" in err.message.lower() for err in result.errors)


class TestModuleImports:
    """Verify all new modules import without errors."""
    
    def test_import_state(self):
        """state.py imports successfully with new WorkflowStep enum."""
        from importer.web.state import (
            AppState,
            WorkflowStep,
            STEP_NAMES,
            STEP_ICONS,
            WORKFLOW_STEPS,
        )
        
        assert WorkflowStep.FETCH_SOURCE is not None
        assert WorkflowStep.EXPLORE_SOURCE is not None
        assert WorkflowStep.SCOPE is not None
        assert WorkflowStep.FETCH_TARGET is not None
        assert WorkflowStep.EXPLORE_TARGET is not None
        assert WorkflowStep.MATCH is not None
        assert WorkflowStep.CONFIGURE is not None
    
    def test_import_fetch_source(self):
        """fetch_source.py imports successfully."""
        from importer.web.pages.fetch_source import create_fetch_source_page
        assert create_fetch_source_page is not None
    
    def test_import_fetch_target(self):
        """fetch_target.py imports successfully."""
        from importer.web.pages.fetch_target import create_fetch_target_page
        assert create_fetch_target_page is not None
    
    def test_import_explore_source(self):
        """explore_source.py imports successfully."""
        from importer.web.pages.explore_source import create_explore_source_page
        assert create_explore_source_page is not None
    
    def test_import_explore_target(self):
        """explore_target.py imports successfully."""
        from importer.web.pages.explore_target import create_explore_target_page
        assert create_explore_target_page is not None
    
    def test_import_scope(self):
        """scope.py imports successfully."""
        from importer.web.pages.scope import create_scope_page
        assert create_scope_page is not None
    
    def test_import_match(self):
        """match.py imports successfully."""
        from importer.web.pages.match import create_match_page
        assert create_match_page is not None
    
    def test_import_configure(self):
        """configure.py imports successfully."""
        from importer.web.pages.configure import create_configure_page
        assert create_configure_page is not None
    
    def test_import_app(self):
        """app.py imports successfully with new routes."""
        from importer.web.app import (
            create_page_content,
            navigate_to_step,
            get_state,
        )
        assert create_page_content is not None
        assert navigate_to_step is not None
        assert get_state is not None


class TestWorkflowTypes:
    """Test different workflow type configurations."""
    
    def test_account_explorer_workflow(self):
        """Account Explorer workflow has correct steps."""
        steps = WORKFLOW_STEPS[WorkflowType.ACCOUNT_EXPLORER]
        
        assert WorkflowStep.FETCH_SOURCE in steps
        assert WorkflowStep.EXPLORE_SOURCE in steps
        assert len(steps) == 2
    
    def test_jobs_as_code_workflow(self):
        """Jobs as Code workflow has correct JAC-specific steps."""
        steps = WORKFLOW_STEPS[WorkflowType.JOBS_AS_CODE]
        
        assert WorkflowStep.JAC_SELECT in steps
        assert WorkflowStep.JAC_FETCH in steps
        assert WorkflowStep.JAC_JOBS in steps
        assert WorkflowStep.JAC_CONFIG in steps
        assert WorkflowStep.JAC_GENERATE in steps
        assert len(steps) == 5
    
    def test_import_adopt_workflow(self):
        """Import & Adopt workflow has all 9 steps including TARGET_CREDENTIALS."""
        steps = WORKFLOW_STEPS[WorkflowType.IMPORT_ADOPT]
        
        assert len(steps) == 9
        assert WorkflowStep.MATCH in steps
        assert WorkflowStep.CONFIGURE in steps
        assert WorkflowStep.TARGET_CREDENTIALS in steps


class TestStepCompletion:
    """Test step completion status tracking."""
    
    def test_fetch_source_complete(self):
        """FETCH_SOURCE complete when fetch.fetch_complete is True."""
        state = AppState()
        
        assert state.step_is_complete(WorkflowStep.FETCH_SOURCE) is False
        
        state.fetch.fetch_complete = True
        assert state.step_is_complete(WorkflowStep.FETCH_SOURCE) is True
    
    def test_scope_complete(self):
        """SCOPE complete when normalize_complete is True."""
        state = AppState()
        
        assert state.step_is_complete(WorkflowStep.SCOPE) is False
        
        state.map.normalize_complete = True
        assert state.step_is_complete(WorkflowStep.SCOPE) is True
    
    def test_fetch_target_complete(self):
        """FETCH_TARGET complete when target_fetch.fetch_complete is True."""
        state = AppState()
        
        assert state.step_is_complete(WorkflowStep.FETCH_TARGET) is False
        
        state.target_fetch.fetch_complete = True
        assert state.step_is_complete(WorkflowStep.FETCH_TARGET) is True
    
    def test_match_complete(self):
        """MATCH complete when mapping_file_valid is True."""
        state = AppState()
        
        assert state.step_is_complete(WorkflowStep.MATCH) is False
        
        state.map.mapping_file_valid = True
        assert state.step_is_complete(WorkflowStep.MATCH) is True
    
    def test_configure_complete(self):
        """CONFIGURE complete when configure_complete is True."""
        state = AppState()
        
        assert state.step_is_complete(WorkflowStep.CONFIGURE) is False
        
        state.deploy.configure_complete = True
        assert state.step_is_complete(WorkflowStep.CONFIGURE) is True
    
    def test_deploy_complete(self):
        """DEPLOY complete when apply_complete is True."""
        state = AppState()
        
        assert state.step_is_complete(WorkflowStep.DEPLOY) is False
        
        state.deploy.apply_complete = True
        assert state.step_is_complete(WorkflowStep.DEPLOY) is True
