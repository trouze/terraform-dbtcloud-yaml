terraform {
  required_version = ">= 1.0"

  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 0.3"
    }
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_api_token
}

module "dbt_cloud" {
  source = "../.."

  dbt_config_path = var.dbt_config_path
  token_map       = var.token_map
  target_name     = var.target_name
}

output "project_id" {
  description = "The created dbt Cloud project ID"
  value       = module.dbt_cloud.project_id
}

output "project_name" {
  description = "The created dbt Cloud project name"
  value       = module.dbt_cloud.project_name
}
