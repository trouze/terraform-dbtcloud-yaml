# Resource IDs created by this topology.
# Use these to reference dbt Cloud resources in other systems.

output "project_ids" {
  description = "Map of project key to dbt Cloud project ID. Key: 'analytics'"
  value       = module.dbt_cloud.project_ids
}

output "environment_ids" {
  description = "Map of composite key to environment ID. Keys: 'analytics_prod', 'analytics_dev'"
  value       = module.dbt_cloud.environment_ids
}

output "profile_ids" {
  description = "Map of composite key to profile ID. Key: 'analytics_prod_profile'"
  value       = module.dbt_cloud.profile_ids
}

output "job_ids" {
  description = "Map of composite key to job ID. Keys: 'analytics_ci_check', 'analytics_merge_build', 'analytics_daily_build'"
  value       = module.dbt_cloud.job_ids
}
