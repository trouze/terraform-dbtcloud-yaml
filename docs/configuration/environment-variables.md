# Environment Variables

Learn how to manage credentials and configuration using environment variables.

## Overview

This module uses Terraform's `TF_VAR_` prefix pattern to pass sensitive values without hardcoding them in `.tf` files. This approach works seamlessly in both local development (`.env` files) and CI/CD (GitHub Secrets, etc.).

## Required Variables

These variables must be set for the module to function:

| Variable | Description | Example |
|----------|-------------|---------|
| `TF_VAR_dbt_account_id` | Your dbt Cloud account ID | `12345` |
| `TF_VAR_dbt_api_token` | dbt Cloud API token | `dbtc_xxxxx...` |
| `TF_VAR_dbt_pat` | dbt Cloud Personal Access Token | `dbtc_xxxxx...` |
| `TF_VAR_dbt_host_url` | dbt Cloud API endpoint | `https://cloud.getdbt.com/api` |
| `TF_VAR_yaml_file_path` | Path to your YAML config | `./dbt-config.yml` |

## Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TF_VAR_token_map` | Map of database credential tokens | `{}` |
| `TF_VAR_target_name` | dbt target name | `null` |

---

## Local Development Setup

### Using .env Files

The recommended approach for local development:

#### Step 1: Create .env File

```bash
# Create from example
cp .env.example .env
```

#### Step 2: Edit with Your Values

```bash title=".env"
# dbt Cloud Configuration
export TF_VAR_dbt_account_id=12345
export TF_VAR_dbt_api_token=dbtc_xxxxxxxxxxxxx
export TF_VAR_dbt_pat=dbtc_xxxxxxxxxxxxx
export TF_VAR_dbt_host_url=https://cloud.getdbt.com/api

# YAML Configuration Path
export TF_VAR_yaml_file_path=./dbt-config.yml

# Database Credentials (JSON format, single line)
export TF_VAR_token_map='{"prod_databricks":"dapi123","dev_snowflake":"abc456"}'
```

!!! warning "JSON Format for token_map"
    The `token_map` must be valid single-line JSON. Use single quotes around the entire value.

#### Step 3: Load Variables

```bash
# Load into current shell
source .env

# Verify they're set
echo $TF_VAR_dbt_account_id
```

#### Step 4: Run Terraform

```bash
terraform plan
terraform apply
```

### Using terraform.tfvars (Alternative)

If you prefer HCL syntax:

```hcl title="terraform.tfvars"
dbt_account_id  = 12345
dbt_api_token   = "dbtc_xxxxxxxxxxxxx"
dbt_pat         = "dbtc_xxxxxxxxxxxxx"
dbt_host_url    = "https://cloud.getdbt.com/api"
yaml_file_path  = "./dbt-config.yml"

token_map = {
  prod_databricks = "dapi123"
  dev_snowflake   = "abc456"
}
```

!!! danger "Never Commit terraform.tfvars"
    Add to `.gitignore`:
    ```
    terraform.tfvars
    *.tfvars
    !*.tfvars.example
    ```

---

## CI/CD Setup

### GitHub Actions

Store secrets in GitHub Settings > Secrets and variables > Actions:

```yaml title=".github/workflows/deploy.yml"
name: Deploy dbt Cloud

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
      
      - name: Terraform Init
        run: terraform init
      
      - name: Terraform Apply
        env:
          TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
          TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
          TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
          TF_VAR_dbt_host_url: https://cloud.getdbt.com/api
          TF_VAR_yaml_file_path: ./dbt-config.yml
          TF_VAR_token_map: ${{ secrets.TOKEN_MAP }}
        run: terraform apply -auto-approve
```

**Required GitHub Secrets:**
- `DBT_ACCOUNT_ID`
- `DBT_API_TOKEN`
- `DBT_PAT`
- `TOKEN_MAP` (JSON string: `{"key":"value"}`)

### GitLab CI/CD

Store in Settings > CI/CD > Variables (masked & protected):

```yaml title=".gitlab-ci.yml"
deploy:
  image: hashicorp/terraform:latest
  stage: deploy
  variables:
    TF_VAR_dbt_account_id: $DBT_ACCOUNT_ID
    TF_VAR_dbt_api_token: $DBT_API_TOKEN
    TF_VAR_dbt_pat: $DBT_PAT
    TF_VAR_dbt_host_url: "https://cloud.getdbt.com/api"
    TF_VAR_yaml_file_path: "./dbt-config.yml"
    TF_VAR_token_map: $TOKEN_MAP
  script:
    - terraform init
    - terraform apply -auto-approve
  only:
    - main
```

### Azure DevOps

Store in Pipelines > Library > Variable groups:

```yaml title="azure-pipelines.yml"
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

variables:
  - group: dbt-cloud-credentials

steps:
  - task: TerraformInstaller@0
    inputs:
      terraformVersion: 'latest'
  
  - task: TerraformTaskV2@2
    inputs:
      command: 'init'
  
  - task: TerraformTaskV2@2
    inputs:
      command: 'apply'
      environmentServiceNameAzureRM: 'terraform'
    env:
      TF_VAR_dbt_account_id: $(DBT_ACCOUNT_ID)
      TF_VAR_dbt_api_token: $(DBT_API_TOKEN)
      TF_VAR_dbt_pat: $(DBT_PAT)
      TF_VAR_dbt_host_url: 'https://cloud.getdbt.com/api'
      TF_VAR_yaml_file_path: './dbt-config.yml'
      TF_VAR_token_map: $(TOKEN_MAP)
```

---

## Token Map Configuration

The `token_map` variable maps credential names in your YAML to actual database tokens.

### How It Works

**In your YAML:**

```yaml
environments:
  - name: "Production"
    credential:
      token_name: "prod_databricks_token"  # ← This is the key
      schema: "analytics"
```

**In your environment variables:**

```bash
export TF_VAR_token_map='{"prod_databricks_token":"dapi_abc123xyz"}'
#                         ↑ Must match              ↑ Actual token
```

### Multiple Credentials Example

```bash
# Multiple database credentials
export TF_VAR_token_map='{
  "prod_databricks": "dapi_prod123",
  "dev_databricks": "dapi_dev456",
  "staging_snowflake": "sf_stg789",
  "prod_snowflake": "sf_prd012"
}'
```

!!! tip "Token Security"
    - **Never** commit actual tokens to Git
    - Use environment-specific tokens (dev, staging, prod)
    - Rotate tokens periodically
    - Use service principals, not personal tokens

---

## Finding Your dbt Cloud Values

### Account ID

1. Log into dbt Cloud
2. Look at the URL: `https://cloud.getdbt.com/accounts/{account_id}/`
3. The number after `/accounts/` is your account ID

### API Token & PAT

1. Go to [https://cloud.getdbt.com/settings/profile](https://cloud.getdbt.com/settings/profile)
2. Scroll to "API Access"
3. Click "Create Token" or "Create Service Account Token"
4. Copy the token (starts with `dbtc_`)

!!! info "Token vs PAT"
    For this module, use the same token for both `dbt_api_token` and `dbt_pat`.

### Host URL

| Region | Host URL |
|--------|----------|
| US (Multi-tenant) | `https://cloud.getdbt.com/api` |
| EMEA (Multi-tenant) | `https://emea.dbt.com/api` |
| AU (Multi-tenant) | `https://au.dbt.com/api` |
| Single-tenant | `https://{your-account}.getdbt.com/api` |

### Connection IDs

1. In dbt Cloud: Admin > Connections
2. Click on your connection
3. Look at the URL: `/connections/{connection_id}`
4. Or check the connection details page

---

## Best Practices

### Security

✅ **DO:**
- Use `.env` for local development
- Use CI/CD secrets for automation
- Add `.env` and `terraform.tfvars` to `.gitignore`
- Use service account tokens, not personal tokens
- Rotate credentials regularly
- Use different tokens for dev/staging/prod

❌ **DON'T:**
- Commit credentials to Git
- Share tokens in chat/email
- Use production tokens in development
- Hardcode credentials in `.tf` files

### Organization

```
my-dbt-project/
├── .env                  # Local credentials (gitignored)
├── .env.example          # Template (committed)
├── .gitignore            # Includes .env, *.tfvars
├── main.tf               # No credentials here!
├── variables.tf          # Variable definitions only
├── dbt-config.yml        # References token_map keys
└── configs/              # Multiple project configs
    ├── finance.yml
    ├── marketing.yml
    └── operations.yml
```

### Debugging

Check if variables are loaded:

```bash
# After source .env
env | grep TF_VAR

# Or for a specific variable
echo $TF_VAR_dbt_account_id
```

---

## Troubleshooting

### "Error: No value for required variable"

**Problem:** Terraform can't find the variable.

**Solutions:**
```bash
# Make sure to source .env
source .env

# Verify it's set
echo $TF_VAR_dbt_account_id

# Or pass directly
terraform plan -var="dbt_account_id=12345"
```

### "Invalid JSON for token_map"

**Problem:** `token_map` isn't valid JSON.

**Solutions:**
```bash
# ❌ Multi-line won't work
export TF_VAR_token_map='{
  "key": "value"
}'

# ✅ Single line
export TF_VAR_token_map='{"key":"value"}'

# ✅ Or use terraform.tfvars
token_map = {
  key = "value"
}
```

### "401 Unauthorized" from dbt Cloud

**Problem:** Invalid or expired API token.

**Solutions:**
- Regenerate token in dbt Cloud settings
- Verify token starts with `dbtc_`
- Check you're using the right account
- Ensure token has necessary permissions

---

## Next Steps

<div class="grid cards" markdown>

-   :material-file-yaml:{ .lg .middle } __YAML Schema__

    ---

    Configure your dbt projects

    [:octicons-arrow-right-24: YAML Schema](yaml-schema.md)

-   :material-github-box:{ .lg .middle } __CI/CD Guide__

    ---

    Automate deployments

    [:octicons-arrow-right-24: CI/CD Integration](../guides/cicd.md)

-   :material-lifebuoy:{ .lg .middle } __Troubleshooting__

    ---

    Common issues and solutions

    [:octicons-arrow-right-24: Troubleshooting](../guides/troubleshooting.md)

</div>
