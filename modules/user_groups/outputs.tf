output "user_group_ids" {
  description = "Map of user_id (string) to user_groups resource ID"
  value       = { for k, ug in dbtcloud_user_groups.user_groups : k => ug.id }
}
