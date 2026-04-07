output "profile_ids" {
  description = "Map of composite key (project_key_profile_key) to dbt Cloud profile_id (numeric API id; use for environment primary_profile_id)"
  value = merge(
    { for k, p in dbtcloud_profile.profiles : k => p.profile_id },
    { for k, p in dbtcloud_profile.protected_profiles : k => p.profile_id },
  )
}
