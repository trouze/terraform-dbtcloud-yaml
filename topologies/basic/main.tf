terraform {
  required_version = ">= 1.0"

  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.9"
    }
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_token
  host_url   = var.dbt_host_url
}

module "dbt_cloud" {
  # Pin to a release tag to avoid unexpected changes on terraform init.
  # Update the ref when you're ready to upgrade:
  #   https://github.com/dbt-labs/terraform-dbtcloud-as-yaml/releases
  source = "github.com/dbt-labs/terraform-dbtcloud-as-yaml?ref=v0.1.0"

  dbt_account_id = var.dbt_account_id
  dbt_token      = var.dbt_token
  dbt_host_url   = var.dbt_host_url
  dbt_pat        = var.dbt_pat
  yaml_file      = "${path.module}/dbt-config.yml"
  target_name    = var.target_name

  # Sensitive credentials — never put these in the YAML file
  token_map               = var.token_map
  environment_credentials = var.environment_credentials
  connection_credentials  = var.connection_credentials
  lineage_tokens          = var.lineage_tokens
  oauth_client_secrets    = var.oauth_client_secrets
}
