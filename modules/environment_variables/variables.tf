variable "project_id" {
  description = "The ID of the project to which jobs belong"
  type        = string
}

variable "environment_ids" {
  description = "The ID of the project this repository is associated with"
  type        = map(string)
}

variable "environment_variables" {
  description = "A list of environment variable configurations"
  type = any
}

variable "token_map" {
    type = map(string)
    description = "Mapping of token names to credential"
    sensitive = true
}
