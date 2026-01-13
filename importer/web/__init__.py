"""dbt Magellan: Exploration & Migration Tool.

A NiceGUI-based web interface for the fetch → explore → map → deploy workflow.
"""

from pathlib import Path

# Read version from the main importer VERSION file
_version_file = Path(__file__).parent.parent / "VERSION"
if _version_file.exists():
    __version__ = _version_file.read_text().strip()
else:
    __version__ = "0.7.1"
