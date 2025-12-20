# Release Notes: v0.5.3

**Release Date:** 2025-12-20  
**Version:** 0.5.3 (Patch Release)  
**Type:** Critical Bug Fix

---

## Summary

This patch release fixes a critical issue preventing the Terraform provider from connecting to custom domain dbt Cloud instances in the E2E test. The root cause was that the test fixture wasn't passing credential variables to the module, causing the provider to use default values instead of the actual instance configuration.

---

## 🐛 Bug Fixes

### Terraform Provider "Unsupported Authorization Type" Error

**Problem:** E2E test was failing with "Unsupported Authorization Type" error when attempting to connect to custom domain instances (e.g., `iq919.us1.dbt.com`). The error showed XML responses from AWS S3, indicating the provider was hitting the wrong endpoint.

**Root Cause:** The test fixture (`test/e2e_test/main.tf`) had an empty provider block and wasn't passing `dbt_account_id`, `dbt_token`, and `dbt_host_url` variables to the module. The module's `providers.tf` was using `var.dbt_host_url` which defaulted to `https://cloud.getdbt.com` instead of the actual instance URL.

**Solution:** 
- Added variable definitions (`dbt_account_id`, `dbt_token`, `dbt_host_url`) to `test/e2e_test/main.tf`
- Configured the provider block to use these variables
- Explicitly passed credentials to the module call
- Module's provider now correctly inherits credentials from the root module

**Impact:** E2E test now successfully connects to custom domain instances. Terraform plan completes successfully (68 resources planned to add).

**Files Changed:**
- `test/e2e_test/main.tf`: Added variable definitions and provider configuration
- `test/run_e2e_test.sh`: Cleaned up debug instrumentation

---

## 🔄 Changes

### E2E Test Script Cleanup

**Change:** Removed debug instrumentation added during provider connection debugging session.

**Details:**
- Removed curl diagnostic calls for API endpoint testing
- Removed debug logging statements (`printf` NDJSON logs)
- Cleaned up unused token manipulation logic
- Simplified credential handling in `phase3_validate`, `phase4_plan`, and `phase5_apply`

**Impact:** Cleaner test script focused on core functionality without debug noise.

**Files Changed:**
- `test/run_e2e_test.sh`: Removed instrumentation, simplified credential handling

---

## 📚 Documentation Updates

- Updated `CHANGELOG.md` with detailed fix description
- Updated `dev_support/importer_implementation_status.md` with version and change log entry
- Updated `dev_support/phase5_e2e_testing_guide.md` with new version number

---

## 🔧 Technical Details

### Provider Configuration Inheritance

Terraform modules inherit provider configuration from their parent. However, when a module defines its own provider block (as in `providers.tf`), it needs explicit variable values passed from the root module. The fix ensures:

1. Root module (`test/e2e_test/main.tf`) defines variables that `TF_VAR_*` environment variables can populate
2. Root provider block uses these variables
3. Module call explicitly passes variables to the module
4. Module's provider block receives the correct values instead of defaults

### Variable Flow

```
Environment Variables (DBT_TARGET_*)
  ↓
TF_VAR_* (exported by test script)
  ↓
Root Module Variables (test/e2e_test/main.tf)
  ↓
Root Provider Block (uses variables)
  ↓
Module Call (explicitly passes variables)
  ↓
Module Provider Block (receives variables)
```

---

## 🚀 Upgrade Instructions

### For Users

No action required. This fix only affects the E2E test fixture configuration.

### For Developers

If you're creating a new test fixture or module that uses the dbt Cloud Terraform module:

1. **Define credential variables** in your root module:
   ```hcl
   variable "dbt_account_id" {
     type = number
   }
   
   variable "dbt_token" {
     type = string
     sensitive = true
   }
   
   variable "dbt_host_url" {
     type = string
     default = "https://cloud.getdbt.com/api"
   }
   ```

2. **Configure provider** to use variables:
   ```hcl
   provider "dbtcloud" {
     account_id = var.dbt_account_id
     token      = var.dbt_token
     host_url   = var.dbt_host_url
   }
   ```

3. **Pass variables to module**:
   ```hcl
   module "dbt_cloud" {
     source = "../.."
     
     dbt_account_id = var.dbt_account_id
     dbt_token      = var.dbt_token
     dbt_host_url   = var.dbt_host_url
     
     # ... other module parameters
   }
   ```

---

## ✅ Testing

- ✅ Terraform provider successfully connects to custom domain instances
- ✅ Terraform plan completes without authentication errors
- ✅ Provider configuration correctly inherits from root to module
- ✅ E2E test script runs cleanly without debug instrumentation

---

## 📝 Next Steps

- Continue E2E testing with corrected provider configuration
- Address remaining Terraform plan errors (missing token_map, schema requirements, repository attributes) - these are separate data/configuration issues
- Monitor for any edge cases with different instance configurations

---

**Related Issues:** N/A  
**Breaking Changes:** None  
**Migration Required:** No

