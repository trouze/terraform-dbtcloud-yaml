"""PEM Private Key validation and normalization utilities.

This module provides functions to validate and normalize PEM-formatted private keys
for use with dbt Cloud credential configurations. It handles common issues like:
- Single-line pasted keys (missing line breaks)
- Windows line endings
- Extra whitespace
- Various PEM format variants (PKCS#8, PKCS#1, encrypted)
"""

import base64
import re
from typing import Tuple

# PEM header/footer patterns
PEM_HEADERS = {
    "PRIVATE KEY": ("-----BEGIN PRIVATE KEY-----", "-----END PRIVATE KEY-----"),  # PKCS#8
    "RSA PRIVATE KEY": ("-----BEGIN RSA PRIVATE KEY-----", "-----END RSA PRIVATE KEY-----"),  # PKCS#1
    "EC PRIVATE KEY": ("-----BEGIN EC PRIVATE KEY-----", "-----END EC PRIVATE KEY-----"),  # EC
    "ENCRYPTED PRIVATE KEY": ("-----BEGIN ENCRYPTED PRIVATE KEY-----", "-----END ENCRYPTED PRIVATE KEY-----"),
}

# Preferred format (PKCS#8)
PREFERRED_HEADER = "-----BEGIN PRIVATE KEY-----"
PREFERRED_FOOTER = "-----END PRIVATE KEY-----"

# Base64 character set (including padding)
BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/=\s]+$")

# Line length for PEM base64 content
PEM_LINE_LENGTH = 64


def is_private_key_field(field: str) -> bool:
    """Check if a field name represents a private key field.
    
    Args:
        field: Field name to check
        
    Returns:
        True if the field is a private key field
    """
    field_lower = field.lower()
    return field_lower == "private_key" or field_lower.endswith("_private_key")


def _detect_pem_type(key: str) -> Tuple[str, str, str]:
    """Detect the PEM key type from the header.
    
    Args:
        key: The PEM key string
        
    Returns:
        Tuple of (key_type, header, footer) or ("", "", "") if not found
    """
    key_upper = key.upper()
    for key_type, (header, footer) in PEM_HEADERS.items():
        if header.upper() in key_upper:
            return key_type, header, footer
    return "", "", ""


def _extract_base64_content(key: str, header: str, footer: str) -> str:
    """Extract the base64 content from between header and footer.
    
    Args:
        key: The full PEM key string
        header: The PEM header line
        footer: The PEM footer line
        
    Returns:
        The base64 content (may include whitespace)
    """
    # Find positions
    header_pos = key.upper().find(header.upper())
    footer_pos = key.upper().find(footer.upper())
    
    if header_pos == -1 or footer_pos == -1:
        return ""
    
    # Extract content between header and footer
    start = header_pos + len(header)
    content = key[start:footer_pos]
    
    return content


def normalize_private_key(key: str) -> str:
    """Normalize a private key to proper PEM format.
    
    This function:
    1. Strips leading/trailing whitespace
    2. Converts Windows line endings to Unix
    3. Detects and fixes single-line keys (splits base64 into 64-char lines)
    4. Ensures proper header/footer format
    5. Removes extraneous whitespace within the key body
    
    Args:
        key: The private key string (may be malformed)
        
    Returns:
        Normalized PEM-formatted private key, or original if normalization fails
    """
    if not key or not key.strip():
        return key
    
    # Step 1: Strip and normalize line endings
    key = key.strip()
    key = key.replace("\r\n", "\n").replace("\r", "\n")
    
    # Step 2: Detect PEM type
    key_type, header, footer = _detect_pem_type(key)
    
    if not key_type:
        # Not a recognized PEM format - return as-is
        return key
    
    # Step 3: Extract base64 content
    base64_content = _extract_base64_content(key, header, footer)
    
    if not base64_content:
        return key
    
    # Step 4: Clean the base64 content
    # Remove all whitespace to get the raw base64
    clean_base64 = re.sub(r"\s+", "", base64_content)
    
    # Validate it's valid base64 characters
    if not BASE64_PATTERN.match(clean_base64):
        # Invalid base64 - return original
        return key
    
    # Step 5: Re-wrap at 64 characters per line
    wrapped_lines = []
    for i in range(0, len(clean_base64), PEM_LINE_LENGTH):
        wrapped_lines.append(clean_base64[i:i + PEM_LINE_LENGTH])
    
    # Step 6: Reconstruct the PEM key
    normalized = header + "\n"
    normalized += "\n".join(wrapped_lines)
    normalized += "\n" + footer
    
    return normalized


def validate_private_key(key: str) -> Tuple[bool, str]:
    """Validate a private key's PEM format.
    
    This function checks:
    1. Has matching header/footer pair
    2. Base64 content is valid
    3. Structure is correct
    
    Args:
        key: The private key string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if valid
        - (True, "warning message") if valid but with warnings (e.g., PKCS#1 format)
        - (False, "error message") if invalid
    """
    if not key or not key.strip():
        return False, "Private key is empty"
    
    key = key.strip()
    
    # Check for PEM header
    key_type, header, footer = _detect_pem_type(key)
    
    if not key_type:
        # Check if it looks like base64 without headers
        clean = re.sub(r"\s+", "", key)
        if BASE64_PATTERN.match(clean) and len(clean) > 100:
            return False, "Missing PEM header/footer. Key should start with '-----BEGIN PRIVATE KEY-----'"
        return False, "Not a valid PEM format. Expected '-----BEGIN PRIVATE KEY-----' header"
    
    # Check for footer
    if footer.upper() not in key.upper():
        return False, f"Missing PEM footer. Expected '{footer}'"
    
    # Extract and validate base64 content
    base64_content = _extract_base64_content(key, header, footer)
    
    if not base64_content.strip():
        return False, "No key content found between header and footer"
    
    # Clean and validate base64
    clean_base64 = re.sub(r"\s+", "", base64_content)
    
    if not clean_base64:
        return False, "Key content is empty"
    
    # Check for invalid characters
    if not BASE64_PATTERN.match(clean_base64):
        invalid_chars = set(re.findall(r"[^A-Za-z0-9+/=\s]", base64_content))
        return False, f"Invalid characters in key content: {', '.join(repr(c) for c in invalid_chars)}"
    
    # Try to decode base64 to verify it's valid
    try:
        # Add padding if needed
        padding_needed = 4 - (len(clean_base64) % 4)
        if padding_needed != 4:
            clean_base64 += "=" * padding_needed
        base64.b64decode(clean_base64)
    except Exception:
        return False, "Base64 content is malformed"
    
    # Check minimum length (a valid RSA-2048 key is ~1700 chars)
    if len(clean_base64) < 100:
        return False, "Key content appears too short for a valid private key"
    
    # Warnings for non-preferred formats
    if key_type == "RSA PRIVATE KEY":
        return True, "PKCS#1 format detected. Consider converting to PKCS#8 for better compatibility."
    
    if key_type == "ENCRYPTED PRIVATE KEY":
        return True, "Encrypted private key detected. Ensure passphrase is also provided."
    
    return True, ""


def get_validation_status(key: str) -> Tuple[str, str, str]:
    """Get validation status for UI display.
    
    Args:
        key: The private key string
        
    Returns:
        Tuple of (status, message, color) where:
        - status: "valid", "warning", "invalid", or "empty"
        - message: Human-readable message
        - color: Color for UI badge ("green", "yellow", "red", "")
    """
    if not key or not key.strip():
        return "empty", "", ""
    
    is_valid, message = validate_private_key(key)
    
    if is_valid:
        if message:
            # Valid with warning
            return "warning", message, "yellow"
        return "valid", "Valid PEM format", "green"
    else:
        return "invalid", message, "red"
