# End-to-End Test Configuration

terraform {
  required_version = ">= 1.5"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 0.3"
    }
  }
}

provider "dbtcloud" {
  # Credentials from environment:
  # DBTCLOUD_ACCOUNT_ID
  # DBTCLOUD_TOKEN
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
  value       = module.dbt_cloud.project_ids
}

output "environment_ids" {
  description = "Map of environment keys to IDs"
  value       = module.dbt_cloud.environment_ids
}

output "job_ids" {
  description = "Map of job keys to IDs"
  value       = module.dbt_cloud.job_ids
}

output "connection_ids" {
  description = "Map of connection keys to IDs"
  value       = module.dbt_cloud.connection_ids
}

