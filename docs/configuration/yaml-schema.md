# YAML Schema Reference

Complete reference for the dbt Cloud YAML configuration format.

## Schema Overview

The YAML configuration is validated against a JSON Schema to ensure correctness. Your IDE can use this schema for auto-completion and validation.

### IDE Setup

Add this to the top of your `dbt-config.yml`:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/trouze/terraform-dbtcloud-yaml/main/schemas/v1.json

project:
  name: "my-dbt-project"
  ...
```

!!! tip "VS Code Users"
    Install the [YAML extension by Red Hat](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) for auto-completion and validation.

---

## Root Structure

```yaml
project:              # Required: Root configuration object
  name: <string>      # Required: Project name
  repository:         # Required: Git repository configuration
    ...
  environments:       # Required: List of environments
    - ...
  environment_variables:  # Optional: Project-level env vars
    - ...
```

---

## Project Configuration

### `project.name`

**Type:** `string` (required)

**Description:** Name of your dbt Cloud project.

**Constraints:**
- Must be alphanumeric with underscores or hyphens
- 1-128 characters
- Pattern: `^[a-zA-Z0-9_-]+$`

**Examples:**

```yaml
project:
  name: "analytics"           # ✅ Valid
  name: "finance-reporting"   # ✅ Valid
  name: "data_warehouse_2"    # ✅ Valid
  name: "Finance Analytics!"  # ❌ Invalid (special char)
  name: ""                    # ❌ Invalid (empty)
```

---

## Repository Configuration

### `project.repository`

**Type:** `object` (required)

Configure Git integration for your dbt project.

#### Fields

##### `remote_url`

**Type:** `string` (required)

**Description:** Git repository URL (HTTPS or SSH format).

**Supported Providers:**
- GitHub: `https://github.com/org/repo.git` or `git@github.com:org/repo.git`
- GitLab: `https://gitlab.com/group/repo.git` or `git@gitlab.com:group/repo.git`
- Azure DevOps: `https://dev.azure.com/org/project/_git/repo`
- Bitbucket: `https://bitbucket.org/user/repo.git`

**Examples:**

```yaml
repository:
  remote_url: "https://github.com/myorg/dbt-analytics.git"   # GitHub HTTPS
  remote_url: "git@github.com:myorg/dbt-analytics.git"       # GitHub SSH
  remote_url: "https://gitlab.com/myorg/data/dbt.git"        # GitLab
  remote_url: "https://dev.azure.com/myorg/data/_git/dbt"    # Azure DevOps
```

##### `git_clone_strategy`

**Type:** `string` (optional)

**Description:** How dbt Cloud authenticates with your Git provider.

**Options:**
- `deploy_key` (default) - SSH deploy key (universal, works with all providers)
- `github_app` - GitHub App integration (GitHub only, recommended)
- `deploy_token` - GitLab deploy token (GitLab only, recommended)
- `azure_active_directory_app` - Azure AD App (Azure DevOps only)

**Auto-Detection:** If omitted, defaults to `deploy_key` for all providers.

**Examples:**

```yaml
# GitHub with GitHub App (recommended for GitHub)
repository:
  remote_url: "https://github.com/myorg/repo.git"
  git_clone_strategy: "github_app"
  github_installation_id: 12345678

# GitLab with Deploy Token (recommended for GitLab)
repository:
  remote_url: "https://gitlab.com/myorg/repo.git"
  git_clone_strategy: "deploy_token"
  gitlab_project_id: 9876543

# Universal SSH Deploy Key (works everywhere)
repository:
  remote_url: "git@github.com:myorg/repo.git"
  git_clone_strategy: "deploy_key"
```

##### Provider-Specific Fields

**GitHub:**

- `github_installation_id` (integer, required with `github_app`)
  - Your GitHub App installation ID
  - Find in: GitHub Settings > Applications > dbt Cloud

**GitLab:**

- `gitlab_project_id` (integer, required with `deploy_token`)
  - Numeric project ID
  - Find in: GitLab Project > Settings > General

**Azure DevOps:**

- `azure_active_directory_project_id` (string, required with `azure_active_directory_app`)
  - Project UUID
- `azure_active_directory_repository_id` (string, required with `azure_active_directory_app`)
  - Repository UUID
- `azure_bypass_webhook_registration_failure` (boolean, optional)
  - Set `true` if user can't register webhooks
  - Default: `false`

##### Other Fields

- `is_active` (boolean, optional) - Default: `true`
- `private_link_endpoint_id` (string, optional) - For VPC/Private Link
- `pull_request_url_template` (string, optional) - Custom PR URL template

---

## Environment Configuration

### `project.environments`

**Type:** `array` (required, min 1 item)

Define your dbt Cloud environments (dev, staging, prod, etc.).

#### Environment Object

```yaml
environments:
  - name: <string>              # Required
    type: <string>              # Required: "development" or "deployment"
    connection_id: <integer>    # Required
    credential:                 # Required
      token_name: <string>      # Required
      schema: <string>          # Required
      catalog: <string>         # Optional
    dbt_version: <string>       # Optional
    custom_branch: <string>     # Optional
    enable_model_query_history: <boolean>  # Optional
    jobs:                       # Optional
      - ...
```

#### Fields

##### `name`

**Type:** `string` (required)

Environment name (e.g., "Production", "Development", "Staging").

##### `type`

**Type:** `string` (required)

**Options:**
- `development` - For development work
- `deployment` - For production/staging deployments

##### `connection_id`

**Type:** `integer` (required)

dbt Cloud connection ID for your data warehouse.

!!! info "Where to find this"
    In dbt Cloud: Admin > Connections > Copy the connection ID

##### `credential`

**Type:** `object` (required)

Database credentials for this environment.

**Fields:**
- `token_name` (string, required) - Key in `token_map` variable containing the database token
- `schema` (string, required) - Default schema/dataset name
- `catalog` (string, optional) - Catalog name (for Unity Catalog, etc.)

**Example:**

```yaml
credential:
  token_name: "prod_databricks_token"  # References token_map["prod_databricks_token"]
  schema: "analytics_prod"
  catalog: "production"  # Optional: for Databricks Unity Catalog
```

##### `dbt_version`

**Type:** `string` (optional)

dbt version to use (e.g., `"1.6.0"`, `"1.7.1"`). Defaults to latest.

##### `custom_branch`

**Type:** `string` (optional)

Git branch to use for this environment. Defaults to repository default branch.

**Example:**

```yaml
- name: "Staging"
  custom_branch: "staging"  # Use staging branch instead of main
```

---

## Jobs Configuration

### `environments[].jobs`

**Type:** `array` (optional)

Define dbt jobs that run in this environment.

#### Job Object

```yaml
jobs:
  - name: <string>              # Required
    description: <string>       # Optional
    is_active: <boolean>        # Optional, default: true
    execute_steps:              # Required
      - <string>
    triggers:                   # Required
      schedule: <boolean>
      github_webhook: <boolean>
      git_provider_webhook: <boolean>
      on_merge: <boolean>
    # Scheduling
    schedule_type: <string>     # Optional: "every_day", "every_week", "every_month"
    schedule_hours: [<int>]     # Optional: Hours (0-23, UTC)
    schedule_days: [<int>]      # Optional: Days (0=Sun, 6=Sat)
    schedule_cron: <string>     # Optional: Custom cron expression
    # Execution
    num_threads: <int>          # Optional: 1-16, default: 4
    timeout_seconds: <int>      # Optional: 300-86400
    target_name: <string>       # Optional: dbt target name
    dbt_version: <string>       # Optional: Job-specific dbt version
    # Features
    generate_docs: <boolean>    # Optional: Generate docs
    run_lint: <boolean>         # Optional: Run linters
    run_generate_sources: <boolean>  # Optional: Source freshness
    # Deferral
    deferring_environment: <string>  # Optional: Defer to environment name
```

### Examples

#### Simple Daily Job

```yaml
jobs:
  - name: "Daily Production Run"
    execute_steps:
      - "dbt run"
      - "dbt test"
    triggers:
      schedule: true
      schedule_hours: [6]  # 6 AM UTC
      github_webhook: false
      git_provider_webhook: false
      on_merge: false
```

#### CI Job (On Merge)

```yaml
jobs:
  - name: "Production CI"
    description: "Run on merge to main"
    execute_steps:
      - "dbt build --select state:modified+"
    triggers:
      schedule: false
      github_webhook: false
      git_provider_webhook: false
      on_merge: true
    deferring_environment: "Production"  # Defer to prod for state comparison
```

#### Advanced Scheduled Job

```yaml
jobs:
  - name: "Weekly Full Refresh"
    execute_steps:
      - "dbt run --full-refresh"
      - "dbt test"
    triggers:
      schedule: true
      github_webhook: false
      git_provider_webhook: false
      on_merge: false
    schedule_type: "every_week"
    schedule_days: [0]  # Sunday
    schedule_hours: [2]  # 2 AM UTC
    num_threads: 8
    timeout_seconds: 7200  # 2 hours
    generate_docs: true
```

---

## Environment Variables

### `project.environment_variables`

**Type:** `array` (optional)

Define project-level environment variables accessible to all jobs.

#### Environment Variable Object

```yaml
environment_variables:
  - name: <string>              # Required: Must use UPPER_SNAKE_CASE
    environment_values:         # Required: Values by environment name
      <environment_name>: <string>
```

### Examples

```yaml
environment_variables:
  - name: "DBT_WAREHOUSE_NAME"
    environment_values:
      Development: "dev_warehouse"
      Staging: "staging_warehouse"
      Production: "prod_warehouse"
  
  - name: "DBT_MAX_RETRIES"
    environment_values:
      Development: "1"
      Production: "3"
```

---

## Complete Example

Here's a full example combining all elements:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/trouze/terraform-dbtcloud-yaml/main/schemas/v1.json

project:
  name: "analytics"
  
  repository:
    remote_url: "https://github.com/myorg/dbt-analytics.git"
    git_clone_strategy: "github_app"
    github_installation_id: 12345678
  
  environments:
    - name: "Development"
      type: "development"
      connection_id: 1001
      credential:
        token_name: "dev_snowflake_token"
        schema: "dev_analytics"
      custom_branch: "develop"
      enable_model_query_history: true
    
    - name: "Production"
      type: "deployment"
      connection_id: 1002
      credential:
        token_name: "prod_snowflake_token"
        schema: "analytics"
      dbt_version: "1.7.1"
      jobs:
        - name: "Daily Run"
          execute_steps:
            - "dbt run"
            - "dbt test"
          triggers:
            schedule: true
            schedule_hours: [6]
            github_webhook: false
            git_provider_webhook: false
            on_merge: false
          num_threads: 8
          generate_docs: true
        
        - name: "CI Check"
          execute_steps:
            - "dbt build --select state:modified+"
          triggers:
            schedule: false
            github_webhook: false
            git_provider_webhook: false
            on_merge: true
          deferring_environment: "Production"
  
  environment_variables:
    - name: "DBT_CLOUD_ENV"
      environment_values:
        Development: "dev"
        Production: "prod"
```

---

## Validation

The module validates your YAML against the schema during `terraform plan`. Common errors:

- **Missing required fields**: Add the required field
- **Invalid enum value**: Check allowed values in this reference
- **Type mismatch**: Ensure strings are quoted, numbers are not
- **Pattern mismatch**: Check format constraints (e.g., project name pattern)

For IDE validation, add the schema URL to your YAML file header as shown above.
