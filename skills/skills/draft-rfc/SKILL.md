---
name: draft-rfc
description: Generate a backend-focused RFC for the technical implementation of a product feature. Takes a problem description, optional PRD file, per-requirement Figma node links or image files, proposed solution details, architectural constraints, and any additional context to produce a structured RFC matching Galileo's RFC format and style.
disable-model-invocation: true
---

# Draft RFC for Technical Implementation (Backend-Focused)

Generate a rough draft RFC given a product or engineering initiative.

This is a **backend-focused RFC**. The goal is to specify the API contracts, data models, runner jobs, SDK changes, and infrastructure needed to enable the product. UI designs and PRDs are used to understand what data the frontend needs — not to dictate UI implementation. The RFC should tell a frontend engineer exactly what endpoints and payloads are available so they can build the UI independently.

**Input:** `$ARGUMENTS` — a description of the feature/initiative. The user may also provide:
1. A high-level description of the problem
2. A PRD as a `.md` file path
3. A list of product requirements, each optionally paired with a Figma node link or local image file
4. A high-level description of the proposed solution + repos/files to look at
5. Architectural limitations or paths to avoid
6. Any additional context

### Input Format for Requirements + Figma

Requirements with associated designs should be structured like this:

```
Requirement: Users can filter log streams by date range
Figma: https://www.figma.com/design/abc123/MyFile?node-id=1-23

Requirement: Results display in a paginated table
Figma: https://www.figma.com/design/abc123/MyFile?node-id=4-56

Requirement: Export results as CSV
(no Figma — text only)
```

Each Figma link should be a **node-level link** (containing `node-id` in the URL), scoped to the specific frame for that requirement. File-level links (no `node-id`) will be flagged as ambiguous and the agent will ask the user to provide a node-level link before proceeding.

---

## Phase 1: Gather Input

Parse `$ARGUMENTS` to extract:
- **Problem description**: What is the current state and what's missing?
- **PRD file path** (if provided): A `.md` file with product requirements — read it now with the `Read` tool
- **Requirements list**: Parse each requirement and its associated Figma link or image file (if any)
- **Proposed solution**: High-level technical direction, repos, and files to examine
- **Architectural constraints**: What approaches to avoid and why
- **Additional context**: Any other relevant information

### Handling Figma links

For each requirement that has an associated Figma URL:
- Check whether the URL contains a `node-id` query parameter
- **If `node-id` is present**: proceed — call `mcp__figma__get_figma_data` with the URL and pass the `node-id` value as the `nodeId` argument. Do this when processing each requirement in Phase 3, not all upfront.
- **If `node-id` is absent** (file-level link): do NOT fetch it. Flag this to the user immediately: "The Figma link for requirement '[X]' is a file-level link and may include unrelated designs. Please share a node-level link (right-click the frame in Figma → Copy link to selection) and re-run."

For requirements with a **local image file**: read it with the `Read` tool when processing that requirement.

When reviewing any design (Figma node or image):
- Extract what data the UI needs: inputs, filters, displayed fields, async/polling flows, pagination, empty/error states
- Do NOT describe how to build the UI components themselves
- Pay attention to frame/layer names and annotations — designers often label fields in ways that map directly to API field names
- Note any states visible in the design (loading, empty, error) as these imply backend response contracts

---

## Phase 2: Explore the Codebase

Based on the proposed solution description and any repos/files mentioned:

1. Read the `AGENTS.md` in each relevant repo to understand conventions and architecture. Use the current working directory and any repo paths the user mentioned. If the user didn't specify paths, infer from the workspace or ask. Common Galileo repos (if present) include:
   - `api` — REST API service
   - `runners` — Celery/worker job service
   - `ui` — Frontend (React) — read only to understand existing API call patterns, not to plan UI work
   - `core` — Core shared library
   - `wizard` — Wizard service
   - `authz` — Authorization service
   - `orbit` — Orbit library
   - `feature-flags` — Feature flag service
   - `galileo-python` — Python SDK
   - `galileo-js` — JavaScript/TypeScript SDK
   - `aperture` — Aperture service
   - `protect` — Protect service
   - `e2e-testing` — End-to-end test suite
   - `deploy` — Deployment configuration
   - `galileo-infra-automation` — Infrastructure automation
   - `load-test` — Load testing
   - Only read the `AGENTS.md` for repos clearly relevant to the feature

2. Explore specific files, services, models, and endpoints mentioned in the proposed solution. Look for:
   - Existing data models, schemas, and DB tables to be extended
   - Existing API endpoints to be modified or that serve as patterns
   - Existing runner tasks or Celery jobs to be modified
   - SDK functions to be added or modify
   - Feature flag patterns (in `feature-flags` repo) if gating is needed
   - Auth/permission models (in `authz` repo) if new resources are introduced
   - Deployment config (in `deploy`) for any new services or infrastructure

3. Use `Glob` and `Grep` to find relevant code:
   - Search for model class names, endpoint paths, or queue names
   - Look for existing patterns (e.g., how similar features were implemented)

4. Take notes on:
   - Which repos are affected
   - What currently exists vs. what needs to be built
   - Any tricky integration points between services

---

## Phase 3: Synthesize and Draft the RFC

Process each requirement in order. For each requirement that has a Figma node link, call `mcp__figma__get_figma_data` now (scoped to that node) and use the result to inform the API contract for that requirement. Then synthesize everything into a structured RFC document.

Follow this format exactly, matching the style and level of detail of Galileo RFCs:

---

```markdown
RFC: [Feature Name] [Project Codename if applicable]
Owner: [Leave blank — to be filled in]
Status: proposed
Last Updated: [Today's date]

## Introduction

[2–4 sentences describing the current state and what this RFC proposes to change. Be specific about current limitations. Mirror the intro style: "This document outlines an implementation of X. Currently, we support Y. We'd like to extend/add Z."]

### Goals
[Bulleted list of what this feature enables. Keep each item concrete and user-facing where possible.]

## Motivation

[1–2 sentences + a link placeholder for any related product doc or north star proposal. Keep it brief — the Introduction should do the heavy lifting.]

## Implementation

> Note: All estimates include ~25% buffer to account for planning, bug fixes, E2E/integration testing, and inter-team coordination.

### Iteration 1: [Name — the smallest shippable unit]
**Begin Work:** [Date or TBD]
**Delivered to Prod:** [Date or TBD]
**Estimate Notes:** [Explain what unblocks what, parallelism opportunities, coordination dependencies. Call out when backend work is complete enough to unblock UI development.]

#### Work Breakdown

**Backend [X days]**
- [List specific backend tasks with concrete names: endpoint paths, model field names, class names, queue names.]
- API:
  - New/modified endpoint: `METHOD /path/to/endpoint`
    - Request body: [field: type — description]
    - Response: [field: type — description]
    - Behavior: [what this endpoint does, any async/polling pattern]
  - [Repeat for each endpoint]
- Data model changes:
  - [New fields, new tables, enum values — be specific]
- Runner/task changes:
  - [New Celery tasks, modified job flows, queue names]

**Python SDK [X days]**
- [Specific public functions to add or modify, with rough signatures and docstring-level description]

**TypeScript SDK [X days]**
- [Specific SDK changes]

**UI dependency note:**
- [1–3 bullets summarizing what the UI needs from this iteration's backend work. Example: "UI can begin building the scorer creation flow once the POST /scorers/llm endpoint is available." Do NOT describe the UI implementation.]

**Feature Flags [X days]** *(if applicable)*
- [Any new flags to gate the rollout, which service they live in]

**Auth/Permissions [X days]** *(if applicable)*
- [New resource types, permission checks, RBAC changes in authz]

**Infrastructure / Deploy [X days]** *(if applicable)*
- [New services, environment variable changes, Helm chart updates, deploy config]

**Data Science [X days]** *(if applicable)*
- [Prompt engineering, model changes, template updates]

---

### Iteration 2: [Name]
[Repeat structure above]

---

[Continue for each subsequent iteration. Group by dependency order — each iteration should be independently deployable. Later iterations can be lighter on detail. Always include a "UI dependency note" so frontend engineers know when they are unblocked.]

---

## Testing Plan

- Each iteration should be fully tested on dev before promotion to prod
- Each iteration should have a corresponding UI E2E test (in `e2e-testing` repo)
- SDK changes should have E2E tests (Python and TypeScript)
- Load testing considerations: [note any endpoints or flows that should be load tested, especially bulk operations or async jobs]
- Explicit sign-off required before each prod release:
  - Eng: [Owner name TBD]
  - Data Science: [DS contact TBD]
  - Product: [PM contact TBD]

## Signoff & Comments

| Name | +1/-1 | Comments |
|------|-------|----------|
| | | |
| | | |
| | | |

## Open Questions

- [List any open questions, ambiguities, or decisions that still need to be made. Be specific — "Need to clarify X" is better than "TBD".]
```

---

## Phase 4: Output and Guidance

1. Write the RFC draft to `/tmp/rfc-draft-[kebab-case-feature-name].md`
   - Use the `Write` tool
   - Tell the user the full path so they can open it

2. After writing, output a brief summary to the user:
   - Where the file was written
   - A bulleted list of the iterations you identified and their scope
   - A bulleted list of **open questions** you flagged that the user should address before sharing the RFC
   - Any areas where you had to make assumptions due to missing context — ask the user to verify these
   - Any Figma links that were skipped due to being file-level (remind the user to provide node-level links)

---

## Important Notes

- **Backend-focused**: The RFC specifies what the backend provides. UI designs are inputs for inferring API needs, not specifications for frontend components. Never write UI implementation detail — instead write "UI is unblocked to implement X once endpoint Y is available."
- **Figma node links are per-requirement**: fetch each node only when processing the requirement it belongs to. Never fetch a Figma file without a `node-id` — flag it to the user instead.
- **Match the Galileo RFC style**: technical, direct, with concrete endpoint names/field names/class names wherever you can infer them from the codebase. Avoid vague language like "handle the data" — prefer "POST /scorers/validate/llm accepts chain_poll_template and returns metrics_experiment_id".
- **Iteration sequencing matters**: each iteration should be independently deployable. Backend work that unblocks UI should be called out explicitly via the "UI dependency note". Shared tasks (like refactoring a DAO method) should be placed in the earliest iteration that needs them.
- **Estimates**: express as ranges in days per discipline (Backend, UI, SDK, DS). Always note what can run in parallel.
- **Be honest about unknowns**: where codebase exploration doesn't give enough to be specific, write `[TBD — needs investigation]` and add it to Open Questions. Do not fabricate field names or endpoint paths.
- **Avoid excluded architectural paths**: if the user specified approaches to avoid, do not include them and briefly note why they were excluded in the relevant section.
- **Feature flags**: consider whether any iterations should be gated behind a feature flag for gradual rollout.
- **Auth/permissions**: if new resource types or actions are introduced, consider whether `authz` changes are needed.
- **E2E tests**: reference the `e2e-testing` repo for any new user-facing flows that need coverage.
- **Repo paths**: derive repo paths from the user's workspace context (additional working directories, CWD, or paths explicitly mentioned in the input). Do not hardcode paths.
