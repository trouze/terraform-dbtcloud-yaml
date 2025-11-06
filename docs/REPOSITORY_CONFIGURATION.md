# Repository Configuration Guide

This guide helps you configure Git repositories in dbt Cloud across different Git providers: GitHub, GitLab, Azure DevOps, and Bitbucket.

## How It Works

The repository module uses **auto-detection** and **smart validation**:

1. **Auto-Detection**: Analyzes your `remote_url` to identify the Git provider
2. **Strategy Auto-Selection**: Defaults to the native integration strategy for that provider
3. **Validation**: Ensures all required fields are present and consistent with your provider choice

This means in most cases, you only need to provide a `remote_url` and let the module handle the rest!

---

## Quick Examples

### GitHub with GitHub App (Recommended)
```yaml
repository:
  remote_url: "https://github.com/myorg/myrepo.git"
  github_installation_id: 12345678
```

### GitLab with Deploy Token
```yaml
repository:
  remote_url: "https://gitlab.com/mygroup/myproject.git"
  gitlab_project_id: 9876543
```

### Azure DevOps
```yaml
repository:
  remote_url: "https://dev.azure.com/myorg/myproject/_git/myrepo"
  azure_active_directory_project_id: "550e8400-e29b-41d4-a716-446655440000"
  azure_active_directory_repository_id: "550e8400-e29b-41d4-a716-446655440001"
```

### Generic (SSH Deploy Key - Works Everywhere)
```yaml
repository:
  remote_url: "git@github.com:myorg/myrepo.git"
```

---

## Detailed Provider Guides

### GitHub

#### Option A: GitHub App (Recommended for Security & Features)

**Auto-Detection**: ✅ Supported  
**Auto-Strategy**: `github_app`

**Prerequisites**:
1. Install dbt Cloud GitHub App on your repository
2. Note the installation ID

**How to Find GitHub Installation ID**:

**Option 1: From GitHub App URL**
- Go to GitHub Settings → Developer Settings → GitHub Apps
- Click on the dbt Cloud app
- Look at the URL: `https://github.com/apps/dbt-cloud/installations/XXXXXXX`
- The number after `/installations/` is your ID

**Option 2: From GitHub API**
```bash
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
  https://api.github.com/user/installations | jq '.installations[] | select(.app.slug=="dbt-cloud") | .id'
```

**Option 3: From dbt Cloud**
- Go to Account Settings → Connections → GitHub
- The Installation ID is displayed

**Configuration**:
```yaml
repository:
  remote_url: "https://github.com/myorg/myrepo.git"
  git_clone_strategy: "github_app"  # optional, auto-detected
  github_installation_id: 12345678
```

**Benefits**:
- Better security (no tokens needed in Terraform)
- Automatic webhook management
- Better PR integration
- Granular permissions

---

#### Option B: SSH Deploy Key (Works Everywhere)

**Auto-Detection**: ✅ Supported  
**Auto-Strategy**: `deploy_key` (if not explicitly set)

**Prerequisites**:
1. Generate SSH keypair for dbt Cloud
2. Add public key as deploy key in GitHub repository
3. Add private key as credential in dbt Cloud

**How to Create SSH Deploy Key**:

```bash
# Generate keypair
ssh-keygen -t ed25519 -f dbt-cloud-key -C "dbt-cloud"

# Add public key to GitHub
# 1. Go to your repository Settings → Deploy Keys
# 2. Click "Add deploy key"
# 3. Paste contents of dbt-cloud-key.pub
# 4. Check "Allow write access" if needed
# 5. Save

# Store private key in dbt Cloud credential
```

**Configuration**:
```yaml
repository:
  remote_url: "git@github.com:myorg/myrepo.git"
  # git_clone_strategy not needed (defaults to deploy_key)
```

**When to Use**:
- If GitHub App installation isn't possible
- For compatibility with other systems
- When using SSH-only environments

---

### GitLab

#### Option A: Deploy Token Integration (Recommended)

**Auto-Detection**: ✅ Supported  
**Auto-Strategy**: `deploy_token`

**Prerequisites**:
1. Create a Deploy Token in GitLab project
2. Note the Project ID
3. Add token to dbt Cloud credentials

**How to Find GitLab Project ID**:

**Option 1: From GitLab URL**
- Go to your project Settings → General
- Project ID is displayed at the top (looks like "12345")

**Option 2: From GitLab API**
```bash
curl -H "PRIVATE-TOKEN: YOUR_GITLAB_TOKEN" \
  https://gitlab.com/api/v4/projects/mygroup%2Fmyproject | jq '.id'
```

**How to Create Deploy Token**:
1. Go to Project Settings → Access Tokens
2. Create a new access token with `api`, `read_repository`, `write_repository` scopes
3. Copy the token (you won't see it again!)
4. Add token to dbt Cloud as a credential

**Configuration**:
```yaml
repository:
  remote_url: "https://gitlab.com/mygroup/myproject.git"
  git_clone_strategy: "deploy_token"  # optional, auto-detected
  gitlab_project_id: 9876543
```

**Benefits**:
- Fine-grained access control
- No personal tokens needed
- Easy to rotate
- Good for CI/CD integration

---

#### Option B: SSH Deploy Key

**Auto-Detection**: ✅ Supported  
**Auto-Strategy**: `deploy_key` (if not explicitly set)

Similar process to GitHub:
1. Generate SSH keypair
2. Add to Project Settings → Deploy Keys
3. Use SSH remote URL

**Configuration**:
```yaml
repository:
  remote_url: "git@gitlab.com:mygroup/myproject.git"
```

---

### Azure DevOps

#### Option A: Azure AD Application (Recommended)

**Auto-Detection**: ✅ Supported  
**Auto-Strategy**: `azure_active_directory_app`

**Prerequisites**:
1. Register Azure AD Application
2. Create application secret
3. Grant repository access
4. Note Project ID and Repository ID

**How to Find Azure DevOps IDs**:

**Project ID**:
1. Go to Project Settings → General
2. In the URL: `https://dev.azure.com/ORGNAME/PROJECT_ID/`
3. Look for the UUID in the URL bar, or in project breadcrumb

**Repository ID**:
1. Go to Repos → Files
2. In the URL: `https://dev.azure.com/ORGNAME/PROJECT/_git/REPO_ID`
3. Or use Azure DevOps CLI:
   ```bash
   az repos list --project "PROJECT_NAME" --org "YOUR_ORG" --query "[].id"
   ```

**How to Create Azure AD Application**:

1. Go to Azure Portal → Azure Active Directory → App registrations
2. Click "New registration"
3. Enter name "dbt-Cloud"
4. Note the Application ID (client ID)
5. Go to Certificates & Secrets
6. Create a new client secret, note the value
7. Grant permissions:
   - Go to API permissions
   - Add Azure DevOps permissions as needed

**Configuration**:
```yaml
repository:
  remote_url: "https://dev.azure.com/myorg/myproject/_git/myrepo"
  git_clone_strategy: "azure_active_directory_app"  # optional, auto-detected
  azure_active_directory_project_id: "550e8400-e29b-41d4-a716-446655440000"
  azure_active_directory_repository_id: "550e8400-e29b-41d4-a716-446655440001"
  # Optional: if webhook registration sometimes fails
  azure_bypass_webhook_registration_failure: true
```

**UUID Format Notes**:
- These look like: `550e8400-e29b-41d4-a716-446655440000`
- Use the full UUID including hyphens
- Different from numeric IDs shown in some URLs

---

#### Option B: SSH Deploy Key

**Auto-Detection**: ✅ Supported  
**Auto-Strategy**: `deploy_key` (if not explicitly set)

Similar to GitHub/GitLab:

**Configuration**:
```yaml
repository:
  remote_url: "git@ssh.dev.azure.com:v3/myorg/myproject/myrepo"
```

---

### Bitbucket

#### Deploy Key (Default for Bitbucket)

**Auto-Detection**: ✅ Supported  
**Auto-Strategy**: `deploy_key`

**Prerequisites**:
1. Generate SSH keypair
2. Add to Repository Settings → Access Keys
3. Add private key to dbt Cloud credential

**Configuration**:
```yaml
repository:
  remote_url: "git@bitbucket.org:myorg/myrepo.git"
  # Strategy defaults to deploy_key automatically
```

---

## Validation & Error Messages

The module validates your configuration and provides helpful error messages if something's wrong.

### Common Errors & Solutions

#### ❌ "git_clone_strategy 'github_app' does not match detected provider 'gitlab'"

**Problem**: You specified `github_app` strategy but your URL is a GitLab repo.

**Solution**: Either:
- Change `remote_url` to GitHub: `https://github.com/...`
- Remove/change `git_clone_strategy` to `deploy_token` for GitLab

```yaml
repository:
  remote_url: "https://gitlab.com/mygroup/myproject.git"
  git_clone_strategy: "deploy_token"  # Correct for GitLab
  gitlab_project_id: 123456
```

---

#### ❌ "git_clone_strategy 'github_app' requires 'github_installation_id'"

**Problem**: You specified `github_app` but didn't provide the installation ID.

**Solution**: Add your GitHub App installation ID:

```yaml
repository:
  remote_url: "https://github.com/myorg/myrepo.git"
  git_clone_strategy: "github_app"
  github_installation_id: 12345678  # Add this
```

See "How to Find GitHub Installation ID" section above.

---

#### ❌ "git_clone_strategy 'deploy_token' requires 'gitlab_project_id'"

**Problem**: You specified `deploy_token` but didn't provide the project ID.

**Solution**: Add your GitLab project ID:

```yaml
repository:
  remote_url: "https://gitlab.com/mygroup/myproject.git"
  git_clone_strategy: "deploy_token"
  gitlab_project_id: 9876543  # Add this
```

See "How to Find GitLab Project ID" section above.

---

#### ⚠️ "github_installation_id' is set but remote_url is not a GitHub URL"

**Problem**: You provided `github_installation_id` but your URL is for a different provider.

**Solution**: Either:
- Change URL to GitHub
- Remove the GitHub-specific field if using a different provider

```yaml
# ❌ Wrong - URL is GitLab, but GitHub field set
repository:
  remote_url: "https://gitlab.com/mygroup/myproject.git"
  github_installation_id: 12345678

# ✅ Correct - Remove GitHub field
repository:
  remote_url: "https://gitlab.com/mygroup/myproject.git"
  gitlab_project_id: 9876543
```

---

#### Azure DevOps: "azure_active_directory_project_id' is required but missing"

**Problem**: Azure DevOps strategy needs both project and repository IDs.

**Solution**: Provide both UUIDs:

```yaml
repository:
  remote_url: "https://dev.azure.com/myorg/myproject/_git/myrepo"
  azure_active_directory_project_id: "550e8400-e29b-41d4-a716-446655440000"
  azure_active_directory_repository_id: "550e8400-e29b-41d4-a716-446655440001"
```

---

## Advanced Options

### Private Link Endpoint (Enterprise)

For private connectivity in enterprises:

```yaml
repository:
  remote_url: "https://github.com/myorg/myrepo.git"
  github_installation_id: 12345678
  private_link_endpoint_id: "vpce-1234567890abcdef0"  # From AWS/Azure
```

---

### Custom Pull Request URL Template

Override the default PR URL format:

```yaml
repository:
  remote_url: "https://github.com/myorg/myrepo.git"
  pull_request_url_template: "https://github.com/myorg/myrepo/pull/{pull_request_id}"
```

---

### Repository Activity Control

Temporarily disable repository without deleting:

```yaml
repository:
  remote_url: "https://github.com/myorg/myrepo.git"
  github_installation_id: 12345678
  is_active: false  # Disables the repository
```

---

## URL Format Reference

### GitHub
- HTTPS: `https://github.com/OWNER/REPO.git`
- SSH: `git@github.com:OWNER/REPO.git`

### GitLab
- HTTPS: `https://gitlab.com/GROUP/PROJECT.git`
- SSH: `git@gitlab.com:GROUP/PROJECT.git`

### Azure DevOps
- HTTPS: `https://dev.azure.com/ORGNAME/PROJECT/_git/REPO`
- SSH: `git@ssh.dev.azure.com:v3/ORGNAME/PROJECT/REPO`

### Bitbucket
- HTTPS: `https://bitbucket.org/TEAM/REPO.git`
- SSH: `git@bitbucket.org:TEAM/REPO.git`

---

## Migration Guide

Switching from one provider to another? Here's the process:

### Moving from GitHub to GitLab

1. **Update remote_url**:
   ```yaml
   # Before
   remote_url: "https://github.com/myorg/myrepo.git"
   github_installation_id: 12345678
   
   # After
   remote_url: "https://gitlab.com/mygroup/myproject.git"
   gitlab_project_id: 9876543
   ```

2. **Terraform will**:
   - Remove the old GitHub-based repository
   - Create new GitLab-based repository
   - Jobs will continue working with the new repository

3. **Post-migration**: Verify:
   - Jobs are running against new repository
   - Webhooks are properly configured in GitLab
   - Deploy keys are set up if using SSH

---

## Troubleshooting

### Connection Test

To verify your repository is accessible:

1. Go to dbt Cloud Project Settings
2. Find your repository
3. Look for connection status indicator
4. If red, check:
   - URL is correct
   - Deploy key/token is valid
   - Repository is accessible from dbt Cloud IP range
   - Webhooks aren't being blocked by firewall

### Webhook Issues

If PRs aren't triggering runs:

1. Check your Git provider's webhook settings
2. Verify IP whitelist (if applicable)
3. For Azure DevOps with webhook failures, try:
   ```yaml
   azure_bypass_webhook_registration_failure: true
   ```

### SSH Key Issues

If getting permission denied:

1. Verify public key is added to repository as deploy key
2. Ensure private key is in dbt Cloud credential
3. Check key permissions (should not be world-readable)
4. Try: `ssh -T git@github.com` to test connection

### Debugging

Enable verbose logging in dbt Cloud:

1. Run a job with `--debug` flag
2. Check logs for repository connection errors
3. Verify remote_url is correct by running: `git ls-remote YOUR_URL`

---

## Best Practices

1. **Use Native Integrations When Possible**: GitHub App, Deploy Token, Azure AD for better security
2. **Rotate Credentials**: Regularly rotate access tokens and keys
3. **Minimal Permissions**: Grant only necessary scopes to deploy keys/tokens
4. **Environment-Specific Repositories**: Use different repositories for dev/staging/prod
5. **Test After Changes**: Always run a test job after changing repository settings
6. **Documentation**: Document which repository each environment uses
7. **Monitoring**: Set up alerts for connection failures

---

## Getting Help

If you encounter issues:

1. Check the error message - it includes detected provider and auto-selected strategy
2. Review the "Common Errors & Solutions" section above
3. Verify IDs using the guides in this document
4. Check repository settings in your Git provider
5. Open an issue on GitHub with your error message (sanitize any tokens/IDs)

For security questions about credentials, see the main README's Security section.
