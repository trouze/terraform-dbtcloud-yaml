variable "projects" {
  description = "Project configs. Optional project_artefacts block (docs_job_key, freshness_job_key); see modules/project_artefacts."
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
