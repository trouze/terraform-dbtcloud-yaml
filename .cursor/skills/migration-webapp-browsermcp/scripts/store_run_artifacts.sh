#!/usr/bin/env bash
set -euo pipefail

# Copy downloaded run artifacts into a repo-local analysis folder.
# Usage:
#   ./.cursor/skills/migration-webapp-browsermcp/scripts/store_run_artifacts.sh <run_id> <file1> [file2 ...]

if [[ "$#" -lt 2 ]]; then
  echo "Usage: $0 <run_id> <file1> [file2 ...]"
  exit 1
fi

RUN_ID="$1"
shift

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
BASE_DIR="${REPO_ROOT}/dev_support/artifact_analysis"
STAMP="$(date +"%Y%m%d_%H%M%S")"
DEST_DIR="${BASE_DIR}/run_${RUN_ID}_${STAMP}"

mkdir -p "${DEST_DIR}"

copied=0
for src in "$@"; do
  if [[ ! -f "${src}" ]]; then
    echo "WARN: Skipping missing file: ${src}"
    continue
  fi
  cp -f "${src}" "${DEST_DIR}/"
  copied=$((copied + 1))
  echo "Copied: ${src} -> ${DEST_DIR}/"
done

if [[ "${copied}" -eq 0 ]]; then
  echo "ERROR: No files copied."
  exit 1
fi

echo "Stored ${copied} artifact(s) in: ${DEST_DIR}"
