#!/bin/bash
# ralph-phase.sh - Run ralph automation with specific phase files
#
# Usage:
#   ./ralph-phase.sh RALPH_TASK_EA_PHASE1.md           # Interactive setup
#   ./ralph-phase.sh RALPH_TASK_PM_PHASE1.md --once    # Single iteration
#   ./ralph-phase.sh RALPH_TASK_PHASE2.md --loop -n 10 # Run 10 iterations

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

show_help() {
  cat << 'EOF'
ralph-phase.sh - Run ralph automation with specific phase files

Usage:
  ./ralph-phase.sh <phase-file> [mode] [options]

Modes:
  --setup    Interactive setup (default)
  --once     Single iteration
  --loop     Full loop

Examples:
  ./ralph-phase.sh RALPH_TASK_EA_PHASE1.md
  ./ralph-phase.sh RALPH_TASK_EA_PHASE1.md --once
  ./ralph-phase.sh RALPH_TASK_PM_PHASE1.md --loop -n 20

How it works:
  1. Temporarily copies your phase file to RALPH_TASK.md
  2. Runs the ralph automation script
  3. Copies changes back to your phase file
  4. Restores original RALPH_TASK.md if it existed

This allows you to use the automation with any task file name.
EOF
}

# Parse arguments
PHASE_FILE=""
MODE="setup"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      exit 0
      ;;
    --setup)
      MODE="setup"
      shift
      ;;
    --once)
      MODE="once"
      shift
      ;;
    --loop)
      MODE="loop"
      shift
      ;;
    -*)
      # Pass through to automation script
      EXTRA_ARGS+=("$1")
      if [[ $# -gt 1 ]] && [[ ! "$2" =~ ^- ]]; then
        EXTRA_ARGS+=("$2")
        shift
      fi
      shift
      ;;
    *)
      if [[ -z "$PHASE_FILE" ]]; then
        PHASE_FILE="$1"
      else
        EXTRA_ARGS+=("$1")
      fi
      shift
      ;;
  esac
done

# Validate phase file
if [[ -z "$PHASE_FILE" ]]; then
  echo -e "${RED}Error: No phase file specified${NC}"
  echo ""
  show_help
  exit 1
fi

if [[ ! -f "$PHASE_FILE" ]]; then
  echo -e "${RED}Error: File not found: $PHASE_FILE${NC}"
  exit 1
fi

# Check if phase file has task format
if ! grep -q "^## Success Criteria" "$PHASE_FILE" 2>/dev/null; then
  echo -e "${YELLOW}Warning: $PHASE_FILE doesn't appear to be a Ralph task file${NC}"
  read -p "Continue anyway? [y/N] " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

WORKSPACE="$(pwd)"
RALPH_TASK="$WORKSPACE/RALPH_TASK.md"
BACKUP="$WORKSPACE/.ralph/RALPH_TASK.md.backup"

# Determine which script to run
case "$MODE" in
  setup)
    SCRIPT="./.cursor/ralph-scripts/ralph-setup.sh"
    ;;
  once)
    SCRIPT="./.cursor/ralph-scripts/ralph-once.sh"
    ;;
  loop)
    SCRIPT="./.cursor/ralph-scripts/ralph-loop.sh"
    ;;
  *)
    echo -e "${RED}Unknown mode: $MODE${NC}"
    exit 1
    ;;
esac

# Check if script exists
if [[ ! -f "$SCRIPT" ]]; then
  echo -e "${RED}Error: $SCRIPT not found${NC}"
  echo ""
  echo "Have you installed ralph-wiggum-cursor?"
  echo "Run: /path/to/ralph-wiggum-cursor/install.sh ."
  exit 1
fi

# Show what we're doing
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Ralph Phase Runner${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Phase file: ${GREEN}$PHASE_FILE${NC}"
echo -e "Mode:       ${GREEN}$MODE${NC}"
echo -e "Script:     ${GREEN}$SCRIPT${NC}"
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  echo -e "Options:    ${GREEN}${EXTRA_ARGS[*]}${NC}"
fi
echo ""

# Backup existing RALPH_TASK.md if it exists and is different
if [[ -f "$RALPH_TASK" ]]; then
  if ! diff -q "$RALPH_TASK" "$PHASE_FILE" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Backing up existing RALPH_TASK.md${NC}"
    mkdir -p "$(dirname "$BACKUP")"
    cp "$RALPH_TASK" "$BACKUP"
  fi
fi

# Copy phase file to RALPH_TASK.md
echo -e "${BLUE}→ Copying $PHASE_FILE to RALPH_TASK.md${NC}"
cp "$PHASE_FILE" "$RALPH_TASK"

# Cleanup function
cleanup() {
  local exit_code=$?
  
  echo ""
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}Cleanup${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
  
  # Copy changes back to phase file
  if [[ -f "$RALPH_TASK" ]]; then
    echo -e "${BLUE}→ Syncing changes back to $PHASE_FILE${NC}"
    cp "$RALPH_TASK" "$PHASE_FILE"
  fi
  
  # Restore backup if it existed
  if [[ -f "$BACKUP" ]]; then
    echo -e "${BLUE}→ Restoring original RALPH_TASK.md${NC}"
    mv "$BACKUP" "$RALPH_TASK"
  elif [[ -f "$RALPH_TASK" ]]; then
    # No backup existed, remove RALPH_TASK.md
    echo -e "${BLUE}→ Removing temporary RALPH_TASK.md${NC}"
    rm "$RALPH_TASK"
  fi
  
  echo ""
  if [[ $exit_code -eq 0 ]]; then
    echo -e "${GREEN}✅ Phase runner complete${NC}"
    echo -e "Changes saved to: ${GREEN}$PHASE_FILE${NC}"
  else
    echo -e "${YELLOW}⚠️  Phase runner exited with code $exit_code${NC}"
    echo -e "Changes saved to: ${GREEN}$PHASE_FILE${NC}"
  fi
  
  exit $exit_code
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Run the automation script
echo ""
echo -e "${GREEN}▶ Starting $MODE mode...${NC}"
echo ""

"$SCRIPT" "${EXTRA_ARGS[@]}"
