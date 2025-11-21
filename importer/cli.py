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


def run() -> None:
    app()


