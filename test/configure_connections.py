#!/usr/bin/env python3
"""
Helper script for configuring connection provider_config interactively.
This is called from the E2E test script to configure connections.
"""
import sys
from pathlib import Path

# Resolve project root relative to this script's absolute location
script_path = Path(__file__).resolve()
project_root = script_path.parent.parent  # test/configure_connections.py -> test/ -> project_root

# Add project root to sys.path if not already there
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from importer.interactive import prompt_connection_credentials_interactive

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: configure_connections.py <yaml_file>", file=sys.stderr)
        sys.exit(1)
    
    yaml_path = Path(sys.argv[1])
    if not yaml_path.exists():
        print(f"Error: YAML file not found: {yaml_path}", file=sys.stderr)
        sys.exit(1)
    
    prompt_connection_credentials_interactive(yaml_path)

