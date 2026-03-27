output "semantic_layer_ids" {
  description = "Map of project key to semantic_layer_configuration resource ID"
  value       = { for k, sl in dbtcloud_semantic_layer_configuration.semantic_layer : k => sl.id }
}
