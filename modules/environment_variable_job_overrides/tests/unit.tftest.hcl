# Unit tests for modules/environment_variable_job_overrides
# Run from modules/environment_variable_job_overrides/: terraform test

mock_provider "dbtcloud" {}

run "v2_environment_variable_overrides_on_project_job" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name            = "Daily"
            key             = "daily"
            environment_key = "dev"
            environment_variable_overrides = {
              DBT_OVERRIDE = "v2-value"
            }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    job_ids = {
      "analytics_daily" = "5001"
    }
    token_map = {}
  }

  assert {
    condition     = dbtcloud_environment_variable_job_override.environment_variable_job_overrides["analytics_daily_DBT_OVERRIDE"].raw_value == "v2-value"
    error_message = "environment_variable_overrides should create job override with expected raw_value"
  }
}

run "merge_prefers_environment_variable_overrides_on_duplicate_keys" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name            = "Daily"
            key             = "daily"
            environment_key = "dev"
            env_var_overrides = {
              DBT_SAME = "legacy"
            }
            environment_variable_overrides = {
              DBT_SAME = "v2-wins"
            }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    job_ids = {
      "analytics_daily" = "5001"
    }
    token_map = {}
  }

  assert {
    condition     = dbtcloud_environment_variable_job_override.environment_variable_job_overrides["analytics_daily_DBT_SAME"].raw_value == "v2-wins"
    error_message = "environment_variable_overrides should win over env_var_overrides for the same key"
  }
}

run "secret_prefix_uses_token_map" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        jobs = [
          {
            name            = "Daily"
            key             = "daily"
            environment_key = "dev"
            environment_variable_overrides = {
              DBT_SECRET = "secret_my_job_token"
            }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    job_ids = {
      "analytics_daily" = "5001"
    }
    token_map = {
      "my_job_token" = "resolved"
    }
  }

  assert {
    condition     = dbtcloud_environment_variable_job_override.environment_variable_job_overrides["analytics_daily_DBT_SECRET"].raw_value == "resolved"
    error_message = "secret_ prefix should strip and resolve token_map (including underscores in key)"
  }
}

run "nested_job_job_key_matches_jobs_module" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name = "Production Display"
            key  = "prod"
            type = "deployment"
            jobs = [
              {
                name = "Nested Run"
                environment_variable_overrides = {
                  DBT_N = "1"
                }
              }
            ]
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    job_ids = {
      "analytics_Production Display_Nested Run" = "6001"
    }
    token_map = {}
  }

  assert {
    condition     = dbtcloud_environment_variable_job_override.environment_variable_job_overrides["analytics_Production Display_Nested Run_DBT_N"].raw_value == "1"
    error_message = "nested layout must use job_key analytics_Production Display_Nested Run (try(env.name, env.key) + job.name) to match modules/jobs"
  }
}
