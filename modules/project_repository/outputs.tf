output "project_repository_ids" {
  description = "Map of project key to project_repository resource ID"
  value = merge(
    { for k, pr in dbtcloud_project_repository.project_repositories : k => pr.id },
    { for k, pr in dbtcloud_project_repository.protected_project_repositories : k => pr.id }
  )
}
