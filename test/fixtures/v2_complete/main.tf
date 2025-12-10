terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.3"
    }
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_token
  host_url   = var.dbt_host_url
}

module "dbt_cloud" {
  source = "../../"

  yaml_file   = "${path.module}/dbt-config.yml"
  target_name = var.target_name
  token_map   = var.token_map
}

output "v2_project_ids" {
  value = try(module.dbt_cloud.v2_project_ids, null)
}

output "v2_environment_ids" {
  value = try(module.dbt_cloud.v2_environment_ids, null)
}

output "v2_job_ids" {
  value = try(module.dbt_cloud.v2_job_ids, null)
}

output "v2_connection_ids" {
  value = try(module.dbt_cloud.v2_connection_ids, null)
}

output "v2_repository_ids" {
  value = try(module.dbt_cloud.v2_repository_ids, null)
}
