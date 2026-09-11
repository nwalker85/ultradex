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

The complete target contract pack also includes:

- the proposed CCC rebuild ADR in this repository;
- the Mimir Tenant Scope and CCC Identity Resolution Design in
  `nwalker85/mimir-schema`;
- the CCC GTM Wire Contract Design in `nate/ravenhelm-contracts`;
- Yager ADR 0006 for process-isolated leaves; and
- Yager ADR 0007 for execution identity versus domain authority.

These records are reviewed together. A reference to a target design is not a
claim that its schema, runtime, policy, migration, or release already exists.

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

ADR-014 and its accepted amendments remain current until that later cutover:
Dex owns current CCC contact truth, Ultradex is the current Python middleware,
and the Svelte glass uses `@ultradex/sdk`. The proposed rebuild ADR explicitly
supersedes those three selections only after ratification and a single-writer
cutover to Mimir plus CCC projections, the fresh CCC domain service, and the
Next.js/generated-`@ravenhelm/sdk-ts` surface. Before then, this design cannot
be cited as permission to dual-write, replace the Svelte UI, or bypass Dex.

## Identity, tenancy, and delegation authority

The supervisor is a named CCC service principal bound to one `workspace_id`
and its corresponding Mimir tenant. Every query and command carries both the
service identity and the operator principal on whose behalf it acts. Forseti
must authorize that exact delegation; possession of a CCC credential alone is
not authority to act for Nate or another tenant.

The command correlation context preserves four distinct identities:

| Stratum | GTM meaning |
|---|---|
| Operator | `rig_user_id` for Nate, never Zitadel `sub`. |
| Durable agent | Mimir Agent `resource_id` / `did:web` for the CCC GTM supervisor. |
| Workload | SPIFFE identity for the deployed CCC process. |
| Session | short-lived `did:key` reference for this execution. |

The context also binds the witnessed delegation, policy version,
workspace-to-tenant mapping version, and deployed revision. Authentication
establishes identities; Forseti OpenFGA and Cedar authorize the exact action.
Neither identity nor a raw credential substitutes for authorization.

The durable-agent stratum carries the complete current Mimir resolution proof,
not only an Agent ID: Agent resource reference and `did:web`, resolution
reference, registry/resolver/policy versions, lineage, resolved/expiry times,
`current` freshness, `active` lifecycle, descriptor schema/digest, and package
surface. A stale, expired, suspended, retired, missing-lineage, or
package-mismatched supervisor cannot submit a command. Yager's harness
principal and child execution identity cannot substitute for this CCC product
principal proof.

Mimir owns the canonical workspace-to-tenant binding registry and its
side-effect-free resolver. CCC caches only the returned tenant, mapping
version, freshness, and lineage as a read-only projection. The supervisor must
resolve and recheck that mapping through the official Mimir SDK; a CCC row,
route, hostname, token claim, or configuration value cannot create or change
it.

The supervisor never forwards its credential, operator token, delegation grant,
connector credential, or CCC client into a child brief. **The initial design
chooses brokered snapshots, not delegated child reads.** The supervisor performs
authorized CCC queries and passes a minimum sanitized snapshot with opaque
entity/evidence references, freshness, lineage, and commitments. Children do
not call CCC or Mimir, cannot submit commands, and cannot refresh or widen the
snapshot themselves.

Private Gmail, Calendar, LinkedIn, and contact-system reads are performed by
bounded CCC source executors under their own governed connector scope. Those
executors write raw content only to the designated custody system and return
metadata, opaque references, commitments, and bounded redacted summaries. A
Yager Relationship Scout analyzes that brokered material; it never receives a
mailbox, social, or contact-system credential.

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

The canonical route may contain `/t/{tenant}`, but the path is an addressing
claim, never a grant. The authenticated identities, governed workspace mapping,
entity parentage, and Forseti Check must agree before lookup. Unauthorized,
foreign-tenant, and absent entities remain indistinguishable `404`s.

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
the target require an immutable, interaction-bound operator compensation
override under the current policy; the agent may recommend the exception but
may not create the confirmation or silently lower the target. The override and
its fresh Forseti decision are bound into the qualification snapshot and must
remain valid at conversion.

### Initial channel and tool policy

- Use public research and CCC first. Gmail, Calendar, LinkedIn, and other
  private context require the named service/delegation identity and
  custody-approved source-executor and metadata-only Relationship Scout
  boundaries below; they are never implied by general source authorization.
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
intake bundle, and render exact drafts for Nate's review and explicit manual-send
authorization. It may not read raw
Gmail, Calendar, LinkedIn, contact-note, or other private-source content. A
private-context bridge requires a separately named, custody-approved,
metadata-only lane; the general phrase "user-authorized context" is not an
authorization boundary.

The bridge may not create a second CRM, autonomously send, bulk-contact, or
represent an unconfirmed rate, capacity, relationship, identity, or
qualification dimension. Any real CCC import uses only the official SDK with
an idempotency key, receives a `ContractHandle`, and waits for receipt plus
projection readback. Any external send still requires approval of the exact
rendered message; in this bridge that is an operator review, not a governed
`outreach.approve` receipt.

The bridge writes unexecuted bundles only under the contract-defined path:

```text
~/var/career-command-center/intake/<workspace_id>/<bundle_id>/bundle.json
```

The fixed owner, mode, no-symlink, atomic-write, digest, expiry, and disposition
rules live in the CCC GTM Wire Contract Design. A path or bundle identifier is
never authority.

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
- The snapshot binds evidence-backed annual cash (base plus realistic cash
  bonus/OTE, equity excluded) against the $250,000 target. A lower amount
  requires the current immutable interaction-bound operator override described
  above; unknown compensation cannot satisfy Budget.

### Opportunity

An Opportunity is created only when a qualified Lead has a confirmed booked
conversation. The conversion transaction must resolve or create the canonical
organization and contact, attach the immutable booking proof and its
interaction, preserve the
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

| Command | Contract status | Purpose |
|---|---|---|
| `leads.create` | Existing v1; revised in v2 | Create or enrich a provenance-backed Lead. |
| `leads.override-compensation` | New v2; operator-interactive only | Record an immutable, expiring exception for a below-floor W-2 Lead. |
| `leads.qualify` | New v2 | Record assessments, evidence, and the resulting immutable BANT snapshot. |
| `relationships.sync` | Existing v1; revised in v2 | Attach governed relationship metadata to a Lead or Opportunity without raw content. |
| `outreach.prepare` | Existing v1; revised in v2 | Bind an exact draft commitment and custody reference to a Lead or Opportunity. |
| `outreach.approve` | Existing v1 tag; v2 semantics replaced | Reconcile a validated Forseti/MFAA/Vor approval result; CCC never issues approval. |
| `outreach.send` | Existing v1; preserved but disabled initially | Execute only with the matching unexpired approval and approved content custody. |
| `outreach.cancel` | Existing v1; preserved | Abandon a draft or approved-but-unsent outreach item. |
| `bookings.reconcile` | New v2 | Resolve confirmed deterministic scheduling evidence against a Lead. |
| `leads.convert` | Existing v1; strengthened in v2 | Atomically create the Opportunity after qualification and booking gates pass. |

`leads.override-compensation`, `leads.qualify`, and `bookings.reconcile` are
target-contract additions.
`relationships.sync`, `outreach.prepare`, and `leads.convert` require v2 shapes
because the GTM workflow acts before an Opportunity exists and requires
qualification/booking proof. Existing command names do not imply the rebuild
implements those revisions. Command acceptance returns a `202` plus
`ContractHandle`; completion is established by the receipt and projection,
never by the acceptance response.

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
content_custody_unavailable
approval_missing
approval_expired
approval_revoked
approval_artifact_mismatch
send_not_enabled
```

The official SDK, generated from the same schemas, is the only agent write
surface. Raw HTTP, NATS publication, database access, and an untyped generic
command escape hatch are prohibited.

Target GTM mutations use `jobsearch/v2` and the four-stratum
`control-surface/v2` correlation context defined in `ravenhelm-contracts`.
`jobsearch/v1` remains readable during migration but cannot receive a v2
mutation because it cannot preserve the full qualification and authority proof.
At target cutover the gateway atomically retires all v1 mutations, including
legacy approve/send/convert, before enabling v2 writers. A v1 mutation then
returns `contract_version_retired` before publication or side effect. There is
no dual-write or v2-to-v1 mutation adapter; rollback fences v2 before a
separately authorized legacy authority-epoch reversal.

### Exact outreach approval

`outreach.prepare` commits to one closed artifact containing the outreach ID,
Lead or Opportunity, recipient, channel, content reference, message commitment,
qualification/evidence snapshot, policy version, and expiry. That canonical
object becomes the artifact of one `approval-envelope/v1` leaf. Its
`artifact_digest`, the separately canonicalized approval event digest, leaf
sequence/digest, one-leaf Merkle root, and ordered aggregate
`approved_artifact_digest` are all validated under `exact_match` with approved
and maximum execution tree sizes fixed at one. The leaf artifact digest and
aggregate artifact digest are different commitments and cannot be aliased.

The operator reviews the full rendered artifact through the official
accountability rail. Forseti owns the authorization/JIT decision; MFAA supplies
device-bound human step-up when required; Vor alone materializes and signs the
Varar; Bifrost verifies and atomically reserves that single-use authority before
an independently deployed sender can execute. Freyr may orchestrate this path
but cannot become an alternate decision-maker or signer. CCC stores only opaque
request/decision/Varar references, commitments, validity/status projection,
and lineage. It never stores signing keys, passkey assertions, device
credentials, or an independent revocation state.

Any content, recipient, channel, subject, evidence, policy, or expiry change
produces a new digest and invalidates approval. A model, child, supervisor,
connector, sender, or CCC command cannot approve.

The initial release keeps the rendered body transient in the supervisor UI and
stores only its commitment in CCC. It stops at `outreach.prepare`: Nate reviews
and sends the exact draft manually. An operator annotation may record that
review, but it is not a governed `outreach.approve` receipt and mints no send
authority. With no approved durable content store and no proven complete
Forseti/MFAA/Vor/Bifrost integration, both `outreach.approve` and
`outreach.send` refuse as disabled. Automated sending remains a later,
separately approved custody and controlled-validation decision.

### Required data-model extension

The target relational schema must add evidence-bearing Lead qualification and
conversion proof without moving MEDDPICC out of the Opportunity aggregate:

```text
lead_compensation_overrides                immutable, operator-interactive
- id
- workspace_id
- lead_id
- policy_version
- annual_cash_floor
- candidate_annual_cash
- currency
- redacted_reason
- operator_principal_ref
- operator_confirmation_ref
- forseti_decision_ref
- override_digest
- approved_at
- expires_at
- supersedes_override_id

lead_compensation_override_evidence
- workspace_id
- override_id
- ordinal
- evidence_ref
- evidence_commitment
- observed_at

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
- w2_annual_cash_amount                   nullable
- w2_annual_cash_currency                 nullable
- w2_annual_cash_evidence_digest          nullable
- compensation_override_id                nullable
- snapshot_digest
- created_at

lead_qualification_snapshot_assessments
- snapshot_id
- dimension
- assessment_id
- PRIMARY KEY(snapshot_id, dimension)

lead_booking_proofs                        immutable
- id
- workspace_id
- lead_id
- interaction_id
- scheduling_provider
- provider_event_ref                      opaque
- provider_event_commitment
- booking_identity_digest
- observation_fingerprint
- observation_version
- event_status                            confirmed | cancelled
- starts_at
- ends_at
- observed_at
- proof_digest
- supersedes_booking_proof_id             nullable self-reference

lead_booking_participants
- workspace_id
- booking_proof_id
- participant_ref                         opaque
- participant_commitment
- is_external
- PRIMARY KEY(booking_proof_id, participant_commitment)

lead_conversions
+ qualification_snapshot_id
+ booking_proof_id
```

Exactly one typed evidence target is present on each evidence row. A new
assessment supersedes by reference but never updates or deletes the prior row.
The immutable snapshot binds one assessment per BANT dimension under one policy
version; its digest commits to those assessment and evidence identifiers plus
the evidence-backed W-2 annual-cash amount/currency and compensation override
ID/digest when a below-floor exception applies. Contract snapshots carry no W-2
cash fields. That exception must be same-Lead, same-policy, match the snapshot
cash/currency, be unexpired and unsuperseded, be interaction-bound to the
operator, and have a freshly positive Forseti decision at qualification and
conversion. Lead conversion references the snapshot row, not a mutable
"current" qualification record. A booking proof binds one calendar
interaction, a stable
provider-plus-event identity digest, a content/status/time/participant
observation fingerprint, ordered observation version, provider-event
commitment, cancellation state, and at least one external participant
commitment. Changed observations form one same-identity linear supersession
chain; retries with the same fingerprint reuse the existing proof. Conversion
references the current confirmed immutable proof rather than a mutable
interaction alone.

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
| Signal Scout | ICP, public sources, supervisor-brokered duplicate snapshot | Candidate signals with public evidence | Public research only; no CCC client |
| Relationship Scout | Bounded candidate plus supervisor-brokered metadata snapshot | Relationship paths and metadata-safe evidence references | No connectors, CCC client, or raw private content |
| BANT Analyst | Brokered redacted summaries, evidence references, freshness, and policy | Per-dimension recommendation and gaps | No CCC, source connector, or mutation tool |
| Outreach Drafter | Sanitized Lead, offer, relationship, and missing qualification context | One personalized draft plus commitment input | No sender and no CCC writer |

This table is the target role set, not a claim about current Yager profiles. The
first Yager task-mode release is Reviewer-only. Signal Scout remains in the
public Codex bridge until a versioned leaf-safe public-research profile is
independently reviewed; Relationship Scout additionally waits for the private
telemetry and custody gates. Neither role may fall back to Developer or
Autonomous task mode. Current interactive Reviewer is not leaf-safe by itself:
task mode must first replace its `$HOME` read scope with no root or an immutable
manifest-bound task snapshot, empty model-facing write roots, and no
Bifrost/non-model network tools. Until those adversarial gates pass, Yager
refuses every child before model execution, including synthetic tasks.

Booking reconciliation is deterministic supervisor logic, not an LLM task
agent. The Calendar source executor supplies governed metadata and evidence
references; participant identity, timing, cancellation state, and idempotency
are machine-checkable and are not inferred by a model.

### Task execution boundary

Each leaf runs as a separate, non-interactive Yager CLI child process under
Yager ADR 0006 (`nate/yager`,
`docs/architecture/decisions/0006-process-isolated-task-agents.md`). Each child
receives an explicit brief and named permission profile, has an isolated
session and ledger, cannot delegate, and returns a bounded structured result.
Initial concurrency is one.

Yager ADR 0007 distinguishes execution provenance from domain authority. A leaf
records its separate Yager harness principal, task execution/session, runtime,
profile, trace, brief, snapshot, and result commitments, but receives
`domain_authority = none`. The Yager harness principal is not the CCC
supervisor's durable agent or SPIFFE workload identity. Those references let
the supervisor correlate which bounded execution informed its decision; they
do not authenticate the child as the CCC workload, authorize the child, or
prove a CCC mutation.

## Data and custody flow

```text
authorized sources
  -> bounded CCC source executor reads within governed connector scope
  -> custody store + metadata-only evidence projection
  -> supervisor performs authorized CCC query
  -> sanitized immutable child snapshot
  -> leaf analyzes within its profile
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
  transient supervisor UI. The initial release chooses transient UI only; CCC
  stores its commitment and governed `outreach.approve` plus `outreach.send`
  remain disabled.
- Langfuse content capture must be disabled until Yager's metadata-only privacy
  profile is implemented and verified. The Relationship Scout is blocked from
  controlled validation until that gate passes.

## Outbound approval boundary

The initial supervisor may programmatically prepare a draft, but it may not
approve or send one. The operator reviews the full rendered content, channel,
recipient, Lead, evidence, and commitment, then sends manually. The controlled
vertical records the preparation commitment and may record a non-authoritative
operator annotation; it does not invoke `outreach.approve` or claim governed
send authority.

Manual delivery remains unverified until the operator attaches provider-side
delivery evidence; it never produces an automated-send receipt. Enabling
`outreach.approve` and `outreach.send` requires the separately approved
content/action-manifest custody, Forseti/MFAA/Vor/Bifrost convergence, sender
executor, delivery receipt, revocation/expiry/single-use tests, rollback, and
controlled-validation gate.

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
expires_at
workspace_ref
tenant_ref
generator_identity_ref
idempotency_keys[]
proposed_commands[]
evidence_refs[]
redacted_summaries[]
validation_results[]
bundle_digest
```

The bundle is an unexecuted proposal. Importing it later must pass the same
command validation, duplicate detection, qualification, approval, and receipt
rules as a live submission. The importer uses the official SDK only, submits
each closed tagged command with its preserved idempotency key, records the
returned `ContractHandle`, and waits for both the terminal receipt and expected
projection readback before advancing the bundle. Acceptance alone never marks
an item imported. A local file, spreadsheet, HubSpot record, or Yager ledger
never becomes interim funnel authority.

The bundle filesystem contract is fixed by the CCC GTM Wire Contract Design:
operator-owned `0700` directories, `0600` files, no symlinks, exclusive
temporary creation, atomic publication, digest-match idempotency, 30-day pending
expiry unless explicitly extended, and metadata-only disposition retention.

## Failure behavior

- Child timeout, cancellation, malformed output, or profile refusal produces a
  failed task result and no CCC mutation.
- A result without required evidence remains a research lead; the supervisor
  may not upgrade its confidence.
- Duplicate candidates merge by governed identity resolution and retain every
  source observation.
- Stale or contradictory evidence reopens the affected qualification dimension
  and can move an MQL back to nurturing before conversion.
- Booking reconciliation uses a stable provider/event identity digest and a
  distinct observation fingerprint; exact retries reuse a proof while changes
  append one linear supersession chain.
- A command accepted without a completed receipt remains pending, not complete.
- Connector outages degrade only the affected task. They do not erase or
  downgrade canonical CCC records.

## Validation plan

Implementation planning must provide tests for:

1. contract qualification refuses every incomplete BANT combination;
2. W-2 qualification allows evidence-backed inferred Budget or Authority but
   refuses unknown or contradicted dimensions;
3. compensation below the starting target requires a current immutable
   interaction-bound operator override and fresh Forseti decision; missing,
   expired, wrong-Lead, wrong-policy, model-minted, or background-supervisor
   overrides fail;
4. a confirmed booking converts exactly one MQL to exactly one Opportunity;
5. an unqualified booking does not convert or increment the KPI;
6. retries and duplicate source signals do not create duplicate Leads,
   bookings, or Opportunities, while reschedule/cancellation creates exactly
   one next booking observation and cannot fork the chain;
7. child processes cannot write CCC or invoke sender tools;
8. changing draft content invalidates the approval commitment, and CCC cannot
   issue or self-resolve approval authority;
9. CCC and Yager telemetry remain metadata-only without explicit content
   authorization; and
10. intake-bundle import produces the same handles, receipts, refusals, and
    projections as live governed commands;
11. ambiguous identity and cross-tenant resolution fail before qualification,
    deduplication, contact, or conversion; and
12. a conversion remains provable after newer qualification assessments are
    appended because it references an immutable snapshot;
13. operator, current Mimir-resolved durable agent, workload, and session
    identities cannot collapse or substitute for one another, and stale,
    inactive, or package-mismatched Agent resolution fails;
14. a child receives no CCC, Mimir, connector, sender, or delegated domain
    authority and can use only its committed brokered snapshot;
15. `/t/{tenant}`, workspace path, entity ID, and source reference tampering
    cannot change the effective tenant;
16. prepared outreach cannot send without a freshly resolved Forseti decision,
    Vor-signed single-use authority, exact current approval artifact, Bifrost
    enforcement, and an enabled content-custody executor;
17. backup delivery and a scratch restore drill complete before authority
    cutover; and
18. the operator surface distinguishes accepted, in-progress, completed,
    refused, pending-sync, and stale-projection states.

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
- Giving a Yager leaf a CCC, Mimir, source-connector, or sender credential.
- Treating a local path, task ledger, UI state, accepted command, or ClickHouse
  projection as domain authority.
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
2. Implement and validate MIS v2 tenant scope, resolver, migration, and the
   deployed Phase-0 Brynn test before CCC reads or writes trust Mimir.
3. Place this specification in the ratified CCC domain repository and leave a
   deprecated pointer here.
4. Implement control-surface/jobsearch v2 contracts, bindings, fixtures, and
   conformance CI in `ravenhelm-contracts`.
5. Extend the target CCC schema and official SDK contracts for Lead
   compensation override, qualification, identity refusal, versioned booking
   proof, and exact outreach approval.
6. Implement a public-only Signal Scout vertical using unexecuted intake
   bundles.
7. Implement governed CCC command submission, `ContractHandle`, receipt, and
   projection readback.
8. Add BANT analysis and transient draft preparation for exact operator review
   and manual send; keep governed approval reconciliation and automated sending
   disabled.
9. Add the governed Calendar source executor, deterministic reconciliation, and
   MQL conversion.
10. Prove backup delivery, scratch restore, migration rollback, and the full
    deployed evidence chain.
11. Add private relationship metadata only after connector, telemetry, custody,
    and cross-tenant gates pass.
12. Add the W-2 motion after the contract vertical proves the end-to-end KPI.

## Delivery responsibility boundaries

| Responsibility | Owner |
|---|---|
| Specification, architecture, and final adjudication | Supervisor |
| Mimir schema and resolver design | Mimir authority, reviewed by Supervisor |
| Executable wire contracts | `ravenhelm-contracts` authority |
| Bounded implementation | `bounded-implementer` through Dispatch |
| Independent diff and contract verification | `claim-verifier` |
| Live deployment and restore proof | `runtime-verifier` / backup assurance lane |
| PR preparation and CI readback | `delivery-closer`, which never merges |
| Exact PR merge after Nate's direct approval | Supervisor |

This role table governs delivery work; it does not turn role primers into
runtime GTM agents. The product's runtime roles remain the CCC supervisor,
bounded source executors, and leaf analysis tasks defined above.

This sequence optimizes for near-term revenue while keeping the private-data
and outbound boundaries fail-closed.
