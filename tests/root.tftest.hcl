# Root module unit tests — validate YAML parsing and module orchestration.
# Uses mock providers so no real dbt Cloud credentials are required.
# Run from the repo root: terraform test -filter=tests/root.tftest.hcl

mock_provider "dbtcloud" {}

mock_provider "dbtcloud" {
  alias = "pat_provider"
}

# ── Shared defaults (overridden per run where needed) ─────────────────────────

variables {
  dbt_account_id = 12345
  dbt_token      = "fake-token-for-testing"
  yaml_file      = "tests/fixtures/basic.yml"
}

# ── Single-project YAML (project: key) ───────────────────────────────────────

run "single_project_yaml_produces_one_project" {
  command = plan

  assert {
    condition     = contains(keys(output.project_ids), "my_project")
    error_message = "Expected project key 'my_project' in project_ids output"
  }

  assert {
    condition     = length(output.project_ids) == 1
    error_message = "Expected exactly one project from basic.yml"
  }
}

run "single_project_environment_ids_populated" {
  command = plan

  assert {
    condition     = contains(keys(output.environment_ids), "my_project_prod")
    error_message = "Expected environment key 'my_project_prod' in environment_ids output"
  }
}

run "single_project_job_ids_populated" {
  command = plan

  assert {
    condition     = contains(keys(output.job_ids), "my_project_daily_run")
    error_message = "Expected job key 'my_project_daily_run' in job_ids output"
  }
}

run "target_name_prefix_does_not_change_project_ids_key" {
  command = plan

  variables {
    target_name = "dev-"
  }

  assert {
    condition     = contains(keys(output.project_ids), "my_project")
    error_message = "project_ids key should use the YAML key, not the prefixed display name"
  }
}

# ── Multi-project YAML (projects: list) ──────────────────────────────────────

run "multi_project_yaml_produces_two_projects" {
  command = plan

  variables {
    yaml_file = "tests/fixtures/complete.yml"
  }

  assert {
    condition     = length(output.project_ids) == 2
    error_message = "Expected two projects from complete.yml"
  }

  assert {
    condition     = contains(keys(output.project_ids), "analytics")
    error_message = "Expected 'analytics' project key in output"
  }

  assert {
    condition     = contains(keys(output.project_ids), "finance")
    error_message = "Expected 'finance' project key in output"
  }
}

run "multi_project_environments_keyed_correctly" {
  command = plan

  variables {
    yaml_file = "tests/fixtures/complete.yml"
  }

  assert {
    condition     = contains(keys(output.environment_ids), "analytics_dev")
    error_message = "Expected composite key 'analytics_dev' in environment_ids"
  }

  assert {
    condition     = contains(keys(output.environment_ids), "analytics_prod")
    error_message = "Expected composite key 'analytics_prod' in environment_ids"
  }

  assert {
    condition     = contains(keys(output.environment_ids), "finance_prod")
    error_message = "Expected composite key 'finance_prod' in environment_ids"
  }
}

run "multi_project_jobs_keyed_correctly" {
  command = plan

  variables {
    yaml_file = "tests/fixtures/complete.yml"
  }

  assert {
    condition     = contains(keys(output.job_ids), "analytics_ci_check")
    error_message = "Expected composite key 'analytics_ci_check' in job_ids"
  }

  assert {
    condition     = contains(keys(output.job_ids), "analytics_daily_run")
    error_message = "Expected composite key 'analytics_daily_run' in job_ids"
  }
}
