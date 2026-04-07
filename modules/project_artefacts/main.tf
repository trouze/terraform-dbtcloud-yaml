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
  # COMPAT(v1-schema): artefacts.docs_job / freshness_job; v2/importer: project_artefacts.docs_job_key / freshness_job_key
  artefacts_rows = [
    for p in var.projects : {
      project_key = try(p.key, p.name)
      docs_job_key = (
        try(p.project_artefacts.docs_job_key, null) != null && try(tostring(p.project_artefacts.docs_job_key), "") != ""
        ? p.project_artefacts.docs_job_key
        : try(p.artefacts.docs_job, null)
      )
      freshness_job_key = (
        try(p.project_artefacts.freshness_job_key, null) != null && try(tostring(p.project_artefacts.freshness_job_key), "") != ""
        ? p.project_artefacts.freshness_job_key
        : try(p.artefacts.freshness_job, null)
      )
      has_block = try(p.artefacts, null) != null || try(p.project_artefacts, null) != null
    }
  ]

  # v2 parity: only manage dbtcloud_project_artefacts when at least one job key is set
  artefacts_map = {
    for row in local.artefacts_rows :
    row.project_key => row
    if row.has_block && (row.docs_job_key != null || row.freshness_job_key != null)
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
