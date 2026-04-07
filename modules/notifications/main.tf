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
  # COMPAT(v1-schema): for_each key from key or legacy name — align with v2 schema when canonical.
  notifications_map = {
    for n in var.notifications_data :
    try(n.key, n.name) => n
  }

  unprotected_notifications_map = {
    for k, n in local.notifications_map :
    k => n if try(n.protected, false) != true
  }

  protected_notifications_map = {
    for k, n in local.notifications_map :
    k => n if try(n.protected, false) == true
  }

  # v2 set resource_metadata on dbtcloud_notification; stock provider has no such argument.
  notifications_provenance_meta = {
    for key, n in local.notifications_map :
    key => {
      source_key      = key
      source_name     = n.name
      source_identity = "NTO:${key}"
      source_id       = try(n.id, null)
      protected       = try(n.protected, false)
    }
  }
}

resource "dbtcloud_notification" "notifications" {
  for_each = local.unprotected_notifications_map

  user_id            = try(each.value.user_id, null)
  on_cancel          = try(each.value.on_cancel, [])
  on_failure         = try(each.value.on_failure, [])
  on_success         = try(each.value.on_success, [])
  on_warning         = try(each.value.on_warning, [])
  notification_type  = try(each.value.notification_type, 1)
  slack_channel_id   = try(each.value.slack_channel_id, null)
  slack_channel_name = try(each.value.slack_channel_name, null)
  external_email     = try(each.value.external_email, null)
  state              = try(each.value.state, 1)
}

resource "dbtcloud_notification" "protected_notifications" {
  for_each = local.protected_notifications_map

  user_id            = try(each.value.user_id, null)
  on_cancel          = try(each.value.on_cancel, [])
  on_failure         = try(each.value.on_failure, [])
  on_success         = try(each.value.on_success, [])
  on_warning         = try(each.value.on_warning, [])
  notification_type  = try(each.value.notification_type, 1)
  slack_channel_id   = try(each.value.slack_channel_id, null)
  slack_channel_name = try(each.value.slack_channel_name, null)
  external_email     = try(each.value.external_email, null)
  state              = try(each.value.state, 1)

  lifecycle {
    prevent_destroy = true
  }
}
