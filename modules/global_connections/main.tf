terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.8"
    }
  }
}

locals {
  # BigQuery: deterministic placeholder when no real key material is supplied (matches v2 / API expectations for create).
  bigquery_dummy_private_key_id   = "0000000000000000000000000000000000000000"
  bigquery_dummy_private_key_seed = "terraform-dbtcloud-as-yaml:dummy:bigquery:private-key"
  bigquery_dummy_private_key_body = join("", [
    for i in range(0, 8) : base64encode(sha512(format("%s:%d", local.bigquery_dummy_private_key_seed, i)))
  ])
  bigquery_dummy_private_key_lines = regexall(".{1,64}", local.bigquery_dummy_private_key_body)
  bigquery_dummy_private_key = join("\n", concat(
    [format("-----BEGIN %s-----", "PRIVATE KEY")],
    local.bigquery_dummy_private_key_lines,
    [format("-----END %s-----", "PRIVATE KEY")]
  ))

  connections_map = {
    for conn in var.connections_data :
    conn.key => conn
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

  privatelink_endpoints_map = {
    for ple in var.privatelink_endpoints :
    ple.key => ple
  }

  needs_privatelink_data = length([
    for k, conn in local.connections_map : k
    if try(conn.private_link_endpoint_key, null) != null && try(conn.private_link_endpoint_id, null) == null
  ]) > 0

  # Resolve PrivateLink via globals.privatelink_endpoints + account data source when only private_link_endpoint_key is set.
  private_link_endpoint_id_by_key = {
    for k, conn in local.connections_map : k => (
      try(conn.private_link_endpoint_id, null) != null ?
      conn.private_link_endpoint_id :
      (
        length(data.dbtcloud_privatelink_endpoints.all) > 0 &&
        try(conn.private_link_endpoint_key, null) != null &&
        lookup(local.privatelink_endpoints_map, conn.private_link_endpoint_key, null) != null
        ) ? data.dbtcloud_privatelink_endpoints.all[0].endpoints[
        index(
          [for ep in data.dbtcloud_privatelink_endpoints.all[0].endpoints : ep.id],
          lookup(local.privatelink_endpoints_map, conn.private_link_endpoint_key, { endpoint_id = null }).endpoint_id
        )
      ].id : null
    )
  }
}

data "dbtcloud_privatelink_endpoints" "all" {
  count = local.needs_privatelink_data ? 1 : 0
}

#############################################
# Unprotected Global Connections
#############################################

resource "dbtcloud_global_connection" "connections" {
  for_each = local.unprotected_connections_map

  name = each.value.name

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/globals.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "CON:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }

  private_link_endpoint_id = local.private_link_endpoint_id_by_key[each.key]

  # Prefer provider_config, then details (globals.connections[]); else top-level fields on the connection object.
  databricks = try(each.value.type, "") == "databricks" ? {
    host          = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    http_path     = try(each.value.provider_config.http_path, try(each.value.details.http_path, try(each.value.http_path, "")))
    catalog       = try(each.value.provider_config.catalog, try(each.value.details.catalog, try(each.value.catalog, null)))
    client_id     = try(var.connection_credentials[each.key].client_id, try(each.value.provider_config.client_id, try(each.value.details.client_id, null)))
    client_secret = try(var.connection_credentials[each.key].client_secret, try(each.value.provider_config.client_secret, try(each.value.details.client_secret, null)))
  } : null

  snowflake = try(each.value.type, "") == "snowflake" ? {
    account                   = try(each.value.provider_config.account, try(each.value.details.account, try(each.value.account, "")))
    database                  = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, "")))
    warehouse                 = try(each.value.provider_config.warehouse, try(each.value.details.warehouse, try(each.value.warehouse, "")))
    role                      = try(each.value.provider_config.role, try(each.value.details.role, try(each.value.role, null)))
    client_session_keep_alive = try(each.value.provider_config.client_session_keep_alive, try(each.value.details.client_session_keep_alive, try(each.value.client_session_keep_alive, false)))
    allow_sso                 = try(each.value.provider_config.allow_sso, try(each.value.details.allow_sso, try(each.value.allow_sso, false)))
    oauth_client_id           = try(var.connection_credentials[each.key].oauth_client_id, try(each.value.provider_config.oauth_client_id, try(each.value.details.oauth_client_id, null)))
    oauth_client_secret       = try(var.connection_credentials[each.key].oauth_client_secret, try(each.value.provider_config.oauth_client_secret, try(each.value.details.oauth_client_secret, null)))
  } : null

  bigquery = try(each.value.type, "") == "bigquery" ? {
    gcp_project_id                = try(each.value.provider_config.gcp_project_id, try(each.value.details.gcp_project_id, try(each.value.gcp_project_id, "")))
    deployment_env_auth_type      = try(each.value.provider_config.deployment_env_auth_type, try(each.value.details.deployment_env_auth_type, null))
    private_key_id                = coalesce(nonsensitive(try(var.connection_credentials[each.key].private_key_id, null)), try(each.value.provider_config.private_key_id, try(each.value.details.private_key_id, null)), local.bigquery_dummy_private_key_id)
    private_key                   = coalesce(try(var.connection_credentials[each.key].private_key, try(each.value.provider_config.private_key, try(each.value.details.private_key, null))), local.bigquery_dummy_private_key)
    client_email                  = try(each.value.provider_config.client_email, try(each.value.details.client_email, try(each.value.client_email, null)))
    client_id                     = try(each.value.provider_config.client_id, try(each.value.details.client_id, try(each.value.client_id, null)))
    auth_uri                      = try(each.value.provider_config.auth_uri, try(each.value.details.auth_uri, try(each.value.auth_uri, null)))
    token_uri                     = try(each.value.provider_config.token_uri, try(each.value.details.token_uri, try(each.value.token_uri, null)))
    auth_provider_x509_cert_url   = try(each.value.provider_config.auth_provider_x509_cert_url, try(each.value.details.auth_provider_x509_cert_url, try(each.value.auth_provider_x509_cert_url, null)))
    client_x509_cert_url          = try(each.value.provider_config.client_x509_cert_url, try(each.value.details.client_x509_cert_url, try(each.value.client_x509_cert_url, null)))
    application_id                = try(var.connection_credentials[each.key].application_id, try(each.value.provider_config.application_id, try(each.value.details.application_id, null)))
    application_secret            = try(var.connection_credentials[each.key].application_secret, try(each.value.provider_config.application_secret, try(each.value.details.application_secret, null)))
    scopes                        = try(each.value.provider_config.scopes, try(each.value.details.scopes, null))
    timeout_seconds               = try(each.value.provider_config.timeout_seconds, try(each.value.details.timeout_seconds, try(each.value.timeout_seconds, null)))
    location                      = try(each.value.provider_config.location, try(each.value.details.location, try(each.value.location, null)))
    maximum_bytes_billed          = try(each.value.provider_config.maximum_bytes_billed, try(each.value.details.maximum_bytes_billed, null))
    priority                      = try(each.value.provider_config.priority, try(each.value.details.priority, null))
    retries                       = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    job_creation_timeout_seconds  = try(each.value.provider_config.job_creation_timeout_seconds, null)
    job_execution_timeout_seconds = try(each.value.provider_config.job_execution_timeout_seconds, null)
    job_retry_deadline_seconds    = try(each.value.provider_config.job_retry_deadline_seconds, null)
    execution_project             = try(each.value.provider_config.execution_project, try(each.value.details.execution_project, null))
    impersonate_service_account   = try(each.value.provider_config.impersonate_service_account, null)
    dataproc_region               = try(each.value.provider_config.dataproc_region, try(each.value.details.dataproc_region, null))
    dataproc_cluster_name         = try(each.value.provider_config.dataproc_cluster_name, try(each.value.details.dataproc_cluster_name, null))
    gcs_bucket                    = try(each.value.provider_config.gcs_bucket, try(each.value.details.gcs_bucket, null))
    use_latest_adapter            = try(each.value.provider_config.use_latest_adapter, null)
  } : null

  postgres = try(each.value.type, "") == "postgres" ? {
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, try(each.value.hostname, "")))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, try(each.value.dbname, "")))
    port     = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, 5432)))
    ssh_tunnel = try(each.value.provider_config.ssh_tunnel_hostname, try(each.value.ssh_tunnel_hostname, null)) != null ? {
      hostname = try(each.value.provider_config.ssh_tunnel_hostname, each.value.ssh_tunnel_hostname)
      port     = try(each.value.provider_config.ssh_tunnel_port, try(each.value.ssh_tunnel_port, 22))
      username = try(each.value.provider_config.ssh_tunnel_username, try(each.value.ssh_tunnel_username, "dbt"))
    } : null
  } : null

  redshift = try(each.value.type, "") == "redshift" ? {
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, try(each.value.hostname, "")))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, try(each.value.dbname, "")))
    port     = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, 5439)))
    ssh_tunnel = try(each.value.provider_config.ssh_tunnel_hostname, try(each.value.ssh_tunnel_hostname, null)) != null ? {
      hostname = try(each.value.provider_config.ssh_tunnel_hostname, each.value.ssh_tunnel_hostname)
      port     = try(each.value.provider_config.ssh_tunnel_port, try(each.value.ssh_tunnel_port, 22))
      username = try(each.value.provider_config.ssh_tunnel_username, try(each.value.ssh_tunnel_username, "dbt"))
    } : null
  } : null

  athena = try(each.value.type, "") == "athena" ? {
    region_name         = try(each.value.provider_config.region_name, try(each.value.details.region_name, try(each.value.region_name, "")))
    database            = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, "")))
    s3_staging_dir      = try(each.value.provider_config.s3_staging_dir, try(each.value.details.s3_staging_dir, try(each.value.s3_staging_dir, "")))
    work_group          = try(each.value.provider_config.work_group, try(each.value.details.work_group, try(each.value.work_group, null)))
    s3_data_dir         = try(each.value.provider_config.s3_data_dir, try(each.value.details.s3_data_dir, try(each.value.s3_data_dir, null)))
    s3_tmp_table_dir    = try(each.value.provider_config.s3_tmp_table_dir, try(each.value.details.s3_tmp_table_dir, try(each.value.s3_tmp_table_dir, null)))
    s3_data_naming      = try(each.value.provider_config.s3_data_naming, try(each.value.details.s3_data_naming, try(each.value.s3_data_naming, null)))
    num_retries         = try(each.value.provider_config.num_retries, try(each.value.details.num_retries, try(each.value.num_retries, null)))
    num_boto3_retries   = try(each.value.provider_config.num_boto3_retries, try(each.value.details.num_boto3_retries, try(each.value.num_boto3_retries, null)))
    num_iceberg_retries = try(each.value.provider_config.num_iceberg_retries, try(each.value.details.num_iceberg_retries, try(each.value.num_iceberg_retries, null)))
    poll_interval       = try(each.value.provider_config.poll_interval, try(each.value.details.poll_interval, try(each.value.poll_interval, null)))
    spark_work_group    = try(each.value.provider_config.spark_work_group, try(each.value.details.spark_work_group, try(each.value.spark_work_group, null)))
  } : null

  fabric = try(each.value.type, "") == "fabric" ? {
    server        = try(each.value.provider_config.server, try(each.value.details.server, try(each.value.server, "")))
    database      = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, "")))
    port          = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, null)))
    retries       = try(each.value.provider_config.retries, try(each.value.details.retries, try(each.value.retries, null)))
    login_timeout = try(each.value.provider_config.login_timeout, try(each.value.details.login_timeout, try(each.value.login_timeout, null)))
    query_timeout = try(each.value.provider_config.query_timeout, try(each.value.details.query_timeout, try(each.value.query_timeout, null)))
  } : null

  synapse = try(each.value.type, "") == "synapse" ? {
    host          = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    database      = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, "")))
    port          = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, null)))
    retries       = try(each.value.provider_config.retries, try(each.value.details.retries, try(each.value.retries, null)))
    login_timeout = try(each.value.provider_config.login_timeout, try(each.value.details.login_timeout, try(each.value.login_timeout, null)))
    query_timeout = try(each.value.provider_config.query_timeout, try(each.value.details.query_timeout, try(each.value.query_timeout, null)))
  } : null

  # YAML type starburst_trino maps to provider starburst block.
  starburst = contains(["starburst", "starburst_trino"], try(each.value.type, "")) ? {
    host   = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    port   = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, null)))
    method = try(each.value.provider_config.method, try(each.value.details.method, try(each.value.method, null)))
  } : null

  teradata = try(each.value.type, "") == "teradata" ? {
    host            = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    tmode           = try(each.value.provider_config.tmode, try(each.value.details.tmode, try(each.value.tmode, "ANSI")))
    port            = try(each.value.provider_config.port, try(each.value.details.port, try(tostring(each.value.port), null)))
    retries         = try(each.value.provider_config.retries, try(each.value.details.retries, try(each.value.retries, null)))
    request_timeout = try(each.value.provider_config.request_timeout, try(each.value.details.request_timeout, try(each.value.request_timeout, null)))
  } : null

  salesforce = try(each.value.type, "") == "salesforce" ? {
    login_url                  = try(each.value.provider_config.login_url, try(each.value.details.login_url, try(each.value.login_url, "")))
    database                   = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, null)))
    data_transform_run_timeout = try(each.value.provider_config.data_transform_run_timeout, try(each.value.details.data_transform_run_timeout, try(each.value.data_transform_run_timeout, null)))
  } : null

  # YAML type spark maps to provider apache_spark (same as credentials module).
  apache_spark = contains(["apache_spark", "spark"], try(each.value.type, "")) ? {
    method          = try(each.value.provider_config.method, try(each.value.details.method, try(each.value.method, "http")))
    host            = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    cluster         = try(each.value.provider_config.cluster, try(each.value.details.cluster, try(each.value.cluster, "")))
    port            = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, null)))
    organization    = try(each.value.provider_config.organization, try(each.value.details.organization, try(each.value.organization, null)))
    user            = try(each.value.provider_config.user, try(each.value.details.user, try(each.value.user, null)))
    auth            = try(each.value.provider_config.auth, try(each.value.details.auth, try(each.value.auth, null)))
    connect_timeout = try(each.value.provider_config.connect_timeout, try(each.value.details.connect_timeout, try(each.value.connect_timeout, null)))
    connect_retries = try(each.value.provider_config.connect_retries, try(each.value.details.connect_retries, try(each.value.connect_retries, null)))
  } : null
}

#############################################
# Protected Global Connections — lifecycle.prevent_destroy
#############################################

resource "dbtcloud_global_connection" "protected_connections" {
  for_each = local.protected_connections_map

  name = each.value.name

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/globals.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "CON:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }

  private_link_endpoint_id = local.private_link_endpoint_id_by_key[each.key]

  databricks = try(each.value.type, "") == "databricks" ? {
    host          = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    http_path     = try(each.value.provider_config.http_path, try(each.value.details.http_path, try(each.value.http_path, "")))
    catalog       = try(each.value.provider_config.catalog, try(each.value.details.catalog, try(each.value.catalog, null)))
    client_id     = try(var.connection_credentials[each.key].client_id, try(each.value.provider_config.client_id, try(each.value.details.client_id, null)))
    client_secret = try(var.connection_credentials[each.key].client_secret, try(each.value.provider_config.client_secret, try(each.value.details.client_secret, null)))
  } : null

  snowflake = try(each.value.type, "") == "snowflake" ? {
    account                   = try(each.value.provider_config.account, try(each.value.details.account, try(each.value.account, "")))
    database                  = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, "")))
    warehouse                 = try(each.value.provider_config.warehouse, try(each.value.details.warehouse, try(each.value.warehouse, "")))
    role                      = try(each.value.provider_config.role, try(each.value.details.role, try(each.value.role, null)))
    client_session_keep_alive = try(each.value.provider_config.client_session_keep_alive, try(each.value.details.client_session_keep_alive, try(each.value.client_session_keep_alive, false)))
    allow_sso                 = try(each.value.provider_config.allow_sso, try(each.value.details.allow_sso, try(each.value.allow_sso, false)))
    oauth_client_id           = try(var.connection_credentials[each.key].oauth_client_id, try(each.value.provider_config.oauth_client_id, try(each.value.details.oauth_client_id, null)))
    oauth_client_secret       = try(var.connection_credentials[each.key].oauth_client_secret, try(each.value.provider_config.oauth_client_secret, try(each.value.details.oauth_client_secret, null)))
  } : null

  bigquery = try(each.value.type, "") == "bigquery" ? {
    gcp_project_id                = try(each.value.provider_config.gcp_project_id, try(each.value.details.gcp_project_id, try(each.value.gcp_project_id, "")))
    deployment_env_auth_type      = try(each.value.provider_config.deployment_env_auth_type, try(each.value.details.deployment_env_auth_type, null))
    private_key_id                = coalesce(nonsensitive(try(var.connection_credentials[each.key].private_key_id, null)), try(each.value.provider_config.private_key_id, try(each.value.details.private_key_id, null)), local.bigquery_dummy_private_key_id)
    private_key                   = coalesce(try(var.connection_credentials[each.key].private_key, try(each.value.provider_config.private_key, try(each.value.details.private_key, null))), local.bigquery_dummy_private_key)
    client_email                  = try(each.value.provider_config.client_email, try(each.value.details.client_email, try(each.value.client_email, null)))
    client_id                     = try(each.value.provider_config.client_id, try(each.value.details.client_id, try(each.value.client_id, null)))
    auth_uri                      = try(each.value.provider_config.auth_uri, try(each.value.details.auth_uri, try(each.value.auth_uri, null)))
    token_uri                     = try(each.value.provider_config.token_uri, try(each.value.details.token_uri, try(each.value.token_uri, null)))
    auth_provider_x509_cert_url   = try(each.value.provider_config.auth_provider_x509_cert_url, try(each.value.details.auth_provider_x509_cert_url, try(each.value.auth_provider_x509_cert_url, null)))
    client_x509_cert_url          = try(each.value.provider_config.client_x509_cert_url, try(each.value.details.client_x509_cert_url, try(each.value.client_x509_cert_url, null)))
    application_id                = try(var.connection_credentials[each.key].application_id, try(each.value.provider_config.application_id, try(each.value.details.application_id, null)))
    application_secret            = try(var.connection_credentials[each.key].application_secret, try(each.value.provider_config.application_secret, try(each.value.details.application_secret, null)))
    scopes                        = try(each.value.provider_config.scopes, try(each.value.details.scopes, null))
    timeout_seconds               = try(each.value.provider_config.timeout_seconds, try(each.value.details.timeout_seconds, try(each.value.timeout_seconds, null)))
    location                      = try(each.value.provider_config.location, try(each.value.details.location, try(each.value.location, null)))
    maximum_bytes_billed          = try(each.value.provider_config.maximum_bytes_billed, try(each.value.details.maximum_bytes_billed, null))
    priority                      = try(each.value.provider_config.priority, try(each.value.details.priority, null))
    retries                       = try(each.value.provider_config.retries, try(each.value.details.retries, null))
    job_creation_timeout_seconds  = try(each.value.provider_config.job_creation_timeout_seconds, null)
    job_execution_timeout_seconds = try(each.value.provider_config.job_execution_timeout_seconds, null)
    job_retry_deadline_seconds    = try(each.value.provider_config.job_retry_deadline_seconds, null)
    execution_project             = try(each.value.provider_config.execution_project, try(each.value.details.execution_project, null))
    impersonate_service_account   = try(each.value.provider_config.impersonate_service_account, null)
    dataproc_region               = try(each.value.provider_config.dataproc_region, try(each.value.details.dataproc_region, null))
    dataproc_cluster_name         = try(each.value.provider_config.dataproc_cluster_name, try(each.value.details.dataproc_cluster_name, null))
    gcs_bucket                    = try(each.value.provider_config.gcs_bucket, try(each.value.details.gcs_bucket, null))
    use_latest_adapter            = try(each.value.provider_config.use_latest_adapter, null)
  } : null

  postgres = try(each.value.type, "") == "postgres" ? {
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, try(each.value.hostname, "")))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, try(each.value.dbname, "")))
    port     = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, 5432)))
    ssh_tunnel = try(each.value.provider_config.ssh_tunnel_hostname, try(each.value.ssh_tunnel_hostname, null)) != null ? {
      hostname = try(each.value.provider_config.ssh_tunnel_hostname, each.value.ssh_tunnel_hostname)
      port     = try(each.value.provider_config.ssh_tunnel_port, try(each.value.ssh_tunnel_port, 22))
      username = try(each.value.provider_config.ssh_tunnel_username, try(each.value.ssh_tunnel_username, "dbt"))
    } : null
  } : null

  redshift = try(each.value.type, "") == "redshift" ? {
    hostname = try(each.value.provider_config.hostname, try(each.value.details.hostname, try(each.value.hostname, "")))
    dbname   = try(each.value.provider_config.dbname, try(each.value.details.dbname, try(each.value.dbname, "")))
    port     = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, 5439)))
    ssh_tunnel = try(each.value.provider_config.ssh_tunnel_hostname, try(each.value.ssh_tunnel_hostname, null)) != null ? {
      hostname = try(each.value.provider_config.ssh_tunnel_hostname, each.value.ssh_tunnel_hostname)
      port     = try(each.value.provider_config.ssh_tunnel_port, try(each.value.ssh_tunnel_port, 22))
      username = try(each.value.provider_config.ssh_tunnel_username, try(each.value.ssh_tunnel_username, "dbt"))
    } : null
  } : null

  athena = try(each.value.type, "") == "athena" ? {
    region_name         = try(each.value.provider_config.region_name, try(each.value.details.region_name, try(each.value.region_name, "")))
    database            = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, "")))
    s3_staging_dir      = try(each.value.provider_config.s3_staging_dir, try(each.value.details.s3_staging_dir, try(each.value.s3_staging_dir, "")))
    work_group          = try(each.value.provider_config.work_group, try(each.value.details.work_group, try(each.value.work_group, null)))
    s3_data_dir         = try(each.value.provider_config.s3_data_dir, try(each.value.details.s3_data_dir, try(each.value.s3_data_dir, null)))
    s3_tmp_table_dir    = try(each.value.provider_config.s3_tmp_table_dir, try(each.value.details.s3_tmp_table_dir, try(each.value.s3_tmp_table_dir, null)))
    s3_data_naming      = try(each.value.provider_config.s3_data_naming, try(each.value.details.s3_data_naming, try(each.value.s3_data_naming, null)))
    num_retries         = try(each.value.provider_config.num_retries, try(each.value.details.num_retries, try(each.value.num_retries, null)))
    num_boto3_retries   = try(each.value.provider_config.num_boto3_retries, try(each.value.details.num_boto3_retries, try(each.value.num_boto3_retries, null)))
    num_iceberg_retries = try(each.value.provider_config.num_iceberg_retries, try(each.value.details.num_iceberg_retries, try(each.value.num_iceberg_retries, null)))
    poll_interval       = try(each.value.provider_config.poll_interval, try(each.value.details.poll_interval, try(each.value.poll_interval, null)))
    spark_work_group    = try(each.value.provider_config.spark_work_group, try(each.value.details.spark_work_group, try(each.value.spark_work_group, null)))
  } : null

  fabric = try(each.value.type, "") == "fabric" ? {
    server        = try(each.value.provider_config.server, try(each.value.details.server, try(each.value.server, "")))
    database      = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, "")))
    port          = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, null)))
    retries       = try(each.value.provider_config.retries, try(each.value.details.retries, try(each.value.retries, null)))
    login_timeout = try(each.value.provider_config.login_timeout, try(each.value.details.login_timeout, try(each.value.login_timeout, null)))
    query_timeout = try(each.value.provider_config.query_timeout, try(each.value.details.query_timeout, try(each.value.query_timeout, null)))
  } : null

  synapse = try(each.value.type, "") == "synapse" ? {
    host          = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    database      = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, "")))
    port          = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, null)))
    retries       = try(each.value.provider_config.retries, try(each.value.details.retries, try(each.value.retries, null)))
    login_timeout = try(each.value.provider_config.login_timeout, try(each.value.details.login_timeout, try(each.value.login_timeout, null)))
    query_timeout = try(each.value.provider_config.query_timeout, try(each.value.details.query_timeout, try(each.value.query_timeout, null)))
  } : null

  starburst = contains(["starburst", "starburst_trino"], try(each.value.type, "")) ? {
    host   = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    port   = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, null)))
    method = try(each.value.provider_config.method, try(each.value.details.method, try(each.value.method, null)))
  } : null

  teradata = try(each.value.type, "") == "teradata" ? {
    host            = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    tmode           = try(each.value.provider_config.tmode, try(each.value.details.tmode, try(each.value.tmode, "ANSI")))
    port            = try(each.value.provider_config.port, try(each.value.details.port, try(tostring(each.value.port), null)))
    retries         = try(each.value.provider_config.retries, try(each.value.details.retries, try(each.value.retries, null)))
    request_timeout = try(each.value.provider_config.request_timeout, try(each.value.details.request_timeout, try(each.value.request_timeout, null)))
  } : null

  salesforce = try(each.value.type, "") == "salesforce" ? {
    login_url                  = try(each.value.provider_config.login_url, try(each.value.details.login_url, try(each.value.login_url, "")))
    database                   = try(each.value.provider_config.database, try(each.value.details.database, try(each.value.database, null)))
    data_transform_run_timeout = try(each.value.provider_config.data_transform_run_timeout, try(each.value.details.data_transform_run_timeout, try(each.value.data_transform_run_timeout, null)))
  } : null

  apache_spark = contains(["apache_spark", "spark"], try(each.value.type, "")) ? {
    method          = try(each.value.provider_config.method, try(each.value.details.method, try(each.value.method, "http")))
    host            = try(each.value.provider_config.host, try(each.value.details.host, try(each.value.host, "")))
    cluster         = try(each.value.provider_config.cluster, try(each.value.details.cluster, try(each.value.cluster, "")))
    port            = try(each.value.provider_config.port, try(each.value.details.port, try(each.value.port, null)))
    organization    = try(each.value.provider_config.organization, try(each.value.details.organization, try(each.value.organization, null)))
    user            = try(each.value.provider_config.user, try(each.value.details.user, try(each.value.user, null)))
    auth            = try(each.value.provider_config.auth, try(each.value.details.auth, try(each.value.auth, null)))
    connect_timeout = try(each.value.provider_config.connect_timeout, try(each.value.details.connect_timeout, try(each.value.connect_timeout, null)))
    connect_retries = try(each.value.provider_config.connect_retries, try(each.value.details.connect_retries, try(each.value.connect_retries, null)))
  } : null

  lifecycle {
    prevent_destroy = true
  }
}
