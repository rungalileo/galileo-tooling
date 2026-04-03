# Slack MCP Server

## Setup

### 1. Create a Slack App

- Go to https://api.slack.com/apps and click **Create New App** → **From scratch**
- Name it (e.g. "Claude Code") and select your workspace

### 2. Add Bot Scopes

- Go to **OAuth & Permissions** in the left sidebar
- Under **Bot Token Scopes**, add:
  - `channels:read`
  - `channels:history`
  - `chat:write`
  - `users:read`

### 3. Install the App

- Click **Install to Workspace** at the top of the OAuth & Permissions page
- Authorize when prompted

### 4. Copy your Bot Token

- After installing, copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 5. Find your Team ID

- Open Slack in a browser
- Your URL will look like: `https://app.slack.com/client/T01ABCDEF/C01234...`
- The `T...` portion is your Team ID

### 6. Add to `.mcp.json`

```json
"slack": {
  "command": "npx",
  "args": ["-y", "@anthropic/mcp-slack@latest"],
  "env": {
    "SLACK_BOT_TOKEN": "{YOUR_XOXB_TOKEN}",
    "SLACK_TEAM_ID": "{YOUR_TEAM_ID}"
  }
}
```
