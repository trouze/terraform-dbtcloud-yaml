# Release Notes - v0.4.2

**Release Date:** December 19, 2025  
**Type:** Patch Release (Bug Fixes + E2E Enhancement)

---

## Overview

This patch release fixes critical Terraform type inconsistency errors and adds an interactive provider configuration step to the E2E test workflow. These fixes enable successful terraform validate and plan operations with multi-project YAML configurations.

---

## 🎯 Highlights

### Interactive Provider Config Step
The E2E test script now pauses after YAML normalization to help configure connection `provider_config` fields (which aren't exported by the dbt Cloud API). Users can choose from 4 options:
1. **Add dummy configs** (recommended for validation testing)
2. **Open YAML in editor** for manual configuration  
3. **Skip** and continue (validation will fail)
4. **Abort** test

### Critical Terraform Fixes
Fixed 3 type inconsistency errors that prevented `terraform plan` from succeeding:
- Conditional type mismatch in `projects_v2` local
- Service tokens missing `service_token_permissions` field (deleted tokens)
- Groups missing `group_permissions` field (special groups)

---

## 🐛 Bug Fixes

### Terraform Type Consistency Issues

**Issue 1: Inconsistent Conditional Result Types**
- **Problem**: `local.projects_v2 = condition ? try(...) : []` created incompatible tuple types
- **Error**: `The 'true' tuple has length 17, but the 'false' tuple has length 0`
- **Fix**: Removed conditionals from locals, always process uniformly with `try()` defaults
- **Impact**: Terraform validate and plan now succeed

**Issue 2: Service Tokens Type Inconsistency**  
- **Problem**: Deleted service tokens (`state: 2`) don't have `service_token_permissions` from API
- **Error**: `attribute "service_tokens": all list elements must have the same type`
- **Root Cause**: Discovered via runtime analysis - deleted tokens lack permissions field entirely
- **Fix**: Normalize by adding `service_token_permissions: []` to tokens missing this field
- **Code**: Uses `merge(token, {service_token_permissions = try(token.service_token_permissions, [])})` in for-comprehension

**Issue 3: Groups Type Inconsistency**
- **Problem**: Special "Everyone" group missing `group_permissions` field
- **Error**: `attribute "groups": all list elements must have the same type`  
- **Fix**: Normalize by adding `group_permissions: []` to groups missing this field
- **Pattern**: Same normalization approach as service tokens

### Testing Improvements

**Test Variable Configuration**
- **Problem**: E2E test failed with "Missing required argument: test_var"
- **Fix**: Added default value to `test_vars.tf` so it's not required when E2E test loads root module
- **Impact**: E2E test can now load root module without extra variables

**Module Output References**
- **Problem**: E2E test outputs referenced non-existent `project_ids`, `connection_ids`
- **Fix**: Updated to use v2-prefixed outputs (`v2_project_ids`, `v2_environment_ids`, etc.)
- **Impact**: Test fixture outputs now correctly reference schema v2 outputs

---

## ✨ New Features

### Interactive Provider Configuration

**Function: `configure_provider_configs()`**
- Detects connections missing `provider_config` in YAML
- Displays connection details (name, key, type)
- Presents 4 interactive options with default selection
- Integrates seamlessly into E2E test flow

**Function: `add_dummy_provider_configs()`**
- Generates type-specific dummy configs:
  - **Databricks**: host, http_path, catalog
  - **Snowflake**: account, database, warehouse, role
  - **BigQuery**: project_id, dataset, location
  - **Redshift**: host, port, dbname
  - **PostgreSQL**: host, port, dbname
- Enables terraform validate/plan without real credentials
- Clearly warns that apply will fail with dummy values

**Function: `open_editor_and_wait()`**
- Opens YAML in user's preferred editor ($EDITOR or nano)
- Pauses execution until user saves and exits
- Verifies `provider_config` was added before continuing
- Displays helpful examples before opening editor

---

## 📚 Documentation

### E2E Testing Guide Updates
- Added "Phase 3: Provider Configuration (Interactive)" section
- Documented all 4 interactive options with use cases
- Provided provider_config examples for 5+ database types
- Explained why this step is required (API security limitation)

---

## 🔧 Technical Details

### Root Cause Analysis

**Terraform Type System Behavior:**
- YAML parsing creates fixed-length tuple types, not dynamic lists
- Conditionals `? :` require both branches to have identical types
- Objects in lists must have identical field presence (not just types)
- Missing optional fields create incompatible object signatures

**Solution Pattern:**
```terraform
# Before (causes type error)
locals {
  projects_v2 = condition ? try(yaml.projects, []) : []
  globals_v2  = try(yaml.globals, null)
}

# After (consistent types)
locals {
  projects_v2 = [for p in try(yaml.projects, []) : p]
  globals_v2  = {
    service_tokens = [
      for token in try(raw.service_tokens, []) :
      merge(token, {service_token_permissions = try(token.service_token_permissions, [])})
    ]
    groups = [
      for group in try(raw.groups, []) :
      merge(group, {group_permissions = try(group.group_permissions, [])})
    ]
  }
}
```

### Data Patterns Discovered

**Deleted Service Tokens (`state: 2`):**
- Do not have `service_token_permissions` field from API
- Runtime evidence: 2 tokens with `state: 2`, both missing permissions
- Active tokens (`state: 1`): 15 tokens, all have permissions field

**Special Groups:**
- "Everyone" group lacks `group_permissions` field
- Standard groups have `group_permissions` array (can be empty)

---

## ✅ Test Results

**E2E Test Status:**
- ✅ Phase 1: Fetch (17 projects, 3 connections)
- ✅ Phase 2: Normalize (YAML generated successfully)
- ✅ Phase 3: Interactive Provider Config (working perfectly)
- ✅ Phase 3: Terraform Validation (PASSED)
- ✅ Phase 4: Terraform Plan (PASSED)
- ⏭️ Phase 5: Terraform Apply (Skipped - dummy configs)

---

## 🚀 Upgrade Instructions

### From 0.4.1 to 0.4.2

No breaking changes. Simply pull the latest code:

```bash
cd terraform-dbtcloud-yaml
git pull origin main
```

**If running E2E tests:**
```bash
cd test
source ../.venv/bin/activate
./run_e2e_test.sh
```

You'll now see the interactive provider config prompt at Phase 3.

---

## 📝 Notes

### Known Limitations

1. **Deleted Resources in YAML**: The normalizer currently includes deleted resources (`state: 2`) in the YAML output. While we now handle this in Terraform, a future improvement would filter these during normalization.

2. **Provider Config Required**: Connection `provider_config` fields are not exported by the dbt Cloud API for security reasons. This manual step is unavoidable for real migrations.

3. **Dummy Configs for Testing Only**: The auto-generated dummy provider configs enable validation/plan but will fail on apply. Use option 2 (manual editor) for real migrations.

### Future Improvements

- **Normalizer Enhancement**: Filter out `state: 2` resources during YAML generation
- **Field Normalization**: Add systematic field presence normalization for all resource types
- **Type Testing**: Add automated tests for Terraform type consistency across various YAML structures

---

## 🙏 Acknowledgments

Special thanks to the user who identified that `state: 2` likely meant deleted tokens, leading to the discovery of the root cause for the service tokens type inconsistency!

---

## 📖 Related Documentation

- [CHANGELOG.md](../CHANGELOG.md) - Full change history
- [Phase 5 E2E Testing Guide](phase5_e2e_testing_guide.md) - Complete testing documentation
- [Implementation Status](importer_implementation_status.md) - Project roadmap and status

---

**Questions or issues?** Please open an issue in the repository.

