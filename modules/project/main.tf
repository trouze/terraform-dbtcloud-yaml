terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  # Normalize projects: ensure each entry has a key field.
  # For single-project YAML without a key:, fall back to the project name.
  projects_map = {
    for p in var.projects :
    try(p.key, p.name) => p
  }

  protected_projects_map = {
    for k, p in local.projects_map :
    k => p
    if try(p.protected, false) == true
  }

  unprotected_projects_map = {
    for k, p in local.projects_map :
    k => p
    if try(p.protected, false) != true
  }
}

#############################################
# Unprotected Projects
#############################################

resource "dbtcloud_project" "projects" {
  for_each = local.unprotected_projects_map

  name = "${var.target_name}${each.value.name}"
}

#############################################
# Protected Projects — lifecycle.prevent_destroy
#############################################

resource "dbtcloud_project" "protected_projects" {
  for_each = local.protected_projects_map

  name = "${var.target_name}${each.value.name}"

  lifecycle {
    prevent_destroy = true
  }
}
