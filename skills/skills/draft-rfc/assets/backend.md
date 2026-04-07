# Backend RFC Rules

These rules apply when generating a **backend-focused** RFC. They define what to emphasize, what to omit, and how to structure backend-specific content.

## Focus and Scope

- The RFC specifies what the backend provides. UI designs are inputs for inferring API needs, not specifications for frontend components.
- Never write UI implementation detail — instead write "UI is unblocked to implement X once endpoint Y is available."
- When reviewing any design (Figma node or image):
  - Extract what data the UI needs: inputs, filters, displayed fields, async/polling flows, pagination, empty/error states
  - Do NOT describe how to build the UI components themselves
  - Pay attention to frame/layer names and annotations — designers often label fields in ways that map directly to API field names
  - Note any states visible in the design (loading, empty, error) as these imply backend response contracts

## Codebase Exploration

Explore these repos when relevant to the feature. Read only the `AGENTS.md` for repos clearly relevant to the feature.

| Repo | Purpose |
|------|---------|
| `api` | REST API service |
| `runners` | Celery/worker job service |
| `ui` | Frontend (React) — read only to understand existing API call patterns, not to plan UI work |
| `core` | Core shared library |
| `wizard` | Wizard service |
| `authz` | Authorization service |
| `orbit` | Orbit library |
| `feature-flags` | Feature flag service |
| `galileo-python` | Python SDK |
| `galileo-js` | JavaScript/TypeScript SDK |
| `aperture` | Aperture service |
| `protect` | Protect service |
| `e2e-testing` | End-to-end test suite |
| `deploy` | Deployment configuration |
| `galileo-infra-automation` | Infrastructure automation |
| `load-test` | Load testing |

When exploring, look for:
- Existing data models, schemas, and DB tables to be extended
- Existing API endpoints to be modified or that serve as patterns
- Existing runner tasks or Celery jobs to be modified
- SDK functions to be added or modified
- Feature flag patterns (in `feature-flags` repo) if gating is needed
- Auth/permission models (in `authz` repo) if new resources are introduced
- Deployment config (in `deploy`) for any new services or infrastructure

## Work Breakdown Disciplines

Include the following sections in each iteration's work breakdown as applicable:

- **Backend** — endpoints, data model changes, runner/Celery task changes
- **Python SDK** — public functions to add or modify
- **TypeScript SDK** — SDK changes
- **UI dependency note** — what the UI needs from this iteration's backend work (not UI implementation)
- **Feature Flags** — new flags to gate rollout
- **Auth/Permissions** — new resource types, permission checks, RBAC changes in authz
- **Infrastructure / Deploy** — new services, environment variables, Helm chart updates
- **Data Science** — prompt engineering, model changes, template updates

## Style Guidelines

- Technical, direct, with concrete endpoint names/field names/class names wherever you can infer them from the codebase
- Avoid vague language like "handle the data" — prefer "POST /scorers/validate/llm accepts chain_poll_template and returns metrics_experiment_id"
- Iteration sequencing matters: each iteration should be independently deployable
- Backend work that unblocks UI should be called out explicitly via the "UI dependency note"
- Shared tasks (like refactoring a DAO method) should be placed in the earliest iteration that needs them
- Estimates: express as ranges in days per discipline. Always note what can run in parallel.
- Be honest about unknowns: write `[TBD — needs investigation]` and add to Open Questions rather than fabricating field names or endpoint paths

## Checklist

- [ ] Feature flags: consider whether any iterations should be gated for gradual rollout
- [ ] Auth/permissions: if new resource types or actions are introduced, consider whether `authz` changes are needed
- [ ] E2E tests: reference the `e2e-testing` repo for any new user-facing flows
- [ ] Load testing: call out any endpoints or flows that should be load tested (especially bulk operations or async jobs)
- [ ] Excluded architectural paths: if the user specified approaches to avoid, note why they were excluded
