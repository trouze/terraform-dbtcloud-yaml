# Testing Guide

This directory contains test fixtures, utilities, and documentation for testing the terraform-dbtcloud-yaml module.

## Test Structure

### Unit Tests (Terratest)

Located in Go test files:
- Test fixtures for v1 and v2 schemas
- YAML parsing validation
- Output validation
- Schema validation

### End-to-End Tests

Located in `e2e_test/`:
- Complete workflow testing (fetch → normalize → apply)
- Real account integration testing
- See [Phase 5 E2E Testing Guide](../dev_support/phase5_e2e_testing_guide.md)

## Running Tests

### Quick Start: Automated E2E Test

The easiest way to run end-to-end testing:

```bash
# 1. Set up credentials
cd test/e2e_test
cp env.example .env
# Edit .env with your credentials

# 2. Run automated test (plan only)
cd ..
./run_e2e_test.sh

# 3. (Optional) Run with apply
./run_e2e_test.sh --apply
```

The script will:
- ✅ Check prerequisites
- ✅ Clean workspace
- ✅ Run fetch
- ✅ Run normalize
- ✅ Validate Terraform
- ✅ Generate plan
- ✅ (Optional) Apply changes
- ✅ Create test summary

### Manual E2E Testing

For step-by-step testing, follow the [Phase 5 E2E Testing Guide](../dev_support/phase5_e2e_testing_guide.md).

### Unit Tests (Terratest)

```bash
cd test
go test -v -timeout 30m
```

## Test Fixtures

### v1 Schema Tests

- `fixtures/basic/` - Basic v1 schema test
- Legacy single-project format

### v2 Schema Tests

- `fixtures/v2_basic/` - Basic v2 schema with minimal resources
- `fixtures/v2_complete/` - Complete v2 schema with all resource types

### E2E Test Fixture

- `e2e_test/` - End-to-end testing environment
- Uses real account data
- Includes automated test script

## Test Checklist

Before running end-to-end tests:

- [ ] Python 3.9+ installed with dependencies
- [ ] Terraform 1.5+ installed (recommend 1.14.1)
- [ ] Source account credentials configured
- [ ] Target account credentials configured
- [ ] Test account has representative data
- [ ] Clean workspace (no existing exports)

See full checklist: [End-to-End Testing Readiness Checklist](../dev_support/importer_implementation_status.md#end-to-end-testing-readiness-checklist)

## Test Results

After running tests, results are saved to:

- `e2e_test/test_summary.md` - Test results summary
- `e2e_test/test_log.md` - Detailed test log (if manually testing)
- `e2e_test/plan_output.txt` - Terraform plan output

## Troubleshooting

See [Phase 5 E2E Testing Guide - Troubleshooting](../dev_support/phase5_e2e_testing_guide.md#troubleshooting) for common issues and solutions.

## Documentation

- [Phase 5 E2E Testing Guide](../dev_support/phase5_e2e_testing_guide.md) - Complete testing procedure
- [Importer Implementation Status](../dev_support/importer_implementation_status.md) - Current testing status
- [Known Issues](../dev_support/known_issues.md) - Known limitations and workarounds

## Contributing

When adding new tests:

1. Create test fixture in `fixtures/` directory
2. Add test case to appropriate test file
3. Document test purpose and expected results
4. Update this README with test coverage information
