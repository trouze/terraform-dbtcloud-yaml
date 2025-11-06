#############################################
# Root Module - dbt Cloud Resources
# 
# This module orchestrates the creation of
# dbt Cloud projects, environments, jobs,
# credentials, and environment variables
# from a YAML configuration file.
#############################################

#############################################
# 1. Project Setup
#############################################

module "project" {
  source = "${path.module}/modules/project"

  project_name = local.project_config.project.name
  target_name  = var.target_name
}

#############################################
# 2. Repository Configuration
#############################################

module "repository" {
  source = "${path.module}/modules/repository"
  providers = {
    dbtcloud = dbtcloud.pat_provider
  }

  repository_data = local.project_config.project.repository
  project_id      = module.project.project_id
}

module "project_repository" {
  source = "${path.module}/modules/project_repository"

  repository_id = module.repository.project_repository_id
  project_id    = module.project.project_id
}

#############################################
# 3. Credentials
#############################################

module "credentials" {
  source = "${path.module}/modules/credentials"

  environments_data = local.project_config.project.environments
  project_id        = module.project.project_id
  token_map         = var.token_map
}

#############################################
# 4. Environments
#############################################

module "environments" {
  source = "${path.module}/modules/environments"

  project_id        = module.project.project_id
  environments_data = local.project_config.project.environments
  credential_ids    = module.credentials.credential_ids
}

#############################################
# 5. Jobs
#############################################

module "jobs" {
  source = "${path.module}/modules/jobs"

  project_id        = module.project.project_id
  environments_data = local.project_config.project.environments
  environment_ids   = module.environments.environment_ids
}

#############################################
# 6. Environment Variables
#############################################

module "environment_variables" {
  source = "${path.module}/modules/environment_variables"

  project_id             = module.project.project_id
  environment_variables  = lookup(local.project_config.project, "environment_variables", {})
  environment_ids        = module.environments.environment_ids
  token_map              = var.token_map

  depends_on = [module.environments]
}

#############################################
# 7. Environment Variable Job Overrides
#############################################

module "environment_variable_job_overrides" {
  source = "${path.module}/modules/environment_variable_job_overrides"

  project_id        = module.project.project_id
  environments_data = local.project_config.project.environments
  job_ids           = module.jobs.job_ids

  depends_on = [module.environment_variables]
}
