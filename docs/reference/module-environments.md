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
| [dbtcloud_environment.environments](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/environment) | resource |
| [dbtcloud_environment.protected_environments](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/environment) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | List of project configurations. Each project may have an 'environments' list. | `any` | n/a | yes |
| <a name="input_credential_ids"></a> [credential\_ids](#input\_credential\_ids) | Map of composite key (project\_key\_env\_key) to credential ID (from credentials module) | `map(string)` | `{}` | no |
| <a name="input_extended_attribute_ids"></a> [extended\_attribute\_ids](#input\_extended\_attribute\_ids) | Map of composite key (project\_key\_ea\_key) to dbt Cloud extended\_attributes\_id (numeric; from extended\_attributes module). | `map(number)` | `{}` | no |
| <a name="input_extended_attribute_ids_by_source_id"></a> [extended\_attribute\_ids\_by\_source\_id](#input\_extended\_attribute\_ids\_by\_source\_id) | Maps legacy YAML extended\_attributes[].id to Terraform-managed extended\_attributes\_id (from extended\_attributes module). | `map(number)` | `{}` | no |
| <a name="input_global_connection_ids"></a> [global\_connection\_ids](#input\_global\_connection\_ids) | Map of global connection key to connection ID (from global\_connections module). Used when YAML environments reference connections by key. | `map(string)` | `{}` | no |
| <a name="input_profile_ids"></a> [profile\_ids](#input\_profile\_ids) | Map of composite key (project\_key\_profile\_key) to dbt Cloud profile\_id (from profiles module); used when environments set primary\_profile\_key. | `map(number)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_deployment_types"></a> [deployment\_types](#output\_deployment\_types) | Map of composite key (project\_key\_env\_key) to environment deployment\_type (for job SAO validation) |
| <a name="output_environment_ids"></a> [environment\_ids](#output\_environment\_ids) | Map of composite key (project\_key\_env\_key) to dbt Cloud environment ID |
<!-- END_TF_DOCS -->