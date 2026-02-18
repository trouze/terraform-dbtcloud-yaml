"""Comprehensive unit tests for the Project Management feature.

Covers:
- Phase 1: CloneConfig, ImportResult, JACProjectMapping, JACEnvironmentMapping serialization
- Phase 2: Tier 1 AppState serialization (all missing fields)
- Phase 3: Tier 2 log file splitting and restoration
- Phase 4: Tier 3 field exclusion
- Phase 5: ProjectManager CRUD, slugify, lifecycle
- Phase 6: Settings preservation across fetch
- Phase 7: Gitignore template correctness
- Backward compatibility with legacy state.json

Reference: PRD 21.02-Project-Management.md Testing Plan
"""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from importer.web.state import (
    AppState,
    CloneConfig,
    DeployState,
    FetchMode,
    FetchState,
    ImportResult,
    JACEnvironmentMapping,
    JACJobConfig,
    JACProjectMapping,
    JACSubWorkflow,
    JACOutputFormat,
    JobsAsCodeState,
    MapState,
    SourceCredentials,
    TargetCredentials,
    WorkflowStep,
    WorkflowType,
)
from importer.web.project_manager import (
    OutputConfig,
    ProjectConfig,
    ProjectManager,
    TIER2_LOG_FILES,
    TIER2_JAC_LOG_FILES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    """Provide a temporary directory that is removed after the test."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def pm(tmp_dir):
    """Provide a ProjectManager backed by a temporary directory."""
    return ProjectManager(base_path=tmp_dir)


@pytest.fixture
def full_state() -> AppState:
    """Return a fully-populated AppState with ALL Tier 1 fields set.
    
    Per PRD testing plan: test_state_full.json equivalent.
    """
    state = AppState()
    state.current_step = WorkflowStep.DEPLOY
    state.theme = "light"
    state.workflow = WorkflowType.MIGRATION
    state.is_migration_licensed = True
    state.license_tier = "solutions_architect"
    state.license_email = "test@example.com"
    state.license_message = "Valid"
    state.active_fetch_mode = FetchMode.TARGET
    state.active_project = "test-project"
    state.project_path = "/tmp/projects/test-project"

    # Source credentials (FR-52: token_type serialized)
    state.source_credentials.host_url = "https://cloud.getdbt.com"
    state.source_credentials.account_id = "12345"
    state.source_credentials.token_type = "user_token"

    # Target credentials
    state.target_credentials.host_url = "https://emea.dbt.com"
    state.target_credentials.account_id = "67890"
    state.target_credentials.token_type = "service_token"

    # Source account
    state.source_account.account_id = "12345"
    state.source_account.account_name = "Source Corp"
    state.source_account.host_url = "https://cloud.getdbt.com"
    state.source_account.is_configured = True
    state.source_account.is_verified = True

    # Target account
    state.target_account.account_id = "67890"
    state.target_account.account_name = "Target Corp"
    state.target_account.is_configured = True

    # Fetch states
    state.fetch.output_dir = "outputs/source"
    state.fetch.fetch_complete = True
    state.fetch.last_fetch_file = "outputs/source/fetch.json"
    state.fetch.resource_counts = {"projects": 5, "environments": 12, "jobs": 30}
    state.target_fetch.fetch_complete = True
    state.target_fetch.last_fetch_file = "outputs/target/fetch.json"

    # Map state — Tier 1 user selections (FR-44, FR-45, FR-46)
    state.map.selected_entities = {"PRJ-1", "PRJ-2", "ENV-1", "ENV-2", "JOB-1", "EXTATTR-1"}
    state.map.selections_loaded = True
    state.map.selection_counts = {"selected": 6, "total": 50}
    state.map.include_groups = True
    state.map.include_notifications = True
    state.map.include_service_tokens = False
    state.map.include_webhooks = False
    state.map.include_privatelink = True
    state.map.auto_cascade_children = True
    state.map.scope_mode = "specific_projects"
    state.map.selected_project_ids = [1, 2, 3]
    state.map.confirmed_mappings = [
        {"source_key": "ENV-1", "target_key": "ENV-100", "type": "ENV"},
        {"source_key": "JOB-1", "target_key": "JOB-200", "type": "JOB"},
    ]
    state.map.rejected_suggestions = {"PRJ-99", "ENV-88"}
    state.map.cloned_resources = [
        CloneConfig(
            source_key="PRJ-1",
            new_name="Cloned Project",
            include_dependents=["ENV-1"],
            include_triggers=True,
        )
    ]
    state.map.protected_resources = {"PRJ-1", "REP-1", "PREP-1", "ENV-1", "JOB-1", "EXTATTR-1"}
    state.map.target_matching_enabled = True
    state.map.normalize_complete = True

    # Deploy state — Tier 1 step completion flags (FR-37, FR-39)
    state.deploy.configure_complete = True
    state.deploy.apply_complete = True
    state.deploy.destroy_complete = False
    state.deploy.terraform_initialized = True
    state.deploy.last_validate_success = True
    state.deploy.last_plan_success = True
    state.deploy.disable_job_triggers = True
    state.deploy.import_mode = "legacy"
    state.deploy.connection_configs = {
        "env-1": {"type": "snowflake", "account": "xy12345"},
    }
    state.deploy.previous_yaml_file = "deployments/migration/main.tf.yaml"
    state.deploy.imports_file_generated = True
    state.deploy.import_results = [
        ImportResult(
            resource_address="dbtcloud_project.p1",
            target_id="123",
            source_key="PRJ-1",
            resource_type="dbtcloud_project",
            status="success",
            duration_ms=450,
        ),
        ImportResult(
            resource_address="dbtcloud_environment.e1",
            target_id="456",
            source_key="ENV-1",
            resource_type="dbtcloud_environment",
            status="failed",
            error_message="Not found",
        ),
    ]
    state.deploy.apply_results = {"added": 3, "changed": 1, "destroyed": 0}
    state.deploy.reconcile_state_loaded = True
    state.deploy.reconcile_state_resources = [{"address": "dbtcloud_project.p1", "type": "dbtcloud_project"}]
    state.deploy.reconcile_drift_results = [{"address": "dbtcloud_project.p1", "status": "changed"}]
    state.deploy.reconcile_adopt_selections = ["dbtcloud_project.p1"]
    state.deploy.reconcile_imports_generated = True
    state.deploy.reconcile_adopt_rows = [{"address": "dbtcloud_project.p1", "target_id": "123"}]
    state.deploy.reconcile_execution_logs = [
        {"timestamp": "2024-01-01T00:00:00", "cmd": "terraform apply", "success": True}
    ]

    # Tier 2 — operation logs
    state.deploy.last_generate_output = "Generated 5 resources"
    state.deploy.last_init_output = "Terraform initialized"
    state.deploy.last_validate_output = "Success! The configuration is valid."
    state.deploy.last_plan_output = "Plan: 3 to add, 0 to change, 0 to destroy."
    state.deploy.last_apply_output = "Apply complete! Resources: 3 added."
    state.deploy.last_import_output = "Import successful."

    # Jobs as Code — Tier 1 (FR-49, FR-50)
    state.jobs_as_code.fetch_complete = True
    state.jobs_as_code.source_jobs = [{"id": 1, "name": "Job A"}]
    state.jobs_as_code.target_jobs = [{"id": 100, "name": "Target Job"}]
    state.jobs_as_code.target_projects = {"10": "Target Project"}
    state.jobs_as_code.target_environments = {"20": "Target Env"}
    state.jobs_as_code.project_mappings = [
        JACProjectMapping(source_id=1, source_name="Src Proj", target_id=10, target_name="Tgt Proj"),
    ]
    state.jobs_as_code.environment_mappings = [
        JACEnvironmentMapping(source_id=2, source_name="Src Env", source_project_id=1, target_id=20, target_name="Tgt Env"),
    ]
    state.jobs_as_code.generated_yaml = "jobs:\n  - name: my_job"
    state.jobs_as_code.generated_vars_yaml = "vars:\n  project_id: 10"
    state.jobs_as_code.generation_complete = True

    # Data quality warnings (FR-51)
    state.data_quality_warnings = {
        "source": {"collisions": {"env_var": [{"key": "MY_VAR", "count": 2}]}},
    }

    return state


# ===========================================================================
# Phase 1: Dataclass serialization
# ===========================================================================

class TestCloneConfigSerialization:
    def test_round_trip(self):
        cc = CloneConfig(
            source_key="PRJ-1", new_name="Test", include_dependents=["ENV-1"],
            dependent_names={"ENV-1": "New Env"}, include_triggers=True,
        )
        cc2 = CloneConfig.from_dict(cc.to_dict())
        assert cc2.source_key == "PRJ-1"
        assert cc2.new_name == "Test"
        assert cc2.include_dependents == ["ENV-1"]
        assert cc2.dependent_names == {"ENV-1": "New Env"}
        assert cc2.include_triggers is True
        assert cc2.include_credentials is False  # default

    def test_defaults(self):
        cc = CloneConfig.from_dict({})
        assert cc.source_key == ""
        assert cc.include_env_values is True


class TestImportResultSerialization:
    def test_round_trip(self):
        ir = ImportResult(
            resource_address="dbtcloud_project.p1", target_id="123",
            source_key="PRJ-1", resource_type="dbtcloud_project",
            status="success", error_message=None, duration_ms=500,
        )
        ir2 = ImportResult.from_dict(ir.to_dict())
        assert ir2.resource_address == "dbtcloud_project.p1"
        assert ir2.status == "success"
        assert ir2.duration_ms == 500
        assert ir2.error_message is None

    def test_defaults(self):
        ir = ImportResult.from_dict({})
        assert ir.status == "pending"
        assert ir.duration_ms is None


class TestJACProjectMappingSerialization:
    def test_round_trip(self):
        pm = JACProjectMapping(source_id=1, source_name="Src", target_id=10, target_name="Tgt")
        pm2 = JACProjectMapping.from_dict(pm.to_dict())
        assert pm2.source_id == 1
        assert pm2.target_id == 10
        assert pm2.target_name == "Tgt"

    def test_none_target(self):
        pm = JACProjectMapping(source_id=1, source_name="Src")
        pm2 = JACProjectMapping.from_dict(pm.to_dict())
        assert pm2.target_id is None


class TestJACEnvironmentMappingSerialization:
    def test_round_trip(self):
        em = JACEnvironmentMapping(
            source_id=2, source_name="Dev", source_project_id=1,
            target_id=20, target_name="Prod",
        )
        em2 = JACEnvironmentMapping.from_dict(em.to_dict())
        assert em2.source_project_id == 1
        assert em2.target_id == 20


# ===========================================================================
# Phase 2: Tier 1 AppState serialization
# ===========================================================================

class TestTier1Serialization:
    """Verify ALL Tier 1 fields round-trip correctly."""

    def test_full_round_trip(self, full_state):
        d = full_state.to_dict()
        restored = AppState.from_dict(d)

        # Project fields
        assert restored.active_project == "test-project"
        assert restored.project_path == "/tmp/projects/test-project"

        # Source credentials (FR-52)
        assert restored.source_credentials.token_type == "user_token"

        # Map selections (FR-44)
        assert restored.map.selected_entities == {"PRJ-1", "PRJ-2", "ENV-1", "ENV-2", "JOB-1", "EXTATTR-1"}
        assert restored.map.selections_loaded is True
        assert restored.map.selection_counts == {"selected": 6, "total": 50}

        # Map toggles (FR-45)
        assert restored.map.include_groups is True
        assert restored.map.include_notifications is True
        assert restored.map.include_service_tokens is False
        assert restored.map.include_webhooks is False
        assert restored.map.include_privatelink is True
        assert restored.map.auto_cascade_children is True

        # Map rejects + clones (FR-46)
        assert restored.map.rejected_suggestions == {"PRJ-99", "ENV-88"}
        assert len(restored.map.cloned_resources) == 1
        assert restored.map.cloned_resources[0].source_key == "PRJ-1"
        assert restored.map.cloned_resources[0].include_triggers is True

        # Deploy step completion (FR-37)
        assert restored.deploy.configure_complete is True
        assert restored.deploy.apply_complete is True
        assert restored.deploy.destroy_complete is False
        assert restored.deploy.terraform_initialized is True

        # Deploy operation flags (FR-39)
        assert restored.deploy.last_validate_success is True
        assert restored.deploy.last_plan_success is True

        # Deploy user settings
        assert restored.deploy.disable_job_triggers is True
        assert restored.deploy.import_mode == "legacy"
        assert "env-1" in restored.deploy.connection_configs
        assert restored.deploy.previous_yaml_file == "deployments/migration/main.tf.yaml"
        assert restored.deploy.imports_file_generated is True

        # Import results (FR-47)
        assert len(restored.deploy.import_results) == 2
        assert restored.deploy.import_results[0].status == "success"
        assert restored.deploy.import_results[1].error_message == "Not found"
        assert restored.deploy.apply_results == {"added": 3, "changed": 1, "destroyed": 0}

        # Reconcile state (FR-48)
        assert restored.deploy.reconcile_state_loaded is True
        assert len(restored.deploy.reconcile_state_resources) == 1
        assert len(restored.deploy.reconcile_drift_results) == 1
        assert restored.deploy.reconcile_adopt_selections == ["dbtcloud_project.p1"]
        assert restored.deploy.reconcile_imports_generated is True
        assert len(restored.deploy.reconcile_execution_logs) == 1

        # JAC mappings (FR-49)
        assert len(restored.jobs_as_code.project_mappings) == 1
        assert restored.jobs_as_code.project_mappings[0].source_id == 1
        assert len(restored.jobs_as_code.environment_mappings) == 1
        assert restored.jobs_as_code.target_jobs == [{"id": 100, "name": "Target Job"}]
        assert restored.jobs_as_code.target_projects == {"10": "Target Project"}

        # JAC generated outputs (FR-50 Tier 2)
        assert "my_job" in restored.jobs_as_code.generated_yaml
        assert "project_id" in restored.jobs_as_code.generated_vars_yaml

        # Data quality warnings (FR-51)
        assert "source" in restored.data_quality_warnings

    def test_protected_resources_all_types(self, full_state):
        """Verify protected_resources covers all resource types (per 41.02)."""
        d = full_state.to_dict()
        restored = AppState.from_dict(d)
        types_present = {k.split("-")[0] for k in restored.map.protected_resources}
        assert types_present >= {"PRJ", "REP", "PREP", "ENV", "JOB", "EXTATTR"}

    def test_set_serialization_sorted(self, full_state):
        """Sets must serialize as sorted lists for deterministic JSON."""
        d = full_state.to_dict()
        assert d["map"]["selected_entities"] == sorted(full_state.map.selected_entities)
        assert d["map"]["rejected_suggestions"] == sorted(full_state.map.rejected_suggestions)
        assert d["map"]["protected_resources"] == sorted(full_state.map.protected_resources)


# ===========================================================================
# Phase 3: Tier 2 log file persistence
# ===========================================================================

class TestTier2LogFiles:
    def test_save_splits_logs_to_files(self, pm, tmp_dir, full_state):
        config = pm.create_project("Log Test", WorkflowType.MIGRATION)
        full_state.active_project = config.slug
        full_state.project_path = str(pm.get_project_path(config.slug))

        pm.save_project(config.slug, full_state)

        # Verify log files created
        proj_path = pm.get_project_path(config.slug)
        for field_name, log_file in TIER2_LOG_FILES.items():
            fp = proj_path / log_file
            assert fp.exists(), f"Missing log file: {log_file}"

        # Verify state.json has empty sentinels
        with open(proj_path / "state.json") as f:
            saved = json.load(f)
        for field_name in TIER2_LOG_FILES:
            assert saved["deploy"][field_name] == "", f"{field_name} should be empty sentinel"

    def test_load_restores_logs_from_files(self, pm, tmp_dir, full_state):
        config = pm.create_project("Log Restore", WorkflowType.MIGRATION)
        pm.save_project(config.slug, full_state)

        _, loaded = pm.load_project(config.slug)
        assert loaded is not None
        assert "Plan: 3 to add" in loaded.deploy.last_plan_output
        assert "Apply complete" in loaded.deploy.last_apply_output
        assert "my_job" in loaded.jobs_as_code.generated_yaml

    def test_missing_log_files_graceful(self, pm, tmp_dir):
        """Loading a project with missing log files should not crash (FR-42)."""
        config = pm.create_project("No Logs", WorkflowType.MIGRATION)
        # Write a minimal state.json (no log files)
        state = AppState()
        state.active_project = config.slug
        proj_path = pm.get_project_path(config.slug)
        with open(proj_path / "state.json", "w") as f:
            json.dump(state.to_dict(), f)

        _, loaded = pm.load_project(config.slug)
        assert loaded is not None
        assert loaded.deploy.last_plan_output == ""


# ===========================================================================
# Phase 4: Tier 3 exclusion
# ===========================================================================

class TestTier3Exclusion:
    """Verify Tier 3 (runtime-only) fields are NOT in serialized output."""

    def test_runtime_fields_excluded(self):
        state = AppState()
        d = state.to_dict()

        # Tier 3 fields that must NOT be present
        assert "account_data" not in d
        assert "target_account_data" not in d
        assert "_protection_intent_manager" not in d

        # Fetch runtime fields
        fetch_d = d["fetch"]
        assert "is_fetching" not in fetch_d
        assert "threads" not in fetch_d

        # Map runtime fields
        map_d = d["map"]
        assert "normalize_running" not in map_d
        assert "normalize_error" not in map_d
        assert "suggested_matches" not in map_d
        assert "mapping_validation_errors" not in map_d

        # Explore runtime fields
        explore_d = d["explore"]
        assert "report_items" not in explore_d
        assert "selected_type_filter" not in explore_d
        assert "search_query" not in explore_d

        # JAC runtime fields
        jac_d = d["jobs_as_code"]
        assert "is_fetching" not in jac_d
        assert "fetch_error" not in jac_d
        assert "validation_errors" not in jac_d
        assert "identifier_warnings" not in jac_d


# ===========================================================================
# Phase 5: ProjectManager CRUD
# ===========================================================================

class TestProjectManagerSlugify:
    def test_basic(self):
        assert ProjectManager.slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert ProjectManager.slugify("My Project! @#$%") == "my-project"

    def test_unicode(self):
        slug = ProjectManager.slugify("Café Project")
        assert "caf" in slug

    def test_max_length(self):
        assert len(ProjectManager.slugify("a" * 100)) <= 50

    def test_empty(self):
        assert ProjectManager.slugify("") == ""

    def test_spaces(self):
        assert ProjectManager.slugify("  many   spaces  ") == "many-spaces"

    def test_hyphens_underscores(self):
        assert ProjectManager.slugify("foo-bar_baz") == "foo-bar_baz"


class TestProjectManagerCRUD:
    def test_list_empty(self, pm):
        assert pm.list_projects() == []

    def test_create_and_list(self, pm):
        pm.create_project("Proj A", WorkflowType.MIGRATION, "Description A")
        pm.create_project("Proj B", WorkflowType.ACCOUNT_EXPLORER)
        projects = pm.list_projects()
        assert len(projects) == 2
        names = {p.name for p in projects}
        assert names == {"Proj A", "Proj B"}

    def test_create_folder_structure(self, pm):
        config = pm.create_project("Structure Test", WorkflowType.JOBS_AS_CODE)
        path = pm.get_project_path(config.slug)
        assert (path / "project.json").exists()
        assert (path / ".gitignore").exists()
        assert (path / "logs").is_dir()
        assert (path / "outputs" / "source").is_dir()
        assert (path / "outputs" / "target").is_dir()
        assert (path / "outputs" / "normalized").is_dir()

    def test_create_duplicate_rejected(self, pm):
        pm.create_project("Dup Test", WorkflowType.MIGRATION)
        with pytest.raises(ValueError, match="already exists"):
            pm.create_project("Dup Test", WorkflowType.MIGRATION)

    def test_create_empty_slug_rejected(self, pm):
        with pytest.raises(ValueError, match="empty slug"):
            pm.create_project("@#$%", WorkflowType.MIGRATION)

    def test_load_nonexistent(self, pm):
        with pytest.raises(FileNotFoundError):
            pm.load_project("nonexistent")

    def test_load_no_state(self, pm):
        pm.create_project("No State", WorkflowType.ACCOUNT_EXPLORER)
        config, state = pm.load_project("no-state")
        assert config.name == "No State"
        assert state is None

    def test_save_and_load(self, pm, full_state):
        config = pm.create_project("Full", WorkflowType.MIGRATION)
        full_state.active_project = config.slug
        pm.save_project(config.slug, full_state)

        loaded_config, loaded_state = pm.load_project(config.slug)
        assert loaded_state is not None
        assert loaded_state.deploy.configure_complete is True
        assert loaded_state.map.selected_entities == full_state.map.selected_entities

    def test_delete(self, pm):
        pm.create_project("To Delete", WorkflowType.MIGRATION)
        assert pm.project_exists("to-delete")
        pm.delete_project("to-delete")
        assert not pm.project_exists("to-delete")

    def test_delete_nonexistent_no_error(self, pm):
        pm.delete_project("nonexistent")  # Should not raise

    def test_project_exists(self, pm):
        assert not pm.project_exists("nope")
        pm.create_project("Exists", WorkflowType.MIGRATION)
        assert pm.project_exists("exists")

    def test_all_workflow_types(self, pm):
        """Test creation with ALL 4 workflow types (per 41.02 Section 10)."""
        for wt in WorkflowType:
            pm.create_project(f"Project {wt.value}", wt)
        projects = pm.list_projects()
        types = {p.workflow_type for p in projects}
        assert types == set(WorkflowType)


class TestProjectConfig:
    def test_serialization_round_trip(self):
        config = ProjectConfig(
            name="Test",
            slug="test",
            workflow_type=WorkflowType.MIGRATION,
            description="A test project",
            source_host="cloud.getdbt.com",
            source_account_id=12345,
            target_host="emea.dbt.com",
            target_account_id=67890,
        )
        d = config.to_dict()
        restored = ProjectConfig.from_dict(d)
        assert restored.name == "Test"
        assert restored.workflow_type == WorkflowType.MIGRATION
        assert restored.source_host == "cloud.getdbt.com"
        assert restored.source_account_id == 12345
        assert restored.target_account_id == 67890
        assert isinstance(restored.created_at, datetime)
        assert isinstance(restored.updated_at, datetime)

    def test_output_config_round_trip(self):
        oc = OutputConfig(source_dir="custom/source/", use_timestamps=False)
        d = oc.to_dict()
        restored = OutputConfig.from_dict(d)
        assert restored.source_dir == "custom/source/"
        assert restored.use_timestamps is False


class TestGitignoreTemplate:
    """Verify gitignore template content (FR-43)."""

    def test_template_includes_required_entries(self, pm):
        config = pm.create_project("Gitignore Test", WorkflowType.MIGRATION)
        path = pm.get_project_path(config.slug) / ".gitignore"
        content = path.read_text()
        assert "source.env" in content
        assert "target.env" in content
        assert ".env.source" in content
        assert ".env.target" in content
        assert "state.json" in content
        assert "logs/" in content
        assert "outputs/" in content

    def test_template_has_comment_header(self, pm):
        config = pm.create_project("Header Test", WorkflowType.MIGRATION)
        path = pm.get_project_path(config.slug) / ".gitignore"
        content = path.read_text()
        assert "defense-in-depth" in content.lower()


class TestAccountSummarySync:
    def test_update_account_summary(self, pm):
        config = pm.create_project("Summary Test", WorkflowType.MIGRATION)
        state = AppState()
        state.source_credentials.host_url = "https://cloud.getdbt.com"
        state.source_credentials.account_id = "12345"
        state.target_credentials.host_url = "https://emea.dbt.com"
        state.target_credentials.account_id = "67890"

        pm.update_account_summary(config.slug, state)

        # Reload and verify
        reloaded_config, _ = pm.load_project(config.slug)
        assert reloaded_config.source_host == "https://cloud.getdbt.com"
        assert reloaded_config.source_account_id == 12345
        assert reloaded_config.target_host == "https://emea.dbt.com"
        assert reloaded_config.target_account_id == 67890


# ===========================================================================
# Backward Compatibility
# ===========================================================================

class TestBackwardCompatibility:
    """Loading state.json from older versions (missing new fields) uses defaults."""

    def test_empty_dict(self):
        """Completely empty dict should produce a valid AppState with all defaults."""
        state = AppState.from_dict({})
        assert state.active_project is None
        assert state.project_path is None
        assert state.map.selected_entities == set()
        assert state.map.include_groups is False
        assert state.map.cloned_resources == []
        assert state.deploy.configure_complete is False
        assert state.deploy.import_results == []
        assert state.jobs_as_code.project_mappings == []
        assert state.data_quality_warnings == {}

    def test_legacy_state_no_project_fields(self):
        """State from before project management was added."""
        legacy = {
            "current_step": 1,
            "workflow": "migration",
            "theme": "dark",
            "map": {
                "scope_mode": "all_projects",
                "confirmed_mappings": [{"source": "PRJ-1", "target": "PRJ-10"}],
            },
            "deploy": {
                "import_mode": "modern",
                "files_generated": True,
            },
        }
        state = AppState.from_dict(legacy)
        assert state.active_project is None
        assert state.map.confirmed_mappings == [{"source": "PRJ-1", "target": "PRJ-10"}]
        assert state.deploy.files_generated is True
        # New Tier 1 fields should have defaults
        assert state.deploy.configure_complete is False
        assert state.deploy.disable_job_triggers is False
        assert state.map.selected_entities == set()

    def test_corrupted_token_type(self):
        """Handle corrupted token_type values gracefully."""
        data = {
            "source_credentials": {"token_type": {"value": "service_token"}},
            "target_credentials": {"token_type": "invalid_type"},
        }
        state = AppState.from_dict(data)
        assert state.source_credentials.token_type == "service_token"
        assert state.target_credentials.token_type == "service_token"


# ===========================================================================
# Full Lifecycle Integration
# ===========================================================================

class TestProjectLifecycle:
    def test_create_save_load_delete(self, pm, full_state):
        """Full lifecycle: create → save state → load → verify → delete."""
        config = pm.create_project("Lifecycle", WorkflowType.MIGRATION, "Full test")
        full_state.active_project = config.slug

        pm.save_project(config.slug, full_state)

        loaded_config, loaded_state = pm.load_project(config.slug)
        assert loaded_config.name == "Lifecycle"
        assert loaded_state is not None
        assert loaded_state.active_project == config.slug
        assert loaded_state.deploy.configure_complete is True
        assert len(loaded_state.deploy.import_results) == 2
        assert "Plan: 3 to add" in loaded_state.deploy.last_plan_output

        pm.delete_project(config.slug)
        assert not pm.project_exists(config.slug)

    def test_cross_project_isolation(self, pm):
        """Verify state is isolated between projects."""
        pm.create_project("Project A", WorkflowType.MIGRATION)
        pm.create_project("Project B", WorkflowType.MIGRATION)

        state_a = AppState()
        state_a.map.protected_resources = {"PRJ-1"}
        state_a.deploy.disable_job_triggers = True
        pm.save_project("project-a", state_a)

        state_b = AppState()
        state_b.map.protected_resources = {"PRJ-2"}
        state_b.deploy.disable_job_triggers = False
        pm.save_project("project-b", state_b)

        _, loaded_a = pm.load_project("project-a")
        _, loaded_b = pm.load_project("project-b")
        assert loaded_a.map.protected_resources == {"PRJ-1"}
        assert loaded_b.map.protected_resources == {"PRJ-2"}
        assert loaded_a.deploy.disable_job_triggers is True
        assert loaded_b.deploy.disable_job_triggers is False

    def test_credential_import_from_env(self, pm, tmp_dir):
        """Test importing credentials from a .env file."""
        config = pm.create_project("Cred Import", WorkflowType.MIGRATION)

        env_file = tmp_dir / "test.env"
        env_file.write_text(
            "DBT_SOURCE_API_TOKEN=src_tok123\n"
            "DBT_SOURCE_ACCOUNT_ID=12345\n"
            "DBT_TARGET_API_TOKEN=tgt_tok456\n"
            "DBT_TARGET_ACCOUNT_ID=67890\n"
        )

        pm.import_credentials(config.slug, str(env_file))

        proj_path = pm.get_project_path(config.slug)
        assert (proj_path / "source.env").exists()
        assert (proj_path / "target.env").exists()
        source_content = (proj_path / "source.env").read_text()
        assert "src_tok123" in source_content
