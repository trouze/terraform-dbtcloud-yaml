#############################################
# Extended Attributes
# Project-scoped JSON config for environment-level connection overrides.
# Supports protected resources with lifecycle.prevent_destroy.
#############################################

locals {
  # Flatten extended attributes from all projects with project_id
  all_extended_attributes = flatten([
    for project in var.projects : [
      for ext in try(project.extended_attributes, []) : {
        project_key = project.key
        project_id  = local.project_id_lookup[project.key]
        ext_key     = ext.key
        ext_data    = ext
      }
    ]
  ])

  # Protected extended attributes (protected: true)
  protected_extended_attributes = [
    for item in local.all_extended_attributes :
    item
    if try(item.ext_data.protected, false) == true
  ]

  # Unprotected extended attributes
  unprotected_extended_attributes = [
    for item in local.all_extended_attributes :
    item
    if try(item.ext_data.protected, false) != true
  ]

  # Resolve extended_attributes_id for environment reference: "project_key_ext_key" => id
  resolve_extended_attributes_id = merge(
    {
      for item in local.unprotected_extended_attributes :
      "${item.project_key}_${item.ext_key}" =>
      dbtcloud_extended_attributes.extended_attrs["${item.project_key}_${item.ext_key}"].extended_attributes_id
    },
    {
      for item in local.protected_extended_attributes :
      "${item.project_key}_${item.ext_key}" =>
      dbtcloud_extended_attributes.protected_extended_attrs["${item.project_key}_${item.ext_key}"].extended_attributes_id
    }
  )
}

#############################################
# Unprotected Extended Attributes
#############################################
resource "dbtcloud_extended_attributes" "extended_attrs" {
  for_each = {
    for item in local.unprotected_extended_attributes :
    "${item.project_key}_${item.ext_key}" => item
  }

  project_id          = each.value.project_id
  state               = lookup(each.value.ext_data, "state", 1)
  extended_attributes = jsonencode(lookup(each.value.ext_data, "extended_attributes", {}))
}

#############################################
# Protected Extended Attributes - prevent_destroy
#############################################
resource "dbtcloud_extended_attributes" "protected_extended_attrs" {
  for_each = {
    for item in local.protected_extended_attributes :
    "${item.project_key}_${item.ext_key}" => item
  }

  project_id          = each.value.project_id
  state               = lookup(each.value.ext_data, "state", 1)
  extended_attributes = jsonencode(lookup(each.value.ext_data, "extended_attributes", {}))

  lifecycle {
    prevent_destroy = true
  }
}
