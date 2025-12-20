"""Interactive mode utilities using InquirerPy for form-like prompts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console

from .config import get_settings, Settings, SOURCE_PREFIX

console = Console()


def prompt_credentials() -> dict[str, str | int]:
    """
    Prompt for dbt Cloud API credentials if not already set in environment.
    
    Returns:
        Dictionary with 'host', 'account_id', and 'api_token'
    """
    # Check what's already set
    current_host = os.getenv(f"{SOURCE_PREFIX}HOST", "")
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
            long_instruction="Enter the base URL for your dbt Cloud instance (e.g., https://cloud.getdbt.com or https://emea.dbt.com)",
        ).execute()
        credentials["host"] = host.rstrip("/")
    else:
        credentials["host"] = current_host.rstrip("/")
    
    if not current_account_id:
        account_id_str = inquirer.text(
            message="Account ID:",
            default="",
            validate=lambda result: result.isdigit() or "Account ID must be numeric",
            long_instruction="Enter your dbt Cloud account ID (numeric)",
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
    try:
        get_settings()
        console.print("[green]✓[/green] Using credentials from environment variables")
    except RuntimeError:
        console.print("[yellow]⚠[/yellow] Some credentials missing, please provide them:")
        credentials = prompt_credentials()

        # Temporarily set environment variables for this session
        os.environ[f"{SOURCE_PREFIX}HOST"] = credentials["host"]
        os.environ[f"{SOURCE_PREFIX}ACCOUNT_ID"] = str(credentials["account_id"])
        os.environ[f"{SOURCE_PREFIX}API_TOKEN"] = credentials["api_token"]

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

