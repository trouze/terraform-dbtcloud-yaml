output "profile_ids" {
  description = "Map of composite key (project_key_profile_key) to dbt Cloud profile ID"
  value       = { for k, p in dbtcloud_profile.profiles : k => p.id }
}
