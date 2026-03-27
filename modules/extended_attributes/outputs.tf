output "extended_attribute_ids" {
  description = "Map of composite key (project_key_ea_key) to extended_attributes resource ID"
  value       = { for k, ea in dbtcloud_extended_attributes.extended_attributes : k => ea.id }
}
