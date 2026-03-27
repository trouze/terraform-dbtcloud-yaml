variable "connections_data" {
  description = "List of global connection configurations from YAML global_connections[]"
  type        = any
  default     = []
}

variable "connection_credentials" {
  description = "Map of connection key to OAuth/auth credential objects (sensitive fields like private_key, client_secret)"
  type        = map(any)
  default     = {}
  sensitive   = true
}
