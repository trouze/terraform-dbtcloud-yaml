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

variable "privatelink_endpoints" {
  description = "Optional account-level PrivateLink endpoint registry (key + endpoint_id) for resolving global_connections[].private_link_endpoint_key"
  type        = any
  default     = []
}
