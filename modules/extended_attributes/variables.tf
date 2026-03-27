variable "projects" {
  description = "List of project configurations. Each project may have an 'extended_attributes' list."
  type        = any
}

variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}
