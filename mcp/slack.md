# Slack MCP Server

## Setup

Slack now uses Slack's official remote MCP server with OAuth authentication. No bot token or app creation is required.

### How it works

The server connects to `https://mcp.slack.com/mcp` and authenticates via OAuth. On first use, Claude Code will open your browser to authorize access to your Slack workspace.

### Configuration

This is handled automatically by `setup.sh`. The template entry in `mcp/mcp.template.json` is:

```json
"slack": {
  "type": "http",
  "url": "https://mcp.slack.com/mcp",
  "oauth": {
    "clientId": "1601185624273.8899143856786",
    "callbackPort": 3118
  }
}
```

No environment variables are needed.
