terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.9"
    }
  }
}

locals {
  semantic_layer_map = {
    for p in var.projects :
    try(p.key, p.name) => p
    if try(p.semantic_layer_config, null) != null
  }

  semantic_environment_id = {
    for k, p in local.semantic_layer_map : k => (
      try(p.semantic_layer_config.environment_id, null) != null && tostring(try(p.semantic_layer_config.environment_id, null)) != ""
      ? tostring(p.semantic_layer_config.environment_id)
      : (
        length(compact([
          try(p.semantic_layer_config.environment_key, null),
          try(p.semantic_layer_config.environment, null),
        ])) > 0
        ? lookup(
          var.environment_ids,
          "${k}_${coalesce(
            try(p.semantic_layer_config.environment_key, null),
            try(p.semantic_layer_config.environment, null),
          )}",
          null
        )
        : null
      )
    )
  }
}

resource "dbtcloud_semantic_layer_configuration" "semantic_layer" {
  for_each = local.semantic_layer_map

  project_id     = var.project_ids[each.key]
  environment_id = local.semantic_environment_id[each.key]
}

# Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_semantic_layer_configuration (terraform providers schema).
# v2/importer semantic_layer_config.id would map to source_id when supported.
