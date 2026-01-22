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


# A valid RSA 2048-bit private key in PKCS#8 PEM format for use as dummy credential.
# This is a randomly generated key with no actual use - purely for Terraform validation.
# Generated once and stored here to ensure consistent dummy credentials across runs.
DUMMY_PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDxqaA1avXCIpS5
IyAY/LafgEQEhV+Jnc5j05rZDP+BG3ZIwdAlUSLogDKMOwjAGYSI3IMG/FvYIixe
kLiz3ZbDF/RdwkEH6DM8Ysysa75pRkGOyBXhDZFHghVc/FlBAob2iCkNOjKy8Eik
+AUfUozgT4fDGbrMSKwTZnFKqmViC1ZrXeXzZx5y40sbybHj4jLjkmGD9BMRnOAi
GamhP4Sdkrgj92S6ffpQJy2VY3wEJ3CcH+mAarlb/XzFZAQW1mteCtlHHbpxWIuN
/wDrpa71T/fb/1CSKQ+AOY+83ZTwQhHmQXt1wUMdupBdXZpu12wl4WcxMmrWUBf2
Q7mJ/tQTAgMBAAECggEBAJ9QqVqt8eiTLaLD4lQ2vhp2z+B/INWzoC21gb8Xz5WI
yjj69MK1M6M9aJWEEae66uHjJcpEMjRRixiopeuF6O8i6qmo94BD9wsXQ0FkInp6
o5uCktH0RNN0karkfd7a0KjUaOPcezH2MJ35GD9nB5KVO7ZGTxx/yFldztBfd0jj
Un30WA5ic1rJ3RU+TlVlXUgTWlYJai0aPiRVT6ucE6FLKN8A8H2DK09xt5EQsI9j
HoLSqX22UL2jA+VJhCABaFlGR9veALP16iaXn6+YudoEi98jBJTMwQSdStjEanKP
gi6OzGriaihHOEKnFBP2CaF1sZfqfSZl+5hLIWRbvqECgYEA/yXsfp2ilEx8ghtf
NmDs7UBEOEw0krOolIFwHnfrdL+bIg8oxXqmQCNbLLrhzJbv5T/OTn7xFI8s5SzV
u8n0YIaun3U+ZYrUyBERNa0tkf9F23BT+Jh3nGFOxltyhdexjOIgZPaH0rXX0XAl
KZ5dtYIFjpX1oLU0JOSCrAN/SBECgYEA8ngtBTh4aGR6nJ1xwVefZ8VG4eMtty8s
CeO6NhZZ8Drhz12TfDj9PC1S9mQPPEx7Xwc/w0J2370bwzW25D5ecM+C8k6lnEm3
o3D5HAcGNyuBqk1l3a93N664izZqzAc+zNp1B+kxPoXlE8DNiH3LQMo/GXjpfHlL
MohwNG14HeMCgYBB/lYgHbeqceoWYOwMjZ9aci/y+8rxUuS8nIoaZ1wQU2rVsWQT
R/juR/bSJ/g1Saj8+7bp2K2Uar/q+uDBdKfvu4Y5GkMsUm9c3AU+g+9wfr1b177w
Ysc1PHn6ljaV5cc3sFk+pAFXf881jbMfA6YrR1kWmzTv/05gaHZf9XubcQKBgQCH
+uG0tdDBKuiggKPVPGDHf5mbAR8YRro56Z76yloyIbOV6fLWjddnMjv+tmrc9D+U
MaqOxO2J2LKDLdKd+mRYe+gCIB08oxL79FWgZEgWFK4pZjKkuszvS2tvl1sZhU6w
8CsF/r+BQvIPu+cIjxO4CDSPAoJfLl7/vgi/Pk1I5QKBgAOS78ZwisHI99n+/r95
Etq02/kN6LbHbwYC6m1sMMPFqPflqUQle5TDjKMwPmLsqGwoT4dQwleb7PJ2Kcro
qoe2dXUBlFwdh2JfhrIWS+kaWbJap1PS3jb1NBb/wdpXyCAGql+Q8J/ywhnzAe/c
SD6TfLyibA7EwovT9hwyr9Ql
-----END PRIVATE KEY-----""".strip()


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
        # Dummy values for sensitive fields by auth_type
        "dummy_sensitive": {
            "password": {
                "password": "dummy_password_placeholder",
            },
            "keypair": {
                "private_key": DUMMY_PRIVATE_KEY_PEM,
            },
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


def build_dummy_credentials_from_source(
    credential_type: str,
    source_values: Dict[str, Any],
) -> Dict[str, Any]:
    """Build dummy credentials by preserving source non-sensitive values and adding dummy secrets.

    This creates a complete credential set that:
    1. Preserves all non-sensitive source values (database, warehouse, role, etc.)
    2. Replaces sensitive fields with syntactically valid placeholders
    3. Ensures required fields are present

    Args:
        credential_type: Credential type key (e.g., 'snowflake')
        source_values: Source values from the original account

    Returns:
        Dictionary with complete credentials suitable for Terraform
    """
    schema = CREDENTIAL_SCHEMAS.get(credential_type)
    if not schema:
        return dict(source_values)

    # Start with all source values
    result = dict(source_values)

    # Always include credential_type
    result["credential_type"] = credential_type

    # Get sensitive fields list
    sensitive_fields = set(schema.get("sensitive", []))

    # Get auth mode info if present
    auth_modes = schema.get("auth_modes", {})
    auth_field = auth_modes.get("field", "auth_type")
    current_auth = result.get(auth_field, auth_modes.get("default", ""))

    # Get dummy values for sensitive fields based on auth type
    dummy_sensitive = schema.get("dummy_sensitive", {})

    # Replace sensitive fields with dummy values
    if current_auth and current_auth in dummy_sensitive:
        # Use auth-specific dummy values
        for field, dummy_value in dummy_sensitive[current_auth].items():
            result[field] = dummy_value
        # Clear other auth mode's sensitive fields
        for auth_mode, auth_fields in dummy_sensitive.items():
            if auth_mode != current_auth:
                for field in auth_fields:
                    if field in result:
                        del result[field]
    else:
        # Fall back to generic dummy values for all sensitive fields
        base_dummy = schema.get("dummy_values", {})
        for field in sensitive_fields:
            if field in base_dummy:
                result[field] = base_dummy[field]
            elif field == "password":
                result[field] = "dummy_password_placeholder"
            elif field == "private_key":
                result[field] = DUMMY_PRIVATE_KEY_PEM
            elif field == "token":
                result[field] = "dummy_token_placeholder"
            elif "secret" in field.lower():
                result[field] = "dummy_secret_placeholder"
            elif "key" in field.lower():
                result[field] = "dummy_key_placeholder"
            else:
                result[field] = f"dummy_{field}_placeholder"

    # Ensure required fields are present (with defaults if needed)
    defaults = schema.get("defaults", {})
    for field in schema.get("required", []):
        if field not in result or not result[field]:
            if field in defaults:
                result[field] = defaults[field]
            elif field in schema.get("dummy_values", {}):
                result[field] = schema["dummy_values"][field]

    return result


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
