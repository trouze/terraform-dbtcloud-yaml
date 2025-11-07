## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_dbtcloud"></a> [dbtcloud](#requirement\_dbtcloud) | ~> 1.3 |

## Providers

No providers.

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_credentials"></a> [credentials](#module\_credentials) | ./modules/credentials | n/a |
| <a name="module_environment_variable_job_overrides"></a> [environment\_variable\_job\_overrides](#module\_environment\_variable\_job\_overrides) | ./modules/environment_variable_job_overrides | n/a |
| <a name="module_environment_variables"></a> [environment\_variables](#module\_environment\_variables) | ./modules/environment_variables | n/a |
| <a name="module_environments"></a> [environments](#module\_environments) | ./modules/environments | n/a |
| <a name="module_jobs"></a> [jobs](#module\_jobs) | ./modules/jobs | n/a |
| <a name="module_project"></a> [project](#module\_project) | ./modules/project | n/a |
| <a name="module_project_repository"></a> [project\_repository](#module\_project\_repository) | ./modules/project_repository | n/a |
| <a name="module_repository"></a> [repository](#module\_repository) | ./modules/repository | n/a |

## Resources

No resources.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_dbt_account_id"></a> [dbt\_account\_id](#input\_dbt\_account\_id) | dbt Cloud account ID | `number` | n/a | yes |
| <a name="input_dbt_host_url"></a> [dbt\_host\_url](#input\_dbt\_host\_url) | dbt Cloud host URL (e.g., https://cloud.getdbt.com or custom domain) | `string` | n/a | yes |
| <a name="input_dbt_pat"></a> [dbt\_pat](#input\_dbt\_pat) | n/a | `string` | `""` | no |
| <a name="input_dbt_token"></a> [dbt\_token](#input\_dbt\_token) | dbt Cloud API token for authentication | `string` | n/a | yes |
| <a name="input_target_name"></a> [target\_name](#input\_target\_name) | Default target name for the dbt project (e.g., 'dev', 'prod') | `string` | `""` | no |
| <a name="input_token_map"></a> [token\_map](#input\_token\_map) | Map of credential token names to their actual values (e.g., Databricks tokens). Token names should correspond to credential.token\_name in YAML. | `map(string)` | `{}` | no |
| <a name="input_yaml_file"></a> [yaml\_file](#input\_yaml\_file) | Path to the YAML file defining dbt Cloud resources (projects, environments, jobs, etc.) | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_credential_ids"></a> [credential\_ids](#output\_credential\_ids) | Map of credential names to their dbt Cloud IDs |
| <a name="output_environment_ids"></a> [environment\_ids](#output\_environment\_ids) | Map of environment names to their dbt Cloud IDs |
| <a name="output_job_ids"></a> [job\_ids](#output\_job\_ids) | Map of job names to their dbt Cloud IDs |
| <a name="output_project_id"></a> [project\_id](#output\_project\_id) | The dbt Cloud project ID |
| <a name="output_repository_id"></a> [repository\_id](#output\_repository\_id) | The dbt Cloud repository ID |
