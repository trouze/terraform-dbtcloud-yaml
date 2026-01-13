"""Environment file (.env) management utilities."""

import os
import re
from pathlib import Path
from typing import Optional, Tuple

from dotenv import dotenv_values, set_key

from importer.web.state import AccountInfo


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
        Dictionary with keys: host_url, account_id, api_token
    """
    values = parse_env_content(content)

    return {
        "host_url": values.get("DBT_SOURCE_HOST_URL", "https://cloud.getdbt.com"),
        "account_id": values.get("DBT_SOURCE_ACCOUNT_ID", ""),
        "api_token": values.get("DBT_SOURCE_API_TOKEN", ""),
    }


def load_target_credentials_from_content(content: str) -> dict:
    """Load target dbt Cloud credentials from .env content string.

    Args:
        content: String content of a .env file

    Returns:
        Dictionary with keys: host_url, account_id, api_token, token_type
    """
    values = parse_env_content(content)

    return {
        "host_url": values.get("DBT_TARGET_HOST_URL", "https://cloud.getdbt.com"),
        "account_id": values.get("DBT_TARGET_ACCOUNT_ID", ""),
        "api_token": values.get("DBT_TARGET_API_TOKEN", ""),
        "token_type": values.get("DBT_TARGET_TOKEN_TYPE", "service_token"),
    }


def load_source_credentials(env_path: Optional[str] = None) -> dict:
    """Load source dbt Cloud credentials from .env file.

    Returns:
        Dictionary with keys: host_url, account_id, api_token
    """
    values = load_env_values(env_path)

    return {
        "host_url": values.get("DBT_SOURCE_HOST_URL", "https://cloud.getdbt.com"),
        "account_id": values.get("DBT_SOURCE_ACCOUNT_ID", ""),
        "api_token": values.get("DBT_SOURCE_API_TOKEN", ""),
    }


def load_target_credentials(env_path: Optional[str] = None) -> dict:
    """Load target dbt Cloud credentials from .env file.

    Returns:
        Dictionary with keys: host_url, account_id, api_token, token_type
    """
    values = load_env_values(env_path)

    return {
        "host_url": values.get("DBT_TARGET_HOST_URL", "https://cloud.getdbt.com"),
        "account_id": values.get("DBT_TARGET_ACCOUNT_ID", ""),
        "api_token": values.get("DBT_TARGET_API_TOKEN", ""),
        "token_type": values.get("DBT_TARGET_TOKEN_TYPE", "service_token"),
    }


def save_source_credentials(
    host_url: str,
    account_id: str,
    api_token: str,
    env_path: Optional[str] = None,
) -> Path:
    """Save source dbt Cloud credentials to .env file.

    Creates the file if it doesn't exist. Preserves existing values.

    Args:
        host_url: dbt Cloud host URL
        account_id: dbt Cloud account ID
        api_token: API token (PAT or service token)
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

    # Use python-dotenv's set_key to preserve formatting
    set_key(str(path), "DBT_SOURCE_HOST_URL", host_url)
    set_key(str(path), "DBT_SOURCE_ACCOUNT_ID", account_id)
    set_key(str(path), "DBT_SOURCE_API_TOKEN", api_token)

    return path


def save_target_credentials(
    host_url: str,
    account_id: str,
    api_token: str,
    token_type: str = "service_token",
    env_path: Optional[str] = None,
) -> Path:
    """Save target dbt Cloud credentials to .env file.

    Creates the file if it doesn't exist. Preserves existing values.

    Args:
        host_url: dbt Cloud host URL
        account_id: dbt Cloud account ID
        api_token: API token
        token_type: Token type ("service_token" or "user_token")
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

    set_key(str(path), "DBT_TARGET_HOST_URL", host_url)
    set_key(str(path), "DBT_TARGET_ACCOUNT_ID", account_id)
    set_key(str(path), "DBT_TARGET_API_TOKEN", api_token)
    set_key(str(path), "DBT_TARGET_TOKEN_TYPE", token_type)

    return path


def load_connection_configs(env_path: Optional[str] = None) -> dict:
    """Load connection provider configurations from .env file.

    Looks for variables matching pattern: DBT_CONNECTION_{NAME}_{FIELD}

    Returns:
        Nested dictionary: {connection_name: {field: value}}
    """
    values = load_env_values(env_path)
    configs = {}

    pattern = re.compile(r"^DBT_CONNECTION_([A-Z0-9_]+)_([A-Z0-9_]+)$")

    for key, value in values.items():
        match = pattern.match(key)
        if match:
            conn_name = match.group(1).lower()
            field_name = match.group(2).lower()

            if conn_name not in configs:
                configs[conn_name] = {}
            configs[conn_name][field_name] = value

    return configs


def save_connection_config(
    connection_name: str,
    config: dict,
    env_path: Optional[str] = None,
) -> Path:
    """Save a connection provider configuration to .env file.

    Args:
        connection_name: Name of the connection (e.g., "snowflake_prod")
        config: Dictionary of field names to values
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
        set_key(str(path), env_key, str(value) if value is not None else "")

    return path


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
