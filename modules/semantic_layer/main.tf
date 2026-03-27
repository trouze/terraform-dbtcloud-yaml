terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  # Only create semantic layer config for projects that have a semantic_layer block
  semantic_layer_map = {
    for p in var.projects :
    try(p.key, p.name) => p
    if try(p.semantic_layer, null) != null
  }
}

resource "dbtcloud_semantic_layer_configuration" "semantic_layer" {
  for_each = local.semantic_layer_map

  project_id = var.project_ids[each.key]
  environment_id = lookup(
    var.environment_ids,
    "${each.key}_${each.value.semantic_layer.environment}",
    null
  )
}
