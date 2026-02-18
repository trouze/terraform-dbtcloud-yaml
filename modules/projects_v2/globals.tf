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

#############################################
# Protection: Split global resources into protected/unprotected
# Same pattern as projects.tf — protected resources get lifecycle.prevent_destroy
#############################################

locals {
  # ---- Groups ----
  all_groups_map = {
    for group in try(var.globals.groups, []) :
    group.key => group
  }
  protected_groups_map = {
    for key, group in local.all_groups_map :
    key => group
    if try(group.protected, false) == true
  }
  unprotected_groups_map = {
    for key, group in local.all_groups_map :
    key => group
    if try(group.protected, false) != true
  }

  # ---- Service Tokens ----
  all_service_tokens_map = {
    for token in try(var.globals.service_tokens, []) :
    token.key => token
  }
  protected_service_tokens_map = {
    for key, token in local.all_service_tokens_map :
    key => token
    if try(token.protected, false) == true
  }
  unprotected_service_tokens_map = {
    for key, token in local.all_service_tokens_map :
    key => token
    if try(token.protected, false) != true
  }

  # ---- Connections ----
  all_connections_map = {
    for conn in try(var.globals.connections, []) :
    conn.key => conn
  }
  protected_connections_map = {
    for key, conn in local.all_connections_map :
    key => conn
    if try(conn.protected, false) == true
  }
  unprotected_connections_map = {
    for key, conn in local.all_connections_map :
    key => conn
    if try(conn.protected, false) != true
  }
}

#############################################
# Unprotected Connections - standard lifecycle
#############################################

# Global Connections
# Note: Provider-specific configuration blocks are required by Terraform
# For test fixtures, we provide minimal required fields based on connection type
# For production use, users should add full provider configuration from their connection details
resource "dbtcloud_global_connection" "connections" {
  for_each = local.unprotected_connections_map

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
  # Read from provider_config first (user-provided), then connection_credentials (sensitive), then details (API), then defaults
  # OAuth/SSO credentials come from var.connection_credentials[connection_key]

  databricks = try(each.value.type, "") == "databricks" ? {
    # Required fields
    host      = try(each.value.provider_config.host, try(each.value.details.host, "test-host.cloud.databricks.com"))
    http_path = try(each.value.provider_config.http_path, try(each.value.details.http_path, "/sql/1.0/warehouses/test"))
    # Optional fields
    catalog = try(each.value.provider_config.catalog, try(each.value.details.catalog, null))
    # OAuth credentials - from connection_credentials variable (sensitive)
    client_id     = try(var.connection_credentials[each.key].client_id, try(each.value.provider_config.client_id, null))
    client_secret = try(var.connection_credentials[each.key].client_secret, try(each.value.provider_config.client_secret, null))
  } : null

  snowflake = try(each.value.type, "") == "snowflake" ? {
    # Required fields
    account   = try(each.value.provider_config.account, try(each.value.details.account, "test-account"))
    database  = try(each.value.provider_config.database, try(each.value.details.database, "TEST_DB"))
    warehouse = try(each.value.provider_config.warehouse, try(each.value.details.warehouse, "TEST_WH"))
    # Optional fields
    role                      = try(each.value.provider_config.role, try(each.value.details.role, null))
    client_session_keep_alive = try(each.value.provider_config.client_session_keep_alive, try(each.value.details.client_session_keep_alive, false))
    allow_sso                 = try(each.value.provider_config.allow_sso, try(each.value.details.allow_sso, false))
    # OAuth credentials - from connection_credentials variable (sensitive)
    oauth_client_id     = try(var.connection_credentials[each.key].oauth_client_id, try(each.value.provider_config.oauth_client_id, null))
    oauth_client_secret = try(var.connection_credentials[each.key].oauth_client_secret, try(each.value.provider_config.oauth_client_secret, null))
  } : null

  bigquery = try(each.value.type, "") == "bigquery" ? {
    # Required field
    gcp_project_id = try(each.value.provider_config.gcp_project_id, try(each.value.details.gcp_project_id, "test-project"))
    # Auth type selector (defaults to service-account-json)
    deployment_env_auth_type = try(each.value.provider_config.deployment_env_auth_type, null)
    # Service Account JSON authentication fields
    private_key_id              = try(var.connection_credentials[each.key].private_key_id, try(each.value.provider_config.private_key_id, try(each.value.details.private_key_id, null)))
    private_key                 = try(var.connection_credentials[each.key].private_key, try(each.value.provider_config.private_key, try(each.value.details.private_key, null)))
    client_email                = try(each.value.provider_config.client_email, try(each.value.details.client_email, null))
    client_id                   = try(each.value.provider_config.client_id, try(each.value.details.client_id, null))
    auth_uri                    = try(each.value.provider_config.auth_uri, try(each.value.details.auth_uri, null))
    token_uri                   = try(each.value.provider_config.token_uri, try(each.value.details.token_uri, null))
    auth_provider_x509_cert_url = try(each.value.provider_config.auth_provider_x509_cert_url, try(each.value.details.auth_provider_x509_cert_url, null))
    client_x509_cert_url        = try(each.value.provider_config.client_x509_cert_url, try(each.value.details.client_x509_cert_url, null))
    # External OAuth (Workload Identity Federation) fields
    application_id     = try(var.connection_credentials[each.key].application_id, try(each.value.provider_config.application_id, null))
    application_secret = try(var.connection_credentials[each.key].application_secret, try(each.value.provider_config.application_secret, null))
    scopes             = try(each.value.provider_config.scopes, null)
    # Query configuration
    timeout_seconds               = try(each.value.provider_config.timeout_seconds, try(each.value.details.timeout_seconds, null))
    location                      = try(each.value.provider_config.location, try(each.value.details.location, null))
    maximum_bytes_billed          = try(each.value.provider_config.maximum_bytes_billed, try(each.value.details.maximum_bytes_billed, null))
    priority                      = try(each.value.provider_config.priority, try(each.value.details.priority, null))
    retries                       = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    job_creation_timeout_seconds  = try(each.value.provider_config.job_creation_timeout_seconds, null)
    job_execution_timeout_seconds = try(each.value.provider_config.job_execution_timeout_seconds, null)
    job_retry_deadline_seconds    = try(each.value.provider_config.job_retry_deadline_seconds, null)
    # Execution and impersonation
    execution_project           = try(each.value.provider_config.execution_project, try(each.value.details.execution_project, null))
    impersonate_service_account = try(each.value.provider_config.impersonate_service_account, null)
    # Dataproc configuration for Python models
    dataproc_region       = try(each.value.provider_config.dataproc_region, try(each.value.details.dataproc_region, null))
    dataproc_cluster_name = try(each.value.provider_config.dataproc_cluster_name, try(each.value.details.dataproc_cluster_name, null))
    gcs_bucket            = try(each.value.provider_config.gcs_bucket, try(each.value.details.gcs_bucket, null))
    # Adapter version
    use_latest_adapter = try(each.value.provider_config.use_latest_adapter, null)
  } : null

  postgres = try(each.value.type, "") == "postgres" ? {
    # Required fields
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, "test-postgres.example.com"))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, "postgres"))
    # Optional fields
    port = try(each.value.provider_config.port, try(each.value.details.port, 5432))
    # SSH Tunnel configuration (nested block)
    ssh_tunnel = try(each.value.provider_config.ssh_tunnel_hostname, null) != null ? {
      hostname = each.value.provider_config.ssh_tunnel_hostname
      port     = try(each.value.provider_config.ssh_tunnel_port, 22)
      username = try(each.value.provider_config.ssh_tunnel_username, "dbt")
    } : null
  } : null

  redshift = try(each.value.type, "") == "redshift" ? {
    # Required fields
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, "test-redshift.example.com"))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, "dev"))
    # Optional fields
    port = try(each.value.provider_config.port, try(each.value.details.port, 5439))
    # SSH Tunnel configuration (nested block)
    ssh_tunnel = try(each.value.provider_config.ssh_tunnel_hostname, null) != null ? {
      hostname = each.value.provider_config.ssh_tunnel_hostname
      port     = try(each.value.provider_config.ssh_tunnel_port, 22)
      username = try(each.value.provider_config.ssh_tunnel_username, "dbt")
    } : null
  } : null

  athena = try(each.value.type, "") == "athena" ? {
    # Required fields
    region_name    = try(each.value.provider_config.region_name, try(each.value.details.region_name, "us-east-1"))
    database       = try(each.value.provider_config.database, try(each.value.details.database, "test_db"))
    s3_staging_dir = try(each.value.provider_config.s3_staging_dir, try(each.value.details.s3_staging_dir, "s3://test-bucket/staging/"))
    # Optional fields
    work_group          = try(each.value.provider_config.work_group, try(each.value.details.work_group, null))
    s3_data_dir         = try(each.value.provider_config.s3_data_dir, try(each.value.details.s3_data_dir, null))
    s3_tmp_table_dir    = try(each.value.provider_config.s3_tmp_table_dir, try(each.value.details.s3_tmp_table_dir, null))
    s3_data_naming      = try(each.value.provider_config.s3_data_naming, try(each.value.details.s3_data_naming, null))
    num_retries         = try(each.value.provider_config.num_retries, try(each.value.details.num_retries, null))
    num_boto3_retries   = try(each.value.provider_config.num_boto3_retries, try(each.value.details.num_boto3_retries, null))
    num_iceberg_retries = try(each.value.provider_config.num_iceberg_retries, try(each.value.details.num_iceberg_retries, null))
    poll_interval       = try(each.value.provider_config.poll_interval, try(each.value.details.poll_interval, null))
    spark_work_group    = try(each.value.provider_config.spark_work_group, try(each.value.details.spark_work_group, null))
  } : null

  fabric = try(each.value.type, "") == "fabric" ? {
    # Required fields
    server   = try(each.value.provider_config.server, try(each.value.details.server, "test-fabric.example.com"))
    database = try(each.value.provider_config.database, try(each.value.details.database, "test_db"))
    # Optional fields
    port          = try(each.value.provider_config.port, try(each.value.details.port, null))
    retries       = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    login_timeout = try(each.value.provider_config.login_timeout, try(each.value.details.login_timeout, null))
    query_timeout = try(each.value.provider_config.query_timeout, try(each.value.details.query_timeout, null))
  } : null

  synapse = try(each.value.type, "") == "synapse" ? {
    # Required fields
    host     = try(each.value.provider_config.host, try(each.value.details.host, "test-synapse.example.com"))
    database = try(each.value.provider_config.database, try(each.value.details.database, "test_db"))
    # Optional fields
    port          = try(each.value.provider_config.port, try(each.value.details.port, null))
    retries       = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    login_timeout = try(each.value.provider_config.login_timeout, try(each.value.details.login_timeout, null))
    query_timeout = try(each.value.provider_config.query_timeout, try(each.value.details.query_timeout, null))
  } : null

  starburst = try(each.value.type, "") == "starburst" ? {
    # Required fields
    host = try(each.value.provider_config.host, try(each.value.details.host, "test-starburst.example.com"))
    # Optional fields
    port   = try(each.value.provider_config.port, try(each.value.details.port, null))
    method = try(each.value.provider_config.method, try(each.value.details.method, null))
  } : null

  teradata = try(each.value.type, "") == "teradata" ? {
    # Required fields
    host  = try(each.value.provider_config.host, try(each.value.details.host, "test-teradata.example.com"))
    tmode = try(each.value.provider_config.tmode, try(each.value.details.tmode, "ANSI"))
    # Optional fields
    port            = try(each.value.provider_config.port, try(each.value.details.port, null))
    retries         = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    request_timeout = try(each.value.provider_config.request_timeout, try(each.value.details.request_timeout, null))
  } : null

  apache_spark = try(each.value.type, "") == "apache_spark" ? {
    # Required fields
    method  = try(each.value.provider_config.method, try(each.value.details.method, "http"))
    host    = try(each.value.provider_config.host, try(each.value.details.host, "test-spark.example.com"))
    cluster = try(each.value.provider_config.cluster, try(each.value.details.cluster, "test-cluster"))
    # Optional fields
    port            = try(each.value.provider_config.port, try(each.value.details.port, null))
    organization    = try(each.value.provider_config.organization, try(each.value.details.organization, null))
    user            = try(each.value.provider_config.user, try(each.value.details.user, null))
    auth            = try(each.value.provider_config.auth, try(each.value.details.auth, null))
    connect_timeout = try(each.value.provider_config.connect_timeout, try(each.value.details.connect_timeout, null))
    connect_retries = try(each.value.provider_config.connect_retries, try(each.value.details.connect_retries, null))
  } : null
}

#############################################
# Protected Connections - prevent_destroy lifecycle
#############################################

resource "dbtcloud_global_connection" "protected_connections" {
  for_each = local.protected_connections_map

  name = each.value.name

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

  databricks = try(each.value.type, "") == "databricks" ? {
    host      = try(each.value.provider_config.host, try(each.value.details.host, "test-host.cloud.databricks.com"))
    http_path = try(each.value.provider_config.http_path, try(each.value.details.http_path, "/sql/1.0/warehouses/test"))
    catalog   = try(each.value.provider_config.catalog, try(each.value.details.catalog, null))
    client_id     = try(var.connection_credentials[each.key].client_id, try(each.value.provider_config.client_id, null))
    client_secret = try(var.connection_credentials[each.key].client_secret, try(each.value.provider_config.client_secret, null))
  } : null

  snowflake = try(each.value.type, "") == "snowflake" ? {
    account   = try(each.value.provider_config.account, try(each.value.details.account, "test-account"))
    database  = try(each.value.provider_config.database, try(each.value.details.database, "TEST_DB"))
    warehouse = try(each.value.provider_config.warehouse, try(each.value.details.warehouse, "TEST_WH"))
    role                      = try(each.value.provider_config.role, try(each.value.details.role, null))
    client_session_keep_alive = try(each.value.provider_config.client_session_keep_alive, try(each.value.details.client_session_keep_alive, false))
    allow_sso                 = try(each.value.provider_config.allow_sso, try(each.value.details.allow_sso, false))
    oauth_client_id     = try(var.connection_credentials[each.key].oauth_client_id, try(each.value.provider_config.oauth_client_id, null))
    oauth_client_secret = try(var.connection_credentials[each.key].oauth_client_secret, try(each.value.provider_config.oauth_client_secret, null))
  } : null

  bigquery = try(each.value.type, "") == "bigquery" ? {
    gcp_project_id              = try(each.value.provider_config.gcp_project_id, try(each.value.details.gcp_project_id, "test-project"))
    deployment_env_auth_type    = try(each.value.provider_config.deployment_env_auth_type, null)
    private_key_id              = try(var.connection_credentials[each.key].private_key_id, try(each.value.provider_config.private_key_id, try(each.value.details.private_key_id, null)))
    private_key                 = try(var.connection_credentials[each.key].private_key, try(each.value.provider_config.private_key, try(each.value.details.private_key, null)))
    client_email                = try(each.value.provider_config.client_email, try(each.value.details.client_email, null))
    client_id                   = try(each.value.provider_config.client_id, try(each.value.details.client_id, null))
    auth_uri                    = try(each.value.provider_config.auth_uri, try(each.value.details.auth_uri, null))
    token_uri                   = try(each.value.provider_config.token_uri, try(each.value.details.token_uri, null))
    auth_provider_x509_cert_url = try(each.value.provider_config.auth_provider_x509_cert_url, try(each.value.details.auth_provider_x509_cert_url, null))
    client_x509_cert_url        = try(each.value.provider_config.client_x509_cert_url, try(each.value.details.client_x509_cert_url, null))
    application_id     = try(var.connection_credentials[each.key].application_id, try(each.value.provider_config.application_id, null))
    application_secret = try(var.connection_credentials[each.key].application_secret, try(each.value.provider_config.application_secret, null))
    scopes             = try(each.value.provider_config.scopes, null)
    timeout_seconds               = try(each.value.provider_config.timeout_seconds, try(each.value.details.timeout_seconds, null))
    location                      = try(each.value.provider_config.location, try(each.value.details.location, null))
    maximum_bytes_billed          = try(each.value.provider_config.maximum_bytes_billed, try(each.value.details.maximum_bytes_billed, null))
    priority                      = try(each.value.provider_config.priority, try(each.value.details.priority, null))
    retries                       = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    job_creation_timeout_seconds  = try(each.value.provider_config.job_creation_timeout_seconds, null)
    job_execution_timeout_seconds = try(each.value.provider_config.job_execution_timeout_seconds, null)
    job_retry_deadline_seconds    = try(each.value.provider_config.job_retry_deadline_seconds, null)
    execution_project           = try(each.value.provider_config.execution_project, try(each.value.details.execution_project, null))
    impersonate_service_account = try(each.value.provider_config.impersonate_service_account, null)
    dataproc_region       = try(each.value.provider_config.dataproc_region, try(each.value.details.dataproc_region, null))
    dataproc_cluster_name = try(each.value.provider_config.dataproc_cluster_name, try(each.value.details.dataproc_cluster_name, null))
    gcs_bucket            = try(each.value.provider_config.gcs_bucket, try(each.value.details.gcs_bucket, null))
    use_latest_adapter = try(each.value.provider_config.use_latest_adapter, null)
  } : null

  postgres = try(each.value.type, "") == "postgres" ? {
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, "test-postgres.example.com"))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, "postgres"))
    port     = try(each.value.provider_config.port, try(each.value.details.port, 5432))
    ssh_tunnel = try(each.value.provider_config.ssh_tunnel_hostname, null) != null ? {
      hostname = each.value.provider_config.ssh_tunnel_hostname
      port     = try(each.value.provider_config.ssh_tunnel_port, 22)
      username = try(each.value.provider_config.ssh_tunnel_username, "dbt")
    } : null
  } : null

  redshift = try(each.value.type, "") == "redshift" ? {
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, "test-redshift.example.com"))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, "dev"))
    port     = try(each.value.provider_config.port, try(each.value.details.port, 5439))
    ssh_tunnel = try(each.value.provider_config.ssh_tunnel_hostname, null) != null ? {
      hostname = each.value.provider_config.ssh_tunnel_hostname
      port     = try(each.value.provider_config.ssh_tunnel_port, 22)
      username = try(each.value.provider_config.ssh_tunnel_username, "dbt")
    } : null
  } : null

  athena = try(each.value.type, "") == "athena" ? {
    region_name         = try(each.value.provider_config.region_name, try(each.value.details.region_name, "us-east-1"))
    database            = try(each.value.provider_config.database, try(each.value.details.database, "test_db"))
    s3_staging_dir      = try(each.value.provider_config.s3_staging_dir, try(each.value.details.s3_staging_dir, "s3://test-bucket/staging/"))
    work_group          = try(each.value.provider_config.work_group, try(each.value.details.work_group, null))
    s3_data_dir         = try(each.value.provider_config.s3_data_dir, try(each.value.details.s3_data_dir, null))
    s3_tmp_table_dir    = try(each.value.provider_config.s3_tmp_table_dir, try(each.value.details.s3_tmp_table_dir, null))
    s3_data_naming      = try(each.value.provider_config.s3_data_naming, try(each.value.details.s3_data_naming, null))
    num_retries         = try(each.value.provider_config.num_retries, try(each.value.details.num_retries, null))
    num_boto3_retries   = try(each.value.provider_config.num_boto3_retries, try(each.value.details.num_boto3_retries, null))
    num_iceberg_retries = try(each.value.provider_config.num_iceberg_retries, try(each.value.details.num_iceberg_retries, null))
    poll_interval       = try(each.value.provider_config.poll_interval, try(each.value.details.poll_interval, null))
    spark_work_group    = try(each.value.provider_config.spark_work_group, try(each.value.details.spark_work_group, null))
  } : null

  fabric = try(each.value.type, "") == "fabric" ? {
    server        = try(each.value.provider_config.server, try(each.value.details.server, "test-fabric.example.com"))
    database      = try(each.value.provider_config.database, try(each.value.details.database, "test_db"))
    port          = try(each.value.provider_config.port, try(each.value.details.port, null))
    retries       = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    login_timeout = try(each.value.provider_config.login_timeout, try(each.value.details.login_timeout, null))
    query_timeout = try(each.value.provider_config.query_timeout, try(each.value.details.query_timeout, null))
  } : null

  synapse = try(each.value.type, "") == "synapse" ? {
    host          = try(each.value.provider_config.host, try(each.value.details.host, "test-synapse.example.com"))
    database      = try(each.value.provider_config.database, try(each.value.details.database, "test_db"))
    port          = try(each.value.provider_config.port, try(each.value.details.port, null))
    retries       = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    login_timeout = try(each.value.provider_config.login_timeout, try(each.value.details.login_timeout, null))
    query_timeout = try(each.value.provider_config.query_timeout, try(each.value.details.query_timeout, null))
  } : null

  starburst = try(each.value.type, "") == "starburst" ? {
    host   = try(each.value.provider_config.host, try(each.value.details.host, "test-starburst.example.com"))
    port   = try(each.value.provider_config.port, try(each.value.details.port, null))
    method = try(each.value.provider_config.method, try(each.value.details.method, null))
  } : null

  teradata = try(each.value.type, "") == "teradata" ? {
    host            = try(each.value.provider_config.host, try(each.value.details.host, "test-teradata.example.com"))
    tmode           = try(each.value.provider_config.tmode, try(each.value.details.tmode, "ANSI"))
    port            = try(each.value.provider_config.port, try(each.value.details.port, null))
    retries         = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    request_timeout = try(each.value.provider_config.request_timeout, try(each.value.details.request_timeout, null))
  } : null

  apache_spark = try(each.value.type, "") == "apache_spark" ? {
    method          = try(each.value.provider_config.method, try(each.value.details.method, "http"))
    host            = try(each.value.provider_config.host, try(each.value.details.host, "test-spark.example.com"))
    cluster         = try(each.value.provider_config.cluster, try(each.value.details.cluster, "test-cluster"))
    port            = try(each.value.provider_config.port, try(each.value.details.port, null))
    organization    = try(each.value.provider_config.organization, try(each.value.details.organization, null))
    user            = try(each.value.provider_config.user, try(each.value.details.user, null))
    auth            = try(each.value.provider_config.auth, try(each.value.details.auth, null))
    connect_timeout = try(each.value.provider_config.connect_timeout, try(each.value.details.connect_timeout, null))
    connect_retries = try(each.value.provider_config.connect_retries, try(each.value.details.connect_retries, null))
  } : null

  lifecycle {
    prevent_destroy = true
  }
}

#############################################
# Unprotected Service Tokens - standard lifecycle
#############################################
resource "dbtcloud_service_token" "service_tokens" {
  for_each = local.unprotected_service_tokens_map

  name  = each.value.name
  state = try(each.value.state, 1)

  dynamic "service_token_permissions" {
    for_each = var.skip_global_project_permissions ? [] : try(each.value.service_token_permissions, [])
    content {
      permission_set = service_token_permissions.value.permission_set
      all_projects   = try(service_token_permissions.value.all_projects, false)
      # Resolve project_key to target project_id, or use explicit project_id if provided
      # Check both protected and unprotected projects
      project_id = (
        try(service_token_permissions.value.project_key, null) != null
        ? coalesce(
            try(dbtcloud_project.projects[service_token_permissions.value.project_key].id, null),
            try(dbtcloud_project.protected_projects[service_token_permissions.value.project_key].id, null)
          )
        : try(service_token_permissions.value.project_id, null)
      )
      writable_environment_categories = try(
        service_token_permissions.value.writable_environment_categories,
        []
      )
    }
  }
  dynamic "service_token_permissions" {
    for_each = var.skip_global_project_permissions ? try(each.value.service_token_permissions, []) : []
    content {
      permission_set = service_token_permissions.value.permission_set
      # Preserve valid shape while avoiding project resource references.
      all_projects = true
      project_id   = null
      writable_environment_categories = try(
        service_token_permissions.value.writable_environment_categories,
        []
      )
    }
  }

}

#############################################
# Protected Service Tokens - prevent_destroy lifecycle
#############################################
resource "dbtcloud_service_token" "protected_service_tokens" {
  for_each = local.protected_service_tokens_map

  name  = each.value.name
  state = try(each.value.state, 1)

  dynamic "service_token_permissions" {
    for_each = var.skip_global_project_permissions ? [] : try(each.value.service_token_permissions, [])
    content {
      permission_set = service_token_permissions.value.permission_set
      all_projects   = try(service_token_permissions.value.all_projects, false)
      project_id = (
        try(service_token_permissions.value.project_key, null) != null
        ? coalesce(
            try(dbtcloud_project.projects[service_token_permissions.value.project_key].id, null),
            try(dbtcloud_project.protected_projects[service_token_permissions.value.project_key].id, null)
          )
        : try(service_token_permissions.value.project_id, null)
      )
      writable_environment_categories = try(
        service_token_permissions.value.writable_environment_categories,
        []
      )
    }
  }
  dynamic "service_token_permissions" {
    for_each = var.skip_global_project_permissions ? try(each.value.service_token_permissions, []) : []
    content {
      permission_set = service_token_permissions.value.permission_set
      all_projects   = true
      project_id     = null
      writable_environment_categories = try(
        service_token_permissions.value.writable_environment_categories,
        []
      )
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

#############################################
# Unprotected Groups - standard lifecycle
#############################################
resource "dbtcloud_group" "groups" {
  for_each = local.unprotected_groups_map

  name               = each.value.name
  assign_by_default  = try(each.value.assign_by_default, false)
  sso_mapping_groups = try(each.value.sso_mapping_groups, [])

  dynamic "group_permissions" {
    for_each = var.skip_global_project_permissions ? [] : try(each.value.group_permissions, [])
    content {
      permission_set = group_permissions.value.permission_set
      all_projects   = try(group_permissions.value.all_projects, false)
      # Avoid implicit project graph coupling during scoped group adoption.
      # We only honor explicit numeric project_id in this path.
      project_id = try(group_permissions.value.project_id, null)
      writable_environment_categories = try(
        group_permissions.value.writable_environment_categories,
        []
      )
    }
  }
  dynamic "group_permissions" {
    for_each = var.skip_global_project_permissions ? try(each.value.group_permissions, []) : []
    content {
      permission_set = group_permissions.value.permission_set
      all_projects   = true
      project_id     = null
      writable_environment_categories = try(
        group_permissions.value.writable_environment_categories,
        []
      )
    }
  }

}

#############################################
# Protected Groups - prevent_destroy lifecycle
#############################################
resource "dbtcloud_group" "protected_groups" {
  for_each = local.protected_groups_map

  name               = each.value.name
  assign_by_default  = try(each.value.assign_by_default, false)
  sso_mapping_groups = try(each.value.sso_mapping_groups, [])

  dynamic "group_permissions" {
    for_each = var.skip_global_project_permissions ? [] : try(each.value.group_permissions, [])
    content {
      permission_set = group_permissions.value.permission_set
      all_projects   = try(group_permissions.value.all_projects, false)
      # Avoid implicit project graph coupling during scoped group adoption.
      # We only honor explicit numeric project_id in this path.
      project_id = try(group_permissions.value.project_id, null)
      writable_environment_categories = try(
        group_permissions.value.writable_environment_categories,
        []
      )
    }
  }
  dynamic "group_permissions" {
    for_each = var.skip_global_project_permissions ? try(each.value.group_permissions, []) : []
    content {
      permission_set = group_permissions.value.permission_set
      all_projects   = true
      project_id     = null
      writable_environment_categories = try(
        group_permissions.value.writable_environment_categories,
        []
      )
    }
  }

  lifecycle {
    prevent_destroy = true
  }
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
    for notif in try(var.globals.notifications, []) :
    notif.key => notif
    if false # Skip all notifications - user_id mapping required
  }

  # Required fields (placeholder values - no instances will be created due to for_each = {})
  user_id           = 0 # Placeholder - never used since for_each is always empty
  notification_type = 1 # Type 1 (user email) - no external_email required
  state             = 1
}

# Data source for PrivateLink endpoints (read-only)
data "dbtcloud_privatelink_endpoints" "all" {}

