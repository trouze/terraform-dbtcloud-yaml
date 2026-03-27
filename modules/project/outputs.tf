output "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  value = merge(
    { for k, p in dbtcloud_project.projects : k => p.id },
    { for k, p in dbtcloud_project.protected_projects : k => p.id }
  )
}
