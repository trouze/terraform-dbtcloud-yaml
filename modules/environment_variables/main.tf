terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  # Flatten all env vars across all projects
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

  env_vars_map = {
    for item in local.all_env_vars :
    item.composite_key => item
  }
}

resource "dbtcloud_environment_variable" "environment_variables" {
  for_each = local.env_vars_map

  name       = each.value.var_name
  project_id = each.value.project_id
  environment_values = {
    for item in each.value.ev_data.environment_values :
    item.env => (
      startswith(tostring(item.value), "secret_")
      ? lookup(var.token_map, join("_", slice(split("_", tostring(item.value)), 1, length(split("_", tostring(item.value))))), null)
      : tostring(item.value)
    )
  }
}
