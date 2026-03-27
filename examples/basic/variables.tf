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

variable "yaml_file_path" {
  description = "Path to the dbt Cloud configuration YAML file"
  type        = string
  default     = "./dbt-config.yml"
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
          credential_type = "databricks"
          token           = "dapi..."
          catalog         = "main"
          schema          = "analytics"
        }
        analytics_prod_snowflake = {
          credential_type = "snowflake"
          auth_type       = "password"
          user            = "DBT_USER"
          password        = "..."
          schema          = "ANALYTICS"
          database        = "ANALYTICS"
          warehouse       = "TRANSFORMING"
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
        databricks_prod = {
          client_id     = "..."
          client_secret = "..."
        }
        snowflake_prod = {
          oauth_client_id     = "..."
          oauth_client_secret = "..."
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
    Key corresponds to the composite of project key + lineage_integrations[].key in YAML.

    Example:
      lineage_tokens = {
        analytics_tableau_prod = "..."
      }
  EOT
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "oauth_client_secrets" {
  description = <<-EOT
    Map of OAuth configuration keys to their client secrets.
    Key corresponds to oauth_configurations[].key in YAML.

    Example:
      oauth_client_secrets = {
        snowflake_oauth = "..."
      }
  EOT
  type        = map(string)
  sensitive   = true
  default     = {}
}
