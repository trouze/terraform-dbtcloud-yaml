variable "projects" {
  description = "List of project configurations. Each project may have a 'semantic_layer' block with an 'environment' key."
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
