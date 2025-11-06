# Testing Guide

This project includes comprehensive Terratest integration tests to validate the Terraform module works correctly with various configurations.

## Prerequisites

### System Requirements

- **Go** 1.20 or later ([install](https://golang.org/doc/install))
- **Terraform** 1.0 or later ([install](https://learn.hashicorp.com/tutorials/terraform/install-cli))
- **Git** ([install](https://git-scm.com/downloads))

### Environment Setup

```bash
# Install Go dependencies
cd test
go mod download
go mod tidy

# Return to project root
cd ..
```

## Running Tests

### Run All Tests

```bash
cd test
go test -v -timeout 30m
```

### Run Specific Test

```bash
cd test

# Test basic configuration
go test -v -run TestBasicConfiguration -timeout 10m

# Test complete configuration
go test -v -run TestCompleteConfiguration -timeout 10m

# Test YAML parsing
go test -v -run TestYAMLParsing -timeout 5m

# Test module structure
go test -v -run TestModuleStructure -timeout 5m
```

### Run Tests in Parallel

```bash
cd test
go test -v -parallel 4 -timeout 30m
```

### Run Tests with Coverage

```bash
cd test
go test -v -cover -coverprofile=coverage.out -timeout 30m
go tool cover -html=coverage.out  # Open in browser
```

## Test Categories

### 1. Configuration Tests

#### TestBasicConfiguration
- **Purpose:** Validates module with minimal YAML configuration
- **Validates:** Required fields, basic syntax, module initialization
- **Fixture:** `fixtures/basic/`
- **Time:** ~5 minutes

```bash
go test -v -run TestBasicConfiguration -timeout 10m
```

#### TestCompleteConfiguration
- **Purpose:** Validates module with comprehensive YAML including advanced features
- **Validates:** Multiple environments, complex jobs, environment variables
- **Fixture:** `fixtures/complete/`
- **Time:** ~5 minutes

```bash
go test -v -run TestCompleteConfiguration -timeout 10m
```

### 2. Validation Tests

#### TestYAMLParsing
- **Purpose:** Validates YAML files are correctly formatted
- **Validates:** YAML syntax, file structure, required sections
- **Fixture:** Auto-validates all fixtures
- **Time:** ~1 minute

```bash
go test -v -run TestYAMLParsing -timeout 5m
```

#### TestVariableValidation
- **Purpose:** Validates input variable constraints
- **Validates:** Type checking, required fields, validation rules
- **Fixture:** `fixtures/basic/`
- **Time:** ~3 minutes

```bash
go test -v -run TestVariableValidation -timeout 10m
```

### 3. Structure Tests

#### TestPathModule
- **Purpose:** Validates that all module sources use `path.module`
- **Validates:** Relative paths not used, portability compliance
- **Fixture:** `main.tf`
- **Time:** <1 minute

```bash
go test -v -run TestPathModule -timeout 5m
```

#### TestModuleStructure
- **Purpose:** Validates all required module files exist
- **Validates:** Required files present in each module
- **Fixture:** Module directory structure
- **Time:** <1 minute

```bash
go test -v -run TestModuleStructure -timeout 5m
```

### 4. Output Tests

#### TestOutputs
- **Purpose:** Validates module exports correct outputs
- **Validates:** All required outputs defined and accessible
- **Fixture:** `fixtures/basic/`
- **Expected Outputs:**
  - `project_id`
  - `repository_id`
  - `environment_ids`
  - `credential_ids`
  - `job_ids`
- **Time:** ~5 minutes

```bash
go test -v -run TestOutputs -timeout 10m
```

### 5. Documentation Tests

#### TestDocumentation
- **Purpose:** Validates documentation files are complete
- **Validates:** Required documentation sections present
- **Fixture:** Documentation files
- **Time:** <1 minute

```bash
go test -v -run TestDocumentation -timeout 5m
```

## Debugging Tests

### Enable Terraform Logging

```bash
export TF_LOG=DEBUG
go test -v -run TestBasicConfiguration -timeout 10m 2>&1 | tee test.log
```

### Inspect Test Fixtures

Test fixtures are created in temporary directories but can be inspected:

```bash
# Run test with verbose output
cd test
go test -v -run TestBasicConfiguration -timeout 10m

# Check output directory (created during test)
ls -la /tmp/dbt-terraform-test-*
```

### Keep Test Fixtures for Debugging

Modify `defer os.RemoveAll(tmpDir)` to skip cleanup:

```go
// Comment out this line to keep fixture
// defer os.RemoveAll(tmpDir)

// Then manually clean up later
rm -rf /tmp/dbt-terraform-test-*
```

### Run Manual Terraform Commands on Fixture

```bash
# Use the fixture directly
cd test/fixtures/basic

# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Plan (without applying)
TF_VAR_dbt_account_id=999999 terraform plan -no-color > plan.log

# View plan details
less plan.log
```

## Continuous Integration

### GitHub Actions

Tests run automatically on:
- Pull requests to `main` branch
- Commits to `main` branch
- Manual dispatch via GitHub Actions

Workflow file: `.github/workflows/terraform-test.yml` (to be created)

### Local Pre-commit Hook

Add this to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
cd test
go test -run TestModuleStructure -run TestPathModule -run TestDocumentation -timeout 5m
if [ $? -ne 0 ]; then
    echo "Tests failed - commit aborted"
    exit 1
fi
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Test Fixtures

### Fixture Structure

```
test/
├── fixtures/
│   ├── basic/
│   │   ├── main.tf          # Module usage
│   │   ├── variables.tf      # Input variables
│   │   └── dbt-config.yml    # Minimal YAML config
│   └── complete/
│       ├── main.tf          # Module usage
│       ├── variables.tf      # Input variables
│       └── dbt-config.yml    # Advanced YAML config
├── go.mod                    # Go dependencies
├── terraform_test.go         # Test suite
```

### Creating New Fixtures

To add a new test scenario:

1. Create fixture directory: `test/fixtures/scenario-name/`
2. Add files: `main.tf`, `variables.tf`, `dbt-config.yml`
3. Create test function in `terraform_test.go`:

```go
func TestScenarioName(t *testing.T) {
    t.Parallel()
    tmpDir := filepath.Join(os.TempDir(), "dbt-terraform-test-scenario")
    defer os.RemoveAll(tmpDir)
    
    err := copyDir("fixtures/scenario-name", tmpDir)
    require.NoError(t, err)
    
    // Test logic...
}
```

## Performance Tuning

### Parallel Test Execution

Tests use `t.Parallel()` for concurrent execution. Control parallelism:

```bash
# Run with 4 parallel workers
go test -v -parallel 4 -timeout 30m

# Run with 8 parallel workers (faster, higher resource usage)
go test -v -parallel 8 -timeout 30m

# Run tests serially (slowest, lowest resource usage)
go test -v -parallel 1 -timeout 30m
```

### Skip Terraform Validation Steps

Modify test to skip expensive operations:

```go
// Skip lock file creation
terraformOptions.Lock = false

// Skip validation
terraform.Init(t, terraformOptions)
// terraform.Validate(t, terraformOptions)  // Skip
```

## Troubleshooting

### "terraform init" Fails

**Cause:** Missing provider or version mismatch

```bash
# Update provider requirements
cd test/fixtures/basic
terraform init -upgrade

# Check provider version
terraform version
```

### "Permission denied" on dbt-config.yml

**Cause:** File permissions issue

```bash
chmod 644 test/fixtures/*/dbt-config.yml
```

### "YAML parsing error"

**Cause:** Invalid YAML in fixture

```bash
# Validate YAML
python3 -c "
import yaml
with open('dbt-config.yml') as f:
    yaml.safe_load(f)
print('✅ Valid YAML')
"
```

### Timeout Errors

Increase timeout or investigate slow operations:

```bash
# Increase timeout to 60 minutes
go test -v -timeout 60m

# Run with profiling
go test -v -cpuprofile=cpu.prof -timeout 30m
go tool pprof cpu.prof  # Analyze
```

## Adding Tests

### Template for New Test

```go
func TestNewScenario(t *testing.T) {
    t.Parallel()
    
    // Setup
    tmpDir := filepath.Join(os.TempDir(), "dbt-terraform-test-scenario")
    defer os.RemoveAll(tmpDir)
    
    err := copyDir("fixtures/scenario", tmpDir)
    require.NoError(t, err)
    
    // Configure
    terraformOptions := &terraform.Options{
        TerraformDir: tmpDir,
        VarFiles:     []string{"terraform.tfvars"},
        Lock:         true,
        NoColor:      true,
        Logger:       t,
        Vars: map[string]interface{}{
            "dbt_account_id": "999999",
            "dbt_host_url":   "https://cloud.getdbt.com",
        },
    }
    
    // Execute
    defer terraform.Destroy(t, terraformOptions)
    terraform.Init(t, terraformOptions)
    
    // Validate
    planOutput := terraform.Plan(t, terraformOptions)
    assert.NotContains(t, planOutput, "Error")
}
```

## Next Steps

- ✅ Set up Go development environment
- ✅ Run `go test -v` in test directory
- ✅ Verify all tests pass
- ✅ Add tests to CI/CD pipeline
- ✅ Run tests before releases

## Questions?

- See [Troubleshooting in README](../README.md#troubleshooting)
- Check [Contributing Guidelines](../CONTRIBUTING.md)
- Open an [issue on GitHub](https://github.com/trouze/dbt-cloud-terraform-starter/issues)
