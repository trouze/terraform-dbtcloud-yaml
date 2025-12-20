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
EXPORT_DIR="$PROJECT_ROOT/dev_support/samples"
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
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Python (prefer python3, fall back to python)
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python not found. Please install Python 3.9+"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    log_success "Python $PYTHON_VERSION found ($PYTHON_CMD)"
    
    # Check if importer dependencies are installed
    if ! $PYTHON_CMD -c "import typer" 2>/dev/null; then
        log_warning "Importer dependencies not found in current Python environment"
        
        # Check for virtual environment
        if [ -d "$PROJECT_ROOT/.venv" ]; then
            log_info "Found .venv directory, activating..."
            source "$PROJECT_ROOT/.venv/bin/activate"
            log_success "Virtual environment activated"
        elif [ -d "$PROJECT_ROOT/venv" ]; then
            log_info "Found venv directory, activating..."
            source "$PROJECT_ROOT/venv/bin/activate"
            log_success "Virtual environment activated"
        else
            log_error "No virtual environment found. Please:"
            log_error "  1. Create venv: python3 -m venv .venv"
            log_error "  2. Activate it: source .venv/bin/activate"
            log_error "  3. Install deps: pip install -r importer/requirements.txt"
            log_error "OR activate your existing venv before running this script"
            exit 1
        fi
        
        # Verify again after activation
        if ! $PYTHON_CMD -c "import typer" 2>/dev/null; then
            log_error "Importer dependencies still not found. Please install:"
            log_error "  pip install -r importer/requirements.txt"
            exit 1
        fi
    fi
    log_success "Importer dependencies found"
    
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
    
    # Recreate export directory
    mkdir -p "$EXPORT_DIR"
    
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
    
    # Generate output filename (importer will auto-number the run)
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    ACCOUNT_ID="${DBT_CLOUD_ACCOUNT_ID:-unknown}"
    OUTPUT_FILE="$EXPORT_DIR/account_${ACCOUNT_ID}_fetch_${TIMESTAMP}.json"
    
    log_info "Running importer fetch..."
    log_info "Requested output: $OUTPUT_FILE"
    $PYTHON_CMD -m importer fetch --output "$OUTPUT_FILE" >&2
    
    # Find the actual file created (importer may use different timestamp/run number)
    EXPORT_FILE=$(ls -t "$EXPORT_DIR"/account_*_run_*__json__*.json 2>/dev/null | head -1)
    
    # Verify a file was created
    if [ -z "$EXPORT_FILE" ] || [ ! -f "$EXPORT_FILE" ]; then
        log_error "No export file found after fetch"
        log_error "Looked in: $EXPORT_DIR"
        ls -la "$EXPORT_DIR" 2>&1 | head -10
        exit 1
    fi
    
    log_success "Fetch completed: $EXPORT_FILE"
    
    # Log statistics
    PROJECT_COUNT=$(jq '.projects | length' "$EXPORT_FILE" 2>/dev/null)
    CONNECTION_COUNT=$(jq '.connections | length' "$EXPORT_FILE" 2>/dev/null)
    
    log_info "Projects fetched: $PROJECT_COUNT"
    log_info "Connections fetched: $CONNECTION_COUNT"
    
    echo "$EXPORT_FILE"
}

phase2_normalize() {
    local export_file=$1
    
    log_info "=== Phase 2: Normalize to YAML ==="
    
    cd "$PROJECT_ROOT"
    
    log_info "Running importer normalize..."
    $PYTHON_CMD -m importer normalize "$export_file" >&2
    
    # Find the most recent normalized YAML
    YAML_FILE=$(ls -t "$EXPORT_DIR"/normalized/account_*_norm_*__yaml__*.yml 2>/dev/null | head -1)
    
    if [ -z "$YAML_FILE" ]; then
        log_error "No YAML file found after normalization"
        exit 1
    fi
    
    log_success "Normalize completed: $YAML_FILE"
    
    # Validate YAML syntax
    if $PYTHON_CMD -c "import yaml; yaml.safe_load(open('$YAML_FILE'))" 2>/dev/null; then
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

configure_provider_configs() {
    log_info "=== Provider Configuration Check ==="
    
    local yaml_file="$TEST_DIR/dbt-cloud-config.yml"
    
    # Check if provider_config already exists
    if grep -q "provider_config:" "$yaml_file"; then
        log_success "provider_config found in YAML - skipping configuration"
        return 0
    fi
    
    # Extract connection information using Python
    log_warning "Connections missing provider_config (API security limitation)" >&2
    echo "" >&2
    
    log_info "Analyzing connections..." >&2
    local connections_info=$($PYTHON_CMD - "$yaml_file" <<'PYPEOF'
import sys
import yaml

yaml_path = sys.argv[1]
with open(yaml_path) as f:
    data = yaml.safe_load(f)

if 'globals' in data and 'connections' in data['globals']:
    connections = data['globals']['connections']
    if isinstance(connections, list):
        for conn in connections:
            conn_type = conn.get('type', 'unknown')
            conn_name = conn.get('name', 'Unknown')
            conn_key = conn.get('key', 'unknown')
            print(f"{conn_key}|{conn_name}|{conn_type}")
PYPEOF
)
    
    if [ -z "$connections_info" ]; then
        log_info "No connections found or all have provider_config" >&2
        return 0
    fi
    
    echo "Connections without provider_config:" >&2
    echo "" >&2
    echo "$connections_info" | while IFS='|' read -r key name type; do
        echo "  • $name" >&2
        echo "    Key: $key" >&2
        echo "    Type: $type" >&2
        echo "" >&2
    done
    
    echo "" >&2
    echo "Provider config is required for Terraform but not exported by the API." >&2
    echo "" >&2
    echo "Options:" >&2
    echo "  1) Add dummy/placeholder provider_config for testing (recommended for validation)" >&2
    echo "  2) Open YAML in editor for manual configuration" >&2
    echo "  3) Skip and continue (terraform validate will fail)" >&2
    echo "  4) Abort test" >&2
    echo "" >&2
    read -p "Select option [1-4] (default: 1): " choice >&2
    
    choice=${choice:-1}
    
    case $choice in
        1) add_dummy_provider_configs "$yaml_file" ;;
        2) open_editor_and_wait "$yaml_file" ;;
        3) log_warning "Skipping provider_config - validation errors expected" >&2 ;;
        4) log_info "Test aborted by user" >&2; exit 0 ;;
        *) log_error "Invalid choice" >&2; exit 1 ;;
    esac
}

add_dummy_provider_configs() {
    local yaml_file=$1
    
    log_info "Adding dummy provider_config for each connection..." >&2
    
    # Use Python to add provider_config to connections based on type
    $PYTHON_CMD - "$yaml_file" <<'PYPEOF'
import sys
import yaml

yaml_path = sys.argv[1]
with open(yaml_path) as f:
    data = yaml.safe_load(f)

# Add provider_config to connections if missing
if 'globals' in data and 'connections' in data['globals']:
    connections = data['globals']['connections']
    if isinstance(connections, list):
        for conn in connections:
            if 'provider_config' not in conn:
                conn_type = conn.get('type', 'unknown').lower()
                
                # Add dummy config based on type
                if 'databricks' in conn_type:
                    conn['provider_config'] = {
                        'host': 'dummy-workspace.cloud.databricks.com',
                        'http_path': '/sql/1.0/warehouses/dummy123',
                        'catalog': 'main'
                    }
                elif 'snowflake' in conn_type:
                    conn['provider_config'] = {
                        'account': 'dummy_account',
                        'database': 'dummy_database',
                        'warehouse': 'dummy_warehouse',
                        'role': 'dummy_role'
                    }
                elif 'bigquery' in conn_type:
                    conn['provider_config'] = {
                        'project_id': 'dummy-project-id',
                        'dataset': 'dummy_dataset',
                        'location': 'US'
                    }
                elif 'redshift' in conn_type:
                    conn['provider_config'] = {
                        'host': 'dummy-cluster.region.redshift.amazonaws.com',
                        'port': 5439,
                        'dbname': 'dummy_db'
                    }
                elif 'postgres' in conn_type:
                    conn['provider_config'] = {
                        'host': 'dummy-postgres.example.com',
                        'port': 5432,
                        'dbname': 'dummy_db'
                    }
                else:
                    # Generic placeholder
                    conn['provider_config'] = {
                        'host': 'dummy-host.example.com',
                        'note': f'Add real config for {conn_type}'
                    }

# Write back to file
with open(yaml_path, 'w') as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

print("Dummy provider configs added successfully")
PYPEOF
    
    if [ $? -eq 0 ]; then
        log_success "Dummy configs added - validation will work, apply requires real values" >&2
        log_warning "These are placeholders only. For real migration, add actual connection details." >&2
    else
        log_error "Failed to add dummy configs" >&2
        exit 1
    fi
}

open_editor_and_wait() {
    local yaml_file=$1
    
    log_info "Opening YAML in editor for manual configuration..." >&2
    echo "" >&2
    log_info "Add provider_config to each connection under globals.connections:" >&2
    echo "" >&2
    echo "Example for Databricks:" >&2
    echo "  - key: my_connection" >&2
    echo "    name: \"My Connection\"" >&2
    echo "    type: databricks" >&2
    echo "    provider_config:" >&2
    echo "      host: \"your-workspace.cloud.databricks.com\"" >&2
    echo "      http_path: \"/sql/1.0/warehouses/abc123\"" >&2
    echo "      catalog: \"main\"" >&2
    echo "" >&2
    log_info "Press Enter to open editor..." >&2
    read -r >&2
    
    # Detect editor
    EDITOR_CMD="${EDITOR:-${VISUAL:-nano}}"
    
    $EDITOR_CMD "$yaml_file"
    
    # Verify provider_config was added
    if grep -q "provider_config:" "$yaml_file"; then
        log_success "provider_config found in YAML" >&2
    else
        log_warning "No provider_config found - terraform validation may fail" >&2
        echo "" >&2
        read -p "Continue anyway? [y/N]: " continue_choice >&2
        if [[ ! "$continue_choice" =~ ^[Yy]$ ]]; then
            log_info "Test aborted" >&2
            exit 0
        fi
    fi
}

phase3_validate() {
    log_info "=== Phase 3: Terraform Validation ===" >&2
    
    cd "$TEST_DIR"
    
    # Check if YAML has connection provider configs (warning only now)
    if ! grep -q "provider_config:" dbt-cloud-config.yml; then
        log_warning "No provider_config found in YAML - validation may fail" >&2
    else
        log_success "provider_config found in YAML" >&2
    fi
    
    log_info "Initializing Terraform..." >&2
    terraform init -backend=false >&2
    
    log_info "Validating Terraform configuration..." >&2
    if terraform validate >&2; then
        log_success "Terraform validation passed" >&2
    else
        log_error "Terraform validation failed" >&2
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
**Importer Version:** $(cd "$PROJECT_ROOT" && $PYTHON_CMD -m importer --version)
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
    log_info "Starting End-to-End Test" >&2
    log_info "Apply mode: $APPLY_FLAG" >&2
    echo "" >&2
    
    check_prerequisites
    clean_workspace
    
    EXPORT_FILE=$(phase1_fetch)
    YAML_FILE=$(phase2_normalize "$EXPORT_FILE")
    
    # Interactive provider config step
    configure_provider_configs
    
    phase3_validate
    phase4_plan
    phase5_apply
    create_test_summary
    
    echo "" >&2
    log_success "=== End-to-End Test Complete ===" >&2
    log_info "Review results in: $TEST_DIR/test_summary.md" >&2
    
    if [ "$APPLY_FLAG" = false ]; then
        log_info "To run with apply: ./run_e2e_test.sh --apply" >&2
    fi
}

main

