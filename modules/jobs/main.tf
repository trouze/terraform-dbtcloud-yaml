terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  flattened_jobs = flatten([
    for env in var.environments_data : [
      for job in env.jobs : {
        environment_name = env.name
        job_name = job.name
        job_data = job
      }
    ] if try(env.jobs, null) != null
  ])

  jobs_map = {
    for item in local.flattened_jobs :
    "${item.environment_name}_${item.job_name}" => item.job_data
  }
}

resource "dbtcloud_job" "job" {
  for_each = local.jobs_map

  project_id     = var.project_id
  name           = split("_", each.key)[1]
  environment_id = lookup(var.environment_ids, split("_", each.key)[0], null)  # Look up the environment ID
  execute_steps  = each.value.execute_steps
  triggers       = each.value.triggers

  # Optional fields with lookup to default to null if not provided
  dbt_version                = lookup(each.value, "dbt_version", null)
  deferring_environment_id   = try(lookup(var.environment_ids, each.value.deferring_environment, null), null)
  deferring_job_id           = null # this is legacy anyway
  description                = lookup(each.value, "description", null)
  errors_on_lint_failure     = lookup(each.value, "errors_on_lint_failure", true)
  generate_docs              = lookup(each.value, "generate_docs", false)
  is_active                  = lookup(each.value, "is_active", true)
  num_threads                = lookup(each.value, "num_threads", 4)
  run_compare_changes        = lookup(each.value, "run_compare_changes", false)
  run_generate_sources       = lookup(each.value, "run_generate_sources", false)
  run_lint                   = lookup(each.value, "run_lint", false)
  schedule_cron              = lookup(each.value, "schedule_cron", null)
  schedule_days              = lookup(each.value, "schedule_days", null)
  schedule_hours             = lookup(each.value, "schedule_hours", null)
  schedule_interval          = lookup(each.value, "schedule_interval", null)
  schedule_type              = lookup(each.value, "schedule_type", null)
  target_name                = lookup(each.value, "target_name", null)
  timeout_seconds            = lookup(each.value, "timeout_seconds", 0)
  triggers_on_draft_pr       = lookup(each.value, "triggers_on_draft_pr", false)
}
