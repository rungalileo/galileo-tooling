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

# Merge MCP servers from generated .mcp.json into ~/.claude/settings.json
MCP_FILE="$REPO_DIR/.mcp.json"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
if [ -f "$MCP_FILE" ]; then
  node -e "
const fs = require('fs');
const [mcpFile, settingsFile] = process.argv.slice(1);

const mcp = JSON.parse(fs.readFileSync(mcpFile, 'utf8'));
const newServers = mcp.mcpServers || {};

let settings = {};
if (fs.existsSync(settingsFile)) {
  try { settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8')); } catch (e) {}
}
if (!settings.mcpServers) settings.mcpServers = {};

let added = [], skipped = [];
for (const [name, server] of Object.entries(newServers)) {
  if (settings.mcpServers[name]) {
    skipped.push(name + ' (already configured)');
  } else {
    settings.mcpServers[name] = server;
    added.push(name);
  }
}

fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2) + '\n');
for (const s of added) console.log('  + ' + s + ' → ~/.claude/settings.json');
for (const s of skipped) console.log('  ~ ' + s + ' (skipped)');
if (added.length === 0 && skipped.length === 0) console.log('  No MCP servers to merge.');
" "$MCP_FILE" "$SETTINGS_FILE"
else
  echo "No .mcp.json found, skipping MCP merge."
fi
