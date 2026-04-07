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
  # Flatten all environments across all projects
  all_environments = flatten([
    for p in var.projects : [
      for env in try(p.environments, []) : {
        project_key   = try(p.key, p.name)
        project_id    = var.project_ids[try(p.key, p.name)]
        env_key       = try(env.key, env.name)
        composite_key = "${try(p.key, p.name)}_${try(env.key, env.name)}"
        env_data      = env
      }
    ]
  ])

  envs_map = {
    for item in local.all_environments :
    item.composite_key => item
  }

  # Prefer connection, then connection_key (schema documents connection_key; some configs use connection).
  env_connection_ref = {
    for k, item in local.envs_map :
    k => try(item.env_data.connection, null) != null ? item.env_data.connection : try(item.env_data.connection_key, null)
  }

  protected_envs_map = {
    for k, item in local.envs_map :
    k => item
    if try(item.env_data.protected, false) == true
  }

  unprotected_envs_map = {
    for k, item in local.envs_map :
    k => item
    if try(item.env_data.protected, false) != true
  }

  # Resolve credential_id: look up composite key in credential_ids map
  resolve_credential_id = {
    for k, item in local.envs_map :
    k => lookup(var.credential_ids, k, null)
  }

  # Resolve connection_id: global connection key, LOOKUP:… placeholder, or numeric id.
  resolve_connection_id = {
    for k, item in local.envs_map :
    k => (
      local.env_connection_ref[k] != null ?
      lookup(var.global_connection_ids, tostring(local.env_connection_ref[k]), null) != null ?
      lookup(var.global_connection_ids, tostring(local.env_connection_ref[k]), null) :
      try(tonumber(local.env_connection_ref[k]), null) :
      try(item.env_data.connection_id, null)
    )
  }

  # COMPAT(v1-schema): key-based lookup, then legacy id remap, then raw extended_attributes_id
  resolve_extended_attributes_id = {
    for k, item in local.envs_map :
    k => try(coalesce(
      try(item.env_data.extended_attributes_key, null) != null && try(item.env_data.extended_attributes_key, "") != "" ?
      lookup(var.extended_attribute_ids, "${item.project_key}_${item.env_data.extended_attributes_key}", null) : null,
      try(item.env_data.extended_attributes_id, null) != null ?
      lookup(var.extended_attribute_ids_by_source_id, tostring(item.env_data.extended_attributes_id), null) : null,
      try(tonumber(item.env_data.extended_attributes_id), null)
    ), null)
  }
}

#############################################
# Unprotected Environments
#############################################

resource "dbtcloud_environment" "environments" {
  for_each = local.unprotected_envs_map

  project_id    = each.value.project_id
  name          = each.value.env_data.name
  type          = each.value.env_data.type
  connection_id = local.resolve_connection_id[each.key]
  credential_id = local.resolve_credential_id[each.key]

  dbt_version                = try(each.value.env_data.dbt_version, null)
  enable_model_query_history = try(each.value.env_data.enable_model_query_history, null)
  custom_branch              = try(each.value.env_data.custom_branch, null)
  deployment_type            = try(each.value.env_data.deployment_type, null)
  use_custom_branch          = try(each.value.env_data.custom_branch, null) != null
  extended_attributes_id     = local.resolve_extended_attributes_id[each.key]
}

#############################################
# Protected Environments — lifecycle.prevent_destroy
#############################################

resource "dbtcloud_environment" "protected_environments" {
  for_each = local.protected_envs_map

  project_id    = each.value.project_id
  name          = each.value.env_data.name
  type          = each.value.env_data.type
  connection_id = local.resolve_connection_id[each.key]
  credential_id = local.resolve_credential_id[each.key]

  dbt_version                = try(each.value.env_data.dbt_version, null)
  enable_model_query_history = try(each.value.env_data.enable_model_query_history, null)
  custom_branch              = try(each.value.env_data.custom_branch, null)
  deployment_type            = try(each.value.env_data.deployment_type, null)
  use_custom_branch          = try(each.value.env_data.custom_branch, null) != null
  extended_attributes_id     = local.resolve_extended_attributes_id[each.key]

  lifecycle {
    prevent_destroy = true
  }
}
