#############################################
# Jobs
# 
# Creates jobs for each project/environment combination.
# Handles cross-references (environments, notifications, deferral).
#############################################

locals {
  # Flatten all jobs across all projects
  # Jobs are at the project level with an environment_key field
  all_jobs = flatten([
    for project in var.projects : [
      for job in try(project.jobs, []) : {
        project_key     = project.key
        project_id      = dbtcloud_project.projects[project.key].id
        environment_key = job.environment_key
        environment_id  = dbtcloud_environment.environments["${project.key}_${job.environment_key}"].environment_id
        job_key         = job.key
        job_data        = job
      }
    ] if try(project.jobs, null) != null
  ])

  # Create map keyed by project_key_job_key
  jobs_map = {
    for item in local.all_jobs :
    "${item.project_key}_${item.job_key}" => item
  }

  # Helper to resolve deferring environment ID by key
  resolve_deferring_environment_id = {
    for key, item in local.jobs_map :
    key => (
      try(item.job_data.deferring_environment_key, null) != null ?
      lookup(
        {
          for env_item in local.all_environments :
          "${env_item.project_key}_${env_item.env_key}" => dbtcloud_environment.environments["${env_item.project_key}_${env_item.env_key}"].environment_id
        },
        "${item.project_key}_${item.job_data.deferring_environment_key}",
        null
      ) : null
    )
  }

  # Helper to resolve deferring job ID by key
  # Note: deferring_job_id cannot be resolved at plan time due to circular dependency.
  # If deferring_job_key is specified, deferring_job_id will be null initially.
  # Jobs with deferral should reference existing jobs by numeric ID, or deferral
  # can be configured after initial creation via Terraform update.
  resolve_deferring_job_id = {
    for key, item in local.jobs_map :
    key => null # Set to null - deferring_job_id requires job to exist first (circular dependency)
  }

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
        )
      ) : false
    )
  }

  # Gate job creation when deployment_type is not set on the target environment.
  # We intentionally do NOT infer deployment_type from the environment name:
  # deployment_type must come from the source snapshot/mapping.
  #
  # Runtime evidence: dbt Cloud job creation can return SAO-related 405s for jobs
  # targeting environments where deployment_type is null.
  env_has_deployment_type = {
    for key, item in local.jobs_map :
    key => (
      local.env_deployment_type_by_job[key] != null && local.env_deployment_type_by_job[key] != ""
    )
  }

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

  jobs_creatable_map = {
    for key, item in local.jobs_map :
    key => item
    if local.env_has_deployment_type[key]
  }

}

# Create jobs
resource "dbtcloud_job" "jobs" {
  for_each = local.jobs_creatable_map

  depends_on = [
    dbtcloud_environment.environments,
    dbtcloud_environment_variable.environment_variables
  ]

  project_id     = each.value.project_id
  name           = each.value.job_data.name
  environment_id = each.value.environment_id
  execute_steps  = each.value.job_data.execute_steps
  triggers       = each.value.job_data.triggers

  # Optional fields
  description              = try(each.value.job_data.description, null)
  dbt_version              = try(each.value.job_data.dbt_version, null)
  deferring_environment_id = local.resolve_deferring_environment_id[each.key]
  deferring_job_id         = local.resolve_deferring_job_id[each.key]
  errors_on_lint_failure   = try(each.value.job_data.errors_on_lint_failure, true)
  generate_docs            = try(each.value.job_data.generate_docs, false)
  is_active                = try(each.value.job_data.is_active, true)
  num_threads              = coalesce(try(each.value.job_data.num_threads, null), 4)
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
  self_deferring        = try(each.value.job_data.self_deferring, null)

  lifecycle {
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

