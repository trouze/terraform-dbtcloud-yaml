"""Interactive mode utilities using InquirerPy for form-like prompts."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Optional

import yaml
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console

from .config import get_settings, Settings, SOURCE_PREFIX, TARGET_PREFIX


def _strip_bracketed_paste_sequences(value: str) -> str:
    """
    Strip bracketed paste mode escape sequences from input.
    
    Bracketed paste mode uses:
    - ESC [ 200 ~ to start paste (^[[200~)
    - ESC [ 201 ~ to end paste (^[[201~)
    
    These can appear when pasting in certain terminals, causing issues.
    """
    if not value:
        return value
    
    # Log the raw input for debugging (only if escape sequences detected)
    original_value = value
    has_escapes = '\x1b[' in value or '^[' in value
    
    # Remove ESC [ 200 ~ (start paste) and ESC [ 201 ~ (end paste)
    # Handle both actual escape characters and caret notation
    value = re.sub(r'\x1b\[200~', '', value)  # ESC [ 200 ~
    value = re.sub(r'\x1b\[201~', '', value)  # ESC [ 201 ~
    value = re.sub(r'\x1b\[200;', '', value)   # Alternative format
    value = re.sub(r'\x1b\[201;', '', value)   # Alternative format
    # Also handle caret notation (^[)
    value = re.sub(r'\^\[\[200~', '', value)   # ^[[200~
    value = re.sub(r'\^\[\[201~', '', value)   # ^[[201~
    
    # Strip any leading/trailing whitespace that might have been added
    result = value.strip()
    
    # Debug logging if escape sequences were found
    if has_escapes:
        import logging
        import sys
        log = logging.getLogger(__name__)
        # Also write to stderr for immediate visibility
        print(f"\n[DEBUG] Stripped bracketed paste sequences:", file=sys.stderr)
        print(f"  Input: {repr(original_value)}", file=sys.stderr)
        print(f"  Output: {repr(result)}", file=sys.stderr)
        log.debug(f"Stripped bracketed paste sequences: {repr(original_value)} -> {repr(result)}")
    
    return result

# Connection type schemas: required fields, optional fields, and descriptions
CONNECTION_SCHEMAS = {
    "snowflake": {
        "required": ["account", "database", "warehouse"],
        "optional": ["role", "client_session_keep_alive", "allow_sso", "oauth_client_id", "oauth_client_secret"],
        "descriptions": {
            "account": "Snowflake account identifier (e.g., 'abc12345.us-east-1' or 'abc12345')",
            "database": "Default database name",
            "warehouse": "Compute warehouse name",
            "role": "Default role (optional)",
            "client_session_keep_alive": "Keep session alive (true/false, optional)",
            "allow_sso": "Allow SSO authentication (true/false, optional)",
        }
    },
    "databricks": {
        "required": ["host", "http_path"],
        "optional": ["catalog", "client_id", "client_secret"],
        "descriptions": {
            "host": "Databricks workspace URL (e.g., 'workspace.cloud.databricks.com')",
            "http_path": "SQL warehouse HTTP path (e.g., '/sql/1.0/warehouses/abc123')",
            "catalog": "Unity Catalog name (optional)",
            "client_id": "OAuth client ID (optional)",
            "client_secret": "OAuth client secret (optional)",
        }
    },
    "bigquery": {
        "required": ["project_id", "dataset"],
        "optional": ["location", "timeout_seconds", "priority", "maximum_bytes_billed", "job_timeout_ms", "job_retries"],
        "descriptions": {
            "project_id": "GCP project ID",
            "dataset": "BigQuery dataset name",
            "location": "Dataset location (e.g., 'US', 'EU', optional, defaults to 'US')",
            "timeout_seconds": "Query timeout in seconds (optional)",
            "priority": "Query priority: 'INTERACTIVE' or 'BATCH' (optional)",
        }
    },
    "redshift": {
        "required": ["hostname", "port", "dbname"],
        "optional": ["ssh_tunnel"],
        "descriptions": {
            "hostname": "Redshift cluster endpoint (e.g., 'cluster.region.redshift.amazonaws.com')",
            "port": "Port number (default: 5439)",
            "dbname": "Database name",
            "ssh_tunnel": "SSH tunnel configuration (optional, complex nested object)",
        }
    },
    "postgres": {
        "required": ["hostname", "port", "dbname"],
        "optional": ["ssh_tunnel"],
        "descriptions": {
            "hostname": "PostgreSQL hostname",
            "port": "Port number (default: 5432)",
            "dbname": "Database name",
            "ssh_tunnel": "SSH tunnel configuration (optional, complex nested object)",
        }
    },
    "athena": {
        "required": ["region_name", "database", "s3_staging_dir"],
        "optional": [],
        "descriptions": {
            "region_name": "AWS region (e.g., 'us-east-1')",
            "database": "Athena database name",
            "s3_staging_dir": "S3 staging directory (e.g., 's3://bucket/staging/')",
        }
    },
    "fabric": {
        "required": ["server", "database"],
        "optional": ["port", "retries", "login_timeout", "query_timeout"],
        "descriptions": {
            "server": "Microsoft Fabric server name",
            "database": "Database name",
            "port": "Port number (optional)",
        }
    },
    "synapse": {
        "required": ["host", "database"],
        "optional": ["port", "retries", "login_timeout", "query_timeout"],
        "descriptions": {
            "host": "Azure Synapse Analytics host",
            "database": "Database name",
            "port": "Port number (optional)",
        }
    },
}

console = Console()


def prompt_credentials() -> dict[str, str | int]:
    """
    Prompt for dbt Cloud API credentials if not already set in environment.
    
    Returns:
        Dictionary with 'host', 'account_id', and 'api_token'
    """
    # Check what's already set
    current_host = os.getenv(f"{SOURCE_PREFIX}HOST_URL") or os.getenv(f"{SOURCE_PREFIX}HOST", "")
    current_account_id = os.getenv(f"{SOURCE_PREFIX}ACCOUNT_ID", "")
    current_token = os.getenv(f"{SOURCE_PREFIX}API_TOKEN", "")
    
    credentials = {}
    
    # Only prompt for missing credentials
    if not current_host:
        host = inquirer.text(
            message="dbt Cloud Host URL:",
            default="https://cloud.getdbt.com",
            validate=lambda result: (
            result.startswith("https://")
        ) or "Host URL must start with https://",
            filter=_strip_bracketed_paste_sequences,
            long_instruction="Enter the base URL for your dbt Cloud instance (e.g., https://cloud.getdbt.com or https://emea.dbt.com)",
        ).execute()
        credentials["host_url"] = host.rstrip("/")
    else:
        credentials["host_url"] = current_host.rstrip("/")
    
    if not current_account_id:
        account_id_str = inquirer.text(
            message="Account ID:",
            default="",
            validate=lambda result: result.isdigit() or "Account ID must be numeric",
            long_instruction="Enter your dbt Cloud account ID (numeric)",
            filter=_strip_bracketed_paste_sequences,
        ).execute()
        credentials["account_id"] = int(account_id_str)
    else:
        credentials["account_id"] = int(current_account_id)
    
    if not current_token:
        token = inquirer.secret(
            message="API Token:",
            default="",
            validate=lambda result: len(result) > 0 or "API token is required",
            long_instruction="Enter your dbt Cloud API token (Account Admin or Owner token recommended)",
        ).execute()
        credentials["api_token"] = token
    else:
        credentials["api_token"] = current_token
    
    return credentials


def prompt_target_credentials() -> dict[str, str | int]:
    """
    Prompt for target dbt Cloud API credentials (for Terraform apply).
    
    Returns:
        Dictionary with 'host', 'account_id', and 'token'
    """
    console.print("\n[bold cyan]Target Account Credentials (for Terraform apply)[/bold cyan]\n")
    
    # Check what's already set
    current_host = os.getenv(f"{TARGET_PREFIX}HOST_URL", "")
    current_account_id = os.getenv(f"{TARGET_PREFIX}ACCOUNT_ID", "")
    current_token = os.getenv(f"{TARGET_PREFIX}API_TOKEN", "")
    
    credentials = {}
    
    # Only prompt for missing credentials
    if not current_host:
        host = inquirer.text(
            message="Target dbt Cloud Host URL:",
            default="https://cloud.getdbt.com",
            validate=lambda result: (
                result.startswith("https://")
            ) or "Host URL must start with https://",
            filter=_strip_bracketed_paste_sequences,
            long_instruction="Enter the base URL for your target dbt Cloud instance",
        ).execute()
        credentials["host_url"] = host.rstrip("/")
    else:
        credentials["host_url"] = current_host.rstrip("/")
    
    if not current_account_id:
        account_id_str = inquirer.text(
            message="Target Account ID:",
            default="",
            validate=lambda result: result.isdigit() or "Account ID must be numeric",
            long_instruction="Enter your target dbt Cloud account ID (numeric)",
            filter=_strip_bracketed_paste_sequences,
        ).execute()
        credentials["account_id"] = int(account_id_str)
    else:
        credentials["account_id"] = int(current_account_id)
    
    if not current_token:
        token = inquirer.secret(
            message="Target API Token:",
            default="",
            validate=lambda result: len(result) > 0 or "API token is required",
            long_instruction="Enter your target dbt Cloud API token (Account Admin or Owner token recommended)",
        ).execute()
        credentials["api_token"] = token
    else:
        credentials["api_token"] = current_token
    
    return credentials


def save_target_credentials_to_env(credentials: dict[str, str | int]) -> None:
    """Save target account credentials to .env file."""
    env_path = _get_env_file_path()
    existing = _read_existing_env()
    
    # Check if any target credentials already exist
    has_existing = any(
        f"{TARGET_PREFIX}{key.upper()}" in existing
        for key in ["host_url", "account_id", "api_token"]
    )
    
    if has_existing:
        overwrite = inquirer.confirm(
            message="Some target credentials already exist in .env. Overwrite existing values?",
            default=False,
        ).execute()
        if not overwrite:
            return
    
    # Check file permissions
    if env_path.exists():
        if not os.access(env_path, os.W_OK):
            console.print(f"[red]Error: Cannot write to {env_path} (permission denied)[/red]")
            return
    
    # Prompt for save
    save = inquirer.confirm(
        message="Save target credentials to .env file?",
        default=True,
    ).execute()
    
    if not save:
        return
    
    # Write target credentials
    mode = "a" if env_path.exists() else "w"
    with open(env_path, mode, encoding="utf-8") as f:
        if mode == "w":
            f.write("# dbt Cloud Importer Credentials\n")
            f.write("# Generated by interactive mode\n")
            f.write("# DO NOT commit this file to version control\n\n")
        
        f.write("\n# Target Account Credentials (for Terraform apply)\n")
        for key, value in sorted(credentials.items()):
            env_key = f"{TARGET_PREFIX}{key.upper()}"
            f.write(f"{env_key}={_format_env_value(value)}\n")
    
    # Set restrictive permissions
    try:
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    
    console.print(f"[green]✓[/green] Target credentials saved to {env_path}")


def _get_env_file_path() -> Path:
    """Get the path to the .env file in the repo root."""
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / ".env"


def _read_existing_env() -> dict[str, str]:
    """Read existing .env file and return as dict."""
    env_path = _get_env_file_path()
    if not env_path.exists():
        return {}
    
    existing = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE format
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                existing[key] = value
    return existing


def _format_env_value(value: str | int) -> str:
    """Format a value for .env file (escape special characters)."""
    value_str = str(value)
    # If value contains spaces or special chars, wrap in quotes
    if " " in value_str or "=" in value_str or "#" in value_str:
        # Escape quotes in value
        value_str = value_str.replace('"', '\\"')
        return f'"{value_str}"'
    return value_str


def _check_gitignore() -> bool:
    """Check if .env is in .gitignore."""
    repo_root = Path(__file__).resolve().parents[1]
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.exists():
        return False
    
    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()
        # Check for .env entry (exact match or pattern)
        return ".env" in content or "/.env" in content or "*.env" in content


def _write_env_file(
    credentials: dict[str, str | int],
    connection_configs: Optional[dict[str, dict[str, str | int]]] = None,
    append: bool = True,
) -> None:
    """Write credentials to .env file."""
    env_path = _get_env_file_path()
    existing = _read_existing_env() if append else {}
    
    # Merge credentials (don't overwrite existing unless user confirmed)
    new_credentials = {}
    for key, value in credentials.items():
        env_key = f"{SOURCE_PREFIX}{key.upper()}"
        if env_key not in existing:
            new_credentials[env_key] = value
    
    # Merge connection configs (keep grouped by conn_key)
    new_connection_configs = {}
    if connection_configs:
        for conn_key, config in connection_configs.items():
            conn_prefix = f"DBT_CONNECTION_{conn_key.upper().replace('-', '_').replace('.', '_')}"
            # Check if any fields for this connection already exist
            has_existing = any(
                f"{conn_prefix}_{field.upper()}" in existing
                for field in config.keys()
            )
            if not has_existing:
                new_connection_configs[conn_key] = config
    
    # If nothing new to add, return early
    if not new_credentials and not new_connection_configs:
        console.print("[yellow]No new credentials to save (all already exist in .env)[/yellow]")
        return
    
    # Write to file
    mode = "a" if append and env_path.exists() else "w"
    with open(env_path, mode, encoding="utf-8") as f:
        if mode == "w" or not append:
            # Write header comment
            f.write("# dbt Cloud Importer Credentials\n")
            f.write("# Generated by interactive mode\n")
            f.write("# DO NOT commit this file to version control\n\n")
        
        # Write source account credentials
        if new_credentials:
            f.write("\n# Source Account Credentials (for fetch)\n")
            for key, value in sorted(new_credentials.items()):
                f.write(f"{key}={_format_env_value(value)}\n")
        
        # Write connection credentials
        if new_connection_configs:
            f.write("\n# Connection Provider Configs\n")
            # connection_configs is already grouped by conn_key
            for conn_key, config in sorted(new_connection_configs.items()):
                conn_prefix = f"DBT_CONNECTION_{conn_key.upper().replace('-', '_').replace('.', '_')}"
                f.write(f"\n# Connection: {conn_key}\n")
                for field, value in sorted(config.items()):
                    env_key = f"{conn_prefix}_{field.upper()}"
                    f.write(f"{env_key}={_format_env_value(value)}\n")
    
    # Set restrictive permissions (600 = rw-------)
    try:
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # Ignore permission errors on some systems
    
    console.print(f"[green]✓[/green] Credentials saved to {env_path}")
    
    # Check gitignore
    if not _check_gitignore():
        console.print("[yellow]⚠[/yellow] Warning: .env is not in .gitignore - credentials may be committed to git!")
        add_to_gitignore = inquirer.confirm(
            message="Add .env to .gitignore?",
            default=True,
        ).execute()
        if add_to_gitignore:
            repo_root = Path(__file__).resolve().parents[1]
            gitignore_path = repo_root / ".gitignore"
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n# Environment variables\n.env\n")
            console.print("[green]✓[/green] Added .env to .gitignore")


def save_credentials_to_env(
    credentials: dict[str, str | int],
    connection_configs: Optional[dict[str, dict[str, str | int]]] = None,
) -> None:
    """Prompt user to save credentials to .env file."""
    env_path = _get_env_file_path()
    existing = _read_existing_env()
    
    # Check if any credentials already exist
    has_existing = any(
        f"{SOURCE_PREFIX}{key.upper()}" in existing
        for key in ["host", "account_id", "api_token"]
    )
    
    if has_existing:
        overwrite = inquirer.confirm(
            message="Some credentials already exist in .env. Overwrite existing values?",
            default=False,
            long_instruction="If 'no', only new credentials will be added.",
        ).execute()
        if not overwrite:
            # Filter out existing credentials
            filtered_creds = {}
            for key, value in credentials.items():
                env_key = f"{SOURCE_PREFIX}{key.upper()}"
                if env_key not in existing:
                    filtered_creds[key] = value
            credentials = filtered_creds
    
    # Check file permissions
    if env_path.exists():
        if not os.access(env_path, os.W_OK):
            console.print(f"[red]Error: Cannot write to {env_path} (permission denied)[/red]")
            return
    
    # Prompt for save
    save = inquirer.confirm(
        message="Save credentials to .env file for future sessions?",
        default=True,
        long_instruction=f"Credentials will be saved to {env_path}",
    ).execute()
    
    if not save:
        return
    
    # Determine append vs overwrite
    append = True
    if env_path.exists() and not has_existing:
        append_choice = inquirer.select(
            message="Append to existing .env or overwrite?",
            choices=[
                Choice("append", "Append (keep existing values)"),
                Choice("overwrite", "Overwrite (replace entire file)"),
            ],
            default="append",
        ).execute()
        append = append_choice == "append"
    
    # Write credentials
    _write_env_file(credentials, connection_configs, append=append)


def prompt_fetch_options() -> dict:
    """
    Interactive prompts for fetch command options.
    
    Returns:
        Dictionary with fetch command options
    """
    console.print("\n[bold cyan]Fetch Command Options[/bold cyan]\n")
    
    # Output path
    output_path = inquirer.filepath(
        message="Output file path (optional, press Enter to skip):",
        default="dev_support/samples/account.json",
        only_files=False,
        validate=lambda result: True,  # Allow empty or any path
        long_instruction="Path where the JSON export will be written. Leave empty to use default location.",
    ).execute()
    
    # Reports directory
    reports_dir = inquirer.filepath(
        message="Reports directory (optional, press Enter to skip):",
        default="dev_support/samples",
        only_files=False,
        validate=lambda result: True,
        long_instruction="Directory where summary and report markdown files will be written.",
    ).execute()
    
    # Auto timestamp
    auto_timestamp = inquirer.confirm(
        message="Add timestamp to filename?",
        default=True,
        long_instruction="If enabled, filenames will include timestamp (e.g., account_12345_run_001__json__20250127_120000.json)",
    ).execute()
    
    # Compact JSON
    compact = inquirer.confirm(
        message="Use compact JSON format?",
        default=False,
        long_instruction="If enabled, JSON will be minified (no pretty-printing).",
    ).execute()
    
    return {
        "output": Path(output_path) if output_path else None,
        "reports_dir": Path(reports_dir) if reports_dir else None,
        "auto_timestamp": auto_timestamp,
        "compact": compact,
    }


def prompt_normalize_options() -> dict:
    """
    Interactive prompts for normalize command options.
    
    Returns:
        Dictionary with normalize command options
    """
    console.print("\n[bold cyan]Normalize Fetch to dbt Cloud Terraform Module YAML format[/bold cyan]\n")
    
    latest_snapshot = _find_latest_snapshot(Path("dev_support/samples"))

    # Find recent JSON files in common locations
    common_dirs = [
        Path("dev_support/samples"),
        Path("."),
    ]
    recent_files = []
    
    for dir_path in common_dirs:
        if dir_path.exists():
            json_files = list(dir_path.glob("account_*_run_*__json__*.json"))
            recent_files.extend(json_files[:5])  # Limit to 5 per directory
    
    # Ensure latest_snapshot is included and unique
    if latest_snapshot:
        recent_files.insert(0, latest_snapshot)
    # Remove duplicates while preserving order
    seen = set()
    deduped = []
    for f in recent_files:
        if f not in seen:
            deduped.append(f)
            seen.add(f)
    recent_files = deduped
    
    # Sort by modification time (newest first)
    recent_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    recent_files = recent_files[:10]  # Show max 10 recent files
    
    # Input JSON file selection
    if recent_files:
        file_choices = [
            Choice(value=str(f), name=f"{f.name} ({f.parent})")
            for f in recent_files
        ]
        file_choices.append(Choice(value="__browse__", name="Browse for file..."))
        
        selected = inquirer.select(
            message="Select input JSON file:",
            choices=file_choices,
            default=file_choices[0].value if file_choices else None,
            long_instruction="Select a recent file or choose to browse for a different file.",
        ).execute()
        
        if selected == "__browse__":
            input_json = inquirer.filepath(
                message="Input JSON file path:",
                only_files=True,
                validate=lambda result: (
                    Path(result).exists() and result.endswith(".json")
                ) or "File must exist and be a JSON file",
                long_instruction="Path to the account JSON export from the fetch command.",
            ).execute()
        else:
            input_json = selected
    else:
        console.print("[yellow]No recent fetch outputs found. Please select a JSON export.[/yellow]")
        input_json = inquirer.filepath(
            message="Input JSON file path:",
            default="dev_support/samples/",
            only_files=True,
            validate=lambda result: (
                Path(result).exists() and result.endswith(".json")
            ) or "File must exist and be a JSON file",
            long_instruction="Path to the account JSON export from the fetch command.",
        ).execute()
    
    # Mapping config
    default_config = Path("importer_mapping.yml")
    mapping_config = inquirer.filepath(
        message="Mapping configuration file:",
        default=str(default_config),
        only_files=True,
            validate=lambda result: (
                Path(result).exists()
            ) or "Mapping config file must exist",
        long_instruction="Path to the normalization mapping configuration YAML file.",
    ).execute()
    
    # Output directory
    output_dir = inquirer.filepath(
        message="Output directory (optional, press Enter to use config default):",
        default="",
        only_files=False,
        validate=lambda result: True,  # Allow empty
        long_instruction="Directory where normalized YAML and artifacts will be written. Leave empty to use config default.",
    ).execute()
    
    return {
        "input_json": Path(input_json),
        "mapping_config": Path(mapping_config),
        "output_dir": Path(output_dir) if output_dir else None,
    }


def _find_latest_snapshot(output_dir: Path) -> Optional[Path]:
    """
    Find the most recent JSON snapshot in the given directory.
    """
    if not output_dir.exists():
        return None
    candidates = list(output_dir.glob("account_*_run_*__json__*.json"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def run_fetch_interactive() -> None:
    """Run fetch command in interactive mode."""
    from .cli import fetch

    console.print("\n[bold cyan]dbt Cloud Importer - Interactive Fetch Mode[/bold cyan]\n")
    console.print("[dim]Navigation: Use arrow keys or Tab/Shift+Tab to move, Enter to confirm, Ctrl+C to cancel[/dim]\n")

    # Prompt for credentials if needed
    credentials_entered = False
    try:
        get_settings()
        console.print("[green]✓[/green] Using credentials from environment variables")
    except RuntimeError:
        console.print("[yellow]⚠[/yellow] Some credentials missing, please provide them:")
        credentials = prompt_credentials()
        credentials_entered = True

        # Temporarily set environment variables for this session (set both new and legacy for compatibility)
        os.environ[f"{SOURCE_PREFIX}HOST_URL"] = credentials["host_url"]
        os.environ[f"{SOURCE_PREFIX}HOST"] = credentials["host_url"]  # Legacy compatibility
        os.environ[f"{SOURCE_PREFIX}ACCOUNT_ID"] = str(credentials["account_id"])
        os.environ[f"{SOURCE_PREFIX}API_TOKEN"] = credentials["api_token"]
        
        # Offer to save credentials
        save_credentials_to_env(credentials)
        
        # Optionally prompt for target account credentials
        prompt_target = inquirer.confirm(
            message="Also configure target account credentials for Terraform apply?",
            default=False,
            long_instruction="Target credentials are used when applying Terraform changes to a different account.",
        ).execute()
        
        if prompt_target:
            target_credentials = prompt_target_credentials()
            if target_credentials:
                save_target_credentials_to_env(target_credentials)

    # Prompt for fetch options
    options = prompt_fetch_options()

    # Show confirmation before executing
    console.print("\n[bold cyan]Ready to fetch:[/bold cyan]")
    console.print(f"  Output: {options['output'] or 'stdout'}")
    console.print(f"  Reports: {options['reports_dir'] or 'same as output'}")
    console.print(f"  Timestamp: {options['auto_timestamp']}")
    console.print(f"  Compact: {options['compact']}")

    proceed = inquirer.confirm(
        message="Proceed with fetch?",
        default=True,
    ).execute()

    if not proceed:
        console.print("[yellow]Fetch cancelled.[/yellow]")
        return

    # Execute fetch command (interactive flag forced off to avoid recursion)
    console.print("\n[bold]Executing fetch command...[/bold]\n")
    fetch(
        output=options["output"],
        reports_dir=options["reports_dir"],
        auto_timestamp=options["auto_timestamp"],
        compact=options["compact"],
        interactive=False,
    )

    # Offer to run normalization on the freshly fetched snapshot
    # Determine where fetch likely wrote files
    output_dir = (
        options["output"].parent if options["output"] else Path("dev_support/samples")
    )
    latest_snapshot = _find_latest_snapshot(output_dir)
    if latest_snapshot:
        console.print("\n[bold cyan]Fetch complete.[/bold cyan]")
        proceed_norm = inquirer.confirm(
            message=f"Run normalize now using {latest_snapshot.name}?",
            default=True,
        ).execute()
        if proceed_norm:
            console.print("\n[bold]Launching normalize...[/bold]\n")
            from .cli import normalize

            normalize(
                input_json=latest_snapshot,
                mapping_config=Path("importer_mapping.yml"),
                output_dir=None,
                interactive=False,
            )


def prompt_connection_credentials_interactive(yaml_file: Path) -> dict[str, dict[str, str | int]]:
    """
    Interactive menu-driven prompts for connection provider_config.
    Updates the YAML file directly with collected configurations.
    
    Args:
        yaml_file: Path to normalized YAML file
        
    Returns:
        Dictionary mapping connection keys to their provider_config dicts
    """
    connection_configs = prompt_connection_credentials(yaml_file)
    
    if connection_configs:
        # Read YAML
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # Update connections with provider_config
        if "globals" in data and "connections" in data["globals"]:
            for conn in data["globals"]["connections"]:
                conn_key = conn.get("key")
                if conn_key in connection_configs:
                    conn["provider_config"] = connection_configs[conn_key]
        
        # Write back to file
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        console.print(f"[green]✓[/green] YAML file updated: {yaml_file}")
    
    return connection_configs


def prompt_connection_credentials(yaml_file: Path) -> dict[str, dict[str, str | int]]:
    """
    Prompt for connection provider_config credentials using interactive menu-driven prompts.
    
    Args:
        yaml_file: Path to normalized YAML file
        
    Returns:
        Dictionary mapping connection keys to their provider_config dicts
    """
    with open(yaml_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    connections = data.get("globals", {}).get("connections", [])
    if not connections:
        return {}
    
    # Find connections missing provider_config
    missing_configs = []
    for conn in connections:
        if "provider_config" not in conn or not conn.get("provider_config"):
            missing_configs.append(conn)
    
    if not missing_configs:
        return {}
    
    console.print(f"\n[bold cyan]Connection Provider Configuration[/bold cyan]")
    console.print(f"[dim]Found {len(missing_configs)} connection(s) needing provider_config[/dim]\n")
    
    connection_configs = {}
    
    for conn in missing_configs:
        conn_key = conn.get("key", "unknown")
        conn_name = conn.get("name", "Unknown")
        conn_type = conn.get("type", "unknown").lower()
        
        # Find matching schema
        schema = None
        for schema_type, schema_data in CONNECTION_SCHEMAS.items():
            if schema_type in conn_type:
                schema = schema_data
                break
        
        console.print(f"\n[bold]Connection: {conn_name}[/bold]")
        console.print(f"[dim]Key: {conn_key}, Type: {conn_type}[/dim]\n")
        
        if not schema:
            console.print(f"[yellow]⚠ Unknown connection type '{conn_type}'. Skipping.[/yellow]")
            continue
        
        config = {}
        
        # Prompt for required fields
        console.print("[bold cyan]Required Fields:[/bold cyan]")
        for field in schema["required"]:
            description = schema["descriptions"].get(field, field.replace("_", " ").title())
            default_value = ""
            
            # Set smart defaults
            if field == "port":
                if "postgres" in conn_type:
                    default_value = "5432"
                elif "redshift" in conn_type:
                    default_value = "5439"
            elif field == "location" and "bigquery" in conn_type:
                default_value = "US"
            
            prompt_msg = f"  ? {description}:"
            if field in ["port"]:
                value = inquirer.text(
                    message=prompt_msg,
                    default=default_value,
                    validate=lambda r: r.isdigit() and int(r) > 0 or f"{field} must be a positive number",
                    filter=_strip_bracketed_paste_sequences,
                ).execute()
                config[field] = int(value) if value else None
            else:
                value = inquirer.text(
                    message=prompt_msg,
                    default=default_value,
                    validate=lambda r: len(r) > 0 or f"{description} is required",
                    long_instruction=schema["descriptions"].get(field, ""),
                    filter=_strip_bracketed_paste_sequences,
                ).execute()
                config[field] = value
        
        # Prompt for optional fields
        if schema["optional"]:
            console.print("\n[bold cyan]Optional Fields:[/bold cyan]")
            console.print("[dim]Press Enter to skip optional fields[/dim]\n")
            
            for field in schema["optional"]:
                # Skip complex nested objects for now
                if field == "ssh_tunnel":
                    console.print(f"[dim]  Skipping {field} (complex nested object - configure manually if needed)[/dim]")
                    continue
                
                description = schema["descriptions"].get(field, field.replace("_", " ").title())
                default_value = ""
                
                # Set smart defaults for booleans
                if field in ["client_session_keep_alive", "allow_sso"]:
                    default_value = "false"
                
                prompt_msg = f"  ? {description} (optional):"
                
                if field in ["client_session_keep_alive", "allow_sso"]:
                    value = inquirer.select(
                        message=prompt_msg,
                        choices=["true", "false", "skip"],
                        default="skip",
                    ).execute()
                    if value != "skip":
                        config[field] = value.lower() == "true"
                else:
                    value = inquirer.text(
                        message=prompt_msg,
                        default=default_value,
                        long_instruction=schema["descriptions"].get(field, ""),
                        filter=_strip_bracketed_paste_sequences,
                    ).execute()
                    if value:
                        config[field] = value
        
        connection_configs[conn_key] = config
        console.print(f"\n[green]✓[/green] Configuration complete for [bold]{conn_key}[/bold]\n")
    
    return connection_configs


def prompt_connection_credentials_legacy(yaml_file: Path) -> dict[str, dict[str, str | int]]:
    """
    Legacy version - kept for reference.
    """
    with open(yaml_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    connections = data.get("globals", {}).get("connections", [])
    if not connections:
        return {}
    
    # Find connections missing provider_config
    missing_configs = []
    for conn in connections:
        if "provider_config" not in conn or not conn.get("provider_config"):
            missing_configs.append(conn)
    
    if not missing_configs:
        return {}
    
    console.print(f"\n[bold cyan]Connection Provider Configuration[/bold cyan]")
    console.print(f"[dim]Found {len(missing_configs)} connection(s) needing provider_config[/dim]\n")
    
    connection_configs = {}
    
    for conn in missing_configs:
        conn_key = conn.get("key", "unknown")
        conn_name = conn.get("name", "Unknown")
        conn_type = conn.get("type", "unknown").lower()
        
        console.print(f"\n[bold]Connection: {conn_name}[/bold]")
        console.print(f"[dim]Key: {conn_key}, Type: {conn_type}[/dim]")
        
        config = {}
        
        if "snowflake" in conn_type:
            config["account"] = inquirer.text(
                message="Snowflake Account:",
                default="",
                validate=lambda r: len(r) > 0 or "Account is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            config["database"] = inquirer.text(
                message="Database:",
                default="",
                validate=lambda r: len(r) > 0 or "Database is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            config["warehouse"] = inquirer.text(
                message="Warehouse:",
                default="",
                validate=lambda r: len(r) > 0 or "Warehouse is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            role = inquirer.text(
                message="Role (optional):",
                default="",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            if role:
                config["role"] = role
        
        elif "databricks" in conn_type:
            config["host"] = inquirer.text(
                message="Databricks Host:",
                default="",
                validate=lambda r: len(r) > 0 or "Host is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            config["http_path"] = inquirer.text(
                message="HTTP Path:",
                default="",
                validate=lambda r: len(r) > 0 or "HTTP path is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            catalog = inquirer.text(
                message="Catalog (optional):",
                default="",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            if catalog:
                config["catalog"] = catalog
        
        elif "bigquery" in conn_type:
            config["project_id"] = inquirer.text(
                message="BigQuery Project ID:",
                default="",
                validate=lambda r: len(r) > 0 or "Project ID is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            config["dataset"] = inquirer.text(
                message="Dataset:",
                default="",
                validate=lambda r: len(r) > 0 or "Dataset is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            config["location"] = inquirer.text(
                message="Location:",
                default="US",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
        
        elif "redshift" in conn_type:
            config["hostname"] = inquirer.text(
                message="Redshift Hostname:",
                default="",
                validate=lambda r: len(r) > 0 or "Hostname is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            port_str = inquirer.text(
                message="Port:",
                default="5439",
                validate=lambda r: r.isdigit() or "Port must be numeric",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            config["port"] = int(port_str)
            config["dbname"] = inquirer.text(
                message="Database Name:",
                default="",
                validate=lambda r: len(r) > 0 or "Database name is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
        
        elif "postgres" in conn_type:
            config["hostname"] = inquirer.text(
                message="PostgreSQL Hostname:",
                default="",
                validate=lambda r: len(r) > 0 or "Hostname is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            port_str = inquirer.text(
                message="Port:",
                default="5432",
                validate=lambda r: r.isdigit() or "Port must be numeric",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
            config["port"] = int(port_str)
            config["dbname"] = inquirer.text(
                message="Database Name:",
                default="",
                validate=lambda r: len(r) > 0 or "Database name is required",
                filter=_strip_bracketed_paste_sequences,
            ).execute()
        
        else:
            console.print(f"[yellow]Unknown connection type: {conn_type}[/yellow]")
            console.print("[yellow]Skipping this connection[/yellow]")
            continue
        
        connection_configs[conn_key] = config
    
    return connection_configs


def run_normalize_interactive() -> None:
    """Run normalize command in interactive mode."""
    from .cli import normalize

    console.print("\n[bold cyan]dbt Cloud Importer - Normalize Fetch to dbt Cloud Terraform Module YAML format[/bold cyan]\n")
    console.print("[dim]Navigation: Use arrow keys or Tab/Shift+Tab to move, Enter to confirm, Ctrl+C to cancel[/dim]\n")

    # Prompt for normalize options
    options = prompt_normalize_options()

    # Show confirmation before executing
    console.print("\n[bold cyan]Ready to normalize:[/bold cyan]")
    console.print(f"  Input: {options['input_json']}")
    console.print(f"  Config: {options['mapping_config']}")
    console.print(f"  Output: {options['output_dir'] or 'from config'}")

    proceed = inquirer.confirm(
        message="Proceed to normalize the fetch to dbt Cloud Terraform Module YAML format?",
        default=True,
    ).execute()

    if not proceed:
        console.print("[yellow]Normalization cancelled.[/yellow]")
        return

    # Execute normalize command (interactive flag forced off to avoid recursion)
    console.print("\n[bold]Executing normalize command...[/bold]\n")
    normalize(
        input_json=options["input_json"],
        mapping_config=options["mapping_config"],
        output_dir=options["output_dir"],
        interactive=False,
    )
    
    # Find the generated YAML file
    output_dir = options["output_dir"] or Path("dev_support/samples/normalized")
    yaml_files = list(output_dir.glob("account_*_norm_*__yaml__*.yml"))
    if yaml_files:
        # Sort by modification time, newest first
        yaml_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        latest_yaml = yaml_files[0]
        
        # Check if connections need provider_config
        with open(latest_yaml, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
        
        connections = yaml_data.get("globals", {}).get("connections", [])
        needs_config = any(
            "provider_config" not in conn or not conn.get("provider_config")
            for conn in connections
        )
        
        if needs_config:
            configure = inquirer.confirm(
                message="Some connections need provider_config. Configure now?",
                default=True,
                long_instruction="You can configure connection credentials now or add them manually later.",
            ).execute()
            
            if configure:
                connection_configs = prompt_connection_credentials_interactive(latest_yaml)
                
                if connection_configs:
                    # Offer to save to .env
                    save = inquirer.confirm(
                        message="Save connection credentials to .env file?",
                        default=True,
                    ).execute()
                    
                    if save:
                        save_credentials_to_env({}, connection_configs=connection_configs)

