---
task: Project Management - Phase 1 (Infrastructure)
test_command: "cd importer && python -m pytest web/tests/test_project_manager.py -v"
browser_validation: false
base_url: "http://localhost:8501"
track: project-management
---

# Task: Project Infrastructure (Epic 1)

Build the foundational project management infrastructure: ProjectConfig model, ProjectManager class, folder structure with gitignore defense-in-depth.

**PRD Reference:** `tasks/prd-web-ui-08-project-management.md` - Epic 1 (US-080 through US-084)

## Success Criteria

### US-080: Project Folder Creation

1. [ ] Create `importer/web/project_manager.py` with ProjectManager class

2. [ ] Implement `slugify(name) -> str` that converts project name to URL-safe slug (lowercase, no special chars, hyphens for spaces, max 50 chars)

3. [ ] Implement `create_project()` that creates project folder under `projects/` directory

4. [ ] Project folder contains: `project.json`, `.gitignore`, `outputs/source/`, `outputs/target/`, `outputs/normalized/`

5. [ ] Duplicate project names (same slug) raise `ValueError` with clear message

6. [ ] Run typecheck: `cd importer && pyright web/project_manager.py`

### US-081: Project-Level Gitignore

7. [ ] `.gitignore` created automatically with each new project (BEFORE any sensitive files)

8. [ ] Gitignore template ignores: `.env.source`, `.env.target`, `.env.*`, `state.json`, `outputs/`

9. [ ] File includes comment header: "# Project-level gitignore (defense-in-depth)"

### US-082: Root Gitignore Update

10. [ ] Add `projects/` entry to root `.gitignore` with explanatory comment

11. [ ] Preserve existing gitignore entries when adding

### US-083: ProjectConfig Model

12. [ ] Create `ProjectConfig` dataclass with fields: `name`, `slug`, `description`, `workflow_type`, `created_at`, `updated_at`, `source_env_file`, `target_env_file`, `output_config`

13. [ ] Add `OutputConfig` dataclass with: `source_dir`, `target_dir`, `normalized_dir`, `use_timestamps`

14. [ ] Add account summary fields: `source_host`, `source_account_id`, `target_host`, `target_account_id` (all Optional)

15. [ ] Implement `to_dict()` and `from_dict()` methods with datetime ISO format

16. [ ] Stored as `project.json` in project folder

### US-083b: ProjectSettings Model (Settings Persistence)

17. [ ] Create `ProjectSettings` dataclass with deploy settings: `disable_job_triggers`, `import_mode`, `terraform_dir`

18. [ ] Add match settings: `target_matching_enabled`, `confirmed_mappings`, `rejected_suggestions`, `cloned_resources`

19. [ ] Add protection settings: `protected_resources` (set[str])

20. [ ] Add mapping settings: `scope_mode`, `selected_project_ids`, `resource_filters`, `normalization_options`

### US-084: ProjectManager Class Methods

21. [ ] Implement `list_projects() -> list[ProjectConfig]` that scans `projects/` folder, sorted by `updated_at` descending

22. [ ] Implement `load_project(slug) -> tuple[ProjectConfig, AppState | None]`

23. [ ] Implement `save_project(slug, state: AppState)` that writes `state.json` and updates `updated_at`

24. [ ] Implement `delete_project(slug)` that removes folder recursively

25. [ ] Implement `get_project_path(slug) -> Path`

26. [ ] Implement `project_exists(slug) -> bool`

27. [ ] Implement `import_credentials(slug, env_path, source=True, target=True)` that copies credentials

### Unit Tests

28. [ ] Create `importer/web/tests/test_project_manager.py`

29. [ ] Test: slug generation from various project names (spaces, unicode, special chars)

30. [ ] Test: duplicate name detection raises ValueError

31. [ ] Test: `list_projects()` returns empty list when no projects

32. [ ] Test: `list_projects()` returns all projects sorted by updated_at

33. [ ] Test: `create_project()` creates all required files/folders

34. [ ] Test: `load_project()` returns None state for new project

35. [ ] Test: `save_project()` and `load_project()` roundtrip preserves full state

36. [ ] Test: `delete_project()` removes folder recursively

37. [ ] Test: ProjectConfig serialization round-trip preserves all fields including datetimes

## Context

### Folder Structure
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
        ├── target/
        └── normalized/
```

### WorkflowType Enum
Must integrate with existing `WorkflowType` enum: Migration, Account Explorer, Jobs as Code, Import & Adopt

## Notes

- Phase 2 will add the New Project Wizard UI
- Phase 3 will add Home Page project selector with AG Grid
- This is independent of Protection Intent track - can run in parallel
