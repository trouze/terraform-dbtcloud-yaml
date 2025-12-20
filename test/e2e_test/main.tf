# End-to-End Test Configuration

terraform {
  required_version = ">= 1.5"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "= 1.5.1"
    }
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_token
  host_url   = var.dbt_host_url
}

variable "dbt_account_id" {
  description = "dbt Cloud account ID"
  type        = number
}

variable "dbt_token" {
  description = "dbt Cloud API token"
  type        = string
  sensitive   = true
}

variable "dbt_host_url" {
  description = "dbt Cloud host URL"
  type        = string
  default     = "https://cloud.getdbt.com/api"
}

module "dbt_cloud" {
  source = "../.."

  # Pass credentials to the module
  dbt_account_id = var.dbt_account_id
  dbt_token      = var.dbt_token
  dbt_host_url   = var.dbt_host_url

  yaml_file   = "${path.module}/dbt-cloud-config.yml"
  target_name = "e2e_test"

  # Provide credential secrets via token_map
  # These are NOT exported by the API and must be provided manually
  token_map = {
    # Example for Databricks:
    # "databricks_prod_token" = var.databricks_token
    
    # Example for Snowflake:
    # "snowflake_prod_password" = var.snowflake_password
    
    # Example for BigQuery:
    # "bigquery_prod_key" = var.bigquery_service_account_json
    
    # Add your actual token keys here based on connection types
    # The keys should match the credential keys in your YAML file
  }
}

# Outputs for verification
output "project_ids" {
  description = "Map of project keys to IDs"
  value       = module.dbt_cloud.v2_project_ids
}

output "environment_ids" {
  description = "Map of environment keys to IDs"
  value       = module.dbt_cloud.v2_environment_ids
}

output "job_ids" {
  description = "Map of job keys to IDs"
  value       = module.dbt_cloud.v2_job_ids
}

output "connection_ids" {
  description = "Map of connection keys to IDs"
  value       = module.dbt_cloud.v2_connection_ids
}

output "repository_ids" {
  description = "Map of repository keys to IDs"
  value       = module.dbt_cloud.v2_repository_ids
}

