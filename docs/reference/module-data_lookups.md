<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.7 |
| <a name="requirement_dbtcloud"></a> [dbtcloud](#requirement\_dbtcloud) | ~> 1.9 |
| <a name="requirement_http"></a> [http](#requirement\_http) | ~> 3.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_dbtcloud"></a> [dbtcloud](#provider\_dbtcloud) | ~> 1.9 |
| <a name="provider_http"></a> [http](#provider\_http) | ~> 3.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [dbtcloud_global_connections.all](https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest/docs/data-sources/global_connections) | data source |
| [http_http.github_installations](https://registry.terraform.io/providers/hashicorp/http/latest/docs/data-sources/http) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_projects"></a> [projects](#input\_projects) | Project list from YAML (same shape as root local.projects) — scanned for LOOKUP: connection and repository placeholders | `any` | n/a | yes |
| <a name="input_dbt_host_url"></a> [dbt\_host\_url](#input\_dbt\_host\_url) | dbt Cloud host URL (e.g. https://cloud.getdbt.com); used for integrations HTTP calls | `string` | `null` | no |
| <a name="input_dbt_pat"></a> [dbt\_pat](#input\_dbt\_pat) | Personal access token for GitHub installations API (optional) | `string` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_github_installation_by_owner"></a> [github\_installation\_by\_owner](#output\_github\_installation\_by\_owner) | Lowercase GitHub org/user login → installation id (empty if dbt\_pat unset or API error) |
| <a name="output_github_installation_fallback_id"></a> [github\_installation\_fallback\_id](#output\_github\_installation\_fallback\_id) | First GitHub installation id when owner cannot be matched (null if none) |
| <a name="output_lookup_connection_ids"></a> [lookup\_connection\_ids](#output\_lookup\_connection\_ids) | Map from literal YAML placeholder (e.g. LOOKUP:My Warehouse) to dbt global connection id from data.dbtcloud\_global\_connections |
| <a name="output_lookup_connection_keys"></a> [lookup\_connection\_keys](#output\_lookup\_connection\_keys) | Set of LOOKUP:… placeholders found under environments.connection and profiles.connection\_key |
| <a name="output_lookup_repository_keys"></a> [lookup\_repository\_keys](#output\_lookup\_repository\_keys) | Set of LOOKUP:… values when project.repository is a scalar (importer/v2 style); object-shaped repositories are not included |
<!-- END_TF_DOCS -->