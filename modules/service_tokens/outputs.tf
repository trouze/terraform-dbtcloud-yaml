output "service_token_ids" {
  description = "Map of service token key to dbt Cloud service token ID"
  value = merge(
    { for k, t in dbtcloud_service_token.service_tokens : k => t.id },
    { for k, t in dbtcloud_service_token.protected_service_tokens : k => t.id }
  )
}
