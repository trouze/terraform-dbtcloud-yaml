# terraform-dbtcloud-yaml

[![Terraform Version](https://img.shields.io/badge/terraform-%3E%3D%201.0-blue?logo=terraform)](https://www.terraform.io) [![dbt Cloud Provider](https://img.shields.io/badge/dbt--cloud--provider-v1.3-blue)](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest) [![License](https://img.shields.io/badge/license-Apache%202.0-green)](https://github.com/trouze/terraform-dbtcloud-yaml/blob/main/LICENSE)

Manage your entire dbt Cloud setup with infrastructure-as-code using Terraform and YAML. Define projects, repositories, environments, credentials, and jobs in a single, human-readable YAML file.

## Why This Project Exists

Setting up dbt Cloud via Terraform requires writing complex HCL for every resource. This module simplifies that by letting you define your infrastructure in YAML - the language data teams already know. No need to learn Terraform syntax just to configure dbt.

**Benefits:**

- ✅ **YAML-based configuration** - intuitive for data engineers
- ✅ **Infrastructure as Code** - version control your dbt setup
- ✅ **Multi-provider Git support** - GitHub, GitLab, Azure DevOps, SSH
- ✅ **Complete resource management** - projects, repos, environments, credentials, jobs
- ✅ **Environment variable management** - set dbt variables alongside infrastructure
- ✅ **Reusable modules** - standardize your dbt deployments

## Quick Start

Get started in 3 simple steps:

## Quick Start

Get started in 3 simple steps:

=== "Step 1: Clone the Example"

    ```bash
    # Clone or copy the basic example
    git clone https://github.com/trouze/terraform-dbtcloud-yaml.git
    cd terraform-dbtcloud-yaml/examples/basic

    # Or copy to your own directory
    cp -r examples/basic my-dbt-setup
    cd my-dbt-setup
    ```

=== "Step 2: Configure Credentials"

    ```bash
    # Create .env file from example
    cp .env.example .env

    # Edit with your dbt Cloud credentials
    export TF_VAR_dbt_account_id=12345
    export TF_VAR_dbt_api_token=dbtc_xxxxx
    export TF_VAR_dbt_pat=dbtc_xxxxx
    export TF_VAR_dbt_host_url=https://cloud.getdbt.com/api
    export TF_VAR_yaml_file_path=./dbt-config.yml
    ```

=== "Step 3: Deploy"

    ```bash
    # Load credentials
    source .env

    # Initialize and deploy
    terraform init
    terraform plan
    terraform apply
    ```

!!! success "That's it!"
    Your dbt Cloud project is now managed with infrastructure-as-code!

## Features

### YAML Configuration

Define everything in one file:

```yaml
project:
  name: "my-dbt-project"
  repository:
    remote_url: "https://github.com/myorg/myrepo.git"
    git_clone_strategy: "github_app"
    github_installation_id: 123456

  environments:
    - name: "Production"
      type: "deployment"
      connection_id: 1
      jobs:
        - name: "daily_run"
          execute_steps:
            - "dbt run"
          triggers:
            schedule: true
            schedule_hours: [6]
```

### Multi-Provider Git Support

Automatically configures your Git provider:

- **GitHub** with GitHub App
- **GitLab** with Deploy Token
- **Azure DevOps** with Azure AD
- **SSH** Deploy Key (universal)

### Secure Credentials

- Keep secrets in `.env` or GitHub Secrets
- Never commit sensitive values
- Support for database credentials as environment variables

## Use Cases

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Single dbt Project**

    ---

    Get started quickly with a single project

    ```bash
    terraform apply
    ```

-   :material-git:{ .lg .middle } **Multiple Projects**

    ---

    Run multiple dbt projects in parallel CI/CD

    ```bash
    # Run each project separately
    for config in configs/*.yml; do
      terraform plan -var="yaml_file_path=$config"
    done
    ```

-   :material-github:{ .lg .middle } **CI/CD Pipeline**

    ---

    Automate deployments with GitHub Actions

    ```yaml
    # GitHub Actions example
    - env:
        TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
        TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
      run: terraform apply
    ```

</div>

## Requirements

- Terraform >= 1.0
- dbt Cloud account
- dbt Cloud API token
- Git repository for your dbt models

## What's Next?

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting Started**

    ---

    Follow the quick start guide to deploy your first dbt Cloud project

    [:octicons-arrow-right-24: Quick Start](getting-started/quickstart.md)

-   :material-file-document:{ .lg .middle } **Configuration**

    ---

    Learn about YAML schema and configuration options

    [:octicons-arrow-right-24: Configuration](configuration/yaml-schema.md)

-   :material-book-open-variant:{ .lg .middle } **Examples**

    ---

    Explore real-world examples and use cases

    [:octicons-arrow-right-24: Examples](getting-started/examples.md)

-   :material-github:{ .lg .middle } **Reference**

    ---

    Complete Terraform module API documentation

    [:octicons-arrow-right-24: Module API](reference/terraform.md)

</div>

## Community & Support

- 📖 **Documentation** - You're reading it!
- 🐛 **Issues** - [Report bugs or request features](https://github.com/trouze/terraform-dbtcloud-yaml/issues)
- 💬 **Discussions** - [Share ideas and best practices](https://github.com/trouze/terraform-dbtcloud-yaml/discussions)

## License

This project is licensed under Apache License 2.0. See [LICENSE](https://github.com/trouze/terraform-dbtcloud-yaml/blob/main/LICENSE) for details.

---

**Ready to manage your dbt Cloud with code?** Start with the [Quick Start Guide](getting-started/quickstart.md)!
