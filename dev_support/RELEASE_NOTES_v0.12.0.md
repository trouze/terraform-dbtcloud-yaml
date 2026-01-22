# Release Notes v0.12.0

**Release Date:** 2026-01-21  
**Type:** Minor Release  
**Focus:** Target Credentials Page Redesign & UX Improvements

---

## Overview

This release delivers a comprehensive redesign of the Target Credentials page, introducing source/override indicators for credential fields, dummy credentials management, and significant layout improvements across the fetch pages. The goal is to provide clear visibility into which credential values come from the source account vs. user overrides.

---

## New Features

### Target Credentials Page Redesign

The environment credentials editing experience has been completely overhauled:

#### Source/Override Indicators
- **"From source" badge (green)**: Indicates the field value matches what was fetched from the source account
- **"Override" badge (yellow)**: Indicates the user has modified the value from the original source
- Badges appear next to each editable field for immediate visibility

#### Per-Field Reset Buttons
- Each field now has a reset button (restore icon) to revert to the source value
- Tooltip shows the source value that will be restored
- Button highlights on hover for clear affordance

#### Authentication Type Selector Enhancements
- Authentication dropdown now shows "From source" / "Override" indicator
- Reset button to restore authentication method to source value
- Supports Snowflake password/keypair and other credential types

#### "Use Dummy Credentials" Toggle
- Toggle to use placeholder values for testing
- **"Overrides Source" indicator**: Yellow badge appears when dummy mode would override real source values
- **Comparison table**: Visual side-by-side comparison showing:
  - Source values (green background)
  - Dummy override values (orange background)
  - Arrow indicators showing the override direction

#### Reset to Dummy Credentials Button
- New action button in environment table to quickly reset credentials to dummy values
- Useful for testing terraform plan/apply cycles

### Credential Metadata Extraction

Enhanced source value extraction from YAML files:

- **New fields extracted**: `auth_type`, `authentication`, `auth_method`
- **Automatic inference**: For Snowflake credentials, `auth_type` is inferred from presence of `private_key` (→ keypair) or `password` (→ password) fields
- **Comprehensive extraction**: Includes `user`, `schema`, `database`, `warehouse`, `role`, `num_threads`, and more

### Progress Visibility Improvements

Renamed progress labels for clarity:
- **"Credentials"** → **"Credential Metadata (No Secret Values)"**
- **"Env Variables"** → **"Env Variables (No Secret Values)"**

This makes it clear that the tool fetches metadata about credentials and environment variables but never retrieves actual secret values.

---

## Changes

### Workflow Lockout Logic

Adjusted step accessibility for better flexibility:

| Step | Previous Behavior | New Behavior |
|------|------------------|--------------|
| Fetch Target | Required source selection first | Accessible at any time |
| Match Existing | Required target fetch | Requires both source AND target fetch |

### Fetch Page Layout

Redesigned from two-column to vertical stack layout:

- **Eliminated layout shift**: Fixed the issue where content would move when transitioning from "ready to fetch" to "fetch complete"
- **No scrollbar issues**: Removed problematic fixed heights that caused scrollbars in progress sections
- **Compact credential forms**: Single-row layout for Host URL, Account ID, and Token fields

### Edit Dialog Improvements

- **Wider dialog**: Increased to `max-w-6xl` for better field visibility
- **CSS Grid layout**: Consistent column alignment across all fields
  - Label column: 140px (right-aligned)
  - Input column: Flexible
  - Indicator column: 100px (centered badges)
  - Reset column: 40px (centered button)

---

## Bug Fixes

- **Layout stability**: Eliminated layout shift between "ready to fetch" and "fetch complete" states
- **State preservation**: Fetch complete page no longer clears logs and progress information
- **Authentication indicator**: Fixed authentication type selector not displaying source/override badges (was missing source value extraction for `auth_type`)

---

## Technical Details

### Files Modified

| File | Changes |
|------|---------|
| `importer/web/pages/target_credentials.py` | Complete redesign of edit dialog, CSS Grid layout, source/override indicators, reset functionality |
| `importer/web/pages/fetch_source.py` | Vertical layout redesign, credential counter, state preservation |
| `importer/web/pages/fetch_target.py` | Vertical layout redesign, credential counter, state preservation |
| `importer/web/pages/fetch.py` | Vertical layout redesign (legacy page) |
| `importer/web/components/credential_form.py` | Compact single-row layout |
| `importer/web/components/progress_tree.py` | Renamed labels with "(No Secret Values)" suffix |
| `importer/web/state.py` | Updated `step_is_accessible()` for new workflow logic |

### Key Code Patterns

**CSS Grid for Columnar Layout:**
```python
with ui.element("div").classes("w-full").style(
    "display: grid; grid-template-columns: 140px 1fr 100px 40px; gap: 12px; align-items: center;"
):
    ui.label(label_text).classes("text-sm text-right")
    # Input field...
    # Indicator badges...
    # Reset button...
```

**Source/Override Indicator Pattern:**
```python
has_source = source_value is not None and not is_sensitive
is_from_source = has_source and str(current_value) == str(source_value)

# Green "From source" badge (visible when matching)
indicators["from_source"] = ui.element("div")
indicators["from_source"].set_visibility(is_from_source)
with indicators["from_source"]:
    ui.badge("From source", color="green").props("dense outline")

# Yellow "Override" badge (visible when not matching)
indicators["override"] = ui.element("div")
indicators["override"].set_visibility(not is_from_source)
with indicators["override"]:
    ui.badge("Override", color="yellow-8").props("dense outline")
```

---

## Upgrade Notes

This is a minor release with no breaking changes. Simply update to the new version:

```bash
# Check current version
python3 -c "from importer import get_version; print(get_version())"

# Should output: 0.12.0
```

---

## What's Next

- Additional credential type support (Redshift, Postgres)
- Bulk credential operations
- Credential validation before deploy
- Enhanced error messages for credential configuration issues
