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

run "v1_artefacts_still_supported" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        artefacts = {
          docs_job      = "daily"
          freshness_job = "hourly"
        }
      }
    ]
    project_ids = { analytics = "1001" }
    job_ids = {
      "analytics_daily"  = "5001"
      "analytics_hourly" = "5002"
    }
  }

  assert {
    condition = (
      tostring(dbtcloud_project_artefacts.artefacts["analytics"].docs_job_id) == "5001" &&
      tostring(dbtcloud_project_artefacts.artefacts["analytics"].freshness_job_id) == "5002"
    )
    error_message = "v1 artefacts.docs_job / freshness_job should still resolve"
  }
}
