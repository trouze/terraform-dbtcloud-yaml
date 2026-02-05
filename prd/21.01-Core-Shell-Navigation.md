# PRD: Web UI - Part 1: Core Shell & Navigation

## Introduction

The foundational shell for the dbt Cloud Importer Web UI. This establishes the application structure, navigation system, state management, and theming—the skeleton upon which all workflow steps will be built.

This is **Part 1 of 5** in the Web UI PRD series.

## Goals

- Create a launchable NiceGUI application with proper entry point
- Establish multi-page navigation with workflow stepper
- Implement session state management that persists across page refreshes
- Provide dark/light theme support
- Set up the `.env` file management utilities

## User Stories

### US-001: Launch Web Interface
**Description:** As a user, I want to start the web interface with a simple command so that I can access the migration wizard in my browser.

**Acceptance Criteria:**
- [ ] Running `python -m importer.web` starts the NiceGUI server
- [ ] Browser automatically opens to `http://localhost:8080`
- [ ] Home/dashboard page loads showing welcome message
- [ ] Server can be stopped with Ctrl+C
- [ ] `--port` flag allows custom port (default 8080)
- [ ] `--no-open` flag prevents auto-opening browser
- [ ] Typecheck passes

---

### US-002: Navigate Workflow Steps
**Description:** As a user, I want to see my progress through the migration workflow so that I know what steps remain.

**Acceptance Criteria:**
- [ ] Left navigation drawer shows all 5 steps: Fetch, Explore, Map, Target, Deploy
- [ ] Current step is visually highlighted (different background color)
- [ ] Completed steps show checkmark indicator
- [ ] Steps are clickable for non-linear navigation
- [ ] Top header shows step name and progress (e.g., "Step 2 of 5: Explore")
- [ ] Navigation drawer is collapsible on smaller screens
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-003: Persist Session State
**Description:** As a user, I want my workflow progress to persist if I refresh the page so that I don't lose my work.

**Acceptance Criteria:**
- [ ] Current step is preserved on page refresh
- [ ] Fetched account data (if any) is preserved on refresh
- [ ] Entity selections are preserved on refresh
- [ ] Form field values are preserved on refresh
- [ ] State stored in browser local storage via NiceGUI storage API
- [ ] "Clear Session" button resets all state
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-004: Dark/Light Theme Toggle
**Description:** As a user, I want to switch between dark and light themes so that I can use my preferred visual style.

**Acceptance Criteria:**
- [ ] Theme toggle button in top-right header area
- [ ] Dark theme is the default
- [ ] Theme preference persisted in browser storage
- [ ] Toggle icon changes based on current theme (sun/moon)
- [ ] All components properly styled in both themes
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-005: View Home Dashboard
**Description:** As a user, I want to see a dashboard when I first open the app so that I can understand my options and see recent activity.

**Acceptance Criteria:**
- [ ] Welcome message with brief description of the tool
- [ ] "Start New Migration" button navigates to Fetch step
- [ ] Quick stats if previous runs exist (last run date, account name)
- [ ] Recent runs table showing last 5 fetch/normalize operations
- [ ] Recent runs sourced from `importer_runs.json` and `normalization_runs.json`
- [ ] Click recent run to load that data into explorer
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-006: Environment File Management Utility
**Description:** As a developer, I need a utility module for reading/writing `.env` files so that credential forms can load and save consistently.

**Acceptance Criteria:**
- [ ] `env_manager.py` module with `load_env()` and `save_env()` functions
- [ ] Support for reading specific keys (e.g., `DBT_SOURCE_*`)
- [ ] Support for updating specific keys without overwriting others
- [ ] Creates `.env` file if it doesn't exist
- [ ] Preserves comments and formatting in existing `.env` files
- [ ] Reuses `python-dotenv` library (already a dependency)
- [ ] Typecheck passes

## Functional Requirements

- **FR-1:** The web UI must be launchable via `python -m importer.web`
- **FR-2:** The UI must display a left navigation drawer with 5 workflow steps
- **FR-3:** Navigation must support non-linear access to any step
- **FR-4:** Session state must persist in browser storage across page refreshes
- **FR-5:** Dark and light themes must be toggleable and persisted
- **FR-6:** Home page must display recent runs from tracking JSON files
- **FR-7:** An `env_manager` utility must provide `.env` read/write functionality

## Non-Goals (Out of Scope)

- Actual fetch/normalize/deploy functionality (covered in later PRDs)
- Form validation beyond basic presence checks
- Multi-user session management
- Server-side state persistence

## Technical Considerations

### File Structure
```
importer/
├── web/
│   ├── __init__.py
│   ├── __main__.py           # Entry point: python -m importer.web
│   ├── app.py                # NiceGUI app setup, routing, theme
│   ├── state.py              # Session state dataclass and management
│   ├── env_manager.py        # .env file read/write utilities
│   ├── pages/
│   │   ├── __init__.py
│   │   └── home.py           # Dashboard/home page
│   └── components/
│       ├── __init__.py
│       └── stepper.py        # Progress stepper component
```

### Key Dependencies
```python
# Add to importer/requirements.txt
nicegui>=2.0,<3
```

### State Structure
```python
@dataclass
class AppState:
    current_step: int = 1
    fetch_complete: bool = False
    account_data: Optional[dict] = None
    selected_entities: set[str] = field(default_factory=set)
    source_credentials: dict = field(default_factory=dict)
    target_credentials: dict = field(default_factory=dict)
```

### App Entry Point Pattern
```python
# __main__.py
from importer.web.app import create_app

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    
    app = create_app()
    ui.run(port=args.port, show=not args.no_open)

if __name__ == '__main__':
    main()
```

## Success Metrics

- App launches in under 3 seconds
- Theme toggle responds instantly (no flicker)
- Page refresh preserves state with no data loss
- Navigation between steps takes under 100ms

## Open Questions

1. Should we add a "Settings" page for configuring default paths?
2. Should recent runs show across all output directories or just the default?
