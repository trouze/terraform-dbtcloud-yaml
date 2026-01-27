# PRD: Web UI - Part 8: Project-Based State Management

## Introduction

A project-based paradigm for the dbt Cloud Importer Web UI that organizes credentials, configuration, and workflow state into self-contained project folders. This enables users to maintain multiple migration projects simultaneously, switch between them seamlessly, and ensures sensitive credentials are properly gitignored with defense-in-depth protection.

This is **Part 8** in the Web UI PRD series.  
**Depends on:** Part 1 (Core Shell), Part 2 (Fetch)

## Goals

- Enable users to create, load, and manage multiple migration projects
- Provide a multi-step wizard for new project creation with credential import options
- Store all project-specific files (credentials, state, outputs) in isolated project folders
- Implement defense-in-depth gitignore strategy (root + per-project)
- Replace direct `.env` overwrites with a file picker dialog for explicit save locations
- Auto-save workflow state when a project is active
- Support seamless switching between projects from the home page

## User Stories

---

### Epic 1: Project Infrastructure

---

### US-080: Project Folder Creation
**Description:** As a user, I want each project to have its own isolated folder so that credentials and state are kept separate.

**Acceptance Criteria:**
- [ ] Projects are created under `projects/` directory in workspace root
- [ ] Project folder name is a URL-safe slug derived from project name
- [ ] Slug generation handles special characters, spaces, and unicode
- [ ] Duplicate project names are rejected with clear error message
- [ ] Project folder contains: `project.json`, `.gitignore`, `outputs/` directory
- [ ] Typecheck passes

**Testing:**
- [ ] Unit test: slug generation from various project names
- [ ] Unit test: duplicate name detection
- [ ] Integration test: folder structure created correctly
- [ ] Browser test: create project and verify folder exists

---

### US-081: Project-Level Gitignore
**Description:** As a user, I want each project folder to have its own `.gitignore` so that sensitive files are protected even if root gitignore is modified.

**Acceptance Criteria:**
- [ ] `.gitignore` created automatically with each new project
- [ ] Ignores: `.env.source`, `.env.target`, `.env.*`, `state.json`, `outputs/`
- [ ] File includes comment header explaining purpose
- [ ] Gitignore is created before any credential files are written
- [ ] Typecheck passes

**Testing:**
- [ ] Unit test: gitignore template content is correct
- [ ] Integration test: gitignore created on project creation
- [ ] Manual test: `git status` does not show ignored files after project creation

---

### US-082: Root Gitignore Update
**Description:** As a user, I want the root `.gitignore` to exclude the entire `projects/` folder as a first line of defense.

**Acceptance Criteria:**
- [ ] Root `.gitignore` updated to include `projects/` entry
- [ ] Entry includes explanatory comment
- [ ] Existing gitignore entries are preserved
- [ ] Typecheck passes

**Testing:**
- [ ] Manual test: verify `projects/` added to root gitignore
- [ ] Manual test: `git status` ignores projects folder

---

### US-083: ProjectConfig Model
**Description:** As a developer, I need a data model for project metadata so that project information can be persisted and loaded.

**Acceptance Criteria:**
- [ ] `ProjectConfig` dataclass with fields:
  - `name: str` - Human-readable project name
  - `slug: str` - Folder-safe identifier
  - `description: str` - Optional description
  - `workflow_type: WorkflowType` - Migration, Account Explorer, etc.
  - `created_at: datetime` - Creation timestamp
  - `updated_at: datetime` - Last modification timestamp
  - `source_env_file: str` - Relative path (default: `.env.source`)
  - `target_env_file: str` - Relative path (default: `.env.target`)
  - `output_config: OutputConfig` - Output directory settings
- [ ] `to_dict()` and `from_dict()` methods for JSON serialization
- [ ] Stored as `project.json` in project folder
- [ ] Typecheck passes

**Testing:**
- [ ] Unit test: serialization round-trip preserves all fields
- [ ] Unit test: datetime fields serialize to ISO format
- [ ] Unit test: default values applied correctly

---

### US-084: ProjectManager Class
**Description:** As a developer, I need a manager class to handle project CRUD operations so that project lifecycle is encapsulated.

**Acceptance Criteria:**
- [ ] `ProjectManager` class in `importer/web/project_manager.py`
- [ ] `list_projects() -> list[ProjectConfig]` - Scans `projects/` folder
- [ ] `create_project(name, workflow_type, description) -> ProjectConfig` - Creates folder structure
- [ ] `load_project(slug) -> tuple[ProjectConfig, AppState | None]` - Loads config and state
- [ ] `save_project(slug, state: AppState)` - Saves state.json
- [ ] `delete_project(slug)` - Removes folder with confirmation
- [ ] `get_project_path(slug) -> Path` - Returns project folder path
- [ ] `project_exists(slug) -> bool` - Checks if project exists
- [ ] `import_credentials(slug, env_path, source=True, target=True)` - Copies credentials
- [ ] All methods raise appropriate exceptions on error
- [ ] Typecheck passes

**Testing:**
- [ ] Unit test: list_projects returns empty list when no projects
- [ ] Unit test: list_projects returns all projects sorted by updated_at
- [ ] Unit test: create_project creates all required files/folders
- [ ] Unit test: create_project rejects duplicate names
- [ ] Unit test: load_project returns None state for new project
- [ ] Unit test: load_project restores full state for existing project
- [ ] Unit test: save_project creates state.json with full AppState
- [ ] Unit test: delete_project removes folder recursively
- [ ] Unit test: import_credentials copies correct env vars
- [ ] Integration test: full lifecycle (create, save, load, delete)

---

### Epic 2: New Project Wizard

---

### US-085: Wizard Dialog Component
**Description:** As a user, I want a multi-step wizard dialog to guide me through creating a new project so that the setup process is clear and organized.

**Acceptance Criteria:**
- [ ] Dialog opens from "New Project" button on home page
- [ ] Stepper component shows 4 steps with labels
- [ ] Current step highlighted, completed steps show checkmark
- [ ] "Back" and "Next" buttons for navigation
- [ ] "Next" disabled until current step is valid
- [ ] "Cancel" button closes dialog without creating project
- [ ] Dialog is modal (prevents interaction with page behind)
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: open wizard, navigate all steps, cancel
- [ ] Browser test: stepper state updates correctly
- [ ] Browser test: cannot proceed with invalid step

---

### US-086: Wizard Step 1 - Project Basics
**Description:** As a user, I want to enter project name, description, and workflow type so that my project is properly identified.

**Acceptance Criteria:**
- [ ] Project name field (required)
  - Validates uniqueness in real-time
  - Shows generated slug below input
  - Min 3 characters, max 100 characters
  - Allows letters, numbers, spaces, hyphens, underscores
- [ ] Description textarea (optional)
  - Max 500 characters
  - Character counter displayed
- [ ] Workflow type selection (required)
  - Radio buttons or dropdown
  - Options: Migration, Account Explorer, Jobs as Code, Import & Adopt
  - Default: Migration
- [ ] Validation errors shown inline
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: enter valid name, see slug generated
- [ ] Browser test: enter duplicate name, see error
- [ ] Browser test: enter name with special chars, see sanitized slug
- [ ] Browser test: select each workflow type
- [ ] Unit test: name validation rules
- [ ] Unit test: slug generation algorithm

---

### US-087: Wizard Step 2 - Import Credentials
**Description:** As a user, I want to optionally import existing credentials into my new project so that I don't have to re-enter them.

**Acceptance Criteria:**
- [ ] Three radio options:
  - "Start fresh" - No credential import (default)
  - "Import from .env file" - File picker appears
  - "Copy from existing project" - Project dropdown appears
- [ ] File picker for .env import:
  - Browse button opens file dialog
  - Shows selected file path
  - Validates file exists and is readable
- [ ] .env preview panel:
  - Shows detected source credentials (masked tokens)
  - Shows detected target credentials (masked tokens)
  - Checkbox: "Import source credentials"
  - Checkbox: "Import target credentials"
- [ ] Project copy dropdown:
  - Lists all existing projects
  - Shows project name and workflow type
  - Same checkboxes for source/target selection
- [ ] Step is always valid (import is optional)
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: select "Start fresh", proceed immediately
- [ ] Browser test: select file import, pick valid .env, see preview
- [ ] Browser test: select file import, pick invalid file, see error
- [ ] Browser test: select project copy, choose project, see preview
- [ ] Browser test: toggle import checkboxes, verify state
- [ ] Unit test: .env parsing for credential detection
- [ ] Unit test: credential masking for preview

---

### US-088: Wizard Step 3 - Output Configuration
**Description:** As a user, I want to configure where output files are stored within my project so that I can organize my workflow.

**Acceptance Criteria:**
- [ ] Source output directory field
  - Default: `outputs/source/`
  - Relative to project folder
  - Browse button for selection
- [ ] Target output directory field
  - Default: `outputs/target/`
  - Relative to project folder
- [ ] Normalized YAML directory field
  - Default: `outputs/normalized/`
  - Relative to project folder
- [ ] Checkbox: "Use timestamped subdirectories" (default: on)
  - When on, each fetch creates `outputs/source/2024-01-15_143022/`
- [ ] Preview of full paths displayed
- [ ] Validation: directories must be within project folder
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: verify default values populated
- [ ] Browser test: modify paths, see preview update
- [ ] Browser test: toggle timestamp option
- [ ] Unit test: path validation (no escape from project folder)
- [ ] Unit test: timestamp directory name generation

---

### US-089: Wizard Step 4 - Summary & Create
**Description:** As a user, I want to review all my settings before creating the project so that I can verify everything is correct.

**Acceptance Criteria:**
- [ ] Summary card displays:
  - Project name and slug
  - Description (or "No description")
  - Workflow type
  - Credential import choice and details
  - Output directory configuration
- [ ] "Create Project" button (prominent styling)
- [ ] Button shows loading state during creation
- [ ] On success:
  - Success notification displayed
  - Dialog closes
  - Project loaded as active
  - Navigation to first workflow step
- [ ] On error:
  - Error notification with details
  - User can go back to fix issues
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: review summary, all settings displayed correctly
- [ ] Browser test: create project, verify success flow
- [ ] Browser test: simulate error, verify error handling
- [ ] Integration test: end-to-end wizard completion

---

### Epic 3: Home Page Project Selector

---

### US-090: Project List Display
**Description:** As a user, I want to see all my existing projects on the home page so that I can quickly access them.

**Acceptance Criteria:**
- [ ] "Your Projects" section on home page
- [ ] Projects displayed as cards in a grid
- [ ] Each card shows:
  - Project name (title)
  - Workflow type badge (colored)
  - Description (truncated to 2 lines)
  - Last modified date (relative, e.g., "2 hours ago")
  - Source account info (if configured): Account ID, host
  - Target account info (if configured): Account ID, host
- [ ] Cards sorted by last modified (most recent first)
- [ ] "No projects yet" message when list empty
- [ ] "New Project" button prominently displayed
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: view empty state
- [ ] Browser test: view single project
- [ ] Browser test: view multiple projects, verify sorting
- [ ] Browser test: verify card content accuracy

---

### US-091: Load Existing Project
**Description:** As a user, I want to click a project to load it so that I can continue my work.

**Acceptance Criteria:**
- [ ] Clicking project card loads that project
- [ ] Loading indicator during project load
- [ ] AppState restored from `state.json`
- [ ] Credentials loaded from `.env.source` and `.env.target`
- [ ] `active_project` field set in AppState
- [ ] Navigation to appropriate workflow step based on state
- [ ] If state.json missing, start from first step
- [ ] Success notification: "Loaded project: {name}"
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: load project with full state, verify restoration
- [ ] Browser test: load project with partial state
- [ ] Browser test: load new project (no state), start at step 1
- [ ] Browser test: verify credentials loaded correctly
- [ ] Unit test: AppState from_dict with various payloads

---

### US-092: Delete Project
**Description:** As a user, I want to delete a project I no longer need so that I can clean up my workspace.

**Acceptance Criteria:**
- [ ] Delete button (trash icon) on each project card
- [ ] Confirmation dialog before deletion
  - Shows project name
  - Warns about permanent deletion
  - "Delete" and "Cancel" buttons
- [ ] On confirm:
  - Project folder deleted recursively
  - Project removed from list
  - Success notification
- [ ] Cannot delete currently active project (must switch first)
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: delete project, confirm, verify removed
- [ ] Browser test: cancel deletion, project remains
- [ ] Browser test: attempt to delete active project, see error
- [ ] Unit test: ProjectManager.delete_project removes all files

---

### US-093: Project Search/Filter
**Description:** As a user, I want to search and filter my projects so that I can quickly find what I need when I have many projects.

**Acceptance Criteria:**
- [ ] Search input above project grid
- [ ] Searches project name and description
- [ ] Filter by workflow type (dropdown or chips)
- [ ] Results update in real-time as user types
- [ ] "No matching projects" message when filter returns empty
- [ ] Clear filters button
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: search by name, verify filtering
- [ ] Browser test: search by description text
- [ ] Browser test: filter by workflow type
- [ ] Browser test: combine search and filter
- [ ] Browser test: clear filters

---

### Epic 4: Save .env Dialog

---

### US-094: Save .env Dialog Component
**Description:** As a user, I want a dialog when saving credentials so that I can choose where to save them.

**Acceptance Criteria:**
- [ ] Dialog opens when clicking "Save to .env" button
- [ ] Shows current project context (if active)
- [ ] File path input field with:
  - Default: project's `.env.source` or `.env.target` (based on context)
  - If no project: defaults to workspace root `.env`
  - Browse button for file selection
- [ ] Overwrite warning if file exists
- [ ] "Save" and "Cancel" buttons
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: open dialog from source fetch, see .env.source default
- [ ] Browser test: open dialog from target fetch, see .env.target default
- [ ] Browser test: open dialog with no project, see root .env default
- [ ] Browser test: select custom path via browse
- [ ] Browser test: verify overwrite warning appears

---

### US-095: Save .env Preview
**Description:** As a user, I want to preview what will be saved so that I can verify before committing.

**Acceptance Criteria:**
- [ ] Preview panel shows credentials to be saved
- [ ] Tokens/secrets are masked (show last 4 chars only)
- [ ] Shows environment variable names (e.g., `DBT_SOURCE_API_TOKEN`)
- [ ] Preview updates if user changes path (different env var prefix)
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: verify preview content matches form
- [ ] Browser test: verify masking is applied
- [ ] Browser test: change path, verify preview updates

---

### US-096: Save .env Execution
**Description:** As a user, I want the save operation to create or update the .env file correctly.

**Acceptance Criteria:**
- [ ] Clicking "Save" writes to specified path
- [ ] Creates parent directories if needed
- [ ] Preserves existing keys not being updated
- [ ] Adds new keys if not present
- [ ] Updates existing keys with new values
- [ ] Success notification with file path
- [ ] Dialog closes on success
- [ ] Error notification on failure (with details)
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: save to new file, verify created
- [ ] Browser test: save to existing file, verify preserved keys
- [ ] Browser test: save to read-only path, verify error handling
- [ ] Unit test: .env file writing with preservation

---

### Epic 5: State Persistence

---

### US-097: AppState Project Fields
**Description:** As a developer, I need AppState to track active project so that state can be associated with projects.

**Acceptance Criteria:**
- [ ] Add `active_project: Optional[str]` field (slug)
- [ ] Add `project_path: Optional[Path]` field
- [ ] Fields included in `to_dict()` and `from_dict()`
- [ ] Fields default to None when no project active
- [ ] Typecheck passes

**Testing:**
- [ ] Unit test: to_dict includes project fields
- [ ] Unit test: from_dict restores project fields
- [ ] Unit test: default values when no project

---

### US-098: Full AppState Serialization
**Description:** As a developer, I need AppState to serialize all fields so that complete state can be saved to projects.

**Acceptance Criteria:**
- [ ] `to_dict()` serializes all nested dataclasses
- [ ] `from_dict()` restores all nested dataclasses
- [ ] Handles None values gracefully
- [ ] Handles missing keys gracefully (uses defaults)
- [ ] Handles datetime fields (ISO format)
- [ ] Handles enum fields (value serialization)
- [ ] Typecheck passes

**Testing:**
- [ ] Unit test: round-trip serialization with full state
- [ ] Unit test: partial state restoration (missing keys)
- [ ] Unit test: datetime serialization
- [ ] Unit test: enum serialization
- [ ] Unit test: nested dataclass handling

---

### US-099: Auto-Save State to Project
**Description:** As a user, I want my workflow state to auto-save when I have an active project so that I don't lose progress.

**Acceptance Criteria:**
- [ ] State saved automatically when project is active
- [ ] Save triggered on significant state changes:
  - Credential form changes
  - Fetch completion
  - Selection changes
  - Mapping changes
  - Deploy progress
- [ ] Debounced saving (max 1 save per second)
- [ ] Save happens in background (non-blocking)
- [ ] Errors logged but don't interrupt user workflow
- [ ] Typecheck passes

**Testing:**
- [ ] Browser test: make changes, verify state.json updated
- [ ] Browser test: rapid changes, verify debouncing
- [ ] Unit test: debounce logic
- [ ] Integration test: state persists across app restart

---

### US-100: Load Last Active Project on Startup
**Description:** As a user, I want the app to remember my last active project so that I can continue where I left off.

**Acceptance Criteria:**
- [ ] Last active project slug stored in browser storage
- [ ] On app startup, if last project exists:
  - Auto-load that project
  - Show notification: "Restored project: {name}"
- [ ] If last project no longer exists:
  - Clear stored slug
  - Show home page normally
- [ ] "Always start on home page" option in settings
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: close and reopen app, verify project restored
- [ ] Browser test: delete project, reopen app, verify graceful handling
- [ ] Browser test: disable auto-restore, verify home page shown

---

### Epic 6: Fetch Page Integration

---

### US-101: Project-Aware Output Directories
**Description:** As a user, I want fetch outputs to go to my project folder so that all project files are organized together.

**Acceptance Criteria:**
- [ ] When project active, fetch outputs go to `{project}/outputs/source/` or `{project}/outputs/target/`
- [ ] When no project, falls back to root output directory
- [ ] Output directory shown in fetch form (read-only when project active)
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: fetch with project active, verify output location
- [ ] Browser test: fetch without project, verify root location
- [ ] Integration test: output files in correct directories

---

### US-102: Save Button Opens Dialog
**Description:** As a user, I want the "Save to .env" button to open the save dialog so that I can choose the destination.

**Acceptance Criteria:**
- [ ] "Save to .env" button opens `SaveEnvDialog`
- [ ] Dialog pre-populated with project context
- [ ] Source fetch page defaults to `.env.source`
- [ ] Target fetch page defaults to `.env.target`
- [ ] After save, credentials marked as "saved to {path}"
- [ ] Typecheck passes
- [ ] Verify in browser

**Testing:**
- [ ] Browser test: click save on source page, verify dialog
- [ ] Browser test: click save on target page, verify dialog
- [ ] Browser test: complete save, verify success indicator

---

## Functional Requirements

- **FR-1:** Projects must be stored as folders under `projects/` directory
- **FR-2:** Each project folder must contain its own `.gitignore` file
- **FR-3:** Root `.gitignore` must exclude the entire `projects/` directory
- **FR-4:** Project names must be unique (enforced via slug)
- **FR-5:** ProjectConfig must be serializable to/from JSON
- **FR-6:** AppState must support full serialization for project persistence
- **FR-7:** New project wizard must have 4 steps with validation
- **FR-8:** Credential import must support .env files and existing projects
- **FR-9:** Save .env dialog must allow custom file paths
- **FR-10:** Save .env must preserve existing keys in target file
- **FR-11:** State auto-save must be debounced and non-blocking
- **FR-12:** Project loading must restore full workflow state
- **FR-13:** Fetch outputs must use project-relative paths when project active

## Non-Goals (Out of Scope)

- **Project sharing/export** - Projects are local only
- **Project templates** - Each project starts fresh or imports credentials
- **Project versioning/history** - No git integration for project state
- **Multi-user project access** - Single-user local tool
- **Cloud sync** - Projects stored locally only
- **Project archiving** - Delete or keep, no archive state

## Technical Considerations

### File Structure

```
importer/web/
├── project_manager.py              # ProjectConfig, ProjectManager
├── components/
│   ├── new_project_wizard.py       # Multi-step wizard dialog
│   └── save_env_dialog.py          # File picker for .env saving
├── pages/
│   ├── home.py                     # Project selector added
│   ├── fetch_source.py             # Save dialog integration
│   └── fetch_target.py             # Save dialog integration
└── state.py                        # active_project fields added
```

### Project Folder Structure

```
projects/
└── my-migration-project/
    ├── .gitignore                  # Defense-in-depth
    ├── project.json                # ProjectConfig
    ├── state.json                  # Full AppState
    ├── .env.source                 # Source credentials
    ├── .env.target                 # Target credentials
    └── outputs/
        ├── source/
        │   └── 2024-01-15_143022/  # Timestamped fetch
        ├── target/
        │   └── 2024-01-15_150134/
        └── normalized/
            └── 2024-01-15_151245/
```

### ProjectManager Implementation

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import re
import shutil

from importer.web.state import AppState, WorkflowType

@dataclass
class OutputConfig:
    source_dir: str = "outputs/source/"
    target_dir: str = "outputs/target/"
    normalized_dir: str = "outputs/normalized/"
    use_timestamps: bool = True

@dataclass
class ProjectConfig:
    name: str
    slug: str
    workflow_type: WorkflowType
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    source_env_file: str = ".env.source"
    target_env_file: str = ".env.target"
    output_config: OutputConfig = field(default_factory=OutputConfig)

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
            "output_config": {
                "source_dir": self.output_config.source_dir,
                "target_dir": self.output_config.target_dir,
                "normalized_dir": self.output_config.normalized_dir,
                "use_timestamps": self.output_config.use_timestamps,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        output_config = OutputConfig(**data.get("output_config", {}))
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
        )


class ProjectManager:
    PROJECTS_DIR = Path("projects")
    GITIGNORE_TEMPLATE = """# Project-level gitignore (defense-in-depth)
# These files contain sensitive credentials and should NEVER be committed

# Credentials
.env.source
.env.target
.env.*

# State may contain sensitive paths
state.json

# Output files may contain sensitive data
outputs/
"""

    def __init__(self, base_path: Path = Path(".")):
        self.base_path = base_path
        self.projects_dir = base_path / self.PROJECTS_DIR

    @staticmethod
    def slugify(name: str) -> str:
        """Convert project name to URL-safe slug."""
        slug = name.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug[:50]  # Limit length

    def list_projects(self) -> list[ProjectConfig]:
        """List all projects sorted by updated_at descending."""
        if not self.projects_dir.exists():
            return []
        
        projects = []
        for folder in self.projects_dir.iterdir():
            if folder.is_dir():
                config_path = folder / "project.json"
                if config_path.exists():
                    with open(config_path) as f:
                        projects.append(ProjectConfig.from_dict(json.load(f)))
        
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
        project_path = self.projects_dir / slug
        
        if project_path.exists():
            raise ValueError(f"Project with slug '{slug}' already exists")
        
        # Create folder structure
        project_path.mkdir(parents=True)
        (project_path / "outputs" / "source").mkdir(parents=True)
        (project_path / "outputs" / "target").mkdir(parents=True)
        (project_path / "outputs" / "normalized").mkdir(parents=True)
        
        # Create .gitignore first (before any sensitive files)
        (project_path / ".gitignore").write_text(self.GITIGNORE_TEMPLATE)
        
        # Create project config
        config = ProjectConfig(
            name=name,
            slug=slug,
            workflow_type=workflow_type,
            description=description,
            output_config=output_config or OutputConfig(),
        )
        
        with open(project_path / "project.json", "w") as f:
            json.dump(config.to_dict(), f, indent=2)
        
        return config

    def load_project(self, slug: str) -> tuple[ProjectConfig, Optional[AppState]]:
        """Load project config and state."""
        project_path = self.projects_dir / slug
        config_path = project_path / "project.json"
        state_path = project_path / "state.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Project '{slug}' not found")
        
        with open(config_path) as f:
            config = ProjectConfig.from_dict(json.load(f))
        
        state = None
        if state_path.exists():
            with open(state_path) as f:
                state = AppState.from_dict(json.load(f))
        
        return config, state

    def save_project(self, slug: str, state: AppState) -> None:
        """Save state to project."""
        project_path = self.projects_dir / slug
        state_path = project_path / "state.json"
        
        with open(state_path, "w") as f:
            json.dump(state.to_dict(), f, indent=2)
        
        # Update project.json updated_at
        config_path = project_path / "project.json"
        with open(config_path) as f:
            config_data = json.load(f)
        config_data["updated_at"] = datetime.now().isoformat()
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)

    def delete_project(self, slug: str) -> None:
        """Delete project folder."""
        project_path = self.projects_dir / slug
        if project_path.exists():
            shutil.rmtree(project_path)

    def get_project_path(self, slug: str) -> Path:
        """Get path to project folder."""
        return self.projects_dir / slug
```

### State Auto-Save Implementation

```python
import asyncio
from functools import wraps
from typing import Callable

class StateSaver:
    """Debounced state saver for projects."""
    
    def __init__(self, project_manager: ProjectManager, debounce_seconds: float = 1.0):
        self.project_manager = project_manager
        self.debounce_seconds = debounce_seconds
        self._pending_save: Optional[asyncio.Task] = None
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
        await asyncio.sleep(self.debounce_seconds)
        if self._last_state and self._last_state.active_project:
            try:
                self.project_manager.save_project(
                    self._last_state.active_project,
                    self._last_state,
                )
            except Exception as e:
                # Log but don't interrupt user
                print(f"Auto-save error: {e}")
```

## Testing Plan

### Unit Tests

| Test File | Coverage |
|-----------|----------|
| `test_project_manager.py` | ProjectConfig, ProjectManager CRUD |
| `test_slugify.py` | Slug generation edge cases |
| `test_state_serialization.py` | AppState to_dict/from_dict |
| `test_gitignore_template.py` | Gitignore content validation |
| `test_env_parsing.py` | .env file parsing for import |

### Integration Tests

| Test Scenario | Description |
|---------------|-------------|
| Project lifecycle | Create → save state → load → delete |
| Credential import | Import from .env, verify files created |
| State persistence | Save state, restart app, verify restored |
| Output directories | Fetch to project folder, verify paths |

### Browser/E2E Tests

| Test Scenario | Steps |
|---------------|-------|
| New project wizard | Open wizard → complete all steps → verify project created |
| Load project | Create project → close app → reopen → verify restored |
| Delete project | Create project → delete → verify removed |
| Save .env dialog | Enter credentials → save → verify file created |
| Project switching | Create 2 projects → switch between → verify state isolated |

### Manual Testing Checklist

- [ ] Create project with special characters in name
- [ ] Create project with very long name (>100 chars)
- [ ] Import credentials from .env with various formats
- [ ] Verify gitignore prevents committing sensitive files
- [ ] Test with 10+ projects (performance)
- [ ] Test wizard cancellation at each step
- [ ] Test browser refresh during wizard
- [ ] Verify state survives app restart

## Success Metrics

- Project creation completes in under 500ms
- State auto-save completes in under 100ms
- Loading a project with full state takes under 1 second
- Home page renders 20 project cards without lag
- Wizard step transitions are instant (<50ms)
- No sensitive files appear in `git status` after project creation

## Open Questions

1. Should projects support "archiving" (hidden but not deleted)?
2. Should there be a "duplicate project" feature?
3. Should project settings be editable after creation?
4. How should we handle project folder rename if user changes project name?
5. Should we support project export/import for sharing between machines?
6. Should there be a "project notes" or "README" feature within projects?
