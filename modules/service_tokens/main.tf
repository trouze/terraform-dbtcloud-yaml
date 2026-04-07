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
  tokens_map = {
    for t in var.service_tokens_data :
    t.key => t
  }

  service_tokens_permissions_by_key = {
    for k, t in local.tokens_map :
    k => try(t.permissions, [])
  }

  protected_tokens_map = {
    for k, t in local.tokens_map :
    k => t
    if try(t.protected, false) == true
  }

  unprotected_tokens_map = {
    for k, t in local.tokens_map :
    k => t
    if try(t.protected, false) != true
  }
}

resource "dbtcloud_service_token" "service_tokens" {
  for_each = local.unprotected_tokens_map

  name  = each.value.name
  state = try(each.value.state, 1)

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/globals.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "TOK:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }

  dynamic "service_token_permissions" {
    for_each = var.skip_global_project_permissions ? [] : tolist(try(local.service_tokens_permissions_by_key[each.key], []))
    content {
      permission_set = service_token_permissions.value.permission_set
      all_projects = try(
        service_token_permissions.value.all_projects,
        try(service_token_permissions.value.project_key, null) == null &&
        try(service_token_permissions.value.project_id, null) == null,
      )
      project_id = (
        try(service_token_permissions.value.project_key, null) != null
        ? try(var.project_ids[service_token_permissions.value.project_key], null)
        : try(service_token_permissions.value.project_id, null)
      )
      writable_environment_categories = try(service_token_permissions.value.writable_environment_categories, [])
    }
  }

  dynamic "service_token_permissions" {
    for_each = var.skip_global_project_permissions ? tolist(try(local.service_tokens_permissions_by_key[each.key], [])) : []
    content {
      permission_set                  = service_token_permissions.value.permission_set
      all_projects                    = true
      project_id                      = null
      writable_environment_categories = try(service_token_permissions.value.writable_environment_categories, [])
    }
  }
}

resource "dbtcloud_service_token" "protected_service_tokens" {
  for_each = local.protected_tokens_map

  name  = each.value.name
  state = try(each.value.state, 1)

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/globals.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "TOK:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }

  dynamic "service_token_permissions" {
    for_each = var.skip_global_project_permissions ? [] : tolist(try(local.service_tokens_permissions_by_key[each.key], []))
    content {
      permission_set = service_token_permissions.value.permission_set
      all_projects = try(
        service_token_permissions.value.all_projects,
        try(service_token_permissions.value.project_key, null) == null &&
        try(service_token_permissions.value.project_id, null) == null,
      )
      project_id = (
        try(service_token_permissions.value.project_key, null) != null
        ? try(var.project_ids[service_token_permissions.value.project_key], null)
        : try(service_token_permissions.value.project_id, null)
      )
      writable_environment_categories = try(service_token_permissions.value.writable_environment_categories, [])
    }
  }

  dynamic "service_token_permissions" {
    for_each = var.skip_global_project_permissions ? tolist(try(local.service_tokens_permissions_by_key[each.key], [])) : []
    content {
      permission_set                  = service_token_permissions.value.permission_set
      all_projects                    = true
      project_id                      = null
      writable_environment_categories = try(service_token_permissions.value.writable_environment_categories, [])
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
