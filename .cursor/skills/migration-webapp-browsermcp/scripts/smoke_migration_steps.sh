#!/usr/bin/env bash
set -euo pipefail

# Non-destructive smoke checks for migration web app readiness.
# This script does not mutate workflow state or run terraform actions.

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
RESTART_SCRIPT="${REPO_ROOT}/restart_web.sh"

ROUTES=(
  "/"
  "/fetch_source"
  "/explore_source"
  "/scope"
  "/fetch_target"
  "/explore_target"
  "/match"
  "/adopt"
  "/configure"
  "/target_credentials"
  "/deploy"
)

echo "Smoke check: migration web app"
echo "Repo root: ${REPO_ROOT}"
echo "Base URL:  ${BASE_URL}"
echo

if [[ ! -x "${RESTART_SCRIPT}" ]]; then
  echo "ERROR: Missing executable restart script: ${RESTART_SCRIPT}"
  echo "Expected canonical startup script is ./restart_web.sh"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required for smoke checks."
  exit 1
fi

check_route() {
  local route="$1"
  local code
  code="$(curl -sS -o /dev/null -m "${TIMEOUT_SECONDS}" -w "%{http_code}" "${BASE_URL}${route}" || true)"
  if [[ "${code}" =~ ^(200|302|303|307|308)$ ]]; then
    printf "OK    %s -> %s\n" "${route}" "${code}"
  else
    printf "FAIL  %s -> %s\n" "${route}" "${code:-no-response}"
    return 1
  fi
}

failures=0
for route in "${ROUTES[@]}"; do
  if ! check_route "${route}"; then
    failures=$((failures + 1))
  fi
done

echo
if [[ "${failures}" -gt 0 ]]; then
  echo "Smoke check completed with ${failures} failing route(s)."
  echo "If server is down, run: ./restart_web.sh"
  exit 1
fi

echo "Smoke check passed."
