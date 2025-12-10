# Quick Testing Guide - Phase 3

## ✅ What We Can Test Right Now (No Credentials Needed)

### 1. Terraform Syntax Validation (2 minutes)

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml

# Format all files
terraform fmt -recursive

# Validate root module
terraform init -backend=false
terraform validate

# Validate v2 module
cd modules/projects_v2
terraform init -backend=false  
terraform validate
cd ../..

# Validate v2 test fixture
cd test/fixtures/v2_basic
terraform init -backend=false
terraform validate
```

**Expected:** All validations pass without errors

### 2. Schema Detection Test (1 minute)

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/test/fixtures/v2_basic

# Check that YAML is detected as v2
terraform init -backend=false
terraform plan -var-file=terraform.tfvars -out=tfplan 2>&1 | grep -E "(projects_v2|Error)" | head -5
```

**Expected:** Plan output mentions `module.projects_v2` or `module.dbt_cloud.module.projects_v2`

### 3. YAML Structure Validation

```bash
# Verify v2 YAML structure
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml
grep -q "version: 2" test/fixtures/v2_basic/dbt-config.yml && echo "✅ v2 schema detected" || echo "❌ Missing version"
grep -q "account:" test/fixtures/v2_basic/dbt-config.yml && echo "✅ Account section found" || echo "❌ Missing account"
grep -q "globals:" test/fixtures/v2_basic/dbt-config.yml && echo "✅ Globals section found" || echo "❌ Missing globals"
grep -q "projects:" test/fixtures/v2_basic/dbt-config.yml && echo "✅ Projects section found" || echo "❌ Missing projects"
```

**Expected:** All checks pass

---

## ⚠️ What Needs Setup

### Terratest Suite

The Go test dependencies have an issue. To fix:

```bash
cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml/test

# Update go.mod dependencies
go get -u github.com/gruntwork-io/terratest/modules/terraform@latest
go mod tidy

# Then run tests
go test -v -run TestV2 -timeout 5m
```

**Note:** Terratest is optional - Terraform validation is sufficient for basic testing.

---

## 🎯 Recommended Test Sequence

1. **Syntax Check** (30 seconds)
   ```bash
   terraform fmt -recursive && echo "✅ Format OK"
   ```

2. **Module Validation** (1 minute)
   ```bash
   cd modules/projects_v2 && terraform init -backend=false && terraform validate
   ```

3. **Fixture Validation** (1 minute)
   ```bash
   cd ../../test/fixtures/v2_basic && terraform init -backend=false && terraform validate
   ```

4. **Schema Detection** (30 seconds)
   ```bash
   terraform plan -var-file=terraform.tfvars 2>&1 | grep -i "projects_v2\|error" | head -3
   ```

**Total Time:** ~3 minutes

---

## 📋 Test Checklist

- [ ] All Terraform files formatted (`terraform fmt -recursive`)
- [ ] Root module validates (`terraform validate`)
- [ ] v2 module validates (`cd modules/projects_v2 && terraform validate`)
- [ ] v2_basic fixture validates (`cd test/fixtures/v2_basic && terraform validate`)
- [ ] v2_complete fixture validates (`cd test/fixtures/v2_complete && terraform validate`)
- [ ] Schema detection works (plan shows v2 module usage)
- [ ] YAML structure correct (version, account, globals, projects)

---

## 🐛 Known Issues

1. **Go Test Dependencies**: Terratest dependencies may need updating
   - **Workaround**: Skip Terratest, use Terraform validation instead
   
2. **Provider Download**: First `terraform init` downloads providers (one-time)
   - **Expected**: Takes 10-30 seconds first time

3. **Plan Errors**: Plan will fail on API calls (expected without real credentials)
   - **OK**: Syntax validation passes
   - **Not OK**: Module/variable errors

---

## 📚 Full Testing Guide

For comprehensive testing including end-to-end workflows, see:
- `dev_support/phase3_testing_guide.md` - Complete testing documentation
