## Requirements

No requirements.

## Providers

| Name | Version |
|------|---------|
| <a name="provider_dbtcloud"></a> [dbtcloud](#provider\_dbtcloud) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [dbtcloud_databricks_credential.databricks_credential](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/databricks_credential) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_environments_data"></a> [environments\_data](#input\_environments\_data) | List of environment configurations, including credentials | `any` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The ID of the project these credentials belong to | `string` | n/a | yes |
| <a name="input_token_map"></a> [token\_map](#input\_token\_map) | Mapping of token names to credential | `map(string)` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_credential_ids"></a> [credential\_ids](#output\_credential\_ids) | Map of environment names to their credential IDs |
