"""Track normalization runs with sequential IDs (separate from fetch runs)."""

from __future__ import annotations

import json
from datetime import datetime as dt
from pathlib import Path
from typing import TypedDict


class NormRunInfo(TypedDict):
    norm_run_id: int
    timestamp: str
    account_id: int
    source_fetch_run_id: int
    started_at: str


class NormalizationRunTracker:
    """Manages normalization run IDs and timestamps."""

    def __init__(self, control_file: Path):
        self.control_file = control_file
        self.control_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_control_data(self) -> dict[str, list[NormRunInfo]]:
        """Load the control file, creating it if it doesn't exist."""
        if not self.control_file.exists():
            return {}
        
        try:
            with open(self.control_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_control_data(self, data: dict[str, list[NormRunInfo]]) -> None:
        """Save the control file."""
        with open(self.control_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def start_run(self, account_id: int, fetch_run_id: int) -> tuple[int, str]:
        """
        Start a new normalization run and return the run ID and timestamp.
        
        Args:
            account_id: Account ID
            fetch_run_id: The fetch run ID that this normalization is based on
        
        Returns:
            Tuple of (norm_run_id, timestamp_str) where timestamp is in YYYYMMDD_HHMMSS format
        """
        data = self._load_control_data()
        account_key = str(account_id)
        
        # Get the next normalization run ID for this account
        if account_key not in data:
            data[account_key] = []
        
        account_runs = data[account_key]
        next_norm_run_id = len(account_runs) + 1
        
        # Generate timestamp
        now = dt.utcnow()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        
        # Record the run
        run_info: NormRunInfo = {
            "norm_run_id": next_norm_run_id,
            "timestamp": timestamp,
            "account_id": account_id,
            "source_fetch_run_id": fetch_run_id,
            "started_at": now.isoformat() + "Z",
        }
        account_runs.append(run_info)
        
        # Save updated control file
        self._save_control_data(data)
        
        return next_norm_run_id, timestamp

