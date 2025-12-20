#!/bin/bash
# End-to-End Test Execution Script
# 
# This script automates the end-to-end testing workflow for Phase 5.
# It executes fetch, normalize, and Terraform validation steps.
#
# Usage:
#   ./run_e2e_test.sh [OPTIONS]
#
# Options:
#   --apply           Run terraform apply (default: plan only)
#   --dummy-configs   Automatically add dummy provider configs (non-interactive)
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
DUMMY_CONFIGS_FLAG=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --apply)
      APPLY_FLAG=true
      shift
      ;;
    --dummy-configs)
      DUMMY_CONFIGS_FLAG=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--apply] [--dummy-configs]"
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
    if [ -z "$DBT_SOURCE_ACCOUNT_ID" ] || [ -z "$DBT_SOURCE_API_TOKEN" ]; then
        log_error "DBT_SOURCE_ACCOUNT_ID and DBT_SOURCE_API_TOKEN must be set in .env"
        exit 1
    fi
    
    if [ -z "$DBT_TARGET_ACCOUNT_ID" ] || [ -z "$DBT_TARGET_API_TOKEN" ]; then
        log_error "DBT_TARGET_ACCOUNT_ID and DBT_TARGET_API_TOKEN must be set in .env"
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
    ACCOUNT_ID="${DBT_SOURCE_ACCOUNT_ID:-unknown}"
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

inject_provider_configs_from_env() {
    local yaml_file=$1
    
    log_info "Checking for connection configs in .env files..." >&2
    
    # Try both project root .env and test .env
    local env_files=("$PROJECT_ROOT/.env" "$TEST_DIR/.env")
    local found_configs=false
    
    for env_file in "${env_files[@]}"; do
        if [ -f "$env_file" ]; then
            # Check if any DBT_CONNECTION_ variables exist in the file
            if grep -q "^DBT_CONNECTION_" "$env_file" 2>/dev/null; then
                found_configs=true
                log_info "Found connection configs in $env_file" >&2
                break
            fi
        fi
    done
    
    if [ "$found_configs" = false ]; then
        log_info "No connection configs found in .env files" >&2
        return 1
    fi
    
    # Use Python to inject configs from environment variables
    $PYTHON_CMD - "$yaml_file" <<'PYPEOF' >&2
import sys
import os
import yaml
from pathlib import Path

yaml_path = Path(sys.argv[1])

# Load YAML
with open(yaml_path) as f:
    data = yaml.safe_load(f)

if 'globals' not in data or 'connections' not in data['globals']:
    print("No connections found in YAML")
    sys.exit(0)

connections = data['globals']['connections']
if not isinstance(connections, list):
    print("Connections is not a list")
    sys.exit(0)

# Load .env files to get environment variables
env_files = [
    Path(sys.argv[1]).resolve().parents[2] / '.env',  # Project root
    Path(sys.argv[1]).parent / '.env',  # Test dir
]

env_vars = {}
for env_file in env_files:
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value

# Inject provider_config from environment variables
configs_added = 0
for conn in connections:
    if 'provider_config' in conn:
        continue  # Skip if already has config
    
    conn_key = conn.get('key', '')
    prefix = f"DBT_CONNECTION_{conn_key.upper()}_"
    
    # Find all env vars for this connection
    conn_env_vars = {k: v for k, v in env_vars.items() if k.startswith(prefix)}
    
    if conn_env_vars:
        # Build provider_config from env vars
        provider_config = {}
        for env_key, env_value in conn_env_vars.items():
            # Remove prefix and convert to lowercase
            field_name = env_key[len(prefix):].lower()
            
            # Parse value (handle booleans, numbers, quoted strings)
            value = env_value.strip().strip('"').strip("'")
            if value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            elif value.isdigit():
                value = int(value)
            
            provider_config[field_name] = value
        
        if provider_config:
            conn['provider_config'] = provider_config
            configs_added += 1
            print(f"✓ Added provider_config for {conn.get('name', conn_key)} from .env")

if configs_added > 0:
    # Write back to YAML
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"\n✓ Injected {configs_added} provider_config(s) from .env into YAML")
else:
    print("No matching connection configs found in .env")
PYPEOF
    
    if [ $? -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

configure_provider_configs() {
    log_info "=== Provider Configuration Check ==="
    
    local yaml_file="$TEST_DIR/dbt-cloud-config.yml"
    
    # First, try to inject provider_config from .env files
    inject_provider_configs_from_env "$yaml_file"
    
    # Check if provider_config already exists (either from previous step or already in YAML)
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
    
    # If --dummy-configs flag is set, automatically add dummy configs
    if [ "$DUMMY_CONFIGS_FLAG" = true ]; then
        log_info "Auto-adding dummy configs (--dummy-configs flag set)" >&2
        add_dummy_provider_configs "$yaml_file"
        return 0
    fi
    
    echo "" >&2
    echo "Provider config is required for Terraform but not exported by the API." >&2
    echo "" >&2
    echo "Options:" >&2
    echo "  1) Add dummy/placeholder provider_config for testing (recommended for validation)" >&2
    echo "  2) Interactive configuration (Python menu-driven prompts)" >&2
    echo "  3) Skip and continue (terraform validate will fail)" >&2
    echo "  4) Abort test" >&2
    echo "" >&2
    read -p "Select option [1-4] (default: 1): " choice >&2
    
    choice=${choice:-1}
    
    case $choice in
        1) add_dummy_provider_configs "$yaml_file" ;;
        2) open_interactive_config "$yaml_file" ;;
        3) log_warning "Skipping provider_config - validation errors expected" >&2 ;;
        4) log_info "Test aborted by user" >&2; exit 0 ;;
        *) log_error "Invalid choice" >&2; exit 1 ;;
    esac
    
    # Offer to save connection credentials to .env
    if grep -q "provider_config:" "$yaml_file"; then
        echo "" >&2
        read -p "Save connection credentials to .env file for future use? (y/n) [n]: " save_choice >&2
        save_choice=${save_choice:-n}
        
        if [ "$save_choice" = "y" ] || [ "$save_choice" = "Y" ]; then
            save_connection_credentials_to_env "$yaml_file"
        fi
    fi
}

save_connection_credentials_to_env() {
    local yaml_file=$1
    local env_file="$PROJECT_ROOT/.env"
    
    log_info "Extracting connection credentials from YAML..." >&2
    
    # Use Python to extract provider_config from YAML and save to .env
    $PYTHON_CMD - "$yaml_file" "$env_file" <<'PYPEOF'
import sys
import yaml
import os
from pathlib import Path

yaml_path = sys.argv[1]
env_path = Path(sys.argv[2])

# Read YAML
with open(yaml_path) as f:
    data = yaml.safe_load(f)

# Extract connection configs
connection_configs = {}
if 'globals' in data and 'connections' in data['globals']:
    connections = data['globals']['connections']
    if isinstance(connections, list):
        for conn in connections:
            conn_key = conn.get('key', 'unknown')
            provider_config = conn.get('provider_config', {})
            if provider_config:
                connection_configs[conn_key] = provider_config

if not connection_configs:
    print("No provider_config found in connections")
    sys.exit(0)

# Read existing .env if it exists
existing_lines = []
if env_path.exists():
    with open(env_path, 'r') as f:
        existing_lines = f.readlines()

# Check for existing connection configs
existing_keys = set()
for line in existing_lines:
    if line.strip().startswith('DBT_CONNECTION_'):
        # Extract connection key from DBT_CONNECTION_CONN_KEY_FIELD format
        parts = line.split('_', 3)
        if len(parts) >= 4:
            conn_key = parts[2].lower()
            existing_keys.add(conn_key)

# Append connection configs to .env
with open(env_path, 'a') as f:
    f.write('\n# Connection Provider Configs (from E2E test)\n')
    
    for conn_key, config in sorted(connection_configs.items()):
        conn_prefix = f"DBT_CONNECTION_{conn_key.upper().replace('-', '_').replace('.', '_')}"
        f.write(f'\n# Connection: {conn_key}\n')
        
        for field, value in sorted(config.items()):
            env_key = f"{conn_prefix}_{field.upper()}"
            # Format value (quote if contains spaces)
            value_str = str(value)
            if ' ' in value_str or '=' in value_str:
                value_str = f'"{value_str}"'
            f.write(f"{env_key}={value_str}\n")

print(f"Connection credentials saved to {env_path}")
PYPEOF

    if [ $? -eq 0 ]; then
        log_success "Connection credentials saved to .env" >&2
    else
        log_error "Failed to save connection credentials" >&2
    fi
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

open_interactive_config() {
    local yaml_file=$1
    
    log_info "Launching interactive connection configuration..." >&2
    echo "" >&2
    
    # Use standalone script for proper terminal access (not stdin/heredoc)
    # This avoids "Input is not a terminal" warnings and CPR issues
    cd "$PROJECT_ROOT" || exit 1
    
    # Set PYTHONPATH to ensure importer module is found
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    # Call script with absolute path to avoid path resolution issues
    $PYTHON_CMD "$PROJECT_ROOT/test/configure_connections.py" "$yaml_file" 2>&1
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        log_error "Interactive configuration failed with exit code $exit_code" >&2
        exit 1
    fi
    
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
    
    # Map DBT_TARGET_* to Terraform provider variables
    # Normalize host URL: ensure single /api suffix for custom domains
    local base_host="${DBT_TARGET_HOST_URL:-https://cloud.getdbt.com}"
    base_host="${base_host%/}"
    local host_url="$base_host"
    if [[ "$base_host" != *"/api" ]]; then
        host_url="${base_host}/api"
    fi

    export TF_VAR_dbt_account_id="${DBT_TARGET_ACCOUNT_ID}"
    export TF_VAR_dbt_token="${DBT_TARGET_API_TOKEN}"
    export TF_VAR_dbt_pat="${DBT_TARGET_PAT:-}"
    export TF_VAR_dbt_host_url="$host_url"
    # Also set DBT_CLOUD_* for provider fallback
    export DBT_CLOUD_ACCOUNT_ID="${DBT_TARGET_ACCOUNT_ID}"
    export DBT_CLOUD_TOKEN="${DBT_TARGET_API_TOKEN}"
    export DBT_CLOUD_HOST_URL="$host_url"
    
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
    
    # Map DBT_TARGET_* to Terraform provider variables
    # Normalize host URL: ensure single /api suffix for custom domains
    local base_host="${DBT_TARGET_HOST_URL:-https://cloud.getdbt.com}"
    base_host="${base_host%/}"
    local host_url="$base_host"
    if [[ "$base_host" != *"/api" ]]; then
        host_url="${base_host}/api"
    fi
    
    export TF_VAR_dbt_account_id="${DBT_TARGET_ACCOUNT_ID}"
    export TF_VAR_dbt_token="${DBT_TARGET_API_TOKEN}"
    export TF_VAR_dbt_pat="${DBT_TARGET_PAT:-}"
    export TF_VAR_dbt_host_url="$host_url"
    
    # Also set DBT_CLOUD_* for provider fallback
    export DBT_CLOUD_ACCOUNT_ID="${DBT_TARGET_ACCOUNT_ID}"
    export DBT_CLOUD_TOKEN="${DBT_TARGET_API_TOKEN}"
    export DBT_CLOUD_HOST_URL="$host_url"
    
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
    
    # Map DBT_TARGET_* to Terraform provider variables
    # Normalize host URL: ensure single /api suffix for custom domains
    local base_host="${DBT_TARGET_HOST_URL:-https://cloud.getdbt.com}"
    base_host="${base_host%/}"
    local host_url="$base_host"
    if [[ "$base_host" != *"/api" ]]; then
        host_url="${base_host}/api"
    fi
    
    export TF_VAR_dbt_account_id="${DBT_TARGET_ACCOUNT_ID}"
    export TF_VAR_dbt_token="${DBT_TARGET_API_TOKEN}"
    export TF_VAR_dbt_pat="${DBT_TARGET_PAT:-}"
    export TF_VAR_dbt_host_url="$host_url"
    # Also set DBT_CLOUD_* for provider fallback
    export DBT_CLOUD_ACCOUNT_ID="${DBT_TARGET_ACCOUNT_ID}"
    export DBT_CLOUD_TOKEN="${DBT_TARGET_API_TOKEN}"
    export DBT_CLOUD_HOST_URL="$host_url"
    
    log_warning "About to apply Terraform changes to account $DBT_TARGET_ACCOUNT_ID"
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
**Importer Version:** $(cd "$PROJECT_ROOT" && $PYTHON_CMD -c "from importer import get_version; print(get_version())")
**Terraform Version:** $(terraform version -json | jq -r '.terraform_version')

## Test Account Details
- **Source Account ID:** $DBT_SOURCE_ACCOUNT_ID
- **Target Account ID:** $DBT_TARGET_ACCOUNT_ID

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
    log_info "Dummy configs: $DUMMY_CONFIGS_FLAG" >&2
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

