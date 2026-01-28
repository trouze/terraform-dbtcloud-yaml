"""Terraform import utilities for importing existing resources into state."""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union


@dataclass
class ImportResult:
    """Result of a single resource import operation."""
    
    resource_address: str
    target_id: str
    source_key: str
    resource_type: str
    status: str = "pending"  # "pending", "importing", "success", "failed", "skipped"
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class ImportSummary:
    """Summary of import operation results."""
    
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    duration_ms: int = 0
    results: list[ImportResult] = field(default_factory=list)


# Resource type to Terraform resource type mapping
RESOURCE_TYPE_TO_TF = {
    "PRJ": "dbtcloud_project",
    "ENV": "dbtcloud_environment",
    "JOB": "dbtcloud_job",
    "CON": "dbtcloud_global_connection",
    "REP": "dbtcloud_repository",
    "PREP": "dbtcloud_project_repository",
    "TOK": "dbtcloud_service_token",
    "GRP": "dbtcloud_group",
    "NOT": "dbtcloud_notification",
    "WEB": "dbtcloud_webhook",
    "VAR": "dbtcloud_environment_variable",
}


def _debug_log(payload: dict) -> None:
    """Append a debug log line for runtime evidence."""
    # region agent log
    try:
        with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug.log", "a") as log_file:
            log_file.write(json.dumps(payload) + "\n")
    except Exception:
        pass
    # endregion


def get_terraform_resource_address(
    source_key: str,
    resource_type: str,
    module_name: str = "dbt_cloud",
) -> str:
    """Generate a Terraform resource address from a source key.
    
    Args:
        source_key: The source entity key (e.g., "project__my_project")
        resource_type: The resource type code (e.g., "PRJ")
        module_name: The Terraform module name
        
    Returns:
        Terraform resource address (e.g., "module.dbt_cloud.dbtcloud_project.my_project")
    """
    tf_type = RESOURCE_TYPE_TO_TF.get(resource_type, "dbtcloud_unknown")
    
    # Convert source key to resource name
    # Source key format: "type__name" or "type__parent__name"
    # We just need the last part, sanitized for Terraform
    parts = source_key.split("__")
    resource_name = parts[-1] if parts else source_key
    
    # Sanitize for Terraform identifier
    resource_name = re.sub(r'[^a-zA-Z0-9_]', '_', resource_name.lower())
    resource_name = re.sub(r'_+', '_', resource_name)  # Collapse multiple underscores
    resource_name = resource_name.strip('_')
    
    if not resource_name:
        resource_name = "resource"
    
    address = f"module.{module_name}.{tf_type}.{resource_name}"
    _debug_log({
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "H1",
        "location": "terraform_import.py:83",
        "message": "computed terraform resource address",
        "data": {
            "source_key": source_key,
            "resource_type": resource_type,
            "module_name": module_name,
            "tf_type": tf_type,
            "resource_name": resource_name,
            "address": address,
        },
        "timestamp": int(time.time() * 1000),
    })
    return address


def generate_import_blocks(
    mappings: list[dict],
    module_name: str = "dbt_cloud",
) -> str:
    """Generate Terraform 1.5+ import blocks from mappings.
    
    Args:
        mappings: List of mapping dictionaries with source_key, target_id, resource_type
        module_name: The Terraform module name
        
    Returns:
        Content for imports.tf file with import {} blocks
    """
    blocks = []
    
    # Header comment
    blocks.append("# Generated import blocks for existing target resources")
    blocks.append("# Run 'terraform plan' to process these imports")
    blocks.append("")
    
    _debug_log({
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "H2",
        "location": "terraform_import.py:106",
        "message": "generate_import_blocks start",
        "data": {
            "module_name": module_name,
            "mapping_count": len(mappings),
        },
        "timestamp": int(time.time() * 1000),
    })
    for mapping in mappings:
        source_key = mapping.get("source_key", "")
        target_id = mapping.get("target_id", "")
        resource_type = mapping.get("resource_type", "")
        source_name = mapping.get("source_name", "")
        
        if not source_key or not target_id:
            continue
        
        # Get the Terraform resource address
        tf_address = get_terraform_resource_address(source_key, resource_type, module_name)
        _debug_log({
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "H3",
            "location": "terraform_import.py:120",
            "message": "import block mapping",
            "data": {
                "source_key": source_key,
                "resource_type": resource_type,
                "target_id": target_id,
                "tf_address": tf_address,
            },
            "timestamp": int(time.time() * 1000),
        })
        
        # Add comment with human-readable info
        blocks.append(f"# {source_name} -> Target ID {target_id}")
        blocks.append("import {")
        blocks.append(f'  to = {tf_address}')
        blocks.append(f'  id = "{target_id}"')
        blocks.append("}")
        blocks.append("")
    
    return "\n".join(blocks)


def generate_import_commands(
    mappings: list[dict],
    module_name: str = "dbt_cloud",
) -> list[tuple[str, str, str, str]]:
    """Generate legacy terraform import commands.
    
    Args:
        mappings: List of mapping dictionaries
        module_name: The Terraform module name
        
    Returns:
        List of (resource_address, import_id, source_key, resource_type) tuples
    """
    commands = []
    
    for mapping in mappings:
        source_key = mapping.get("source_key", "")
        target_id = mapping.get("target_id", "")
        resource_type = mapping.get("resource_type", "")
        
        if not source_key or not target_id:
            continue
        
        tf_address = get_terraform_resource_address(source_key, resource_type, module_name)
        commands.append((tf_address, str(target_id), source_key, resource_type))
    
    return commands


async def detect_terraform_version(cwd: Union[str, Path]) -> tuple[Optional[tuple[int, int, int]], Optional[str]]:
    """Detect installed Terraform version.
    
    Args:
        cwd: Working directory
        
    Returns:
        Tuple of (version_tuple, error_message)
        version_tuple is (major, minor, patch) or None if error
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "terraform", "version", "-json",
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            # Try without -json flag for older versions
            process2 = await asyncio.create_subprocess_exec(
                "terraform", "version",
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout2, _ = await process2.communicate()
            
            # Parse version from "Terraform v1.5.0"
            match = re.search(r'v(\d+)\.(\d+)\.(\d+)', stdout2.decode())
            if match:
                return (int(match.group(1)), int(match.group(2)), int(match.group(3))), None
            return None, "Could not parse Terraform version"
        
        data = json.loads(stdout.decode())
        version_str = data.get("terraform_version", "")
        
        # Parse version string "1.5.0"
        match = re.match(r'(\d+)\.(\d+)\.(\d+)', version_str)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3))), None
        
        return None, f"Could not parse version: {version_str}"
        
    except FileNotFoundError:
        return None, "Terraform not found. Please install Terraform."
    except Exception as e:
        return None, f"Error detecting Terraform version: {e}"


def supports_import_blocks(version: tuple[int, int, int]) -> bool:
    """Check if Terraform version supports import {} blocks.
    
    Import blocks were added in Terraform 1.5.0.
    
    Args:
        version: (major, minor, patch) tuple
        
    Returns:
        True if import blocks are supported
    """
    return version >= (1, 5, 0)


async def run_terraform_import(
    resource_address: str,
    import_id: str,
    cwd: Union[str, Path],
    on_output: Optional[Callable[[str], None]] = None,
) -> tuple[bool, str]:
    """Run a single terraform import command.
    
    Args:
        resource_address: The Terraform resource address
        import_id: The ID to import
        cwd: Working directory
        on_output: Optional callback for output lines
        
    Returns:
        Tuple of (success, output)
    """
    output_lines = []
    
    try:
        process = await asyncio.create_subprocess_exec(
            "terraform", "import", resource_address, import_id,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        async for line in process.stdout:
            decoded = line.decode()
            output_lines.append(decoded)
            if on_output:
                on_output(decoded)
        
        await process.wait()
        
        output = "".join(output_lines)
        success = process.returncode == 0
        
        return success, output
        
    except Exception as e:
        return False, str(e)


async def run_import_batch(
    import_commands: list[tuple[str, str, str, str]],
    cwd: Union[str, Path],
    on_progress: Optional[Callable[[ImportResult], None]] = None,
    on_output: Optional[Callable[[str], None]] = None,
) -> ImportSummary:
    """Run a batch of terraform import commands sequentially.
    
    Args:
        import_commands: List of (address, id, source_key, resource_type) tuples
        cwd: Working directory
        on_progress: Callback for progress updates per resource
        on_output: Callback for command output
        
    Returns:
        ImportSummary with results
    """
    summary = ImportSummary(total=len(import_commands))
    start_time = time.time()
    
    for address, import_id, source_key, resource_type in import_commands:
        result = ImportResult(
            resource_address=address,
            target_id=import_id,
            source_key=source_key,
            resource_type=resource_type,
            status="importing",
        )
        
        if on_progress:
            on_progress(result)
        
        import_start = time.time()
        success, output = await run_terraform_import(
            address, import_id, cwd, on_output
        )
        import_duration = int((time.time() - import_start) * 1000)
        
        result.duration_ms = import_duration
        
        if success:
            result.status = "success"
            summary.success += 1
        else:
            result.status = "failed"
            result.error_message = output
            summary.failed += 1
        
        summary.results.append(result)
        
        if on_progress:
            on_progress(result)
    
    summary.duration_ms = int((time.time() - start_time) * 1000)
    return summary


def write_import_blocks_file(
    mappings: list[dict],
    output_dir: Union[str, Path],
    module_name: str = "dbt_cloud",
    filename: str = "imports.tf",
) -> tuple[Optional[Path], Optional[str]]:
    """Write import blocks to a file.
    
    Args:
        mappings: List of mapping dictionaries
        output_dir: Directory to write to
        module_name: Terraform module name
        filename: Output filename
        
    Returns:
        Tuple of (file_path, error_message)
    """
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        content = generate_import_blocks(mappings, module_name)
        file_path = output_dir / filename
        
        file_path.write_text(content, encoding="utf-8")
        return file_path, None
        
    except Exception as e:
        return None, str(e)


def generate_reconcile_import_blocks(
    drift_results: list,
    module_name: str = "dbt_cloud",
) -> str:
    """Generate Terraform import blocks for state reconciliation.
    
    This is used to adopt current target resources into Terraform state
    when drift has been detected (e.g., ID mismatch or missing in state).
    
    Args:
        drift_results: List of DriftResult objects or dicts from drift detection
        module_name: The Terraform module name
        
    Returns:
        Content for reconcile_imports.tf file with import {} blocks
    """
    from importer.web.utils.drift_detector import DriftType
    
    blocks = []
    
    # Header comment
    blocks.append("# Generated import blocks for state reconciliation")
    blocks.append("# These imports will adopt current target resources into Terraform state")
    blocks.append("# Run 'terraform plan' to preview, then 'terraform apply' to execute")
    blocks.append("")
    
    import_count = 0
    
    for drift in drift_results:
        # Handle both DriftResult objects and dicts
        if hasattr(drift, "drift_type"):
            drift_type = drift.drift_type
            element_code = drift.element_code
            resource_name = drift.resource_name
            state_address = drift.state_address
            target_id = drift.target_id
            adopt = drift.adopt
        else:
            # Dict format
            drift_type_str = drift.get("drift_type", "")
            if isinstance(drift_type_str, str):
                try:
                    drift_type = DriftType(drift_type_str)
                except ValueError:
                    continue
            else:
                drift_type = drift_type_str
            element_code = drift.get("element_code", "")
            resource_name = drift.get("resource_name", "")
            state_address = drift.get("state_address")
            target_id = drift.get("target_id")
            adopt = drift.get("adopt", False)
        
        # Only process adoptable drift types that are marked for adoption
        if not adopt:
            continue
        
        if drift_type not in {DriftType.ID_MISMATCH, DriftType.MISSING_IN_STATE}:
            continue
        
        if not target_id:
            continue
        
        # For ID_MISMATCH, we use the existing state address
        # For MISSING_IN_STATE, we need to generate an address
        if state_address:
            tf_address = state_address
            address_reason = "state_address"
        else:
            # Generate address from element code and name
            tf_type = RESOURCE_TYPE_TO_TF.get(element_code, "dbtcloud_unknown")
            # Sanitize resource name for Terraform
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', resource_name.lower())
            safe_name = re.sub(r'_+', '_', safe_name).strip('_')
            if not safe_name:
                safe_name = "resource"
            tf_address = f"module.{module_name}.{tf_type}.{safe_name}"
            address_reason = "default"

            # Special-case repositories in v2 module layout
            if element_code == "REP":
                project_name = ""
                if isinstance(drift, dict):
                    context = drift.get("context") or {}
                    if isinstance(context, dict):
                        project_name = context.get("project_name", "") or ""
                if project_name:
                    tf_address = (
                        f"module.{module_name}.module.projects_v2[0]."
                        f"dbtcloud_repository.repositories[\"{project_name}\"]"
                    )
                    address_reason = "projects_v2_repo"
            if element_code == "PREP":
                project_name = ""
                if isinstance(drift, dict):
                    context = drift.get("context") or {}
                    if isinstance(context, dict):
                        project_name = context.get("project_name", "") or ""
                if project_name:
                    tf_address = (
                        f"module.{module_name}.module.projects_v2[0]."
                        f"dbtcloud_project_repository.project_repositories[\"{project_name}\"]"
                    )
                    address_reason = "projects_v2_project_repository"
        _debug_log({
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "H11",
            "location": "terraform_import.py:472",
            "message": "reconcile import address computed",
            "data": {
                "element_code": element_code,
                "resource_name": resource_name,
                "state_address": state_address,
                "target_id": target_id,
                "module_name": module_name,
                "tf_address": tf_address,
                "address_reason": address_reason,
            },
            "timestamp": int(time.time() * 1000),
        })
        
        # Determine the import ID format based on resource type
        # Some resources need composite IDs like project_id:resource_id
        import_id = str(target_id)
        
        # Repositories need project_id:repository_id format
        # Note: PREP (project_repository) target_id is already in composite format
        if element_code == "REP":
            project_id = None
            if isinstance(drift, dict):
                context = drift.get("context") or {}
                if isinstance(context, dict):
                    project_id = context.get("project_id")
            if project_id:
                import_id = f"{project_id}:{target_id}"
        
        # Add comment with context
        if drift_type == DriftType.ID_MISMATCH:
            blocks.append(f"# {resource_name} - adopting target ID {target_id} (was different in state)")
        else:
            blocks.append(f"# {resource_name} - importing target ID {target_id} (not in state)")
        
        blocks.append("import {")
        blocks.append(f'  to = {tf_address}')
        blocks.append(f'  id = "{import_id}"')
        blocks.append("}")
        blocks.append("")
        import_count += 1
    
    if import_count == 0:
        return "# No resources selected for adoption\n"
    
    return "\n".join(blocks)


def write_reconcile_import_blocks_file(
    drift_results: list,
    output_dir: Union[str, Path],
    module_name: str = "dbt_cloud",
    filename: str = "reconcile_imports.tf",
) -> tuple[Optional[Path], Optional[str]]:
    """Write reconciliation import blocks to a file.
    
    Args:
        drift_results: List of DriftResult objects from drift detection
        output_dir: Directory to write to
        module_name: Terraform module name
        filename: Output filename
        
    Returns:
        Tuple of (file_path, error_message)
    """
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        content = generate_reconcile_import_blocks(drift_results, module_name)
        file_path = output_dir / filename
        
        file_path.write_text(content, encoding="utf-8")
        return file_path, None
        
    except Exception as e:
        return None, str(e)


def generate_adopt_imports_from_grid(
    grid_rows: list[dict],
    module_name: str = "dbt_cloud",
) -> str:
    """Generate Terraform import blocks from grid rows with action='adopt'.
    
    This converts Match grid rows to import blocks for resources that
    the user has marked for adoption.
    
    Args:
        grid_rows: List of grid row dicts with action, source_type, source_name, target_id
        module_name: The Terraform module name
        
    Returns:
        Content for imports.tf file with import {} blocks
    """
    from importer.web.utils.drift_detector import DriftType
    
    _debug_log({
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "H4",
        "location": "terraform_import.py:536",
        "message": "generate_adopt_imports_from_grid start",
        "data": {
            "module_name": module_name,
            "grid_row_count": len(grid_rows),
        },
        "timestamp": int(time.time() * 1000),
    })
    
    # Build a lookup map of project_name -> target_id from PRJ rows
    # This allows us to find project_id for REP rows even if not passed through
    project_id_by_name: dict[str, str] = {}
    for row in grid_rows:
        if row.get("source_type") == "PRJ":
            pname = row.get("source_name") or row.get("source_key")
            # Target ID for a project IS its dbt Cloud project_id
            pid = row.get("target_id") or row.get("source_id")
            if pname and pid:
                project_id_by_name[pname] = str(pid)
    
    _debug_log({
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "H15",
        "location": "terraform_import.py:570",
        "message": "project_id_by_name lookup built",
        "data": {
            "project_count": len(project_id_by_name),
            "sample": dict(list(project_id_by_name.items())[:5]),
        },
        "timestamp": int(time.time() * 1000),
    })
    
    # Convert grid rows to drift result format
    drift_results = []
    for row in grid_rows:
        if row.get("action") != "adopt":
            continue
        
        target_id = row.get("target_id")
        if not target_id:
            continue
        _debug_log({
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "H5",
            "location": "terraform_import.py:560",
            "message": "adopt row selected",
            "data": {
                "source_key": row.get("source_key"),
                "source_type": row.get("source_type"),
                "source_name": row.get("source_name"),
                "project_name": row.get("project_name"),
                "project_id": row.get("project_id"),
                "target_id": target_id,
                "target_id_type": str(type(target_id)),
            },
            "timestamp": int(time.time() * 1000),
        })
        
        # Get project_id - from row, or lookup by project_name
        element_code = row.get("source_type", "")
        project_name = row.get("project_name", "")
        project_id = row.get("project_id")
        if not project_id and project_name:
            project_id = project_id_by_name.get(project_name)
        
        # Convert to drift result format
        drift_result = {
            "drift_type": DriftType.ID_MISMATCH.value,  # Treat adopt as ID mismatch
            "element_code": element_code,
            "resource_name": row.get("source_name", "").lstrip(" ↳"),  # Remove indent chars
            "state_address": None,  # Will be computed from source_key
            "target_id": int(target_id) if target_id else None,
            "adopt": True,
            "context": {
                "source_key": row.get("source_key", ""),
                "project_name": project_name,
                "project_id": project_id or "",
            },
        }
        drift_results.append(drift_result)

        # For repository adopts in projects_v2, also import project_repository link
        if element_code == "REP":
            # project_name and project_id are already populated above
            _debug_log({
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "H14",
                "location": "terraform_import.py:610",
                "message": "rep link import decision",
                "data": {
                    "project_id": project_id,
                    "project_id_source": "row" if row.get("project_id") else "lookup",
                    "project_name": project_name,
                    "target_id": target_id,
                },
                "timestamp": int(time.time() * 1000),
            })
            if project_id and project_name:
                link_target_id = f"{project_id}:{target_id}"
                drift_results.append({
                    "drift_type": DriftType.MISSING_IN_STATE.value,
                    "element_code": "PREP",
                    "resource_name": project_name,
                    "state_address": None,
                    "target_id": link_target_id,
                    "adopt": True,
                    "context": {
                        "source_key": row.get("source_key", ""),
                        "project_name": project_name,
                        "project_id": project_id,
                    },
                })
    
    if not drift_results:
        return "# No resources selected for adoption\n"
    
    return generate_reconcile_import_blocks(drift_results, module_name)


def generate_state_rm_commands(grid_rows: list[dict]) -> list[str]:
    """Generate terraform state rm commands for resources with ID mismatch.
    
    When a resource has drift_status='id_mismatch', we need to remove the stale
    state entry before we can import the correct one.
    
    Args:
        grid_rows: List of grid row dicts from Match tab
        
    Returns:
        List of terraform state rm command strings
    """
    commands = []
    seen_addresses = set()
    
    # Debug: log all adopt rows with their drift info
    adopt_rows = [r for r in grid_rows if r.get("action") == "adopt"]
    _debug_log({
        "sessionId": "debug-session",
        "runId": "run1",
        "hypothesisId": "H16",
        "location": "terraform_import.py:740",
        "message": "generate_state_rm_commands adopt rows",
        "data": {
            "adopt_count": len(adopt_rows),
            "samples": [
                {
                    "source_name": r.get("source_name"),
                    "source_type": r.get("source_type"),
                    "project_name": r.get("project_name"),
                    "drift_status": r.get("drift_status"),
                    "state_address": r.get("state_address"),
                    "state_id": r.get("state_id"),
                    "target_id": r.get("target_id"),
                }
                for r in adopt_rows[:5]
            ],
        },
        "timestamp": int(time.time() * 1000),
    })
    
    for row in grid_rows:
        if row.get("action") != "adopt":
            continue
        
        # Only generate state rm if there's an ID mismatch AND we have the state address
        drift_status = row.get("drift_status", "")
        state_address = row.get("state_address")
        
        if drift_status == "id_mismatch" and state_address and state_address not in seen_addresses:
            seen_addresses.add(state_address)
            commands.append(f'terraform state rm \'{state_address}\'')
            
            # For repositories, also need to remove the project_repository link
            if row.get("source_type") == "REP":
                # The project_repository address follows a similar pattern
                # e.g., module.dbt_cloud.module.projects_v2[0].dbtcloud_project_repository.project_repositories["project_name"]
                project_name = row.get("project_name", "")
                if project_name and "dbtcloud_repository" in state_address:
                    prep_address = state_address.replace(
                        "dbtcloud_repository.repositories",
                        "dbtcloud_project_repository.project_repositories"
                    )
                    if prep_address not in seen_addresses:
                        seen_addresses.add(prep_address)
                        commands.append(f'terraform state rm \'{prep_address}\'')
    
    return commands


def generate_adoption_script(
    grid_rows: list[dict],
    module_name: str = "dbt_cloud",
    tf_dir: str = ".",
) -> str:
    """Generate a complete adoption script with state rm commands and import blocks.
    
    This generates a bash script that:
    1. Removes stale state entries (terraform state rm)
    2. Creates import blocks file
    3. Runs terraform plan to preview
    
    Args:
        grid_rows: List of grid row dicts from Match tab
        module_name: Terraform module name
        tf_dir: Terraform directory path
        
    Returns:
        Complete bash script content
    """
    state_rm_commands = generate_state_rm_commands(grid_rows)
    import_blocks = generate_adopt_imports_from_grid(grid_rows, module_name)
    
    lines = [
        "#!/bin/bash",
        "# Terraform Adoption Script",
        "# Generated by terraform-dbtcloud-yaml importer",
        "#",
        "# This script will:",
        "#   1. Remove stale state entries (if any)",
        "#   2. Write import blocks to adopt_imports.tf",
        "#   3. Run terraform plan to preview changes",
        "#",
        "# Review each step before proceeding.",
        "",
        f"cd {tf_dir}",
        "",
    ]
    
    if state_rm_commands:
        lines.extend([
            "# Step 1: Remove stale state entries",
            "# These resources have different IDs in state vs target.",
            "# Removing from state does NOT destroy the actual resources.",
            "echo '=== Removing stale state entries ==='",
            "",
        ])
        for cmd in state_rm_commands:
            lines.append(cmd)
        lines.append("")
    else:
        lines.extend([
            "# Step 1: No stale state entries to remove",
            "",
        ])
    
    lines.extend([
        "# Step 2: Write import blocks",
        "echo '=== Writing import blocks to adopt_imports.tf ==='",
        "cat > adopt_imports.tf << 'IMPORT_EOF'",
        import_blocks.rstrip(),
        "IMPORT_EOF",
        "",
        "# Step 3: Preview changes",
        "echo '=== Running terraform plan ==='",
        "terraform plan",
        "",
        "echo '=== Done! Review the plan above. ==='",
        "echo 'If the plan looks correct, run: terraform apply'",
    ])
    
    return "\n".join(lines)


def write_adopt_imports_file(
    grid_rows: list[dict],
    output_dir: Union[str, Path],
    module_name: str = "dbt_cloud",
    filename: str = "adopt_imports.tf",
) -> tuple[Optional[Path], Optional[str]]:
    """Write import blocks for adopted resources from Match grid.
    
    Args:
        grid_rows: List of grid row dicts from Match tab
        output_dir: Directory to write to
        module_name: Terraform module name
        filename: Output filename
        
    Returns:
        Tuple of (file_path, error_message)
    """
    try:
        _debug_log({
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "H6",
            "location": "terraform_import.py:601",
            "message": "write_adopt_imports_file start",
            "data": {
                "module_name": module_name,
                "output_dir": str(output_dir),
                "filename": filename,
                "grid_row_count": len(grid_rows),
            },
            "timestamp": int(time.time() * 1000),
        })
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        content = generate_adopt_imports_from_grid(grid_rows, module_name)
        file_path = output_dir / filename
        
        file_path.write_text(content, encoding="utf-8")
        _debug_log({
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "H7",
            "location": "terraform_import.py:608",
            "message": "write_adopt_imports_file wrote file",
            "data": {
                "file_path": str(file_path),
                "content_length": len(content),
            },
            "timestamp": int(time.time() * 1000),
        })
        return file_path, None
        
    except Exception as e:
        return None, str(e)


def parse_import_errors(output: str) -> dict:
    """Parse Terraform import errors for user-friendly messages.
    
    Args:
        output: Raw Terraform output
        
    Returns:
        Dictionary with error_type and suggestion
    """
    output_lower = output.lower()
    
    if "resource already managed" in output_lower or "already exists in state" in output_lower:
        return {
            "error_type": "already_imported",
            "suggestion": "This resource is already in Terraform state. You can skip it.",
        }
    
    if "not found" in output_lower or "404" in output_lower:
        return {
            "error_type": "not_found",
            "suggestion": "The resource was not found. Check if the Target ID is correct.",
        }
    
    if "unauthorized" in output_lower or "401" in output_lower:
        return {
            "error_type": "auth_error",
            "suggestion": "Authentication failed. Check your target API token permissions.",
        }
    
    if "forbidden" in output_lower or "403" in output_lower:
        return {
            "error_type": "permission_denied",
            "suggestion": "Permission denied. Your token may not have access to this resource.",
        }
    
    return {
        "error_type": "unknown",
        "suggestion": "Check the full error output for details.",
    }
