# Interactive Mode Guide

## Overview

The dbt Cloud Importer provides an interactive mode with a terminal-based UI for both `fetch` and `normalize` commands. This guide covers keyboard navigation, error recovery, and common workflows.

## Keyboard Navigation

### Basic Navigation
- **↑/↓ Arrow Keys** or **k/j**: Move between options in lists/menus
- **Tab**: Move to next field in forms
- **Shift+Tab**: Move to previous field in forms
- **Enter**: Confirm selection or submit current field
- **Space**: Toggle checkboxes or select/deselect items
- **Ctrl+C**: Cancel and exit (at any prompt)

### Text Input Fields
- **Backspace**: Delete character before cursor
- **Delete**: Delete character at cursor
- **Ctrl+A**: Move to beginning of line
- **Ctrl+E**: Move to end of line
- **Ctrl+U**: Clear entire line
- **Ctrl+K**: Clear from cursor to end of line

### File Browser
- **Type to filter**: Start typing to filter files by name
- **Enter**: Select highlighted file
- **Esc**: Cancel file selection

## Error Recovery & Backing Up

### Cancelling Operations

**At any prompt, you can press Ctrl+C to cancel:**
- If you're in the middle of entering credentials, Ctrl+C will exit completely
- If you've entered something wrong and want to start over, press Ctrl+C and re-run the command

### Fixing Mistakes

**During input:**
- Use **Backspace** to delete incorrect characters
- Use **Ctrl+U** to clear the entire line and start over
- For validation errors (e.g., invalid URL format), just re-enter the correct value

**After confirming:**
- Interactive mode shows a final confirmation screen before executing
- Review all your settings at the confirmation prompt
- Answer "No" to the "Proceed?" question to cancel without running
- If you proceed and want to change something, you'll need to re-run the command

### Example Recovery Workflow

```bash
# 1. Start interactive fetch
$ python -m importer fetch --interactive

# 2. Enter wrong host URL
? dbt Cloud Host URL: https://wrong.url
                      ^^^ Oops! Wrong URL

# 3. Press Ctrl+U to clear the line
? dbt Cloud Host URL: |

# 4. Enter correct URL
? dbt Cloud Host URL: https://cloud.getdbt.com

# 5. Continue through prompts...

# 6. Review at confirmation screen
Ready to fetch:
  Output: dev_support/samples/account.json
  Reports: dev_support/samples
  Timestamp: True
  Compact: False

? Proceed with fetch? (Y/n)
# Answer 'n' if anything looks wrong, 'Y' to continue
```

## Common Workflows

### First-Time Fetch (No Credentials Configured)

```bash
# Activate virtualenv
source .venv/bin/activate

# Run interactive fetch
python -m importer fetch --interactive

# You'll be prompted for:
# 1. dbt Cloud Host URL (defaults to https://cloud.getdbt.com)
# 2. Account ID (must be numeric)
# 3. API Token (hidden input with ***)
# 4. Output file path
# 5. Reports directory
# 6. Timestamp preference
# 7. Compact JSON preference
# 8. Final confirmation
```

### Quick Fetch (Credentials Already in .env)

```bash
# If credentials are in .env, you'll skip to file options
python -m importer fetch --interactive

# Prompts:
# ✓ Using credentials from environment variables
# 1. Output file path
# 2. Reports directory
# 3. Timestamp preference
# 4. Compact JSON preference
# 5. Final confirmation
```

### Interactive Normalize

```bash
python -m importer normalize --interactive

# You'll be prompted for:
# 1. Select input JSON file (shows recent files or browse)
# 2. Mapping configuration file (defaults to importer_mapping.yml)
# 3. Output directory (optional, uses config default if empty)
# 4. Final confirmation
```

## Tips & Tricks

### Speed Up Navigation

1. **Use defaults**: Most fields have sensible defaults - just press Enter to accept
2. **Tab through forms**: Use Tab to quickly move between fields
3. **Type to filter**: In file lists, start typing to filter by name

### Credential Management

**Option 1: Use .env file (Recommended)**
```bash
# Create .env file at repo root
cat > .env << 'EOF'
DBT_SOURCE_HOST=https://cloud.getdbt.com
DBT_SOURCE_ACCOUNT_ID=12345
DBT_SOURCE_API_TOKEN=your_token_here
EOF

# Interactive mode will use these automatically
python -m importer fetch --interactive
```

**Option 2: Enter each time**
- Interactive mode will prompt for any missing credentials
- Credentials are stored in environment variables for the session only
- They are NOT saved to disk

### Validation Errors

If you enter invalid data, you'll see an error message:
```
? dbt Cloud Host URL: http://cloud.getdbt.com
❌ Host URL must start with https://
# Just re-enter with the correct format
```

Common validations:
- **Host URL**: Must start with `https://`
- **Account ID**: Must be numeric only
- **API Token**: Must not be empty
- **File paths**: File must exist and be readable

## Troubleshooting

### "Input is not a terminal" Error

This happens when you pipe output or run in a non-interactive shell:

```bash
# ❌ Won't work
python -m importer fetch --interactive | tee output.log

# ✅ Works
python -m importer fetch --interactive
```

**Solution**: Run in a real terminal without piping output.

### Stuck in a Loop

If the interactive mode seems to loop back to the beginning:

1. Press **Ctrl+C** to exit
2. Make sure you're using the latest version
3. Check that you answered the confirmation prompt

### Can't See Password as I Type

This is intentional! The API token field is a "secret" input that hides characters for security. You won't see anything as you type, but the characters are being recorded.

### File Browser Not Showing My File

The file browser initially shows:
- Recent files matching pattern `account_*_run_*__json__*.json`
- From `dev_support/samples/` and current directory
- Max 10 most recent files

If your file isn't listed:
1. Select "Browse for file..." option
2. Use the file picker to navigate to your file
3. Or type the path directly

## Command Reference

### Interactive Fetch
```bash
python -m importer fetch --interactive
# or
python -m importer fetch -i
```

### Interactive Normalize
```bash
python -m importer normalize --interactive
# or
python -m importer normalize -i
```

### Exit Interactive Mode
- Press **Ctrl+C** at any prompt
- Answer **No** at the final confirmation prompt

### Get Help
```bash
python -m importer fetch --help
python -m importer normalize --help
```

