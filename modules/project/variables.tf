variable "projects" {
  description = "List of project configurations. Each entry must have at minimum a 'name' field, and optionally a 'key' field (defaults to name) and 'protected' boolean."
  type        = any
}

variable "target_name" {
  description = "Optional prefix prepended to all project names (e.g., 'dev-' or 'prod-')"
  type        = string
  default     = ""
}
