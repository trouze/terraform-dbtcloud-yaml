# PRD: Web UI - Part 5: Target & Deploy Steps

## Introduction

The Target and Deploy steps of the dbt Cloud Importer Web UI. Target configures destination credentials and connection providers. Deploy executes Terraform operations (init, plan, apply) to create resources in the target account. When migrating to an account with existing infrastructure, this step also handles **importing matched resources into Terraform state** before running plan/apply, preventing "resource already exists" errors.

This is **Part 5 of 5** in the Web UI PRD series.  
**Depends on:** Part 1 (Core Shell), Part 2 (Fetch), Part 3 (Explore), Part 4 (Map)

## Goals

- Configure target dbt Cloud account credentials
- Configure connection provider details (Snowflake, Databricks, etc.)
- Support both "generate files only" and direct Terraform execution
- Provide real-time streaming output for Terraform operations
- Display deployment results and resource creation status
- **Import existing target resources into Terraform state using mapping file**
- **Execute `terraform import` for matched resources before plan/apply**
- **Display import results and handle import failures gracefully**

## User Stories

### US-037: Configure Target Credentials
**Description:** As a user, I want to enter target account credentials so that Terraform can deploy to the destination.

**Acceptance Criteria:**
- [ ] Form fields for: Target Host URL, Target Account ID, Target API Token
- [ ] Clear visual separation from source credentials (different section/color)
- [ ] Token type selector: Service Token / User Token (PAT)
- [ ] API Token field is password-masked with show/hide toggle
- [ ] "Load from .env" / "Save to .env" buttons
- [ ] Reads/writes `DBT_TARGET_*` environment variables
- [ ] Validation with inline error messages
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-038: Test Target Connection
**Description:** As a user, I want to test my target credentials so that I can verify they work before deploying.

**Acceptance Criteria:**
- [ ] "Test Connection" button makes API call to target
- [ ] Shows spinner during test
- [ ] Success: shows account name and confirms write permissions
- [ ] Failure: shows specific error (auth failed, network error, etc.)
- [ ] Does not create any resources (read-only test)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-039: Configure Connection Providers
**Description:** As a user, I want to configure connection provider details so that connections can be created in the target.

**Acceptance Criteria:**
- [ ] Section shows list of connections from the YAML
- [ ] Each connection type has appropriate config fields:
  - Snowflake: account, database, warehouse, role
  - Databricks: host, http_path, catalog
  - BigQuery: project, dataset
  - Redshift: host, port, database
- [ ] Sensitive fields (passwords, keys) are masked
- [ ] "Save to .env" writes as `DBT_CONNECTION_{NAME}_{FIELD}` variables
- [ ] Collapsible sections per connection
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-040: Configure Terraform Backend
**Description:** As a user, I want to configure where Terraform state is stored so that I can use my preferred backend.

**Acceptance Criteria:**
- [ ] Backend selector: Local / S3 / GCS / Azure Blob
- [ ] Local: just needs state file path
- [ ] Cloud backends: appropriate fields (bucket, key, region, etc.)
- [ ] "Use existing backend.tf" option to skip configuration
- [ ] Settings written to backend.tf or passed as CLI args
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-041: View Deployment Summary
**Description:** As a user, I want to see a summary of what will be deployed so that I can confirm before proceeding.

**Acceptance Criteria:**
- [ ] Deployment summary panel showing:
  - Target account info
  - Resource counts to be created
  - Connections requiring provider config
  - Any warnings (missing configs, lookups unresolved)
- [ ] "Generate Files Only" button for manual deployment
- [ ] "Run Terraform" button for direct execution
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-042: Generate Terraform Files
**Description:** As a user, I want to generate all Terraform files without executing so that I can run Terraform manually.

**Acceptance Criteria:**
- [ ] "Generate Files" button creates:
  - main.tf (module call)
  - variables.tf (variable definitions)  
  - terraform.tfvars (variable values from .env)
  - backend.tf (if configured)
- [ ] Output directory configurable
- [ ] Success shows file paths
- [ ] "Open in Finder/Explorer" button (if supported)
- [ ] Instructions for manual terraform commands
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-043: Run Terraform Init
**Description:** As a user, I want to run `terraform init` so that providers and modules are downloaded.

**Acceptance Criteria:**
- [ ] "Initialize" button runs `terraform init`
- [ ] Terminal panel shows real-time output
- [ ] Handles provider download progress
- [ ] Success: shows "Terraform initialized" message
- [ ] Failure: shows error with remediation hints
- [ ] Init state tracked (don't re-init unnecessarily)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-044: Run Terraform Plan
**Description:** As a user, I want to run `terraform plan` so that I can preview what will be created.

**Acceptance Criteria:**
- [ ] "Plan" button runs `terraform plan`
- [ ] Real-time streaming output in terminal panel
- [ ] Plan summary displayed: X to add, Y to change, Z to destroy
- [ ] Resource list showing planned additions
- [ ] Expandable details per resource
- [ ] "Save Plan" button to save plan file
- [ ] Plan can be cancelled mid-execution
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-045: Run Terraform Apply
**Description:** As a user, I want to run `terraform apply` so that I can deploy resources to the target account.

**Acceptance Criteria:**
- [ ] "Apply" button only enabled after successful plan
- [ ] Confirmation dialog showing resource count
- [ ] Real-time streaming output during apply
- [ ] Progress indicator showing resources created (X of Y)
- [ ] Individual resource status (creating, created, failed)
- [ ] On success: summary of created resources with IDs
- [ ] On failure: error details with affected resource
- [ ] Apply can be cancelled (will attempt graceful stop)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-046: View Apply Results
**Description:** As a user, I want to see detailed results after apply so that I can verify deployment success.

**Acceptance Criteria:**
- [ ] Results panel shows:
  - Total resources created
  - List of resources with their new dbt Cloud IDs
  - Any resources that failed
  - Total execution time
- [ ] "View in dbt Cloud" links for created resources (where applicable)
- [ ] "Export Results" button saves results to JSON
- [ ] "Start New Migration" button to reset workflow
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-047: Handle Terraform Errors
**Description:** As a user, I want clear error handling during Terraform operations so that I can resolve issues.

**Acceptance Criteria:**
- [ ] Parse Terraform error output for user-friendly messages
- [ ] Common errors have specific guidance:
  - Auth errors: "Check target credentials"
  - Resource conflicts: "Resource already exists"
  - Provider errors: "Check connection config"
- [ ] Full error output available in expandable section
- [ ] "Retry" button to attempt operation again
- [ ] "Skip and Continue" for non-critical failures (where safe)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-048: Support Terraform Destroy
**Description:** As a user, I want to destroy created resources so that I can clean up test deployments.

**Acceptance Criteria:**
- [ ] "Destroy" button in results/settings area
- [ ] Strong confirmation dialog (type resource count to confirm)
- [ ] Real-time output during destroy
- [ ] Summary of destroyed resources
- [ ] Warning that this is irreversible
- [ ] Only available after successful apply
- [ ] Typecheck passes
- [ ] Verify in browser

---

## Resource Import Sub-Flow

When migrating to an account with existing infrastructure, resources defined in the mapping file must be imported into Terraform state before running plan/apply. This ensures Terraform knows about existing resources and won't try to create duplicates.

### US-049: View Import Summary
**Description:** As a user, I want to see a summary of resources that will be imported so that I understand what Terraform will take over.

**Acceptance Criteria:**
- [ ] Import summary panel shows resources from mapping file
- [ ] Grouped by resource type with counts
- [ ] Shows source name → target ID mapping for each resource
- [ ] Warning if mapping file is missing or invalid
- [ ] Warning if mapping file has changed since last validation
- [ ] "Skip Import" option (with confirmation) if user wants to create all new
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-050: Generate Import Blocks
**Description:** As a user, I want to generate Terraform import blocks so that I can use Terraform 1.5+ native import.

**Acceptance Criteria:**
- [ ] "Generate Import Blocks" button creates `imports.tf` file
- [ ] Uses Terraform 1.5+ `import {}` block syntax
- [ ] One import block per mapping entry
- [ ] Import block includes resource address and target ID
- [ ] Example output:
  ```hcl
  import {
    to = module.dbt_cloud.dbtcloud_project.analytics_project
    id = "98765"
  }
  ```
- [ ] File saved alongside other generated Terraform files
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-051: Run Terraform Import
**Description:** As a user, I want to run the import process so that existing resources are added to Terraform state.

**Acceptance Criteria:**
- [ ] "Import Resources" button triggers import process
- [ ] Supports two modes:
  - Modern: `terraform plan` with import blocks (Terraform 1.5+)
  - Legacy: Sequential `terraform import` commands
- [ ] Progress indicator showing X of Y resources imported
- [ ] Real-time streaming output in terminal panel
- [ ] Each resource shows status: pending, importing, imported, failed
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-052: View Import Progress
**Description:** As a user, I want to see real-time progress during import so that I know which resources are being processed.

**Acceptance Criteria:**
- [ ] Progress table shows each resource being imported
- [ ] Columns: Resource Type, Source Name, Target ID, Status, Duration
- [ ] Status updates in real-time: Pending → Importing → Success/Failed
- [ ] Failed imports show error message inline
- [ ] Running total: "Imported 15 of 23 resources"
- [ ] Estimated time remaining (based on average per resource)
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-053: Handle Import Errors
**Description:** As a user, I want clear error handling when imports fail so that I can resolve issues and continue.

**Acceptance Criteria:**
- [ ] Failed imports don't stop the entire process (continue with others)
- [ ] Failed imports collected and displayed at end
- [ ] Common errors have specific guidance:
  - "Resource not found": Target ID may be incorrect
  - "Resource already in state": Already imported, can skip
  - "Permission denied": Check API token permissions
- [ ] "Retry Failed" button to retry just the failed imports
- [ ] "Skip Failed" button to proceed without failed resources
- [ ] Option to edit mapping file and re-validate
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-054: Import Before Plan Workflow
**Description:** As a user, I want import to run automatically before plan so that I get an accurate plan output.

**Acceptance Criteria:**
- [ ] When mapping file exists, "Plan" button shows "Import & Plan"
- [ ] Import runs automatically before plan if not already done
- [ ] Import results displayed before plan starts
- [ ] If import has failures, prompt to continue or abort
- [ ] Plan output shows imported resources as "no changes" (in sync)
- [ ] Plan output shows new resources as "will be created"
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-055: View Import Results
**Description:** As a user, I want to see detailed results after import so that I can verify which resources were successfully imported.

**Acceptance Criteria:**
- [ ] Import results panel shows:
  - Total resources attempted
  - Successfully imported count
  - Failed imports count
  - List of each resource with status
- [ ] Successfully imported resources show Terraform resource address
- [ ] Failed resources show error details
- [ ] "Export Results" button saves import log to file
- [ ] Results persist in session for reference during plan/apply
- [ ] Typecheck passes
- [ ] Verify in browser

---

### US-056: Verify Imported State
**Description:** As a user, I want to verify that imported resources match the expected configuration so that I catch drift before apply.

**Acceptance Criteria:**
- [ ] After import, option to run `terraform plan` in verify mode
- [ ] Plan shows any differences between state and configuration
- [ ] Differences highlighted (e.g., "job name will change from X to Y")
- [ ] Option to accept drift (update config) or fix drift (update resource)
- [ ] Warning if significant drift detected
- [ ] Typecheck passes
- [ ] Verify in browser

## Functional Requirements

- **FR-1:** Target credentials must be stored separately from source credentials
- **FR-2:** Connection provider configs must be dynamically generated based on YAML content
- **FR-3:** "Generate Files" must create valid, runnable Terraform configuration
- **FR-4:** Terraform commands must stream output in real-time
- **FR-5:** Apply must only be available after successful plan
- **FR-6:** Errors must be parsed for user-friendly messaging
- **FR-7:** Destroy must require explicit confirmation
- **FR-8:** When mapping file exists, import blocks must be generated for matched resources
- **FR-9:** Import must run before plan when matched resources exist
- **FR-10:** Import progress must be displayed per-resource with real-time status updates
- **FR-11:** Import failures must not block other imports (continue and report)
- **FR-12:** Plan must show imported resources as "no changes" when state matches config
- **FR-13:** Import results must be persisted in session for reference

## Non-Goals (Out of Scope)

- Terraform state management UI (view/edit state)
- Terraform workspace management
- Rolling back applies (use terraform manually)
- Partial applies (applying subset of resources)
- Terraform Cloud/Enterprise integration
- Automatic drift remediation (show drift, but user decides action)
- Import of resources not in mapping file (only explicit mappings)

## Technical Considerations

### Terraform Process Execution
```python
import asyncio
import subprocess

async def run_terraform(command: list[str], cwd: str, on_output: Callable[[str], None]):
    """Run terraform command with streaming output."""
    process = await asyncio.create_subprocess_exec(
        'terraform', *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    
    async for line in process.stdout:
        on_output(line.decode())
    
    await process.wait()
    return process.returncode
```

### Import Block Generation
```python
def generate_import_blocks(mapping_data: dict, resource_address_map: dict) -> str:
    """Generate Terraform 1.5+ import blocks from mapping file.
    
    Args:
        mapping_data: Parsed target_resource_mapping.yml content
        resource_address_map: Maps source_key to Terraform resource address
    
    Returns:
        Contents for imports.tf file
    """
    blocks = []
    for mapping in mapping_data.get('mappings', []):
        source_key = mapping['source_key']
        target_id = mapping['target_id']
        resource_type = mapping['resource_type']
        
        # Get the Terraform resource address for this source entity
        tf_address = resource_address_map.get(source_key)
        if not tf_address:
            continue
            
        # Generate import block
        block = f'''import {{
  to = {tf_address}
  id = "{target_id}"
}}
'''
        blocks.append(block)
    
    return '\n'.join(blocks)

# Example resource address mapping (generated from YAML)
RESOURCE_ADDRESS_MAP = {
    'project__analytics_project': 'module.dbt_cloud.dbtcloud_project.analytics_project',
    'environment__analytics_project__production': 'module.dbt_cloud.dbtcloud_environment.analytics_project_production',
    'global_connection__snowflake_prod': 'module.dbt_cloud.dbtcloud_global_connection.snowflake_prod',
}
```

### Legacy Import Command Generation
```python
def generate_import_commands(mapping_data: dict, resource_address_map: dict) -> list[tuple[str, str]]:
    """Generate terraform import commands for pre-1.5 Terraform.
    
    Returns:
        List of (resource_address, import_id) tuples
    """
    commands = []
    for mapping in mapping_data.get('mappings', []):
        source_key = mapping['source_key']
        target_id = mapping['target_id']
        
        tf_address = resource_address_map.get(source_key)
        if tf_address:
            commands.append((tf_address, str(target_id)))
    
    return commands

async def run_legacy_imports(
    commands: list[tuple[str, str]], 
    cwd: str,
    on_progress: Callable[[str, str, str], None]  # (address, id, status)
):
    """Run sequential terraform import commands."""
    results = []
    for address, import_id in commands:
        on_progress(address, import_id, 'importing')
        
        returncode = await run_terraform(
            ['import', address, import_id],
            cwd=cwd,
            on_output=lambda x: None  # Capture but don't stream
        )
        
        status = 'success' if returncode == 0 else 'failed'
        on_progress(address, import_id, status)
        results.append({'address': address, 'id': import_id, 'status': status})
    
    return results
```

### Import with Plan (Terraform 1.5+)
```python
async def run_import_plan(cwd: str, on_output: Callable[[str], None]):
    """Run terraform plan which will process import blocks."""
    # Terraform 1.5+ processes import {} blocks during plan
    return await run_terraform(
        ['plan', '-generate-config-out=generated.tf'],
        cwd=cwd,
        on_output=on_output
    )
```

### Provider Configuration Generation
```python
def generate_provider_config(target_creds: dict) -> str:
    """Generate provider.tf content."""
    return f'''
terraform {{
  required_providers {{
    dbtcloud = {{
      source  = "dbt-labs/dbtcloud"
      version = "~> 0.3"
    }}
  }}
}}

provider "dbtcloud" {{
  account_id = var.dbt_target_account_id
  token      = var.dbt_target_api_token
  host_url   = var.dbt_target_host_url
}}
'''
```

### Connection Config Mapping
```python
CONNECTION_FIELDS = {
    'snowflake': ['account', 'database', 'warehouse', 'role', 'user', 'password'],
    'databricks': ['host', 'http_path', 'catalog', 'token'],
    'bigquery': ['project', 'dataset', 'keyfile_json'],
    'redshift': ['host', 'port', 'database', 'user', 'password'],
    'postgres': ['host', 'port', 'database', 'user', 'password'],
}
```

### File Structure Addition
```
importer/web/
├── pages/
│   ├── target.py             # Target credentials page
│   └── deploy.py             # Deploy/Terraform page
└── components/
    ├── credential_form.py    # (reused from fetch)
    ├── connection_config.py  # Connection provider forms
    ├── terminal_output.py    # (reused, enhanced for TF)
    ├── terraform_results.py  # Results display component
    ├── import_generator.py   # Import block/command generation
    └── import_progress.py    # Import progress UI component
```

### State for Deploy Step
```python
@dataclass
class ImportResult:
    resource_address: str
    target_id: str
    status: str  # 'pending', 'importing', 'success', 'failed'
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None

@dataclass
class DeployState:
    target_credentials: dict = field(default_factory=dict)
    connection_configs: dict[str, dict] = field(default_factory=dict)
    terraform_initialized: bool = False
    last_plan_success: bool = False
    last_plan_output: str = ''
    apply_results: Optional[dict] = None
    
    # Import state
    import_results: list[ImportResult] = field(default_factory=list)
    import_completed: bool = False
    import_mode: str = 'modern'  # 'modern' (TF 1.5+) or 'legacy'
```

### Terraform Version Detection
```python
async def detect_terraform_version(cwd: str) -> tuple[int, int, int]:
    """Detect installed Terraform version."""
    process = await asyncio.create_subprocess_exec(
        'terraform', 'version', '-json',
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    data = json.loads(stdout)
    version = data['terraform_version']
    major, minor, patch = map(int, version.split('.'))
    return (major, minor, patch)

def supports_import_blocks(version: tuple[int, int, int]) -> bool:
    """Check if Terraform version supports import {} blocks."""
    return version >= (1, 5, 0)
```

## Success Metrics

- Terraform output streams with less than 1 second latency
- Plan of 100 resources displays within 10 seconds
- Apply progress updates per-resource
- Error messages are actionable
- Import of 50 resources completes in under 2 minutes (legacy mode)
- Import block generation completes in under 1 second
- Import progress updates within 500ms of status change
- Zero "resource already exists" errors when mapping file is properly configured

## Open Questions

1. Should we support Terraform Cloud for remote execution?
2. Should we detect if terraform is installed and show install instructions?
3. Should we support multiple target environments (dev/staging/prod)?
4. Should apply results link directly to resources in dbt Cloud UI?
5. Should we auto-detect Terraform version and choose import mode, or let user select?
6. How should we handle partial imports (some succeed, some fail) before plan?
7. Should we support importing resources that aren't in the mapping file (manual import)?
8. Should we show a diff between imported state and expected config before apply?
9. How should we handle resources that exist in target but are NOT in the mapping file?