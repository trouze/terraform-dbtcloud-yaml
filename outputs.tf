output "project_id" {
  description = "The dbt Cloud project ID"
  value       = module.project.project_id
}

output "repository_id" {
  description = "The dbt Cloud repository ID"
  value       = module.repository.repository_id
}

output "environment_ids" {
  description = "Map of environment names to their dbt Cloud IDs"
  value       = module.environments.environment_ids
}

output "credential_ids" {
  description = "Map of credential names to their dbt Cloud IDs"
  value       = module.credentials.credential_ids
}

output "job_ids" {
  description = "Map of job names to their dbt Cloud IDs"
  value       = module.jobs.job_ids
}
