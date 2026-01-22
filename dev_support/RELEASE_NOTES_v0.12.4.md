# Release Notes - v0.12.4

**Release Date:** 2026-01-22  
**Type:** Patch Release (Private Key Validation & Normalization)

---

## Summary

This release adds robust client-side and server-side validation and normalization for PEM private keys in the Target Credentials page. This addresses recurring issues where pasted private keys with improper formatting caused Terraform parse errors.

---

## New Features

### Private Key Validation & Normalization

- **New `pem_validator.py` module** with reusable validation functions:
  - `normalize_private_key()` - Fixes single-line keys, normalizes whitespace, ensures proper 64-char line wrapping
  - `validate_private_key()` - Validates PEM format, base64 content, and structure
  - `get_validation_status()` - Returns UI-friendly status with color coding
  - `is_private_key_field()` - Helper to identify private key fields

- **Auto-Reformatting on Blur**: When users paste or type a private key and leave the field:
  - Single-line keys are automatically wrapped to proper PEM format
  - Whitespace is normalized
  - Base64 content is re-wrapped at 64 characters per line
  - Headers/footers are preserved

- **Real-Time Validation Badges**:
  - Green "Valid" badge for properly formatted PKCS#8 keys
  - Yellow "Valid" badge with warning tooltip for PKCS#1 keys (recommending PKCS#8)
  - Red "Invalid" badge with error tooltip explaining the issue
  - No badge for empty fields

- **Enhanced Private Key Input**:
  - Replaced single-line input with 6-row multi-line textarea
  - Monospace font for better readability
  - Placeholder showing expected PEM format
  - Help text explaining auto-formatting behavior

- **Server-Side Normalization**: Keys are normalized in `env_manager.py` before saving to `.env` file, ensuring consistent storage format regardless of input method.

---

## Files Changed

| File | Change Type |
|------|-------------|
| `importer/web/components/pem_validator.py` | **New** - Validation module |
| `importer/web/pages/target_credentials.py` | Modified - Enhanced private key field |
| `importer/web/env_manager.py` | Modified - Added normalization before save |
| `importer/VERSION` | Updated to 0.12.4 |
| `CHANGELOG.md` | Added v0.12.4 entry |
| `dev_support/importer_implementation_status.md` | Updated version and change log |
| `dev_support/phase5_e2e_testing_guide.md` | Updated version reference |

---

## Upgrade Notes

This is a backwards-compatible patch release. No configuration changes required.

### Testing Recommendations

1. Navigate to Target Credentials page
2. Select an environment with Snowflake keypair authentication
3. Test pasting various private key formats:
   - Properly formatted multi-line PEM key
   - Single-line key (should auto-reformat on blur)
   - Key with extra whitespace (should normalize)
   - Invalid content (should show red "Invalid" badge)
4. Verify validation badge updates in real-time as you type
5. Save credentials and verify they work with `terraform plan`

---

## Known Limitations

- Validation is client-side only for immediate feedback; invalid keys can still be saved but will fail at Terraform execution
- PKCS#1 format keys show a warning but are accepted (Snowflake supports both)
- Encrypted private keys show a warning about potential passphrase requirements

---

**Previous Version:** 0.12.3  
**Next Version:** TBD
