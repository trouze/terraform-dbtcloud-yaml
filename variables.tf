#############################################
# dbt Cloud Configuration
#############################################

variable "dbt_account_id" {
  description = "dbt Cloud account ID"
  type        = number
  default     = null

  validation {
    condition     = var.dbt_account_id == null || var.dbt_account_id > 0
    error_message = "dbt_account_id must be a positive integer"
  }
}

variable "dbt_token" {
  description = "dbt Cloud API token for authentication"
  type        = string
  sensitive   = true
  default     = null

  validation {
    condition     = var.dbt_token == null || length(var.dbt_token) > 0
    error_message = "dbt_token cannot be empty"
  }
}

variable "dbt_pat" {
  description = "dbt Cloud personal access token for GitHub App integration discovery (service tokens cannot access the integrations API)"
  type        = string
  sensitive   = true
  default     = null
}

variable "dbt_host_url" {
  description = "dbt Cloud host URL (e.g., https://cloud.getdbt.com or custom domain). Required by the Terraform dbtcloud provider; version: 1 YAML account.host_url is used only for HTTP lookups (module data_lookups) when this variable is null — mirror account.host_url here for real applies."
  type        = string
  default     = null

  validation {
    condition     = var.dbt_host_url == null || can(regex("^https://", var.dbt_host_url))
    error_message = "dbt_host_url must start with https://"
  }
}

#############################################
# YAML Configuration
#############################################

variable "yaml_file" {
  description = "Path to the YAML file defining dbt Cloud resources. Must set version: 1 with account, globals.* (connections, optional groups, service_tokens, notifications, privatelink_endpoints), and projects[] — see schemas/v1.json. Root locals hoist globals into top-level keys modules consume and normalize environment_variables[].environment_values from maps to lists."
  type        = string

  validation {
    condition     = can(file(var.yaml_file))
    error_message = "yaml_file '${var.yaml_file}' does not exist or cannot be read. Check the path relative to where you run terraform."
  }

  validation {
    condition     = can(yamldecode(file(var.yaml_file)))
    error_message = "yaml_file '${var.yaml_file}' exists but cannot be parsed as YAML. Check for indentation errors or invalid syntax."
  }
}

variable "target_name" {
  description = "Default target name for the dbt project (e.g., 'dev', 'prod')"
  type        = string
  default     = ""
}

#############################################
# Credentials
#############################################

variable "token_map" {
  description = "Map of token names to secret values. Used for legacy Databricks credential.token_name in YAML and for jobs[].environment_variable_overrides values prefixed with secret_ (lookup key is the string after the prefix)."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "connection_credentials" {
  description = "Map of global connection keys to their OAuth/auth credential objects (client_id, client_secret, private_key, etc.)"
  type        = map(any)
  default     = {}
  sensitive   = true
}

variable "environment_credentials" {
  description = "Map of credential keys to warehouse credential objects. Key format: project_key_env_key for environments, or project_key_profile_key for standalone profile-owned credentials. Supports 14 warehouse types via credential_type field."
  type        = map(any)
  default     = {}
  sensitive   = true
}

variable "oauth_client_secrets" {
  description = "Map of OAuth configuration keys to their client secrets"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "lineage_tokens" {
  description = "Map of lineage integration keys to their authentication tokens (Tableau, Looker, etc.)"
  type        = map(string)
  default     = {}
  sensitive   = true
}

#############################################
# Repository Options
#############################################

variable "enable_gitlab_deploy_token" {
  description = "Preserve native GitLab deploy_token strategy. Defaults to false due to a known API limitation (GitlabGetError on some accounts). Set to true only when GitLab OAuth access is confirmed."
  type        = bool
  default     = false
}

variable "skip_global_project_permissions" {
  description = "When true, account-level group permissions from YAML are applied as all_projects-only blocks so Terraform does not add edges to project resources (scoped adoption of globals)."
  type        = bool
  default     = false
}

#############################################
# Locals
#############################################

locals {
  _raw_yaml = yamldecode(file(var.yaml_file))

  # version: 1 — hoist globals into the top-level keys root modules read.
  yaml_content = merge(
    {
      for k, v in local._raw_yaml : k => v
      if !contains([
        "version",
        "account",
        "globals",
        "metadata",
        "projects",
        "global_connections",
        "privatelink_endpoints",
        "service_tokens",
        "groups",
        "notifications",
      ], k)
    },
    {
      global_connections    = try(local._raw_yaml.globals.connections, [])
      privatelink_endpoints = try(local._raw_yaml.globals.privatelink_endpoints, [])
      projects              = local._raw_yaml.projects
      service_tokens        = try(local._raw_yaml.globals.service_tokens, [])
      groups                = try(local._raw_yaml.globals.groups, [])
      notifications         = try(local._raw_yaml.globals.notifications, [])
    },
  )

  # environment_variables[].environment_values: map env_key → value (YAML) → list of { env, value } for modules.
  projects = [
    for p in local.yaml_content.projects : merge(p, {
      environment_variables = [
        for ev in try(p.environment_variables, []) : merge(ev, {
          environment_values = [
            for k, v in try(tomap(ev.environment_values), tomap({})) : { env = k, value = tostring(v) }
          ]
        })
      ]
    })
  ]

  # HTTP helpers (module data_lookups): var.dbt_host_url, then version: 1 account.host_url, then public default (matches modules/data_lookups).
  dbt_host_url_effective = coalesce(
    var.dbt_host_url,
    try(local._raw_yaml.account.host_url, null) != null && try(trimspace(tostring(local._raw_yaml.account.host_url)), "") != "" ? trimspace(tostring(local._raw_yaml.account.host_url)) : null,
    "https://cloud.getdbt.com",
  )

  # Gating for module.data_lookups — keep in sync with modules/data_lookups LOOKUP extraction.
  _lookup_connection_ref_strings = toset([
    for conn_ref in flatten([
      for p in local.projects : concat(
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

  # Merged map for environments/profiles: Terraform-managed global_connections + pre-existing account connections (LOOKUP:…).
  global_connection_ids_effective = merge(
    length(module.data_lookups) > 0 ? module.data_lookups[0].lookup_connection_ids : {},
    length(try(local.yaml_content.global_connections, [])) > 0 ? module.global_connections[0].connection_ids : {},
  )
}
