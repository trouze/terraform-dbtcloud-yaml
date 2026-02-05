"""Unit tests for key format handling.

These tests ensure consistent key formatting across the application:
- PRJ: prefix for projects
- REPO: prefix for repositories (covers both dbtcloud_repository and dbtcloud_project_repository)
- Legacy key migration (bare keys → prefixed keys)
- Key parsing and validation

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.6 Unit Tests
"""

import pytest
from typing import Optional, Tuple

# Key format constants (should be extracted to a shared module)
KEY_PREFIXES = {
    "PRJ": "Project",
    "REPO": "Repository",
    "ENV": "Environment",
    "JOB": "Job",
}

VALID_PREFIXES = frozenset(KEY_PREFIXES.keys())


def format_resource_key(resource_type: str, resource_name: str) -> str:
    """Format a resource key with the appropriate prefix.
    
    Args:
        resource_type: Resource type code (PRJ, REPO, ENV, JOB)
        resource_name: Resource name (e.g., "my_project")
        
    Returns:
        Formatted key (e.g., "PRJ:my_project")
        
    Raises:
        ValueError: If resource_type is not a valid prefix
    """
    if resource_type not in VALID_PREFIXES:
        raise ValueError(f"Invalid resource type: {resource_type}. Must be one of {VALID_PREFIXES}")
    return f"{resource_type}:{resource_name}"


def parse_resource_key(key: str) -> Tuple[Optional[str], str]:
    """Parse a resource key into its type and name components.
    
    Handles both prefixed keys (PRJ:my_project) and legacy bare keys (my_project).
    
    Args:
        key: Resource key to parse
        
    Returns:
        Tuple of (resource_type, resource_name). resource_type is None for legacy keys.
    """
    if ":" in key:
        parts = key.split(":", 1)
        prefix = parts[0]
        if prefix in VALID_PREFIXES:
            return (prefix, parts[1])
    # Legacy bare key
    return (None, key)


def migrate_legacy_key(key: str, default_type: str = "PRJ") -> str:
    """Migrate a legacy bare key to prefixed format.
    
    If the key already has a valid prefix, returns it unchanged.
    If the key is bare (no prefix), adds the default_type prefix.
    
    Args:
        key: Resource key (may or may not have prefix)
        default_type: Prefix to add for bare keys
        
    Returns:
        Key with prefix
    """
    resource_type, resource_name = parse_resource_key(key)
    if resource_type is not None:
        # Already has prefix
        return key
    # Add default prefix
    return format_resource_key(default_type, resource_name)


def is_valid_key(key: str, require_prefix: bool = True) -> bool:
    """Check if a key is valid.
    
    Args:
        key: Resource key to validate
        require_prefix: If True, bare keys are invalid
        
    Returns:
        True if key is valid
    """
    if not key:
        return False
    
    resource_type, resource_name = parse_resource_key(key)
    
    if require_prefix and resource_type is None:
        return False
    
    if not resource_name:
        return False
    
    return True


def get_resource_type_label(key: str) -> str:
    """Get human-readable label for a resource key's type.
    
    Args:
        key: Resource key
        
    Returns:
        Human-readable type label (e.g., "Project", "Repository")
    """
    resource_type, _ = parse_resource_key(key)
    if resource_type is None:
        return "Unknown"
    return KEY_PREFIXES.get(resource_type, resource_type)


# =============================================================================
# Tests: format_resource_key
# =============================================================================

class TestFormatResourceKey:
    """Tests for format_resource_key function."""
    
    def test_format_project_key(self):
        """Test formatting project key."""
        result = format_resource_key("PRJ", "my_project")
        assert result == "PRJ:my_project"
    
    def test_format_repo_key(self):
        """Test formatting repository key."""
        result = format_resource_key("REPO", "my_repo")
        assert result == "REPO:my_repo"
    
    def test_format_env_key(self):
        """Test formatting environment key."""
        result = format_resource_key("ENV", "production")
        assert result == "ENV:production"
    
    def test_format_job_key(self):
        """Test formatting job key."""
        result = format_resource_key("JOB", "daily_sync")
        assert result == "JOB:daily_sync"
    
    def test_preserves_special_characters(self):
        """Test that special characters in name are preserved."""
        result = format_resource_key("PRJ", "my-project_v2.0")
        assert result == "PRJ:my-project_v2.0"
    
    def test_invalid_resource_type_raises(self):
        """Test that invalid resource type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid resource type"):
            format_resource_key("INVALID", "name")
    
    def test_case_sensitive(self):
        """Test that prefixes are case-sensitive."""
        with pytest.raises(ValueError):
            format_resource_key("prj", "name")  # Lowercase not valid


# =============================================================================
# Tests: parse_resource_key
# =============================================================================

class TestParseResourceKey:
    """Tests for parse_resource_key function."""
    
    def test_parse_project_key(self):
        """Test parsing prefixed project key."""
        resource_type, resource_name = parse_resource_key("PRJ:my_project")
        assert resource_type == "PRJ"
        assert resource_name == "my_project"
    
    def test_parse_repo_key(self):
        """Test parsing prefixed repository key."""
        resource_type, resource_name = parse_resource_key("REPO:my_repo")
        assert resource_type == "REPO"
        assert resource_name == "my_repo"
    
    def test_parse_legacy_bare_key(self):
        """Test parsing legacy bare key (no prefix)."""
        resource_type, resource_name = parse_resource_key("my_project")
        assert resource_type is None
        assert resource_name == "my_project"
    
    def test_parse_key_with_colon_in_name(self):
        """Test parsing key where name contains colon."""
        resource_type, resource_name = parse_resource_key("PRJ:my:project:name")
        assert resource_type == "PRJ"
        assert resource_name == "my:project:name"  # Everything after first colon
    
    def test_parse_empty_name_after_prefix(self):
        """Test parsing key with empty name after prefix."""
        resource_type, resource_name = parse_resource_key("PRJ:")
        assert resource_type == "PRJ"
        assert resource_name == ""
    
    def test_parse_invalid_prefix_treated_as_bare(self):
        """Test that invalid prefix is treated as part of bare key."""
        resource_type, resource_name = parse_resource_key("INVALID:something")
        assert resource_type is None
        assert resource_name == "INVALID:something"


# =============================================================================
# Tests: migrate_legacy_key
# =============================================================================

class TestMigrateLegacyKey:
    """Tests for migrate_legacy_key function."""
    
    def test_migrate_bare_key_to_project(self):
        """Test migrating bare key to PRJ prefix."""
        result = migrate_legacy_key("my_project")
        assert result == "PRJ:my_project"
    
    def test_migrate_bare_key_to_repo(self):
        """Test migrating bare key with REPO default."""
        result = migrate_legacy_key("my_repo", default_type="REPO")
        assert result == "REPO:my_repo"
    
    def test_preserves_existing_prefix(self):
        """Test that already-prefixed keys are unchanged."""
        result = migrate_legacy_key("PRJ:my_project")
        assert result == "PRJ:my_project"
    
    def test_preserves_different_existing_prefix(self):
        """Test that existing REPO prefix is preserved even with PRJ default."""
        result = migrate_legacy_key("REPO:my_repo", default_type="PRJ")
        assert result == "REPO:my_repo"
    
    def test_handles_empty_string(self):
        """Test migration of empty string."""
        result = migrate_legacy_key("")
        assert result == "PRJ:"


# =============================================================================
# Tests: is_valid_key
# =============================================================================

class TestIsValidKey:
    """Tests for is_valid_key function."""
    
    def test_valid_prefixed_key(self):
        """Test that valid prefixed key passes."""
        assert is_valid_key("PRJ:my_project") is True
    
    def test_valid_repo_key(self):
        """Test that valid REPO key passes."""
        assert is_valid_key("REPO:my_repo") is True
    
    def test_bare_key_invalid_when_prefix_required(self):
        """Test that bare key fails when prefix required."""
        assert is_valid_key("my_project", require_prefix=True) is False
    
    def test_bare_key_valid_when_prefix_not_required(self):
        """Test that bare key passes when prefix not required."""
        assert is_valid_key("my_project", require_prefix=False) is True
    
    def test_empty_key_invalid(self):
        """Test that empty key is invalid."""
        assert is_valid_key("") is False
        assert is_valid_key("", require_prefix=False) is False
    
    def test_prefix_only_invalid(self):
        """Test that prefix-only key (no name) is invalid."""
        assert is_valid_key("PRJ:") is False


# =============================================================================
# Tests: get_resource_type_label
# =============================================================================

class TestGetResourceTypeLabel:
    """Tests for get_resource_type_label function."""
    
    def test_project_label(self):
        """Test label for project key."""
        assert get_resource_type_label("PRJ:my_project") == "Project"
    
    def test_repo_label(self):
        """Test label for repository key."""
        assert get_resource_type_label("REPO:my_repo") == "Repository"
    
    def test_env_label(self):
        """Test label for environment key."""
        assert get_resource_type_label("ENV:production") == "Environment"
    
    def test_job_label(self):
        """Test label for job key."""
        assert get_resource_type_label("JOB:daily") == "Job"
    
    def test_bare_key_label(self):
        """Test label for bare key."""
        assert get_resource_type_label("my_project") == "Unknown"


# =============================================================================
# Tests: Key Format Consistency (Integration)
# =============================================================================

class TestKeyFormatConsistency:
    """Integration tests ensuring key format consistency across operations."""
    
    def test_roundtrip_format_parse(self):
        """Test that format → parse is lossless."""
        for prefix in VALID_PREFIXES:
            name = f"test_{prefix.lower()}_resource"
            key = format_resource_key(prefix, name)
            parsed_type, parsed_name = parse_resource_key(key)
            
            assert parsed_type == prefix
            assert parsed_name == name
    
    def test_migrate_then_parse(self):
        """Test that migrated keys can be parsed correctly."""
        legacy_keys = ["my_project", "another_resource", "test_123"]
        
        for legacy_key in legacy_keys:
            migrated = migrate_legacy_key(legacy_key)
            resource_type, resource_name = parse_resource_key(migrated)
            
            assert resource_type == "PRJ"
            assert resource_name == legacy_key
    
    def test_all_migrated_keys_are_valid(self):
        """Test that all migrated keys pass validation."""
        legacy_keys = ["proj1", "proj2", "my-project", "test_resource_v2"]
        
        for legacy_key in legacy_keys:
            migrated = migrate_legacy_key(legacy_key)
            assert is_valid_key(migrated, require_prefix=True)


# =============================================================================
# Tests: REPO Key Special Cases
# =============================================================================

class TestREPOKeySpecialCases:
    """Tests for REPO key handling.
    
    REPO keys are special because they represent two Terraform resources:
    - dbtcloud_repository
    - dbtcloud_project_repository
    
    A single REPO: key should result in protection changes for both.
    """
    
    def test_repo_key_format(self):
        """Test REPO key formatting."""
        key = format_resource_key("REPO", "my_repo")
        assert key == "REPO:my_repo"
    
    def test_repo_key_distinct_from_prj(self):
        """Test that REPO and PRJ keys for same name are distinct."""
        repo_key = format_resource_key("REPO", "my_resource")
        prj_key = format_resource_key("PRJ", "my_resource")
        
        assert repo_key != prj_key
        assert repo_key == "REPO:my_resource"
        assert prj_key == "PRJ:my_resource"
    
    def test_repo_key_label(self):
        """Test that REPO key has correct label."""
        label = get_resource_type_label("REPO:my_repo")
        assert label == "Repository"


# =============================================================================
# Tests: Backward Compatibility
# =============================================================================

class TestBackwardCompatibility:
    """Tests ensuring backward compatibility with legacy keys."""
    
    def test_legacy_intent_file_keys(self):
        """Test that legacy intent file keys can be migrated."""
        # Simulate keys from an old intent file
        legacy_intents = {
            "my_project": {"protected": True},
            "other_project": {"protected": False},
            "dbt_ep_my_repo": {"protected": True},
        }
        
        # Migrate to new format
        migrated = {}
        for key, intent in legacy_intents.items():
            # Detect type heuristically (in practice, this would use more context)
            if "repo" in key.lower() or "dbt_ep" in key:
                migrated_key = migrate_legacy_key(key, default_type="REPO")
            else:
                migrated_key = migrate_legacy_key(key, default_type="PRJ")
            migrated[migrated_key] = intent
        
        # Verify all migrated keys are valid
        for key in migrated.keys():
            assert is_valid_key(key, require_prefix=True)
    
    def test_mixed_old_new_keys(self):
        """Test system handles mix of old and new format keys."""
        keys = [
            "PRJ:new_project",  # New format
            "old_project",      # Legacy format
            "REPO:new_repo",    # New format
        ]
        
        normalized_keys = []
        for key in keys:
            resource_type, _ = parse_resource_key(key)
            if resource_type is None:
                # Legacy key - migrate
                normalized_keys.append(migrate_legacy_key(key))
            else:
                # Already new format
                normalized_keys.append(key)
        
        # All should now be valid prefixed keys
        for key in normalized_keys:
            assert is_valid_key(key, require_prefix=True)
