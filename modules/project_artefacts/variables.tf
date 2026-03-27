variable "projects" {
  description = "List of project configurations. Each project may have an 'artefacts' block with docs_job and freshness_job keys."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "job_ids" {
  description = "Map of composite key (project_key_job_key) to dbt Cloud job ID (from jobs module)"
  type        = map(string)
  default     = {}
}
