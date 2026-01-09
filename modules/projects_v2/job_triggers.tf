locals {
  # Filter jobs that have trigger conditions
  # The normalizer outputs job_completion_trigger_condition as:
  # {
  #   "job_key": "upstream_job_key",
  #   "statuses": ["success", "error", ...]
  # }
  # for intra-project triggers.
  job_triggers = flatten([
    for key, item in local.jobs_creatable_map : [
      for cond in [try(item.job_data.job_completion_trigger_condition, null)] : {
        key            = key
        job_key        = item.job_key
        project_key    = item.project_key
        project_id     = item.project_id
        condition      = cond
        upstream_job_key = try(cond.job_key, null)
      }
      if cond != null && try(cond.job_key, null) != null
    ]
  ])
}

resource "dbtcloud_job_completion_trigger" "job_triggers" {
  for_each = {
    for item in local.job_triggers :
    item.key => item
    # Ensure the upstream job exists in the jobs map and is being created
    if contains(keys(dbtcloud_job.jobs), "${item.project_key}_${item.upstream_job_key}")
  }

  # Downstream job (the one being triggered)
  job_id = tonumber(dbtcloud_job.jobs[each.key].id)

  # Upstream job (the trigger)
  trigger_job_id = tonumber(dbtcloud_job.jobs["${each.value.project_key}_${each.value.upstream_job_key}"].id)

  # Project ID (same for both in intra-project chaining)
  project_id = each.value.project_id

  statuses = each.value.condition.statuses
}

