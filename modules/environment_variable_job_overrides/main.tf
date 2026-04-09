terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.9"
    }
  }
}

locals {
  overrides_from_project_jobs = flatten([
    for p in var.projects : [
      for job in try(p.jobs, []) : [
        for var_name, var_value in try(job.environment_variable_overrides, {}) : {
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
    for item in local.overrides_from_project_jobs :
    item.composite_key => item
  }
}

resource "dbtcloud_environment_variable_job_override" "environment_variable_job_overrides" {
  for_each = local.all_overrides_map

  name              = each.value.var_name
  project_id        = each.value.project_id
  job_definition_id = lookup(var.job_ids, each.value.job_key, null)
  raw_value = (
    startswith(tostring(each.value.var_value), "secret_") ?
    lookup(var.token_map, trimprefix(tostring(each.value.var_value), "secret_"), tostring(each.value.var_value)) :
    tostring(each.value.var_value)
  )

  # Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_environment_variable_job_override (terraform providers schema).
  # resource_metadata = {
  #   source_project_id  = null # v2 importer: lookup(local.source_project_ids_by_key, each.value.project_key, null)
  #   source_id          = null
  #   source_identity    = "VAR_JOB_OVERRIDE:${each.value.project_key}:${each.value.job_key}:${each.value.var_name}"
  #   source_key         = each.value.var_name
  #   source_project_key = each.value.project_key
  #   source_name        = each.value.var_name
  # }
}
