output "notification_ids" {
  description = "Map of notification key to dbt Cloud notification ID"
  value       = { for k, n in dbtcloud_notification.notifications : k => n.id }
}
