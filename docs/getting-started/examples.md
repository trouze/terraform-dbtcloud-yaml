# Examples

Explore real-world examples and use cases for managing dbt Cloud with Terraform.

## Basic Example

The simplest possible setup to get started.

### What It Includes

- Single dbt Cloud project
- GitHub repository integration
- One production environment
- One scheduled job

### Directory Structure

```
examples/basic/
├── main.tf              # Terraform module call
├── variables.tf         # Input variables
├── dbt-config.yml      # dbt Cloud configuration
└── .env.example        # Credential template
```

### Try It Out

```bash
cd examples/basic
cp .env.example .env
# Edit .env with your credentials
source .env
terraform init
terraform plan
terraform apply
```

[:material-github: View Source](https://github.com/trouze/dbt-terraform-modules-yaml/tree/main/examples/basic){ .md-button }

---

## Managing Multiple Projects

Store multiple YAML configurations and manage them independently or in parallel.

### Scenario: Multiple Teams

You have separate dbt projects for different teams (Finance, Marketing, Operations) and want to manage them with the same Terraform workflow.

### Directory Structure

```
my-dbt-infrastructure/
├── main.tf
├── variables.tf
├── .env
└── configs/
    ├── finance.yml
    ├── marketing.yml
    └── operations.yml
```

### Deploy Specific Project

```bash
# Load credentials once
source .env

# Deploy Finance project
terraform plan -var="yaml_file_path=./configs/finance.yml"
terraform apply -var="yaml_file_path=./configs/finance.yml"

# Deploy Marketing project
terraform plan -var="yaml_file_path=./configs/marketing.yml"
terraform apply -var="yaml_file_path=./configs/marketing.yml"
```

### Deploy All Projects (Sequential)

```bash
source .env

for config in configs/*.yml; do
  echo "Deploying $config..."
  terraform apply -var="yaml_file_path=$config" -auto-approve
done
```

---

## CI/CD with GitHub Actions

Automate dbt Cloud infrastructure deployment on configuration changes.

### Single Project Workflow

```yaml title=".github/workflows/dbt-infrastructure.yml"
name: Deploy dbt Cloud Infrastructure

on:
  push:
    branches: [main]
    paths:
      - 'dbt-config.yml'
      - '**.tf'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.6.0
      
      - name: Terraform Init
        run: terraform init
      
      - name: Terraform Plan
        env:
          TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
          TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
          TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
          TF_VAR_dbt_host_url: https://cloud.getdbt.com/api
          TF_VAR_yaml_file_path: ./dbt-config.yml
        run: terraform plan
      
      - name: Terraform Apply
        if: github.ref == 'refs/heads/main'
        env:
          TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
          TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
          TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
          TF_VAR_dbt_host_url: https://cloud.getdbt.com/api
          TF_VAR_yaml_file_path: ./dbt-config.yml
        run: terraform apply -auto-approve
```

### Multi-Project Parallel Deployment

```yaml title=".github/workflows/multi-project.yml"
name: Deploy Multiple dbt Projects

on:
  push:
    branches: [main]
    paths:
      - 'configs/**.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        project: [finance, marketing, operations]
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
      
      - name: Terraform Init
        run: terraform init
      
      - name: Deploy ${{ matrix.project }}
        env:
          TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
          TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
          TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
          TF_VAR_dbt_host_url: https://cloud.getdbt.com/api
          TF_VAR_yaml_file_path: ./configs/${{ matrix.project }}.yml
        run: |
          terraform plan
          terraform apply -auto-approve
```

!!! tip "Required Secrets"
    Add these to your GitHub repository secrets:
    
    - `DBT_ACCOUNT_ID`
    - `DBT_API_TOKEN`
    - `DBT_PAT`

---

## Advanced: Multi-Environment Configuration

Manage development, staging, and production environments in one YAML file.

```yaml title="dbt-config.yml"
project:
  name: "analytics"
  repository:
    remote_url: "https://github.com/myorg/dbt-analytics.git"
    git_clone_strategy: "github_app"
    github_installation_id: 123456
  
  environments:
    # Development environment
    - name: "Development"
      type: "development"
      connection_id: 1
      credential:
        token_name: "dev_databricks_token"
        schema: "dev"
      custom_branch: "develop"
    
    # Staging environment
    - name: "Staging"
      type: "deployment"
      connection_id: 2
      credential:
        token_name: "staging_databricks_token"
        schema: "staging"
      jobs:
        - name: "Staging CI"
          execute_steps:
            - "dbt build"
          triggers:
            on_merge: true
    
    # Production environment
    - name: "Production"
      type: "deployment"
      connection_id: 3
      credential:
        token_name: "prod_databricks_token"
        schema: "prod"
      jobs:
        - name: "Production Daily"
          execute_steps:
            - "dbt run"
            - "dbt test"
          triggers:
            schedule: true
            schedule_hours: [6]
            schedule_days: [0, 1, 2, 3, 4]
          
        - name: "Production CI"
          execute_steps:
            - "dbt build --select state:modified+"
          triggers:
            on_merge: true
          deferring_environment: "Production"
```

---

## Complete YAML Schema Reference

For the full specification of all available configuration options, see the [YAML Schema documentation](../configuration/yaml-schema.md).

### Quick Reference

```yaml
project:
  name: <string>                    # Required
  repository:
    remote_url: <string>            # Required
    git_clone_strategy: <string>    # Required
    gitlab_project_id: <number>     # Optional
    github_installation_id: <number> # Optional
  
  environments:
    - name: <string>                # Required
      type: <string>                # Required: "development" or "deployment"
      connection_id: <number>       # Required
      credential:
        token_name: <string>        # Optional
        schema: <string>            # Optional
        catalog: <string>           # Optional
      dbt_version: <string>         # Optional: default "latest"
      custom_branch: <string>       # Optional
      jobs:
        - name: <string>            # Required
          execute_steps:            # Required
            - <string>
          triggers:                 # Required
            schedule: <boolean>
            github_webhook: <boolean>
            on_merge: <boolean>
          # ... many more optional fields
  
  environment_variables:            # Optional
    - name: <string>                # Must start with DBT_
      environment_values:
        - env: <string>
          value: <string>
```

---

## More Examples Coming Soon

- **Snowflake Integration**
- **Databricks Unity Catalog**
- **BigQuery with Service Accounts**
- **GitLab CI/CD Pipeline**
- **Azure DevOps Integration**

Want to contribute an example? [Open a PR](https://github.com/trouze/dbt-terraform-modules-yaml/pulls)!
