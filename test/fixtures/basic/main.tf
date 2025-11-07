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

  dbt_account_id = var.dbt_account_id
  dbt_token      = var.dbt_token
  dbt_host_url   = var.dbt_host_url
  yaml_file      = "${path.module}/dbt-config.yml"
  target_name    = var.target_name
  token_map      = var.token_map
}

output "project_id" {
  value = try(module.dbt_cloud.project_id, null)
}

output "repository_id" {
  value = try(module.dbt_cloud.repository_id, null)
}

output "environment_ids" {
  value = try(module.dbt_cloud.environment_ids, {})
}

output "credential_ids" {
  value = try(module.dbt_cloud.credential_ids, {})
}

output "job_ids" {
  value = try(module.dbt_cloud.job_ids, {})
}
