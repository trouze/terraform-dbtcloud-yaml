# dbt Cloud Terraform Modules via YAML

[![Terraform Version](https://img.shields.io/badge/terraform-%3E%3D%201.0-blue?logo=terraform)](https://www.terraform.io)
[![dbt Cloud Provider](https://img.shields.io/badge/dbt--cloud--provider-%3E%3D%200.3-blue)](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

Terraform modules for managing dbt Cloud projects, environments, jobs, credentials, and environment variables using YAML configuration files instead of HCL. Define your dbt Cloud infrastructure once in YAML and deploy it consistently across environments.

## Features

✅ **YAML-Based Configuration** - Define dbt Cloud resources in simple, readable YAML  
✅ **Infrastructure as Code** - Version control, code review, and audit trails for dbt Cloud  
✅ **Modular Design** - Composable modules for each dbt Cloud resource type  
✅ **Production-Ready** - Input validation, sensitive value handling, and best practices  
✅ **Credential Management** - Secure token handling for database credentials  
✅ **Environment Variables** - Project-level and job-level environment variable configuration  

## Quick Start

### Option 1: Use as a Terraform Module (Recommended for Most Users)

Create a `main.tf` in your Terraform workspace:

```hcl
module "dbt_cloud" {
  source = "git::https://github.com/yourusername/dbt-terraform-modules-yaml.git?ref=v1.0.0"
  
  yaml_file        = file("${path.module}/dbt-config.yml")
  dbt_account_id   = var.dbt_account_id
  dbt_token        = var.dbt_token
  dbt_host_url     = var.dbt_host_url
  token_map        = var.token_map
  target_name      = "prod"
}

output "project_id" {
  value = module.dbt_cloud.project_id
}

output "job_ids" {
  value = module.dbt_cloud.job_ids
}
```

Create `variables.tf`:

```hcl
variable "dbt_account_id" {
  type      = number
  sensitive = true
}

variable "dbt_token" {
  type      = string
  sensitive = true
}

variable "dbt_host_url" {
  type    = string
  default = "https://cloud.getdbt.com"
}

variable "token_map" {
  type      = map(string)
  default   = {}
  sensitive = true
}
```

Then deploy:

```bash
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply
```

### Option 2: Clone and Customize

For development or advanced customization:

```bash
git clone https://github.com/yourusername/dbt-terraform-modules-yaml.git
cd dbt-terraform-modules-yaml
terraform init
terraform plan -var-file="terraform.tfvars"
```

## Configuration

### Input Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `yaml_file` | string | Yes | Path to the YAML configuration file |
| `dbt_account_id` | number | Yes | dbt Cloud account ID |
| `dbt_token` | string | Yes | dbt Cloud API token (sensitive) |
| `dbt_host_url` | string | Yes | dbt Cloud host URL (default: `https://cloud.getdbt.com`) |
| `token_map` | map(string) | No | Map of credential token names to values (sensitive) |
| `target_name` | string | No | Default target name for the project |

### Outputs

The module exports the following outputs:

```hcl
output "project_id" {
  description = "The dbt Cloud project ID"
  value       = module.dbt_cloud.project_id
}

output "repository_id" {
  description = "The dbt Cloud repository ID"
  value       = module.dbt_cloud.repository_id
}

output "environment_ids" {
  description = "Map of environment names to their dbt Cloud IDs"
  value       = module.dbt_cloud.environment_ids
}

output "credential_ids" {
  description = "Map of credential names to their dbt Cloud IDs"
  value       = module.dbt_cloud.credential_ids
}

output "job_ids" {
  description = "Map of job names to their dbt Cloud IDs"
  value       = module.dbt_cloud.job_ids
}
```

## YAML Configuration Spec

The YAML file defines all dbt Cloud resources. Below is the complete specification:

```yaml
project:
  name: <string> # Required. Name of the dbt project.
  repository:
    remote_url: <string> # Required. URL of the remote Git repository.
    gitlab_project_id: <number> # Optional. GitLab project ID if using GitLab integration.
  environments:
    - name: <string> # Required. Name of the environment.
      credential:
        token_name: <string> # Optional. Name of the token to use.
        schema: <string> # Optional. Schema to be used.
        catalog: <string> # Optional. Catalog to be used.
      connection_id: <number> # Required. Connection ID for the environment.
      type: <string> # Required. Type of environment. Allowed values: 'development', 'deployment'.
      dbt_version: <string> # Optional. dbt version to use. Defaults to "latest".
      enable_model_query_history: <boolean> # Optional. Enable model query history. Defaults to false.
      custom_branch: <string> # Optional. Custom branch for dbt. Defaults to null.
      deployment_type: <string> # Optional. Deployment type (e.g., 'production'). Defaults to null.
      jobs:
        - name: <string> # Required. Name of the job.
          execute_steps: 
            - <string> # Required. Steps to execute in the job.
          triggers:
            github_webhook: <boolean> # Required. Trigger job on GitHub webhook.
            git_provider_webhook: <boolean> # Required. Trigger job on Git provider webhook.
            schedule: <boolean> # Required. Trigger job on a schedule.
            on_merge: <boolean> # Required. Trigger job on merge.
          dbt_version: <string> # Optional. dbt version for the job. Defaults to "latest".
          deferring_environment: <string> # Optional. Enable deferral of job to environment. Defaults to no deferral.
          description: <string> # Optional. Description of the job. Defaults to null.
          errors_on_lint_failure: <boolean> # Optional. Fail job on lint errors. Defaults to true.
          generate_docs: <boolean> # Optional. Generate docs. Defaults to false.
          is_active: <boolean> # Optional. Whether the job is active. Defaults to true.
          num_threads: <number> # Optional. Number of threads for the job. Defaults to 4.
          run_compare_changes: <boolean> # Optional. Compare changes before running. Defaults to false.
          run_generate_sources: <boolean> # Optional. Generate sources before running. Defaults to false.
          run_lint: <boolean> # Optional. Run lint before running. Defaults to false.
          schedule_cron: <string> # Optional. Cron schedule for the job. Defaults to null.
          schedule_days: <array> of <ints> # Optional. Days for schedule. Defaults to null. e.g. [0, 1, 2]
          schedule_hours: <array> of <ints> # Optional. Hours for schedule. Defaults to null. e.g. [0, 1, 2]
          schedule_interval: <string> # Optional. Interval for schedule. Defaults to null.
          schedule_type: <string> # Optional. Type of schedule. Defaults to null.
          self_deferring: <boolean> # Optional. Whether the job is self-deferring. Defaults to false.
          target_name: <string> # Optional. Target name for the job. Defaults to null.
          timeout_seconds: <number> # Optional. Job timeout in seconds. Defaults to 0.
          triggers_on_draft_pr: <boolean> # Optional. Trigger job on draft PRs. Defaults to false.
          env_var_overrides:
            <ENV_VAR>: <string> # Optional. Specify a job env var override
  environment_variables:
    - name: DBT_<string> # Required. Name of the environment variable. Starts with DBT_
      environment_values:
        - env: project
          value: <string> # Optional. Environment value
        - env: Production
          value: <string> # Optional. Environment value
        - env: UAT
          value: <string> # Optional. Environment value
        - env: Development
          value: <string> # Optional. Environment value
    - name: DBT_SECRET_<string> # Required. Name of the secret environment variable. Starts with DBT_SECRET_
      environment_values:
        - env: project
          value: secret_<string> # Optional. Environment value
        - env: Production
          value: secret_<string> # Optional. Environment value
        - env: UAT
          value: secret_<string> # Optional. Environment value
        - env: Development
          value: secret_<string> # Optional. Environment value
```

### Example YAML Configuration

```yaml
project:
  name: my_analytics_project
  repository:
    remote_url: https://github.com/myorg/dbt-analytics.git
  environments:
    - name: Development
      type: development
      connection_id: 12345
      credential:
        token_name: dev_warehouse_token
        schema: dev
      dbt_version: "1.5.0"
      jobs:
        - name: nightly_build
          description: "Nightly dbt run"
          is_active: true
          execute_steps:
            - "dbt run"
            - "dbt test"
          triggers:
            schedule: true
            github_webhook: false
            git_provider_webhook: false
            on_merge: false
          schedule_type: "every_day"
          schedule_hours: [2]
          generate_docs: true
    
    - name: Production
      type: deployment
      connection_id: 12346
      credential:
        token_name: prod_warehouse_token
        schema: prod
      dbt_version: "1.5.0"
      jobs:
        - name: daily_prod_build
          description: "Daily production build"
          is_active: true
          execute_steps:
            - "dbt run"
            - "dbt test"
          triggers:
            schedule: true
            github_webhook: false
            git_provider_webhook: false
            on_merge: false
          schedule_type: "every_day"
          schedule_hours: [6]
          num_threads: 8
  
  environment_variables:
    - name: DBT_ENV_TYPE
      environment_values:
        - env: project
          value: prod
        - env: Production
          value: production
        - env: Development
          value: development
```

### YAML Validation Examples

**💡 Tip:** Enable IDE validation with JSON Schema for real-time error detection. See [SCHEMA_SETUP.md](SCHEMA_SETUP.md) for VS Code, JetBrains, Vim, and other IDE setup instructions.

#### ✅ Correct - Minimal Configuration

```yaml
project:
  name: minimal_project
  repository:
    remote_url: https://github.com/org/dbt-repo.git
  environments:
    - name: Dev
      type: development
      connection_id: 123
```

#### ❌ Incorrect - Missing Required Fields

```yaml
project:
  # ❌ Missing: name
  repository:
    # ❌ Missing: remote_url
  environments:
    - name: Dev
      # ❌ Missing: type (must be 'development' or 'deployment')
      # ❌ Missing: connection_id
```

#### ✅ Correct - Complete Configuration

```yaml
project:
  name: full_featured_project
  repository:
    remote_url: https://github.com/org/dbt-repo.git
  environments:
    - name: Development
      type: development
      connection_id: 12345
      credential:
        token_name: dev_token
        schema: dev_schema
      dbt_version: "1.5.0"
      jobs:
        - name: dev_job
          execute_steps:
            - "dbt run"
            - "dbt test"
          triggers:
            schedule: false
            github_webhook: true
            git_provider_webhook: false
            on_merge: false
  environment_variables:
    - name: DBT_PROFILES_DIR
      environment_values:
        - env: project
          value: /home/dbt_user/.dbt
```

#### ❌ Incorrect - Common Type Mistakes

```yaml
project:
  name: type_error_project
  repository:
    remote_url: "https://github.com/org/dbt-repo.git"
  environments:
    - name: Dev
      type: "development"  # ❌ String instead of unquoted
      connection_id: "123"  # ❌ String instead of number
      jobs:
        - name: job_name
          execute_steps:
            - "dbt run"
          triggers:
            schedule: "true"  # ❌ String instead of boolean
            github_webhook: "false"  # ❌ String instead of boolean
```

#### ✅ Correct - Proper Types

```yaml
project:
  name: type_correct_project
  repository:
    remote_url: https://github.com/org/dbt-repo.git
  environments:
    - name: Dev
      type: development  # ✅ Unquoted string (literal)
      connection_id: 123  # ✅ Number
      jobs:
        - name: job_name
          execute_steps:
            - "dbt run"
          triggers:
            schedule: true  # ✅ Boolean
            github_webhook: false  # ✅ Boolean
```

### YAML Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `yaml_file must point to a valid, readable file` | File path incorrect or doesn't exist | Verify: `ls -la ./dbt-config.yml` |
| `project_name is null` | Missing `project.name` in YAML | Add: `name: my_project` under `project:` |
| `environment_ids is empty` | Missing `environments` section | Add environments list under `project:` |
| `credential not found in dbt Cloud` | Token name in YAML doesn't match `token_map` | Ensure: `credential.token_name` matches key in `token_map` |
| `connection_id not found` | Invalid connection ID for environment | Verify connection ID exists in dbt Cloud UI |
| `invalid value for type: expected bool, got string` | Boolean wrapped in quotes | Remove quotes: `true` not `"true"` |
| `invalid trigger configuration` | Missing required trigger fields | All four triggers needed: `schedule`, `github_webhook`, `git_provider_webhook`, `on_merge` |

### YAML Best Practices

1. **Always quote environment variable values**
   ```yaml
   # ✅ Correct
   value: "my_value"
   
   # ❌ Incorrect (unquoted strings can cause parsing issues)
   value: my_value
   ```

2. **Use unquoted strings for type indicators**
   ```yaml
   # ✅ Correct
   type: development
   
   # ❌ Incorrect (string in quotes becomes a literal)
   type: "development"
   ```

3. **Use proper numbers for IDs**
   ```yaml
   # ✅ Correct
   connection_id: 12345
   
   # ❌ Incorrect
   connection_id: "12345"
   ```

4. **Always include all trigger types**
   ```yaml
   # ✅ Correct
   triggers:
     schedule: true
     github_webhook: false
     git_provider_webhook: false
     on_merge: false
   
   # ❌ Incorrect (missing trigger types)
   triggers:
     schedule: true
   ```

5. **Use arrays for lists**
   ```yaml
   # ✅ Correct - execute_steps as array
   execute_steps:
     - "dbt run"
     - "dbt test"
   
   # ✅ Correct - hours as array
   schedule_hours: [6, 18]
   
   # ✅ Correct - environment_values as array of objects
   environment_values:
     - env: project
       value: "value1"
     - env: Production
       value: "value2"
   ```

## Getting Secrets to Deploy via Terraform

To deploy secret values (tokens, API keys, etc.) via Terraform:

### 1. Add the Secret to Your CI/CD System

For GitHub Actions:
```yaml
# .github/workflows/terraform.yml
env:
  TF_VAR_token_map: |
    {
      "dev_warehouse_token": "${{ secrets.DEV_WAREHOUSE_TOKEN }}",
      "prod_warehouse_token": "${{ secrets.PROD_WAREHOUSE_TOKEN }}"
    }
```

### 2. Reference in Your YAML

```yaml
credential:
  token_name: dev_warehouse_token  # Maps to TF_VAR_token_map.dev_warehouse_token
  schema: dev
```

### 3. Pass to Terraform

```bash
export TF_VAR_token_map='{
  "dev_warehouse_token": "your-token-value",
  "prod_warehouse_token": "your-other-token"
}'

terraform apply
```

## Importing Existing dbt Cloud Resources

If you have existing dbt Cloud resources, use [`dbtcloud-terraforming`](https://github.com/dbt-labs/dbtcloud-terraforming) to generate resource blocks:

```bash
dbtcloud-terraforming generate \
  --resource-types environments,jobs \
  -p <project_id> \
  --modern-import-block > imports.tf
```

Then:

1. Run `terraform apply` to import existing resources into state
2. Manually convert the imported resources to your YAML spec (one-time process)
3. Verify with `terraform plan` (should show no changes)

## Module Structure

```
dbt-terraform-modules-yaml/
├── main.tf                    # Root module orchestration
├── variables.tf               # Input variables
├── outputs.tf                 # Output definitions
├── providers.tf               # Provider configuration
└── modules/
    ├── project/               # Project creation
    ├── repository/            # Repository setup
    ├── project_repository/    # Project-repository association
    ├── credentials/           # Credential management
    ├── environments/          # Environment creation
    ├── jobs/                  # Job configuration
    ├── environment_variables/ # Env var management
    └── environment_variable_job_overrides/  # Job-level env var overrides
```

## Credential Rotation

To rotate credentials without recreating jobs:

```bash
terraform apply \
  -var-file="terraform.tfvars" \
  -target=module.credentials
```

## Development & Contributing

### Prerequisites

- Terraform >= 1.0
- dbt Cloud account with API access
- Git

### Local Setup

```bash
git clone https://github.com/yourusername/dbt-terraform-modules-yaml.git
cd dbt-terraform-modules-yaml
terraform init

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
dbt_account_id = YOUR_ACCOUNT_ID
dbt_token      = "dbtc_YOUR_TOKEN"
dbt_host_url   = "https://cloud.getdbt.com"
yaml_file      = "./projects/demo/demo.yml"
token_map = {
  "my_token" = "your-token-value"
}
EOF

terraform plan
```

## Troubleshooting

### "yaml_file must point to a valid, readable file"

**Solution:** Ensure the YAML file path is correct and readable:

```bash
ls -la ./projects/demo/demo.yml
```

Check that:
- File path is correct
- File has read permissions
- File extension is `.yml` or `.yaml`

### "yaml not valid YAML: syntax error..."

**Solution:** YAML is whitespace-sensitive. Common issues:

```yaml
# ❌ Incorrect - inconsistent indentation
project:
 name: my_project  # 1 space indent
  repository:      # 2 space indent - ERROR!

# ✅ Correct - consistent indentation
project:
  name: my_project  # 2 space indent
  repository:       # 2 space indent
```

**Debug with:**
```bash
terraform console
> yamldecode(file("./dbt-config.yml"))
```

### "project_name is null" or "project not found"

**Solution:** Ensure your YAML has a project section with required fields:

```yaml
# ❌ Incorrect - missing project structure
environments:
  - name: Dev

# ✅ Correct - proper project structure
project:
  name: my_project
  repository:
    remote_url: https://github.com/org/repo.git
  environments:
    - name: Dev
```

### "token_map is required for credential"

**Solution:** Verify your `token_map` includes all credential token names referenced in your YAML:

```hcl
# terraform.tfvars
token_map = {
  "dev_warehouse_token"  = "your-dev-token"
  "prod_warehouse_token" = "your-prod-token"
}
```

Then ensure YAML references match:
```yaml
credential:
  token_name: dev_warehouse_token  # Must exist in token_map
```

### "credential not found in dbt Cloud"

**Solution:** Check that credentials are created first by running:

```bash
terraform apply -target=module.credentials
```

Also verify:
- Token names match between YAML and `token_map`
- Connection IDs are valid
- Credentials have proper schemas defined

### "environment_ids is empty"

**Solution:** Ensure your YAML includes the environments section:

```yaml
project:
  name: my_project
  environments:  # ✅ This section is required
    - name: Development
      type: development
      connection_id: 12345
```

### "connection_id is not a valid dbt Cloud connection"

**Solution:** Verify the connection ID exists in your dbt Cloud account:

1. Go to dbt Cloud UI
2. Navigate to Admin → Connections
3. Find your connection and copy the ID
4. Use that ID in your YAML:

```yaml
environments:
  - name: Dev
    connection_id: 12345  # Get from dbt Cloud UI
```

### "invalid value for type: expected bool, got string"

**Solution:** Remove quotes around boolean values:

```yaml
# ❌ Incorrect - booleans should not be quoted
triggers:
  schedule: "true"
  github_webhook: "false"

# ✅ Correct - unquoted booleans
triggers:
  schedule: true
  github_webhook: false
```

### "missing required trigger fields"

**Solution:** All four trigger types must be specified (even if false):

```yaml
# ❌ Incomplete
triggers:
  schedule: true

# ✅ Complete
triggers:
  schedule: true
  github_webhook: false
  git_provider_webhook: false
  on_merge: false
```

### "Terraform is trying to update resources on every plan"

**Solution:** This usually means your YAML file has been modified. Run:

```bash
terraform plan -destroy  # Review what would be destroyed
terraform plan           # See full diff
```

To avoid drift:
- Keep YAML file stable
- Use `terraform state` commands carefully
- Use remote state to share across team

### "Module version mismatch" or "provider version error"

**Solution:** Ensure your Terraform version matches requirements:

```hcl
# Check required version
terraform version

# Upgrade Terraform if needed
terraform init -upgrade
```

### Debugging YAML Parse Errors

Enable Terraform debug output:

```bash
TF_LOG=DEBUG terraform plan -var-file="terraform.tfvars" 2>&1 | grep -i yaml
```

For detailed inspection:
```bash
terraform console
> yamldecode(file("./dbt-config.yml"))
> keys(local.project_config.project)
```

### "apply failed" with cryptic error message

**Solution:** Check the raw error message:

```bash
terraform apply -var-file="terraform.tfvars" 2>&1 | tail -50
```

Common causes:
- API token is expired or invalid
- Account ID doesn't match token
- YAML has syntax errors (check with yamldecode)
- dbt Cloud API is temporarily unavailable

### "aws provider not found" or other provider errors

**Solution:** Initialize Terraform properly:

```bash
rm -rf .terraform .terraform.lock.hcl
terraform init
terraform plan
```

## Debugging Checklist

When something goes wrong:

- [ ] Check YAML syntax: `terraform console` → `yamldecode(file(...))`
- [ ] Verify credentials: `echo $TF_VAR_dbt_token | wc -c`
- [ ] Test connectivity: Try logging into dbt Cloud UI with the same credentials
- [ ] Check file paths: `ls -la ./dbt-config.yml`
- [ ] Review Terraform logs: `TF_LOG=DEBUG terraform plan 2>&1 | head -100`
- [ ] Validate variables: `terraform validate`
- [ ] Test with example: Copy `examples/basic/` and test

## Performance Notes

- First deployment: ~2-3 minutes
- Credential updates: ~30 seconds
- Job updates: ~45 seconds
- Full redeploy: ~3-5 minutes

Deployment time depends on the number of resources and dbt Cloud API responsiveness.

## Best Practices

1. **Version Your Module** - Pin to specific releases: `ref=v1.0.0`
2. **Use `terraform.tfvars.example`** - Check in example with dummy values, never commit real secrets
3. **Separate Environments** - Use different YAML files per environment
4. **Validate Before Apply** - Always run `terraform plan` first
5. **Track State** - Use remote state (S3, Terraform Cloud) for team collaboration
6. **Secrets Management** - Use your CI/CD system's secrets manager, not environment variables

## License

This project is licensed under the MIT License - see [LICENSE](./LICENSE) file for details.

## Support

For issues and questions:

1. Check [Troubleshooting](#troubleshooting) section
2. Review [YAML Configuration Spec](#yaml-configuration-spec)
3. Open an [issue on GitHub](https://github.com/yourusername/dbt-terraform-modules-yaml/issues)
4. See [dbt Cloud Terraform Provider Docs](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs)

## Roadmap

- [ ] JSON schema validation for YAML files
- [ ] GitHub Actions workflow example
- [ ] Terraform Cloud integration guide
- [ ] Multi-project support
- [ ] dbt Cloud metrics integration
