#############################################
# v1 Outputs (Single Project)
#############################################

output "project_id" {
  description = "The dbt Cloud project ID (v1 only)"
  value       = local.schema_version == 1 ? module.project[0].project_id : null
}

output "repository_id" {
  description = "The dbt Cloud repository ID (v1 only)"
  value       = local.schema_version == 1 ? module.repository[0].repository_id : null
}

output "environment_ids" {
  description = "Map of environment names to their dbt Cloud IDs (v1 only)"
  value       = local.schema_version == 1 ? module.environments[0].environment_ids : null
}

output "credential_ids" {
  description = "Map of credential names to their dbt Cloud IDs (v1 only)"
  value       = local.schema_version == 1 ? module.credentials[0].credential_ids : null
}

output "job_ids" {
  description = "Map of job names to their dbt Cloud IDs (v1 only)"
  value       = local.schema_version == 1 ? module.jobs[0].job_ids : null
}

#############################################
# v2 Outputs (Multi-Project)
#############################################

output "v2_project_ids" {
  description = "Map of project keys to project IDs (v2 only)"
  value       = local.schema_version == 2 ? module.projects_v2[0].project_ids : null
}

output "v2_environment_ids" {
  description = "Map of project_key_environment_key to environment IDs (v2 only)"
  value       = local.schema_version == 2 ? module.projects_v2[0].environment_ids : null
}

output "v2_job_ids" {
  description = "Map of project_key_environment_key_job_key to job IDs (v2 only)"
  value       = local.schema_version == 2 ? module.projects_v2[0].job_ids : null
}

output "v2_connection_ids" {
  description = "Map of connection keys to connection IDs (v2 only)"
  value       = local.schema_version == 2 ? module.projects_v2[0].connection_ids : null
}

output "v2_repository_ids" {
  description = "Map of project keys to repository IDs (v2 only)"
  value       = local.schema_version == 2 ? module.projects_v2[0].repository_ids : null
}

output "v2_service_token_ids" {
  description = "Map of service token keys to service token IDs (v2 only)"
  value       = local.schema_version == 2 ? module.projects_v2[0].service_token_ids : null
}

output "v2_group_ids" {
  description = "Map of group keys to group IDs (v2 only)"
  value       = local.schema_version == 2 ? module.projects_v2[0].group_ids : null
}

output "v2_notification_ids" {
  description = "Map of notification keys to notification IDs (v2 only)"
  value       = local.schema_version == 2 ? module.projects_v2[0].notification_ids : null
}

output "v2_job_deferral_debug" {
  description = "Debug: Job deferral resolution (v2 only)"
  value       = local.schema_version == 2 ? module.projects_v2[0].job_deferral_debug : null
}
