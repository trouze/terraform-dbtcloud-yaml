"""Track importer runs with sequential run IDs."""

from __future__ import annotations

import json
from datetime import datetime as dt
from pathlib import Path
from typing import TypedDict


class RunInfo(TypedDict):
    run_id: int
    timestamp: str
    account_id: int
    started_at: str


class RunTracker:
    """Manages run IDs and timestamps for importer executions."""

    def __init__(self, control_file: Path):
        self.control_file = control_file
        self.control_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_control_data(self) -> dict[str, list[RunInfo]]:
        """Load the control file, creating it if it doesn't exist."""
        if not self.control_file.exists():
            return {}
        
        try:
            with open(self.control_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_control_data(self, data: dict[str, list[RunInfo]]) -> None:
        """Save the control file."""
        with open(self.control_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def start_run(self, account_id: int) -> tuple[int, str]:
        """
        Start a new run and return the run ID and timestamp.
        
        Returns:
            Tuple of (run_id, timestamp_str) where timestamp is in YYYYMMDD_HHMMSS format
        """
        data = self._load_control_data()
        account_key = str(account_id)
        
        # Get the next run ID for this account
        if account_key not in data:
            data[account_key] = []
        
        account_runs = data[account_key]
        next_run_id = len(account_runs) + 1
        
        # Generate timestamp
        now = dt.utcnow()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        
        # Record the run
        run_info: RunInfo = {
            "run_id": next_run_id,
            "timestamp": timestamp,
            "account_id": account_id,
            "started_at": now.isoformat() + "Z",
        }
        account_runs.append(run_info)
        
        # Save updated control file
        self._save_control_data(data)
        
        return next_run_id, timestamp

    def get_filename(
        self,
        account_id: int,
        run_id: int,
        timestamp: str,
        file_type: str,
        extension: str,
    ) -> str:
        """
        Generate a standardized filename.
        
        Args:
            account_id: Account ID
            run_id: Run ID (will be zero-padded to 3 digits)
            timestamp: Timestamp string (YYYYMMDD_HHMMSS format)
            file_type: Type of file (json, summary, report, logs)
            extension: File extension (e.g., 'json', 'md', 'log')
        
        Returns:
            Filename in format: account_{ID}_run_{RUN}__{TYPE}__{TIMESTAMP}.{EXT}
        """
        return f"account_{account_id}_run_{run_id:03d}__{file_type}__{timestamp}.{extension}"

