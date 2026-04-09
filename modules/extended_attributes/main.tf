terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.9"
    }
  }
}

locals {
  all_extended_attributes = flatten([
    for p in var.projects : [
      for ea in try(p.extended_attributes, []) : {
        project_key   = try(p.key, p.name)
        project_id    = var.project_ids[try(p.key, p.name)]
        ea_key        = try(ea.key, ea.name)
        composite_key = "${try(p.key, p.name)}_${try(ea.key, ea.name)}"
        ea_data       = ea
      }
    ]
  ])

  protected_extended_attributes = [
    for item in local.all_extended_attributes :
    item
    if try(item.ea_data.protected, false) == true
  ]

  unprotected_extended_attributes = [
    for item in local.all_extended_attributes :
    item
    if try(item.ea_data.protected, false) != true
  ]

  ea_body = {
    for item in local.all_extended_attributes :
    item.composite_key => try(item.ea_data.extended_attributes, {})
  }

  extended_attribute_ids_by_source_id = merge(
    {
      for item in local.unprotected_extended_attributes :
      tostring(try(item.ea_data.id, null)) =>
      dbtcloud_extended_attributes.extended_attributes[item.composite_key].extended_attributes_id
      if try(item.ea_data.id, null) != null
    },
    {
      for item in local.protected_extended_attributes :
      tostring(try(item.ea_data.id, null)) =>
      dbtcloud_extended_attributes.protected_extended_attributes[item.composite_key].extended_attributes_id
      if try(item.ea_data.id, null) != null
    }
  )
}

#############################################
# Unprotected extended attributes
#############################################
resource "dbtcloud_extended_attributes" "extended_attributes" {
  for_each = {
    for item in local.unprotected_extended_attributes :
    item.composite_key => item
  }

  project_id          = each.value.project_id
  state               = coalesce(try(each.value.ea_data.state, null), 1)
  extended_attributes = jsonencode(local.ea_body[each.key])

  # Deferred: stock dbtcloud provider has no resource_metadata on this resource (terraform providers schema).
  # resource_metadata = {
  #   source_project_id  = lookup(local.source_project_ids_by_key, each.value.project_key, null)
  #   source_id          = try(each.value.ea_data.id, null)
  #   source_identity    = "EXTATTR:${each.value.project_key}:${each.value.ea_key}"
  #   source_key         = each.value.ea_key
  #   source_name        = each.value.ea_key
  #   source_project_key = each.value.project_key
  # }
}

#############################################
# Protected extended attributes — lifecycle.prevent_destroy
#############################################
resource "dbtcloud_extended_attributes" "protected_extended_attributes" {
  for_each = {
    for item in local.protected_extended_attributes :
    item.composite_key => item
  }

  project_id          = each.value.project_id
  state               = coalesce(try(each.value.ea_data.state, null), 1)
  extended_attributes = jsonencode(local.ea_body[each.key])

  # Deferred: stock dbtcloud provider has no resource_metadata on this resource.
  # resource_metadata = {
  #   source_project_id  = lookup(local.source_project_ids_by_key, each.value.project_key, null)
  #   source_id          = try(each.value.ea_data.id, null)
  #   source_identity    = "EXTATTR:${each.value.project_key}:${each.value.ea_key}"
  #   source_key         = each.value.ea_key
  #   source_name        = each.value.ea_key
  #   source_project_key = each.value.project_key
  # }

  lifecycle {
    prevent_destroy = true
  }
}
