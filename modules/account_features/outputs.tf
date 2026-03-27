output "account_features_id" {
  description = "The dbt Cloud account_features resource ID (if created)"
  value       = length(dbtcloud_account_features.features) > 0 ? dbtcloud_account_features.features[0].id : null
}
