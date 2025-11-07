# Quick Start Guide

Get your dbt Cloud project set up with Terraform in under 5 minutes.

## Prerequisites

Before you begin, make sure you have:

- [x] Terraform >= 1.0 installed
- [x] dbt Cloud account with admin access
- [x] dbt Cloud API token ([Get one here](https://cloud.getdbt.com/settings/profile))
- [x] Git repository with your dbt project

## Step 1: Clone the Example

Start with the basic example as a template:

```bash
git clone https://github.com/trouze/dbt-terraform-modules-yaml.git
cd dbt-terraform-modules-yaml/examples/basic

# Or copy to your own directory
cp -r examples/basic ~/my-dbt-setup
cd ~/my-dbt-setup
```

The basic example includes:

```
basic/
├── main.tf              # Terraform configuration
├── variables.tf         # Input variable definitions
├── dbt-config.yml      # Your dbt Cloud configuration
└── .env.example        # Credential template
```

## Step 2: Configure Your Credentials

Create a `.env` file for your dbt Cloud credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```bash
# Required: dbt Cloud credentials
export TF_VAR_dbt_account_id=12345
export TF_VAR_dbt_api_token=dbtc_xxxxxxxxxxxxx
export TF_VAR_dbt_pat=dbtc_xxxxxxxxxxxxx
export TF_VAR_dbt_host_url=https://cloud.getdbt.com/api

# Optional: Path to your YAML config (you can pass this via -var flag to switch between projects easily)
export TF_VAR_yaml_file_path=./dbt-config.yml

# Optional: Database credential tokens (if using Databricks, Snowflake, etc.)
export TF_VAR_token_map='{"my_credential":"abc123"}'
```

!!! tip "Where to find these values"
    - **Account ID**: Found in your dbt Cloud URL: `https://cloud.getdbt.com/accounts/{account_id}/`
    - **API Token**: Generate at [https://cloud.getdbt.com/settings/profile](https://cloud.getdbt.com/settings/profile)
    - **PAT**: Same as API Token (Personal Access Token)
    - **Host URL**: `https://cloud.getdbt.com/api` for US, check [docs](https://docs.getdbt.com/docs/dbt-cloud/api-v2) for other regions

!!! warning "Security"
    Never commit `.env` to version control! It's already in `.gitignore`.

## Step 3: Configure Your dbt Project

Edit `dbt-config.yml` with your project details:

```yaml
project:
  name: "my-dbt-project"
  repository:
    remote_url: "https://github.com/myorg/my-dbt-repo.git"
    git_clone_strategy: "github_app"  # or "deploy_key", "gitlab_deploy_token"
    github_installation_id: 123456     # Your GitHub App installation ID
  
  environments:
    - name: "Production"
      type: "deployment"
      connection_id: 1  # Your dbt Cloud connection ID
      credential:
        token_name: "databricks_token"  # Maps to token_map
        schema: "prod"
      jobs:
        - name: "Daily Production Run"
          execute_steps:
            - "dbt run"
            - "dbt test"
          triggers:
            schedule: true
            schedule_hours: [6]  # 6 AM daily
            schedule_days: [0, 1, 2, 3, 4]  # Weekdays
```

!!! info "Git Clone Strategies"
    Choose based on your Git provider:
    
    - **GitHub**: `github_app` (recommended) or `deploy_key`
    - **GitLab**: `gitlab_deploy_token` or `deploy_key`
    - **Azure DevOps**: `azure_active_directory_app`
    - **Other**: `deploy_key` (universal SSH)

## Step 4: Initialize Terraform

Load your credentials and initialize:

```bash
# Load credentials from .env
source .env

# Initialize Terraform
terraform init
```

You should see:

```
Initializing modules...
Downloading git::https://github.com/trouze/dbt-terraform-modules-yaml.git...

Terraform has been successfully initialized!
```

## Step 5: Preview Changes

Always review what Terraform will create:

```bash
terraform plan
```

You'll see an output like:

```
Plan: 8 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + project_id      = (known after apply)
  + repository_id   = (known after apply)
  + environment_ids = {
      + "Production" = (known after apply)
    }
```

!!! tip "Understanding the Plan"
    - **Resources being created**: Project, repository, environments, credentials, jobs
    - **Nothing exists yet**: Resources are only created when you run `apply`
    - **Review carefully**: Make sure connection IDs, URLs, and names are correct

## Step 6: Apply Configuration

Create your dbt Cloud infrastructure:

```bash
terraform apply
```

Type `yes` when prompted. Terraform will create:

1. ✅ dbt Cloud project
2. ✅ Repository connection
3. ✅ Environments (Production, Development, etc.)
4. ✅ Credentials (database connections)
5. ✅ Jobs (scheduled runs, CI checks)

```
Apply complete! Resources: 8 added, 0 changed, 0 destroyed.

Outputs:
project_id = 12345
repository_id = 67890
environment_ids = {
  "Production" = 11111
}
```

## Step 7: Verify in dbt Cloud

1. Log into [dbt Cloud](https://cloud.getdbt.com)
2. Navigate to your account
3. You should see your new project!
4. Check that environments and jobs are configured correctly

## What's Next?

<div class="grid cards" markdown>

-   :material-rocket:{ .lg .middle } __Customize Your Setup__

    ---

    Learn about all configuration options

    [:octicons-arrow-right-24: YAML Schema](../configuration/yaml-schema.md)

-   :material-github-box:{ .lg .middle } __CI/CD Integration__

    ---

    Automate deployments with GitHub Actions

    [:octicons-arrow-right-24: CI/CD Guide](../guides/cicd.md)

-   :material-book-multiple:{ .lg .middle } __More Examples__

    ---

    See real-world use cases

    [:octicons-arrow-right-24: Examples](examples.md)

-   :material-lifebuoy:{ .lg .middle } __Need Help?__

    ---

    Common issues and solutions

    [:octicons-arrow-right-24: Troubleshooting](../guides/troubleshooting.md)

</div>

## Making Changes

After initial setup, you can modify your configuration:

1. Edit `dbt-config.yml`
2. Run `terraform plan` to preview changes
3. Run `terraform apply` to apply them

```bash
# Example: Add a new environment
nano dbt-config.yml  # Add new environment
source .env
terraform plan      # Review changes
terraform apply     # Apply changes
```

!!! success "You're All Set!"
    Your dbt Cloud project is now managed as code. All changes are tracked in Git and deployed via Terraform.
