#!/usr/bin/env bash
# Install skills via Vercel skills framework
set -euo pipefail

REPO_DIR="${REPO_DIR:?REPO_DIR must be set}"

echo ""
echo "========================================="
echo "  Installing Skills"
echo "========================================="
echo ""

if command -v npx &> /dev/null; then
  echo "Installing Galileo skills via Vercel skills framework..."
  npx skills add "$REPO_DIR/skills" --all || echo "Warning: skills install failed. You can retry with: npx skills add $REPO_DIR/skills"
else
  echo "npx not found — skipping skills install."
  echo "Install Node.js, then run: npx skills add $REPO_DIR/skills"
fi
