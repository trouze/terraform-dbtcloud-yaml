# Unit tests for modules/repository
# Validates git provider auto-detection, clone strategy selection, and fallback
# behavior for GitHub (no installation ID), GitLab (deploy_token gate), and
# Azure DevOps (missing IDs fallback).
# Run from modules/repository/: terraform test

mock_provider "dbtcloud" {}

# ── GitHub URL auto-detection ─────────────────────────────────────────────────

run "github_url_without_explicit_strategy_auto_detects_github_app" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        repository = {
          remote_url = "git@github.com:my-org/analytics.git"
        }
      }
    ]
    project_ids = { analytics = "1001" }
    dbt_pat     = null
  }

  assert {
    condition     = dbtcloud_repository.repositories["analytics"].git_clone_strategy == "github_app"
    error_message = "GitHub URL without explicit strategy auto-detects to github_app (no installation_id check in auto-detect path)"
  }
}

run "github_url_with_installation_id_uses_github_app" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        repository = {
          remote_url             = "https://github.com/my-org/analytics"
          github_installation_id = 12345678
        }
      }
    ]
    project_ids = { analytics = "1001" }
    dbt_pat     = null
  }

  assert {
    condition     = dbtcloud_repository.repositories["analytics"].git_clone_strategy == "github_app"
    error_message = "GitHub URL with installation_id should use github_app strategy"
  }
}

run "github_url_with_pat_uses_github_app" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        repository = {
          remote_url = "https://github.com/my-org/analytics"
        }
      }
    ]
    project_ids = { analytics = "1001" }
    dbt_pat     = "ghp_fake_pat_token"
  }

  assert {
    condition     = dbtcloud_repository.repositories["analytics"].git_clone_strategy == "github_app"
    error_message = "GitHub URL with PAT set should use github_app strategy"
  }
}

# ── GitLab URL auto-detection ─────────────────────────────────────────────────

run "gitlab_url_without_explicit_strategy_auto_detects_deploy_token" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        repository = {
          remote_url = "https://gitlab.com/my-org/analytics"
        }
      }
    ]
    project_ids                = { analytics = "1001" }
    enable_gitlab_deploy_token = false
  }

  assert {
    condition     = dbtcloud_repository.repositories["analytics"].git_clone_strategy == "deploy_token"
    error_message = "GitLab URL without explicit strategy auto-detects to deploy_token (enable_gitlab_deploy_token only gates explicit deploy_token strategy)"
  }
}

run "gitlab_deploy_token_enabled_uses_deploy_token" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        repository = {
          remote_url         = "https://gitlab.com/my-org/analytics"
          git_clone_strategy = "deploy_token"
          gitlab_project_id  = 999
        }
      }
    ]
    project_ids                = { analytics = "1001" }
    enable_gitlab_deploy_token = true
  }

  assert {
    condition     = dbtcloud_repository.repositories["analytics"].git_clone_strategy == "deploy_token"
    error_message = "GitLab with enable_gitlab_deploy_token=true and explicit deploy_token strategy should use deploy_token"
  }
}

# ── Azure DevOps URL auto-detection ──────────────────────────────────────────

run "azure_devops_url_without_ids_falls_back_to_deploy_key" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        repository = {
          remote_url         = "https://dev.azure.com/my-org/my-project/_git/analytics"
          git_clone_strategy = "azure_active_directory_app"
        }
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = dbtcloud_repository.repositories["analytics"].git_clone_strategy == "deploy_key"
    error_message = "Azure DevOps without required IDs should fall back to deploy_key"
  }
}

run "azure_devops_with_required_ids_uses_aad_strategy" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        repository = {
          remote_url                           = "https://dev.azure.com/my-org/my-project/_git/analytics"
          git_clone_strategy                   = "azure_active_directory_app"
          azure_active_directory_project_id    = "proj-uuid"
          azure_active_directory_repository_id = "repo-uuid"
        }
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = dbtcloud_repository.repositories["analytics"].git_clone_strategy == "azure_active_directory_app"
    error_message = "Azure DevOps with both IDs should use azure_active_directory_app"
  }
}

# ── Generic / unknown URL ─────────────────────────────────────────────────────

run "unknown_url_uses_deploy_key" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        repository = {
          remote_url = "git@bitbucket.org:my-org/analytics.git"
        }
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = dbtcloud_repository.repositories["analytics"].git_clone_strategy == "deploy_key"
    error_message = "Bitbucket URL without explicit strategy should use deploy_key"
  }
}

# ── Protected repositories ────────────────────────────────────────────────────

run "protected_repository_routed_to_protected_resource" {
  command = plan

  variables {
    projects = [
      {
        key       = "analytics"
        name      = "Analytics"
        protected = true
        repository = {
          remote_url = "git@github.com:my-org/analytics.git"
        }
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = length(dbtcloud_repository.protected_repositories) == 1
    error_message = "Protected project should route repository to protected_repositories"
  }

  assert {
    condition     = length(dbtcloud_repository.repositories) == 0
    error_message = "Protected project should not put repository in unprotected resource"
  }
}

run "project_with_no_repository_creates_no_resource" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
      }
    ]
    project_ids = { analytics = "1001" }
  }

  assert {
    condition     = length(dbtcloud_repository.repositories) == 0
    error_message = "Project without repository block should create no repository resource"
  }
}
