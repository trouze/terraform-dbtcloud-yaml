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
  protected_repository_key_set = toset(var.protected_repository_keys)

  unprotected_project_repository_ids = {
    for k, rid in var.repository_ids : k => rid
    if !contains(local.protected_repository_key_set, k)
  }

  protected_project_repository_ids = {
    for k, rid in var.repository_ids : k => rid
    if contains(local.protected_repository_key_set, k)
  }
}

resource "dbtcloud_project_repository" "project_repositories" {
  for_each = local.unprotected_project_repository_ids

  project_id    = var.project_ids[each.key]
  repository_id = each.value

  # Deferred until dbt-labs/dbtcloud supports resource_metadata on dbtcloud_project_repository (v2 parity).
  # v2 used try(project.id) / try(repo.id) from YAML for source_*_id; wire when uncommenting.
  # resource_metadata = {
  #   source_project_id  = null
  #   source_id          = null
  #   source_identity    = "PREP:${each.key}"
  #   source_key         = each.key
  #   source_project_key = each.key
  #   source_name        = each.key
  # }
}

resource "dbtcloud_project_repository" "protected_project_repositories" {
  for_each = local.protected_project_repository_ids

  project_id    = var.project_ids[each.key]
  repository_id = each.value

  # Deferred until dbt-labs/dbtcloud supports resource_metadata on dbtcloud_project_repository (v2 parity).
  # v2 used try(project.id) / try(repo.id) from YAML for source_*_id; wire when uncommenting.
  # resource_metadata = {
  #   source_project_id  = null
  #   source_id          = null
  #   source_identity    = "PREP:${each.key}"
  #   source_key         = each.key
  #   source_project_key = each.key
  #   source_name        = each.key
  # }

  lifecycle {
    prevent_destroy = true
  }
}
