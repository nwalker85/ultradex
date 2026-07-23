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

Read-only lifecycle queries are mounted at `POST /api/graphql`. The official Python
SDK uses GraphQL for operation and event projections. REST v1/v2 operation reads
remain available for compatibility during the migration.

## Python SDK

```python
from ultradex_sdk import UltradexClient

async with UltradexClient("http://localhost:8000") as client:
    handle = await client.submit_analyze_contacts(
        limit=50,
        idempotency_key="analysis-2026-07-22",
    )
    operation = await client.get_operation(handle.operation_id)
```

The existing `analyze_contacts()` and `sync_contacts()` SDK methods remain blocking
submit-and-poll wrappers. See [SDK_README.md](SDK_README.md).

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

Requirements: Python 3.11+, PostgreSQL 14+, Redis, Dex credentials, and an Anthropic
credential. Secrets belong in 1Password-backed environment configuration; never
commit them.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
python -m compileall -q api core sdk tests
python -m build
```

Run the service through the repository's managed runtime/deployment configuration.
Node processes, if added, must use PM2 per Ravenhelm standards.

## Delivery sequence

The baseline currently establishes the contract boundary, packageable Python SDK,
GraphQL read surface, idempotent command compatibility, and hermetic tests. Subsequent
bounded units add:

1. job-search persistence and migrations;
2. governed opportunity, application, relationship, and outreach commands;
3. Gmail, LinkedIn, Dex, GitHub, and web ingestion adapters;
4. Go SDK and CLI generated from the same contracts;
5. MCP tools that call the official SDK only;
6. canonical telemetry, audit correlation, and computed blind-spot/broken-binding
   registers.

The existing top-level `mcp` package has a known import collision. Its repair is
strictly deferred to the MCP unit and remains visible as an expected test failure.
