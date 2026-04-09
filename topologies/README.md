# dbt Cloud Topologies

Pre-built, opinionated dbt Cloud configurations for common deployment patterns. Each topology is a complete, copy-paste-ready bundle — analogous to a Helm chart — that deploys a specific pattern to your dbt Cloud account.

## Choose your topology

| Topology | Environments | Jobs | Best for |
|---|---|---|---|
| [**basic**](basic/) | Dev + Prod | CI Check, Merge Build | Teams starting out; single project, single warehouse |

More topologies coming soon.

---

## How to use a topology

1. **Pick a topology** from the table above based on your setup
2. **Copy the folder** to your own directory:
   ```bash
   cp -r topologies/basic my-dbt-cloud
   cd my-dbt-cloud
   ```
3. **Read the README** in the topology folder — it walks you through every placeholder
4. **Fill in your values** in `dbt-config.yml` (search for `YOUR_`)
5. **Set up credentials** by copying `.env.example` to `.env` and filling in secrets
6. **Deploy:**
   ```bash
   source .env
   terraform init && terraform apply
   ```

---

## Credential handling

Sensitive values (warehouse passwords, API tokens) are never stored in the YAML file. They're passed as Terraform environment variables and matched to YAML resources by key.

| Variable | Key format | What it covers |
|---|---|---|
| `TF_VAR_environment_credentials` | `{project_key}_{env_key}` | Warehouse auth per environment |
| `TF_VAR_connection_credentials` | `{connection_key}` | OAuth / service principal for the connection |
| `TF_VAR_dbt_token` | — | dbt Cloud API token |

Each topology's `.env.example` documents exactly which keys to set for that pattern.

---

## Full schema reference

Every field available in `dbt-config.yml` is documented in [`../docs/configuration/yaml-schema.md`](../docs/configuration/yaml-schema.md).
