terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  groups_map = {
    for g in var.groups_data :
    try(g.key, g.name) => g
  }

  protected_groups_map = {
    for k, g in local.groups_map :
    k => g
    if try(g.protected, false) == true
  }

  unprotected_groups_map = {
    for k, g in local.groups_map :
    k => g
    if try(g.protected, false) != true
  }
}

resource "dbtcloud_group" "groups" {
  for_each = local.unprotected_groups_map

  name               = each.value.name
  assign_by_default  = try(each.value.assign_by_default, false)
  sso_mapping_groups = try(each.value.sso_mapping_groups, null)

  dynamic "group_permissions" {
    for_each = try(each.value.permissions, [])
    content {
      permission_set = group_permissions.value.permission_set
      project_id     = try(group_permissions.value.project_id, null)
      all_projects   = try(group_permissions.value.all_projects, group_permissions.value.project_id == null)
    }
  }
}

resource "dbtcloud_group" "protected_groups" {
  for_each = local.protected_groups_map

  name               = each.value.name
  assign_by_default  = try(each.value.assign_by_default, false)
  sso_mapping_groups = try(each.value.sso_mapping_groups, null)

  dynamic "group_permissions" {
    for_each = try(each.value.permissions, [])
    content {
      permission_set = group_permissions.value.permission_set
      project_id     = try(group_permissions.value.project_id, null)
      all_projects   = try(group_permissions.value.all_projects, group_permissions.value.project_id == null)
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
