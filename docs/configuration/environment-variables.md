# Environment Variables

Learn how to manage credentials and configuration using environment variables.

## Overview

This module uses Terraform's `TF_VAR_` prefix pattern to pass sensitive values without hardcoding them in `.tf` files. This approach works seamlessly in both local development (`.env` files) and CI/CD (GitHub Secrets, GitLab masked variables, Azure key vault, etc.).

## Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TF_VAR_dbt_account_id` | Numeric dbt Cloud account ID | `12345` |
| `TF_VAR_dbt_token` | dbt Cloud API token | `dbtc_xxxxx...` |
| `TF_VAR_dbt_host_url` | dbt Cloud host URL | `https://cloud.getdbt.com` |

## Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TF_VAR_dbt_pat` | Personal access token (for GitHub App integration; can equal `dbt_token`) | `null` |
| `TF_VAR_environment_credentials` | JSON map of environment credential objects | `{}` |
| `TF_VAR_connection_credentials` | JSON map of global connection OAuth/key credentials | `{}` |
| `TF_VAR_token_map` | Map of Databricks token names to values (legacy) | `{}` |
| `TF_VAR_lineage_tokens` | Map of lineage integration tokens | `{}` |
| `TF_VAR_oauth_client_secrets` | Map of OAuth configuration client secrets | `{}` |
| `TF_VAR_target_name` | Default dbt target name | `""` |

---

## Local Development Setup

### Using .env Files

The recommended approach for local development:

```bash
# Create from example
cp .env.example .env
```

Edit `.env` with your actual values (never commit this file):

```bash title=".env"
# --- Required ---
export TF_VAR_dbt_account_id=12345
export TF_VAR_dbt_token=dbtc_your_api_token
export TF_VAR_dbt_host_url=https://cloud.getdbt.com

# --- Environment credentials (keyed by "{project_key}_{env_key}") ---
export TF_VAR_environment_credentials='{
  "analytics_prod": {
    "credential_type": "databricks",
    "token": "dapi...",
    "catalog": "main",
    "schema": "analytics"
  }
}'

# --- Optional: Global connection OAuth credentials ---
# export TF_VAR_connection_credentials='{"databricks_prod": {"client_id": "...", "client_secret": "..."}}'

# --- Optional: Lineage integration tokens ---
# export TF_VAR_lineage_tokens='{"analytics_tableau_prod": "..."}'

# --- Optional: OAuth config client secrets ---
# export TF_VAR_oauth_client_secrets='{"snowflake_oauth": "..."}'
```

Then load and run:

```bash
source .env
terraform plan
terraform apply
```

!!! warning "JSON Format"
    JSON blob variables must be valid single-line JSON when set via `export`. In `terraform.tfvars` you can use HCL map syntax instead (see below).

### Using terraform.tfvars (Alternative)

If you prefer HCL syntax instead of JSON:

```hcl title="terraform.tfvars"
dbt_account_id = 12345
dbt_token      = "dbtc_your_api_token"
dbt_host_url   = "https://cloud.getdbt.com"

environment_credentials = {
  analytics_prod = {
    credential_type = "databricks"
    token           = "dapi..."
    catalog         = "main"
    schema          = "analytics"
  }
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

In CI/CD, set credentials as platform secrets — never in the workflow file itself.

### GitHub Actions

Store in **Settings > Secrets and variables > Actions**:

```yaml title=".github/workflows/cd.yml"
env:
  TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
  TF_VAR_dbt_token: ${{ secrets.DBT_TOKEN }}
  TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
  TF_VAR_dbt_host_url: "https://cloud.getdbt.com"
  TF_VAR_environment_credentials: ${{ secrets.ENVIRONMENT_CREDENTIALS }}
  TF_VAR_connection_credentials: ${{ secrets.CONNECTION_CREDENTIALS }}
  TF_VAR_lineage_tokens: ${{ secrets.LINEAGE_TOKENS }}
  TF_VAR_oauth_client_secrets: ${{ secrets.OAUTH_CLIENT_SECRETS }}
```

**Required secrets:** `DBT_ACCOUNT_ID`, `DBT_TOKEN`

**Credential secrets (add as needed):** `ENVIRONMENT_CREDENTIALS`, `CONNECTION_CREDENTIALS`, `LINEAGE_TOKENS`, `OAUTH_CLIENT_SECRETS`

Store each JSON blob as a single-line string in the secret value:
```
{"analytics_prod": {"credential_type": "databricks", "token": "dapi...", "catalog": "main", "schema": "analytics"}}
```

See the [CI/CD Guide](../guides/cicd.md) for complete workflow files.

### GitLab CI/CD

Store in **Settings > CI/CD > Variables** (mark as **Masked** and **Protected**):

```yaml title=".gitlab-ci.yml"
variables:
  TF_VAR_dbt_account_id: $DBT_ACCOUNT_ID
  TF_VAR_dbt_token: $DBT_TOKEN
  TF_VAR_dbt_pat: $DBT_PAT
  TF_VAR_dbt_host_url: "https://cloud.getdbt.com"
  TF_VAR_environment_credentials: $ENVIRONMENT_CREDENTIALS
  TF_VAR_connection_credentials: $CONNECTION_CREDENTIALS
```

### Azure DevOps

Store in **Pipelines > Library > Variable groups** (mark as secret):

```yaml title="azure-pipelines.yml"
env:
  TF_VAR_dbt_account_id: $(DBT_ACCOUNT_ID)
  TF_VAR_dbt_token: $(DBT_TOKEN)
  TF_VAR_dbt_pat: $(DBT_PAT)
  TF_VAR_dbt_host_url: 'https://cloud.getdbt.com'
  TF_VAR_environment_credentials: $(ENVIRONMENT_CREDENTIALS)
```

---

## Credential Variable Reference

### `environment_credentials`

Map of environment credential objects, keyed by `"{project_key}_{env_key}"`.

Each object must include `credential_type` and the type-specific fields:

```bash
export TF_VAR_environment_credentials='{
  "analytics_prod": {
    "credential_type": "databricks",
    "token": "dapi...",
    "catalog": "main",
    "schema": "analytics"
  },
  "analytics_dev": {
    "credential_type": "snowflake",
    "auth_type": "password",
    "user": "DBT_USER",
    "password": "...",
    "schema": "DEV_ANALYTICS",
    "database": "ANALYTICS",
    "warehouse": "TRANSFORMING"
  }
}'
```

The key `"analytics_prod"` maps to a project with `key: analytics` and an environment with `key: prod`.

### `connection_credentials`

Map of connection credential objects for global connections, keyed by `global_connections[].key`:

```bash
export TF_VAR_connection_credentials='{
  "databricks_prod": {
    "client_id": "...",
    "client_secret": "..."
  },
  "snowflake_prod": {
    "oauth_client_id": "...",
    "oauth_client_secret": "..."
  }
}'
```

### `token_map`

Legacy Databricks token map, keyed by `credential.token_name` in YAML:

```bash
export TF_VAR_token_map='{"my_databricks_token": "dapi_abc123"}'
```

This is the older pattern. Prefer `environment_credentials` for new setups.

### `lineage_tokens`

Tokens for Tableau/Looker lineage integrations, keyed by `"{project_key}_{integration_key}"`:

```bash
export TF_VAR_lineage_tokens='{"analytics_tableau_prod": "..."}'
```

### `oauth_client_secrets`

Client secrets for OAuth configurations, keyed by `oauth_configurations[].key`:

```bash
export TF_VAR_oauth_client_secrets='{"snowflake_oauth": "..."}'
```

---

## Finding Your dbt Cloud Values

### Account ID

1. Log into dbt Cloud
2. Look at the URL: `https://cloud.getdbt.com/accounts/{account_id}/`
3. The number after `/accounts/` is your account ID

### API Token

1. Go to [https://cloud.getdbt.com/settings/profile](https://cloud.getdbt.com/settings/profile)
2. Scroll to **API Access**
3. Click **Create Token** or use an existing service account token
4. Copy the token — it starts with `dbtc_`

!!! info "Token vs PAT"
    For most setups, use the same token for both `dbt_token` and `dbt_pat`. The PAT is only required separately if you're using GitHub App integration with a different auth token.

### Host URL

| Region | Host URL |
|--------|----------|
| US (Multi-tenant) | `https://cloud.getdbt.com` |
| EMEA (Multi-tenant) | `https://emea.dbt.com` |
| AU (Multi-tenant) | `https://au.dbt.com` |
| Single-tenant | `https://{your-account}.getdbt.com` |

---

## Best Practices

✅ **DO:**
- Use CI/CD platform secrets for all automated workflows
- Use `.env` for local development only — never in production
- Add `.env` and `terraform.tfvars` to `.gitignore`
- Use service account tokens, not personal tokens
- Rotate tokens regularly

❌ **DON'T:**
- Commit credentials to Git
- Echo secret values in scripts or logs
- Use production tokens in development
- Hardcode credentials in `.tf` files

### Debugging

Check if variables are loaded:

```bash
# After source .env
env | grep TF_VAR

# Specific variable
echo $TF_VAR_dbt_account_id
```

---

## Troubleshooting

### "Error: No value for required variable"

```bash
# Make sure to source .env first
source .env
echo $TF_VAR_dbt_account_id   # Should print your account ID

# Or pass directly
terraform plan -var="dbt_account_id=12345"
```

### "Invalid JSON for environment_credentials"

```bash
# ❌ Multi-line won't work in export
export TF_VAR_environment_credentials='{
  "key": "value"
}'

# ✅ Single line with single quotes
export TF_VAR_environment_credentials='{"analytics_prod": {"credential_type": "databricks", "token": "dapi..."}}'

# ✅ Or use terraform.tfvars with HCL syntax
```

### "401 Unauthorized"

- Regenerate token at [dbt Cloud Profile](https://cloud.getdbt.com/settings/profile)
- Verify token starts with `dbtc_`
- Confirm you're using the correct account ID
- Ensure the token has account-level permissions

---

## Next Steps

<div class="grid cards" markdown>

-   :material-file-yaml:{ .lg .middle } **YAML Schema**

    ---

    Configure your dbt projects in YAML

    [:octicons-arrow-right-24: YAML Schema](yaml-schema.md)

-   :material-github-box:{ .lg .middle } **CI/CD Guide**

    ---

    Complete GitHub Actions workflow examples

    [:octicons-arrow-right-24: CI/CD Integration](../guides/cicd.md)

-   :material-lifebuoy:{ .lg .middle } **Troubleshooting**

    ---

    Common issues and solutions

    [:octicons-arrow-right-24: Troubleshooting](../guides/troubleshooting.md)

</div>
