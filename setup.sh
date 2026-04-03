#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "  Galileo Tooling Setup"
echo "========================================="
echo ""

# Resolve repo root (works from any subdirectory)
export REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$REPO_DIR/env.sample" ]; then
  echo "Error: setup.sh must be run from within the galileo-tooling repo."
  exit 1
fi

echo "Repo: $REPO_DIR"

source "$REPO_DIR/scripts/collect-tokens.sh"
source "$REPO_DIR/scripts/generate-mcp.sh"
source "$REPO_DIR/scripts/install-skills.sh"
source "$REPO_DIR/scripts/configure-claude.sh"

# --- Summary ---
echo ""
echo "========================================="
echo "  Setup Complete"
echo "========================================="
echo ""
echo "  Repo:      $REPO_DIR"
echo "  Env:       $REPO_DIR/.env"
if [ -f "$REPO_DIR/.mcp.json" ]; then
echo "  MCP:       $REPO_DIR/.mcp.json"
fi
echo ""
