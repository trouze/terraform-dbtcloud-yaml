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

  # Map of environment keys to environment IDs (separate local for clarity)
  environment_id_by_key = {
    for env_item in local.all_environments :
    "${env_item.project_key}_${env_item.env_key}" => dbtcloud_environment.environments["${env_item.project_key}_${env_item.env_key}"].environment_id
  }

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

  # Validate run_compare_changes compatibility
  # State-aware orchestration (run_compare_changes) is only available for:
  # 1. Jobs on staging or production environments (deployment_type must be "staging" or "production")
  # Note: Terraform's coalesce() treats empty strings as invalid, so don't use it for null->"" normalization.
  env_deployment_type_by_job = {
    for key, item in local.jobs_map :
    key => try(
      dbtcloud_environment.environments["${item.project_key}_${item.environment_key}"].deployment_type,
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

  # force_node_selection: null for CI/Merge jobs, configured value otherwise
  # Note: This field is deprecated in favor of cost_optimization_features
  force_node_selection_effective = {
    for key, item in local.jobs_map :
    key => local.is_ci_or_merge_job[key] ? null : try(item.job_data.force_node_selection, null)
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
  errors_on_lint_failure = try(each.value.job_data.errors_on_lint_failure, true)
  generate_docs          = try(each.value.job_data.generate_docs, false)
  is_active              = try(each.value.job_data.is_active, true)
  num_threads            = coalesce(try(each.value.job_data.num_threads, null), 4)
  # Only enable run_compare_changes if validation passes (staging/prod environment and not CI/Merge job)
  run_compare_changes = local.validate_run_compare_changes[each.key]
  # Use null for compare_changes_flags if validation fails - empty string still triggers SAO validation
  compare_changes_flags = local.validate_run_compare_changes[each.key] ? try(each.value.job_data.compare_changes_flags, "--select state:modified") : null
  run_generate_sources  = try(each.value.job_data.run_generate_sources, false)
  run_lint              = try(each.value.job_data.run_lint, false)
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

  # SAO (State-Aware Orchestration) fields
  # force_node_selection: Controls SAO. null for CI/Merge jobs (API rejects explicit values)
  # Deprecated in favor of cost_optimization_features
  force_node_selection = local.force_node_selection_effective[each.key]
  # cost_optimization_features: New preferred method for SAO control
  # Include "state_aware_orchestration" to enable SAO (requires dbt_version="latest-fusion")
  cost_optimization_features = try(each.value.job_data.cost_optimization_features, null)

  lifecycle {
    ignore_changes = [
      job_completion_trigger_condition
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
  errors_on_lint_failure = try(each.value.job_data.errors_on_lint_failure, true)
  generate_docs          = try(each.value.job_data.generate_docs, false)
  is_active              = try(each.value.job_data.is_active, true)
  num_threads            = coalesce(try(each.value.job_data.num_threads, null), 4)
  # Only enable run_compare_changes if validation passes (staging/prod environment and not CI/Merge job)
  run_compare_changes = local.validate_run_compare_changes[each.key]
  # Use null for compare_changes_flags if validation fails - empty string still triggers SAO validation
  compare_changes_flags = local.validate_run_compare_changes[each.key] ? try(each.value.job_data.compare_changes_flags, "--select state:modified") : null
  run_generate_sources  = try(each.value.job_data.run_generate_sources, false)
  run_lint              = try(each.value.job_data.run_lint, false)
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

  # SAO (State-Aware Orchestration) fields
  force_node_selection       = local.force_node_selection_effective[each.key]
  cost_optimization_features = try(each.value.job_data.cost_optimization_features, null)

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      job_completion_trigger_condition
    ]
  }
}

# Note: Notification job associations are handled in globals.tf
# The dbtcloud_notification resource in globals.tf includes job IDs
# from the on_success, on_failure, etc. fields in the YAML.
# If jobs reference notifications via notification_keys, those associations
# should be included in the notification definition in the YAML.

