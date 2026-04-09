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
| [dbtcloud_repository.protected_repositories](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/repository) | resource |
| [dbtcloud_repository.repositories](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/repository) | resource |
| [dbtcloud_privatelink_endpoints.all](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/data-sources/privatelink_endpoints) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID (from modules/project output) | `map(string)` | n/a | yes |
| <a name="input_projects"></a> [projects](#input\_projects) | List of project configurations. Each project may have a 'repository' sub-object with git configuration. | `any` | n/a | yes |
| <a name="input_dbt_pat"></a> [dbt\_pat](#input\_dbt\_pat) | Personal access token for GitHub App integration discovery. If set, github\_app strategy is enabled even without an explicit installation ID. | `string` | `null` | no |
| <a name="input_enable_gitlab_deploy_token"></a> [enable\_gitlab\_deploy\_token](#input\_enable\_gitlab\_deploy\_token) | Preserve native GitLab deploy\_token strategy. Defaults to false due to known API limitations. Set to true only when GitLab OAuth access is confirmed. | `bool` | `false` | no |
| <a name="input_github_installation_by_owner"></a> [github\_installation\_by\_owner](#input\_github\_installation\_by\_owner) | Lowercase GitHub org/user login → installation id (from module data\_lookups when dbt\_pat is set). Used to set github\_installation\_id when not in YAML. | `map(any)` | `{}` | no |
| <a name="input_github_installation_fallback_id"></a> [github\_installation\_fallback\_id](#input\_github\_installation\_fallback\_id) | First GitHub App installation id in the account when owner-based match fails (from module data\_lookups) | `number` | `null` | no |
| <a name="input_privatelink_endpoints"></a> [privatelink\_endpoints](#input\_privatelink\_endpoints) | Optional account-level PrivateLink registry (key + endpoint\_id) for resolving repository.private\_link\_endpoint\_key | `list(any)` | `[]` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_protected_repository_keys"></a> [protected\_repository\_keys](#output\_protected\_repository\_keys) | Project keys whose dbtcloud\_repository uses lifecycle.prevent\_destroy (for module.project\_repository split). |
| <a name="output_repository_ids"></a> [repository\_ids](#output\_repository\_ids) | Map of project key to repository\_id (integer ID used for project\_repository links) |
<!-- END_TF_DOCS -->