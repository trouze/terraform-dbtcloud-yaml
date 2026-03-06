#############################################
# Project Artefacts (docs/freshness job IDs)
# Singleton per project — only created when docs_job_id or freshness_job_id is set.
#############################################

locals {
  project_artefacts_list = flatten([
    for project in var.projects : [
      {
        project_key      = project.key
        project_id       = dbtcloud_project.projects[project.key].id
        docs_job_id      = try(project.project_artefacts.docs_job_id, null)
        freshness_job_id = try(project.project_artefacts.freshness_job_id, null)
      }
    ] if try(project.project_artefacts, null) != null
  ])

  project_artefacts_map = {
    for item in local.project_artefacts_list :
    item.project_key => item
  }
}

resource "dbtcloud_project_artefacts" "artefacts" {
  for_each = local.project_artefacts_map

  project_id       = each.value.project_id
  docs_job_id      = each.value.docs_job_id
  freshness_job_id = each.value.freshness_job_id

  depends_on = [
    dbtcloud_project.projects,
    dbtcloud_job.jobs,
  ]
}
