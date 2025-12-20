#############################################
# Global Resources
# 
# Creates account-level resources that can be referenced by projects:
# - Connections (global connections)
# - Service Tokens
# - Groups
# - Notifications (created but job associations handled later)
#
# Note: Repositories are project-scoped and created per-project.
# Note: PrivateLink endpoints are read-only (must exist in account).
#############################################

# Global Connections
# Note: Provider-specific configuration blocks are required by Terraform
# For test fixtures, we provide minimal required fields based on connection type
# For production use, users should add full provider configuration from their connection details
resource "dbtcloud_global_connection" "connections" {
  for_each = {
    for conn in var.globals.connections :
    conn.key => conn
  }

  name = each.value.name

  # PrivateLink endpoint reference (if specified)
  private_link_endpoint_id = try(
    lookup(local.privatelink_endpoints_map, each.value.private_link_endpoint_key, null) != null ?
    data.dbtcloud_privatelink_endpoints.all.endpoints[
      index(
        [for ep in data.dbtcloud_privatelink_endpoints.all.endpoints : ep.id],
        lookup(local.privatelink_endpoints_map, each.value.private_link_endpoint_key).endpoint_id
      )
    ].id : null,
    null
  )

  # Provider-specific blocks - conditionally added based on connection type
  # Read from provider_config first (user-provided), then details (API), then defaults
  databricks = try(each.value.type, "") == "databricks" ? {
    host      = try(each.value.provider_config.host, try(each.value.details.host, "test-host.cloud.databricks.com"))
    http_path = try(each.value.provider_config.http_path, try(each.value.details.http_path, "/sql/1.0/warehouses/test"))
    catalog   = try(each.value.provider_config.catalog, try(each.value.details.catalog, null))
  } : null

  snowflake = try(each.value.type, "") == "snowflake" ? {
    account                   = try(each.value.provider_config.account, try(each.value.details.account, "test-account"))
    database                  = try(each.value.provider_config.database, try(each.value.details.database, "TEST_DB"))
    warehouse                 = try(each.value.provider_config.warehouse, try(each.value.details.warehouse, "TEST_WH"))
    role                      = try(each.value.provider_config.role, try(each.value.details.role, null))
    client_session_keep_alive = try(each.value.provider_config.client_session_keep_alive, try(each.value.details.client_session_keep_alive, false))
    allow_sso                 = try(each.value.provider_config.allow_sso, try(each.value.details.allow_sso, false))
  } : null

  bigquery = try(each.value.type, "") == "bigquery" ? {
    gcp_project_id              = try(each.value.provider_config.gcp_project_id, try(each.value.details.gcp_project_id, "test-project"))
    private_key_id              = try(each.value.provider_config.private_key_id, try(each.value.details.private_key_id, "test-key-id"))
    private_key                 = try(each.value.provider_config.private_key, try(each.value.details.private_key, "test-key"))
    client_email                = try(each.value.provider_config.client_email, try(each.value.details.client_email, "test@example.com"))
    client_id                   = try(each.value.provider_config.client_id, try(each.value.details.client_id, "test-client-id"))
    auth_uri                    = try(each.value.provider_config.auth_uri, try(each.value.details.auth_uri, "https://accounts.google.com/o/oauth2/auth"))
    token_uri                   = try(each.value.provider_config.token_uri, try(each.value.details.token_uri, "https://oauth2.googleapis.com/token"))
    auth_provider_x509_cert_url = try(each.value.provider_config.auth_provider_x509_cert_url, try(each.value.details.auth_provider_x509_cert_url, "https://www.googleapis.com/oauth2/v1/certs"))
    client_x509_cert_url        = try(each.value.provider_config.client_x509_cert_url, try(each.value.details.client_x509_cert_url, "https://www.googleapis.com/robot/v1/metadata/x509/test%40example.com"))
  } : null

  postgres = try(each.value.type, "") == "postgres" ? {
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, "test-postgres.example.com"))
    port     = try(each.value.provider_config.port, try(each.value.details.port, 5432))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, null))
  } : null

  redshift = try(each.value.type, "") == "redshift" ? {
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, "test-redshift.example.com"))
    port     = try(each.value.provider_config.port, try(each.value.details.port, 5439))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, null))
  } : null

  athena = try(each.value.type, "") == "athena" ? {
    region_name    = try(each.value.details.region_name, "us-east-1")
    database       = try(each.value.details.database, "test_db")
    s3_staging_dir = try(each.value.details.s3_staging_dir, "s3://test-bucket/staging/")
  } : null

  fabric = try(each.value.type, "") == "fabric" ? {
    server   = try(each.value.details.server, "test-fabric.example.com")
    database = try(each.value.details.database, "test_db")
  } : null

  synapse = try(each.value.type, "") == "synapse" ? {
    host     = try(each.value.details.host, "test-synapse.example.com")
    database = try(each.value.details.database, "test_db")
  } : null

  starburst = try(each.value.type, "") == "starburst" ? {
    host     = try(each.value.details.host, "test-starburst.example.com")
    database = try(each.value.details.database, "test_db")
  } : null

  teradata = try(each.value.type, "") == "teradata" ? {
    host  = try(each.value.details.host, "test-teradata.example.com")
    tmode = try(each.value.details.tmode, "ANSI")
  } : null

  apache_spark = try(each.value.type, "") == "apache_spark" ? {
    method  = try(each.value.details.method, "http")
    host    = try(each.value.details.host, "test-spark.example.com")
    cluster = try(each.value.details.cluster, "test-cluster")
  } : null
}

# Service Tokens
# Ensure projects exist before creating service tokens with project-specific permissions
resource "dbtcloud_service_token" "service_tokens" {
  for_each = {
    for token in var.globals.service_tokens :
    token.key => token
  }

  name  = each.value.name
  state = try(each.value.state, 1)

  dynamic "service_token_permissions" {
    for_each = try(each.value.service_token_permissions, [])
    content {
      permission_set = service_token_permissions.value.permission_set
      all_projects   = try(service_token_permissions.value.all_projects, false)
      # Resolve project_key to target project_id, or use explicit project_id if provided
      project_id = (
        try(service_token_permissions.value.project_key, null) != null
        ? try(dbtcloud_project.projects[service_token_permissions.value.project_key].id, null)
        : try(service_token_permissions.value.project_id, null)
      )
      writable_environment_categories = try(
        service_token_permissions.value.writable_environment_categories,
        []
      )
    }
  }

  depends_on = [
    dbtcloud_project.projects
  ]
}

# Groups
# Ensure projects exist before creating groups with project-specific permissions
resource "dbtcloud_group" "groups" {
  for_each = {
    for group in var.globals.groups :
    group.key => group
  }

  name               = each.value.name
  assign_by_default  = try(each.value.assign_by_default, false)
  sso_mapping_groups = try(each.value.sso_mapping_groups, [])

  dynamic "group_permissions" {
    for_each = try(each.value.group_permissions, [])
    content {
      permission_set = group_permissions.value.permission_set
      all_projects   = try(group_permissions.value.all_projects, false)
      # Resolve project_key to target project_id, or use explicit project_id if provided
      project_id = (
        try(group_permissions.value.project_key, null) != null
        ? try(dbtcloud_project.projects[group_permissions.value.project_key].id, null)
        : try(group_permissions.value.project_id, null)
      )
      writable_environment_categories = try(
        group_permissions.value.writable_environment_categories,
        []
      )
    }
  }

  depends_on = [
    dbtcloud_project.projects
  ]
}

# Notifications
# 
# Notification Migration Strategy:
# - User notifications (type 1): Skipped - source user IDs don't exist in target account
# - Slack notifications (type 2): Skipped - requires Slack integration in target account
# - Job-linked notifications: Skipped - job IDs from source account don't exist in target
# - External email notifications (type 4): Skipped - user_id is required even for external emails
#   (API requires a valid user_id from target account, which we cannot map from source)
#
# All notifications are still fetched and normalized (preserved in YAML for future migration mode).
#
# Future: A separate `--migrate-notifications` mode will handle:
# - User ID mapping (source user IDs → target user IDs)
# - Job ID mapping (source job IDs → target job IDs)
# - Slack integration detection and configuration
#
resource "dbtcloud_notification" "notifications" {
  # Skip all notifications during initial migration
  # The for_each is empty, so no notifications will be created
  for_each = {
    for notif in var.globals.notifications :
    notif.key => notif
    if false  # Skip all notifications - user_id mapping required
  }

  # Required fields (placeholder values - no instances will be created due to for_each = {})
  user_id           = 0  # Placeholder - never used since for_each is always empty
  notification_type = 1  # Type 1 (user email) - no external_email required
  state             = 1
}

# Data source for PrivateLink endpoints (read-only)
data "dbtcloud_privatelink_endpoints" "all" {}

