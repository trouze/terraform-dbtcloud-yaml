# Release Notes: v0.5.1

**Release Date:** 2025-12-20  
**Type:** Patch Release (Bug Fixes & Improvements)  
**Status:** ✅ Ready for Use

---

## Overview

Version 0.5.1 standardizes environment variable naming and enhances the interactive connection configuration experience. This release fixes inconsistencies in environment variable names and replaces the text editor with Python menu-driven prompts for better usability.

### Key Changes

- **Environment Variable Standardization**: Consistent naming across source and target accounts
- **Interactive Connection Configuration**: Replaced nano editor with Python menu-driven prompts
- **Improved User Experience**: Better guidance for required vs optional fields

---

## What's Fixed

### 1. Environment Variable Naming Standardization

**Problem Solved:**  
Environment variables were inconsistent:
- Source account used `DBT_SOURCE_*` (correct) but E2E test script checked `DBT_CLOUD_*` (incorrect)
- Target account used `DBTCLOUD_*` instead of `DBT_TARGET_*` pattern
- Target token used `DBT_TARGET_TOKEN` instead of `DBT_TARGET_API_TOKEN`

**Solution:**  
Standardized all environment variable names to follow consistent patterns:
- **Source account:** `DBT_SOURCE_ACCOUNT_ID`, `DBT_SOURCE_API_TOKEN`, `DBT_SOURCE_HOST`
- **Target account:** `DBT_TARGET_ACCOUNT_ID`, `DBT_TARGET_API_TOKEN`, `DBT_TARGET_HOST_URL`

**Files Updated:**
- `test/e2e_test/env.example`: Updated variable names
- `test/run_e2e_test.sh`: Updated all references and prerequisite checks
- `importer/interactive.py`: Updated target credential prompting and saving
- Documentation files: Updated all examples and references

**Migration:**  
Users with existing `.env` files need to update variable names:
```bash
# Old (v0.5.0)
DBTCLOUD_ACCOUNT_ID=12345
DBTCLOUD_TOKEN=your_token

# New (v0.5.1)
DBT_TARGET_ACCOUNT_ID=12345
DBT_TARGET_API_TOKEN=your_token
```

---

## What's Changed

### 2. Interactive Connection Configuration Enhancement

**Problem Solved:**  
Users had to manually edit YAML files in nano editor, which required:
- Knowledge of YAML syntax
- Understanding of required vs optional fields for each connection type
- Manual validation of field names and types

**Solution:**  
Replaced nano editor with Python menu-driven interactive prompts that:
- Show required vs optional fields clearly
- Provide helpful descriptions and examples for each field
- Validate input (e.g., port numbers, required fields)
- Automatically update the YAML file

**User Experience:**

**Before (v0.5.0):**
```
Options:
  1) Add dummy configs
  2) Open YAML in editor ← Opens nano, user must know YAML syntax
  3) Skip
  4) Abort
```

**After (v0.5.1):**
```
Options:
  1) Add dummy configs
  2) Interactive configuration ← Python menu-driven prompts
  3) Skip
  4) Abort

[If option 2 selected]
Connection: Snowflake Production
Required Fields:
  ? Snowflake Account: abc12345
  ? Database: prod_db
  ? Warehouse: compute_wh
Optional Fields:
  ? Role (press Enter to skip): transform_role
  ✓ Configuration saved
```

**Technical Changes:**
- **File:** `importer/interactive.py`
- **New Schema Definitions:** `CONNECTION_SCHEMAS` dictionary with:
  - Required vs optional fields for each connection type
  - Field descriptions and examples
  - Validation rules
- **Enhanced Function:** `prompt_connection_credentials()` now uses schemas
- **New Wrapper:** `prompt_connection_credentials_interactive()` automatically updates YAML
- **Updated E2E Script:** `test/run_e2e_test.sh` uses Python function instead of nano

**Supported Connection Types:**
- Snowflake (account, database, warehouse, role, etc.)
- Databricks (host, http_path, catalog, etc.)
- BigQuery (project_id, dataset, location, etc.)
- Redshift (hostname, port, dbname, etc.)
- PostgreSQL (hostname, port, dbname, etc.)
- Athena (region_name, database, s3_staging_dir)
- Fabric (server, database, port, etc.)
- Synapse (host, database, port, etc.)

---

## Technical Details

### Environment Variable Mapping

The E2E test script now properly maps environment variables for Terraform:

```bash
# Source account (for fetch)
DBT_SOURCE_ACCOUNT_ID → Used by importer
DBT_SOURCE_API_TOKEN → Used by importer
DBT_SOURCE_HOST → Used by importer

# Target account (for Terraform apply)
DBT_TARGET_ACCOUNT_ID → TF_VAR_dbt_account_id + DBT_CLOUD_ACCOUNT_ID
DBT_TARGET_API_TOKEN → TF_VAR_dbt_token + DBT_CLOUD_TOKEN
DBT_TARGET_HOST_URL → TF_VAR_dbt_host_url + DBT_CLOUD_HOST_URL
```

### Connection Schema Structure

```python
CONNECTION_SCHEMAS = {
    "snowflake": {
        "required": ["account", "database", "warehouse"],
        "optional": ["role", "client_session_keep_alive", "allow_sso"],
        "descriptions": {
            "account": "Snowflake account identifier (e.g., 'abc12345')",
            "database": "Default database name",
            # ... etc
        }
    },
    # ... other connection types
}
```

---

## Upgrade Instructions

### For Users

1. **Update `.env` file** with new variable names:
   ```bash
   # Update target account variables
   DBT_TARGET_ACCOUNT_ID=<your_account_id>
   DBT_TARGET_API_TOKEN=<your_token>
   DBT_TARGET_HOST_URL=https://cloud.getdbt.com
   ```

2. **No code changes required** - all changes are backward compatible in functionality

3. **Test E2E workflow** - the interactive connection configuration is now easier to use

### For Developers

- Review `CONNECTION_SCHEMAS` in `importer/interactive.py` to understand field definitions
- Update any scripts that reference old environment variable names
- Test interactive connection configuration with various connection types

---

## Testing

### Verified

- ✅ Environment variable mapping works correctly in E2E test script
- ✅ Interactive connection prompts show required/optional fields correctly
- ✅ YAML file updates automatically after interactive configuration
- ✅ All connection types supported with appropriate field prompts
- ✅ Validation works for numeric fields (ports) and required fields

### Recommended Testing

- Test with each connection type (Snowflake, Databricks, BigQuery, etc.)
- Verify `.env` file updates correctly with new variable names
- Test E2E workflow end-to-end with interactive connection configuration

---

## Next Steps

- Continue Phase 5 E2E testing with improved interactive configuration
- Gather user feedback on new interactive prompts
- Consider adding more connection types if needed
- Potential future enhancement: Support for SSH tunnel configuration in interactive mode

---

## Related Documentation

- [Version Update Checklist](VERSION_UPDATE_CHECKLIST.md)
- [Phase 5 E2E Testing Guide](phase5_e2e_testing_guide.md)
- [Interactive Guide](../importer/INTERACTIVE_GUIDE.md)
- [Implementation Status](importer_implementation_status.md)

---

**Questions or Issues?**  
Please report issues or questions via GitHub Issues or team communication channels.

