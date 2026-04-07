---
name: rfc-to-tickets
description: Parse a backend RFC implementation plan and create Shortcut tickets — one detailed backend ticket per logical work unit per iteration. Takes an RFC file path, epic name or ID, and team name.
disable-model-invocation: true
---

# Backend RFC → Shortcut Tickets

Parse a backend RFC and create Shortcut stories for each backend work item in the implementation plan.

**Input:** `$ARGUMENTS` — provide in this order:

```
<RFC file path>  <epic name or ID>  <team name>
```

Example:
```
/tmp/rfc-draft-metrics-testing-on-datasets.md "Metrics Testing on Datasets" "Platform"
```

---

## Phase 1: Parse Arguments

From `$ARGUMENTS`, extract:
- **rfc_path**: path to the RFC markdown file. If not provided, check whether the user has a file open in the IDE (it will appear as an `ide_opened_file` in context) and use that path. If neither is available, ask the user for the path before proceeding.
- **epic_name**: name or numeric ID of the Shortcut epic
- **team_name**: the Shortcut team name

If `epic_name` or `team_name` is missing, tell the user what's needed and stop.

---

## Phase 2: Read the RFC

Read the RFC file at `rfc_path` using the `Read` tool.

Parse out the following for each iteration:
- **Iteration name** (e.g. "Iteration 0: Prerequisite — Streaming Results…")
- **Delivered to Prod date** (the `**Delivered to Prod:**` field — use as the due date for all tickets in that iteration)
- **Backend work breakdown** — all tasks under `**Backend**` subsections (both API and Runners sub-sections if present)
- **Estimate notes** — the `**Estimate Notes:**` field

Also note:
- The feature flag name if present (add to the relevant backend ticket description)
- Any open questions relevant to specific tickets
- **Inter-iteration dependencies** — note which iterations depend on others (e.g. "depends on Iter 0", "can run in parallel with Iter 1"). Record these per-iteration so they can be surfaced in ticket descriptions.
- **Testing Plan section** — parse the explicit test requirements per iteration (integration tests, E2E tests, load tests, sign-off requirements). These will be used to create dedicated testing tickets.
- **Begin Work date** on the first iteration — used to set the epic's `planned_start_date`.

---

## Phase 3: Resolve Epic and Team

1. **Find the epic:**
   - If `epic_name` is a number, call `mcp__shortcut__epics-get-by-id` with that ID.
   - Otherwise, call `mcp__shortcut__epics-search` with `epic_name` and pick the best match. Tell the user what you found.
   - Extract the epic's numeric ID.
   - After resolving the epic, update it using `mcp__shortcut__epics-update`:
     - **`deadline`**: the latest end date across the entire RFC including UI and testing. If the RFC has a "Revised Timeline with UI" table or equivalent, use the latest "Prod (both)" date. Fall back to the latest backend `Delivered to Prod` date if no combined timeline exists.
     - **`planned_start_date`**: the `Begin Work` date from the earliest iteration (Iteration 0 if present, otherwise Iteration 1).
   - Tell the user what dates were set and where they came from.

2. **Find the team:**
   - Call `mcp__shortcut__teams-list`.
   - Find the team whose name matches `team_name` (case-insensitive substring match).
   - Extract the team ID.
   - If no match, list available teams and ask the user to pick one.

---

## Phase 4: Plan the Tickets

Before creating anything, plan all tickets and print them grouped by iteration. For each ticket show: number, title, type (`feature`/`chore`/`bug`), and target date. Example format:

```
**Iteration 0 — Streaming Results for Log Record Validation (Target: 2026-04-18)**
1. Fix `stream_metrics` and `scorer_config` fields in LLM/code scorer job requests [chore]
2. Verify v2 streaming path end-to-end in `ScorerJobsService` [chore]
3. [Testing] Iter 0 — Integration test for v2 streaming path [chore]

**Iteration 1 — Metric Ground Truth on Datasets (Target: 2026-04-18)**
4. Relax column allowlist in `DatasetService._validate_dataset_table()` [chore]
...
```

Total: N tickets across M iterations.

### Ticket Planning Rules

**Backend tickets (detailed):**

Create one ticket per distinct logical work unit in the backend breakdown. Each ticket should cover a coherent, independently shippable chunk of work. Examples of what constitutes one ticket:
- Adding a field or flag to an existing method/schema
- Creating a new API endpoint
- Creating a new service method or helper
- Verifying or fixing an existing code path
- Adding/updating integration tests for a specific service

Do NOT split trivially small related changes into separate tickets (e.g. adding two fields to the same function = one ticket). Do NOT lump large, independent pieces of work into one ticket.

**Testing tickets (one per iteration with explicit test requirements):**

If the RFC's Testing Plan section calls out specific test work for an iteration (integration tests, E2E tests, load tests), create one `chore`-type ticket for that iteration's testing work:
- Title: `[Testing] <Iteration name>`
- Description: list the specific test scenarios from the Testing Plan, plus any sign-off requirements mentioned
- Due date: same as the iteration's `Delivered to Prod` date

Only create a testing ticket if the RFC explicitly specifies test work for that iteration — don't invent generic "write tests" tickets.

**Story type classification:**
- `"chore"` → infrastructure, refactoring, test coverage, configuration, relaxing/removing validations, data migrations, feature flag work
- `"bug"` → fixing something confirmed broken (RFC explicitly marks it as a bug or "must fix")
- `"feature"` → new endpoints, new data model capabilities, new service methods, new job flows

**Due date:**

`mcp__shortcut__stories-create` does not have a deadline field. Include the target date in the ticket description instead (e.g. `**Target:** 2026-04-18`).

**Description format for backend tickets:**

```
**Iteration:** <Iteration name>
**Target:** <Delivered to Prod date>
**Dependencies:** <e.g. "Depends on Iter 0 landing first" or "Can start in parallel with Iter 1" — omit if none>

<2–4 sentences: what this ticket covers, why it matters, and key implementation details from the RFC. Name the actual files, classes, endpoints, or fields involved. Don't copy the RFC verbatim — distill what this ticket needs.>

**Acceptance criteria:**
- <1–4 concrete, checkable criteria specific to this ticket>

**RFC reference:** <RFC feature name>
```

---

## Phase 5: Confirm and Create

After printing the plan, ask the user: **"Ready to create these N tickets? (yes/no)"**

If confirmed, create each ticket using `mcp__shortcut__stories-create`:
- `name`: ticket title
- `description`: formatted as above
- `type`: `"feature"`, `"chore"`, or `"bug"`
- `epic`: resolved epic numeric ID
- `team`: resolved team ID
- Do **not** set `owner` — leave unassigned

Create tickets in iteration order. After each is created, print: `✓ [sc-XXXX] <ticket name> — <URL>`

If any creation fails, print the error and continue with the remaining tickets. Note failed tickets in the Phase 6 summary.

---

## Phase 6: Summary

Print a summary table after all tickets are created (truncate ticket names to ~50 chars):

```
| sc-ID | Title (truncated) | Type | Iteration | Target |
|-------|-------------------|------|-----------|--------|
| sc-123 | Fix stream_metrics in scorer job requests | chore | Iter 0 | 2026-04-18 |
...
```

Then print two follow-up lists:
- **Open questions to resolve:** tickets whose descriptions reference open questions from the RFC — note the question and which ticket it affects.
- **Failed tickets (if any):** tickets that were not created due to errors, with the error message.

---

## Important Notes

- **Leave all tickets unassigned** — do not set `owner`.
- **Don't over-ticket** — related small changes in the same file/function belong in one ticket.
- **Don't under-ticket** — each major independent backend deliverable (new endpoint, new service method, new data model change) deserves its own ticket.
- **Be specific in descriptions** — name the actual files, classes, and methods from the RFC. Vague descriptions like "implement the backend" are not acceptable.
- **Feature flag work** → `chore` type, placed in the earliest iteration that needs it.
- **Prerequisite / Iteration 0 work** → treat as its own group with its own due date.
- **Runners and API are both backend** — create separate tickets for Runners work vs. API work when they are clearly distinct deliverables within an iteration.