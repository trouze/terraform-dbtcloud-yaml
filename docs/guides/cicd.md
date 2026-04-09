# CI/CD Integration

Automate your dbt Cloud infrastructure deployments using CI/CD pipelines.

## Overview

The recommended pattern is two separate workflows:

- **CI** (`ci.yml`) — runs on every PR, validates config and posts the Terraform plan as a comment
- **CD** (`cd.yml`) — runs on merge to main, applies the plan with an optional approval gate

The `topologies/basic/.github/workflows/` directory contains ready-to-use versions of both.

---

## GitHub Actions

### Required Secrets

Set these in your repository: **Settings > Secrets and variables > Actions**

| Secret | Description | Required |
|--------|-------------|----------|
| `DBT_ACCOUNT_ID` | Numeric dbt Cloud account ID | Yes |
| `DBT_TOKEN` | dbt Cloud API token | Yes |
| `DBT_PAT` | Personal access token (GitHub App integration only; can equal `DBT_TOKEN`) | Conditional |
| `ENVIRONMENT_CREDENTIALS` | JSON blob — see [Environment Variables](../configuration/environment-variables.md) | Yes (if using env credentials) |
| `CONNECTION_CREDENTIALS` | JSON blob for global connection OAuth/keys | If using global connections |
| `LINEAGE_TOKENS` | JSON blob for Tableau/Looker tokens | If using lineage integrations |
| `OAUTH_CLIENT_SECRETS` | JSON blob for OAuth configurations | If using OAuth |

### CI — Plan on PR

Runs on every pull request that touches `dbt-config.yml` or any `.tf` file. Posts the Terraform plan as a PR comment (updates the existing comment on re-push rather than stacking new ones).

```yaml title=".github/workflows/ci.yml"
name: CI — Terraform Plan

on:
  pull_request:
    branches: [main]
    paths:
      - "dbt-config.yml"
      - "**.tf"

permissions:
  contents: read
  pull-requests: write

jobs:
  plan:
    name: Validate and Plan
    runs-on: ubuntu-latest

    env:
      TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
      TF_VAR_dbt_token: ${{ secrets.DBT_TOKEN }}
      TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
      TF_VAR_dbt_host_url: "https://cloud.getdbt.com"
      TF_VAR_environment_credentials: ${{ secrets.ENVIRONMENT_CREDENTIALS }}
      TF_VAR_connection_credentials: ${{ secrets.CONNECTION_CREDENTIALS }}
      TF_VAR_lineage_tokens: ${{ secrets.LINEAGE_TOKENS }}
      TF_VAR_oauth_client_secrets: ${{ secrets.OAUTH_CLIENT_SECRETS }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "~1"

      - name: Terraform Init
        run: terraform init

      - name: Terraform Validate
        run: terraform validate

      - name: Terraform Plan
        id: plan
        run: |
          terraform plan -no-color -out=tfplan
          terraform show -no-color tfplan > plan.txt
        continue-on-error: true  # Post comment even if plan fails

      - name: Post plan as PR comment
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const raw = fs.readFileSync('plan.txt', 'utf8');

            // Truncate if the plan is too large for a GitHub comment
            const maxLen = 60000;
            const plan = raw.length > maxLen
              ? raw.slice(0, maxLen) + '\n\n... output truncated (full plan in Actions log)'
              : raw;

            const status = '${{ steps.plan.outcome }}' === 'success' ? '✅' : '❌';
            const body = `### ${status} Terraform Plan

            <details><summary>Show plan</summary>

            \`\`\`hcl
            ${plan}
            \`\`\`

            </details>

            > Triggered by @${{ github.actor }} on \`${{ github.head_ref }}\``;

            // Replace any previous plan comment instead of stacking new ones
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
            });
            const prev = comments.find(c =>
              c.user.type === 'Bot' && c.body.includes('Terraform Plan')
            );
            if (prev) {
              await github.rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: prev.id,
                body,
              });
            } else {
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body,
              });
            }

      - name: Fail if plan errored
        if: steps.plan.outcome == 'failure'
        run: exit 1
```

### CD — Apply on Merge

Runs on push to main (i.e., after a PR merges). Uses a GitHub Environment (`production`) which can be configured with required reviewers for an approval gate before apply.

```yaml title=".github/workflows/cd.yml"
name: CD — Terraform Apply

on:
  push:
    branches: [main]
    paths:
      - "dbt-config.yml"
      - "**.tf"

permissions:
  contents: read

jobs:
  apply:
    name: Apply
    runs-on: ubuntu-latest
    environment: production  # remove this line if you don't need an approval gate

    env:
      TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
      TF_VAR_dbt_token: ${{ secrets.DBT_TOKEN }}
      TF_VAR_dbt_pat: ${{ secrets.DBT_PAT }}
      TF_VAR_dbt_host_url: "https://cloud.getdbt.com"
      TF_VAR_environment_credentials: ${{ secrets.ENVIRONMENT_CREDENTIALS }}
      TF_VAR_connection_credentials: ${{ secrets.CONNECTION_CREDENTIALS }}
      TF_VAR_lineage_tokens: ${{ secrets.LINEAGE_TOKENS }}
      TF_VAR_oauth_client_secrets: ${{ secrets.OAUTH_CLIENT_SECRETS }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "~1"

      - name: Terraform Init
        run: terraform init

      - name: Terraform Plan
        run: terraform plan -no-color -out=tfplan

      - name: Terraform Apply
        run: terraform apply -auto-approve tfplan
```

### Setting Up the Approval Gate

To require a reviewer before applying to production:

1. Go to **Settings > Environments** in your GitHub repository
2. Create an environment named `production`
3. Add **Required reviewers**
4. Optionally add branch protection rules (e.g., only allow deploys from `main`)

Remove the `environment: production` line from `cd.yml` if you don't need this gate.

### Remote State

Before using these workflows in production, configure a [Terraform backend](https://developer.hashicorp.com/terraform/language/settings/backends/configuration) in `main.tf` (S3, GCS, Terraform Cloud, etc.). Without it, state is local and lost between CI runs.

---

## GitLab CI/CD

### Masked Variables

Store credentials in **Settings > CI/CD > Variables**. Mark all credential variables as **Masked** and **Protected**.

```yaml title=".gitlab-ci.yml"
stages:
  - validate
  - plan
  - apply

variables:
  TF_VAR_dbt_host_url: "https://cloud.getdbt.com"

.terraform-base:
  image: hashicorp/terraform:latest
  before_script:
    - terraform init

validate:
  extends: .terraform-base
  stage: validate
  script:
    - terraform validate

plan:
  extends: .terraform-base
  stage: plan
  variables:
    TF_VAR_dbt_account_id: $DBT_ACCOUNT_ID
    TF_VAR_dbt_token: $DBT_TOKEN
    TF_VAR_dbt_pat: $DBT_PAT
    TF_VAR_environment_credentials: $ENVIRONMENT_CREDENTIALS
    TF_VAR_connection_credentials: $CONNECTION_CREDENTIALS
  script:
    - terraform plan -out=tfplan
  artifacts:
    paths:
      - tfplan
    expire_in: 1 day

apply:
  extends: .terraform-base
  stage: apply
  variables:
    TF_VAR_dbt_account_id: $DBT_ACCOUNT_ID
    TF_VAR_dbt_token: $DBT_TOKEN
    TF_VAR_dbt_pat: $DBT_PAT
    TF_VAR_environment_credentials: $ENVIRONMENT_CREDENTIALS
    TF_VAR_connection_credentials: $CONNECTION_CREDENTIALS
  script:
    - terraform apply tfplan
  dependencies:
    - plan
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual   # Approval gate
```

---

## Azure DevOps

Store credentials in **Pipelines > Library > Variable groups** (mark as secret).

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
    value: 'https://cloud.getdbt.com'

stages:
  - stage: Plan
    jobs:
      - job: TerraformPlan
        steps:
          - task: TerraformInstaller@1
            inputs:
              terraformVersion: 'latest'

          - task: TerraformTaskV4@4
            displayName: 'Terraform Init'
            inputs:
              command: 'init'

          - task: TerraformTaskV4@4
            displayName: 'Terraform Plan'
            inputs:
              command: 'plan'
            env:
              TF_VAR_dbt_account_id: $(DBT_ACCOUNT_ID)
              TF_VAR_dbt_token: $(DBT_TOKEN)
              TF_VAR_dbt_pat: $(DBT_PAT)
              TF_VAR_environment_credentials: $(ENVIRONMENT_CREDENTIALS)

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
                - task: TerraformTaskV4@4
                  displayName: 'Terraform Apply'
                  inputs:
                    command: 'apply'
                  env:
                    TF_VAR_dbt_account_id: $(DBT_ACCOUNT_ID)
                    TF_VAR_dbt_token: $(DBT_TOKEN)
                    TF_VAR_dbt_pat: $(DBT_PAT)
                    TF_VAR_environment_credentials: $(ENVIRONMENT_CREDENTIALS)
```

---

## Best Practices

### Secret Management

✅ **DO:**
- Use platform-native secrets (GitHub Secrets, GitLab masked variables, Azure Library, key vault)
- Mark secrets as "masked" or "protected" so they never appear in logs
- Use the same secret names across environments for consistency
- Rotate tokens regularly

❌ **DON'T:**
- Hardcode credentials in workflow files
- Echo secrets in scripts
- Use personal tokens for automated workflows (use service account tokens)

### Credential JSON Format

JSON blob variables (`ENVIRONMENT_CREDENTIALS`, `CONNECTION_CREDENTIALS`, etc.) must be single-line JSON strings in CI/CD secrets:

```
{"analytics_prod": {"credential_type": "databricks", "token": "dapi...", "catalog": "main", "schema": "analytics"}}
```

In `terraform.tfvars` (local use only), you can use HCL map syntax instead:

```hcl
environment_credentials = {
  analytics_prod = {
    credential_type = "databricks"
    token           = "dapi..."
    catalog         = "main"
    schema          = "analytics"
  }
}
```

### Approval Gates

Require manual approval before production apply:

- **GitHub Actions**: `environment: production` with Required reviewers configured
- **GitLab CI**: `when: manual` on the apply job
- **Azure DevOps**: deployment environment with approval policies

---

## Next Steps

<div class="grid cards" markdown>

-   :material-key:{ .lg .middle } **Environment Variables**

    ---

    Full credential variable reference and setup instructions

    [:octicons-arrow-right-24: Environment Variables](../configuration/environment-variables.md)

-   :material-folder-multiple:{ .lg .middle } **Multi-Project Setup**

    ---

    Manage multiple dbt projects in one repo

    [:octicons-arrow-right-24: Multi-Project Guide](../configuration/multi-project.md)

-   :material-security:{ .lg .middle } **Best Practices**

    ---

    Secure and reliable deployments

    [:octicons-arrow-right-24: Best Practices](best-practices.md)

</div>
