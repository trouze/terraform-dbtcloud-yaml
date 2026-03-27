# terraform-dbtcloud-yaml

[![Terraform Version](https://img.shields.io/badge/terraform-%3E%3D%201.0-blue?logo=terraform)](https://www.terraform.io) [![dbt Cloud Provider](https://img.shields.io/badge/dbt--cloud--provider-v1.8-blue)](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest) [![License](https://img.shields.io/badge/license-Apache%202.0-green)](https://github.com/trouze/terraform-dbtcloud-yaml/blob/main/LICENSE)

Manage your entire dbt Cloud setup with infrastructure-as-code using Terraform and YAML. Define projects, repositories, environments, credentials, and jobs in a single, human-readable YAML file.

## Why This Project Exists

dbt engineers already know YAML. They write it every day for models, sources, and tests. But managing dbt Cloud infrastructure — projects, environments, jobs, credentials — means writing Terraform HCL, a completely different language with its own mental model.

This module bridges that gap: you describe your dbt Cloud setup in YAML, and Terraform handles the rest. No HCL required for day-to-day changes.

**Benefits:**

- **YAML-based configuration** — intuitive for data engineers
- **Infrastructure as Code** — version control your dbt Cloud setup
- **Multi-project support** — manage multiple projects from one YAML or one per team
- **Complete resource coverage** — projects, environments, jobs, global connections, service tokens, groups, notifications, IP restrictions, and more
- **Safe by default** — `protected: true` prevents accidental `terraform destroy` on critical resources
- **CI/CD ready** — GitHub Actions workflows included in the example

## Quick Start

=== "Step 1: Create main.tf"

    ```hcl
    terraform {
      required_providers {
        dbtcloud = {
          source  = "dbt-labs/dbtcloud"
          version = "~> 1.8"
        }
      }
    }

    module "dbt_cloud" {
      source = "github.com/trouze/terraform-dbtcloud-yaml"

      dbt_account_id          = var.dbt_account_id
      dbt_token               = var.dbt_token
      dbt_host_url            = var.dbt_host_url
      yaml_file               = "${path.module}/dbt-config.yml"
      environment_credentials = var.environment_credentials
    }
    ```

=== "Step 2: Create dbt-config.yml"

    ```yaml
    projects:
      - name: Analytics
        key: analytics
        repository:
          remote_url: "your-org/your-repo"
          github_installation_id: 1234567

        environments:
          - name: Production
            key: prod
            type: deployment
            deployment_type: production
            connection_key: databricks_prod   # references global_connections[].key
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
    ```

=== "Step 3: Set credentials"

    ```bash
    # In CI/CD, set these as GitHub Secrets (never hardcode values here)
    # For local dev, export them before running terraform

    export TF_VAR_dbt_account_id=12345
    export TF_VAR_dbt_token=dbtc_your_api_token
    export TF_VAR_dbt_host_url=https://cloud.getdbt.com

    # Environment credentials — JSON blob keyed by "{project_key}_{env_key}"
    export TF_VAR_environment_credentials='{
      "analytics_prod": {
        "credential_type": "databricks",
        "token": "dapi...",
        "catalog": "main",
        "schema": "analytics"
      }
    }'
    ```

=== "Step 4: Deploy"

    ```bash
    terraform init
    terraform plan
    terraform apply
    ```

!!! success "That's it!"
    Your dbt Cloud project is now managed as code.

## Features

### Supported Resources

| Scope | Resources |
|-------|-----------|
| Account | Projects, global connections, service tokens, groups, user groups, notifications, OAuth configurations, IP restrictions, account features |
| Project | Repository, environments, credentials (14 warehouse types), jobs, environment variables, extended attributes, profiles, lineage integrations, project artefacts, semantic layer |

### Credential Types

Databricks, Snowflake (password + keypair), BigQuery, Postgres, Redshift, Athena, Fabric, Synapse, Starburst, Trino, Spark, Teradata — all managed from YAML.

### Multi-Project

Manage multiple dbt Cloud projects from one YAML file:

```yaml
projects:
  - name: Finance Analytics
    key: finance
    ...
  - name: Marketing Analytics
    key: marketing
    ...
```

Or one YAML file per team using `yaml_file` variable:

```bash
terraform apply -var="yaml_file=./configs/finance.yml"
```

### Credential Keys

Sensitive values are never in the YAML. They're passed as Terraform variables and matched by key:

| Variable | Key format | Matches in YAML |
|---|---|---|
| `environment_credentials` | `"project_key_env_key"` | Environment `credential:` block |
| `connection_credentials` | `"connection_key"` | `global_connections[].key` |
| `token_map` | `"token_name"` | `credential.token_name` (legacy Databricks) |
| `lineage_tokens` | `"project_key_integration_key"` | `lineage_integrations[].key` composite |
| `oauth_client_secrets` | `"oauth_config_key"` | `oauth_configurations[].key` |

### Protection Lifecycle

Set `protected: true` on any resource to prevent accidental deletion:

```yaml
environments:
  - name: Production
    key: prod
    protected: true   # terraform destroy will fail for this resource
```

## Requirements

- Terraform >= 1.0
- dbt Cloud account with admin access
- dbt Cloud API token

## What's Next?

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    ---

    Deploy your first dbt Cloud project in minutes

    [:octicons-arrow-right-24: Quick Start](getting-started/quickstart.md)

-   :material-file-document:{ .lg .middle } **YAML Schema**

    ---

    Full reference for every field in `dbt-config.yml`

    [:octicons-arrow-right-24: YAML Schema](configuration/yaml-schema.md)

-   :material-github-box:{ .lg .middle } **CI/CD Guide**

    ---

    GitHub Actions workflows for plan on PR and apply on merge

    [:octicons-arrow-right-24: CI/CD Guide](guides/cicd.md)

-   :material-book-open-variant:{ .lg .middle } **Examples**

    ---

    Real-world configuration examples

    [:octicons-arrow-right-24: Examples](getting-started/examples.md)

</div>

## Community & Support

- 📖 **Documentation** — You're reading it!
- 🐛 **Issues** — [Report bugs or request features](https://github.com/trouze/terraform-dbtcloud-yaml/issues)
- 💬 **Discussions** — [Share ideas and best practices](https://github.com/trouze/terraform-dbtcloud-yaml/discussions)

## License

Apache License 2.0. See [LICENSE](https://github.com/trouze/terraform-dbtcloud-yaml/blob/main/LICENSE) for details.

---

**Ready to manage your dbt Cloud with code?** Start with the [Quick Start Guide](getting-started/quickstart.md).
