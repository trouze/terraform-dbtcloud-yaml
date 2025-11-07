# Troubleshooting

Common issues and their solutions.

## Terraform Errors

### "No value for required variable"

**Error Message:**
```
Error: No value for required variable
│ on variables.tf line 1:
│   1: variable "dbt_account_id" {
│ 
│ The root module input variable "dbt_account_id" is not set
```

**Causes:**
- Environment variables not loaded
- Incorrect variable name
- Missing `.env` file

**Solutions:**

1. **Load environment variables:**
```bash
source .env
echo $TF_VAR_dbt_account_id  # Verify it's set
```

2. **Check variable names match:**
```bash
# In .env, must be TF_VAR_<name>
export TF_VAR_dbt_account_id=12345

# In variables.tf
variable "dbt_account_id" {  # Name matches after TF_VAR_
  type = number
}
```

3. **Pass directly:**
```bash
terraform plan -var="dbt_account_id=12345"
```

---

### "Invalid JSON for token_map"

**Error Message:**
```
Error: Invalid value for input variable
│ The given value is not suitable for var.token_map
```

**Cause:** `token_map` isn't valid JSON.

**Solutions:**

```bash
# ❌ Multi-line won't work in .env
export TF_VAR_token_map='{
  "key": "value"
}'

# ✅ Single line, use single quotes
export TF_VAR_token_map='{"key":"value","key2":"value2"}'

# ✅ Or use terraform.tfvars (HCL syntax)
token_map = {
  key  = "value"
  key2 = "value2"
}
```

---

### "State Lock Timeout"

**Error Message:**
```
Error: Error acquiring the state lock
│ Lock Info:
│   ID:        abc123...
│   Operation: OperationTypePlan
│   Who:       user@hostname
```

**Causes:**
- Previous Terraform run didn't finish
- Crashed Terraform process
- Concurrent runs

**Solutions:**

1. **Wait** for the other operation to complete

2. **Verify no other runs are active:**
```bash
# Check for terraform processes
ps aux | grep terraform
```

3. **Force unlock (use carefully):**
```bash
terraform force-unlock abc123
```

!!! danger "Force Unlock Warning"
    Only force unlock if you're CERTAIN no other process is running. This can corrupt state.

---

### "Module not found"

**Error Message:**
```
Error: Module not installed
│ This configuration requires module "dbt_cloud"
```

**Cause:** Terraform modules not downloaded.

**Solution:**
```bash
terraform init
# Or if already initialized
terraform get
```

---

## dbt Cloud API Errors

### "401 Unauthorized"

**Error Message:**
```
Error: dbt Cloud API error: 401 Unauthorized
```

**Causes:**
- Invalid API token
- Expired token
- Wrong dbt Cloud account

**Solutions:**

1. **Regenerate token:**
   - Go to [dbt Cloud Profile](https://cloud.getdbt.com/settings/profile)
   - Create new API token
   - Update `.env` or secrets

2. **Verify account ID:**
```bash
# Check URL: https://cloud.getdbt.com/accounts/{ACCOUNT_ID}/
echo $TF_VAR_dbt_account_id
```

3. **Check token format:**
```bash
# Should start with 'dbtc_'
echo $TF_VAR_dbt_api_token
```

---

### "403 Forbidden"

**Error Message:**
```
Error: dbt Cloud API error: 403 Forbidden
```

**Cause:** Token doesn't have required permissions.

**Solutions:**

1. **Use account-level token** (not project-level)
2. **Check token permissions** in dbt Cloud
3. **Create service account token** with admin permissions

---

### "404 Not Found - Connection ID"

**Error Message:**
```
Error: Cannot find connection with ID: 1234
```

**Cause:** Connection ID doesn't exist or is in different account.

**Solutions:**

1. **Find correct connection ID:**
   - In dbt Cloud: Admin > Connections
   - Click connection, check URL: `/connections/{CONNECTION_ID}`

2. **Update YAML:**
```yaml
environments:
  - name: "Production"
    connection_id: 1234  # Use the correct ID
```

---

## YAML Configuration Errors

### "YAML Parse Error"

**Error Message:**
```
Error: failed to parse YAML
│ yaml: line 10: did not find expected key
```

**Causes:**
- Invalid YAML syntax
- Incorrect indentation
- Missing quotes

**Solutions:**

1. **Validate YAML syntax:**
```bash
# Use yamllint
yamllint dbt-config.yml

# Or online validator
# https://www.yamllint.com/
```

2. **Check indentation (2 spaces, no tabs):**
```yaml
# ❌ Wrong
project:
    name: "test"  # 4 spaces

# ✅ Correct
project:
  name: "test"    # 2 spaces
```

3. **Quote special characters:**
```yaml
# ❌ Wrong
name: My Project: Production

# ✅ Correct
name: "My Project: Production"
```

---

### "Missing Required Field"

**Error Message:**
```
Error: Missing required field: connection_id
```

**Cause:** Required field not provided in YAML.

**Solutions:**

Check the [YAML Schema](../configuration/yaml-schema.md) for required fields:

```yaml
environments:
  - name: "Production"        # Required
    type: "deployment"        # Required
    connection_id: 1001       # Required ← Add this!
    credential:               # Required
      token_name: "token"     # Required
      schema: "analytics"     # Required
```

---

### "Invalid Enum Value"

**Error Message:**
```
Error: Invalid value for type: must be 'development' or 'deployment'
```

**Cause:** Used invalid value for a restricted field.

**Solutions:**

```yaml
# ❌ Wrong
type: "prod"  # Not a valid option

# ✅ Correct
type: "deployment"  # Must be 'development' or 'deployment'
```

---

## Git Integration Errors

### "GitHub Installation ID Not Found"

**Error Message:**
```
Error: GitHub App installation not found
```

**Causes:**
- Invalid installation ID
- GitHub App not installed on repository
- Using wrong git_clone_strategy

**Solutions:**

1. **Find installation ID:**
   - Go to GitHub Settings > Applications > dbt Cloud
   - Check URL: `/settings/installations/{INSTALLATION_ID}`

2. **Install GitHub App:**
   - In dbt Cloud: Admin > Integrations > GitHub
   - Click "Connect GitHub App"
   - Authorize for your repositories

3. **Update YAML:**
```yaml
repository:
  remote_url: "https://github.com/org/repo.git"
  git_clone_strategy: "github_app"
  github_installation_id: 12345678  # Your installation ID
```

---

### "GitLab Project ID Not Found"

**Error Message:**
```
Error: GitLab project not found
```

**Cause:** Invalid GitLab project ID.

**Solutions:**

1. **Find project ID:**
   - In GitLab: Project > Settings > General
   - Look for "Project ID" (numeric value)

2. **Update YAML:**
```yaml
repository:
  remote_url: "https://gitlab.com/group/repo.git"
  git_clone_strategy: "deploy_token"
  gitlab_project_id: 9876543  # Numeric ID, not name
```

---

## Credential Errors

### "Token Not Found in token_map"

**Error Message:**
```
Error: Token key 'prod_databricks_token' not found in token_map
```

**Cause:** YAML references a token key that doesn't exist in `token_map`.

**Solutions:**

1. **Check YAML credential name:**
```yaml
credential:
  token_name: "prod_databricks_token"  # This key...
```

2. **Must match token_map:**
```bash
export TF_VAR_token_map='{
  "prod_databricks_token": "dapi_abc123"
  # ↑ Must match exactly
}'
```

3. **Or add to terraform.tfvars:**
```hcl
token_map = {
  prod_databricks_token = "dapi_abc123"
}
```

---

## CI/CD Issues

### "Terraform Init Failed"

**Problem:** CI/CD can't initialize Terraform.

**Solutions:**

1. **Check Terraform version:**
```yaml
- name: Setup Terraform
  uses: hashicorp/setup-terraform@v2
  with:
    terraform_version: 1.6.0  # Pin specific version
```

2. **Verify backend access:**
```yaml
# Ensure CI has permissions to state bucket
- name: Configure AWS Credentials
  uses: aws-actions/configure-aws-credentials@v2
  with:
    role-to-assume: arn:aws:iam::123456789012:role/terraform
```

---

### "Secrets Not Available"

**Problem:** Environment variables are undefined in CI/CD.

**Solutions:**

1. **Verify secrets are defined:**
   - GitHub: Settings > Secrets and variables > Actions
   - GitLab: Settings > CI/CD > Variables
   - Azure DevOps: Pipelines > Library

2. **Check secret names match:**
```yaml
env:
  TF_VAR_dbt_account_id: ${{ secrets.DBT_ACCOUNT_ID }}
  # Secret name must match exactly ↑
```

3. **Ensure workflow has access:**
```yaml
# For protected branches
environment:
  name: production  # Must have access to this environment's secrets
```

---

## Performance Issues

### "Terraform Plan Takes Too Long"

**Problem:** `terraform plan` runs for minutes.

**Solutions:**

1. **Use targeted plans:**
```bash
terraform plan -target=module.dbt_cloud.module.jobs
```

2. **Enable parallelism:**
```bash
terraform plan -parallelism=10
```

3. **Upgrade Terraform:**
```bash
# Newer versions have performance improvements
terraform version
brew upgrade terraform  # or similar
```

---

### "State Refresh Slow"

**Problem:** State refresh takes a long time.

**Solutions:**

1. **Skip refresh when safe:**
```bash
terraform plan -refresh=false
```

2. **Use remote state caching:**
```hcl
terraform {
  backend "s3" {
    # Enable caching
    skip_metadata_api_check = true
  }
}
```

---

## Debug Mode

Enable detailed logging:

```bash
# Set debug level
export TF_LOG=DEBUG
export TF_LOG_PATH=./terraform-debug.log

# Run terraform
terraform plan

# Review logs
cat terraform-debug.log
```

---

## Getting Help

Still stuck? Here's how to get support:

### 1. Check Existing Issues

Search [GitHub Issues](https://github.com/trouze/terraform-dbtcloud-yaml/issues) for similar problems.

### 2. Create Detailed Issue

Include:
- **Error message** (full output)
- **Terraform version**: `terraform version`
- **Module version**: Check your `source` URL
- **Minimal config** that reproduces the issue
- **What you've tried** already

### Community Support

- [GitHub Discussions](https://github.com/trouze/terraform-dbtcloud-yaml/discussions)
- [dbt Community Slack](https://www.getdbt.com/community/)

---

## Common Mistakes

### ❌ Hardcoding Credentials

```hcl
# DON'T DO THIS!
variable "dbt_token" {
  default = "dbtc_xxxxx"
}
```

### ❌ Committing .env File

```bash
# Make sure it's in .gitignore
echo ".env" >> .gitignore
```

### ❌ Using Root Tokens

```bash
# Use service accounts, not personal tokens
# Generate at: dbt Cloud > Admin > Service Tokens
```

### ❌ Not Pinning Versions

```hcl
# ❌ Bad
module "dbt" {
  source = "git::https://github.com/..."
}

# ✅ Good
module "dbt" {
  source = "git::https://github.com/...?ref=v1.0.0"
}
```

---

## Prevention Checklist

Before deployment:

- [ ] Run `terraform fmt -check`
- [ ] Run `terraform validate`
- [ ] Review `terraform plan` output
- [ ] Test in non-production first
- [ ] Have rollback plan ready
- [ ] Monitor logs during apply
- [ ] Verify resources in dbt Cloud UI

---

## Need More Help?

<div class="grid cards" markdown>

-   :material-book-open-variant:{ .lg .middle } __Documentation__

    ---

    Review the full documentation

    [:octicons-arrow-right-24: Documentation Home](../index.md)

-   :material-github:{ .lg .middle } __GitHub Issues__

    ---

    Report bugs or request features

    [:octicons-arrow-right-24: Open Issue](https://github.com/trouze/terraform-dbtcloud-yaml/issues)

-   :material-forum:{ .lg .middle } __Discussions__

    ---

    Ask questions and share ideas

    [:octicons-arrow-right-24: Join Discussion](https://github.com/trouze/terraform-dbtcloud-yaml/discussions)

</div>
