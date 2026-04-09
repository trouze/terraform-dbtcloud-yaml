# Topology: Basic dbt Cloud Setup

The minimal production-ready dbt Cloud configuration for a single-project team. Sets up the CI/merge job pattern that dbt Labs recommends as the foundation of a healthy dbt workflow.

## What this deploys

```
Global Connection (your warehouse)
    │
    └── Project (your dbt repo)
            │
            ├── Production Environment
            │       ├── CI Check job    ← runs on every pull request
            │       └── Merge Build job ← runs when a PR merges to main
            │
            └── Development Environment
                    └── (used by developers in the dbt Cloud IDE)
```

**CI Check** — slim CI using `state:modified+` and deferred state. Only builds models changed in the PR and their downstream dependents, comparing against the production artifact from the last merge.

**Merge Build** — full `dbt build` that runs when a PR merges to your main branch. Keeps the production artifact fresh so the next CI run has an accurate baseline.

---

## Before you start

Gather the following before editing any files:

| What | Where to find it |
|---|---|
| dbt Cloud account ID | dbt Cloud > Account Settings > Account (numeric ID in the URL) |
| dbt Cloud API token | dbt Cloud > Account Settings > Service Tokens |
| GitHub org and repo name | Your GitHub repository URL: `github.com/ORG/REPO` |
| Warehouse host/account | Your warehouse admin or cloud console |
| Warehouse username + password (or token) | Your warehouse admin |
| Prod schema name | Where you want dbt to write production models |
| Dev schema name | Where you want dbt to write developer models (use a separate schema) |

---

## Step 1: Fill in the YAML

Open `dbt-config.yml` and search for `YOUR_` — replace every placeholder:

| Placeholder | What to put here |
|---|---|
| `YOUR_ACCOUNT_NAME` | Any display name for your dbt Cloud account |
| `YOUR_CONNECTION_NAME` | A descriptive name for your warehouse connection |
| `YOUR_ACCOUNT_LOCATOR` | Snowflake account locator (e.g. `xy12345.us-east-1`) |
| `YOUR_DATABASE` | The Snowflake database containing your dbt models |
| `YOUR_WAREHOUSE` | The Snowflake virtual warehouse for compute |
| `YOUR_ROLE` | The Snowflake role dbt will use (or remove the line) |
| `YOUR_PROJECT_NAME` | Display name for your dbt project in dbt Cloud |
| `YOUR_ORG/YOUR_REPO` | GitHub repository in `org/repo` format |
| `YOUR_PROD_SCHEMA` | Schema where production models will be written |
| `YOUR_DEV_SCHEMA` | Schema where IDE development models will be written |

**Using a different warehouse?** The YAML has commented-out connection and credential blocks for Databricks and BigQuery directly below the Snowflake blocks. Uncomment the one that matches your warehouse and remove the Snowflake block.

---

## Step 2: Set up credentials

Sensitive values (passwords, tokens) are never in the YAML — they're passed as environment variables.

```bash
cp .env.example .env
```

Open `.env` and fill in:

1. **dbt Cloud credentials** — account ID, API token, host URL
2. **Warehouse credentials** — the `TF_VAR_environment_credentials` JSON block

The credential keys must match your YAML keys exactly. This topology uses:
- `analytics_prod` → credentials for the Production environment
- `analytics_dev` → credentials for the Development environment

The `.env.example` file has warehouse-specific credential blocks for Snowflake (active), Databricks, and BigQuery (commented out). Uncomment the block that matches your warehouse.

Add `.env` to your `.gitignore` — never commit it.

---

## Step 3: Deploy

```bash
source .env

terraform init
terraform plan   # Review what will be created
terraform apply
```

Terraform will create the connection, project, two environments, and two jobs in your dbt Cloud account.

---

## What you'll get

After `terraform apply`, your dbt Cloud account will have:

- A **global warehouse connection** that both environments share
- A **dbt project** linked to your GitHub repository with the dbt Cloud GitHub App
- A **Production environment** configured as the deployment target
- A **Development environment** for the dbt Cloud IDE
- A **CI Check job** that fires on every pull request — runs `dbt build --select state:modified+ --defer --favor-state` against the production deferred state (slim CI)
- A **Merge Build job** that fires when a PR merges — runs `dbt build` to keep production artifacts current

To see your resources: dbt Cloud > Deploy > Environments / Jobs.

---

## CI/CD (GitHub Actions)

To run this from a GitHub Actions pipeline:

```yaml
- name: Apply dbt Cloud config
  env:
    TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
    TF_VAR_dbt_token: ${{ secrets.DBT_API_TOKEN }}
    TF_VAR_dbt_pat: ${{ secrets.DBT_API_TOKEN }}
    TF_VAR_environment_credentials: ${{ secrets.DBT_ENVIRONMENT_CREDENTIALS }}
  run: |
    terraform init
    terraform apply -auto-approve
```

Store `TF_VAR_environment_credentials` as a JSON-encoded secret (the full blob from `.env.example`).

---

## Next steps

- **Add a scheduled daily job** — extend `dbt-config.yml` with a job using `schedule: true` and a `schedule_cron`
- **Add notifications** — wire Slack or email alerts to your jobs via `globals.notifications`
- **Explore other topologies** — see [`../README.md`](../README.md) for more patterns
- **Full schema reference** — [`../../docs/configuration/yaml-schema.md`](../../docs/configuration/yaml-schema.md)
