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
  # Project-level jobs only (project.jobs[].environment_key).
  all_jobs_flat = flatten([
    for p in var.projects : [
      for job in try(p.jobs, []) : {
        project_key   = try(p.key, p.name)
        project_id    = var.project_ids[try(p.key, p.name)]
        env_key       = job.environment_key
        composite_key = "${try(p.key, p.name)}_${try(job.key, job.name)}"
        job_key       = try(job.key, job.name)
        job_data      = job
      }
    ]
  ])

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

  # deployment_type from environments module (SAO / run_compare_changes validation)
  env_deployment_type_by_job = {
    for k, item in local.jobs_map :
    k => try(var.deployment_types["${item.project_key}_${item.env_key}"], null)
  }

  # State-aware orchestration: run_compare_changes only when env is staging/production
  # and job defers to a different environment (v2/importer parity).
  validate_run_compare_changes = {
    for k, item in local.jobs_map :
    k => (
      try(item.job_data.run_compare_changes, false) == true ?
      (
        contains(
          ["staging", "production"],
          local.env_deployment_type_by_job[k] != null ? local.env_deployment_type_by_job[k] : ""
        ) &&
        (
          try(item.job_data.deferring_environment_key, null) != null &&
          item.job_data.deferring_environment_key != item.env_key
        )
      ) : false
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

  # COMPAT(v1-schema): cost_optimization_features ["state_aware_orchestration"] => force_node_selection false (v2/importer)
  force_node_selection_effective = {
    for k, item in local.jobs_map :
    k => (
      local.is_ci_or_merge_job[k]
      ? null
      : (
        length(coalesce(try(item.job_data.cost_optimization_features, null), [])) > 0 && contains(coalesce(try(item.job_data.cost_optimization_features, null), []), "state_aware_orchestration")
        ? false
        : try(item.job_data.force_node_selection, null)
      )
    )
  }

  # API canonicalizes compare_changes_flags for CI/Merge; normalize to avoid inconsistent results after apply.
  compare_changes_flags_effective = {
    for k, item in local.jobs_map :
    k => (
      local.is_ci_or_merge_job[k]
      ? "--select state:modified"
      : (
        try(item.job_data.compare_changes_flags, null) == null ||
        try(item.job_data.compare_changes_flags, null) == false ||
        lower(trimspace(try(tostring(item.job_data.compare_changes_flags), ""))) == "false" ||
        trimspace(try(tostring(item.job_data.compare_changes_flags), "")) == ""
        ? "--select state:modified"
        : trimspace(try(tostring(item.job_data.compare_changes_flags), "--select state:modified"))
      )
    )
  }

  # API only allows linting on CI jobs (git_provider_webhook or job_type ci).
  run_lint_effective = {
    for k, item in local.jobs_map :
    k => (
      (
        try(item.job_data.triggers.git_provider_webhook, false) == true ||
        lower(trimspace(try(tostring(item.job_data.job_type), ""))) == "ci"
      )
      ? try(item.job_data.run_lint, false)
      : false
    )
  }

  errors_on_lint_failure_effective = {
    for k, item in local.jobs_map :
    k => local.run_lint_effective[k] ? try(item.job_data.errors_on_lint_failure, false) : false
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

  dbt_version            = try(each.value.job_data.dbt_version, null)
  description            = try(each.value.job_data.description, null)
  errors_on_lint_failure = local.errors_on_lint_failure_effective[each.key]
  generate_docs          = try(each.value.job_data.generate_docs, false)
  is_active              = try(each.value.job_data.is_active, true)
  num_threads            = coalesce(try(each.value.job_data.num_threads, null), 4)
  run_compare_changes    = local.validate_run_compare_changes[each.key]
  compare_changes_flags  = local.compare_changes_flags_effective[each.key]
  run_generate_sources   = try(each.value.job_data.run_generate_sources, false)
  run_lint               = local.run_lint_effective[each.key]
  self_deferring = (
    try(each.value.job_data.deferring_environment_key, null) == null
  ) ? try(each.value.job_data.self_deferring, null) : null
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

  # Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_job (terraform providers schema).
  # resource_metadata = {
  #   source_project_id  = null # v2 importer: lookup(local.source_project_ids_by_key, each.value.project_key, null)
  #   source_id          = try(each.value.job_data.id, null)
  #   source_identity    = "JOB:${each.value.project_key}:${each.value.job_key}"
  #   source_key         = each.value.job_key
  #   source_project_key = each.value.project_key
  #   source_name        = each.value.job_data.name
  # }

  lifecycle {
    ignore_changes = [
      job_completion_trigger_condition,
      job_type,
    ]
  }
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

  dbt_version            = try(each.value.job_data.dbt_version, null)
  description            = try(each.value.job_data.description, null)
  errors_on_lint_failure = local.errors_on_lint_failure_effective[each.key]
  generate_docs          = try(each.value.job_data.generate_docs, false)
  is_active              = try(each.value.job_data.is_active, true)
  num_threads            = coalesce(try(each.value.job_data.num_threads, null), 4)
  run_compare_changes    = local.validate_run_compare_changes[each.key]
  compare_changes_flags  = local.compare_changes_flags_effective[each.key]
  run_generate_sources   = try(each.value.job_data.run_generate_sources, false)
  run_lint               = local.run_lint_effective[each.key]
  self_deferring = (
    try(each.value.job_data.deferring_environment_key, null) == null
  ) ? try(each.value.job_data.self_deferring, null) : null
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

  # Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_job (terraform providers schema).
  # resource_metadata = {
  #   source_project_id  = null # v2 importer: lookup(local.source_project_ids_by_key, each.value.project_key, null)
  #   source_id          = try(each.value.job_data.id, null)
  #   source_identity    = "JOB:${each.value.project_key}:${each.value.job_key}"
  #   source_key         = each.value.job_key
  #   source_project_key = each.value.project_key
  #   source_name        = each.value.job_data.name
  # }

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      job_completion_trigger_condition,
      job_type,
    ]
  }
}
