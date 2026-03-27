# YAML Schema Reference

Complete field reference for `dbt-config.yml`. Every key the module reads is documented here with its type, whether it is required, valid values, and an example.

---

## Full skeleton

The top-level keys available in any `dbt-config.yml`:

```yaml
# ── Account-level (all optional — omit any section you don't need) ────────────
account_features: { ... }
global_connections: [ ... ]
service_tokens: [ ... ]
groups: [ ... ]
user_groups: [ ... ]
notifications: [ ... ]
oauth_configurations: [ ... ]
ip_restrictions: [ ... ]

# ── Projects (required) ───────────────────────────────────────────────────────
projects:
  - name: Analytics
    key: analytics
    protected: false
    repository: { ... }
    environments: [ ... ]
    jobs: [ ... ]
    environment_variables: [ ... ]
    extended_attributes: [ ... ]
    profiles: [ ... ]
    lineage_integrations: [ ... ]
    artefacts: { ... }
    semantic_layer: { ... }
```

!!! note "Backward compatibility"
    The singular `project:` key is accepted and automatically wrapped into a one-element list. Existing single-project configs work without change.

---

## `account_features`

Singleton object. All fields are optional and default to `null` (dbt Cloud account default applies).

| Field | Type | Default | Description |
|---|---|---|---|
| `advanced_ci` | bool | null | Enable Advanced CI comparison features |
| `partial_parsing` | bool | null | Enable incremental manifest parsing |
| `repo_caching` | bool | null | Enable repository-level caching |

```yaml
account_features:
  advanced_ci: true
  partial_parsing: true
  repo_caching: false
```

---

## `global_connections`

Account-level warehouse connections shared across projects. Reference them from environments using `connection_key`.

### Common fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name in dbt Cloud |
| `key` | string | no | `name` | Unique identifier used in `connection_key` references |
| `type` | string | **yes** | — | Adapter type — see valid values below |
| `private_link_endpoint_id` | string | no | null | PrivateLink endpoint ID |
| `protected` | bool | no | false | Prevents `terraform destroy` |

**Valid `type` values:** `databricks` · `snowflake` · `bigquery` · `postgres` · `redshift`

### Databricks

```yaml
global_connections:
  - name: Databricks Production
    key: databricks_prod
    type: databricks
    host: adb-1234567890123456.7.azuredatabricks.net
    http_path: /sql/1.0/warehouses/abc1234def567890
    catalog: main                         # optional — Unity Catalog catalog name
    private_link_endpoint_id: null        # optional
    protected: false
    # OAuth credentials via connection_credentials["databricks_prod"]
```

| Field | Type | Required | Default |
|---|---|---|---|
| `host` | string | **yes** | "" |
| `http_path` | string | **yes** | "" |
| `catalog` | string | no | null |

### Snowflake

```yaml
global_connections:
  - name: Snowflake Production
    key: snowflake_prod
    type: snowflake
    account: xy12345.us-east-1
    database: ANALYTICS
    warehouse: TRANSFORMING
    role: TRANSFORMER                     # optional
    allow_sso: false                      # optional
    client_session_keep_alive: false      # optional
    # OAuth credentials via connection_credentials["snowflake_prod"]
```

| Field | Type | Required | Default |
|---|---|---|---|
| `account` | string | **yes** | "" |
| `database` | string | **yes** | "" |
| `warehouse` | string | **yes** | "" |
| `role` | string | no | null |
| `allow_sso` | bool | no | false |
| `client_session_keep_alive` | bool | no | false |

### BigQuery

```yaml
global_connections:
  - name: BigQuery Production
    key: bigquery_prod
    type: bigquery
    gcp_project_id: my-gcp-project-id
    client_email: dbt-sa@my-project.iam.gserviceaccount.com   # optional
    client_id: "123456789012345678901"                         # optional
    auth_uri: https://accounts.google.com/o/oauth2/auth       # optional
    token_uri: https://oauth2.googleapis.com/token            # optional
    auth_provider_x509_cert_url: https://www.googleapis.com/oauth2/v1/certs   # optional
    client_x509_cert_url: https://www.googleapis.com/...      # optional
    timeout_seconds: 300                                       # optional
    location: US                                               # optional
    # private_key / private_key_id via connection_credentials["bigquery_prod"]
```

| Field | Type | Required | Default |
|---|---|---|---|
| `gcp_project_id` | string | **yes** | "" |
| `client_email` | string | no | null |
| `client_id` | string | no | null |
| `auth_uri` | string | no | null |
| `token_uri` | string | no | null |
| `auth_provider_x509_cert_url` | string | no | null |
| `client_x509_cert_url` | string | no | null |
| `timeout_seconds` | number | no | null |
| `location` | string | no | null |

### Postgres

```yaml
global_connections:
  - name: Postgres Production
    key: postgres_prod
    type: postgres
    hostname: my-host.rds.amazonaws.com
    dbname: analytics
    port: 5432                            # optional — default 5432
```

| Field | Type | Required | Default |
|---|---|---|---|
| `hostname` | string | **yes** | "" |
| `dbname` | string | **yes** | "" |
| `port` | number | no | 5432 |

### Redshift

```yaml
global_connections:
  - name: Redshift Production
    key: redshift_prod
    type: redshift
    hostname: my-cluster.abc123.us-east-1.redshift.amazonaws.com
    dbname: analytics
    port: 5439                            # optional — default 5439
```

| Field | Type | Required | Default |
|---|---|---|---|
| `hostname` | string | **yes** | "" |
| `dbname` | string | **yes** | "" |
| `port` | number | no | 5439 |

---

## `service_tokens`

Account-level API service tokens.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name |
| `key` | string | no | `name` | Unique identifier |
| `permissions` | list | no | [] | List of permission objects |
| `protected` | bool | no | false | Prevents `terraform destroy` |

### `permissions[]`

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `permission_set` | string | **yes** | — | Permission level — see values below |
| `all_projects` | bool | no | true | Apply to all projects |
| `project_id` | number | no | null | Numeric project ID when `all_projects: false` |

**Valid `permission_set` values:** `account_admin` · `git_admin` · `job_admin` · `job_runner` · `job_viewer` · `member` · `metadata_only` · `owner` · `readonly` · `seeker_user` · `webhook_admin`

```yaml
service_tokens:
  - name: CI Service Token
    key: ci_token
    protected: false
    permissions:
      - permission_set: job_runner
        all_projects: true
      - permission_set: git_admin
        all_projects: false
        project_id: 12345
```

---

## `groups`

Account-level user groups.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name |
| `key` | string | no | `name` | Unique identifier |
| `assign_by_default` | bool | no | false | Auto-assign new users to this group |
| `sso_mapping_groups` | list(string) | no | null | SSO/IdP group names to sync |
| `permissions` | list | no | [] | Project-level permission grants |
| `protected` | bool | no | false | Prevents `terraform destroy` |

### `permissions[]`

Same structure as `service_tokens[].permissions[]` above.

```yaml
groups:
  - name: Developers
    key: developers
    assign_by_default: false
    sso_mapping_groups:
      - "data-team-eng"
    permissions:
      - permission_set: job_runner
        all_projects: true
```

---

## `user_groups`

Assigns existing dbt Cloud users to groups. `group_keys` references `groups[].key`.

| Field | Type | Required | Default |
|---|---|---|---|
| `user_id` | number | **yes** | — |
| `group_keys` | list(string) | no | [] |

```yaml
user_groups:
  - user_id: 12345
    group_keys:
      - developers
      - analysts
```

---

## `notifications`

Job notification rules.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name |
| `key` | string | no | `name` | Unique identifier |
| `notification_type` | number | no | 1 | See valid values below |
| `user_id` | number | no | null | dbt Cloud user ID (required for type 1) |
| `slack_channel_id` | string | no | null | Slack channel ID (required for type 2) |
| `slack_channel_name` | string | no | null | Slack channel display name (type 2) |
| `external_email` | string | no | null | Email address (required for type 3) |
| `on_failure` | list(number) | no | [] | Job IDs to notify on failure |
| `on_success` | list(number) | no | [] | Job IDs to notify on success |
| `on_cancel` | list(number) | no | [] | Job IDs to notify on cancel |
| `on_warning` | list(number) | no | [] | Job IDs to notify on warning |

**Valid `notification_type` values:**

| Value | Destination |
|---|---|
| `1` | dbt Cloud user (email) |
| `2` | Slack channel |
| `3` | External email address |

```yaml
notifications:
  # dbt Cloud user notification
  - name: prod-failures-user
    key: prod_failures_user
    notification_type: 1
    user_id: 12345
    on_failure: [1001, 1002]
    on_success: []

  # Slack channel notification
  - name: prod-failures-slack
    key: prod_failures_slack
    notification_type: 2
    slack_channel_id: C0123456789
    slack_channel_name: "#dbt-alerts"
    on_failure: [1001, 1002]
    on_cancel: [1001]

  # External email notification
  - name: prod-failures-email
    key: prod_failures_email
    notification_type: 3
    external_email: oncall@example.com
    on_failure: [1001]
```

---

## `oauth_configurations`

Account-level OAuth configurations (e.g., Snowflake OAuth, BigQuery WIF).

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name |
| `key` | string | no | `name` | Unique identifier |
| `type` | string | **yes** | — | OAuth provider type |
| `authorize_url` | string | **yes** | — | OAuth authorization endpoint |
| `token_url` | string | **yes** | — | OAuth token endpoint |
| `redirect_uri` | string | **yes** | — | Redirect URI registered with the provider |
| `client_id` | string | **yes** | — | OAuth client ID |

!!! note "Client secret"
    The `client_secret` is supplied via the `oauth_client_secrets` Terraform variable keyed by this entry's `key` — never hard-code it in YAML.

```yaml
oauth_configurations:
  - name: Snowflake OAuth
    key: snowflake_oauth
    type: snowflake
    authorize_url: https://xy12345.snowflakecomputing.com/oauth/authorize
    token_url: https://xy12345.snowflakecomputing.com/oauth/token-request
    redirect_uri: https://cloud.getdbt.com/complete/oauth
    client_id: my-client-id
    # client_secret via: TF_VAR_oauth_client_secrets='{"snowflake_oauth":"..."}'
```

---

## `ip_restrictions`

Account-level IP allowlist / denylist rules.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name |
| `key` | string | no | `name` | Unique identifier |
| `type` | string | no | `allow` | `allow` or `deny` |
| `description` | string | no | null | Human-readable description |
| `rule_set_enabled` | bool | no | true | Whether this rule is active |
| `cidrs` | list | no | [] | List of CIDR objects |

### `cidrs[]`

| Field | Type | Required |
|---|---|---|
| `cidr` | string | **yes** |

```yaml
ip_restrictions:
  - name: Corporate VPN
    key: corp_vpn
    type: allow
    description: "Allow traffic from corporate network"
    rule_set_enabled: true
    cidrs:
      - cidr: 203.0.113.0/24
      - cidr: 198.51.100.0/24

  - name: Block public ranges
    key: block_public
    type: deny
    rule_set_enabled: true
    cidrs:
      - cidr: 0.0.0.0/0
```

---

## `projects[]`

### Core fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | dbt Cloud project display name |
| `key` | string | no | `name` | Unique identifier used in cross-references |
| `protected` | bool | no | false | Prevents `terraform destroy` |

```yaml
projects:
  - name: Analytics
    key: analytics
    protected: false
```

---

### `repository`

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `remote_url` | string | **yes** | — | `"org/repo"` slug or full HTTPS URL |
| `git_clone_strategy` | string | no | auto-detected | Override clone strategy — see values below |
| `is_active` | bool | no | true | Whether the repository integration is active |
| `github_installation_id` | number | no | null | GitHub App installation ID |
| `gitlab_project_id` | number | no | null | GitLab numeric project ID |
| `pull_request_url_template` | string | no | null | Custom PR URL template (GitLab) |
| `azure_active_directory_project_id` | string | no | null | Azure DevOps project UUID |
| `azure_active_directory_repository_id` | string | no | null | Azure DevOps repository UUID |
| `azure_bypass_webhook_registration_failure` | bool | no | false | Skip webhook registration errors |
| `private_link_endpoint_id` | string | no | null | PrivateLink endpoint |
| `protected` | bool | no | false | Prevents `terraform destroy` |

**Valid `git_clone_strategy` values:** `github_app` · `deploy_key` · `deploy_token` · `azure_active_directory_app`

The strategy is auto-detected from the presence of `github_installation_id`, `gitlab_project_id`, or Azure fields — you normally don't need to set it manually.

=== "GitHub App"
    ```yaml
    repository:
      remote_url: "your-org/your-repo"
      github_installation_id: 12345678
    ```

=== "GitLab"
    ```yaml
    repository:
      remote_url: "https://gitlab.com/your-org/your-repo.git"
      gitlab_project_id: 9876543
      pull_request_url_template: "https://gitlab.com/your-org/your-repo/-/merge_requests/{{prNumber}}"
    ```

=== "Azure DevOps"
    ```yaml
    repository:
      remote_url: "https://dev.azure.com/org/project/_git/repo"
      git_clone_strategy: azure_active_directory_app
      azure_active_directory_project_id: "00000000-0000-0000-0000-000000000001"
      azure_active_directory_repository_id: "00000000-0000-0000-0000-000000000002"
      azure_bypass_webhook_registration_failure: false
    ```

=== "Deploy Key (public repos)"
    ```yaml
    repository:
      remote_url: "https://github.com/your-org/your-repo.git"
      git_clone_strategy: deploy_key
    ```

---

### `environments[]`

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name |
| `key` | string | no | `name` | Unique identifier used in `deferring_environment_key`, etc. |
| `type` | string | **yes** | — | `deployment` or `development` |
| `deployment_type` | string | conditional | — | `production` or `staging` — required when `type: deployment` |
| `connection_key` | string | no | null | References `global_connections[].key` |
| `dbt_version` | string | no | null | Pin dbt Core version (e.g., `"1.9.0"`) |
| `custom_branch` | string | no | null | Custom git branch (development envs) |
| `enable_model_query_history` | bool | no | null | Enable query history tracking |
| `extended_attributes_key` | string | no | null | References `extended_attributes[].key` |
| `protected` | bool | no | false | Prevents `terraform destroy` |
| `credential` | object | no | — | Warehouse credential block — see below |

```yaml
environments:
  - name: Production
    key: prod
    type: deployment
    deployment_type: production
    connection_key: databricks_prod
    dbt_version: "1.9.0"
    custom_branch: main
    enable_model_query_history: false
    extended_attributes_key: databricks_overrides
    protected: true
    credential:
      credential_type: databricks
      catalog: main
      schema: analytics
```

#### `credential` — per warehouse type

The `credential_type` field selects which credential resource is created. Sensitive values (passwords, tokens, keys) must be supplied via the `environment_credentials` Terraform variable keyed by `"{project_key}_{env_key}"`.

=== "Databricks"
    | Field | Type | Required | Default | Notes |
    |---|---|---|---|---|
    | `credential_type` | string | **yes** | — | `"databricks"` |
    | `catalog` | string | no | null | Unity Catalog catalog |
    | `schema` | string | no | `""` | Target schema |
    | `token_name` | string | no | — | Legacy: key in `token_map` variable |

    ```yaml
    credential:
      credential_type: databricks
      catalog: main
      schema: analytics
      # token via environment_credentials["analytics_prod"]["token"]
    ```

=== "Snowflake (password)"
    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `auth_type` | string | **yes** | `"password"` |
    | `user` | string | **yes** | — |
    | `schema` | string | no | `""` |
    | `database` | string | no | null |
    | `role` | string | no | null |
    | `warehouse` | string | no | null |
    | `num_threads` | number | no | null |

    ```yaml
    credential:
      credential_type: snowflake
      auth_type: password
      user: DBT_USER
      schema: ANALYTICS
      database: ANALYTICS
      warehouse: TRANSFORMING
      role: TRANSFORMER
      num_threads: 8
      # password via environment_credentials["analytics_prod"]["password"]
    ```

=== "Snowflake (keypair)"
    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `auth_type` | string | **yes** | `"keypair"` |
    | `user` | string | **yes** | — |
    | `schema` | string | no | `""` |
    | `database` | string | no | null |
    | `role` | string | no | null |
    | `warehouse` | string | no | null |
    | `num_threads` | number | no | null |

    ```yaml
    credential:
      credential_type: snowflake
      auth_type: keypair
      user: DBT_USER
      schema: ANALYTICS
      # private_key + private_key_passphrase via environment_credentials["analytics_prod"]
    ```

=== "BigQuery"
    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `dataset` | string | no | `""` |
    | `num_threads` | number | no | null |

    ```yaml
    credential:
      credential_type: bigquery
      dataset: analytics
      num_threads: 8
    ```

=== "Postgres"
    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `username` | string | **yes** | — |
    | `default_schema` | string | no | `""` |
    | `num_threads` | number | no | null |
    | `target_name` | string | no | null |

    ```yaml
    credential:
      credential_type: postgres
      username: dbt_user
      default_schema: analytics
      num_threads: 4
      target_name: prod
      # password via environment_credentials["analytics_prod"]["password"]
    ```

=== "Redshift"
    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `username` | string | **yes** | — |
    | `default_schema` | string | no | `""` |
    | `num_threads` | number | no | 4 |

    ```yaml
    credential:
      credential_type: redshift
      username: dbt_user
      default_schema: analytics
      num_threads: 4
      # password via environment_credentials["analytics_prod"]["password"]
    ```

=== "Athena"
    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `schema` | string | no | `""` |
    | `num_threads` | number | no | null |

    ```yaml
    credential:
      credential_type: athena
      schema: analytics
      num_threads: 4
      # aws_access_key_id + aws_secret_access_key via environment_credentials["analytics_prod"]
    ```

=== "Fabric / Synapse"
    **SQL auth** (`credential_type: fabric` or `credential_type: synapse`):

    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `schema` | string | no | `""` |
    | `user` | string | **yes** | — |
    | `schema_authorization` | string | no | null |
    | `authentication` | string | no | `"sql"` (Synapse only) |

    ```yaml
    credential:
      credential_type: fabric
      schema: analytics
      user: DBT_USER
      schema_authorization: dbo
      # password via environment_credentials["analytics_prod"]["password"]
    ```

    **Service Principal auth:**

    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `schema` | string | no | `""` |
    | `tenant_id` | string | **yes** | — |
    | `client_id` | string | **yes** | — |
    | `schema_authorization` | string | no | null |
    | `authentication` | string | no | `"ServicePrincipal"` (Synapse only) |

    ```yaml
    credential:
      credential_type: synapse
      schema: analytics
      tenant_id: "00000000-0000-0000-0000-000000000001"
      client_id: "my-app-client-id"
      authentication: ServicePrincipal
      # client_secret via environment_credentials["analytics_prod"]["client_secret"]
    ```

=== "Starburst / Trino"
    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | `"starburst"` or `"trino"` |
    | `schema` | string | no | `""` |
    | `catalog` | string | no | `""` |
    | `user` | string | **yes** | — |
    | `num_threads` | number | no | null |

    ```yaml
    credential:
      credential_type: starburst
      schema: analytics
      catalog: iceberg
      user: DBT_USER
      num_threads: 4
      # password via environment_credentials["analytics_prod"]["password"]
    ```

=== "Spark"
    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `schema` | string | no | `""` |

    ```yaml
    credential:
      credential_type: spark
      schema: analytics
      # token via environment_credentials["analytics_prod"]["token"]
    ```

=== "Teradata"
    | Field | Type | Required | Default |
    |---|---|---|---|
    | `credential_type` | string | **yes** | — |
    | `user` | string | **yes** | — |
    | `schema` | string | no | `""` |
    | `num_threads` | number | no | null |

    ```yaml
    credential:
      credential_type: teradata
      user: DBT_USER
      schema: analytics
      num_threads: 4
      # password via environment_credentials["analytics_prod"]["password"]
    ```

---

### `jobs[]`

Jobs are defined at project level and reference environments by `key`. They are **not** nested inside environments.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name |
| `key` | string | no | `name` | Unique identifier — used in `artefacts` references |
| `environment_key` | string | **yes** | — | References `environments[].key` |
| `execute_steps` | list(string) | **yes** | — | Ordered list of dbt CLI commands |
| `triggers` | object | **yes** | — | At least one trigger must be set — see below |
| `description` | string | no | null | Job description shown in dbt Cloud |
| `dbt_version` | string | no | null | Pin dbt Core version (overrides environment) |
| `num_threads` | number | no | 4 | Thread count |
| `target_name` | string | no | null | dbt target name (e.g., `"prod"`) |
| `timeout_seconds` | number | no | 0 | Job timeout — `0` means no timeout |
| `is_active` | bool | no | true | Whether the job is enabled |
| `job_type` | string | no | — | `"scheduled"` · `"ci"` · `"merge"` |
| `generate_docs` | bool | no | false | Regenerate docs on each run |
| `run_generate_sources` | bool | no | false | Run `dbt source freshness` |
| `run_lint` | bool | no | false | Run SQLFluff lint step |
| `errors_on_lint_failure` | bool | no | true | Treat lint failures as errors |
| `run_compare_changes` | bool | no | false | Advanced CI — requires deployment env with deferral |
| `triggers_on_draft_pr` | bool | no | false | Trigger on draft pull requests |
| `deferring_environment_key` | string | no | null | References `environments[].key` for state deferral |
| `self_deferring` | bool | no | null | Defer to the job's own previous run |
| `force_node_selection` | bool | no | auto | SAO — set automatically; null for CI/merge jobs |
| `protected` | bool | no | false | Prevents `terraform destroy` |
| `env_var_overrides` | map(string) | no | {} | Job-level env var overrides |

#### `triggers`

| Field | Type | Default | Description |
|---|---|---|---|
| `schedule` | bool | false | Run on a schedule |
| `github_webhook` | bool | false | Trigger on GitHub PR events |
| `git_provider_webhook` | bool | false | Trigger on generic git provider webhooks |
| `on_merge` | bool | false | Trigger when PR is merged |

At least one of these must be `true`.

#### Schedule fields

Only one schedule mode is applied — precedence order: `schedule_cron` > `schedule_interval` > `schedule_hours`.

| Field | Type | Default | Description |
|---|---|---|---|
| `schedule_type` | string | null | `"every_day"` · `"days_of_week"` · `"days_of_month"` |
| `schedule_days` | list(number) | null | Days to run — 0–6 (Sun–Sat) for week; 1–31 for month |
| `schedule_hours` | list(number) | null | UTC hours to run — e.g., `[6, 18]` |
| `schedule_cron` | string | null | Cron expression — overrides other schedule fields |
| `schedule_interval` | number | null | Run every N hours — overrides `schedule_hours` |

```yaml
jobs:
  # Scheduled job — weekdays at 6 AM UTC
  - name: Production Daily
    key: prod_daily
    environment_key: prod
    execute_steps:
      - dbt build
    triggers:
      schedule: true
    schedule_type: days_of_week
    schedule_days: [1, 2, 3, 4, 5]
    schedule_hours: [6]
    num_threads: 8
    target_name: prod
    timeout_seconds: 3600
    generate_docs: true
    deferring_environment_key: prod
    self_deferring: true
    protected: true
    env_var_overrides:
      DBT_TARGET: prod

  # CI job — triggered on PR
  - name: Staging CI
    key: staging_ci
    environment_key: staging
    execute_steps:
      - dbt build --select state:modified+
    triggers:
      github_webhook: true
      git_provider_webhook: true
    job_type: ci
    run_compare_changes: true
    deferring_environment_key: prod

  # Merge job — triggered on PR merge
  - name: Staging Merge
    key: staging_merge
    environment_key: staging
    execute_steps:
      - dbt build --select state:modified+
    triggers:
      on_merge: true
    job_type: merge
    deferring_environment_key: prod

  # Cron schedule
  - name: Hourly Refresh
    key: hourly_refresh
    environment_key: prod
    execute_steps:
      - dbt run --select marts.finance
    triggers:
      schedule: true
    schedule_cron: "0 * * * *"
```

---

### `environment_variables[]`

Project-level dbt environment variables with per-environment value overrides.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | **yes** | Variable name — must use `DBT_` prefix convention |
| `environment_values` | list | **yes** | Per-environment value list |

#### `environment_values[]`

| Field | Type | Required | Description |
|---|---|---|---|
| `env` | string | **yes** | `"project"` for project default, or the environment `name` (not key) |
| `value` | string | **yes** | Variable value |

```yaml
environment_variables:
  - name: DBT_WAREHOUSE
    environment_values:
      - env: project           # project-level default
        value: "prod_warehouse"
      - env: Production        # matches environment name
        value: "prod_warehouse"
      - env: Development
        value: "dev_warehouse"

  - name: DBT_TARGET
    environment_values:
      - env: project
        value: "prod"
      - env: Staging
        value: "staging"
```

---

### `extended_attributes[]`

Per-project connection-level overrides applied at the environment level. Linked to environments via `extended_attributes_key`.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | **yes** | Display name |
| `key` | string | no | Unique identifier — referenced by `environments[].extended_attributes_key` |
| `content` | map | no | Nested YAML object of connection overrides |

```yaml
extended_attributes:
  - name: Databricks HTTP Override
    key: databricks_overrides
    content:
      databricks:
        http_path: /sql/1.0/warehouses/override-warehouse-id
        catalog: overridden_catalog

  - name: Snowflake Warehouse Override
    key: snowflake_overrides
    content:
      snowflake:
        warehouse: HIGH_MEMORY_WH
```

---

### `profiles[]`

Links a global connection + environment credential + extended attributes into a named profile for an environment.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name |
| `key` | string | no | `name` | Unique identifier |
| `connection_key` | string | no | null | References `global_connections[].key` |
| `connection_id` | number | no | null | Numeric connection ID (alternative to `connection_key`) |
| `credential_key` | string | no | null | Composite key `"{project_key}_{env_key}"` |
| `credentials_id` | number | no | null | Numeric credential ID (alternative to `credential_key`) |
| `extended_attributes_key` | string | no | null | References `extended_attributes[].key` |

```yaml
    profiles:
      - name: prod-profile
        key: prod_profile
        connection_key: databricks_prod
        credential_key: analytics_prod
        extended_attributes_key: databricks_overrides
```

---

### `lineage_integrations[]`

Per-project lineage integrations (e.g., Tableau, Looker).

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Display name |
| `key` | string | no | `name` | Unique identifier |
| `host` | string | **yes** | — | Lineage tool host URL |
| `site_id` | string | **yes** | — | Site/workspace identifier |
| `token_name` | string | **yes** | — | Token name label |

!!! note "Token"
    The actual token value is supplied via `lineage_tokens` Terraform variable keyed by `"{project_key}_{integration_key}"`.

```yaml
    lineage_integrations:
      - name: Tableau Production
        key: tableau_prod
        host: https://tableau.example.com
        site_id: my-site
        token_name: dbt-cloud-tableau-token
        # token via: TF_VAR_lineage_tokens='{"analytics_tableau_prod":"token..."}'
```

---

### `artefacts`

Links the project's documentation and source freshness jobs. Both fields reference `jobs[].key`.

| Field | Type | Required | Description |
|---|---|---|---|
| `docs_job` | string | no | Job key for the documentation artifact |
| `freshness_job` | string | no | Job key for the source freshness artifact |

```yaml
    artefacts:
      docs_job: prod_daily
      freshness_job: prod_daily
```

---

### `semantic_layer`

Configures the dbt Semantic Layer for a project.

| Field | Type | Required | Description |
|---|---|---|---|
| `environment` | string | **yes** | References `environments[].key` |

!!! warning "Create-only"
    The semantic layer configuration cannot be imported. It is created once and Terraform will not attempt to update it on subsequent runs if it already exists.

```yaml
    semantic_layer:
      environment: prod
```

---

## Sensitive credential reference

Sensitive values are never written directly in YAML. Instead, they are passed as Terraform variables and matched by key at apply time.

| Terraform variable | Key format | Matched to |
|---|---|---|
| `token_map` | `"my_token_name"` | `credential.token_name` in YAML (legacy Databricks) |
| `environment_credentials` | `"project_key_env_key"` | Environment `credential` block |
| `connection_credentials` | `"connection_key"` | `global_connections[].key` |
| `lineage_tokens` | `"project_key_integration_key"` | `lineage_integrations[].key` composite |
| `oauth_client_secrets` | `"oauth_config_key"` | `oauth_configurations[].key` |

Keys use underscores and must exactly match the `key:` values in your YAML. For example, a project with `key: analytics` and an environment with `key: prod` uses the `environment_credentials` key `"analytics_prod"`.

```bash
export TF_VAR_environment_credentials='{
  "analytics_prod": {
    "credential_type": "databricks",
    "token": "dapi...",
    "catalog": "main",
    "schema": "analytics"
  },
  "analytics_staging": {
    "credential_type": "databricks",
    "token": "dapi...",
    "catalog": "main",
    "schema": "analytics_staging"
  }
}'

export TF_VAR_connection_credentials='{
  "snowflake_prod": {
    "oauth_client_id": "...",
    "oauth_client_secret": "..."
  }
}'

export TF_VAR_lineage_tokens='{
  "analytics_tableau_prod": "tableau-pat-token..."
}'

export TF_VAR_oauth_client_secrets='{
  "snowflake_oauth": "client-secret-value..."
}'
```

---

## `protected: true` behavior

Any resource that supports a `protected` field uses a duplicate Terraform resource block pattern:

- `protected: false` (default) — resource created normally; `terraform destroy` works
- `protected: true` — resource created with `lifecycle { prevent_destroy = true }`; `terraform destroy` is blocked with an error

This is the only reliable way to prevent accidental destruction in Terraform. Use it for production environments, production jobs, and any resource that would be costly to recreate.
