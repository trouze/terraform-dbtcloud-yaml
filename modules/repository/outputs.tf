output "repository_ids" {
  description = "Map of project key to repository_id (integer ID used for project_repository links)"
  value = merge(
    { for k, r in dbtcloud_repository.repositories : k => tostring(r.repository_id) },
    { for k, r in dbtcloud_repository.protected_repositories : k => tostring(r.repository_id) }
  )
}

output "protected_repository_keys" {
  description = "Project keys whose dbtcloud_repository uses lifecycle.prevent_destroy (for module.project_repository split)."
  value       = keys(local.protected_repos_map)
}
