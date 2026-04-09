terraform {
  required_version = ">= 1.14"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.9"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.0"
    }
  }
}

provider "http" {}

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
