output "notification_ids" {
  description = "Map of notification key to dbt Cloud notification ID"
  value = merge(
    { for k, n in dbtcloud_notification.notifications : k => n.id },
    { for k, n in dbtcloud_notification.protected_notifications : k => n.id },
  )
}

output "notifications_provenance" {
  description = "Per-notification provenance (YAML key, logical identity, optional external id) merged with dbt_notification_id — mirrors v2 resource_metadata without provider support"
  value = {
    for key, meta in local.notifications_provenance_meta :
    key => merge(
      meta,
      {
        dbt_notification_id = coalesce(
          try(dbtcloud_notification.notifications[key].id, null),
          try(dbtcloud_notification.protected_notifications[key].id, null),
        )
      },
    )
  }
}
