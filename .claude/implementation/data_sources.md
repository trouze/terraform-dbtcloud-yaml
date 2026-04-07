# Data lookups module (`modules/data_lookups`)

This module centralizes **read-only** account discovery used when YAML references resources that are **not** defined in the same Terraform state (for example connections that already exist in dbt Cloud, or GitHub App installation IDs that are account-specific).

It mirrors the intent of `modules/projects_v2/data_sources.tf` on the importer branch, but as an explicit child module with clear inputs and outputs so root orchestration stays predictable.

## When the module is instantiated

Root enables `module.data_lookups` when **either**:

- The merged project YAML contains at least one **`LOOKUP:`** global-connection placeholder (see below), **or**
- `var.dbt_pat` is set (so GitHub installations can be fetched from the dbt Cloud integrations API).

Gating uses `local._lookup_connection_ref_strings` in `variables.tf`; keep that extraction **in sync** with the `lookup_connection_keys` logic in `modules/data_lookups/main.tf`.

## `LOOKUP:` global connections

### Syntax

Use a **string** value that starts with `LOOKUP:` followed by the **exact display name** of an existing global connection in the target dbt Cloud account (the `name` field returned by `data.dbtcloud_global_connections`).

Example:

```yaml
environments:
  - name: Prod
    key: prod
    type: deployment
    connection_key: "LOOKUP:Snowflake Production"
```

The map key passed to `modules/environments` and `modules/profiles` is the **full placeholder string** (e.g. `LOOKUP:Snowflake Production`), not the name alone.

### Where placeholders are scanned

- **Environments**: `connection` if set, otherwise `connection_key` (same precedence as `modules/environments` resolution).
- **Profiles**: `connection_key` only.

### Resolution

1. `data.dbtcloud_global_connections` runs **only** when at least one such placeholder exists (avoids an unnecessary read).
2. `lookup_connection_ids` maps each placeholder to `tostring(connection.id)` where `connection.name == replace(placeholder, "LOOKUP:", "")`.
3. Root builds `local.global_connection_ids_effective`:

   `merge(lookup_connection_ids, managed_global_connection_ids)`

   **Managed Terraform connections win on key collision** (in practice YAML keys and `LOOKUP:…` keys should not overlap).

### Validation (V-01)

`validation.tf` **does not** require `LOOKUP:…` values to appear under `global_connections[]`. Placeholders are intentionally for **pre-existing** connections. If no matching name exists in the account, resolution yields `null` and apply can fail on the environment resource; fixing that is an operational/data issue, not schema validation.

## GitHub App installations

When `var.dbt_pat` is non-null, the module calls:

`GET {dbt_host}/api/v2/integrations/github/installations/`

with `Authorization: Bearer <dbt_pat>`.

Outputs:

- `github_installation_by_owner` — map of **lowercase** GitHub `account.login` → installation **numeric id**.
- `github_installation_fallback_id` — first installation in the filtered list when owner matching is not used.

**Note:** Service tokens cannot use this API; use a PAT. Default host for the HTTP call is `coalesce(var.dbt_host_url, "https://cloud.getdbt.com")` with a trailing `/api` segment stripped if present.

### Consumption in `modules/repository`

Root passes `module.data_lookups[0].github_installation_by_owner` and `github_installation_fallback_id` into the repository module when `data_lookups` is enabled (same conditions as above). The repository module resolves **`github_installation_id`** in order:

1. **`repository.github_installation_id`** from YAML, if set  
2. **`github_installation_by_owner[lower(owner)]`** where `owner` is parsed from `remote_url` (`github.com/<owner>/…` or `git@github.com:<owner>/…`)  
3. **`github_installation_fallback_id`** (first installation returned for the account)

**Auto-detect GitHub** (`remote_url` on github.com, no explicit `git_clone_strategy`) uses **`github_app`** only when a non-null resolved installation id exists **or** `dbt_pat` is set (discovery may fill the id at apply). Otherwise it uses **`deploy_key`**.

Explicit **`git_clone_strategy: github_app`** follows the same rule: without YAML id, discovery map entry, fallback, or PAT, strategy downgrades to **`deploy_key`**.

Root still exposes the GitHub outputs for debugging and for any external callers.

## Repository `LOOKUP:` (scalar, legacy)

If `project.repository` is a **scalar** string beginning with `LOOKUP:` (v2 / importer style), it is collected in `lookup_repository_keys`. There is **no** resolution here yet; repository linking for the current v1 object-shaped `repository` block is unchanged.

## Root outputs

| Output | Meaning |
|--------|---------|
| `connection_ids` | **Effective** map used by environments/profiles (managed + `LOOKUP:`). |
| `lookup_connection_ids` | Only the `LOOKUP:`-resolved entries. |
| `github_installation_by_owner` / `github_installation_fallback_id` | From integrations API when PAT is set. |

## Dependencies

- **Provider**: `hashicorp/http` (declared in root `providers.tf` and the module).
- **dbt Cloud**: `data.dbtcloud_global_connections` uses the default `dbtcloud` provider configuration at root (`dbt_token`, `dbt_account_id`).

## Extending this module

When adding new lookup types:

1. Add **inputs** only if root cannot derive them from existing YAML/locals.
2. Gate **expensive** `data` sources with a `count` tied to a `local.needs_*` flag.
3. Expose stable **outputs**; merge at root if multiple modules need the same id map.
4. Update **this document** and, where relevant, `schemas/v1.json` descriptions.
