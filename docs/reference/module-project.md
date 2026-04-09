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
| [dbtcloud_project.projects](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/project) | resource |
| [dbtcloud_project.protected_projects](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/project) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_projects"></a> [projects](#input\_projects) | List of project configurations. Each entry must have at minimum a 'name' field, and optionally a 'key' field (defaults to name) and 'protected' boolean. | `any` | n/a | yes |
| <a name="input_target_name"></a> [target\_name](#input\_target\_name) | Optional prefix prepended to all project names (e.g., 'dev-' or 'prod-') | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_project_ids"></a> [project\_ids](#output\_project\_ids) | Map of project key to dbt Cloud project ID |
<!-- END_TF_DOCS -->