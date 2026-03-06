#############################################
# Jobs
# 
# Creates jobs for each project/environment combination.
# Handles cross-references (environments, notifications, deferral).
# Supports protected resources with lifecycle.prevent_destroy.
#############################################

locals {
  # Flatten all jobs across all projects
  # Jobs are at the project level with an environment_key field
  all_jobs = flatten([
    for project in var.projects : [
      for job in try(project.jobs, []) : {
        project_key     = project.key
        project_id      = local.project_id_lookup[project.key]
        environment_key = job.environment_key
        environment_id  = local.environment_id_lookup["${project.key}_${job.environment_key}"]
        job_key         = job.key
        job_data        = job
      }
    ] if try(project.jobs, null) != null
  ])

  # Helper to get environment_id from either protected or unprotected environments
  environment_id_lookup = merge(
    {
      for item in local.unprotected_environments :
      "${item.project_key}_${item.env_key}" => dbtcloud_environment.environments["${item.project_key}_${item.env_key}"].environment_id
    },
    {
      for item in local.protected_environments :
      "${item.project_key}_${item.env_key}" => dbtcloud_environment.protected_environments["${item.project_key}_${item.env_key}"].environment_id
    }
  )

  # Create map keyed by project_key_job_key
  jobs_map = {
    for item in local.all_jobs :
    "${item.project_key}_${item.job_key}" => item
  }

  #############################################
  # Protection: Split jobs into protected/unprotected
  #############################################

  # Protected jobs (protected: true in job_data)
  protected_jobs_map = {
    for key, item in local.jobs_map :
    key => item
    if try(item.job_data.protected, false) == true
  }

  # Unprotected jobs (protected: false or not set)
  unprotected_jobs_map = {
    for key, item in local.jobs_map :
    key => item
    if try(item.job_data.protected, false) != true
  }

  # Map of environment keys to environment IDs - resolves from either protected or unprotected
  # Reuses environment_id_lookup which already merges both resource blocks
  environment_id_by_key = local.environment_id_lookup

  # Helper to resolve deferring environment ID by key
  resolve_deferring_environment_id = {
    for key, item in local.jobs_map :
    key => (
      try(item.job_data.deferring_environment_key, null) != null ?
      lookup(
        local.environment_id_by_key,
        "${item.project_key}_${item.job_data.deferring_environment_key}",
        null
      ) : null
    )
  }

  # Note: deferring_job_id is intentionally not supported in this module.
  # It conflicts with deferring_environment_id and self_deferring.
  # Use deferring_environment_key in YAML for environment-based deferral,
  # or self_deferring for job self-deferral.

  # Merged deployment_type lookup - resolves from either protected or unprotected environments
  env_deployment_type_lookup = merge(
    {
      for key, env in dbtcloud_environment.environments :
      key => env.deployment_type
    },
    {
      for key, env in dbtcloud_environment.protected_environments :
      key => env.deployment_type
    }
  )

  # Validate run_compare_changes compatibility
  # State-aware orchestration (run_compare_changes) is only available for:
  # 1. Jobs on staging or production environments (deployment_type must be "staging" or "production")
  # Note: Terraform's coalesce() treats empty strings as invalid, so don't use it for null->"" normalization.
  env_deployment_type_by_job = {
    for key, item in local.jobs_map :
    key => try(
      local.env_deployment_type_lookup["${item.project_key}_${item.environment_key}"],
      null
    )
  }

  validate_run_compare_changes = {
    for key, item in local.jobs_map :
    key => (
      # Check if run_compare_changes is requested
      try(item.job_data.run_compare_changes, false) == true ?
      (
        # Check if environment is staging or production
        contains(
          ["staging", "production"],
          local.env_deployment_type_by_job[key] != null ? local.env_deployment_type_by_job[key] : ""
        ) &&
        # Must defer to a DIFFERENT environment (same-env deferral doesn't count for compare changes)
        (
          try(item.job_data.deferring_environment_key, null) != null &&
          item.job_data.deferring_environment_key != item.environment_key
        )
      ) : false
    )
  }

  # Note on deployment_type:
  # dbt Cloud allows only ONE environment per project to be "production" and ONE to be "staging".
  # All other deployment environments are "general" (deployment_type = null).
  # 
  # Jobs CAN be created on general environments, but SAO features (run_compare_changes,
  # cross-environment deferral) require staging or production deployment_type.
  # The validate_run_compare_changes logic below properly gates SAO features.
  #
  # We previously gated ALL job creation on deployment_type, but this was too restrictive.
  # Jobs on general environments are valid - they just can't use SAO.

  # Schedule field mutual exclusivity:
  # Provider enforces that schedule_cron cannot be combined with schedule_interval or schedule_hours.
  # Some source jobs include both, so we resolve to a single schedule mode (cron > interval > hours).
  schedule_cron_effective = {
    for key, item in local.jobs_map :
    key => (
      try(item.job_data.schedule_cron, null) != null && try(item.job_data.schedule_cron, "") != ""
      ? item.job_data.schedule_cron
      : null
    )
  }
  schedule_interval_effective = {
    for key, item in local.jobs_map :
    key => (
      local.schedule_cron_effective[key] == null
      ? try(item.job_data.schedule_interval, null)
      : null
    )
  }
  schedule_hours_effective = {
    for key, item in local.jobs_map :
    key => (
      local.schedule_cron_effective[key] == null && local.schedule_interval_effective[key] == null
      ? try(item.job_data.schedule_hours, null)
      : null
    )
  }

  # All jobs can be created - SAO features are gated separately by validate_run_compare_changes
  # Split into protected and unprotected for lifecycle management
  jobs_creatable_map           = local.unprotected_jobs_map
  protected_jobs_creatable_map = local.protected_jobs_map

  # SAO (State-Aware Orchestration) field handling
  # Detect CI/Merge jobs: force_node_selection must be omitted for these job types
  # as the dbt Cloud API rejects explicit values for CI/Merge jobs
  is_ci_or_merge_job = {
    for key, item in local.jobs_map :
    key => (
      try(item.job_data.triggers.github_webhook, false) == true ||
      try(item.job_data.triggers.git_provider_webhook, false) == true ||
      try(item.job_data.triggers.on_merge, false) == true ||
      contains(["ci", "merge"], try(item.job_data.job_type, "scheduled"))
    )
  }

  # force_node_selection: null for CI/Merge jobs, otherwise from cost_optimization_features or legacy force_node_selection
  # cost_optimization_features ["state_aware_orchestration"] = SAO on = force_node_selection false (same thing, different name)
  force_node_selection_effective = {
    for key, item in local.jobs_map :
    key => (
      local.is_ci_or_merge_job[key]
      ? null
      : (
        length(coalesce(try(item.job_data.cost_optimization_features, null), [])) > 0 && contains(coalesce(try(item.job_data.cost_optimization_features, null), []), "state_aware_orchestration")
        ? false
        : try(item.job_data.force_node_selection, null)
      )
    )
  }

  # compare_changes_flags is canonicalized by the API for CI/Merge jobs.
  # Normalize to the API-stable value to avoid provider "inconsistent result"
  # errors when the server strips "+" and "--exclude ..." suffixes.
  compare_changes_flags_effective = {
    for key, item in local.jobs_map :
    key => (
      local.is_ci_or_merge_job[key]
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

  # API only allows linting on CI jobs.
  run_lint_effective = {
    for key, item in local.jobs_map :
    key => (
      (
        try(item.job_data.triggers.git_provider_webhook, false) == true ||
        lower(trimspace(try(item.job_data.job_type, ""))) == "ci"
      )
      ? try(item.job_data.run_lint, false)
      : false
    )
  }

  # errors_on_lint_failure only applies when linting is active (CI jobs only).
  errors_on_lint_failure_effective = {
    for key, item in local.jobs_map :
    key => local.run_lint_effective[key] ? try(item.job_data.errors_on_lint_failure, false) : false
  }

}

#############################################
# Unprotected Jobs - standard lifecycle
#############################################
resource "dbtcloud_job" "jobs" {
  for_each = local.jobs_creatable_map

  depends_on = [
    dbtcloud_environment.environments,
    dbtcloud_environment.protected_environments,
    dbtcloud_environment_variable.environment_variables
  ]

  project_id     = each.value.project_id
  name           = each.value.job_data.name
  environment_id = each.value.environment_id
  execute_steps  = each.value.job_data.execute_steps
  triggers       = each.value.job_data.triggers

  # Optional fields
  description = try(each.value.job_data.description, null)
  dbt_version = try(each.value.job_data.dbt_version, null)
  # Deferring environment ID: Look up from the environment_id_lookup which handles both protected/unprotected
  deferring_environment_id = (
    try(each.value.job_data.deferring_environment_key, null) != null
  ) ? try(local.environment_id_lookup["${each.value.project_key}_${each.value.job_data.deferring_environment_key}"], null) : null
  errors_on_lint_failure = local.errors_on_lint_failure_effective[each.key]
  generate_docs          = try(each.value.job_data.generate_docs, false)
  is_active              = try(each.value.job_data.is_active, true)
  num_threads            = coalesce(try(each.value.job_data.num_threads, null), 4)
  # Only enable run_compare_changes if validation passes (staging/prod environment and not CI/Merge job)
  run_compare_changes = local.validate_run_compare_changes[each.key]
  # Always pass compare_changes_flags from YAML; the provider internally gates it
  # (only sends to API when run_compare_changes=true), so this is safe and avoids
  # perpetual "(known after apply)" diffs when run_compare_changes is false.
  compare_changes_flags = local.compare_changes_flags_effective[each.key]
  run_generate_sources  = try(each.value.job_data.run_generate_sources, false)
  run_lint              = local.run_lint_effective[each.key]
  schedule_cron         = local.schedule_cron_effective[each.key]
  schedule_days         = try(each.value.job_data.schedule_days, null)
  schedule_hours        = local.schedule_hours_effective[each.key]
  schedule_interval     = local.schedule_interval_effective[each.key]
  schedule_type         = try(each.value.job_data.schedule_type, null)
  target_name           = try(each.value.job_data.target_name, null)
  timeout_seconds       = try(each.value.job_data.timeout_seconds, 0)
  triggers_on_draft_pr  = try(each.value.job_data.triggers_on_draft_pr, false)
  # self_deferring conflicts with deferring_environment_id - only set when no environment deferral
  self_deferring = (
    try(each.value.job_data.deferring_environment_key, null) == null
  ) ? try(each.value.job_data.self_deferring, null) : null

  # SAO (State-Aware Orchestration): we map YAML cost_optimization_features to force_node_selection (same purpose)
  force_node_selection = local.force_node_selection_effective[each.key]

  resource_metadata = {
    source_project_id  = lookup(local.source_project_ids_by_key, each.value.project_key, null)
    source_id          = try(each.value.job_data.id, null)
    source_identity    = "JOB:${each.value.project_key}:${each.value.job_key}"
    source_key         = each.value.job_key
    source_project_key = each.value.project_key
    source_name        = each.value.job_data.name
  }

  lifecycle {
    ignore_changes = [
      job_completion_trigger_condition,
      # job_type is provider-computed and not configurable via this module;
      # ignoring prevents noisy "other -> (known after apply)" diffs.
      job_type,
    ]
  }
}

#############################################
# Protected Jobs - prevent_destroy lifecycle
#############################################
resource "dbtcloud_job" "protected_jobs" {
  for_each = local.protected_jobs_creatable_map

  depends_on = [
    dbtcloud_environment.environments,
    dbtcloud_environment.protected_environments,
    dbtcloud_environment_variable.environment_variables
  ]

  project_id     = each.value.project_id
  name           = each.value.job_data.name
  environment_id = each.value.environment_id
  execute_steps  = each.value.job_data.execute_steps
  triggers       = each.value.job_data.triggers

  # Optional fields
  description = try(each.value.job_data.description, null)
  dbt_version = try(each.value.job_data.dbt_version, null)
  # Deferring environment ID: Look up from the environment_id_lookup which handles both protected/unprotected
  deferring_environment_id = (
    try(each.value.job_data.deferring_environment_key, null) != null
  ) ? try(local.environment_id_lookup["${each.value.project_key}_${each.value.job_data.deferring_environment_key}"], null) : null
  errors_on_lint_failure = local.errors_on_lint_failure_effective[each.key]
  generate_docs          = try(each.value.job_data.generate_docs, false)
  is_active              = try(each.value.job_data.is_active, true)
  num_threads            = coalesce(try(each.value.job_data.num_threads, null), 4)
  # Only enable run_compare_changes if validation passes (staging/prod environment and not CI/Merge job)
  run_compare_changes = local.validate_run_compare_changes[each.key]
  # Always pass compare_changes_flags from YAML; the provider internally gates it
  # (only sends to API when run_compare_changes=true), so this is safe and avoids
  # perpetual "(known after apply)" diffs when run_compare_changes is false.
  compare_changes_flags = local.compare_changes_flags_effective[each.key]
  run_generate_sources  = try(each.value.job_data.run_generate_sources, false)
  run_lint              = local.run_lint_effective[each.key]
  schedule_cron         = local.schedule_cron_effective[each.key]
  schedule_days         = try(each.value.job_data.schedule_days, null)
  schedule_hours        = local.schedule_hours_effective[each.key]
  schedule_interval     = local.schedule_interval_effective[each.key]
  schedule_type         = try(each.value.job_data.schedule_type, null)
  target_name           = try(each.value.job_data.target_name, null)
  timeout_seconds       = try(each.value.job_data.timeout_seconds, 0)
  triggers_on_draft_pr  = try(each.value.job_data.triggers_on_draft_pr, false)
  # self_deferring conflicts with deferring_environment_id - only set when no environment deferral
  self_deferring = (
    try(each.value.job_data.deferring_environment_key, null) == null
  ) ? try(each.value.job_data.self_deferring, null) : null

  # SAO: same as jobs above (YAML cost_optimization_features mapped to force_node_selection)
  force_node_selection = local.force_node_selection_effective[each.key]

  resource_metadata = {
    source_project_id  = lookup(local.source_project_ids_by_key, each.value.project_key, null)
    source_id          = try(each.value.job_data.id, null)
    source_identity    = "JOB:${each.value.project_key}:${each.value.job_key}"
    source_key         = each.value.job_key
    source_project_key = each.value.project_key
    source_name        = each.value.job_data.name
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      job_completion_trigger_condition,
      job_type,
    ]
  }
}

# Note: Notification job associations are handled in globals.tf
# The dbtcloud_notification resource in globals.tf includes job IDs
# from the on_success, on_failure, etc. fields in the YAML.
# If jobs reference notifications via notification_keys, those associations
# should be included in the notification definition in the YAML.

