terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  # Flatten all environments across all projects that have credentials defined
  all_credential_owners = flatten([
    for p in var.projects : [
      for env in try(p.environments, []) : {
        project_key   = try(p.key, p.name)
        project_id    = var.project_ids[try(p.key, p.name)]
        env_key       = try(env.key, env.name)
        composite_key = "${try(p.key, p.name)}_${try(env.key, env.name)}"
        cred_data     = try(env.credential, null)
      }
      if try(env.credential, null) != null
    ]
  ])

  credential_owners_map = {
    for item in local.all_credential_owners :
    item.composite_key => item
  }

  # Non-sensitive helpers for for_each conditions
  available_env_cred_keys = toset(nonsensitive(keys(var.environment_credentials)))

  env_cred_types = nonsensitive({
    for k, v in var.environment_credentials :
    k => try(v.credential_type, "")
  })

  # Fabric/Synapse: service principal auth uses tenant_id
  env_cred_has_tenant = nonsensitive({
    for k, v in var.environment_credentials :
    k => try(v.tenant_id, null) != null
  })
}

#############################################
# Databricks Credentials
#############################################

resource "dbtcloud_databricks_credential" "credentials" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if(
      contains(local.available_env_cred_keys, k) &&
      try(local.env_cred_types[k], "") == "databricks"
      ) || (
      !contains(local.available_env_cred_keys, k) &&
      try(item.cred_data.credential_type, try(item.cred_data.type, "databricks")) == "databricks"
    )
  }

  project_id   = each.value.project_id
  adapter_type = "databricks"
  token        = try(var.environment_credentials[each.key].token, lookup(var.token_map, try(each.value.cred_data.token_name, ""), null))
  schema       = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  catalog      = try(var.environment_credentials[each.key].catalog, try(each.value.cred_data.catalog, null))
}

#############################################
# Snowflake Credentials — Password Auth
#############################################

resource "dbtcloud_snowflake_credential" "credentials_password" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "snowflake" &&
    try(nonsensitive(var.environment_credentials[k].auth_type), "password") == "password"
  }

  project_id  = each.value.project_id
  auth_type   = "password"
  user        = try(var.environment_credentials[each.key].user, "")
  password    = try(var.environment_credentials[each.key].password, null)
  schema      = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  num_threads = try(var.environment_credentials[each.key].num_threads, null)
  database    = try(var.environment_credentials[each.key].database, null)
  role        = try(var.environment_credentials[each.key].role, null)
  warehouse   = try(var.environment_credentials[each.key].warehouse, null)
}

#############################################
# Snowflake Credentials — Key Pair Auth
#############################################

resource "dbtcloud_snowflake_credential" "credentials_keypair" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "snowflake" &&
    try(nonsensitive(var.environment_credentials[k].auth_type), "password") == "keypair"
  }

  project_id             = each.value.project_id
  auth_type              = "keypair"
  user                   = try(var.environment_credentials[each.key].user, "")
  private_key            = try(var.environment_credentials[each.key].private_key, null)
  private_key_passphrase = try(var.environment_credentials[each.key].private_key_passphrase, null)
  schema                 = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  num_threads            = try(var.environment_credentials[each.key].num_threads, null)
  database               = try(var.environment_credentials[each.key].database, null)
  role                   = try(var.environment_credentials[each.key].role, null)
  warehouse              = try(var.environment_credentials[each.key].warehouse, null)
}

#############################################
# BigQuery Credentials
#############################################

resource "dbtcloud_bigquery_credential" "credentials" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "bigquery"
  }

  project_id  = each.value.project_id
  dataset     = try(var.environment_credentials[each.key].dataset, try(each.value.cred_data.schema, ""))
  num_threads = try(var.environment_credentials[each.key].num_threads, null)
}

#############################################
# Postgres Credentials
#############################################

resource "dbtcloud_postgres_credential" "credentials" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "postgres"
  }

  project_id     = each.value.project_id
  type           = "postgres"
  default_schema = try(var.environment_credentials[each.key].default_schema, try(each.value.cred_data.schema, ""))
  username       = try(var.environment_credentials[each.key].username, "")
  password       = try(var.environment_credentials[each.key].password, null)
  target_name    = try(var.environment_credentials[each.key].target_name, null)
  num_threads    = try(var.environment_credentials[each.key].num_threads, null)
}

#############################################
# Redshift Credentials
#############################################

resource "dbtcloud_redshift_credential" "credentials" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "redshift"
  }

  project_id     = each.value.project_id
  default_schema = try(var.environment_credentials[each.key].default_schema, try(each.value.cred_data.schema, ""))
  username       = try(var.environment_credentials[each.key].username, "")
  password       = try(var.environment_credentials[each.key].password, null)
  num_threads    = try(var.environment_credentials[each.key].num_threads, 4)
}

#############################################
# Athena Credentials
#############################################

resource "dbtcloud_athena_credential" "credentials" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "athena"
  }

  project_id            = each.value.project_id
  aws_access_key_id     = try(var.environment_credentials[each.key].aws_access_key_id, "")
  aws_secret_access_key = try(var.environment_credentials[each.key].aws_secret_access_key, "")
  schema                = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
}

#############################################
# Fabric Credentials — SQL Auth (no tenant_id)
#############################################

resource "dbtcloud_fabric_credential" "credentials_sql" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "fabric" &&
    !try(local.env_cred_has_tenant[k], false)
  }

  project_id           = each.value.project_id
  adapter_type         = "fabric"
  schema               = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  user                 = try(var.environment_credentials[each.key].user, "")
  password             = try(var.environment_credentials[each.key].password, "")
  schema_authorization = try(var.environment_credentials[each.key].schema_authorization, null)
}

#############################################
# Fabric Credentials — Service Principal Auth (tenant_id present)
#############################################

resource "dbtcloud_fabric_credential" "credentials_sp" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "fabric" &&
    try(local.env_cred_has_tenant[k], false)
  }

  project_id           = each.value.project_id
  adapter_type         = "fabric"
  schema               = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  tenant_id            = try(var.environment_credentials[each.key].tenant_id, "")
  client_id            = try(var.environment_credentials[each.key].client_id, "")
  client_secret        = try(var.environment_credentials[each.key].client_secret, "")
  schema_authorization = try(var.environment_credentials[each.key].schema_authorization, null)
}

#############################################
# Synapse Credentials — SQL Auth (no tenant_id)
#############################################

resource "dbtcloud_synapse_credential" "credentials_sql" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "synapse" &&
    !try(local.env_cred_has_tenant[k], false)
  }

  project_id           = each.value.project_id
  adapter_type         = "synapse"
  authentication       = try(var.environment_credentials[each.key].authentication, "sql")
  schema               = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  user                 = try(var.environment_credentials[each.key].user, "")
  password             = try(var.environment_credentials[each.key].password, "")
  schema_authorization = try(var.environment_credentials[each.key].schema_authorization, null)
}

#############################################
# Synapse Credentials — Service Principal Auth
#############################################

resource "dbtcloud_synapse_credential" "credentials_sp" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "synapse" &&
    try(local.env_cred_has_tenant[k], false)
  }

  project_id           = each.value.project_id
  adapter_type         = "synapse"
  authentication       = try(var.environment_credentials[each.key].authentication, "ServicePrincipal")
  schema               = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  tenant_id            = try(var.environment_credentials[each.key].tenant_id, "")
  client_id            = try(var.environment_credentials[each.key].client_id, "")
  client_secret        = try(var.environment_credentials[each.key].client_secret, "")
  schema_authorization = try(var.environment_credentials[each.key].schema_authorization, null)
}

#############################################
# Starburst / Trino Credentials
#############################################

resource "dbtcloud_starburst_credential" "credentials" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    contains(["starburst", "trino"], try(local.env_cred_types[k], ""))
  }

  project_id = each.value.project_id
  database   = try(var.environment_credentials[each.key].catalog, try(each.value.cred_data.catalog, ""))
  schema     = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  user       = try(var.environment_credentials[each.key].user, "")
  password   = try(var.environment_credentials[each.key].password, "")
}

#############################################
# Spark Credentials
#############################################

resource "dbtcloud_spark_credential" "credentials" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    contains(["spark", "apache_spark"], try(local.env_cred_types[k], ""))
  }

  project_id = each.value.project_id
  schema     = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  token      = try(var.environment_credentials[each.key].token, "")
}

#############################################
# Teradata Credentials
#############################################

resource "dbtcloud_teradata_credential" "credentials" {
  for_each = {
    for k, item in local.credential_owners_map :
    k => item
    if contains(local.available_env_cred_keys, k) &&
    try(local.env_cred_types[k], "") == "teradata"
  }

  project_id = each.value.project_id
  schema     = try(var.environment_credentials[each.key].schema, try(each.value.cred_data.schema, ""))
  user       = try(var.environment_credentials[each.key].user, "")
  password   = try(var.environment_credentials[each.key].password, "")
  threads    = try(var.environment_credentials[each.key].num_threads, null)
}
