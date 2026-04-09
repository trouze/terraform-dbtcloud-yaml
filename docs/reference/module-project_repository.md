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
| [dbtcloud_project_repository.project_repositories](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/project_repository) | resource |
| [dbtcloud_project_repository.protected_project_repositories](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/project_repository) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID | `map(string)` | n/a | yes |
| <a name="input_repository_ids"></a> [repository\_ids](#input\_repository\_ids) | Map of project key to repository\_id (the integer ID used for project\_repository links, not the resource ID) | `map(string)` | n/a | yes |
| <a name="input_protected_repository_keys"></a> [protected\_repository\_keys](#input\_protected\_repository\_keys) | Project keys that use protected dbtcloud\_repository resources; matching links get lifecycle.prevent\_destroy (v2 projects.tf parity). | `list(string)` | `[]` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_project_repository_ids"></a> [project\_repository\_ids](#output\_project\_repository\_ids) | Map of project key to project\_repository resource ID |
<!-- END_TF_DOCS -->