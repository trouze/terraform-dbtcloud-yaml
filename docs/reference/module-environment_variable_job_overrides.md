Populated from each project’s `jobs[]` entries that set **`environment_variable_overrides`**: a map of variable name to string. The root module passes resolved job IDs and project IDs after jobs are created. See [YAML Schema — environment variable job overrides](../configuration/yaml-schema.md#environment_variable_overrides).

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
| [dbtcloud_environment_variable_job_override.environment_variable_job_overrides](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/environment_variable_job_override) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_environments_data"></a> [environments\_data](#input\_environments\_data) | List of environment configurations, including credentials, overrides | `any` | n/a | yes |
| <a name="input_job_ids"></a> [job\_ids](#input\_job\_ids) | Map of Env Name \_ Job Name as key : Job ID | `any` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The ID of the project to which jobs belong | `string` | n/a | yes |

## Outputs

No outputs.
