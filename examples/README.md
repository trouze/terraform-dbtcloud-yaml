# Examples

## basic/

Minimal working example. Copy it, fill in your values, and deploy.

```
examples/basic/
├── main.tf              # Root module — provider + module block
├── variables.tf         # All input variable definitions with descriptions
└── dbt-config.yml       # Full annotated YAML schema example
```

### Steps

```bash
cp -r examples/basic my-dbt-setup
cd my-dbt-setup
```

Create `terraform.tfvars`:

```hcl
dbt_account_id = 12345
dbt_token      = "dbt_your_api_token"
dbt_host_url   = "https://cloud.getdbt.com"

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

Edit `dbt-config.yml` with your project details, then:

```bash
terraform init
terraform plan
terraform apply
```

---

## Credential keys

Sensitive values are never in the YAML. They're passed as Terraform variables and matched to YAML resources by key.

| Variable | Key format | Matches in YAML |
|---|---|---|
| `token_map` | `"token_name"` | `credential.token_name` (Databricks legacy) or `secret_*` values in `jobs[].environment_variable_overrides` |
| `environment_credentials` | `"project_key_env_key"` | Environment `credential:` block |
| `connection_credentials` | `"connection_key"` | `globals.connections[].key` |
| `lineage_tokens` | `"project_key_integration_key"` | `lineage_integrations[].key` composite |
| `oauth_client_secrets` | `"oauth_config_key"` | `oauth_configurations[].key` |

Keys use underscores and must exactly match the `key:` values in your YAML.

---

## Multiple teams / projects

**Option A — one YAML, multiple projects in a list:**
```yaml
projects:
  - name: Finance Analytics
    key: finance
    ...
  - name: Marketing Analytics
    key: marketing
    ...
```

**Option B — one YAML file per team, one Terraform workspace per team:**
```bash
terraform apply -var="yaml_file=./configs/finance.yml"
terraform apply -var="yaml_file=./configs/marketing.yml"
```

---

## CI/CD (GitHub Actions)

```yaml
- name: Deploy dbt Cloud config
  env:
    TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
    TF_VAR_dbt_token: ${{ secrets.DBT_API_TOKEN }}
    TF_VAR_environment_credentials: ${{ secrets.ENVIRONMENT_CREDENTIALS_JSON }}
  run: |
    terraform init
    terraform apply -auto-approve
```

Store `environment_credentials` as a JSON-encoded secret.

---

## Full schema reference

See [docs/configuration/yaml-schema.md](../docs/configuration/yaml-schema.md) for every field with types, defaults, and examples.
