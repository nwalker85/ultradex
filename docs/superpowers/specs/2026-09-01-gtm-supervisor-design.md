# Career Command Center GTM Supervisor Design

- **Status:** Review
- **Maturity:** Informational
- **Decision:** The business rules and supervisor/task-agent topology were
  ratified by Nate Walker on 2026-09-01. Implementation, production use, and
  autonomous outbound are not authorized by this document.
- **Version:** v0.1.0-review
- **Date:** 2026-09-01
- **Owner:** Nate Walker
- **Product:** Career Command Center (CCC)
- **Data class:** Private, operator-only career and commercial data
- **Production use:** Not authorized

## Purpose

Define the top-of-funnel agent that supplies Career Command Center with
qualified demand for two commercial motions:

1. immediate voice-AI and contact-center subcontracting revenue; and
2. senior W-2 roles.

Marketing succeeds when a qualified conversation is booked. In CCC terms, a
qualified Lead becomes a marketing-qualified lead (MQL), and a confirmed
booking converts that MQL into an Opportunity. CCC remains the authority for
the entire `Lead -> MQL -> Opportunity` lifecycle.

This design extends the
[Career CRM Relational Schema Design](2026-08-31-career-crm-relational-schema-design.md)
and preserves its shared employment/contract opportunity model, provenance,
custody, and append-only history requirements.

## Placement during the CCC rebuild

The proposed
[CCC rebuild ADR](../../decisions/0001-ccc-rebuild-tiers-tenancy-phasing.md)
freezes the current Ultradex runtime and moves the future system of record into
fresh Project Factory repositories after explicit ratification and cutover
gates. This specification does not reverse that decision or authorize a
rebuild-in-place.

Until the future CCC domain-service repository exists, this file is the review
record next to the current domain contracts. If the rebuild ADR is accepted,
the specification must move with the CCC domain authority before
implementation. The Ultradex copy then becomes a deprecated pointer; it must
not remain a competing source of truth.

## Identity, tenancy, and delegation authority

The supervisor is a named CCC service principal bound to one `workspace_id`
and its corresponding Mimir tenant. Every query and command carries both the
service identity and the operator principal on whose behalf it acts. Forseti
must authorize that exact delegation; possession of a CCC credential alone is
not authority to act for Nate or another tenant.

The supervisor never forwards its credential, operator token, or delegation
grant into a child brief. Children receive opaque workspace and entity
references plus profile-bounded CCC reads. They do not call Mimir directly and
cannot submit CCC commands.

Identity resolution is a CCC domain-service responsibility:

- organizations resolve to estate-global Mimir entities and workspace-local
  CCC projections;
- people and contacts resolve only within the caller's tenant;
- cross-tenant absence returns `404`, never a revealing authorization error;
- ambiguous or conflicting identity candidates fail closed into a resolution
  action; and
- an unresolved person or organization may remain a Lead signal but cannot be
  qualified, deduplicated destructively, converted, or contacted.

The Phase-0 tenancy and authorization gates in the CCC rebuild ADR therefore
precede live supervisor writes. An intake bundle may carry unresolved identity
evidence, but it may not mint a canonical Mimir identity or claim that identity
resolution succeeded.

## Outcome and measurement

The primary outcome is:

```text
qualified_conversations_booked
```

A count increments only when all of these are true:

1. one canonical CCC Lead exists;
2. the applicable qualification gate passes with evidence;
3. a conversation with at least one external participant is confirmed by a
   calendar event or equivalent scheduling evidence; and
4. CCC atomically records the Lead conversion and resulting Opportunity.

The primary conversion metric is `MQL -> Opportunity`. Supporting metrics are
Lead-to-MQL conversion, median time to qualification, booked conversations by
motion, and the age of qualified Leads without a booking. Sent messages,
connection requests, scraped contacts, and unqualified meetings are activity,
not success.

## Commercial policy

### Contract motion

The initial offer is senior and principal voice-AI/contact-center engineering
for implementation partners with an active delivery-capacity gap. Direct work
and subcontracting are both permitted. The starting capacity is 20-30 hours per
week.

Private qualification floors are:

- **$175/hour** for senior delivery work; and
- **$200/hour** for principal or architecture work.

These are internal qualification guardrails, not public rate-card copy. A
deal-specific rate, capacity, payment terms, and order structure must be
confirmed before representation or commitment. No customer identity or
unrelated contract language belongs in agent briefs, CCC summaries, or
outreach.

Implementation partners named during design, including Deloitte, are seed
hypotheses rather than pre-qualified accounts. The organization referred to as
"Opex" is not resolvable from the current record and must not be turned into a
canonical organization until its exact identity is confirmed.

### W-2 motion

The starting target is **$250,000 annual cash compensation**, defined as base
salary plus a realistic cash bonus or OTE. Equity, stock, and RSUs are tracked
separately and do not close a cash-compensation gap. Exceptional roles below
the target require an explicit operator override; the agent may recommend the
exception but may not silently lower the target.

### Initial channel and tool policy

- Use public research and CCC first. Gmail, Calendar, LinkedIn, and other
  private context require the named service/delegation identity and
  custody-approved metadata-only Relationship Scout boundaries below; they are
  never implied by general source authorization.
- Use no paid GTM, enrichment, warmed-inbox, bulk-email, or LinkedIn-automation
  tools in the initial version.
- Do not create synthetic contacts merely to fill a funnel.
- Do not make HubSpot a second authority. Retirement of HubSpot remains a
  separate ADR, migration, and cutover decision.
- Every external message is a draft until Nate approves that exact content.

## Immediate operator-assisted bridge

Near-term revenue work does not wait for the Yager or CCC rebuild. Until the
supervisor is implemented, an operator-directed Codex session may perform a
public-only Signal Scout, public-evidence BANT analysis, and Outreach Drafter
pass manually under this specification.

The bridge may read public sources and sanitized CCC projections, prepare a CCC
intake bundle, and render exact drafts for Nate's approval. It may not read raw
Gmail, Calendar, LinkedIn, contact-note, or other private-source content. A
private-context bridge requires a separately named, custody-approved,
metadata-only lane; the general phrase "user-authorized context" is not an
authorization boundary.

The bridge may not create a second CRM, autonomously send, bulk-contact, or
represent an unconfirmed rate, capacity, relationship, identity, or
qualification dimension. Any real CCC import uses only the official SDK with
an idempotency key, receives a `ContractHandle`, and waits for receipt plus
projection readback. Any external send still requires approval of the exact
rendered message.

This is an operating bridge, not an alternate architecture. It ends when the
governed supervisor vertical proves the same artifacts can be produced and
reconciled without losing evidence or operator control.

## Funnel semantics

### Lead

A Lead is an unqualified signal with source provenance. It may refer to a
person, organization, role, contract need, or partner delivery gap. Duplicate
signals enrich one canonical Lead rather than creating parallel funnel rows.

### MQL

MQL is a qualification state of a Lead, not a second CRM aggregate. In the
relational model it is represented by `leads.status = qualified`, a complete
qualification snapshot, and evidence-linked dimension assessments.

Every qualification dimension uses one of these states:

- `unknown` - no usable evidence;
- `inferred` - supported by evidence but not directly confirmed;
- `validated` - directly confirmed or supported by authoritative evidence; or
- `contradicted` - evidence conflicts with the required condition.

#### Contract MQL gate

All BANT dimensions must be `validated`:

| Dimension | Required evidence |
|---|---|
| Budget | A credible budget or rate envelope that can meet the applicable private floor. |
| Authority | An identified buyer, decision maker, or authorized implementation-partner sponsor. |
| Need | A concrete voice-AI/contact-center delivery gap that matches Nate's capability. |
| Timeline | A current or dated buying/delivery window, not a generic future interest. |

One missing, inferred, unknown, or contradicted dimension keeps the Lead in
`nurturing`; contract qualification is all-or-nothing.

#### W-2 MQL gate

- Need and Timeline must be `validated`.
- Budget and Authority may be `validated` or `inferred`, but each must have an
  evidence reference and neither may be `unknown` or `contradicted`.
- Compensation evidence should support the $250,000 cash target. A lower band
  requires an explicit exceptional-role override before qualification.

### Opportunity

An Opportunity is created only when a qualified Lead has a confirmed booked
conversation. The conversion transaction must resolve or create the canonical
organization and contact, attach the booking interaction, preserve the
qualification snapshot, create the employment or contract Opportunity, and
mark the Lead `converted`.

A booking that arrives before qualification remains attached to the Lead and
creates a qualification action. It does not count as marketing success and does
not create an Opportunity until the gate passes.

## Target CCC contract

Agents are SDK consumers. They never write Postgres, ClickHouse, Mimir, NATS,
or projection tables directly. Target writes use governed commands with
idempotency keys, receipts, and append-only events. The logical command surface
is:

| Command | Purpose |
|---|---|
| `leads.create` | Create or enrich a provenance-backed Lead. |
| `leads.qualify` | Record dimension assessments, evidence, and the resulting MQL state. |
| `relationships.sync` | Resolve governed relationship metadata without importing raw private content. |
| `outreach.prepare` | Bind an exact draft commitment and custody reference to a Lead. |
| `bookings.reconcile` | Resolve confirmed scheduling evidence against a Lead. |
| `leads.convert` | Atomically create the Opportunity after qualification and booking gates pass. |

`leads.qualify` and `bookings.reconcile` are target-contract additions. Existing
command names do not imply the rebuild already implements them. In the future
CCC control surface, command acceptance returns a `202` plus `ContractHandle`;
completion is established by the receipt and projection, never by the
acceptance response.

Every command has a versioned tag, a closed parameter schema, one response
shape, and a closed refusal-code set. Unknown fields, unknown tags, stale
policy versions, unresolved or ambiguous identities, tenant mismatch, missing
evidence, and malformed references fail before acceptance. The GTM-specific
refusal vocabulary includes:

```text
identity_unresolved
identity_ambiguous
tenant_mismatch
qualification_incomplete
qualification_evidence_missing
qualification_snapshot_stale
booking_unconfirmed
booking_participant_unresolved
content_commitment_mismatch
```

The official SDK, generated from the same schemas, is the only agent write
surface. Raw HTTP, NATS publication, database access, and an untyped generic
command escape hatch are prohibited.

### Required data-model extension

The target relational schema must add evidence-bearing Lead qualification and
conversion proof without moving MEDDPICC out of the Opportunity aggregate:

```text
lead_qualification_assessments             append-only
- id
- workspace_id
- lead_id
- dimension                               budget | authority | need | timeline
- assessment                              unknown | inferred | validated | contradicted
- policy_version
- redacted_summary
- assessed_at
- assessor_type
- supersedes_assessment_id                nullable self-reference

lead_qualification_evidence                append-only, typed references
- id
- workspace_id
- assessment_id
- evidence_type                           source_record | interaction | document | public_url
- source_record_id                        nullable
- interaction_id                          nullable
- document_version_id                     nullable
- public_url                              nullable
- content_ref                             nullable
- content_commitment
- observed_at

lead_qualification_snapshots               immutable
- id
- workspace_id
- lead_id
- policy_version
- qualification_state                     nurturing | qualified
- snapshot_digest
- created_at

lead_qualification_snapshot_assessments
- snapshot_id
- dimension
- assessment_id
- PRIMARY KEY(snapshot_id, dimension)

lead_conversions
+ booking_interaction_id
+ qualification_snapshot_id
```

Exactly one typed evidence target is present on each evidence row. A new
assessment supersedes by reference but never updates or deletes the prior row.
The immutable snapshot binds one assessment per BANT dimension under one policy
version; its digest commits to those assessment and evidence identifiers. Lead
conversion references the snapshot row, not a mutable "current" qualification
record.

MEDDPICC continues after conversion as Opportunity qualification. BANT is the
pre-conversion marketing gate; the two models serve different lifecycle
decisions and must not overwrite each other.

## Supervisor and task agents

The GTM supervisor is a CCC product workflow. Yager provides generic leaf-task
execution but owns no marketing policy or funnel state.

The supervisor is the only agent component permitted to submit CCC commands.
It schedules one child at a time, validates every result, decides the next
bounded task, and submits only idempotent governed commands. It never treats a
child result as proof of a CCC state change.

Initial leaf roles are:

| Role | Inputs | Output | Tool ceiling |
|---|---|---|---|
| Signal Scout | ICP, public sources, CCC duplicate checks | Candidate signals with public evidence | Public research and CCC read-only |
| Relationship Scout | A bounded candidate plus user-authorized connector scope | Relationship paths and metadata-safe evidence references | Private connector reads and CCC read-only |
| BANT Analyst | Redacted summaries and evidence references | Per-dimension assessment and gaps | CCC/evidence read-only; no source connectors by default |
| Outreach Drafter | Sanitized Lead, offer, relationship, and missing qualification context | One personalized draft plus commitment input | No sender and no CCC writer |

This table is the target role set, not a claim about current Yager profiles. The
first Yager task-mode release is Reviewer-only. Signal Scout remains in the
public Codex bridge until a versioned leaf-safe public-research profile is
independently reviewed; Relationship Scout additionally waits for the private
telemetry and custody gates. Neither role may fall back to Developer or
Autonomous task mode.

Booking reconciliation is deterministic supervisor logic, not an LLM task
agent. Calendar evidence, participant identity, timing, and idempotency are
machine-checkable and should not be inferred by a model.

### Task execution boundary

Each leaf runs as a separate, non-interactive Yager CLI child process under
Yager ADR 0006 (`nate/yager`,
`docs/architecture/decisions/0006-process-isolated-task-agents.md`). Each child
receives an explicit brief and named permission profile, has an isolated
session and ledger, cannot delegate, and returns a bounded structured result.
Initial concurrency is one.

## Data and custody flow

```text
authorized sources
  -> leaf task reads within its profile
  -> bounded result with evidence references and redacted summaries
  -> supervisor validates result
  -> CCC SDK command
  -> receipt and projection readback
  -> next task or operator action
```

- Gmail bodies, LinkedIn messages, contact notes, source documents, and other
  raw private content remain in their designated custody system.
- CCC stores opaque references, commitments, timestamps, provenance, and
  redacted summaries of at most the governed limit; it does not ingest raw
  private content through this workflow.
- A leaf brief contains only the minimum context needed for that task.
- A generic Yager result envelope may not contain raw mailbox or direct-message
  content.
- Draft outreach content remains in the designated outreach content store or
  transient supervisor UI. CCC stores its content reference and commitment.
- Langfuse content capture must be disabled until Yager's metadata-only privacy
  profile is implemented and verified. The Relationship Scout is blocked from
  controlled validation until that gate passes.

## Outbound approval boundary

The initial supervisor may programmatically prepare a draft, but it may not
approve or send one. The operator reviews the full rendered content, channel,
recipient, Lead, evidence, and commitment before using CCC's governed approval
and send actions.

No child receives a sender tool. Any content change invalidates the prior
commitment and approval. Approval expiry, recipient mismatch, channel mismatch,
or stale Lead evidence fails closed and requires a new review. Bulk sends,
sequence automation, and autonomous LinkedIn interaction are out of scope.

## Scheduling and prioritization

Each supervisor cycle prioritizes:

1. contract Leads with an active delivery signal and a warm relationship path;
2. contract Leads with an active delivery signal and a credible cold path;
3. qualified contract Leads awaiting a booking;
4. senior W-2 Leads meeting the compensation and qualification policy; and
5. nurture/research work that can close a specific evidence gap.

The score is advisory. The operator can override order, dismiss a Lead, or
pause either motion. An override is recorded as an action or receipt; it does
not rewrite source evidence.

## Rebuild fallback: CCC intake bundle

If the stable CCC write SDK is unavailable during the rebuild, the supervisor
may emit a schema-valid intake bundle instead of writing any database or shadow
CRM:

```text
schema_version
bundle_id
generated_at
workspace_ref
idempotency_keys
proposed_commands[]
evidence_refs[]
redacted_summaries[]
validation_results[]
```

The bundle is an unexecuted proposal. Importing it later must pass the same
command validation, duplicate detection, qualification, approval, and receipt
rules as a live submission. The importer uses the official SDK only, submits
each closed tagged command with its preserved idempotency key, records the
returned `ContractHandle`, and waits for both the terminal receipt and expected
projection readback before advancing the bundle. Acceptance alone never marks
an item imported. A local file, spreadsheet, HubSpot record, or Yager ledger
never becomes interim funnel authority.

## Failure behavior

- Child timeout, cancellation, malformed output, or profile refusal produces a
  failed task result and no CCC mutation.
- A result without required evidence remains a research lead; the supervisor
  may not upgrade its confidence.
- Duplicate candidates merge by governed identity resolution and retain every
  source observation.
- Stale or contradictory evidence reopens the affected qualification dimension
  and can move an MQL back to nurturing before conversion.
- Booking reconciliation is idempotent by scheduling-provider identifier plus
  participant/time fingerprint.
- A command accepted without a completed receipt remains pending, not complete.
- Connector outages degrade only the affected task. They do not erase or
  downgrade canonical CCC records.

## Validation plan

Implementation planning must provide tests for:

1. contract qualification refuses every incomplete BANT combination;
2. W-2 qualification allows evidence-backed inferred Budget or Authority but
   refuses unknown or contradicted dimensions;
3. compensation below the starting target requires an explicit override;
4. a confirmed booking converts exactly one MQL to exactly one Opportunity;
5. an unqualified booking does not convert or increment the KPI;
6. retries and duplicate source signals do not create duplicate Leads,
   bookings, or Opportunities;
7. child processes cannot write CCC or invoke sender tools;
8. changing draft content invalidates the approval commitment;
9. CCC and Yager telemetry remain metadata-only without explicit content
   authorization; and
10. intake-bundle import produces the same handles, receipts, refusals, and
    projections as live governed commands;
11. ambiguous identity and cross-tenant resolution fail before qualification,
    deduplication, contact, or conversion; and
12. a conversion remains provable after newer qualification assessments are
    appended because it references an immutable snapshot.

Controlled validation starts with public-source Signal Scout work and synthetic
CCC fixtures. Private Relationship Scout validation waits for the Yager privacy
gate and a custody review. Production use, autonomous sending, and a CCC
cutover each require separate approval.

## Explicit non-goals

- Replacing CCC with Yager, HubSpot, a spreadsheet, or an agent ledger.
- Building a general-purpose sales CRM outside CCC.
- Paid enrichment, bulk outbound, warmed inboxes, or social automation.
- Autonomous approval or sending.
- Storing raw private source content in CCC, task envelopes, or telemetry.
- Implementing deep agent graphs, nested delegation, or parallel fan-out in
  Yager.
- Retiring HubSpot or the Ultradex runtime without their own migration and
  cutover decisions.
- Authorizing the CCC rebuild, schema migration, production deployment, or
  legacy decommission.

## Implementation sequence after written-spec approval

The public-only operator bridge and unexecuted intake bundles may proceed while
the rebuild is undecided. Every other CCC implementation step fails closed
unless the operator has ratified the rebuild ADR, fixed the new domain
authority/repository, and preserved the separate current-to-target mapping,
migration, rollback, cutover, and loud-decommission gates.

The live supervisor write path has a second hard prerequisite: Phase-0 Mimir
tenancy and delegation authorization must pass the deployed cross-tenant
absence, ambiguous-identity refusal, and service-on-behalf-of-operator tests.
Until then, neither the legacy runtime nor a fresh service may accept supervisor
writes.

After those authority gates and written-spec approval:

1. Add the generic Yager child-process contract and acceptance tests.
2. Place this specification in the ratified CCC domain repository and leave a
   deprecated pointer here.
3. Extend the target CCC schema and official SDK contracts for Lead
   qualification, identity refusal, and booking proof.
4. Implement a public-only Signal Scout vertical using unexecuted intake
   bundles.
5. Implement governed CCC command submission, `ContractHandle`, receipt, and
   projection readback.
6. Add BANT analysis and draft preparation with operator approval.
7. Add deterministic Calendar reconciliation and MQL conversion.
8. Add private Relationship Scout only after telemetry and custody gates pass.
9. Add the W-2 motion after the contract vertical proves the end-to-end KPI.

This sequence optimizes for near-term revenue while keeping the private-data
and outbound boundaries fail-closed.
