#############################################
# Projects
# 
# Creates dbt Cloud projects and their repositories.
# Each project references a repository (by key or inline object).
#############################################

locals {
  # Helper function to resolve repository reference
  # Returns repository object whether it's a key reference or inline object
  resolve_repository = {
    for project in var.projects :
    project.key => (
      # If repository is a string (key reference), look it up in globals
      can(regex("^[a-zA-Z0-9_.-]+$", tostring(project.repository))) ?
      local.repositories_map[project.repository] :
      # Otherwise, it's an inline object, use it directly
      project.repository
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
# Repositories are project-scoped, so we create one per project
resource "dbtcloud_repository" "repositories" {
  for_each = {
    for project in var.projects :
    project.key => project
  }

  project_id = dbtcloud_project.projects[each.key].id
  remote_url = local.resolve_repository[each.key].remote_url

  # Git clone strategy (auto-detect if not specified)
  git_clone_strategy = try(
    local.resolve_repository[each.key].git_clone_strategy,
    null # Let Terraform/provider auto-detect
  )

  is_active = try(local.resolve_repository[each.key].is_active, true)

  # GitHub native integration
  github_installation_id = try(
    local.resolve_repository[each.key].github_installation_id,
    null
  )

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
  for_each = {
    for project in var.projects :
    project.key => project
  }

  project_id    = dbtcloud_project.projects[each.key].id
  repository_id = dbtcloud_repository.repositories[each.key].id
}

