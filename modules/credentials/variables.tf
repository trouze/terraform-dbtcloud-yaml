variable "environments_data" {
  description = "List of environment configurations, including credentials"
  type = any
}

variable "project_id" {
  description = "The ID of the project these credentials belong to"
  type        = string
}

variable "token_map" {
    type = map(string)
    description = "Mapping of token names to credential"
    sensitive = true
}
