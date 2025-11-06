variable "repository_data" {
  description = <<-EOT
    Repository configuration object with auto-detection and validation.
    
    Supported providers (auto-detected from remote_url):
      - GitHub: https://github.com/* or git@github.com:* (supports github_app strategy)
      - GitLab: https://gitlab.com/* or git@gitlab.com:* (supports deploy_token strategy)
      - Azure DevOps: https://dev.azure.com/* or git@ssh.dev.azure.com:* (supports azure_active_directory_app strategy)
      - Bitbucket: https://bitbucket.org/* (uses deploy_key strategy)
      - Generic: Any other URL (uses deploy_key strategy)
    
    Required fields:
      - remote_url: Git repository URL (HTTPS or SSH)
    
    Optional fields depend on git_clone_strategy:
      - git_clone_strategy: Auto-detected, but can be explicitly set to:
          * deploy_key (default for all providers)
          * github_app (GitHub only, requires github_installation_id)
          * deploy_token (GitLab only, requires gitlab_project_id)
          * azure_active_directory_app (Azure DevOps only, requires azure_active_directory_project_id and azure_active_directory_repository_id)
      
      - github_installation_id: (GitHub app integration only) Integer ID of GitHub App installation
      - gitlab_project_id: (GitLab integration only) Integer ID of GitLab project
      - azure_active_directory_project_id: (Azure DevOps only) UUID of Azure DevOps project
      - azure_active_directory_repository_id: (Azure DevOps only) UUID of Azure DevOps repository
      - azure_bypass_webhook_registration_failure: (Azure DevOps only) Boolean, default false
      
      - is_active: Boolean, default true
      - private_link_endpoint_id: Optional private link endpoint ID (all providers)
      - pull_request_url_template: Optional custom PR URL template (all providers)
    
    Example GitHub with GitHub App:
      repository = {
        remote_url = "https://github.com/myorg/myrepo.git"
        git_clone_strategy = "github_app"
        github_installation_id = 12345678
      }
    
    Example GitLab with Deploy Token:
      repository = {
        remote_url = "https://gitlab.com/mygroup/myproject.git"
        git_clone_strategy = "deploy_token"
        gitlab_project_id = 9876543
      }
    
    Example Azure DevOps:
      repository = {
        remote_url = "https://dev.azure.com/myorg/myproject/_git/myrepo"
        git_clone_strategy = "azure_active_directory_app"
        azure_active_directory_project_id = "550e8400-e29b-41d4-a716-446655440000"
        azure_active_directory_repository_id = "550e8400-e29b-41d4-a716-446655440001"
      }
    
    Example Generic (SSH Deploy Key):
      repository = {
        remote_url = "git@github.com:myorg/myrepo.git"
      }
  EOT
  type        = any
  
  validation {
    condition     = can(var.repository_data.remote_url) && var.repository_data.remote_url != ""
    error_message = "repository_data must contain a non-empty 'remote_url' field."
  }
}

variable "project_id" {
  description = "The ID of the dbt Cloud project this repository is associated with"
  type        = string
}
