---
title: Career Command Center (CCC) Operator UI PRD
status: draft
date: 2026-08-08
owner: Nate Walker (@nwalker85)
system: Ultradex / CCC
---

# Career Command Center (CCC) Operator UI: Product Requirements Document

## 1. Summary

Career Command Center (CCC) is the operator UI over Ultradex, an event-sourced, CQRS job-search platform (commands to events to projections). Ultradex exposes 9 read queries and 9 write commands through its TypeScript SDK. The CCC glass in production today uses 2 of those 9 queries (`listOpportunities`, `listRelationships`) and 0 of the 9 commands. It is a read-only two-table viewer built around hash-anchor sections in a single route. This PRD defines the work to turn it into the full operator surface: every read query bound to a screen, every write command reachable through one governed, auditable interaction pattern, and every governance concept the platform is built on (asynchronous commands, approval contracts, evidence classification, freshness, receipts) represented honestly rather than implied away.

**Who this is for.** Nate Walker, sole operator of Ultradex today. There is no multi-tenant auth model and none is proposed here (see Non-goals, OOS-3).

**What problem this solves.** Ultradex's value proposition is a governed, auditable job-search workflow: every write is a command that produces an operation, an event trail, and a receipt; every external effect (an outreach send) is gated by an approval contract; every fact has a classification and a freshness stamp. None of that is visible today. The operator cannot create an application, cannot see an outreach pipeline, cannot watch a command resolve, cannot inspect a receipt. The governance the backend enforces is invisible, which defeats the point of building it.

**What "done" looks like.** All 9 read queries are bound to routed screens (list, detail, or contextual panel as appropriate to the entity). All 9 write commands are reachable through a single governed-write pattern built once and reused everywhere, with every terminal outcome (`completed` / `failed` / `refused`) rendered as a distinct, honest state, not just "success or error." Not every command will *succeed* on submission today; four refuse for lack of a bound adapter (scorer, source connector, relationship resolver, delivery transport), and the UI's job is to make that refusal legible as the system working correctly, not broken.

**Lead with the blocker.** Two of the highest-leverage backend fixes identified in this PRD, `applications.create` (BE-6, fixes the empty Applications vertical) and `outreach.cancel` (BE-7, fixes the outreach dead end below), both require adding a command to the shared `ravenhelm_contracts` package. That package's release state is broken: production Ultradex depends on `ravenhelm_contracts` 0.3.0, but `main` in the source repo is 0.1.0 with no jobsearch contracts at all, five versions diverge across five unmerged feature branches, and the git worktree that backed the exact 0.3.0 checkout lives in `/private/tmp` and is marked `prunable`; that checkout is effectively gone. BE-6 and BE-7 cannot be scoped, let alone started, until this is resolved. This is Nate's decision alone (see section 11.1); no branch is recommended here.

**Also load-bearing to read before building anything.** Two product gaps are severe enough to call out at the top rather than bury in a backlog:

- **The outreach dead end.** `outreach.approve` requires state `pending_approval` and sets it to `approved`, permanently; a second approve call refuses (`outreach_not_pending_approval`, `jobsearch_executors.py:794-803`). `outreach.send` requires an unexpired approval; the window is a hardcoded 24 hours. There is no revoke and no cancel command. Once the window lapses, the record is stranded: unsendable and un-reapprovable, forever. Nobody has hit this yet because outreach has never run in this system's life (0 rows). The first approval left overnight will discover it.
- **No command creates an Application.** The stage FSM (`draft` to `applied` to `screening` and onward) is real, enforced server-side, and has a working transition command. Nothing originates a row. That is the entire reason the `applications` table has 0 rows today, and no UI change fixes it.

## 2. Context and current state

### 2.1 Verified system picture

| Piece | Fact |
|---|---|
| API | uvicorn `api.main:app`, `127.0.0.1:8000`, worktree `~/var/worktrees/ultradex-dashboard-runtime`, branch `local/dashboard-runtime-main` |
| Glass | Vite dev `127.0.0.1:5175`, worktree `~/var/worktrees/ultradex-ccc-glass`, branch `feat/ccc-local-svelte-glass` |
| GraphQL | `POST /api/graphql`, operator Bearer token |
| Postgres | container `ultradex-postgres`, db `ultradex`, 17 tables |
| Also running | `ultradex-redis` (6379), `ultradex-nats` (4222), and a queue worker, PID 50714, `python -m core.jobsearch_worker` |

### 2.2 Live table counts (verified against the live DB, 2026-08-07)

| Table | Count |
|---|---|
| opportunities | 6 |
| applications | 0 |
| relationships | 23 |
| outreach | 0 |
| approvals | 0 |
| evidence_refs | 7 |
| commands | 3 |
| receipts | 3 |
| operations | 11 (6 completed, 5 failed, 0 pending/running) |

**Applications, outreach, and approvals are all empty.** The entire outreach and approval governance chain, the part of the system whose whole purpose is auditable external action, has never executed once.

### 2.3 Command history: the whole history, all 3 rows

| Command | Timestamp | Outcome |
|---|---|---|
| `workspace.initialize` | 2026-08-03 14:22 | (non-CCC operation) |
| `opportunities.create` | 2026-08-03 14:27 | failed, `executor_failure` |
| `opportunities.create` | 2026-08-03 14:35 | succeeded |

Only two distinct command types have ever been submitted, out of 9 available. **Most of what looks like real data in this system is seeded fixtures, not command-produced.** The 6 opportunities, 23 relationships, and 7 evidence refs predate any command execution; only one opportunity was actually created by a command, and it was the second attempt after a first one failed.

### 2.4 The worker is running; the adapters are not bound

A prior review step incorrectly concluded no worker binding exists in production. **A worker is running.** It constructs `JobSearchExecutor(session, ReceiptIssuer.from_env())` with **no adapters bound** (`core/jobsearch_worker.py:145`). Four commands hit a guard on submission and refuse cleanly:

| Command | Guard | Location |
|---|---|---|
| `sources.ingest` | `source_adapter_unbound` | `jobsearch_executors.py:534` |
| `opportunities.score` | `scorer_unbound` | `jobsearch_executors.py:637` |
| `relationships.sync` | `relationship_resolver_unbound` | `jobsearch_executors.py:714` |
| `outreach.send` | `delivery_transport_unbound` | `jobsearch_executors.py:883` |

The failure mode is a clean, governed refusal, not a hang or a crash: the command is accepted, an `Operation` row is persisted, a receipt is written with `status=refused` and a machine-readable `reasonCode`. This is the system working as designed, and it is the single best thing this UI can be built to display well. The remaining 5 commands can fully succeed today given real input: `opportunities.create`, `applications.transition` (no row to transition against yet), `outreach.prepare`, `outreach.approve`, `evidence.export`.

### 2.5 The gap, stated plainly

| | Today | Target of this PRD |
|---|---|---|
| Read queries used | 2 of 9 | 9 of 9 |
| Write commands reachable | 0 of 9 | 9 of 9 through the governed-write pattern (4 refuse today for lack of bound adapters, BE-8, out of scope) |
| Applications, outreach, operations, evidence | Entirely unsurfaced | Full screens, per section 7 |
| Any write path | None | One pattern, section 8, reused by every write screen |

## 3. Goals and non-goals

### 3.1 Goals

- Bind all 9 SDK read queries to routed, addressable screens.
- Make all 9 SDK write commands reachable through a single, reused governed-write interaction pattern.
- Represent every governance concept accurately, including where the system currently cannot do the thing the UI might imply it can (message preview, staleness, risk-tier enforcement).
- Turn the four `*_unbound` refusals from apparent failures into a designed, legible feature.
- Make the outreach approval dead end and the missing application-origination command visible in the product itself, so nobody discovers them by accident.
- Fix the known error-detail bug (the glass currently renders only `err.message`, discarding `UltradexGraphQLError.errors[]`, `UltradexHttpError.details`, `UltradexSchemaError.issues`) before building anything on top of it.

### 3.2 Non-goals (OOS-1 through OOS-9)

| ID | Out of scope | Why |
|---|---|---|
| OOS-1 | Kanban board for applications | 0 live rows and a linear FSM; a 9-column empty board is worse than a filterable table. |
| OOS-2 | Persistent, cross-page operation tray | A page-scoped polling store is sufficient for v1. |
| OOS-3 | Real multi-tenant auth UI | Single operator, local-first; tenant/user are deliberate stubs. |
| OOS-4 | API-sourced message preview for outreach | Architecturally impossible: Ultradex never stores outreach message text, only a client-computed `messageCommitment` hash. |
| OOS-5 | Re-approve / extend an expired approval | No such command exists; adding one is Nate-gated (11.2). |
| OOS-6 | Evidence-consumption enforcement | Audit-policy call, not a UI concern (11.4). |
| OOS-7 | Server-side risk-tier enforcement | `read_only`/`internal_write`/`external_effect` are UI design tokens, not enforced anywhere (11.6). |
| OOS-8 | Adapter binding | A separate program (BE-8). |
| OOS-9 | Delegation sub-reason granularity | `DelegationService.validate_delegation` collapses four denial reasons into one boolean. |

## 4. Governance principles

These are the constraints the entire design rests on. A UI that violates any of them actively misrepresents what Ultradex did, which is worse for an auditability platform than shipping no UI at all.

1. **Commands are governed and asynchronous.** Every write returns an `operationId`, not a result. There is no synchronous "save."
2. **Approval contracts gate external effects.** `outreach.send` requires an unexpired approval carrying a `messageCommitment`. The approval's `status` never flips to `expired` or `revoked` server-side; expiry is enforced only reactively at send time. Send-button enablement must be computed from `expiresAt` client-side, never from `status` (FR-OUT-6, risk G1).
3. **Evidence is classified and redaction-bounded.** Show only `redactedSummary`, never a raw `sourceRef`; bind the classification badge to the actual field value.
4. **Freshness is shown honestly, never hidden and never overstated.** Every projection is stamped `fresh`/`lagMs: 0` synchronously today (`jobsearch_executors.py:504-527`), so staleness cannot currently occur. `Operation.freshness` is hardcoded `null` by design (`api/graphql/schema.py:102-104`) and must be excluded from any rollup.
5. **Receipts are the audit trail.** `proofStatus` is always the literal `"server-recorded"`. **Present it plainly, as text, with no lock, shield, or seal iconography.** It means Ultradex recorded that this happened; it is explicitly not a claim of cryptographic verification.

**A UI that misrepresents any of these five principles is worse than no UI.**

## 5. Users and workflows

Single operator: Nate Walker. No role separation, no delegation UI.

1. **Discover and qualify an opportunity.** `/opportunities`, filter by status, open detail, submit `Score`. Refuses today (`scorer_unbound`).
2. **Create an opportunity from evidence.** Supply `employer`, `title`, `sourceEvidenceId`. No evidence picker exists; copy an id from an existing opportunity's Evidence tab. The one command proven to succeed end to end.
3. **Connect a relationship.** `relationships.sync` with `opportunityId` and `dexContactRef`. Refuses today.
4. **Track an application through its stage FSM.** Permanently empty today; no command originates a row.
5. **Prepare, approve, and send outreach.** Message written locally, commitment computed client-side, `outreach.prepare` and `outreach.approve` both succeed today; `outreach.send` refuses. **Outside the 24h window this journey has no continuation.**
6. **Ingest a source.** `/sources`, always refuses today.
7. **Export evidence.** Succeeds, but does not write a reusable `sourceEvidenceId`.
8. **Watch a command resolve; audit what happened.** Every write lands on an `OperationTracker` linking to `/operations/[id]`.
9. **Orient at the start of a session.** `/`, Command home.

## 6. Requirements

Tags: `[TODAY]` buildable now. `[SDK EXT]` thin wrapper on an existing resolver. `[BACKEND]` new server work. `[GATED]` blocked on a Nate decision.

### 6.1 FR-CMD-1..5 — Command home (`/`)

| ID | Requirement | Tag | Acceptance criteria |
|---|---|---|---|
| FR-CMD-1 | Independent per-section load and failure | [TODAY] | If any of the four mount-time calls throws, only that section shows an inline danger banner; the other three still render. No all-or-nothing page failure. |
| FR-CMD-2 | Freshness strip covers the 4 real projections only | [TODAY] | Aggregate computed worst-status-wins from the projection queries. `Operation.freshness` is explicitly excluded; a regression test asserts it is never in the rollup input set. |
| FR-CMD-3 | Needs Attention rail ordering | [TODAY] | Ordered: outreach `pending_approval`; outreach `approved` with `expiresAt` inside 4h (client-computed, never from `status`); opportunities `discovered`; operations `pending`/`running`. |
| FR-CMD-4 | Past-`nextActionAt` rule implemented but unfireable, unit-tested | [TODAY] | Implemented and covered by a unit test using synthetic data, since the field is permanently null today. Must not silently vanish for lack of live data. |
| FR-CMD-5 | Single centered empty state on a fresh install | [TODAY] | If opportunities and operations are both ever-empty, render one centered `EmptyState`, not four empty panels. |

### 6.2 FR-OPP-1..8 — Opportunities

| ID | Requirement | Tag | Acceptance criteria |
|---|---|---|---|
| FR-OPP-1 | 3-value status filter | [TODAY] | Exactly `discovered`, `qualified`, `watching`. `archived` never offered; written by no command. |
| FR-OPP-2 | True-zero vs filtered-zero empty states | [TODAY] | Two visibly different strings; a test asserts they never share copy. |
| FR-OPP-3 | Detail-by-id with fallback flagged for swap | [SDK EXT] / [TODAY] | Preferred `opportunity(id)` (BE-1); fallback `listOpportunities({first:100})` + client find, commented as a fallback that breaks past a few hundred rows. |
| FR-OPP-4 | `classification` bound to the field, not hardcoded | [TODAY] | Renders whatever string the API returns; must not assume `"private"`. |
| FR-OPP-5 | Corrected evidence help text | [TODAY] | Must not ship "or from `evidence.export`'s receipt": that ref passes client-side format validation then refuses server-side with `source_evidence_not_found`. |
| FR-OPP-6 | Plain `Field`, not a picker, for `sourceEvidenceId` | [TODAY] / [GATED] on BE-2 | Free-text field with FR-OPP-5 help text in v1. |
| FR-OPP-7 | `Score` submits through the governed pattern | [TODAY] | Refuses today (`scorer_unbound`) with warning tone and canned copy, not a generic error. |
| FR-OPP-8 | `Sync relationship` submits through the governed pattern | [TODAY] | Same treatment, `relationship_resolver_unbound`. |

### 6.3 FR-APP-1..6 — Applications

| ID | Requirement | Tag | Acceptance criteria |
|---|---|---|---|
| FR-APP-1 | Stage-grouped table, not a kanban | [TODAY] | Table with stage filter and grouped section headers. |
| FR-APP-2 | Empty state names the real cause, offers no fake create | [TODAY] | No "New application" button exists until BE-6 lands. |
| FR-APP-3 | Client-side opportunity join degrades to raw id | [TODAY] | On lookup miss, falls back to the raw `opportunityId`, never a blank cell. |
| FR-APP-4 | Every stage pill routes through the governed pattern | [TODAY] | An illegal transition yields a legible `invalid_application_transition` refusal, not a silent client-side block. |
| FR-APP-5 | End-to-end QA gated on origination | [GATED] on BE-6 | Ship the UI; do not claim end-to-end verification until BE-6 lands. |
| FR-APP-6 | Structurally-empty tabs labeled honestly | [TODAY] | Artifacts, Next Action, and stage `evidenceRef` each show a specific reason, not blank. |

### 6.4 FR-REL-1..2 — Relationships

| ID | Requirement | Tag | Acceptance criteria |
|---|---|---|---|
| FR-REL-1 | Split view with `?open=<id>` deep link | [TODAY] | Direct navigation pre-populates the rail without a click. |
| FR-REL-2 | No bare "New relationship" entry point | [TODAY] | `relationships.sync` requires an `opportunityId`; entry only from an Opportunity's Related tab. |

### 6.5 FR-OUT-1..9 — Outreach

| ID | Requirement | Tag | Acceptance criteria |
|---|---|---|---|
| FR-OUT-1 | Client-side `SubtleCrypto` commitment; submit blocked on hash drift | [TODAY] | Hash recomputed live as the operator types; submit disabled while stale. |
| FR-OUT-2 | Local draft cache with explicit "this browser only" disclosure | [TODAY] | Keyed by `messageCommitment` in `localStorage`, with a persistent visible label stating Ultradex will never store or return the text. |
| FR-OUT-3 | List badges reflect computed expiry, not bare status | [TODAY] | An expired-but-still-`approved` record renders visibly differently from an actionable one. Closes the design draft's internal inconsistency. |
| FR-OUT-4 | `messageCommitment` never hand-typed | [TODAY] | Carried forward programmatically; no text field to retype a sha256. |
| FR-OUT-5 | `ApprovalCountdown` is the single place approval status and expiry are read | [TODAY] | Exactly one component owns the computation; every other screen imports it. |
| FR-OUT-6 | Send enablement bound to the countdown selector, with a regression test | [TODAY] | A record with `status === "approved"` and elapsed `expiresAt` renders `Send` disabled (risk G1). |
| FR-OUT-7 | Explicit verification checkbox gates the send confirm | [TODAY] | Submit stays disabled until checked. |
| FR-OUT-8 | No cancel affordance until BE-7 | [GATED] on BE-7 | Do not ship a button that calls a non-existent command. |
| FR-OUT-9 | Message review renders three distinct designed states | [TODAY] | Hash-verified draft; hash mismatch (refuse to render, danger banner); no draft found (commitment only). None may degrade to a blank panel. |

### 6.6 FR-OPS-1..9 — Operations / Activity

| ID | Requirement | Tag | Acceptance criteria |
|---|---|---|---|
| FR-OPS-1 | CCC-only default filter with show-all toggle | [TODAY] | Default excludes `workspace.initialize`; toggle reveals it. |
| FR-OPS-2 | `limit` select, not cursor pagination | [TODAY] | This query has no cursor (`schema.py:281-296`); no "Load more" button on this screen. |
| FR-OPS-3 | `refused` is warning-toned, never danger | [TODAY] | Danger reserved for `failed`. A refusal is a correct governance decision. |
| FR-OPS-4 | Both reason-code vocabularies visible at the same glance level | [TODAY] | Granular `reasonCode` and the coarse receipt enum shown together, neither hidden behind a disclosure the other isn't. |
| FR-OPS-5 | Canned copy for the four `*_unbound` codes | [TODAY] | Plain-language explanation instead of raw snake_case. |
| FR-OPS-6 | `proofStatus` plain text, no lock or shield iconography | [TODAY] | No icon implying cryptographic verification anywhere near it. |
| FR-OPS-7 | Cryptographic detail collapsed by default | [TODAY] | `signature`, `daml_transaction`, `action_commitment` inside a closed disclosure. |
| FR-OPS-8 | Session-scoped History tabs explicitly labeled | [TODAY] / [BACKEND] | Must not imply it is the entity's full write history. Full fix requires BE-4. |
| FR-OPS-9 | 503 renders as already-terminal-failed, no polling loop | [TODAY] | `_record_dispatch_failure` (`core/jobsearch_commands.py:431-495`) already calls `fail_operation` and issues a receipt before the 503 returns. |

### 6.7 FR-SRC-1..2 — Sources

| ID | Requirement | Tag | Acceptance criteria |
|---|---|---|---|
| FR-SRC-1 | Session-local attempt list labeled "not from Ultradex" | [TODAY] | Explicitly states there is no query that lists past ingests. |
| FR-SRC-2 | Always refuses today, standard pattern | [TODAY] | `source_adapter_unbound` with canned-copy discipline. |

### 6.8 FR-GW-1..8 — Governed write

| ID | Requirement | Tag | Acceptance criteria |
|---|---|---|---|
| FR-GW-1 | Fresh idempotency key per attempt | [TODAY] | Retry never reuses a prior key. |
| FR-GW-2 | 503 renders as already-terminal-failed, no polling | [TODAY] | Enforced once at the pattern level so every screen inherits it. |
| FR-GW-3 | 409 keeps the composer open | [TODAY] | Form state intact; no navigation away. |
| FR-GW-4 | 403 distinguishes scope vs delegation by shape | [TODAY] | Bare string detail = missing scope; structured `{code, message}` = delegation denial. Residual gap: reasons collapse upstream (OOS-9). |
| FR-GW-5 | No auto-retry on network or timeout | [TODAY] | "Unclear whether this was received; check Operations before resubmitting." |
| FR-GW-6 | Every banner renders all structured SDK detail | [TODAY] | `UltradexHttpError.details`, `UltradexGraphQLError.errors[]`, `UltradexSchemaError.issues`, collapsed behind a disclosure, never discarded to `err.message`. **Must land first.** |
| FR-GW-7 | 1.5s polling with capped backoff, survives navigation | [TODAY] | Page-scoped store, not tied to a component's mount state. |
| FR-GW-8 | Receipt fetched for all three terminal outcomes | [TODAY] | Including `refused`. |

### 6.9 FR-EVID-1..2 — Evidence

| ID | Requirement | Tag | Acceptance criteria |
|---|---|---|---|
| FR-EVID-1 | No ref rendered untruncated inline | [TODAY] | Only via `CopyableCode`, never raw inline prose. |
| FR-EVID-2 | `redactedSummary` is the only evidence text shown | [TODAY] | Raw `sourceRef` never appears as readable prose. |

### 6.10 NFR-1..9

| ID | Requirement | Acceptance criteria |
|---|---|---|
| NFR-1 | Degraded-path flagging past the 100-row fallback cap | Dev-mode warning once the backing list exceeds 100 rows. |
| NFR-2 | Deduped and capped polling | No two components independently poll the same `operationId`. |
| NFR-3 | Accessibility parity for new components, including focus traps | `Drawer`, `ConfirmDialog`, `SplitView`, `Tabs` keyboard-navigable, matching the existing a11y bar. |
| NFR-4 | Risk tone never conveyed by color alone | Paired with text or icon. |
| NFR-5 | `UltradexSchemaError` handled distinctly, no auto-retry | Visually and behaviorally distinct from transport or auth failure. |
| NFR-6 | Unknown enum values render a labeled fallback, never blank or thrown | Guards the day BE-6, BE-7, or an adapter first writes a currently-unwritten enum value. |
| NFR-7 | Structured detail logged to console without over-logging evidence | Redacted evidence content never logged. |
| NFR-8 | Three governance display rules each owned by exactly one named component | `FreshnessTag`, risk-tone styling, `ReceiptCard`. No screen re-implements any inline. |
| NFR-9 | Cursor and non-cursor pagination never look identical | `LoadMore` vs the `limit` `Select` are visually distinct. |

## 7. Screen inventory

| Route | Purpose | Primary SDK binding | Phase |
|---|---|---|---|
| `/` (Command) | Cross-entity roll-up: governance banner, freshness strip, Needs Attention, Recent Activity, quick actions | `listOpportunities`, `listApplications`, `listOutreach`, `listOperations` | 1 (reads); writes progressively in 2 |
| `/opportunities` | List, status filter, create entry point | `listOpportunities` | 1; `opportunities.create` ships in 1 |
| `/opportunities/[id]` | Overview, evidence, related, history; Score and Sync | `opportunity(id)` [SDK EXT], fallback `listOpportunities` | 1 (read); writes in 2 |
| `/applications` | List grouped by stage, honest empty state | `listApplications` | 1 |
| `/applications/[id]` | `StageTracker`, stage history/artifacts/next-action | `application(id)` [SDK EXT], fallback | 1 (read); transition in 2, e2e gated on BE-6 |
| `/relationships` | Split view, `?open=<id>` deep link | `listRelationships` | 1 |
| `/outreach` | List with expiry-aware status badge | `listOutreach` | 1 |
| `/outreach/[id]` | Prepare, approve, send; message review; countdown | `outreach_item(id)` [SDK EXT], fallback | 1 (read); writes in 2 |
| `/operations` | Activity browser, CCC-filtered by default | `listOperations` | 1. Where the governed-write pattern is built and tested in isolation. |
| `/operations/[id]` | Status, event timeline, receipt | `getOperation`, `getOperationEvents`, `getExecutionReceipt` | 1 |
| `/sources` (no nav item) | Ingest composer, session-local attempt list | `sources.ingest` | 2 |

## 8. The governed-write pattern

The single highest-leverage, highest-complexity piece of the application. Every write screen reuses it verbatim. Two tiers, because they behave differently and conflating them misnarrates what happened.

### 8.1 Tier 1: submission acknowledgment (synchronous)

| HTTP | Meaning | What happened server-side | UI treatment |
|---|---|---|---|
| 202 `accepted` | Normal path | `Operation` created `PENDING`, published to the worker queue | Proceed to Tier 2 |
| 503 `failed` | Dispatch failure | **Already terminal**: `_record_dispatch_failure` calls `fail_operation` and issues a receipt with `reason_code="executor_failure"` before the 503 returns | Render immediately as terminal-failed. **Do not start a polling loop.** Retry = resubmit with a fresh key. |
| 409 | Idempotency key reuse | No new operation | "Already submitted" banner; composer stays open |
| 403 | Missing `command` scope, or delegation `PermissionError` | No operation created | Distinguish by response shape (bare string vs structured object) |
| 422 | Parameter contract violation | No operation created | Inline field error where mappable, else banner |
| network/timeout | Transport failure, may or may not have completed | Unknown | "Unclear whether this was received." Never auto-retry. |

**A fix that must land first.** Today's glass renders only `err.message`, discarding all structured SDK detail. FR-GW-6 is a prerequisite for the rest of the pattern being trustworthy.

### 8.2 Tier 2: domain outcome (asynchronous)

1. **Poll** `getOperation(operationId)` at 1.5s with capped backoff until terminal. Survives navigation.
2. **Events** via `getOperationEvents(id)` as a timeline with collapsed payload disclosures.
3. **Terminal resolution**, three distinct presentations:
   - **`completed`**: `Badge tone="success"`. Freshness is stamped synchronously, so the entity view refetches with no race.
   - **`failed`**: an executor problem, not a governance decision. `Badge tone="danger"`.
   - **`refused`**: a governance decision working correctly. `Badge tone="warning"`, deliberately not danger. Two distinct fields shown together: the granular code (`scorer_unbound`, `approval_expired`, `invalid_application_transition`) and the coarse receipt enum (`policy_denied | executor_failure | authority_expired | safety_refusal`). The four `*_unbound` codes get canned copy.
4. **Receipt.** `getExecutionReceipt` always present once terminal, for all three outcomes. `proofStatus` shown plainly; cryptographic detail collapsed.

### 8.3 Worked example: outreach prepare, approve, send

**Ultradex never holds the message text.** The prepare composer is a local textarea whose only server-facing output is a `SubtleCrypto`-computed `messageCommitment`. The draft caches in `localStorage` keyed by commitment, disclosed as a feature. On approve, the draft is re-hashed and compared before being trusted: match shows verified text, mismatch refuses to render and shows a danger banner, not-found falls back to the commitment hash alone.

**Approval expires 24h after issue; `status` never flips; there is no revoke.** `ApprovalCountdown` computes everything from `expiresAt` client-side and is the only place this happens. Tone degrades info → warning (under 4h) → danger (under 1h) → expired. Once expired, Send disables permanently, and the copy states plainly that no re-approve or cancel exists and Ultradex's own record will keep reading "approved."

**Send** is the one `external_effect`-tier action in the system. Heavier confirm: full recap, danger-variant button, required verification checkbox. Refuses today with `delivery_transport_unbound`: "No delivery connector is bound. The approval, the commitment, and this refusal are all durably recorded; nothing was sent, and nothing was lost."

## 9. Phasing and sequencing

**Phase 1 — foundations, full read breadth, one real write. All `[TODAY]`. Size L.**
Migrate off hash anchors to real routes (`adapter-static` unchanged; dynamic-id routes go SPA-mode). **Fix the error-detail bug first** (FR-GW-6). Build and test the governed-write pattern in isolation before any entity screen depends on it. All reads online: 9 of 9, up from 2 of 9. First real write is `opportunities.create`, chosen because it is the one command proven to succeed. Design-system build-out runs in parallel.

**Phase 2 — remaining writes on today's backend. All `[TODAY]`. Size M.**
The four `*_unbound` refusers; `outreach.prepare` and `outreach.approve`, both of which succeed today and constitute the highest governance-risk surface in the app; `evidence.export`; `applications.transition` UI (not e2e testable until BE-6). Include a scripted golden-path run so at least one real non-fixture record proves the flow.

**Phase 3 — additive backend, parallelizable with Phase 2. Size M.**
BE-1, BE-2, BE-3, BE-5 (low risk); BE-4 (migration).

**Phase 4 — Nate-gated. Sign-off required before code.**
BE-6 and BE-7, both additionally blocked by the contracts-package finding. BE-8 is a separate program.

## 10. Backend change register

| ID | Change | Unblocks | Size | Status |
|---|---|---|---|---|
| BE-1 | SDK wrappers for the 4 single-entity GraphQL fields | Efficient detail routes | S | Nice-to-have at N=6; blocker past a few hundred rows |
| BE-2 | `listEvidence` / `evidence(id)` | Real evidence picker | S-M | Blocker once `sources.ingest` gets an adapter |
| BE-3 | Expose `allowedTransitions` | Removes client-duplicated FSM | S | Nice-to-have |
| BE-4 | Persist `entity_type`/`entity_ref` on `OperationDB` | Real per-entity history | M | Nice-to-have; logic already exists in `_entity_for()`, unpersisted |
| BE-5 | `code` field on missing-scope 403 | Structural auth distinction | XS | Hardening |
| BE-6 | `applications.create` + optional `evidenceRef` on transition | The entire Applications vertical | M | **Blocker; Nate's call (11.3); also blocked by contracts finding** |
| BE-7 | `outreach.cancel` | The permanent-stranding gap | M | **Blocker for product completeness; Nate's call (11.2); also blocked by contracts finding** |
| BE-8 | Adapter bindings | Turns every `*_unbound` refusal into a real success | L/XL | Separate program, out of scope (OOS-8) |
| BE-9 | Client-side retry breadcrumb after 503 | Operator orientation | XS-S | Likely zero backend |

## 11. Open decisions requiring Nate

No branch, no new command, and no enforcement model is chosen in this document.

### 11.1 Contracts package release strategy (the blocker)

**Decision.** Which branch or process becomes the trunk for `ravenhelm_contracts`, and how the package gets released so a checked-out, buildable source of truth exists again.

**Verified facts.** Production's venv has `ravenhelm_contracts` 0.3.0 installed via `uv`, with no `direct_url.json` (not a path or editable install, so the venv alone cannot regenerate the source). Source repo: `/Users/nate/src/platforms/ravenhelm/libraries/ravenhelm-contracts`. `main` is 0.1.0 and contains no jobsearch contracts at all.

| Ref | Version | Note |
|---|---|---|
| `main` | 0.1.0 | No jobsearch contracts |
| `chore/package-registry-publish` | 0.2.0 | First jobsearch schemas/fixtures |
| `feat/approval-envelope-v1` | 0.3.0 | What production runs |
| `feat/jobsearch-workspace-initialize` | 0.4.0 | |
| `feat/corpus-v1-contracts` | 0.5.0 | |

The worktree backing the exact 0.3.0 checkout, `/private/tmp/accountable-ai-build-new/ravenhelm-contracts-approval-envelope`, is marked `prunable` and lives under `/private/tmp`, which macOS clears. Only the installed wheel remains.

**Recommendation.** None. Surface the options; do not pick a branch.

**Alternatives.** Designate one of the five branches as trunk and merge to `main`, reconciling the others. Reconstruct 0.3.0 from the installed wheel, then reconcile. Start a new version superseding all five and formally retire the others.

**What this blocks.** BE-6, BE-7, the Applications vertical, and the outreach dead-end fix. Independent of CCC, it is a live audit finding: a platform whose value proposition is auditability cannot currently reconstruct its production dependency's source from any merged branch.

### 11.2 New command: outreach dead-end fix

**Decision.** Whether to add `outreach.cancel`, and whether to add any form of re-approve or extend.

**Recommendation.** Add `outreach.cancel`, scoped to abandon before `send`. Recommend **against** re-approve or extend: an approval is a witnessed act about one hashed message at one instant, and resetting its clock erodes the audit property that makes it meaningful. The correct "try again" path is preparing a new outreach.

**Alternatives.** Do nothing and accept permanent stranding. Add cancel (recommended). Add re-approve/extend (recommended against).

**What this blocks.** BE-7, FR-OUT-8, and the outreach dead end.

### 11.3 New command: application origination

**Decision.** Whether to add `applications.create` / `applications.originate`, and whether `applications.transition` should gain an optional `evidenceRef` parameter.

**Recommendation.** None beyond noting the vertical is dead without it.

**Alternatives.** Add an origination command. Leave Applications read-and-transition-only permanently, accepting it never has real data.

**What this blocks.** BE-6, the Applications vertical, FR-APP-5.

### 11.4 Evidence-consumption semantics

**Decision.** Should an evidence ref be single-use once consumed by `opportunities.create` (`jobsearch_executors.py:579-586` checks existence only), or remain reusable?

**Recommendation.** None; explicitly an audit-policy call.

**Alternatives.** Leave reusable (current). Add consumption tracking and enforce single-use.

**What this blocks.** Whether OOS-6 remains permanent policy.

### 11.5 `lens` vocabulary for `opportunities.score`

**Decision.** Whether `lens` (free string, no enum) should become a closed vocabulary.

**Recommendation.** Defer to whoever binds the first scorer adapter; unanswerable today.

**Alternatives.** Keep free text (recommended). Pre-define an enum speculatively (not recommended).

**What this blocks.** The field type on the Score composer.

### 11.6 Auth and enforcement model for risk tiers

**Decision.** Whether `read_only` / `internal_write` / `external_effect`, currently UI-only design tokens with no server enforcement, should ever be enforced, and where.

**Recommendation.** UI-only for v1. If enforcement is ever added, the architecturally consistent home is the already-approved Identity/RBAC design (Forseti as sole OpenFGA PDP), not a bespoke check in `api/auth.py`.

**Alternatives.** Enforce ad hoc in `api/auth.py` (not recommended). Enforce via Forseti/OpenFGA. Never enforce.

**What this blocks.** OOS-7 remains operative until decided.

## 12. Risks

### 12.1 Governance risks

- **G1: Send enablement must never bind to `approval.status`.** It never flips after approval; a refactor to `disabled={status !== "approved"}` would present an expired window as sendable. The server would still refuse, so no unauthorized delivery, but the UI would misrepresent governance state. Medium likelihood (looks like a cleanup, survives casual review), high impact. Mitigated by FR-OUT-6's regression test.
- **G2: "Always fresh" today may train the operator to stop reading freshness before it starts mattering.** Keep the affordance legible while it is boring.
- **G3: Burying the receipt's coarse `reasonCode` hides the governance category behind the mechanism.** Both must be equally visible (FR-OPS-4).
- **G4: `proofStatus: "server-recorded"` next to cryptographic fields invites someone to add a lock icon later.** Guard in review, not just at build (FR-OPS-6).
- **G5: Any screen rendering bare `approval.status` looks like a permanently valid approval.** This already happened once, in the design draft's outreach list spec, before being caught (closed by FR-OUT-3). Most likely governance bug to recur.

### 12.2 Product risks

- **P1: Applications and Outreach ship against near-zero real data.** Any review looks empty regardless of design quality. Mitigate with the Phase 2 golden-path run.
- **P2: The governed-write pattern is the long pole, not "just another form."** Underestimating it risks a rushed implementation that skips the honesty requirements in section 4.

### 12.3 Technical risks

- **T1:** The `applications.transition` write-to-read round trip has never executed. Smoke test recommended.
- **T2:** Client-side duplication of the Application FSM drifts silently until BE-3. Mitigate with a contract test.
- **T3:** Polling storms. Low today; mitigated by NFR-2.
- **T4:** Contract-vocabulary drift. The day a currently-unwritten enum value is first written, non-exhaustive switches misrender silently. Mitigated by NFR-6.

## 13. Open questions

1. Is a client-side retry breadcrumb (BE-9) sufficient after a 503, or does the path deserve a first-class resubmit button pre-filling prior form state with a fresh idempotency key?
2. Should the persistent operation tray (OOS-2) be scheduled as a v2 item now, or revisited only if the page-scoped store proves insufficient?
3. Should BE-4 be pulled into Phase 1, given how directly it affects the credibility of every entity's History tab? It is additive and low risk; its Phase 3 placement is sequencing, not technical dependency.
4. What is the value of building BE-2 ahead of BE-8, given it is marked "blocker once `sources.ingest` gets an adapter" rather than a blocker today?
5. Does the T1 smoke test belong in CI now, gated on a synthetic application row, or wait for BE-6 to produce a real one?

## Appendix: file and path references

- SDK: `sdk/typescript/src/{contracts,client,jobsearch-queries,jobsearch-commands,transport}.ts` (worktree `ultradex-ccc-glass`)
- Server: `api/graphql/schema.py`, `api/auth.py`, `api/routes/v2/{commands,jobsearch_commands}.py`, `core/{jobsearch_executors,jobsearch_commands,jobsearch_worker,operation_service}.py` (worktree `ultradex-dashboard-runtime`)
- Existing UI: `apps/web/src/lib/components/{AppShell,TopBar,LeftNav}.svelte`, `apps/web/src/routes/{+layout,+page}.svelte`, `apps/web/src/lib/{whats-next,client}.ts`, `apps/web/src/app.css` (worktree `ultradex-ccc-glass`)
- Design system: `packages/ui-svelte/src/lib/` (worktree `ultradex-ccc-glass`)
- Contracts package: `/Users/nate/src/platforms/ravenhelm/libraries/ravenhelm-contracts`; production dependency checkout `/private/tmp/accountable-ai-build-new/ravenhelm-contracts-approval-envelope` (marked `prunable`)
