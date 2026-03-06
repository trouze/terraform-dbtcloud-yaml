#############################################
# Lineage Integrations (project-scoped)
# Token is sensitive — sourced from var.lineage_tokens.
#############################################

locals {
  lineage_integrations_list = flatten([
    for project in var.projects : [
      for li in try(project.lineage_integrations, []) : {
        project_key     = project.key
        project_id      = dbtcloud_project.projects[project.key].id
        integration_key = li.key
        host            = try(li.host, null)
        site_id         = try(li.site_id, null)
        token_name      = try(li.token_name, null)
        source_id       = try(li.id, null)
      }
    ]
  ])

  lineage_integrations_map = {
    for item in local.lineage_integrations_list :
    "${item.project_key}_${item.integration_key}" => item
  }
}

resource "dbtcloud_lineage_integration" "integrations" {
  for_each = local.lineage_integrations_map

  project_id = each.value.project_id
  host       = each.value.host
  site_id    = each.value.site_id
  token_name = each.value.token_name
  token      = lookup(var.lineage_tokens, each.key, "")

  resource_metadata = {
    source_project_id  = lookup(local.source_project_ids_by_key, each.value.project_key, null)
    source_id          = each.value.source_id
    source_identity    = "LNGI:${each.value.project_key}:${each.value.integration_key}"
    source_key         = each.value.integration_key
    source_name        = each.value.integration_key
    source_project_key = each.value.project_key
  }

  depends_on = [dbtcloud_project.projects]
}
