terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

resource "dbtcloud_project_repository" "project_repositories" {
  for_each = var.repository_ids

  project_id    = var.project_ids[each.key]
  repository_id = each.value
}
