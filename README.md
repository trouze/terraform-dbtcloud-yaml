# dbt-terraform-modules-yaml

[![Terraform Version](https://img.shields.io/badge/terraform-%3E%3D%201.0-blue?logo=terraform)](https://www.terraform.io)
[![dbt Cloud Provider](https://img.shields.io/badge/dbt--cloud--provider-%3E%3D%201.3-blue)](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

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

See [examples/README.md](examples/README.md) for a complete walkthrough. Here's the 30-second version:

1. **Copy the basic example**
   ```bash
   cp -r examples/basic my-dbt-setup
   cd my-dbt-setup
   ```

2. **Create your .env file**
   ```bash
   cp .env.example .env
   # Edit with your dbt Cloud credentials
   ```

3. **Deploy**
   ```bash
   source .env
   terraform init && terraform plan && terraform apply
   ```

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
    - name: "dev"
      type: "development"
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

### Single dbt Project
```bash
terraform apply
```

### Multiple dbt Projects (parallel CI/CD)
```bash
# Run each project separately
for config in configs/*.yml; do
  terraform plan -var="yaml_file_path=$config"
done
```

### CI/CD Pipeline
```yaml
# GitHub Actions example
- env:
    TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
    TF_VAR_dbt_api_token: ${{ secrets.DBT_API_TOKEN }}
  run: terraform apply
```

## Requirements

- Terraform >= 1.0
- dbt Cloud account
- dbt Cloud API token
- Git repository for your dbt models

## Documentation

- [Examples](examples/README.md) - Get started in 5 minutes
- [Module Details](docs/) - Complete configuration reference
- [Best Practices](docs/BEST_PRACTICES.md) - Recommended patterns

## Best Practices

### Security
- ✅ **Never commit credentials** - use `.env` (local) or GitHub Secrets (CI/CD)
- ✅ **Use service principals** - create dedicated dbt Cloud API tokens
- ✅ **Limit token scope** - only grant necessary permissions
- ✅ **Rotate regularly** - refresh tokens periodically

### Organization
- ✅ **Version control your YAML** - track all infrastructure changes
- ✅ **Use environments** - separate dev/staging/prod configs
- ✅ **Document custom settings** - add comments in your YAML
- ✅ **Test before deploying** - use `terraform plan` first

### CI/CD
- ✅ **Run in parallel** - use matrix builds for multiple projects
- ✅ **Store secrets** - use platform-native secret management
- ✅ **Automate deployments** - trigger on config changes
- ✅ **Require approvals** - review plans before applying

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

- 📖 **Documentation** - Check [docs/](docs/) for detailed guides
- 🐛 **Issues** - Report bugs or request features on GitHub
- 💬 **Discussions** - Share ideas and best practices

## License

This project is licensed under Apache License 2.0. See [LICENSE](LICENSE) for details.

---

**Ready to manage your dbt Cloud with code?** Start with the [examples](examples/README.md)!
