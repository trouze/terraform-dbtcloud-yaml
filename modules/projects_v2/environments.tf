#############################################
# Environments and Credentials
# 
# Creates credentials and environments for each project.
# Credentials are created based on connection type.
# Environments reference global connections and credentials.
#############################################

locals {
  # Flatten all environments across all projects with project context
  all_environments = flatten([
    for project in var.projects : [
      for env in project.environments : {
        project_key = project.key
        project_id  = dbtcloud_project.projects[project.key].id
        env_key     = env.key
        env_data    = env
      }
    ]
  ])

  # Helper to resolve connection ID from reference (key, LOOKUP, or ID)
  resolve_connection_id = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => (
      # If it's a LOOKUP placeholder, use lookup map
      can(regex("^LOOKUP:", tostring(item.env_data.connection))) ?
      local.lookup_connection_ids[item.env_data.connection] :
      # If it's a numeric ID, use it directly
      can(try(tonumber(item.env_data.connection), null)) ?
      tonumber(item.env_data.connection) :
      # Otherwise, it's a key reference to a global connection
      dbtcloud_global_connection.connections[item.env_data.connection].id
    )
  }

  # Determine credential type from connection type
  # This is a simplified mapping - in practice, you may need to check the connection details
  credential_type_map = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => (
      # Infer credential type from connection type
      # This is a simplified approach - you may need to check connection details
      lookup(local.connections_map, try(item.env_data.connection, ""), {}) != {} ?
      lookup(local.connections_map, item.env_data.connection, {}).type :
      "databricks" # Default fallback
    )
  }
}

# Create credentials per environment
# Note: We create Databricks credentials as a default. For other types,
# you may need to add additional credential resources (snowflake_credential, etc.)
resource "dbtcloud_databricks_credential" "credentials" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
    if try(item.env_data.credential, null) != null
  }

  project_id   = each.value.project_id
  token        = lookup(var.token_map, each.value.env_data.credential.token_name, null)
  schema       = each.value.env_data.credential.schema
  catalog      = try(each.value.env_data.credential.catalog, null)
  adapter_type = "databricks"
}

# Create environments
resource "dbtcloud_environment" "environments" {
  for_each = {
    for item in local.all_environments :
    "${item.project_key}_${item.env_key}" => item
  }

  project_id    = each.value.project_id
  name          = each.value.env_data.name
  type          = each.value.env_data.type
  connection_id = local.resolve_connection_id["${each.value.project_key}_${each.value.env_key}"]
  credential_id = try(
    dbtcloud_databricks_credential.credentials["${each.value.project_key}_${each.value.env_key}"].credential_id,
    null
  )

  # Optional fields
  dbt_version                = try(each.value.env_data.dbt_version, null)
  enable_model_query_history = try(each.value.env_data.enable_model_query_history, null)
  custom_branch              = try(each.value.env_data.custom_branch, null)
  # Note: target_name is not a valid argument for dbtcloud_environment resource
  use_custom_branch          = try(each.value.env_data.custom_branch, null) != null
}

