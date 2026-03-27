terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  notifications_map = {
    for n in var.notifications_data :
    try(n.key, n.name) => n
  }
}

resource "dbtcloud_notification" "notifications" {
  for_each = local.notifications_map

  user_id            = try(each.value.user_id, null)
  on_cancel          = try(each.value.on_cancel, [])
  on_failure         = try(each.value.on_failure, [])
  on_success         = try(each.value.on_success, [])
  on_warning         = try(each.value.on_warning, [])
  notification_type  = try(each.value.notification_type, 1)
  slack_channel_id   = try(each.value.slack_channel_id, null)
  slack_channel_name = try(each.value.slack_channel_name, null)
  external_email     = try(each.value.external_email, null)
}
