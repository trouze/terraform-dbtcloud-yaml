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
| [dbtcloud_oauth_configuration.oauth_configurations](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/oauth_configuration) | resource |
| [dbtcloud_oauth_configuration.protected_oauth_configurations](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/oauth_configuration) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_oauth_client_secrets"></a> [oauth\_client\_secrets](#input\_oauth\_client\_secrets) | Map of OAuth config key to client secret value | `map(string)` | `{}` | no |
| <a name="input_oauth_data"></a> [oauth\_data](#input\_oauth\_data) | List of OAuth configuration entries from YAML oauth\_configurations[] (optional: id for resource\_metadata.source\_id when provider supports it, protected, application\_id\_uri for Entra) | `any` | `[]` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_oauth_configuration_ids"></a> [oauth\_configuration\_ids](#output\_oauth\_configuration\_ids) | Map of OAuth configuration key to dbt Cloud OAuth configuration ID |
<!-- END_TF_DOCS -->