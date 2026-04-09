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
| [dbtcloud_extended_attributes.extended_attributes](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/extended_attributes) | resource |
| [dbtcloud_extended_attributes.protected_extended_attributes](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/extended_attributes) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | List of project configurations. Each project may have an 'extended\_attributes' list. | `any` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_extended_attribute_ids"></a> [extended\_attribute\_ids](#output\_extended\_attribute\_ids) | Map of composite key (project\_key\_ea\_key) to dbt Cloud extended\_attributes\_id (numeric API id for environments/profiles). |
| <a name="output_extended_attribute_ids_by_source_id"></a> [extended\_attribute\_ids\_by\_source\_id](#output\_extended\_attribute\_ids\_by\_source\_id) | Maps YAML extended\_attributes[].id (legacy dbt Cloud id) to Terraform-managed extended\_attributes\_id after apply. |
<!-- END_TF_DOCS -->