# Phase 5: End-to-End Testing Guide

**Version:** 2.0  
**Date:** 2026-01-16  
**Importer Version:** 0.11.1  
**Status:** Ready for Execution

---

## Overview

This guide provides a comprehensive, step-by-step procedure for executing Phase 5 end-to-end testing of the dbt Cloud Account Migration Importer. The goal is to validate the complete workflow from source account fetch through Terraform apply in a target account.

**Testing Workflow:**
```
Source Account → Fetch (JSON) → Normalize (YAML) → Terraform (validate/plan/apply) → Target Account
```

---

## Prerequisites

Before starting, ensure you have completed the [End-to-End Testing Readiness Checklist](importer_implementation_status.md#end-to-end-testing-readiness-checklist) in the implementation status document.

**Quick Checklist:**
- [ ] Source account credentials configured
- [ ] Target account credentials configured (can be same as source)
- [ ] Python 3.9+ with dependencies installed
- [ ] Terraform 1.5+ installed (recommend 1.14.1 via tfenv)
- [ ] Test account has representative data (2-5 projects, connections, jobs, etc.)
- [ ] Clean workspace (no existing exports)

---

## Test Environment Setup

### 1. Create Test Directory

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml
mkdir -p test/e2e_test
cd test/e2e_test
```

### 2. Configure Environment Variables

Create a `.env` file in the test directory:

```bash
cat > .env << 'EOF'
# Source Account (for fetch)
DBT_SOURCE_ACCOUNT_ID=12345
DBT_SOURCE_API_TOKEN=your_source_token_here
DBT_SOURCE_HOST=https://cloud.getdbt.com

# Target Account (for Terraform apply)
# Can be same as source for testing
DBT_TARGET_ACCOUNT_ID=12345
DBT_TARGET_API_TOKEN=your_target_token_here
DBT_TARGET_HOST_URL=https://cloud.getdbt.com

# Optional: Scope filtering
# DBT_SCOPE=all_projects
# DBT_PROJECT_IDS=1001,1002,1003

# Optional: Report line item start
# DBT_REPORT_LINE_ITEM_START=1001
EOF
```

**Security Note:** Add `.env` to `.gitignore` to prevent credential exposure.

### 3. Verify Connectivity

Test source account API access:

```bash
curl -H "Authorization: Token $DBT_SOURCE_API_TOKEN" \
  https://cloud.getdbt.com/api/v2/accounts/$DBT_SOURCE_ACCOUNT_ID/ | jq .
```

Expected: JSON response with account details.

---

## Phase 1: Fetch Source Account

### Step 1.1: Run Fetch Command

Choose one of the following methods:

**Option A: Interactive Mode (Recommended for first-time)**
```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml
python -m importer fetch --interactive
```

Follow prompts:
1. Confirm/enter credentials
2. Select scope (all_projects recommended for full test)
3. Confirm execution

**Option B: Non-Interactive Mode**
```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml
python -m importer fetch
```

### Step 1.2: Verify Fetch Results

Check for successful completion:

```bash
ls -lh importer_export/
```

Expected files:
- `account_{ACCOUNT_ID}_run_{RUN}__{TIMESTAMP}.json` (main export)
- `account_{ACCOUNT_ID}_run_{RUN}__summary_report.md` (human-readable summary)
- `account_{ACCOUNT_ID}_run_{RUN}__report_items__{TIMESTAMP}.json` (line items)

### Step 1.3: Inspect Export

Open the summary report:

```bash
cat importer_export/account_*_summary_report.md | less
```

Verify:
- [ ] Account name matches source
- [ ] Project count matches expected
- [ ] Connection count matches expected
- [ ] Global resources listed (if applicable)

Open the JSON export and spot-check:

```bash
jq '.projects | length' importer_export/account_*_run_*.json
jq '.connections | length' importer_export/account_*_run_*.json
jq '.projects[0] | keys' importer_export/account_*_run_*.json
```

### Step 1.4: Document Fetch Results

Create a test log:

```bash
cat > test/e2e_test/test_log.md << EOF
# End-to-End Test Log

**Test Date:** $(date)
**Importer Version:** $(python -m importer --version)
**Source Account ID:** $DBT_SOURCE_ACCOUNT_ID

## Phase 1: Fetch

- **Start Time:** $(date)
- **Export File:** $(ls importer_export/account_*_run_*.json)
- **Projects Fetched:** $(jq '.projects | length' importer_export/account_*_run_*.json)
- **Connections Fetched:** $(jq '.connections | length' importer_export/account_*_run_*.json)
- **Status:** ✅ Success / ❌ Failed

**Notes:**
- (Add any observations or issues)

EOF
```

---

## Phase 2: Normalize to YAML

### Step 2.1: Run Normalize Command

Choose one of the following methods:

**Option A: Interactive Mode (Recommended)**
```bash
python -m importer normalize --interactive
```

Follow prompts:
1. Select export file from recent files list
2. Confirm/adjust scope and filters
3. Confirm execution

**Option B: Non-Interactive Mode**
```bash
EXPORT_FILE=$(ls -t importer_export/account_*_run_*.json | head -1)
python -m importer normalize "$EXPORT_FILE"
```

### Step 2.2: Verify Normalize Results

Check for generated files:

```bash
ls -lh importer_export/normalized_*
```

Expected files:
- `normalized_{TIMESTAMP}.yml` (main YAML output)
- `lookups_{TIMESTAMP}.json` (LOOKUP placeholder manifest)
- `exclusions_{TIMESTAMP}.md` (exclusions report, if any)
- `diff_{TIMESTAMP}.json` (diff for regression testing)
- `normalization_{TIMESTAMP}.log` (DEBUG logs)

### Step 2.3: Inspect YAML

Open the generated YAML:

```bash
YAML_FILE=$(ls -t importer_export/normalized_*.yml | head -1)
less "$YAML_FILE"
```

Verify:
- [ ] `version: 2` at top
- [ ] `globals:` section present
- [ ] `connections:` under globals (with keys)
- [ ] `projects:` section present
- [ ] LOOKUP placeholders present (e.g., `LOOKUP[connection:...]`)
- [ ] No sensitive data (secrets redacted)

Check YAML syntax:

```bash
python -c "import yaml; yaml.safe_load(open('$YAML_FILE'))" && echo "✅ YAML syntax valid"
```

### Step 2.4: Review Exclusions

If exclusions report exists:

```bash
EXCLUSIONS=$(ls -t importer_export/exclusions_*.md 2>/dev/null | head -1)
if [ -f "$EXCLUSIONS" ]; then
  cat "$EXCLUSIONS"
fi
```

Document any excluded resources and reasons.

### Step 2.5: Update Test Log

```bash
cat >> test/e2e_test/test_log.md << EOF

## Phase 2: Normalize

- **Start Time:** $(date)
- **YAML File:** $YAML_FILE
- **Lookups Count:** $(jq '. | length' importer_export/lookups_*.json 2>/dev/null || echo "N/A")
- **Status:** ✅ Success / ❌ Failed

**YAML Validation:**
- Version: $(grep '^version:' "$YAML_FILE")
- Globals Section: $(grep -c 'globals:' "$YAML_FILE" > 0 && echo "✅ Present" || echo "❌ Missing")
- Projects Section: $(grep -c 'projects:' "$YAML_FILE" > 0 && echo "✅ Present" || echo "❌ Missing")

**Notes:**
- (Add any observations or issues)

EOF
```

---

## Phase 3: Provider Configuration (Interactive)

### Step 3.0: Configure Connection Provider Configs

**⚠️ IMPORTANT:** Connection provider configurations are not exported by the dbt Cloud API for security reasons. This is a required manual step.

The E2E test script will automatically pause here and present you with options.

#### Interactive Options

When the script reaches this step, you'll see:

```
[INFO] === Provider Configuration Check ===
[WARNING] Connections missing provider_config (API security limitation)

Connections without provider_config:
  • Databricks Production
    Key: databricks_prod
    Type: databricks

Options:
  1) Add dummy/placeholder provider_config for testing (recommended for validation)
  2) Open YAML in editor for manual configuration
  3) Skip and continue (terraform validate will fail)
  4) Abort test

Select option [1-4] (default: 1):
```

#### Option 1: Dummy Config (Recommended for Testing)

Automatically adds placeholder provider_config based on connection type:

**Databricks:**
```yaml
provider_config:
  host: "dummy-workspace.cloud.databricks.com"
  http_path: "/sql/1.0/warehouses/dummy123"
  catalog: "main"
```

**Snowflake:**
```yaml
provider_config:
  account: "dummy_account"
  database: "dummy_database"
  warehouse: "dummy_warehouse"
  role: "dummy_role"
```

**BigQuery:**
```yaml
provider_config:
  project_id: "dummy-project-id"
  dataset: "dummy_dataset"
  location: "US"
```

**Use Case:** Quick validation testing - terraform validate and plan will work, but apply will fail with invalid credentials.

#### Option 2: Manual Editor

Opens the YAML file in your default editor (respects `$EDITOR` environment variable, defaults to `nano`).

**Steps:**
1. Script pauses and displays example provider_config format
2. Press Enter to open editor
3. Navigate to `globals.connections` section
4. Add `provider_config` to each connection
5. Save and exit editor
6. Script verifies provider_config exists and continues

**Use Case:** Real migration testing - add actual connection details for end-to-end apply testing.

#### Option 3: Skip

Continues without adding provider_config.

**Expected:** Terraform validation will fail with "provider_config is required" errors.

**Use Case:** Testing error handling or if you've already added configs manually.

#### Option 4: Abort

Exits the test cleanly.

**Use Case:** Need to prepare connection details before continuing.

### Step 3.1: Copy YAML to Test Fixture

**Note:** This step is now automated by the script. The YAML is copied after normalization.

---

## Phase 4: Terraform Validation

```bash
cp "$YAML_FILE" test/e2e_test/dbt-cloud-config.yml
```

### Step 3.2: Create Terraform Configuration

Create `test/e2e_test/main.tf`:

**Note:** This step is now automated - the file is pre-created in the repository. You only need to adjust `token_map` if using real credentials.

```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.3"
    }
  }
}

provider "dbtcloud" {
  # Credentials from environment:
  # DBT_TARGET_ACCOUNT_ID (mapped to TF_VAR_dbt_account_id)
  # DBT_TARGET_API_TOKEN (mapped to TF_VAR_dbt_token)
  # DBT_TARGET_HOST_URL (mapped to TF_VAR_dbt_host_url)
}

module "dbt_cloud" {
  source = "../.."

  yaml_file   = "${path.module}/dbt-cloud-config.yml"
  target_name = "e2e_test"

  # Provide credential secrets via token_map
  token_map = {
    # Example: "databricks_token_key" = "your_databricks_token_here"
    # Add actual tokens for your connections
  }
}

output "project_ids" {
  description = "Created project IDs"
  value       = module.dbt_cloud.v2_project_ids
}

output "environment_ids" {
  description = "Created environment IDs"
  value       = module.dbt_cloud.v2_environment_ids
}

output "job_ids" {
  description = "Created job IDs"
  value       = module.dbt_cloud.v2_job_ids
}

output "connection_ids" {
  description = "Created connection IDs"
  value       = module.dbt_cloud.v2_connection_ids
}
```

**Note:** Adjust `token_map` based on your connection types. This is required because credential secrets are not exported by the API.

### Step 3.3: Automated Testing Flow

**Note:** When using the automated test script (`./test/run_e2e_test.sh`), Steps 3.3-3.5 (manual provider config addition, terraform init, and validate) are handled automatically with the interactive provider configuration step described in Phase 3 above. The script will:

1. Detect missing provider_config
2. Prompt for configuration method (dummy, editor, skip, abort)
3. Apply the configuration
4. Run terraform init and validate automatically

If running manually, continue with the steps below.

### Step 3.4: Add Connection Provider Configs (Manual)

Open `test/e2e_test/dbt-cloud-config.yml` and manually add `provider_config` to each connection:

**Example for Databricks:**
```yaml
globals:
  connections:
    databricks_connection:
      name: "Databricks Production"
      type: "databricks"
      # Add provider_config manually:
      provider_config:
        host: "your-databricks-workspace.cloud.databricks.com"
        http_path: "/sql/1.0/warehouses/abc123"
        catalog: "prod_catalog"
```

**Reason:** Connection provider configs are not available from the API for security reasons.

### Step 3.5: Initialize Terraform (Manual)

```bash
cd test/e2e_test
terraform init -backend=false
```

Expected output: "Terraform has been successfully initialized!"

### Step 3.6: Validate Configuration (Manual)

```bash
terraform validate
```

Expected output: "Success! The configuration is valid."

If errors occur:
- Check YAML syntax
- Verify connection provider configs are present
- Check for module variable recognition issues (see [Known Issues](known_issues.md))

### Step 3.7: Update Test Log (Manual)

```bash
cat >> test_log.md << EOF

## Phase 3: Terraform Validation

- **Start Time:** $(date)
- **Terraform Version:** $(terraform version -json | jq -r '.terraform_version')
- **Init Status:** ✅ Success / ❌ Failed
- **Validate Status:** ✅ Success / ❌ Failed

**Notes:**
- (Add any validation errors or warnings)

EOF
```

---

## Phase 4: Terraform Plan

### Step 4.1: Set Target Account Credentials

Ensure target account credentials are set:

```bash
export DBT_TARGET_ACCOUNT_ID=12345
export DBT_TARGET_API_TOKEN=your_target_token_here
export DBT_TARGET_HOST_URL=https://cloud.getdbt.com
```

### Step 4.2: Run Terraform Plan

```bash
terraform plan -out=tfplan 2>&1 | tee plan_output.txt
```

This will:
1. Query target account for LOOKUP resolution (data sources)
2. Calculate resource differences
3. Output a plan of changes

### Step 4.3: Review Plan Output

Inspect the plan:

```bash
less plan_output.txt
```

Check for:
- [ ] **No errors** (warnings for deprecations are acceptable)
- [ ] **Resource counts** match expectations
- [ ] **LOOKUP resolutions** succeeded (no "data source not found" errors)
- [ ] **Creates** (not updates/deletes) for all resources (clean target account)

Count planned resources:

```bash
grep "Plan:" plan_output.txt
```

Expected format: `Plan: X to add, 0 to change, 0 to destroy.`

### Step 4.4: Review Data Source Lookups

Check if LOOKUP placeholders resolved correctly:

```bash
grep "Reading..." plan_output.txt | head -20
```

If you see errors like "data source not found", verify:
- Target account has the referenced resources (e.g., existing connections)
- LOOKUP keys match actual resource names in target account

### Step 4.5: Update Test Log

```bash
cat >> test_log.md << EOF

## Phase 4: Terraform Plan

- **Start Time:** $(date)
- **Plan Status:** ✅ Success / ❌ Failed
- **Resources to Add:** $(grep "Plan:" plan_output.txt | awk '{print $2}')
- **Resources to Change:** $(grep "Plan:" plan_output.txt | awk '{print $5}')
- **Resources to Destroy:** $(grep "Plan:" plan_output.txt | awk '{print $8}')

**LOOKUP Resolutions:**
- $(grep -c "Reading..." plan_output.txt) data sources read

**Notes:**
- (Add any plan errors, warnings, or observations)

EOF
```

---

## Phase 5: Terraform Apply (Optional)

**⚠️ CAUTION:** Only proceed with apply if:
- Target account is a test/sandbox account
- You are prepared to destroy resources afterward
- Plan review shows no unexpected changes

### Step 5.1: Review Pre-Apply Checklist

- [ ] Target account is **NOT** production
- [ ] Terraform plan reviewed and approved
- [ ] Backup of target account state (if applicable)
- [ ] Connection provider configs manually added to YAML
- [ ] Credential secrets provided via `token_map`
- [ ] Team aware of apply operation (if shared account)

### Step 5.2: Run Terraform Apply

**Option A: Apply Plan (Recommended)**
```bash
terraform apply tfplan
```

**Option B: Apply with Review**
```bash
terraform apply
```

Type `yes` when prompted.

### Step 5.3: Monitor Apply Progress

Watch for:
- [ ] Resources creating successfully
- [ ] No errors during apply
- [ ] All resources reach "Creation complete" state

If errors occur, note the resource and error message for debugging.

### Step 5.4: Verify Resources in dbt Cloud UI

After apply completes:

1. Log in to target account dbt Cloud UI
2. Navigate to **Account Settings** → verify global resources:
   - [ ] Connections created
   - [ ] Service tokens created (if applicable)
   - [ ] Groups created (if applicable)
3. Navigate to **Projects** → verify each project:
   - [ ] Project exists with correct name
   - [ ] Environments created
   - [ ] Jobs created
   - [ ] Environment variables configured

### Step 5.5: Run Sample Job (Optional)

If a job was created, trigger a manual run to verify:

```bash
# Get job ID from Terraform outputs
terraform output job_ids

# Use dbt Cloud UI to trigger a run
```

Verify job completes successfully.

### Step 5.6: Update Test Log

```bash
cat >> test_log.md << EOF

## Phase 5: Terraform Apply

- **Start Time:** $(date)
- **Apply Status:** ✅ Success / ❌ Failed
- **Resources Created:** $(terraform show -json | jq '[.values.root_module.resources[]] | length')

**UI Verification:**
- Connections: ✅ / ❌
- Service Tokens: ✅ / ❌
- Projects: ✅ / ❌
- Environments: ✅ / ❌
- Jobs: ✅ / ❌

**Notes:**
- (Add any apply errors or UI discrepancies)

EOF
```

---

## Phase 6: Cleanup (Optional)

If you applied resources to a test account, clean up:

### Step 6.1: Run Terraform Destroy

```bash
terraform destroy
```

Type `yes` when prompted.

### Step 6.2: Verify Cleanup

Check dbt Cloud UI to ensure resources are removed.

### Step 6.3: Remove Local Files

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml
rm -rf test/e2e_test
rm -rf importer_export
rm importer_runs.json
```

---

## Test Results & Reporting

### Success Criteria

Phase 5 is considered **successful** if:

- ✅ Fetch completes without errors
- ✅ All expected resources captured in JSON export
- ✅ Normalize completes without errors
- ✅ Generated YAML is valid (schema v2, well-formed)
- ✅ Terraform validate passes
- ✅ Terraform plan shows expected resources (no errors)
- ✅ (Optional) Terraform apply succeeds and resources are visible in dbt Cloud UI

### Reporting Results

After completing testing, create a summary report:

```bash
cat > test/e2e_test/test_summary.md << EOF
# End-to-End Test Summary

**Test Date:** $(date)
**Tester:** Your Name
**Importer Version:** $(python -m importer --version)
**Terraform Version:** $(terraform version -json | jq -r '.terraform_version')

## Test Account Details
- **Source Account ID:** $DBT_SOURCE_ACCOUNT_ID
- **Target Account ID:** $DBT_TARGET_ACCOUNT_ID
- **Projects:** [List project names]
- **Connections:** [List connection types]

## Results

### Phase 1: Fetch
- Status: ✅ Success / ❌ Failed
- Duration: [X minutes]
- Resources Fetched: [X projects, Y connections, etc.]

### Phase 2: Normalize
- Status: ✅ Success / ❌ Failed
- Duration: [X minutes]
- YAML Size: [X lines]
- Exclusions: [Y resources excluded]

### Phase 3: Terraform Validation
- Status: ✅ Success / ❌ Failed
- Validation Passed: Yes/No

### Phase 4: Terraform Plan
- Status: ✅ Success / ❌ Failed
- Resources to Create: [X]
- LOOKUP Resolutions: [Y successes, Z failures]

### Phase 5: Terraform Apply (Optional)
- Status: ✅ Success / ❌ Failed / N/A
- Resources Created: [X]
- UI Verification: ✅ All resources visible / ❌ Discrepancies

## Issues Encountered
- [List any errors, warnings, or unexpected behavior]

## Recommendations
- [Suggestions for improvements or bug fixes]

EOF
```

### Share Results

1. Update [importer_implementation_status.md](importer_implementation_status.md) Phase 5 section
2. Create GitHub issue with test results (if applicable)
3. Share summary with team

---

## Troubleshooting

### Common Issues

#### 1. Fetch Errors

**Error:** `401 Unauthorized`
- **Cause:** Invalid or expired token
- **Solution:** Verify `DBT_SOURCE_API_TOKEN` has correct value and permissions

**Error:** `429 Rate Limit Exceeded`
- **Cause:** Too many API requests
- **Solution:** Wait 60 seconds and retry (importer has built-in backoff)

#### 2. Normalize Errors

**Error:** `KeyError: 'projects'`
- **Cause:** Malformed JSON export
- **Solution:** Re-run fetch to regenerate export

**Error:** `YAML syntax error`
- **Cause:** Special characters in resource names
- **Solution:** Check exclusions report, may need to manually edit YAML

#### 3. Terraform Validation Errors

**Error:** `Unsupported argument "yaml_file"`
- **Cause:** Module variable recognition issue
- **Solution:** See [Known Issues](known_issues.md#module-variable-recognition-issue)

**Error:** `Invalid YAML schema`
- **Cause:** YAML doesn't match schema v2
- **Solution:** Verify `version: 2` present, check schema documentation

#### 4. Terraform Plan Errors

**Error:** `data source "dbtcloud_connection" not found`
- **Cause:** LOOKUP reference doesn't exist in target account
- **Solution:** Create missing resource in target account or remove LOOKUP placeholder

**Error:** `provider_config is required`
- **Cause:** Connection missing provider config
- **Solution:** Manually add `provider_config` to connection in YAML

#### 5. Terraform Apply Errors

**Error:** `Error creating project: name already exists`
- **Cause:** Target account already has resource with same name
- **Solution:** Use clean target account or rename resources in YAML

**Error:** `Invalid credential token`
- **Cause:** Missing or incorrect `token_map` entry
- **Solution:** Add credential token to `token_map` in `main.tf`

---

## Next Steps

After completing Phase 5 end-to-end testing:

1. **Document Results** in implementation status document
2. **Create User-Facing Migration Guide** based on learnings
3. **Address Issues** discovered during testing
4. **Performance Testing** with larger accounts (100+ projects)
5. **Edge Case Testing** (empty jobs, archived resources, etc.)

---

## Related Documentation

- [Importer Implementation Status](importer_implementation_status.md) - Current project status
- [Known Issues](known_issues.md) - Known limitations and workarounds
- [Interactive Guide](../importer/INTERACTIVE_GUIDE.md) - Interactive mode usage
- [PROJECT_OVERVIEW](PROJECT_OVERVIEW.md) - Complete project reference

---

**Remember:** End-to-end testing is critical for validating the complete workflow. Take time to document results thoroughly! 🚀

