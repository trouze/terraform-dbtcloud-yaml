variable "oauth_data" {
  description = "List of OAuth configuration entries from YAML oauth_configurations[] (optional: id for resource_metadata.source_id when provider supports it, protected, application_id_uri for Entra)"
  type        = any
  default     = []
}

variable "oauth_client_secrets" {
  description = "Map of OAuth config key to client secret value"
  type        = map(string)
  default     = {}
  sensitive   = true
}
