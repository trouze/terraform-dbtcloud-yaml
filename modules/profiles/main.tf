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
  all_profiles = flatten([
    for p in var.projects : [
      for profile in try(p.profiles, []) : {
        project_key   = try(p.key, p.name)
        project_id    = var.project_ids[try(p.key, p.name)]
        profile_key   = try(profile.key, profile.name)
        composite_key = "${try(p.key, p.name)}_${try(profile.key, profile.name)}"
        profile_data  = profile
      }
    ]
  ])

  protected_profiles_map = {
    for item in local.all_profiles :
    item.composite_key => item
    if try(item.profile_data.protected, false) == true
  }

  unprotected_profiles_map = {
    for item in local.all_profiles :
    item.composite_key => item
    if try(item.profile_data.protected, false) != true
  }

  # Global connection key, LOOKUP:… (via root global_connection_ids_effective), or numeric id.
  resolve_profile_connection_id = {
    for item in local.all_profiles :
    item.composite_key => (
      try(item.profile_data.connection_key, null) != null ?
      lookup(var.global_connection_ids, tostring(item.profile_data.connection_key), null) != null ?
      lookup(var.global_connection_ids, tostring(item.profile_data.connection_key), null) :
      try(tonumber(item.profile_data.connection_key), null) :
      null
    )
  }

  resolve_profile_credential_id = {
    for item in local.all_profiles :
    item.composite_key => try(coalesce(
      lookup(var.credential_ids, item.composite_key, null),
      try(item.profile_data.credentials_key, null) != null && try(item.profile_data.credentials_key, "") != "" ?
      lookup(var.credential_ids, "${item.project_key}_${item.profile_data.credentials_key}", null) : null,
      try(item.profile_data.credentials_id, null) != null ?
      lookup(var.credential_ids_by_source_id, tostring(item.profile_data.credentials_id), null) : null,
      try(tonumber(item.profile_data.credentials_id), null),
    ), null)
  }

  resolve_profile_extended_attributes_id = {
    for item in local.all_profiles :
    item.composite_key => try(coalesce(
      try(item.profile_data.extended_attributes_key, null) != null && try(item.profile_data.extended_attributes_key, "") != "" ?
      lookup(var.extended_attribute_ids, "${item.project_key}_${item.profile_data.extended_attributes_key}", null) : null,
      try(item.profile_data.extended_attributes_id, null) != null ?
      lookup(var.extended_attribute_ids_by_source_id, tostring(item.profile_data.extended_attributes_id), null) : null,
      try(tonumber(item.profile_data.extended_attributes_id), null)
    ), null)
  }
}

resource "dbtcloud_profile" "profiles" {
  for_each = local.unprotected_profiles_map

  project_id             = each.value.project_id
  key                    = each.value.profile_key
  connection_id          = local.resolve_profile_connection_id[each.key]
  credentials_id         = local.resolve_profile_credential_id[each.key]
  extended_attributes_id = local.resolve_profile_extended_attributes_id[each.key]

  # Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_profile (terraform providers schema).
  # resource_metadata = {
  #   source_project_id  = null # v2 importer: lookup(local.source_project_ids_by_key, each.value.project_key, null)
  #   source_id          = try(each.value.profile_data.id, null)
  #   source_identity    = "PRF:${each.value.project_key}:${each.value.profile_key}"
  #   source_key         = each.value.profile_key
  #   source_name        = each.value.profile_key
  #   source_project_key = each.value.project_key
  # }
}

resource "dbtcloud_profile" "protected_profiles" {
  for_each = local.protected_profiles_map

  project_id             = each.value.project_id
  key                    = each.value.profile_key
  connection_id          = local.resolve_profile_connection_id[each.key]
  credentials_id         = local.resolve_profile_credential_id[each.key]
  extended_attributes_id = local.resolve_profile_extended_attributes_id[each.key]

  # Deferred: stock dbtcloud provider has no resource_metadata on dbtcloud_profile (terraform providers schema).
  # resource_metadata = {
  #   source_project_id  = null # v2 importer: lookup(local.source_project_ids_by_key, each.value.project_key, null)
  #   source_id          = try(each.value.profile_data.id, null)
  #   source_identity    = "PRF:${each.value.project_key}:${each.value.profile_key}"
  #   source_key         = each.value.profile_key
  #   source_name        = each.value.profile_key
  #   source_project_key = each.value.project_key
  # }

  lifecycle {
    prevent_destroy = true
  }
}
