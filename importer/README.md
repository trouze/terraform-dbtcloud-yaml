# dbt Cloud Importer CLI

Prototype CLI for Phase 1 of the importer plan. It authenticates against the dbt Cloud APIs, captures an internal account snapshot, and emits JSON that will later feed YAML normalization (Phase 2).

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
python -m importer fetch --output dev_support/samples/account_snapshot.json
```

Flags:

| Flag | Description |
|------|-------------|
| `--output PATH` | Optional path to write the JSON snapshot (defaults to stdout). |
| `--compact` | Emit compact JSON instead of pretty-printed output. |

After completion, the CLI prints a summary table with counts for projects, connections, and repositories. Additional metrics will be added as new globals are fetched.

If `python -m importer fetch` reports missing env vars, ensure the `.env` file is readable within your shell environment (the repo ships with `.env` in `.gitignore`, so you need to create it locally).

## Implementation Notes

- API access is performed via `httpx` with separate clients for v2 (`Token`) and v3 (`Bearer`) authentication styles. See `importer/client.py`.
- `importer/fetcher.py` currently gathers: connections (v3), repositories (v2), projects (v2), environments (v2), jobs (v2), and project environment variables (v3). More globals (service tokens, groups, PrivateLink, semantic layer) will be layered in next iterations.
- The internal data model lives in `importer/models.py` (Pydantic v2). All objects expose deterministic `key` values so Phase 2 can map them directly to the new YAML schema.
- Version information is sourced from `importer/VERSION` and logged by the CLI; bump this file whenever we cut a new importer release.
- HTTP requests automatically retry on transient 5xx / 429 responses using exponential backoff and `Retry-After` headers, so long-running inventory jobs can complete without manual babysitting.

## Next Steps

- Add retries/backoff + rate limit handling to the client.
- Persist raw API payloads under `dev_support/samples/` for schema normalization tests.
- Extend the globals map with service tokens, groups, notifications, PrivateLink endpoints, and semantic layer configs per the Phase 1 inventory.

