output "credential_ids" {
  description = "Map of composite key (project_key_env_key or project_key_profile_key) to credential ID. Merges all warehouse types."
  value       = local.merged_credential_ids
}

output "credential_ids_by_source_id" {
  description = "Maps YAML credential.id (environment or standalone profile credentials, legacy dbt Cloud ID) to Terraform-managed credential_id after apply (COMPAT v2/importer)."
  value       = local.credential_ids_by_source_id
}
