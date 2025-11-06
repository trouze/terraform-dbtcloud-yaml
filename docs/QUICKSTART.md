# Quick Start Guide

Get your dbt Cloud infrastructure up and running in 5 minutes!

## Prerequisites

- ✅ Terraform >= 1.0 installed
- ✅ dbt Cloud account with API access
- ✅ Git repository for your dbt project
- ✅ dbt Cloud connection already created (you'll need the connection ID)

## Step 1: Create Your Workspace

```bash
mkdir my-dbt-terraform
cd my-dbt-terraform
```

## Step 2: Create Main Configuration

Create `main.tf`:

```hcl
terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 0.3"
    }
  }
}

module "dbt_cloud" {
  source = "git::https://github.com/yourusername/dbt-terraform-modules-yaml.git?ref=v1.0.0"
  
  yaml_file        = file("${path.module}/dbt-config.yml")
  dbt_account_id   = var.dbt_account_id
  dbt_token        = var.dbt_token
  dbt_host_url     = var.dbt_host_url
  token_map        = var.token_map
  target_name      = var.target_name
}

output "project_id" {
  value       = module.dbt_cloud.project_id
  description = "Your dbt Cloud project ID"
}

output "job_ids" {
  value       = module.dbt_cloud.job_ids
  description = "Map of job names to IDs"
}
```

## Step 3: Create Variables File

Create `variables.tf`:

```hcl
variable "dbt_account_id" {
  type      = number
  sensitive = true
}

variable "dbt_token" {
  type      = string
  sensitive = true
}

variable "dbt_host_url" {
  type    = string
  default = "https://cloud.getdbt.com"
}

variable "token_map" {
  type      = map(string)
  default   = {}
  sensitive = true
}

variable "target_name" {
  type    = string
  default = "prod"
}
```

## Step 4: Create Your YAML Configuration

Create `dbt-config.yml`:

```yaml
project:
  name: my_analytics_project
  repository:
    remote_url: https://github.com/your-org/dbt-analytics.git
  
  environments:
    - name: Development
      type: development
      connection_id: 12345  # Get this from dbt Cloud UI
      credential:
        token_name: dev_token
        schema: dev
      dbt_version: "1.5.0"
      jobs:
        - name: dev_run
          description: "Development run"
          is_active: true
          execute_steps:
            - "dbt run"
            - "dbt test"
          triggers:
            github_webhook: true
            git_provider_webhook: false
            schedule: false
            on_merge: false
    
    - name: Production
      type: deployment
      connection_id: 12346  # Get this from dbt Cloud UI
      credential:
        token_name: prod_token
        schema: prod
      dbt_version: "1.5.0"
      jobs:
        - name: daily_build
          description: "Daily production build"
          is_active: true
          execute_steps:
            - "dbt run"
            - "dbt test"
          triggers:
            github_webhook: false
            git_provider_webhook: false
            schedule: true
            on_merge: false
          schedule_type: "every_day"
          schedule_hours: [6]
```

## Step 5: Create Credentials File

Create `terraform.tfvars`:

```hcl
dbt_account_id = YOUR_ACCOUNT_ID
dbt_token      = "dbtc_YOUR_TOKEN"
dbt_host_url   = "https://cloud.getdbt.com"

# If using database tokens, map them here
token_map = {
  "dev_token"  = "your-dev-token-value"
  "prod_token" = "your-prod-token-value"
}

target_name = "prod"
```

⚠️ **IMPORTANT**: Never commit `terraform.tfvars` to version control!

## Step 6: Deploy

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy
terraform apply
```

## Verify

Check your dbt Cloud UI to see your new project, environments, and jobs!

## Troubleshooting

**Error: "yaml_file must point to a valid, readable file"**
- Verify the path to your `dbt-config.yml` is correct
- Try: `ls -la ./dbt-config.yml`

**Error: "dbt_account_id must be a positive integer"**
- Check your `terraform.tfvars` - make sure `dbt_account_id` is a number (no quotes)

**Error: "credential not found"**
- Ensure your tokens in `token_map` match the `token_name` values in your YAML

**Need help?**
- Check the [README](README.md) for full documentation
- Review the [examples](examples/) directory
- See [Troubleshooting](README.md#troubleshooting) section

## Next Steps

- ✅ Read the [full README](README.md)
- ✅ Review [YAML Configuration Spec](README.md#yaml-configuration-spec)
- ✅ Check out [Advanced Examples](examples/)
- ✅ Set up [Remote State](https://developer.hashicorp.com/terraform/language/state/remote)
