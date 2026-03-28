# Basic Example

The fastest way to get a dbt Cloud project, environments, and a scheduled job under Terraform management — using only YAML.

## What's here

| File | Purpose |
|---|---|
| `dbt-config.yml` | Your dbt Cloud configuration (edit this) |
| `main.tf` | Wires the YAML file into the module (no edits needed) |
| `variables.tf` | Input variable declarations |
| `.env.example` | Environment variable template for CI/CD secrets |
| `.github/workflows/` | GitHub Actions CI (plan on PR) and CD (apply on merge) |

## Get started

**1. Get these files**

```bash
curl -fsSL https://github.com/trouze/terraform-dbtcloud-yaml/releases/latest/download/install.sh | bash
cd my-dbt-cloud
```

The script downloads a pre-packaged tarball from the latest release — no npm or git required. It falls back to `degit` or `git sparse-checkout` automatically if the release asset is unavailable. To use a different directory name: `curl -fsSL ... | bash -s -- my-project`.

**2. Set your credentials**

```bash
cp .env.example .env
```

Open `.env` and fill in:
- `DBT_ACCOUNT_ID` — from dbt Cloud Settings > Account
- `DBT_TOKEN` — a service token from Settings > API Tokens
- `ENVIRONMENT_CREDENTIALS` — warehouse token/password for your prod environment

**3. Configure your dbt Cloud setup**

Open `dbt-config.yml` and replace all `YOUR_` placeholders:
- `global_connections` — your warehouse host, http_path, catalog
- `projects[].name` and `key`
- `repository.remote_url` and `github_installation_id` (or GitLab equivalent)
- Environment `catalog` and `schema`

The credential key in `terraform.tfvars` must match `{project_key}_{env_key}`. With the defaults (`key: analytics`, env `key: prod`), the credential key is `analytics_prod`.

**4. Deploy**

```bash
source .env
terraform init
terraform plan    # review what will be created
terraform apply
```

## CI/CD (optional)

The `.github/workflows/` directory has ready-to-use GitHub Actions workflows:

- **`ci.yml`** — formats check, validates, plans on every PR, and posts the plan as a comment
- **`cd.yml`** — applies on merge to main, with an optional approval gate via GitHub Environments

Terraform state is stored as an encrypted artifact in GitHub Actions — no remote backend required to get started.

Set these GitHub repository secrets (Settings > Secrets and variables > Actions):

```
DBT_ACCOUNT_ID          numeric account ID
DBT_TOKEN               dbt Cloud service token
ENVIRONMENT_CREDENTIALS JSON, e.g. {"analytics_prod":{"credential_type":"databricks","token":"dapi...","catalog":"main","schema":"analytics"}}
AES_256_ENCRYPTION_KEY  random key used to encrypt the state artifact — generate with: openssl rand -hex 16
```

Optional secrets (omit if not used): `DBT_PAT`, `CONNECTION_CREDENTIALS`, `LINEAGE_TOKENS`, `OAUTH_CLIENT_SECRETS`.

> **When to graduate off artifact state:** artifact state works well for a single user or small team. When you need concurrent runs, state locking, or a more durable audit trail, add a [Terraform backend](https://developer.hashicorp.com/terraform/language/backend) to `main.tf` and remove the `badgerhobbs/terraform-state` steps from both workflow files.

## Going further

- [Full YAML schema reference](../../docs/configuration/yaml-schema.md) — every supported field
- [Multi-project setup](../../docs/configuration/multi-project.md)
- [CI/CD guide](../../docs/guides/cicd.md)
- [Best practices](../../docs/guides/best-practices.md)
