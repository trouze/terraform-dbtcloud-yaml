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
  # Mirror environments module: same project_key, env_key, composite_key, and display name.
  all_environments = flatten([
    for p in var.projects : [
      for env in try(p.environments, []) : {
        project_key   = try(p.key, p.name)
        env_key       = try(env.key, env.name)
        composite_key = "${try(p.key, p.name)}_${try(env.key, env.name)}"
        env_data      = env
      }
    ]
  ])

  # Resolve environment_values[].env (name or YAML key) -> composite_key, then -> dbt Cloud environment name (env_data.name).
  env_name_to_resource_key = merge(
    {
      for item in local.all_environments :
      "${item.project_key}_${item.env_data.name}" => item.composite_key
    },
    {
      for item in local.all_environments :
      "${item.project_key}_${item.env_key}" => item.composite_key
    }
  )

  env_display_name_by_composite_key = {
    for item in local.all_environments :
    item.composite_key => item.env_data.name
  }

  all_env_vars = flatten([
    for p in var.projects : [
      for ev in try(p.environment_variables, []) : {
        project_key   = try(p.key, p.name)
        project_id    = var.project_ids[try(p.key, p.name)]
        var_name      = ev.name
        composite_key = "${try(p.key, p.name)}_${ev.name}"
        ev_data       = ev
      }
    ]
  ])

  protected_env_var_items = [
    for item in local.all_env_vars :
    item
    if try(item.ev_data.protected, false) == true
  ]

  unprotected_env_var_items = [
    for item in local.all_env_vars :
    item
    if try(item.ev_data.protected, false) != true
  ]

  env_vars_map = {
    for item in local.unprotected_env_var_items :
    item.composite_key => item
  }

  protected_env_vars_map = {
    for item in local.protected_env_var_items :
    item.composite_key => item
  }
}

resource "dbtcloud_environment_variable" "environment_variables" {
  for_each = local.env_vars_map

  name       = each.value.ev_data.name
  project_id = each.value.project_id

  environment_values = {
    for item in each.value.ev_data.environment_values :
    (
      item.env == "project" ? "project" : (
        lookup(local.env_name_to_resource_key, "${each.value.project_key}_${item.env}", null) != null ?
        local.env_display_name_by_composite_key[local.env_name_to_resource_key["${each.value.project_key}_${item.env}"]] :
        item.env
      )
      ) => (
      startswith(tostring(item.value), "secret_") ?
      lookup(var.token_map, trimprefix(tostring(item.value), "secret_"), tostring(item.value)) :
      tostring(item.value)
    )
  }

  # Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_environment_variable (terraform providers schema).
  # resource_metadata = {
  #   source_project_id  = null # v2 importer: lookup(local.source_project_ids_by_key, each.value.project_key, null)
  #   source_id          = try(each.value.ev_data.id, null)
  #   source_identity    = "VAR:${each.value.project_key}:${each.value.var_name}"
  #   source_key         = each.value.var_name
  #   source_project_key = each.value.project_key
  #   source_name        = each.value.ev_data.name
  # }
}

resource "dbtcloud_environment_variable" "protected_environment_variables" {
  for_each = local.protected_env_vars_map

  name       = each.value.ev_data.name
  project_id = each.value.project_id

  environment_values = {
    for item in each.value.ev_data.environment_values :
    (
      item.env == "project" ? "project" : (
        lookup(local.env_name_to_resource_key, "${each.value.project_key}_${item.env}", null) != null ?
        local.env_display_name_by_composite_key[local.env_name_to_resource_key["${each.value.project_key}_${item.env}"]] :
        item.env
      )
      ) => (
      startswith(tostring(item.value), "secret_") ?
      lookup(var.token_map, trimprefix(tostring(item.value), "secret_"), tostring(item.value)) :
      tostring(item.value)
    )
  }

  # Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_environment_variable (terraform providers schema).
  # resource_metadata = {
  #   source_project_id  = null # v2 importer: lookup(local.source_project_ids_by_key, each.value.project_key, null)
  #   source_id          = try(each.value.ev_data.id, null)
  #   source_identity    = "VAR:${each.value.project_key}:${each.value.var_name}"
  #   source_key         = each.value.var_name
  #   source_project_key = each.value.project_key
  #   source_name        = each.value.ev_data.name
  # }

  lifecycle {
    prevent_destroy = true
  }
}
