# End-to-End Test Configuration

terraform {
  required_version = ">= 1.5"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.3"
    }
  }
}

provider "dbtcloud" {
  # Credentials from environment:
  # DBT_TARGET_ACCOUNT_ID (mapped to TF_VAR_dbt_account_id)
  # DBT_TARGET_API_TOKEN (mapped to TF_VAR_dbt_token)
  # DBT_TARGET_HOST_URL (mapped to TF_VAR_dbt_host_url)
}

module "dbt_cloud" {
  source = "../.."

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

