output "lookup_connection_ids" {
  description = "Map from literal YAML placeholder (e.g. LOOKUP:My Warehouse) to dbt global connection id from data.dbtcloud_global_connections"
  value       = local.lookup_connection_ids
}

output "lookup_connection_keys" {
  description = "Set of LOOKUP:… placeholders found under environments.connection and profiles.connection_key"
  value       = local.lookup_connection_keys
}

output "lookup_repository_keys" {
  description = "Set of LOOKUP:… values when project.repository is a scalar (importer/v2 style); object-shaped repositories are not included"
  value       = local.lookup_repository_keys
}

output "github_installation_by_owner" {
  description = "Lowercase GitHub org/user login → installation id (empty if dbt_pat unset or API error)"
  value       = local.github_installation_by_owner
}

output "github_installation_fallback_id" {
  description = "First GitHub installation id when owner cannot be matched (null if none)"
  value       = local.github_installation_fallback_id
}
