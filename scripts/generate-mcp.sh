#!/usr/bin/env bash
# Generate .mcp.json from template, merging with any existing config
set -euo pipefail

REPO_DIR="${REPO_DIR:?REPO_DIR must be set}"
MCP_FILE="$REPO_DIR/.mcp.json"
MCP_TEMPLATE="$REPO_DIR/mcp/mcp.template.json"

echo ""
echo "========================================="
echo "  Configuring MCP Servers"
echo "========================================="
echo ""

# Load .env if not already loaded (for standalone usage)
if [ -z "${SENTRY_ACCESS_TOKEN:-}${LOGZIO_API_KEY:-}${SLACK_BOT_TOKEN:-}" ] && [ -f "$REPO_DIR/.env" ]; then
  set -a
  source "$REPO_DIR/.env"
  set +a
fi

node -e "
const fs = require('fs');
const [mcpFile, templateFile] = process.argv.slice(1);

// Read template and substitute \${VAR} placeholders from env
let raw = fs.readFileSync(templateFile, 'utf8');
raw = raw.replace(/\\\$\{(\w+)\}/g, (_, key) => process.env[key] || '');
const template = JSON.parse(raw);

// Drop servers where any env value is empty
for (const [name, server] of Object.entries(template.mcpServers)) {
  const envVals = Object.values(server.env || {});
  if (envVals.some(v => !v)) {
    delete template.mcpServers[name];
  }
}

// Load existing .mcp.json if present
let existing = { mcpServers: {} };
if (fs.existsSync(mcpFile)) {
  try {
    existing = JSON.parse(fs.readFileSync(mcpFile, 'utf8'));
    if (!existing.mcpServers) existing.mcpServers = {};
    console.log('  Loaded existing ' + mcpFile);
  } catch (e) {
    console.log('  Warning: could not parse existing .mcp.json, starting fresh');
  }
}

// Merge: existing servers take priority (don't overwrite)
let added = [];
let skipped = [];
for (const [name, server] of Object.entries(template.mcpServers)) {
  if (existing.mcpServers[name]) {
    skipped.push(name + ' (already configured)');
  } else {
    existing.mcpServers[name] = server;
    added.push(name);
  }
}

for (const s of added) console.log('  + ' + s);
for (const s of skipped) console.log('  ~ ' + s);

if (Object.keys(existing.mcpServers).length > 0) {
  fs.writeFileSync(mcpFile, JSON.stringify(existing, null, 2) + '\n');
  console.log('');
  console.log('  Wrote ' + mcpFile);
  console.log('');
  console.log('  To use in your service repos, copy or symlink:');
  console.log('    cp ' + mcpFile + ' ~/your-project/.mcp.json');
  console.log('    # or');
  console.log('    ln -sf ' + mcpFile + ' ~/your-project/.mcp.json');
} else {
  console.log('  No MCP tokens provided, skipping .mcp.json');
}
" "$MCP_FILE" "$MCP_TEMPLATE"
