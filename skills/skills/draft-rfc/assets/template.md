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
