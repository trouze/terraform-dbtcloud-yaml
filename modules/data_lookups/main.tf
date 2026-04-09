terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.9"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.0"
    }
  }
}

#############################################
# LOOKUP: global connection resolution
# Matches account global connections by name (suffix after LOOKUP:).
#############################################

locals {
  lookup_connection_keys = toset([
    for conn_ref in flatten([
      for p in var.projects : concat(
        [
          for env in try(p.environments, []) :
          try(env.connection, null)
          if try(env.connection, null) != null && startswith(tostring(env.connection), "LOOKUP:")
        ],
        [
          for prof in try(p.profiles, []) :
          try(prof.connection_key, null)
          if try(prof.connection_key, null) != null && startswith(tostring(prof.connection_key), "LOOKUP:")
        ]
      )
    ]) :
    tostring(conn_ref) if startswith(tostring(conn_ref), "LOOKUP:")
  ])

  needs_global_connections_data = length(local.lookup_connection_keys) > 0

  # Base URL for dbt Cloud Admin API (integrations); strip accidental /api suffix.
  dbt_host_url_raw = coalesce(var.dbt_host_url, "https://cloud.getdbt.com")
  dbt_host_url     = replace(local.dbt_host_url_raw, "/api", "")

  # Optional: repository field as a scalar LOOKUP (v2 / importer shape); object repos are ignored.
  lookup_repository_keys = toset([
    for repo_ref in [
      for p in var.projects :
      p.repository
      if can(regex("^LOOKUP:", try(tostring(p.repository), "")))
    ] : try(tostring(repo_ref), "") if startswith(try(tostring(repo_ref), ""), "LOOKUP:")
  ])
}

data "dbtcloud_global_connections" "all" {
  count = local.needs_global_connections_data ? 1 : 0
}

locals {
  lookup_connection_ids = {
    for lookup_key in local.lookup_connection_keys :
    lookup_key => try(
      tostring([
        for conn in data.dbtcloud_global_connections.all[0].connections :
        conn.id if try(conn.name, null) == replace(lookup_key, "LOOKUP:", "")
      ][0]),
      null
    )
  }
}

#############################################
# GitHub App installations (account integrations API)
# Requires PAT — not available on service tokens.
#############################################

data "http" "github_installations" {
  count = var.dbt_pat != null ? 1 : 0

  url = format("%s/api/v2/integrations/github/installations/", local.dbt_host_url)
  request_headers = {
    Authorization = format("Bearer %s", var.dbt_pat)
  }
}

locals {
  github_installations_raw = length(data.http.github_installations) > 0 ? try(
    tolist(jsondecode(data.http.github_installations[0].response_body)),
    []
  ) : []

  github_installations = [
    for inst in local.github_installations_raw :
    inst if can(regex("github", try(inst.access_tokens_url, "")))
  ]

  github_installation_by_owner = {
    for inst in local.github_installations :
    lower(try(inst.account.login, "")) => inst.id
    if try(inst.account.login, "") != ""
  }

  github_installation_fallback_id = length(local.github_installations) > 0 ? local.github_installations[0].id : null
}
