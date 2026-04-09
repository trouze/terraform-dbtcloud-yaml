variable "dbt_account_id" {
  description = "dbt Cloud account ID"
  type        = number
}

variable "dbt_token" {
  description = "dbt Cloud API token"
  type        = string
  sensitive   = true
}

variable "dbt_pat" {
  description = "dbt Cloud personal access token (required for GitHub App integration; can be the same as dbt_token)"
  type        = string
  sensitive   = true
  default     = null
}

variable "dbt_host_url" {
  description = "dbt Cloud host URL"
  type        = string
  default     = "https://cloud.getdbt.com"
}

variable "target_name" {
  description = "Default target name (e.g., 'prod')"
  type        = string
  default     = ""
}

#
# Credential variables — sensitive values that are referenced by key from the YAML.
# Never put actual secrets in the YAML file.
#

variable "token_map" {
  description = <<-EOT
    Map of Databricks token names to their values.
    Key corresponds to credential.token_name in YAML.
    Example: { "my_databricks_token" = "dapi..." }
  EOT
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "environment_credentials" {
  description = <<-EOT
    Map of environment credential objects keyed by "{project_key}_{env_key}".
    Each object must include credential_type and type-specific fields.

    Example:
      environment_credentials = {
        analytics_prod = {
          credential_type = "snowflake"
          auth_type       = "password"
          user            = "DBT_USER"
          password        = "..."
          schema          = "ANALYTICS"
          database        = "ANALYTICS"
          warehouse       = "TRANSFORMING_WH"
          role            = "TRANSFORMER"
        }
        analytics_dev = {
          credential_type = "snowflake"
          auth_type       = "password"
          user            = "DBT_USER"
          password        = "..."
          schema          = "ANALYTICS_DEV"
          database        = "ANALYTICS"
          warehouse       = "TRANSFORMING_WH"
          role            = "TRANSFORMER"
        }
      }
  EOT
  type        = map(any)
  sensitive   = true
  default     = {}
}

variable "connection_credentials" {
  description = <<-EOT
    Map of global connection keys to their OAuth/auth credential objects.
    Key corresponds to global_connections[].key in YAML.

    Example:
      connection_credentials = {
        main_connection = {
          client_id     = "..."
          client_secret = "..."
        }
      }
  EOT
  type        = map(any)
  sensitive   = true
  default     = {}
}

variable "lineage_tokens" {
  description = <<-EOT
    Map of lineage integration tokens keyed by "{project_key}_{integration_key}".
    Not used in this topology — included for compatibility.
  EOT
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "oauth_client_secrets" {
  description = <<-EOT
    Map of OAuth configuration keys to their client secrets.
    Not used in this topology — included for compatibility.
  EOT
  type        = map(string)
  sensitive   = true
  default     = {}
}
