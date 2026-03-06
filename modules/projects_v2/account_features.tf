#############################################
# Account Features (singleton)
# Boolean feature flags for the entire account.
# Private API — may not be available on all deployments.
# No import or delete support.
#############################################

resource "dbtcloud_account_features" "features" {
  count = local.account_features != null ? 1 : 0

  advanced_ci     = try(local.account_features.advanced_ci, null)
  partial_parsing = try(local.account_features.partial_parsing, null)
  repo_caching    = try(local.account_features.repo_caching, null)
}
