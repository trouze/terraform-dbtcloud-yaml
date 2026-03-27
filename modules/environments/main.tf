terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
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

  # Resolve connection_id: prefer connection key lookup (global connections),
  # fall back to direct numeric ID from YAML
  resolve_connection_id = {
    for k, item in local.envs_map :
    k => (
      try(item.env_data.connection, null) != null ?
      lookup(var.global_connection_ids, tostring(item.env_data.connection), null) != null ?
      lookup(var.global_connection_ids, tostring(item.env_data.connection), null) :
      try(tonumber(item.env_data.connection), null) :
      try(item.env_data.connection_id, null)
    )
  }

  # Resolve extended_attributes_id via key lookup
  resolve_extended_attributes_id = {
    for k, item in local.envs_map :
    k => (
      try(item.env_data.extended_attributes_key, null) != null ?
      lookup(var.extended_attribute_ids, "${item.project_key}_${item.env_data.extended_attributes_key}", null) :
      null
    )
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
