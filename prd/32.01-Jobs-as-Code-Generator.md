# PRD: Jobs as Code Generator

A new workflow module for the terraform-dbtcloud-yaml Web UI that enables users to generate dbt-jobs-as-code YAML files from existing dbt Cloud jobs. Supports two primary workflows: adopting existing jobs under code management, and cloning/migrating jobs to different environments or accounts.

---

## 1. Problem Statement

Users managing dbt Cloud jobs face these challenges:

- **Adoption Gap**: Existing manually-created jobs cannot easily transition to jobs-as-code management
- **Migration Complexity**: Cloning jobs between environments/projects/accounts requires manual YAML creation and ID mapping
- **Trigger Management**: Jobs migrated or cloned should not run until properly configured, requiring trigger deactivation

The existing `dbt-jobs-as-code import-jobs` CLI command provides basic job export but lacks:

- Interactive job selection
- Environment/project mapping for cloning
- Trigger control during migration
- Visual workflow guidance

---

## 2. Goals

- Integrate Jobs as Code Generator into the existing terraform-dbtcloud-yaml Web UI
- Enable **Adopt Workflow**: Generate YAML with `linked_id` to take existing jobs under management
- Enable **Clone/Migrate Workflow**: Generate YAML for creating new jobs in different environments/projects/accounts
- Support both Jinja-templated and hardcoded YAML output formats
- Provide interactive environment/project mapping for target selection
- Allow bulk job renaming with pattern support
- Auto-disable triggers during migration (configurable)

---

## 3. User Stories

### 3.1 Workflow Selection

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-JG-01 | As a user, I want to select "Jobs as Code Generator" from the home page | Workflow card with clear description appears on home |
| US-JG-02 | As a user, I want to choose between "Adopt Existing Jobs" and "Clone/Migrate Jobs" | Sub-workflow selector after main workflow selection |
| US-JG-03 | As a user, I want clear explanations of each sub-workflow | Help text explaining Adopt vs Clone differences |

### 3.2 Source Fetch and Job Selection

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-JG-10 | As a user, I want to enter source dbt Cloud credentials | Credential form with Host URL, Account ID, API Token |
| US-JG-11 | As a user, I want to fetch all jobs from my source account | Fetch operation retrieves jobs via dbt Cloud API |
| US-JG-12 | As a user, I want to see a list of all fetched jobs in a grid | AG Grid with columns: Name, Project, Environment, Job Type, Triggers |
| US-JG-13 | As a user, I want to filter jobs by project, environment, or job type | Filter dropdowns and search box |
| US-JG-14 | As a user, I want to select which jobs to include | Checkbox column with Select All / Deselect All |
| US-JG-15 | As a user, I want to see job details by clicking a row | Detail panel shows full job configuration JSON |
| US-JG-16 | As a user, I want to see which jobs are already managed by jobs-as-code | Badge/icon for jobs with `[[identifier]]` in name |

### 3.3 Adopt Workflow

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-JG-20 | As a user, I want to generate YAML for adopting selected jobs | "Generate Adopt YAML" button triggers generation |
| US-JG-21 | As a user, I want each job to have a `linked_id` field | YAML includes `linked_id: <job_id>` for each job |
| US-JG-22 | As a user, I want to customize the identifier for each job | Editable "Identifier" column in grid (defaults to sanitized job name) |
| US-JG-23 | As a user, I want identifier validation (unique, valid characters) | Error if duplicate identifiers or invalid characters |
| US-JG-24 | As a user, I want to preview the generated YAML before saving | YAML preview panel with syntax highlighting |
| US-JG-25 | As a user, I want to download the generated YAML file | Download button saves `jobs.yml` locally |
| US-JG-26 | As a user, I want instructions for running the `link` command | Instructions panel shows: `dbt-jobs-as-code link jobs.yml` |

### 3.4 Clone/Migrate Workflow - Target Configuration

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-JG-30 | As a user, I want to specify whether target is same or different account | Toggle: "Same Account" / "Different Account" |
| US-JG-31 | As a user, I want to enter target account credentials (if different account) | Credential form appears when "Different Account" selected |
| US-JG-32 | As a user, I want to fetch target account environments and projects | Fetch retrieves available projects/environments from target |
| US-JG-33 | As a user, I want to see available target projects in a list | Project selector dropdown/list with project names |
| US-JG-34 | As a user, I want to see available target environments for selected project | Environment selector filtered by selected project |

### 3.5 Clone/Migrate Workflow - Mapping

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-JG-40 | As a user, I want to map source projects to target projects | Mapping table: Source Project → Target Project dropdown |
| US-JG-41 | As a user, I want to map source environments to target environments | Mapping table: Source Environment → Target Environment dropdown |
| US-JG-42 | As a user, I want auto-suggestions for environment mapping by name | Exact name matches pre-selected as suggestions |
| US-JG-43 | As a user, I want validation that all required mappings are complete | Error if job references unmapped project/environment |
| US-JG-44 | As a user, I want to handle deferring environment/job references | Mapping section for deferral references |
| US-JG-45 | As a user, I want to handle job completion trigger references | Warning for cross-job triggers; option to clear or map |

### 3.6 Clone/Migrate Workflow - Job Configuration

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-JG-50 | As a user, I want to rename jobs during clone | Editable "New Name" column in grid |
| US-JG-51 | As a user, I want bulk rename with pattern | "Add Prefix/Suffix" dialog: e.g., "[QA] {name}" |
| US-JG-52 | As a user, I want to auto-generate unique identifiers | Identifier column auto-generated from new name |
| US-JG-53 | As a user, I want to disable all triggers by default | Checkbox: "Disable triggers on cloned jobs" (default: checked) |
| US-JG-54 | As a user, I want to choose which trigger types to disable | Checkboxes: Schedule, GitHub Webhook, Git Provider Webhook, On Merge |
| US-JG-55 | As a user, I want to preserve job description | Option to keep original description or clear |
| US-JG-56 | As a user, I want to preserve custom environment variables | Option to include/exclude env var overwrites |

### 3.7 Output Format Selection

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-JG-60 | As a user, I want to choose between templated and hardcoded output | Radio: "Jinja Templated" / "Hardcoded IDs" |
| US-JG-61 | As a user, I want templated output to use `{{ project_id }}` variables | YAML contains Jinja variables for IDs |
| US-JG-62 | As a user, I want a vars file generated for templated output | Separate `vars.yml` with actual target IDs |
| US-JG-63 | As a user, I want to customize variable names in templated output | Editable variable names (e.g., `{{ prod_project_id }}`) |
| US-JG-64 | As a user, I want hardcoded output to have actual target IDs | YAML contains resolved numeric IDs |
| US-JG-65 | As a user, I want to generate multiple vars files for different environments | Option to create `vars_prod.yml`, `vars_qa.yml` etc. |

### 3.8 Generation and Export

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-JG-70 | As a user, I want to preview the generated YAML | Preview panel with syntax highlighting |
| US-JG-71 | As a user, I want to preview the vars file (if templated) | Separate preview tab for vars file |
| US-JG-72 | As a user, I want to validate the generated YAML | "Validate" button runs offline validation |
| US-JG-73 | As a user, I want to validate online against target account | "Validate Online" button checks IDs exist |
| US-JG-74 | As a user, I want to download the YAML file(s) | Download buttons for jobs.yml and vars.yml |
| US-JG-75 | As a user, I want to download as a zip archive | "Download All" creates zip with all files |
| US-JG-76 | As a user, I want to see next steps after generation | Instructions: `dbt-jobs-as-code plan jobs.yml --vars-yml vars.yml` |

### 3.9 Optional: Direct Sync

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-JG-80 | As a user, I want to run `plan` directly from the UI | "Run Plan" button executes jobs-as-code plan |
| US-JG-81 | As a user, I want to see plan output in real-time | Terminal panel streams plan output |
| US-JG-82 | As a user, I want to run `sync` to create jobs | "Run Sync" button (requires plan first) |
| US-JG-83 | As a user, I want confirmation before sync | "This will create X jobs. Continue?" dialog |

---

## 4. Technical Design

### 4.1 Workflow Steps

**Adopt Workflow:**

```
Home → Select "Jobs as Code Generator" → Select "Adopt Existing Jobs"
  → Fetch Source → Select Jobs → Configure Identifiers → Generate → Export
```

**Clone/Migrate Workflow:**

```
Home → Select "Jobs as Code Generator" → Select "Clone/Migrate Jobs"
  → Fetch Source → Select Jobs → Configure Target → Map Environments
  → Configure Jobs (rename, triggers) → Select Output Format → Generate → Export
```

### 4.2 File Structure

```
importer/web/
├── workflows/
│   └── jobs_as_code/
│       ├── __init__.py
│       ├── pages/
│       │   ├── workflow_select.py    # Adopt vs Clone selection
│       │   ├── source_fetch.py       # Source credentials + fetch
│       │   ├── job_select.py         # Job selection grid
│       │   ├── adopt_config.py       # Identifier configuration
│       │   ├── target_config.py      # Target account/project/env
│       │   ├── mapping.py            # Environment/project mapping
│       │   ├── job_config.py         # Rename, triggers config
│       │   ├── output_format.py      # Templated vs hardcoded
│       │   └── generate.py           # Preview + export
│       ├── components/
│       │   ├── job_grid.py           # Job selection AG Grid
│       │   ├── mapping_table.py      # Source→Target mapping
│       │   ├── yaml_preview.py       # YAML preview panel
│       │   └── rename_dialog.py      # Bulk rename dialog
│       └── utils/
│           ├── job_fetcher.py        # Fetch jobs via API
│           ├── yaml_generator.py     # Generate jobs-as-code YAML
│           └── validator.py          # Validate generated YAML
```

### 4.3 State Structure

```python
@dataclass
class JobsAsCodeState:
    # Workflow type
    workflow_mode: str  # "adopt" | "clone"
    
    # Source data
    source_credentials: dict
    source_jobs: list[dict]
    selected_job_ids: set[int]
    
    # Target data (clone only)
    target_same_account: bool = True
    target_credentials: dict = field(default_factory=dict)
    target_projects: list[dict] = field(default_factory=list)
    target_environments: list[dict] = field(default_factory=list)
    
    # Mapping (clone only)
    project_mapping: dict[int, int] = field(default_factory=dict)  # source_id → target_id
    environment_mapping: dict[int, int] = field(default_factory=dict)
    
    # Job configuration
    job_identifiers: dict[int, str] = field(default_factory=dict)  # job_id → identifier
    job_new_names: dict[int, str] = field(default_factory=dict)  # job_id → new_name
    
    # Trigger settings (clone only)
    disable_schedule: bool = True
    disable_github_webhook: bool = True
    disable_git_provider_webhook: bool = True
    disable_on_merge: bool = True
    
    # Output format (clone only)
    output_format: str = "templated"  # "templated" | "hardcoded"
    variable_prefix: str = ""  # e.g., "prod_" for {{ prod_project_id }}
```

### 4.4 YAML Generation Examples

**Adopt Output:**

```yaml
# yaml-language-server: $schema=https://...
jobs:
  daily_analytics_run:
    linked_id: 12345  # Links to existing job
    account_id: 43791
    project_id: 176941
    environment_id: 134459
    name: "Daily Analytics Run"
    # ... rest of job config
```

**Clone Output (Templated):**

```yaml
# yaml-language-server: $schema=https://...
jobs:
  daily_analytics_run_qa:
    account_id: "{{ account_id }}"
    project_id: "{{ project_id }}"
    environment_id: "{{ environment_id }}"
    name: "[QA] Daily Analytics Run"
    triggers:
      schedule: false
      github_webhook: false
      git_provider_webhook: false
      on_merge: false
    # ... rest of job config
```

**Clone Output (Hardcoded):**

```yaml
# yaml-language-server: $schema=https://...
jobs:
  daily_analytics_run_qa:
    account_id: 43791
    project_id: 188234
    environment_id: 145678
    name: "[QA] Daily Analytics Run"
    triggers:
      schedule: false
      github_webhook: false
      git_provider_webhook: false
      on_merge: false
    # ... rest of job config
```

### 4.5 API Integration

Leverage existing dbt-jobs-as-code client for:

- `get_jobs()` - Fetch jobs from account
- `get_environments()` - Fetch environments
- `get_projects()` - Fetch projects (if available, otherwise extract from jobs/environments)

---

## 5. UI Mockups

### 5.1 Workflow Selection

```
┌──────────────────────────────────────────────────────────────────┐
│  Jobs as Code Generator                                          │
│  ────────────────────────────────────────────────────────────────│
│                                                                  │
│  Select your workflow:                                           │
│                                                                  │
│  ┌────────────────────────────┐  ┌────────────────────────────┐  │
│  │  📥 Adopt Existing Jobs    │  │  🔄 Clone/Migrate Jobs     │  │
│  │  ─────────────────────────  │  │  ─────────────────────────  │  │
│  │  Take existing jobs under   │  │  Create copies of jobs in  │  │
│  │  dbt-jobs-as-code control.  │  │  different environments.   │  │
│  │  Jobs keep their IDs and    │  │  New jobs created with     │  │
│  │  are linked via [[id]].     │  │  mapped project/env IDs.   │  │
│  │                             │  │                             │  │
│  │  [Select]                   │  │  [Select]                   │  │
│  └────────────────────────────┘  └────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Job Selection Grid

```
┌──────────────────────────────────────────────────────────────────┐
│  Select Jobs                                    [Filter ▼] 🔍    │
│  ────────────────────────────────────────────────────────────────│
│  ☑ Select All  |  12 of 45 jobs selected                        │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │☑│ Name                    │ Project     │ Environment │ Type ││
│  │─┼─────────────────────────┼─────────────┼─────────────┼──────││
│  │☑│ Daily Analytics Run     │ Analytics   │ Production  │ Sched││
│  │☑│ Hourly Refresh          │ Analytics   │ Production  │ Sched││
│  │☐│ CI Check [[ci_check]]🔗│ Analytics   │ CI          │ CI   ││
│  │☑│ Weekly Report           │ Reporting   │ Production  │ Sched││
│  │☑│ Data Quality Tests      │ Analytics   │ Staging     │ Other││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                  │
│  🔗 = Already managed by jobs-as-code                            │
│                                                                  │
│  [Back]                                              [Continue →]│
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Environment Mapping (Clone Workflow)

```
┌──────────────────────────────────────────────────────────────────┐
│  Map Source to Target                                            │
│  ────────────────────────────────────────────────────────────────│
│                                                                  │
│  Project Mapping                                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Source Project          →  Target Project                  │  │
│  │ ───────────────────────────────────────────────────────────│  │
│  │ Analytics (176941)      →  [Analytics QA (188234)    ▼]   │  │
│  │ Reporting (176942)      →  [Reporting QA (188235)    ▼]   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Environment Mapping                                             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Source Environment      →  Target Environment              │  │
│  │ ───────────────────────────────────────────────────────────│  │
│  │ Production (134459)     →  [QA (145678)              ▼]   │  │
│  │ Staging (134460)        →  [Dev (145679)             ▼]   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ⚠️ 2 jobs reference deferring environments that need mapping    │
│                                                                  │
│  [Back]                                              [Continue →]│
└──────────────────────────────────────────────────────────────────┘
```

### 5.4 Job Configuration (Clone Workflow)

```
┌──────────────────────────────────────────────────────────────────┐
│  Configure Cloned Jobs                                           │
│  ────────────────────────────────────────────────────────────────│
│                                                                  │
│  Rename Jobs                          [Bulk Rename: Add Prefix]  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Original Name           │ New Name              │Identifier│  │
│  │ ─────────────────────────────────────────────────────────────││
│  │ Daily Analytics Run     │ [QA] Daily Analytics  │ qa_daily │  │
│  │ Hourly Refresh          │ [QA] Hourly Refresh   │ qa_hourly│  │
│  │ Weekly Report           │ [QA] Weekly Report    │ qa_weekly│  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Trigger Settings                                                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ ☑ Disable scheduled triggers                               │  │
│  │ ☑ Disable GitHub webhook triggers                          │  │
│  │ ☑ Disable Git provider webhook triggers                    │  │
│  │ ☑ Disable on-merge triggers                                │  │
│  │                                                            │  │
│  │ ℹ️ Jobs will be created with triggers disabled. Enable     │  │
│  │    them manually or update the YAML after verification.    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  [Back]                                              [Continue →]│
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Integration Points

### 6.1 terraform-dbtcloud-yaml Web UI

- Add "Jobs as Code Generator" card to home page
- Reuse existing components: credential form, terminal output, YAML preview
- Share state management patterns from existing workflows

### 6.2 dbt-jobs-as-code

- Use `DBTCloud` client for API calls (jobs, environments, projects)
- Use `export_jobs_yml()` as reference for YAML generation
- Support `linked_id` field for adopt workflow
- Generate YAML compatible with `plan`, `sync`, `link` commands

---

## 7. Success Metrics

- Adopt workflow generates valid YAML in under 5 seconds for 100 jobs
- Clone workflow completes end-to-end in under 2 minutes for 50 jobs
- Generated YAML validates successfully with `dbt-jobs-as-code validate --online`
- Zero manual ID lookups required for clone workflow
- 100% of triggers disabled when option selected

---

## 8. Non-Goals (Out of Scope)

- Automatic execution of `link` command (user runs CLI manually)
- Real-time sync between UI and dbt Cloud (generate → export flow only)
- Job completion trigger chain analysis/visualization
- Version control integration (git commit/push)
- Schedule modification (only disable/enable, not edit cron)
