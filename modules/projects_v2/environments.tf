#############################################
# Environments and Credentials
# 
# Creates credentials and environments for each project.
# Credentials are created based on credential type from environment_credentials.
# Environments reference global connections and credentials.
# Supports protected resources with lifecycle.prevent_destroy.
#############################################

locals {
  # Helper to get project_id from either protected or unprotected projects
  # This allows environments to reference their parent project regardless of protection status
  project_id_lookup = {
    for project in var.projects :
    project.key => (
      try(project.protected, false) == true
      ? dbtcloud_project.protected_projects[project.key].id
      : dbtcloud_project.projects[project.key].id
    )
  }

  # Flatten all environments across all projects with project context
  all_environments = flatten([
    for project in var.projects : [
      for env in project.environments : {
        project_key = project.key
        project_id  = local.project_id_lookup[project.key]
        env_key     = env.key
        env_data    = env
      }
    ]
  ])

  #############################################
  # Protection: Split environments into protected/unprotected
  #############################################

  # Protected environments (protected: true in env_data)
  protected_environments = [
    for item in local.all_environments :
    item
    if try(item.env_data.protected, false) == true
  ]

  # Unprotected environments (protected: false or not set)
  unprotected_environments = [
    for item in local.all_environments :
    item
    if try(item.env_data.protected, false) != true
  ]

  # Non-sensitive set of token names available in token_map
  # Use nonsensitive() to extract keys from sensitive map for filtering
  # Keys themselves are not sensitive, only the values are
  available_token_names = toset(nonsensitive(keys(var.token_map)))

  # Non-sensitive set of environment credential keys
  # Extract keys from sensitive map for filtering in for_each
  available_env_cred_keys = toset(nonsensitive(keys(var.environment_credentials)))

  # Map of environment credential types for use in for_each conditions
  # Use nonsensitive() because credential_type itself is not sensitive - only the actual
  # credential values (passwords, keys) are. This allows using credential_type in for_each.
  env_cred_types = nonsensitive({
    for k, v in var.environment_credentials :
    k => try(v.credential_type, "")
  })

  # Map of tenant_id presence for Fabric/Synapse auth type routing
  # Use nonsensitive() because we only care about presence (true/false), not the actual value
  env_cred_has_tenant = nonsensitive({
    for k, v in var.environment_credentials :
    k => try(v.tenant_id, null) != null
  })

  # Helper to resolve connection ID from reference (key, LOOKUP, or ID)
  resolve_connection_id = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => (
      # If it's a LOOKUP placeholder, use lookup map
      can(regex("^LOOKUP:", tostring(item.env_data.connection))) ?
      local.lookup_connection_ids[item.env_data.connection] :
      # Try to look up as a connection key first (most common case after fix)
      # Check if connection key exists in the connections map
      contains(keys(dbtcloud_global_connection.connections), item.env_data.connection) ?
      dbtcloud_global_connection.connections[item.env_data.connection].id :
      # Check protected connections too
      contains(keys(dbtcloud_global_connection.protected_connections), item.env_data.connection) ?
      dbtcloud_global_connection.protected_connections[item.env_data.connection].id :
      # Fall back to numeric ID (for backward compatibility)
      # Use try() to safely attempt conversion - returns null if conversion fails
      try(tonumber(item.env_data.connection), null) != null ?
      tonumber(item.env_data.connection) :
      # If all else fails, this is an error case
      null
    )
  }

  # Determine credential type from connection type (used for legacy token_map approach)
  credential_type_map = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => (
      # First check if we have environment_credentials with explicit type
      contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") ?
      try(var.environment_credentials["${item.project_key}_${item.env_key}"].credential_type, "databricks") :
      # Fallback to inferring from connection type
      lookup(local.connections_map, try(item.env_data.connection, ""), {}) != {} ?
      lookup(local.connections_map, item.env_data.connection, {}).type :
      "databricks"
    )
  }
}

#############################################
# Databricks Credentials
# Uses token_map for sensitive token value
#############################################
resource "dbtcloud_databricks_credential" "credentials" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if(
      # Legacy approach: Use token_map with token_name from YAML
      (
        try(item.env_data.credential, null) != null &&
        try(item.env_data.credential.token_name, null) != null &&
        contains(local.available_token_names, item.env_data.credential.token_name) &&
        try(item.env_data.credential.schema, null) != null
      ) ||
      # New approach: Use environment_credentials with credential_type = databricks
      (
        contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
        try(local.env_cred_types["${item.project_key}_${item.env_key}"], "") == "databricks"
      )
    )
  }

  project_id = each.value.project_id
  # Prefer environment_credentials token, fall back to token_map
  token = (
    contains(local.available_env_cred_keys, each.key) ?
    try(var.environment_credentials[each.key].token, null) :
    lookup(var.token_map, try(each.value.env_data.credential.token_name, ""), null)
  )
  schema = coalesce(
    try(var.environment_credentials[each.key].schema, null),
    try(each.value.env_data.credential.schema, null)
  )
  catalog = coalesce(
    try(var.environment_credentials[each.key].catalog, null),
    try(each.value.env_data.credential.catalog, null)
  )
  adapter_type = "databricks"
}

#############################################
# Snowflake Credentials
#############################################
resource "dbtcloud_snowflake_credential" "credentials" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    try(local.env_cred_types["${item.project_key}_${item.env_key}"], "") == "snowflake"
  }

  project_id             = each.value.project_id
  auth_type              = try(var.environment_credentials[each.key].auth_type, "password")
  num_threads            = try(var.environment_credentials[each.key].num_threads, 4)
  schema                 = try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, null))
  user                   = try(var.environment_credentials[each.key].user, null)
  password               = try(var.environment_credentials[each.key].password, null)
  private_key            = try(var.environment_credentials[each.key].private_key, null)
  private_key_passphrase = try(var.environment_credentials[each.key].private_key_passphrase, null)
  warehouse              = try(var.environment_credentials[each.key].warehouse, null)
  role                   = try(var.environment_credentials[each.key].role, null)
  database               = try(var.environment_credentials[each.key].database, null)
}

#############################################
# BigQuery Credentials
#############################################
resource "dbtcloud_bigquery_credential" "credentials" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    try(local.env_cred_types["${item.project_key}_${item.env_key}"], "") == "bigquery"
  }

  project_id  = each.value.project_id
  dataset     = try(var.environment_credentials[each.key].dataset, try(each.value.env_data.credential.schema, ""))
  num_threads = try(var.environment_credentials[each.key].num_threads, 4)
}

#############################################
# Postgres Credentials (also used for Redshift)
#############################################
resource "dbtcloud_postgres_credential" "credentials" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    contains(["postgres", "redshift"], try(local.env_cred_types["${item.project_key}_${item.env_key}"], ""))
  }

  project_id     = each.value.project_id
  type           = try(var.environment_credentials[each.key].target_name, var.environment_credentials[each.key].credential_type)
  username       = try(var.environment_credentials[each.key].username, "")
  password       = try(var.environment_credentials[each.key].password, null)
  default_schema = try(var.environment_credentials[each.key].default_schema, try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, null)))
  num_threads    = try(var.environment_credentials[each.key].num_threads, null)
}

#############################################
# Athena Credentials
#############################################
resource "dbtcloud_athena_credential" "credentials" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    try(local.env_cred_types["${item.project_key}_${item.env_key}"], "") == "athena"
  }

  project_id            = each.value.project_id
  aws_access_key_id     = try(var.environment_credentials[each.key].aws_access_key_id, "")
  aws_secret_access_key = try(var.environment_credentials[each.key].aws_secret_access_key, "")
  schema                = try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, ""))
}

#############################################
# Fabric Credentials - SQL Auth
# Uses user + password authentication
#############################################
resource "dbtcloud_fabric_credential" "credentials_sql" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    try(local.env_cred_types["${item.project_key}_${item.env_key}"], "") == "fabric" &&
    !try(local.env_cred_has_tenant["${item.project_key}_${item.env_key}"], false)
  }

  project_id           = each.value.project_id
  adapter_type         = "fabric"
  schema               = try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, ""))
  user                 = try(var.environment_credentials[each.key].user, "")
  password             = try(var.environment_credentials[each.key].password, "")
  schema_authorization = try(var.environment_credentials[each.key].schema_authorization, null)
}

#############################################
# Fabric Credentials - Service Principal Auth
# Uses tenant_id + client_id + client_secret authentication
#############################################
resource "dbtcloud_fabric_credential" "credentials_sp" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    try(local.env_cred_types["${item.project_key}_${item.env_key}"], "") == "fabric" &&
    try(local.env_cred_has_tenant["${item.project_key}_${item.env_key}"], false)
  }

  project_id           = each.value.project_id
  adapter_type         = "fabric"
  schema               = try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, ""))
  tenant_id            = try(var.environment_credentials[each.key].tenant_id, "")
  client_id            = try(var.environment_credentials[each.key].client_id, "")
  client_secret        = try(var.environment_credentials[each.key].client_secret, "")
  schema_authorization = try(var.environment_credentials[each.key].schema_authorization, null)
}

#############################################
# Synapse Credentials - SQL Auth
# Uses user + password authentication
#############################################
resource "dbtcloud_synapse_credential" "credentials_sql" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    try(local.env_cred_types["${item.project_key}_${item.env_key}"], "") == "synapse" &&
    !try(local.env_cred_has_tenant["${item.project_key}_${item.env_key}"], false)
  }

  project_id           = each.value.project_id
  adapter_type         = "synapse"
  authentication       = try(var.environment_credentials[each.key].authentication, "sql")
  schema               = try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, ""))
  user                 = try(var.environment_credentials[each.key].user, "")
  password             = try(var.environment_credentials[each.key].password, "")
  schema_authorization = try(var.environment_credentials[each.key].schema_authorization, null)
}

#############################################
# Synapse Credentials - Service Principal Auth
# Uses tenant_id + client_id + client_secret authentication
#############################################
resource "dbtcloud_synapse_credential" "credentials_sp" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    try(local.env_cred_types["${item.project_key}_${item.env_key}"], "") == "synapse" &&
    try(local.env_cred_has_tenant["${item.project_key}_${item.env_key}"], false)
  }

  project_id           = each.value.project_id
  adapter_type         = "synapse"
  authentication       = try(var.environment_credentials[each.key].authentication, "ServicePrincipal")
  schema               = try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, ""))
  tenant_id            = try(var.environment_credentials[each.key].tenant_id, "")
  client_id            = try(var.environment_credentials[each.key].client_id, "")
  client_secret        = try(var.environment_credentials[each.key].client_secret, "")
  schema_authorization = try(var.environment_credentials[each.key].schema_authorization, null)
}

#############################################
# Starburst/Trino Credentials
#############################################
resource "dbtcloud_starburst_credential" "credentials" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    contains(["starburst", "trino"], try(local.env_cred_types["${item.project_key}_${item.env_key}"], ""))
  }

  project_id = each.value.project_id
  database   = try(var.environment_credentials[each.key].catalog, try(each.value.env_data.credential.catalog, ""))
  schema     = try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, ""))
  user       = try(var.environment_credentials[each.key].user, "")
  password   = try(var.environment_credentials[each.key].password, "")
}

#############################################
# Spark Credentials
#############################################
resource "dbtcloud_spark_credential" "credentials" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    contains(["spark", "apache_spark"], try(local.env_cred_types["${item.project_key}_${item.env_key}"], ""))
  }

  project_id = each.value.project_id
  schema     = try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, ""))
  token      = try(var.environment_credentials[each.key].token, "")
}

#############################################
# Teradata Credentials
#############################################
resource "dbtcloud_teradata_credential" "credentials" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if contains(local.available_env_cred_keys, "${item.project_key}_${item.env_key}") &&
    try(local.env_cred_types["${item.project_key}_${item.env_key}"], "") == "teradata"
  }

  project_id = each.value.project_id
  schema     = try(var.environment_credentials[each.key].schema, try(each.value.env_data.credential.schema, ""))
  user       = try(var.environment_credentials[each.key].user, "")
  password   = try(var.environment_credentials[each.key].password, "")
  threads    = try(var.environment_credentials[each.key].num_threads, null)
}

#############################################
# Unprotected Environments - standard lifecycle
# Note: If fusion is not available on target account, API will return an error
# This allows users to see the error and act on it, rather than silently filtering
#############################################
resource "dbtcloud_environment" "environments" {
  for_each = {
    for item in local.unprotected_environments :
    "${item.project_key}_${item.env_key}" => item
  }

  project_id    = each.value.project_id
  name          = each.value.env_data.name
  type          = each.value.env_data.type
  connection_id = local.resolve_connection_id["${each.value.project_key}_${each.value.env_key}"]

  # Look up credential_id from the appropriate credential resource based on type
  # Use try() to handle environments without credentials (returns null)
  credential_id = try(coalesce(
    try(dbtcloud_databricks_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_snowflake_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_bigquery_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_postgres_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_athena_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_fabric_credential.credentials_sql[each.key].credential_id, null),
    try(dbtcloud_fabric_credential.credentials_sp[each.key].credential_id, null),
    try(dbtcloud_synapse_credential.credentials_sql[each.key].credential_id, null),
    try(dbtcloud_synapse_credential.credentials_sp[each.key].credential_id, null),
    try(dbtcloud_starburst_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_spark_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_teradata_credential.credentials[each.key].credential_id, null),
  ), null)

  # Optional fields
  dbt_version                = try(each.value.env_data.dbt_version, null)
  enable_model_query_history = try(each.value.env_data.enable_model_query_history, null)
  custom_branch              = try(each.value.env_data.custom_branch, null)
  # deployment_type must come from the source snapshot / mapping.
  # Do NOT infer from the environment name.
  deployment_type = try(each.value.env_data.deployment_type, null)
  # Note: target_name is not a valid argument for dbtcloud_environment resource
  use_custom_branch = try(each.value.env_data.custom_branch, null) != null

  # Extended attributes (project-scoped JSON overrides)
  extended_attributes_id = try(each.value.env_data.extended_attributes_key, null) != null && each.value.env_data.extended_attributes_key != "" ? lookup(local.resolve_extended_attributes_id, "${each.value.project_key}_${each.value.env_data.extended_attributes_key}", null) : null
}

#############################################
# Protected Environments - prevent_destroy lifecycle
#############################################
resource "dbtcloud_environment" "protected_environments" {
  for_each = {
    for item in local.protected_environments :
    "${item.project_key}_${item.env_key}" => item
  }

  project_id    = each.value.project_id
  name          = each.value.env_data.name
  type          = each.value.env_data.type
  connection_id = local.resolve_connection_id["${each.value.project_key}_${each.value.env_key}"]  # Look up credential_id from the appropriate credential resource based on type
  # Use try() to handle environments without credentials (returns null)
  credential_id = try(coalesce(
    try(dbtcloud_databricks_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_snowflake_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_bigquery_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_postgres_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_athena_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_fabric_credential.credentials_sql[each.key].credential_id, null),
    try(dbtcloud_fabric_credential.credentials_sp[each.key].credential_id, null),
    try(dbtcloud_synapse_credential.credentials_sql[each.key].credential_id, null),
    try(dbtcloud_synapse_credential.credentials_sp[each.key].credential_id, null),
    try(dbtcloud_starburst_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_spark_credential.credentials[each.key].credential_id, null),
    try(dbtcloud_teradata_credential.credentials[each.key].credential_id, null),
  ), null)  # Optional fields
  dbt_version                = try(each.value.env_data.dbt_version, null)
  enable_model_query_history = try(each.value.env_data.enable_model_query_history, null)
  custom_branch              = try(each.value.env_data.custom_branch, null)
  deployment_type            = try(each.value.env_data.deployment_type, null)
  use_custom_branch          = try(each.value.env_data.custom_branch, null) != null

  # Extended attributes (project-scoped JSON overrides)
  extended_attributes_id = try(each.value.env_data.extended_attributes_key, null) != null && each.value.env_data.extended_attributes_key != "" ? lookup(local.resolve_extended_attributes_id, "${each.value.project_key}_${each.value.env_data.extended_attributes_key}", null) : null

  lifecycle {
    prevent_destroy = true
  }
}
