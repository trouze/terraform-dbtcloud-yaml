# Quick Start Guide

## Setup

1. **Activate the virtual environment:**
   ```bash
   cd /Users/operator/Documents/git/dbt-labs/terraform-dbtcloud-yaml
   source .venv/bin/activate
   ```

2. **Install/update dependencies (if needed):**
   ```bash
   pip install -r importer/requirements.txt
   ```

3. **Configure credentials** (create `.env` file at repo root):
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

## Running Commands

### Interactive Mode (Recommended for first-time users)

```bash
# Make sure virtualenv is activated first!
source .venv/bin/activate

# Interactive fetch
python -m importer fetch --interactive

# Interactive normalize
python -m importer normalize --interactive
```

### Command-Line Mode

```bash
# Fetch
python -m importer fetch --output dev_support/samples/account.json

# Normalize
python -m importer normalize dev_support/samples/account_12345_run_001__json__20250127_120000.json
```

## Troubleshooting

**Error: `ModuleNotFoundError: No module named 'typer'`**
- Solution: Activate the virtual environment first with `source .venv/bin/activate`

**Error: Missing credentials**
- Solution: Create `.env` file or use `--interactive` mode to enter credentials

**Interactive mode not working**
- Make sure InquirerPy is installed: `pip install InquirerPy`

