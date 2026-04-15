#!/usr/bin/env bash
# install.sh — bootstrap a dbt Cloud Terraform starter from terraform-dbtcloud-as-yaml
#
# Usage:
#   curl -fsSL https://github.com/dbt-labs/terraform-dbtcloud-as-yaml/releases/latest/download/install.sh | bash
#   curl -fsSL https://github.com/dbt-labs/terraform-dbtcloud-as-yaml/releases/latest/download/install.sh | bash -s -- my-project
#
set -euo pipefail

TARGET=${1:-my-dbt-platform}
REPO="trouze/terraform-dbtcloud-as-yaml"
RELEASE_URL="https://github.com/$REPO/releases/latest/download/starter.tar.gz"

echo "Setting up dbt Platform Terraform starter in ./$TARGET ..."
echo ""

if [[ -e "$TARGET" ]]; then
  echo "Error: '$TARGET' already exists. Pass a different directory name:" >&2
  echo "  bash <(curl -fsSL ...) my-other-name" >&2
  exit 1
fi

mkdir -p "$TARGET"

# Strategy 1: curl + tar (no extra tools required — fastest)
if command -v curl &>/dev/null && command -v tar &>/dev/null; then
  if curl -fsSL "$RELEASE_URL" | tar -xz --strip-components=1 -C "$TARGET" 2>/dev/null; then
    :
  else
    # Fall through to strategy 2 if the release asset doesn't exist yet
    rmdir "$TARGET" 2>/dev/null || true
    _fallback=1
  fi
fi

# Strategy 2: degit (needs npm/npx)
if [[ ${_fallback:-0} -eq 1 ]] || [[ ! -d "$TARGET" ]]; then
  if command -v npx &>/dev/null; then
    echo "(release asset not found, falling back to degit)"
    npx --yes degit "$REPO/topologies/basic" "$TARGET"
  else
    # Strategy 3: git sparse-checkout
    echo "(falling back to git sparse-checkout)"
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    git clone --no-checkout --depth=1 "https://github.com/$REPO" "$TMP/repo" --quiet
    git -C "$TMP/repo" sparse-checkout set topologies/basic
    git -C "$TMP/repo" checkout --quiet
    cp -r "$TMP/repo/topologies/basic/." "$TARGET/"
  fi
fi

echo "Done. Starter created in ./$TARGET"
echo ""
echo "Next steps:"
echo "  1.  cd $TARGET"
echo "  2.  cp .env.example .env"
echo "      # fill in DBT_ACCOUNT_ID, DBT_TOKEN, and warehouse credentials"
echo "  3.  Edit dbt-config.yml"
echo "      # replace YOUR_ placeholders with your warehouse and repo details"
echo "  4.  source .env && terraform init && terraform apply"
echo ""
echo "Full walkthrough: https://github.com/$REPO/blob/main/topologies/basic/README.md"
