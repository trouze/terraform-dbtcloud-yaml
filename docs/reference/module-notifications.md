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
| [dbtcloud_notification.notifications](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/notification) | resource |
| [dbtcloud_notification.protected_notifications](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/notification) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_notifications_data"></a> [notifications\_data](#input\_notifications\_data) | List of notification configurations from YAML notifications[] | `any` | `[]` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_notification_ids"></a> [notification\_ids](#output\_notification\_ids) | Map of notification key to dbt Cloud notification ID |
<!-- END_TF_DOCS -->