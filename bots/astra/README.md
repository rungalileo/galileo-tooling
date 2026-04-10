# Astra

Galileo dev bot.  Runs agent-enabled commands in a remote container.

<img src="assets/astra-logo-800x800.png" alt="Astra logo" width="200">

## Commands

- `review`: PR review

## Implementation

A CLI wrapping Claude Agent SDK workflows with Galileo-specific skills, tools and development environment setup.

The CLI is activated through an asynchronous command pipeline and runs in sandbox containers via GCP Cloud Tasks.

## Directory Structure

```
astra/
├── assets/                  # Logo and static assets
├── deployment/              # Deployment and provisioning scripts
└── job/                     # Main application package
    ├── Dockerfile
    ├── pyproject.toml
    ├── src/astra/           # Application source code
    └── tests/
```

## Why the name Astra?

Astra comes from the Latin word for “stars,” a nod to Galileo Galilei and his work observing the heavens.

The name reflects Galileo’s legacy of careful observation, discovery, and turning what we see into evidence.
