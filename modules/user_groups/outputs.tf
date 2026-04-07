output "user_group_ids" {
  description = "Map of assignment key (YAML key or string user_id) to dbtcloud_user_groups resource ID"
  value       = { for k, ug in dbtcloud_user_groups.user_groups : k => ug.id }
}
