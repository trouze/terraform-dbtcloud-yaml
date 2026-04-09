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
| [dbtcloud_user_groups.user_groups](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/user_groups) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_group_ids"></a> [group\_ids](#input\_group\_ids) | Map of group key to dbt Cloud group ID (from groups module) | `map(string)` | `{}` | no |
| <a name="input_user_groups_data"></a> [user\_groups\_data](#input\_user\_groups\_data) | List of user-to-group assignments from YAML user\_groups[]. Each entry has user\_id, group\_keys; optional key (for\_each key, default user\_id) and optional id (resource\_metadata.source\_id when provider supports it). | `any` | `[]` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_user_group_ids"></a> [user\_group\_ids](#output\_user\_group\_ids) | Map of assignment key (YAML key or string user\_id) to dbtcloud\_user\_groups resource ID |
<!-- END_TF_DOCS -->