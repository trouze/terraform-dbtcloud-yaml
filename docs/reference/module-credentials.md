<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.7 |
| <a name="requirement_dbtcloud"></a> [dbtcloud](#requirement\_dbtcloud) | ~> 1.9 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_dbtcloud"></a> [dbtcloud](#provider\_dbtcloud) | 1.9.1 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [dbtcloud_athena_credential.credentials](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/athena_credential) | resource |
| [dbtcloud_bigquery_credential.credentials](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/bigquery_credential) | resource |
| [dbtcloud_databricks_credential.credentials](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/databricks_credential) | resource |
| [dbtcloud_fabric_credential.credentials_sp](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/fabric_credential) | resource |
| [dbtcloud_fabric_credential.credentials_sql](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/fabric_credential) | resource |
| [dbtcloud_postgres_credential.credentials](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/postgres_credential) | resource |
| [dbtcloud_redshift_credential.credentials](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/redshift_credential) | resource |
| [dbtcloud_snowflake_credential.credentials_keypair](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/snowflake_credential) | resource |
| [dbtcloud_snowflake_credential.credentials_password](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/snowflake_credential) | resource |
| [dbtcloud_spark_credential.credentials](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/spark_credential) | resource |
| [dbtcloud_starburst_credential.credentials](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/starburst_credential) | resource |
| [dbtcloud_synapse_credential.credentials_sp](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/synapse_credential) | resource |
| [dbtcloud_synapse_credential.credentials_sql](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/synapse_credential) | resource |
| [dbtcloud_teradata_credential.credentials](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/teradata_credential) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | List of project configurations. Each project's environments may have a 'credential' sub-object. | `any` | n/a | yes |
| <a name="input_environment_credentials"></a> [environment\_credentials](#input\_environment\_credentials) | Map of composite key (project\_key\_env\_key) to credential objects. Each object must include 'credential\_type' to select the warehouse adapter. | `map(any)` | `{}` | no |
| <a name="input_token_map"></a> [token\_map](#input\_token\_map) | Map of token names to their values (used for legacy Databricks token\_name references) | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_credential_ids"></a> [credential\_ids](#output\_credential\_ids) | Map of composite key (project\_key\_env\_key or project\_key\_profile\_key) to credential ID. Merges all warehouse types. |
| <a name="output_credential_ids_by_source_id"></a> [credential\_ids\_by\_source\_id](#output\_credential\_ids\_by\_source\_id) | Maps YAML credential.id (environment or standalone profile credentials, legacy dbt Cloud ID) to Terraform-managed credential\_id after apply (COMPAT v2/importer). |
<!-- END_TF_DOCS -->