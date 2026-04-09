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
| [dbtcloud_ip_restrictions_rule.ip_rules](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/ip_restrictions_rule) | resource |
| [dbtcloud_ip_restrictions_rule.protected_ip_rules](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/ip_restrictions_rule) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_ip_rules_data"></a> [ip\_rules\_data](#input\_ip\_rules\_data) | List of IP restriction rule configurations from YAML ip\_restrictions[]. Optional protected: true applies lifecycle.prevent\_destroy; optional id for resource\_metadata.source\_id when provider supports it. | `any` | `[]` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_ip_rule_ids"></a> [ip\_rule\_ids](#output\_ip\_rule\_ids) | Map of IP rule key to dbt Cloud IP restriction rule ID |
<!-- END_TF_DOCS -->