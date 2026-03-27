variable "projects" {
  description = "List of project configurations. Each project may have a 'repository' sub-object with git configuration."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID (from modules/project output)"
  type        = map(string)
}

variable "dbt_pat" {
  description = "Personal access token for GitHub App integration discovery. If set, github_app strategy is enabled even without an explicit installation ID."
  type        = string
  sensitive   = true
  default     = null
}

variable "enable_gitlab_deploy_token" {
  description = "Preserve native GitLab deploy_token strategy. Defaults to false due to known API limitations. Set to true only when GitLab OAuth access is confirmed."
  type        = bool
  default     = false
}
