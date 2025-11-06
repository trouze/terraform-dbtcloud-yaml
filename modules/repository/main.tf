terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
    }
    null = {
      source = "hashicorp/null"
    }
  }
}

################################################################################
# Auto-Detection & Validation Logic
# Detects git provider from remote_url and validates configuration
################################################################################

locals {
  # Auto-detect git provider from remote_url
  # This determines which native integration fields are valid
  detected_provider = (
    can(regex("github\\.com", var.repository_data.remote_url)) ? "github" :
    can(regex("gitlab\\.com", var.repository_data.remote_url)) ? "gitlab" :
    can(regex("dev\\.azure\\.com|ssh\\.dev\\.azure\\.com", var.repository_data.remote_url)) ? "azure_devops" :
    can(regex("bitbucket\\.org", var.repository_data.remote_url)) ? "bitbucket" :
    "unknown"
  )

  # Extract git_clone_strategy from input, or auto-detect based on provider
  git_clone_strategy_explicit = try(var.repository_data.git_clone_strategy, null)
  
  git_clone_strategy = local.git_clone_strategy_explicit != null ? local.git_clone_strategy_explicit : (
    local.detected_provider == "github" ? "github_app" :
    local.detected_provider == "gitlab" ? "deploy_token" :
    local.detected_provider == "azure_devops" ? "azure_active_directory_app" :
    "deploy_key"
  )

  # Validation: Ensure provider matches clone strategy
  provider_strategy_mismatch = (
    (local.detected_provider == "github" && local.git_clone_strategy == "deploy_token") ||
    (local.detected_provider == "github" && local.git_clone_strategy == "azure_active_directory_app") ||
    (local.detected_provider == "gitlab" && local.git_clone_strategy == "github_app") ||
    (local.detected_provider == "gitlab" && local.git_clone_strategy == "azure_active_directory_app") ||
    (local.detected_provider == "azure_devops" && local.git_clone_strategy == "github_app") ||
    (local.detected_provider == "azure_devops" && local.git_clone_strategy == "deploy_token")
  )

  # Validation: Check for required fields based on clone strategy
  github_app_missing_id = (
    local.git_clone_strategy == "github_app" && 
    (try(var.repository_data.github_installation_id, null) == null)
  )

  gitlab_deploy_token_missing_id = (
    local.git_clone_strategy == "deploy_token" && 
    (try(var.repository_data.gitlab_project_id, null) == null)
  )

  azure_missing_project_id = (
    local.git_clone_strategy == "azure_active_directory_app" && 
    (try(var.repository_data.azure_active_directory_project_id, null) == null)
  )

  azure_missing_repo_id = (
    local.git_clone_strategy == "azure_active_directory_app" && 
    (try(var.repository_data.azure_active_directory_repository_id, null) == null)
  )

  # Validation: Check for provider-specific fields that don't match the provider
  github_id_on_non_github = (
    local.detected_provider != "github" && 
    (try(var.repository_data.github_installation_id, null) != null)
  )

  gitlab_id_on_non_gitlab = (
    local.detected_provider != "gitlab" && 
    (try(var.repository_data.gitlab_project_id, null) != null)
  )

  azure_project_id_on_non_azure = (
    local.detected_provider != "azure_devops" && 
    (try(var.repository_data.azure_active_directory_project_id, null) != null)
  )

  azure_repo_id_on_non_azure = (
    local.detected_provider != "azure_devops" && 
    (try(var.repository_data.azure_active_directory_repository_id, null) != null)
  )

  azure_webhook_bypass_on_non_azure = (
    local.detected_provider != "azure_devops" && 
    (try(var.repository_data.azure_bypass_webhook_registration_failure, false) != false)
  )

  # Compile all validation errors
  validation_errors = concat(
    local.provider_strategy_mismatch ? [
      "❌ CONFIGURATION ERROR: git_clone_strategy '${local.git_clone_strategy}' does not match detected provider '${local.detected_provider}'. Check remote_url and git_clone_strategy."
    ] : [],
    local.github_app_missing_id ? [
      "❌ CONFIGURATION ERROR: git_clone_strategy 'github_app' requires 'github_installation_id'. See documentation for how to find your GitHub App installation ID."
    ] : [],
    local.gitlab_deploy_token_missing_id ? [
      "❌ CONFIGURATION ERROR: git_clone_strategy 'deploy_token' requires 'gitlab_project_id'. See documentation for how to find your GitLab project ID."
    ] : [],
    local.azure_missing_project_id ? [
      "❌ CONFIGURATION ERROR: git_clone_strategy 'azure_active_directory_app' requires 'azure_active_directory_project_id'. See documentation for how to find your Azure DevOps project ID."
    ] : [],
    local.azure_missing_repo_id ? [
      "❌ CONFIGURATION ERROR: git_clone_strategy 'azure_active_directory_app' requires 'azure_active_directory_repository_id'. See documentation for how to find your Azure DevOps repository ID."
    ] : [],
    local.github_id_on_non_github ? [
      "⚠️  WARNING: 'github_installation_id' is set but remote_url is not a GitHub URL. This field will be ignored. Did you mean to use a GitHub repository?"
    ] : [],
    local.gitlab_id_on_non_gitlab ? [
      "⚠️  WARNING: 'gitlab_project_id' is set but remote_url is not a GitLab URL. This field will be ignored. Did you mean to use a GitLab repository?"
    ] : [],
    local.azure_project_id_on_non_azure ? [
      "⚠️  WARNING: 'azure_active_directory_project_id' is set but remote_url is not an Azure DevOps URL. This field will be ignored. Did you mean to use an Azure DevOps repository?"
    ] : [],
    local.azure_repo_id_on_non_azure ? [
      "⚠️  WARNING: 'azure_active_directory_repository_id' is set but remote_url is not an Azure DevOps URL. This field will be ignored. Did you mean to use an Azure DevOps repository?"
    ] : [],
    local.azure_webhook_bypass_on_non_azure ? [
      "⚠️  WARNING: 'azure_bypass_webhook_registration_failure' is set but remote_url is not an Azure DevOps URL. This field will be ignored. Did you mean to use an Azure DevOps repository?"
    ] : []
  )

  # Fail if there are critical errors (not just warnings)
  has_critical_errors = anytrue([
    local.provider_strategy_mismatch,
    local.github_app_missing_id,
    local.gitlab_deploy_token_missing_id,
    local.azure_missing_project_id,
    local.azure_missing_repo_id
  ])
}

# Validation check: Fail if critical errors detected
resource "null_resource" "validation" {
  lifecycle {
    precondition {
      condition     = !local.has_critical_errors
      error_message = join("\n", concat(
        local.validation_errors,
        [
          "",
          "--- CONFIGURATION HELP ---",
          "Detected Provider: ${local.detected_provider}",
          "Auto-Selected Strategy: ${local.git_clone_strategy}",
          "Remote URL: ${var.repository_data.remote_url}",
          "",
          "Supported Strategies:",
          "  - deploy_key (default for all providers): No additional configuration needed",
          "  - github_app (GitHub only): Requires github_installation_id",
          "  - deploy_token (GitLab only): Requires gitlab_project_id",
          "  - azure_active_directory_app (Azure DevOps only): Requires azure_active_directory_project_id and azure_active_directory_repository_id",
          "",
          "See docs/REPOSITORY_CONFIGURATION.md for detailed setup instructions."
        ]
      ))
    }
  }

  triggers = {
    repository = var.repository_data.remote_url
  }
}

# Create the repository
resource "dbtcloud_repository" "repository" {
  depends_on = [null_resource.validation]

  project_id         = var.project_id
  remote_url         = var.repository_data.remote_url
  is_active          = try(var.repository_data.is_active, true)
  git_clone_strategy = local.git_clone_strategy

  # GitHub native integration
  github_installation_id = try(var.repository_data.github_installation_id, null)

  # GitLab native integration
  gitlab_project_id = try(var.repository_data.gitlab_project_id, null)

  # Azure DevOps native integration
  azure_active_directory_project_id = try(
    var.repository_data.azure_active_directory_project_id,
    null
  )
  azure_active_directory_repository_id = try(
    var.repository_data.azure_active_directory_repository_id,
    null
  )
  azure_bypass_webhook_registration_failure = try(
    var.repository_data.azure_bypass_webhook_registration_failure,
    false
  )

  # Optional common fields
  private_link_endpoint_id = try(var.repository_data.private_link_endpoint_id, null)
  pull_request_url_template = try(var.repository_data.pull_request_url_template, null)
}
