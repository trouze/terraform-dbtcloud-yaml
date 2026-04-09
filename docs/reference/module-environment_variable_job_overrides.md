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
| [dbtcloud_environment_variable_job_override.environment_variable_job_overrides](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/environment_variable_job_override) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_job_ids"></a> [job\_ids](#input\_job\_ids) | Map of composite key (project\_key\_job\_key) to dbt Cloud job ID (from jobs module) | `map(string)` | n/a | yes |
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | List of project configurations. Job-level environment\_variable\_overrides on project.jobs[] (see modules/environment\_variable\_job\_overrides). | `any` | n/a | yes |
| <a name="input_token_map"></a> [token\_map](#input\_token\_map) | Secret values for override values prefixed with secret\_ (same semantics as modules/environment\_variables). | `map(string)` | `{}` | no |

## Outputs

No outputs.
<!-- END_TF_DOCS -->