terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.8"
    }
  }
}

locals {
  groups_map = {
    for g in var.groups_data :
    g.key => g
  }

  groups_permissions_by_key = {
    for k, g in local.groups_map :
    k => try(g.group_permissions, [])
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
  sso_mapping_groups = try(each.value.sso_mapping_groups, [])

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/globals.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "GRP:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }

  dynamic "group_permissions" {
    for_each = var.skip_global_project_permissions ? [] : tolist(try(local.groups_permissions_by_key[each.key], []))
    content {
      permission_set                  = group_permissions.value.permission_set
      all_projects                    = try(group_permissions.value.all_projects, group_permissions.value.project_id == null)
      project_id                      = try(group_permissions.value.project_id, null)
      writable_environment_categories = try(group_permissions.value.writable_environment_categories, [])
    }
  }
  dynamic "group_permissions" {
    for_each = var.skip_global_project_permissions ? tolist(try(local.groups_permissions_by_key[each.key], [])) : []
    content {
      permission_set                  = group_permissions.value.permission_set
      all_projects                    = true
      project_id                      = null
      writable_environment_categories = try(group_permissions.value.writable_environment_categories, [])
    }
  }
}

resource "dbtcloud_group" "protected_groups" {
  for_each = local.protected_groups_map

  name               = each.value.name
  assign_by_default  = try(each.value.assign_by_default, false)
  sso_mapping_groups = try(each.value.sso_mapping_groups, [])

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/globals.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "GRP:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }

  dynamic "group_permissions" {
    for_each = var.skip_global_project_permissions ? [] : tolist(try(local.groups_permissions_by_key[each.key], []))
    content {
      permission_set                  = group_permissions.value.permission_set
      all_projects                    = try(group_permissions.value.all_projects, group_permissions.value.project_id == null)
      project_id                      = try(group_permissions.value.project_id, null)
      writable_environment_categories = try(group_permissions.value.writable_environment_categories, [])
    }
  }
  dynamic "group_permissions" {
    for_each = var.skip_global_project_permissions ? tolist(try(local.groups_permissions_by_key[each.key], [])) : []
    content {
      permission_set                  = group_permissions.value.permission_set
      all_projects                    = true
      project_id                      = null
      writable_environment_categories = try(group_permissions.value.writable_environment_categories, [])
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
