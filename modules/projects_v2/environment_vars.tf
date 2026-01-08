#############################################
# Environment Variables
# 
# Creates project-scoped environment variables with
# environment-specific values and job-level overrides.
#############################################

locals {
  # Flatten all environment variables across all projects
  all_environment_variables = flatten([
    for project in var.projects : [
      for env_var in try(project.environment_variables, []) : {
        project_key  = project.key
        project_id   = dbtcloud_project.projects[project.key].id
        env_var_key  = env_var.name
        env_var_data = env_var
      }
    ]
  ])

  # Create map keyed by project_key_env_var_name
  env_vars_map = {
    for item in local.all_environment_variables :
    "${item.project_key}_${item.env_var_key}" => item
  }

  # Build a map of environment names to environment resource keys
  # This maps "project_key_env_name" => environment resource key
  # Used to create implicit dependencies by referencing created environment resources
  env_name_to_resource_key = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_data.name}" => "${item.project_key}_${item.env_key}"
  }
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
      # Reference the created environment resource to create implicit dependency
      # Use the environment's name (which matches what the API expects)
      dbtcloud_environment.environments[local.env_name_to_resource_key["${each.value.project_key}_${env_key}"]].name :
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

# Job-level environment variable overrides
# These override environment-specific values for specific jobs
locals {
  # Collect all job overrides from job definitions
  job_env_var_overrides = flatten([
    for job_key, job_item in local.jobs_map : [
      for override_key, override_value in try(job_item.job_data.environment_variable_overrides, {}) : {
        job_key       = job_key
        job_definition_id = dbtcloud_job.jobs[job_key].id
        env_var_name  = override_key
        env_var_value = override_value
        project_key   = job_item.project_key
      }
    ]
  ])
}

resource "dbtcloud_environment_variable_job_override" "job_overrides" {
  for_each = {
    for override in local.job_env_var_overrides :
    "${override.job_key}_${override.env_var_name}" => override
  }

  project_id        = each.value.project_key
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
    dbtcloud_job.jobs
  ]
}

