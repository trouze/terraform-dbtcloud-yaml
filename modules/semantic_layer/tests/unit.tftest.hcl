# Unit tests for modules/semantic_layer — run from modules/semantic_layer/: terraform test

mock_provider "dbtcloud" {}

run "semantic_layer_config_environment_id" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        semantic_layer_config = {
          environment_id = "9001"
        }
      }
    ]
    project_ids = { analytics = "1001" }
    environment_ids = {
      "analytics_dev" = "8001"
    }
  }

  assert {
    condition     = tostring(dbtcloud_semantic_layer_configuration.semantic_layer["analytics"].environment_id) == "9001"
    error_message = "semantic_layer_config.environment_id should pass through directly"
  }
}

run "semantic_layer_config_environment_key_lookup" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        semantic_layer_config = {
          environment_key = "dev"
        }
      }
    ]
    project_ids = { analytics = "1001" }
    environment_ids = {
      "analytics_dev" = "8001"
    }
  }

  assert {
    condition     = tostring(dbtcloud_semantic_layer_configuration.semantic_layer["analytics"].environment_id) == "8001"
    error_message = "semantic_layer_config.environment_key should resolve via environment_ids composite key"
  }
}
