# Release Notes v0.6.2

**Release Date:** 2025-12-20  
**Type:** Patch Release (Bug Fixes)  
**Previous Version:** 0.6.1

---

## Summary

This patch release fixes two critical bugs affecting cross-account migration:

1. **Service Token Permission Grants**: The dbt Cloud API requires permissions to be passed via `permission_grants` during service token creation, not `service_token_permissions`. The provider was using the wrong field name.

2. **Cross-Account Project ID Resolution**: Service token and group permissions were using source account project IDs, which don't exist in the target account, causing 404 errors during apply.

---

## Bug Fixes

### 1. Service Token Permission Grants (Provider Fix)

**Problem:**
- dbt Cloud API POST `/service-tokens/` endpoint expects `permission_grants` array
- Provider was sending `service_token_permissions` which was ignored by the API
- Service tokens were created without any permissions

**Solution:**
- Added `ServiceTokenPermissionGrant` struct with correct JSON tags
- Added `CreateServiceTokenRequest` struct with `permission_grants` field
- Updated `CreateServiceToken()` to use the correct request structure
- Changed `WritableEnvironmentCategories` to pointer type (`*[]EnvironmentCategory`) to properly serialize empty arrays (vs omitting them)

**Files Changed:**
- `terraform-provider-dbtcloud/pkg/dbt_cloud/service_token.go`
- `terraform-provider-dbtcloud/pkg/framework/objects/service_token/model.go`
- `terraform-provider-dbtcloud/pkg/framework/objects/service_token/resource.go`

### 2. Cross-Account Project ID Resolution (Normalizer + Terraform Fix)

**Problem:**
- Service token permissions like `{"project_id": 346697, "permission_set": "developer"}` use source account project IDs
- When migrating to a target account, project ID 346697 doesn't exist
- Terraform apply failed with 404 errors: `resource-not-found-permissions`

**Solution:**
- Added `project_id_to_key` mapping in `NormalizationContext` to track source project IDs → project keys
- Added `_build_project_id_mapping()` pre-pass in normalizer to build the mapping
- Updated `_normalize_service_tokens()` to output `project_key` instead of `project_id`
- Updated `_normalize_groups()` to output `project_key` instead of `project_id`
- Updated Terraform module to resolve `project_key` → target `project_id` using `dbtcloud_project.projects[project_key].id`

**Example - Before (source project ID):**
```yaml
service_token_permissions:
  - permission_set: developer
    project_id: 346697  # Source account ID - doesn't exist in target!
```

**Example - After (project key reference):**
```yaml
service_token_permissions:
  - permission_set: developer
    project_key: getting_to_ok_clone_and_defer  # Resolved at apply time
    project_id: null
```

**Files Changed:**
- `terraform-dbtcloud-yaml/importer/normalizer/__init__.py`
- `terraform-dbtcloud-yaml/importer/normalizer/core.py`
- `terraform-dbtcloud-yaml/modules/projects_v2/globals.tf`

---

## Technical Details

### Provider Changes

```go
// New struct for API creation request
type ServiceTokenPermissionGrant struct {
    PermissionSet               string                 `json:"permission_set"`
    ProjectID                   *int                   `json:"project_id,omitempty"`
    WritableEnvironmentCategories *[]EnvironmentCategory `json:"writable_environment_categories,omitempty"`
}

// Request body with correct field name
type CreateServiceTokenRequest struct {
    Name            string                      `json:"name"`
    PermissionGrants []ServiceTokenPermissionGrant `json:"permission_grants,omitempty"`
}
```

### Normalizer Changes

```python
# New context method
def resolve_project_id_to_key(self, project_id: Optional[int]) -> Optional[str]:
    """Resolve a project ID to its normalized key."""
    if not project_id:
        return None
    return self.project_id_to_key.get(project_id)

# Pre-pass to build mapping
def _build_project_id_mapping(projects: List[Dict], context: NormalizationContext) -> None:
    for project in projects:
        if project_id := project.get("id"):
            key = context.generate_key("project", project.get("name", "unnamed"))
            context.register_project(project_id, key)
```

### Terraform Changes

```hcl
# Service token permissions now resolve project_key to target ID
dynamic "service_token_permissions" {
  for_each = try(each.value.service_token_permissions, [])
  content {
    permission_set = service_token_permissions.value.permission_set
    all_projects   = try(service_token_permissions.value.all_projects, false)
    project_id     = try(
      service_token_permissions.value.project_key != null ?
      dbtcloud_project.projects[service_token_permissions.value.project_key].id :
      null,
      null
    )
  }
}
```

---

## Upgrade Instructions

### For dbt Cloud Account Migration

1. Update importer version:
   ```bash
   git pull  # or pip install -U dbt-cloud-importer
   ```

2. Re-run normalization to generate updated YAML:
   ```bash
   python3 -m importer normalize --input dev_support/samples/your_export.json --output test/e2e_test/dbt-cloud-config.yml
   ```

3. Verify YAML shows `project_key` instead of `project_id` for service token permissions:
   ```yaml
   service_token_permissions:
     - permission_set: developer
       project_key: your_project_key  # ← Should see project_key
       project_id: null               # ← project_id should be null
   ```

4. Re-run Terraform:
   ```bash
   terraform plan
   terraform apply
   ```

### For Local Provider Development

If using a local build of the provider:

1. Rebuild the provider:
   ```bash
   cd terraform-provider-dbtcloud
   go build -o terraform-provider-dbtcloud
   ```

2. Ensure dev_overrides are configured in `~/.terraformrc`:
   ```hcl
   provider_installation {
     dev_overrides {
       "dbt-labs/dbtcloud" = "/path/to/terraform-provider-dbtcloud"
     }
     direct {}
   }
   ```

---

## Verification

After upgrading, verify the fix:

1. **Check YAML output** for `project_key` in permissions:
   ```bash
   grep -A5 "service_token_permissions" test/e2e_test/dbt-cloud-config.yml
   ```

2. **Run Terraform plan** - should not show 404 errors for permissions

3. **Check service tokens in target account** - should have correct project associations

---

## Related Issues

- Service token permissions cannot be modified after creation - must be set during create
- dbt Cloud API documentation: [Service Token API](https://docs.getdbt.com/dbt-cloud/api-v3#/operations/Create%20Service%20Token)

---

## Contributors

- Provider fix for `permission_grants` field
- Normalizer enhancement for project ID → key mapping
- Terraform module updates for dynamic project resolution

