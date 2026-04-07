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
#
# Provenance: v2 set resource_metadata on assignments; stock dbtcloud may not
# support that on dbtcloud_user_groups — mirror intent via
# local.user_groups_provenance and output user_groups_provenance.
#############################################

locals {
  # COMPAT(v1-schema): for_each key from explicit key or user_id — v2 schema may require key always.
  user_groups_map = {
    for ug in var.user_groups_data :
    coalesce(try(ug.key, null), tostring(ug.user_id)) => ug
  }

  user_groups_provenance = {
    for key, ug in local.user_groups_map :
    key => {
      source_key      = key
      source_identity = "USERGRP:${key}"
      source_id       = try(ug.id, null)
      user_id         = ug.user_id
    }
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
