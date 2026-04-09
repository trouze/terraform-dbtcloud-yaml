<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.7 |
| <a name="requirement_dbtcloud"></a> [dbtcloud](#requirement\_dbtcloud) | ~> 1.9 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_dbtcloud"></a> [dbtcloud](#provider\_dbtcloud) | ~> 1.9 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [dbtcloud_global_connection.connections](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/global_connection) | resource |
| [dbtcloud_global_connection.protected_connections](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/global_connection) | resource |
| [dbtcloud_privatelink_endpoints.all](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/data-sources/privatelink_endpoints) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_connection_credentials"></a> [connection\_credentials](#input\_connection\_credentials) | Map of connection key to OAuth/auth credential objects (sensitive fields like private\_key, client\_secret) | `map(any)` | `{}` | no |
| <a name="input_connections_data"></a> [connections\_data](#input\_connections\_data) | List of global connection configurations from YAML global\_connections[] | `any` | `[]` | no |
| <a name="input_privatelink_endpoints"></a> [privatelink\_endpoints](#input\_privatelink\_endpoints) | Optional account-level PrivateLink endpoint registry (key + endpoint\_id) for resolving global\_connections[].private\_link\_endpoint\_key | `any` | `[]` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_connection_ids"></a> [connection\_ids](#output\_connection\_ids) | Map of connection key to dbt Cloud global connection ID |
<!-- END_TF_DOCS -->