output "lineage_integration_ids" {
  description = "Map of composite key (project_key_integration_key) to lineage integration ID"
  value       = { for k, li in dbtcloud_lineage_integration.integrations : k => li.id }
}
