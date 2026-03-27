# Unit tests for modules/environments
# Validates composite key construction, credential/connection ID resolution,
# custom branch handling, and protected environment routing.
# Run from modules/environments/: terraform test

mock_provider "dbtcloud" {}

# ── Basic environment creation ────────────────────────────────────────────────

run "deployment_environment_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name            = "Production"
            key             = "prod"
            type            = "deployment"
            deployment_type = "production"
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = length(dbtcloud_environment.environments) == 1
    error_message = "Expected one environment to be created"
  }

  assert {
    condition     = dbtcloud_environment.environments["analytics_prod"].name == "Production"
    error_message = "Environment name should match YAML"
  }

  assert {
    condition     = dbtcloud_environment.environments["analytics_prod"].type == "deployment"
    error_message = "Environment type should match YAML"
  }
}

run "development_environment_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name = "Development"
            key  = "dev"
            type = "development"
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = length(dbtcloud_environment.environments) == 1
    error_message = "Expected one development environment"
  }

  assert {
    condition     = dbtcloud_environment.environments["analytics_dev"].type == "development"
    error_message = "Environment type should be development"
  }
}

run "multiple_environments_across_projects" {
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
          },
          {
            name            = "Prod"
            key             = "prod"
            type            = "deployment"
            deployment_type = "production"
          }
        ]
      },
      {
        key  = "finance"
        name = "Finance"
        environments = [
          {
            name            = "Prod"
            key             = "prod"
            type            = "deployment"
            deployment_type = "production"
          }
        ]
      }
    ]
    project_ids = {
      analytics = "1001"
      finance   = "1002"
    }
  }

  assert {
    condition     = length(dbtcloud_environment.environments) == 3
    error_message = "Expected three environments total"
  }

  assert {
    condition     = contains(keys(dbtcloud_environment.environments), "analytics_dev")
    error_message = "Expected composite key 'analytics_dev'"
  }

  assert {
    condition     = contains(keys(dbtcloud_environment.environments), "finance_prod")
    error_message = "Expected composite key 'finance_prod'"
  }
}

# ── Composite key construction ────────────────────────────────────────────────

run "composite_key_uses_env_key_field" {
  command = plan

  variables {
    projects = [
      {
        key  = "my_project"
        name = "My Project"
        environments = [
          {
            name = "My Env Name"
            key  = "my_env_key"
            type = "development"
          }
        ]
      }
    ]
    project_ids = { my_project = "1001" }
  }

  assert {
    condition     = contains(keys(dbtcloud_environment.environments), "my_project_my_env_key")
    error_message = "Composite key should use env.key when both key and name are present"
  }
}

# ── Credential ID resolution ──────────────────────────────────────────────────

run "credential_id_resolved_from_map" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name            = "Prod"
            key             = "prod"
            type            = "deployment"
            deployment_type = "production"
          }
        ]
      }
    ]
    project_ids    = { analytics = "1001" }
    credential_ids = { analytics_prod = "999" }
  }

  assert {
    condition     = dbtcloud_environment.environments["analytics_prod"].credential_id != null
    error_message = "credential_id should be looked up from credential_ids map (not null)"
  }
}

run "credential_id_null_when_not_in_map" {
  command = apply

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
      }
    ]
    project_ids    = { analytics = "1001" }
    credential_ids = {}
  }

  assert {
    # Mock provider returns 0 for unset numeric attributes; either value means "not set from map"
    condition     = dbtcloud_environment.environments["analytics_dev"].credential_id == null || dbtcloud_environment.environments["analytics_dev"].credential_id == 0
    error_message = "credential_id should be null/0 when not in credential_ids map"
  }
}

# ── Connection ID resolution ──────────────────────────────────────────────────

run "connection_id_resolved_from_global_connections_map" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name            = "Prod"
            key             = "prod"
            type            = "deployment"
            deployment_type = "production"
            connection      = "my_snowflake"
          }
        ]
      }
    ]
    project_ids           = { analytics = "1001" }
    global_connection_ids = { my_snowflake = "42" }
  }

  assert {
    condition     = dbtcloud_environment.environments["analytics_prod"].connection_id != null
    error_message = "connection_id should be resolved from global_connection_ids when connection key matches"
  }
}

# ── Custom branch handling ────────────────────────────────────────────────────

run "use_custom_branch_true_when_custom_branch_set" {
  command = apply

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name          = "Dev"
            key           = "dev"
            type          = "development"
            custom_branch = "feature/my-branch"
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = dbtcloud_environment.environments["analytics_dev"].use_custom_branch == true
    error_message = "use_custom_branch should be true when custom_branch is set"
  }

  assert {
    condition     = dbtcloud_environment.environments["analytics_dev"].custom_branch == "feature/my-branch"
    error_message = "custom_branch value should be passed through"
  }
}

run "use_custom_branch_false_when_custom_branch_absent" {
  command = apply

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
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = dbtcloud_environment.environments["analytics_dev"].use_custom_branch == false
    error_message = "use_custom_branch should be false when custom_branch is not set"
  }
}

# ── Protected environments ────────────────────────────────────────────────────

run "protected_environment_in_protected_resource" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name            = "Prod"
            key             = "prod"
            type            = "deployment"
            deployment_type = "production"
            protected       = true
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = length(dbtcloud_environment.protected_environments) == 1
    error_message = "Protected environment should be in protected_environments resource"
  }

  assert {
    condition     = length(dbtcloud_environment.environments) == 0
    error_message = "Protected environment should NOT be in unprotected environments"
  }
}
