# Migration Guide: From Manual Setup to YAML Configuration

This guide helps you migrate from manually managing dbt Cloud resources to defining everything in YAML with this Terraform module.

## Before vs After

### Before: Manual dbt Cloud UI Setup

```
Browser → dbt Cloud UI
├── Create Project
├── Connect Repository
├── Create Credentials
├── Create Environments
├── Create Connections
├── Configure Jobs
│   ├── Set dbt version
│   ├── Set threads
│   ├── Configure triggers
│   └── Set environment variables
└── Repeat for each environment (Dev, Staging, Prod)

Time: 30-60 minutes per project
Error-prone: Easy to misconfigure
Reproducible: Difficult - no audit trail
Shareable: Requires screenshots/documentation
```

### After: Infrastructure-as-Code with YAML

```
Git Repository
├── dbt-config.yml (one file defines everything)
└── terraform apply (creates all resources automatically)

Time: 10-15 minutes per project
Error-proof: Schema validation catches mistakes
Reproducible: Version controlled, completely auditable
Shareable: Share repo, others run same code
```

## Migration Steps

### Step 1: Collect Current Configuration

**In dbt Cloud UI, gather:**

#### Project Information
- [ ] Project name: ____________________
- [ ] Git repository URL: ____________________
- [ ] Default branch: ____________________

#### Environments
For each environment, note:
- [ ] Environment name: ____________________
- [ ] Type (development/deployment): ____________________
- [ ] dbt version: ____________________
- [ ] Custom branch (if different): ____________________

#### Credentials
For each environment, note:
- [ ] Connection type (e.g., Snowflake, BigQuery): ____________________
- [ ] Connection ID (URL: Admin → Connections → View Details): ____________________
- [ ] Warehouse/Dataset name: ____________________
- [ ] Schema name: ____________________

#### Jobs
For each job, note:
- [ ] Job name: ____________________
- [ ] Environment: ____________________
- [ ] Execute steps:
  ```
  dbt run
  dbt test
  ```
- [ ] Triggers (check which are enabled):
  - [ ] Scheduled (if yes: type _____, time _____)
  - [ ] GitHub webhook
  - [ ] On merge
- [ ] Settings:
  - [ ] Number of threads: ____
  - [ ] Generate docs: Yes / No
  - [ ] Run lint: Yes / No

#### Environment Variables
- [ ] Variables defined in this project: ____________________

### Step 2: Create terraform.tfvars

Create a new file `terraform.tfvars` with your dbt Cloud credentials:

```hcl
dbt_account_id = 999999           # Your dbt account ID
dbt_token      = "dbt_xxxxx..."   # Your dbt API token
dbt_host_url   = "https://cloud.getdbt.com"

# Map token names to warehouse tokens
token_map = {
  "dev_token"  = "warehouse_token_for_dev"
  "prod_token" = "warehouse_token_for_prod"
}

target_name = "dev"
```

**⚠️ IMPORTANT:** Add `terraform.tfvars` to `.gitignore` to avoid committing secrets:

```bash
echo "terraform.tfvars" >> .gitignore
```

### Step 3: Write dbt-config.yml

Create `dbt-config.yml` based on collected information:

#### Simple Migration (Single Environment)

**Before (Manual Setup):**
```
dbt Cloud UI:
1. Create Project: my_project
2. Connect to: https://github.com/myorg/myrepo.git
3. Create 1 Development environment
4. Create 1 connection to Snowflake
5. Create 1 job: "dev_run" triggered on PR
```

**After (YAML):**
```yaml
project:
  name: my_project
  repository:
    remote_url: https://github.com/myorg/myrepo.git
  
  environments:
    - name: Development
      type: development
      connection_id: 12345        # From dbt Cloud UI
      credential:
        token_name: dev_token
        schema: dev_schema
      jobs:
        - name: dev_run
          execute_steps:
            - dbt run
            - dbt test
          triggers:
            schedule: false
            github_webhook: true
            git_provider_webhook: false
            on_merge: false
```

#### Complex Migration (Multiple Environments with Different Schedules)

**Before (Manual Setup):**
```
dbt Cloud UI:
1. Create Project: analytics
2. Connect Repository
3. Create 3 Environments:
   - Development (GitHub webhook)
   - Staging (daily 2 AM, 2 PM UTC)
   - Production (daily 6 AM, 30 threads)
4. Create 3 Connections (one per warehouse)
5. Create 7 Jobs total (1 dev, 2 staging, 4 prod)
6. Set environment variables for each
```

**After (YAML):**
```yaml
project:
  name: analytics
  repository:
    remote_url: https://github.com/company/analytics.git
  
  environments:
    - name: Development
      type: development
      connection_id: 10001
      credential:
        token_name: dev_token
        schema: dev
      dbt_version: "1.5.0"
      jobs:
        - name: dev_run
          execute_steps:
            - dbt run
            - dbt test
          triggers:
            schedule: false
            github_webhook: true
            git_provider_webhook: false
            on_merge: false
    
    - name: Staging
      type: deployment
      connection_id: 10002
      credential:
        token_name: staging_token
        schema: staging
      dbt_version: "1.5.0"
      jobs:
        - name: staging_build
          execute_steps:
            - dbt run
            - dbt test
          triggers:
            schedule: true
            github_webhook: false
            git_provider_webhook: false
            on_merge: false
          schedule_type: "every_day"
          schedule_hours: [2, 14]  # 2 AM and 2 PM UTC
          num_threads: 8
    
    - name: Production
      type: deployment
      connection_id: 10003
      credential:
        token_name: prod_token
        schema: prod
      dbt_version: "1.5.0"
      jobs:
        - name: prod_daily
          description: "Daily production run"
          execute_steps:
            - dbt run
            - dbt test
            - dbt docs generate
          triggers:
            schedule: true
            github_webhook: false
            git_provider_webhook: false
            on_merge: false
          schedule_type: "every_day"
          schedule_hours: [6]
          num_threads: 30
          generate_docs: true
          run_compare_changes: true

        - name: prod_weekly
          description: "Weekly deep analysis"
          execute_steps:
            - dbt run --select model_tag:weekly
          triggers:
            schedule: true
            github_webhook: false
            git_provider_webhook: false
            on_merge: false
          schedule_type: "every_week"
          schedule_days: [0]  # Sunday
          schedule_hours: [1]

  environment_variables:
    - name: DBT_PROFILES_DIR
      environment_values:
        Development: /home/dbt/profiles_dev
        Staging: /home/dbt/profiles_staging
        Production: /home/dbt/profiles_prod
    
    - name: LOG_LEVEL
      environment_values:
        Development: debug
        Staging: info
        Production: warn
```

### Step 4: Map Token Names

**Before (Manual Setup):**
```
dbt Cloud UI → Credentials Tab
- Dev Warehouse Token: "xxx-dev-token-xxx"
- Prod Warehouse Token: "xxx-prod-token-xxx"
```

**In terraform.tfvars:**
```hcl
token_map = {
  "dev_token"  = "xxx-dev-token-xxx"
  "prod_token" = "xxx-prod-token-xxx"
}
```

### Step 5: Validate YAML Configuration

Before applying, validate your YAML:

```bash
# Option 1: Using Terraform console
terraform console
yamldecode(file("./dbt-config.yml"))

# Option 2: Using Python
python3 -c "
import yaml
with open('dbt-config.yml') as f:
    config = yaml.safe_load(f)
print('✅ YAML is valid')
print(f'Project: {config[\"project\"][\"name\"]}')
print(f'Environments: {len(config[\"project\"][\"environments\"])}')
"

# Option 3: Using IDE schema validation (see SCHEMA_SETUP.md)
# VS Code will show red squiggles for errors
```

### Step 6: Plan Terraform Changes

Before applying, review what will be created:

```bash
terraform init
terraform plan -var-file="terraform.tfvars"
```

**Review the output:**
```
Terraform will perform the following actions:

  # module.dbt_cloud.module.project.dbtcloud_project.project will be created
  + resource "dbtcloud_project" "project" {
      + account_id  = 999999
      + id          = (known after apply)
      + name        = "my_project"
    }

  # module.dbt_cloud.module.repository.dbtcloud_repository.repo will be created
  + resource "dbtcloud_repository" "repo" {
      ...
    }

  # module.dbt_cloud.module.jobs.dbtcloud_job.job will be created (4 times)
  + resource "dbtcloud_job" "job" {
      ...
    }

Plan: 12 to add, 0 to change, 0 to destroy
```

### Step 7: Apply and Verify

```bash
# Apply the Terraform configuration
terraform apply -var-file="terraform.tfvars"

# Review the outputs
terraform output

# Example output:
# project_id = "123456"
# environment_ids = {
#   "Development" = "78901"
#   "Production" = "78902"
# }
# job_ids = {
#   "dev_run" = "100001"
#   "prod_daily" = "100002"
# }
```

### Step 8: Verify in dbt Cloud UI

Go to dbt Cloud and verify:

- ✅ Project created with correct name
- ✅ Repository connected to correct branch
- ✅ Environments created (Development, Production, etc.)
- ✅ Jobs appear with correct names
- ✅ Job triggers configured correctly
- ✅ Schedules match expected times
- ✅ Environment variables set correctly

### Step 9: Delete Old Manual Resources (Optional)

If you created duplicates during testing:

**Via dbt Cloud UI:**
1. Admin → Account Settings
2. Find old project → Delete
3. Confirm deletion

**Via Terraform (if you want to be more careful):**
```bash
# Plan deletion to see what will be destroyed
terraform destroy -var-file="terraform.tfvars" -auto-approve=false

# Review the plan, then approve
terraform destroy -var-file="terraform.tfvars" -auto-approve=true
```

### Step 10: Commit to Version Control

```bash
# Add configuration files
git add dbt-config.yml main.tf variables.tf

# Verify terraform.tfvars is in .gitignore
cat .gitignore | grep terraform.tfvars

# Commit
git commit -m "feat: migrate dbt Cloud config to Terraform YAML"

# Push
git push origin main
```

## Common Migration Patterns

### Pattern 1: Single Environment → Multiple Environments

**Before:**
```
dbt Cloud:
- 1 Development environment
- 1 job (dev_run)
```

**After:**
```yaml
environments:
  - name: Development
    type: development
    jobs:
      - name: dev_run
        triggers:
          github_webhook: true

  - name: Production
    type: deployment
    jobs:
      - name: prod_run
        triggers:
          schedule: true
          schedule_type: every_day
```

### Pattern 2: Multiple Manual Jobs → Scheduled Jobs

**Before:**
```
dbt Cloud:
- Job 1: run_models (manual trigger only)
- Job 2: run_tests (manual trigger only)
- Job 3: generate_docs (manual trigger only)
```

**After:**
```yaml
jobs:
  - name: daily_workflow
    execute_steps:
      - dbt run
      - dbt test
      - dbt docs generate
    triggers:
      schedule: true
      schedule_type: every_day
      schedule_hours: [6]
```

### Pattern 3: Different Credentials per Environment

**Before:**
```
dbt Cloud:
- Dev environment → Dev Warehouse
- Prod environment → Prod Warehouse (different creds)
```

**After:**
```hcl
# terraform.tfvars
token_map = {
  "dev_token"  = "dev_warehouse_token"
  "prod_token" = "prod_warehouse_token"
}
```

```yaml
# dbt-config.yml
environments:
  - name: Development
    credential:
      token_name: dev_token      # Links to terraform.tfvars
      schema: dev_schema
  
  - name: Production
    credential:
      token_name: prod_token     # Links to terraform.tfvars
      schema: prod_schema
```

## Troubleshooting Migration

### "Connection ID not found"

**Problem:** YAML references connection_id that doesn't exist in dbt Cloud

**Solution:**
```bash
# Find correct connection ID in dbt Cloud UI
# Admin → Connections → View Details
# Update dbt-config.yml with correct ID

connection_id: 12345  # Verify this exists
```

### "Token invalid or expired"

**Problem:** dbt_token in terraform.tfvars is invalid

**Solution:**
```bash
# Generate new token in dbt Cloud
# Account Settings → API Tokens → Generate Token
# Copy entire token value

# Update terraform.tfvars
dbt_token = "dbt_xxxxx_new_token_xxxxx"

# Try again
terraform plan -var-file="terraform.tfvars"
```

### "YAML parse error: expected mapping"

**Problem:** YAML syntax error in dbt-config.yml

**Solution:**
```yaml
# ❌ Wrong - missing colon
project
  name: my_project

# ✅ Correct
project:
  name: my_project
```

See [YAML Validation Examples](README.md#yaml-validation-examples) for more examples.

### "Module mismatch" error

**Problem:** Terraform state from manual UI changes conflicts with new config

**Solution:**
```bash
# Option 1: Start fresh (recommended for first migration)
terraform destroy -var-file="terraform.tfvars" -auto-approve=true
terraform apply -var-file="terraform.tfvars" -auto-approve=true

# Option 2: Import existing resources
# (Advanced - only if you want to preserve state IDs)
terraform import module.dbt_cloud.module.project.dbtcloud_project.project PROJECT_ID
```

## Migration Checklist

- [ ] **Preparation**
  - [ ] Collected all current dbt Cloud configuration
  - [ ] Created terraform.tfvars with credentials
  - [ ] Added terraform.tfvars to .gitignore

- [ ] **YAML Configuration**
  - [ ] Created dbt-config.yml with all environments
  - [ ] Validated YAML syntax
  - [ ] Verified all token names match terraform.tfvars
  - [ ] Validated via `terraform console`

- [ ] **Terraform**
  - [ ] Ran `terraform init`
  - [ ] Reviewed `terraform plan` output
  - [ ] Ran `terraform apply`
  - [ ] Verified outputs with `terraform output`

- [ ] **Verification**
  - [ ] Checked dbt Cloud UI for all resources
  - [ ] Tested one job manually (Run → View logs)
  - [ ] Verified schedule triggers work
  - [ ] Tested GitHub webhook trigger

- [ ] **Version Control**
  - [ ] Committed dbt-config.yml
  - [ ] Pushed to git repository
  - [ ] Created Pull Request for review

- [ ] **Cleanup**
  - [ ] Deleted old manual resources (if keeping backup)
  - [ ] Documented any custom configurations

## Next Steps

- Read [README.md](README.md) for complete reference
- See [QUICKSTART.md](QUICKSTART.md) for setup refresher
- Check [TROUBLESHOOTING](README.md#troubleshooting) if issues arise
- Review [CONTRIBUTING.md](CONTRIBUTING.md) to contribute improvements

## Questions?

- See [Troubleshooting section in README](README.md#troubleshooting)
- Check existing [GitHub issues](https://github.com/trouze/dbt-cloud-terraform-starter/issues)
- Open a [new issue](https://github.com/trouze/dbt-cloud-terraform-starter/issues/new) if stuck
