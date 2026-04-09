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
| [dbtcloud_environment_variable.environment_variables](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/environment_variable) | resource |
| [dbtcloud_environment_variable.protected_environment_variables](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/environment_variable) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | List of project configurations. Each project may have an 'environment\_variables' list. | `any` | n/a | yes |
| <a name="input_token_map"></a> [token\_map](#input\_token\_map) | Map of token names to values (used for secret\_ prefixed env var values) | `map(string)` | `{}` | no |

## Outputs

No outputs.
<!-- END_TF_DOCS -->