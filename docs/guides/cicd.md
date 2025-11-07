# CI/CD Integration

Automate your dbt Cloud infrastructure deployments using CI/CD pipelines.

## Overview

This module integrates seamlessly with popular CI/CD platforms:

- **GitHub Actions** - Native GitHub integration
- **GitLab CI/CD** - Built into GitLab
- **Azure DevOps Pipelines** - Microsoft Azure
- **Jenkins** - Self-hosted automation
- **CircleCI** - Cloud-based CI/CD

All examples use environment variables for credentials, making them portable across platforms.

---

## GitHub Actions

### Basic Workflow

Deploy on push to main:

```yaml title=".github/workflows/dbt-cloud.yml"
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
      - name: Checkout code
        uses: actions/checkout@v3
      
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
          TF_VAR_token_map: ${{ secrets.TOKEN_MAP }}
        run: terraform plan -out=tfplan
      
      - name: Terraform Apply
        env:
          TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
          TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
          TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
          TF_VAR_dbt_host_url: https://cloud.getdbt.com/api
          TF_VAR_yaml_file_path: ./dbt-config.yml
          TF_VAR_token_map: ${{ secrets.TOKEN_MAP }}
        run: terraform apply tfplan
```

### With Pull Request Preview

Show plan in PR comments:

```yaml title=".github/workflows/terraform-pr.yml"
name: Terraform PR Check

on:
  pull_request:
    paths:
      - 'dbt-config.yml'
      - '**.tf'

permissions:
  contents: read
  pull-requests: write

jobs:
  plan:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
      
      - name: Terraform Init
        run: terraform init
      
      - name: Terraform Plan
        id: plan
        env:
          TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
          TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
          TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
          TF_VAR_dbt_host_url: https://cloud.getdbt.com/api
          TF_VAR_yaml_file_path: ./dbt-config.yml
          TF_VAR_token_map: ${{ secrets.TOKEN_MAP }}
        run: terraform plan -no-color
        continue-on-error: true
      
      - name: Comment Plan on PR
        uses: actions/github-script@v6
        with:
          script: |
            const output = `#### Terraform Plan 📋
            
            \`\`\`
            ${{ steps.plan.outputs.stdout }}
            \`\`\`
            
            *Pushed by: @${{ github.actor }}, Action: \`${{ github.event_name }}\`*`;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            })
```

### Multi-Project Matrix

Deploy multiple projects in parallel:

```yaml title=".github/workflows/multi-project.yml"
name: Deploy Multiple Projects

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        project: [finance, marketing, operations]
      fail-fast: false
    
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
          TF_VAR_token_map: ${{ secrets.TOKEN_MAP }}
        run: |
          terraform workspace select -or-create ${{ matrix.project }}
          terraform plan -out=tfplan
          terraform apply tfplan
```

---

## GitLab CI/CD

### Basic Pipeline

```yaml title=".gitlab-ci.yml"
stages:
  - validate
  - plan
  - apply

variables:
  TF_ROOT: ${CI_PROJECT_DIR}
  TF_VAR_dbt_host_url: "https://cloud.getdbt.com/api"
  TF_VAR_yaml_file_path: "./dbt-config.yml"

.terraform-base:
  image: hashicorp/terraform:latest
  before_script:
    - cd ${TF_ROOT}
    - terraform init

validate:
  extends: .terraform-base
  stage: validate
  script:
    - terraform fmt -check
    - terraform validate

plan:
  extends: .terraform-base
  stage: plan
  variables:
    TF_VAR_dbt_account_id: ${DBT_ACCOUNT_ID}
    TF_VAR_dbt_api_token: ${DBT_API_TOKEN}
    TF_VAR_dbt_pat: ${DBT_PAT}
    TF_VAR_token_map: ${TOKEN_MAP}
  script:
    - terraform plan -out=tfplan
  artifacts:
    paths:
      - ${TF_ROOT}/tfplan
    expire_in: 1 day

apply:
  extends: .terraform-base
  stage: apply
  variables:
    TF_VAR_dbt_account_id: ${DBT_ACCOUNT_ID}
    TF_VAR_dbt_api_token: ${DBT_API_TOKEN}
    TF_VAR_dbt_pat: ${DBT_PAT}
    TF_VAR_token_map: ${TOKEN_MAP}
  script:
    - terraform apply tfplan
  dependencies:
    - plan
  only:
    - main
  when: manual
```

---

## Azure DevOps

```yaml title="azure-pipelines.yml"
trigger:
  branches:
    include:
      - main
  paths:
    include:
      - dbt-config.yml
      - '*.tf'

pool:
  vmImage: 'ubuntu-latest'

variables:
  - group: dbt-cloud-credentials
  - name: TF_VAR_dbt_host_url
    value: 'https://cloud.getdbt.com/api'
  - name: TF_VAR_yaml_file_path
    value: './dbt-config.yml'

stages:
  - stage: Plan
    jobs:
      - job: TerraformPlan
        steps:
          - task: TerraformInstaller@0
            inputs:
              terraformVersion: 'latest'
          
          - task: TerraformTaskV2@2
            displayName: 'Terraform Init'
            inputs:
              command: 'init'
              workingDirectory: '$(System.DefaultWorkingDirectory)'
          
          - task: TerraformTaskV2@2
            displayName: 'Terraform Plan'
            inputs:
              command: 'plan'
              workingDirectory: '$(System.DefaultWorkingDirectory)'
              environmentServiceNameAzureRM: 'terraform-sp'
            env:
              TF_VAR_dbt_account_id: $(DBT_ACCOUNT_ID)
              TF_VAR_dbt_api_token: $(DBT_API_TOKEN)
              TF_VAR_dbt_pat: $(DBT_PAT)
              TF_VAR_token_map: $(TOKEN_MAP)
  
  - stage: Apply
    dependsOn: Plan
    condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
    jobs:
      - deployment: TerraformApply
        environment: 'production'
        strategy:
          runOnce:
            deploy:
              steps:
                - task: TerraformTaskV2@2
                  displayName: 'Terraform Apply'
                  inputs:
                    command: 'apply'
                    workingDirectory: '$(System.DefaultWorkingDirectory)'
                  env:
                    TF_VAR_dbt_account_id: $(DBT_ACCOUNT_ID)
                    TF_VAR_dbt_api_token: $(DBT_API_TOKEN)
                    TF_VAR_dbt_pat: $(DBT_PAT)
                    TF_VAR_token_map: $(TOKEN_MAP)
```

---

## Best Practices

### 1. Secret Management

✅ **DO:**
- Use platform-native secrets (GitHub Secrets, GitLab Variables, etc.)
- Mark secrets as "masked" or "protected"
- Use different secrets for dev/staging/prod
- Rotate secrets regularly

❌ **DON'T:**
- Hardcode credentials in workflow files
- Echo secrets in logs
- Share secrets across unrelated projects

### 2. Environment Separation

Use different workflows for environments:

```yaml
# Production
on:
  push:
    branches: [main]

# Staging
on:
  push:
    branches: [staging]

# Development
on:
  push:
    branches: [develop]
```

### 3. Approval Gates

Require manual approval for production:

**GitHub Actions:**
```yaml
environment:
  name: production
  url: https://cloud.getdbt.com
```

**GitLab CI/CD:**
```yaml
apply:
  when: manual
  only:
    - main
```

### 4. Plan Artifact

Save plan output for review:

```yaml
- name: Save Plan
  run: terraform show -no-color tfplan > plan.txt

- name: Upload Plan
  uses: actions/upload-artifact@v3
  with:
    name: terraform-plan
    path: plan.txt
```

### 5. Parallel Execution

Use matrix strategy for multiple projects:

```yaml
strategy:
  matrix:
    project: [a, b, c]
  fail-fast: false  # Continue even if one fails
  max-parallel: 3   # Limit concurrent jobs
```

---

## Troubleshooting

### "No value for required variable"

**Problem:** Secrets not loaded.

**Solution:**
- Verify secrets are defined in CI/CD platform
- Check variable names match exactly
- Ensure workflow has access to secrets

### "State Lock Timeout"

**Problem:** Previous run didn't release state lock.

**Solution:**
```yaml
- name: Force Unlock (emergency only)
  run: terraform force-unlock -force <LOCK_ID>
```

### "Plan Changes Unexpectedly"

**Problem:** State drift or external changes.

**Solution:**
- Run `terraform refresh` to sync state
- Review changes carefully
- Consider using `terraform import` for existing resources

---

## Complete Example

Putting it all together:

```yaml title=".github/workflows/complete.yml"
name: dbt Cloud Infrastructure

on:
  pull_request:
    paths: ['**.yml', '**.tf']
  push:
    branches: [main]
    paths: ['**.yml', '**.tf']

permissions:
  contents: read
  pull-requests: write

jobs:
  terraform:
    name: Terraform ${{ github.event_name == 'pull_request' && 'Plan' || 'Apply' }}
    runs-on: ubuntu-latest
    
    env:
      TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
      TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
      TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
      TF_VAR_dbt_host_url: https://cloud.getdbt.com/api
      TF_VAR_yaml_file_path: ./dbt-config.yml
      TF_VAR_token_map: ${{ secrets.TOKEN_MAP }}
    
    steps:
      - name: Checkout
        uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.6.0
      
      - name: Terraform Format Check
        run: terraform fmt -check -recursive
      
      - name: Terraform Init
        run: terraform init
      
      - name: Terraform Validate
        run: terraform validate
      
      - name: Terraform Plan
        id: plan
        run: |
          terraform plan -no-color -out=tfplan
          terraform show -no-color tfplan > plan.txt
      
      - name: Comment Plan on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const plan = fs.readFileSync('plan.txt', 'utf8');
            const output = `#### Terraform Plan 📋
            <details><summary>Show Plan</summary>
            
            \`\`\`
            ${plan}
            \`\`\`
            
            </details>
            
            *Pusher: @${{ github.actor }}, Action: \`${{ github.event_name }}\`*`;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            })
      
      - name: Terraform Apply
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        run: terraform apply -auto-approve tfplan
      
      - name: Upload Plan Artifact
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: terraform-plan
          path: plan.txt
          retention-days: 30
```

---

## Next Steps

<div class="grid cards" markdown>

-   :material-folder-multiple:{ .lg .middle } __Multi-Project Setup__

    ---

    Manage multiple dbt projects

    [:octicons-arrow-right-24: Multi-Project Guide](../configuration/multi-project.md)

-   :material-security:{ .lg .middle } __Best Practices__

    ---

    Secure and reliable deployments

    [:octicons-arrow-right-24: Best Practices](best-practices.md)

</div>
