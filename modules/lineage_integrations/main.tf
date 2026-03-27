terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  all_integrations = flatten([
    for p in var.projects : [
      for li in try(p.lineage_integrations, []) : {
        project_key   = try(p.key, p.name)
        project_id    = var.project_ids[try(p.key, p.name)]
        li_key        = try(li.key, li.name)
        composite_key = "${try(p.key, p.name)}_${try(li.key, li.name)}"
        li_data       = li
      }
    ]
  ])

  integrations_map = {
    for item in local.all_integrations :
    item.composite_key => item
  }
}

resource "dbtcloud_lineage_integration" "integrations" {
  for_each = local.integrations_map

  project_id = each.value.project_id
  host       = each.value.li_data.host
  site_id    = each.value.li_data.site_id
  token_name = each.value.li_data.token_name
  token = try(
    lookup(var.lineage_tokens, each.key, null),
    each.value.li_data.token
  )
}
