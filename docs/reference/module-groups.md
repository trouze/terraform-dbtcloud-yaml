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
| [dbtcloud_group.groups](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/group) | resource |
| [dbtcloud_group.protected_groups](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/group) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_groups_data"></a> [groups\_data](#input\_groups\_data) | List of group configurations from YAML groups[] | `any` | `[]` | no |
| <a name="input_skip_global_project_permissions"></a> [skip\_global\_project\_permissions](#input\_skip\_global\_project\_permissions) | When true, project-scoped permission entries are collapsed to all\_projects-only blocks so global groups do not expand the project dependency graph (scoped global-object adoption). | `bool` | `false` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_group_ids"></a> [group\_ids](#output\_group\_ids) | Map of group key to dbt Cloud group ID |
<!-- END_TF_DOCS -->