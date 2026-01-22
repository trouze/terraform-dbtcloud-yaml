# Release Notes: v0.12.3

**Release Date:** 2026-01-22  
**Release Type:** Patch  
**Previous Version:** 0.12.2

---

## Summary

This patch release fixes a critical issue where multi-line private keys in `secrets.auto.tfvars` caused Terraform parsing failures. It also improves the dummy credential system with a valid PEM key format and better UI visibility.

---

## Fixed

### Private Key HCL Escaping

**Issue:** Private keys stored in `.env` with literal newlines were written to `secrets.auto.tfvars` without proper escaping, causing Terraform to fail with "Invalid multi-line string" errors.

**Solution:** Added `escape_hcl_string()` helper function in `yaml_converter.py` that properly escapes:
- Newlines (`\n` → `\\n`)
- Carriage returns (`\r` → `\\r`)
- Tabs (`\t` → `\\t`)
- Backslashes and quotes

**Files Changed:**
- `importer/yaml_converter.py` - Added `escape_hcl_string()` function in `_write_secrets_tfvars()`

---

## Changed

### Valid Dummy Private Key

**Before:** Dummy keypair credentials used an invalid placeholder string that could cause validation issues:
```
-----BEGIN PRIVATE KEY-----
dummy_key_placeholder_for_terraform_validation_only
-----END PRIVATE KEY-----
```

**After:** Now uses a syntactically valid 2048-bit RSA private key in PKCS#8 PEM format, stored as `DUMMY_PRIVATE_KEY_PEM` constant.

**Benefits:**
- Terraform validation passes with dummy credentials
- Prevents confusion about whether credentials are properly formatted
- Key is obviously for testing (randomly generated, not associated with any real account)

**Files Changed:**
- `importer/web/components/credential_schemas.py` - Added `DUMMY_PRIVATE_KEY_PEM` constant

### Dummy Credential Indicator

**Before:** Environments with dummy credentials had `[DUMMY CREDENTIALS]` prefix added to their **description** field.

**After:** Now appends `[DUMMY CREDENTIALS]` as a **suffix** to the environment **name** field.

**Rationale:** Environment descriptions are not prominently displayed in the dbt Cloud UI. The name suffix makes dummy credential status immediately visible when viewing environments.

**Example:**
- Before: Description = `[DUMMY CREDENTIALS] Production environment`
- After: Name = `1 - Prod [DUMMY CREDENTIALS]`

**Files Changed:**
- `importer/yaml_converter.py` - Updated `_copy_yaml_with_dummy_markers()` and `_update_yaml_with_dummy_markers()`

---

## Upgrade Notes

### No Breaking Changes

This is a backward-compatible patch release. No migration steps required.

### Recommended Actions

1. **Regenerate Terraform files** if you have existing deployments with keypair credentials
2. **Reset dummy credentials** to get the new valid PEM key format (optional)

---

## Testing

Verified:
- `terraform validate` passes with new dummy key format
- `terraform plan` succeeds without multi-line string errors
- Private keys with newlines properly escaped in HCL output

---

## Files Changed

| File | Changes |
|------|---------|
| `importer/VERSION` | 0.12.2 → 0.12.3 |
| `importer/yaml_converter.py` | Added HCL escaping, updated name suffix logic |
| `importer/web/components/credential_schemas.py` | Added valid dummy private key constant |
| `CHANGELOG.md` | Added v0.12.3 entry |
| `dev_support/importer_implementation_status.md` | Updated version, added change log entry |
| `dev_support/phase5_e2e_testing_guide.md` | Updated version |
