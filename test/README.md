# Test Suite Overview

This repository now contains both Go-based Terratest coverage and Python-based schema validation checks:

- `go test ./test` &rightarrow; Runs the existing Terratest matrix to ensure the Terraform module plans successfully with the provided fixtures.
- `python -m unittest test/schema_validation_test.py` &rightarrow; Validates representative YAML files against `schemas/v1.json` and `schemas/v2.json`. Use this to guard importer work and schema changes.

## Running the Python Schema Tests

1. Create a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install the requirements:
   ```bash
   pip install -r test/requirements.txt
   ```
3. Execute the suite:
   ```bash
   python -m unittest test/schema_validation_test.py
   ```

The Python tests currently validate:
- `test/fixtures/basic/dbt-config.yml` (v1 schema)
- `test/fixtures/complete/dbt-config.yml` (v1 schema)
- `test/fixtures/v2_full/dbt-config.yml` (v2 schema)

Add additional fixtures/tests as schema features evolve to keep both versions covered.

