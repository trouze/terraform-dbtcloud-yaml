#############################################
# Project Outputs
#############################################

output "project_ids" {
  description = "Map of project key to dbt Cloud project ID"
  value       = module.project.project_ids
}

#############################################
# Repository Outputs
#############################################

output "repository_ids" {
  description = "Map of project key to repository ID"
  value       = module.repository.repository_ids
}

#############################################
# Environment Outputs
#############################################

output "environment_ids" {
  description = "Map of composite key (project_key_env_key) to dbt Cloud environment ID"
  value       = module.environments.environment_ids
}

#############################################
# Credential Outputs
#############################################

output "credential_ids" {
  description = "Map of composite key (project_key_env_key or project_key_profile_key) to credential ID"
  value       = module.credentials.credential_ids
}

#############################################
# Job Outputs
#############################################

output "job_ids" {
  description = "Map of composite key (project_key_job_key) to dbt Cloud job ID"
  value       = module.jobs.job_ids
}

#############################################
# Account-Level Outputs
#############################################

output "connection_ids" {
  description = "Map of global connection key (and LOOKUP:… placeholders) to dbt Cloud connection ID — merged managed global_connections + data_lookups"
  value       = local.global_connection_ids_effective
}

output "lookup_connection_ids" {
  description = "Subset of connection_ids from LOOKUP:… resolution only (empty if module.data_lookups not used)"
  value       = length(module.data_lookups) > 0 ? module.data_lookups[0].lookup_connection_ids : {}
}

output "github_installation_by_owner" {
  description = "GitHub App installation id by org/user login (from dbt integrations API when dbt_pat is set)"
  value       = length(module.data_lookups) > 0 ? module.data_lookups[0].github_installation_by_owner : {}
}

output "github_installation_fallback_id" {
  description = "First GitHub installation id when owner-based match is not used"
  value       = length(module.data_lookups) > 0 ? module.data_lookups[0].github_installation_fallback_id : null
}

output "service_token_ids" {
  description = "Map of service token key to dbt Cloud service token ID"
  value       = length(try(local.yaml_content.service_tokens, [])) > 0 ? module.service_tokens[0].service_token_ids : {}
}

output "group_ids" {
  description = "Map of group key to dbt Cloud group ID"
  value       = length(try(local.yaml_content.groups, [])) > 0 ? module.groups[0].group_ids : {}
}

output "notification_ids" {
  description = "Map of notification key to dbt Cloud notification ID"
  value       = length(try(local.yaml_content.notifications, [])) > 0 ? module.notifications[0].notification_ids : {}
}

output "oauth_configuration_ids" {
  description = "Map of OAuth configuration key to dbt Cloud OAuth configuration ID"
  value       = length(try(local.yaml_content.oauth_configurations, [])) > 0 ? module.oauth_configurations[0].oauth_configuration_ids : {}
}

output "ip_rule_ids" {
  description = "Map of IP rule key to dbt Cloud IP restriction rule ID"
  value       = length(try(local.yaml_content.ip_restrictions, [])) > 0 ? module.ip_restrictions[0].ip_rule_ids : {}
}

#############################################
# Project-Scoped Outputs
#############################################

output "extended_attribute_ids" {
  description = "Map of composite key (project_key_ea_key) to extended_attributes resource ID"
  value       = length(flatten([for p in local.projects : try(p.extended_attributes, [])])) > 0 ? module.extended_attributes[0].extended_attribute_ids : {}
}

output "profile_ids" {
  description = "Map of composite key (project_key_profile_key) to dbt Cloud profile ID"
  value       = length(flatten([for p in local.projects : try(p.profiles, [])])) > 0 ? module.profiles[0].profile_ids : {}
}

output "lineage_integration_ids" {
  description = "Map of composite key (project_key_integration_key) to lineage integration ID"
  value       = length(flatten([for p in local.projects : try(p.lineage_integrations, [])])) > 0 ? module.lineage_integrations[0].lineage_integration_ids : {}
}
