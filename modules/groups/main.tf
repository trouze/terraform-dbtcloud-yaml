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
    try(g.key, g.name) => g
  }

  # COMPAT(v1-schema): prefer group_permissions[] when non-empty, else legacy permissions[] — collapse when v2 schema is canonical.
  groups_permissions_by_key = {
    for k, g in local.groups_map :
    k => (
      length(try(g.group_permissions, [])) > 0 ? try(g.group_permissions, []) :
      try(g.permissions, [])
    )
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

  # v2 set resource_metadata on dbtcloud_group; stock provider has no such argument.
  groups_provenance = {
    for key, g in local.groups_map :
    key => {
      source_key      = key
      source_name     = g.name
      source_identity = "GRP:${key}"
      source_id       = try(g.id, null)
      protected       = try(g.protected, false)
    }
  }
}

resource "dbtcloud_group" "groups" {
  for_each = local.unprotected_groups_map

  name               = each.value.name
  assign_by_default  = try(each.value.assign_by_default, false)
  sso_mapping_groups = try(each.value.sso_mapping_groups, [])

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
