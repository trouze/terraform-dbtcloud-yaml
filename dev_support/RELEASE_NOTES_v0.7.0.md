# Release Notes v0.7.0

**Release Date:** 2026-01-13  
**Type:** Minor Release (New Feature)

---

## Summary

This release introduces a new web-based user interface for the dbt Cloud Account Migration Tool, providing an interactive and visual way to manage the account migration workflow.

---

## New Features

### Web UI: Account Migration Tool

A new NiceGUI-based web interface that provides a guided workflow for migrating dbt Cloud configurations between accounts.

#### Key Features

- **5-Step Guided Workflow**
  - **Fetch**: Configure source credentials and download account data
  - **Explore**: Browse entities, view reports, export data to CSV
  - **Map**: Select entities to migrate, configure normalization options
  - **Target**: Set up destination account credentials
  - **Deploy**: Generate Terraform and apply changes

- **User Experience**
  - Dark/light theme toggle with dbt brand colors (#FF694A orange)
  - Session state persistence across page refreshes
  - Recent runs dashboard showing previous fetch/normalize operations
  - Step locking ensures workflow completion order
  - Responsive sidebar navigation

- **Launch Options**
  ```bash
  # Basic launch (opens browser automatically)
  python -m importer.web
  
  # Custom port, no auto-open
  python -m importer.web --port 9000 --no-open
  
  # Development mode with hot reload
  python -m importer.web --reload
  ```

#### Technical Details

- Built with NiceGUI framework (Python-native UI)
- Leverages existing importer modules (`fetch`, `normalize`)
- Credentials stored in local `.env` file
- Session data persisted via NiceGUI storage

---

## Changes

### Branding

- Renamed "Importer" to "Account Migration Tool" in web UI
- Updated logo and favicon to use dbt Labs branding

---

## Dependencies

New dependencies added to `importer/requirements.txt`:

```
nicegui>=2.0,<3
pandas>=2.0,<3
plotly>=5.0,<6
```

---

## Migration Notes

No breaking changes. The existing CLI commands (`fetch`, `normalize`) continue to work unchanged.

---

## Files Added/Modified

### New Files
- `importer/web/__init__.py` - Package initialization
- `importer/web/__main__.py` - Entry point
- `importer/web/app.py` - Main application and routing
- `importer/web/state.py` - Session state management
- `importer/web/env_manager.py` - .env file handling
- `importer/web/pages/home.py` - Dashboard page
- `importer/web/components/stepper.py` - Navigation component
- `importer/web/static/dbt-labs-logo.svg` - Logo asset
- `importer/web/static/favicon.svg` - Favicon asset

### Modified Files
- `importer/requirements.txt` - Added web UI dependencies
- `CHANGELOG.md` - Added v0.7.0 entry
- `importer/VERSION` - Bumped to 0.7.0

---

## Known Limitations

1. **Fetch/Explore/Map/Target/Deploy pages**: Currently placeholder implementations. Full functionality to be added in subsequent releases.
2. **Multi-user support**: Not supported. Web UI is designed for single-user local use.

---

## Next Steps

- Implement Fetch step with credential form and API connection
- Implement Explore step with AGGrid tables and Plotly charts
- Implement Map step with entity selection
- Implement Target step with destination credentials
- Implement Deploy step with Terraform integration

---

**Full Changelog:** [CHANGELOG.md](../CHANGELOG.md)
