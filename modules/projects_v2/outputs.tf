#############################################
# Module Outputs
# 
# Exposes resource IDs for reference by other modules or outputs.
#############################################

# Global resource IDs
output "connection_ids" {
  description = "Map of connection keys to connection IDs"
  value = merge(
    {
      for key, conn in dbtcloud_global_connection.connections :
      key => conn.id
    },
    {
      for key, conn in dbtcloud_global_connection.protected_connections :
      key => conn.id
    }
  )
}

output "repository_ids" {
  description = "Map of project keys to repository IDs"
  value = merge(
    {
      for key, repo in dbtcloud_repository.repositories :
      key => repo.id
    },
    {
      for key, repo in dbtcloud_repository.protected_repositories :
      key => repo.id
    }
  )
}

output "service_token_ids" {
  description = "Map of service token keys to service token IDs"
  value = merge(
    {
      for key, token in dbtcloud_service_token.service_tokens :
      key => token.id
    },
    {
      for key, token in dbtcloud_service_token.protected_service_tokens :
      key => token.id
    }
  )
}

output "group_ids" {
  description = "Map of group keys to group IDs"
  value = merge(
    {
      for key, group in dbtcloud_group.groups :
      key => group.id
    },
    {
      for key, group in dbtcloud_group.protected_groups :
      key => group.id
    }
  )
}

output "notification_ids" {
  description = "Map of notification keys to notification IDs"
  value = {
    for key, notif in dbtcloud_notification.notifications :
    key => notif.id
  }
}

# Project resource IDs
output "project_ids" {
  description = "Map of project keys to project IDs"
  value = merge(
    {
      for key, project in dbtcloud_project.projects :
      key => project.id
    },
    {
      for key, project in dbtcloud_project.protected_projects :
      key => project.id
    }
  )
}

output "environment_ids" {
  description = "Map of project_key_environment_key to environment IDs"
  value = merge(
    {
      for key, env in dbtcloud_environment.environments :
      key => env.id
    },
    {
      for key, env in dbtcloud_environment.protected_environments :
      key => env.id
    }
  )
}

output "job_ids" {
  description = "Map of project_key_environment_key_job_key to job IDs"
  value = merge(
    {
      for key, job in dbtcloud_job.jobs :
      key => job.id
    },
    {
      for key, job in dbtcloud_job.protected_jobs :
      key => job.id
    }
  )
}

output "credential_ids" {
  description = "Map of project_key_environment_key to credential IDs"
  value = {
    for key, cred in dbtcloud_databricks_credential.credentials :
    key => cred.credential_id
  }
}

# Debug outputs for troubleshooting connection and repository linking
output "connection_mapping" {
  description = "Debug: Connection key to ID mapping"
  value = merge(
    {
      for key, conn in dbtcloud_global_connection.connections :
      key => {
        id        = conn.id
        name      = conn.name
        protected = false
      }
    },
    {
      for key, conn in dbtcloud_global_connection.protected_connections :
      key => {
        id        = conn.id
        name      = conn.name
        protected = true
      }
    }
  )
}

output "environment_connections" {
  description = "Debug: Environment to connection mapping"
  value = merge(
    {
      for key, env in dbtcloud_environment.environments :
      key => {
        environment_id = env.id
        connection_id  = env.connection_id
        project_key    = split("_", key)[0]
        env_key        = split("_", key)[1]
        protected      = false
      }
    },
    {
      for key, env in dbtcloud_environment.protected_environments :
      key => {
        environment_id = env.id
        connection_id  = env.connection_id
        project_key    = split("_", key)[0]
        env_key        = split("_", key)[1]
        protected      = true
      }
    }
  )
}

output "repository_integration_status" {
  description = "Debug: Repository integration linking status"
  value = merge(
    {
      for key, repo in dbtcloud_repository.repositories :
      key => {
        repository_id          = repo.id
        git_clone_strategy     = repo.git_clone_strategy
        github_installation_id = repo.github_installation_id
        gitlab_project_id      = repo.gitlab_project_id
        azure_project_id       = repo.azure_active_directory_project_id
        azure_repository_id    = repo.azure_active_directory_repository_id
        linked_to_project      = try(dbtcloud_project_repository.project_repositories[key].id, null) != null
        protected              = false
      }
    },
    {
      for key, repo in dbtcloud_repository.protected_repositories :
      key => {
        repository_id          = repo.id
        git_clone_strategy     = repo.git_clone_strategy
        github_installation_id = repo.github_installation_id
        gitlab_project_id      = repo.gitlab_project_id
        azure_project_id       = repo.azure_active_directory_project_id
        azure_repository_id    = repo.azure_active_directory_repository_id
        linked_to_project      = try(dbtcloud_project_repository.protected_project_repositories[key].id, null) != null
        protected              = true
      }
    }
  )
}

output "gitlab_deploy_token_status" {
  description = "GitLab deploy_token repos: which are native vs downgraded to deploy_key"
  value = {
    enabled = var.enable_gitlab_deploy_token
    repos = {
      for key, repo in local.resolve_repository :
      key => {
        source_strategy    = try(repo.git_clone_strategy, null)
        effective_strategy = local.effective_git_clone_strategy[key]
        downgraded         = local.gitlab_deploy_token_downgraded[key]
        gitlab_project_id  = local.gitlab_deploy_token_downgraded[key] ? null : try(repo.gitlab_project_id, null)
        remote_url         = local.effective_repository_remote_url[key]
      }
      if try(repo.git_clone_strategy, "") == "deploy_token"
    }
  }
}

output "github_integration_discovery" {
  description = "Debug: GitHub integration discovery status"
  value = {
    pat_provided          = var.dbt_pat != null
    installations_found   = length(local.github_installations)
    installation_by_owner = local.github_installation_by_owner
    fallback_id           = local.github_installation_id
    host_url              = local.dbt_host_url
    http_status = var.dbt_pat != null && length(data.http.github_installations) > 0 ? (
      try(data.http.github_installations[0].status_code, "unknown")
    ) : "not_called"
    raw_response_length = var.dbt_pat != null && length(data.http.github_installations) > 0 ? (
      try(length(data.http.github_installations[0].response_body), 0)
    ) : 0
  }
}

# Debug outputs for job deferral
output "job_deferral_debug" {
  description = "Debug: Job deferring environment resolution"
  value = {
    # All environment keys from all_environments
    all_environments_keys = [for env in local.all_environments : "${env.project_key}_${env.env_key}"]
    # Direct environment resource keys (both protected and unprotected)
    environment_resource_keys = concat(
      keys(dbtcloud_environment.environments),
      keys(dbtcloud_environment.protected_environments)
    )
    # Job deferral lookups
    deferring_env_lookups = {
      for key, item in local.jobs_map :
      key => {
        project_key               = item.project_key
        deferring_environment_key = try(item.job_data.deferring_environment_key, "NULL")
        lookup_key                = "${item.project_key}_${try(item.job_data.deferring_environment_key, "NULL")}"
        key_exists_in_envs = contains(
          concat(keys(dbtcloud_environment.environments), keys(dbtcloud_environment.protected_environments)),
          "${item.project_key}_${try(item.job_data.deferring_environment_key, "")}"
        )
        run_compare_changes = try(item.job_data.run_compare_changes, false)
      }
      if try(item.job_data.deferring_environment_key, null) != null
    }
  }
}

# Debug outputs for environment variables
output "env_var_debug" {
  description = "Debug: Environment variable processing status"
  value = {
    all_env_vars_count = length(local.all_environment_variables)
    env_vars_map_keys  = keys(local.env_vars_map)
    env_vars_map_count = length(local.env_vars_map)
    sample_env_var = length(local.all_environment_variables) > 0 ? {
      name               = local.all_environment_variables[0].env_var_key
      project_key        = local.all_environment_variables[0].project_key
      environment_values = try(local.all_environment_variables[0].env_var_data.environment_values, {})
      env_values_count   = length(try(local.all_environment_variables[0].env_var_data.environment_values, {}))
    } : null
    resources_planned = length(dbtcloud_environment_variable.environment_variables)
  }
}

