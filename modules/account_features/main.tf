terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.9"
    }
  }
}

#############################################
# Account Features (singleton)
# Boolean feature flags for the entire account.
# Private API — may not be available on all deployments.
# No import or delete support.
#############################################

resource "dbtcloud_account_features" "features" {
  count = var.features != null ? 1 : 0

  advanced_ci     = try(var.features.advanced_ci, null)
  partial_parsing = try(var.features.partial_parsing, null)
  repo_caching    = try(var.features.repo_caching, null)
}
