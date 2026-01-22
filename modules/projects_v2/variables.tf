terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
    null = {
      source = "hashicorp/null"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.0"
    }
  }
}

variable "account" {
  description = "Account-level metadata"
  type = object({
    name     = string
    host_url = string
    id       = optional(number)
  })
}

variable "globals" {
  description = "Global resources (connections, repositories, service tokens, groups, notifications, PrivateLink endpoints)"
  type = object({
    connections           = optional(list(any), [])
    repositories          = optional(list(any), [])
    service_tokens        = optional(list(any), [])
    groups                = optional(list(any), [])
    notifications         = optional(list(any), [])
    privatelink_endpoints = optional(list(any), [])
  })
  default = {
    connections           = []
    repositories          = []
    service_tokens        = []
    groups                = []
    notifications         = []
    privatelink_endpoints = []
  }
}

variable "projects" {
  description = "List of projects to create"
  # Using any type to allow yamldecode() tuples with heterogeneous structures
  # (empty lists vs populated lists, null vs string values)
  type = any
}

variable "token_map" {
  description = "Map of credential token names to their actual values"
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

variable "dbt_account_id" {
  description = "dbt Cloud account ID"
  type        = number
}

variable "dbt_pat" {
  description = "dbt Cloud Personal Access Token (dbtu_*) for retrieving integration IDs. Required for GitHub App integration discovery. Service tokens cannot access the integrations API."
  type        = string
  default     = null
  sensitive   = true
}

variable "dbt_host_url" {
  description = "dbt Cloud host URL (e.g., https://cloud.getdbt.com). Defaults to account.host_url if not provided."
  type        = string
  default     = null
}

variable "environment_credentials" {
  description = "Map of environment keys to credential values. Keys are 'project_key_env_key' (e.g., 'my_project_prod')"
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

    # BigQuery
    dataset = optional(string)

    # Postgres/Redshift
    default_schema = optional(string)
    username       = optional(string)
    target_name    = optional(string) # "postgres" or "redshift"

    # Athena
    aws_access_key_id     = optional(string)
    aws_secret_access_key = optional(string)

    # Fabric/Synapse
    tenant_id            = optional(string)
    client_id            = optional(string)
    client_secret        = optional(string)
    schema_authorization = optional(string)
    authentication       = optional(string) # SQL, ActiveDirectoryPassword, ServicePrincipal

    # Databricks
    token   = optional(string)
    catalog = optional(string)

    # Starburst/Trino
    # Uses catalog + schema (already defined above)

    # Spark
    # Uses schema (already defined above)

    # Teradata
    # Uses schema (already defined above)
  }))
  default = {}
  # Note: Not marking as sensitive because credential_type needs to be used
  # in for_each conditions. The actual sensitive values (passwords, keys)
  # should be stored in gitignored .tfvars files.
}

