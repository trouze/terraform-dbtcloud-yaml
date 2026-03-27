output "environment_ids" {
  description = "Map of composite key (project_key_env_key) to dbt Cloud environment ID"
  value = merge(
    { for k, e in dbtcloud_environment.environments : k => e.environment_id },
    { for k, e in dbtcloud_environment.protected_environments : k => e.environment_id }
  )
}

output "deployment_types" {
  description = "Map of composite key (project_key_env_key) to environment deployment_type (for job SAO validation)"
  value = merge(
    { for k, e in dbtcloud_environment.environments : k => e.deployment_type },
    { for k, e in dbtcloud_environment.protected_environments : k => e.deployment_type }
  )
}
