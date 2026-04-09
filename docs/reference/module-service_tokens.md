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
| [dbtcloud_service_token.protected_service_tokens](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/service_token) | resource |
| [dbtcloud_service_token.service_tokens](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/resources/service_token) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_project_ids"></a> [project\_ids](#input\_project\_ids) | Map of project key to dbt Cloud project ID (resolves permissions[].project\_key) | `map(number)` | `{}` | no |
| <a name="input_service_tokens_data"></a> [service\_tokens\_data](#input\_service\_tokens\_data) | List of service token configurations from YAML service\_tokens[] | `any` | `[]` | no |
| <a name="input_skip_global_project_permissions"></a> [skip\_global\_project\_permissions](#input\_skip\_global\_project\_permissions) | When true, create permissions without per-project IDs (all\_projects only); for when projects are managed outside this root module | `bool` | `false` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_service_token_ids"></a> [service\_token\_ids](#output\_service\_token\_ids) | Map of service token key to dbt Cloud service token ID |
<!-- END_TF_DOCS -->