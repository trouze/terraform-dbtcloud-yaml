terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  connections_map = {
    for conn in var.connections_data :
    try(conn.key, conn.name) => conn
  }

  protected_connections_map = {
    for k, conn in local.connections_map :
    k => conn
    if try(conn.protected, false) == true
  }

  unprotected_connections_map = {
    for k, conn in local.connections_map :
    k => conn
    if try(conn.protected, false) != true
  }
}

#############################################
# Unprotected Global Connections
#############################################

resource "dbtcloud_global_connection" "connections" {
  for_each = local.unprotected_connections_map

  name = each.value.name

  private_link_endpoint_id = try(each.value.private_link_endpoint_id, null)

  databricks = try(each.value.type, "") == "databricks" ? {
    host          = try(each.value.host, "")
    http_path     = try(each.value.http_path, "")
    catalog       = try(each.value.catalog, null)
    client_id     = try(var.connection_credentials[each.key].client_id, null)
    client_secret = try(var.connection_credentials[each.key].client_secret, null)
  } : null

  snowflake = try(each.value.type, "") == "snowflake" ? {
    account                   = try(each.value.account, "")
    database                  = try(each.value.database, "")
    warehouse                 = try(each.value.warehouse, "")
    role                      = try(each.value.role, null)
    client_session_keep_alive = try(each.value.client_session_keep_alive, false)
    allow_sso                 = try(each.value.allow_sso, false)
    oauth_client_id           = try(var.connection_credentials[each.key].oauth_client_id, null)
    oauth_client_secret       = try(var.connection_credentials[each.key].oauth_client_secret, null)
  } : null

  bigquery = try(each.value.type, "") == "bigquery" ? {
    gcp_project_id              = try(each.value.gcp_project_id, "")
    private_key_id              = try(var.connection_credentials[each.key].private_key_id, null)
    private_key                 = try(var.connection_credentials[each.key].private_key, null)
    client_email                = try(each.value.client_email, null)
    client_id                   = try(each.value.client_id, null)
    auth_uri                    = try(each.value.auth_uri, null)
    token_uri                   = try(each.value.token_uri, null)
    auth_provider_x509_cert_url = try(each.value.auth_provider_x509_cert_url, null)
    client_x509_cert_url        = try(each.value.client_x509_cert_url, null)
    timeout_seconds             = try(each.value.timeout_seconds, null)
    location                    = try(each.value.location, null)
  } : null

  postgres = try(each.value.type, "") == "postgres" ? {
    hostname = try(each.value.hostname, "")
    dbname   = try(each.value.dbname, "")
    port     = try(each.value.port, 5432)
  } : null

  redshift = try(each.value.type, "") == "redshift" ? {
    hostname = try(each.value.hostname, "")
    dbname   = try(each.value.dbname, "")
    port     = try(each.value.port, 5439)
  } : null
}

#############################################
# Protected Global Connections — lifecycle.prevent_destroy
#############################################

resource "dbtcloud_global_connection" "protected_connections" {
  for_each = local.protected_connections_map

  name = each.value.name

  private_link_endpoint_id = try(each.value.private_link_endpoint_id, null)

  databricks = try(each.value.type, "") == "databricks" ? {
    host          = try(each.value.host, "")
    http_path     = try(each.value.http_path, "")
    catalog       = try(each.value.catalog, null)
    client_id     = try(var.connection_credentials[each.key].client_id, null)
    client_secret = try(var.connection_credentials[each.key].client_secret, null)
  } : null

  snowflake = try(each.value.type, "") == "snowflake" ? {
    account                   = try(each.value.account, "")
    database                  = try(each.value.database, "")
    warehouse                 = try(each.value.warehouse, "")
    role                      = try(each.value.role, null)
    client_session_keep_alive = try(each.value.client_session_keep_alive, false)
    allow_sso                 = try(each.value.allow_sso, false)
    oauth_client_id           = try(var.connection_credentials[each.key].oauth_client_id, null)
    oauth_client_secret       = try(var.connection_credentials[each.key].oauth_client_secret, null)
  } : null

  bigquery = try(each.value.type, "") == "bigquery" ? {
    gcp_project_id              = try(each.value.gcp_project_id, "")
    private_key_id              = try(var.connection_credentials[each.key].private_key_id, null)
    private_key                 = try(var.connection_credentials[each.key].private_key, null)
    client_email                = try(each.value.client_email, null)
    client_id                   = try(each.value.client_id, null)
    auth_uri                    = try(each.value.auth_uri, null)
    token_uri                   = try(each.value.token_uri, null)
    auth_provider_x509_cert_url = try(each.value.auth_provider_x509_cert_url, null)
    client_x509_cert_url        = try(each.value.client_x509_cert_url, null)
    timeout_seconds             = try(each.value.timeout_seconds, null)
    location                    = try(each.value.location, null)
  } : null

  postgres = try(each.value.type, "") == "postgres" ? {
    hostname = try(each.value.hostname, "")
    dbname   = try(each.value.dbname, "")
    port     = try(each.value.port, 5432)
  } : null

  redshift = try(each.value.type, "") == "redshift" ? {
    hostname = try(each.value.hostname, "")
    dbname   = try(each.value.dbname, "")
    port     = try(each.value.port, 5439)
  } : null

  lifecycle {
    prevent_destroy = true
  }
}
