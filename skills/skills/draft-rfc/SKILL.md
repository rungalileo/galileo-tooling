---
name: draft-rfc
description: Generate an RFC for the technical implementation of a product feature. Takes a problem description, optional PRD file, per-requirement Figma node links or image files, proposed solution details, architectural constraints, RFC type (default: backend), and any additional context to produce a structured RFC matching Galileo's RFC format and style.
disable-model-invocation: true
---

# Draft RFC for Technical Implementation

Generate a rough draft RFC given a product or engineering initiative.

**RFC type** defaults to **backend-focused** unless the user specifies otherwise (e.g. `type: ui`). Read the rules file for the selected type from `assets/<type>.md` (e.g. `assets/backend.md`) now using the `Read` tool — it defines scope, codebase exploration guidance, work breakdown disciplines, and style rules for that RFC type.

**Input:** `$ARGUMENTS` — a description of the feature/initiative. The user may also provide:
1. A high-level description of the problem
2. A PRD as a `.md` file path
3. A list of product requirements, each optionally paired with a Figma node link or local image file
4. A high-level description of the proposed solution + repos/files to look at
5. Architectural limitations or paths to avoid
6. RFC type (e.g. `type: backend` or `type: ui`) — defaults to `backend`
7. Any additional context

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

Read `assets/backend.md` (or the relevant type file) using the `Read` tool before proceeding.

Parse `$ARGUMENTS` to extract:
- **Problem description**: What is the current state and what's missing?
- **PRD file path** (if provided): A `.md` file with product requirements — read it now with the `Read` tool
- **Requirements list**: Parse each requirement and its associated Figma link or image file (if any)
- **Proposed solution**: High-level technical direction, repos, and files to examine
- **Architectural constraints**: What approaches to avoid and why
- **RFC type**: `backend` (default) or another type — determines which rules file to apply
- **Additional context**: Any other relevant information

### Handling Figma links

For each requirement that has an associated Figma URL:
- Check whether the URL contains a `node-id` query parameter
- **If `node-id` is present**: proceed — call `mcp__figma__get_figma_data` with the URL and pass the `node-id` value as the `nodeId` argument. Do this when processing each requirement in Phase 3, not all upfront.
- **If `node-id` is absent** (file-level link): do NOT fetch it. Flag this to the user immediately: "The Figma link for requirement '[X]' is a file-level link and may include unrelated designs. Please share a node-level link (right-click the frame in Figma → Copy link to selection) and re-run."

For requirements with a **local image file**: read it with the `Read` tool when processing that requirement.

---

## Phase 2: Explore the Codebase

Follow the codebase exploration guidance in the rules file loaded in Phase 1 (`assets/<type>.md`). Use `Glob` and `Grep` to find relevant code. Take notes on:
- Which repos are affected
- What currently exists vs. what needs to be built
- Any tricky integration points between services

---

## Phase 3: Synthesize and Draft the RFC

Process each requirement in order. For each requirement that has a Figma node link, call `mcp__figma__get_figma_data` now (scoped to that node) and use the result to inform the API contract for that requirement. Then synthesize everything into a structured RFC document.

Read `assets/template.md` using the `Read` tool and follow that format exactly, matching the style and level of detail of Galileo RFCs. Apply all style rules and discipline-specific guidance from the rules file (`assets/<type>.md`).

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
