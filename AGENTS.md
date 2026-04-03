# Galileo Agent Setup

This document describes how to configure your environment for Galileo tooling.

## Quick Setup

Run the interactive setup script — it handles cloning, API tokens, skills installation, and Claude Code configuration:

```bash
./setup.sh
```

Or pre-fill your tokens in `.env` first (copy from `env.sample`), then run `setup.sh` — it will skip prompts for any tokens already set.

## Environment Variables

Tokens are stored in `.env` (never committed to git). See `env.sample` for the full list.

## MCP Servers

Some skills work best with MCP (Model Context Protocol) servers connected. See the setup guides in `mcp/`:

- [Sentry](mcp/sentry.md) — Error investigation and issue tracking
- [Logz.io](mcp/logzio.md) — Log analysis and search
- [Slack](mcp/slack.md) — Channel reading and messaging

Add each server's config block to your project's `.mcp.json` under `mcpServers`.
