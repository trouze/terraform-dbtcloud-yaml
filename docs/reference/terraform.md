## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.0 |
| <a name="requirement_dbtcloud"></a> [dbtcloud](#requirement\_dbtcloud) | ~> 1.8 |

## Providers

No providers.

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_account_features"></a> [account\_features](#module\_account\_features) | ./modules/account_features | n/a |
| <a name="module_credentials"></a> [credentials](#module\_credentials) | ./modules/credentials | n/a |
| <a name="module_environment_variable_job_overrides"></a> [environment\_variable\_job\_overrides](#module\_environment\_variable\_job\_overrides) | ./modules/environment_variable_job_overrides | n/a |
| <a name="module_environment_variables"></a> [environment\_variables](#module\_environment\_variables) | ./modules/environment_variables | n/a |
| <a name="module_environments"></a> [environments](#module\_environments) | ./modules/environments | n/a |
| <a name="module_extended_attributes"></a> [extended\_attributes](#module\_extended\_attributes) | ./modules/extended_attributes | n/a |
| <a name="module_global_connections"></a> [global\_connections](#module\_global\_connections) | ./modules/global_connections | n/a |
| <a name="module_groups"></a> [groups](#module\_groups) | ./modules/groups | n/a |
| <a name="module_ip_restrictions"></a> [ip\_restrictions](#module\_ip\_restrictions) | ./modules/ip_restrictions | n/a |
| <a name="module_jobs"></a> [jobs](#module\_jobs) | ./modules/jobs | n/a |
| <a name="module_lineage_integrations"></a> [lineage\_integrations](#module\_lineage\_integrations) | ./modules/lineage_integrations | n/a |
| <a name="module_notifications"></a> [notifications](#module\_notifications) | ./modules/notifications | n/a |
| <a name="module_oauth_configurations"></a> [oauth\_configurations](#module\_oauth\_configurations) | ./modules/oauth_configurations | n/a |
| <a name="module_profiles"></a> [profiles](#module\_profiles) | ./modules/profiles | n/a |
| <a name="module_project"></a> [project](#module\_project) | ./modules/project | n/a |
| <a name="module_project_artefacts"></a> [project\_artefacts](#module\_project\_artefacts) | ./modules/project_artefacts | n/a |
| <a name="module_project_repository"></a> [project\_repository](#module\_project\_repository) | ./modules/project_repository | n/a |
| <a name="module_repository"></a> [repository](#module\_repository) | ./modules/repository | n/a |
| <a name="module_semantic_layer"></a> [semantic\_layer](#module\_semantic\_layer) | ./modules/semantic_layer | n/a |
| <a name="module_service_tokens"></a> [service\_tokens](#module\_service\_tokens) | ./modules/service_tokens | n/a |
| <a name="module_user_groups"></a> [user\_groups](#module\_user\_groups) | ./modules/user_groups | n/a |

## Resources

No resources.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_dbt_account_id"></a> [dbt\_account\_id](#input\_dbt\_account\_id) | dbt Cloud account ID | `number` | n/a | yes |
| <a name="input_dbt_host_url"></a> [dbt\_host\_url](#input\_dbt\_host\_url) | dbt Cloud host URL (e.g., https://cloud.getdbt.com) | `string` | n/a | yes |
| <a name="input_dbt_pat"></a> [dbt\_pat](#input\_dbt\_pat) | dbt Cloud personal access token (for GitHub App integration; can equal dbt\_token) | `string` | `null` | no |
| <a name="input_dbt_token"></a> [dbt\_token](#input\_dbt\_token) | dbt Cloud API token for authentication | `string` | n/a | yes |
| <a name="input_yaml_file"></a> [yaml\_file](#input\_yaml\_file) | Path to the YAML file defining dbt Cloud resources | `string` | n/a | yes |
| <a name="input_target_name"></a> [target\_name](#input\_target\_name) | Default target name for dbt jobs (e.g., 'prod') | `string` | `""` | no |
| <a name="input_token_map"></a> [token\_map](#input\_token\_map) | Map of Databricks token names to values. Key corresponds to `credential.token_name` in YAML. | `map(string)` | `{}` | no |
| <a name="input_environment_credentials"></a> [environment\_credentials](#input\_environment\_credentials) | Map of environment credential objects keyed by `"{project_key}_{env_key}"`. Each object must include `credential_type` and type-specific fields. Supports 14 warehouse types. | `map(any)` | `{}` | no |
| <a name="input_connection_credentials"></a> [connection\_credentials](#input\_connection\_credentials) | Map of global connection keys to OAuth/auth credential objects. Key corresponds to `global_connections[].key` in YAML. | `map(any)` | `{}` | no |
| <a name="input_lineage_tokens"></a> [lineage\_tokens](#input\_lineage\_tokens) | Map of lineage integration tokens keyed by `"{project_key}_{integration_key}"`. | `map(string)` | `{}` | no |
| <a name="input_oauth_client_secrets"></a> [oauth\_client\_secrets](#input\_oauth\_client\_secrets) | Map of OAuth configuration keys to their client secrets. Key corresponds to `oauth_configurations[].key` in YAML. | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_project_ids"></a> [project\_ids](#output\_project\_ids) | Map of project keys to their dbt Cloud IDs |
| <a name="output_environment_ids"></a> [environment\_ids](#output\_environment\_ids) | Map of environment keys (project\_key\_env\_key) to their dbt Cloud IDs |
| <a name="output_job_ids"></a> [job\_ids](#output\_job\_ids) | Map of job keys to their dbt Cloud IDs |
| <a name="output_credential_ids"></a> [credential\_ids](#output\_credential\_ids) | Map of credential keys to their dbt Cloud IDs |
| <a name="output_repository_ids"></a> [repository\_ids](#output\_repository\_ids) | Map of project keys to their dbt Cloud repository IDs |
| <a name="output_connection_ids"></a> [connection\_ids](#output\_connection\_ids) | Map of global connection keys to their dbt Cloud IDs |
| <a name="output_service_token_ids"></a> [service\_token\_ids](#output\_service\_token\_ids) | Map of service token keys to their dbt Cloud IDs |
| <a name="output_group_ids"></a> [group\_ids](#output\_group\_ids) | Map of group keys to their dbt Cloud IDs |
