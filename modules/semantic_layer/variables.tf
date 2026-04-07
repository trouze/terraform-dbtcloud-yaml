variable "projects" {
  description = "Project configs. Optional semantic_layer_config (environment_id and/or environment_key); see modules/semantic_layer."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "environment_ids" {
  description = "Map of composite key (project_key_env_key) to dbt Cloud environment ID (from environments module)"
  type        = map(string)
  default     = {}
}
