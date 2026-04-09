<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.14 |
| <a name="requirement_dbtcloud"></a> [dbtcloud](#requirement\_dbtcloud) | ~> 1.9 |
| <a name="requirement_http"></a> [http](#requirement\_http) | ~> 3.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_terraform"></a> [terraform](#provider\_terraform) | n/a |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_account_features"></a> [account\_features](#module\_account\_features) | ./modules/account_features | n/a |
| <a name="module_credentials"></a> [credentials](#module\_credentials) | ./modules/credentials | n/a |
| <a name="module_data_lookups"></a> [data\_lookups](#module\_data\_lookups) | ./modules/data_lookups | n/a |
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

| Name | Type |
|------|------|
| [terraform_data.validate_yaml_config](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/resources/data) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_yaml_file"></a> [yaml\_file](#input\_yaml\_file) | Path to the YAML file defining dbt Cloud resources. Must set version: 1 with account, globals.* (connections, optional groups, service\_tokens, notifications, privatelink\_endpoints), and projects[] — see schemas/v1.json. Root locals hoist globals into top-level keys modules consume and normalize environment\_variables[].environment\_values from maps to lists. | `string` | n/a | yes |
| <a name="input_connection_credentials"></a> [connection\_credentials](#input\_connection\_credentials) | Map of global connection keys to their OAuth/auth credential objects (client\_id, client\_secret, private\_key, etc.) | `map(any)` | `{}` | no |
| <a name="input_dbt_account_id"></a> [dbt\_account\_id](#input\_dbt\_account\_id) | dbt Cloud account ID | `number` | `null` | no |
| <a name="input_dbt_host_url"></a> [dbt\_host\_url](#input\_dbt\_host\_url) | dbt Cloud host URL (e.g., https://cloud.getdbt.com or custom domain). Required by the Terraform dbtcloud provider; version: 1 YAML account.host\_url is used only for HTTP lookups (module data\_lookups) when this variable is null — mirror account.host\_url here for real applies. | `string` | `null` | no |
| <a name="input_dbt_pat"></a> [dbt\_pat](#input\_dbt\_pat) | dbt Cloud personal access token for GitHub App integration discovery (service tokens cannot access the integrations API) | `string` | `null` | no |
| <a name="input_dbt_token"></a> [dbt\_token](#input\_dbt\_token) | dbt Cloud API token for authentication | `string` | `null` | no |
| <a name="input_enable_gitlab_deploy_token"></a> [enable\_gitlab\_deploy\_token](#input\_enable\_gitlab\_deploy\_token) | Preserve native GitLab deploy\_token strategy. Defaults to false due to a known API limitation (GitlabGetError on some accounts). Set to true only when GitLab OAuth access is confirmed. | `bool` | `false` | no |
| <a name="input_environment_credentials"></a> [environment\_credentials](#input\_environment\_credentials) | Map of credential keys to warehouse credential objects. Key format: project\_key\_env\_key for environments, or project\_key\_profile\_key for standalone profile-owned credentials. Supports 14 warehouse types via credential\_type field. | `map(any)` | `{}` | no |
| <a name="input_lineage_tokens"></a> [lineage\_tokens](#input\_lineage\_tokens) | Map of lineage integration keys to their authentication tokens (Tableau, Looker, etc.) | `map(string)` | `{}` | no |
| <a name="input_oauth_client_secrets"></a> [oauth\_client\_secrets](#input\_oauth\_client\_secrets) | Map of OAuth configuration keys to their client secrets | `map(string)` | `{}` | no |
| <a name="input_skip_global_project_permissions"></a> [skip\_global\_project\_permissions](#input\_skip\_global\_project\_permissions) | When true, account-level group permissions from YAML are applied as all\_projects-only blocks so Terraform does not add edges to project resources (scoped adoption of globals). | `bool` | `false` | no |
| <a name="input_target_name"></a> [target\_name](#input\_target\_name) | Default target name for the dbt project (e.g., 'dev', 'prod') | `string` | `""` | no |
| <a name="input_token_map"></a> [token\_map](#input\_token\_map) | Map of token names to secret values. Used for legacy Databricks credential.token\_name in YAML and for jobs[].environment\_variable\_overrides values prefixed with secret\_ (lookup key is the string after the prefix). | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_connection_ids"></a> [connection\_ids](#output\_connection\_ids) | Map of global connection key (and LOOKUP:… placeholders) to dbt Cloud connection ID — merged managed global\_connections + data\_lookups |
| <a name="output_credential_ids"></a> [credential\_ids](#output\_credential\_ids) | Map of composite key (project\_key\_env\_key or project\_key\_profile\_key) to credential ID |
| <a name="output_environment_ids"></a> [environment\_ids](#output\_environment\_ids) | Map of composite key (project\_key\_env\_key) to dbt Cloud environment ID |
| <a name="output_extended_attribute_ids"></a> [extended\_attribute\_ids](#output\_extended\_attribute\_ids) | Map of composite key (project\_key\_ea\_key) to dbt Cloud extended\_attributes\_id (numeric API id) |
| <a name="output_github_installation_by_owner"></a> [github\_installation\_by\_owner](#output\_github\_installation\_by\_owner) | GitHub App installation id by org/user login (from dbt integrations API when dbt\_pat is set) |
| <a name="output_github_installation_fallback_id"></a> [github\_installation\_fallback\_id](#output\_github\_installation\_fallback\_id) | First GitHub installation id when owner-based match is not used |
| <a name="output_group_ids"></a> [group\_ids](#output\_group\_ids) | Map of group key to dbt Cloud group ID |
| <a name="output_ip_rule_ids"></a> [ip\_rule\_ids](#output\_ip\_rule\_ids) | Map of IP rule key to dbt Cloud IP restriction rule ID |
| <a name="output_job_ids"></a> [job\_ids](#output\_job\_ids) | Map of composite key (project\_key\_job\_key) to dbt Cloud job ID |
| <a name="output_lineage_integration_ids"></a> [lineage\_integration\_ids](#output\_lineage\_integration\_ids) | Map of composite key (project\_key\_integration\_key) to lineage integration ID |
| <a name="output_lookup_connection_ids"></a> [lookup\_connection\_ids](#output\_lookup\_connection\_ids) | Subset of connection\_ids from LOOKUP:… resolution only (empty if module.data\_lookups not used) |
| <a name="output_notification_ids"></a> [notification\_ids](#output\_notification\_ids) | Map of notification key to dbt Cloud notification ID |
| <a name="output_oauth_configuration_ids"></a> [oauth\_configuration\_ids](#output\_oauth\_configuration\_ids) | Map of OAuth configuration key to dbt Cloud OAuth configuration ID |
| <a name="output_profile_ids"></a> [profile\_ids](#output\_profile\_ids) | Map of composite key (project\_key\_profile\_key) to dbt Cloud profile\_id (numeric API id) |
| <a name="output_project_artefact_ids"></a> [project\_artefact\_ids](#output\_project\_artefact\_ids) | Map of project key to dbt Cloud project\_artefacts resource ID |
| <a name="output_project_ids"></a> [project\_ids](#output\_project\_ids) | Map of project key to dbt Cloud project ID |
| <a name="output_repository_ids"></a> [repository\_ids](#output\_repository\_ids) | Map of project key to repository ID |
| <a name="output_semantic_layer_ids"></a> [semantic\_layer\_ids](#output\_semantic\_layer\_ids) | Map of project key to dbt Cloud semantic layer configuration ID |
| <a name="output_service_token_ids"></a> [service\_token\_ids](#output\_service\_token\_ids) | Map of service token key to dbt Cloud service token ID |
| <a name="output_yaml_account"></a> [yaml\_account](#output\_yaml\_account) | The YAML account block (name, host\_url, id) |
| <a name="output_yaml_schema_version"></a> [yaml\_schema\_version](#output\_yaml\_schema\_version) | YAML version key from the config file (must be 1; see schemas/v1.json) |
<!-- END_TF_DOCS -->