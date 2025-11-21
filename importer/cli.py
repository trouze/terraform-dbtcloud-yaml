"""Typer CLI entrypoint for the importer."""

from __future__ import annotations

import json
import logging
from datetime import datetime as dt
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import get_version
from .client import DbtCloudClient
from .config import get_settings
from .element_ids import apply_element_ids
from .fetcher import fetch_account_snapshot
from .models import AccountSnapshot
from .norm_tracker import NormalizationRunTracker
from .normalizer import MappingConfig, NormalizationContext
from .normalizer.core import normalize_snapshot
from .normalizer.writer import YAMLWriter
from .run_tracker import RunTracker
from .utils import encode_run_identifier, short_hash, slugify_url

app = typer.Typer(add_completion=False)
console = Console()


@app.callback()
def main_callback() -> None:
    console.log(f"dbtcloud-importer version {get_version()}")


def _setup_logging(log_file: Path) -> None:
    """Configure logging to both file and console."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Console handler (only warnings and errors)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Also configure importer logger
    importer_logger = logging.getLogger('importer')
    importer_logger.setLevel(logging.INFO)


def _line_item_start_value() -> int:
    raw = os.getenv("DBT_REPORT_LINE_ITEM_START")
    if raw is None:
        return 1001
    try:
        return int(raw)
    except ValueError:
        return 1001


@app.command()
def fetch(
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Path to write the account JSON export (defaults to stdout).",
    ),
    compact: bool = typer.Option(
        False,
        "--compact",
        help="Emit compact (non-pretty) JSON output.",
        is_flag=True,
    ),
    reports_dir: Optional[Path] = typer.Option(
        None,
        "--reports-dir",
        help="Directory to write summary/report markdown files (defaults to same dir as output).",
    ),
    auto_timestamp: bool = typer.Option(
        True,
        "--auto-timestamp/--no-auto-timestamp",
        help="Automatically add timestamp to output filename.",
    ),
) -> None:
    """Fetch an account JSON export via the dbt Cloud API."""
    settings = get_settings()
    
    # Initialize run tracker and start a new run
    output_dir = Path("dev_support/samples") if not output else output.parent
    run_tracker = RunTracker(output_dir / "importer_runs.json")
    run_id, timestamp = run_tracker.start_run(settings.account_id)
    
    # Setup logging early with the run timestamp
    log_filename = run_tracker.get_filename(
        settings.account_id, run_id, timestamp, "logs", "log"
    )
    log_file = output_dir / log_filename
    _setup_logging(log_file)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting dbt Cloud importer v{get_version()}")
    logger.info(f"Run ID: {run_id:03d}, Timestamp: {timestamp}")
    logger.info(f"Target account: {settings.account_id} at {settings.host}")
    
    client = DbtCloudClient(settings)
    try:
        snapshot = fetch_account_snapshot(client)
        logger.info(f"Successfully fetched snapshot: {len(snapshot.projects)} projects, {len(snapshot.globals.connections)} connections, {len(snapshot.globals.repositories)} repositories")
    except Exception as e:
        logger.exception("Failed to fetch account snapshot")
        raise
    finally:
        client.close()

    payload = snapshot.model_dump(mode="json")
    
    # Add metadata about the importer
    source_url = settings.host
    run_label = f"run_{run_id:03d}"
    timestamp_dt = dt.strptime(timestamp, "%Y%m%d_%H%M%S")
    source_url_hash = short_hash(source_url)
    account_source_hash = short_hash(f"{settings.account_id}|{source_url}")
    payload["_metadata"] = {
        "generated_at": timestamp_dt.isoformat() + "Z",
        "importer_version": get_version(),
        "run_id": run_id,
        "run_label": run_label,
        "account_id": settings.account_id,
        "source_url": source_url,
        "source_url_hash": source_url_hash,
        "source_url_slug": slugify_url(source_url),
        "account_source_hash": account_source_hash,
        "unique_run_identifier": encode_run_identifier(account_source_hash, run_label),
    }
    line_items = apply_element_ids(payload, start_number=_line_item_start_value())
    
    output_text = json.dumps(payload, indent=None if compact else 2, sort_keys=True)

    # Determine output path with run-based naming
    if output:
        if auto_timestamp:
            json_filename = run_tracker.get_filename(
                settings.account_id, run_id, timestamp, "json", "json"
            )
            output = output.parent / json_filename
        
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_text, encoding="utf-8")
        console.log(f"Wrote account JSON export to {output}")
        logger.info(f"Wrote account JSON export to {output}")
    else:
        console.print(output_text)

    _print_summary(snapshot)

    # Generate reports with consistent naming
    report_dir = reports_dir or (output.parent if output else Path("dev_support/samples"))
    report_dir.mkdir(parents=True, exist_ok=True)

    summary_filename = run_tracker.get_filename(
        settings.account_id, run_id, timestamp, "summary", "md"
    )
    report_filename = run_tracker.get_filename(
        settings.account_id, run_id, timestamp, "report", "md"
    )
    line_items_filename = run_tracker.get_filename(
        settings.account_id, run_id, timestamp, "report_items", "json"
    )
    summary_path = report_dir / summary_filename
    report_path = report_dir / report_filename
    line_items_path = report_dir / line_items_filename
    
    # Write reports (updated signature)
    from .reporter import generate_summary_report, generate_detailed_report
    summary_path.write_text(generate_summary_report(snapshot), encoding="utf-8")
    report_path.write_text(generate_detailed_report(snapshot), encoding="utf-8")
    line_items_path.write_text(json.dumps(line_items, indent=2), encoding="utf-8")
    
    console.log(f"Wrote summary report to {summary_path}")
    console.log(f"Wrote detailed report to {report_path}")
    console.log(f"Wrote report line items to {line_items_path}")
    logger.info(f"Wrote summary report to {summary_path}")
    logger.info(f"Wrote detailed report to {report_path}")
    logger.info(f"Wrote report line items to {line_items_path}")
    logger.info(f"Log file written to {log_file}")
    console.log(f"Log file written to {log_file}")


def _print_summary(snapshot) -> None:
    table = Table(title="Snapshot Summary")
    table.add_column("Metric", justify="left")
    table.add_column("Value", justify="right")
    table.add_row("Projects", str(len(snapshot.projects)))
    table.add_row("Connections", str(len(snapshot.globals.connections)))
    table.add_row("Repositories", str(len(snapshot.globals.repositories)))
    table.add_row("Service Tokens", str(len(snapshot.globals.service_tokens)))
    table.add_row("Groups", str(len(snapshot.globals.groups)))
    table.add_row("Notifications", str(len(snapshot.globals.notifications)))
    table.add_row("Webhooks", str(len(snapshot.globals.webhooks)))
    table.add_row("PrivateLink Endpoints", str(len(snapshot.globals.privatelink_endpoints)))
    console.print(table)


@app.command()
def normalize(
    input_json: Path = typer.Argument(
        ...,
        help="Path to account JSON export from 'fetch' command.",
    ),
    mapping_config: Path = typer.Option(
        Path("importer_mapping.yml"),
        "--config",
        "-c",
        help="Path to mapping configuration YAML file.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory for normalized YAML and artifacts (defaults to config value).",
    ),
) -> None:
    """Normalize a JSON export into v2 YAML format."""
    console.log(f"dbtcloud-importer normalize v{get_version()}")
    
    # Load mapping configuration
    if not mapping_config.exists():
        console.print(f"[red]Error: Mapping config not found at {mapping_config}[/red]")
        raise typer.Exit(1)
    
    try:
        config = MappingConfig.load(mapping_config)
        console.log(f"Loaded mapping config from {mapping_config}")
    except Exception as e:
        console.print(f"[red]Error loading mapping config: {e}[/red]")
        raise typer.Exit(1)
    
    # Load input JSON
    if not input_json.exists():
        console.print(f"[red]Error: Input JSON not found at {input_json}[/red]")
        raise typer.Exit(1)
    
    try:
        with open(input_json, "r", encoding="utf-8") as f:
            snapshot_data = json.load(f)
        
        # Extract metadata for run tracking
        metadata = snapshot_data.get("_metadata", {})
        account_id = metadata.get("account_id") or snapshot_data.get("account_id", 0)
        fetch_run_id = metadata.get("run_id", 0)
        
        # Reconstruct AccountSnapshot from JSON
        snapshot = AccountSnapshot(**snapshot_data)
        console.log(f"Loaded snapshot: {len(snapshot.projects)} projects")
    except Exception as e:
        console.print(f"[red]Error loading input JSON: {e}[/red]")
        raise typer.Exit(1)
    
    # Initialize normalization run tracking
    norm_output_dir = output_dir or Path(config.get_output_directory())
    norm_tracker = NormalizationRunTracker(norm_output_dir / "normalization_runs.json")
    norm_run_id, timestamp = norm_tracker.start_run(account_id, fetch_run_id)
    
    # Setup logging
    log_filename = f"account_{account_id}_norm_{norm_run_id:03d}__logs__{timestamp}.log"
    log_file = norm_output_dir / log_filename
    _setup_logging(log_file)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting normalization v{get_version()}")
    logger.info(f"Normalization Run ID: {norm_run_id:03d}, Timestamp: {timestamp}")
    logger.info(f"Source Fetch Run ID: {fetch_run_id:03d}")
    logger.info(f"Mapping config: {mapping_config}")
    logger.info(f"Scope mode: {config.get_scope_mode()}")
    
    # Initialize normalization context
    context = NormalizationContext(config)
    
    # Normalize snapshot to v2 structure
    console.log("Normalizing account snapshot to v2 YAML structure...")
    try:
        normalized_data = normalize_snapshot(snapshot, config, context)
        logger.info("Normalization complete")
    except Exception as e:
        logger.exception("Normalization failed")
        console.print(f"[red]Error during normalization: {e}[/red]")
        raise typer.Exit(1)
    
    # Write YAML and artifacts
    writer = YAMLWriter(config, context)
    try:
        artifacts = writer.write_all_artifacts(
            normalized_data,
            norm_output_dir,
            norm_run_id,
            timestamp,
            account_id,
        )
        logger.info("All artifacts written successfully")
    except Exception as e:
        logger.exception("Failed to write artifacts")
        console.print(f"[red]Error writing artifacts: {e}[/red]")
        raise typer.Exit(1)
    
    # Print summary
    console.print("\n[bold green]Normalization Complete[/bold green]")
    
    summary_table = Table(title="Normalization Summary")
    summary_table.add_column("Metric", justify="left")
    summary_table.add_column("Value", justify="right")
    summary_table.add_row("Projects Included", str(len(normalized_data.get("projects", []))))
    summary_table.add_row("LOOKUP Placeholders", str(len(context.placeholders)))
    summary_table.add_row("Resources Excluded", str(len(context.exclusions)))
    
    # Count collisions across all namespaces
    total_collisions = sum(
        sum(1 for count in namespace_counts.values() if count > 1)
        for namespace_counts in context.collisions.values()
    )
    summary_table.add_row("Key Collisions", str(total_collisions))
    console.print(summary_table)
    
    artifacts_table = Table(title="Generated Artifacts")
    artifacts_table.add_column("Type", justify="left")
    artifacts_table.add_column("Path", justify="left")
    for artifact_type, artifact_path in artifacts.items():
        artifacts_table.add_row(artifact_type, str(artifact_path))
    artifacts_table.add_row("logs", str(log_file))
    console.print(artifacts_table)
    
    console.log(f"\nLog file: {log_file}")
    
    if context.placeholders:
        console.print(f"\n[yellow]⚠ Warning: {len(context.placeholders)} LOOKUP placeholders need manual resolution.[/yellow]")
        console.print(f"See {artifacts.get('lookups')} for details.")
    
    if context.exclusions:
        console.print(f"\n[yellow]ℹ Info: {len(context.exclusions)} resources were excluded.[/yellow]")
        console.print(f"See {artifacts.get('exclusions')} for details.")


def run() -> None:
    app()


