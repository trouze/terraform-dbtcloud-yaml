# Multi-Project Setup

Learn how to manage multiple dbt Cloud projects with a single Terraform configuration.

## Overview

This module supports managing multiple dbt projects efficiently:

- **Sequential deployment**: Deploy projects one at a time
- **Parallel deployment**: Deploy multiple projects simultaneously in CI/CD
- **Shared configuration**: Reuse Terraform code across projects
- **Independent state**: Each project can have its own state file

## Architecture Patterns

### Pattern 1: Single Directory, Multiple Configs

Best for: Small teams, similar projects

```
terraform/
├── main.tf
├── variables.tf
├── .env
└── configs/
    ├── finance.yml
    ├── marketing.yml
    └── operations.yml
```

Deploy specific project:

```bash
source .env
terraform apply -var="yaml_file_path=./configs/finance.yml"
```

### Pattern 2: Separate Directories (Recommended)

Best for: Large teams, different requirements, independent state

```
dbt-infrastructure/
├── finance/
│   ├── main.tf
│   ├── variables.tf
│   ├── .env
│   └── dbt-config.yml
├── marketing/
│   ├── main.tf
│   ├── variables.tf
│   ├── .env
│   └── dbt-config.yml
└── operations/
    ├── main.tf
    ├── variables.tf
    ├── .env
    └── dbt-config.yml
```

Each directory has independent Terraform state.

### Pattern 3: Workspaces

Best for: Same configuration, different values

```
terraform/
├── main.tf
├── variables.tf
└── configs/
    ├── dev.yml
    ├── staging.yml
    └── prod.yml
```

Use Terraform workspaces:

```bash
terraform workspace new finance
terraform workspace select finance
terraform apply -var="yaml_file_path=./configs/finance.yml"
```

---

## Sequential Deployment

Deploy multiple projects one at a time.

### Bash Script

```bash title="deploy-all.sh"
#!/bin/bash

# Load credentials
source .env

# Deploy each project
for config in configs/*.yml; do
  project_name=$(basename $config .yml)
  echo "Deploying $project_name..."
  
  terraform apply \
    -var="yaml_file_path=$config" \
    -auto-approve
  
  if [ $? -eq 0 ]; then
    echo "✅ $project_name deployed successfully"
  else
    echo "❌ $project_name deployment failed"
    exit 1
  fi
done

echo "🎉 All projects deployed!"
```

Run it:

```bash
chmod +x deploy-all.sh
./deploy-all.sh
```

---

## Parallel Deployment

Deploy multiple projects simultaneously using CI/CD matrix builds.

### GitHub Actions

```yaml title=".github/workflows/deploy-multi.yml"
name: Deploy Multiple Projects

on:
  push:
    branches: [main]
    paths:
      - 'configs/**.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        project:
          - finance
          - marketing
          - operations
      fail-fast: false  # Continue even if one fails
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.6.0
      
      - name: Terraform Init
        run: terraform init
      
      - name: Deploy ${{ matrix.project }}
        env:
          TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
          TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
          TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
          TF_VAR_dbt_host_url: https://cloud.getdbt.com/api
          TF_VAR_yaml_file_path: ./configs/${{ matrix.project }}.yml
          TF_VAR_token_map: ${{ secrets.TOKEN_MAP }}
        run: |
          terraform plan -out=tfplan
          terraform apply tfplan
```

### GitLab CI/CD

```yaml title=".gitlab-ci.yml"
stages:
  - deploy

.deploy-template:
  image: hashicorp/terraform:latest
  stage: deploy
  variables:
    TF_VAR_dbt_account_id: $DBT_ACCOUNT_ID
    TF_VAR_dbt_api_token: $DBT_API_TOKEN
    TF_VAR_dbt_pat: $DBT_PAT
    TF_VAR_dbt_host_url: "https://cloud.getdbt.com/api"
    TF_VAR_token_map: $TOKEN_MAP
  script:
    - terraform init
    - terraform plan -out=tfplan
    - terraform apply tfplan
  only:
    - main

deploy-finance:
  extends: .deploy-template
  variables:
    TF_VAR_yaml_file_path: "./configs/finance.yml"

deploy-marketing:
  extends: .deploy-template
  variables:
    TF_VAR_yaml_file_path: "./configs/marketing.yml"

deploy-operations:
  extends: .deploy-template
  variables:
    TF_VAR_yaml_file_path: "./configs/operations.yml"
```

---

## Shared vs Independent State

### Shared State (Not Recommended)

All projects share one `terraform.tfstate`.

**Pros:**
- Simple setup
- One backend configuration

**Cons:**
- ⚠️ All projects must be deployed together
- ⚠️ State conflicts if deployed in parallel
- ⚠️ One failure affects all projects
- ⚠️ Slower plan/apply for large projects

### Independent State (Recommended)

Each project has its own state.

**Pros:**
- ✅ Deploy independently
- ✅ Parallel deployments
- ✅ Isolated failures
- ✅ Faster operations

**Cons:**
- More backend configurations

#### Implementation

**Option 1: Separate Directories**

```
projects/
├── finance/
│   ├── main.tf
│   └── backend.tf  # Different key
├── marketing/
│   ├── main.tf
│   └── backend.tf  # Different key
```

```hcl title="finance/backend.tf"
terraform {
  backend "s3" {
    bucket = "my-terraform-state"
    key    = "dbt-cloud/finance/terraform.tfstate"
    region = "us-east-1"
  }
}
```

**Option 2: Workspaces**

```bash
terraform workspace new finance
terraform workspace new marketing
terraform workspace new operations
```

---

## Best Practices

### 1. Naming Conventions

Use consistent naming across projects:

```yaml
# finance.yml
project:
  name: "finance-analytics"

# marketing.yml  
project:
  name: "marketing-analytics"

# operations.yml
project:
  name: "operations-analytics"
```

### 2. Shared Variables

Extract common configuration:

```hcl title="common-variables.tf"
variable "dbt_account_id" {
  type = number
}

variable "common_tags" {
  type = map(string)
  default = {
    managed_by = "terraform"
    team       = "data"
  }
}
```

### 3. Credential Management

Use project-specific tokens in `token_map`:

```bash
export TF_VAR_token_map='{
  "finance_prod_db": "token1",
  "finance_dev_db": "token2",
  "marketing_prod_db": "token3",
  "marketing_dev_db": "token4"
}'
```

### 4. CI/CD Triggers

Deploy only when relevant configs change:

```yaml
on:
  push:
    paths:
      - 'configs/finance.yml'  # Only finance project
```

### 5. Error Handling

Use `fail-fast: false` in matrix jobs to continue on failures:

```yaml
strategy:
  matrix:
    project: [finance, marketing, operations]
  fail-fast: false
```

---

## Example: Complete Multi-Project Setup

### Directory Structure

```
dbt-projects/
├── .github/
│   └── workflows/
│       └── deploy.yml
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── backend.tf
│   └── .env.example
├── configs/
│   ├── finance.yml
│   ├── marketing.yml
│   └── operations.yml
└── README.md
```

### Main Configuration

```hcl title="terraform/main.tf"
terraform {
  required_version = ">= 1.0"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.3"
    }
  }
  
  backend "s3" {
    bucket = "my-company-terraform-state"
    key    = "dbt-cloud/${var.project_name}/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_api_token
  host_url   = var.dbt_host_url
}

module "dbt_cloud" {
  source = "git::https://github.com/trouze/terraform-dbtcloud-yaml.git"
  
  dbt_account_id = var.dbt_account_id
  dbt_token      = var.dbt_api_token
  dbt_pat        = var.dbt_pat
  dbt_host_url   = var.dbt_host_url
  yaml_file      = var.yaml_file_path
  token_map      = var.token_map
  target_name    = var.target_name
}
```

### GitHub Actions Workflow

```yaml title=".github/workflows/deploy.yml"
name: Deploy dbt Projects

on:
  push:
    branches: [main]
    paths:
      - 'configs/**.yml'
      - 'terraform/**.tf'

jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      projects: ${{ steps.filter.outputs.changes }}
    steps:
      - uses: actions/checkout@v3
      
      - uses: dorny/paths-filter@v2
        id: filter
        with:
          filters: |
            finance:
              - 'configs/finance.yml'
            marketing:
              - 'configs/marketing.yml'
            operations:
              - 'configs/operations.yml'
  
  deploy:
    needs: detect-changes
    if: ${{ needs.detect-changes.outputs.projects != '[]' }}
    runs-on: ubuntu-latest
    strategy:
      matrix:
        project: ${{ fromJSON(needs.detect-changes.outputs.projects) }}
      fail-fast: false
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
      
      - name: Terraform Init
        working-directory: terraform
        run: terraform init
      
      - name: Deploy ${{ matrix.project }}
        working-directory: terraform
        env:
          TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
          TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
          TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
          TF_VAR_dbt_host_url: https://cloud.getdbt.com/api
          TF_VAR_yaml_file_path: ../configs/${{ matrix.project }}.yml
          TF_VAR_token_map: ${{ secrets.TOKEN_MAP_${{ matrix.project | upper }} }}
        run: |
          terraform workspace select -or-create ${{ matrix.project }}
          terraform plan -out=tfplan
          terraform apply tfplan
```

---

## Monitoring & Reporting

### Terraform Cloud

Use Terraform Cloud for visibility across projects:

```hcl title="backend.tf"
terraform {
  cloud {
    organization = "my-company"
    
    workspaces {
      tags = ["dbt-cloud", "production"]
    }
  }
}
```

### Custom Reporting

Track deployments across projects:

```bash title="report-status.sh"
#!/bin/bash

echo "dbt Cloud Project Status"
echo "========================"

for config in configs/*.yml; do
  project=$(basename $config .yml)
  workspace=$(terraform workspace show 2>/dev/null || echo "default")
  
  if terraform show -json | jq -e '.values' > /dev/null 2>&1; then
    status="✅ Deployed"
  else
    status="❌ Not deployed"
  fi
  
  echo "$project: $status (workspace: $workspace)"
done
```

---

## Troubleshooting

### Issue: State Lock Errors

**Problem:** Multiple parallel deploys trying to modify same state.

**Solution:** Use independent state files or workspaces.

### Issue: Credential Confusion

**Problem:** Wrong database tokens used for projects.

**Solution:** Use project-specific environment variable suffixes:

```bash
export TF_VAR_token_map_finance='{"key":"value"}'
export TF_VAR_token_map_marketing='{"key":"value"}'
```

### Issue: Slow Deployments

**Problem:** Sequential deployment takes too long.

**Solution:** Use parallel CI/CD matrix builds.

---

## Next Steps

<div class="grid cards" markdown>

-   :material-github-box:{ .lg .middle } __CI/CD Integration__

    ---

    Automate multi-project deployments

    [:octicons-arrow-right-24: CI/CD Guide](../guides/cicd.md)

-   :material-folder-multiple:{ .lg .middle } __Best Practices__

    ---

    Organize your infrastructure

    [:octicons-arrow-right-24: Best Practices](../guides/best-practices.md)

</div>
