#############################################
# Projects
# 
# Creates dbt Cloud projects and their repositories.
# Each project references a repository (by key or inline object).
#############################################

locals {
  # Resolve repository references
  # The normalizer outputs repository references as string keys (e.g., "jaffle_shop")
  # We look them up in repositories_map to get the full repository object
  resolve_repository = {
    for project in var.projects :
    project.key => (
      # Handle null repository
      project.repository == null ? null :
      # Handle LOOKUP placeholder (unresolved reference)
      can(regex("^LOOKUP:", tostring(project.repository))) ? null :
      # Try to look up string key in repositories_map
      # try() returns null if the key doesn't exist or if project.repository isn't a valid key
      try(local.repositories_map[project.repository], null)
    )
  }

  # Filter projects that have valid repositories (not null, not LOOKUP)
  projects_with_repositories = {
    for project in var.projects :
    project.key => project
    if local.resolve_repository[project.key] != null
  }

  # Check if any GitLab repositories exist (require PAT)
  has_gitlab_repositories = length([
    for key, project in local.projects_with_repositories :
    key if try(local.resolve_repository[key].git_clone_strategy, "") == "deploy_token"
  ]) > 0

  # Determine effective git clone strategy for each repository
  # If github_app is specified but no PAT available, fallback to deploy_key
  # When github_installation_id is provided, API automatically uses github_app, so we must match that
  # Use nonsensitive() to prevent strategy string from inheriting PAT's sensitivity
  effective_git_clone_strategy = {
    for key, repo in local.resolve_repository :
    key => nonsensitive(
      # If github_installation_id is provided, API will use github_app regardless of what we send
      # So we must set it to github_app to match API behavior and avoid replacement
      local.effective_github_installation_id[key] != null ? "github_app" :
      # If explicitly set, use it (unless github_app without PAT)
      try(repo.git_clone_strategy, null) != null ? (
        try(repo.git_clone_strategy, "") == "github_app" && local.github_installation_id == null ?
        "deploy_key" : # Fallback to deploy_key if github_app but no PAT
        try(repo.git_clone_strategy, null)
      ) : null # Let Terraform/provider auto-detect
    )
  }

  # Determine effective GitHub installation ID
  # For migrations, prefer the discovered TARGET account installation ID
  # But allow per-repo override for adoption workflows where we know the target's ID
  effective_github_installation_id = {
    for key, repo in local.resolve_repository :
    key => (
      try(repo.git_clone_strategy, "") == "github_app" ? (
        # First, use discovered target account installation ID if available
        local.github_installation_id != null ? local.github_installation_id :
        # Fallback: use per-repo github_installation_id if specified (for adoption workflows)
        # This allows adopting existing repos without needing PAT discovery
        try(repo.github_installation_id, null)
      ) :
      # For non-github_app strategies, no installation ID needed
      null
    )
  }
}

# Create projects
resource "dbtcloud_project" "projects" {
  for_each = {
    for project in var.projects :
    project.key => project
  }

  name = each.value.name
}

# Create repositories for each project
# Note: GitLab repositories (deploy_token strategy) require a PAT - use TF_VAR_dbt_token with PAT
resource "dbtcloud_repository" "repositories" {
  for_each = local.projects_with_repositories

  project_id = dbtcloud_project.projects[each.key].id
  remote_url = local.resolve_repository[each.key].remote_url

  # Git clone strategy (with fallback to deploy_key if github_app without PAT)
  git_clone_strategy = local.effective_git_clone_strategy[each.key]

  is_active = try(local.resolve_repository[each.key].is_active, true)

  # GitHub native integration
  # Use discovered target account GitHub installation ID when github_app strategy is used
  # Falls back to deploy_key strategy if no PAT provided
  github_installation_id = local.effective_github_installation_id[each.key]

  # GitLab native integration
  gitlab_project_id = try(
    local.resolve_repository[each.key].gitlab_project_id,
    null
  )

  # Azure DevOps native integration
  azure_active_directory_project_id = try(
    local.resolve_repository[each.key].azure_active_directory_project_id,
    null
  )
  azure_active_directory_repository_id = try(
    local.resolve_repository[each.key].azure_active_directory_repository_id,
    null
  )
  azure_bypass_webhook_registration_failure = try(
    local.resolve_repository[each.key].azure_bypass_webhook_registration_failure,
    false
  )

  # PrivateLink endpoint reference
  private_link_endpoint_id = try(
    local.resolve_repository[each.key].private_link_endpoint_key != null ?
    lookup(
      {
        for ple in data.dbtcloud_privatelink_endpoints.all.endpoints :
        ple.id => ple.id
      },
      lookup(local.privatelink_endpoints_map, local.resolve_repository[each.key].private_link_endpoint_key, {}).endpoint_id,
      null
    ) : null,
    null
  )

  pull_request_url_template = try(
    local.resolve_repository[each.key].pull_request_url_template,
    null
  )
}

# Link repositories to projects
resource "dbtcloud_project_repository" "project_repositories" {
  for_each = local.projects_with_repositories

  project_id    = dbtcloud_project.projects[each.key].id
  repository_id = dbtcloud_repository.repositories[each.key].repository_id
}

