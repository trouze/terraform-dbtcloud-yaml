variable "project_id" {
  description = "The ID of the project to which environments belong"
  type        = string
}

variable "environments_data" {
  description = "List of environment configurations, including credentials"
  type = any
}

variable "credential_ids" {
  description = "A map of environment names to their corresponding credential IDs"
  type = map(string)
  default = {}
}
