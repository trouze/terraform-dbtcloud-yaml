terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.8"
    }
  }
}

provider "dbtcloud" {
  account_id = var.dbt_account_id
  token      = var.dbt_token
  host_url   = var.dbt_host_url
}

provider "dbtcloud" {
  alias      = "pat_provider"
  host_url   = var.dbt_host_url
  account_id = var.dbt_account_id
  token      = var.dbt_pat
}
