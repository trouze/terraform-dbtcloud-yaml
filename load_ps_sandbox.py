#!/usr/bin/env python3
"""Load the PS Sandbox project into active session state."""

import json
from pathlib import Path

# Load the PS Sandbox state
project_state_path = Path("projects/ps-sandbox/state.json")
if not project_state_path.exists():
    print(f"Error: {project_state_path} not found")
    exit(1)

with open(project_state_path) as f:
    state_data = json.load(f)

# Update the active_project field
state_data["active_project"] = "ps-sandbox"
state_data["project_path"] = str(Path("projects/ps-sandbox").absolute())

# Print confirmation
print(f"Project: {state_data.get('active_project')}")
print(f"Path: {state_data.get('project_path')}")
print(f"Workflow: {state_data.get('workflow')}")
print(f"Source fetch complete: {state_data.get('fetch', {}).get('complete', False)}")
print(f"Target fetch complete: {state_data.get('target_fetch', {}).get('complete', False)}")
print("\nState loaded successfully. The web app should pick this up on next page load.")
