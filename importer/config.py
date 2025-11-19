"""Configuration helpers for the importer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ENV_FILE_CANDIDATES = (".env", ".env.local", ".env.importer")

# Environment variable prefixes
SOURCE_PREFIX = "DBT_SOURCE_"  # For source account credentials (import side)
TARGET_PREFIX = "DBT_TARGET_"  # For target account credentials (future use)


def _load_dotenv() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for filename in ENV_FILE_CANDIDATES:
        env_path = repo_root / filename
        if env_path.exists():
            load_dotenv(env_path, override=False)


@dataclass
class Settings:
    host: str
    account_id: int
    api_token: str
    timeout: float = 30.0
    max_retries: int = 5
    backoff_factor: float = 1.5
    rate_limit_retry_after: bool = True
    verify_ssl: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()

        host = os.getenv(f"{SOURCE_PREFIX}HOST")
        account_id_raw = os.getenv(f"{SOURCE_PREFIX}ACCOUNT_ID")
        api_token = os.getenv(f"{SOURCE_PREFIX}API_TOKEN")

        missing = [
            name
            for name, value in {
                f"{SOURCE_PREFIX}HOST": host,
                f"{SOURCE_PREFIX}ACCOUNT_ID": account_id_raw,
                f"{SOURCE_PREFIX}API_TOKEN": api_token,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

        try:
            account_id = int(account_id_raw)
        except ValueError as exc:
            raise RuntimeError(f"{SOURCE_PREFIX}ACCOUNT_ID must be an integer") from exc

        timeout = float(os.getenv(f"{SOURCE_PREFIX}API_TIMEOUT", "30"))
        max_retries = int(os.getenv(f"{SOURCE_PREFIX}API_MAX_RETRIES", "5"))
        backoff_factor = float(os.getenv(f"{SOURCE_PREFIX}API_BACKOFF_FACTOR", "1.5"))
        rate_limit_retry_after = os.getenv(f"{SOURCE_PREFIX}API_RETRY_AFTER", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        verify_ssl = os.getenv(f"{SOURCE_PREFIX}SSL_VERIFY", "true").lower() in {"1", "true", "yes", "on"}

        return cls(
            host=host.rstrip("/"),
            account_id=account_id,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            rate_limit_retry_after=rate_limit_retry_after,
            verify_ssl=verify_ssl,
        )


def get_settings() -> Settings:
    return Settings.from_env()


