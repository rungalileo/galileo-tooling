# Logz.io MCP Server

## Setup

1. Get the Logz.io API key from 1Password (ask Shuai Shao for access)

2. Add to your `.mcp.json`:

```json
"logzio": {
  "command": "npx",
  "args": ["-y", "logzio-mcp-server"],
  "env": {
    "LOGZIO_API_KEY": "{API_KEY}",
    "LOGZIO_REGION": "us"
  }
}
```
