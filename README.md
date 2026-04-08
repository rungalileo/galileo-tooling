# Galileo Tooling

Shared AI tooling for the Galileo platform — skills, rules, memory, and MCP configs.

## Quick Start

```bash
git clone https://github.com/rungalileo/galileo-tooling.git
cd galileo-tooling
./setup.sh
```

## Structure

```
galileo-tooling/
├── skills/                    # Vercel skills framework package
│   ├── skills/                # Individual skills (SKILL.md files)
│   └── package.json           # Skills metadata
├── memory/                    # Shared team memory
├── rules/                     # Shared rules (.claude, cursor, etc.)
├── mcp/                       # MCP server configs
├── setup.sh                   # Interactive setup script
├── AGENTS.md                  # Setup guide
├── env.sample                 # API token template
└── README.md
```

## Using with service repos

This repo is designed to work alongside your existing Galileo service repos (api, runners, ui, orbit, etc.). Clone it as a sibling:

```
~/galileo/
├── galileo-tooling/    # this repo
├── api/
├── runners/
├── ui/
├── orbit/
└── ...
```

After running `./setup.sh`:

- **Skills** are installed at **project level** inside `galileo-tooling/` (under `.agents/skills/` and symlinked into `.claude/skills/`, etc. for each detected agent). They are only available when working inside this directory.
- **Rules** are symlinked from `~/.claude/shared-rules` → `<repo>/rules/`, making them available in every repo.
- **MCP servers** are merged into `~/.claude.json`, making them available in every repo.

If you want repo-specific skills or rules in addition to the shared ones, add them to that repo's own `.claude/skills/` or `.cursor/rules/` directory as usual. They layer on top of the shared set.

## Updating

```bash
git -C ~/galileo-tooling pull
```

## Composing with other skills

```bash
npx skills add clickhouse/agent-skills
npx skills add vercel-labs/agent-skills
```
