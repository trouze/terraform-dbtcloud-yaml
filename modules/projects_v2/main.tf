#############################################
# Projects v2 Module - Main Entry Point
# 
# This module orchestrates multi-project dbt Cloud resource creation
# from v2 YAML schema with global resources and project-scoped resources.
#############################################

locals {
  # Create maps keyed by resource keys for easy lookup
  connections_map = {
    for conn in try(var.globals.connections, []) :
    conn.key => conn
  }

  repositories_map = {
    for repo in try(var.globals.repositories, []) :
    repo.key => repo
  }

  service_tokens_map = {
    for token in try(var.globals.service_tokens, []) :
    token.key => token
  }

  groups_map = {
    for group in try(var.globals.groups, []) :
    group.key => group
  }

  notifications_map = {
    for notif in try(var.globals.notifications, []) :
    notif.key => notif
  }

  privatelink_endpoints_map = {
    for ple in try(var.globals.privatelink_endpoints, []) :
    ple.key => ple
  }

  ip_restrictions_map = {
    for rule in try(var.globals.ip_restrictions, []) :
    rule.key => rule
  }

  oauth_configurations_map = {
    for oauth in try(var.globals.oauth_configurations, []) :
    oauth.key => oauth
  }

  user_groups_map = {
    for ug in try(var.globals.user_groups, []) :
    ug.key => ug
  }

  account_features = try(var.globals.account_features, null)

  # Extract LOOKUP placeholders from connection references
  lookup_connections = toset([
    for conn_ref in flatten([
      for project in var.projects : [
        for env in project.environments :
        env.connection if can(regex("^LOOKUP:", tostring(env.connection)))
      ]
    ]) :
    conn_ref if startswith(tostring(conn_ref), "LOOKUP:")
  ])

  # Extract LOOKUP placeholders from repository references
  lookup_repositories = toset([
    for repo_ref in [
      for project in var.projects :
      project.repository if can(regex("^LOOKUP:", tostring(project.repository)))
    ] :
    repo_ref if startswith(tostring(repo_ref), "LOOKUP:")
  ])
}

