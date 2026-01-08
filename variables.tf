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

#############################################
# Locals (legacy - kept for backward compatibility)
#############################################

locals {
  project_config = try(yamldecode(file(var.yaml_file)), {})
}
