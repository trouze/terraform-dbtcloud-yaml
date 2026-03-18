#############################################
# Profiles
#
# Project-scoped profiles that tie together connections, credentials,
# and optional extended attributes for deployment environments.
#############################################

locals {
  all_profiles = flatten([
    for project in var.projects : [
      for profile in try(project.profiles, []) : {
        project_key  = project.key
        project_id   = local.project_id_lookup[project.key]
        profile_key  = profile.key
        profile_data = profile
      }
    ]
  ])

  protected_profiles = [
    for item in local.all_profiles :
    item
    if try(item.profile_data.protected, false) == true
  ]

  unprotected_profiles = [
    for item in local.all_profiles :
    item
    if try(item.profile_data.protected, false) != true
  ]

  resolve_profile_connection_id = {
    for item in local.all_profiles :
    "${item.project_key}_${item.profile_key}" => (
      can(regex("^LOOKUP:", tostring(item.profile_data.connection_key))) ?
      local.lookup_connection_ids[item.profile_data.connection_key] :
      contains(keys(dbtcloud_global_connection.connections), item.profile_data.connection_key) ?
      dbtcloud_global_connection.connections[item.profile_data.connection_key].id :
      contains(keys(dbtcloud_global_connection.protected_connections), item.profile_data.connection_key) ?
      dbtcloud_global_connection.protected_connections[item.profile_data.connection_key].id :
      try(tonumber(item.profile_data.connection_key), null)
    )
  }

  resolve_profile_credential_id = {
    for item in local.all_profiles :
    "${item.project_key}_${item.profile_key}" => coalesce(
      lookup(local.resolve_credential_id, "${item.project_key}_${item.profile_key}", null),
      lookup(local.resolve_environment_credential_id, "${item.project_key}_${try(item.profile_data.credentials_key, "")}", null),
      lookup(local.source_credential_id_to_target_id, tostring(try(item.profile_data.credentials_id, null)), null),
      try(tonumber(item.profile_data.credentials_key), null)
    )
  }

  resolve_profile_extended_attributes_id = {
    for item in local.all_profiles :
    "${item.project_key}_${item.profile_key}" => (
      try(item.profile_data.extended_attributes_key, null) != null && try(item.profile_data.extended_attributes_key, "") != "" ?
      lookup(local.resolve_extended_attributes_id, "${item.project_key}_${item.profile_data.extended_attributes_key}", null) :
      (
      try(item.profile_data.extended_attributes_id, null) != null ?
      lookup(
        local.source_extended_attributes_id_to_target_id,
        tostring(item.profile_data.extended_attributes_id),
        null
      ) :
      null
      )
    )
  }

  resolve_profile_id = merge(
    {
      for item in local.unprotected_profiles :
      "${item.project_key}_${item.profile_key}" =>
      dbtcloud_profile.profiles["${item.project_key}_${item.profile_key}"].profile_id
    },
    {
      for item in local.protected_profiles :
      "${item.project_key}_${item.profile_key}" =>
      dbtcloud_profile.protected_profiles["${item.project_key}_${item.profile_key}"].profile_id
    }
  )
}

resource "dbtcloud_profile" "profiles" {
  for_each = {
    for item in local.unprotected_profiles :
    "${item.project_key}_${item.profile_key}" => item
  }

  project_id             = each.value.project_id
  key                    = each.value.profile_key
  connection_id          = local.resolve_profile_connection_id[each.key]
  credentials_id         = local.resolve_profile_credential_id[each.key]
  extended_attributes_id = local.resolve_profile_extended_attributes_id[each.key]

  resource_metadata = {
    source_project_id  = lookup(local.source_project_ids_by_key, each.value.project_key, null)
    source_id          = try(each.value.profile_data.id, null)
    source_identity    = "PRF:${each.value.project_key}:${each.value.profile_key}"
    source_key         = each.value.profile_key
    source_name        = each.value.profile_key
    source_project_key = each.value.project_key
  }
}

resource "dbtcloud_profile" "protected_profiles" {
  for_each = {
    for item in local.protected_profiles :
    "${item.project_key}_${item.profile_key}" => item
  }

  project_id             = each.value.project_id
  key                    = each.value.profile_key
  connection_id          = local.resolve_profile_connection_id[each.key]
  credentials_id         = local.resolve_profile_credential_id[each.key]
  extended_attributes_id = local.resolve_profile_extended_attributes_id[each.key]

  resource_metadata = {
    source_project_id  = lookup(local.source_project_ids_by_key, each.value.project_key, null)
    source_id          = try(each.value.profile_data.id, null)
    source_identity    = "PRF:${each.value.project_key}:${each.value.profile_key}"
    source_key         = each.value.profile_key
    source_name        = each.value.profile_key
    source_project_key = each.value.project_key
  }

  lifecycle {
    prevent_destroy = true
  }
}
