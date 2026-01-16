"""Session state management for the web UI."""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Optional


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
    DEPLOY = 8
    DESTROY = 9


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
    WorkflowStep.MATCH: "Match Existing",
    WorkflowStep.CONFIGURE: "Configure Migration",
    WorkflowStep.DEPLOY: "Deploy",
    WorkflowStep.DESTROY: "Destroy",
}

STEP_ICONS = {
    WorkflowStep.HOME: "home",
    WorkflowStep.FETCH_SOURCE: "cloud_download",
    WorkflowStep.EXPLORE_SOURCE: "search",
    WorkflowStep.SCOPE: "tune",
    WorkflowStep.FETCH_TARGET: "cloud_download",
    WorkflowStep.EXPLORE_TARGET: "manage_search",
    WorkflowStep.MATCH: "link",
    WorkflowStep.CONFIGURE: "settings",
    WorkflowStep.DEPLOY: "rocket_launch",
    WorkflowStep.DESTROY: "delete_forever",
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
        WorkflowStep.CONFIGURE,
        WorkflowStep.DEPLOY,
        WorkflowStep.DESTROY,
    ],
    WorkflowType.ACCOUNT_EXPLORER: [
        WorkflowStep.FETCH_SOURCE,
        WorkflowStep.EXPLORE_SOURCE,
    ],
    WorkflowType.JOBS_AS_CODE: [
        WorkflowStep.FETCH_SOURCE,
        WorkflowStep.EXPLORE_SOURCE,
        WorkflowStep.SCOPE,
        WorkflowStep.DEPLOY,
    ],
    WorkflowType.IMPORT_ADOPT: [
        WorkflowStep.FETCH_SOURCE,
        WorkflowStep.EXPLORE_SOURCE,
        WorkflowStep.SCOPE,
        WorkflowStep.FETCH_TARGET,
        WorkflowStep.EXPLORE_TARGET,
        WorkflowStep.MATCH,
        WorkflowStep.CONFIGURE,
        WorkflowStep.DEPLOY,
        WorkflowStep.DESTROY,
    ],
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
    threads: int = 15
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
    threads: int = 15
    is_fetching: bool = False
    fetch_complete: bool = False
    last_fetch_file: Optional[str] = None
    last_summary_file: Optional[str] = None
    last_report_file: Optional[str] = None
    last_report_items_file: Optional[str] = None
    account_name: Optional[str] = None
    resource_counts: dict = field(default_factory=dict)


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


@dataclass
class DeployState:
    """State for the deploy step."""

    connection_configs: dict = field(default_factory=dict)
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

    def has_state_file(self) -> bool:
        """Check if a Terraform state file exists."""
        from pathlib import Path
        tf_dir = self.terraform_dir or "deployments/migration"
        state_path = Path(tf_dir) / "terraform.tfstate"
        return state_path.exists()
    
    def has_pending_imports(self) -> bool:
        """Check if there are mappings that need to be imported."""
        return len(self.import_results) > 0 and not self.import_completed


@dataclass
class AppState:
    """Complete application state."""

    current_step: WorkflowStep = WorkflowStep.HOME
    theme: str = "dark"  # "dark" or "light"
    workflow: WorkflowType = WorkflowType.MIGRATION

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

    # Raw account data from fetch
    account_data: Optional[dict] = None
    # Raw target account data from target fetch
    target_account_data: Optional[dict] = None

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
            return self.deploy.files_generated
        elif step == WorkflowStep.DEPLOY:
            return self.deploy.apply_complete
        elif step == WorkflowStep.DESTROY:
            return self.deploy.destroy_complete
        return False

    def step_is_accessible(self, step: WorkflowStep) -> bool:
        """Check if a workflow step can be accessed."""
        if step != WorkflowStep.HOME and step not in self.workflow_steps():
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
            return self.map.normalize_complete
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
        elif step == WorkflowStep.DEPLOY:
            return self.deploy.files_generated
        elif step == WorkflowStep.DESTROY:
            return self.deploy.has_state_file()
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
        """Convert state to dictionary for storage."""
        return {
            "current_step": self.current_step.value,
            "theme": self.theme,
            "workflow": self.workflow.value,
            "active_fetch_mode": self.active_fetch_mode.value,
            "source_credentials": {
                "host_url": self.source_credentials.host_url,
                "account_id": self.source_credentials.account_id,
                # Don't persist token for security
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
            },
            "explore": {
                "visible_columns": self.explore.visible_columns,
            },
            "map": {
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
            },
            "deploy": {
                "import_completed": self.deploy.import_completed,
                "import_mode": self.deploy.import_mode,
                "terraform_version": self.deploy.terraform_version,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppState":
        """Restore state from dictionary."""
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
        if "active_fetch_mode" in data:
            try:
                state.active_fetch_mode = FetchMode(data["active_fetch_mode"])
            except Exception:
                state.active_fetch_mode = FetchMode.SOURCE

        if "source_credentials" in data:
            sc = data["source_credentials"]
            state.source_credentials.host_url = sc.get(
                "host_url", "https://cloud.getdbt.com"
            )
            state.source_credentials.account_id = sc.get("account_id", "")

        if "target_credentials" in data:
            tc = data["target_credentials"]
            state.target_credentials.host_url = tc.get(
                "host_url", "https://cloud.getdbt.com"
            )
            state.target_credentials.account_id = tc.get("account_id", "")
            state.target_credentials.token_type = tc.get("token_type", "service_token")

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

        if "deploy" in data:
            d = data["deploy"]
            state.deploy.import_completed = d.get("import_completed", False)
            state.deploy.import_mode = d.get("import_mode", "modern")
            state.deploy.terraform_version = d.get("terraform_version")

        return state
