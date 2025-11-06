#############################################
# dbt Cloud Configuration
#############################################

variable "dbt_account_id" {
  description = "dbt Cloud account ID"
  type        = number

  validation {
    condition     = var.dbt_account_id > 0
    error_message = "dbt_account_id must be a positive integer"
  }
}

variable "dbt_token" {
  description = "dbt Cloud API token for authentication"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.dbt_token) > 0
    error_message = "dbt_token cannot be empty"
  }
}

variable "dbt_pat" {
  type = string
  sensitive = true
  default = ""
}

variable "dbt_host_url" {
  description = "dbt Cloud host URL (e.g., https://cloud.getdbt.com or custom domain)"
  type        = string

  validation {
    condition     = can(regex("^https://", var.dbt_host_url))
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
    error_message = "yaml_file must point to a valid, readable file"
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
  description = "Map of credential token names to their actual values (e.g., Databricks tokens). Token names should correspond to credential.token_name in YAML."
  type        = map(string)
  default     = {}
  sensitive   = true
}

#############################################
# Locals
#############################################

locals {
  project_config = yamldecode(file(var.yaml_file))
}
