# dbt Cloud Importer CLI

Prototype CLI for Phase 1 of the importer plan. It authenticates against the dbt Cloud APIs, captures an internal account snapshot, and emits a JSON export that will later feed YAML normalization (Phase 2).

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

## Usage

Run the fetch command to capture the current account state:

```bash
python -m importer fetch --output dev_support/samples/account.json --reports-dir dev_support/samples
```

Flags:

| Flag | Description |
|------|-------------|
| `--output PATH` | Optional path to write the JSON export (defaults to stdout). |
| `--compact` | Emit compact JSON instead of pretty-printed output. |
| `--reports-dir PATH` | Directory to write summary/report markdown files (defaults to same directory as output). |
| `--auto-timestamp / --no-auto-timestamp` | Automatically add timestamp to output filename (default: enabled). |

Environment variable knobs:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DBT_REPORT_LINE_ITEM_START` | `1001` | Starting line-item number for the report JSON export (`report_items`). |

After completion, the CLI prints a summary table with counts for projects, connections, and repositories. Additional metrics will be added as new globals are fetched.

### Output Files

When `--auto-timestamp` is enabled (default), the importer generates timestamped files with sequential run IDs:

- **JSON Export**: `account_{ACCOUNT_ID}_run_{RUN}__json__{TIMESTAMP}.json` - Raw JSON account data
- **Summary**: `account_{ACCOUNT_ID}_run_{RUN}__summary__{TIMESTAMP}.md` - High-level counts and per-project breakdown
- **Report**: `account_{ACCOUNT_ID}_run_{RUN}__report__{TIMESTAMP}.md` - Detailed tree showing IDs, names, and nested structure
- **Report Line Items**: `account_{ACCOUNT_ID}_run_{RUN}__report_items__{TIMESTAMP}.json` - Machine-readable list of every element with mapping IDs and inclusion flags
- **Logs**: `account_{ACCOUNT_ID}_run_{RUN}__logs__{TIMESTAMP}.log` - Execution logs

Where:
- `{ACCOUNT_ID}` is the dbt Cloud account ID
- `{RUN}` is a zero-padded 3-digit sequential run number (001, 002, 003...)
- `{TIMESTAMP}` is in the format `YYYYMMDD_HHMMSS` (UTC)

All files from the same run share the same run ID and timestamp. Run IDs are tracked in `importer_runs.json` in the output directory, which maintains a sequential counter per account.

If `python -m importer fetch` reports missing env vars, ensure the `.env` file is readable within your shell environment (the repo ships with `.env` in `.gitignore`, so you need to create it locally).

## Implementation Notes

- API access is performed via `httpx` with separate clients for v2 (`Token`) and v3 (`Bearer`) authentication styles. See `importer/client.py`.
- `importer/fetcher.py` currently gathers: connections (v3), repositories (v2), projects (v2), environments (v2), jobs (v2), and project environment variables (v3). More globals (service tokens, groups, PrivateLink, semantic layer) will be layered in next iterations.
- The internal data model lives in `importer/models.py` (Pydantic v2). All objects expose deterministic `key` values so Phase 2 can map them directly to the new YAML schema.
- Each run enriches `_metadata` with hashing context for traceability:
  - `run_label` (`run_034`), `source_url_hash`, human-readable `source_url_slug`, `account_source_hash`, and `unique_run_identifier`.
  - These hashes use the first 12 hex chars of SHA-256 so they remain deterministic but compact.
- Every element (account, globals, projects, envs, jobs, env vars, etc.) now includes an `element_mapping_id = sha256("{TYPE}:{name_or_id}")[:12]` plus an `include_in_conversion` flag. See the line-item JSON for one-row-per-resource output starting at line number `DBT_REPORT_LINE_ITEM_START` (default 1001).
- Version information is sourced from `importer/VERSION` and logged by the CLI; bump this file whenever we cut a new importer release.
- HTTP requests automatically retry on transient 5xx / 429 responses using exponential backoff and `Retry-After` headers, so long-running inventory jobs can complete without manual babysitting.

## Next Steps

- Extend the globals map with service tokens, groups, notifications, PrivateLink endpoints, semantic layer configs per the Phase 1 inventory.
- Begin Phase 2: YAML normalization from the account JSON export into v2 schema format.

