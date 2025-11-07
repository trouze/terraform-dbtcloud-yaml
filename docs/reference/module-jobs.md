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
| [dbtcloud_job.job](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/job) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_environment_ids"></a> [environment\_ids](#input\_environment\_ids) | The ID of the project this repository is associated with | `map(string)` | n/a | yes |
| <a name="input_environments_data"></a> [environments\_data](#input\_environments\_data) | List of environment configurations, including credentials | `any` | n/a | yes |
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The ID of the project to which jobs belong | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_job_ids"></a> [job\_ids](#output\_job\_ids) | n/a |
