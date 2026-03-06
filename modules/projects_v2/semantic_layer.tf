#############################################
# Semantic Layer Configuration (project-scoped singleton)
# No import support in provider — create-only.
#############################################

locals {
  semantic_layer_configs_list = flatten([
    for project in var.projects : [
      {
        project_key    = project.key
        project_id     = dbtcloud_project.projects[project.key].id
        environment_id = try(project.semantic_layer_config.environment_id, null)
        source_id      = try(project.semantic_layer_config.id, null)
      }
    ] if try(project.semantic_layer_config, null) != null
  ])

  semantic_layer_configs_map = {
    for item in local.semantic_layer_configs_list :
    item.project_key => item
  }
}

resource "dbtcloud_semantic_layer_configuration" "configs" {
  for_each = local.semantic_layer_configs_map

  project_id     = each.value.project_id
  environment_id = each.value.environment_id

  depends_on = [
    dbtcloud_project.projects,
    dbtcloud_environment.environments,
  ]
}
