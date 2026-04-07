output "group_ids" {
  description = "Map of group key to dbt Cloud group ID"
  value = merge(
    { for k, g in dbtcloud_group.groups : k => g.id },
    { for k, g in dbtcloud_group.protected_groups : k => g.id }
  )
}

output "groups_provenance" {
  description = "Per-group provenance (YAML key, logical identity, optional external id) merged with dbt_group_id — mirrors v2 resource_metadata without provider support"
  value = {
    for key, meta in local.groups_provenance :
    key => merge(
      meta,
      {
        dbt_group_id = coalesce(
          try(dbtcloud_group.groups[key].id, null),
          try(dbtcloud_group.protected_groups[key].id, null),
        )
      },
    )
  }
}
