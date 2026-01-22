"""Pydantic models describing the importer internal representation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ImporterBaseModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True, extra='allow')


class Connection(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class Repository(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    remote_url: str
    git_clone_strategy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ServiceToken(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    name: str
    state: Optional[int] = None
    token_string: Optional[str] = None  # Masked value from API
    permission_sets: List[str] = Field(default_factory=list)
    project_ids: List[int] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Group(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    name: str
    assign_by_default: Optional[bool] = None
    sso_mapping_groups: List[str] = Field(default_factory=list)
    permission_sets: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Notification(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    notification_type: Optional[int] = None  # 1=internal, 2=slack, 4=external
    state: Optional[int] = None  # 1=active, 2=inactive
    user_id: Optional[int] = None
    on_success: List[int] = Field(default_factory=list)  # List of job IDs
    on_failure: List[int] = Field(default_factory=list)  # List of job IDs
    on_cancel: List[int] = Field(default_factory=list)  # List of job IDs
    on_warning: List[int] = Field(default_factory=list)  # List of job IDs
    external_email: Optional[str] = None  # For type 4 (external email)
    slack_channel_id: Optional[str] = None  # For type 2 (Slack)
    slack_channel_name: Optional[str] = None  # For type 2 (Slack)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebhookSubscription(ImporterBaseModel):
    key: str
    id: Optional[str] = None  # UUID from API
    name: Optional[str] = None
    client_url: Optional[str] = None
    event_types: List[str] = Field(default_factory=list)
    job_ids: List[int] = Field(default_factory=list)
    active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PrivateLinkEndpoint(ImporterBaseModel):
    key: str
    id: Optional[str] = None  # UUID from API
    name: Optional[str] = None
    type: Optional[str] = None  # e.g., "fabric", "databricks", "snowflake"
    state: Optional[str] = None  # e.g., "active", "creating", "deleting"
    cidr_range: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Credential(ImporterBaseModel):
    """Credential configuration for an environment.
    
    Supports all dbt Cloud credential types: Snowflake, Databricks, BigQuery,
    Postgres, Redshift, Athena, Fabric, Synapse, Starburst, Spark, Teradata.
    """
    # Credential ID and type
    id: Optional[int] = None
    credential_type: Optional[str] = None  # snowflake, databricks, bigquery, postgres, etc.
    
    # Common fields
    schema_name: str = Field(alias="schema", serialization_alias="schema", default="")
    num_threads: Optional[int] = None
    is_active: Optional[bool] = True
    
    # Snowflake-specific
    auth_type: Optional[str] = None  # "password" or "keypair"
    user: Optional[str] = None
    warehouse: Optional[str] = None
    role: Optional[str] = None
    database: Optional[str] = None
    
    # Databricks-specific
    token_name: Optional[str] = None
    catalog: Optional[str] = None
    adapter_type: Optional[str] = None
    
    # BigQuery-specific
    dataset: Optional[str] = None
    
    # Postgres/Redshift-specific
    default_schema: Optional[str] = None
    username: Optional[str] = None
    target_name: Optional[str] = None  # "postgres" or "redshift"
    
    # Athena-specific (sensitive fields not fetched from API)
    # aws_access_key_id and aws_secret_access_key are sensitive - not stored here
    
    # Fabric/Synapse-specific
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    schema_authorization: Optional[str] = None
    authentication: Optional[str] = None  # SQL, ActiveDirectoryPassword, ServicePrincipal
    
    # Starburst/Trino-specific
    # Uses catalog + schema (already defined)
    
    # Metadata from API
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def schema(self) -> str:
        return self.schema_name


class Environment(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    name: str
    type: str
    connection_key: str
    credential: Optional[Credential] = None  # Optional - development envs may not have credentials
    dbt_version: Optional[str] = None
    custom_branch: Optional[str] = None
    enable_model_query_history: Optional[bool] = None
    deployment_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Job(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    name: str
    environment_key: str
    execute_steps: List[str]
    triggers: Dict[str, Any]
    settings: Dict[str, Any] = Field(default_factory=dict)
    environment_variable_overrides: Dict[str, str] = Field(default_factory=dict)


class EnvironmentVariable(ImporterBaseModel):
    name: str
    project_default: Optional[str] = None
    environment_values: Dict[str, str]


class Project(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    name: str
    repository_key: Optional[str] = None
    environments: List[Environment] = Field(default_factory=list)
    environment_variables: List[EnvironmentVariable] = Field(default_factory=list)
    jobs: List[Job] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Globals(ImporterBaseModel):
    connections: Dict[str, Connection] = Field(default_factory=dict)
    repositories: Dict[str, Repository] = Field(default_factory=dict)
    service_tokens: Dict[str, ServiceToken] = Field(default_factory=dict)
    groups: Dict[str, Group] = Field(default_factory=dict)
    notifications: Dict[str, Notification] = Field(default_factory=dict)
    webhooks: Dict[str, WebhookSubscription] = Field(default_factory=dict)
    privatelink_endpoints: Dict[str, PrivateLinkEndpoint] = Field(default_factory=dict)


class AccountSnapshot(ImporterBaseModel):
    account_id: int
    account_name: Optional[str] = None
    globals: Globals = Field(default_factory=Globals)
    projects: List[Project] = Field(default_factory=list)


