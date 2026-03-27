terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  # Flatten all jobs across all projects.
  # Jobs can be at project level (job.environment_key) or nested under environments.
  # We support both layouts for backward compatibility.
  all_jobs_flat = flatten(concat(
    # Project-level jobs (new layout: project.jobs[].environment_key)
    [
      for p in var.projects : [
        for job in try(p.jobs, []) : {
          project_key     = try(p.key, p.name)
          project_id      = var.project_ids[try(p.key, p.name)]
          env_key         = try(job.environment_key, job.environment)
          composite_key   = "${try(p.key, p.name)}_${try(job.key, job.name)}"
          job_data        = job
        }
      ]
    ],
    # Environment-nested jobs (legacy v1 layout: project.environments[].jobs[])
    [
      for p in var.projects : [
        for env in try(p.environments, []) : [
          for job in try(env.jobs, []) : {
            project_key   = try(p.key, p.name)
            project_id    = var.project_ids[try(p.key, p.name)]
            env_key       = try(env.key, env.name)
            composite_key = "${try(p.key, p.name)}_${try(env.name, env.key)}_${job.name}"
            job_data      = job
          }
        ] if try(env.jobs, null) != null
      ]
    ]
  ))

  jobs_map = {
    for item in local.all_jobs_flat :
    item.composite_key => item
  }

  # Resolve environment ID per job
  resolve_environment_id = {
    for k, item in local.jobs_map :
    k => lookup(
      var.environment_ids,
      "${item.project_key}_${item.env_key}",
      null
    )
  }

  # Resolve deferring environment ID by key
  resolve_deferring_environment_id = {
    for k, item in local.jobs_map :
    k => (
      try(item.job_data.deferring_environment_key, null) != null ?
      lookup(
        var.environment_ids,
        "${item.project_key}_${item.job_data.deferring_environment_key}",
        null
      ) : null
    )
  }

  # Detect CI/Merge jobs — force_node_selection must be null for these
  is_ci_or_merge_job = {
    for k, item in local.jobs_map :
    k => (
      try(item.job_data.triggers.github_webhook, false) == true ||
      try(item.job_data.triggers.git_provider_webhook, false) == true ||
      try(item.job_data.triggers.on_merge, false) == true ||
      contains(["ci", "merge"], try(item.job_data.job_type, "scheduled"))
    )
  }

  # force_node_selection: null for CI/Merge, otherwise from YAML
  force_node_selection_effective = {
    for k, item in local.jobs_map :
    k => local.is_ci_or_merge_job[k] ? null : try(item.job_data.force_node_selection, null)
  }

  # Schedule mutual exclusivity: cron takes precedence, then interval, then hours
  schedule_cron_effective = {
    for k, item in local.jobs_map :
    k => (
      try(item.job_data.schedule_cron, null) != null && try(item.job_data.schedule_cron, "") != ""
      ? item.job_data.schedule_cron : null
    )
  }

  schedule_interval_effective = {
    for k, item in local.jobs_map :
    k => (
      local.schedule_cron_effective[k] == null
      ? try(item.job_data.schedule_interval, null)
      : null
    )
  }

  schedule_hours_effective = {
    for k, item in local.jobs_map :
    k => (
      local.schedule_cron_effective[k] == null && local.schedule_interval_effective[k] == null
      ? try(item.job_data.schedule_hours, null)
      : null
    )
  }

  # Protected/unprotected split
  protected_jobs_map = {
    for k, item in local.jobs_map :
    k => item
    if try(item.job_data.protected, false) == true
  }

  unprotected_jobs_map = {
    for k, item in local.jobs_map :
    k => item
    if try(item.job_data.protected, false) != true
  }
}

#############################################
# Unprotected Jobs
#############################################

resource "dbtcloud_job" "jobs" {
  for_each = local.unprotected_jobs_map

  project_id     = each.value.project_id
  environment_id = local.resolve_environment_id[each.key]
  name           = each.value.job_data.name
  execute_steps  = each.value.job_data.execute_steps
  triggers       = each.value.job_data.triggers

  dbt_version              = try(each.value.job_data.dbt_version, null)
  description              = try(each.value.job_data.description, null)
  errors_on_lint_failure   = try(each.value.job_data.errors_on_lint_failure, true)
  generate_docs            = try(each.value.job_data.generate_docs, false)
  is_active                = try(each.value.job_data.is_active, true)
  num_threads              = try(each.value.job_data.num_threads, 4)
  run_compare_changes      = try(each.value.job_data.run_compare_changes, false)
  run_generate_sources     = try(each.value.job_data.run_generate_sources, false)
  run_lint                 = try(each.value.job_data.run_lint, false)
  self_deferring           = try(each.value.job_data.self_deferring, null)
  target_name              = try(each.value.job_data.target_name, null)
  timeout_seconds          = try(each.value.job_data.timeout_seconds, 0)
  triggers_on_draft_pr     = try(each.value.job_data.triggers_on_draft_pr, false)
  force_node_selection     = local.force_node_selection_effective[each.key]
  deferring_environment_id = local.resolve_deferring_environment_id[each.key]

  schedule_cron     = local.schedule_cron_effective[each.key]
  schedule_days     = try(each.value.job_data.schedule_days, null)
  schedule_hours    = local.schedule_hours_effective[each.key]
  schedule_interval = local.schedule_interval_effective[each.key]
  schedule_type     = try(each.value.job_data.schedule_type, null)
}

#############################################
# Protected Jobs — lifecycle.prevent_destroy
#############################################

resource "dbtcloud_job" "protected_jobs" {
  for_each = local.protected_jobs_map

  project_id     = each.value.project_id
  environment_id = local.resolve_environment_id[each.key]
  name           = each.value.job_data.name
  execute_steps  = each.value.job_data.execute_steps
  triggers       = each.value.job_data.triggers

  dbt_version              = try(each.value.job_data.dbt_version, null)
  description              = try(each.value.job_data.description, null)
  errors_on_lint_failure   = try(each.value.job_data.errors_on_lint_failure, true)
  generate_docs            = try(each.value.job_data.generate_docs, false)
  is_active                = try(each.value.job_data.is_active, true)
  num_threads              = try(each.value.job_data.num_threads, 4)
  run_compare_changes      = try(each.value.job_data.run_compare_changes, false)
  run_generate_sources     = try(each.value.job_data.run_generate_sources, false)
  run_lint                 = try(each.value.job_data.run_lint, false)
  self_deferring           = try(each.value.job_data.self_deferring, null)
  target_name              = try(each.value.job_data.target_name, null)
  timeout_seconds          = try(each.value.job_data.timeout_seconds, 0)
  triggers_on_draft_pr     = try(each.value.job_data.triggers_on_draft_pr, false)
  force_node_selection     = local.force_node_selection_effective[each.key]
  deferring_environment_id = local.resolve_deferring_environment_id[each.key]

  schedule_cron     = local.schedule_cron_effective[each.key]
  schedule_days     = try(each.value.job_data.schedule_days, null)
  schedule_hours    = local.schedule_hours_effective[each.key]
  schedule_interval = local.schedule_interval_effective[each.key]
  schedule_type     = try(each.value.job_data.schedule_type, null)

  lifecycle {
    prevent_destroy = true
  }
}
