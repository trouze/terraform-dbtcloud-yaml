"""Typer CLI entrypoint for the importer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import get_version
from .client import DbtCloudClient
from .config import get_settings
from .fetcher import fetch_account_snapshot

app = typer.Typer(add_completion=False)
console = Console()


@app.callback()
def main_callback() -> None:
    console.log(f"dbtcloud-importer version {get_version()}")


@app.command()
def fetch(
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Path to write the account snapshot JSON (defaults to stdout).",
    ),
    compact: bool = typer.Option(
        False,
        "--compact",
        help="Emit compact (non-pretty) JSON output.",
        is_flag=True,
    ),
) -> None:
    """Fetch an account snapshot via the dbt Cloud API."""
    settings = get_settings()
    client = DbtCloudClient(settings)
    try:
        snapshot = fetch_account_snapshot(client)
    finally:
        client.close()

    payload = snapshot.model_dump(mode="json")
    output_text = json.dumps(payload, indent=None if compact else 2, sort_keys=True)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_text, encoding="utf-8")
        console.log(f"Wrote snapshot to {output}")
    else:
        console.print(output_text)

    _print_summary(snapshot)


def _print_summary(snapshot) -> None:
    table = Table(title="Snapshot Summary")
    table.add_column("Metric", justify="left")
    table.add_column("Value", justify="right")
    table.add_row("Projects", str(len(snapshot.projects)))
    table.add_row("Connections", str(len(snapshot.globals.connections)))
    table.add_row("Repositories", str(len(snapshot.globals.repositories)))
    console.print(table)


def run() -> None:
    app()


