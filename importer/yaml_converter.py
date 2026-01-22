"""YAML to Terraform deployment setup.

This module creates a Terraform deployment directory that uses the 
terraform-dbtcloud-yaml module to deploy dbt Cloud resources from 
a normalized YAML configuration file.

Follows the same pattern as test/e2e_test/ - generates main.tf that
references the root module, and relies on TF_VAR_* environment 
variables for credentials (not stored in files).
"""

import shutil
from pathlib import Path
from typing import Dict, Optional, Any

import yaml


# Sensitive credential fields that should be included in connection_credentials
# These are the fields that need to be passed via TF_VAR for security
SENSITIVE_CONNECTION_FIELDS = {
    # Snowflake OAuth
    "oauth_client_id",
    "oauth_client_secret",
    # Databricks OAuth
    "client_id",
    "client_secret",
    # BigQuery Service Account
    "private_key_id",
    "private_key",
    # BigQuery External OAuth (WIF)
    "application_id",
    "application_secret",
}

# Environment credential fields by credential type
# These are the fields that can be passed via environment_credentials
ENVIRONMENT_CREDENTIAL_FIELDS = {
    "credential_type",
    "schema",
    "num_threads",
    # Snowflake
    "auth_type",
    "user",
    "password",
    "private_key",
    "private_key_passphrase",
    "warehouse",
    "role",
    "database",
    # BigQuery
    "dataset",
    # Postgres/Redshift
    "default_schema",
    "username",
    "target_name",
    # Athena
    "aws_access_key_id",
    "aws_secret_access_key",
    # Fabric/Synapse
    "tenant_id",
    "client_id",
    "client_secret",
    "schema_authorization",
    "authentication",
    # Databricks
    "token",
    "catalog",
}


class YamlToTerraformConverter:
    """Sets up a Terraform deployment directory for deploying dbt Cloud resources."""

    def __init__(
        self,
        module_source: Optional[str] = None,
        provider_version: str = "= 1.5.1",
    ):
        """Initialize the converter.

        Args:
            module_source: Source path for the terraform-dbtcloud-yaml module.
                          If None, calculates relative path from output directory.
            provider_version: dbtcloud provider version constraint.
        """
        self.module_source = module_source
        self.provider_version = provider_version
        # Get the repo root (parent of importer directory)
        self._repo_root = Path(__file__).parent.parent.resolve()

    def convert(
        self,
        yaml_file: str,
        output_dir: str,
        target_host_url: Optional[str] = None,
        target_account_id: Optional[int] = None,
        target_token: Optional[str] = None,
        connection_credentials: Optional[Dict[str, Dict[str, Any]]] = None,
        environment_credentials: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """Create a Terraform deployment directory.

        Args:
            yaml_file: Path to the normalized YAML configuration file.
            output_dir: Directory to create the Terraform files in.
            target_host_url: Target dbt Cloud host URL (for reference only, uses env vars).
            target_account_id: Target dbt Cloud account ID (for reference only, uses env vars).
            target_token: Target dbt Cloud API token (not stored - uses env vars).
            connection_credentials: Optional dict of connection keys to credential values.
                                   If None, reads from .env file.
            environment_credentials: Optional dict of environment keys to credential values.
                                    If None, reads from .env file.
        """
        yaml_path = Path(yaml_file).resolve()
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)

        # Copy YAML file to output directory (skip if already there)
        yaml_dest = output_path / "dbt-cloud-config.yml"
        if yaml_path != yaml_dest:
            shutil.copy2(yaml_path, yaml_dest)

        # Load connection keys from YAML to determine which credentials are needed
        connection_keys = self._extract_connection_keys(yaml_path)

        # Load connection credentials from .env if not provided
        if connection_credentials is None:
            connection_credentials = self._load_connection_credentials_from_env(connection_keys)

        # Load environment credentials from .env if not provided
        if environment_credentials is None:
            environment_credentials = self._load_environment_credentials_from_env(yaml_path)

        # Calculate relative path from output dir to repo root
        # This follows the same pattern as test/e2e_test which uses "../.."
        if self.module_source:
            module_source = self.module_source
        else:
            try:
                # Calculate relative path
                module_source = str(Path("..") / output_path.relative_to(self._repo_root).parent)
                # Simplify: if output is terraform_output, relative is ".."
                # Count how many levels deep we are from repo root
                rel_parts = output_path.relative_to(self._repo_root).parts
                module_source = "/".join([".."] * len(rel_parts))
            except ValueError:
                # Output dir is outside repo, use absolute path
                module_source = str(self._repo_root)

        # Generate main.tf (following test/e2e_test/main.tf pattern)
        self._write_main_tf(output_path, module_source, connection_keys, connection_credentials, environment_credentials)
        
        # Generate secrets.auto.tfvars with credentials (auto-loaded by Terraform)
        if connection_credentials or environment_credentials:
            self._write_secrets_tfvars(output_path, connection_credentials, environment_credentials)

    def _extract_connection_keys(self, yaml_path: Path) -> list:
        """Extract connection keys from the YAML file.

        Args:
            yaml_path: Path to the YAML configuration file.

        Returns:
            List of connection key strings.
        """
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            connections = data.get("globals", {}).get("connections", [])
            return [conn.get("key") for conn in connections if conn.get("key")]
        except Exception:
            return []

    def _load_connection_credentials_from_env(
        self,
        connection_keys: list,
    ) -> Dict[str, Dict[str, Any]]:
        """Load connection credentials from .env file.

        Args:
            connection_keys: List of connection keys to look for.

        Returns:
            Dict mapping connection keys to their credential values.
        """
        try:
            from importer.web.env_manager import load_connection_configs
            
            all_configs = load_connection_configs()
            result = {}
            
            for key in connection_keys:
                # Normalize key for lookup (env_manager normalizes to lowercase)
                normalized_key = key.lower().replace("-", "_")
                if normalized_key in all_configs:
                    config = all_configs[normalized_key]
                    # Filter to only include sensitive fields
                    sensitive_config = {
                        field: value
                        for field, value in config.items()
                        if field in SENSITIVE_CONNECTION_FIELDS and value
                    }
                    if sensitive_config:
                        result[key] = sensitive_config
            
            return result
        except ImportError:
            return {}
        except Exception:
            return {}

    def _load_environment_credentials_from_env(
        self,
        yaml_path: Path,
    ) -> Dict[str, Dict[str, Any]]:
        """Load environment credentials from .env file.
        
        Reads DBT_ENV_CRED_* variables from .env and maps them to
        project_key_env_key format for Terraform.

        Args:
            yaml_path: Path to the YAML configuration file for project/env context.

        Returns:
            Dict mapping "project_key_env_key" to their credential values.
        """
        try:
            from importer.web.env_manager import load_env_credential_configs
            
            # Load all environment credential configs from .env
            env_creds = load_env_credential_configs()
            if not env_creds:
                return {}
            
            result = {}
            
            # Load YAML to get project/env structure
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            for project in data.get("projects", []):
                project_key = project.get("key", "")
                for env in project.get("environments", []):
                    env_key = env.get("key", "")
                    if not env_key:
                        continue
                    
                    # Normalize key for lookup (env_manager normalizes to lowercase with underscores)
                    normalized_key = env_key.lower().replace("-", "_")
                    
                    if normalized_key in env_creds:
                        creds = env_creds[normalized_key].copy()
                        
                        # Skip dummy credentials
                        use_dummy = creds.pop("use_dummy", "false")
                        if use_dummy.lower() == "true":
                            continue
                        
                        # Filter to only include valid credential fields and non-empty values
                        filtered_creds = {
                            field: value
                            for field, value in creds.items()
                            if field in ENVIRONMENT_CREDENTIAL_FIELDS and value
                        }
                        
                        # Filter mutually exclusive fields based on auth_type (for Snowflake)
                        # When auth_type is 'keypair', password should not be set
                        # When auth_type is 'password', private_key/private_key_passphrase should not be set
                        auth_type = filtered_creds.get("auth_type", "")
                        if auth_type == "keypair":
                            filtered_creds.pop("password", None)
                        elif auth_type == "password":
                            filtered_creds.pop("private_key", None)
                            filtered_creds.pop("private_key_passphrase", None)
                        
                        if filtered_creds:
                            # Use project_key_env_key format for Terraform
                            tf_key = f"{project_key}_{env_key}"
                            result[tf_key] = filtered_creds
            
            return result
        except ImportError:
            return {}
        except Exception:
            return {}

    def _write_main_tf(
        self,
        output_path: Path,
        module_source: str,
        connection_keys: list,
        connection_credentials: Dict[str, Dict[str, Any]],
        environment_credentials: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """Write the main.tf file following the e2e test pattern.

        Args:
            output_path: Directory to write the file to.
            module_source: Terraform module source path.
            connection_keys: List of connection keys from YAML.
            connection_credentials: Dict of connection credentials.
            environment_credentials: Dict of environment credentials.
        """
        environment_credentials = environment_credentials or {}
        
        # Build connection_credentials block for module call
        credentials_block = self._build_connection_credentials_block(connection_credentials)
        
        # Build variable definitions for connection credentials
        credential_vars = self._build_credential_variable_definitions(connection_keys, connection_credentials)

        content = f'''# Deployment Configuration
# Generated by dbt Magellan
#
# Credentials are provided via environment variables:
#   TF_VAR_dbt_account_id - Target account ID
#   TF_VAR_dbt_token      - API token (service token or PAT)
#   TF_VAR_dbt_host_url   - Host URL (e.g., https://cloud.getdbt.com)
#   TF_VAR_dbt_pat        - Optional: PAT for GitHub App integration
#   TF_VAR_connection_credentials - Optional: Connection OAuth/SSO credentials
#   TF_VAR_environment_credentials - Optional: Environment-specific credentials

terraform {{
  required_version = ">= 1.5"
  required_providers {{
    dbtcloud = {{
      source  = "dbt-labs/dbtcloud"
      version = "{self.provider_version}"
    }}
  }}
}}

provider "dbtcloud" {{
  account_id = var.dbt_account_id
  token      = var.dbt_token
  host_url   = var.dbt_host_url
}}

variable "dbt_account_id" {{
  description = "dbt Cloud account ID"
  type        = number
}}

variable "dbt_token" {{
  description = "dbt Cloud API token"
  type        = string
  sensitive   = true
}}

variable "dbt_host_url" {{
  description = "dbt Cloud API URL (including /api suffix)"
  type        = string
  default     = "https://cloud.getdbt.com/api"
}}

variable "dbt_pat" {{
  description = "dbt Cloud Personal Access Token (dbtu_*) for GitHub App integration"
  type        = string
  sensitive   = true
  default     = null
}}

variable "connection_credentials" {{
  description = "Map of connection keys to their sensitive credential values (OAuth secrets, etc.)"
  type = map(object({{
    oauth_client_id     = optional(string)
    oauth_client_secret = optional(string)
    client_id           = optional(string)
    client_secret       = optional(string)
    private_key_id      = optional(string)
    private_key         = optional(string)
    application_id      = optional(string)
    application_secret  = optional(string)
  }}))
  default   = {{}}
  sensitive = true
}}

variable "environment_credentials" {{
  description = "Map of environment keys (project_key_env_key) to credential values"
  type = map(object({{
    credential_type        = string
    schema                 = optional(string)
    num_threads            = optional(number)
    auth_type              = optional(string)
    user                   = optional(string)
    password               = optional(string)
    private_key            = optional(string)
    private_key_passphrase = optional(string)
    warehouse              = optional(string)
    role                   = optional(string)
    database               = optional(string)
    dataset                = optional(string)
    default_schema         = optional(string)
    username               = optional(string)
    target_name            = optional(string)
    aws_access_key_id      = optional(string)
    aws_secret_access_key  = optional(string)
    tenant_id              = optional(string)
    client_id              = optional(string)
    client_secret          = optional(string)
    schema_authorization   = optional(string)
    authentication         = optional(string)
    token                  = optional(string)
    catalog                = optional(string)
  }}))
  default   = {{}}
  sensitive = true
}}
{credential_vars}
module "dbt_cloud" {{
  source = "{module_source}"

  # Pass credentials to the module
  dbt_account_id = var.dbt_account_id
  dbt_token      = var.dbt_token
  dbt_host_url   = var.dbt_host_url
  dbt_pat        = var.dbt_pat

  yaml_file   = "${{path.module}}/dbt-cloud-config.yml"
  target_name = "deployment"

  # Credential token mapping (add secrets here if needed)
  token_map = {{
    # Example: "databricks_token" = var.databricks_token
  }}

  # Connection credentials (OAuth/SSO secrets)
{credentials_block}

  # Environment credentials (per-environment database credentials)
  environment_credentials = var.environment_credentials
}}

# Outputs for verification
output "project_ids" {{
  description = "Map of project keys to IDs"
  value       = module.dbt_cloud.v2_project_ids
}}

output "environment_ids" {{
  description = "Map of environment keys to IDs"
  value       = module.dbt_cloud.v2_environment_ids
}}

output "job_ids" {{
  description = "Map of job keys to IDs"
  value       = module.dbt_cloud.v2_job_ids
}}

output "connection_ids" {{
  description = "Map of connection keys to IDs"
  value       = module.dbt_cloud.v2_connection_ids
}}

output "repository_ids" {{
  description = "Map of repository keys to IDs"
  value       = module.dbt_cloud.v2_repository_ids
}}
'''
        (output_path / "main.tf").write_text(content)

    def _build_connection_credentials_block(
        self,
        connection_credentials: Dict[str, Dict[str, Any]],
    ) -> str:
        """Build the connection_credentials block for the module call.

        Args:
            connection_credentials: Dict of connection credentials.

        Returns:
            Terraform HCL string for the connection_credentials block.
        """
        if not connection_credentials:
            return "  connection_credentials = var.connection_credentials"
        
        # Build a merged block that combines var.connection_credentials with any
        # statically known credentials (though we prefer using the variable)
        return "  connection_credentials = var.connection_credentials"

    def _build_credential_variable_definitions(
        self,
        connection_keys: list,
        connection_credentials: Dict[str, Dict[str, Any]],
    ) -> str:
        """Build variable definitions for connection credentials.

        This generates helpful comments showing which connections have credentials
        and how to set them via environment variables.

        Args:
            connection_keys: List of connection keys from YAML.
            connection_credentials: Dict of connection credentials.

        Returns:
            Terraform HCL string with variable definitions and comments.
        """
        if not connection_keys:
            return ""
        
        lines = [
            "",
            "# Connection credential hints (set via TF_VAR_connection_credentials):",
            "# Example JSON format for TF_VAR_connection_credentials:",
            "# {",
        ]
        
        for key in connection_keys:
            creds = connection_credentials.get(key, {})
            if creds:
                cred_fields = ", ".join(f'"{k}": "..."' for k in creds.keys())
                lines.append(f'#   "{key}": {{ {cred_fields} }},')
            else:
                lines.append(f'#   "{key}": {{ }},  # No sensitive credentials detected')
        
        lines.append("# }")
        lines.append("")
        
        return "\n".join(lines)

    def _write_secrets_tfvars(
        self,
        output_path: Path,
        connection_credentials: Dict[str, Dict[str, Any]],
        environment_credentials: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """Write a secrets.auto.tfvars file with connection and environment credentials.

        This file is auto-loaded by Terraform and should be gitignored.
        The .auto.tfvars extension ensures automatic loading.

        Args:
            output_path: Directory to write the file to.
            connection_credentials: Dict of connection credentials.
            environment_credentials: Dict of environment credentials.
        """
        environment_credentials = environment_credentials or {}
        
        if not connection_credentials and not environment_credentials:
            return

        lines = [
            "# Auto-generated credentials",
            "# WARNING: This file contains sensitive values - add to .gitignore!",
            "",
        ]

        # Build HCL map for connection_credentials
        if connection_credentials:
            lines.append("connection_credentials = {")
            for conn_key, creds in connection_credentials.items():
                lines.append(f'  "{conn_key}" = {{')
                for field, value in creds.items():
                    # Escape quotes in values
                    escaped_value = str(value).replace('\\', '\\\\').replace('"', '\\"')
                    lines.append(f'    {field} = "{escaped_value}"')
                lines.append("  }")
            lines.append("}")
            lines.append("")

        # Build HCL map for environment_credentials
        if environment_credentials:
            lines.append("environment_credentials = {")
            for env_key, creds in environment_credentials.items():
                lines.append(f'  "{env_key}" = {{')
                for field, value in creds.items():
                    # Handle different value types
                    if isinstance(value, bool):
                        lines.append(f'    {field} = {str(value).lower()}')
                    elif isinstance(value, (int, float)):
                        lines.append(f'    {field} = {value}')
                    else:
                        # Escape quotes in string values
                        escaped_value = str(value).replace('\\', '\\\\').replace('"', '\\"')
                        lines.append(f'    {field} = "{escaped_value}"')
                lines.append("  }")
            lines.append("}")
            lines.append("")

        secrets_file = output_path / "secrets.auto.tfvars"
        secrets_file.write_text("\n".join(lines))
        
        # Also ensure .gitignore exists with secrets.auto.tfvars
        gitignore_path = output_path / ".gitignore"
        gitignore_content = "# Sensitive credential files\nsecrets.auto.tfvars\n*.tfvars\n!example.tfvars\n"
        if not gitignore_path.exists():
            gitignore_path.write_text(gitignore_content)
        else:
            existing = gitignore_path.read_text()
            if "secrets.auto.tfvars" not in existing:
                gitignore_path.write_text(existing + "\n" + gitignore_content)
