variable "projects" {
  description = "List of project configurations. Each project may have a 'profiles' list."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "global_connection_ids" {
  description = "Map of global connection key to connection ID (from global_connections module)"
  type        = map(string)
  default     = {}
}

variable "credential_ids" {
  description = "Map of composite key (project_key_env_key) to credential ID (from credentials module)"
  type        = map(string)
  default     = {}
}

variable "extended_attribute_ids" {
  description = "Map of composite key (project_key_ea_key) to extended_attributes ID (from extended_attributes module)"
  type        = map(string)
  default     = {}
}
