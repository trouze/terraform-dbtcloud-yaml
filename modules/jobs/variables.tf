variable "project_id" {
  description = "The ID of the project to which jobs belong"
  type        = string
}

variable "environment_ids" {
  description = "The ID of the project this repository is associated with"
  type        = map(string)
}

variable "environments_data" {
  description = "List of environment configurations, including credentials"
  type = any
}
