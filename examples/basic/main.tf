terraform {
  required_version = ">= 1.0"

  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.3"
    }
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_api_token
}

# Test the dbt-terraform-modules-yaml module from GitHub
module "dbt_cloud_test" {
  source = "git::https://github.com/trouze/dbt-terraform-modules-yaml.git?ref=v0.1.0-alpha"

  dbt_account_id = var.dbt_account_id
  dbt_token      = var.dbt_token
  dbt_pat        = var.dbt_pat != "" ? var.dbt_pat : var.dbt_token
  dbt_host_url   = var.dbt_host_url
  yaml_file      = var.yaml_file_path
  token_map      = var.token_map
  target_name    = var.target_name
}
