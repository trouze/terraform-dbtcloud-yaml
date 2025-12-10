#############################################
# Root Module - dbt Cloud Resources
# 
# This module orchestrates the creation of
# dbt Cloud projects, environments, jobs,
# credentials, and environment variables
# from a YAML configuration file.
#
# Supports both v1 (single-project) and v2 (multi-project) schemas.
#############################################

#############################################
# Schema Version Detection
#############################################

locals {
  # Use try() to handle case where yaml_file might not be set during module loading
  yaml_content   = try(yamldecode(file(var.yaml_file)), {})
  schema_version = try(local.yaml_content.version, 1) # Default to v1 if not specified

  # v1 schema (single project)
  project_config_v1 = local.schema_version == 1 ? try(local.yaml_content.project, null) : null

  # v2 schema (multi-project)
  account_config_v2 = local.schema_version == 2 ? try(local.yaml_content.account, null) : null
  globals_v2        = local.schema_version == 2 ? try(local.yaml_content.globals, null) : null
  projects_v2       = local.schema_version == 2 ? try(local.yaml_content.projects, []) : []
}

#############################################
# v1 Path (Single Project) - Existing Logic
#############################################

module "project" {
  count  = local.schema_version == 1 ? 1 : 0
  source = "./modules/project"

  project_name = local.project_config_v1.name
  target_name  = var.target_name
}

#############################################
# 2. Repository Configuration (v1 only)
#############################################

module "repository" {
  count  = local.schema_version == 1 ? 1 : 0
  source = "./modules/repository"
  providers = {
    dbtcloud = dbtcloud.pat_provider
  }

  repository_data = local.project_config_v1.repository
  project_id      = module.project[0].project_id
}

module "project_repository" {
  count  = local.schema_version == 1 ? 1 : 0
  source = "./modules/project_repository"

  repository_id = module.repository[0].project_repository_id
  project_id    = module.project[0].project_id
}

#############################################
# 3. Credentials (v1 only)
#############################################

module "credentials" {
  count  = local.schema_version == 1 ? 1 : 0
  source = "./modules/credentials"

  environments_data = local.project_config_v1.environments
  project_id        = module.project[0].project_id
  token_map         = var.token_map
}

#############################################
# 4. Environments (v1 only)
#############################################

module "environments" {
  count  = local.schema_version == 1 ? 1 : 0
  source = "./modules/environments"

  project_id        = module.project[0].project_id
  environments_data = local.project_config_v1.environments
  credential_ids    = module.credentials[0].credential_ids
}

#############################################
# 5. Jobs (v1 only)
#############################################

module "jobs" {
  count  = local.schema_version == 1 ? 1 : 0
  source = "./modules/jobs"

  project_id        = module.project[0].project_id
  environments_data = local.project_config_v1.environments
  environment_ids   = module.environments[0].environment_ids
}

#############################################
# 6. Environment Variables (v1 only)
#############################################

module "environment_variables" {
  count  = local.schema_version == 1 ? 1 : 0
  source = "./modules/environment_variables"

  project_id            = module.project[0].project_id
  environment_variables = lookup(local.project_config_v1, "environment_variables", {})
  environment_ids       = module.environments[0].environment_ids
  token_map             = var.token_map

  depends_on = [module.environments]
}

#############################################
# 7. Environment Variable Job Overrides (v1 only)
#############################################

module "environment_variable_job_overrides" {
  count  = local.schema_version == 1 ? 1 : 0
  source = "./modules/environment_variable_job_overrides"

  project_id        = module.project[0].project_id
  environments_data = local.project_config_v1.environments
  job_ids           = module.jobs[0].job_ids

  depends_on = [module.environment_variables]
}

#############################################
# v2 Path (Multi-Project) - New Logic
#############################################

module "projects_v2" {
  count  = local.schema_version == 2 ? 1 : 0
  source = "./modules/projects_v2"

  account        = local.account_config_v2
  globals        = local.globals_v2
  projects       = local.projects_v2
  token_map      = var.token_map
  dbt_account_id = var.dbt_account_id
}
