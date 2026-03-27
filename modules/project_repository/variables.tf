variable "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  type        = map(string)
}

variable "repository_ids" {
  description = "Map of project key to repository_id (the integer ID used for project_repository links, not the resource ID)"
  type        = map(string)
}
