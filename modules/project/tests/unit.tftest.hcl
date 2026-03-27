# Unit tests for modules/project
# Validates project naming, target_name prefix, and protected resource routing.
# Run from modules/project/: terraform test

mock_provider "dbtcloud" {}

# ── Basic project creation ────────────────────────────────────────────────────

run "single_project_created" {
  command = plan

  variables {
    projects = [
      {
        name = "My Project"
        key  = "my_project"
      }
    ]
    target_name = ""
  }

  assert {
    condition     = length(dbtcloud_project.projects) == 1
    error_message = "Expected one unprotected project to be created"
  }

  assert {
    condition     = dbtcloud_project.projects["my_project"].name == "My Project"
    error_message = "Project name should match YAML name"
  }
}

run "project_key_falls_back_to_name" {
  command = plan

  variables {
    projects = [
      {
        name = "No Key Project"
      }
    ]
    target_name = ""
  }

  assert {
    condition     = length(dbtcloud_project.projects) == 1
    error_message = "Expected one project even without a key field"
  }

  assert {
    condition     = contains(keys(dbtcloud_project.projects), "No Key Project")
    error_message = "Key should fall back to project name when key is absent"
  }
}

# ── target_name prefix ────────────────────────────────────────────────────────

run "target_name_prepended_to_project_name" {
  command = plan

  variables {
    projects = [
      {
        name = "Analytics"
        key  = "analytics"
      }
    ]
    target_name = "dev-"
  }

  assert {
    condition     = dbtcloud_project.projects["analytics"].name == "dev-Analytics"
    error_message = "target_name prefix should be prepended to the project name"
  }
}

run "empty_target_name_leaves_name_unchanged" {
  command = plan

  variables {
    projects = [
      {
        name = "Analytics"
        key  = "analytics"
      }
    ]
    target_name = ""
  }

  assert {
    condition     = dbtcloud_project.projects["analytics"].name == "Analytics"
    error_message = "Empty target_name should not alter the project name"
  }
}

# ── Protected resources ───────────────────────────────────────────────────────

run "protected_project_routed_to_protected_resource" {
  command = plan

  variables {
    projects = [
      {
        name      = "Finance"
        key       = "finance"
        protected = true
      }
    ]
    target_name = ""
  }

  assert {
    condition     = length(dbtcloud_project.protected_projects) == 1
    error_message = "Protected project should be in protected_projects resource"
  }

  assert {
    condition     = length(dbtcloud_project.projects) == 0
    error_message = "Protected project should NOT be in unprotected projects resource"
  }
}

run "unprotected_project_not_in_protected_resource" {
  command = plan

  variables {
    projects = [
      {
        name = "Analytics"
        key  = "analytics"
      }
    ]
    target_name = ""
  }

  assert {
    condition     = length(dbtcloud_project.protected_projects) == 0
    error_message = "Unprotected project should not appear in protected_projects"
  }
}

run "mixed_protected_and_unprotected_projects" {
  command = plan

  variables {
    projects = [
      {
        name = "Analytics"
        key  = "analytics"
      },
      {
        name      = "Finance"
        key       = "finance"
        protected = true
      }
    ]
    target_name = ""
  }

  assert {
    condition     = length(dbtcloud_project.projects) == 1
    error_message = "Expected one unprotected project"
  }

  assert {
    condition     = length(dbtcloud_project.protected_projects) == 1
    error_message = "Expected one protected project"
  }
}

# ── Output structure ──────────────────────────────────────────────────────────

run "output_project_ids_merges_both_resource_sets" {
  command = plan

  variables {
    projects = [
      {
        name = "Analytics"
        key  = "analytics"
      },
      {
        name      = "Finance"
        key       = "finance"
        protected = true
      }
    ]
    target_name = ""
  }

  assert {
    condition     = contains(keys(output.project_ids), "analytics")
    error_message = "project_ids output should contain unprotected project key"
  }

  assert {
    condition     = contains(keys(output.project_ids), "finance")
    error_message = "project_ids output should contain protected project key"
  }
}
