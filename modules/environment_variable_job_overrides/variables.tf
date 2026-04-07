variable "projects" {
  description = "List of project configurations. Job-level environment_variable_overrides on project.jobs[] (see modules/environment_variable_job_overrides)."
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

variable "token_map" {
  description = "Secret values for override values prefixed with secret_ (same semantics as modules/environment_variables)."
  type        = map(string)
  default     = {}
}
