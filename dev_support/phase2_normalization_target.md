# Phase 2 Normalization Target Specification

**Version:** 0.3.1-dev  
**Date:** 2025-11-21

This document defines the canonical v2 YAML structure that the Phase 2 normalizer will generate from importer JSON exports.

---

## Overview

The v2 schema (`schemas/v2.json`) supports multi-project, account-aware configurations with:
- **Account metadata**: Name, host URL, optional ID
- **Global resources**: Reusable connections, repositories, tokens, groups, notifications, webhooks, PrivateLink endpoints
- **Projects**: One or more projects with environments, jobs, and environment variables
- **Metadata**: Placeholder descriptions for manual LOOKUP resolutions

---

## Root Structure

```yaml
version: 2
account:
  name: "Account Name"
  host_url: "https://cloud.getdbt.com"
  id: 12345  # optional

globals:
  connections: []
  repositories: []
  privatelink_endpoints: []
  service_tokens: []
  groups: []
  notifications: []

projects:
  - name: "ProjectName"
    key: "project_name"
    repository: "repo_key"  # or inline object
    environments: []
    jobs: []
    environment_variables: []
    notifications: []  # project-scoped

metadata:
  placeholders:
    - id: "LOOKUP:connection_1"
      description: "Snowflake production connection"
```

---

## Resource Coverage & Mapping

### Account Level
| Importer Field | YAML Target | Notes |
|----------------|-------------|-------|
| `account_id` | `account.id` | Optional; primarily for reference |
| `account_name` | `account.name` | Required |
| `_metadata.source_url` | `account.host_url` | Required |

### Global Resources

#### Connections
| Importer Field | YAML Target | Source of Truth |
|----------------|-------------|-----------------|
| `globals.connections[].key` | `globals.connections[].key` | Yes (slug) |
| `globals.connections[].name` | `globals.connections[].name` | Yes |
| `globals.connections[].type` | `globals.connections[].type` | Yes |
| `globals.connections[].id` | `globals.connections[].id` | Advisory (strip for target) |
| `globals.connections[].details.private_link_endpoint_id` | `globals.connections[].private_link_endpoint_key` | Map to key |
| `globals.connections[].details.*` | `globals.connections[].details` | Provider-specific passthrough |

**Handling Strategy**: 
- Strip source `id` unless `--preserve-ids` flag
- Resolve `private_link_endpoint_id` → `private_link_endpoint_key` via element mapping
- If connection doesn't exist in target, emit `LOOKUP:connection_name` placeholder

#### Repositories
| Importer Field | YAML Target | Source of Truth |
|----------------|-------------|-----------------|
| `globals.repositories[].key` | `globals.repositories[].key` | Yes |
| `globals.repositories[].remote_url` | `globals.repositories[].remote_url` | Yes |
| `globals.repositories[].git_clone_strategy` | `globals.repositories[].git_clone_strategy` | Yes |
| `globals.repositories[].metadata.github_installation_id` | `globals.repositories[].github_installation_id` | Yes (if applicable) |
| `globals.repositories[].metadata.gitlab_project_id` | `globals.repositories[].gitlab_project_id` | Yes (if applicable) |
| `globals.repositories[].id` | Omit | Advisory only |

**Handling Strategy**:
- Always include repositories used by projects
- Strip source `id`
- Preserve provider-specific fields (github_installation_id, etc.)

#### Service Tokens
| Importer Field | YAML Target | Notes |
|----------------|-------------|-------|
| `globals.service_tokens[].key` | `globals.service_tokens[].key` | Yes |
| `globals.service_tokens[].name` | `globals.service_tokens[].name` | Yes |
| `globals.service_tokens[].permission_sets` | `globals.service_tokens[].scopes` | Map permission_sets → scopes |
| `globals.service_tokens[].id` | Omit | Advisory |
| `globals.service_tokens[].token_string` | Never emit | Security: never in YAML |

**Handling Strategy**:
- Include only if mapping config allows
- Never emit token values (secrets)
- Map permission_sets to scopes array

#### Groups
| Importer Field | YAML Target | Notes |
|----------------|-------------|-------|
| `globals.groups[].key` | `globals.groups[].key` | Yes |
| `globals.groups[].name` | `globals.groups[].name` | Yes |
| `globals.groups[].id` | Omit | Advisory |
| SSO mappings | `metadata` note | Not directly manageable via Terraform |

**Handling Strategy**:
- Include groups for RBAC reference
- SSO mappings are read-only; document in metadata

#### Notifications
| Importer Field | YAML Target | Notes |
|----------------|-------------|-------|
| `globals.notifications[].key` | `globals.notifications[].key` | Yes |
| `globals.notifications[].notification_type` | `globals.notifications[].type` | Map int → string (1=email, 2=slack, 3=webhook) |
| `globals.notifications[].metadata.external_email` | `globals.notifications[].target.email` | For email type |
| `globals.notifications[].metadata.slack_channel_name` | `globals.notifications[].target.channel` | For slack type |
| `globals.notifications[].metadata.url` | `globals.notifications[].target.url` | For webhook type |
| Job trigger lists | Project job references | Handle via job.notification_keys |

**Handling Strategy**:
- Map notification_type integers to strings
- Extract destination into type-specific target object
- Job associations handled via job.notification_keys array

#### Webhooks
| Importer Field | YAML Target | Notes |
|----------------|-------------|-------|
| `globals.webhooks[].key` | Omit from v2 YAML | Webhooks are account-managed, not Terraform |
| All webhook fields | Document in metadata | Reference only |

**Handling Strategy**:
- Webhooks are typically managed via dbt Cloud UI
- Document in metadata.placeholders for awareness
- Do not include in Terraform YAML

#### PrivateLink Endpoints
| Importer Field | YAML Target | Notes |
|----------------|-------------|-------|
| `globals.privatelink_endpoints[].key` | `globals.privatelink_endpoints[].key` | Yes |
| `globals.privatelink_endpoints[].type` | `globals.privatelink_endpoints[].cloud` | Map type → cloud |
| `globals.privatelink_endpoints[].cidr_range` | Document in details | Advisory |
| `globals.privatelink_endpoints[].id` | `globals.privatelink_endpoints[].endpoint_id` | Provider endpoint ID |

**Handling Strategy**:
- Include only if referenced by connections
- Map importer type to v2 cloud field

### Project Resources

#### Projects
| Importer Field | YAML Target | Source of Truth |
|----------------|-------------|-----------------|
| `projects[].key` | `projects[].key` | Yes |
| `projects[].name` | `projects[].name` | Yes |
| `projects[].id` | Omit | Advisory |
| `projects[].repository_key` | `projects[].repository` | Reference or inline |

**Handling Strategy**:
- One YAML per project OR multi-project YAML (user choice via mapping config)
- Strip source project IDs
- Repository can be key reference or inline object

#### Environments
| Importer Field | YAML Target | Source of Truth |
|----------------|-------------|-----------------|
| `projects[].environments[].key` | `projects[].environments[].key` | Yes |
| `projects[].environments[].name` | `projects[].environments[].name` | Yes |
| `projects[].environments[].type` | `projects[].environments[].type` | Yes |
| `projects[].environments[].connection_key` | `projects[].environments[].connection` | Map to connection key or LOOKUP |
| `projects[].environments[].credential.token_name` | `projects[].environments[].credential.token_name` | Yes |
| `projects[].environments[].credential.schema` | `projects[].environments[].credential.schema` | Yes |
| `projects[].environments[].credential.catalog` | `projects[].environments[].credential.catalog` | Yes (if present) |
| `projects[].environments[].dbt_version` | `projects[].environments[].dbt_version` | Yes |
| `projects[].environments[].id` | Omit | Advisory |

**Handling Strategy**:
- Preserve all environment configuration
- Map connection via element_mapping_id → key
- Credentials reference external token_map variable

#### Jobs
| Importer Field | YAML Target | Source of Truth |
|----------------|-------------|-----------------|
| `projects[].jobs[].key` | `projects[].jobs[].key` | Yes |
| `projects[].jobs[].name` | `projects[].jobs[].name` | Yes |
| `projects[].jobs[].environment_key` | `projects[].jobs[].environment_key` | Yes |
| `projects[].jobs[].execute_steps` | `projects[].jobs[].execute_steps` | Yes |
| `projects[].jobs[].triggers` | `projects[].jobs[].triggers` | Yes (all boolean fields) |
| `projects[].jobs[].settings.schedule_type` | `projects[].jobs[].schedule_type` | Yes |
| `projects[].jobs[].settings.schedule_hours` | `projects[].jobs[].schedule_hours` | Yes |
| `projects[].jobs[].settings.schedule_days` | `projects[].jobs[].schedule_days` | Yes |
| `projects[].jobs[].settings.num_threads` | `projects[].jobs[].num_threads` | Yes |
| `projects[].jobs[].id` | Omit | Advisory |

**Handling Strategy**:
- Include all job configuration
- Map trigger booleans exactly
- Schedule settings preserved if present
- Optional fields (num_threads, timeout_seconds, etc.) only if set

#### Environment Variables
| Importer Field | YAML Target | Source of Truth |
|----------------|-------------|-----------------|
| `projects[].environment_variables[].name` | `projects[].environment_variables[].name` | Yes |
| `projects[].environment_variables[].project_default` | Omit (handled in token_map) | User must provide |
| `projects[].environment_variables[].environment_values` | `projects[].environment_variables[].environment_values` | Yes |

**Handling Strategy**:
- Regular variables: Emit with environment-specific values
- Secrets (DBT_ENV_SECRET prefix): Document in metadata that values must be provided via token_map
- Project defaults: Not directly in YAML; user provides via Terraform variables

---

## Reference Resolution

### Slug-Based References
Resources within the same YAML file reference each other by `key`:
```yaml
projects:
  - name: "Analytics"
    repository: "jaffle_shop"  # references globals.repositories[].key
    environments:
      - name: "Production"
        connection: "snowflake_prod"  # references globals.connections[].key
```

### LOOKUP Placeholders
When a resource doesn't exist in the source export but is needed in the target:
```yaml
environments:
  - name: "Production"
    connection: "LOOKUP:prod_connection"

metadata:
  placeholders:
    - id: "LOOKUP:prod_connection"
      description: "Snowflake production connection - must exist in target account"
```

User must:
1. Create the resource in target account via UI or separate Terraform
2. Use Terraform data source to fetch ID
3. Update YAML to reference by ID or configure provider data source

### ID Stripping Rules
- **Default behavior**: Strip all source IDs (connections, repos, projects, envs, jobs)
- **Optional preservation**: `--preserve-ids` flag keeps IDs as advisory for debugging
- **Never strip**: Provider-specific IDs (github_installation_id, gitlab_project_id, endpoint_id)

---

## Name Collision Handling

When normalizing, check for duplicate keys within each resource type:
1. **Detect**: Log warning if two resources normalize to same key
2. **Disambiguate**: Append numeric suffix: `key_2`, `key_3`
3. **Report**: Include in exclusion report with original names

Example:
```
Source: "Prod Connection" → key: "prod_connection"
Source: "Prod-Connection" → key: "prod_connection"

Normalized:
- key: "prod_connection"  (first)
- key: "prod_connection_2"  (collision)
```

---

## Secret Redaction

Never emit secret values in YAML:
- Service token strings: Never included
- Environment variable secrets: Emit name only, document that value must be in token_map
- Credentials: token_name references external token_map, never inline values

Example:
```yaml
environment_variables:
  - name: "DBT_ENV_SECRET_API_KEY"
    environment_values:
      production: "REDACTED"  # or omit entirely

# User must provide via Terraform:
# token_map = {
#   "DBT_ENV_SECRET_API_KEY" = var.api_key_secret
# }
```

---

## Advisory vs Source-of-Truth Fields

### Source of Truth (Must Preserve)
- All names, keys, types
- Execute steps, triggers, schedules
- Connection details (adapter-specific)
- Repository URLs, clone strategies
- Credential schema/catalog references

### Advisory (Optional/Strip by Default)
- All numeric IDs from source account
- SSO mapping group names (read-only)
- Account features/flags
- Job run history, last modified timestamps

### Manual Intervention Required
- Token/secret values (provide via token_map)
- OAuth configurations (recreate in target)
- Webhook subscriptions (recreate via UI)
- User/group memberships (managed externally)

---

## Multi-Project Strategy

Users can choose via mapping config:

### Option 1: Single Multi-Project YAML
```yaml
version: 2
account: {...}
globals: {...}
projects:
  - name: "Analytics"
  - name: "Marketing"
  - name: "Finance"
```

**Pros**: Centralized, easier to see cross-project dependencies  
**Cons**: Large file, harder to parallelize Terraform

### Option 2: One YAML Per Project
```yaml
# analytics.yml
version: 2
account: {...}
globals:
  connections: [...]  # Only those used by this project
  repositories: [...]
projects:
  - name: "Analytics"
```

**Pros**: Modular, easier to manage per-team  
**Cons**: Duplicate global resource definitions, harder to maintain consistency

**Recommendation**: Start with multi-project, split if > 10 projects or if teams need independent control.

---

## Next Steps

This document will guide the normalizer implementation (Phase 2, Task 2-3). See `schemas/importer_mapping.json` for filtering/scope controls.

