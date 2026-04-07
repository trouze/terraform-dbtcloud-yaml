variable "projects" {
  description = "Project configs. v1 'semantic_layer' (environment / environment_key → environment_ids) or v2 'semantic_layer_config' (environment_id); see modules/semantic_layer."
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
