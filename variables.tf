#############################################
# dbt Cloud Configuration
#############################################

variable "dbt_account_id" {
  description = "dbt Cloud account ID (required when used as root module, optional when used as module)"
  type        = number
  default     = null

  validation {
    condition     = var.dbt_account_id == null || var.dbt_account_id > 0
    error_message = "dbt_account_id must be a positive integer"
  }
}

variable "dbt_token" {
  description = "dbt Cloud API token for authentication (required when used as root module, optional when used as module)"
  type        = string
  sensitive   = true
  default     = null

  validation {
    condition     = var.dbt_token == null || length(var.dbt_token) > 0
    error_message = "dbt_token cannot be empty"
  }
}

variable "dbt_pat" {
  description = "dbt Cloud Personal Access Token (dbtu_*) for retrieving integration IDs. Required for GitHub App integration discovery. Service tokens cannot access the integrations API."
  type        = string
  sensitive   = true
  default     = null
}

variable "dbt_host_url" {
  description = "dbt Cloud host URL (e.g., https://cloud.getdbt.com or custom domain) (required when used as root module, optional when used as module)"
  type        = string
  default     = "https://cloud.getdbt.com"

  validation {
    condition     = var.dbt_host_url == null || can(regex("^https://", var.dbt_host_url))
    error_message = "dbt_host_url must start with https://"
  }
}

variable "projects_v2_skip_global_project_permissions" {
  description = "When true, omits project-scoped permissions on global groups/service tokens in projects_v2. Intended for scoped global-object adoption plans."
  type        = bool
  default     = false
}

#############################################
# YAML Configuration
#############################################

variable "yaml_file" {
  description = "Path to the YAML file defining dbt Cloud resources (projects, environments, jobs, etc.)"
  type        = string
  # Note: Validation removed to allow module to be loaded without file existing
  # The file will be validated when the module is actually used
}

variable "target_name" {
  description = "Default target name for the dbt project (e.g., 'dev', 'prod')"
  type        = string
  default     = ""
}

#############################################
# Credentials
#############################################

variable "token_map" {
  description = "Map of credential token names to their actual values (e.g., Databricks tokens). Token names should correspond to credential.token_name in YAML."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "connection_credentials" {
  description = "Map of connection keys to their sensitive credential values (OAuth secrets, private keys, etc.). Keys should match connection.key in YAML."
  type = map(object({
    # Snowflake OAuth
    oauth_client_id     = optional(string)
    oauth_client_secret = optional(string)
    # Databricks OAuth
    client_id     = optional(string)
    client_secret = optional(string)
    # BigQuery Service Account
    private_key_id = optional(string)
    private_key    = optional(string)
    # BigQuery External OAuth (WIF)
    application_id     = optional(string)
    application_secret = optional(string)
  }))
  default   = {}
  sensitive = true
}

variable "environment_credentials" {
  description = "Map of environment keys (project_key_env_key) to credential values for each environment."
  type = map(object({
    # Credential type (required to route to correct resource)
    credential_type = string # snowflake, databricks, bigquery, postgres, redshift, athena, fabric, synapse, starburst, spark, teradata

    # Common fields
    schema      = optional(string)
    num_threads = optional(number)

    # Snowflake
    auth_type              = optional(string) # "password" or "keypair"
    user                   = optional(string)
    password               = optional(string)
    private_key            = optional(string)
    private_key_passphrase = optional(string)
    warehouse              = optional(string)
    role                   = optional(string)
    database               = optional(string)

    # Databricks
    token   = optional(string)
    catalog = optional(string)

    # BigQuery
    dataset = optional(string)

    # Postgres/Redshift
    default_schema = optional(string)
    username       = optional(string)
    target_name    = optional(string)

    # Athena
    aws_access_key_id     = optional(string)
    aws_secret_access_key = optional(string)

    # Fabric/Synapse
    tenant_id            = optional(string)
    client_id            = optional(string)
    client_secret        = optional(string)
    schema_authorization = optional(string)
    authentication       = optional(string)
  }))
  default = {}
  # Note: Not marking as sensitive because credential_type needs to be used
  # in for_each conditions. The actual sensitive values (passwords, keys)
  # should be stored in gitignored .tfvars files.
}

#############################################
# Locals (legacy - kept for backward compatibility)
#############################################

locals {
  project_config = try(yamldecode(file(var.yaml_file)), {})
}
