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
| [dbtcloud_semantic_layer_configuration.semantic_layer](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/semantic_layer_configuration) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | Project configs. Optional semantic\_layer\_config (environment\_id and/or environment\_key); see modules/semantic\_layer. | `any` | n/a | yes |
| <a name="input_environment_ids"></a> [environment\_ids](#input\_environment\_ids) | Map of composite key (project\_key\_env\_key) to dbt Cloud environment ID (from environments module) | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_semantic_layer_ids"></a> [semantic\_layer\_ids](#output\_semantic\_layer\_ids) | Map of project key to semantic\_layer\_configuration resource ID |
<!-- END_TF_DOCS -->