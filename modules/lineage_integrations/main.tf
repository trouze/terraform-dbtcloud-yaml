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
  # Provider marks site_id / token_name required; use empty string when omitted (e.g. non-Tableau integrations).
  site_id    = coalesce(try(each.value.li_data.site_id, null), "")
  token_name = coalesce(try(each.value.li_data.token_name, null), "")
  token = coalesce(
    try(lookup(var.lineage_tokens, each.key, null), null),
    try(each.value.li_data.token, null),
    ""
  )
}

# Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_lineage_integration (terraform providers schema).
# v2/importer: resource_metadata.source_identity LNGI:<project_key>:<integration_key>; source_id from lineage_integrations[].id.
