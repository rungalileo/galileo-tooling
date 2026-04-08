# Astra

Galileo dev bot.

Runs agent-enabled commands in a remote container.

## Commands

- `review`: PR review

## Implementation

A CLI wrapping Claude Agent SDK workflows with Galileo-specific skills, tools and development environment setup.

The CLI is activated through an asynchronous command pipeline and runs in sandbox containers via GCP Cloud Tasks.

## Why the name Astra?

Astra comes from the Latin word for “stars,” a nod to Galileo Galilei and his work observing the heavens.

The name reflects Galileo’s legacy of careful observation, discovery, and turning what we see into evidence.
