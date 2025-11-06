variable "project_id" {
  description = "The ID of the project to which jobs belong"
  type        = string
}

variable "job_ids" {
  description = "Map of Env Name _ Job Name as key : Job ID"
  type        = any
}

variable "environments_data" {
  description = "List of environment configurations, including credentials, overrides"
  type = any
}
