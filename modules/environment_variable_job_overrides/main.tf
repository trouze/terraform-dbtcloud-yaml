terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  # Flatten env var job overrides from environment-nested jobs (legacy layout)
  overrides_from_env_jobs = flatten([
    for p in var.projects : [
      for env in try(p.environments, []) : [
        for job in try(env.jobs, []) : [
          for var_name, var_value in try(job.env_var_overrides, {}) : {
            project_key   = try(p.key, p.name)
            project_id    = var.project_ids[try(p.key, p.name)]
            job_key       = "${try(p.key, p.name)}_${env.name}_${job.name}"
            var_name      = var_name
            var_value     = var_value
            composite_key = "${try(p.key, p.name)}_${env.name}_${job.name}_${var_name}"
          }
        ]
      ] if try(env.jobs, null) != null
    ]
  ])

  # Flatten env var job overrides from project-level jobs (new layout)
  overrides_from_project_jobs = flatten([
    for p in var.projects : [
      for job in try(p.jobs, []) : [
        for var_name, var_value in try(job.env_var_overrides, {}) : {
          project_key   = try(p.key, p.name)
          project_id    = var.project_ids[try(p.key, p.name)]
          job_key       = "${try(p.key, p.name)}_${try(job.key, job.name)}"
          var_name      = var_name
          var_value     = var_value
          composite_key = "${try(p.key, p.name)}_${try(job.key, job.name)}_${var_name}"
        }
      ]
    ]
  ])

  all_overrides_map = {
    for item in concat(local.overrides_from_env_jobs, local.overrides_from_project_jobs) :
    item.composite_key => item
  }
}

resource "dbtcloud_environment_variable_job_override" "environment_variable_job_overrides" {
  for_each = local.all_overrides_map

  name              = each.value.var_name
  project_id        = each.value.project_id
  job_definition_id = lookup(var.job_ids, each.value.job_key, null)
  raw_value         = tostring(each.value.var_value)
}
