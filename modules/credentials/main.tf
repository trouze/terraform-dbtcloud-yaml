terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
    }
  }
}

resource "dbtcloud_databricks_credential" "databricks_credential" {
  for_each = {
    for env in var.environments_data : env.name => env
    if try(env.credential, null) != null
  }
  project_id = var.project_id
  token      = lookup(var.token_map, each.value.credential.token_name, null)
  schema     = each.value.credential.schema
  catalog    = each.value.credential.catalog
  adapter_type = "databricks"
}
