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
| [dbtcloud_environment_variable.environment_variables](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/environment_variable) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_environment_ids"></a> [environment\_ids](#input\_environment\_ids) | The ID of the project this repository is associated with | `map(string)` | n/a | yes |
| <a name="input_environment_variables"></a> [environment\_variables](#input\_environment\_variables) | A list of environment variable configurations | `any` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The ID of the project to which jobs belong | `string` | n/a | yes |
| <a name="input_token_map"></a> [token\_map](#input\_token\_map) | Mapping of token names to credential | `map(string)` | n/a | yes |

## Outputs

No outputs.
