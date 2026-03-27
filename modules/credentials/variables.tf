variable "projects" {
  description = "List of project configurations. Each project's environments may have a 'credential' sub-object."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "token_map" {
  description = "Map of token names to their values (used for legacy Databricks token_name references)"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "environment_credentials" {
  description = "Map of composite key (project_key_env_key) to credential objects. Each object must include 'credential_type' to select the warehouse adapter."
  type        = map(any)
  default     = {}
  sensitive   = true
}
