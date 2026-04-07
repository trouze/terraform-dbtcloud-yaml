terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.8"
    }
  }
}

#############################################
# OAuth configurations (account-level)
# client_secret is sensitive — sourced from var.oauth_client_secrets (or optional YAML).
#############################################

locals {
  # COMPAT(v1-schema): for_each key from key or legacy name — align with v2 schema when canonical.
  oauth_configurations_map = {
    for o in var.oauth_data :
    try(o.key, o.name) => o
  }
  unprotected_oauth_map = {
    for key, oauth in local.oauth_configurations_map :
    key => oauth if !try(oauth.protected, false)
  }
  protected_oauth_map = {
    for key, oauth in local.oauth_configurations_map :
    key => oauth if try(oauth.protected, false)
  }
}

resource "dbtcloud_oauth_configuration" "oauth_configurations" {
  for_each = local.unprotected_oauth_map

  name      = each.value.name
  type      = try(each.value.type, null)
  client_id = try(each.value.client_id, null)
  # COMPAT(v1-schema): secrets from root map (preferred) or inline YAML — v2 schema may narrow to one path.
  client_secret = lookup(var.oauth_client_secrets, each.key, try(each.value.client_secret, ""))
  authorize_url = try(each.value.authorize_url, null)
  token_url     = try(each.value.token_url, null)
  redirect_uri  = try(each.value.redirect_uri, null)

  application_id_uri = try(each.value.application_id_uri, null)

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/oauth_configurations.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "OAUTH:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }
}

resource "dbtcloud_oauth_configuration" "protected_oauth_configurations" {
  for_each = local.protected_oauth_map

  name      = each.value.name
  type      = try(each.value.type, null)
  client_id = try(each.value.client_id, null)
  # COMPAT(v1-schema): secrets from root map (preferred) or inline YAML — v2 schema may narrow to one path.
  client_secret = lookup(var.oauth_client_secrets, each.key, try(each.value.client_secret, ""))
  authorize_url = try(each.value.authorize_url, null)
  token_url     = try(each.value.token_url, null)
  redirect_uri  = try(each.value.redirect_uri, null)

  application_id_uri = try(each.value.application_id_uri, null)

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/oauth_configurations.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "OAUTH:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }

  lifecycle {
    prevent_destroy = true
  }
}
