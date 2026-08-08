# Ultradex

Ultradex is a private relationship and job-market intelligence service. It is being
extended from contact analysis into a governed job-search tracker that can ingest
opportunities, correlate relationships, support application and outreach workflows,
and project lifecycle state without placing private source content in telemetry.

The platform is API/SDK/CLI driven. User interfaces and agents are consumers of the
same official control surface; they do not bypass it with direct database writes.

## Control surface

```text
Python SDK / Go CLI / MCP / UI
              |
              v
REST commands -> ContractHandleV1 -> durable operation/task
              |
              +-> GraphQL projections and lifecycle reads
              +-> immutable events and execution receipts
              +-> redacted OpenTelemetry projections
```

Current compatibility commands:

- `POST /api/v2/contacts/commands/analyze`
- `POST /api/v2/contacts/commands/sync`

Both return `202 Accepted` with the shared Ravenhelm `ContractHandleV1`. The
`Idempotency-Key` header deduplicates submissions. A legacy query-string `limit`
remains supported for analyze clients; new clients send `{"limit": N}` as JSON.
If queue dispatch fails after durable acceptance, the same schema is returned at
`503` with status `failed`; the SDK preserves that governed outcome.
All domain surfaces require a bearer credential. Actor identity is derived from the
validated credential; caller-supplied `X-Actor-Id` values are ignored.

Governed job-search mutations use
`POST /api/v2/job-search/commands/{command_name}` and the same
`ContractHandleV1` response. The closed command catalog is:

- `sources.ingest`
- `opportunities.create`
- `opportunities.score`
- `applications.transition`
- `relationships.sync`
- `outreach.prepare`
- `outreach.approve`
- `outreach.send`
- `evidence.export`

Call these commands through the official Python SDK methods, which validate the
shared `JobSearchCommandV1` contract before making a REST request. Neither the SDK
nor other clients receive database or NATS credentials.

Read-only lifecycle queries are mounted at `POST /api/graphql`. The official Python
SDK uses GraphQL for operation and event projections. REST v1/v2 operation reads
remain available for compatibility during the migration.

The job-search GraphQL surface is also read-only. It exposes the singular queries
`opportunity`, `application`, `relationship`, and `outreachItem`, plus the bounded
list queries `opportunities`, `applications`, `relationships`, and `outreach`.
List pages return `freshness: null` until a durable projection checkpoint exists;
the service never invents a source position or zero-lag state. Raw connector content
such as Gmail bodies, LinkedIn messages, Dex notes, resumes, prompts, completions,
drafts, and outreach text is never persisted or returned by these projections.

## Career Command Center glass (local Svelte)

The career Director surface is **`apps/web`** — a minimal SvelteKit static SPA in a
local container. It consumes `@ultradex/sdk` and `@ravenhelm/ui-svelte`. ML and
scoring stay on the Python Ultradex worker.

```bash
npm install
npm run build --workspace=@ultradex/sdk
npm run dev --workspace=ccc-glass
```

See [apps/web/README.md](apps/web/README.md).

## Obsidian operator client (DEPRECATED)

**Frozen 2026-08-05** (ADR-014 amendment). Obsidian is not the career Director.
See `integrations/obsidian-ultradex/DEPRECATED.md`. Historical docs remain at
[Ultradex Obsidian Operator](docs/obsidian-operator.md).

## Python SDK

```python
from ultradex_sdk import UltradexClient

async with UltradexClient(
    "http://localhost:8000",
    api_key="...",  # injected from 1Password-backed environment configuration
) as client:
    handle = await client.submit_analyze_contacts(
        limit=50,
        idempotency_key="analysis-2026-07-22",
    )
    operation = await client.get_operation(handle.operation_id)
```

The existing `analyze_contacts()` and `sync_contacts()` SDK methods remain blocking
submit-and-poll wrappers. Job-search command methods include
`submit_sources_ingest()`, `submit_opportunity_create()`,
`submit_opportunity_score()`, `submit_application_transition()`,
`submit_relationship_sync()`, `submit_outreach_prepare()`,
`submit_outreach_approve()`, `submit_outreach_send()`, and
`submit_evidence_export()`. See [SDK_README.md](SDK_README.md).

## Job-search runtime

NATS JetStream carries durable command and lifecycle facts on the bounded subjects
`ultradex.jobsearch.commands.v1.*` and `ultradex.jobsearch.events.v1.*`. The
`jobsearch-worker` is a separate durable pull consumer; the existing Redis/ARQ
`worker` remains unchanged for contact-analysis compatibility. Accepted commands
and unpublished lifecycle events form a database-backed outbox. The worker drains
that outbox before consuming tasks, so a process crash between the database commit
and JetStream publication is recovered with the original NATS deduplication ID.

Every terminal job-search outcome commits its lifecycle event, projection
checkpoint, and signed `accountability.v1` execution receipt in one database
transaction before the worker acknowledges the message. Execution holds the
operation transaction through the domain mutation, serializing duplicate deliveries
before they can repeat a side effect. Receipts contain opaque or pairwise references
and HMAC commitments, not private source content.

The command runtime is intentionally fail-closed. Gmail, LinkedIn, Dex, scoring,
relationship-resolution, and message-delivery adapters remain unbound until their
bounded implementation units land. Commands requiring an unbound adapter produce a
governed refusal; `outreach.send` also requires an exact, unexpired approval matching
the draft commitment and delivery channel.

## Privacy and observability

Ultradex is `private` tier with destination `stays`. Raw Gmail, LinkedIn, Dex,
resume, prompt, draft, and message content is never emitted as telemetry. Metrics use
closed catalogs and bounded labels; governance IDs stay in traces/logs/audit context,
not metric labels. Mutating commands must yield a contract handle, lifecycle events,
and an execution receipt. Telemetry is a derived projection and cannot rewrite
operation truth.

The approved design and bounded work units are recorded in:

- [Job-search platform design](docs/superpowers/specs/2026-07-22-job-search-platform-design.md)
- [Execution manifest](docs/superpowers/plans/2026-07-22-job-search-platform-execution-manifest.md)
- [Ultradex baseline and SDK unit](docs/superpowers/plans/2026-07-22-ultradex-baseline-python-sdk.md)

## Development

Requirements: Python 3.11+, PostgreSQL 14+, Redis, NATS with JetStream, Dex
credentials, an Anthropic credential, `ULTRADEX_API_TOKEN`,
`ULTRADEX_OPERATOR_ID`, and the accountability receipt settings shown in
`.env.example`. Secrets belong in 1Password-backed environment configuration; never
commit them.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
pytest -q
python -m compileall -q api core sdk ultradex_sdk tests migrations
python -m build
python -m pip check
```

Production startup preserves the legacy table bootstrap and then applies the
versioned job-search Alembic revisions. Start the API, the existing ARQ worker, and
the dedicated job-search worker only after PostgreSQL and JetStream report healthy.

Run the service through the repository's managed runtime/deployment configuration.
Node processes, if added, must use PM2 per Ravenhelm standards.

## Delivery sequence

The implemented foundation establishes the contract boundary, packageable Python
SDK, GraphQL read surface, governed job-search commands, durable execution, and
hermetic tests. Subsequent bounded units add:

1. Gmail, LinkedIn-safe, Dex, GitHub, and web ingestion adapters;
2. Go SDK and CLI generated from the same contracts;
3. MCP tools that call the official SDK only;
4. canonical telemetry, audit correlation, and computed blind-spot/broken-binding
   registers.

The existing top-level `mcp` package has a known import collision. Its repair is
strictly deferred to the MCP unit and remains visible as an expected test failure.
