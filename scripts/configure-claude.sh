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

# Merge MCP servers from generated .mcp.json into ~/.claude.json (the correct location for user-scoped MCP servers)
MCP_FILE="$REPO_DIR/.mcp.json"
CLAUDE_JSON="$HOME/.claude.json"
if [ -f "$MCP_FILE" ]; then
  node -e "
const fs = require('fs');
const [mcpFile, claudeJson] = process.argv.slice(1);

const mcp = JSON.parse(fs.readFileSync(mcpFile, 'utf8'));
const newServers = mcp.mcpServers || {};

let config = {};
if (fs.existsSync(claudeJson)) {
  try { config = JSON.parse(fs.readFileSync(claudeJson, 'utf8')); } catch (e) {}
}
if (!config.mcpServers) config.mcpServers = {};

let added = [], updated = [], unchanged = [];
for (const [name, server] of Object.entries(newServers)) {
  if (!config.mcpServers[name]) {
    config.mcpServers[name] = server;
    added.push(name);
  } else if (JSON.stringify(config.mcpServers[name]) !== JSON.stringify(server)) {
    config.mcpServers[name] = server;
    updated.push(name);
  } else {
    unchanged.push(name);
  }
}

fs.writeFileSync(claudeJson, JSON.stringify(config, null, 2) + '\n');
for (const s of added) console.log('  + ' + s + ' → ~/.claude.json');
for (const s of updated) console.log('  ~ ' + s + ' (updated)');
for (const s of unchanged) console.log('  = ' + s + ' (unchanged)');
if (added.length === 0 && updated.length === 0 && unchanged.length === 0) console.log('  No MCP servers to merge.');
" "$MCP_FILE" "$CLAUDE_JSON"
else
  echo "No .mcp.json found, skipping MCP merge."
fi
