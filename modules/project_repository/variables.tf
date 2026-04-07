variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "repository_ids" {
  description = "Map of project key to repository_id (the integer ID used for project_repository links, not the resource ID)"
  type        = map(string)
}

variable "protected_repository_keys" {
  description = "Project keys that use protected dbtcloud_repository resources; matching links get lifecycle.prevent_destroy (v2 projects.tf parity)."
  type        = list(string)
  default     = []
}
