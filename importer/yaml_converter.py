"""YAML to Terraform deployment setup.

This module creates a Terraform deployment directory that uses the 
terraform-dbtcloud-yaml module to deploy dbt Cloud resources from 
a normalized YAML configuration file.

Follows the same pattern as test/e2e_test/ - generates main.tf that
references the root module, and relies on TF_VAR_* environment 
variables for credentials (not stored in files).
"""

import shutil
import json
import ast
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

# Non-sensitive fields from connection env config should override YAML provider_config.
# Keep sensitive credential material in TF vars only.
NON_SENSITIVE_CONNECTION_OVERRIDE_FIELDS = {
    # BigQuery
    "gcp_project_id",
    "project_id",
    "location",
    "timeout_seconds",
    "priority",
    "auth_provider_x509_cert_url",
    "auth_uri",
    "client_email",
    "client_id",
    "client_x509_cert_url",
    "token_uri",
    "deployment_env_auth_type",
    "use_latest_adapter",
    "maximum_bytes_billed",
    "retries",
    "execution_project",
    "impersonate_service_account",
    "job_creation_timeout_seconds",
    "job_execution_timeout_seconds",
    "job_retry_deadline_seconds",
    "dataproc_region",
    "dataproc_cluster_name",
    "gcs_bucket",
    "scopes",
    # Snowflake / Databricks / Redshift / Postgres common provider config values
    "account",
    "database",
    "warehouse",
    "role",
    "allow_sso",
    "client_session_keep_alive",
    "host",
    "http_path",
    "catalog",
    "hostname",
    "port",
    "dbname",
    "ssh_tunnel_enabled",
    "ssh_tunnel_hostname",
    "ssh_tunnel_port",
    "ssh_tunnel_username",
}

# Fields that should be coerced from string env values.
_CONNECTION_BOOL_FIELDS = {
    "allow_sso",
    "client_session_keep_alive",
    "ssh_tunnel_enabled",
    "use_latest_adapter",
}
_CONNECTION_INT_FIELDS = {
    "port",
    "ssh_tunnel_port",
    "timeout_seconds",
    "maximum_bytes_billed",
    "retries",
    "connect_timeout",
    "connect_retries",
    "login_timeout",
    "query_timeout",
    "request_timeout",
    "job_creation_timeout_seconds",
    "job_execution_timeout_seconds",
    "job_retry_deadline_seconds",
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
        env_path: Optional[str] = None,
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

        # Copy YAML file to output directory and add [DUMMY CREDENTIALS] markers
        # For environments using dummy credentials, we modify the description field
        yaml_dest = output_path / "dbt-cloud-config.yml"
        if yaml_path == yaml_dest:
            # YAML is already in output dir - update in place with dummy markers
            self._update_yaml_with_dummy_markers(yaml_path)
        else:
            # Copy to output dir and add markers
            self._copy_yaml_with_dummy_markers(yaml_path, yaml_dest)

        # Load connection keys from YAML to determine which credentials are needed
        connection_keys = self._extract_connection_keys(yaml_path)
        yaml_data = yaml.safe_load(yaml_path.read_text()) or {}
        account_data = yaml_data.get("account") if isinstance(yaml_data, dict) else {}
        account_host_url = (
            str((account_data or {}).get("host_url") or target_host_url or "").strip()
            if isinstance(account_data, dict)
            else str(target_host_url or "").strip()
        )

        # Load connection credentials from .env if not provided
        if connection_credentials is None:
            connection_credentials = self._load_connection_credentials_from_env(
                connection_keys,
                env_path=env_path,
            )

        # Load environment credentials from .env if not provided
        if environment_credentials is None:
            environment_credentials = self._load_environment_credentials_from_env(
                yaml_path,
                env_path=env_path,
            )

        # Apply non-sensitive connection overrides from env onto YAML provider_config.
        self._apply_connection_provider_overrides_from_env(yaml_dest, env_path=env_path)

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
        self._write_main_tf(
            output_path,
            module_source,
            connection_keys,
            connection_credentials,
            environment_credentials,
            account_host_url=account_host_url,
        )
        
        # Generate secrets.auto.tfvars with credentials (auto-loaded by Terraform)
        if connection_credentials or environment_credentials:
            self._write_secrets_tfvars(output_path, connection_credentials, environment_credentials)

    def _copy_yaml_with_dummy_markers(self, source_path: Path, dest_path: Path) -> None:
        """Copy YAML file and add [DUMMY CREDENTIALS] suffix to environment names.

        For environments that have dummy credentials configured (use_dummy=true in .env),
        this modifies the name field to include a [DUMMY CREDENTIALS] suffix.
        We use name instead of description because environments don't display descriptions.

        Args:
            source_path: Path to source YAML file.
            dest_path: Path to destination YAML file.
        """
        try:
            from importer.web.env_manager import get_dummy_credential_env_ids
            
            # Load dummy env IDs
            dummy_env_ids = get_dummy_credential_env_ids()
            
            if not dummy_env_ids:
                # No dummy credentials, just copy the file
                shutil.copy2(source_path, dest_path)
                return
            
            # Load and modify YAML
            with open(source_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            # Process projects to find environments
            projects = data.get("projects", [])
            for project in projects:
                project_key = project.get("key", "")
                environments = project.get("environments", [])
                
                for env in environments:
                    env_key = env.get("key", "")
                    # The .env file uses just the env_key (e.g., "1_prod"), not project_key_env_key
                    env_id = env_key.lower().replace("-", "_")
                    
                    if env_id in dummy_env_ids:
                        # Add [DUMMY CREDENTIALS] suffix to name
                        current_name = env.get("name", "")
                        if current_name:
                            if not current_name.endswith("[DUMMY CREDENTIALS]"):
                                env["name"] = f"{current_name} [DUMMY CREDENTIALS]"
                        else:
                            env["name"] = "[DUMMY CREDENTIALS]"
            
            # Write modified YAML
            with open(dest_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                
        except Exception:
            # On any error, fall back to simple copy
            shutil.copy2(source_path, dest_path)

    def _update_yaml_with_dummy_markers(self, yaml_path: Path) -> None:
        """Update YAML file in place to add [DUMMY CREDENTIALS] suffix to environment names.

        For environments that have dummy credentials configured (use_dummy=true in .env),
        this modifies the name field to include a [DUMMY CREDENTIALS] suffix.
        We use name instead of description because environments don't display descriptions.

        Args:
            yaml_path: Path to YAML file to update.
        """
        try:
            from importer.web.env_manager import get_dummy_credential_env_ids

            # Load dummy env IDs
            dummy_env_ids = get_dummy_credential_env_ids()

            if not dummy_env_ids:
                # No dummy credentials, nothing to do
                return

            # Load and modify YAML
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            modified = False

            # Process projects to find environments
            projects = data.get("projects", [])
            for project in projects:
                environments = project.get("environments", [])

                for env in environments:
                    env_key = env.get("key", "")
                    # The .env file uses just the env_key (e.g., "1_prod")
                    env_id = env_key.lower().replace("-", "_")

                    if env_id in dummy_env_ids:
                        # Add [DUMMY CREDENTIALS] suffix to name
                        current_name = env.get("name", "")
                        if current_name:
                            if not current_name.endswith("[DUMMY CREDENTIALS]"):
                                env["name"] = f"{current_name} [DUMMY CREDENTIALS]"
                                modified = True
                        else:
                            env["name"] = "[DUMMY CREDENTIALS]"
                            modified = True

            # Only write if we made changes
            if modified:
                with open(yaml_path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        except Exception:
            # On any error, silently skip marker update
            pass

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
        env_path: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Load connection credentials from .env file.

        Args:
            connection_keys: List of connection keys to look for.

        Returns:
            Dict mapping connection keys to their credential values.
        """
        try:
            from importer.web.env_manager import load_connection_configs
            
            all_configs = load_connection_configs(env_path=env_path)
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
        env_path: Optional[str] = None,
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
            from importer.web.env_manager import find_env_file, load_env_credential_configs
            
            # Load all environment credential configs from .env
            env_creds = load_env_credential_configs(env_path=env_path)
            if not env_creds and env_path:
                fallback_env_path = find_env_file()
                if str(fallback_env_path) != str(env_path):
                    env_creds = load_env_credential_configs(env_path=str(fallback_env_path))
            if not env_creds:
                return {}
            
            result = {}
            
            # Load YAML to get project/env structure
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            for project in data.get("projects", []):
                project_key = project.get("key", "")
                for env_index, env in enumerate(project.get("environments", []), start=1):
                    env_key = env.get("key", "")
                    if not env_key:
                        continue
                    
                    # Match the same environment-id variants used by the target credentials UI.
                    lookup_candidates = [
                        env_key.lower(),
                        env_key.replace("-", "_").lower(),
                        env_key.replace("_", "-").lower(),
                        f"{env_index}_{env_key}".replace("-", "_").lower(),
                        f"{env_index}_{env_key}".replace("_", "-").lower(),
                    ]
                    seen_candidates: set[str] = set()

                    matched_creds = None
                    for candidate in lookup_candidates:
                        if not candidate or candidate in seen_candidates:
                            continue
                        seen_candidates.add(candidate)
                        if candidate in env_creds:
                            matched_creds = env_creds[candidate]
                            break

                    if matched_creds:
                        creds = matched_creds.copy()
                        
                        # Remove meta field (use_dummy) - it's not a credential field
                        # Note: we now INCLUDE dummy credentials so Terraform still manages them
                        creds.pop("use_dummy", None)
                        
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
                        
                        # Ensure required fields are present for Snowflake credentials
                        # The Terraform provider requires 'schema' when semantic_layer_credential is false
                        credential_type = filtered_creds.get("credential_type", "")
                        if credential_type == "snowflake" and "schema" not in filtered_creds:
                            # Try to get schema from original creds (might be empty string)
                            if "schema" in creds:
                                filtered_creds["schema"] = creds["schema"] or "dummy_schema"
                            else:
                                filtered_creds["schema"] = "dummy_schema"
                        
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
        account_host_url: Optional[str] = None,
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
        default_host_url = (account_host_url or "https://cloud.getdbt.com").rstrip("/")
        if not default_host_url.endswith("/api"):
            default_host_url = f"{default_host_url}/api"
        
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
  default     = "{default_host_url}"
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
  default = {{}}
  # Note: sensitive = true removed to allow visibility of non-secret fields
  # like schema, user, num_threads in terraform plan output.
  # Actual secrets (password, private_key, tokens) are still protected by
  # Terraform's state encryption and should not be committed to version control.
}}

variable "enable_gitlab_deploy_token" {{
  description = "Allow GitLab repositories to use deploy_token strategy (verified by pre-flight probe)"
  type        = bool
  default     = false
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

  # GitLab deploy_token strategy (set by pre-flight probe)
  enable_gitlab_deploy_token = var.enable_gitlab_deploy_token

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

        def escape_hcl_string(value: str) -> str:
            """Escape a string value for HCL format.
            
            HCL quoted strings cannot contain literal newlines - they must be escaped.
            """
            escaped = str(value)
            escaped = escaped.replace('\\', '\\\\')  # Escape backslashes first
            escaped = escaped.replace('"', '\\"')    # Escape quotes
            escaped = escaped.replace('\n', '\\n')   # Escape newlines
            escaped = escaped.replace('\r', '\\r')   # Escape carriage returns
            escaped = escaped.replace('\t', '\\t')   # Escape tabs
            return escaped

        # Build HCL map for connection_credentials
        if connection_credentials:
            lines.append("connection_credentials = {")
            for conn_key, creds in connection_credentials.items():
                lines.append(f'  "{conn_key}" = {{')
                for field, value in creds.items():
                    escaped_value = escape_hcl_string(value)
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
                        escaped_value = escape_hcl_string(value)
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

    def _apply_connection_provider_overrides_from_env(
        self,
        yaml_file: Path,
        *,
        env_path: Optional[str] = None,
    ) -> None:
        """Apply non-sensitive env overrides to YAML globals.connections provider_config."""
        try:
            from importer.web.env_manager import load_connection_configs

            env_configs = load_connection_configs(env_path=env_path)
            if not env_configs:
                return

            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            globals_block = data.get("globals", {}) if isinstance(data, dict) else {}
            connections = globals_block.get("connections", []) if isinstance(globals_block, dict) else []
            if not isinstance(connections, list):
                return

            overrides_applied: Dict[str, Dict[str, Any]] = {}

            for conn in connections:
                if not isinstance(conn, dict):
                    continue
                key = conn.get("key")
                if not key:
                    continue
                normalized_key = str(key).lower().replace("-", "_")
                env_cfg = env_configs.get(normalized_key)
                if not env_cfg:
                    continue

                provider_config = conn.get("provider_config")
                if not isinstance(provider_config, dict):
                    provider_config = {}
                    conn["provider_config"] = provider_config

                applied_fields: Dict[str, Any] = {}
                for field, value in env_cfg.items():
                    if field not in NON_SENSITIVE_CONNECTION_OVERRIDE_FIELDS:
                        continue
                    if value is None or value == "":
                        continue
                    normalized_value = self._normalize_connection_override_value(field, value)
                    provider_config[field] = normalized_value
                    applied_fields[field] = normalized_value

                if applied_fields:
                    overrides_applied[str(key)] = applied_fields

            if overrides_applied:
                with open(yaml_file, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        except Exception:
            return

    def _normalize_connection_override_value(self, field: str, value: Any) -> Any:
        """Normalize env-string overrides to Terraform-compatible types/values."""
        if isinstance(value, str):
            raw = value.strip()
        else:
            raw = value

        # Normalize BigQuery priority to provider-accepted lowercase enum.
        if field == "priority" and isinstance(raw, str):
            lowered = raw.lower()
            if lowered in {"interactive", "batch"}:
                return lowered
            return raw

        # Normalize BigQuery scopes from persisted string/list into list[str].
        if field == "scopes":
            if isinstance(raw, list):
                return [str(v) for v in raw if str(v).strip()]
            if isinstance(raw, str):
                if not raw:
                    return []
                parsed: Any = None
                # Try JSON first, then Python literal list format.
                try:
                    parsed = json.loads(raw)
                except Exception:
                    try:
                        parsed = ast.literal_eval(raw)
                    except Exception:
                        parsed = None
                if isinstance(parsed, list):
                    return [str(v) for v in parsed if str(v).strip()]
                # Fallback: comma-separated string.
                if "," in raw:
                    return [part.strip() for part in raw.split(",") if part.strip()]
                return [raw]

        # Normalize bool-like strings.
        if field in _CONNECTION_BOOL_FIELDS and isinstance(raw, str):
            lowered = raw.lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False

        # Normalize int-like strings.
        if field in _CONNECTION_INT_FIELDS and isinstance(raw, str):
            try:
                return int(raw)
            except Exception:
                return value

        return value
