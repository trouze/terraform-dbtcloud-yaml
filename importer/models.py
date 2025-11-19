"""Pydantic models describing the importer internal representation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ImporterBaseModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)


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


class Credential(ImporterBaseModel):
    token_name: str
    schema_name: str = Field(alias="schema", serialization_alias="schema")
    catalog: Optional[str] = None

    @property
    def schema(self) -> str:
        return self.schema_name


class Environment(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    name: str
    type: str
    connection_key: str
    credential: Credential
    dbt_version: Optional[str] = None
    custom_branch: Optional[str] = None
    enable_model_query_history: Optional[bool] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Job(ImporterBaseModel):
    key: str
    id: Optional[int] = None
    name: str
    environment_key: str
    execute_steps: List[str]
    triggers: Dict[str, Any]
    settings: Dict[str, Any] = Field(default_factory=dict)


class EnvironmentVariable(ImporterBaseModel):
    name: str
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


class AccountSnapshot(ImporterBaseModel):
    account_id: int
    account_name: Optional[str] = None
    globals: Globals = Field(default_factory=Globals)
    projects: List[Project] = Field(default_factory=list)


