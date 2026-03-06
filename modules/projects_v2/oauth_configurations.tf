#############################################
# OAuth Configurations (account-level, guarded)
# client_secret is sensitive — sourced from var.oauth_client_secrets.
#############################################

locals {
  unprotected_oauth_map = {
    for key, oauth in local.oauth_configurations_map :
    key => oauth if !try(oauth.protected, false)
  }
  protected_oauth_map = {
    for key, oauth in local.oauth_configurations_map :
    key => oauth if try(oauth.protected, false)
  }
}

resource "dbtcloud_oauth_configuration" "configs" {
  for_each = local.unprotected_oauth_map

  name          = each.value.name
  type          = try(each.value.type, null)
  client_id     = try(each.value.client_id, null)
  client_secret = lookup(var.oauth_client_secrets, each.key, try(each.value.client_secret, ""))
  authorize_url = try(each.value.authorize_url, null)
  token_url     = try(each.value.token_url, null)
  redirect_uri  = try(each.value.redirect_uri, null)

  resource_metadata = {
    source_id       = try(each.value.id, null)
    source_identity = "OAUTH:${each.key}"
    source_key      = each.key
    source_name     = each.value.name
  }
}

resource "dbtcloud_oauth_configuration" "protected_configs" {
  for_each = local.protected_oauth_map

  name          = each.value.name
  type          = try(each.value.type, null)
  client_id     = try(each.value.client_id, null)
  client_secret = lookup(var.oauth_client_secrets, each.key, try(each.value.client_secret, ""))
  authorize_url = try(each.value.authorize_url, null)
  token_url     = try(each.value.token_url, null)
  redirect_uri  = try(each.value.redirect_uri, null)

  resource_metadata = {
    source_id       = try(each.value.id, null)
    source_identity = "OAUTH:${each.key}"
    source_key      = each.key
    source_name     = each.value.name
  }

  lifecycle {
    prevent_destroy = true
  }
}
