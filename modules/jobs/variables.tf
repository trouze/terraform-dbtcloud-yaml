variable "projects" {
  description = "List of project configurations. Jobs are defined only on project.jobs[] with environment_key."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "environment_ids" {
  description = "Map of composite key (project_key_env_key) to dbt Cloud environment ID (from environments module)"
  type        = map(string)
}

variable "deployment_types" {
  description = "Map of project_key_env_key to environment deployment_type (from module.environments.deployment_types). Used to gate run_compare_changes (staging/production + cross-env deferral only)."
  type        = map(any)
  default     = {}
}
