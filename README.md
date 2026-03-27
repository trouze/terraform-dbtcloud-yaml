# terraform-dbtcloud-yaml

[![Terraform Version](https://img.shields.io/badge/terraform-%3E%3D%201.0-blue?logo=terraform)](https://www.terraform.io)
[![dbt Cloud Provider](https://img.shields.io/badge/dbt--cloud--provider-%3E%3D%201.8-blue)](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](./LICENSE)

## Get started in 60 seconds

```bash
curl -fsSL https://github.com/trouze/terraform-dbtcloud-yaml/releases/latest/download/install.sh | bash
```

This downloads the [examples/basic/](examples/basic/) starter into `./my-dbt-cloud`. No npm, no git magic — just curl and tar. To use a different directory name: `curl -fsSL ... | bash -s -- my-project`.

Then:

```bash
cd my-dbt-platform
cp .env.example .env        # fill in your dbt Cloud credentials
# edit dbt-config.yml       # replace YOUR_ placeholders with your warehouse details
source .env && terraform init && terraform apply
```

See [examples/basic/README.md](examples/basic/README.md) for a full walkthrough.

---

## Why this exists

dbt developers already speak YAML — `dbt_project.yml`, `schema.yml`, `sources.yml`. But managing the infrastructure that runs dbt (projects, environments, jobs, credentials) typically means writing Terraform HCL, a different language with a steep learning curve that most data teams don't have time to acquire.

This module flips that. You write one YAML file that describes your entire dbt Cloud setup. Terraform reads it and manages everything. Your data team owns the config. Your platform team (or a CI pipeline) owns the apply. No HCL required on day one.

---

## Quickstart

**1. Create `main.tf`**

```hcl
terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.8"
    }
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_token
  host_url   = var.dbt_host_url
}

module "dbt_cloud" {
  source = "github.com/trouze/terraform-dbtcloud-yaml"

  dbt_account_id = var.dbt_account_id
  dbt_token      = var.dbt_token
  dbt_host_url   = var.dbt_host_url
  yaml_file      = "${path.module}/dbt-config.yml"

  # Sensitive credentials passed separately (never in YAML)
  token_map               = var.token_map
  environment_credentials = var.environment_credentials
}
```

**2. Create `dbt-config.yml`**

```yaml
projects:
  - name: Analytics
    key: analytics

    repository:
      remote_url: "your-org/your-repo"
      github_installation_id: 1234567   # GitHub App installation ID

    environments:
      - name: Production
        key: prod
        connection_key: databricks_prod   # references global_connections key below
        deployment_type: production
        type: deployment
        custom_branch: main
        protected: true
        credential:
          credential_type: databricks
          catalog: main
          schema: analytics

      - name: Development
        key: dev
        connection_key: databricks_prod
        type: development

    jobs:
      - name: Daily Build
        key: daily_build
        environment_key: prod
        execute_steps:
          - dbt build
        triggers:
          schedule: true
          github_webhook: false
          git_provider_webhook: false
          on_merge: false
        schedule_type: days_of_week
        schedule_days: [1, 2, 3, 4, 5]
        schedule_hours: [6]

global_connections:
  - name: Databricks Production
    key: databricks_prod
    type: databricks
    host: adb-1234567890.1.azuredatabricks.net
    http_path: /sql/1.0/warehouses/abc123
    catalog: main
```

**3. Create `terraform.tfvars`**

```hcl
dbt_account_id = 12345
dbt_token      = "dbt_your_api_token"
dbt_host_url   = "https://cloud.getdbt.com"

# Databricks token for the Production environment credential
# Key format: "{project_key}_{env_key}"
environment_credentials = {
  analytics_prod = {
    credential_type = "databricks"
    token           = "dapi..."
    catalog         = "main"
    schema          = "analytics"
  }
}
```

**4. Deploy**

```bash
terraform init
terraform plan
terraform apply
```

That's it. Or skip the manual setup entirely — use the [60-second clone](#get-started-in-60-seconds) at the top.

---

## How credentials work

Sensitive values are never in the YAML file. They're passed as Terraform variables and matched to YAML resources by key.

| Variable | Key format | Matches |
|---|---|---|
| `token_map` | `"my_token_name"` | `credential.token_name` in YAML (Databricks legacy) |
| `environment_credentials` | `"project_key_env_key"` | Environment credential by composite key |
| `connection_credentials` | `"connection_key"` | `global_connections[].key` in YAML |
| `lineage_tokens` | `"project_key_integration_key"` | `lineage_integrations[].key` composite |
| `oauth_client_secrets` | `"oauth_config_key"` | `oauth_configurations[].key` in YAML |

The composite key for `environment_credentials` uses underscores: a project with `key: analytics` and an environment with `key: prod` → `analytics_prod`.

---

## What you can manage

**Account-level**
- `account_features` — advanced CI, partial parsing, repo caching flags
- `global_connections` — shared warehouse connections (Databricks, Snowflake, BigQuery, Postgres, Redshift)
- `service_tokens` — API tokens with scoped permissions
- `groups` — user groups with project/account permissions
- `user_groups` — user-to-group assignments
- `notifications` — email, Slack, PagerDuty, webhook alerts
- `oauth_configurations` — OAuth provider configs
- `ip_restrictions` — IP allowlist/denylist rules

**Per-project**
- `repository` — Git integration (GitHub App, GitLab deploy token, Azure DevOps, SSH)
- `environments` — deployment and development environments
- `credentials` — warehouse credentials (14 types: Databricks, Snowflake password/keypair, BigQuery, Postgres, Redshift, Athena, Fabric, Synapse, Starburst, Spark, Teradata)
- `jobs` — scheduled, CI, merge, and on-demand jobs
- `environment_variables` — project and environment-level dbt vars
- `extended_attributes` — connection-level overrides per environment
- `profiles` — links connection + credential + extended attributes
- `lineage_integrations` — Tableau/Looker lineage config
- `artefacts` — docs job and freshness job links
- `semantic_layer` — semantic layer configuration

---

## Resource protection

Set `protected: true` on any resource to prevent accidental deletion:

```yaml
global_connections:
  - name: Databricks Production
    key: databricks_prod
    protected: true   # terraform destroy will be blocked for this resource
    ...

projects:
  - name: Analytics
    key: analytics
    protected: true
    environments:
      - name: Production
        key: prod
        protected: true
        ...
```

Protection uses `lifecycle { prevent_destroy = true }` under the hood, which means the resource appears in Terraform state with a `protected_` prefix in the resource name (e.g., `dbtcloud_project.protected_projects["analytics"]`).

---

## Multi-project support

Put all your dbt Cloud projects in a single YAML file under `projects:`:

```yaml
projects:
  - name: Finance Analytics
    key: finance
    ...

  - name: Marketing Analytics
    key: marketing
    ...
```

Or keep separate YAML files per team and apply them independently:

```bash
terraform apply -var="yaml_file=./configs/finance.yml"
terraform apply -var="yaml_file=./configs/marketing.yml"
```

**Backward compatibility:** If your existing YAML uses the singular `project:` key, it still works — the module automatically wraps it in a list.

---

## Job scheduling

Three mutually exclusive schedule modes (cron takes precedence if multiple are set):

```yaml
# Cron expression
schedule_cron: "0 6 * * 1-5"

# Hours-based (every N hours)
schedule_interval: 2

# Specific days and hours
schedule_type: days_of_week
schedule_days: [1, 2, 3, 4, 5]   # 0=Sun, 6=Sat
schedule_hours: [6, 18]            # UTC
```

---

## Requirements

- Terraform >= 1.0
- dbt Cloud account with API token
- dbt Labs Terraform provider >= 1.8

---

## Documentation

- [examples/basic/](examples/basic/) — clone-and-go starter with step-by-step README
- [docs/configuration/yaml-schema.md](docs/configuration/yaml-schema.md) — full YAML field reference
- [docs/guides/cicd.md](docs/guides/cicd.md) — CI/CD setup (GitHub Actions, etc.)
- [docs/guides/best-practices.md](docs/guides/best-practices.md) — patterns and recommendations

---

## Contributing

Contributions welcome. Please open an issue before large changes to align on approach.

## License

Apache License 2.0. See [LICENSE](LICENSE).
