# Known Issues

## Module Variable Recognition Issue

**Status:** Under Investigation  
**Date:** 2025-01-27  
**Terraform Version:** 1.14.1

### Problem

When the root module (`/`) is used as a module from test fixtures (`test/fixtures/*/main.tf`), Terraform loads the module but doesn't recognize its variables (`yaml_file`, `target_name`, `token_map`, etc.).

**Error:**
```
Error: Unsupported argument
  on main.tf line 19, in module "dbt_cloud":
  19:   yaml_file   = "${path.module}/dbt-config.yml"
An argument named "yaml_file" is not expected here.
```

### Investigation

- ✅ Variables are correctly defined in `variables.tf` (7 variables found)
- ✅ Module loads successfully (`- dbt_cloud in ../..`)
- ✅ No syntax errors in `variables.tf` or `main.tf`
- ❌ Terraform doesn't extract variable schema when module is loaded

### Affected Areas

- `test/fixtures/basic/main.tf` - Also affected
- `test/fixtures/v2_basic/main.tf` - Affected
- `test/fixtures/v2_complete/main.tf` - Likely affected

### Workaround

1. **Direct Module Testing**: Test modules directly without using root as module
   ```bash
   cd modules/projects_v2
   terraform init -backend=false
   terraform validate
   ```

2. **Root Module Testing**: Test root module as root (not as module)
   ```bash
   cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml
   terraform init -backend=false
   terraform validate
   ```

### Possible Causes

1. Terraform 1.14.1 behavior change with local module loading
2. Module structure issue preventing variable schema extraction
3. `file()` call in `main.tf` locals block causing parsing issues
4. Provider configuration in root module interfering with module loading

### Next Steps

1. Test with different Terraform versions
2. Investigate Terraform module loading internals
3. Consider restructuring root module if needed
4. Check Terraform issue tracker for similar reports

### Related Files

- `variables.tf` - Variable definitions
- `main.tf` - Module logic with `file(var.yaml_file)` call
- `providers.tf` - Provider configuration
- `test/fixtures/*/main.tf` - Test fixtures calling root as module
