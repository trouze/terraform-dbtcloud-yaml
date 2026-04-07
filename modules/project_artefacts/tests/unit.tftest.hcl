# Unit tests for modules/project_artefacts — run from modules/project_artefacts/: terraform test

mock_provider "dbtcloud" {}

run "v2_project_artefacts_docs_job_key" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        project_artefacts = {
          docs_job_key = "daily"
        }
      }
    ]
    project_ids = { analytics = "1001" }
    job_ids = {
      "analytics_daily" = "5001"
    }
  }

  assert {
    condition     = tostring(dbtcloud_project_artefacts.artefacts["analytics"].docs_job_id) == "5001"
    error_message = "project_artefacts.docs_job_key should resolve job id via project_key_job_key"
  }
}
