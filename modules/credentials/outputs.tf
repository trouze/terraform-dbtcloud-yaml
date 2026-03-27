output "credential_ids" {
  description = "Map of composite key (project_key_env_key) to credential ID. Merges all warehouse types."
  value = merge(
    { for k, c in dbtcloud_databricks_credential.credentials : k => c.credential_id },
    { for k, c in dbtcloud_snowflake_credential.credentials_password : k => c.credential_id },
    { for k, c in dbtcloud_snowflake_credential.credentials_keypair : k => c.credential_id },
    { for k, c in dbtcloud_bigquery_credential.credentials : k => c.credential_id },
    { for k, c in dbtcloud_postgres_credential.credentials : k => c.credential_id },
    { for k, c in dbtcloud_redshift_credential.credentials : k => c.credential_id },
    { for k, c in dbtcloud_athena_credential.credentials : k => c.credential_id },
    { for k, c in dbtcloud_fabric_credential.credentials_sql : k => c.credential_id },
    { for k, c in dbtcloud_fabric_credential.credentials_sp : k => c.credential_id },
    { for k, c in dbtcloud_synapse_credential.credentials_sql : k => c.credential_id },
    { for k, c in dbtcloud_synapse_credential.credentials_sp : k => c.credential_id },
    { for k, c in dbtcloud_starburst_credential.credentials : k => c.credential_id },
    { for k, c in dbtcloud_spark_credential.credentials : k => c.credential_id },
    { for k, c in dbtcloud_teradata_credential.credentials : k => c.credential_id },
  )
}
