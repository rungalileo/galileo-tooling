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

`setup.sh` configures Sentry, Logz.io, and Slack MCP servers automatically and generates `.mcp.json`.

For Slack, you need to create an app and get a bot token first — see [mcp/slack.md](mcp/slack.md) for the prerequisites.
