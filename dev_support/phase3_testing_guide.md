# Phase 3 Testing Guide

**Date:** 2025-01-27  
**Purpose:** Comprehensive testing guide for Phase 3 Terraform v2 module implementation

---

## Quick Start Testing

### Prerequisites

1. **Terraform**: v1.5+ (we have 1.14.1 installed via tfenv)
2. **Go**: 1.21+ (we have 1.25.5 installed)
3. **Python**: 3.9+ (we have 3.9.6 with virtualenv)
4. **dbt Cloud Provider**: Will be downloaded automatically on `terraform init`

### Test Levels

1. **Quick Validation** (No credentials needed) - ~2 minutes
2. **Terratest Suite** (No credentials needed) - ~5 minutes
3. **Manual Terraform Plan** (No credentials needed) - ~1 minute per fixture
4. **End-to-End** (Requires credentials) - ~10+ minutes

---

## Level 1: Quick Validation Tests

### Test 1: Terraform Format & Validate

```bash
# Format all Terraform files
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml
terraform fmt -recursive

# Validate root module syntax
terraform init
terraform validate

# Validate v2 module syntax
cd modules/projects_v2
terraform init
terraform validate
```

**Expected:** No errors, all files formatted correctly

### Test 2: Schema Detection Logic

```bash
# Test v1 YAML detection
cd test/fixtures/basic
terraform init
terraform plan -var="dbt_account_id=999999" -var="dbt_token=test" -var="dbt_host_url=https://cloud.getdbt.com"

# Test v2 YAML detection  
cd ../v2_basic
terraform init
terraform plan -var="dbt_account_id=999999" -var="dbt_token=test" -var="dbt_host_url=https://cloud.getdbt.com"
```

**Expected:** 
- v1: Uses `module.project[0]`, `module.environments[0]`, etc.
- v2: Uses `module.projects_v2[0]`, `module.dbt_cloud.module.projects_v2`

---

## Level 2: Terratest Suite

### Setup

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/test

# Install Go test dependencies (if not already done)
go mod download
go mod tidy
```

### Run All Tests

```bash
# Run all tests (including v2 tests)
go test -v ./...

# Run only v2 tests
go test -v -run TestV2 ./...

# Run specific test
go test -v -run TestV2BasicConfiguration ./...
```

### Expected Test Results

**TestV2BasicConfiguration**
- ✅ Terraform init succeeds
- ✅ Terraform plan succeeds
- ✅ Plan output contains `module.projects_v2`
- ✅ No errors in plan output

**TestV2CompleteConfiguration**
- ✅ Terraform init succeeds
- ✅ Terraform plan succeeds
- ✅ Plan output contains multi-project resources
- ✅ Plan output contains global resources (connections, tokens, groups)

**TestV2YAMLParsing**
- ✅ YAML file contains `version: 2`
- ✅ YAML file contains `account:`, `globals:`, `projects:`

**TestV2Outputs**
- ✅ Outputs include `v2_project_ids`, `v2_environment_ids`, `v2_job_ids`

### Troubleshooting Terratest

If tests fail:
1. Check Go version: `go version` (need 1.21+)
2. Check Terraform is in PATH: `which terraform`
3. Check test fixtures exist: `ls test/fixtures/v2_basic/`
4. Run with verbose output: `go test -v -run TestV2BasicConfiguration ./...`

---

## Level 3: Manual Terraform Plan Tests

### Test v2_basic Fixture

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/test/fixtures/v2_basic

# Create terraform.tfvars (if missing)
cat > terraform.tfvars <<EOF
dbt_account_id = 999999
dbt_token      = "test-token-not-real"
dbt_host_url   = "https://cloud.getdbt.com"
target_name    = "dev"
token_map = {
  dev_token = "test-token-dev"
}
EOF

# Initialize
terraform init

# Plan (will fail on API calls, but validates syntax)
terraform plan
```

**What to Check:**
- ✅ No syntax errors
- ✅ Module loads correctly
- ✅ Schema version detected as v2
- ✅ Resources planned: `dbtcloud_global_connection`, `dbtcloud_project`, `dbtcloud_repository`, `dbtcloud_environment`, `dbtcloud_job`

### Test v2_complete Fixture

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/test/fixtures/v2_complete

# Create terraform.tfvars (if missing)
cat > terraform.tfvars <<EOF
dbt_account_id = 999999
dbt_token      = "test-token-not-real"
dbt_host_url   = "https://cloud.getdbt.com"
target_name    = "dev"
token_map = {
  prod_token = "test-token-prod"
  dev_token  = "test-token-dev"
}
EOF

# Initialize and plan
terraform init
terraform plan
```

**What to Check:**
- ✅ Multiple projects planned
- ✅ Global resources planned (connections, service tokens, groups)
- ✅ Multiple environments per project
- ✅ Multiple jobs per environment
- ✅ Environment variables planned

---

## Level 4: End-to-End Testing (Requires Credentials)

### Prerequisites

1. **dbt Cloud Account**: Test account with API access
2. **API Token**: Account Admin or Owner token
3. **`.env` file**: Configured with credentials

### Step 1: Configure Environment

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml

# Create .env file (if not exists)
cat > .env <<EOF
DBT_SOURCE_HOST=https://cloud.getdbt.com
DBT_SOURCE_ACCOUNT_ID=<your_account_id>
DBT_SOURCE_API_TOKEN=<your_api_token>
EOF

# Load environment
source .venv/bin/activate
set -a
source .env
set +a
```

### Step 2: Run Importer Fetch

```bash
# Fetch account data
python -m importer fetch --output dev_support/samples/test_account.json

# Verify JSON export created
ls -lh dev_support/samples/account_*_run_*__json__*.json | tail -1
```

### Step 3: Run Importer Normalize

```bash
# Get the latest JSON export
LATEST_JSON=$(ls -t dev_support/samples/account_*_run_*__json__*.json | head -1)

# Normalize to v2 YAML
python -m importer normalize "$LATEST_JSON"

# Verify YAML created
ls -lh dev_support/samples/normalized/account_*_norm_*__yaml__*.yml | tail -1
```

### Step 4: Test Terraform with Generated YAML

```bash
# Get the latest YAML
LATEST_YAML=$(ls -t dev_support/samples/normalized/account_*_norm_*__yaml__*.yml | head -1)

# Create test Terraform workspace
mkdir -p test/end_to_end
cd test/end_to_end

# Create main.tf
cat > main.tf <<EOF
terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 0.3"
    }
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_token
  host_url   = var.dbt_host_url
}

module "dbt_cloud" {
  source = "../../"

  dbt_account_id = var.dbt_account_id
  dbt_token      = var.dbt_token
  dbt_host_url   = var.dbt_host_url
  yaml_file      = "$LATEST_YAML"
  token_map      = var.token_map
}
EOF

# Create variables.tf
cat > variables.tf <<EOF
variable "dbt_account_id" {
  type = number
}

variable "dbt_token" {
  type      = string
  sensitive = true
}

variable "dbt_host_url" {
  type = string
}

variable "token_map" {
  type        = map(string)
  default     = {}
  sensitive   = true
}
EOF

# Create terraform.tfvars (use your target account)
cat > terraform.tfvars <<EOF
dbt_account_id = <target_account_id>
dbt_token      = "<target_api_token>"
dbt_host_url   = "https://cloud.getdbt.com"
token_map = {
  # Add your warehouse tokens here
  # "token_name" = "token_value"
}
EOF

# Initialize and plan
terraform init
terraform plan

# If plan looks good, you can apply (CAREFUL - creates real resources!)
# terraform apply
```

**What to Check:**
- ✅ Terraform detects v2 schema
- ✅ Plan shows resources to be created
- ✅ No errors in plan
- ✅ Resource counts match expectations
- ⚠️ Review plan carefully before applying!

---

## Test Checklist

### Basic Functionality
- [ ] Terraform format passes (`terraform fmt -recursive`)
- [ ] Terraform validate passes (`terraform validate`)
- [ ] v2_basic fixture plans successfully
- [ ] v2_complete fixture plans successfully
- [ ] Schema detection works (v1 vs v2)

### Terratest Suite
- [ ] `TestV2BasicConfiguration` passes
- [ ] `TestV2CompleteConfiguration` passes
- [ ] `TestV2YAMLParsing` passes
- [ ] `TestV2Outputs` passes

### Module Components
- [ ] Global resources created (connections, tokens, groups)
- [ ] Projects created correctly
- [ ] Repositories linked to projects
- [ ] Environments created with connection resolution
- [ ] Jobs created with environment references
- [ ] Environment variables created
- [ ] LOOKUP placeholders resolved (if any)

### Outputs
- [ ] `v2_project_ids` output exists
- [ ] `v2_environment_ids` output exists
- [ ] `v2_job_ids` output exists
- [ ] `v2_connection_ids` output exists
- [ ] Outputs return correct structure

---

## Common Issues & Solutions

### Issue: "Module not found"
**Solution:** Run `terraform init` in the test fixture directory

### Issue: "Provider version constraint"
**Solution:** Check `test/fixtures/v2_basic/main.tf` uses `~> 1.3` or `~> 0.3`

### Issue: "Variable not set"
**Solution:** Create `terraform.tfvars` file with required variables

### Issue: "LOOKUP placeholder not resolved"
**Solution:** This is expected in plan - resources must exist in target account or be created manually first

### Issue: "Connection provider config missing"
**Solution:** This is expected - provider config blocks must be manually added to YAML (API limitation)

---

## Next Steps After Testing

1. **If all tests pass:**
   - ✅ Phase 3 implementation is validated
   - ✅ Ready for end-to-end testing with real accounts
   - ✅ Consider documenting any edge cases found

2. **If tests fail:**
   - Review error messages
   - Check Terraform version compatibility
   - Verify test fixtures are correct
   - Check module file paths and references

3. **For production use:**
   - Test with a non-production account first
   - Review generated YAML carefully
   - Verify LOOKUP placeholders are resolved
   - Test incremental updates (modify YAML, re-apply)

---

## Quick Test Commands Summary

```bash
# Format and validate
terraform fmt -recursive
terraform validate

# Run Terratest suite
cd test && go test -v -run TestV2 ./...

# Manual plan test
cd test/fixtures/v2_basic
terraform init && terraform plan -var="dbt_account_id=999999" -var="dbt_token=test"

# End-to-end (requires credentials)
python -m importer fetch
python -m importer normalize <json_file>
terraform plan -var-file=terraform.tfvars
```

---

## Test Results Template

After running tests, document results:

```
Date: 2025-01-27
Tester: [Your Name]
Terraform Version: 1.14.1
Go Version: 1.25.5

Quick Validation: ✅ Pass / ❌ Fail
Terratest Suite: ✅ Pass / ❌ Fail
Manual Plan Tests: ✅ Pass / ❌ Fail
End-to-End: ✅ Pass / ❌ Fail / ⏭️ Skipped

Issues Found:
- [List any issues]

Notes:
- [Any observations or recommendations]
```

