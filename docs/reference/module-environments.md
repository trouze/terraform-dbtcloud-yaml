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
| [dbtcloud_environment.environments](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/environment) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_credential_ids"></a> [credential\_ids](#input\_credential\_ids) | A map of environment names to their corresponding credential IDs | `map(string)` | `{}` | no |
| <a name="input_environments_data"></a> [environments\_data](#input\_environments\_data) | List of environment configurations, including credentials | `any` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The ID of the project to which environments belong | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_environment_ids"></a> [environment\_ids](#output\_environment\_ids) | n/a |
