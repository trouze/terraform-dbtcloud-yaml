terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  tokens_map = {
    for t in var.service_tokens_data :
    try(t.key, t.name) => t
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

  name = each.value.name

  dynamic "service_token_permissions" {
    for_each = try(each.value.permissions, [])
    content {
      permission_set = service_token_permissions.value.permission_set
      project_id     = try(service_token_permissions.value.project_id, null)
      all_projects   = try(service_token_permissions.value.all_projects, service_token_permissions.value.project_id == null)
    }
  }
}

resource "dbtcloud_service_token" "protected_service_tokens" {
  for_each = local.protected_tokens_map

  name = each.value.name

  dynamic "service_token_permissions" {
    for_each = try(each.value.permissions, [])
    content {
      permission_set = service_token_permissions.value.permission_set
      project_id     = try(service_token_permissions.value.project_id, null)
      all_projects   = try(service_token_permissions.value.all_projects, service_token_permissions.value.project_id == null)
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
