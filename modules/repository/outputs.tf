output "repository_ids" {
  description = "Map of project key to repository_id (integer ID used for project_repository links)"
  value = merge(
    { for k, r in dbtcloud_repository.repositories : k => tostring(r.repository_id) },
    { for k, r in dbtcloud_repository.protected_repositories : k => tostring(r.repository_id) }
  )
}
