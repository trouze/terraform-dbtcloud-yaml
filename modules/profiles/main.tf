terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
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

  profiles_map = {
    for item in local.all_profiles :
    item.composite_key => item
  }
}

resource "dbtcloud_profile" "profiles" {
  for_each = local.profiles_map

  project_id  = each.value.project_id
  key         = each.value.profile_key
  connection_id = try(
    lookup(var.global_connection_ids, tostring(each.value.profile_data.connection_key), null),
    try(tonumber(each.value.profile_data.connection_id), null)
  )
  credentials_id = try(
    lookup(var.credential_ids, "${each.value.project_key}_${each.value.profile_data.credential_key}", null),
    try(each.value.profile_data.credentials_id, null)
  )
  extended_attributes_id = try(
    lookup(var.extended_attribute_ids, "${each.value.project_key}_${each.value.profile_data.extended_attributes_key}", null),
    null
  )
}
