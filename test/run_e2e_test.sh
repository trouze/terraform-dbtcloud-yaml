#!/bin/bash
# End-to-End Test Execution Script
# 
# This script automates the end-to-end testing workflow for Phase 5.
# It executes fetch, normalize, and Terraform validation steps.
#
# Usage:
#   ./run_e2e_test.sh [--apply]
#
# Options:
#   --apply    Run terraform apply (default: plan only)
#
# Prerequisites:
#   - Python 3.9+ with importer dependencies installed
#   - Terraform 1.5+ installed
#   - .env file configured with credentials in test/e2e_test/

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$PROJECT_ROOT/test/e2e_test"
EXPORT_DIR="$PROJECT_ROOT/importer_export"
APPLY_FLAG=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --apply)
      APPLY_FLAG=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Python
    if ! command -v python &> /dev/null; then
        log_error "Python not found. Please install Python 3.9+"
        exit 1
    fi
    
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    log_success "Python $PYTHON_VERSION found"
    
    # Check Terraform
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform not found. Please install Terraform 1.5+"
        exit 1
    fi
    
    TF_VERSION=$(terraform version -json | jq -r '.terraform_version')
    log_success "Terraform $TF_VERSION found"
    
    # Check .env file
    if [ ! -f "$TEST_DIR/.env" ]; then
        log_warning ".env file not found in $TEST_DIR"
        log_info "Creating .env from template..."
        cp "$TEST_DIR/env.example" "$TEST_DIR/.env"
        log_error "Please edit $TEST_DIR/.env with your credentials and re-run"
        exit 1
    fi
    
    # Load environment variables
    set -a
    source "$TEST_DIR/.env"
    set +a
    
    # Check required variables
    if [ -z "$DBT_CLOUD_ACCOUNT_ID" ] || [ -z "$DBT_CLOUD_TOKEN" ]; then
        log_error "DBT_CLOUD_ACCOUNT_ID and DBT_CLOUD_TOKEN must be set in .env"
        exit 1
    fi
    
    if [ -z "$DBTCLOUD_ACCOUNT_ID" ] || [ -z "$DBTCLOUD_TOKEN" ]; then
        log_error "DBTCLOUD_ACCOUNT_ID and DBTCLOUD_TOKEN must be set in .env"
        exit 1
    fi
    
    log_success "All prerequisites met"
}

clean_workspace() {
    log_info "Cleaning workspace..."
    
    # Backup existing exports
    if [ -d "$EXPORT_DIR" ]; then
        BACKUP_DIR="$EXPORT_DIR.backup.$(date +%Y%m%d_%H%M%S)"
        log_warning "Backing up existing exports to $BACKUP_DIR"
        mv "$EXPORT_DIR" "$BACKUP_DIR"
    fi
    
    # Clean test directory
    rm -f "$TEST_DIR/dbt-cloud-config.yml"
    rm -f "$TEST_DIR/test_log.md"
    rm -f "$TEST_DIR/plan_output.txt"
    rm -f "$TEST_DIR/tfplan"
    
    log_success "Workspace cleaned"
}

phase1_fetch() {
    log_info "=== Phase 1: Fetch Source Account ==="
    
    cd "$PROJECT_ROOT"
    
    log_info "Running importer fetch..."
    python -m importer fetch
    
    # Find the most recent export
    EXPORT_FILE=$(ls -t "$EXPORT_DIR"/account_*_run_*.json 2>/dev/null | head -1)
    
    if [ -z "$EXPORT_FILE" ]; then
        log_error "No export file found after fetch"
        exit 1
    fi
    
    log_success "Fetch completed: $EXPORT_FILE"
    
    # Log statistics
    PROJECT_COUNT=$(jq '.projects | length' "$EXPORT_FILE")
    CONNECTION_COUNT=$(jq '.connections | length' "$EXPORT_FILE")
    
    log_info "Projects fetched: $PROJECT_COUNT"
    log_info "Connections fetched: $CONNECTION_COUNT"
    
    echo "$EXPORT_FILE"
}

phase2_normalize() {
    local export_file=$1
    
    log_info "=== Phase 2: Normalize to YAML ==="
    
    cd "$PROJECT_ROOT"
    
    log_info "Running importer normalize..."
    python -m importer normalize "$export_file"
    
    # Find the most recent normalized YAML
    YAML_FILE=$(ls -t "$EXPORT_DIR"/normalized_*.yml 2>/dev/null | head -1)
    
    if [ -z "$YAML_FILE" ]; then
        log_error "No YAML file found after normalization"
        exit 1
    fi
    
    log_success "Normalize completed: $YAML_FILE"
    
    # Validate YAML syntax
    if python -c "import yaml; yaml.safe_load(open('$YAML_FILE'))" 2>/dev/null; then
        log_success "YAML syntax is valid"
    else
        log_error "YAML syntax is invalid"
        exit 1
    fi
    
    # Copy to test directory
    cp "$YAML_FILE" "$TEST_DIR/dbt-cloud-config.yml"
    log_success "YAML copied to test directory"
    
    echo "$YAML_FILE"
}

phase3_validate() {
    log_info "=== Phase 3: Terraform Validation ==="
    
    cd "$TEST_DIR"
    
    # Check if YAML has connection provider configs
    if ! grep -q "provider_config:" dbt-cloud-config.yml; then
        log_error "No provider_config found in YAML"
        log_error "Please manually add provider_config to connections in:"
        log_error "  $TEST_DIR/dbt-cloud-config.yml"
        log_error ""
        log_error "Example:"
        log_error "  connections:"
        log_error "    databricks_connection:"
        log_error "      name: \"Databricks Production\""
        log_error "      type: \"databricks\""
        log_error "      provider_config:"
        log_error "        host: \"your-workspace.cloud.databricks.com\""
        log_error "        http_path: \"/sql/1.0/warehouses/abc123\""
        log_error ""
        log_error "After adding provider configs, re-run this script"
        exit 1
    fi
    
    log_info "Initializing Terraform..."
    terraform init -backend=false
    
    log_info "Validating Terraform configuration..."
    if terraform validate; then
        log_success "Terraform validation passed"
    else
        log_error "Terraform validation failed"
        exit 1
    fi
}

phase4_plan() {
    log_info "=== Phase 4: Terraform Plan ==="
    
    cd "$TEST_DIR"
    
    log_info "Running terraform plan..."
    if terraform plan -out=tfplan 2>&1 | tee plan_output.txt; then
        log_success "Terraform plan completed"
    else
        log_error "Terraform plan failed"
        log_error "See plan_output.txt for details"
        exit 1
    fi
    
    # Extract resource counts
    if grep -q "Plan:" plan_output.txt; then
        PLAN_SUMMARY=$(grep "Plan:" plan_output.txt)
        log_info "$PLAN_SUMMARY"
    fi
    
    # Check for errors
    if grep -qi "error" plan_output.txt; then
        log_warning "Errors detected in plan output"
        grep -i "error" plan_output.txt | head -5
    fi
}

phase5_apply() {
    if [ "$APPLY_FLAG" = false ]; then
        log_warning "Skipping apply (use --apply flag to enable)"
        return
    fi
    
    log_info "=== Phase 5: Terraform Apply ==="
    
    cd "$TEST_DIR"
    
    log_warning "About to apply Terraform changes to account $DBTCLOUD_ACCOUNT_ID"
    log_warning "Press Ctrl+C within 10 seconds to cancel..."
    sleep 10
    
    log_info "Running terraform apply..."
    if terraform apply tfplan; then
        log_success "Terraform apply completed"
        
        # Show outputs
        log_info "Resource IDs created:"
        terraform output -json
    else
        log_error "Terraform apply failed"
        exit 1
    fi
}

create_test_summary() {
    log_info "=== Creating Test Summary ==="
    
    cd "$TEST_DIR"
    
    cat > test_summary.md << EOF
# End-to-End Test Summary

**Test Date:** $(date)
**Importer Version:** $(cd "$PROJECT_ROOT" && python -m importer --version)
**Terraform Version:** $(terraform version -json | jq -r '.terraform_version')

## Test Account Details
- **Source Account ID:** $DBT_CLOUD_ACCOUNT_ID
- **Target Account ID:** $DBTCLOUD_ACCOUNT_ID

## Results

### Phase 1: Fetch
- Status: ✅ Success
- Export File: $(basename "$EXPORT_FILE")
- Projects: $(jq '.projects | length' "$EXPORT_FILE")
- Connections: $(jq '.connections | length' "$EXPORT_FILE")

### Phase 2: Normalize
- Status: ✅ Success
- YAML File: dbt-cloud-config.yml
- YAML Validation: ✅ Valid

### Phase 3: Terraform Validation
- Status: ✅ Success
- Validation: Passed

### Phase 4: Terraform Plan
- Status: ✅ Success
$(grep "Plan:" plan_output.txt || echo "- No plan summary available")

### Phase 5: Terraform Apply
EOF

    if [ "$APPLY_FLAG" = true ]; then
        cat >> test_summary.md << EOF
- Status: ✅ Success
- Resources Created: $(terraform show -json 2>/dev/null | jq '[.values.root_module.resources[]] | length' || echo "N/A")
EOF
    else
        cat >> test_summary.md << EOF
- Status: N/A (skipped)
EOF
    fi
    
    cat >> test_summary.md << EOF

## Files Generated
- Export: $EXPORT_FILE
- YAML: $TEST_DIR/dbt-cloud-config.yml
- Plan Output: $TEST_DIR/plan_output.txt
- Summary: $TEST_DIR/test_summary.md

## Next Steps
- Review test_summary.md and plan_output.txt
- Update importer_implementation_status.md Phase 5 section
- Document any issues or improvements needed
EOF

    log_success "Test summary created: $TEST_DIR/test_summary.md"
}

# Main execution
main() {
    log_info "Starting End-to-End Test"
    log_info "Apply mode: $APPLY_FLAG"
    echo ""
    
    check_prerequisites
    clean_workspace
    
    EXPORT_FILE=$(phase1_fetch)
    YAML_FILE=$(phase2_normalize "$EXPORT_FILE")
    phase3_validate
    phase4_plan
    phase5_apply
    create_test_summary
    
    echo ""
    log_success "=== End-to-End Test Complete ==="
    log_info "Review results in: $TEST_DIR/test_summary.md"
    
    if [ "$APPLY_FLAG" = false ]; then
        log_info "To run with apply: ./run_e2e_test.sh --apply"
    fi
}

main

