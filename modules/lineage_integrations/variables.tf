variable "projects" {
  description = "List of project configurations. Each project may have a 'lineage_integrations' list."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "lineage_tokens" {
  description = "Map of composite key (project_key_integration_key) to authentication token"
  type        = map(string)
  default     = {}
  sensitive   = true
}
