#!/usr/bin/env bash
# Symlink shared memory and rules into ~/.claude
set -euo pipefail

REPO_DIR="${REPO_DIR:?REPO_DIR must be set}"

echo ""
echo "========================================="
echo "  Configuring Claude Code"
echo "========================================="
echo ""

CLAUDE_DIR="$HOME/.claude"
mkdir -p "$CLAUDE_DIR"

# Symlink shared memory
if [ -d "$REPO_DIR/memory" ] && [ "$(ls -A "$REPO_DIR/memory" 2>/dev/null)" ]; then
  if [ -L "$CLAUDE_DIR/shared-memory" ]; then
    rm "$CLAUDE_DIR/shared-memory"
  fi
  ln -sf "$REPO_DIR/memory" "$CLAUDE_DIR/shared-memory"
  echo "Linked shared memory → $CLAUDE_DIR/shared-memory"
else
  echo "No shared memory files yet, skipping symlink."
fi

# Symlink shared rules
if [ -d "$REPO_DIR/rules" ] && [ "$(ls -A "$REPO_DIR/rules" 2>/dev/null)" ]; then
  if [ -L "$CLAUDE_DIR/shared-rules" ]; then
    rm "$CLAUDE_DIR/shared-rules"
  fi
  ln -sf "$REPO_DIR/rules" "$CLAUDE_DIR/shared-rules"
  echo "Linked shared rules → $CLAUDE_DIR/shared-rules"
else
  echo "No shared rules yet, skipping symlink."
fi
