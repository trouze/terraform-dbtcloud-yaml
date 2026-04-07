variable "ip_rules_data" {
  description = "List of IP restriction rule configurations from YAML ip_restrictions[]. Optional protected: true applies lifecycle.prevent_destroy; optional id for resource_metadata.source_id when provider supports it."
  type        = any
  default     = []
}
