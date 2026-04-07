output "oauth_configuration_ids" {
  description = "Map of OAuth configuration key to dbt Cloud OAuth configuration ID"
  value = merge(
    { for k, o in dbtcloud_oauth_configuration.oauth_configurations : k => o.id },
    { for k, o in dbtcloud_oauth_configuration.protected_oauth_configurations : k => o.id },
  )
}
