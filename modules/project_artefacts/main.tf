terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  # Only create artefacts for projects that have an artefacts block
  artefacts_map = {
    for p in var.projects :
    try(p.key, p.name) => p
    if try(p.artefacts, null) != null
  }
}

resource "dbtcloud_project_artefacts" "artefacts" {
  for_each = local.artefacts_map

  project_id = var.project_ids[each.key]

  docs_job_id = try(
    lookup(var.job_ids, "${each.key}_${each.value.artefacts.docs_job}", null),
    null
  )

  freshness_job_id = try(
    lookup(var.job_ids, "${each.key}_${each.value.artefacts.freshness_job}", null),
    null
  )
}
