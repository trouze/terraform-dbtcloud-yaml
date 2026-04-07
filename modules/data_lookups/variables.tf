variable "projects" {
  description = "Project list from YAML (same shape as root local.projects) — scanned for LOOKUP: connection and repository placeholders"
  type        = any
}

variable "dbt_pat" {
  description = "Personal access token for GitHub installations API (optional)"
  type        = string
  sensitive   = true
  default     = null
}

variable "dbt_host_url" {
  description = "dbt Cloud host URL (e.g. https://cloud.getdbt.com); used for integrations HTTP calls"
  type        = string
  default     = null
}
