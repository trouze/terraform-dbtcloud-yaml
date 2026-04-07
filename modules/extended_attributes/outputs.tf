output "extended_attribute_ids" {
  description = "Map of composite key (project_key_ea_key) to dbt Cloud extended_attributes_id (numeric API id for environments/profiles)."
  value = merge(
    {
      for k, ea in dbtcloud_extended_attributes.extended_attributes :
      k => ea.extended_attributes_id
    },
    {
      for k, ea in dbtcloud_extended_attributes.protected_extended_attributes :
      k => ea.extended_attributes_id
    }
  )
}

output "extended_attribute_ids_by_source_id" {
  description = "Maps YAML extended_attributes[].id (legacy dbt Cloud id) to Terraform-managed extended_attributes_id after apply."
  value       = local.extended_attribute_ids_by_source_id
}
