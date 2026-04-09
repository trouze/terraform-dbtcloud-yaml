terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.9"
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

  privatelink_endpoints_map = {
    for ple in var.privatelink_endpoints :
    ple.key => ple
  }

  # COMPAT(v1-schema): resolve PrivateLink via privatelink_endpoints[] + account data when only private_link_endpoint_key is set (v2 projects.tf parity).
  needs_privatelink_data = length([
    for k, repo in local.repos_map : k
    if try(repo.private_link_endpoint_key, null) != null && try(repo.private_link_endpoint_id, null) == null
  ]) > 0

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

  # GitHub owner segment from remote_url (github.com only), for installation lookup
  # With a single capture group, regexall returns one element per match; inner list is [ capture ] (see terraform console).
  github_owner_from_url = {
    for k, repo in local.repos_map :
    k => try(regexall("github\\.com[/:]([^/]+)/", trimspace(try(repo.remote_url, "")))[0][0], null)
  }

  installation_id_from_discovery = {
    for k, repo in local.repos_map :
    k => lookup(
      var.github_installation_by_owner,
      try(local.github_owner_from_url[k], null) != null && trimspace(tostring(local.github_owner_from_url[k])) != "" ? lower(local.github_owner_from_url[k]) : "",
      null
    )
  }

  # YAML github_installation_id > owner match from discovery map > account fallback installation
  resolved_github_installation_id = {
    for k, repo in local.repos_map :
    k => (
      try(repo.github_installation_id, null) != null ? try(repo.github_installation_id, null) : (
        local.installation_id_from_discovery[k] != null ?
        local.installation_id_from_discovery[k] :
        try(var.github_installation_fallback_id, null)
      )
    )
  }

  # Effective git clone strategy per repo (with fallbacks).
  # nonsensitive() keeps the strategy string from inheriting sensitivity from var.dbt_pat (v2 projects.tf).
  effective_git_clone_strategy = {
    for k, repo in local.repos_map :
    k => nonsensitive(
      try(repo.git_clone_strategy, "") == "azure_active_directory_app" && (
        trimspace(tostring(try(repo.azure_active_directory_project_id, ""))) == "" ||
        trimspace(tostring(try(repo.azure_active_directory_repository_id, ""))) == ""
      ) ? "deploy_key" :
      try(repo.git_clone_strategy, "") == "deploy_token" ? (
        var.enable_gitlab_deploy_token ? "deploy_token" : "deploy_key"
      ) :
      try(repo.git_clone_strategy, "") == "github_app" ? (
        try(repo.github_installation_id, null) != null ||
        local.resolved_github_installation_id[k] != null ||
        var.dbt_pat != null
        ? "github_app" : "deploy_key"
      ) :
      try(repo.git_clone_strategy, null) != null ? try(repo.git_clone_strategy, "deploy_key") :
      local.detected_provider[k] == "github" ? (
        local.resolved_github_installation_id[k] != null || var.dbt_pat != null ? "github_app" : "deploy_key"
      ) :
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

  private_link_endpoint_id_by_repo_key = {
    for k, repo in local.repos_map : k => (
      try(repo.private_link_endpoint_id, null) != null && trimspace(tostring(try(repo.private_link_endpoint_id, ""))) != "" ?
      try(repo.private_link_endpoint_id, null) :
      (
        length(data.dbtcloud_privatelink_endpoints.all) > 0 &&
        try(repo.private_link_endpoint_key, null) != null &&
        lookup(local.privatelink_endpoints_map, repo.private_link_endpoint_key, null) != null
        ) ? data.dbtcloud_privatelink_endpoints.all[0].endpoints[
        index(
          [for ep in data.dbtcloud_privatelink_endpoints.all[0].endpoints : ep.id],
          lookup(local.privatelink_endpoints_map, repo.private_link_endpoint_key, { endpoint_id = null }).endpoint_id
        )
      ].id : null
    )
  }
}

data "dbtcloud_privatelink_endpoints" "all" {
  count = local.needs_privatelink_data ? 1 : 0
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
    ? local.resolved_github_installation_id[each.key]
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

  private_link_endpoint_id  = local.private_link_endpoint_id_by_repo_key[each.key]
  pull_request_url_template = try(each.value.pull_request_url_template, null)

  # Deferred until dbt-labs/dbtcloud supports resource_metadata on dbtcloud_repository (v2 parity).
  # resource_metadata = {
  #   source_project_id  = try(local.all_projects_map[each.key].id, null)
  #   source_id          = try(each.value.id, null)
  #   source_identity    = "REP:${each.key}"
  #   source_key         = each.key
  #   source_project_key = each.key
  #   source_name        = try(each.value.name, each.key)
  # }
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
    ? local.resolved_github_installation_id[each.key]
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

  private_link_endpoint_id  = local.private_link_endpoint_id_by_repo_key[each.key]
  pull_request_url_template = try(each.value.pull_request_url_template, null)

  # Deferred until dbt-labs/dbtcloud supports resource_metadata on dbtcloud_repository (v2 parity).
  # resource_metadata = {
  #   source_project_id  = try(local.all_projects_map[each.key].id, null)
  #   source_id          = try(each.value.id, null)
  #   source_identity    = "REP:${each.key}"
  #   source_key         = each.key
  #   source_project_key = each.key
  #   source_name        = try(each.value.name, each.key)
  # }

  lifecycle {
    prevent_destroy = true
  }
}
