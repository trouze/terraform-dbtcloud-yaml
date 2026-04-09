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
| [dbtcloud_lineage_integration.integrations](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/lineage_integration) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | List of project configurations. Each project may have a 'lineage\_integrations' list. | `any` | n/a | yes |
| <a name="input_lineage_tokens"></a> [lineage\_tokens](#input\_lineage\_tokens) | Map of composite key (project\_key\_integration\_key) to authentication token | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_lineage_integration_ids"></a> [lineage\_integration\_ids](#output\_lineage\_integration\_ids) | Map of composite key (project\_key\_integration\_key) to lineage integration ID |
<!-- END_TF_DOCS -->