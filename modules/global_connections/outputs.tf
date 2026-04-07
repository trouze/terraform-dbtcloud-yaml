output "connection_ids" {
  description = "Map of connection key to dbt Cloud global connection ID"
  value = merge(
    { for k, c in dbtcloud_global_connection.connections : k => tostring(c.id) },
    { for k, c in dbtcloud_global_connection.protected_connections : k => tostring(c.id) }
  )
}
