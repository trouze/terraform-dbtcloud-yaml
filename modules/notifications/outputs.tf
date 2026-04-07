output "notification_ids" {
  description = "Map of notification key to dbt Cloud notification ID"
  value = merge(
    { for k, n in dbtcloud_notification.notifications : k => n.id },
    { for k, n in dbtcloud_notification.protected_notifications : k => n.id },
  )
}
