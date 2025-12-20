# Release Notes: v0.5.2

**Release Date:** 2025-12-20  
**Version:** 0.5.2 (Patch Release)  
**Type:** Bug Fixes and Improvements

---

## Summary

This patch release fixes several critical issues with connection type detection, interactive prompt handling, and environment variable naming. It also enhances the E2E test workflow with automatic provider configuration injection from `.env` files.

---

## 🐛 Bug Fixes

### Connection Types Showing as "Unknown"

**Problem:** Connections were displaying as "Type: unknown" in interactive prompts and E2E test output, even though the API provided connection type information.

**Root Cause:** The dbt Cloud API v3 `/connections/` endpoint returns `"type": null` but provides `"adapter_version": "databricks_v0"` or `"snowflake_v0"`. The fetcher was only checking the `type` field, which was always null.

**Solution:** Added `_extract_connection_type_from_adapter_version()` function in `importer/fetcher.py` that:
- Extracts connection type from `adapter_version` strings (e.g., "databricks_v0" → "databricks")
- Handles all connection types: databricks, snowflake, bigquery, redshift, postgres, athena, fabric, synapse, starburst, apache_spark, teradata
- Falls back to adapter_version parsing if type is not explicitly set

**Impact:** Connection types now correctly display as "databricks", "snowflake", etc., enabling proper schema-based prompts in interactive mode.

**Files Changed:**
- `importer/fetcher.py`: Added type extraction function and updated `_fetch_connections()`

---

### Bracketed Paste Sequences in Terminal

**Problem:** When pasting values into interactive prompts, terminal escape sequences (`^[[200~` and `^[[201~`) were being included in the input, causing validation errors.

**Root Cause:** Modern terminals use bracketed paste mode, which wraps pasted content with escape sequences. InquirerPy was receiving these sequences as part of the input.

**Solution:** Added `_strip_bracketed_paste_sequences()` filter function that:
- Removes bracketed paste mode escape sequences (`\x1b[200~`, `\x1b[201~`)
- Handles both escape character format and caret notation (`^[[200~`)
- Applied as a filter to all 23 `inquirer.text()` prompts throughout interactive mode

**Impact:** Users can now paste connection credentials seamlessly without manual cleanup of escape sequences.

**Files Changed:**
- `importer/interactive.py`: Added filter function and applied to all text prompts

---

### Terminal Access Warnings in E2E Test

**Problem:** When running interactive connection configuration from the E2E test script, users saw warnings:
- `Warning: Input is not a terminal (fd=0)`
- `WARNING: your terminal doesn't support cursor position requests (CPR)`

**Root Cause:** The E2E test script was invoking Python via heredoc (`python - <<'SCRIPT'`), which doesn't provide proper terminal access for InquirerPy's interactive features.

**Solution:** Created standalone `test/configure_connections.py` script that:
- Executes as a regular Python script with full terminal access
- Uses the same InquirerPy menu system as the importer
- Properly resolves module paths using `Path(__file__).resolve()`

**Impact:** Interactive prompts now work correctly in E2E test context without terminal warnings.

**Files Changed:**
- `test/configure_connections.py`: New standalone script
- `test/run_e2e_test.sh`: Updated `open_interactive_config()` to call standalone script

---

## 🔄 Changes

### Environment Variable Naming Standardization

**Change:** Standardized source account credential variable names to match target account naming convention.

**Details:**
- Changed `DBT_SOURCE_HOST` → `DBT_SOURCE_HOST_URL` for consistency
- Maintains backward compatibility by checking both variable names
- Updated `importer/config.py` to prefer `DBT_SOURCE_HOST_URL` but fall back to legacy `DBT_SOURCE_HOST`
- Updated all documentation and examples

**Impact:** Consistent naming across source and target credentials makes configuration more intuitive.

**Files Changed:**
- `importer/config.py`: Added fallback for legacy variable name
- `importer/interactive.py`: Updated to use and save `DBT_SOURCE_HOST_URL`
- `test/e2e_test/env.example`: Updated variable names
- `importer/README.md`: Updated documentation

---

### E2E Test: Automatic Provider Config Injection

**Enhancement:** Added automatic injection of connection provider configurations from `.env` files.

**Details:**
- Created `inject_provider_configs_from_env()` function in E2E test script
- Reads `DBT_CONNECTION_{CONN_KEY}_{FIELD}` environment variables from `.env` files
- Checks both project root `.env` and test-specific `.env` files
- Automatically converts environment variables to YAML `provider_config` entries
- Skips interactive prompts if configs are already available

**Example:**
```bash
# .env file:
DBT_CONNECTION_DATABRICKS_DEV_UC_ENABLED_HOST=dbc-4a77cdc0-e046.cloud.databricks.com
DBT_CONNECTION_DATABRICKS_DEV_UC_ENABLED_HTTP_PATH=/sql/1.0/warehouses/1d4c807769c9a45d
DBT_CONNECTION_DATABRICKS_DEV_UC_ENABLED_CATALOG=dbt_wsargent

# Gets automatically injected into YAML as:
connections:
  - key: databricks_dev_uc_enabled
    provider_config:
      host: dbc-4a77cdc0-e046.cloud.databricks.com
      http_path: /sql/1.0/warehouses/1d4c807769c9a45d
      catalog: dbt_wsargent
```

**Impact:** Reduces manual configuration steps in E2E testing and enables better test automation.

**Files Changed:**
- `test/run_e2e_test.sh`: Added `inject_provider_configs_from_env()` function

---

## 📚 Documentation Updates

- Updated `CHANGELOG.md` with detailed change descriptions
- Updated `dev_support/importer_implementation_status.md` with version and change log entry
- Updated `dev_support/phase5_e2e_testing_guide.md` with new version number
- Updated `importer/README.md` with standardized environment variable names

---

## 🔧 Technical Details

### Connection Type Extraction Logic

The new `_extract_connection_type_from_adapter_version()` function handles:
- Special cases: `databricks_spark_v0` → `databricks`, `trino_v0` → `starburst`
- Generic parsing: Removes `_v0`, `_v1` suffixes
- Fallback: Returns `None` if pattern doesn't match

### Bracketed Paste Filter

The filter handles multiple formats:
- `\x1b[200~` (actual escape character)
- `^[[200~` (caret notation, common in terminal output)
- Both start (`200~`) and end (`201~`) markers

### Environment Variable Format

Connection configs use the format:
```
DBT_CONNECTION_{CONNECTION_KEY}_{FIELD_NAME}
```

Where:
- `CONNECTION_KEY` is the normalized connection key (e.g., `DATABRICKS_DEV_UC_ENABLED`)
- `FIELD_NAME` is the provider config field name in uppercase (e.g., `HOST`, `HTTP_PATH`, `CATALOG`)

---

## 🚀 Upgrade Instructions

### For Users

1. **Update Environment Variables** (optional but recommended):
   ```bash
   # Old format (still works):
   DBT_SOURCE_HOST=https://cloud.getdbt.com
   
   # New format (recommended):
   DBT_SOURCE_HOST_URL=https://cloud.getdbt.com
   ```

2. **Connection Configs in .env** (new feature):
   ```bash
   # Add connection configs to .env for automatic injection:
   DBT_CONNECTION_DATABRICKS_PROD_HOST=workspace.cloud.databricks.com
   DBT_CONNECTION_DATABRICKS_PROD_HTTP_PATH=/sql/1.0/warehouses/abc123
   ```

### For Developers

- No breaking changes
- All changes are backward compatible
- Existing `.env` files with `DBT_SOURCE_HOST` will continue to work

---

## ✅ Testing

- ✅ Connection types correctly extracted from adapter_version
- ✅ Bracketed paste sequences stripped from all interactive prompts
- ✅ Terminal access works correctly in E2E test script
- ✅ Environment variable fallback maintains backward compatibility
- ✅ Provider config injection works from both project root and test `.env` files

---

## 📝 Next Steps

- Continue E2E testing with corrected connection types and improved workflow
- Monitor for any edge cases in connection type extraction
- Consider adding support for additional connection types as they become available

---

**Related Issues:** N/A  
**Breaking Changes:** None  
**Migration Required:** No

