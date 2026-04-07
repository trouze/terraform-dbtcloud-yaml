terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.8"
    }
  }
}

#############################################
# User Groups (account-level, maps users to group IDs)
# No delete support — manages group membership only.
#############################################

locals {
  # COMPAT(v1-schema): for_each key from explicit key or user_id — v2 schema may require key always.
  user_groups_map = {
    for ug in var.user_groups_data :
    coalesce(try(ug.key, null), tostring(ug.user_id)) => ug
  }
}

resource "dbtcloud_user_groups" "user_groups" {
  for_each = local.user_groups_map

  user_id = each.value.user_id

  # resource_metadata: pending official dbtcloud provider support on dbtcloud_user_groups.
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "USERGRP:${each.key}"
  #   source_key      = each.key
  #   source_name     = coalesce(try(each.value.name, null), format("user_%s", each.value.user_id))
  # }

  group_ids = [
    for gk in try(each.value.group_keys, []) :
    tonumber(lookup(var.group_ids, gk, null))
    if lookup(var.group_ids, gk, null) != null
  ]
}
