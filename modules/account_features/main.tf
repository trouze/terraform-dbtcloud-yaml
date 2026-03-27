terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

resource "dbtcloud_account_features" "features" {
  count = var.features != null ? 1 : 0

  advanced_ci     = try(var.features.advanced_ci, null)
  partial_parsing = try(var.features.partial_parsing, null)
  repo_caching    = try(var.features.repo_caching, null)
}
