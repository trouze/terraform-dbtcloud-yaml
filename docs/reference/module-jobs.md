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
| [dbtcloud_job.jobs](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/job) | resource |
| [dbtcloud_job.protected_jobs](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/job) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_environment_ids"></a> [environment\_ids](#input\_environment\_ids) | Map of composite key (project\_key\_env\_key) to dbt Cloud environment ID (from environments module) | `map(string)` | n/a | yes |
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | List of project configurations. Jobs are defined only on project.jobs[] with environment\_key. | `any` | n/a | yes |
| <a name="input_deployment_types"></a> [deployment\_types](#input\_deployment\_types) | Map of project\_key\_env\_key to environment deployment\_type (from module.environments.deployment\_types). Used to gate run\_compare\_changes (staging/production + cross-env deferral only). | `map(any)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_job_ids"></a> [job\_ids](#output\_job\_ids) | Map of composite key (project\_key\_job\_key) to dbt Cloud job ID |
<!-- END_TF_DOCS -->