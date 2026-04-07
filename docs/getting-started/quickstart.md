# Quick Start Guide

Get your dbt Cloud project set up with Terraform in under 5 minutes.

## Prerequisites

Before you begin, make sure you have:

- [x] Terraform >= 1.0 installed
- [x] dbt Cloud account with admin access
- [x] dbt Cloud API token ([generate at Profile > API Access](https://cloud.getdbt.com/settings/profile))
- [x] Git repository with your dbt project

## Step 1: Copy the Example

Start with the basic example as a template:

```bash
git clone https://github.com/dbt-labs/terraform-dbtcloud-as-yaml.git
cd terraform-dbtcloud-as-yaml/examples/basic

# Or copy to your own directory
cp -r examples/basic ~/my-dbt-setup
cd ~/my-dbt-setup
```

The basic example includes:

```
basic/
├── main.tf                         # Terraform module call
├── variables.tf                    # Input variable definitions
├── dbt-config.yml                  # Your dbt Cloud configuration
├── .env.example                    # Credential template
└── .github/
    └── workflows/
        ├── ci.yml                  # Plan on PR
        └── cd.yml                  # Apply on merge
```

## Step 2: Set Your Credentials

Credentials are passed via environment variables — never hardcoded. In CI/CD, set these as secrets in your platform (see [CI/CD Guide](../guides/cicd.md)). For local use:

```bash
cp .env.example .env
# Edit .env with your actual values, then:
source .env
```

Your `.env` should look like:

```bash
# Required
export TF_VAR_dbt_account_id=12345
export TF_VAR_dbt_token=dbtc_your_api_token
export TF_VAR_dbt_host_url=https://cloud.getdbt.com

# Environment credentials — keyed by "{project_key}_{env_key}"
export TF_VAR_environment_credentials='{
  "analytics_prod": {
    "credential_type": "databricks",
    "token": "dapi...",
    "catalog": "main",
    "schema": "analytics"
  }
}'
```

!!! tip "Where to find these values"
    - **Account ID**: Found in your dbt Cloud URL: `https://cloud.getdbt.com/accounts/{account_id}/`
    - **API Token**: Generate at [https://cloud.getdbt.com/settings/profile](https://cloud.getdbt.com/settings/profile) — starts with `dbtc_`
    - **Host URL**: `https://cloud.getdbt.com` for US multi-tenant; see [Environment Variables](../configuration/environment-variables.md) for other regions

!!! warning "Security"
    Never commit `.env` or `terraform.tfvars` to version control. Both are in `.gitignore` by default.

## Step 3: Configure Your dbt Project

Edit `dbt-config.yml` with your project details:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/dbt-labs/terraform-dbtcloud-as-yaml/main/schemas/v1.json

version: 1
account:
  name: Your Account
  host_url: https://cloud.getdbt.com

globals:
  connections:
    - name: Databricks Production
      key: databricks_prod
      type: databricks
      details:
        host: adb-1234567890.1.azuredatabricks.net
        http_path: /sql/1.0/warehouses/abc123
        catalog: main

projects:
  - name: Analytics
    key: analytics
    repository:
      remote_url: "your-org/your-repo"      # GitHub: "org/repo", or full URL
      github_installation_id: 1234567        # From GitHub App integration

    environments:
      - name: Production
        key: prod
        type: deployment
        deployment_type: production
        connection: databricks_prod          # globals.connections[].key (or id / LOOKUP:…)
        credential:
          credential_type: databricks
          catalog: main
          schema: analytics

    jobs:
      - name: Daily Build
        key: daily_build
        environment_key: prod               # References environments[].key
        execute_steps:
          - dbt build
        triggers:
          schedule: true
        schedule_type: every_day
        schedule_hours: [6]                 # 6 AM UTC
```

!!! info "`connection`"
    Environments reference a global connection with **`connection`**: the `key` from `globals.connections`, a numeric dbt Cloud connection id, or a `LOOKUP:…` placeholder for existing account connections. Alternatively, set **`primary_profile_key`** to use a profile instead of `connection`.

!!! info "Jobs at project level"
    Jobs are defined at the project level with an `environment_key` field, not nested inside environments. This makes them easier to read and reference by key for deferral.

See the [YAML Schema](../configuration/yaml-schema.md) for all available fields including global connections, service tokens, Snowflake credentials, scheduled jobs, and more.

## Step 4: Initialize Terraform

```bash
source .env

terraform init
```

You should see:

```
Initializing modules...
Downloading git::https://github.com/dbt-labs/terraform-dbtcloud-as-yaml.git...

Terraform has been successfully initialized!
```

## Step 5: Preview Changes

Always review what Terraform will create:

```bash
terraform plan
```

You'll see output like:

```
Plan: 5 to add, 0 to change, 0 to destroy.

  + dbtcloud_project.projects["analytics"]
  + dbtcloud_repository.repositories["analytics"]
  + dbtcloud_environment.environments["analytics_prod"]
  + dbtcloud_databricks_credential.credentials["analytics_prod"]
  + dbtcloud_job.jobs["analytics_daily_build"]
```

## Step 6: Apply Configuration

```bash
terraform apply
```

Type `yes` when prompted. Terraform will create your dbt Cloud project, environments, credentials, and jobs.

```
Apply complete! Resources: 5 added, 0 changed, 0 destroyed.
```

## Step 7: Verify in dbt Cloud

1. Log into [dbt Cloud](https://cloud.getdbt.com)
2. Navigate to your account
3. Confirm your project, environments, and jobs are configured correctly

## Making Changes

After initial setup, all changes go through the same loop:

1. Edit `dbt-config.yml`
2. Run `terraform plan` to preview
3. Run `terraform apply` to apply

```bash
source .env
terraform plan
terraform apply
```

## What's Next?

<div class="grid cards" markdown>

-   :material-file-document:{ .lg .middle } **YAML Schema**

    ---

    All configuration options with types, defaults, and examples

    [:octicons-arrow-right-24: YAML Schema](../configuration/yaml-schema.md)

-   :material-github-box:{ .lg .middle } **CI/CD Integration**

    ---

    Automate plan on PR and apply on merge

    [:octicons-arrow-right-24: CI/CD Guide](../guides/cicd.md)

-   :material-key:{ .lg .middle } **Environment Variables**

    ---

    Full credential variable reference

    [:octicons-arrow-right-24: Environment Variables](../configuration/environment-variables.md)

-   :material-lifebuoy:{ .lg .middle } **Troubleshooting**

    ---

    Common issues and solutions

    [:octicons-arrow-right-24: Troubleshooting](../guides/troubleshooting.md)

</div>

!!! success "You're all set!"
    Your dbt Cloud project is now managed as code. All changes are tracked in Git and deployed via Terraform.
