# Examples

Explore real-world examples and use cases for managing dbt Cloud with Terraform.

## Basic Example

The simplest possible setup to get started.

### What It Includes

- Single dbt Cloud project
- GitHub repository integration
- One production environment with Databricks credentials
- One scheduled job
- GitHub Actions workflows for CI (plan on PR) and CD (apply on merge)

### Directory Structure

```
examples/basic/
├── main.tf                         # Terraform module call
├── variables.tf                    # Input variables
├── dbt-config.yml                  # dbt Cloud configuration
├── .env.example                    # Credential template
└── .github/
    └── workflows/
        ├── ci.yml                  # Plan on PR, post as comment
        └── cd.yml                  # Apply on merge to main
```

### Try It Out

```bash
cd examples/basic
cp .env.example .env
# Edit .env with your credentials
source .env
terraform init
terraform plan
terraform apply
```

[:material-github: View Source](https://github.com/trouze/terraform-dbtcloud-yaml/tree/main/examples/basic){ .md-button }

---

## Multi-Project in One YAML

Store multiple projects in a single YAML file. All share one Terraform state.

```yaml title="dbt-config.yml"
projects:
  - name: Finance Analytics
    key: finance
    repository:
      remote_url: "your-org/finance-dbt"
      github_installation_id: 1234567
    environments:
      - name: Production
        key: prod
        type: deployment
        deployment_type: production
        connection_key: databricks_prod
        credential:
          credential_type: databricks
          catalog: main
          schema: finance_analytics
    jobs:
      - name: Daily Build
        key: daily_build
        environment_key: prod
        execute_steps:
          - dbt build
        triggers:
          schedule: true
        schedule_type: every_day
        schedule_hours: [5]

  - name: Marketing Analytics
    key: marketing
    repository:
      remote_url: "your-org/marketing-dbt"
      github_installation_id: 1234567
    environments:
      - name: Production
        key: prod
        type: deployment
        deployment_type: production
        connection_key: snowflake_prod
        credential:
          credential_type: snowflake
          auth_type: password
          user: DBT_USER
          schema: MARKETING
          database: ANALYTICS
          warehouse: TRANSFORMING
    jobs:
      - name: Daily Build
        key: daily_build
        environment_key: prod
        execute_steps:
          - dbt build
        triggers:
          schedule: true
        schedule_type: every_day
        schedule_hours: [6]
```

Environment credentials are keyed by `"{project_key}_{env_key}"`:

```bash
export TF_VAR_environment_credentials='{
  "finance_prod": {
    "credential_type": "databricks",
    "token": "dapi_finance...",
    "catalog": "main",
    "schema": "finance_analytics"
  },
  "marketing_prod": {
    "credential_type": "snowflake",
    "auth_type": "password",
    "user": "DBT_USER",
    "password": "...",
    "schema": "MARKETING",
    "database": "ANALYTICS",
    "warehouse": "TRANSFORMING"
  }
}'
```

---

## Multiple Teams — One YAML File Per Team

For larger teams, use separate YAML files and deploy with the `yaml_file` variable:

```
my-dbt-infrastructure/
├── main.tf
├── variables.tf
└── configs/
    ├── finance.yml
    ├── marketing.yml
    └── operations.yml
```

```bash
source .env

# Deploy Finance project
terraform apply -var="yaml_file=./configs/finance.yml"

# Deploy Marketing project
terraform apply -var="yaml_file=./configs/marketing.yml"
```

---

## Multi-Environment Project

Development, staging, and production environments in one project, with job deferral:

```yaml title="dbt-config.yml"
projects:
  - name: Analytics
    key: analytics
    repository:
      remote_url: "your-org/analytics-dbt"
      github_installation_id: 1234567

    environments:
      - name: Development
        key: dev
        type: development
        connection_key: databricks_prod
        custom_branch: develop
        credential:
          credential_type: databricks
          catalog: main
          schema: dev_analytics

      - name: Staging
        key: staging
        type: deployment
        deployment_type: staging
        connection_key: databricks_prod
        credential:
          credential_type: databricks
          catalog: main
          schema: staging_analytics

      - name: Production
        key: prod
        type: deployment
        deployment_type: production
        connection_key: databricks_prod
        protected: true
        credential:
          credential_type: databricks
          catalog: main
          schema: analytics

    jobs:
      - name: Production Daily
        key: prod_daily
        environment_key: prod
        execute_steps:
          - dbt build
        triggers:
          schedule: true
        schedule_type: days_of_week
        schedule_days: [1, 2, 3, 4, 5]   # Weekdays
        schedule_hours: [6]
        generate_docs: true

      - name: Staging CI
        key: staging_ci
        environment_key: staging
        execute_steps:
          - dbt build --select state:modified+
        triggers:
          on_merge: true
        deferring_environment_key: prod   # Defer to prod for state comparison
```

---

## CI/CD with GitHub Actions

Use the two-workflow pattern from `examples/basic/.github/workflows/`:

- `ci.yml` — validates and plans on every PR, posts plan as a comment (updates existing comment on re-push)
- `cd.yml` — applies on merge to main, with optional approval gate via GitHub Environments

```yaml title=".github/workflows/ci.yml (key steps)"
- name: Terraform Plan
  id: plan
  run: |
    terraform plan -no-color -out=tfplan
    terraform show -no-color tfplan > plan.txt
  continue-on-error: true

- name: Post plan as PR comment
  uses: actions/github-script@v7
  # ... posts/updates comment with plan output
```

See the [CI/CD Guide](../guides/cicd.md) for the full workflow files and GitLab/Azure DevOps equivalents.

---

## Full Schema Reference

See [YAML Schema](../configuration/yaml-schema.md) for every field with types, defaults, and examples.

### Quick Reference

```yaml
# Account-level (optional)
account_features:
  advanced_ci: true
  partial_parsing: true

global_connections:
  - name: Databricks Production
    key: databricks_prod
    type: databricks
    host: adb-1234.azuredatabricks.net
    http_path: /sql/1.0/warehouses/abc123

service_tokens:
  - name: CI Service Token
    key: ci_token
    permissions:
      - permission_set: job_runner
        all_projects: true

groups:
  - name: Developers
    key: developers
    assign_by_default: false

notifications:
  - name: prod-failures
    key: prod_failures
    notification_type: 2          # 2 = Slack
    slack_channel_id: C0123456789
    slack_channel_name: "#dbt-alerts"
    on_failure: []

# Projects (required)
projects:
  - name: Analytics
    key: analytics
    protected: false

    repository:
      remote_url: "your-org/your-repo"
      github_installation_id: 1234567

    environments:
      - name: Production
        key: prod
        type: deployment
        deployment_type: production
        connection_key: databricks_prod
        protected: true
        credential:
          credential_type: databricks
          catalog: main
          schema: analytics

    jobs:
      - name: Daily Build
        key: daily_build
        environment_key: prod
        execute_steps:
          - dbt build
        triggers:
          schedule: true
        schedule_type: every_day
        schedule_hours: [6]
        generate_docs: true
        deferring_environment_key: prod

    environment_variables:
      - name: DBT_WAREHOUSE
        environment_values:
          - env: project
            value: "prod_warehouse"
          - env: Production
            value: "prod_warehouse"
```
