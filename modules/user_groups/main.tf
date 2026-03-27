terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  user_groups_map = {
    for ug in var.user_groups_data :
    tostring(ug.user_id) => ug
  }
}

resource "dbtcloud_user_groups" "user_groups" {
  for_each = local.user_groups_map

  user_id = each.value.user_id
  group_ids = [
    for gk in try(each.value.group_keys, []) :
    tonumber(lookup(var.group_ids, gk, null))
    if lookup(var.group_ids, gk, null) != null
  ]
}
