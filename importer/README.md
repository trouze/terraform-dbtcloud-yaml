# dbt Cloud Importer CLI

Full-featured CLI for extracting dbt Cloud account configurations and normalizing them into Terraform-ready v2 YAML format. Supports Phases 1 (fetch) and 2 (normalize) of the importer workflow.

## Overview

The importer consists of two main commands:
1. **`fetch`**: Extracts account data via dbt Cloud API → JSON export + reports
2. **`normalize`**: Converts JSON export → v2 YAML + manifests (Terraform-ready)

## Setup

1. **Create a virtualenv** (or reuse the repo-level `.venv`):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r importer/requirements.txt
   ```
2. **Populate `.env`** at the repo root:
   ```bash
   DBT_SOURCE_HOST=https://cloud.getdbt.com
   DBT_SOURCE_ACCOUNT_ID=12345
   DBT_SOURCE_API_TOKEN=your_pat_here
   ```
   - The PAT must have sufficient scopes to read projects, jobs, environments, connections, service tokens, and groups. Use an Account Admin/Owner token for now.
   - Optional tuning knobs:
     | Variable | Default | Description |
     |----------|---------|-------------|
     | `DBT_SOURCE_API_TIMEOUT` | `30` | Client timeout in seconds |
     | `DBT_SOURCE_API_MAX_RETRIES` | `5` | Max attempts per request on 5xx/429 responses |
     | `DBT_SOURCE_API_BACKOFF_FACTOR` | `1.5` | Multiplier for exponential backoff (sleep = factor * 2^(attempt-1)) |
     | `DBT_SOURCE_API_RETRY_AFTER` | `true` | Honor `Retry-After` header on 429 responses |
     | `DBT_SOURCE_SSL_VERIFY` | `true` | Disable only for debugging self-signed hosts |
     | `DBT_REPORT_LINE_ITEM_START` | `1001` | Starting `line_item_number` for `report_items` export |

---

## Phase 1: Fetch Command

Extract account data from dbt Cloud API.

### Usage

```bash
python -m importer fetch --output dev_support/samples/account.json --reports-dir dev_support/samples
```

### Flags

| Flag | Description |
|------|-------------|
| `--output PATH` | Optional path to write the JSON export (defaults to stdout). |
| `--compact` | Emit compact JSON instead of pretty-printed output. |
| `--reports-dir PATH` | Directory to write summary/report markdown files (defaults to same directory as output). |
| `--auto-timestamp / --no-auto-timestamp` | Automatically add timestamp to output filename (default: enabled). |

### Output Files

When `--auto-timestamp` is enabled (default), the importer generates timestamped files with sequential run IDs:

- **JSON Export**: `account_{ACCOUNT_ID}_run_{RUN}__json__{TIMESTAMP}.json` - Full account data with enriched metadata
- **Summary**: `account_{ACCOUNT_ID}_run_{RUN}__summary__{TIMESTAMP}.md` - High-level counts and per-project breakdown
- **Report**: `account_{ACCOUNT_ID}_run_{RUN}__report__{TIMESTAMP}.md` - Detailed tree showing IDs, names, and nested structure
- **Report Items**: `account_{ACCOUNT_ID}_run_{RUN}__report_items__{TIMESTAMP}.json` - Machine-readable list with `element_mapping_id` and `include_in_conversion` flags
- **Logs**: `account_{ACCOUNT_ID}_run_{RUN}__logs__{TIMESTAMP}.log` - Execution logs (DEBUG level)

Where:
- `{ACCOUNT_ID}` is the dbt Cloud account ID
- `{RUN}` is a zero-padded 3-digit sequential run number (001, 002, 003...)
- `{TIMESTAMP}` is in the format `YYYYMMDD_HHMMSS` (UTC)

All files from the same run share the same run ID and timestamp. Run IDs are tracked in `importer_runs.json` in the output directory.

---

## Phase 2: Normalize Command

Convert JSON export into Terraform-ready v2 YAML format.

### Usage

```bash
python -m importer normalize dev_support/samples/account_86165_run_001__json__20251121_120000.json
```

### Flags

| Flag | Description |
|------|-------------|
| `input_json` | **Required**: Path to JSON export from `fetch` command. |
| `--config PATH` / `-c` | Path to mapping configuration YAML (default: `importer_mapping.yml`). |
| `--output-dir PATH` / `-o` | Output directory for YAML and artifacts (overrides config value). |

### Configuration

Create an `importer_mapping.yml` file to control normalization behavior:

```yaml
version: 1

scope:
  mode: all_projects  # all_projects | specific_projects | account_level_only

resource_filters:
  connections:
    include: true
  environments:
    exclude_keys:
      - dev
      - local

normalization_options:
  strip_source_ids: true
  placeholder_strategy: lookup
  secret_handling: redact

output:
  yaml_file: dbt-config.yml
  output_directory: dev_support/samples/normalized/
  generate_manifests:
    lookups: true
    exclusions: true
    diff_json: true
```

See [Importer Mapping Reference](../docs/importer_mapping_reference.md) for complete configuration documentation.

### Output Files

Normalization generates timestamped artifacts with sequential normalization run IDs:

- **YAML**: `account_{ID}_norm_{NORM_RUN}__yaml__{TIMESTAMP}.yml` - Terraform-ready v2 YAML configuration
- **Lookups Manifest**: `account_{ID}_norm_{NORM_RUN}__lookups__{TIMESTAMP}.json` - List of `LOOKUP:` placeholders needing manual resolution
- **Exclusions Report**: `account_{ID}_norm_{NORM_RUN}__exclusions__{TIMESTAMP}.md` - Markdown report of excluded resources with reasons
- **Diff JSON**: `account_{ID}_norm_{NORM_RUN}__diff__{TIMESTAMP}.json` - Diff-friendly JSON for regression testing
- **Logs**: `account_{ID}_norm_{NORM_RUN}__logs__{TIMESTAMP}.log` - Normalization decision logs (DEBUG level)

Where:
- `{ID}` is the account ID
- `{NORM_RUN}` is a zero-padded 3-digit sequential normalization run number (001, 002...)
- `{TIMESTAMP}` is in the format `YYYYMMDD_HHMMSS` (UTC)

Normalization run IDs are tracked separately from fetch run IDs in `normalization_runs.json`.

---

## Logging and Artifacts

### Logging Strategy

Both `fetch` and `normalize` commands use structured Python logging:
- **Console**: WARNING level and above (errors, warnings visible to user)
- **Log File**: DEBUG level (all decisions, API calls, transformations)
- **Format**: `YYYY-MM-DD HH:MM:SS - module - LEVEL - message`

### Log File Contents

**Fetch logs include**:
- API endpoint calls and response times
- Resource counts (projects, environments, jobs, etc.)
- Warnings about unexpected data structures
- Errors during API communication

**Normalize logs include**:
- Mapping config loading and validation
- Scope and filter decisions (why resources were included/excluded)
- Placeholder creations (LOOKUP: items)
- Name collision resolutions
- Secret redaction actions
- Artifact generation steps

### Artifact Naming Conventions

All artifacts follow a consistent naming pattern:

**Format**: `account_{ID}_{phase}_{RUN}__{type}__{TIMESTAMP}.{ext}`

- `{phase}`: `run` for fetch, `norm` for normalize
- `{RUN}`: Zero-padded 3-digit sequential ID
- `{type}`: `json`, `yaml`, `summary`, `report`, `lookups`, `exclusions`, `diff`, `logs`, `report_items`
- `{TIMESTAMP}`: `YYYYMMDD_HHMMSS` UTC

This ensures:
- Chronological sorting by timestamp
- Easy correlation of artifacts from the same run
- No filename conflicts across runs

### Run Tracking

**Fetch runs**: Tracked in `importer_runs.json`
```json
{
  "12345": [
    {
      "run_id": 1,
      "timestamp": "20251121_120000",
      "account_id": 12345,
      "started_at": "2025-11-21T12:00:00Z"
    }
  ]
}
```

**Normalization runs**: Tracked in `normalization_runs.json`
```json
{
  "12345": [
    {
      "norm_run_id": 1,
      "timestamp": "20251121_121500",
      "account_id": 12345,
      "source_fetch_run_id": 1,
      "started_at": "2025-11-21T12:15:00Z"
    }
  ]
}
```

---

## End-to-End Workflow

1. **Fetch source account data**:
   ```bash
   python -m importer fetch --output dev_support/samples/account.json
   ```
   
   Review generated reports (`summary` and `report` markdown files).

2. **Configure normalization**:
   Edit `importer_mapping.yml` to set scope, filters, and options.

3. **Normalize to v2 YAML**:
   ```bash
   python -m importer normalize dev_support/samples/account_86165_run_001__json__20251121_120000.json
   ```

4. **Review artifacts**:
   - Check `exclusions` report for unintended omissions
   - Review `lookups` manifest for placeholders needing manual resolution
   - Validate YAML structure

5. **Resolve LOOKUP placeholders** (if any):
   - Create missing resources in target account
   - Update YAML to reference by key, or
   - Let Terraform data sources auto-resolve by name

6. **Apply with Terraform**:
   ```bash
   cd path/to/terraform-workspace
   terraform init
   terraform plan -var-file=prod.tfvars
   terraform apply
   ```

---

## Implementation Notes

- API access is performed via `httpx` with separate clients for v2 (`Token`) and v3 (`Bearer`) authentication styles. See `importer/client.py`.
- `importer/fetcher.py` currently gathers: connections (v3), repositories (v2), projects (v2), environments (v2), jobs (v2), project environment variables (v3), service tokens (v3), groups (v3), notifications (v2), webhook subscriptions (v3), and PrivateLink endpoints (v3).
- The internal data model lives in `importer/models.py` (Pydantic v2). All objects expose deterministic `key` values and `element_mapping_id` for stable referencing.
- Version information is sourced from `importer/VERSION` and logged by the CLI; bump this file whenever we cut a new importer release.
- HTTP requests automatically retry on transient 5xx / 429 responses using exponential backoff and `Retry-After` headers.
- Markdown reports are generated by `importer/reporter.py` for human-readable summaries.
- Normalization logic lives in `importer/normalizer/` with core normalization (`core.py`), YAML writing (`writer.py`), and config handling (`__init__.py`).
- `element_mapping_id` is a stable, deterministic hash for each resource, used for consistent referencing across runs and for downstream tooling.
- The `report_items` JSON export provides a flat, machine-readable list of all fetched elements, including their `element_mapping_id` and an `include_in_conversion` flag.

---

## Next Steps

- Begin Phase 3: Terraform v2 module implementation
- Test end-to-end: fetch → normalize → apply
- Document migration helpers for v1 → v2 upgrades
