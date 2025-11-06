# Repository Configuration Examples

This directory contains ready-to-use example configurations for different Git providers and integration strategies.

## Overview

The repository module supports multiple Git providers with auto-detection and smart validation:
- **GitHub** (with GitHub App native integration)
- **GitLab** (with Deploy Token native integration)
- **Azure DevOps** (with Azure AD native integration)
- **Bitbucket** and other providers (with SSH Deploy Key)

Each example folder contains a complete, copy-paste-ready configuration.

## Quick Start

1. **Choose your Git provider** - Pick the example that matches your setup:
   - [GitHub with GitHub App](#github-with-github-app) - Recommended for GitHub
   - [GitLab with Deploy Token](#gitlab-with-deploy-token) - Recommended for GitLab
   - [Azure DevOps Native](#azure-devops-native) - Recommended for Azure
   - [Generic SSH Deploy Key](#generic-ssh-deploy-key) - Works anywhere

2. **Copy the example folder:**
   ```bash
   cp -r examples/github-github-app/ my-dbt-setup
   cd my-dbt-setup
   ```

3. **Fill in your values:**
   - Edit `dbt-config.yml` with your repository URL and provider-specific IDs
   - Copy `terraform.tfvars.example` to `terraform.tfvars`
   - Edit `terraform.tfvars` with your credentials

4. **Deploy:**
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

---

## Examples Directory

### GitHub with GitHub App

**Best for**: GitHub users who want native GitHub App integration  
**Location**: `github-github-app/`

**Features**:
- ✅ No tokens in Terraform (better security)
- ✅ Automatic webhook management
- ✅ Native PR integration
- ✅ Granular permissions

See [REPOSITORY_CONFIGURATION.md](../docs/REPOSITORY_CONFIGURATION.md) for how to find your GitHub App installation ID.

---

### GitLab with Deploy Token

**Best for**: GitLab users who want native Deploy Token integration  
**Location**: `gitlab-deploy-token/`

**Features**:
- ✅ Fine-grained access control
- ✅ No personal tokens needed
- ✅ Easy to rotate
- ✅ Good for CI/CD

See [REPOSITORY_CONFIGURATION.md](../docs/REPOSITORY_CONFIGURATION.md) for how to find your GitLab project ID.

---

### Azure DevOps Native

**Best for**: Azure DevOps users who want native Azure AD integration  
**Location**: `azure-devops-native/`

**Features**:
- ✅ Seamless Azure AD authentication
- ✅ Native webhook support
- ✅ Better PR integration
- ✅ Granular permissions

See [REPOSITORY_CONFIGURATION.md](../docs/REPOSITORY_CONFIGURATION.md) for how to find your Azure project and repository IDs.

---

### Generic SSH Deploy Key

**Best for**: Any Git provider (including self-hosted systems)  
**Location**: `generic-ssh-deploy-key/`

**Features**:
- ✅ Works with GitHub, GitLab, Azure, Bitbucket, Gitea, etc.
- ✅ No provider-specific IDs needed
- ✅ Simple SSH key authentication
- ✅ Good for self-hosted Git systems

See [REPOSITORY_CONFIGURATION.md](../docs/REPOSITORY_CONFIGURATION.md) for SSH key setup instructions.

---

## File Structure

Each example contains:

```
examples/
├── github-github-app/
│   ├── main.tf                    # Root module call
│   ├── variables.tf               # Variable definitions
│   ├── dbt-config.yml             # dbt Cloud config (edit this)
│   └── terraform.tfvars.example   # Terraform vars (copy & edit)
│
├── gitlab-deploy-token/           # Same structure for GitLab
├── azure-devops-native/           # Same structure for Azure
├── generic-ssh-deploy-key/        # Same structure for SSH
└── basic/                         # Minimal legacy example
```

---

## Quick Deployment

```bash
# 1. Choose your provider and copy
cp -r examples/github-github-app my-setup
cd my-setup

# 2. Edit configuration
nano dbt-config.yml              # Update with your repo details
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars            # Add your credentials

# 3. Deploy
terraform init
terraform plan
terraform apply
```

---

## Detailed Guides

For complete provider setup guides, see:
- **[REPOSITORY_CONFIGURATION.md](../docs/REPOSITORY_CONFIGURATION.md)** - Detailed setup for each provider
- **[MIGRATION_GUIDE.md](../docs/MIGRATION_GUIDE.md)** - Migrating from manual setup
- **[QUICKSTART.md](../docs/QUICKSTART.md)** - Getting started in 5 minutes
- **[README.md](../README.md)** - Complete documentation

---

## Common Tasks

**Running a test deployment:**
```bash
terraform plan -out=tfplan
terraform show tfplan  # Review changes
```

**Updating repository configuration:**
1. Edit `dbt-config.yml`
2. Run `terraform plan`
3. Run `terraform apply`

**Switching providers:**
1. Copy different example directory
2. Update `dbt-config.yml` with new repository URL
3. Update `terraform.tfvars` if needed
4. Run `terraform apply`

**Temporary disable:**
```yaml
repository:
  is_active: false
```

---

## Security Best Practices

1. **Never commit credentials** - Add `terraform.tfvars` to `.gitignore`
2. **Use native integrations** - GitHub App, Deploy Tokens are more secure
3. **Rotate credentials** - Regularly update tokens and keys
4. **Minimal permissions** - Grant only necessary scopes
5. **Separate dev/prod** - Use different credentials per environment

---

## Troubleshooting

**Configuration validation failed?**
- Check `remote_url` matches your Git provider
- Verify `git_clone_strategy` is correct
- Ensure provider-specific IDs are present

**Repository connection failed?**
- Verify `remote_url` is correct
- Check deploy keys/tokens are configured
- Review GitHub App installation (if using GitHub)

**See full troubleshooting:**
- [REPOSITORY_CONFIGURATION.md - Troubleshooting](../docs/REPOSITORY_CONFIGURATION.md#troubleshooting)
- [README.md - Troubleshooting](../README.md#troubleshooting)

---

## Contributing

Have improvements to the examples? See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## License

Apache License 2.0 - See [LICENSE](../LICENSE)