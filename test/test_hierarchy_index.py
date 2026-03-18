"""Unit tests for HierarchyIndex component, specifically connection ID lookups."""

import pytest

from importer.web.components.hierarchy_index import HierarchyIndex


@pytest.fixture
def sample_entities():
    """Sample entities with connections and environments for testing."""
    return [
        # Account
        {
            "element_mapping_id": "ACC_001",
            "element_type_code": "ACC",
            "name": "Test Account",
            "dbt_id": 12345,
        },
        # Connections
        {
            "element_mapping_id": "CON_001",
            "element_type_code": "CON",
            "name": "Snowflake Production",
            "key": "snowflake_prod",
            "dbt_id": 100,
        },
        {
            "element_mapping_id": "CON_002",
            "element_type_code": "CON",
            "name": "Snowflake Dev",
            "key": "snowflake_dev",
            "dbt_id": 200,
        },
        # Connection with fallback key (simulating orphaned connection)
        {
            "element_mapping_id": "CON_003",
            "element_type_code": "CON",
            "name": "Connection 1559",
            "key": "connection_1559",
            "dbt_id": 1559,
        },
        # Project
        {
            "element_mapping_id": "PRJ_001",
            "element_type_code": "PRJ",
            "name": "Test Project",
            "key": "test_project",
            "project_key": "test_project",
            "dbt_id": 500,
        },
        # Environment with connection_key and connection_id
        {
            "element_mapping_id": "ENV_001",
            "element_type_code": "ENV",
            "name": "Production",
            "key": "production",
            "dbt_id": 1000,
            "parent_project_id": "PRJ_001",
            "connection_key": "snowflake_prod",
            "connection_id": 100,
        },
        # Environment with fallback connection key
        {
            "element_mapping_id": "ENV_002",
            "element_type_code": "ENV",
            "name": "Dev Environment",
            "key": "dev",
            "dbt_id": 1001,
            "parent_project_id": "PRJ_001",
            "connection_key": "connection_1559",
            "connection_id": 1559,
        },
        # Environment without connection_id (backward compatibility)
        {
            "element_mapping_id": "ENV_003",
            "element_type_code": "ENV",
            "name": "Legacy Environment",
            "key": "legacy",
            "dbt_id": 1002,
            "parent_project_id": "PRJ_001",
            "connection_key": "snowflake_dev",
            # No connection_id - tests backward compatibility
        },
        # Credential
        {
            "element_mapping_id": "CRD_001",
            "element_type_code": "CRD",
            "name": "Production Credential",
            "dbt_id": 901,
            "parent_environment_id": "ENV_001",
        },
    ]


class TestHierarchyIndexConnectionLookup:
    """Tests for connection ID-based lookup functionality."""

    def test_get_connection_by_id_returns_mapping(self, sample_entities):
        """Test that get_connection_by_id returns correct mapping ID."""
        index = HierarchyIndex(sample_entities)
        
        # Should find connection by ID
        mapping_id = index.get_connection_by_id(100)
        assert mapping_id == "CON_001"
        
        mapping_id = index.get_connection_by_id(200)
        assert mapping_id == "CON_002"
        
        mapping_id = index.get_connection_by_id(1559)
        assert mapping_id == "CON_003"

    def test_get_connection_by_id_returns_none_for_unknown(self, sample_entities):
        """Test that get_connection_by_id returns None for unknown IDs."""
        index = HierarchyIndex(sample_entities)
        
        # Should return None for non-existent connection ID
        mapping_id = index.get_connection_by_id(99999)
        assert mapping_id is None

    def test_connection_by_key_still_works(self, sample_entities):
        """Test that connection lookup by key still works alongside ID lookup."""
        index = HierarchyIndex(sample_entities)
        
        # Key-based lookup via _connection_by_key
        assert index._connection_by_key.get("snowflake_prod") == "CON_001"
        assert index._connection_by_key.get("snowflake_dev") == "CON_002"
        assert index._connection_by_key.get("connection_1559") == "CON_003"

    def test_both_indexes_populated(self, sample_entities):
        """Test that both ID and key indexes are populated correctly."""
        index = HierarchyIndex(sample_entities)
        
        # Both indexes should have entries
        assert len(index._connection_by_key) == 3
        assert len(index._connection_by_id) == 3
        
        # ID index should map to same entities as key index
        for conn_id, mapping_id in index._connection_by_id.items():
            entity = index.get_entity(mapping_id)
            assert entity is not None
            assert entity.get("element_type_code") == "CON"
            assert entity.get("dbt_id") == conn_id

    def test_index_clears_on_rebuild(self, sample_entities):
        """Test that indexes are cleared when rebuilding."""
        index = HierarchyIndex(sample_entities)
        
        # Verify initial state
        assert len(index._connection_by_id) == 3
        
        # Rebuild with empty list
        index.build_index([])
        
        # Both indexes should be empty
        assert len(index._connection_by_id) == 0
        assert len(index._connection_by_key) == 0

    def test_environment_has_connection_id_field(self, sample_entities):
        """Test that environment entities include connection_id in indexed data."""
        index = HierarchyIndex(sample_entities)
        
        # Get environment entity
        env = index.get_entity("ENV_001")
        assert env is not None
        assert env.get("connection_id") == 100
        assert env.get("connection_key") == "snowflake_prod"
        
        # Check fallback key environment
        env2 = index.get_entity("ENV_002")
        assert env2 is not None
        assert env2.get("connection_id") == 1559
        assert env2.get("connection_key") == "connection_1559"

    def test_backward_compatibility_no_connection_id(self, sample_entities):
        """Test that environments without connection_id still work."""
        index = HierarchyIndex(sample_entities)
        
        # Legacy environment without connection_id
        env = index.get_entity("ENV_003")
        assert env is not None
        assert env.get("connection_key") == "snowflake_dev"
        assert env.get("connection_id") is None  # Not set

    def test_get_credential_by_id_returns_mapping(self, sample_entities):
        """Test that get_credential_by_id returns the credential mapping ID."""
        index = HierarchyIndex(sample_entities)

        assert index.get_credential_by_id(901) == "CRD_001"
        assert index.get_credential_by_id(99999) is None


class TestHierarchyIndexBasicFunctionality:
    """Tests to ensure basic HierarchyIndex functionality still works."""

    def test_get_entity(self, sample_entities):
        """Test basic entity retrieval."""
        index = HierarchyIndex(sample_entities)
        
        entity = index.get_entity("PRJ_001")
        assert entity is not None
        assert entity.get("name") == "Test Project"

    def test_get_entities_by_type(self, sample_entities):
        """Test getting entities by type code."""
        index = HierarchyIndex(sample_entities)
        
        cons = index.get_entities_by_type("CON")
        assert len(cons) == 3
        
        envs = index.get_entities_by_type("ENV")
        assert len(envs) == 3

    def test_parent_child_relationships(self, sample_entities):
        """Test that parent-child relationships are correctly built."""
        index = HierarchyIndex(sample_entities)
        
        # Environments should be children of projects
        children = index.get_children("PRJ_001")
        assert "ENV_001" in children
        assert "ENV_002" in children
        assert "ENV_003" in children
        
        # Environments should have project as parent
        parents = index.get_parents("ENV_001")
        assert "PRJ_001" in parents


def test_profile_parent_is_project_and_depth_is_two():
    """Profiles are project-scoped resources in the hierarchy."""
    entities = [
        {
            "element_mapping_id": "PRJ_001",
            "element_type_code": "PRJ",
            "name": "Test Project",
            "key": "test_project",
            "project_key": "test_project",
        },
        {
            "element_mapping_id": "PRF_001",
            "element_type_code": "PRF",
            "name": "Prod Profile",
            "key": "test_project_prod_profile",
            "project_key": "test_project",
            "parent_project_id": "PRJ_001",
            "connection_key": "snowflake_prod",
        },
    ]

    index = HierarchyIndex(entities)

    assert index.get_parents("PRF_001") == {"PRJ_001"}
    assert index.get_depth("PRF_001") == 2


def test_environment_and_profile_are_linked():
    """Profiles pull in their linked environment, connection, credential, and ext attrs."""
    entities = [
        {
            "element_mapping_id": "PRJ_001",
            "element_type_code": "PRJ",
            "name": "Test Project",
            "key": "test_project",
            "project_key": "test_project",
        },
        {
            "element_mapping_id": "PRF_001",
            "element_type_code": "PRF",
            "name": "Prod Profile",
            "key": "test_project_prod_profile",
            "project_key": "test_project",
            "parent_project_id": "PRJ_001",
            "profile_key": "prod_profile",
            "connection_key": "snowflake_prod",
            "connection_id": 100,
            "credentials_id": 901,
            "extended_attributes_key": "ext_attrs_prod",
        },
        {
            "element_mapping_id": "ENV_001",
            "element_type_code": "ENV",
            "name": "Production",
            "key": "test_project_production",
            "project_key": "test_project",
            "parent_project_id": "PRJ_001",
            "primary_profile_key": "prod_profile",
        },
        {
            "element_mapping_id": "CON_001",
            "element_type_code": "CON",
            "name": "Snowflake Production",
            "key": "snowflake_prod",
            "dbt_id": 100,
        },
        {
            "element_mapping_id": "CRD_001",
            "element_type_code": "CRD",
            "name": "Production Credential",
            "dbt_id": 901,
            "parent_environment_id": "ENV_001",
        },
        {
            "element_mapping_id": "EXTATTR_001",
            "element_type_code": "EXTATTR",
            "name": "ext_attrs_prod",
            "key": "test_project_ext_attrs_prod",
            "extended_attributes_key": "ext_attrs_prod",
            "project_key": "test_project",
            "parent_project_id": "PRJ_001",
        },
    ]

    index = HierarchyIndex(entities)

    assert index.get_linked_entities("ENV_001") == {"PRF_001"}
    assert index.get_linked_entities("PRF_001") == {
        "CON_001",
        "CRD_001",
        "ENV_001",
        "EXTATTR_001",
    }


def test_profile_links_environment_via_credential_parent():
    """Profiles can discover their environment through the credential parent edge."""
    entities = [
        {
            "element_mapping_id": "PRJ_001",
            "element_type_code": "PRJ",
            "name": "Test Project",
            "key": "test_project",
            "project_key": "test_project",
        },
        {
            "element_mapping_id": "PRF_001",
            "element_type_code": "PRF",
            "name": "CI Profile",
            "key": "ci_profile",
            "project_key": "test_project",
            "parent_project_id": "PRJ_001",
            "profile_key": "ci_profile",
            "connection_key": "snowflake_ci",
            "connection_id": 100,
            "credentials_key": "ci_environment",
            "credentials_id": 901,
        },
        {
            "element_mapping_id": "ENV_001",
            "element_type_code": "ENV",
            "name": "CI Environment",
            "key": "ci_environment",
            "project_key": "test_project",
            "parent_project_id": "PRJ_001",
            "primary_profile_key": None,
        },
        {
            "element_mapping_id": "CRD_001",
            "element_type_code": "CRD",
            "name": "CI Credential",
            "dbt_id": 901,
            "parent_environment_id": "ENV_001",
        },
        {
            "element_mapping_id": "CON_001",
            "element_type_code": "CON",
            "name": "Snowflake CI",
            "key": "snowflake_ci",
            "dbt_id": 100,
        },
    ]

    index = HierarchyIndex(entities)

    assert index.get_linked_entities("PRF_001") == {"CON_001", "CRD_001", "ENV_001"}


def test_profile_falls_back_to_project_environments_when_no_direct_edge_exists():
    """Profiles retain project environments even when report items omit explicit links."""
    entities = [
        {
            "element_mapping_id": "PRJ_001",
            "element_type_code": "PRJ",
            "name": "Test Project",
            "key": "test_project",
            "project_key": "test_project",
        },
        {
            "element_mapping_id": "PRF_001",
            "element_type_code": "PRF",
            "name": "Orphan Profile",
            "key": "orphan_profile",
            "project_key": "test_project",
            "parent_project_id": "PRJ_001",
            "profile_key": "orphan_profile",
            "connection_key": "snowflake_prod",
            "connection_id": 100,
            "credentials_key": "cred_123",
            "credentials_id": 123,
        },
        {
            "element_mapping_id": "ENV_001",
            "element_type_code": "ENV",
            "name": "Development",
            "key": "development",
            "project_key": "test_project",
            "parent_project_id": "PRJ_001",
            "primary_profile_key": None,
        },
        {
            "element_mapping_id": "ENV_002",
            "element_type_code": "ENV",
            "name": "Production",
            "key": "prod",
            "project_key": "test_project",
            "parent_project_id": "PRJ_001",
            "primary_profile_key": None,
        },
        {
            "element_mapping_id": "CON_001",
            "element_type_code": "CON",
            "name": "Snowflake Production",
            "key": "snowflake_prod",
            "dbt_id": 100,
        },
    ]

    index = HierarchyIndex(entities)

    assert index.get_linked_entities("PRF_001") == {"CON_001", "ENV_001", "ENV_002"}
