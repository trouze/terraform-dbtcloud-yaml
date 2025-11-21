"""Utility helpers shared across importer components."""

from __future__ import annotations

import base64
import hashlib
import re


def short_hash(value: str, length: int = 12) -> str:
    """Return a short, deterministic hash derived from SHA-256."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:length]


def slugify_url(url: str) -> str:
    """Produce a snake-case slug for the source URL (host only)."""
    host = re.sub(r"^https?://", "", url.lower())
    host = host.rstrip("/")
    host = re.sub(r"[^a-z0-9]+", "_", host)
    return host.strip("_") or "unknown"


def encode_run_identifier(account_source_hash: str, run_label: str) -> str:
    """Create a stable unique run identifier for downstream tooling."""
    raw = f"{account_source_hash}_{run_label}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

