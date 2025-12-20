# End-to-End Test Directory

This directory contains the setup for Phase 5 end-to-end testing.

## Purpose

Test the complete workflow from source account fetch through Terraform apply in a target account.

## Setup

1. **Create `.env` file** with credentials (copy from `.env.example`):
   ```bash
   cp env.example .env
   # Edit .env with your actual credentials
   ```

2. **Run fetch and normalize** (from project root):
   ```bash
   cd ../..
   python -m importer fetch --interactive
   python -m importer normalize --interactive
   ```

3. **Copy generated YAML** to this directory:
   ```bash
   cp importer_export/normalized_*.yml test/e2e_test/dbt-cloud-config.yml
   ```

4. **Manually add connection provider configs** to YAML:
   - Open `dbt-cloud-config.yml`
   - Add `provider_config` section to each connection
   - See [Phase 5 E2E Testing Guide](../../dev_support/phase5_e2e_testing_guide.md) for examples

5. **Initialize Terraform**:
   ```bash
   terraform init -backend=false
   ```

6. **Validate configuration**:
   ```bash
   terraform validate
   ```

7. **Plan changes**:
   ```bash
   terraform plan -out=tfplan
   ```

8. **(Optional) Apply changes**:
   ```bash
   terraform apply tfplan
   ```

## Files

- `main.tf` - Terraform configuration calling root module
- `env.example` - Template for environment variables
- `dbt-cloud-config.yml` - Generated YAML (not in git, created during testing)
- `test_log.md` - Test execution log (created during testing)
- `test_summary.md` - Test results summary (created after testing)

## Documentation

See the complete testing guide: [Phase 5 E2E Testing Guide](../../dev_support/phase5_e2e_testing_guide.md)

## Cleanup

After testing, remove generated files:

```bash
rm -f dbt-cloud-config.yml test_log.md test_summary.md plan_output.txt tfplan
rm -rf .terraform .terraform.lock.hcl terraform.tfstate*
```

