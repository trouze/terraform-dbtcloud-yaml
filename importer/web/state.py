"""Session state management for the web UI."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


class WorkflowStep(IntEnum):
    """Workflow steps in order."""

    HOME = 0
    FETCH = 1
    EXPLORE = 2
    MAP = 3
    TARGET = 4
    DEPLOY = 5


STEP_NAMES = {
    WorkflowStep.HOME: "Home",
    WorkflowStep.FETCH: "Fetch",
    WorkflowStep.EXPLORE: "Explore",
    WorkflowStep.MAP: "Map",
    WorkflowStep.TARGET: "Target",
    WorkflowStep.DEPLOY: "Deploy",
}

STEP_ICONS = {
    WorkflowStep.HOME: "home",
    WorkflowStep.FETCH: "cloud_download",
    WorkflowStep.EXPLORE: "search",
    WorkflowStep.MAP: "tune",
    WorkflowStep.TARGET: "settings",
    WorkflowStep.DEPLOY: "rocket_launch",
}


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
    """State for the fetch step."""

    output_dir: str = "dev_support/samples"
    auto_timestamp: bool = True
    is_fetching: bool = False
    fetch_complete: bool = False
    last_fetch_file: Optional[str] = None
    last_summary_file: Optional[str] = None
    last_report_file: Optional[str] = None
    last_report_items_file: Optional[str] = None
    account_name: Optional[str] = None
    resource_counts: dict = field(default_factory=dict)


@dataclass
class ExploreState:
    """State for the explore step."""

    report_items: list = field(default_factory=list)
    selected_type_filter: str = "all"
    search_query: str = ""


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
    normalize_complete: bool = False
    last_yaml_file: Optional[str] = None
    last_lookups_file: Optional[str] = None
    last_exclusions_file: Optional[str] = None


@dataclass
class DeployState:
    """State for the deploy step."""

    connection_configs: dict = field(default_factory=dict)
    terraform_initialized: bool = False
    last_plan_success: bool = False
    last_plan_output: str = ""
    apply_complete: bool = False
    apply_results: Optional[dict] = None


@dataclass
class AppState:
    """Complete application state."""

    current_step: WorkflowStep = WorkflowStep.HOME
    theme: str = "dark"  # "dark" or "light"

    source_credentials: SourceCredentials = field(default_factory=SourceCredentials)
    target_credentials: TargetCredentials = field(default_factory=TargetCredentials)

    # Account info (populated from .env and API calls)
    source_account: AccountInfo = field(default_factory=AccountInfo)
    target_account: AccountInfo = field(default_factory=AccountInfo)

    fetch: FetchState = field(default_factory=FetchState)
    explore: ExploreState = field(default_factory=ExploreState)
    map: MapState = field(default_factory=MapState)
    deploy: DeployState = field(default_factory=DeployState)

    # Raw account data from fetch
    account_data: Optional[dict] = None

    def step_is_complete(self, step: WorkflowStep) -> bool:
        """Check if a workflow step has been completed."""
        if step == WorkflowStep.HOME:
            return True
        elif step == WorkflowStep.FETCH:
            return self.fetch.fetch_complete
        elif step == WorkflowStep.EXPLORE:
            return self.fetch.fetch_complete  # Can explore once fetched
        elif step == WorkflowStep.MAP:
            return self.map.normalize_complete
        elif step == WorkflowStep.TARGET:
            return self.target_credentials.is_complete()
        elif step == WorkflowStep.DEPLOY:
            return self.deploy.apply_complete
        return False

    def step_is_accessible(self, step: WorkflowStep) -> bool:
        """Check if a workflow step can be accessed."""
        if step == WorkflowStep.HOME:
            return True
        elif step == WorkflowStep.FETCH:
            return True  # Always accessible
        elif step == WorkflowStep.EXPLORE:
            return self.fetch.fetch_complete
        elif step == WorkflowStep.MAP:
            return self.fetch.fetch_complete
        elif step == WorkflowStep.TARGET:
            return self.map.normalize_complete
        elif step == WorkflowStep.DEPLOY:
            return self.map.normalize_complete and self.target_credentials.is_complete()
        return False

    def to_dict(self) -> dict:
        """Convert state to dictionary for storage."""
        return {
            "current_step": self.current_step.value,
            "theme": self.theme,
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
            "map": {
                "scope_mode": self.map.scope_mode,
                "selected_project_ids": self.map.selected_project_ids,
                "resource_filters": self.map.resource_filters,
                "normalization_options": self.map.normalization_options,
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

        if "map" in data:
            m = data["map"]
            state.map.scope_mode = m.get("scope_mode", "all_projects")
            state.map.selected_project_ids = m.get("selected_project_ids", [])
            if "resource_filters" in m:
                state.map.resource_filters.update(m["resource_filters"])
            if "normalization_options" in m:
                state.map.normalization_options.update(m["normalization_options"])

        return state
