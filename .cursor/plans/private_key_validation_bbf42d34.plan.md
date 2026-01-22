---
name: Private Key Validation
overview: Add validation and reformatting for private keys when entered in the credentials UI, ensuring proper PEM format before saving.
todos:
  - id: create-validator
    content: Create `importer/web/components/pem_validator.py` with normalize and validate functions
    status: pending
  - id: update-form-field
    content: Update `_create_single_field()` to use textarea with validation for private_key fields
    status: pending
  - id: integrate-save
    content: Apply normalization in `save_env_credential_config()` before writing to .env
    status: pending
  - id: add-tests
    content: Add unit tests for the validator with various malformed key inputs
    status: pending
---

# Private Key Validation and Reformatting

## Overview

Add a utility module for PEM private key validation and normalization, integrate it into the credentials form UI for immediate feedback, and apply normalization before saving.

## Implementation

### 1. Create Validation Utility Module

Create a new file `importer/web/components/pem_validator.py` with:

- `normalize_private_key(key: str) -> str` - Normalizes a private key to proper PEM format:
- Strip leading/trailing whitespace
- Convert Windows line endings (`\r\n`) to Unix (`\n`)
- Detect and fix single-line keys (split base64 content into 64-char lines)
- Ensure proper header/footer (`-----BEGIN PRIVATE KEY-----` / `-----END PRIVATE KEY-----`)
- Handle RSA, EC, and encrypted private key variants
- Remove extraneous whitespace within the key body

- `validate_private_key(key: str) -> tuple[bool, str]` - Validates the key format:
- Returns `(True, "")` if valid
- Returns `(False, "error message")` if invalid
- Checks: has header/footer, base64 content is valid, structure is correct

- `is_private_key_field(field: str) -> bool` - Helper to identify private key fields

### 2. Enhance Form Field for Private Keys

Modify `_create_single_field()` in [target_credentials.py](importer/web/pages/target_credentials.py) (around line 995):

- Use a `ui.textarea` instead of `ui.input` for `private_key` fields (multi-line support)
- Add `on_blur` handler that:
- Normalizes the pasted key automatically (including single-line keys)
- Updates the input value with the normalized/reformatted version
- Triggers format validation
- Add badge indicator for validation status:
- Green "Valid" badge when PEM format is correct
- Red "Invalid format" badge with reason when format is wrong
- No badge when field is empty

### 3. Apply Validation Before Save

Modify `save_env_credential_config()` in [env_manager.py](importer/web/env_manager.py):

- Import the validator
- Normalize `private_key` values before saving to `.env`
- Optionally validate and warn/error if invalid format

### 4. Update Dummy Key Format

The dummy key in [credential_schemas.py](importer/web/components/credential_schemas.py) (lines 78, 505) already has proper format - no changes needed there.

## Provider-Specific Requirements (Researched)

### Snowflake

- RSA algorithm, minimum 2048 bits
- **PKCS#8 format strongly recommended** - some drivers fail with PKCS#1
- Both encrypted and unencrypted supported
- Encrypted keys require AES cipher and passphrase
- Newlines are critical - missing newlines break parsing

### BigQuery/Google

- PKCS#8 format (`-----BEGIN PRIVATE KEY-----`)
- RSA-2048 default
- Unencrypted (no passphrase)
- JSON credentials use `\n` for line breaks in `private_key` field

## Supported PEM Formats

Priority order (most to least preferred):

1. `-----BEGIN PRIVATE KEY-----` / `-----END PRIVATE KEY-----` (PKCS#8 - **preferred**)
2. `-----BEGIN RSA PRIVATE KEY-----` / `-----END RSA PRIVATE KEY-----` (PKCS#1 - accept with warning)
3. `-----BEGIN ENCRYPTED PRIVATE KEY-----` / `-----END ENCRYPTED PRIVATE KEY-----` (requires passphrase)

## Normalization Rules

1. Strip leading/trailing whitespace from entire input
2. Convert Windows line endings (`\r\n`) to Unix (`\n`)
3. Ensure base64 content is wrapped at 64 characters per line
4. Ensure single newline after header and before footer
5. Remove any blank lines within the base64 content
6. Handle single-line pasted keys (detect and split)

## Validation Rules

1. Must have matching header/footer pair
2. Base64 content must be valid (only A-Z, a-z, 0-9, +, /, =)
3. Warn (don't reject) if using PKCS#1 format - suggest converting to PKCS#8