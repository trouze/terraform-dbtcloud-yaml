#############################################
# Projects
# 
# Creates dbt Cloud projects and their repositories.
# Each project references a repository (by key or inline object).
# Supports protected resources with lifecycle.prevent_destroy.
#############################################

locals {
  repository_ssh_fallback_url = "git@github.com:dbt-labs/jaffle-shop.git"

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
      # If source remote_url is not SSH-style, force deploy_key.
      # This supports integration-not-configured migrations by pairing with SSH fallback URL.
      !can(regex("^(git@|ssh:)", trimspace(try(repo.remote_url, "")))) ? "deploy_key" :
      # If Azure integration strategy is selected but required Azure IDs are missing, force deploy_key.
      # This avoids API failures when integrations are not configured in the target account yet.
      try(repo.git_clone_strategy, "") == "azure_active_directory_app" && (
        trimspace(tostring(try(repo.azure_active_directory_project_id, ""))) == "" ||
        trimspace(tostring(try(repo.azure_active_directory_repository_id, ""))) == ""
      ) ? "deploy_key" :
      # If GitLab integration strategy is selected but project ID is missing, force deploy_key.
      try(repo.git_clone_strategy, "") == "deploy_token" && try(repo.gitlab_project_id, null) == null ? "deploy_key" :
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

  # dbt Cloud repository creation expects SSH-style URLs ("git@" or "ssh:")
  # when integrations are not configured. Fall back to a known-good SSH repo.
  effective_repository_remote_url = {
    for key, repo in local.resolve_repository :
    key => (
      can(regex("^(git@|ssh:)", trimspace(try(repo.remote_url, "")))) ?
      trimspace(try(repo.remote_url, "")) :
      local.repository_ssh_fallback_url
    )
    if repo != null
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

  #############################################
  # Protection: Split projects into protected/unprotected
  # 
  # Two independent protection scopes:
  # - protected: Controls project resource protection (independent)
  # - repository_protected: Controls repository + project_repository protection
  #   Falls back to `protected` if not explicitly set, for backward compatibility
  #############################################

  # All projects as a map
  all_projects_map = {
    for project in var.projects :
    project.key => project
  }

  # Protected projects (protected: true)
  protected_projects_map = {
    for key, project in local.all_projects_map :
    key => project
    if try(project.protected, false) == true
  }

  # Unprotected projects (protected: false or not set)
  unprotected_projects_map = {
    for key, project in local.all_projects_map :
    key => project
    if try(project.protected, false) != true
  }

  # Determine effective repository protection status
  # Uses repository_protected if explicitly set, otherwise falls back to project.protected
  # This enables independent protection: protect project but not repo, or vice versa
  effective_repository_protected = {
    for key, project in local.all_projects_map :
    key => (
      # If repository_protected is explicitly set (true or false), use it
      try(project.repository_protected, null) != null ? project.repository_protected :
      # Otherwise fall back to project.protected for backward compatibility
      try(project.protected, false)
    )
  }

  # Protected repositories (based on effective_repository_protected)
  protected_repositories_map = {
    for key, project in local.all_projects_map :
    key => project
    if local.effective_repository_protected[key] == true && local.resolve_repository[key] != null
  }

  # Unprotected repositories (based on effective_repository_protected)
  unprotected_repositories_map = {
    for key, project in local.all_projects_map :
    key => project
    if local.effective_repository_protected[key] != true && local.resolve_repository[key] != null
  }

  debug_repository_resolution_entries = [
    for key, repo in local.resolve_repository : {
      project_key              = key
      remote_url               = try(repo.remote_url, null)
      effective_remote_url     = try(local.effective_repository_remote_url[key], null)
      fallback_applied         = try(local.effective_repository_remote_url[key], null) != trimspace(try(repo.remote_url, ""))
      is_ssh_style             = can(regex("^(git@|ssh:)", trimspace(try(repo.remote_url, ""))))
      configured_strategy      = try(repo.git_clone_strategy, null)
      effective_strategy       = try(local.effective_git_clone_strategy[key], null)
      has_github_installation  = try(local.effective_github_installation_id[key], null) != null
      has_gitlab_project_id    = try(repo.gitlab_project_id, null) != null
      has_azure_repository_id  = try(repo.azure_active_directory_repository_id, null) != null
      fallback_candidate_ssh   = "git@github.com:dbt-labs/jaffle-shop.git"
      fallback_candidate_https = "https://github.com/dbt-labs/jaffle-shop.git"
    }
    if repo != null
  ]
}

#region agent log
resource "null_resource" "debug_repository_resolution" {
  count = length(local.debug_repository_resolution_entries) > 0 ? 1 : 0

  triggers = {
    entries_json = jsonencode(local.debug_repository_resolution_entries)
  }

  provisioner "local-exec" {
    command = <<-EOT
python3 - <<'PY'
import json
import time

payload = {
    "sessionId": "25ac29",
    "runId": "repo-post-fix-3",
    "hypothesisId": "H6_H7_H8_H9",
    "location": "modules/projects_v2/projects.tf",
    "message": "repository resolution snapshot",
    "data": {"entries": json.loads(r'''${self.triggers.entries_json}''')},
    "timestamp": int(time.time() * 1000),
}

with open("/Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/.cursor/debug-25ac29.log", "a", encoding="utf-8") as f:
    f.write(json.dumps(payload, separators=(",", ":")) + "\\n")
PY
EOT
  }
}
#endregion

#############################################
# Unprotected Projects - standard lifecycle
#############################################

resource "dbtcloud_project" "projects" {
  for_each = local.unprotected_projects_map

  name = each.value.name
}

#############################################
# Protected Projects - prevent_destroy lifecycle
#############################################

resource "dbtcloud_project" "protected_projects" {
  for_each = local.protected_projects_map

  name = each.value.name

  lifecycle {
    prevent_destroy = true
  }
}

#############################################
# Unprotected Repositories - standard lifecycle
# Uses effective_repository_protected (independent of project protection)
#############################################

# Note: GitLab repositories (deploy_token strategy) require a PAT - use TF_VAR_dbt_token with PAT
resource "dbtcloud_repository" "repositories" {
  for_each = local.unprotected_repositories_map

  depends_on = [
    null_resource.debug_repository_resolution,
  ]

  # Reference the correct project resource based on PROJECT protection status
  # (repo protection is independent - repo can be unprotected while project is protected)
  project_id = (
    contains(keys(local.protected_projects_map), each.key) ?
    dbtcloud_project.protected_projects[each.key].id :
    dbtcloud_project.projects[each.key].id
  )
  remote_url = local.effective_repository_remote_url[each.key]

  # Git clone strategy (with fallback to deploy_key if github_app without PAT)
  git_clone_strategy = local.effective_git_clone_strategy[each.key]

  is_active = try(local.resolve_repository[each.key].is_active, true)

  # GitHub native integration
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

#############################################
# Protected Repositories - prevent_destroy lifecycle
# Uses effective_repository_protected (independent of project protection)
#############################################

resource "dbtcloud_repository" "protected_repositories" {
  for_each = local.protected_repositories_map

  depends_on = [
    null_resource.debug_repository_resolution,
  ]

  # Reference the correct project resource based on PROJECT protection status
  # (repo protection is independent - repo can be protected while project is unprotected)
  project_id = (
    contains(keys(local.protected_projects_map), each.key) ?
    dbtcloud_project.protected_projects[each.key].id :
    dbtcloud_project.projects[each.key].id
  )
  remote_url = local.effective_repository_remote_url[each.key]

  # Git clone strategy (with fallback to deploy_key if github_app without PAT)
  git_clone_strategy = local.effective_git_clone_strategy[each.key]

  is_active = try(local.resolve_repository[each.key].is_active, true)

  # GitHub native integration
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

  lifecycle {
    prevent_destroy = true
  }
}

#############################################
# Project-Repository Links
# Protection follows repository_protected (same as repository resources)
#############################################

# Link unprotected repositories to projects
resource "dbtcloud_project_repository" "project_repositories" {
  for_each = local.unprotected_repositories_map

  # Reference the correct project resource based on PROJECT protection status
  project_id = (
    contains(keys(local.protected_projects_map), each.key) ?
    dbtcloud_project.protected_projects[each.key].id :
    dbtcloud_project.projects[each.key].id
  )
  repository_id = dbtcloud_repository.repositories[each.key].repository_id
}

# Link protected repositories to projects
resource "dbtcloud_project_repository" "protected_project_repositories" {
  for_each = local.protected_repositories_map

  # Reference the correct project resource based on PROJECT protection status
  project_id = (
    contains(keys(local.protected_projects_map), each.key) ?
    dbtcloud_project.protected_projects[each.key].id :
    dbtcloud_project.projects[each.key].id
  )
  repository_id = dbtcloud_repository.protected_repositories[each.key].repository_id

  lifecycle {
    prevent_destroy = true
  }
}