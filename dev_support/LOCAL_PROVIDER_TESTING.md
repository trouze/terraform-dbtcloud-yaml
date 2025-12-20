# Testing with Local Terraform Provider

This guide explains how to test the terraform-dbtcloud-yaml module with a locally built version of the Terraform provider.

## Overview

When developing fixes or features in the Terraform provider (`terraform-provider-dbtcloud`), you may want to test them with the terraform-dbtcloud-yaml module before submitting a PR. Terraform's `dev_overrides` feature allows you to use a locally built provider instead of downloading from the registry.

## Setup

### 1. Build the Local Provider

Navigate to the provider repository and build it:

```bash
cd /path/to/terraform-provider-dbtcloud
go build -o terraform-provider-dbtcloud
```

This creates a binary `terraform-provider-dbtcloud` in the current directory.

### 2. Configure Terraform dev_overrides

Create or edit `~/.terraformrc` (or `%APPDATA%\terraform.rc` on Windows):

```hcl
provider_installation {
  dev_overrides {
    "dbt-labs/dbtcloud" = "/absolute/path/to/terraform-provider-dbtcloud"
  }
  direct {}
}
```

**Important**: Use the **absolute path** to the directory containing the provider binary, not the binary itself.

**Example**:
```hcl
provider_installation {
  dev_overrides {
    "dbt-labs/dbtcloud" = "/Users/operator/Documents/git/dbt-labs/terraform-provider-dbtcloud"
  }
  direct {}
}
```

### 3. Verify Configuration

Run `terraform init` in any directory that uses the provider. You should see:

```
Warning: Provider development overrides are in effect
```

This confirms Terraform is using your local provider.

## Testing with E2E Test Script

The E2E test script (`test/run_e2e_test.sh`) automatically uses the local provider if `dev_overrides` is configured:

```bash
cd /path/to/terraform-dbtcloud-yaml/test
./run_e2e_test.sh --test-apply
```

The script runs `terraform init -backend=false`, which respects the `dev_overrides` configuration.

### Verification Steps

1. **Check that dev_overrides are active**:
   ```bash
   cd test/e2e_test
   terraform init -backend=false
   ```
   Look for: `Warning: Provider development overrides are in effect`

2. **Run the E2E test**:
   ```bash
   cd ..
   ./run_e2e_test.sh --test-plan
   ```

3. **Verify the local provider is being used**:
   - Check the Terraform init output for the warning message
   - The provider version should match your local build
   - Any fixes/features should be visible in the test results

## Rebuilding After Changes

After making changes to the provider code, rebuild it:

```bash
cd /path/to/terraform-provider-dbtcloud
go build -o terraform-provider-dbtcloud
```

**Note**: You may need to clear Terraform's provider cache or re-run `terraform init`:

```bash
cd test/e2e_test
rm -rf .terraform .terraform.lock.hcl
terraform init -backend=false
```

## Troubleshooting

### Provider Not Found

**Error**: `Error: Failed to query available provider packages`

**Solution**: 
- Verify the path in `~/.terraformrc` is absolute and correct
- Ensure the provider binary exists at that location
- Check file permissions: `chmod +x terraform-provider-dbtcloud`

### Wrong Provider Version

**Issue**: Terraform still uses registry version

**Solution**:
- Clear Terraform cache: `rm -rf .terraform .terraform.lock.hcl`
- Re-run `terraform init`
- Verify the warning message appears

### Provider Binary Not Executable

**Error**: Permission denied

**Solution**:
```bash
chmod +x /path/to/terraform-provider-dbtcloud/terraform-provider-dbtcloud
```

## Disabling dev_overrides

To return to using the registry version:

1. **Comment out or remove** the `dev_overrides` block in `~/.terraformrc`:
   ```hcl
   provider_installation {
     # dev_overrides {
     #   "dbt-labs/dbtcloud" = "/path/to/provider"
     # }
     direct {}
   }
   ```

2. **Clear Terraform cache**:
   ```bash
   rm -rf .terraform .terraform.lock.hcl
   ```

3. **Re-initialize**:
   ```bash
   terraform init
   ```

## Example Workflow

Complete workflow for testing a provider fix:

```bash
# 1. Make changes to provider code
cd /path/to/terraform-provider-dbtcloud
# ... edit code ...

# 2. Build provider
go build -o terraform-provider-dbtcloud

# 3. Configure dev_overrides (if not already done)
cat > ~/.terraformrc << 'EOF'
provider_installation {
  dev_overrides {
    "dbt-labs/dbtcloud" = "/path/to/terraform-provider-dbtcloud"
  }
  direct {}
}
EOF

# 4. Test with E2E script
cd /path/to/terraform-dbtcloud-yaml/test
./run_e2e_test.sh --test-apply

# 5. Verify fix works
# Check test output for expected behavior
```

## Related Documentation

- [Terraform Provider Development Overrides](https://www.terraform.io/docs/cli/config/config-file.html#provider-installation)
- [Phase 5 E2E Testing Guide](./phase5_e2e_testing_guide.md)
- [Known Issues](./KNOWN_ISSUES.md)

