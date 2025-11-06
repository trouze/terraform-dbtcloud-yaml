terraform {
  required_version = ">= 1.0"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 0.3"
    }
  }
}

# Use the module from your local clone or from GitHub
module "dbt_cloud" {
source = "github.com/trouze/dbt-terraform-modules-yaml"
  
  yaml_file      = file("${path.module}/dbt-config.yml")
  dbt_account_id = var.dbt_account_id
  dbt_token      = var.dbt_token
  dbt_host_url   = var.dbt_host_url
  token_map      = var.token_map
  target_name    = var.target_name
}

output "project_id" {
  description = "The dbt Cloud project ID"
  value       = module.dbt_cloud.project_id
}

output "environment_ids" {
  description = "Map of environment names to their dbt Cloud IDs"
  value       = module.dbt_cloud.environment_ids
}

output "job_ids" {
  description = "Map of job names to their dbt Cloud IDs"
  value       = module.dbt_cloud.job_ids
}
