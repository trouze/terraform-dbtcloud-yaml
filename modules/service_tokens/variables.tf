variable "service_tokens_data" {
  description = "List of service token configurations from YAML service_tokens[]"
  type        = any
  default     = []
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID (resolves permissions[].project_key)"
  type        = map(number)
  default     = {}
}

variable "skip_global_project_permissions" {
  description = "When true, create permissions without per-project IDs (all_projects only); for when projects are managed outside this root module"
  type        = bool
  default     = false
}
