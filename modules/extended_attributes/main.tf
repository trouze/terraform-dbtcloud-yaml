terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  all_extended_attributes = flatten([
    for p in var.projects : [
      for ea in try(p.extended_attributes, []) : {
        project_key   = try(p.key, p.name)
        project_id    = var.project_ids[try(p.key, p.name)]
        ea_key        = try(ea.key, ea.name)
        composite_key = "${try(p.key, p.name)}_${try(ea.key, ea.name)}"
        ea_data       = ea
      }
    ]
  ])

  ea_map = {
    for item in local.all_extended_attributes :
    item.composite_key => item
  }
}

resource "dbtcloud_extended_attributes" "extended_attributes" {
  for_each = local.ea_map

  project_id          = each.value.project_id
  extended_attributes = jsonencode(try(each.value.ea_data.content, each.value.ea_data))
}
