variable "projects" {
  description = "List of project configurations. Each project may have an 'environment_variables' list."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "token_map" {
  description = "Map of token names to values (used for secret_ prefixed env var values)"
  type        = map(string)
  default     = {}
  sensitive   = true
}
