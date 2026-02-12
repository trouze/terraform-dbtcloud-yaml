"""Terraform state reader utility.

Reads and parses Terraform state via `terraform show -json` command.
Maps dbt Cloud Terraform resource types to internal element codes.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union


logger = logging.getLogger(__name__)


# Map Terraform resource types to internal element codes
TF_TYPE_TO_CODE = {
    "dbtcloud_project": "PRJ",
    "dbtcloud_repository": "REP",
    "dbtcloud_environment": "ENV",
    "dbtcloud_job": "JOB",
    "dbtcloud_global_connection": "CON",
    "dbtcloud_global_connections": "CON",  # Plural form
    "dbtcloud_service_token": "TOK",
    "dbtcloud_group": "GRP",
    "dbtcloud_notification": "NOT",
    "dbtcloud_webhook": "WEB",
    "dbtcloud_environment_variable": "VAR",
    "dbtcloud_environment_variable_job_override": "JEVO",
    "dbtcloud_privatelink_endpoint": "PLE",
    "dbtcloud_privatelink_endpoints": "PLE",  # Plural form
    "dbtcloud_project_repository": "PREP",
    "dbtcloud_job_completion_trigger": "JCTG",
    "dbtcloud_extended_attributes": "EXTATTR",
    # Credential types - all map to CRD
    "dbtcloud_athena_credential": "CRD",
    "dbtcloud_bigquery_credential": "CRD",
    "dbtcloud_databricks_credential": "CRD",
    "dbtcloud_fabric_credential": "CRD",
    "dbtcloud_postgres_credential": "CRD",
    "dbtcloud_redshift_credential": "CRD",
    "dbtcloud_snowflake_credential": "CRD",
    "dbtcloud_spark_credential": "CRD",
    "dbtcloud_starburst_credential": "CRD",
    "dbtcloud_synapse_credential": "CRD",
    "dbtcloud_teradata_credential": "CRD",
    # Semantic layer credentials
    "dbtcloud_bigquery_semantic_layer_credential": "CRD",
    "dbtcloud_databricks_semantic_layer_credential": "CRD",
    "dbtcloud_postgres_semantic_layer_credential": "CRD",
    "dbtcloud_redshift_semantic_layer_credential": "CRD",
    "dbtcloud_snowflake_semantic_layer_credential": "CRD",
}

# Reverse mapping for generating import blocks
CODE_TO_TF_TYPE = {v: k for k, v in TF_TYPE_TO_CODE.items()}

# Map Terraform resource types to global YAML section keys.
# Used by get_tf_state_global_sections() to detect which global sections
# have resources in TF state (for auto-retain safety net).
TF_TYPE_TO_GLOBAL_SECTION: dict[str, str] = {
    "dbtcloud_group": "groups",
    "dbtcloud_service_token": "service_tokens",
    "dbtcloud_notification": "notifications",
    "dbtcloud_webhook": "webhooks",
    "dbtcloud_privatelink_endpoint": "privatelink_endpoints",
    "dbtcloud_privatelink_endpoints": "privatelink_endpoints",
    "dbtcloud_global_connection": "connections",
    "dbtcloud_global_connections": "connections",
    "dbtcloud_repository": "repositories",
}


@dataclass
class StateResource:
    """A resource parsed from Terraform state."""
    
    # Terraform resource address (e.g., "module.dbt_cloud.dbtcloud_project.my_project")
    address: str
    # Terraform resource type (e.g., "dbtcloud_project")
    tf_type: str
    # Internal element code (e.g., "PRJ")
    element_code: str
    # Resource name in Terraform (e.g., "my_project")
    tf_name: str
    # dbt Cloud resource ID
    dbt_id: Optional[int] = None
    # Resource name in dbt Cloud
    name: Optional[str] = None
    # Project ID (for project-scoped resources)
    project_id: Optional[int] = None
    # Full attributes from state
    attributes: dict = field(default_factory=dict)
    # For for_each resources, the key (e.g., "sse_dm_fin_fido")
    resource_index: Optional[str] = None


@dataclass
class StateReadResult:
    """Result of reading Terraform state."""
    
    success: bool
    error_message: Optional[str] = None
    terraform_version: Optional[str] = None
    # Resources indexed by (element_code, dbt_id)
    resources_by_id: dict[tuple[str, int], StateResource] = field(default_factory=dict)
    # Resources indexed by address
    resources_by_address: dict[str, StateResource] = field(default_factory=dict)
    # All resources as a list
    resources: list[StateResource] = field(default_factory=list)


async def read_terraform_state(
    tf_dir: Union[str, Path],
    timeout_seconds: int = 60,
) -> StateReadResult:
    """Read Terraform state by running `terraform show -json`.
    
    This works with any backend (local, S3, Terraform Cloud, etc.)
    because it uses the Terraform CLI to read state.
    
    Args:
        tf_dir: Directory containing Terraform configuration
        timeout_seconds: Timeout for the terraform command
        
    Returns:
        StateReadResult with parsed resources or error
    """
    tf_dir = Path(tf_dir)
    
    if not tf_dir.exists():
        return StateReadResult(
            success=False,
            error_message=f"Directory does not exist: {tf_dir}",
        )
    
    # Temporarily move import .tf files out of the way if present.
    # These files contain `import {}` blocks that are only needed during
    # `terraform apply` but cause `terraform show` to fail when they
    # reference duplicate or already-imported addresses.
    _moved_import_files: list[tuple[Path, Path]] = []
    for import_filename in ("adopt_imports.tf", "reconcile_imports.tf"):
        import_file = tf_dir / import_filename
        import_backup = tf_dir / f"{import_filename}.bak"
        if import_file.exists():
            try:
                import_file.rename(import_backup)
                _moved_import_files.append((import_file, import_backup))
                logger.info(f"Temporarily moved {import_filename} aside for terraform show")
            except OSError as e:
                logger.warning(f"Could not move {import_filename} aside: {e}")
    
    try:
        logger.info(f"Reading Terraform state from {tf_dir}")
        
        process = await asyncio.create_subprocess_exec(
            "terraform", "show", "-json",
            cwd=str(tf_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            return StateReadResult(
                success=False,
                error_message=f"Terraform command timed out after {timeout_seconds}s",
            )
        
        if process.returncode != 0:
            error_text = stderr.decode().strip()
            # Check for common errors
            if "No state file" in error_text or "state is empty" in error_text.lower():
                return StateReadResult(
                    success=True,
                    error_message=None,
                    # Empty state - no resources
                )
            return StateReadResult(
                success=False,
                error_message=f"Terraform show failed: {error_text}",
            )
        
        # Parse JSON output
        try:
            state_json = json.loads(stdout.decode())
        except json.JSONDecodeError as e:
            return StateReadResult(
                success=False,
                error_message=f"Failed to parse Terraform state JSON: {e}",
            )
        
        # Parse resources from state
        return parse_state_json(state_json)
        
    except FileNotFoundError:
        return StateReadResult(
            success=False,
            error_message="Terraform CLI not found. Please install Terraform.",
        )
    except Exception as e:
        logger.exception("Error reading Terraform state")
        return StateReadResult(
            success=False,
            error_message=f"Error reading state: {e}",
        )
    finally:
        # Restore any import files we moved aside
        for orig_path, backup_path in _moved_import_files:
            if backup_path.exists():
                try:
                    backup_path.rename(orig_path)
                    logger.info(f"Restored {orig_path.name} after terraform show")
                except OSError as e:
                    logger.warning(f"Could not restore {orig_path.name}: {e}")


def parse_state_json(state_json: dict) -> StateReadResult:
    """Parse Terraform state JSON into StateResource objects.
    
    Args:
        state_json: Output from `terraform show -json`
        
    Returns:
        StateReadResult with parsed resources
    """
    result = StateReadResult(success=True)
    
    # Get Terraform version
    result.terraform_version = state_json.get("terraform_version")
    
    # Get values (contains the actual state data)
    values = state_json.get("values", {})
    if not values:
        # Empty state
        return result
    
    # Parse root module resources
    root_module = values.get("root_module", {})
    _parse_module_resources(root_module, "", result)
    
    # Parse child modules (like module.dbt_cloud)
    child_modules = root_module.get("child_modules", [])
    for child in child_modules:
        module_address = child.get("address", "")
        _parse_module_resources(child, module_address, result)
        
        # Handle nested child modules
        nested_children = child.get("child_modules", [])
        for nested in nested_children:
            nested_address = nested.get("address", "")
            _parse_module_resources(nested, nested_address, result)
    
    logger.info(f"Parsed {len(result.resources)} resources from Terraform state")
    return result


def _parse_module_resources(
    module: dict,
    module_address: str,
    result: StateReadResult,
) -> None:
    """Parse resources from a module in the state.
    
    Args:
        module: Module object from state JSON
        module_address: Address prefix (e.g., "module.dbt_cloud")
        result: StateReadResult to populate
    """
    resources = module.get("resources", [])
    
    for resource in resources:
        tf_type = resource.get("type", "")
        
        # Only process dbt Cloud resources
        if not tf_type.startswith("dbtcloud_"):
            continue
        
        element_code = TF_TYPE_TO_CODE.get(tf_type)
        if not element_code:
            logger.warning(f"Unknown dbt Cloud resource type: {tf_type}")
            continue
        
        tf_name = resource.get("name", "")
        resource_index = resource.get("index")  # Key for for_each resources
        
        # Use the actual address from the JSON if available (includes for_each keys)
        # Otherwise fall back to constructing it
        address = resource.get("address")
        if not address:
            if module_address:
                address = f"{module_address}.{tf_type}.{tf_name}"
            else:
                address = f"{tf_type}.{tf_name}"
            # Append the index for for_each resources
            if resource_index is not None:
                address = f'{address}["{resource_index}"]'
        
        # FALLBACK: Extract resource_index from address if not provided directly
        # Address format: module.x.resource_type.name["key"] or resource_type.name["key"]
        # This handles cases where terraform show -json doesn't include the index field separately
        if resource_index is None and address and "[" in address:
            # Match the key inside brackets, handling both ["key"] and [0] formats
            match = re.search(r'\["([^"]+)"\]$', address)
            if match:
                resource_index = match.group(1)
            else:
                # Try numeric index
                match = re.search(r'\[(\d+)\]$', address)
                if match:
                    resource_index = match.group(1)
        
        # Get attributes from values
        values = resource.get("values", {})
        
        # Extract common fields
        dbt_id = values.get("id")
        if dbt_id is not None:
            # ID might be string or int, normalize to int
            try:
                dbt_id = int(dbt_id)
            except (ValueError, TypeError):
                # Some resources have composite IDs like "project_id:repo_id"
                # Try to extract just the resource ID
                if isinstance(dbt_id, str) and ":" in dbt_id:
                    parts = dbt_id.split(":")
                    try:
                        dbt_id = int(parts[-1])
                    except ValueError:
                        dbt_id = None
                else:
                    dbt_id = None
        
        name = values.get("name")
        project_id = values.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (ValueError, TypeError):
                project_id = None
        
        state_resource = StateResource(
            address=address,
            tf_type=tf_type,
            element_code=element_code,
            tf_name=tf_name,
            dbt_id=dbt_id,
            name=name,
            project_id=project_id,
            attributes=values,
            resource_index=str(resource_index) if resource_index is not None else None,
        )
        
        result.resources.append(state_resource)
        result.resources_by_address[address] = state_resource
        
        if dbt_id is not None:
            result.resources_by_id[(element_code, dbt_id)] = state_resource


def get_resource_id_from_state(
    state_result: StateReadResult,
    element_code: str,
    resource_name: str,
) -> Optional[int]:
    """Get the dbt Cloud ID for a resource from state by name.
    
    Args:
        state_result: Parsed state
        element_code: Element type code (e.g., "PRJ")
        resource_name: Name of the resource in dbt Cloud
        
    Returns:
        dbt Cloud ID if found, None otherwise
    """
    for resource in state_result.resources:
        if resource.element_code == element_code and resource.name == resource_name:
            return resource.dbt_id
    return None


def get_state_resource_by_target_id(
    state_result: StateReadResult,
    element_code: str,
    target_id: int,
) -> Optional[StateResource]:
    """Find a state resource that references a specific target ID.
    
    Args:
        state_result: Parsed state
        element_code: Element type code
        target_id: The dbt Cloud ID to find
        
    Returns:
        StateResource if found, None otherwise
    """
    return state_result.resources_by_id.get((element_code, target_id))
