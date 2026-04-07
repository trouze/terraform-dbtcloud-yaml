variable "groups_data" {
  description = "List of group configurations from YAML groups[]"
  type        = any
  default     = []
}

variable "skip_global_project_permissions" {
  description = "When true, project-scoped permission entries are collapsed to all_projects-only blocks so global groups do not expand the project dependency graph (scoped global-object adoption)."
  type        = bool
  default     = false
}
