#############################################
# Environment Variables
# 
# Creates project-scoped environment variables with
# environment-specific values and job-level overrides.
#############################################

locals {
  # Helper to get project_id from either protected or unprotected projects
  # This allows env vars to reference their parent project regardless of protection status
  env_var_project_id_lookup = {
    for project in var.projects :
    project.key => (
      try(project.protected, false) == true
      ? dbtcloud_project.protected_projects[project.key].id
      : dbtcloud_project.projects[project.key].id
    )
  }

  # Flatten all environment variables across all projects
  all_environment_variables = flatten([
    for project in var.projects : [
      for env_var in try(project.environment_variables, []) : {
        project_key  = project.key
        project_id   = local.env_var_project_id_lookup[project.key]
        env_var_key  = env_var.name
        env_var_data = env_var
      }
    ]
  ])

  #############################################
  # Protection: Split env vars into protected/unprotected
  #############################################

  # Protected environment variables (protected: true in env_var_data)
  protected_environment_variables = [
    for item in local.all_environment_variables :
    item
    if try(item.env_var_data.protected, false) == true
  ]

  # Unprotected environment variables (protected: false or not set)
  unprotected_environment_variables = [
    for item in local.all_environment_variables :
    item
    if try(item.env_var_data.protected, false) != true
  ]

  # Create maps keyed by project_key_env_var_name
  env_vars_map = {
    for item in local.unprotected_environment_variables :
    "${item.project_key}_${item.env_var_key}" => item
  }

  protected_env_vars_map = {
    for item in local.protected_environment_variables :
    "${item.project_key}_${item.env_var_key}" => item
  }

  # Build a map of environment names to environment resource keys
  # This maps "project_key_env_name" => environment resource key
  # Used to create implicit dependencies by referencing created environment resources
  env_name_to_resource_key = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_data.name}" => "${item.project_key}_${item.env_key}"
  }

  # Merged environment name lookup - resolves from either protected or unprotected environments
  # This allows env vars to reference their parent environment regardless of protection status
  env_resolved_name = merge(
    {
      for key, env in dbtcloud_environment.environments :
      key => env.name
    },
    {
      for key, env in dbtcloud_environment.protected_environments :
      key => env.name
    }
  )
}

# Create project-scoped environment variables
resource "dbtcloud_environment_variable" "environment_variables" {
  for_each = local.env_vars_map

  name       = each.value.env_var_data.name
  project_id = each.value.project_id

  # Map environment values
  # Keys in environment_values should match environment names
  # Reference created environment resources directly to create implicit dependencies
  # This ensures environments exist before env vars are created, but only for referenced environments
  environment_values = {
    for env_key, env_value in each.value.env_var_data.environment_values :
    # Resolve environment name (use env_key directly if it's "project" or if lookup fails)
    env_key == "project" ? "project" : (
      # Try to find the environment resource key for this environment name
      contains(keys(local.env_name_to_resource_key), "${each.value.project_key}_${env_key}") ?
      # Reference the merged environment lookup to create implicit dependency
      # This resolves from either protected or unprotected environments
      local.env_resolved_name[local.env_name_to_resource_key["${each.value.project_key}_${env_key}"]] :
      # Fallback to env_key if environment not found (will cause API error, but that's expected)
      env_key
      ) => (
      # If value starts with secret prefix, look it up in token_map
      can(regex("^secret_", env_value)) ?
      lookup(var.token_map, replace(env_value, "secret_", ""), env_value) :
      env_value
    )
  }
}

#############################################
# Protected Environment Variables - prevent_destroy lifecycle
#############################################

resource "dbtcloud_environment_variable" "protected_environment_variables" {
  for_each = local.protected_env_vars_map

  name       = each.value.env_var_data.name
  project_id = each.value.project_id

  # Map environment values (same logic as unprotected)
  environment_values = {
    for env_key, env_value in each.value.env_var_data.environment_values :
    env_key == "project" ? "project" : (
      contains(keys(local.env_name_to_resource_key), "${each.value.project_key}_${env_key}") ?
      local.env_resolved_name[local.env_name_to_resource_key["${each.value.project_key}_${env_key}"]] :
      env_key
      ) => (
      can(regex("^secret_", env_value)) ?
      lookup(var.token_map, replace(env_value, "secret_", ""), env_value) :
      env_value
    )
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Job-level environment variable overrides
# These override environment-specific values for specific jobs
locals {
  # Collect all job overrides from job definitions
  # Only include overrides for jobs we actually create (jobs_creatable_map),
  # otherwise references to dbtcloud_job.jobs[job_key] can fail.
  job_env_var_overrides = flatten([
    for job_key, job_item in local.jobs_creatable_map : [
      for override_key, override_value in try(job_item.job_data.environment_variable_overrides, {}) : {
        job_key           = job_key
        project_id        = job_item.project_id
        job_definition_id = dbtcloud_job.jobs[job_key].job_id
        env_var_name      = override_key
        env_var_value     = override_value
      }
    ]
  ])
}

resource "dbtcloud_environment_variable_job_override" "job_overrides" {
  for_each = {
    for override in local.job_env_var_overrides :
    "${override.job_key}_${override.env_var_name}" => override
  }

  project_id        = each.value.project_id
  job_definition_id = each.value.job_definition_id
  name              = each.value.env_var_name
  raw_value = (
    # If value starts with secret prefix, look it up in token_map
    can(regex("^secret_", each.value.env_var_value)) ?
    lookup(var.token_map, replace(each.value.env_var_value, "secret_", ""), each.value.env_var_value) :
    each.value.env_var_value
  )

  depends_on = [
    dbtcloud_environment_variable.environment_variables,
    dbtcloud_environment_variable.protected_environment_variables,
    dbtcloud_job.jobs
  ]
}

