output "credential_ids" {
  description = "Map of environment names to their credential IDs"
  value = { for env, cred in dbtcloud_databricks_credential.databricks_credential : env => cred.credential_id }
}
