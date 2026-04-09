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
| [dbtcloud_account_features.features](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/account_features) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_features"></a> [features](#input\_features) | Account feature flags from YAML account\_features. Set to null to skip (no resource created). | `any` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_account_features_id"></a> [account\_features\_id](#output\_account\_features\_id) | The dbt Cloud account\_features resource ID (if created) |
<!-- END_TF_DOCS -->