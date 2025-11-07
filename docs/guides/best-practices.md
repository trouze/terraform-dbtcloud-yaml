# Best Practices

Recommended patterns for managing dbt Cloud infrastructure with Terraform.

## Security

### Credential Management

✅ **Use environment variables** for all sensitive data:

```bash
# .env file (never commit)
export TF_VAR_dbt_api_token=dbtc_xxxxx
export TF_VAR_token_map='{"key":"value"}'
```

❌ **Never hardcode** credentials:

```hcl
# DON'T DO THIS!
variable "dbt_token" {
  default = "dbtc_xxxxx"  # ❌ Exposed in version control
}
```

### Token Security

- **Use service accounts** instead of personal tokens
- **Rotate tokens** every 90 days
- **Limit permissions** to minimum required
- **Use different tokens** for dev/staging/prod
- **Store in secrets managers** (GitHub Secrets, Vault, etc.)

### Gitignore

Always exclude sensitive files:

```gitignore title=".gitignore"
# Terraform
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl
crash.log
override.tf
override.tf.json

# Credentials
.env
.env.local
*.tfvars
!*.tfvars.example
terraform.rc
.terraformrc

# IDE
.vscode/
.idea/
*.swp
```

---

## Code Organization

### Directory Structure

Recommended layout:

```
my-dbt-infrastructure/
├── .github/
│   └── workflows/
│       └── deploy.yml
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── backend.tf
│   └── versions.tf
├── configs/
│   ├── production.yml
│   ├── staging.yml
│   └── development.yml
├── docs/
│   └── README.md
├── .env.example
├── .gitignore
└── README.md
```

### File Naming

Use clear, descriptive names:

- `main.tf` - Primary module configuration
- `variables.tf` - Input variable definitions
- `outputs.tf` - Output value definitions
- `backend.tf` - State backend configuration
- `versions.tf` - Provider version constraints

### Module Version Pinning

Always pin module versions:

```hcl
module "dbt_cloud" {
  source = "git::https://github.com/trouze/dbt-terraform-modules-yaml.git?ref=v1.0.0"
  # NOT: source = "git::https://github.com/..."  # ❌ Unpredictable
}
```

---

## YAML Configuration

### Naming Conventions

Use consistent, descriptive names:

```yaml
project:
  name: "analytics-production"  # ✅ Clear and specific
  # NOT: name: "project1"       # ❌ Vague
  
  environments:
    - name: "Production"         # ✅ Proper case
      # NOT: name: "prod"        # ❌ Abbreviation
```

### Comments

Document non-obvious configurations:

```yaml
project:
  environments:
    - name: "Production"
      # Using connection_id 1001 for Databricks Unity Catalog
      connection_id: 1001
      
      jobs:
        - name: "Daily Run"
          # Runs at 6 AM UTC (2 AM ET)
          schedule_hours: [6]
```

### Environment-Specific Values

Keep environment configs consistent:

```yaml
# ✅ Good: Consistent structure across environments
environments:
  - name: "Development"
    type: "development"
    credential:
      token_name: "dev_databricks"
      schema: "dev_analytics"
  
  - name: "Production"
    type: "deployment"
    credential:
      token_name: "prod_databricks"
      schema: "analytics"
```

---

## State Management

### Remote State

Always use remote state for teams:

```hcl title="backend.tf"
terraform {
  backend "s3" {
    bucket         = "my-company-terraform-state"
    key            = "dbt-cloud/production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-lock"
  }
}
```

### State Locking

Enable locking to prevent concurrent modifications:

```hcl
# S3 + DynamoDB (AWS)
terraform {
  backend "s3" {
    bucket         = "state-bucket"
    key            = "dbt/terraform.tfstate"
    dynamodb_table = "terraform-locks"
  }
}

# Azure Blob Storage
terraform {
  backend "azurerm" {
    storage_account_name = "tfstate"
    container_name       = "tfstate"
    key                  = "dbt.tfstate"
  }
}
```

### State Backup

Always maintain state backups:

```bash
# Before major changes
terraform state pull > backup-$(date +%Y%m%d-%H%M%S).tfstate
```

---

## Testing & Validation

### Pre-Deployment Checks

Always validate before applying:

```bash
# 1. Format check
terraform fmt -check -recursive

# 2. Validation
terraform validate

# 3. Plan review
terraform plan -out=tfplan

# 4. Manual review
terraform show tfplan

# 5. Apply only if satisfied
terraform apply tfplan
```

### YAML Validation

Use schema validation in IDE:

```yaml
# Add to top of dbt-config.yml
# yaml-language-server: $schema=https://raw.githubusercontent.com/trouze/dbt-terraform-modules-yaml/main/schemas/v1.json

project:
  name: "my-project"
```

### Automated Testing

Run tests in CI/CD:

```yaml
steps:
  - name: Terraform Format Check
    run: terraform fmt -check -recursive
  
  - name: Terraform Validate
    run: terraform validate
  
  - name: YAML Lint
    uses: ibiqlik/action-yamllint@v3
```

---

## CI/CD Best Practices

### Branch Protection

Protect production branches:

- Require pull request reviews
- Require status checks to pass
- Require up-to-date branches
- Include administrators in restrictions

### Pull Request Workflow

1. **Branch** from main: `git checkout -b feature/add-prod-job`
2. **Make changes** to YAML or Terraform
3. **Commit** with clear messages
4. **Push** and create PR
5. **Review** automated plan output
6. **Approve** and merge
7. **Automated apply** on merge to main

### Deployment Strategy

Use progressive deployment:

```
Development → Staging → Production
```

```yaml
# Deploy to dev automatically
on:
  push:
    branches: [develop]

# Deploy to staging on PR merge
on:
  pull_request:
    types: [closed]
    branches: [main]

# Deploy to prod manually
when: manual
```

---

## Performance

### Parallelism

Optimize for multiple projects:

```yaml
# GitHub Actions
strategy:
  matrix:
    project: [finance, marketing, operations]
  max-parallel: 3
```

### Caching

Cache Terraform plugins:

```yaml
- name: Cache Terraform Plugins
  uses: actions/cache@v3
  with:
    path: ~/.terraform.d/plugin-cache
    key: ${{ runner.os }}-terraform-${{ hashFiles('**/.terraform.lock.hcl') }}
```

### Resource Timeouts

Set appropriate timeouts:

```yaml
jobs:
  - name: "Large Job"
    timeout_seconds: 7200  # 2 hours for complex runs
```

---

## Monitoring & Observability

### Terraform Cloud

Use Terraform Cloud for visibility:

```hcl
terraform {
  cloud {
    organization = "my-company"
    workspaces {
      name = "dbt-cloud-production"
    }
  }
}
```

### Notifications

Set up alerts for failures:

```yaml
# GitHub Actions
- name: Notify on Failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "Terraform deployment failed: ${{ github.workflow }}"
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

### Logging

Capture detailed logs:

```yaml
- name: Terraform Apply
  run: terraform apply -auto-approve 2>&1 | tee terraform.log

- name: Upload Logs
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: terraform-logs
    path: terraform.log
```

---

## Documentation

### README Template

Every project should have:

```markdown
# dbt Cloud Infrastructure - [Project Name]

## Overview
Brief description of what this manages.

## Prerequisites
- Terraform >= 1.0
- dbt Cloud account
- Required permissions

## Setup
\`\`\`bash
# Clone and configure
git clone <repo>
cp .env.example .env
# Edit .env with credentials
\`\`\`

## Usage
\`\`\`bash
source .env
terraform init
terraform plan
terraform apply
\`\`\`

## Configuration
Link to YAML schema and examples.

## CI/CD
Describe automated deployment process.

## Support
Where to get help.
```

### Inline Documentation

Use Terraform comments:

```hcl
# Configure dbt Cloud provider
# Requires: DBT_ACCOUNT_ID and DBT_API_TOKEN env vars
provider "dbtcloud" {
  account_id = var.dbt_account_id  # Found in dbt Cloud URL
  token      = var.dbt_api_token   # Generate in Profile settings
  host_url   = var.dbt_host_url    # Regional API endpoint
}
```

### Change Management

Document major changes:

```markdown
## Changelog

### 2024-01-15
- Added staging environment
- Updated prod job schedule to 6 AM UTC
- Migrated from GitHub Deploy Key to GitHub App

### 2024-01-10
- Initial production deployment
- Configured Databricks credentials
```

---

## Common Patterns

### Multiple Environments

```yaml
environments:
  # Development: Full access, custom branch
  - name: "Development"
    type: "development"
    custom_branch: "develop"
    enable_model_query_history: true
  
  # Staging: Production-like, limited access
  - name: "Staging"
    type: "deployment"
    dbt_version: "1.7.1"  # Pin to same as prod
    jobs:
      - name: "Staging CI"
        triggers:
          on_merge: true
        deferring_environment: "Production"
  
  # Production: Locked down, scheduled
  - name: "Production"
    type: "deployment"
    dbt_version: "1.7.1"
    jobs:
      - name: "Daily Run"
        triggers:
          schedule: true
        schedule_hours: [6]
```

### Job Naming

Use consistent, descriptive names:

```yaml
jobs:
  # ✅ Good
  - name: "Production Daily Full Refresh"
  - name: "Staging CI - Modified Models Only"
  - name: "Development - Ad Hoc Testing"
  
  # ❌ Bad
  - name: "job1"
  - name: "run"
  - name: "test"
```

### Credential Mapping

Organize by environment and warehouse:

```bash
export TF_VAR_token_map='{
  "dev_databricks_uc": "dapi_dev123",
  "staging_databricks_uc": "dapi_stg456",
  "prod_databricks_uc": "dapi_prd789",
  "dev_snowflake": "sf_dev_abc",
  "prod_snowflake": "sf_prd_xyz"
}'
```

---

## Checklist

Before deploying to production:

- [ ] All credentials in environment variables or secrets manager
- [ ] `.env` and `*.tfvars` in `.gitignore`
- [ ] Remote state backend configured
- [ ] State locking enabled
- [ ] Terraform version pinned
- [ ] Module version pinned
- [ ] YAML validated against schema
- [ ] `terraform plan` reviewed
- [ ] CI/CD pipeline tested
- [ ] Rollback plan documented
- [ ] Team notified of changes
- [ ] Monitoring/alerts configured

---

## Getting Help

- 📖 [Documentation](https://trouze.github.io/dbt-terraform-modules-yaml)
- 🐛 [Issues](https://github.com/trouze/dbt-terraform-modules-yaml/issues)
- 💬 [Discussions](https://github.com/trouze/dbt-terraform-modules-yaml/discussions)
