# terraform-dbtcloud-as-yaml

[![Terraform Version](https://img.shields.io/badge/terraform-%3E%3D%201.0-blue?logo=terraform)](https://www.terraform.io)
[![dbt Cloud Provider](https://img.shields.io/badge/dbt--cloud--provider-%3E%3D%201.9-blue)](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](./LICENSE)

Managing dbt Cloud infrastructure shouldn't require deep Terraform expertise. Whether you've never written HCL or just don't want to untangle the provider's resource model yourself, this module gives you a single YAML file that maps to how dbt Platform actually works — projects, environments, jobs, and connections — with relationship wiring, credential handling, and production safeguards built in.

## Begin managing your dbt Platform resources as code in 60 seconds

```bash
curl -fsSL https://github.com/trouze/terraform-dbtcloud-as-yaml/releases/latest/download/install.sh | bash
```

This downloads the [topologies/basic/](topologies/basic/) starter into `./my-dbt-cloud`. No npm, no git magic — just curl and tar. To use a different directory name: `curl -fsSL ... | bash -s -- my-project`.

Then:

```bash
cd my-dbt-cloud
cp .env.example .env        # fill in your dbt Cloud credentials
# edit dbt-config.yml       # replace YOUR_ placeholders with your warehouse details
source .env && terraform init && terraform apply
```

See [topologies/basic/README.md](topologies/basic/README.md) for a full walkthrough.

---

## Who this is for

Teams that want to manage **dbt Cloud** projects, environments, jobs, and related settings from a single YAML file—without writing Terraform HCL for every resource. Typical users are analytics engineers and data platform engineers who already maintain `dbt_project.yml` and related config, and platform teams that run `terraform plan` / `apply` in CI or manually.

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
  source = "github.com/trouze/terraform-dbtcloud-as-yaml"

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

Configuration uses **`version: 1`**, an **`account`** block (including `host_url` for the dbt Cloud region), shared resources under **`globals`** (connections, service tokens, groups, notifications, PrivateLink endpoints), and a **`projects`** list. Validate in your editor with [`schemas/v1.json`](docs/configuration/yaml-schema.md).

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/trouze/terraform-dbtcloud-as-yaml/main/schemas/v1.json

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
      remote_url: "your-org/your-repo"
      github_installation_id: 1234567   # GitHub App installation ID

    environments:
      - name: Production
        key: prod
        connection: databricks_prod      # globals.connections[].key (or numeric id / LOOKUP:…)
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
        connection: databricks_prod
        type: development
        credential:
          credential_type: databricks
          catalog: main
          schema: analytics_dev

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
| `token_map` | `"my_token_name"` | `credential.token_name` (Databricks legacy) or `jobs[].environment_variable_overrides` values prefixed with `secret_` |
| `environment_credentials` | `"project_key_env_key"` | Environment credential by composite key |
| `connection_credentials` | `"connection_key"` | `globals.connections[].key` in YAML |
| `lineage_tokens` | `"project_key_integration_key"` | `lineage_integrations[].key` composite |
| `oauth_client_secrets` | `"oauth_config_key"` | `oauth_configurations[].key` in YAML |

The composite key for `environment_credentials` uses underscores: a project with `key: analytics` and an environment with `key: prod` → `analytics_prod`.

---

## What you can manage

**Account-level** (optional unless noted; shared connections and RBAC live under `globals` in YAML)
- `account_features` — advanced CI, partial parsing, repo caching flags
- `globals.connections` — shared warehouse connections (Databricks, Snowflake, BigQuery, Postgres, Redshift, and other adapter types supported by the provider)
- `globals.service_tokens` — API tokens with scoped permissions
- `globals.groups` — user groups with project/account permissions
- `user_groups` — user-to-group assignments (document root)
- `globals.notifications` — job alerts (dbt Cloud user, Slack channel, or external email)
- `oauth_configurations` — OAuth provider configs
- `ip_restrictions` — IP allowlist/denylist rules

**Per-project**
- `repository` — Git integration (GitHub App, GitLab, Azure DevOps, deploy key/token)
- `environments` — deployment and development environments (reference a global connection with `connection`, or use `primary_profile_key` when using profiles)
- per-environment `credential` — warehouse credentials (many adapter types; secrets via `environment_credentials`)
- `jobs` — scheduled, CI, merge, and other job types; optional `environment_variable_overrides` for job-specific env vars
- `environment_variables` — project- and environment-scoped dbt vars (with map or list `environment_values` forms normalized at apply time)
- `extended_attributes` — connection-level override payloads linked from environments
- `profiles` — link connection, credentials, and extended attributes for deployment environments
- `lineage_integrations` — Tableau / Looker lineage config
- `project_artefacts` — docs job and freshness job keys
- `semantic_layer_config` — semantic layer target environment

---

## Resource protection

Set `protected: true` on any resource to prevent accidental deletion:

```yaml
globals:
  connections:
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

## Validate your YAML in CI (GitHub Action)

Use the bundled `validate` action to check your `dbt-config.yml` against the
JSON schema **before** running Terraform or supplying any dbt Cloud credentials.
This catches typos and structural errors early in your pull-request workflow.

```yaml
# .github/workflows/dbt-cloud-validate.yml
name: Validate dbt Cloud YAML

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dbt-labs/terraform-dbtcloud-as-yaml/validate@v1  # pin to a release tag or commit SHA
        with:
          file: dbt-config.yml   # default; omit if your file is named dbt-config.yml
```

| Input | Default | Description |
|---|---|---|
| `file` | `dbt-config.yml` | Path to the YAML file to validate (relative to the workspace root). |

The action exits with code `1` and prints a structured error report when the
file does not conform to the schema, so your CI run fails fast without needing
Terraform credentials.

---

## Requirements

- Terraform >= 1.0
- dbt Cloud account with API token
- dbt Labs Terraform provider >= 1.8

---

## Documentation

- **Hosted docs (GitHub Pages):** [dbt-labs.github.io/terraform-dbtcloud-as-yaml](https://dbt-labs.github.io/terraform-dbtcloud-as-yaml/)
- [topologies/basic/](topologies/basic/) — clone-and-go starter with step-by-step README
- [docs/configuration/yaml-schema.md](docs/configuration/yaml-schema.md) — full YAML field reference
- [docs/guides/cicd.md](docs/guides/cicd.md) — CI/CD setup (GitHub Actions, etc.)
- [docs/guides/best-practices.md](docs/guides/best-practices.md) — patterns and recommendations

---

## Support and maintenance

This project is provided **as-is**, without SLAs or contractual support. dbt Labs and maintainers may address bugs and improvements on a **best-effort** basis.

- **Questions and ideas:** [GitHub Discussions](https://github.com/dbt-labs/terraform-dbtcloud-as-yaml/discussions)
- **Bugs and feature requests:** [GitHub Issues](https://github.com/dbt-labs/terraform-dbtcloud-as-yaml/issues)
- **Security:** see [SECURITY.md](SECURITY.md) (do not file public issues for undisclosed vulnerabilities)

For contribution workflow, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributing

Contributions welcome. Please open an issue before large changes to align on approach. See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
