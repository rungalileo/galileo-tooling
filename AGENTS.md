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

Some skills work best with MCP (Model Context Protocol) servers connected. Configure these in your tool's MCP settings:

- **Sentry** — For error investigation skills
- **ClickHouse** — For metrics and analytics skills
- **Logz.io** — For log analysis skills
- **Shortcut** — For project management skills

Refer to each MCP server's documentation for setup instructions.
