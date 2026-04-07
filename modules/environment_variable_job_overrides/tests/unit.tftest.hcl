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
