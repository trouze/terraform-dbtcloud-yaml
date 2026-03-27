variable "projects" {
  description = "List of project configurations. Env var job overrides are read from project.environments[].jobs[].env_var_overrides or project.jobs[].env_var_overrides."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "job_ids" {
  description = "Map of composite key (project_key_job_key) to dbt Cloud job ID (from jobs module)"
  type        = map(string)
}
