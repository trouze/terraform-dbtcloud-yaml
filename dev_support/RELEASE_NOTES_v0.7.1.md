# Release Notes — v0.7.1 (2026-01-13)

## Summary

This patch release improves importer performance and usability for large accounts, and hardens Terraform planning for complex job schedules.

## Highlights

### Fetch performance: parallel API calls

- Parallelized Phase 1 fetch across:
  - Global resources (connections, repositories, service tokens, groups, notifications, webhooks, PrivateLink endpoints)
  - Projects (environments, jobs, env vars)
  - Job env-var overrides
- Configurable concurrency:
  - `DBT_SOURCE_FETCH_THREADS` (default: 5)
  - `python -m importer fetch --threads N` (CLI overrides env var)

### Fetch progress UX

- Progress display shows thread count and provides clearer visibility into project completion vs. override fetching.

### Terraform hardening

- Jobs module now avoids invalid schedule attribute combinations (cron vs interval vs hours).
- E2E runner no longer flags false-positive “errors” based on substrings like `errors_on_lint_failure`.

## Upgrade Notes

- No breaking changes expected.
- If you hit dbt Cloud rate limits, lower concurrency (e.g. `--threads 2`).

