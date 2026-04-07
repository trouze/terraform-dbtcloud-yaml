# Unit tests for modules/environment_variables
# Run from modules/environment_variables/: terraform test

mock_provider "dbtcloud" {}

run "resolves_environment_key_to_display_name" {
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
          }
        ]
        environment_variables = [
          {
            name = "DBT_MY_VAR"
            environment_values = [
              { env = "prod", value = "from-key" }
            ]
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    token_map   = {}
  }

  assert {
    condition     = dbtcloud_environment_variable.environment_variables["analytics_DBT_MY_VAR"].environment_values["Production Display"] == "from-key"
    error_message = "env YAML key should resolve to environment display name for API map keys"
  }
}

run "protected_and_unprotected_split" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name = "Dev"
            key  = "dev"
            type = "development"
          }
        ]
        environment_variables = [
          {
            name               = "DBT_A"
            environment_values = [{ env = "project", value = "a" }]
            protected          = false
          },
          {
            name               = "DBT_B"
            environment_values = [{ env = "project", value = "b" }]
            protected          = true
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    token_map   = {}
  }

  assert {
    condition     = length(dbtcloud_environment_variable.environment_variables) == 1
    error_message = "Expected one unprotected environment variable"
  }

  assert {
    condition     = length(dbtcloud_environment_variable.protected_environment_variables) == 1
    error_message = "Expected one protected environment variable"
  }
}

run "secret_prefix_uses_token_map" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environment_variables = [
          {
            name = "DBT_SECRET_VAR"
            environment_values = [
              { env = "project", value = "secret_my_token_name" }
            ]
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    token_map = {
      "my_token_name" = "resolved-secret"
    }
  }

  assert {
    condition     = dbtcloud_environment_variable.environment_variables["analytics_DBT_SECRET_VAR"].environment_values["project"] == "resolved-secret"
    error_message = "secret_ prefix should strip and look up token_map (including keys with underscores)"
  }
}
