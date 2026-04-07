output "credential_ids" {
  description = "Map of composite key (project_key_env_key or project_key_profile_key) to credential ID. Merges all warehouse types."
  value       = local.merged_credential_ids
}

output "credential_ids_by_source_id" {
  description = "Maps environments' YAML credential.id (legacy dbt Cloud ID) to the Terraform-managed credential_id after apply."
  value       = local.credential_ids_by_source_id
}
