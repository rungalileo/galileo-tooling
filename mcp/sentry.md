# Sentry MCP Server

## Setup

1. Create a Sentry API key at https://sentry.io/settings/account/api/auth-tokens/
2. Set the following permissions:
   - `event:read`
   - `org:read`
   - `project:read`
   - `team:read`
   - `issue:read`

3. Add to your `.mcp.json`:

```json
"sentry": {
  "command": "npx",
  "args": ["-y", "@sentry/mcp-server@latest"],
  "env": {
    "SENTRY_ACCESS_TOKEN": "{YOUR_TOKEN}"
  }
}
```
