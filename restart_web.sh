#!/usr/bin/env bash
set -euo pipefail

PORT=8080
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v lsof >/dev/null 2>&1; then
  lsof -ti:${PORT} | xargs kill -9 2>/dev/null || true
fi

cd "${ROOT_DIR}"
python3 -m importer.web --no-open
