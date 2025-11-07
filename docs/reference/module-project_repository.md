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
| [dbtcloud_project_repository.project_repository](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/project_repository) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_id"></a> [project\_id](#input\_project\_id) | The ID of the project this repository is associated with | `string` | n/a | yes |
| <a name="input_repository_id"></a> [repository\_id](#input\_repository\_id) | The ID of the repository this project is associated with | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_project_repository_id"></a> [project\_repository\_id](#output\_project\_repository\_id) | n/a |
