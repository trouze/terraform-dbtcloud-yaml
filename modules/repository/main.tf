terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  # Build a map of project_key => repository object (skip projects with no repository)
  repos_map = {
    for p in var.projects :
    try(p.key, p.name) => p.repository
    if try(p.repository, null) != null
  }

  # All projects as map for protection lookups
  all_projects_map = {
    for p in var.projects :
    try(p.key, p.name) => p
  }

  # Auto-detect provider from remote_url
  detected_provider = {
    for k, repo in local.repos_map :
    k => (
      can(regex("github\\.com", try(repo.remote_url, ""))) ? "github" :
      can(regex("gitlab\\.com|gitlab\\.", try(repo.remote_url, ""))) ? "gitlab" :
      can(regex("dev\\.azure\\.com|ssh\\.dev\\.azure\\.com", try(repo.remote_url, ""))) ? "azure_devops" :
      can(regex("bitbucket\\.org", try(repo.remote_url, ""))) ? "bitbucket" :
      "unknown"
    )
  }

  # Effective git clone strategy per repo (with fallbacks)
  effective_git_clone_strategy = {
    for k, repo in local.repos_map :
    k => (
      # Azure DevOps: downgrade if required IDs are missing
      try(repo.git_clone_strategy, "") == "azure_active_directory_app" && (
        trimspace(tostring(try(repo.azure_active_directory_project_id, ""))) == "" ||
        trimspace(tostring(try(repo.azure_active_directory_repository_id, ""))) == ""
      ) ? "deploy_key" :
      # GitLab deploy_token: downgrade to deploy_key unless explicitly enabled
      try(repo.git_clone_strategy, "") == "deploy_token" ? (
        var.enable_gitlab_deploy_token ? "deploy_token" : "deploy_key"
      ) :
      # GitHub App: use if installation ID available, else deploy_key
      try(repo.git_clone_strategy, "") == "github_app" ? (
        try(repo.github_installation_id, null) != null || var.dbt_pat != null ? "github_app" : "deploy_key"
      ) :
      # Explicit strategy set to something other than the above
      try(repo.git_clone_strategy, null) != null ? try(repo.git_clone_strategy, "deploy_key") :
      # Auto-detect defaults
      local.detected_provider[k] == "github" ? "github_app" :
      local.detected_provider[k] == "gitlab" ? "deploy_token" :
      local.detected_provider[k] == "azure_devops" ? "azure_active_directory_app" :
      "deploy_key"
    )
  }

  # Downgraded GitLab repos (deploy_token → deploy_key) need SSH URL format
  gitlab_deploy_token_downgraded = {
    for k, repo in local.repos_map :
    k => try(repo.git_clone_strategy, "") == "deploy_token" && local.effective_git_clone_strategy[k] == "deploy_key"
  }

  # Extract GitLab hostname from pull_request_url_template for SSH URL construction
  gitlab_ssh_host = {
    for k, repo in local.repos_map :
    k => try(regex("https?://([^/]+)/", try(repo.pull_request_url_template, ""))[0], "gitlab.com")
  }

  # Effective remote URL
  effective_remote_url = {
    for k, repo in local.repos_map :
    k => (
      local.gitlab_deploy_token_downgraded[k] ? (
        "git@${local.gitlab_ssh_host[k]}:${trimspace(try(repo.remote_url, ""))}.git"
      ) :
      contains(["github_app", "azure_active_directory_app"], local.effective_git_clone_strategy[k]) ? (
        trimspace(try(repo.remote_url, ""))
      ) :
      can(regex("^(git@|ssh:)", trimspace(try(repo.remote_url, "")))) ?
      trimspace(try(repo.remote_url, "")) :
      "git@github.com:dbt-labs/jaffle-shop.git"
    )
  }

  # Effective protection status per repo
  # Uses repository_protected if explicitly set, else falls back to project.protected
  repo_protected = {
    for k, repo in local.repos_map :
    k => (
      try(local.all_projects_map[k].repository_protected, null) != null
      ? local.all_projects_map[k].repository_protected
      : try(local.all_projects_map[k].protected, false)
    )
  }

  protected_repos_map = {
    for k, repo in local.repos_map : k => repo
    if local.repo_protected[k] == true
  }

  unprotected_repos_map = {
    for k, repo in local.repos_map : k => repo
    if local.repo_protected[k] != true
  }
}

#############################################
# Unprotected Repositories
#############################################

resource "dbtcloud_repository" "repositories" {
  for_each = local.unprotected_repos_map

  project_id         = var.project_ids[each.key]
  remote_url         = local.effective_remote_url[each.key]
  is_active          = try(each.value.is_active, true)
  git_clone_strategy = local.effective_git_clone_strategy[each.key]

  github_installation_id = (
    local.effective_git_clone_strategy[each.key] == "github_app"
    ? try(each.value.github_installation_id, null)
    : null
  )

  gitlab_project_id = (
    local.gitlab_deploy_token_downgraded[each.key] ? null
    : try(each.value.gitlab_project_id, null)
  )

  azure_active_directory_project_id = try(
    each.value.azure_active_directory_project_id, null
  )
  azure_active_directory_repository_id = try(
    each.value.azure_active_directory_repository_id, null
  )
  azure_bypass_webhook_registration_failure = try(
    each.value.azure_bypass_webhook_registration_failure, false
  )

  private_link_endpoint_id  = try(each.value.private_link_endpoint_id, null)
  pull_request_url_template = try(each.value.pull_request_url_template, null)
}

#############################################
# Protected Repositories — lifecycle.prevent_destroy
#############################################

resource "dbtcloud_repository" "protected_repositories" {
  for_each = local.protected_repos_map

  project_id         = var.project_ids[each.key]
  remote_url         = local.effective_remote_url[each.key]
  is_active          = try(each.value.is_active, true)
  git_clone_strategy = local.effective_git_clone_strategy[each.key]

  github_installation_id = (
    local.effective_git_clone_strategy[each.key] == "github_app"
    ? try(each.value.github_installation_id, null)
    : null
  )

  gitlab_project_id = (
    local.gitlab_deploy_token_downgraded[each.key] ? null
    : try(each.value.gitlab_project_id, null)
  )

  azure_active_directory_project_id = try(
    each.value.azure_active_directory_project_id, null
  )
  azure_active_directory_repository_id = try(
    each.value.azure_active_directory_repository_id, null
  )
  azure_bypass_webhook_registration_failure = try(
    each.value.azure_bypass_webhook_registration_failure, false
  )

  private_link_endpoint_id  = try(each.value.private_link_endpoint_id, null)
  pull_request_url_template = try(each.value.pull_request_url_template, null)

  lifecycle {
    prevent_destroy = true
  }
}
