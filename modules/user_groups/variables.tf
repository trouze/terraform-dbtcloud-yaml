variable "user_groups_data" {
  description = "List of user-to-group assignments from YAML user_groups[]. Each entry has user_id and group_keys list."
  type        = any
  default     = []
}

variable "group_ids" {
  description = "Map of group key to dbt Cloud group ID (from groups module)"
  type        = map(string)
  default     = {}
}
