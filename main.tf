#############################################
# Root Module - dbt Cloud Resources
#
# Orchestrates all dbt Cloud resources from a YAML file.
# Supports both single-project (project:) and multi-project (projects:) YAML.
# Account-scoped resources are created first, then project-scoped resources.
#############################################

#############################################
# YAML Configuration Validation
# All validation logic lives in validation.tf.
# This resource fails at plan time if any errors are found,
# reporting all issues together in one message.
#############################################

resource "terraform_data" "validate_yaml_config" {
  lifecycle {
    precondition {
      condition     = length(local._all_validation_errors) == 0
      error_message = "dbt Cloud YAML configuration has ${length(local._all_validation_errors)} error(s):\n\n${join("\n\n", [for i, e in local._all_validation_errors : "  ${i + 1}. ${e}"])}"
    }
  }
}

#############################################
# Account-Level Features
#############################################

module "account_features" {
  count  = try(local.yaml_content.account_features, null) != null ? 1 : 0
  source = "./modules/account_features"

  features = try(local.yaml_content.account_features, null)
}

#############################################
# Account-Level: Global Connections
#############################################

module "global_connections" {
  count  = length(try(local.yaml_content.global_connections, [])) > 0 ? 1 : 0
  source = "./modules/global_connections"

  connections_data       = try(local.yaml_content.global_connections, [])
  connection_credentials = var.connection_credentials
  privatelink_endpoints  = try(local.yaml_content.privatelink_endpoints, [])
}

#############################################
# Account-Level: Data lookups (LOOKUP: + GitHub installations)
#############################################

module "data_lookups" {
  count  = length(local._lookup_connection_ref_strings) > 0 || var.dbt_pat != null ? 1 : 0
  source = "./modules/data_lookups"

  projects     = local.projects
  dbt_pat      = var.dbt_pat
  dbt_host_url = var.dbt_host_url
}

#############################################
# Account-Level: Groups
#############################################

module "groups" {
  count  = length(try(local.yaml_content.groups, [])) > 0 ? 1 : 0
  source = "./modules/groups"

  groups_data                     = try(local.yaml_content.groups, [])
  skip_global_project_permissions = var.skip_global_project_permissions
}

#############################################
# Account-Level: User Groups (user ↔ group assignment)
#############################################

module "user_groups" {
  count  = length(try(local.yaml_content.user_groups, [])) > 0 ? 1 : 0
  source = "./modules/user_groups"

  user_groups_data = try(local.yaml_content.user_groups, [])
  group_ids        = length(try(local.yaml_content.groups, [])) > 0 ? module.groups[0].group_ids : {}
}

#############################################
# Account-Level: Notifications
#############################################

module "notifications" {
  count  = length(try(local.yaml_content.notifications, [])) > 0 ? 1 : 0
  source = "./modules/notifications"

  notifications_data = try(local.yaml_content.notifications, [])
}

#############################################
# Account-Level: OAuth Configurations
#############################################

module "oauth_configurations" {
  count  = length(try(local.yaml_content.oauth_configurations, [])) > 0 ? 1 : 0
  source = "./modules/oauth_configurations"

  oauth_data           = try(local.yaml_content.oauth_configurations, [])
  oauth_client_secrets = var.oauth_client_secrets
}

#############################################
# Account-Level: IP Restrictions
#############################################

module "ip_restrictions" {
  count  = length(try(local.yaml_content.ip_restrictions, [])) > 0 ? 1 : 0
  source = "./modules/ip_restrictions"

  ip_rules_data = try(local.yaml_content.ip_restrictions, [])
}

#############################################
# Project Setup
#############################################

module "project" {
  source = "./modules/project"

  projects    = local.projects
  target_name = var.target_name
}

#############################################
# Account-Level: Service Tokens
# Declared after project so permissions[].project_key resolves via project_ids.
#############################################

module "service_tokens" {
  count  = length(try(local.yaml_content.service_tokens, [])) > 0 ? 1 : 0
  source = "./modules/service_tokens"

  service_tokens_data             = try(local.yaml_content.service_tokens, [])
  project_ids                     = module.project.project_ids
  skip_global_project_permissions = var.skip_global_project_permissions
}

#############################################
# Repository Configuration
#############################################

module "repository" {
  source = "./modules/repository"
  providers = {
    dbtcloud = dbtcloud.pat_provider
  }

  projects                        = local.projects
  project_ids                     = module.project.project_ids
  dbt_pat                         = var.dbt_pat
  enable_gitlab_deploy_token      = var.enable_gitlab_deploy_token
  github_installation_by_owner    = length(module.data_lookups) > 0 ? module.data_lookups[0].github_installation_by_owner : {}
  github_installation_fallback_id = length(module.data_lookups) > 0 ? module.data_lookups[0].github_installation_fallback_id : null
  privatelink_endpoints           = try(local.yaml_content.privatelink_endpoints, [])
}

module "project_repository" {
  source = "./modules/project_repository"

  project_ids               = module.project.project_ids
  repository_ids            = module.repository.repository_ids
  protected_repository_keys = module.repository.protected_repository_keys
}

#############################################
# Extended Attributes (must precede environments)
#############################################

module "extended_attributes" {
  count  = length(flatten([for p in local.projects : try(p.extended_attributes, [])])) > 0 ? 1 : 0
  source = "./modules/extended_attributes"

  projects    = local.projects
  project_ids = module.project.project_ids
}

#############################################
# Credentials
#############################################

module "credentials" {
  source = "./modules/credentials"

  projects                = local.projects
  project_ids             = module.project.project_ids
  token_map               = var.token_map
  environment_credentials = var.environment_credentials
}

#############################################
# Environments
#############################################

module "environments" {
  source = "./modules/environments"

  projects               = local.projects
  project_ids            = module.project.project_ids
  credential_ids         = module.credentials.credential_ids
  global_connection_ids  = local.global_connection_ids_effective
  extended_attribute_ids = length(flatten([for p in local.projects : try(p.extended_attributes, [])])) > 0 ? module.extended_attributes[0].extended_attribute_ids : {}
}

#############################################
# Jobs
#############################################

module "jobs" {
  source = "./modules/jobs"

  projects        = local.projects
  project_ids     = module.project.project_ids
  environment_ids = module.environments.environment_ids
}

#############################################
# Environment Variables
#############################################

module "environment_variables" {
  source = "./modules/environment_variables"

  projects    = local.projects
  project_ids = module.project.project_ids
  token_map   = var.token_map

  depends_on = [module.environments]
}

#############################################
# Environment Variable Job Overrides
#############################################

module "environment_variable_job_overrides" {
  source = "./modules/environment_variable_job_overrides"

  projects    = local.projects
  project_ids = module.project.project_ids
  job_ids     = module.jobs.job_ids

  depends_on = [module.environment_variables]
}

#############################################
# Profiles (links connection + credential + extended_attributes)
#############################################

module "profiles" {
  count  = length(flatten([for p in local.projects : try(p.profiles, [])])) > 0 ? 1 : 0
  source = "./modules/profiles"

  projects                    = local.projects
  project_ids                 = module.project.project_ids
  global_connection_ids       = local.global_connection_ids_effective
  credential_ids              = module.credentials.credential_ids
  credential_ids_by_source_id = module.credentials.credential_ids_by_source_id
  extended_attribute_ids      = length(flatten([for p in local.projects : try(p.extended_attributes, [])])) > 0 ? module.extended_attributes[0].extended_attribute_ids : {}
}

#############################################
# Lineage Integrations
#############################################

module "lineage_integrations" {
  count  = length(flatten([for p in local.projects : try(p.lineage_integrations, [])])) > 0 ? 1 : 0
  source = "./modules/lineage_integrations"

  projects       = local.projects
  project_ids    = module.project.project_ids
  lineage_tokens = var.lineage_tokens
}

#############################################
# Project Artefacts (docs job + freshness job links)
#############################################

module "project_artefacts" {
  count  = length([for p in local.projects : p if try(p.artefacts, null) != null]) > 0 ? 1 : 0
  source = "./modules/project_artefacts"

  projects    = local.projects
  project_ids = module.project.project_ids
  job_ids     = module.jobs.job_ids

  depends_on = [module.jobs]
}

#############################################
# Semantic Layer
#############################################

module "semantic_layer" {
  count  = length([for p in local.projects : p if try(p.semantic_layer, null) != null]) > 0 ? 1 : 0
  source = "./modules/semantic_layer"

  projects        = local.projects
  project_ids     = module.project.project_ids
  environment_ids = module.environments.environment_ids
}
