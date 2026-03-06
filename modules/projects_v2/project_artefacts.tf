#############################################
# Project Artefacts (docs/freshness job IDs)
# Singleton per project — only created when docs_job_key or freshness_job_key is set.
#############################################

locals {
  # Build a job ID lookup from all created jobs (both protected and unprotected)
  job_id_by_key = merge(
    {
      for key, job in dbtcloud_job.jobs :
      key => job.id
    },
    {
      for key, job in dbtcloud_job.protected_jobs :
      key => job.id
    }
  )

  project_artefacts_list = flatten([
    for project in var.projects : [
      {
        project_key      = project.key
        project_id       = local.project_id_lookup[project.key]
        docs_job_key     = try(project.project_artefacts.docs_job_key, null)
        freshness_job_key = try(project.project_artefacts.freshness_job_key, null)
      }
    ] if try(project.project_artefacts, null) != null
  ])

  project_artefacts_map = {
    for item in local.project_artefacts_list :
    item.project_key => item
    if item.docs_job_key != null || item.freshness_job_key != null
  }
}

resource "dbtcloud_project_artefacts" "artefacts" {
  for_each = local.project_artefacts_map

  project_id = each.value.project_id

  docs_job_id = (
    each.value.docs_job_key != null
    ? try(local.job_id_by_key["${each.value.project_key}_${each.value.docs_job_key}"], null)
    : null
  )

  freshness_job_id = (
    each.value.freshness_job_key != null
    ? try(local.job_id_by_key["${each.value.project_key}_${each.value.freshness_job_key}"], null)
    : null
  )

  depends_on = [
    dbtcloud_project.projects,
    dbtcloud_project.protected_projects,
    dbtcloud_job.jobs,
    dbtcloud_job.protected_jobs,
  ]
}
