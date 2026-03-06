"""Shared Terraform utility functions.

Consolidated from match.py, adopt.py, utilities.py, and deploy.py to provide
a single source of truth for path resolution, environment setup, target flag
construction, and terraform command execution.

See PRD 43.03 — Unified Protect & Adopt Pipeline.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from importer.web.state import AppState
    from importer.web.utils.protection_intent import ProtectionIntentManager

logger = logging.getLogger(__name__)

# Module prefix for Terraform resource addresses.
MODULE_PREFIX = "module.dbt_cloud.module.projects_v2[0]"


def _dbg_db419a(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "db419a",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(
            "/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-db419a.log",
            "a",
            encoding="utf-8",
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        return


def _project_root(state: Optional["AppState"] = None) -> Path:
    """Return active project root when available, else repository root."""
    project_path = getattr(state, "project_path", None) if state is not None else None
    if project_path:
        return Path(str(project_path)).resolve()
    return Path(__file__).parent.parent.parent.parent.resolve()


@dataclass(frozen=True)
class OutputBudget:
    """Bounded terminal rendering budget for process output."""

    max_lines: int
    head_lines: int
    tail_lines: int


def _dbg_673991(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    """Debug logging disabled after fix verification."""
    return


def budget_output_lines(lines: list[str], budget: Optional[OutputBudget]) -> tuple[list[str], int]:
    """Apply head/tail output budget, returning rendered lines + omitted count."""
    if budget is None or len(lines) <= budget.max_lines:
        return lines, 0

    head = max(0, budget.head_lines)
    tail = max(0, budget.tail_lines)
    if head + tail > budget.max_lines:
        head = min(head, budget.max_lines)
        tail = max(0, budget.max_lines - head)

    if head == 0 and tail == 0:
        return [], len(lines)

    kept = lines[:head] + lines[-tail:] if tail > 0 else lines[:head]
    omitted = len(lines) - len(kept)
    return kept, max(0, omitted)


def emit_process_output(
    stdout: str,
    stderr: str,
    *,
    on_stdout_line: Callable[[str], None],
    on_stderr_line: Callable[[str], None],
    stdout_budget: Optional[OutputBudget] = None,
    stderr_budget: Optional[OutputBudget] = None,
    on_omitted: Optional[Callable[[int], None]] = None,
) -> tuple[int, int]:
    """Emit stdout/stderr to terminal callbacks with optional budgets."""
    stdout_lines, stdout_omitted = budget_output_lines(stdout.splitlines(), stdout_budget)
    stderr_lines, stderr_omitted = budget_output_lines(stderr.splitlines(), stderr_budget)
    omitted_total = stdout_omitted + stderr_omitted
    if omitted_total > 0 and on_omitted:
        on_omitted(omitted_total)

    for line in stdout_lines:
        if line.strip():
            on_stdout_line(line)
    for line in stderr_lines:
        if line.strip():
            on_stderr_line(line)

    return stdout_omitted, stderr_omitted


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_deployment_paths(
    state: "AppState",
) -> tuple[Path, Path, Optional[Path]]:
    """Resolve the terraform directory, YAML config file, and baseline YAML.

    Returns:
        (tf_path, yaml_file, baseline_yaml_path)

        * ``tf_path`` is always an absolute, resolved Path.
        * ``yaml_file`` is the best-candidate YAML config (may not exist if
          the deployment directory hasn't been set up yet).
        * ``baseline_yaml_path`` is the target baseline YAML path or ``None``.
    """
    # --- Terraform directory ---
    tf_dir = state.deploy.terraform_dir or "deployments/migration"
    tf_path = Path(tf_dir)
    if not tf_path.is_absolute():
        tf_path = _project_root(state) / tf_dir
    tf_path = tf_path.resolve()
    # region agent log
    _dbg_db419a(
        "H34",
        "terraform_helpers.py:resolve_deployment_paths",
        "resolved deployment paths for terraform helpers",
        {
            "project_path": getattr(state, "project_path", None),
            "active_project": getattr(state, "active_project", None),
            "terraform_dir_state": getattr(state.deploy, "terraform_dir", None),
            "resolved_tf_path": str(tf_path),
            "root_used_for_relative_tf_dir": str(_project_root(state)),
            "uses_absolute_tf_dir": Path(tf_dir).is_absolute(),
        },
    )
    # endregion

    # --- YAML config file ---
    yaml_file = tf_path / "dbt-cloud-config.yml"
    if not yaml_file.exists():
        merged_yaml = tf_path / "dbt-cloud-config-merged.yml"
        if merged_yaml.exists():
            yaml_file = merged_yaml

    if not yaml_file.exists() and state.fetch.output_dir:
        fetch_yaml = Path(state.fetch.output_dir) / "dbt-cloud-config.yml"
        if fetch_yaml.exists():
            yaml_file = fetch_yaml

    # --- Baseline YAML ---
    baseline_yaml_path: Optional[Path] = None
    try:
        from importer.web.utils.target_intent import normalize_target_fetch

        raw = normalize_target_fetch(state)
        if raw:
            baseline_yaml_path = Path(raw)
    except Exception:
        pass

    return tf_path, yaml_file, baseline_yaml_path


# ---------------------------------------------------------------------------
# Terraform environment
# ---------------------------------------------------------------------------

def get_terraform_env(state: "AppState") -> dict[str, str]:
    """Build the environment dict for ``subprocess.run`` terraform calls.

    Replicates the logic from ``deploy.py:_get_terraform_env`` without the
    NiceGUI-specific logging.
    """
    env = dict(os.environ)

    api_token = state.target_credentials.api_token or ""
    account_id = state.target_credentials.account_id or ""
    host_url = state.target_credentials.host_url or ""
    token_type = getattr(state.target_credentials, "token_type", "")

    # Normalize host URL
    base_host = (host_url or "https://cloud.getdbt.com").rstrip("/")
    if not base_host.endswith("/api"):
        host_url = f"{base_host}/api"
    else:
        host_url = base_host

    env["TF_VAR_dbt_account_id"] = str(account_id)
    env["TF_VAR_dbt_token"] = api_token
    env["TF_VAR_dbt_host_url"] = host_url

    # PAT support
    is_pat = token_type == "user_token" or (
        api_token and api_token.startswith("dbtu_")
    )
    if is_pat:
        env["TF_VAR_dbt_pat"] = api_token

    # Provider fallback
    env["DBT_CLOUD_ACCOUNT_ID"] = str(account_id)
    env["DBT_CLOUD_TOKEN"] = api_token
    env["DBT_CLOUD_HOST_URL"] = host_url

    # Use local provider dev override when project .terraformrc exists (for debugging)
    project_root = _project_root(state)
    terraformrc = project_root / ".terraformrc"
    if terraformrc.exists():
        env["TF_CLI_CONFIG_FILE"] = str(terraformrc.resolve())

    return env


# ---------------------------------------------------------------------------
# Target flag construction
# ---------------------------------------------------------------------------

def build_target_flags(
    tf_path: Path,
    protection_intent_manager: Optional["ProtectionIntentManager"] = None,
) -> list[str]:
    """Build ``-target`` flags for a scoped ``terraform plan``/``apply``.

    Collects target addresses from three sources:

    1. Protection intents with ``needs_tf_move`` (both old and new addresses).
    2. ``protection_moves.tf`` (``from``/``to`` addresses in moved blocks).
    3. ``adopt_imports.tf`` (``to`` addresses in import blocks).

    Returns:
        A flat list like ``["-target", "addr1", "-target", "addr2", ...]``.
    """
    from importer.web.utils.protection_manager import get_resource_address

    target_addresses: list[str] = []
    source1_intent_addresses = 0
    source2_move_addresses = 0
    source3_import_addresses = 0

    # 1) From protection intent manager
    if protection_intent_manager is not None:
        for ikey, intent in protection_intent_manager._intent.items():
            if not intent.needs_tf_move:
                continue

            if ":" in ikey:
                rtype, rkey = ikey.split(":", 1)
            elif intent.resource_type:
                rtype = intent.resource_type
                rkey = ikey
            else:
                # Legacy project-level key → expand to PRJ + REP + PREP
                for legacy_type in ("PRJ", "REP", "PREP"):
                    try:
                        target_addresses.append(
                            get_resource_address(legacy_type, ikey, protected=intent.protected)
                        )
                        target_addresses.append(
                            get_resource_address(legacy_type, ikey, protected=not intent.protected)
                        )
                    except (ValueError, KeyError):
                        pass
                continue

            try:
                target_addresses.append(
                    get_resource_address(rtype, rkey, protected=intent.protected)
                )
                target_addresses.append(
                    get_resource_address(rtype, rkey, protected=not intent.protected)
                )
                source1_intent_addresses += 2
            except (ValueError, KeyError):
                pass

    # 2) From protection_moves.tf
    moves_tf = tf_path / "protection_moves.tf"
    if moves_tf.exists():
        content = moves_tf.read_text()
        for m in re.finditer(r"(?:from|to)\s*=\s*(module\.\S+)", content):
            addr = m.group(1)
            if addr not in target_addresses:
                target_addresses.append(addr)
                source2_move_addresses += 1

    # 3) From adopt_imports.tf
    imports_tf = tf_path / "adopt_imports.tf"
    if imports_tf.exists():
        content = imports_tf.read_text()
        for m in re.finditer(r"to\s*=\s*(module\.\S+)", content):
            addr = m.group(1)
            if addr not in target_addresses:
                target_addresses.append(addr)
                source3_import_addresses += 1

    # Build flat flag list
    flags: list[str] = []
    for addr in target_addresses:
        flags.extend(["-target", addr])

    # region agent log
    _dbg_673991(
        "H6",
        "terraform_helpers.py:build_target_flags",
        "target flag source breakdown",
        {
            "using_intent_manager": protection_intent_manager is not None,
            "source1_intent_addresses": source1_intent_addresses,
            "source2_move_addresses": source2_move_addresses,
            "source3_import_addresses": source3_import_addresses,
            "total_addresses": len(target_addresses),
            "sample": target_addresses[:30],
        },
    )
    # endregion

    return flags


# ---------------------------------------------------------------------------
# Terraform command execution
# ---------------------------------------------------------------------------

async def run_terraform_command(
    cmd: list[str],
    tf_path: Path,
    env: dict[str, str],
    *,
    on_output: Optional[Callable[[str], None]] = None,
) -> tuple[int, str, str]:
    """Run a terraform command asynchronously via ``subprocess.run``.

    Args:
        cmd: The full command list, e.g. ``["terraform", "plan", ...]``.
        tf_path: Working directory for the command.
        env: Environment variables dict (from ``get_terraform_env``).
        on_output: Optional callback invoked with each stdout/stderr line.

    Returns:
        ``(returncode, stdout, stderr)``
    """
    result = await asyncio.to_thread(
        subprocess.run,
        cmd,
        cwd=str(tf_path),
        capture_output=True,
        text=True,
        env=env,
    )

    if on_output:
        for line in result.stdout.splitlines():
            on_output(line)
        for line in result.stderr.splitlines():
            on_output(line)

    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# TF state address reader
# ---------------------------------------------------------------------------

def read_tf_state_addresses(tf_path: Path) -> set[str]:
    """Read all resource addresses from ``terraform.tfstate``.

    Returns an empty set if the state file does not exist or cannot be parsed.
    """
    state_file = tf_path / "terraform.tfstate"
    if not state_file.exists():
        return set()

    try:
        data = json.loads(state_file.read_text())
    except Exception:
        return set()

    addresses: set[str] = set()
    for res in data.get("resources", []):
        mod = res.get("module", "")
        rtype = res.get("type", "")
        rname = res.get("name", "")
        for inst in res.get("instances", []):
            ik = inst.get("index_key", "")
            if ik:
                addresses.add(f'{mod}.{rtype}.{rname}["{ik}"]')
            else:
                addresses.add(f"{mod}.{rtype}.{rname}")

    return addresses
