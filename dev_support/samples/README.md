# Account JSON Samples

This directory contains sanitized JSON exports captured by the importer from real dbt Cloud accounts. These samples feed Phase 2 normalization + YAML generation and serve as test fixtures.

## Files

The importer generates timestamped files for each run:

- **`account_{ID}_json__{timestamp}.json`** – Full account export with all resources plus per-element `element_mapping_id`
- **`account_{ID}_summary__{timestamp}.md`** – High-level summary with counts by resource type
- **`account_{ID}_report__{timestamp}.md`** – Detailed tree showing IDs and names
- **`account_{ID}_report_items__{timestamp}.json`** – Line-item JSON array (starting at line number 1001) with `element_type_code`, `element_mapping_id`, and `include_in_conversion` flag for each resource

The latest snapshot contains 17 projects, 3 connections, and 15 repositories, including:
  - Globals: connections, repositories
  - Projects with environments, jobs, and environment variables
  - Some environment variables are redacted (marked with `**********` by the API for secrets)

## Structure

The JSON export follows the `AccountSnapshot` Pydantic model defined in `importer/models.py`:

```json
{
  "account_id": 86165,
  "account_name": null,
  "globals": {
    "connections": { "<key>": { "id": ..., "name": ..., "details": {...} } },
    "repositories": { "<key>": { "id": ..., "remote_url": ..., "metadata": {...} } }
  },
  "projects": [
    {
      "key": "<slug>",
      "id": 123,
      "name": "...",
      "repository_key": "<slug>",
      "environments": [...],
      "environment_variables": [...],
      "jobs": [...],
      "metadata": {...}
    }
  ]
}
```

## Notes

- The warnings about "Unexpected payload structure" in the importer output indicate that the environment variables API response format differs slightly from expectations (it wraps data in a nested structure). The importer still captured the data successfully.
- IDs are preserved for now; Phase 2 will strip source IDs and replace with key-based references for the target YAML.
- Future iterations will add: service tokens, groups, notifications, PrivateLink endpoints, semantic layer configs.

## Usage

These samples can be used to:
1. Validate Phase 2 YAML normalization logic
2. Test schema v2 coverage against real-world data
3. Develop Terraform module updates without hitting live APIs

To regenerate after code changes:
```bash
cd /path/to/repo
source .venv/bin/activate
python -m importer fetch --output dev_support/samples/account.json --reports-dir dev_support/samples
```

The importer will automatically generate timestamped json, summary, report, and report-items files.

