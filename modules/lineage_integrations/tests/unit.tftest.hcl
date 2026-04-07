# Unit tests for modules/lineage_integrations — run from modules/lineage_integrations/: terraform test

mock_provider "dbtcloud" {}

run "lineage_token_from_var_map" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        lineage_integrations = [
          {
            name       = "Tableau"
            key        = "tableau_prod"
            host       = "https://tableau.example.com"
            site_id    = "site"
            token_name = "pat"
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    lineage_tokens = {
      "analytics_tableau_prod" = "secret-token-value"
    }
  }

  assert {
    condition     = dbtcloud_lineage_integration.integrations["analytics_tableau_prod"].host == "https://tableau.example.com"
    error_message = "lineage integration should be created for composite key analytics_tableau_prod"
  }
}

run "lineage_inline_token_fallback" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        lineage_integrations = [
          {
            name       = "Tableau"
            key        = "tableau_prod"
            host       = "https://tableau.example.com"
            site_id    = "site"
            token_name = "pat"
            token      = "inline-fallback"
          }
        ]
      }
    ]
    project_ids    = { analytics = "1001" }
    lineage_tokens = {}
  }

  assert {
    condition     = dbtcloud_lineage_integration.integrations["analytics_tableau_prod"].token == "inline-fallback"
    error_message = "inline token on integration should be used when lineage_tokens omits the key"
  }
}
