"""License management for Migration Workflow access control.

This module implements Ed25519-based license verification. Authorized public keys
are stored in a GitHub repository, and users authenticate with their email and
private key.

Environment variables:
    MAGELLAN_LICENSE_EMAIL: User's email address (must match key registration)
    MAGELLAN_LICENSE_KEY: Base64-encoded Ed25519 private key (32 bytes)
    MAGELLAN_LICENSE_KEYS_URL: URL to fetch authorized keys JSON (optional)
    MAGELLAN_LICENSE_BYPASS: Set to "true" to bypass licensing (temporary)

License Tiers:
    - Explorer: Account Explorer only (default for no license)
    - Solutions Architect: Account Explorer + Jobs as Code
    - Resident Architect: All workflows
    - Engineering: All workflows (internal)
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv


class LicenseTier(Enum):
    """License tier levels with ascending access."""

    EXPLORER = "explorer"
    SOLUTIONS_ARCHITECT = "solutions_architect"
    RESIDENT_ARCHITECT = "resident_architect"
    ENGINEERING = "engineering"


# Feature access by tier
# No license defaults to EXPLORER tier
TIER_FEATURES: Dict[LicenseTier, Dict[str, bool]] = {
    LicenseTier.EXPLORER: {
        "account_explorer": True,
        "jobs_as_code": False,
        "migration": False,
        "import_adopt": False,
    },
    LicenseTier.SOLUTIONS_ARCHITECT: {
        "account_explorer": True,
        "jobs_as_code": True,
        "migration": False,
        "import_adopt": False,
    },
    LicenseTier.RESIDENT_ARCHITECT: {
        "account_explorer": True,
        "jobs_as_code": True,
        "migration": True,
        "import_adopt": True,
    },
    LicenseTier.ENGINEERING: {
        "account_explorer": True,
        "jobs_as_code": True,
        "migration": True,
        "import_adopt": True,
    },
}

# Tier Access Matrix:
# | Tier                | Account Explorer | Jobs as Code | Migration | Import & Adopt |
# |---------------------|-----------------|--------------|-----------|----------------|
# | Explorer (default)  | Yes             | No           | No        | No             |
# | Solutions Architect | Yes             | Yes          | No        | No             |
# | Resident Architect  | Yes             | Yes          | Yes       | Yes            |
# | Engineering         | Yes             | Yes          | Yes       | Yes            |

TIER_DISPLAY_NAMES: Dict[LicenseTier, str] = {
    LicenseTier.EXPLORER: "Explorer",
    LicenseTier.SOLUTIONS_ARCHITECT: "Solutions Architect",
    LicenseTier.RESIDENT_ARCHITECT: "Resident Architect",
    LicenseTier.ENGINEERING: "Engineering",
}


def get_tier_features(tier: LicenseTier) -> Dict[str, bool]:
    """Get the feature access dictionary for a tier."""
    return TIER_FEATURES.get(tier, TIER_FEATURES[LicenseTier.EXPLORER])


def has_feature_access(tier: LicenseTier, feature: str) -> bool:
    """Check if a tier has access to a specific feature.

    Args:
        tier: The license tier to check
        feature: Feature name (account_explorer, jobs_as_code, migration, import_adopt)

    Returns:
        True if the tier has access to the feature
    """
    features = get_tier_features(tier)
    return features.get(feature, False)

logger = logging.getLogger(__name__)

# Default URL for authorized keys (dbt-labs/magellan-auth repo)
DEFAULT_KEYS_URL = "https://raw.githubusercontent.com/dbt-labs/magellan-auth/main/authorized_keys.json"

# Environment variable names
ENV_LICENSE_EMAIL = "MAGELLAN_LICENSE_EMAIL"
ENV_LICENSE_KEY = "MAGELLAN_LICENSE_KEY"
ENV_LICENSE_KEYS_URL = "MAGELLAN_LICENSE_KEYS_URL"
ENV_LICENSE_BYPASS = "MAGELLAN_LICENSE_BYPASS"


@dataclass
class LicenseStatus:
    """Result of license verification."""

    is_valid: bool
    email: Optional[str] = None
    message: str = ""
    tier: LicenseTier = field(default=LicenseTier.EXPLORER)

    @classmethod
    def valid(
        cls, email: str, tier: LicenseTier = LicenseTier.RESIDENT_ARCHITECT
    ) -> "LicenseStatus":
        """Create a valid license status.

        Args:
            email: The licensed email address
            tier: The license tier (defaults to RESIDENT_ARCHITECT until server provides tier)
        """
        return cls(
            is_valid=True,
            email=email,
            message=f"Licensed to {email}",
            tier=tier,
        )

    @classmethod
    def invalid(cls, message: str) -> "LicenseStatus":
        """Create an invalid license status (defaults to Explorer tier)."""
        return cls(is_valid=False, message=message, tier=LicenseTier.EXPLORER)

    def has_feature(self, feature: str) -> bool:
        """Check if this license has access to a feature.

        Args:
            feature: Feature name (account_explorer, jobs_as_code, migration, import_adopt)

        Returns:
            True if the license tier has access to the feature
        """
        return has_feature_access(self.tier, feature)

    @property
    def tier_display_name(self) -> str:
        """Get the display name for the current tier."""
        return TIER_DISPLAY_NAMES.get(self.tier, "Unknown")


@dataclass
class AuthorizedKey:
    """An authorized public key entry."""
    
    email: str
    pubkey: str  # Base64-encoded Ed25519 public key
    
    @classmethod
    def from_dict(cls, data: dict) -> "AuthorizedKey":
        return cls(
            email=data.get("email", data.get("id", "")),  # Support both 'email' and 'id' fields
            pubkey=data.get("pubkey", ""),
        )


class LicenseManager:
    """Manages license verification for Migration Workflow access.
    
    Authentication requires:
    1. User's email address (MAGELLAN_LICENSE_EMAIL)
    2. User's Ed25519 private key (MAGELLAN_LICENSE_KEY, base64-encoded)
    
    The manager fetches authorized public keys from a GitHub repository and
    verifies that the user's derived public key matches an entry for their email.
    """
    
    def __init__(
        self,
        keys_url: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """Initialize the license manager.
        
        Args:
            keys_url: URL to fetch authorized keys JSON. Defaults to magellan-auth repo.
            timeout: HTTP request timeout in seconds.
        """
        self._keys_url = keys_url or os.getenv(ENV_LICENSE_KEYS_URL, DEFAULT_KEYS_URL)
        self._timeout = timeout
        self._cached_status: Optional[LicenseStatus] = None
    
    def _load_env(self) -> None:
        """Load environment variables from .env files."""
        # Check common locations for .env
        candidates = [
            Path.cwd() / ".env",
            Path.cwd() / ".env.local",
            Path(__file__).parent.parent.parent / ".env",  # Repo root
            Path("/app/.env"),  # Docker mount point
        ]
        for env_path in candidates:
            if env_path.exists():
                load_dotenv(env_path, override=False)
    
    def _get_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """Get license credentials from environment.
        
        Returns:
            Tuple of (email, private_key_base64) or (None, None) if not set.
        """
        self._load_env()
        email = os.getenv(ENV_LICENSE_EMAIL)
        key = os.getenv(ENV_LICENSE_KEY)
        return email, key

    def _is_bypass_enabled(self) -> bool:
        """Check if license verification is bypassed via env flag."""
        self._load_env()
        return os.getenv(ENV_LICENSE_BYPASS, "").lower() in {"1", "true", "yes", "on"}
    
    def _fetch_authorized_keys(self) -> list[AuthorizedKey]:
        """Fetch authorized keys from the remote repository.
        
        Returns:
            List of authorized key entries.
            
        Raises:
            httpx.HTTPError: If the request fails.
        """
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(self._keys_url)
                response.raise_for_status()
                data = response.json()
                
                keys = []
                for entry in data.get("keys", []):
                    try:
                        keys.append(AuthorizedKey.from_dict(entry))
                    except Exception as e:
                        logger.warning(f"Skipping malformed key entry: {e}")
                
                return keys
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch authorized keys from {self._keys_url}: {e}")
            raise
    
    def _derive_public_key(self, private_key_b64: str) -> str:
        """Derive the public key from a private key.
        
        Args:
            private_key_b64: Base64-encoded Ed25519 private key (32 bytes seed).
            
        Returns:
            Base64-encoded public key.
            
        Raises:
            ValueError: If the private key is invalid.
        """
        try:
            from nacl.signing import SigningKey
            
            # Decode the private key seed
            private_bytes = base64.b64decode(private_key_b64)
            if len(private_bytes) != 32:
                raise ValueError(f"Invalid private key length: expected 32 bytes, got {len(private_bytes)}")
            
            # Create signing key and derive public key
            signing_key = SigningKey(private_bytes)
            public_key = signing_key.verify_key
            
            return base64.b64encode(bytes(public_key)).decode("ascii")
        except ImportError:
            raise ImportError("PyNaCl is required for license verification. Install with: pip install pynacl")
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}")
    
    def verify(self, force_refresh: bool = False) -> LicenseStatus:
        """Verify the current license credentials.
        
        Args:
            force_refresh: If True, bypass cached status and re-verify.
            
        Returns:
            LicenseStatus indicating whether access is granted.
        """
        # Return cached status if available
        if self._cached_status is not None and not force_refresh:
            return self._cached_status

        if self._is_bypass_enabled():
            self._cached_status = LicenseStatus.valid(
                "license-bypass", tier=LicenseTier.RESIDENT_ARCHITECT
            )
            self._cached_status.message = "License bypass enabled (Resident Architect access)"
            return self._cached_status
        
        # Get credentials from environment
        email, private_key = self._get_credentials()
        
        if not email:
            self._cached_status = LicenseStatus.invalid(
                "License email not configured. Set MAGELLAN_LICENSE_EMAIL in .env"
            )
            return self._cached_status
        
        if not private_key:
            self._cached_status = LicenseStatus.invalid(
                "License key not configured. Set MAGELLAN_LICENSE_KEY in .env"
            )
            return self._cached_status
        
        # Derive public key from private key
        try:
            derived_pubkey = self._derive_public_key(private_key)
        except ValueError as e:
            self._cached_status = LicenseStatus.invalid(f"Invalid license key: {e}")
            return self._cached_status
        except ImportError as e:
            self._cached_status = LicenseStatus.invalid(str(e))
            return self._cached_status
        
        # Fetch authorized keys from GitHub
        try:
            authorized_keys = self._fetch_authorized_keys()
        except httpx.HTTPError as e:
            self._cached_status = LicenseStatus.invalid(
                f"Unable to verify license (network error): {e}"
            )
            return self._cached_status
        except Exception as e:
            self._cached_status = LicenseStatus.invalid(
                f"Unable to verify license: {e}"
            )
            return self._cached_status
        
        # Find matching key for this email
        email_lower = email.lower().strip()
        for key_entry in authorized_keys:
            if key_entry.email.lower().strip() == email_lower:
                # Email matches, check public key
                if key_entry.pubkey == derived_pubkey:
                    # Default to RESIDENT_ARCHITECT until license server provides tier info
                    self._cached_status = LicenseStatus.valid(
                        email, tier=LicenseTier.RESIDENT_ARCHITECT
                    )
                    logger.info(f"License verified for {email} (tier: Resident Architect)")
                    return self._cached_status
                else:
                    # Email found but key doesn't match
                    self._cached_status = LicenseStatus.invalid(
                        f"License key does not match registration for {email}"
                    )
                    return self._cached_status
        
        # Email not found in authorized keys
        self._cached_status = LicenseStatus.invalid(
            f"Email {email} is not authorized for Migration Workflow access"
        )
        return self._cached_status
    
    def clear_cache(self) -> None:
        """Clear the cached license status."""
        self._cached_status = None
    
    @property
    def is_licensed(self) -> bool:
        """Check if the current credentials are licensed.
        
        This is a convenience property that calls verify() and returns the result.
        """
        return self.verify().is_valid


# Global license manager instance
_license_manager: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    """Get the global license manager instance."""
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager


def check_migration_license() -> LicenseStatus:
    """Check if the Migration Workflow is licensed.
    
    This is the main entry point for license verification.
    
    Returns:
        LicenseStatus with verification result.
    """
    return get_license_manager().verify()


def is_migration_licensed() -> bool:
    """Quick check if Migration Workflow is licensed.

    Returns:
        True if licensed, False otherwise.
    """
    return get_license_manager().is_licensed


def get_current_tier() -> LicenseTier:
    """Get the current license tier.

    Returns:
        The current tier (EXPLORER if no valid license).
    """
    status = get_license_manager().verify()
    return status.tier


def can_access_workflow(workflow: str) -> bool:
    """Check if the current license can access a workflow.

    Args:
        workflow: Workflow name matching TIER_FEATURES keys
                 (account_explorer, jobs_as_code, migration, import_adopt)

    Returns:
        True if the workflow is accessible with the current license.
    """
    status = get_license_manager().verify()
    return status.has_feature(workflow)
