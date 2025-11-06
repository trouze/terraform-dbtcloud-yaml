terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  flattened_overrides = flatten([
    for env in var.environments_data : [
      for job in env.jobs : [
        for var_name, var_value in try(job.env_var_overrides, {}) : {
          job_key = "${env.name}_${job.name}"
          var_name = var_name
          var_value = var_value
        }
      ] if try(job.env_var_overrides, null) != null
    ] if try(env.jobs, null) != null
  ])

  env_var_map = {
    for item in local.flattened_overrides : "${item.job_key}_${item.var_name}" => {
      job_key = item.job_key
      var_name = item.var_name
      var_value = item.var_value
    }
  }
}

resource "dbtcloud_environment_variable_job_override" "environment_variable_job_overrides" {
  for_each = local.env_var_map
  
  name = each.value.var_name
  project_id = var.project_id
  job_definition_id = lookup(var.job_ids, each.value.job_key, null)
  raw_value = each.value.var_value
}
