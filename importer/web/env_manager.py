"""Environment file (.env) management utilities."""

from pathlib import Path
from typing import Optional, Tuple

from dotenv import dotenv_values, set_key

from importer.web.state import AccountInfo


def detect_token_type(api_token: str) -> str:
    """Detect token type from prefix.

    Args:
        api_token: The API token string

    Returns:
        "user_token" if token starts with "dbtu_" (PAT),
        "service_token" if token starts with "dbtc_" or other prefix.
    """
    if not api_token:
        return "service_token"
    if api_token.startswith("dbtu_"):
        return "user_token"
    # dbtc_ is service token, and treat unknown prefixes as service token
    return "service_token"


def find_env_file(start_dir: Optional[str] = None) -> Path:
    """Find the .env file, starting from given directory or current working directory.

    Searches upward through parent directories until finding a .env file
    or reaching the filesystem root.
    """
    if start_dir:
        current = Path(start_dir).resolve()
    else:
        current = Path.cwd()

    while current != current.parent:
        env_path = current / ".env"
        if env_path.exists():
            return env_path
        current = current.parent

    # Default to .env in original directory
    return Path(start_dir or ".") / ".env"


def load_env_values(env_path: Optional[str] = None) -> dict:
    """Load all values from a .env file.

    Args:
        env_path: Path to .env file. If None, searches for one.

    Returns:
        Dictionary of environment variable names to values.
    """
    if env_path:
        path = Path(env_path)
    else:
        path = find_env_file()

    if not path.exists():
        return {}

    return dotenv_values(path)


def parse_env_content(content: str) -> dict:
    """Parse .env content from a string (for uploaded files).

    Args:
        content: String content of a .env file

    Returns:
        Dictionary of environment variable names to values.
    """
    values = {}
    for line in content.splitlines():
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        # Handle KEY=VALUE format
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            values[key] = value
    return values


def load_source_credentials_from_content(content: str) -> dict:
    """Load source dbt Cloud credentials from .env content string.

    Args:
        content: String content of a .env file

    Returns:
        Dictionary with keys: host_url, account_id, api_token, token_type
    """
    values = parse_env_content(content)
    api_token = values.get("DBT_SOURCE_API_TOKEN", "")
    
    # Always auto-detect token type from prefix (ignore stored value)
    # Token prefixes are authoritative: dbtc_* = service_token, dbtu_* = user_token
    token_type = detect_token_type(api_token)

    return {
        "host_url": values.get("DBT_SOURCE_HOST_URL", "https://cloud.getdbt.com"),
        "account_id": values.get("DBT_SOURCE_ACCOUNT_ID", ""),
        "api_token": api_token,
        "token_type": token_type,
    }


def load_target_credentials_from_content(content: str) -> dict:
    """Load target dbt Cloud credentials from .env content string.

    Args:
        content: String content of a .env file

    Returns:
        Dictionary with keys: host_url, account_id, api_token, token_type
    """
    values = parse_env_content(content)
    api_token = values.get("DBT_TARGET_API_TOKEN", "")
    
    # Always auto-detect token type from prefix (ignore stored value)
    # Token prefixes are authoritative: dbtc_* = service_token, dbtu_* = user_token
    token_type = detect_token_type(api_token)

    return {
        "host_url": values.get("DBT_TARGET_HOST_URL", "https://cloud.getdbt.com"),
        "account_id": values.get("DBT_TARGET_ACCOUNT_ID", ""),
        "api_token": api_token,
        "token_type": token_type,
    }


def load_source_credentials(env_path: Optional[str] = None) -> dict:
    """Load source dbt Cloud credentials from .env file.

    Returns:
        Dictionary with keys: host_url, account_id, api_token, token_type
    """
    values = load_env_values(env_path)
    api_token = values.get("DBT_SOURCE_API_TOKEN", "")
    
    # Always auto-detect token type from prefix (ignore stored value)
    # Token prefixes are authoritative: dbtc_* = service_token, dbtu_* = user_token
    token_type = detect_token_type(api_token)

    return {
        "host_url": values.get("DBT_SOURCE_HOST_URL", "https://cloud.getdbt.com"),
        "account_id": values.get("DBT_SOURCE_ACCOUNT_ID", ""),
        "api_token": api_token,
        "token_type": token_type,
    }


def load_target_credentials(env_path: Optional[str] = None) -> dict:
    """Load target dbt Cloud credentials from .env file.

    Returns:
        Dictionary with keys: host_url, account_id, api_token, token_type
    """
    values = load_env_values(env_path)
    api_token = values.get("DBT_TARGET_API_TOKEN", "")
    
    # Always auto-detect token type from prefix (ignore stored value)
    # Token prefixes are authoritative: dbtc_* = service_token, dbtu_* = user_token
    token_type = detect_token_type(api_token)

    return {
        "host_url": values.get("DBT_TARGET_HOST_URL", "https://cloud.getdbt.com"),
        "account_id": values.get("DBT_TARGET_ACCOUNT_ID", ""),
        "api_token": api_token,
        "token_type": token_type,
    }


def save_source_credentials(
    host_url: str,
    account_id: str,
    api_token: str,
    token_type: Optional[str] = None,
    env_path: Optional[str] = None,
) -> Path:
    """Save source dbt Cloud credentials to .env file.

    Creates the file if it doesn't exist. Preserves existing values.

    Args:
        host_url: dbt Cloud host URL
        account_id: dbt Cloud account ID
        api_token: API token (PAT or service token)
        token_type: Token type - auto-detected from prefix if None
        env_path: Path to .env file. If None, uses default location.

    Returns:
        Path to the saved .env file.
    """
    if env_path:
        path = Path(env_path)
    else:
        path = find_env_file()

    # Create file if it doesn't exist
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    # Auto-detect token type if not provided
    if token_type is None:
        token_type = detect_token_type(api_token)

    # Use python-dotenv's set_key to preserve formatting
    set_key(str(path), "DBT_SOURCE_HOST_URL", host_url)
    set_key(str(path), "DBT_SOURCE_ACCOUNT_ID", account_id)
    set_key(str(path), "DBT_SOURCE_API_TOKEN", api_token)
    set_key(str(path), "DBT_SOURCE_TOKEN_TYPE", token_type)

    return path


def save_target_credentials(
    host_url: str,
    account_id: str,
    api_token: str,
    token_type: Optional[str] = None,
    env_path: Optional[str] = None,
) -> Path:
    """Save target dbt Cloud credentials to .env file.

    Creates the file if it doesn't exist. Preserves existing values.

    Args:
        host_url: dbt Cloud host URL
        account_id: dbt Cloud account ID
        api_token: API token
        token_type: Token type - auto-detected from prefix if None
        env_path: Path to .env file. If None, uses default location.

    Returns:
        Path to the saved .env file.
    """
    if env_path:
        path = Path(env_path)
    else:
        path = find_env_file()

    # Create file if it doesn't exist
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    # Auto-detect token type if not provided
    if token_type is None:
        token_type = detect_token_type(api_token)

    set_key(str(path), "DBT_TARGET_HOST_URL", host_url)
    set_key(str(path), "DBT_TARGET_ACCOUNT_ID", account_id)
    set_key(str(path), "DBT_TARGET_API_TOKEN", api_token)
    set_key(str(path), "DBT_TARGET_TOKEN_TYPE", token_type)

    return path


def load_connection_configs(env_path: Optional[str] = None) -> dict:
    """Load connection provider configurations from .env file.

    Looks for variables matching pattern: DBT_CONNECTION_{NAME}_{FIELD}
    
    Field names can be multi-part (e.g., OAUTH_CLIENT_ID, HTTP_PATH) so we
    match against known field names to correctly split connection name from field.

    Returns:
        Nested dictionary: {connection_name: {field: value}}
    """
    values = load_env_values(env_path)
    configs = {}
    
    # Known field names (in uppercase, may have underscores)
    # These are all the fields used in CONNECTION_SCHEMAS and Terraform provider
    known_fields = {
        # Common fields
        "HOST", "PORT", "DATABASE", "DBNAME", "HOSTNAME",
        # Snowflake
        "ACCOUNT", "WAREHOUSE", "ROLE", "CLIENT_SESSION_KEEP_ALIVE", "ALLOW_SSO",
        "OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET",
        # Databricks
        "HTTP_PATH", "CATALOG", "CLIENT_ID", "CLIENT_SECRET",
        # BigQuery
        "GCP_PROJECT_ID", "PROJECT_ID", "LOCATION", "TIMEOUT_SECONDS", "PRIORITY",
        "PRIVATE_KEY_ID", "PRIVATE_KEY", "CLIENT_EMAIL", "AUTH_URI", "TOKEN_URI",
        "AUTH_PROVIDER_X509_CERT_URL", "CLIENT_X509_CERT_URL",
        "APPLICATION_ID", "APPLICATION_SECRET", "SCOPES",
        "DEPLOYMENT_ENV_AUTH_TYPE", "USE_LATEST_ADAPTER",
        "MAXIMUM_BYTES_BILLED", "RETRIES", "EXECUTION_PROJECT",
        "IMPERSONATE_SERVICE_ACCOUNT",
        "JOB_CREATION_TIMEOUT_SECONDS", "JOB_EXECUTION_TIMEOUT_SECONDS", "JOB_RETRY_DEADLINE_SECONDS",
        "DATAPROC_REGION", "DATAPROC_CLUSTER_NAME", "GCS_BUCKET",
        # Postgres/Redshift
        "SSH_TUNNEL_ENABLED", "SSH_TUNNEL_HOSTNAME", "SSH_TUNNEL_PORT", "SSH_TUNNEL_USERNAME",
        "PASSWORD",
        # Athena
        "REGION_NAME", "S3_STAGING_DIR", "WORK_GROUP", "S3_DATA_DIR",
        "S3_TMP_TABLE_DIR", "S3_DATA_NAMING", "NUM_RETRIES",
        "NUM_BOTO3_RETRIES", "NUM_ICEBERG_RETRIES", "POLL_INTERVAL",
        "SPARK_WORK_GROUP",
        # Fabric/Synapse
        "SERVER", "LOGIN_TIMEOUT", "QUERY_TIMEOUT",
        # Starburst
        "METHOD",
        # Apache Spark
        "CLUSTER", "ORGANIZATION", "USER", "AUTH",
        "CONNECT_TIMEOUT", "CONNECT_RETRIES",
        # Teradata
        "TMODE", "REQUEST_TIMEOUT",
    }

    prefix = "DBT_CONNECTION_"
    
    for key, value in values.items():
        if not key.startswith(prefix):
            continue
            
        # Remove prefix
        remainder = key[len(prefix):]
        
        # Try to find a known field name from the end
        field_name = None
        conn_name = None
        
        for known_field in sorted(known_fields, key=len, reverse=True):
            # Check if the remainder ends with _FIELD_NAME
            suffix = f"_{known_field}"
            if remainder.endswith(suffix):
                conn_name = remainder[:-len(suffix)].lower()
                field_name = known_field.lower()
                break
        
        if conn_name and field_name:
            if conn_name not in configs:
                configs[conn_name] = {}
            configs[conn_name][field_name] = value

    return configs


# Fields that contain sensitive OAuth/SSO credentials
# These should be handled with care and not logged
SENSITIVE_OAUTH_FIELDS = {
    "oauth_client_secret",  # Snowflake OAuth
    "client_secret",        # Databricks OAuth, BigQuery
    "private_key",          # BigQuery service account
    "application_secret",   # BigQuery external OAuth (WIF)
    "password",             # Redshift, Postgres
}


def save_connection_config(
    connection_name: str,
    config: dict,
    env_path: Optional[str] = None,
) -> Path:
    """Save a connection provider configuration to .env file.

    Saves all connection fields including OAuth/SSO credentials.
    Sensitive fields (oauth_client_secret, client_secret, private_key, etc.)
    are stored as environment variables with the naming convention:
    DBT_CONNECTION_{CONNECTION_NAME}_{FIELD_NAME}

    For example:
    - DBT_CONNECTION_SNOWFLAKE_PROD_OAUTH_CLIENT_ID
    - DBT_CONNECTION_SNOWFLAKE_PROD_OAUTH_CLIENT_SECRET
    - DBT_CONNECTION_DATABRICKS_DEV_CLIENT_ID
    - DBT_CONNECTION_DATABRICKS_DEV_CLIENT_SECRET
    - DBT_CONNECTION_BIGQUERY_MAIN_PRIVATE_KEY

    Note: Sensitive credentials are stored in plaintext in the .env file.
    Ensure the .env file has appropriate permissions and is excluded from
    version control (add to .gitignore).

    Args:
        connection_name: Name of the connection (e.g., "snowflake_prod")
        config: Dictionary of field names to values (including OAuth fields)
        env_path: Path to .env file. If None, uses default location.

    Returns:
        Path to the saved .env file.
    """
    if env_path:
        path = Path(env_path)
    else:
        path = find_env_file()

    # Create file if it doesn't exist
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    # Normalize connection name to uppercase
    conn_upper = connection_name.upper().replace("-", "_")

    for field_name, value in config.items():
        field_upper = field_name.upper().replace("-", "_")
        env_key = f"DBT_CONNECTION_{conn_upper}_{field_upper}"
        
        # Convert booleans to string representation
        if isinstance(value, bool):
            value = "true" if value else "false"
        
        set_key(str(path), env_key, str(value) if value is not None else "")

    return path


def load_connection_config(
    connection_name: str,
    env_path: Optional[str] = None,
) -> dict:
    """Load a specific connection's configuration from .env file.

    Args:
        connection_name: Name of the connection to load
        env_path: Path to .env file. If None, searches for one.

    Returns:
        Dictionary of field names to values for this connection
    """
    all_configs = load_connection_configs(env_path)
    return all_configs.get(connection_name.lower().replace("-", "_"), {})


def get_env_file_path(env_path: Optional[str] = None) -> Path:
    """Get the path to the .env file that would be used.

    Args:
        env_path: Explicit path, or None to search.

    Returns:
        Path to the .env file (may not exist yet).
    """
    if env_path:
        return Path(env_path)
    return find_env_file()


def fetch_account_name(
    host_url: str,
    account_id: str,
    api_token: str,
) -> Tuple[bool, str]:
    """Fetch account name from dbt Cloud API.

    Args:
        host_url: dbt Cloud host URL
        account_id: Account ID
        api_token: API token

    Returns:
        Tuple of (success, account_name or error_message)
    """
    try:
        import httpx
        from importer import get_version

        url = f"{host_url.rstrip('/')}/api/v2/accounts/{account_id}/"
        headers = {
            "Authorization": f"Token {api_token}",
            "User-Agent": f"dbtcloud-importer/{get_version()}",
        }

        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                account_name = data.get("data", {}).get("name", "")
                return True, account_name
            elif resp.status_code == 401:
                return False, "Invalid API token"
            elif resp.status_code == 403:
                return False, "Access denied"
            elif resp.status_code == 404:
                return False, f"Account {account_id} not found"
            else:
                return False, f"API error: {resp.status_code}"

    except httpx.ConnectError:
        return False, "Connection failed - check host URL"
    except httpx.TimeoutException:
        return False, "Request timed out"
    except Exception as e:
        return False, str(e)


# =============================================================================
# Environment Credentials Management
# =============================================================================
# These functions handle per-environment credential configurations stored in .env
# Format: DBT_ENV_CRED_{ENV_ID}_{FIELD_NAME}=value
# Example: DBT_ENV_CRED_12345_SCHEMA=my_schema
#          DBT_ENV_CRED_12345_USER=my_user
#          DBT_ENV_CRED_12345_USE_DUMMY=true


def _normalize_env_id(env_id: str) -> str:
    """Normalize environment ID for use in env var names.
    
    Replaces dashes with underscores and converts to uppercase.
    """
    return str(env_id).upper().replace("-", "_")


def _get_env_cred_prefix(env_id: str) -> str:
    """Get the env var prefix for an environment's credentials."""
    return f"DBT_ENV_CRED_{_normalize_env_id(env_id)}_"


# Known field names for environment credentials (for parsing)
ENV_CRED_KNOWN_FIELDS = {
    # Credential type (required for Terraform routing)
    "CREDENTIAL_TYPE",
    # Common fields
    "SCHEMA", "USER", "PASSWORD", "NUM_THREADS", "DATABASE",
    # Snowflake
    "AUTH_TYPE", "PRIVATE_KEY", "PRIVATE_KEY_PASSPHRASE", "WAREHOUSE", "ROLE",
    # Databricks
    "TOKEN", "CATALOG", "ADAPTER_TYPE", "TARGET_NAME",
    # BigQuery
    "DATASET",
    # Redshift
    "DEFAULT_SCHEMA", "USERNAME",
    # Athena
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    # Fabric/Synapse
    "TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "SCHEMA_AUTHORIZATION", "AUTHENTICATION",
    # Starburst
    # (uses common fields)
    # Teradata
    "THREADS",
    # Meta field
    "USE_DUMMY",
}


def load_env_credential_configs(env_path: Optional[str] = None) -> dict:
    """Load all environment credential configurations from .env file.
    
    Looks for variables matching pattern: DBT_ENV_CRED_{ENV_ID}_{FIELD}
    
    Returns:
        Nested dictionary: {env_id: {field: value, ...}}
    """
    values = load_env_values(env_path)
    configs = {}
    
    prefix = "DBT_ENV_CRED_"
    
    for key, value in values.items():
        if not key.startswith(prefix):
            continue
        
        # Remove prefix
        remainder = key[len(prefix):]
        
        # Try to find a known field name from the end
        field_name = None
        env_id = None
        
        for known_field in sorted(ENV_CRED_KNOWN_FIELDS, key=len, reverse=True):
            # Check if the remainder ends with _FIELD_NAME
            suffix = f"_{known_field}"
            if remainder.endswith(suffix):
                env_id = remainder[:-len(suffix)].lower()
                field_name = known_field.lower()
                break
        
        if env_id and field_name:
            if env_id not in configs:
                configs[env_id] = {}
            configs[env_id][field_name] = value
    
    return configs


def load_env_credential_config(
    env_id: str,
    env_path: Optional[str] = None,
) -> dict:
    """Load a specific environment's credential configuration from .env file.
    
    Args:
        env_id: Environment ID
        env_path: Path to .env file
        
    Returns:
        Dictionary of field names to values for this environment
    """
    all_configs = load_env_credential_configs(env_path)
    normalized_id = _normalize_env_id(env_id).lower()
    return all_configs.get(normalized_id, {})


def get_dummy_credential_env_ids(env_path: Optional[str] = None) -> set:
    """Get set of environment IDs that use dummy credentials.
    
    Args:
        env_path: Path to .env file
        
    Returns:
        Set of environment IDs (normalized, lowercase) with use_dummy=true
    """
    all_configs = load_env_credential_configs(env_path)
    dummy_envs = set()
    
    for env_id, config in all_configs.items():
        use_dummy = config.get("use_dummy", "false")
        if str(use_dummy).lower() == "true":
            dummy_envs.add(env_id)
    
    return dummy_envs


def save_env_credential_config(
    env_id: str,
    config: dict,
    use_dummy: bool = False,
    env_path: Optional[str] = None,
) -> Path:
    """Save an environment's credential configuration to .env file.
    
    Args:
        env_id: Environment ID
        config: Dictionary of field names to values
        use_dummy: Whether dummy credentials are being used (stored as meta field)
        env_path: Path to .env file
        
    Returns:
        Path to the saved .env file
    """
    if env_path:
        path = Path(env_path)
    else:
        path = find_env_file()
    
    # Create file if it doesn't exist
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    
    prefix = _get_env_cred_prefix(env_id)
    
    # Save USE_DUMMY meta field
    set_key(str(path), f"{prefix}USE_DUMMY", "true" if use_dummy else "false")
    
    # Save all config fields
    for field_name, value in config.items():
        field_upper = field_name.upper().replace("-", "_")
        env_key = f"{prefix}{field_upper}"
        
        # Convert booleans to string
        if isinstance(value, bool):
            value = "true" if value else "false"
        
        set_key(str(path), env_key, str(value) if value is not None else "")
    
    return path


def save_all_env_credential_configs(
    configs: dict,
    env_path: Optional[str] = None,
) -> Path:
    """Save multiple environment credential configurations to .env file.
    
    Args:
        configs: Dictionary of env_id -> {field: value, use_dummy: bool}
        env_path: Path to .env file
        
    Returns:
        Path to the saved .env file
    """
    if env_path:
        path = Path(env_path)
    else:
        path = find_env_file()
    
    # Create file if it doesn't exist
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    
    for env_id, env_config in configs.items():
        use_dummy = env_config.pop("use_dummy", False) if "use_dummy" in env_config else False
        save_env_credential_config(env_id, env_config, use_dummy, str(path))
    
    return path


def clear_env_credential_config(
    env_id: str,
    env_path: Optional[str] = None,
) -> None:
    """Clear an environment's credential configuration from .env file.
    
    Note: This sets values to empty strings rather than removing the keys,
    as python-dotenv's set_key doesn't have a clean removal mechanism.
    
    Args:
        env_id: Environment ID
        env_path: Path to .env file
    """
    if env_path:
        path = Path(env_path)
    else:
        path = find_env_file()
    
    if not path.exists():
        return
    
    prefix = _get_env_cred_prefix(env_id)
    values = load_env_values(str(path))
    
    for key in values.keys():
        if key.startswith(prefix):
            set_key(str(path), key, "")


def load_account_info_from_env(
    account_type: str = "source",
    env_path: Optional[str] = None,
) -> AccountInfo:
    """Load account info from .env file credentials.

    Attempts to fetch account name from API if credentials are complete.

    Args:
        account_type: "source" or "target"
        env_path: Path to .env file

    Returns:
        AccountInfo populated from .env (and API if possible)
    """
    if account_type == "source":
        creds = load_source_credentials(env_path)
    else:
        creds = load_target_credentials(env_path)

    info = AccountInfo(
        account_id=creds.get("account_id", ""),
        host_url=creds.get("host_url", "https://cloud.getdbt.com"),
    )

    # Check if credentials are complete
    if creds.get("account_id") and creds.get("api_token"):
        info.is_configured = True

        # Try to fetch account name
        success, result = fetch_account_name(
            creds["host_url"],
            creds["account_id"],
            creds["api_token"],
        )
        if success:
            info.account_name = result
            info.is_verified = True

    return info


# =============================================================================
# License Credentials Management
# =============================================================================
# These functions handle Magellan license credentials stored in .env
# Format: MAGELLAN_LICENSE_EMAIL and MAGELLAN_LICENSE_KEY


def load_license_credentials(env_path: Optional[str] = None) -> dict:
    """Load Magellan license credentials from .env file.

    Args:
        env_path: Path to .env file. If None, searches for one.

    Returns:
        Dictionary with keys: email, key
        Both values will be empty strings if not found.
    """
    values = load_env_values(env_path)

    return {
        "email": values.get("MAGELLAN_LICENSE_EMAIL", ""),
        "key": values.get("MAGELLAN_LICENSE_KEY", ""),
    }


def load_license_credentials_from_content(content: str) -> dict:
    """Load Magellan license credentials from .env content string.

    Args:
        content: String content of a .env file

    Returns:
        Dictionary with keys: email, key
    """
    values = parse_env_content(content)

    return {
        "email": values.get("MAGELLAN_LICENSE_EMAIL", ""),
        "key": values.get("MAGELLAN_LICENSE_KEY", ""),
    }


def save_license_credentials(
    email: str,
    key: str,
    env_path: Optional[str] = None,
) -> Path:
    """Save Magellan license credentials to .env file.

    Creates the file if it doesn't exist. Preserves existing values.

    Args:
        email: License email address (MAGELLAN_LICENSE_EMAIL)
        key: License key (MAGELLAN_LICENSE_KEY) - base64-encoded Ed25519 private key
        env_path: Path to .env file. If None, uses default location.

    Returns:
        Path to the saved .env file.
    """
    if env_path:
        path = Path(env_path)
    else:
        path = find_env_file()

    # Create file if it doesn't exist
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    # Save credentials using python-dotenv's set_key
    set_key(str(path), "MAGELLAN_LICENSE_EMAIL", email)
    set_key(str(path), "MAGELLAN_LICENSE_KEY", key)

    return path


def clear_license_credentials(env_path: Optional[str] = None) -> None:
    """Clear Magellan license credentials from .env file.

    Sets the values to empty strings rather than removing the keys.

    Args:
        env_path: Path to .env file. If None, uses default location.
    """
    if env_path:
        path = Path(env_path)
    else:
        path = find_env_file()

    if not path.exists():
        return

    set_key(str(path), "MAGELLAN_LICENSE_EMAIL", "")
    set_key(str(path), "MAGELLAN_LICENSE_KEY", "")
