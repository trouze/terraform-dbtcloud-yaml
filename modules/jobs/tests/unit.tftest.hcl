# Unit tests for modules/jobs
# Validates dual layout support, composite key construction, environment ID
# resolution, CI job detection, schedule mutual exclusivity, and protected jobs.
# Run from modules/jobs/: terraform test

mock_provider "dbtcloud" {}

# ── Project-level job layout (new style) ─────────────────────────────────────

run "project_level_job_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name            = "Daily Run"
            key             = "daily_run"
            environment_key = "prod"
            execute_steps   = ["dbt build"]
            triggers = {
              schedule             = false
              github_webhook       = false
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids     = { analytics = "1001" }
    environment_ids = { analytics_prod = "2001" }
  }

  assert {
    condition     = length(dbtcloud_job.jobs) == 1
    error_message = "Expected one job from project-level layout"
  }

  assert {
    condition     = contains(keys(dbtcloud_job.jobs), "analytics_daily_run")
    error_message = "Expected composite key 'analytics_daily_run'"
  }

  assert {
    condition     = dbtcloud_job.jobs["analytics_daily_run"].name == "Daily Run"
    error_message = "Job name should match YAML"
  }
}

run "project_level_job_environment_id_resolved" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name            = "Daily Run"
            key             = "daily_run"
            environment_key = "prod"
            execute_steps   = ["dbt build"]
            triggers = {
              schedule             = false
              github_webhook       = false
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids     = { analytics = "1001" }
    environment_ids = { analytics_prod = "2001" }
  }

  assert {
    condition     = dbtcloud_job.jobs["analytics_daily_run"].environment_id != null
    error_message = "Job environment_id should be looked up from environment_ids map (not null)"
  }
}

# ── Legacy nested job layout ──────────────────────────────────────────────────

run "legacy_nested_job_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name = "Production"
            key  = "prod"
            jobs = [
              {
                name          = "Legacy Job"
                execute_steps = ["dbt run"]
                triggers = {
                  schedule             = false
                  github_webhook       = false
                  git_provider_webhook = false
                  on_merge             = false
                }
              }
            ]
          }
        ]
      }
    ]
    project_ids     = { analytics = "1001" }
    environment_ids = { analytics_prod = "2001" }
  }

  assert {
    condition     = length(dbtcloud_job.jobs) == 1
    error_message = "Expected one job from legacy nested layout"
  }

  assert {
    # Legacy layout uses env.name (not env.key): "${project_key}_${env.name}_${job.name}"
    condition     = contains(keys(dbtcloud_job.jobs), "analytics_Production_Legacy Job")
    error_message = "Legacy layout composite key should be project_envname_jobname"
  }
}

# ── CI job detection and force_node_selection ─────────────────────────────────

run "ci_job_github_webhook_clears_force_node_selection" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name                 = "CI Check"
            key                  = "ci_check"
            environment_key      = "prod"
            execute_steps        = ["dbt build --select state:modified+"]
            force_node_selection = "state:modified+"
            triggers = {
              schedule             = false
              github_webhook       = true
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids     = { analytics = "1001" }
    environment_ids = { analytics_prod = "2001" }
  }

  assert {
    # Module sets force_node_selection = null for CI jobs; mock provider returns false for unset bools
    condition     = dbtcloud_job.jobs["analytics_ci_check"].force_node_selection == null || dbtcloud_job.jobs["analytics_ci_check"].force_node_selection == false
    error_message = "CI jobs triggered by github_webhook should have force_node_selection cleared (null/false)"
  }
}

run "scheduled_job_retains_force_node_selection" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name                 = "Daily Run"
            key                  = "daily_run"
            environment_key      = "prod"
            execute_steps        = ["dbt build"]
            force_node_selection = true
            triggers = {
              schedule             = false
              github_webhook       = false
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids     = { analytics = "1001" }
    environment_ids = { analytics_prod = "2001" }
  }

  assert {
    condition     = dbtcloud_job.jobs["analytics_daily_run"].force_node_selection == true
    error_message = "Non-CI jobs should retain force_node_selection value"
  }
}

# ── Schedule mutual exclusivity ───────────────────────────────────────────────

run "cron_takes_precedence_over_interval" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name              = "Daily Run"
            key               = "daily_run"
            environment_key   = "prod"
            execute_steps     = ["dbt build"]
            schedule_cron     = "0 6 * * 1-5"
            schedule_interval = 2
            triggers = {
              schedule             = false
              github_webhook       = false
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids     = { analytics = "1001" }
    environment_ids = { analytics_prod = "2001" }
  }

  assert {
    condition     = dbtcloud_job.jobs["analytics_daily_run"].schedule_cron == "0 6 * * 1-5"
    error_message = "schedule_cron should be set when provided"
  }

  assert {
    # Mock provider returns 0 for unset numeric attributes; either value means "not scheduled by interval"
    condition     = dbtcloud_job.jobs["analytics_daily_run"].schedule_interval == null || dbtcloud_job.jobs["analytics_daily_run"].schedule_interval == 0
    error_message = "schedule_interval should be null/0 when schedule_cron is set"
  }
}

# ── Protected jobs ────────────────────────────────────────────────────────────

run "protected_job_routed_to_protected_resource" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name            = "Production Run"
            key             = "prod_run"
            environment_key = "prod"
            execute_steps   = ["dbt build"]
            protected       = true
            triggers = {
              schedule             = false
              github_webhook       = false
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids     = { analytics = "1001" }
    environment_ids = { analytics_prod = "2001" }
  }

  assert {
    condition     = length(dbtcloud_job.protected_jobs) == 1
    error_message = "Protected job should be in protected_jobs resource"
  }

  assert {
    condition     = length(dbtcloud_job.jobs) == 0
    error_message = "Protected job should NOT be in unprotected jobs resource"
  }
}

# ── Deferring environment resolution ─────────────────────────────────────────

run "cost_optimization_state_aware_sets_force_node_false" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name                       = "SAO Run"
            key                        = "sao_run"
            environment_key            = "prod"
            execute_steps              = ["dbt build"]
            force_node_selection       = true
            cost_optimization_features = ["state_aware_orchestration"]
            triggers = {
              schedule             = false
              github_webhook       = false
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids     = { analytics = "1001" }
    environment_ids = { analytics_prod = "2001" }
  }

  assert {
    condition     = dbtcloud_job.jobs["analytics_sao_run"].force_node_selection == false
    error_message = "state_aware_orchestration in cost_optimization_features should set force_node_selection to false"
  }
}

run "run_compare_changes_true_when_staging_and_cross_env_defer" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name                      = "Compare Run"
            key                       = "compare_run"
            environment_key           = "prod"
            deferring_environment_key = "staging"
            run_compare_changes       = true
            execute_steps             = ["dbt build"]
            triggers = {
              schedule             = false
              github_webhook       = false
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids      = { analytics = "1001" }
    environment_ids  = { analytics_prod = "2001", analytics_staging = "2002" }
    deployment_types = { analytics_prod = "staging" }
  }

  assert {
    condition     = dbtcloud_job.jobs["analytics_compare_run"].run_compare_changes == true
    error_message = "run_compare_changes should be true when job env is staging/production and deferral is a different environment"
  }
}

run "run_compare_changes_false_when_not_eligible" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name                      = "No Compare"
            key                       = "no_compare"
            environment_key           = "prod"
            deferring_environment_key = "staging"
            run_compare_changes       = true
            execute_steps             = ["dbt build"]
            triggers = {
              schedule             = false
              github_webhook       = false
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids      = { analytics = "1001" }
    environment_ids  = { analytics_prod = "2001", analytics_staging = "2002" }
    deployment_types = { analytics_prod = "other" }
  }

  assert {
    condition     = dbtcloud_job.jobs["analytics_no_compare"].run_compare_changes == false
    error_message = "run_compare_changes should be false when deployment_type is not staging or production"
  }
}

run "deferring_environment_id_resolved" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name                      = "CI Check"
            key                       = "ci_check"
            environment_key           = "prod"
            deferring_environment_key = "prod"
            execute_steps             = ["dbt build --select state:modified+"]
            triggers = {
              schedule             = false
              github_webhook       = true
              git_provider_webhook = false
              on_merge             = false
            }
          }
        ]
      }
    ]
    project_ids     = { analytics = "1001" }
    environment_ids = { analytics_prod = "2001" }
  }

  assert {
    condition     = dbtcloud_job.jobs["analytics_ci_check"].deferring_environment_id != null
    error_message = "deferring_environment_id should be resolved from environment_ids map (not null)"
  }
}
