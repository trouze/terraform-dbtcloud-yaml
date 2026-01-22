"""Environment credential schemas based on Terraform provider *_credential resources.

These schemas define the fields required for each credential type when configuring
environment-level credentials for deployment. The schemas are aligned with the
dbtcloud Terraform provider's *_credential resources.

Schema structure:
- required: Fields that must be provided
- optional: Fields that can be provided but have defaults
- sensitive: Fields that contain secrets (password, tokens, keys)
- descriptions: Human-readable descriptions for each field
- auth_modes: For credentials with multiple auth options (e.g., password vs keypair)
- conditional: Fields with conditional visibility based on other field values
"""

from typing import Any, Dict, List, Optional


# Credential type schemas - aligned with Terraform provider *_credential resources
# Each schema defines the fields needed for environment credentials
CREDENTIAL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "snowflake": {
        "resource_name": "dbtcloud_snowflake_credential",
        "required": ["auth_type", "num_threads"],
        "optional": [
            "schema",
            "user",
            "password",
            "private_key",
            "private_key_passphrase",
            "database",
            "warehouse",
            "role",
        ],
        "sensitive": ["password", "private_key", "private_key_passphrase"],
        "auth_modes": {
            "field": "auth_type",
            "options": ["password", "keypair"],
            "default": "password",
        },
        "conditional": {
            # Password auth fields
            "password": {"depends_on": "auth_type", "when": "password"},
            # Keypair auth fields
            "private_key": {"depends_on": "auth_type", "when": "keypair"},
            "private_key_passphrase": {"depends_on": "auth_type", "when": "keypair"},
        },
        "descriptions": {
            "auth_type": "Authentication type: 'password' or 'keypair'",
            "schema": "The schema where to create models",
            "user": "Username for Snowflake",
            "password": "Password for the Snowflake account (password auth)",
            "private_key": "Private key for the Snowflake account (keypair auth)",
            "private_key_passphrase": "Passphrase for the private key",
            "database": "The catalog/database to use",
            "warehouse": "The warehouse to use",
            "role": "The role to assume",
            "num_threads": "Number of threads to use",
        },
        "defaults": {
            "schema": "default_schema",
            "user": "default_user",
            "num_threads": 4,
        },
        "dummy_values": {
            "auth_type": "password",
            "schema": "dummy_schema",
            "user": "dummy_user",
            "password": "dummy_password",
            "num_threads": 1,
        },
    },
    "databricks": {
        "resource_name": "dbtcloud_databricks_credential",
        "required": ["token"],
        "optional": ["schema", "catalog", "adapter_type"],
        "sensitive": ["token"],
        "descriptions": {
            "token": "Token for Databricks user",
            "schema": "The schema where to create models",
            "catalog": "The Unity Catalog name (databricks adapter only)",
            "adapter_type": "Adapter type: 'databricks' or 'spark' (deprecated)",
        },
        "defaults": {
            "schema": "default_schema",
            "adapter_type": "databricks",
        },
        "dummy_values": {
            "token": "dummy_token",
            "schema": "dummy_schema",
            "adapter_type": "databricks",
        },
    },
    "bigquery": {
        "resource_name": "dbtcloud_bigquery_credential",
        "required": ["dataset", "num_threads"],
        "optional": [],
        "sensitive": [],
        "descriptions": {
            "dataset": "Default dataset name (schema)",
            "num_threads": "Number of threads to use",
        },
        "defaults": {
            "num_threads": 4,
        },
        "dummy_values": {
            "dataset": "dummy_dataset",
            "num_threads": 1,
        },
    },
    "redshift": {
        "resource_name": "dbtcloud_redshift_credential",
        "required": ["default_schema", "num_threads"],
        "optional": ["username", "password"],
        "sensitive": ["password"],
        "descriptions": {
            "username": "Username for the Redshift account",
            "password": "Password for the Redshift account",
            "default_schema": "Default schema name",
            "num_threads": "Number of threads to use",
        },
        "defaults": {
            "username": "default_user",
            "num_threads": 4,
        },
        "dummy_values": {
            "username": "dummy_user",
            "password": "dummy_password",
            "default_schema": "dummy_schema",
            "num_threads": 1,
        },
    },
    "postgres": {
        "resource_name": "dbtcloud_postgres_credential",
        "required": ["username"],
        "optional": ["default_schema", "password", "type", "target_name", "num_threads"],
        "sensitive": ["password"],
        "descriptions": {
            "type": "Connection type: 'postgres' or 'redshift' (use postgres for AlloyDB)",
            "default_schema": "Default schema name",
            "target_name": "Target name",
            "username": "Username for Postgres/Redshift/AlloyDB",
            "password": "Password for Postgres/Redshift/AlloyDB",
            "num_threads": "Number of threads to use (required for Redshift)",
        },
        "defaults": {
            "type": "postgres",
            "default_schema": "default_schema",
            "target_name": "default",
            "num_threads": 0,
        },
        "dummy_values": {
            "type": "postgres",
            "username": "dummy_user",
            "password": "dummy_password",
            "default_schema": "dummy_schema",
        },
    },
    "athena": {
        "resource_name": "dbtcloud_athena_credential",
        "required": ["aws_access_key_id", "aws_secret_access_key", "schema"],
        "optional": [],
        "sensitive": ["aws_access_key_id", "aws_secret_access_key"],
        "descriptions": {
            "aws_access_key_id": "AWS access key ID for Athena user",
            "aws_secret_access_key": "AWS secret access key for Athena user",
            "schema": "The schema where to create models",
        },
        "defaults": {},
        "dummy_values": {
            "aws_access_key_id": "AKIADUMMYACCESSKEY",
            "aws_secret_access_key": "dummy_secret_access_key",
            "schema": "dummy_schema",
        },
    },
    "fabric": {
        "resource_name": "dbtcloud_fabric_credential",
        "required": ["schema", "adapter_type"],
        "optional": [
            "user",
            "password",
            "tenant_id",
            "client_id",
            "client_secret",
            "schema_authorization",
        ],
        "sensitive": ["password", "client_secret"],
        "auth_modes": {
            "field": "_auth_mode",  # Virtual field for UI
            "options": ["user_password", "service_principal"],
            "default": "user_password",
        },
        "conditional": {
            # User/password auth
            "user": {"depends_on": "_auth_mode", "when": "user_password"},
            "password": {"depends_on": "_auth_mode", "when": "user_password"},
            # Service principal auth
            "tenant_id": {"depends_on": "_auth_mode", "when": "service_principal"},
            "client_id": {"depends_on": "_auth_mode", "when": "service_principal"},
            "client_secret": {"depends_on": "_auth_mode", "when": "service_principal"},
        },
        "descriptions": {
            "user": "Username for AD user/pass authentication",
            "password": "Password for AD user/pass authentication",
            "tenant_id": "Azure AD tenant ID (service principal auth)",
            "client_id": "Azure AD client ID (service principal auth)",
            "client_secret": "Azure AD client secret (service principal auth)",
            "schema": "The schema where to create dbt models",
            "schema_authorization": "Principal who should own the schemas created by dbt",
            "adapter_type": "Adapter type (must be 'fabric')",
        },
        "defaults": {
            "adapter_type": "fabric",
        },
        "dummy_values": {
            "schema": "dummy_schema",
            "adapter_type": "fabric",
            "user": "dummy_user",
            "password": "dummy_password",
        },
    },
    "synapse": {
        "resource_name": "dbtcloud_synapse_credential",
        "required": ["schema", "adapter_type", "authentication"],
        "optional": [
            "user",
            "password",
            "tenant_id",
            "client_id",
            "client_secret",
            "schema_authorization",
        ],
        "sensitive": ["password", "client_secret"],
        "auth_modes": {
            "field": "authentication",
            "options": ["SQL", "ActiveDirectoryPassword", "ServicePrincipal"],
            "default": "SQL",
        },
        "conditional": {
            # SQL/AD Password auth
            "user": {"depends_on": "authentication", "when": ["SQL", "ActiveDirectoryPassword"]},
            "password": {"depends_on": "authentication", "when": ["SQL", "ActiveDirectoryPassword"]},
            # Service principal auth
            "tenant_id": {"depends_on": "authentication", "when": "ServicePrincipal"},
            "client_id": {"depends_on": "authentication", "when": "ServicePrincipal"},
            "client_secret": {"depends_on": "authentication", "when": "ServicePrincipal"},
        },
        "descriptions": {
            "authentication": "Auth type: SQL, ActiveDirectoryPassword, or ServicePrincipal",
            "user": "Username (SQL or AD Password auth)",
            "password": "Password (SQL or AD Password auth)",
            "tenant_id": "Azure AD tenant ID (service principal auth)",
            "client_id": "Azure AD client ID (service principal auth)",
            "client_secret": "Azure AD client secret (service principal auth)",
            "schema": "The schema where to create dbt models",
            "schema_authorization": "Principal who should own the schemas created by dbt",
            "adapter_type": "Adapter type (must be 'synapse')",
        },
        "defaults": {
            "adapter_type": "synapse",
            "authentication": "SQL",
        },
        "dummy_values": {
            "schema": "dummy_schema",
            "adapter_type": "synapse",
            "authentication": "SQL",
            "user": "dummy_user",
            "password": "dummy_password",
        },
    },
    "starburst": {
        "resource_name": "dbtcloud_starburst_credential",
        "required": ["user", "password", "database", "schema"],
        "optional": [],
        "sensitive": ["password"],
        "descriptions": {
            "user": "Username for Starburst/Trino account",
            "password": "Password for Starburst/Trino account",
            "database": "The catalog to connect to",
            "schema": "The schema where to create models",
        },
        "defaults": {},
        "dummy_values": {
            "user": "dummy_user",
            "password": "dummy_password",
            "database": "dummy_catalog",
            "schema": "dummy_schema",
        },
    },
    "spark": {
        "resource_name": "dbtcloud_spark_credential",
        "required": ["token", "schema"],
        "optional": ["target_name"],
        "sensitive": ["token"],
        "descriptions": {
            "token": "Token for Apache Spark user",
            "schema": "The schema where to create models",
            "target_name": "Target name (deprecated)",
        },
        "defaults": {
            "target_name": "default",
        },
        "dummy_values": {
            "token": "dummy_token",
            "schema": "dummy_schema",
        },
    },
    "teradata": {
        "resource_name": "dbtcloud_teradata_credential",
        "required": ["user", "password", "schema"],
        "optional": ["threads"],
        "sensitive": ["password"],
        "descriptions": {
            "user": "Username for Teradata account",
            "password": "Password for Teradata account",
            "schema": "The schema where to create models",
            "threads": "Number of threads to use (default: 1)",
        },
        "defaults": {
            "threads": 1,
        },
        "dummy_values": {
            "user": "dummy_user",
            "password": "dummy_password",
            "schema": "dummy_schema",
            "threads": 1,
        },
    },
}


# Mapping from connection/adapter type strings to credential schema keys
# Used to determine which credential schema to use for a given environment
CONNECTION_TYPE_TO_CREDENTIAL: Dict[str, str] = {
    # Snowflake variants
    "snowflake": "snowflake",
    "snowflake_v0": "snowflake",
    # Databricks
    "databricks": "databricks",
    # BigQuery variants
    "bigquery": "bigquery",
    "bigquery_v0": "bigquery",
    "bigquery_v1": "bigquery",
    # Redshift
    "redshift": "redshift",
    # Postgres/AlloyDB
    "postgres": "postgres",
    "alloydb": "postgres",
    # Athena
    "athena": "athena",
    # Fabric
    "fabric": "fabric",
    # Synapse
    "synapse": "synapse",
    # Starburst/Trino
    "starburst": "starburst",
    "trino": "starburst",
    # Spark
    "spark": "spark",
    "apache_spark": "spark",
    # Teradata
    "teradata": "teradata",
}


def get_credential_schema(connection_type: str) -> Optional[Dict[str, Any]]:
    """Get the credential schema for a given connection type.

    Args:
        connection_type: Connection/adapter type string (e.g., 'snowflake', 'databricks')

    Returns:
        Schema dict or None if not found
    """
    conn_type_lower = connection_type.lower().replace("-", "_")

    # Direct lookup
    if conn_type_lower in CREDENTIAL_SCHEMAS:
        return CREDENTIAL_SCHEMAS[conn_type_lower]

    # Check mapping
    schema_key = CONNECTION_TYPE_TO_CREDENTIAL.get(conn_type_lower)
    if schema_key and schema_key in CREDENTIAL_SCHEMAS:
        return CREDENTIAL_SCHEMAS[schema_key]

    # Fuzzy match on substring
    for key, schema in CREDENTIAL_SCHEMAS.items():
        if key in conn_type_lower:
            return schema

    return None


def get_credential_type_for_connection(connection_type: str) -> Optional[str]:
    """Get the credential type key for a given connection type.

    Args:
        connection_type: Connection/adapter type string

    Returns:
        Credential type key (e.g., 'snowflake') or None
    """
    conn_type_lower = connection_type.lower().replace("-", "_")

    # Direct match
    if conn_type_lower in CREDENTIAL_SCHEMAS:
        return conn_type_lower

    # Check mapping
    schema_key = CONNECTION_TYPE_TO_CREDENTIAL.get(conn_type_lower)
    if schema_key:
        return schema_key

    # Fuzzy match
    for key in CREDENTIAL_SCHEMAS:
        if key in conn_type_lower:
            return key

    return None


def get_dummy_credentials(credential_type: str) -> Dict[str, Any]:
    """Get dummy/placeholder credentials for a credential type.

    Args:
        credential_type: Credential type key (e.g., 'snowflake')

    Returns:
        Dictionary of field -> dummy value
    """
    schema = CREDENTIAL_SCHEMAS.get(credential_type)
    if not schema:
        return {}
    return dict(schema.get("dummy_values", {}))


def get_required_fields(credential_type: str) -> List[str]:
    """Get list of required fields for a credential type.

    Args:
        credential_type: Credential type key

    Returns:
        List of required field names
    """
    schema = CREDENTIAL_SCHEMAS.get(credential_type)
    if not schema:
        return []
    return list(schema.get("required", []))


def get_all_fields(credential_type: str) -> List[str]:
    """Get list of all fields (required + optional) for a credential type.

    Args:
        credential_type: Credential type key

    Returns:
        List of all field names
    """
    schema = CREDENTIAL_SCHEMAS.get(credential_type)
    if not schema:
        return []
    return list(schema.get("required", [])) + list(schema.get("optional", []))


def get_sensitive_fields(credential_type: str) -> List[str]:
    """Get list of sensitive fields for a credential type.

    Args:
        credential_type: Credential type key

    Returns:
        List of sensitive field names
    """
    schema = CREDENTIAL_SCHEMAS.get(credential_type)
    if not schema:
        return []
    return list(schema.get("sensitive", []))


def should_show_field(
    credential_type: str,
    field: str,
    current_values: Dict[str, Any],
) -> bool:
    """Determine if a conditional field should be shown.

    Args:
        credential_type: Credential type key
        field: Field name to check
        current_values: Current form values

    Returns:
        True if field should be shown
    """
    schema = CREDENTIAL_SCHEMAS.get(credential_type)
    if not schema:
        return True

    conditionals = schema.get("conditional", {})
    if field not in conditionals:
        return True  # Non-conditional fields are always shown

    condition = conditionals[field]
    depends_on = condition.get("depends_on")
    expected_value = condition.get("when")

    current_value = current_values.get(depends_on, "")

    # Handle list of acceptable values
    if isinstance(expected_value, list):
        return current_value in expected_value

    # Single value comparison
    return str(current_value) == str(expected_value)


def get_supported_credential_types() -> List[str]:
    """Get list of all supported credential types.

    Returns:
        List of credential type keys
    """
    return list(CREDENTIAL_SCHEMAS.keys())
