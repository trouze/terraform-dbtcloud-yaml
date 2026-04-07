output "group_ids" {
  description = "Map of group key to dbt Cloud group ID"
  value = merge(
    { for k, g in dbtcloud_group.groups : k => g.id },
    { for k, g in dbtcloud_group.protected_groups : k => g.id }
  )
}
