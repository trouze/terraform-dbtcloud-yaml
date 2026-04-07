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
  artefacts_rows = [
    for p in var.projects : {
      project_key       = try(p.key, p.name)
      docs_job_key      = try(p.project_artefacts.docs_job_key, null)
      freshness_job_key = try(p.project_artefacts.freshness_job_key, null)
      has_block         = try(p.project_artefacts, null) != null
    }
  ]

  artefacts_map = {
    for row in local.artefacts_rows :
    row.project_key => row
    if row.has_block && (
      (try(row.docs_job_key, null) != null && try(tostring(row.docs_job_key), "") != "") ||
      (try(row.freshness_job_key, null) != null && try(tostring(row.freshness_job_key), "") != "")
    )
  }
}

resource "dbtcloud_project_artefacts" "artefacts" {
  for_each = local.artefacts_map

  project_id = var.project_ids[each.key]

  docs_job_id = (
    each.value.docs_job_key != null
    ? try(lookup(var.job_ids, "${each.key}_${each.value.docs_job_key}", null), null)
    : null
  )

  freshness_job_id = (
    each.value.freshness_job_key != null
    ? try(lookup(var.job_ids, "${each.key}_${each.value.freshness_job_key}", null), null)
    : null
  )
}

# Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_project_artefacts (terraform providers schema).
