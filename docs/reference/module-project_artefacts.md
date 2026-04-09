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
| [dbtcloud_project_artefacts.artefacts](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/project_artefacts) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | Project configs. Optional project\_artefacts block (docs\_job\_key, freshness\_job\_key); see modules/project\_artefacts. | `any` | n/a | yes |
| <a name="input_job_ids"></a> [job\_ids](#input\_job\_ids) | Map of composite key (project\_key\_job\_key) to dbt Cloud job ID (from jobs module) | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_project_artefact_ids"></a> [project\_artefact\_ids](#output\_project\_artefact\_ids) | Map of project key to project\_artefacts resource ID |
<!-- END_TF_DOCS -->