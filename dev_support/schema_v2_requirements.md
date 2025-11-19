# dbt Cloud YAML Schema v2 Requirements & Terraform Impact

This document captures the schema changes we need for the importer and the Terraform updates required to consume those changes. Treat this as the working contract between the importer, schema, and Terraform deployment workflows.

---

## Goals
- Enable the importer to describe a full dbt Cloud account (not just a single project) in one YAML artifact.
- Normalize reusable account resources (connections, groups, service tokens, notifications, semantic layer configs, PrivateLink endpoints) so they can be referenced by name/slug rather than opaque IDs.
- Preserve a compatibility layer so existing `schemas/v1.json` users and Terraform pipelines continue to work unchanged.

---

## Proposed Root Structure (v2)

```yaml
version: 2
account:
  name: <string>
  host_url: <string>

globals:
  connections: [ConnectionRef...]
  repositories: [RepositoryRef...]      # if shared across projects
  privatelink_endpoints: [PrivateLink...]
  service_tokens: [ServiceToken...]
  groups: [Group...]
  semantic_layer_configs: [SemanticLayerConfig...]
  notifications: [NotificationTarget...]  # reused by jobs or account alerts

projects:
  - name: <string>
    repository: <repository_ref> | inline object
    environments: [...]
    environment_variables: [...]
    jobs: [...]
    notifications: [...]               # optional project-scoped overrides

metadata:
  placeholders:
    - id: <string>                      # e.g., LOOKUP:global_connection.my_connection
      description: <string>
```

### Reference Conventions
- Every reusable object exposes a `key` (string slug) alongside any known numeric `id`. Example:
  ```yaml
  connections:
    - key: "snowflake_prod"
      id: 123
      name: "Snowflake Prod"
      type: "snowflake"
  ```
- Project/environment/job fields that previously required numeric IDs now accept `oneOf` `[integer, LookupString, key reference]`. Lookup strings follow the pattern `LOOKUP:<collection>.<key>` so Terraform can decide whether to call a data source, skip creation, or expect manual input.
- Jobs gain `deferring_environment_key` and `deferring_job_key` (string) that map to the normalized objects; numeric IDs stay optional for backwards compatibility.
- Credentials gain optional `catalog`.
- Job notification targets become an array referencing `globals.notifications[*].key` (with optional inline overrides).

---

## Normalized Object Definitions

| Object | Required Fields | Notes |
|--------|-----------------|-------|
| `connections` | `key`, `name`, `type`, optional `id`, provider-specific payload | Acts as lookup-only; importer never emits secrets |
| `repositories` | `key`, `remote_url`, optional SCM specifics | Allows multiple projects to share one repo definition |
| `service_tokens` | `key`, `name`, `scopes`, optional `id` | Captures metadata; secret material stays external |
| `groups` | `key`, `name`, `membership` (user emails or IDs) | Enables permission migration |
| `privatelink_endpoints` | `key`, `cloud`, `region`, `endpoint_id` | Referenced by repositories/connections |
| `notifications` | `key`, `type` (`slack`, `email`, `pagerduty`, `webhook`), target payload | Jobs reference via `notification_keys` |
| `semantic_layer_configs` | `key`, `enabled`, `project_key`, etc. | Placeholder for future importer support |

Each object definition must document whether Terraform will **create** the resource or **look it up**. For lookups only, require either an `id` or a lookup placeholder string.

---

## Terraform Deployment Impact

1. **Schema Dispatch**
   - Introduce `var.schema_version` (default `1`) in `variables.tf`.
   - Update the YAML loader (currently in the `local_file` + `yamldecode` pipeline) to branch on the version and map v2 structures to module inputs.
   - Add validation that errors early when a v2 file is supplied without enabling the new flow.

2. **Module Graph Changes**
   - Create new modules (or extend existing ones) for account-level entities:
     - `modules/connections` (data source/lookup wrapper)
     - `modules/service_tokens`
     - `modules/groups`
     - `modules/notifications`
     - `modules/semantic_layer`
     - `modules/privatelink`
   - Update `modules/environments` and `modules/jobs` to accept `connection_key`, `credential.catalog`, `deferring_*_key`, and `notification_keys`.
   - Allow jobs/environment modules to resolve `LOOKUP:*` placeholders by invoking provider data sources (e.g., `dbtcloud_connection`).

3. **Provider Requirements**
   - Confirm `terraform-provider-dbtcloud` exposes resources/data sources for service tokens, notifications, groups, semantic layer configs, and PrivateLink. If gaps exist, open matching issues in that repo.
   - Ensure provider supports filtering by name so lookups can succeed when only a `key` (string) is provided.

4. **State & Outputs**
   - Expand module outputs to include maps keyed by `key` (not just name) for new objects, enabling downstream automation to stitch resources together.
   - Maintain existing outputs for v1 users.

5. **Examples & Tests**
   - Add a `test/fixtures/v2_complete` scenario covering all new sections.
   - Provide `examples/multi-account/` showcasing mixed lookup + creation flows.

---

## Compatibility Strategy

- Keep `schemas/v1.json` and current Terraform behavior as-is.
- Ship `schemas/v2.json` alongside and gate via `version: 2` at the top of the YAML file.
- Terraform module detects the version and:
  - For `version == 1` (or missing), reuse today’s logic.
  - For `version == 2`, run the new normalization pipeline.
- Provide a conversion script (maybe within the importer) to downgrade v2→v1 for simple single-project cases to ease adoption.
- Document migration guidance in `docs/configuration/multi-project.md` (new section) and in the Terraform reference.

---

## Next Steps
1. Formalize the JSON Schema for each normalized object (ideally generated from source-of-truth structs).
2. Align with the Terraform provider team on required resources/data sources.
3. Prototype YAML → Terraform decoding for `connections` + `jobs.notification_keys` to validate the lookup pattern.
4. Update docs and examples once the schema + Terraform implementations are stable.


