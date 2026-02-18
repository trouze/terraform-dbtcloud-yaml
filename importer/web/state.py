"""Session state management for the web UI."""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from importer.web.utils.protection_intent import ProtectionIntentManager
    from importer.web.utils.target_intent import TargetIntentManager, TargetIntentResult


class WorkflowStep(IntEnum):
    """Workflow steps in order."""

    HOME = 0
    FETCH_SOURCE = 1
    EXPLORE_SOURCE = 2
    SCOPE = 3
    FETCH_TARGET = 4
    EXPLORE_TARGET = 5
    MATCH = 6
    CONFIGURE = 7
    TARGET_CREDENTIALS = 8  # Target credentials (connections + environment credentials)
    DEPLOY = 9
    DESTROY = 10
    # Jobs as Code Generator steps
    JAC_SELECT = 11  # Select sub-workflow: Adopt vs Clone
    JAC_FETCH = 12   # Fetch jobs from source
    JAC_JOBS = 13    # Select jobs
    JAC_TARGET = 14  # Configure target (Clone only)
    JAC_MAPPING = 15 # Map environments/projects (Clone only)
    JAC_CONFIG = 16  # Configure jobs (rename, triggers)
    JAC_GENERATE = 17  # Preview and export
    # Utilities
    UTILITIES = 18  # Protection intent management and utilities
    # Adoption step (between Match and Configure in Migration workflow)
    ADOPT = 19  # Automated terraform state rm + import for adopted resources


class WorkflowType(str, Enum):
    """Supported workflows."""

    MIGRATION = "migration"
    ACCOUNT_EXPLORER = "account_explorer"
    JOBS_AS_CODE = "jobs_as_code"
    IMPORT_ADOPT = "import_adopt"


STEP_NAMES = {
    WorkflowStep.HOME: "Home",
    WorkflowStep.FETCH_SOURCE: "Fetch Source",
    WorkflowStep.EXPLORE_SOURCE: "Explore Source",
    WorkflowStep.SCOPE: "Select Source",
    WorkflowStep.FETCH_TARGET: "Fetch Target",
    WorkflowStep.EXPLORE_TARGET: "Explore Target",
    WorkflowStep.MATCH: "Set Target Intent",
    WorkflowStep.CONFIGURE: "Configure Migration",
    WorkflowStep.TARGET_CREDENTIALS: "Target Credentials",
    WorkflowStep.DEPLOY: "Deploy",
    WorkflowStep.DESTROY: "Destroy Target Resources",
    # Jobs as Code Generator steps
    WorkflowStep.JAC_SELECT: "Select Workflow",
    WorkflowStep.JAC_FETCH: "Fetch Jobs",
    WorkflowStep.JAC_JOBS: "Select Jobs",
    WorkflowStep.JAC_TARGET: "Target Account",
    WorkflowStep.JAC_MAPPING: "Map Resources",
    WorkflowStep.JAC_CONFIG: "Configure Jobs",
    WorkflowStep.JAC_GENERATE: "Generate YAML",
    # Utilities
    WorkflowStep.UTILITIES: "Protection Management",
    # Adoption step
    WorkflowStep.ADOPT: "Adopt Resources",
}

STEP_ICONS = {
    WorkflowStep.HOME: "home",
    WorkflowStep.FETCH_SOURCE: "cloud_download",
    WorkflowStep.EXPLORE_SOURCE: "search",
    WorkflowStep.SCOPE: "tune",
    WorkflowStep.FETCH_TARGET: "cloud_download",
    WorkflowStep.EXPLORE_TARGET: "manage_search",
    WorkflowStep.MATCH: "assignment",
    WorkflowStep.CONFIGURE: "settings",
    WorkflowStep.TARGET_CREDENTIALS: "key",
    WorkflowStep.DEPLOY: "rocket_launch",
    WorkflowStep.DESTROY: "delete_forever",
    # Jobs as Code Generator steps
    WorkflowStep.JAC_SELECT: "alt_route",
    WorkflowStep.JAC_FETCH: "cloud_download",
    WorkflowStep.JAC_JOBS: "checklist",
    WorkflowStep.JAC_TARGET: "flight_land",
    WorkflowStep.JAC_MAPPING: "swap_horiz",
    WorkflowStep.JAC_CONFIG: "tune",
    WorkflowStep.JAC_GENERATE: "code",
    # Utilities
    WorkflowStep.UTILITIES: "security",
    # Adoption step
    WorkflowStep.ADOPT: "download_for_offline",
}


WORKFLOW_LABELS = {
    WorkflowType.MIGRATION: "Migration Workflow",
    WorkflowType.ACCOUNT_EXPLORER: "Account Explorer",
    WorkflowType.JOBS_AS_CODE: "Jobs as Code Generator",
    WorkflowType.IMPORT_ADOPT: "Import & Adopt",
}

WORKFLOW_STEPS = {
    WorkflowType.MIGRATION: [
        WorkflowStep.FETCH_SOURCE,
        WorkflowStep.EXPLORE_SOURCE,
        WorkflowStep.SCOPE,
        WorkflowStep.FETCH_TARGET,
        WorkflowStep.EXPLORE_TARGET,
        WorkflowStep.MATCH,
        WorkflowStep.ADOPT,
        WorkflowStep.CONFIGURE,
        WorkflowStep.TARGET_CREDENTIALS,
        WorkflowStep.DEPLOY,
    ],
    WorkflowType.ACCOUNT_EXPLORER: [
        WorkflowStep.FETCH_SOURCE,
        WorkflowStep.EXPLORE_SOURCE,
    ],
    WorkflowType.JOBS_AS_CODE: [
        WorkflowStep.JAC_SELECT,
        WorkflowStep.JAC_FETCH,
        WorkflowStep.JAC_JOBS,
        WorkflowStep.JAC_CONFIG,
        WorkflowStep.JAC_GENERATE,
    ],
    WorkflowType.IMPORT_ADOPT: [
        WorkflowStep.FETCH_SOURCE,
        WorkflowStep.EXPLORE_SOURCE,
        WorkflowStep.SCOPE,
        WorkflowStep.FETCH_TARGET,
        WorkflowStep.EXPLORE_TARGET,
        WorkflowStep.MATCH,
        WorkflowStep.ADOPT,
        WorkflowStep.CONFIGURE,
        WorkflowStep.TARGET_CREDENTIALS,
        WorkflowStep.DEPLOY,
    ],
}

# Utility steps shown in sidebar but not numbered (available after deploy)
WORKFLOW_UTILITIES = {
    WorkflowType.MIGRATION: [WorkflowStep.UTILITIES, WorkflowStep.DESTROY],
    WorkflowType.IMPORT_ADOPT: [WorkflowStep.UTILITIES, WorkflowStep.DESTROY],
}

# No workflow-specific name overrides needed - all steps have descriptive names now
WORKFLOW_STEP_NAMES: dict = {}


@dataclass
class AccountInfo:
    """Information about a dbt Cloud account."""

    account_id: str = ""
    account_name: str = ""
    host_url: str = "https://cloud.getdbt.com"
    is_configured: bool = False
    is_verified: bool = False  # True if we've successfully fetched account info


@dataclass
class SourceCredentials:
    """Source dbt Cloud account credentials."""

    host_url: str = "https://cloud.getdbt.com"
    account_id: str = ""
    api_token: str = ""
    token_type: str = "service_token"  # or "user_token" - auto-detected from prefix

    def is_complete(self) -> bool:
        """Check if all required fields are filled."""
        return bool(self.host_url and self.account_id and self.api_token)


@dataclass
class TargetCredentials:
    """Target dbt Cloud account credentials."""

    host_url: str = "https://cloud.getdbt.com"
    account_id: str = ""
    api_token: str = ""
    token_type: str = "service_token"  # or "user_token"

    def is_complete(self) -> bool:
        """Check if all required fields are filled."""
        return bool(self.host_url and self.account_id and self.api_token)


@dataclass
class FetchState:
    """State for the source fetch step."""

    output_dir: str = "dev_support/samples"
    auto_timestamp: bool = True
    threads: int = 50
    is_fetching: bool = False
    fetch_complete: bool = False
    last_fetch_file: Optional[str] = None
    last_summary_file: Optional[str] = None
    last_report_file: Optional[str] = None
    last_report_items_file: Optional[str] = None
    account_name: Optional[str] = None
    resource_counts: dict = field(default_factory=dict)


@dataclass
class TargetFetchState:
    """State for the target fetch step (fetching existing target infrastructure)."""

    output_dir: str = "dev_support/samples/target"
    auto_timestamp: bool = True
    threads: int = 50
    is_fetching: bool = False
    fetch_complete: bool = False
    last_fetch_file: Optional[str] = None
    last_summary_file: Optional[str] = None
    last_report_file: Optional[str] = None
    last_report_items_file: Optional[str] = None
    account_name: Optional[str] = None
    resource_counts: dict = field(default_factory=dict)
    # Path to the normalized YAML produced from target fetch data (all projects, no exclusions)
    target_baseline_yaml: Optional[str] = None
    # Post-apply staleness tracking
    is_stale: bool = False
    stale_reason: str = ""
    stale_marked_at: Optional[str] = None

    def mark_stale(self, reason: str) -> None:
        """Mark the target snapshot as stale after a destructive action like apply."""
        from datetime import datetime, timezone
        self.is_stale = True
        self.stale_reason = reason
        self.stale_marked_at = datetime.now(timezone.utc).isoformat()
        self.fetch_complete = False

    def clear_stale(self) -> None:
        """Clear staleness flags after a successful target re-fetch."""
        self.is_stale = False
        self.stale_reason = ""
        self.stale_marked_at = None


class FetchMode(str, Enum):
    """Active fetch mode - source or target."""
    
    SOURCE = "source"
    TARGET = "target"


@dataclass
class ExploreState:
    """State for the explore step."""

    report_items: list = field(default_factory=list)
    selected_type_filter: str = "all"
    search_query: str = ""
    # Column visibility settings (field names that are visible)
    visible_columns: list = field(default_factory=lambda: [
        "element_type_code", "name", "project_name", "key", "dbt_id",
        "include_in_conversion", "line_item_number"
    ])


@dataclass
class CloneConfig:
    """Configuration for cloning a resource."""
    
    source_key: str = ""  # Key of the source resource to clone
    new_name: str = ""  # Name for the cloned resource
    include_dependents: list = field(default_factory=list)  # Keys of dependents to include
    dependent_names: dict = field(default_factory=dict)  # source_key -> new_name for dependents
    include_env_values: bool = True  # Whether to copy environment variable values
    include_triggers: bool = False  # Whether to copy job triggers/schedules
    include_credentials: bool = False  # Whether to copy connection credentials

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "source_key": self.source_key,
            "new_name": self.new_name,
            "include_dependents": list(self.include_dependents),
            "dependent_names": dict(self.dependent_names),
            "include_env_values": self.include_env_values,
            "include_triggers": self.include_triggers,
            "include_credentials": self.include_credentials,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CloneConfig":
        """Create from dictionary."""
        return cls(
            source_key=data.get("source_key", ""),
            new_name=data.get("new_name", ""),
            include_dependents=data.get("include_dependents", []),
            dependent_names=data.get("dependent_names", {}),
            include_env_values=data.get("include_env_values", True),
            include_triggers=data.get("include_triggers", False),
            include_credentials=data.get("include_credentials", False),
        )


@dataclass
class EnvironmentCredentialConfig:
    """Configuration for credentials of a single environment.
    
    Stores the credential configuration for a target environment that will be
    migrated. Each environment has its own credential type (based on its connection
    type) and can either use real credentials or dummy placeholder values.
    """
    
    env_id: str = ""  # Environment ID (from source or target)
    env_name: str = ""  # Environment name for display
    project_id: str = ""  # Project ID this environment belongs to
    project_name: str = ""  # Project name for display
    connection_type: str = ""  # Connection/adapter type (e.g., 'snowflake', 'databricks')
    credential_type: str = ""  # Credential schema type key
    
    # Environment metadata
    env_type: str = ""  # 'development' or 'deployment'
    deployment_type: str = ""  # 'production', 'staging', or empty
    dbt_version: str = ""  # dbt version for the environment
    custom_branch: str = ""  # Custom branch if set
    
    # Credential values (field_name -> value)
    credential_values: dict = field(default_factory=dict)
    
    # Source values from YAML (for pre-fill, e.g., schema, database from connection/credential)
    source_values: dict = field(default_factory=dict)
    
    # Dummy credentials toggle
    use_dummy_credentials: bool = False
    
    # Real values backup (preserved when toggling to dummy, restored when toggling back)
    _real_values_backup: dict = field(default_factory=dict)
    
    # Saved state
    is_saved: bool = False  # True if saved to .env
    
    def set_use_dummy(self, use_dummy: bool) -> None:
        """Toggle between dummy and real credentials.
        
        When switching to dummy: backs up current values
        When switching to real: restores backed up values
        """
        if use_dummy and not self.use_dummy_credentials:
            # Switching to dummy - back up current values
            self._real_values_backup = dict(self.credential_values)
            self.credential_values = {}
        elif not use_dummy and self.use_dummy_credentials:
            # Switching back to real - restore backup
            if self._real_values_backup:
                self.credential_values = dict(self._real_values_backup)
        self.use_dummy_credentials = use_dummy
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "env_id": self.env_id,
            "env_name": self.env_name,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "connection_type": self.connection_type,
            "credential_type": self.credential_type,
            "env_type": self.env_type,
            "deployment_type": self.deployment_type,
            "dbt_version": self.dbt_version,
            "custom_branch": self.custom_branch,
            "credential_values": self.credential_values,
            "source_values": self.source_values,
            "use_dummy_credentials": self.use_dummy_credentials,
            "_real_values_backup": self._real_values_backup,
            "is_saved": self.is_saved,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EnvironmentCredentialConfig":
        """Create from dictionary."""
        config = cls(
            env_id=data.get("env_id", ""),
            env_name=data.get("env_name", ""),
            project_id=data.get("project_id", ""),
            project_name=data.get("project_name", ""),
            connection_type=data.get("connection_type", ""),
            credential_type=data.get("credential_type", ""),
            env_type=data.get("env_type", ""),
            deployment_type=data.get("deployment_type", ""),
            dbt_version=data.get("dbt_version", ""),
            custom_branch=data.get("custom_branch", ""),
            credential_values=data.get("credential_values", {}),
            source_values=data.get("source_values", {}),
            use_dummy_credentials=data.get("use_dummy_credentials", False),
            is_saved=data.get("is_saved", False),
        )
        config._real_values_backup = data.get("_real_values_backup", {})
        return config


@dataclass
class EnvironmentCredentialsState:
    """State for the environment credentials configuration step.
    
    Tracks credential configurations for all selected target environments.
    """
    
    # Per-environment credential configurations, keyed by env_id
    env_configs: dict = field(default_factory=dict)  # env_id -> EnvironmentCredentialConfig
    
    # Step completion tracking
    step_complete: bool = False
    
    # Selected environments (populated from scope/match steps)
    selected_env_ids: set = field(default_factory=set)
    
    def get_config(self, env_id: str) -> Optional["EnvironmentCredentialConfig"]:
        """Get credential config for an environment."""
        return self.env_configs.get(env_id)
    
    def set_config(self, config: "EnvironmentCredentialConfig") -> None:
        """Set credential config for an environment."""
        self.env_configs[config.env_id] = config
    
    def has_selected_environments(self) -> bool:
        """Check if there are any selected environments."""
        return len(self.selected_env_ids) > 0
    
    def all_saved(self) -> bool:
        """Check if all selected environments have been saved."""
        if not self.selected_env_ids:
            return True  # No environments = nothing to save = complete
        for env_id in self.selected_env_ids:
            config = self.env_configs.get(env_id)
            if config and not config.is_saved:
                return False
        return True
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "env_configs": {
                env_id: config.to_dict()
                for env_id, config in self.env_configs.items()
            },
            "step_complete": self.step_complete,
            "selected_env_ids": list(self.selected_env_ids),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EnvironmentCredentialsState":
        """Create from dictionary."""
        state = cls()
        state.step_complete = data.get("step_complete", False)
        state.selected_env_ids = set(data.get("selected_env_ids", []))
        
        env_configs_data = data.get("env_configs", {})
        for env_id, config_data in env_configs_data.items():
            state.env_configs[env_id] = EnvironmentCredentialConfig.from_dict(config_data)
        
        return state


@dataclass
class MapState:
    """State for the map step."""

    selected_entities: set = field(default_factory=set)  # element_mapping_ids
    scope_mode: str = "all_projects"
    selected_project_ids: list = field(default_factory=list)
    resource_filters: dict = field(
        default_factory=lambda: {
            "connections": True,
            "repositories": True,
            "service_tokens": True,
            "groups": True,
            "notifications": True,
            "webhooks": False,
            "privatelink_endpoints": True,
            "projects": True,
            "environments": True,
            "jobs": True,
            "environment_variables": True,
        }
    )
    normalization_options: dict = field(
        default_factory=lambda: {
            "strip_source_ids": True,
            "secret_handling": "redact",
            "name_collision_strategy": "suffix",
        }
    )
    # Selection tracking
    selections_loaded: bool = False
    selection_counts: dict = field(default_factory=lambda: {"selected": 0, "total": 0})
    
    # View filter state (persisted across reloads)
    type_filter: str = "all"
    selected_only_filter: bool = False
    
    # Auto-cascade setting
    auto_cascade_children: bool = False
    
    # Global resource inclusion toggles (for Apply Scope Selection)
    include_groups: bool = False
    include_notifications: bool = False
    include_service_tokens: bool = False
    include_webhooks: bool = False
    include_privatelink: bool = False
    
    # Removal intent: resource keys flagged for removal from TF state (future UI)
    removal_keys: set = field(default_factory=set)
    
    # Target-only visibility: when True, target-only rows are visible in the grid
    show_target_only: bool = True
    
    # Target-only exclusive: when True, show ONLY target-only rows (hide everything else)
    target_only_exclusive: bool = False
    
    # Scope visibility filter: when True, only show rows related to source scope
    show_scope_only: bool = False

    # Normalization state
    normalize_running: bool = False
    normalize_complete: bool = False
    normalize_error: Optional[str] = None
    last_yaml_file: Optional[str] = None
    last_lookups_file: Optional[str] = None
    last_exclusions_file: Optional[str] = None
    lookups_count: int = 0
    exclusions_count: int = 0
    
    # Target resource matching state
    target_matching_enabled: bool = False
    suggested_matches: list = field(default_factory=list)  # Auto-generated match suggestions
    confirmed_mappings: list = field(default_factory=list)  # User-confirmed mappings
    rejected_suggestions: set = field(default_factory=set)  # Source keys user rejected
    mapping_file_path: Optional[str] = None
    mapping_file_valid: bool = False
    mapping_validation_errors: list = field(default_factory=list)
    
    # Resource protection state
    # Set of source_keys for resources marked as protected
    # When protecting a resource, its ancestors (parents) are also automatically protected
    protected_resources: set = field(default_factory=set)
    
    # Set of resource_keys that the user has unprotected via the Destroy page
    # These will be filtered out from the Protected Resources panel
    unprotected_keys: set = field(default_factory=set)
    
    # Resource cloning state
    cloned_resources: list = field(default_factory=list)  # List of CloneConfig
    
    # Protection fix state - tracks pending protection moves.tf changes for undo
    protection_fix_pending: bool = False
    protection_fix_file_path: str = ""
    protection_fix_previous_content: str = ""
    protection_fix_action: str = ""  # "protect" or "unprotect"
    # Backup of protection sets before fix was applied (for undo)
    protection_fix_backup_protected: set = field(default_factory=set)
    protection_fix_backup_unprotected: set = field(default_factory=set)


@dataclass
class ImportResult:
    """Result of a single resource import operation."""
    
    resource_address: str = ""
    target_id: str = ""
    source_key: str = ""
    resource_type: str = ""
    status: str = "pending"  # "pending", "importing", "success", "failed"
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "resource_address": self.resource_address,
            "target_id": self.target_id,
            "source_key": self.source_key,
            "resource_type": self.resource_type,
            "status": self.status,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImportResult":
        """Create from dictionary."""
        return cls(
            resource_address=data.get("resource_address", ""),
            target_id=data.get("target_id", ""),
            source_key=data.get("source_key", ""),
            resource_type=data.get("resource_type", ""),
            status=data.get("status", "pending"),
            error_message=data.get("error_message"),
            duration_ms=data.get("duration_ms"),
        )


@dataclass
class DeployState:
    """State for the deploy step."""

    connection_configs: dict = field(default_factory=dict)
    configure_complete: bool = False  # Set when user proceeds from Configure to Deploy
    files_generated: bool = False
    terraform_dir: str = ""  # Path to terraform output directory
    last_generate_output: str = ""  # Output from generate step
    terraform_initialized: bool = False
    last_init_output: str = ""  # Output from terraform init
    last_validate_success: bool = False
    last_validate_output: str = ""  # Output from terraform validate
    last_plan_success: bool = False
    last_plan_output: str = ""
    apply_complete: bool = False
    last_apply_output: str = ""  # Output from terraform apply
    apply_results: Optional[dict] = None
    destroy_complete: bool = False
    
    # Resource import state
    import_results: list = field(default_factory=list)  # List of ImportResult
    import_completed: bool = False
    import_mode: str = "modern"  # "modern" (TF 1.5+ import blocks) or "legacy"
    terraform_version: Optional[str] = None
    imports_file_generated: bool = False
    last_import_output: str = ""
    
    # Job trigger control
    disable_job_triggers: bool = False  # When True, sets all job triggers to false in generated YAML
    
    # Protection tracking
    previous_yaml_file: Optional[str] = None  # Path to previous YAML for detecting protection changes
    
    # State reconciliation / drift detection
    reconcile_state_loaded: bool = False  # True after terraform show -json succeeds
    reconcile_state_resources: list = field(default_factory=list)  # Parsed state resources
    reconcile_drift_results: list = field(default_factory=list)  # Drift detection results
    reconcile_adopt_selections: list = field(default_factory=list)  # Resource addresses selected for adoption
    reconcile_imports_generated: bool = False  # True after imports.tf generated for reconciliation
    reconcile_adopt_rows: list = field(default_factory=list)  # Full grid row data for adopted resources (includes target_id, source_type, etc.)
    reconcile_execution_logs: list = field(default_factory=list)  # Execution logs: [(timestamp, cmd, success, output, cwd), ...]
    
    # Adopt step state (PRD 43.02)
    adopt_step_complete: bool = False  # True after adopt step finishes or is skipped
    adopt_step_skipped: bool = False  # True if user clicked "Skip"
    adopt_step_running: bool = False  # True while execution is in progress
    adopt_step_status: str = ""  # "idle", "backup", "state_rm", "write_imports", "init", "apply", "verify", "complete", "failed"
    adopt_step_backup_path: str = ""  # Path to terraform.tfstate.adopt-backup
    adopt_step_last_output: str = ""  # Last execution output for display
    adopt_step_error: str = ""  # Error message if failed
    adopt_step_imported_count: int = 0  # Actual number of resources imported (from TF apply output)

    def has_state_file(self) -> bool:
        """Check if a Terraform state file exists.
        
        Checks the configured terraform_dir (or default deployments/migration).
        Uses absolute paths based on project root.
        """
        from pathlib import Path
        
        # Get the project root (terraform-dbtcloud-yaml directory)
        project_root = Path(__file__).parent.parent.parent.resolve()
        
        # Determine the terraform directory to check
        tf_dir = self.terraform_dir if self.terraform_dir else "deployments/migration"
        
        # Make path absolute if needed
        tf_path = Path(tf_dir)
        if not tf_path.is_absolute():
            tf_path = project_root / tf_path
        
        state_path = tf_path / "terraform.tfstate"
        return state_path.exists()
    
    def has_pending_imports(self) -> bool:
        """Check if there are mappings that need to be imported."""
        return len(self.import_results) > 0 and not self.import_completed


class JACSubWorkflow(str, Enum):
    """Jobs as Code sub-workflow types."""
    
    ADOPT = "adopt"  # Take existing jobs under jobs-as-code management
    CLONE = "clone"  # Clone/migrate jobs to different environment


class JACOutputFormat(str, Enum):
    """Output format options for Jobs as Code generation."""
    
    TEMPLATED = "templated"  # Use Jinja variables
    HARDCODED = "hardcoded"  # Use actual IDs


@dataclass
class JACJobConfig:
    """Configuration for a single job in Jobs as Code workflow."""
    
    job_id: int = 0
    original_name: str = ""
    new_name: str = ""  # For clone workflow
    identifier: str = ""  # YAML key identifier
    selected: bool = True
    is_managed: bool = False  # Already has [[identifier]] in name


@dataclass
class JACProjectMapping:
    """Mapping from source project to target project."""
    
    source_id: int = 0
    source_name: str = ""
    target_id: Optional[int] = None
    target_name: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "target_id": self.target_id,
            "target_name": self.target_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JACProjectMapping":
        """Create from dictionary."""
        return cls(
            source_id=data.get("source_id", 0),
            source_name=data.get("source_name", ""),
            target_id=data.get("target_id"),
            target_name=data.get("target_name", ""),
        )


@dataclass
class JACEnvironmentMapping:
    """Mapping from source environment to target environment."""
    
    source_id: int = 0
    source_name: str = ""
    source_project_id: int = 0
    target_id: Optional[int] = None
    target_name: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_project_id": self.source_project_id,
            "target_id": self.target_id,
            "target_name": self.target_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JACEnvironmentMapping":
        """Create from dictionary."""
        return cls(
            source_id=data.get("source_id", 0),
            source_name=data.get("source_name", ""),
            source_project_id=data.get("source_project_id", 0),
            target_id=data.get("target_id"),
            target_name=data.get("target_name", ""),
        )


@dataclass
class JobsAsCodeState:
    """State for the Jobs as Code Generator workflow."""
    
    # Sub-workflow selection
    sub_workflow: JACSubWorkflow = JACSubWorkflow.ADOPT
    
    # Source data
    source_jobs: list = field(default_factory=list)  # List of job dicts from API
    source_projects: dict = field(default_factory=dict)  # project_id -> project_name
    source_environments: dict = field(default_factory=dict)  # env_id -> env_name
    
    # Job selection and configuration
    job_configs: list = field(default_factory=list)  # List of JACJobConfig
    selected_job_ids: set = field(default_factory=set)
    
    # Fetch state
    is_fetching: bool = False
    fetch_complete: bool = False
    fetch_error: Optional[str] = None
    
    # Target data (clone workflow only)
    target_same_account: bool = True
    target_jobs: list = field(default_factory=list)
    target_projects: dict = field(default_factory=dict)  # project_id -> project_name  
    target_environments: dict = field(default_factory=dict)  # env_id -> env_name
    target_fetch_complete: bool = False
    
    # Mapping (clone workflow only)
    project_mappings: list = field(default_factory=list)  # List of JACProjectMapping
    environment_mappings: list = field(default_factory=list)  # List of JACEnvironmentMapping
    
    # Trigger settings (clone workflow)
    disable_schedule: bool = True
    disable_github_webhook: bool = True
    disable_git_provider_webhook: bool = True
    disable_on_merge: bool = True
    
    # Output format
    output_format: JACOutputFormat = JACOutputFormat.HARDCODED
    variable_prefix: str = ""  # e.g., "prod_" for {{ prod_project_id }}
    
    # Generation state
    generated_yaml: str = ""
    generated_vars_yaml: str = ""  # For templated output
    generation_complete: bool = False
    validation_errors: list = field(default_factory=list)
    
    # Identifier warnings (auto-renamed duplicates)
    identifier_warnings: list = field(default_factory=list)  # List of warning strings
    
    # Bulk rename settings
    name_prefix: str = ""
    name_suffix: str = ""


@dataclass
class AppState:
    """Complete application state."""

    current_step: WorkflowStep = WorkflowStep.HOME
    theme: str = "dark"  # "dark" or "light"
    workflow: WorkflowType = WorkflowType.MIGRATION
    is_migration_licensed: bool = False
    license_tier: str = "explorer"  # LicenseTier value: explorer, solutions_architect, resident_architect, engineering
    license_email: str = ""
    license_message: str = ""

    source_credentials: SourceCredentials = field(default_factory=SourceCredentials)
    target_credentials: TargetCredentials = field(default_factory=TargetCredentials)

    # Account info (populated from .env and API calls)
    source_account: AccountInfo = field(default_factory=AccountInfo)
    target_account: AccountInfo = field(default_factory=AccountInfo)

    # Source fetch state (primary)
    fetch: FetchState = field(default_factory=FetchState)
    # Target fetch state (for matching existing infrastructure)
    target_fetch: TargetFetchState = field(default_factory=TargetFetchState)
    # Active fetch mode (which credentials/output to use)
    active_fetch_mode: FetchMode = FetchMode.SOURCE
    
    explore: ExploreState = field(default_factory=ExploreState)
    map: MapState = field(default_factory=MapState)
    deploy: DeployState = field(default_factory=DeployState)
    
    # Environment credentials state
    env_credentials: EnvironmentCredentialsState = field(default_factory=EnvironmentCredentialsState)
    
    # Jobs as Code Generator state
    jobs_as_code: JobsAsCodeState = field(default_factory=JobsAsCodeState)

    # Raw account data from fetch
    account_data: Optional[dict] = None
    # Raw target account data from target fetch
    target_account_data: Optional[dict] = None
    
    # Data quality warnings (collisions, duplicates, etc.) from normalization
    # Structure: {"source": {...}, "target": {...}}
    # Each contains: {"collisions": {namespace: [{"key": str, "count": int, "generated_keys": list}]}, ...}
    data_quality_warnings: dict = field(default_factory=dict)

    # Project management fields (US-097)
    active_project: Optional[str] = None  # Slug of the currently active project
    project_path: Optional[str] = None  # Path to the active project folder (stored as str for serialization)

    # Protection intent manager (not serialized - manages its own file)
    # This is a cached reference, initialized lazily via get_protection_intent_manager()
    _protection_intent_manager: Optional["ProtectionIntentManager"] = field(
        default=None, repr=False, compare=False
    )
    # Target intent manager (not serialized - manages target-intent.json in deployment dir)
    _target_intent_manager: Optional["TargetIntentManager"] = field(
        default=None, repr=False, compare=False
    )

    def get_protection_intent_manager(self) -> "ProtectionIntentManager":
        """Get or create the ProtectionIntentManager.
        
        The manager is initialized lazily using the deployment directory path.
        Intent file is stored at: {terraform_dir}/protection-intent.json
        
        Returns:
            ProtectionIntentManager instance (cached after first call)
        """
        if self._protection_intent_manager is None:
            from importer.web.utils.protection_intent import ProtectionIntentManager
            
            # Determine the terraform directory
            tf_dir = self.deploy.terraform_dir or "deployments/migration"
            tf_path = Path(tf_dir)
            
            # Make relative paths absolute based on project root
            if not tf_path.is_absolute():
                # Get project root (parent of importer directory)
                project_root = Path(__file__).parent.parent.parent.resolve()
                tf_path = project_root / tf_dir
            
            # Intent file is stored in the terraform directory
            intent_file = tf_path / "protection-intent.json"
            
            self._protection_intent_manager = ProtectionIntentManager(intent_file)
            self._protection_intent_manager.load()

            # Wire up callback: after protection-intent.json is saved, sync dirty keys
            # to target intent dispositions (write-through to target-intent.json)
            self._protection_intent_manager._on_intent_changed = (
                lambda key, protected: self.sync_protection_to_target_intent(key, protected)
            )
        
        return self._protection_intent_manager
    
    def save_protection_intent(self) -> None:
        """Save the protection intent file if it has been initialized.

        This is a no-op if the manager hasn't been accessed yet.
        """
        if self._protection_intent_manager is not None:
            self._protection_intent_manager.save()

    def get_target_intent_manager(self) -> "TargetIntentManager":
        """Get or create the TargetIntentManager.

        The manager is initialized lazily using the deployment directory path.
        Intent file is stored at: {terraform_dir}/target-intent.json

        Returns:
            TargetIntentManager instance (cached after first call)
        """
        if self._target_intent_manager is None:
            from importer.web.utils.target_intent import TargetIntentManager

            tf_dir = self.deploy.terraform_dir or "deployments/migration"
            tf_path = Path(tf_dir)
            if not tf_path.is_absolute():
                project_root = Path(__file__).parent.parent.parent.resolve()
                tf_path = project_root / tf_dir
            deployment_dir = tf_path
            self._target_intent_manager = TargetIntentManager(deployment_dir)
        return self._target_intent_manager

    def save_target_intent(self, intent: "TargetIntentResult") -> None:
        """Save the target intent to target-intent.json.

        Uses the target intent manager (creates it if needed). Caller provides
        the intent to persist (e.g. from Match page or Deploy generate).
        """
        self.get_target_intent_manager().save(intent)

    def sync_protection_to_target_intent(self, resource_key: str, protected: bool) -> bool:
        """Sync a protection edit to the target intent disposition.

        Called AFTER ProtectionIntentManager.set_intent() writes to protection-intent.json.
        Updates the corresponding ResourceDisposition.protected in target-intent.json.

        Returns:
            True if a disposition was found and updated, False otherwise.
        """
        return self.get_target_intent_manager().sync_protection_to_disposition(
            resource_key, protected
        )

    def step_is_complete(self, step: WorkflowStep) -> bool:
        """Check if a workflow step has been completed."""
        if step != WorkflowStep.HOME and step not in self.workflow_steps():
            return False
        if step == WorkflowStep.HOME:
            return True
        elif step == WorkflowStep.FETCH_SOURCE:
            return self.fetch.fetch_complete
        elif step == WorkflowStep.EXPLORE_SOURCE:
            return self.fetch.fetch_complete  # Can explore once fetched
        elif step == WorkflowStep.SCOPE:
            return self.map.normalize_complete
        elif step == WorkflowStep.FETCH_TARGET:
            return self.target_fetch.fetch_complete
        elif step == WorkflowStep.EXPLORE_TARGET:
            return self.target_fetch.fetch_complete
        elif step == WorkflowStep.MATCH:
            # Match is complete when mapping file is valid
            return self.map.mapping_file_valid
        elif step == WorkflowStep.CONFIGURE:
            return self.deploy.configure_complete
        elif step == WorkflowStep.TARGET_CREDENTIALS:
            return self.env_credentials.step_complete
        elif step == WorkflowStep.DEPLOY:
            return self.deploy.apply_complete
        elif step == WorkflowStep.DESTROY:
            return self.deploy.destroy_complete
        # Jobs as Code Generator steps
        elif step == WorkflowStep.JAC_SELECT:
            return True  # Always complete (just a selection)
        elif step == WorkflowStep.JAC_FETCH:
            return self.jobs_as_code.fetch_complete
        elif step == WorkflowStep.JAC_JOBS:
            return len(self.jobs_as_code.selected_job_ids) > 0
        elif step == WorkflowStep.JAC_TARGET:
            return self.jobs_as_code.target_fetch_complete
        elif step == WorkflowStep.JAC_MAPPING:
            return len(self.jobs_as_code.project_mappings) > 0
        elif step == WorkflowStep.JAC_CONFIG:
            return len(self.jobs_as_code.job_configs) > 0
        elif step == WorkflowStep.JAC_GENERATE:
            return self.jobs_as_code.generation_complete
        return False

    def step_is_accessible(self, step: WorkflowStep) -> bool:
        """Check if a workflow step can be accessed."""
        # Check if step is in workflow steps OR utility steps
        utility_steps = WORKFLOW_UTILITIES.get(self.workflow, [])
        if step != WorkflowStep.HOME and step not in self.workflow_steps() and step not in utility_steps:
            return False
        if step == WorkflowStep.HOME:
            return True
        elif step == WorkflowStep.FETCH_SOURCE:
            return True  # Always accessible
        elif step == WorkflowStep.EXPLORE_SOURCE:
            return self.fetch.fetch_complete
        elif step == WorkflowStep.SCOPE:
            return self.fetch.fetch_complete
        elif step == WorkflowStep.FETCH_TARGET:
            return True  # Always accessible - can fetch target anytime
        elif step == WorkflowStep.EXPLORE_TARGET:
            return self.target_fetch.fetch_complete
        elif step == WorkflowStep.MATCH:
            # Match requires both source scoped and target fetched
            return self.map.normalize_complete and self.target_fetch.fetch_complete
        elif step == WorkflowStep.CONFIGURE:
            # Configure requires match complete (or skip if no target resources matched)
            has_match = WorkflowStep.MATCH in self.workflow_steps()
            if has_match:
                return self.map.mapping_file_valid or len(self.map.confirmed_mappings) == 0
            return self.map.normalize_complete
        elif step == WorkflowStep.TARGET_CREDENTIALS:
            # Target credentials accessible after configure is complete
            return self.deploy.configure_complete
        elif step == WorkflowStep.DEPLOY:
            # Deploy requires env credentials step complete (or no environments selected)
            return self.env_credentials.step_complete or not self.env_credentials.has_selected_environments()
        elif step == WorkflowStep.DESTROY:
            return self.deploy.has_state_file()
        elif step == WorkflowStep.ADOPT:
            # Adopt is accessible whenever Match (Set Target Intent) is accessible
            return self.map.normalize_complete and self.target_fetch.fetch_complete
        elif step == WorkflowStep.UTILITIES:
            return True  # Always accessible - can load state, manage protection intents, etc.
        # Jobs as Code Generator steps
        elif step == WorkflowStep.JAC_SELECT:
            return True  # Always accessible
        elif step == WorkflowStep.JAC_FETCH:
            return True  # Always accessible (credentials checked on fetch)
        elif step == WorkflowStep.JAC_JOBS:
            return self.jobs_as_code.fetch_complete
        elif step == WorkflowStep.JAC_TARGET:
            # Only for clone workflow
            return (self.jobs_as_code.sub_workflow == JACSubWorkflow.CLONE 
                    and len(self.jobs_as_code.selected_job_ids) > 0)
        elif step == WorkflowStep.JAC_MAPPING:
            # Only for clone workflow
            return (self.jobs_as_code.sub_workflow == JACSubWorkflow.CLONE 
                    and self.jobs_as_code.target_fetch_complete)
        elif step == WorkflowStep.JAC_CONFIG:
            return len(self.jobs_as_code.selected_job_ids) > 0
        elif step == WorkflowStep.JAC_GENERATE:
            return len(self.jobs_as_code.job_configs) > 0
        return False

    def workflow_steps(self) -> list[WorkflowStep]:
        """Get workflow steps for the active workflow."""
        return WORKFLOW_STEPS.get(self.workflow, WORKFLOW_STEPS[WorkflowType.MIGRATION])

    def get_step_label(self, step: WorkflowStep) -> str:
        """Get the workflow-specific label for a step."""
        override = WORKFLOW_STEP_NAMES.get(self.workflow, {})
        return override.get(step, STEP_NAMES.get(step, step.name.title()))

    def get_step_number(self, step: WorkflowStep) -> Optional[int]:
        """Get the 1-based step number within the active workflow."""
        steps = self.workflow_steps()
        if step in steps:
            return steps.index(step) + 1
        return None

    def to_dict(self) -> dict:
        """Convert state to dictionary for storage.
        
        Serialization tiers (per PRD 21.02 US-098):
        - Tier 1: MUST serialize — user work, configuration, step completion
        - Tier 2: SHOULD serialize — operation logs/outputs (large text stored as
          separate files when using ProjectManager; inline otherwise)
        - Tier 3: SKIP — runtime-only, transient, or re-derivable fields
        """
        return {
            "current_step": self.current_step.value,
            "theme": self.theme,
            "workflow": self.workflow.value,
            "is_migration_licensed": self.is_migration_licensed,
            "license_tier": self.license_tier,
            "license_email": self.license_email,
            "license_message": self.license_message,
            "active_fetch_mode": self.active_fetch_mode.value,
            # Project management (US-097)
            "active_project": self.active_project,
            "project_path": self.project_path,
            "source_credentials": {
                "host_url": self.source_credentials.host_url,
                "account_id": self.source_credentials.account_id,
                # Don't persist token for security
                "token_type": self.source_credentials.token_type,  # Tier 1: was missing (FR-52)
            },
            "target_credentials": {
                "host_url": self.target_credentials.host_url,
                "account_id": self.target_credentials.account_id,
                "token_type": self.target_credentials.token_type,
            },
            "source_account": {
                "account_id": self.source_account.account_id,
                "account_name": self.source_account.account_name,
                "host_url": self.source_account.host_url,
                "is_configured": self.source_account.is_configured,
                "is_verified": self.source_account.is_verified,
            },
            "target_account": {
                "account_id": self.target_account.account_id,
                "account_name": self.target_account.account_name,
                "host_url": self.target_account.host_url,
                "is_configured": self.target_account.is_configured,
                "is_verified": self.target_account.is_verified,
            },
            "fetch": {
                "output_dir": self.fetch.output_dir,
                "auto_timestamp": self.fetch.auto_timestamp,
                "fetch_complete": self.fetch.fetch_complete,
                "last_fetch_file": self.fetch.last_fetch_file,
                "last_summary_file": self.fetch.last_summary_file,
                "last_report_file": self.fetch.last_report_file,
                "last_report_items_file": self.fetch.last_report_items_file,
                "account_name": self.fetch.account_name,
                "resource_counts": self.fetch.resource_counts,
                # Tier 3 SKIP: is_fetching (runtime flag, always starts False)
                # Tier 3 SKIP: threads (runtime config, use default)
            },
            "target_fetch": {
                "output_dir": self.target_fetch.output_dir,
                "auto_timestamp": self.target_fetch.auto_timestamp,
                "fetch_complete": self.target_fetch.fetch_complete,
                "last_fetch_file": self.target_fetch.last_fetch_file,
                "last_summary_file": self.target_fetch.last_summary_file,
                "last_report_file": self.target_fetch.last_report_file,
                "last_report_items_file": self.target_fetch.last_report_items_file,
                "account_name": self.target_fetch.account_name,
                "resource_counts": self.target_fetch.resource_counts,
                "target_baseline_yaml": self.target_fetch.target_baseline_yaml,
                # Tier 3 SKIP: is_fetching (runtime flag)
                # Tier 3 SKIP: threads (runtime config)
            },
            "explore": {
                "visible_columns": self.explore.visible_columns,
                # Tier 3 SKIP: report_items (loaded from last_report_items_file)
                # Tier 3 SKIP: selected_type_filter (minor UI filter state)
                # Tier 3 SKIP: search_query (minor UI filter state)
            },
            "map": {
                # Existing serialized fields
                "scope_mode": self.map.scope_mode,
                "selected_project_ids": self.map.selected_project_ids,
                "resource_filters": self.map.resource_filters,
                "normalization_options": self.map.normalization_options,
                "normalize_complete": self.map.normalize_complete,
                "last_yaml_file": self.map.last_yaml_file,
                "last_lookups_file": self.map.last_lookups_file,
                "last_exclusions_file": self.map.last_exclusions_file,
                "lookups_count": self.map.lookups_count,
                "exclusions_count": self.map.exclusions_count,
                # Target matching state
                "target_matching_enabled": self.map.target_matching_enabled,
                "confirmed_mappings": self.map.confirmed_mappings,
                "mapping_file_path": self.map.mapping_file_path,
                "mapping_file_valid": self.map.mapping_file_valid,
                # Resource protection state
                "protected_resources": sorted(self.map.protected_resources),
                "unprotected_keys": sorted(self.map.unprotected_keys),
                # Removal intent: keys flagged for unadoption (PRD 43.03 fix)
                "removal_keys": sorted(self.map.removal_keys),
                # Protection fix state
                "protection_fix_pending": self.map.protection_fix_pending,
                "protection_fix_file_path": self.map.protection_fix_file_path,
                "protection_fix_action": self.map.protection_fix_action,
                "protection_fix_backup_protected": sorted(self.map.protection_fix_backup_protected),
                "protection_fix_backup_unprotected": sorted(self.map.protection_fix_backup_unprotected),
                # Tier 1: User selections (FR-44)
                "selected_entities": sorted(self.map.selected_entities),
                "selections_loaded": self.map.selections_loaded,
                "selection_counts": self.map.selection_counts,
                # Tier 1: Resource type toggles (FR-45)
                "include_groups": self.map.include_groups,
                "include_notifications": self.map.include_notifications,
                "include_service_tokens": self.map.include_service_tokens,
                "include_webhooks": self.map.include_webhooks,
                "include_privatelink": self.map.include_privatelink,
                "auto_cascade_children": self.map.auto_cascade_children,
                # Tier 1: Rejected suggestions and cloned resources (FR-46)
                "rejected_suggestions": sorted(self.map.rejected_suggestions),
                "cloned_resources": [c.to_dict() for c in self.map.cloned_resources],
                # Tier 3 SKIP: normalize_running (runtime flag)
                # Tier 3 SKIP: normalize_error (transient error)
                # Tier 3 SKIP: type_filter (minor UI filter state)
                # Tier 3 SKIP: selected_only_filter (minor UI filter state)
                # Tier 3 SKIP: suggested_matches (re-generated from source+target data)
                # Tier 3 SKIP: mapping_validation_errors (re-validated on load)
                # Tier 3 SKIP: protection_fix_pending through protection_fix_backup_* (transient fix state)
                #   Note: protection_fix fields ARE serialized above for undo support
                # Tier 3 SKIP: protection_fix_previous_content (large, transient)
            },
            "deploy": {
                # Previously serialized fields
                "import_completed": self.deploy.import_completed,
                "import_mode": self.deploy.import_mode,
                "terraform_version": self.deploy.terraform_version,
                "terraform_dir": self.deploy.terraform_dir,
                "files_generated": self.deploy.files_generated,
                # Tier 1: Step completion flags (FR-37)
                "configure_complete": self.deploy.configure_complete,
                "apply_complete": self.deploy.apply_complete,
                "destroy_complete": self.deploy.destroy_complete,
                "terraform_initialized": self.deploy.terraform_initialized,
                # Tier 1: Operation success flags (FR-39)
                "last_validate_success": self.deploy.last_validate_success,
                "last_plan_success": self.deploy.last_plan_success,
                # Tier 1: User settings
                "disable_job_triggers": self.deploy.disable_job_triggers,
                "connection_configs": self.deploy.connection_configs,
                "previous_yaml_file": self.deploy.previous_yaml_file,
                "imports_file_generated": self.deploy.imports_file_generated,
                # Tier 1: Import results (FR-47)
                "import_results": [r.to_dict() for r in self.deploy.import_results],
                "apply_results": self.deploy.apply_results,
                # Tier 1: Reconcile state (FR-48)
                "reconcile_state_loaded": self.deploy.reconcile_state_loaded,
                "reconcile_state_resources": self.deploy.reconcile_state_resources,
                "reconcile_drift_results": self.deploy.reconcile_drift_results,
                "reconcile_adopt_selections": self.deploy.reconcile_adopt_selections,
                "reconcile_imports_generated": self.deploy.reconcile_imports_generated,
                "reconcile_adopt_rows": self.deploy.reconcile_adopt_rows,
                "reconcile_execution_logs": self.deploy.reconcile_execution_logs,
                # Tier 2: Operation logs (FR-40) — stored inline here, ProjectManager
                # will split to separate files in {project}/logs/ when saving to project
                "last_generate_output": self.deploy.last_generate_output,
                "last_init_output": self.deploy.last_init_output,
                "last_validate_output": self.deploy.last_validate_output,
                "last_plan_output": self.deploy.last_plan_output,
                "last_apply_output": self.deploy.last_apply_output,
                "last_import_output": self.deploy.last_import_output,
            },
            "env_credentials": self.env_credentials.to_dict(),
            "jobs_as_code": {
                "sub_workflow": self.jobs_as_code.sub_workflow.value,
                "fetch_complete": self.jobs_as_code.fetch_complete,
                "source_jobs": self.jobs_as_code.source_jobs,
                "source_projects": self.jobs_as_code.source_projects,
                "source_environments": self.jobs_as_code.source_environments,
                "selected_job_ids": sorted(self.jobs_as_code.selected_job_ids),
                "job_configs": [
                    {
                        "job_id": c.job_id,
                        "original_name": c.original_name,
                        "new_name": c.new_name,
                        "identifier": c.identifier,
                        "selected": c.selected,
                        "is_managed": c.is_managed,
                    }
                    for c in self.jobs_as_code.job_configs
                ],
                "target_same_account": self.jobs_as_code.target_same_account,
                "target_fetch_complete": self.jobs_as_code.target_fetch_complete,
                "disable_schedule": self.jobs_as_code.disable_schedule,
                "disable_github_webhook": self.jobs_as_code.disable_github_webhook,
                "disable_git_provider_webhook": self.jobs_as_code.disable_git_provider_webhook,
                "disable_on_merge": self.jobs_as_code.disable_on_merge,
                "output_format": self.jobs_as_code.output_format.value,
                "variable_prefix": self.jobs_as_code.variable_prefix,
                "generation_complete": self.jobs_as_code.generation_complete,
                "name_prefix": self.jobs_as_code.name_prefix,
                "name_suffix": self.jobs_as_code.name_suffix,
                # Tier 1: Target data and mappings (FR-49)
                "target_jobs": self.jobs_as_code.target_jobs,
                "target_projects": self.jobs_as_code.target_projects,
                "target_environments": self.jobs_as_code.target_environments,
                "project_mappings": [m.to_dict() for m in self.jobs_as_code.project_mappings],
                "environment_mappings": [m.to_dict() for m in self.jobs_as_code.environment_mappings],
                # Tier 2: Generated outputs (FR-50) — stored inline, ProjectManager
                # will split to logs/jac_generated.yaml and logs/jac_generated_vars.yaml
                "generated_yaml": self.jobs_as_code.generated_yaml,
                "generated_vars_yaml": self.jobs_as_code.generated_vars_yaml,
                # Tier 3 SKIP: is_fetching (runtime flag)
                # Tier 3 SKIP: fetch_error (transient error)
                # Tier 3 SKIP: validation_errors (re-validated on load)
                # Tier 3 SKIP: identifier_warnings (re-validated on load)
            },
            # Tier 1: Data quality warnings (FR-51)
            "data_quality_warnings": self.data_quality_warnings,
            # Tier 3 SKIP: account_data (huge raw API data; loaded from fetch.last_fetch_file)
            # Tier 3 SKIP: target_account_data (huge raw API data; loaded from target_fetch.last_fetch_file)
            # Tier 3 SKIP: _protection_intent_manager (runtime object, manages its own file)
            # Tier 3 SKIP: _target_intent_manager (runtime object, manages target-intent.json)
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppState":
        """Restore state from dictionary.
        
        Handles missing keys gracefully — uses field defaults for any key not present
        in the data dict. This ensures backward compatibility when loading state.json
        from older versions that lack newer fields.
        """
        state = cls()

        if "current_step" in data:
            state.current_step = WorkflowStep(data["current_step"])
        if "theme" in data:
            state.theme = data["theme"]
        if "workflow" in data:
            try:
                state.workflow = WorkflowType(data["workflow"])
            except Exception:
                state.workflow = WorkflowType.MIGRATION
        if "is_migration_licensed" in data:
            state.is_migration_licensed = bool(data["is_migration_licensed"])
        if "license_tier" in data:
            state.license_tier = data["license_tier"] or "explorer"
        if "license_email" in data:
            state.license_email = data["license_email"] or ""
        if "license_message" in data:
            state.license_message = data["license_message"] or ""
        if "active_fetch_mode" in data:
            try:
                state.active_fetch_mode = FetchMode(data["active_fetch_mode"])
            except Exception:
                state.active_fetch_mode = FetchMode.SOURCE

        # Project management fields (US-097)
        state.active_project = data.get("active_project")
        state.project_path = data.get("project_path")

        if "source_credentials" in data:
            sc = data["source_credentials"]
            state.source_credentials.host_url = sc.get(
                "host_url", "https://cloud.getdbt.com"
            )
            state.source_credentials.account_id = sc.get("account_id", "")
            # Tier 1: Restore token_type for source credentials (FR-52)
            token_type = sc.get("token_type", "service_token")
            if isinstance(token_type, dict):
                token_type = token_type.get("value", "service_token")
            if token_type not in ("service_token", "user_token"):
                token_type = "service_token"
            state.source_credentials.token_type = token_type

        if "target_credentials" in data:
            tc = data["target_credentials"]
            state.target_credentials.host_url = tc.get(
                "host_url", "https://cloud.getdbt.com"
            )
            state.target_credentials.account_id = tc.get("account_id", "")
            # Sanitize token_type - handle corrupted state values
            token_type = tc.get("token_type", "service_token")
            if isinstance(token_type, dict):
                token_type = token_type.get("value", "service_token")
            if token_type not in ("service_token", "user_token"):
                token_type = "service_token"
            state.target_credentials.token_type = token_type

        if "source_account" in data:
            sa = data["source_account"]
            state.source_account.account_id = sa.get("account_id", "")
            state.source_account.account_name = sa.get("account_name", "")
            state.source_account.host_url = sa.get("host_url", "https://cloud.getdbt.com")
            state.source_account.is_configured = sa.get("is_configured", False)
            state.source_account.is_verified = sa.get("is_verified", False)

        if "target_account" in data:
            ta = data["target_account"]
            state.target_account.account_id = ta.get("account_id", "")
            state.target_account.account_name = ta.get("account_name", "")
            state.target_account.host_url = ta.get("host_url", "https://cloud.getdbt.com")
            state.target_account.is_configured = ta.get("is_configured", False)
            state.target_account.is_verified = ta.get("is_verified", False)

        if "fetch" in data:
            f = data["fetch"]
            state.fetch.output_dir = f.get("output_dir", "dev_support/samples")
            state.fetch.auto_timestamp = f.get("auto_timestamp", True)
            state.fetch.fetch_complete = f.get("fetch_complete", False)
            state.fetch.last_fetch_file = f.get("last_fetch_file")
            state.fetch.last_summary_file = f.get("last_summary_file")
            state.fetch.last_report_file = f.get("last_report_file")
            state.fetch.last_report_items_file = f.get("last_report_items_file")
            state.fetch.account_name = f.get("account_name")
            state.fetch.resource_counts = f.get("resource_counts", {})

        if "target_fetch" in data:
            tf = data["target_fetch"]
            state.target_fetch.output_dir = tf.get("output_dir", "dev_support/samples/target")
            state.target_fetch.auto_timestamp = tf.get("auto_timestamp", True)
            state.target_fetch.fetch_complete = tf.get("fetch_complete", False)
            state.target_fetch.last_fetch_file = tf.get("last_fetch_file")
            state.target_fetch.last_summary_file = tf.get("last_summary_file")
            state.target_fetch.last_report_file = tf.get("last_report_file")
            state.target_fetch.last_report_items_file = tf.get("last_report_items_file")
            state.target_fetch.account_name = tf.get("account_name")
            state.target_fetch.resource_counts = tf.get("resource_counts", {})
            state.target_fetch.target_baseline_yaml = tf.get("target_baseline_yaml")

        if "explore" in data:
            e = data["explore"]
            if "visible_columns" in e:
                state.explore.visible_columns = e["visible_columns"]

        if "map" in data:
            m = data["map"]
            state.map.scope_mode = m.get("scope_mode", "all_projects")
            state.map.selected_project_ids = m.get("selected_project_ids", [])
            if "resource_filters" in m:
                state.map.resource_filters.update(m["resource_filters"])
            if "normalization_options" in m:
                state.map.normalization_options.update(m["normalization_options"])
            state.map.normalize_complete = m.get("normalize_complete", False)
            state.map.last_yaml_file = m.get("last_yaml_file")
            state.map.last_lookups_file = m.get("last_lookups_file")
            state.map.last_exclusions_file = m.get("last_exclusions_file")
            state.map.lookups_count = m.get("lookups_count", 0)
            state.map.exclusions_count = m.get("exclusions_count", 0)
            # Target matching state
            state.map.target_matching_enabled = m.get("target_matching_enabled", False)
            state.map.confirmed_mappings = m.get("confirmed_mappings", [])
            state.map.mapping_file_path = m.get("mapping_file_path")
            state.map.mapping_file_valid = m.get("mapping_file_valid", False)
            # Resource protection state
            state.map.protected_resources = set(m.get("protected_resources", []))
            state.map.unprotected_keys = set(m.get("unprotected_keys", []))
            # Removal intent (PRD 43.03 fix — unadopt decisions survive restart)
            state.map.removal_keys = set(m.get("removal_keys", []))
            # Protection fix state
            state.map.protection_fix_pending = m.get("protection_fix_pending", False)
            state.map.protection_fix_file_path = m.get("protection_fix_file_path", "")
            state.map.protection_fix_action = m.get("protection_fix_action", "")
            state.map.protection_fix_backup_protected = set(m.get("protection_fix_backup_protected", []))
            state.map.protection_fix_backup_unprotected = set(m.get("protection_fix_backup_unprotected", []))
            # Tier 1: User selections (FR-44)
            state.map.selected_entities = set(m.get("selected_entities", []))
            state.map.selections_loaded = m.get("selections_loaded", False)
            state.map.selection_counts = m.get("selection_counts", {"selected": 0, "total": 0})
            # Tier 1: Resource type toggles (FR-45)
            state.map.include_groups = m.get("include_groups", False)
            state.map.include_notifications = m.get("include_notifications", False)
            state.map.include_service_tokens = m.get("include_service_tokens", False)
            state.map.include_webhooks = m.get("include_webhooks", False)
            state.map.include_privatelink = m.get("include_privatelink", False)
            state.map.auto_cascade_children = m.get("auto_cascade_children", False)
            # Tier 1: Rejected suggestions and cloned resources (FR-46)
            state.map.rejected_suggestions = set(m.get("rejected_suggestions", []))
            cloned_data = m.get("cloned_resources", [])
            state.map.cloned_resources = [
                CloneConfig.from_dict(c) if isinstance(c, dict) else c
                for c in cloned_data
            ]

        if "deploy" in data:
            d = data["deploy"]
            state.deploy.import_completed = d.get("import_completed", False)
            state.deploy.import_mode = d.get("import_mode", "modern")
            state.deploy.terraform_version = d.get("terraform_version")
            state.deploy.terraform_dir = d.get("terraform_dir", "")
            state.deploy.files_generated = d.get("files_generated", False)
            # Tier 1: Step completion flags (FR-37)
            state.deploy.configure_complete = d.get("configure_complete", False)
            state.deploy.apply_complete = d.get("apply_complete", False)
            state.deploy.destroy_complete = d.get("destroy_complete", False)
            state.deploy.terraform_initialized = d.get("terraform_initialized", False)
            # Tier 1: Operation success flags (FR-39)
            state.deploy.last_validate_success = d.get("last_validate_success", False)
            state.deploy.last_plan_success = d.get("last_plan_success", False)
            # Tier 1: User settings
            state.deploy.disable_job_triggers = d.get("disable_job_triggers", False)
            state.deploy.connection_configs = d.get("connection_configs", {})
            state.deploy.previous_yaml_file = d.get("previous_yaml_file")
            state.deploy.imports_file_generated = d.get("imports_file_generated", False)
            # Tier 1: Import results (FR-47)
            import_results_data = d.get("import_results", [])
            state.deploy.import_results = [
                ImportResult.from_dict(r) if isinstance(r, dict) else r
                for r in import_results_data
            ]
            state.deploy.apply_results = d.get("apply_results")
            # Tier 1: Reconcile state (FR-48)
            state.deploy.reconcile_state_loaded = d.get("reconcile_state_loaded", False)
            state.deploy.reconcile_state_resources = d.get("reconcile_state_resources", [])
            state.deploy.reconcile_drift_results = d.get("reconcile_drift_results", [])
            state.deploy.reconcile_adopt_selections = d.get("reconcile_adopt_selections", [])
            state.deploy.reconcile_imports_generated = d.get("reconcile_imports_generated", False)
            state.deploy.reconcile_adopt_rows = d.get("reconcile_adopt_rows", [])
            state.deploy.reconcile_execution_logs = d.get("reconcile_execution_logs", [])
            # Tier 2: Operation logs (FR-40)
            state.deploy.last_generate_output = d.get("last_generate_output", "")
            state.deploy.last_init_output = d.get("last_init_output", "")
            state.deploy.last_validate_output = d.get("last_validate_output", "")
            state.deploy.last_plan_output = d.get("last_plan_output", "")
            state.deploy.last_apply_output = d.get("last_apply_output", "")
            state.deploy.last_import_output = d.get("last_import_output", "")

        if "env_credentials" in data:
            state.env_credentials = EnvironmentCredentialsState.from_dict(data["env_credentials"])

        if "jobs_as_code" in data:
            jac = data["jobs_as_code"]
            try:
                state.jobs_as_code.sub_workflow = JACSubWorkflow(jac.get("sub_workflow", "adopt"))
            except Exception:
                state.jobs_as_code.sub_workflow = JACSubWorkflow.ADOPT
            state.jobs_as_code.fetch_complete = jac.get("fetch_complete", False)
            state.jobs_as_code.source_jobs = jac.get("source_jobs", [])
            state.jobs_as_code.source_projects = jac.get("source_projects", {})
            state.jobs_as_code.source_environments = jac.get("source_environments", {})
            state.jobs_as_code.selected_job_ids = set(jac.get("selected_job_ids", []))
            
            # Restore job configs
            job_configs_data = jac.get("job_configs", [])
            state.jobs_as_code.job_configs = [
                JACJobConfig(
                    job_id=c.get("job_id"),
                    original_name=c.get("original_name", ""),
                    new_name=c.get("new_name", ""),
                    identifier=c.get("identifier", ""),
                    selected=c.get("selected", False),
                    is_managed=c.get("is_managed", False),
                )
                for c in job_configs_data
            ]
            
            state.jobs_as_code.target_same_account = jac.get("target_same_account", True)
            state.jobs_as_code.target_fetch_complete = jac.get("target_fetch_complete", False)
            state.jobs_as_code.disable_schedule = jac.get("disable_schedule", True)
            state.jobs_as_code.disable_github_webhook = jac.get("disable_github_webhook", True)
            state.jobs_as_code.disable_git_provider_webhook = jac.get("disable_git_provider_webhook", True)
            state.jobs_as_code.disable_on_merge = jac.get("disable_on_merge", True)
            try:
                state.jobs_as_code.output_format = JACOutputFormat(jac.get("output_format", "hardcoded"))
            except Exception:
                state.jobs_as_code.output_format = JACOutputFormat.HARDCODED
            state.jobs_as_code.variable_prefix = jac.get("variable_prefix", "")
            state.jobs_as_code.generation_complete = jac.get("generation_complete", False)
            state.jobs_as_code.name_prefix = jac.get("name_prefix", "")
            state.jobs_as_code.name_suffix = jac.get("name_suffix", "")
            # Tier 1: Target data and mappings (FR-49)
            state.jobs_as_code.target_jobs = jac.get("target_jobs", [])
            state.jobs_as_code.target_projects = jac.get("target_projects", {})
            state.jobs_as_code.target_environments = jac.get("target_environments", {})
            project_mappings_data = jac.get("project_mappings", [])
            state.jobs_as_code.project_mappings = [
                JACProjectMapping.from_dict(m) if isinstance(m, dict) else m
                for m in project_mappings_data
            ]
            environment_mappings_data = jac.get("environment_mappings", [])
            state.jobs_as_code.environment_mappings = [
                JACEnvironmentMapping.from_dict(m) if isinstance(m, dict) else m
                for m in environment_mappings_data
            ]
            # Tier 2: Generated outputs (FR-50)
            state.jobs_as_code.generated_yaml = jac.get("generated_yaml", "")
            state.jobs_as_code.generated_vars_yaml = jac.get("generated_vars_yaml", "")

        # Tier 1: Data quality warnings (FR-51)
        state.data_quality_warnings = data.get("data_quality_warnings", {})

        return state
