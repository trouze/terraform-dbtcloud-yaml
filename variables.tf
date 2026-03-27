#############################################
# dbt Cloud Configuration
#############################################

variable "dbt_account_id" {
  description = "dbt Cloud account ID"
  type        = number
  default     = null

  validation {
    condition     = var.dbt_account_id == null || var.dbt_account_id > 0
    error_message = "dbt_account_id must be a positive integer"
  }
}

variable "dbt_token" {
  description = "dbt Cloud API token for authentication"
  type        = string
  sensitive   = true
  default     = null

  validation {
    condition     = var.dbt_token == null || length(var.dbt_token) > 0
    error_message = "dbt_token cannot be empty"
  }
}

variable "dbt_pat" {
  description = "dbt Cloud personal access token for GitHub App integration discovery (service tokens cannot access the integrations API)"
  type        = string
  sensitive   = true
  default     = null
}

variable "dbt_host_url" {
  description = "dbt Cloud host URL (e.g., https://cloud.getdbt.com or custom domain)"
  type        = string
  default     = null

  validation {
    condition     = var.dbt_host_url == null || can(regex("^https://", var.dbt_host_url))
    error_message = "dbt_host_url must start with https://"
  }
}

#############################################
# YAML Configuration
#############################################

variable "yaml_file" {
  description = "Path to the YAML file defining dbt Cloud resources (projects, environments, jobs, etc.)"
  type        = string

  validation {
    condition     = can(file(var.yaml_file))
    error_message = "yaml_file '${var.yaml_file}' does not exist or cannot be read. Check the path relative to where you run terraform."
  }

  validation {
    condition     = can(yamldecode(file(var.yaml_file)))
    error_message = "yaml_file '${var.yaml_file}' exists but cannot be parsed as YAML. Check for indentation errors or invalid syntax."
  }
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
  description = "Map of credential token names to their actual values (e.g., Databricks tokens). Token names correspond to credential.token_name in YAML."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "connection_credentials" {
  description = "Map of global connection keys to their OAuth/auth credential objects (client_id, client_secret, private_key, etc.)"
  type        = map(any)
  default     = {}
  sensitive   = true
}

variable "environment_credentials" {
  description = "Map of environment credential keys to their warehouse credential objects. Key format: project_key_env_key. Supports 14 warehouse types via credential_type field."
  type        = map(any)
  default     = {}
  sensitive   = true
}

variable "oauth_client_secrets" {
  description = "Map of OAuth configuration keys to their client secrets"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "lineage_tokens" {
  description = "Map of lineage integration keys to their authentication tokens (Tableau, Looker, etc.)"
  type        = map(string)
  default     = {}
  sensitive   = true
}

#############################################
# Repository Options
#############################################

variable "enable_gitlab_deploy_token" {
  description = "Preserve native GitLab deploy_token strategy. Defaults to false due to a known API limitation (GitlabGetError on some accounts). Set to true only when GitLab OAuth access is confirmed."
  type        = bool
  default     = false
}

#############################################
# Locals
#############################################

locals {
  yaml_content = yamldecode(file(var.yaml_file))

  # Support both single project (project:) and multi-project (projects:) YAML shapes.
  # Single-project users keep their existing YAML unchanged — the project: key is
  # automatically wrapped into a one-element list.
  projects = try(
    local.yaml_content.projects,
    [local.yaml_content.project]
  )
}
