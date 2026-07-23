# Job Search Intelligence Platform Design

**Status:** Approved by Nate Walker on 2026-07-22

## Purpose

Extend Ultradex into a private, operator-only job-search intelligence platform that mines user-authorized sources, tracks opportunities and applications, supports relationship-aware outreach, and exposes every supported capability through official SDKs. The CLI, agents, automations, and any later UI are SDK consumers; raw APIs and NATS are implementation details.

## Non-negotiable architecture

```text
CLI / agents / n8n / future UI
              |
        official domain SDKs
              |
   +----------+-----------+
REST Command API     GraphQL Query API
   | mutations             | side-effect-free reads
   v                       ^
Gateway -> NATS -> executors -> immutable events and receipts
                         |                    |
                         +-> projections -----+
                         +-> redacted telemetry
```

- Every mutation is an explicit command and returns a `ContractHandle`.
- Acceptance is not completion. Lifecycle events and a durable receipt establish outcome.
- Reads are GraphQL queries over disposable projections and expose source position and freshness.
- The Gateway is the source of truth for accepted or refused intent.
- NATS JetStream is the internal task and lifecycle-fact plane. Clients never receive NATS credentials.
- Observability explains behavior. Audit evidence proves governed action. Neither mints authority.
- The Python SDK serves agents and automation; the Go SDK serves the CLI; a TypeScript SDK is added only with a web client.

## Domain model

### Opportunity

A discovered or manually entered role. It retains normalized employer, title, location, source references, role-family lens, fit score, explanation, risks, and freshness without copying restricted source content into telemetry.

Statuses: `discovered`, `qualified`, `watching`, `archived`.

### Application

The governed pursuit of an opportunity. It owns current stage, stage history, submitted artifact references, next action, deadlines, and relationship links.

Statuses: `draft`, `applied`, `screening`, `interviewing`, `offer`, `accepted`, `rejected`, `withdrawn`, `closed`.

### Relationship

A link to a Dex contact and the contact's relevance to an opportunity. Dex remains the contact system of record; Ultradex stores opaque identifiers, derived relevance, and source freshness.

### Outreach

A prepared message associated with an opportunity and relationship. Drafting, approval, and sending are separate commands. No send is accepted without an unexpired approval contract for the exact message commitment and channel.

Statuses: `draft`, `pending_approval`, `approved`, `sent`, `failed`, `cancelled`.

### Evidence reference

An opaque source reference, classification, timestamp, commitment, and redacted summary. Gmail bodies, LinkedIn messages, Dex notes, resumes, prompts, completions, and outreach text remain in their designated custody systems.

## Command surface

- `sources.ingest`
- `opportunities.create`
- `opportunities.score`
- `applications.transition`
- `relationships.sync`
- `outreach.prepare`
- `outreach.approve`
- `outreach.send`
- `evidence.export`

Commands preserve idempotency, correlation, causation, delegation, classification, and actor context. Refusal is a structured outcome, not a generic exception.

## Query surface

- Opportunity detail and filtered opportunity lists
- Application detail, stage history, and pipeline roll-up
- Relationship context and source freshness
- Outreach queue and approval state
- Operation lifecycle, receipt state, and proof references
- Source ingestion health and projection freshness

Every projected result exposes its source event identity or position, projection timestamp, and lag.

## Source adapters

- Gmail ingestion reads only explicitly authorized job-search mail and stores opaque source references plus normalized facts.
- LinkedIn begins with user-provided URLs, exports, or browser-assisted capture. It does not automate prohibited scraping or sending.
- Dex synchronization uses Dex as the contact system of record.
- Manual and web research ingestion use the same evidence-reference contract.
- All adapters are bounded executors triggered by task contracts, not code embedded in API handlers or clients.

## Observability and audit

The domain uses Ravenhelm's canonical correlation context: tenant, operation, action, task, contract, event, correlation, causation, execution, actor, delegation, request, trace, span, session, and audit references plus service version and deployment identity.

Routine telemetry contains bounded states, counts, durations, hashes, commitments, and opaque references. It never contains raw source content or unbounded identifiers as Prometheus labels.

Minimum monitoring intent covers:

- service availability;
- connector and scheduled-job availability, performance, and security;
- queue, worker, and projection lag;
- model-run performance, cost, and governance;
- missing terminal events, receipts, or authority evidence;
- redaction and classification violations;
- watcher self-health.

Every census entity and concern has a triplet or a reasoned Blind Spot. Every triplet binds at least one live function, alert route, dashboard, and runbook. Broken Bindings and Blind Spots are computed.

## Privacy boundary

The domain is `private`, `operator-only`, and assigned to proposed `private-estate` until ratified. Its default destination is `stays`. Only sanitized aggregate health and opaque proof references may project into fleet-wide surfaces. Shared agent memory contains user-approved derived career context, never raw mailbox, direct-message, contact-note, or outreach content.

## Delivery units

1. Canonical control-surface and job-search contracts.
2. Python observability correlation and redaction conformance.
3. Go observability instrumentation package.
4. Ultradex baseline repair and official Python SDK.
5. Job-search persistence, commands, queries, and projections.
6. Gmail, LinkedIn-safe, Dex, and manual adapters.
7. Go SDK and CLI migration.
8. MCP, agent, and automation migration.
9. Event-to-telemetry projector, dashboards, alerts, and runbooks.
10. Computed registers and end-to-end conformance.

Each unit uses a dedicated worktree, produces one reviewable PR, and has a red-green test cycle. No PR is merged without explicit PR-specific approval.

