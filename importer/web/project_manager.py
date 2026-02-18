"""Project-based state management for the web UI.

Provides ProjectConfig, OutputConfig, ProjectManager, and StateSaver for
organizing credentials, configuration, and workflow state into self-contained
project folders.

See PRD 21.02-Project-Management.md for full specification.
"""

import asyncio
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from importer.web.state import AppState, WorkflowType


# ---------------------------------------------------------------------------
# Data models (US-083, US-083b)
# ---------------------------------------------------------------------------

@dataclass
class OutputConfig:
    """Configuration for project output directories."""

    source_dir: str = "outputs/source/"
    target_dir: str = "outputs/target/"
    normalized_dir: str = "outputs/normalized/"
    use_timestamps: bool = True

    def to_dict(self) -> dict:
        return {
            "source_dir": self.source_dir,
            "target_dir": self.target_dir,
            "normalized_dir": self.normalized_dir,
            "use_timestamps": self.use_timestamps,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OutputConfig":
        return cls(
            source_dir=data.get("source_dir", "outputs/source/"),
            target_dir=data.get("target_dir", "outputs/target/"),
            normalized_dir=data.get("normalized_dir", "outputs/normalized/"),
            use_timestamps=data.get("use_timestamps", True),
        )


@dataclass
class ProjectConfig:
    """Metadata for a single project (US-083).

    Stored as ``project.json`` in the project folder. Account summary fields
    (source_host, source_account_id, etc.) enable fast home-page filtering
    without loading the full AppState (FR-29).
    """

    name: str
    slug: str
    workflow_type: WorkflowType
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    source_env_file: str = "source.env"
    target_env_file: str = "target.env"
    output_config: OutputConfig = field(default_factory=OutputConfig)
    # Account summary fields for fast filtering (FR-29)
    source_host: Optional[str] = None
    source_account_id: Optional[int] = None
    target_host: Optional[str] = None
    target_account_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "slug": self.slug,
            "workflow_type": self.workflow_type.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "source_env_file": self.source_env_file,
            "target_env_file": self.target_env_file,
            "output_config": self.output_config.to_dict(),
            "source_host": self.source_host,
            "source_account_id": self.source_account_id,
            "target_host": self.target_host,
            "target_account_id": self.target_account_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        output_config = OutputConfig.from_dict(data.get("output_config", {}))
        return cls(
            name=data["name"],
            slug=data["slug"],
            workflow_type=WorkflowType(data["workflow_type"]),
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            source_env_file=data.get("source_env_file", ".env.source"),
            target_env_file=data.get("target_env_file", ".env.target"),
            output_config=output_config,
            source_host=data.get("source_host"),
            source_account_id=data.get("source_account_id"),
            target_host=data.get("target_host"),
            target_account_id=data.get("target_account_id"),
        )


# ---------------------------------------------------------------------------
# Tier 2 log-file helpers (US-098c, FR-40-43)
# ---------------------------------------------------------------------------

# Map of DeployState / JACState field names → log file names
TIER2_LOG_FILES: dict[str, str] = {
    "last_generate_output": "logs/last_generate_output.txt",
    "last_init_output": "logs/last_init_output.txt",
    "last_validate_output": "logs/last_validate_output.txt",
    "last_plan_output": "logs/last_plan_output.txt",
    "last_apply_output": "logs/last_apply_output.txt",
    "last_import_output": "logs/last_import_output.txt",
}

TIER2_JAC_LOG_FILES: dict[str, str] = {
    "generated_yaml": "logs/jac_generated.yaml",
    "generated_vars_yaml": "logs/jac_generated_vars.yaml",
}

MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB truncation limit


def _write_log_file(project_path: Path, relative_name: str, content: str) -> None:
    """Write a Tier-2 log file, truncating at MAX_LOG_SIZE."""
    fp = project_path / relative_name
    fp.parent.mkdir(parents=True, exist_ok=True)
    truncated = content[:MAX_LOG_SIZE] if len(content) > MAX_LOG_SIZE else content
    fp.write_text(truncated, encoding="utf-8")


def _read_log_file(project_path: Path, relative_name: str) -> str:
    """Read a Tier-2 log file, returning empty string if missing (FR-42)."""
    fp = project_path / relative_name
    if fp.exists():
        try:
            return fp.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""


# ---------------------------------------------------------------------------
# ProjectManager (US-084)
# ---------------------------------------------------------------------------

class ProjectManager:
    """Manages project CRUD, state persistence, and log file splitting."""

    PROJECTS_DIR = Path("projects")

    GITIGNORE_TEMPLATE = """# Project-level gitignore (defense-in-depth)
# These files contain sensitive credentials and should NEVER be committed

# Credentials (visible + legacy names)
source.env
target.env
.env.source
.env.target
.env.*

# State may contain sensitive paths and tokens
state.json

# Operation logs (terraform plan/apply output, may contain sensitive data)
logs/

# Output files may contain sensitive data
outputs/
"""

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self.base_path = Path(base_path) if base_path else Path(".")
        self.projects_dir = self.base_path / self.PROJECTS_DIR

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def slugify(name: str) -> str:
        """Convert project name to URL-safe slug."""
        slug = name.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        slug = slug.strip("-")  # Remove leading/trailing hyphens
        return slug[:50]  # Limit length

    # ---- CRUD -------------------------------------------------------------

    def list_projects(self) -> list[ProjectConfig]:
        """List all projects sorted by updated_at descending."""
        if not self.projects_dir.exists():
            return []

        projects: list[ProjectConfig] = []
        for folder in self.projects_dir.iterdir():
            if folder.is_dir():
                config_path = folder / "project.json"
                if config_path.exists():
                    try:
                        with open(config_path, encoding="utf-8") as f:
                            projects.append(ProjectConfig.from_dict(json.load(f)))
                    except Exception:
                        pass

        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    def create_project(
        self,
        name: str,
        workflow_type: WorkflowType,
        description: str = "",
        output_config: Optional[OutputConfig] = None,
    ) -> ProjectConfig:
        """Create a new project with folder structure."""
        slug = self.slugify(name)
        if not slug:
            raise ValueError("Project name produces an empty slug")
        project_path = self.projects_dir / slug

        if project_path.exists():
            raise ValueError(f"Project with slug '{slug}' already exists")

        # Create folder structure
        project_path.mkdir(parents=True)
        (project_path / "logs").mkdir(parents=True, exist_ok=True)
        (project_path / "outputs" / "source").mkdir(parents=True, exist_ok=True)
        (project_path / "outputs" / "target").mkdir(parents=True, exist_ok=True)
        (project_path / "outputs" / "normalized").mkdir(parents=True, exist_ok=True)

        # Create .gitignore first (before any sensitive files)
        (project_path / ".gitignore").write_text(self.GITIGNORE_TEMPLATE, encoding="utf-8")

        # Create project config
        config = ProjectConfig(
            name=name,
            slug=slug,
            workflow_type=workflow_type,
            description=description,
            output_config=output_config or OutputConfig(),
        )

        with open(project_path / "project.json", "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2)

        return config

    def load_project(self, slug: str) -> tuple[ProjectConfig, Optional[AppState]]:
        """Load project config and optionally its persisted state."""
        project_path = self.projects_dir / slug
        config_path = project_path / "project.json"
        state_path = project_path / "state.json"

        if not config_path.exists():
            raise FileNotFoundError(f"Project '{slug}' not found")

        with open(config_path, encoding="utf-8") as f:
            config = ProjectConfig.from_dict(json.load(f))

        state: Optional[AppState] = None
        if state_path.exists():
            with open(state_path, encoding="utf-8") as f:
                state_data = json.load(f)

            state = AppState.from_dict(state_data)

            # Restore Tier-2 log fields from separate files (FR-40)
            deploy_data = state_data.get("deploy", {})
            for field_name, log_file in TIER2_LOG_FILES.items():
                # If state.json has a file-path sentinel (empty string) or is
                # absent, read from the log file on disk instead.
                current = getattr(state.deploy, field_name, "")
                if not current:
                    content = _read_log_file(project_path, log_file)
                    if content:
                        setattr(state.deploy, field_name, content)

            jac_data = state_data.get("jobs_as_code", {})
            for field_name, log_file in TIER2_JAC_LOG_FILES.items():
                current = getattr(state.jobs_as_code, field_name, "")
                if not current:
                    content = _read_log_file(project_path, log_file)
                    if content:
                        setattr(state.jobs_as_code, field_name, content)

        return config, state

    def save_project(self, slug: str, state: AppState) -> None:
        """Save state to project folder.

        Tier-2 large outputs are split into separate files under ``logs/``
        and replaced with empty strings in ``state.json`` (FR-41).
        """
        project_path = self.projects_dir / slug
        state_path = project_path / "state.json"

        state_dict = state.to_dict()

        # Split Tier-2 deploy logs to files
        deploy_dict = state_dict.get("deploy", {})
        for field_name, log_file in TIER2_LOG_FILES.items():
            content = deploy_dict.get(field_name, "")
            if content:
                _write_log_file(project_path, log_file, content)
                deploy_dict[field_name] = ""  # Replace inline with empty sentinel

        # Split Tier-2 JAC logs to files
        jac_dict = state_dict.get("jobs_as_code", {})
        for field_name, log_file in TIER2_JAC_LOG_FILES.items():
            content = jac_dict.get(field_name, "")
            if content:
                _write_log_file(project_path, log_file, content)
                jac_dict[field_name] = ""

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, indent=2)

        # Update project.json updated_at
        config_path = project_path / "project.json"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config_data = json.load(f)
            config_data["updated_at"] = datetime.now().isoformat()
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)

    def delete_project(self, slug: str) -> None:
        """Delete project folder recursively."""
        project_path = self.projects_dir / slug
        if project_path.exists():
            shutil.rmtree(project_path)

    def get_project_path(self, slug: str) -> Path:
        """Get path to project folder."""
        return self.projects_dir / slug

    def project_exists(self, slug: str) -> bool:
        """Check if a project with the given slug exists."""
        return (self.projects_dir / slug / "project.json").exists()

    def import_credentials(
        self,
        slug: str,
        env_path: str,
        *,
        source: bool = True,
        target: bool = True,
    ) -> None:
        """Copy credentials from an .env file into the project folder.

        Parses the given env_path and writes ``{project}/source.env`` and/or
        ``{project}/target.env`` with the relevant keys.
        """
        project_path = self.projects_dir / slug
        if not project_path.exists():
            raise FileNotFoundError(f"Project '{slug}' not found")

        env_file = Path(env_path)
        if not env_file.exists():
            raise FileNotFoundError(f"Env file not found: {env_path}")

        # Parse the env file
        env_vars: dict[str, str] = {}
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                env_vars[key] = value

        source_keys = {k: v for k, v in env_vars.items() if "SOURCE" in k.upper()}
        target_keys = {k: v for k, v in env_vars.items() if "TARGET" in k.upper()}

        if source and source_keys:
            self._write_env_file(project_path / "source.env", source_keys)
        if target and target_keys:
            self._write_env_file(project_path / "target.env", target_keys)

    def update_account_summary(self, slug: str, state: AppState) -> None:
        """Sync account summary fields from AppState to ProjectConfig (FR-30)."""
        project_path = self.projects_dir / slug
        config_path = project_path / "project.json"
        if not config_path.exists():
            return

        with open(config_path, encoding="utf-8") as f:
            config_data = json.load(f)

        config_data["source_host"] = state.source_credentials.host_url or None
        try:
            config_data["source_account_id"] = int(state.source_credentials.account_id) if state.source_credentials.account_id else None
        except (ValueError, TypeError):
            config_data["source_account_id"] = None

        config_data["target_host"] = state.target_credentials.host_url or None
        try:
            config_data["target_account_id"] = int(state.target_credentials.account_id) if state.target_credentials.account_id else None
        except (ValueError, TypeError):
            config_data["target_account_id"] = None

        config_data["updated_at"] = datetime.now().isoformat()

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

    # ---- private helpers --------------------------------------------------

    @staticmethod
    def _write_env_file(path: Path, env_vars: dict[str, str]) -> None:
        """Write key=value pairs to an env file, preserving existing keys."""
        existing: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    existing[key.strip()] = value.strip()

        existing.update(env_vars)

        lines = [f"{k}={v}" for k, v in sorted(existing.items())]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# StateSaver — debounced auto-save (US-099)
# ---------------------------------------------------------------------------

class StateSaver:
    """Debounced state saver for projects."""

    def __init__(
        self,
        project_manager: ProjectManager,
        debounce_seconds: float = 1.0,
    ) -> None:
        self.project_manager = project_manager
        self.debounce_seconds = debounce_seconds
        self._pending_save: Optional[asyncio.Task[None]] = None
        self._last_state: Optional[AppState] = None

    async def schedule_save(self, state: AppState) -> None:
        """Schedule a debounced save."""
        if not state.active_project:
            return

        self._last_state = state

        # Cancel pending save
        if self._pending_save and not self._pending_save.done():
            self._pending_save.cancel()

        # Schedule new save
        self._pending_save = asyncio.create_task(self._delayed_save())

    async def _delayed_save(self) -> None:
        """Execute save after debounce delay."""
        try:
            await asyncio.sleep(self.debounce_seconds)
        except asyncio.CancelledError:
            return

        if self._last_state and self._last_state.active_project:
            try:
                self.project_manager.save_project(
                    self._last_state.active_project,
                    self._last_state,
                )
                # Also sync account summary (FR-30)
                self.project_manager.update_account_summary(
                    self._last_state.active_project,
                    self._last_state,
                )
            except Exception:
                # Don't interrupt user workflow
                pass

    async def force_save(self, state: AppState) -> None:
        """Immediately save without debouncing (e.g., on shutdown)."""
        if not state.active_project:
            return
        try:
            self.project_manager.save_project(state.active_project, state)
            self.project_manager.update_account_summary(state.active_project, state)
        except Exception:
            pass
